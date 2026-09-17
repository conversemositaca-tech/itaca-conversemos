"""De dónde vino quien reservó por la web.

Hoy toda reserva entra con `fuente = WEB`, y eso solo dice CÓMO reservó, no de
dónde salió: una consulta traída por un anuncio pagado y otra que llegó
buscando en Google son indistinguibles. Sin esto no se puede saber qué campaña
trae consultas que de verdad inician proceso, ni cuál solo gasta.

Lo que llega del navegador es texto que escribe cualquiera en la URL, así que
aquí se limpia antes de guardarlo: se recortan longitudes, se descarta lo vacío
y se ignora cualquier clave que no esté en la lista blanca. Nada de esto es
dato personal: describe el origen del tráfico, no a la persona.
"""

# Claves que aceptamos del navegador. Las cinco `utm_*` son el estándar que usan
# Google, Meta y el resto; `gclid`/`fbclid` los añade la propia plataforma al
# clic y permiten cruzar con su reporte de gasto; `landing` y `referrer` dicen
# en qué página entró y qué sitio la mandó.
CLAVES = (
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
    "gclid", "fbclid", "referrer", "landing", "variante",
)

LARGO_MAX = 200
# Un `referrer` o una landing con muchos parámetros se va de largo; se recorta
# sin perder el dominio, que es lo que interesa.
LARGO_URL = 400

# Medios que significan "esto se pagó". Sirve para marcar `es_pauta` sin que
# nadie tenga que acordarse de hacerlo a mano en cada lead.
MEDIOS_PAGADOS = {"cpc", "ppc", "paid", "paid_social", "paidsocial", "ads", "display", "retargeting"}


def _texto(valor, largo=LARGO_MAX):
    if valor is None:
        return ""
    return str(valor).strip()[:largo]


def limpiar(datos):
    """Deja solo las claves conocidas, ya recortadas. Devuelve {} si no hay nada."""
    if not isinstance(datos, dict):
        return {}
    fuera = {}
    for clave in CLAVES:
        largo = LARGO_URL if clave in ("referrer", "landing") else LARGO_MAX
        valor = _texto(datos.get(clave), largo)
        if valor:
            fuera[clave] = valor
    return fuera


def es_pagado(atribucion):
    """¿La visita vino de un anuncio pagado?

    Lo dice el medio declarado (cpc, paid_social…) o la presencia del
    identificador de clic que añaden Google y Meta a sus anuncios.
    """
    medio = (atribucion.get("utm_medium") or "").lower().replace("-", "_")
    return medio in MEDIOS_PAGADOS or bool(atribucion.get("gclid") or atribucion.get("fbclid"))


def campos_de_lead(atribucion):
    """Traduce el origen a los campos del Lead.

    `campania`, `es_pauta` y `subfuente` YA existen y son los que lee el reporte
    de captación; se llenan desde aquí en vez de crear un circuito paralelo.
    Los detalles que no tienen columna propia (término, ids de clic, referente,
    landing) se guardan juntos en `origen_detalle`.
    """
    limpia = limpiar(atribucion)
    if not limpia:
        return {}

    campos = {
        "origen_canal": (limpia.get("utm_source") or "")[:80],
        "origen_medio": (limpia.get("utm_medium") or "")[:80],
        "origen_contenido": (limpia.get("utm_content") or "")[:120],
        "origen_detalle": limpia,
    }
    if limpia.get("utm_campaign"):
        campos["campania"] = limpia["utm_campaign"][:120]
    if es_pagado(limpia):
        campos["es_pauta"] = True
    # La subfuente es la etiqueta que el equipo ya lee en Captación ("de dónde
    # exactamente"): canal + medio, sin inventar un vocabulario nuevo.
    canal, medio = campos["origen_canal"], campos["origen_medio"]
    if canal:
        campos["subfuente"] = f"{canal} · {medio}"[:60] if medio else canal[:60]
    return campos
