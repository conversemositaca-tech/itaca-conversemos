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

from django.apps import apps
from django.core import serializers
from django.utils import timezone

# Apps del negocio, de padres a hijos: Clinica (core) y Usuario (usuarios) van
# antes que todo lo que apunta a ellos. Lo que no está aquí —sesiones, permisos,
# logs del admin, contenttypes— se regenera solo y solo abultaría el archivo.
APPS = ["core", "usuarios", "pacientes", "finanzas", "leads", "mensajes", "espacios"]


def modelos_a_respaldar():
    """Todos los modelos de las apps del negocio, sin lista escrita a mano: una
    tabla nueva entra al respaldo el mismo día que se crea. (La lista a mano
    dejó fuera once tablas creadas entre agosto y septiembre de 2026.)"""
    return [m for app in APPS for m in apps.get_app_config(app).get_models()]


def armar_respaldo():
    """Devuelve (bytes_gzip, resumen). El resumen dice cuántas filas por modelo,
    para poder comprobar de un vistazo que el respaldo no salió vacío."""
    resumen = {}
    objetos = []
    for modelo in modelos_a_respaldar():
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
