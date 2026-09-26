"""El informe individual para la familia: el PDF y el correo que lo lleva.

El consentimiento le promete a cada apoderado el resultado de su hijo o hija
por correo, en un informe que explica qué significa cada indicador. Este módulo
cumple esa promesa y nada más: no decide nada clínico, no recalcula puntajes
(usa los que quedaron guardados con la respuesta) y no manda nada por su
cuenta.

Lo dispara el equipo clínico desde el panel, colegio por colegio, con dos
frenos que salen del propio consentimiento y del protocolo:

· Un nivel rojo no se envía hasta que la alerta esté atendida. La familia se
  entera por la llamada del psicólogo, nunca por un archivo adjunto.
· Se envía una sola vez por autorización. Reenviar es una decisión que se toma
  a mano, no un efecto de apretar dos veces el botón.

Lo que NO va en el informe son las respuestas una por una. La familia recibe lo
mismo que ve el colegio —nivel y puntajes— más una explicación en palabras.
"""
from io import BytesIO

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

from . import instrumentos as ins

CONTACTO = "conversemos.itaca@gmail.com"

NIVELES = {
    ins.VERDE: ("Sin indicadores relevantes",
                "Ninguno de los cuestionarios superó su punto de corte. No hay nada que "
                "atender por ahora; el resultado se entrega igual porque es suyo."),
    ins.AMBAR: ("Indicadores que requieren seguimiento",
                "Alguno de los cuestionarios muestra señales que conviene acompañar. "
                "No es un diagnóstico: es una invitación a mirar con más cuidado, y el "
                "psicólogo del colegio recibe el caso para ese seguimiento."),
    ins.ROJO: ("Riesgo que se atendió el mismo día",
               "Las respuestas mostraron señales que requerían atención inmediata. El "
               "psicólogo responsable conversó con el estudiante y se comunicó con "
               "usted antes de enviarle este informe."),
}

ROLES = {
    "No involucrado": "No reporta haber sufrido ni ejercido maltrato con frecuencia.",
    "Víctima": "Reporta haber sufrido alguna forma de maltrato al menos una o dos "
               "veces al mes.",
    "Agresor": "Reporta haber ejercido alguna forma de maltrato al menos una o dos "
               "veces al mes.",
    "Víctima y agresor": "Reporta haber sufrido y también ejercido maltrato con esa "
                         "frecuencia. Son situaciones que se trabajan juntas.",
    "Cibervíctima": "Reporta haber sufrido maltrato por internet, redes o mensajes al "
                    "menos una o dos veces al mes.",
    "Ciberagresor": "Reporta haber ejercido maltrato por internet, redes o mensajes "
                    "al menos una o dos veces al mes.",
    "Cibervíctima y ciberagresor": "Reporta haber sufrido y también ejercido maltrato "
                                   "por internet con esa frecuencia.",
}


def _severidad(prefijo, total):
    """La banda que le corresponde a un total, con los cortes del instrumento.

    Se le pasa el total guardado como si fuera el primer ítem: así la banda sale
    de la misma función que puntúa, sin copiar los cortes aquí, y sin volver a
    sumar las respuestas crudas de un resultado que ya se entregó.
    """
    f = ins.puntuar_phq_a if prefijo == "phq" else ins.puntuar_gad_7
    return f({f"{prefijo}1": total})["severidad"]


def indicadores(r):
    """Los cinco renglones del informe: (área, resultado, qué significa)."""
    phq = _severidad("phq", r.phq_total)
    gad = _severidad("gad", r.gad_total)
    ebipq = r.ebipq_rol or "No involucrado"
    ciber = r.ciber_rol or "No involucrado"
    return [
        ("Convivencia escolar", ebipq, ROLES.get(ebipq, "")),
        ("Convivencia por internet", ciber, ROLES.get(ciber, "")),
        ("Estado de ánimo", f"{r.phq_total} de 27 · {phq}",
         "Cómo se ha sentido en las últimas dos semanas. Desde 10 puntos se "
         "recomienda seguimiento."),
        ("Ansiedad", f"{r.gad_total} de 21 · {gad}",
         "Preocupación, nerviosismo y dificultad para relajarse en los últimos "
         "quince días. Desde 10 puntos se recomienda seguimiento."),
        ("Señales de riesgo", "Con señales" if r.asq_positivo else "Sin señales",
         "Preguntas directas sobre pensamientos de hacerse daño. Cualquier señal "
         "se atiende el mismo día con una conversación privada." if r.asq_positivo
         else "Preguntas directas sobre pensamientos de hacerse daño. No las hubo."),
    ]


def _fecha(r):
    return timezone.localtime(r.creado_en).strftime("%d/%m/%Y")


def asunto(r):
    return f"Faro · Resultado de {r.nombre} · {r.aplicacion.institucion}"


def cuerpo(r):
    a = r.autorizacion
    titulo, _ = NIVELES[r.nivel]
    lineas = [
        f"Estimado/a {a.apoderado}:",
        "",
        f"Le enviamos el resultado del tamizaje de bienestar emocional que {r.nombre} "
        f"respondió el {_fecha(r)} en {r.aplicacion.institucion}, dentro del programa Faro.",
        "",
        f"Nivel de atención: {titulo}.",
        "",
        "El informe completo va adjunto en PDF y explica qué significa cada indicador. "
        "Recuerde que un tamizaje no es un diagnóstico: es una primera mirada.",
        "",
        f"Si tiene dudas, escríbanos a {CONTACTO}. Si en algún momento necesita hablar "
        "con alguien, la Línea 113, opción 5, del Ministerio de Salud atiende todos "
        "los días y es gratuita.",
        "",
        "Ítaca Conversemos",
    ]
    return "\n".join(lineas)


