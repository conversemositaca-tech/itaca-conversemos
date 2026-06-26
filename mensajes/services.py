"""Lógica de envío de mensajes: registra en la bitácora y envía por WhatsApp.

Orden de envío:
1. WhatsApp Cloud API (Meta) eligiendo el número por la SEDE del paciente,
   si hay un número configurado en "Conexión WhatsApp".
2. Evolution API, si la Cloud API no está configurada.
3. Enlace wa.me de respaldo (lo arma quien recibe el resultado) cuando ninguno
   envió de forma automática.
"""
from . import cloud_api
from .evolution import enviar_texto as enviar_evolution, wa_link
from .models import Mensaje


def _sede_de(paciente, cita):
    if paciente is not None and getattr(paciente, "sede", ""):
        return paciente.sede
    if cita is not None and getattr(cita, "sede", ""):
        return cita.sede
    return ""


def registrar_y_enviar(clinica, *, telefono, texto, tipo, paciente=None, cita=None, usuario=None):
    """Intenta enviar por WhatsApp y deja registro en la bitácora.

    Devuelve (mensaje, resultado, wa_url). `wa_url` es el enlace de respaldo
    (wa.me) cuando el envío automático no salió (sin configurar o falló).
    """
    sede = _sede_de(paciente, cita)
    if cloud_api.esta_configurado(clinica, sede):
        resultado = cloud_api.enviar_texto(clinica, telefono, texto, sede=sede)
    else:
        resultado = enviar_evolution(clinica, telefono, texto)

    mensaje = Mensaje.objects.create(
        clinica=clinica,
        paciente=paciente,
        cita=cita,
        telefono=telefono or "",
        texto=texto,
        tipo=tipo,
        estado=resultado["estado"],
        detalle=resultado.get("detalle", "")[:300],
        enviado_por=usuario,
    )
    wa_url = wa_link(telefono, texto) if resultado["estado"] != "enviado" else None
    return mensaje, resultado, wa_url
