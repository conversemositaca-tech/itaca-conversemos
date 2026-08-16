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
import re
from datetime import date, timedelta

from django.conf import settings
from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from django.utils import timezone

from core import estructurar_nota
from pacientes.models import Atencion, Cita, ObjetivoTerapeutico, Paciente
from pacientes.recordatorios import enviar_recordatorios
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


_DIAS_SEMANA = {
    "lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2, "jueves": 3,
    "viernes": 4, "sabado": 5, "sábado": 5, "domingo": 6,
}
_ETIQUETA_DIA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _fecha_de_pregunta(t):
    """Detecta de qué FECHA pregunta el psicólogo: hoy, mañana, pasado mañana, un
    día de la semana ('el viernes') o dd/mm. Devuelve (date, etiqueta) o None."""
    hoy = timezone.localdate()
    if re.search(r"pasado\s*ma[nñ]ana", t):
        return hoy + timedelta(days=2), "pasado mañana"
    if re.search(r"\bma[nñ]ana\b", t):
        return hoy + timedelta(days=1), "mañana"
    if re.search(r"\bhoy\b", t):
        return hoy, "hoy"
    for nombre, idx in _DIAS_SEMANA.items():
        if re.search(rf"\b{nombre}\b", t):
            delta = (idx - hoy.weekday()) % 7  # 0 = hoy mismo (ese día ya es hoy)
            f = hoy + timedelta(days=delta)
            return f, f"el {_ETIQUETA_DIA[idx]} {f:%d/%m}"
    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", t)
    if m:
        d, mes = int(m.group(1)), int(m.group(2))
        anio = int(m.group(3)) if m.group(3) else hoy.year
        if anio < 100:
            anio += 2000
        try:
            return date(anio, mes, d), f"el {d:02d}/{mes:02d}"
        except ValueError:
            pass
    return None


def _agenda_de(psico, fecha):
    return (Cita.objects.filter(clinica=psico.clinica, medico=psico, inicio__date=fecha)
            .exclude(estado=Cita.Estado.CANCELADA).select_related("paciente").order_by("inicio"))


def _linea_cita(c):
    mod = " (virtual)" if getattr(c, "modalidad", "") == "virtual" else ""
    return f"• {timezone.localtime(c.inicio):%H:%M} — {c.paciente.nombre}{mod}"


def _responder_consulta(psico, pregunta):
    """Responde en texto (formato WhatsApp) una pregunta del psicólogo sobre SUS
    datos reales: pacientes activos, su agenda (hoy, mañana, un día concreto o la
    semana), pacientes sin próxima cita. Todo acotado a su clínica."""
    t = (pregunta or "").lower()
    mis_pac = Paciente.objects.filter(clinica=psico.clinica, profesional__usuario=psico)

    # 1) Pacientes sin próxima cita (para reactivar) — antes que la agenda, porque
    #    "sin cita" contiene la palabra "cita".
    if any(k in t for k in ["sin proxima", "sin próxima", "reactivar", "retencion", "retención", "sin cita", "no tienen cita"]):
        con_futura = set(
            Cita.objects.filter(clinica=psico.clinica, medico=psico, inicio__gte=timezone.now())
            .exclude(estado=Cita.Estado.CANCELADA).values_list("paciente_id", flat=True))
        sin = mis_pac.exclude(frecuencia=Paciente.Frecuencia.ALTA).exclude(id__in=con_futura).order_by("nombre")
        n = sin.count()
        if not n:
            return "Todos tus pacientes activos tienen próxima cita agendada. 👏"
        nombres = list(sin.values_list("nombre", flat=True)[:15])
        cuerpo = "\n".join(f"• {x}" for x in nombres)
        extra = f"\n… y {n - 15} más." if n > 15 else ""
        return f"*{n}* paciente(s) sin próxima cita (conviene reagendar):\n{cuerpo}{extra}"

    # 2) Agenda de la semana ("qué tengo esta semana")
    es_agenda = any(k in t for k in ["agenda", "sesion", "sesión", "cita", "agendad"])
    if "semana" in t and (es_agenda or "tengo" in t or "paciente" in t or len(t) <= 25):
        hoy = timezone.localdate()
        bloques, total = [], 0
        for i in range(7):
            f = hoy + timedelta(days=i)
            citas = list(_agenda_de(psico, f)[:25])
            if not citas:
                continue
            total += len(citas)
            dia = "Hoy" if i == 0 else ("Mañana" if i == 1 else _ETIQUETA_DIA[f.weekday()].capitalize())
            bloques.append(f"*{dia} {f:%d/%m}*\n" + "\n".join(_linea_cita(c) for c in citas))
        if not total:
            return "No tienes sesiones agendadas en los próximos 7 días. 🌿"
        return f"Tu semana ({total} sesión(es)):\n\n" + "\n\n".join(bloques)

    # 3) Agenda por FECHA: "hoy", "mañana", "el viernes", "25/07"… Si menciona una
    #    fecha (aunque diga "pacientes tengo mañana"), es una consulta de agenda.
    fecha_et = _fecha_de_pregunta(t)
    if fecha_et or es_agenda:
        fecha, etiqueta = fecha_et if fecha_et else (timezone.localdate(), "hoy")
        citas = _agenda_de(psico, fecha)
        n = citas.count()
        etiqueta_cap = etiqueta[0].upper() + etiqueta[1:]
        if not n:
            return (f"{etiqueta_cap} no tienes sesiones agendadas. 🌿\n\n"
                    "_También puedes preguntarme por otro día: mañana, el viernes, 25/07 o \"esta semana\"._")
        cuerpo = "\n".join(_linea_cita(c) for c in citas[:25])
        return f"{etiqueta_cap} tienes *{n}* sesión(es):\n{cuerpo}"

    # 4) Pacientes activos (por defecto para preguntas de "pacientes"/"cartera")
    if any(k in t for k in ["activ", "paciente", "cartera", "cuantos", "cuántos", "tengo"]):
        activos = mis_pac.exclude(frecuencia=Paciente.Frecuencia.ALTA).order_by("nombre")
        n = activos.count()
        if not n:
            return "No tienes pacientes activos asignados por ahora."
        nombres = list(activos.values_list("nombre", flat=True)[:15])
        cuerpo = "\n".join(f"• {x}" for x in nombres)
        extra = f"\n… y {n - 15} más." if n > 15 else ""
        return f"Tienes *{n}* paciente(s) activo(s):\n{cuerpo}{extra}"

    # Fallback: qué puede responder
    return ("Puedo darte datos rápidos de tu consulta. Pregúntame, por ejemplo:\n"
            "• ¿Qué sesiones tengo hoy? ¿Y mañana? ¿Y el viernes?\n"
            "• ¿Qué tengo esta semana?\n"
            "• ¿Qué pacientes tengo activos?\n"
            "• ¿Qué pacientes están sin próxima cita?\n\n"
            "O envíame la nota (texto o voz) para *registrar una sesión*.")


