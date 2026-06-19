"""Generador del reporte de pauta/captación en texto (listo para WhatsApp).

Reconstruye, a partir de los leads estructurados (origen, anuncio, etapa, fechas),
el mismo reporte que las asistentes arman a mano, por sede y período.
"""
from .models import Lead

MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
E = Lead.Estado
FUENTE_LABEL = dict(Lead.Fuente.choices)


def _rango_txt(desde, hasta):
    if desde.month == hasta.month and desde.year == hasta.year:
        return f"{desde.day:02d}–{hasta.day:02d} de {MESES[desde.month]} {desde.year}"
    return f"{desde.day:02d} {MESES[desde.month]} – {hasta.day:02d} {MESES[hasta.month]} {hasta.year}"


def generar_reporte_pauta(clinica, sede, desde, hasta):
    """Devuelve {texto, datos} con el reporte de captación de la sede en el período."""
    base = Lead.objects.filter(clinica=clinica)
    if sede:
        base = base.filter(sede=sede)

    # Leads que llegaron en el período.
    leads_periodo = base.filter(creado_en__date__gte=desde, creado_en__date__lte=hasta)
    total_leads = leads_periodo.count()

    # Consultas: leads cuya consulta ocurrió en el período (incluye recontactos de antes).
    consultas = list(base.filter(fecha_consulta__gte=desde, fecha_consulta__lte=hasta).select_related("anuncio"))
    total_consultas = len(consultas)

    def cuenta(estado):
        return sum(1 for c in consultas if c.estado == estado)

    proceso = cuenta(E.GANADO)
    evaluando = cuenta(E.EVALUANDO)
    pendiente = cuenta(E.PENDIENTE_PAGO)
    por_desarrollarse = cuenta(E.AGENDADO)
    no_realizada = cuenta(E.NO_REALIZADA)
    desarrolladas = proceso + evaluando + pendiente
    recontactos = sum(1 for c in consultas if c.creado_en.date() < desde)

    # Consultas por origen.
    por_origen = {}
    for c in consultas:
        k = FUENTE_LABEL.get(c.fuente, c.fuente)
        por_origen[k] = por_origen.get(k, 0) + 1
    por_origen = sorted(por_origen.items(), key=lambda x: -x[1])

    # Procesos confirmados en el período (por fecha de cierre).
    procesos_qs = base.filter(estado=E.GANADO, fecha_cierre__gte=desde, fecha_cierre__lte=hasta)
    procesos_total = procesos_qs.count()
    procesos_mes = procesos_qs.filter(fecha_consulta__gte=desde, fecha_consulta__lte=hasta).count()
    procesos_prev = procesos_total - procesos_mes

    # Publicidad que atrajo consultas.
    consultas_pauta = [c for c in consultas if c.es_pauta]
    total_pauta = len(consultas_pauta)
    por_anuncio = {}
    for c in consultas_pauta:
        if c.anuncio_id:
            key = (c.anuncio.nombre, c.anuncio.link)
        else:
            key = ("(sin anuncio especificado)", "")
        por_anuncio[key] = por_anuncio.get(key, 0) + 1
    anuncios = sorted(por_anuncio.items(), key=lambda x: -x[1])

    sede_txt = dict(Lead.Sede.choices).get(sede, "").upper() or "TODAS LAS SEDES"
    rango = _rango_txt(desde, hasta)

    L = []
    L.append(f"*{clinica.nombre.upper()} · {sede_txt} — {rango}*")
    L.append("")
    L.append(f"💬 Total leads: {total_leads}")
    L.append("")
    L.append(f"✅ *Total consultas: {total_consultas}*")
    if por_origen:
        L.append("Por origen:")
        for nombre, n in por_origen:
            L.append(f"* {nombre}: {n}")
    if recontactos:
        L.append(f"_({recontactos} provienen de leads de períodos anteriores — recontacto)_")
    L.append("")
    L.append(f"✅ *Total procesos: {procesos_total}*")
    L.append(f"* {procesos_mes} de consultas del período")
    L.append(f"* {procesos_prev} de consultantes de períodos anteriores")
    L.append("")
    L.append("_Detalle de citas_")
    L.append(f"{total_consultas} consultas agendadas")
    L.append(f"{desarrolladas} consultas desarrolladas")
    L.append(f"_{por_desarrollarse} por desarrollarse_")
    if no_realizada:
        L.append(f"_{no_realizada} no se realizaron_")
    L.append("")
    L.append("Estado de las consultas:")
    L.append(f"* {proceso} iniciaron proceso")
    L.append(f"* {evaluando} evaluando inicio")
    L.append(f"* {pendiente} pendientes de pago")
    L.append(f"* {por_desarrollarse} por desarrollarse")
    L.append("")
    L.append(f"📣 Publicidad que atrajo consultas: {total_pauta}")
    if anuncios:
        for (nombre, link), n in anuncios:
            L.append(f"* {nombre}{(' — ' + link) if link else ''} ({n})")
    L.append("")
    L.append("_Generado automáticamente por el sistema. Si hay dudas, coméntenme 🫡_")

    texto = "\n".join(L)
    datos = {
        "total_leads": total_leads, "total_consultas": total_consultas,
        "desarrolladas": desarrolladas, "por_desarrollarse": por_desarrollarse,
        "proceso": proceso, "evaluando": evaluando, "pendiente_pago": pendiente,
        "no_realizada": no_realizada, "procesos_total": procesos_total,
        "procesos_mes": procesos_mes, "procesos_prev": procesos_prev,
        "consultas_por_publicidad": total_pauta, "recontactos": recontactos,
        "por_origen": [{"origen": k, "n": v} for k, v in por_origen],
        "anuncios": [{"nombre": k[0], "link": k[1], "n": v} for k, v in anuncios],
    }
    return {"texto": texto, "datos": datos}
