"""Integración con Eli (bot de WhatsApp): notas clínicas por voz.

Endpoints servidor-a-servidor, autenticados por un token compartido
(`ITACA_INTEGRACION_TOKEN`, cabecera `X-Integracion-Token`), para que Eli pueda:
  1. saber si un número de WhatsApp es una psicóloga registrada,
  2. buscar un paciente por nombre o documento, y
  3. guardar la transcripción de la sesión como una atención (historia clínica).

La psicóloga se identifica por su teléfono (`usuarios.Usuario.telefono`); de ahí
sale la clínica, y TODO se filtra/crea con esa clínica explícitamente (aislamiento
multitenant · Ley 29733). No dependemos del middleware de tenant porque estas
rutas no tienen usuario logueado.
"""
from django.conf import settings
from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from core import estructurar_nota
from pacientes.models import Atencion, ObjetivoTerapeutico, Paciente
from usuarios.models import Usuario


def _solo_digitos(s):
    return "".join(ch for ch in (s or "") if ch.isdigit())


def _token_esperado():
    return (getattr(settings, "ITACA_INTEGRACION_TOKEN", "") or "").strip()


class TokenIntegracion(BasePermission):
    """Permite el acceso solo si la cabecera trae el token compartido correcto.
    Si no hay token configurado en el servidor, la integración queda apagada."""

    message = "Token de integración inválido."

    def has_permission(self, request, view):
        esperado = _token_esperado()
        if not esperado:
            return False
        enviado = (request.headers.get("X-Integracion-Token") or "").strip()
        return bool(enviado) and enviado == esperado


def _psicologo_por_telefono(telefono):
    """Usuario médico activo cuyo teléfono coincide por los últimos 9 dígitos
    (formato peruano). Devuelve None si no hay coincidencia."""
    suf = _solo_digitos(telefono)[-9:]
    if len(suf) < 9:
        return None
    for u in Usuario.objects.filter(rol=Usuario.Rol.MEDICO, is_active=True).exclude(telefono=""):
        if _solo_digitos(u.telefono).endswith(suf):
            return u
    return None


def _paciente_payload(p):
    return {
        "id": p.id,
        "nombre": p.nombre,
        "documento": p.numero_documento or "",
        "sede": p.get_sede_display() if p.sede else "",
    }


class _Base(APIView):
    authentication_classes = []          # servidor-a-servidor: sin sesión ni CSRF
    permission_classes = [TokenIntegracion]


class PsicologoView(_Base):
    """¿El número de WhatsApp es de una psicóloga registrada?
    GET /api/integraciones/psicologo/?telefono=51961211614"""

    def get(self, request):
        psico = _psicologo_por_telefono(request.query_params.get("telefono"))
        if psico is None:
            return Response({"ok": False})
        return Response({
            "ok": True,
            "id": psico.id,
            "nombre": psico.nombre or psico.email,
            "clinica": psico.clinica_id,
        })


class PacientesBuscarView(_Base):
    """Busca pacientes (de la clínica de la psicóloga) por nombre o documento.
    GET /api/integraciones/pacientes/?telefono=...&q=Juan"""

    def get(self, request):
        psico = _psicologo_por_telefono(request.query_params.get("telefono"))
        if psico is None:
            return Response({"ok": False, "detail": "Número no autorizado."},
                            status=status.HTTP_403_FORBIDDEN)
        q = (request.query_params.get("q") or "").strip()
        if len(q) < 2:
            return Response({"ok": True, "pacientes": []})
        digitos = _solo_digitos(q)
        filtro = Q(nombre__icontains=q)
        if digitos:
            filtro |= Q(numero_documento__icontains=digitos)
        pacientes = (
            Paciente.objects.filter(clinica=psico.clinica)
            .filter(filtro)
            .order_by("nombre")[:8]
        )
        return Response({"ok": True, "pacientes": [_paciente_payload(p) for p in pacientes]})


def _norm_riesgo(s):
    s = (s or "").lower()
    if "alto" in s:
        return "alto"
    if "moder" in s:
        return "moderado"
    if "bajo" in s or "baja" in s or "sin riesgo" in s or "ningun" in s:
        return "bajo"
    return ""


