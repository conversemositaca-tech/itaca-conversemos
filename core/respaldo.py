"""Respaldo de los datos del sistema.

Railway guarda la base, pero si un día se borra algo por error —un paciente, un
mes de cobros, la base entera— no hay de dónde sacarlo. Esto arma un volcado
completo de los datos del negocio, comprimido, para que algo de afuera se lo
lleve y lo guarde.

Se expone en /api/integraciones/respaldo/ con el token compartido, y lo recoge
un cron de kira-bot que lo sube a un bucket privado. Itaca no necesita, así,
credenciales de almacenamiento.

OJO: el archivo lleva datos de pacientes (Ley 29733). Va cifrado en tránsito por
HTTPS y debe quedar en un bucket PRIVADO, nunca público.
"""
import gzip
import io

from django.core import serializers
from django.utils import timezone

from finanzas.models import Cobro, Egreso, Paquete, Servicio
from leads.models import Anuncio, Lead
from mensajes.models import Mensaje, PlantillaMensaje
from pacientes.models import (
    Adjunto, Atencion, BloqueoAgenda, Cita, Consentimiento, ObjetivoTerapeutico,
    Paciente, SeguimientoSesion,
)
from usuarios.models import DocumentoLegal, Profesional, Usuario
from espacios.models import (
    Consultorio, ContratoAlquiler, InteresadoAlquiler, PagoAlquiler, ReservaEspacio,
)
from core.models import Clinica

# Lo que hay que poder recuperar. No incluye sesiones, logs ni tablas de Django:
# eso se regenera solo y solo abultaría el archivo.
MODELOS = [
    Clinica, Usuario, Profesional, DocumentoLegal,
    Paciente, Cita, Atencion, SeguimientoSesion, ObjetivoTerapeutico,
    Consentimiento, Adjunto, BloqueoAgenda,
    Servicio, Cobro, Paquete, Egreso,
    Lead, Anuncio, Mensaje, PlantillaMensaje,
    Consultorio, InteresadoAlquiler, ContratoAlquiler, PagoAlquiler, ReservaEspacio,
]


def armar_respaldo():
    """Devuelve (bytes_gzip, resumen). El resumen dice cuántas filas por modelo,
    para poder comprobar de un vistazo que el respaldo no salió vacío."""
    resumen = {}
    objetos = []
    for modelo in MODELOS:
        filas = list(modelo.objects.all())
        resumen[modelo.__name__] = len(filas)
        objetos.extend(filas)

    crudo = serializers.serialize("json", objetos, indent=None)
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0) as gz:
        gz.write(crudo.encode("utf-8"))
    return buffer.getvalue(), resumen


def nombre_de_archivo():
    return f"itaca-{timezone.localdate():%Y-%m-%d}.json.gz"
