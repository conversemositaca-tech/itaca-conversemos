"""Cuánta gente llega, cuánta da el paso y dónde se pierde.

`Lead` responde "¿de dónde vino quien reservó?". No responde "¿cuántos llegaron
y NO reservaron?", que es la mitad que decide si una campaña vale la pena.

El recorrido que se mide:

    vio una página  →  hizo clic en reservar  →  abrió el formulario  →  reservó

Los tres primeros pasos los manda el navegador y se guardan en `EventoSitio`.
El cuarto sale de `Lead`, donde ya está desde el ítem 39: no se duplica.

Nada de esto identifica a nadie. Ver el modelo para qué se guarda y qué no.
"""
from django.db.models import Count
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from core.sitio import clinica_del_sitio
from leads import atribucion
from leads.models import EventoSitio, Lead

# Quien rastrea el sitio (Google, Meta, un monitor) ejecuta JavaScript y
# dispararía eventos. No son personas buscando terapia: ensucian el embudo.
SENALES_DE_ROBOT = ("bot", "crawler", "spider", "slurp", "bingpreview",
                    "headlesschrome", "python-requests", "curl", "wget",
                    "facebookexternalhit", "whatsapp", "preview")


class _RitmoEmbudo(AnonRateThrottle):
    """Límite de peticiones por IP.

    Matiz honesto: esto SÍ mira la IP de quien llama, porque es la única forma de
    frenar a alguien que quiera inflar los números. La usa el cache de Django —en
    memoria del proceso, se pierde al reiniciar— y **no llega a la base de datos
    ni se guarda junto a ningún evento**. Lo que queda escrito del embudo no
    permite reconstruir quién hizo qué.
    """

    scope = "embudo"


def _solo_ruta(valor):
    """La página, sin lo que venga pegado detrás.

    El navegador manda `location.pathname`, que ya viene limpio, pero esto lo
    llama cualquiera: cortar en `?` y en `#` evita guardar parámetros que no
    pedimos y que podrían traer cualquier cosa.
    """
    return str(valor or "").split("?")[0].split("#")[0][:200]


def es_robot(user_agent):
    ua = (user_agent or "").lower()
    return not ua or any(s in ua for s in SENALES_DE_ROBOT)


class RegistrarEventoView(APIView):
    """Recibe un paso del embudo. Público, sin sesión.

    Responde 204 pase lo que pase: es medición, nunca puede estorbar a alguien
    que está intentando reservar, y contestar distinto según el caso le diría a
    cualquiera qué clínica hay detrás.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [_RitmoEmbudo]

    def post(self, request):
        vacio = Response(status=status.HTTP_204_NO_CONTENT)
        if es_robot(request.META.get("HTTP_USER_AGENT")):
            return vacio

        d = request.data if isinstance(request.data, dict) else {}
        tipo = str(d.get("tipo") or "").strip()
        if tipo not in EventoSitio.Tipo.values:
            return vacio

        clinica = clinica_del_sitio()
        if not clinica:
            return vacio

        # El origen llega del mismo sitio que lo guardado para la reserva, así
        # que se limpia con las mismas reglas: lista blanca y recorte.
        origen = atribucion.limpiar(d.get("atribucion"))
        EventoSitio.objects.create(
            clinica=clinica,
            tipo=tipo,
            ruta=_solo_ruta(d.get("ruta")),
            canal=(origen.get("utm_source") or "")[:80],
            medio=(origen.get("utm_medium") or "")[:80],
            campania=(origen.get("utm_campaign") or "")[:120],
            sesion=str(d.get("sesion") or "")[:32],
        )
        return vacio


def _clave(canal, medio, campania):
    """Cómo se agrupa un origen. Lo que no viene etiquetado cae en 'directo'."""
    if not (canal or medio or campania):
        return "directo"
    partes = [canal or "—", medio or "—"]
    if campania:
        partes.append(campania)
    return " · ".join(partes)


def resumen(clinica, desde, hasta):
    """El embudo del período, entero y desglosado por origen.

    `personas` cuenta visitas distintas (por `sesion`); `paginas`, páginas
    vistas. La diferencia importa: alguien que mira cuatro páginas es una
    persona interesada, no cuatro oportunidades.
    """
    eventos = EventoSitio.objects.filter(clinica=clinica, creado_en__gte=desde,
                                         creado_en__lte=hasta)
    reservas = Lead.objects.filter(clinica=clinica, fuente=Lead.Fuente.WEB,
                                   creado_en__gte=desde, creado_en__lte=hasta)

    por_origen = {}

    def casilla(clave):
        return por_origen.setdefault(clave, {
            "origen": clave, "personas": 0, "paginas": 0,
            "clic_reservar": 0, "abre_agenda": 0, "reservas": 0,
        })

    # Personas distintas por origen: una fila por (origen, sesión).
    #
    # El `order_by()` vacío NO sobra. El modelo ordena por `creado_en`, y Django
    # arrastra la columna de ordenación dentro del SELECT del `distinct()`: como
    # cada visita tiene su propia hora, las cuatro páginas que miró una persona
    # salían como cuatro personas y toda tasa de conversión quedaba dividida por
    # las páginas vistas.
    for fila in (eventos.filter(tipo=EventoSitio.Tipo.VISITA)
                 .order_by()
                 .values("canal", "medio", "campania", "sesion").distinct()):
        casilla(_clave(fila["canal"], fila["medio"], fila["campania"]))["personas"] += 1

    campos = {EventoSitio.Tipo.VISITA: "paginas",
              EventoSitio.Tipo.CLIC_RESERVAR: "clic_reservar",
              EventoSitio.Tipo.ABRE_AGENDA: "abre_agenda"}
    for fila in eventos.values("tipo", "canal", "medio", "campania").annotate(n=Count("id")):
        campo = campos.get(fila["tipo"])
        if campo:
            casilla(_clave(fila["canal"], fila["medio"], fila["campania"]))[campo] += fila["n"]

    for fila in reservas.values("origen_canal", "origen_medio", "campania").annotate(n=Count("id")):
        casilla(_clave(fila["origen_canal"], fila["origen_medio"],
                       fila["campania"]))["reservas"] += fila["n"]

    filas = sorted(por_origen.values(), key=lambda f: (-f["reservas"], -f["personas"]))
    for f in filas:
        f["tasa"] = round(100 * f["reservas"] / f["personas"], 1) if f["personas"] else None

    total = {
        "personas": sum(f["personas"] for f in filas),
        "paginas": sum(f["paginas"] for f in filas),
        "clic_reservar": sum(f["clic_reservar"] for f in filas),
        "abre_agenda": sum(f["abre_agenda"] for f in filas),
        "reservas": sum(f["reservas"] for f in filas),
    }
    total["tasa"] = (round(100 * total["reservas"] / total["personas"], 1)
                     if total["personas"] else None)
    # Sin visitas medidas todavía no hay embudo que mostrar, solo las reservas
    # de siempre: conviene que la pantalla lo diga en vez de fingir un 0 %.
    total["midiendo"] = total["personas"] > 0
    return {"total": total, "por_origen": filas[:12]}