def _contexto_paciente(paciente):
    """Resumen breve del proceso del paciente, para que la evolución sea coherente
    con la historia clínica ya registrada."""
    partes = []
    if paciente.resumen_clinico:
        partes.append("Resumen clínico: " + paciente.resumen_clinico)
    if paciente.objetivo_principal:
        partes.append("Objetivo principal: " + paciente.objetivo_principal)
    hist = paciente.atenciones.filter(tipo=Atencion.Tipo.HISTORIA).order_by("-fecha").first()
    if hist:
        if hist.objetivos:
            partes.append("Objetivos del proceso: " + hist.objetivos)
        if hist.aspectos_historicos:
            partes.append("Antecedentes: " + hist.aspectos_historicos)
    evo = paciente.atenciones.filter(tipo=Atencion.Tipo.EVOLUCION).order_by("-fecha").first()
    if evo and evo.proximos_pasos:
        partes.append("Próximos pasos de la última sesión: " + evo.proximos_pasos)
    return "\n".join(partes).strip()


def _autoalimentar_perfil(paciente, est):
    """Historia clínica → alimenta las tarjetas del perfil (resumen, objetivo, riesgo)
    y crea los objetivos terapéuticos. Es el 'documento madre' (pedido de Emma)."""
    cambios = []
    if est.get("resumen_clinico"):
        paciente.resumen_clinico = est["resumen_clinico"][:4000]
        cambios.append("resumen_clinico")
    lineas = [l.strip(" -•\t") for l in (est.get("objetivos") or "").splitlines() if l.strip(" -•\t")]
    if lineas:
        paciente.objetivo_principal = lineas[0][:200]
        cambios.append("objetivo_principal")
    riesgo = _norm_riesgo(est.get("riesgo"))
    if riesgo:
        paciente.riesgo = riesgo
        cambios.append("riesgo")
    if cambios:
        paciente.save(update_fields=cambios)
    if lineas:
        existentes = {o.texto.strip().lower() for o in paciente.objetivos.all()}
        for l in lineas[:8]:
            if l.strip().lower() not in existentes:
                ObjetivoTerapeutico.objects.create(clinica=paciente.clinica, paciente=paciente, texto=l[:200])
                existentes.add(l.strip().lower())


class ContextoView(_Base):
    """Contexto clínico breve de un paciente, para que Eli lo muestre antes de
    registrar una evolución. GET /api/integraciones/contexto/?telefono&paciente_id"""

    def get(self, request):
        psico = _psicologo_por_telefono(request.query_params.get("telefono"))
        if psico is None:
            return Response({"ok": False, "detail": "Número no autorizado."}, status=status.HTTP_403_FORBIDDEN)
        paciente = Paciente.objects.filter(clinica=psico.clinica, id=request.query_params.get("paciente_id")).first()
        if paciente is None:
            return Response({"ok": False, "detail": "Paciente no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            "ok": True,
            "paciente": paciente.nombre,
            "tiene_historia": paciente.atenciones.filter(tipo=Atencion.Tipo.HISTORIA).exists(),
            "resumen": paciente.resumen_clinico or "",
            "objetivo": paciente.objetivo_principal or "",
            "riesgo": paciente.get_riesgo_display() if paciente.riesgo else "",
            "contexto": _contexto_paciente(paciente),
        })


