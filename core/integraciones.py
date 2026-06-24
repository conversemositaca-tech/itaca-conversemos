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

from pacientes.models import Atencion, Paciente
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


class NotaVozView(_Base):
    """Guarda una atención en la historia clínica desde Eli.
    POST /api/integraciones/nota-voz/
    body: {telefono, paciente_id, tipo, ...}
      - Nota guiada (Eli pregunta): resumen, aspectos, objetivos, recomendaciones.
      - Legado (una sola dictada): transcripcion.
    Los 4 campos guiados se mapean a la ficha según el tipo."""

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

        resumen, aspectos = g("resumen"), g("aspectos")
        objetivos, recomendaciones = g("objetivos"), g("recomendaciones")
        transcripcion = g("transcripcion")

        marca = "🎙️ Registrado por voz vía WhatsApp."
        campos = dict(clinica=psico.clinica, paciente=paciente, medico=psico,
                      registrado_por=psico, tipo=tipo, especialidad=psico.especialidad or "")

        if resumen or aspectos or objetivos or recomendaciones:
            # Nota guiada: cada respuesta a su campo de la ficha (según el tipo).
            campos["nota"] = (marca + "\n\n" + resumen).strip() if resumen else marca
            campos["indicaciones"] = recomendaciones
            if tipo == Atencion.Tipo.EVOLUCION:
                campos["puntos_importantes"] = aspectos
                campos["proximos_pasos"] = objetivos
            else:
                campos["aspectos_historicos"] = aspectos
                campos["objetivos"] = objetivos
        elif transcripcion:
            campos["nota"] = marca + "\n\n" + transcripcion
        else:
            return Response({"ok": False, "detail": "No hay contenido para guardar."},
                            status=status.HTTP_400_BAD_REQUEST)

        atencion = Atencion.objects.create(**campos)
        return Response(
            {"ok": True, "atencion_id": atencion.id, "paciente": paciente.nombre,
             "tipo": atencion.get_tipo_display()},
            status=status.HTTP_201_CREATED,
        )