def pdf(r):
    """El informe en PDF. Una hoja, sin jerga, sin respuestas crudas."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    a = r.autorizacion
    titulo, explicacion = NIVELES[r.nivel]
    ss = getSampleStyleSheet()
    normal = ParagraphStyle("n", parent=ss["Normal"], fontName="Helvetica", fontSize=10.5, leading=15)
    chico = ParagraphStyle("c", parent=normal, fontSize=9, leading=12.5, textColor=colors.HexColor("#555555"))
    h1 = ParagraphStyle("h1", parent=normal, fontName="Helvetica-Bold", fontSize=16, leading=20, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=normal, fontName="Helvetica-Bold", fontSize=11.5, leading=15,
                        spaceBefore=10, spaceAfter=4)

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm,
                            title=asunto(r), author="Ítaca Conversemos")
    cuerpo_pdf = [
        Paragraph("Ítaca Conversemos · Programa Faro", chico),
        Paragraph("Resultado individual del tamizaje", h1),
        Paragraph(f"<b>{r.nombre}</b> · {r.grado} {r.seccion}".strip(" ·"), normal),
        Paragraph(f"{r.aplicacion.institucion} · aplicado el {_fecha(r)}", normal),
        Spacer(1, 8),
        Paragraph(f"Nivel de atención: {titulo}", h2),
        Paragraph(explicacion, normal),
        Paragraph("Qué se encontró en cada área", h2),
    ]
    filas = [["Área", "Resultado", "Qué significa"]]
    for area, resultado, significado in indicadores(r):
        filas.append([Paragraph(area, normal), Paragraph(resultado, normal), Paragraph(significado, chico)])
    tabla = Table(filas, colWidths=[38 * mm, 42 * mm, 90 * mm], repeatRows=1)
    tabla.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF2F5")),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCD3DA")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    cuerpo_pdf += [
        tabla,
        Paragraph("Qué es este resultado, y qué no es", h2),
        Paragraph("Un tamizaje es una primera mirada, no un diagnóstico. No dice que su hijo o "
                  "hija tenga un trastorno ni reemplaza una evaluación individual. Tampoco es "
                  "un examen: no tiene nota ni queda en el registro académico.", normal),
        Paragraph("Qué sigue", h2),
        Paragraph("Si el nivel es de seguimiento o de atención, el psicólogo del colegio y el "
                  "equipo de Ítaca Conversemos acompañan el caso y se comunican con usted. Si "
                  "quiere una evaluación individual o conversar sobre este informe, escríbanos "
                  f"a {CONTACTO}.", normal),
        Paragraph("Si en algún momento su hijo o hija necesita hablar con alguien: Línea 113, "
                  "opción 5, del Ministerio de Salud. Gratuita, todos los días.", normal),
        Spacer(1, 10),
        Paragraph(f"Informe enviado a {a.apoderado} ({a.correo}), quien autorizó la participación "
                  f"con la versión {a.version_texto or 'en papel'} del consentimiento. Este documento "
                  "contiene datos sensibles protegidos por la Ley N.° 29733: no lo comparta.", chico),
    ]
    doc.build(cuerpo_pdf)
    return buf.getvalue()


def enviar(r):
    """Manda el informe de una respuesta y deja constancia en su autorización.

    Devuelve True si salió. Si falla, guarda el porqué en `envio_detalle` y no
    marca la fecha: así el siguiente intento lo vuelve a tomar.
    """
    a = r.autorizacion
    try:
        msg = EmailMessage(asunto(r), cuerpo(r), settings.DEFAULT_FROM_EMAIL, [a.correo])
        msg.attach(f"faro-{r.nombre.replace(' ', '-').lower()}.pdf", pdf(r), "application/pdf")
        msg.send(fail_silently=False)
    except Exception as e:  # noqa: BLE001 — cualquier fallo del correo se registra, no se pierde
        a.envio_detalle = f"Falló: {e}"[:300]
        a.save(update_fields=["envio_detalle"])
        return False
    a.enviado_en = timezone.now()
    a.envio_detalle = "Enviado"
    a.save(update_fields=["enviado_en", "envio_detalle"])
    return True


def enviar_pendientes(ap):
    """Manda los informes que faltan de un colegio y dice qué pasó con cada uno.

    Devuelve cuántos salieron y por qué se omitió el resto, para que quien
    apretó el botón sepa si le falta emparejar, atender una alerta o pedir un
    correo, en vez de un "listo" que no dice nada.
    """
    enviados, errores = 0, 0
    omitidos = {"sin_autorizacion": 0, "sin_correo": 0, "rojo_pendiente": 0, "ya_enviado": 0}
    qs = ap.respuestas.select_related("autorizacion", "aplicacion").order_by("id")
    for r in qs:
        a = r.autorizacion
        if a is None or not a.autoriza:
            omitidos["sin_autorizacion"] += 1
            continue
        if not a.correo:
            omitidos["sin_correo"] += 1
            continue
        if a.enviado_en:
            omitidos["ya_enviado"] += 1
            continue
        if r.nivel == ins.ROJO:
            alerta = getattr(r, "alerta", None)
            if alerta is None or not alerta.atendida:
                omitidos["rojo_pendiente"] += 1
                continue
        if enviar(r):
            enviados += 1
        else:
            errores += 1
    return {"enviados": enviados, "errores": errores, "omitidos": omitidos}
