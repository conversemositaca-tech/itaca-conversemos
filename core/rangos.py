"""Servir archivos entendiendo la cabecera `Range` (RFC 7233).

Safari en iPhone no reproduce un `<video>` si el servidor no responde por
tramos: pide los primeros bytes para leer la cabecera del archivo y, si recibe
el archivo entero con un 200, abandona y deja el recuadro en negro. Django sirve
con `FileResponse`, que no implementa `Range`, así que hace falta esto.

Es además lo que permite adelantar el video sin descargarlo completo, y lo que
evita que alguien que solo quiere ver el final se traiga todo el archivo.
"""
import re

from django.http import FileResponse, HttpResponse

# Tipos que servimos. No se deduce del nombre del archivo a ciegas: lo que no
# reconocemos sale como mp4, que es lo que graba un celular.
_TIPOS = {
    "mp4": "video/mp4",
    "m4v": "video/mp4",
    "mov": "video/quicktime",
    "webm": "video/webm",
}

_RANGO = re.compile(r"^bytes=(\d*)-(\d*)$")


def tipo_de_video(nombre):
    ext = (nombre or "").rsplit(".", 1)[-1].lower()
    return _TIPOS.get(ext, "video/mp4")


def _tramo(fh, restante, bloque=8192):
    """Lee solo los bytes pedidos y cierra. Sin esto se manda el archivo entero."""
    try:
        while restante > 0:
            datos = fh.read(min(bloque, restante))
            if not datos:
                break
            restante -= len(datos)
            yield datos
    finally:
        fh.close()


def respuesta_de_archivo(request, archivo, content_type=None, nombre=None):
    """Devuelve el archivo completo, o el tramo que pida el navegador.

    `archivo` es un FieldFile (por ejemplo `prof.video`). Si no hay cabecera
    `Range`, responde 200 con todo; si la hay, 206 con el tramo; y si el tramo
    pedido no existe, 416 — que es lo que el navegador espera para reintentar.
    """
    content_type = content_type or tipo_de_video(nombre or getattr(archivo, "name", ""))
    tamano = archivo.size

    cabecera = (request.headers.get("Range") or "").strip()
    m = _RANGO.match(cabecera) if cabecera else None
    if not m:
        resp = FileResponse(archivo.open("rb"), content_type=content_type)
        resp["Content-Length"] = str(tamano)
        # Sin esto el navegador ni siquiera intenta pedir tramos.
        resp["Accept-Ranges"] = "bytes"
        return resp

    desde_txt, hasta_txt = m.groups()
    if desde_txt == "":
        # "bytes=-500" son los ÚLTIMOS 500 bytes, no los primeros.
        ultimos = int(hasta_txt or 0)
        if ultimos <= 0:
            return _fuera_de_rango(tamano)
        desde = max(0, tamano - ultimos)
        hasta = tamano - 1
    else:
        desde = int(desde_txt)
        hasta = int(hasta_txt) if hasta_txt else tamano - 1

    if desde >= tamano or desde > hasta:
        return _fuera_de_rango(tamano)
    hasta = min(hasta, tamano - 1)
    largo = hasta - desde + 1

    fh = archivo.open("rb")
    fh.seek(desde)
    resp = FileResponse(_tramo(fh, largo), status=206, content_type=content_type)
    resp["Content-Range"] = f"bytes {desde}-{hasta}/{tamano}"
    resp["Content-Length"] = str(largo)
    resp["Accept-Ranges"] = "bytes"
    return resp


def _fuera_de_rango(tamano):
    resp = HttpResponse(status=416)
    resp["Content-Range"] = f"bytes */{tamano}"
    resp["Accept-Ranges"] = "bytes"
    return resp
