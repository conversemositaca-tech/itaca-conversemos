"""Lógica de envío de mensajes: registra en la bitácora y envía por WhatsApp."""
from .evolution import enviar_texto, wa_link
from .models import Mensaje


def registrar_y_enviar(clinica, *, telefono, texto, tipo, paciente=None, cita=None, usuario=None):
    """Intenta enviar por WhatsApp y deja registro en la bitácora.

    Devuelve (mensaje, resultado, wa_url). `wa_url` es el enlace de respaldo
    (wa.me) cuando el envío automático no salió (sin configurar o falló).
    """
    resultado = enviar_texto(clinica, telefono, texto)
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
