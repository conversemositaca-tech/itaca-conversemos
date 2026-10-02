"""Historial de consentimiento de comunicaciones: otorgar, revocar, consultar.

Todo pasa por aquí para que el historial sea siempre el mismo: filas nuevas,
nunca ediciones, y el estado vigente es el del evento más reciente de la
persona (sumando paciente y leads que se le convirtieron).
"""
from django.db import transaction
from django.utils import timezone

from correo import textos
from correo.models import ConsentimientoComunicacion as CC

FINALIDADES = {CC.Finalidad.MARKETING, CC.Finalidad.ASISTENCIAL}


def ultimo_evento(dest, finalidad):
    return (CC.objects.filter(dest.filtro(), clinica=dest.clinica, finalidad=finalidad,
                              canal=CC.Canal.CORREO)
            .order_by("-fecha", "-id").first())


def estado_vigente(dest, finalidad):
    """OTORGADO, REVOCADO o "" (nunca se pidió)."""
    ev = ultimo_evento(dest, finalidad)
    return ev.estado if ev else ""


def tiene_consentimiento(dest, finalidad):
    return estado_vigente(dest, finalidad) == CC.Estado.OTORGADO


def _ip_y_agente(request):
    if request is None:
        return None, ""
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip = fwd.split(",")[0].strip() if fwd else (request.META.get("REMOTE_ADDR") or None)
    return ip or None, (request.META.get("HTTP_USER_AGENT") or "")[:400]


def otorgar(dest, origen, *, finalidad=CC.Finalidad.MARKETING, request=None, usuario=None,
            version=None, texto=None):
    """Registra un otorgamiento. Sin correo en la ficha no hay nada que autorizar."""
    if finalidad not in FINALIDADES:
        raise ValueError("Finalidad desconocida.")
    correo = dest.correo()
    if not correo:
        return None
    ip, agente = _ip_y_agente(request)
    with transaction.atomic():
        nuevo = CC.objects.create(
            **dest.identidad(), canal=CC.Canal.CORREO, finalidad=finalidad,
            estado=CC.Estado.OTORGADO, origen=origen,
            version_texto=version or textos.CONSENTIMIENTO_MARKETING_VERSION,
            texto_aceptado=texto or textos.CONSENTIMIENTO_MARKETING_TEXTO,
            correo=correo, fecha=timezone.now(), ip=ip, user_agent=agente,
            registrado_por=usuario)
        if finalidad == CC.Finalidad.MARKETING:
            from correo.services import preferencias
            preferencias.desbloquear_marketing(dest)
    return nuevo


def revocar(dest, origen, *, finalidad=CC.Finalidad.MARKETING, request=None, usuario=None):
    """Registra una revocación. Idempotente: si ya estaba revocado, no duplica.

    Revocar MARKETING también bloquea los envíos comerciales en las
    preferencias, aunque nunca se hubiera otorgado (una baja vale siempre).
    """
    if finalidad not in FINALIDADES:
        raise ValueError("Finalidad desconocida.")
    ip, agente = _ip_y_agente(request)
    with transaction.atomic():
        if finalidad == CC.Finalidad.MARKETING:
            from correo.services import preferencias
            preferencias.bloquear_marketing(dest)
        previo = ultimo_evento(dest, finalidad)
        if previo is None or previo.estado == CC.Estado.REVOCADO:
            return previo
        return CC.objects.create(
            **dest.identidad(), canal=CC.Canal.CORREO, finalidad=finalidad,
            estado=CC.Estado.REVOCADO, origen=origen,
            version_texto=previo.version_texto, correo=dest.correo(),
            fecha=timezone.now(), ip=ip, user_agent=agente, registrado_por=usuario,
            consentimiento_previo=previo)


def resumen(dest):
    """Lo que el panel muestra del consentimiento comercial de una persona."""
    ev = ultimo_evento(dest, CC.Finalidad.MARKETING)
    if ev is None:
        return {"estado": "NO_OTORGADO", "estado_label": "No otorgado",
                "fecha": None, "origen": "", "origen_label": "", "version": ""}
    return {
        "estado": ev.estado,
        "estado_label": "Otorgado" if ev.estado == CC.Estado.OTORGADO else "Revocado",
        "fecha": ev.fecha.isoformat(),
        "origen": ev.origen,
        "origen_label": ev.get_origen_display(),
        "version": ev.version_texto,
    }
