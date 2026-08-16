"""Envío de los recordatorios de WhatsApp de las citas de un día.

Vive aparte del management command porque lo disparan dos caminos: el comando
(a mano o por tarea programada) y el endpoint de integraciones, que es el que
permite que un cron en la nube lo llame sin depender de que una computadora
esté encendida.

Es idempotente por diseño: solo toma citas con `recordatorio_enviado=False` y
marca la cita únicamente cuando el envío salió. Si el mismo día lo disparan los
dos caminos, el segundo no encuentra nada que mandar; nadie recibe el mensaje
dos veces.
"""
from django.utils import timezone

from core.models import Clinica
from mensajes.models import Mensaje
from mensajes.services import plantilla_por_clave, registrar_y_enviar
from pacientes.api import texto_recordatorio
from pacientes.models import Cita


def citas_pendientes(clinica, fecha):
    """Citas de esa fecha que todavía esperan su recordatorio."""
    return (
        Cita.objects.filter(clinica=clinica, inicio__date=fecha, recordatorio_enviado=False)
        .exclude(estado__in=[Cita.Estado.ATENDIDA, Cita.Estado.CANCELADA])
        .select_related("paciente", "medico")
        .order_by("inicio")
    )


def enviar_recordatorios(fecha=None, dry=False):
    """Manda los recordatorios de `fecha` (hoy si no se indica) en todas las
    clínicas activas.

    Devuelve un resumen: {fecha, enviados, fallidos, omitidos, detalle[]}, donde
    cada línea de `detalle` dice qué pasó con una cita. Con `dry=True` no envía
    nada y solo arma el detalle de lo que mandaría.
    """
    fecha = fecha or timezone.localdate()
    enviados = fallidos = omitidos = 0
    detalle = []

    for clinica in Clinica.objects.filter(activo=True):
        for cita in citas_pendientes(clinica, fecha):
            nombre = cita.paciente.nombre
            tel = cita.paciente.telefono
            hora = f"{timezone.localtime(cita.inicio):%H:%M}"

            if not tel:
                omitidos += 1
                detalle.append({"paciente": nombre, "hora": hora, "estado": "sin_telefono"})
                continue

            if dry:
                detalle.append({"paciente": nombre, "hora": hora, "estado": "se_enviaria"})
                continue

            _, resultado, _ = registrar_y_enviar(
                clinica, telefono=tel, texto=texto_recordatorio(cita),
                tipo=Mensaje.Tipo.RECORDATORIO, paciente=cita.paciente, cita=cita,
                usuario=None, plantilla=plantilla_por_clave(clinica, "recordatorio"),
            )
            if resultado["estado"] == "enviado":
                cita.recordatorio_enviado = True
                cita.save(update_fields=["recordatorio_enviado"])
                enviados += 1
                detalle.append({"paciente": nombre, "hora": hora, "estado": "enviado"})
            else:
                fallidos += 1
                detalle.append({"paciente": nombre, "hora": hora, "estado": "falló",
                                "motivo": (resultado.get("detalle") or resultado["estado"])[:120]})

    return {"fecha": fecha.isoformat(), "enviados": enviados, "fallidos": fallidos,
            "omitidos": omitidos, "detalle": detalle}