class ConsultaView(_Base):
    """Responde preguntas rápidas del psicólogo con sus datos reales.
    POST /api/integraciones/consulta/  body: {telefono, pregunta}"""

    def post(self, request):
        d = request.data if isinstance(request.data, dict) else {}
        psico = _psicologo_por_telefono(d.get("telefono"))
        if psico is None:
            return Response({"ok": False, "detail": "Número no autorizado."},
                            status=status.HTTP_403_FORBIDDEN)
        pregunta = (d.get("pregunta") or "").strip()
        return Response({"ok": True, "respuesta": _responder_consulta(psico, pregunta)})


class ResumenDiarioView(_Base):
    """Agenda del día de TODOS los psicólogos activos con teléfono registrado,
    para que Eli les envíe su recordatorio automático de la mañana.
    GET /api/integraciones/resumen-dia/?fecha=YYYY-MM-DD  (sin fecha = hoy)"""

    def get(self, request):
        f = (request.query_params.get("fecha") or "").strip()
        try:
            y, m, d = [int(x) for x in f.split("-")]
            fecha = date(y, m, d)
        except (ValueError, TypeError, AttributeError):
            fecha = timezone.localdate()
        out = []
        for u in Usuario.objects.filter(rol=Usuario.Rol.MEDICO, is_active=True).exclude(telefono=""):
            citas = _agenda_de(u, fecha)
            out.append({
                "telefono": _solo_digitos(u.telefono),
                "nombre": u.nombre or u.email,
                "citas": [{
                    "hora": f"{timezone.localtime(c.inicio):%H:%M}",
                    "paciente": c.paciente.nombre,
                    "modalidad": getattr(c, "modalidad", "") or "",
                } for c in citas[:30]],
            })
        return Response({"ok": True, "fecha": fecha.isoformat(), "psicologos": out})


class RecordatoriosView(_Base):
    """Dispara el envío de los recordatorios de las citas del día.

    Existe para que un cron en la nube (kira-bot) los mande cada mañana, en vez
    de depender de una tarea programada en la computadora de alguien: si esa
    computadora está apagada, ese día nadie recibe su recordatorio.

    POST /api/integraciones/recordatorios/
      body opcional: {"fecha": "YYYY-MM-DD", "dry": true}

    Es seguro llamarlo de más: solo toma las citas que aún no fueron recordadas,
    así que una segunda llamada el mismo día no reenvía nada.
    """

    def post(self, request):
        d = request.data if isinstance(request.data, dict) else {}
        f = (d.get("fecha") or "").strip()
        try:
            y, m, dd = [int(x) for x in f.split("-")]
            fecha = date(y, m, dd)
        except (ValueError, TypeError, AttributeError):
            fecha = timezone.localdate()
        res = enviar_recordatorios(fecha=fecha, dry=bool(d.get("dry")))
        return Response({"ok": True, **res})


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
                campos["motivo"] = cg("motivo")[:300]  # Atencion.motivo es CharField(300)
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
                campos["motivo"] = (est.get("motivo", "") or "")[:300]  # CharField(300)
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
