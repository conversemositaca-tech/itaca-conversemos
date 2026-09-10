"""Monitor de las líneas de WhatsApp por Evolution (solo lectura, solo gerencia).

Muestra qué instancia atiende a cada sede y si está conectada. Es un tablero
para mirar, no para operar: no hay desconectar, ni cerrar sesión, ni borrar
instancia, ni emparejar por QR. Conectar o desconectar un número es una decisión
de Coordinación y se hace en Evolution, no desde aquí.

Nada de lo que devuelve incluye secretos: ni la EVOLUTION_API_KEY, ni el token
del webhook, ni la URL del webhook (que lleva el token dentro). Del webhook solo
se informa si está encendido, con qué eventos y si apunta a este sistema.
"""
import logging

import requests
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import InstanciaEvolution
from core.tenant import get_clinica_actual

log = logging.getLogger(__name__)

# Eventos que el sistema necesita para funcionar. Se comparan con los que tiene
# configurados la instancia para avisar si falta alguno.
EVENTOS_REQUERIDOS = ["MESSAGES_UPSERT", "MESSAGES_UPDATE", "CONNECTION_UPDATE"]

TIMEOUT = 8


def _es_admin(user):
    from usuarios.models import Usuario

    return getattr(user, "rol", None) == Usuario.Rol.ADMIN


def _ctx(request):
    """(clinica, respuesta_de_error). El monitor es solo para gerencia."""
    if not _es_admin(request.user):
        return None, Response(
            {"detail": "Solo el gerente (admin) puede ver la conexión de WhatsApp."},
            status=status.HTTP_403_FORBIDDEN,
        )
    clinica = get_clinica_actual()
    if clinica is None:
        return None, Response({"detail": "Sin clínica en contexto."},
                              status=status.HTTP_400_BAD_REQUEST)
    return clinica, None


def _instancia_dict(i):
    return {
        "id": i.id,
        "sede": i.sede,
        "sede_display": i.get_sede_display() if i.sede else "",
        "instancia": i.nombre_instancia,
        "activo": i.activo,
        "proveedor": "evolution",
        "proveedor_display": "Evolution API",
        "respuestas_automaticas": i.respuestas_automaticas,
        "ultimo_estado": i.ultimo_estado,
        "ultimo_evento_en": i.ultimo_evento_en.isoformat() if i.ultimo_evento_en else None,
    }


def _servidor():
    return settings.EVOLUTION_API_URL.strip(), settings.EVOLUTION_API_KEY.strip()


def _consultar_estado(url, key, nombre):
    """GET /instance/connectionState/{instance} → open | close | connecting."""
    try:
        r = requests.get(
            url.rstrip("/") + "/instance/connectionState/" + nombre,
            headers={"apikey": key}, timeout=TIMEOUT,
        )
    except requests.RequestException as e:
        return {"ok": False, "estado": "", "detalle": f"No se pudo consultar: {e}"[:200]}
    if r.status_code == 404:
        return {"ok": False, "estado": "", "detalle": "Esa instancia no existe en Evolution."}
    if r.status_code not in (200, 201):
        # El cuerpo del error de Evolution no se reenvía tal cual: puede traer
        # datos del servidor. Solo el código.
        return {"ok": False, "estado": "", "detalle": f"Evolution respondió {r.status_code}."}
    try:
        data = r.json()
    except ValueError:
        return {"ok": False, "estado": "", "detalle": "Respuesta ilegible de Evolution."}
    estado = ((data.get("instance") or {}) if isinstance(data, dict) else {}).get("state") or ""
    return {"ok": True, "estado": str(estado), "detalle": ""}


def _consultar_webhook(url, key, nombre, host_esperado):
    """GET /webhook/find/{instance}.

    Devuelve si el webhook está encendido, qué eventos tiene y si apunta a este
    sistema — NUNCA la URL, que lleva el token secreto dentro.
    """
    try:
        r = requests.get(
            url.rstrip("/") + "/webhook/find/" + nombre,
            headers={"apikey": key}, timeout=TIMEOUT,
        )
    except requests.RequestException:
        return {"consultado": False}
    if r.status_code not in (200, 201):
        return {"consultado": True, "configurado": False}
    try:
        data = r.json()
    except ValueError:
        return {"consultado": True, "configurado": False}
    if not isinstance(data, dict):
        return {"consultado": True, "configurado": False}
    destino = str(data.get("url") or "")
    eventos = [str(e).upper() for e in (data.get("events") or []) if e]
    return {
        "consultado": True,
        "configurado": bool(data.get("enabled")) and bool(destino),
        "apunta_aqui": bool(host_esperado and host_esperado in destino),
        "eventos": eventos,
        "faltan_eventos": [e for e in EVENTOS_REQUERIDOS if e not in eventos],
    }


class EvolutionInstanciasView(APIView):
    """GET: las líneas registradas y lo último que se supo de ellas (sin red)."""

    def get(self, request):
        clinica, err = _ctx(request)
        if err:
            return err
        url, key = _servidor()
        instancias = InstanciaEvolution.objects.filter(clinica=clinica).order_by("sede", "id")
        return Response({
            # Solo se informa SI hay servidor configurado, no cuál ni con qué clave.
            "servidor_configurado": bool(url and key),
            "eventos_requeridos": EVENTOS_REQUERIDOS,
            "instancias": [_instancia_dict(i) for i in instancias],
        })


class EvolutionEstadoView(APIView):
    """GET: consulta en vivo el estado de conexión de cada línea en Evolution.

    Va contra el servidor de Evolution con la API key del ENTORNO; la clave no
    sale de aquí (no se devuelve ni se registra en el log).
    """

    def get(self, request):
        clinica, err = _ctx(request)
        if err:
            return err
        url, key = _servidor()
        instancias = list(InstanciaEvolution.objects.filter(clinica=clinica).order_by("sede", "id"))
        if not (url and key):
            return Response({
                "servidor_configurado": False,
                "detalle": "Falta configurar el servidor de Evolution en el entorno.",
                "instancias": [{**_instancia_dict(i), "conexion": {"ok": False, "estado": "",
                                                                   "detalle": "Sin servidor."}}
                               for i in instancias],
            })
        host = request.get_host()
        salida = []
        for i in instancias:
            fila = _instancia_dict(i)
            fila["conexion"] = _consultar_estado(url, key, i.nombre_instancia)
            fila["webhook"] = _consultar_webhook(url, key, i.nombre_instancia, host)
            salida.append(fila)
        return Response({
            "servidor_configurado": True,
            "eventos_requeridos": EVENTOS_REQUERIDOS,
            "instancias": salida,
        })