class NotaVozView(_Base):
    """Guarda una atención en la historia clínica desde Eli.
    POST /api/integraciones/nota-voz/  body: {telefono, paciente_id, tipo, contenido}
      - `contenido`: la nota cruda (dictada o escrita). El servidor la ESTRUCTURA
        con IA según el tipo (historia|evolucion). Para evolución usa la historia
        previa como contexto. Si es historia, ADEMÁS alimenta el perfil del paciente
        (resumen clínico, objetivo principal, riesgo, objetivos terapéuticos).
      - Legado: {resumen, aspectos, objetivos, recomendaciones} o {transcripcion}.
    Devuelve un extracto de lo guardado para que Eli lo confirme."""

    def post(self, request):
        d = request.data if isinstance(request.data, dict) else {}
        psico = _psicologo_por_telefono(d.get("telefono"))
        if psico is None:
            return Response({"ok": False, "detail": "Número no autorizado."},
                            status=status.HTTP_403_FORBIDDEN)

        paciente = Paciente.objects.filter(clinica=psico.clinica, id=d.get("paciente_id")).first()
        if paciente is None:
            return Response({"ok": False, "detail": "Paciente no encontrado en tu clínica."},
                            status=status.HTTP_404_NOT_FOUND)

        tipo = d.get("tipo") if d.get("tipo") in dict(Atencion.Tipo.choices) else Atencion.Tipo.EVOLUCION

        def g(k):
            return (d.get(k) or "").strip()

        marca = "🎙️ Registrado por voz vía WhatsApp."
        campos = dict(clinica=psico.clinica, paciente=paciente, medico=psico,
                      registrado_por=psico, tipo=tipo, especialidad=psico.especialidad or "")
        contenido = g("contenido")
        campos_guiados = d.get("campos") if isinstance(d.get("campos"), dict) else None
        est = None
        extracto = {}

        if campos_guiados:
            # Registro GUIADO desde Eli: cada campo va a su lugar (sin IA).
            def cg(k):
                return (campos_guiados.get(k) or "").strip()
            if tipo == Atencion.Tipo.HISTORIA:
                campos["nota"] = (marca + "\n\n" + cg("resumen")).strip()
                campos["motivo"] = cg("motivo")
                campos["aspectos_historicos"] = cg("antecedentes")
                campos["objetivos"] = cg("objetivos")
                campos["indicaciones"] = cg("recomendaciones")
                # Alimenta el perfil (resumen, objetivo, riesgo) como el documento madre.
                est = {"resumen_clinico": cg("resumen"), "objetivos": cg("objetivos"), "riesgo": cg("riesgo")}
                extracto = {"resumen": cg("resumen"), "riesgo": _norm_riesgo(cg("riesgo"))}
            else:
                partes = []
                if cg("cambios"):
                    partes.append("Cambios desde la última sesión: " + cg("cambios"))
                if cg("temas"):
                    partes.append("Temas trabajados: " + cg("temas"))
                if cg("intervenciones"):
                    partes.append("Intervenciones del terapeuta: " + cg("intervenciones"))
                campos["nota"] = (marca + ("\n\n" + "\n".join(partes) if partes else "")).strip()
                campos["puntos_importantes"] = cg("avances")
                campos["indicaciones"] = cg("tareas")
                campos["proximos_pasos"] = cg("siguiente")
                extracto = {"resumen": cg("cambios") or cg("temas")}
        elif contenido:
            contexto = _contexto_paciente(paciente) if tipo == Atencion.Tipo.EVOLUCION else ""
            est = estructurar_nota.estructurar(contenido, tipo, contexto)
            if est and tipo == Atencion.Tipo.HISTORIA:
                campos["nota"] = (marca + "\n\n" + (est.get("resumen_clinico") or "")).strip()
                campos["motivo"] = est.get("motivo", "")
                campos["aspectos_historicos"] = est.get("aspectos_historicos", "")
                campos["objetivos"] = est.get("objetivos", "")
                campos["diagnostico"] = est.get("diagnostico", "")
                extracto = {"resumen": est.get("resumen_clinico", ""),
                            "objetivos": est.get("objetivos", ""),
                            "riesgo": _norm_riesgo(est.get("riesgo"))}
            elif est:
                campos["nota"] = (marca + "\n\n" + (est.get("nota") or "")).strip()
                campos["puntos_importantes"] = est.get("puntos_importantes", "")
                campos["proximos_pasos"] = est.get("proximos_pasos", "")
                campos["indicaciones"] = est.get("indicaciones", "")
                extracto = {"resumen": est.get("nota", ""),
                            "puntos": est.get("puntos_importantes", ""),
                            "proximos": est.get("proximos_pasos", "")}
            else:
                # Sin IA disponible: guardamos el crudo en la nota (el terapeuta edita).
                campos["nota"] = marca + "\n\n" + contenido
                extracto = {"resumen": contenido}
        else:
            # ── Legado: campos guiados o transcripción cruda ──
            resumen, aspectos = g("resumen"), g("aspectos")
            objetivos, recomendaciones = g("objetivos"), g("recomendaciones")
            transcripcion = g("transcripcion")
            if resumen or aspectos or objetivos or recomendaciones:
                campos["nota"] = (marca + "\n\n" + resumen).strip() if resumen else marca
                campos["indicaciones"] = recomendaciones
                if tipo == Atencion.Tipo.EVOLUCION:
                    campos["puntos_importantes"] = aspectos
                    campos["proximos_pasos"] = objetivos
                else:
                    campos["aspectos_historicos"] = aspectos
                    campos["objetivos"] = objetivos
                extracto = {"resumen": resumen}
            elif transcripcion:
                campos["nota"] = marca + "\n\n" + transcripcion
                extracto = {"resumen": transcripcion}
            else:
                return Response({"ok": False, "detail": "No hay contenido para guardar."},
                                status=status.HTTP_400_BAD_REQUEST)

        atencion = Atencion.objects.create(**campos)
        if tipo == Atencion.Tipo.HISTORIA and est:
            _autoalimentar_perfil(paciente, est)

        return Response(
            {"ok": True, "atencion_id": atencion.id, "paciente": paciente.nombre,
             "tipo": atencion.get_tipo_display(), "extracto": extracto,
             "perfil_actualizado": bool(tipo == Atencion.Tipo.HISTORIA and est)},
            status=status.HTTP_201_CREATED,
        )
