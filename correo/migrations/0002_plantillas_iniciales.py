"""Siembra las cuatro plantillas de Email 1.0 (versión 1).

Los textos son los aprobados en la especificación. Un cambio de redacción NO
se hace editando esta migración ni la fila: se crea la versión 2 con otra
migración (la bitácora apunta a la versión que salió).
"""
from django.db import migrations

P = 'style="margin:0 0 16px 0;"'
CAJA = ('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="background:#D7F4FA; border-radius:10px; margin:0 0 16px 0;"><tr>'
        '<td style="padding:16px 20px; font-family:Montserrat, Arial, Helvetica, sans-serif; '
        'font-size:15px; line-height:1.8; color:#343434;">')
FIN_CAJA = "</td></tr></table>"

RESERVA_HTML = f"""<p {P}>Hola, {{{{ nombre }}}}:</p>
<p {P}>Tu reserva quedó confirmada.</p>
{CAJA}<strong>Fecha:</strong> {{{{ fecha }}}}<br>
<strong>Hora:</strong> {{{{ hora }}}}<br>
<strong>Modalidad:</strong> {{{{ modalidad }}}}<br>
{{% if es_virtual %}}<strong>Acceso:</strong> {{% if enlace_virtual %}}<a href="{{{{ enlace_virtual }}}}" style="color:#00B8D8;">{{{{ enlace_virtual }}}}</a>{{% else %}}te enviaremos el enlace antes de la cita.{{% endif %}}{{% else %}}<strong>Lugar:</strong> {{{{ direccion_sede }}}}{{% endif %}}{FIN_CAJA}
<p {P}>Si necesitas reprogramar o tienes alguna duda antes de la cita, puedes responder este correo o escribirnos por nuestros canales habituales.</p>
<p {P}>Te recomendamos guardar este mensaje para tener la información a la mano.</p>
<p style="margin:0;">Un abrazo,<br><br><strong>Equipo Conversemos</strong><br><span style="color:#6E6E6E; font-weight:300;">Te cambia la vida.</span></p>"""

RESERVA_TEXTO = """Hola, {{ nombre }}:

Tu reserva quedó confirmada.

Fecha: {{ fecha }}
Hora: {{ hora }}
Modalidad: {{ modalidad }}
{% if es_virtual %}Acceso: {% if enlace_virtual %}{{ enlace_virtual }}{% else %}te enviaremos el enlace antes de la cita.{% endif %}{% else %}Lugar: {{ direccion_sede }}{% endif %}

Si necesitas reprogramar o tienes alguna duda antes de la cita, puedes responder este correo o escribirnos por nuestros canales habituales.

Te recomendamos guardar este mensaje para tener la información a la mano.

Un abrazo,

Equipo Conversemos
Te cambia la vida."""


def _html(parrafos, cierre):
    cuerpo = "\n".join(f"<p {P}>{x}</p>" for x in parrafos)
    return f"{cuerpo}\n<p style=\"margin:0;\">{cierre}</p>"


DP02 = {
    "dp02_dia_1": {
        "nombre": "Seguimiento DP-02 · día 1",
        "asunto": "Gracias por conversar con nosotros",
        "pre": "Si necesitas tiempo para decidir, está bien. Seguimos disponibles.",
        "parrafos": [
            "Hola, {{ nombre }}:",
            "Gracias por darte el tiempo de conversar con nuestro equipo.",
            "Sabemos que decidir cómo continuar puede requerir un poco de tiempo, así que no tienes que resolverlo todo hoy.",
            "Si más adelante quieres continuar, resolver alguna duda o conversar nuevamente sobre las opciones disponibles, puedes escribirnos. Estaremos para orientarte con calma.",
        ],
        "cierre_html": "Un abrazo,<br><br><strong>Equipo Conversemos</strong>",
        "cierre_texto": "Un abrazo,\n\nEquipo Conversemos",
    },
    "dp02_dia_7": {
        "nombre": "Seguimiento DP-02 · día 7",
        "asunto": "¿Te quedó alguna duda?",
        "pre": "Si quedó algo pendiente por aclarar, puedes escribirnos.",
        "parrafos": [
            "Hola, {{ nombre }}:",
            "Han pasado algunos días desde que conversamos y queríamos dejarte este espacio por si quedó alguna pregunta pendiente.",
            "Puede ser sobre horarios, modalidad, el proceso, el profesional que te atendería o cualquier aspecto práctico que necesites tener más claro antes de decidir.",
            "Si quieres conversar con nosotros, responde este correo o escríbenos por WhatsApp. Con gusto te ayudamos.",
            "A tu ritmo. 🌿",
        ],
        "cierre_html": "<strong>Equipo Conversemos</strong>",
        "cierre_texto": "Equipo Conversemos",
    },
    "dp02_dia_21": {
        "nombre": "Seguimiento DP-02 · día 21",
        "asunto": "Seguimos por aquí",
        "pre": "Si más adelante quieres retomar la conversación, seguimos disponibles.",
        "parrafos": [
            "Hola, {{ nombre }}:",
            "Solo queríamos recordarte que seguimos disponibles.",
            "Si en algún momento quieres retomar la conversación, consultar otras alternativas de horario o modalidad, o simplemente resolver una duda antes de decidir, puedes escribirnos.",
            "No necesitas empezar de nuevo ni explicarnos todo otra vez. Nuestro equipo puede orientarte desde donde quedó la conversación.",
            "Cuando lo necesites, aquí estamos. 🤍",
        ],
        "cierre_html": "<strong>Equipo Conversemos</strong>",
        "cierre_texto": "Equipo Conversemos",
    },
}


def sembrar(apps, schema_editor):
    Plantilla = apps.get_model("correo", "PlantillaCorreo")
    Plantilla.objects.get_or_create(clave="reserva_confirmada", version=1, defaults=dict(
        nombre="Confirmación de reserva web", categoria="SERVICE",
        asunto="Tu reserva está confirmada",
        preencabezado="Aquí tienes la información práctica para tu cita.",
        cuerpo_html=RESERVA_HTML, cuerpo_texto=RESERVA_TEXTO, activa=True,
        incluye_preferencias=False, requiere_baja_un_clic=False))
    for clave, d in DP02.items():
        Plantilla.objects.get_or_create(clave=clave, version=1, defaults=dict(
            nombre=d["nombre"], categoria="MARKETING", asunto=d["asunto"], preencabezado=d["pre"],
            cuerpo_html=_html(d["parrafos"], d["cierre_html"]),
            cuerpo_texto="\n\n".join(d["parrafos"] + [d["cierre_texto"]]),
            activa=True, incluye_preferencias=True, requiere_baja_un_clic=True))


def quitar(apps, schema_editor):
    Plantilla = apps.get_model("correo", "PlantillaCorreo")
    Plantilla.objects.filter(version=1, clave__in=["reserva_confirmada", *DP02]).delete()


class Migration(migrations.Migration):
    dependencies = [("correo", "0001_inicial")]
    operations = [migrations.RunPython(sembrar, quitar)]
