"""Armar un correo a partir de su plantilla: asunto, HTML, texto y cabeceras.

El cuerpo de cada plantilla usa la sintaxis de plantillas de Django
(`{{ nombre }}`) y se envuelve en el diseño compartido
`correo/templates/correo/base.html`. El HTML escapa todo; el texto plano no.

El contexto no puede traer datos clínicos: hay una lista de claves prohibidas
que hace fallar el armado antes de que nada salga del sistema.
"""
from django.template import Context, Template
from django.template.loader import render_to_string
from django.utils.html import escape
from django.utils.safestring import mark_safe

from correo import textos
from correo.models import Categoria
from correo.services import urls_publicas

# Ninguna clave que suene a dato clínico o interno puede llegar a un correo.
CLAVES_PROHIBIDAS = {
    "diagnostico", "motivo", "motivo_consulta", "historia", "historia_clinica", "notas",
    "riesgo", "escala", "escalas", "alertas", "nps", "n_sesion", "sesion", "proceso",
    "decision", "dp", "objeciones", "motivo_perdida", "especialidad", "continuidad",
    "paciente_id", "lead_id", "cita_id", "decision_id",
}

# Cada plantilla trae su propio cierre (no todas terminan igual), así que el
# diseño no agrega una firma por defecto.


class ContextoNoPermitido(ValueError):
    pass


def validar_contexto(contexto):
    malas = sorted(k for k in contexto if k.lower() in CLAVES_PROHIBIDAS)
    if malas:
        raise ContextoNoPermitido(f"Claves no permitidas en un correo: {', '.join(malas)}")


def _render(texto, contexto, autoescape):
    return Template(texto).render(Context(contexto, autoescape=autoescape))


def armar(plantilla, contexto, *, token_preferencias=None, request=None):
    """Devuelve (asunto, html, texto, cabeceras)."""
    validar_contexto(contexto)
    es_marketing = plantilla.categoria == Categoria.MARKETING
    asunto = _render(plantilla.asunto, contexto, autoescape=False).strip()
    preencabezado = _render(plantilla.preencabezado, contexto, autoescape=False).strip()
    cuerpo_html = _render(plantilla.cuerpo_html, contexto, autoescape=True)
    cuerpo_texto = _render(plantilla.cuerpo_texto, contexto, autoescape=False).strip()

    pref_url = urls_publicas.preferencias(token_preferencias, request) if token_preferencias else ""
    # El enlace del pie lleva a la página (que da de baja al abrirse con
    # JavaScript: los antivirus que "visitan" enlaces no la disparan). La
    # cabecera List-Unsubscribe apunta directo al endpoint POST (RFC 8058).
    baja_url = (urls_publicas.preferencias(token_preferencias, request) + "?baja=1"
                if token_preferencias else "")
    baja_post_url = urls_publicas.baja(token_preferencias, request) if token_preferencias else ""
    legal = textos.datos_legales()

    html = render_to_string("correo/base.html", {
        "asunto": asunto,
        "preencabezado": preencabezado,
        "logo_url": urls_publicas.logo(request),
        "cuerpo": mark_safe(cuerpo_html),
        "firma": mark_safe(contexto.get("firma_html") or ""),
        "cta_url": contexto.get("cta_url", ""),
        "cta_texto": contexto.get("cta_texto", ""),
        "es_marketing": es_marketing,
        "legal": legal,
        "preferencias_url": pref_url,
        "baja_url": baja_url,
    })

    partes = [cuerpo_texto]
    if contexto.get("cta_url") and contexto.get("cta_texto"):
        partes.append(f"{contexto['cta_texto']}: {contexto['cta_url']}")
    if contexto.get("firma_texto"):
        partes.append(contexto["firma_texto"])
    if es_marketing:
        partes.append("\n".join([
            "—",
            "Ítaca Conversemos",
            "Recibes este correo porque aceptaste recibir comunicaciones de Ítaca Conversemos.",
            f"Responsable del tratamiento de datos personales: {legal['razon_social']}",
            f"Domicilio: {legal['domicilio']}",
            "Puedes ejercer tus derechos de acceso, rectificación, cancelación y oposición (ARCO) "
            f"a través de: {legal['canal_arco']}",
            f"Política de Privacidad: {legal['url_privacidad']}" if legal["url_privacidad"] else "Política de Privacidad",
            f"Administrar preferencias: {pref_url}",
            f"Cancelar suscripción: {baja_url}",
        ]))
    texto = "\n\n".join(p for p in partes if p)

    cabeceras = {}
    if es_marketing and plantilla.requiere_baja_un_clic and baja_post_url:
        # RFC 8058: baja de un clic desde el propio cliente de correo.
        cabeceras["List-Unsubscribe"] = f"<{baja_post_url}>"
        cabeceras["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    return asunto, html, texto, cabeceras


def html_seguro(texto):
    """Escapa texto libre para meterlo dentro de un bloque HTML del contexto."""
    return mark_safe(escape(texto or ""))
