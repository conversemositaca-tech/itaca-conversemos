"""Generador del reporte de pauta/captación en texto (listo para WhatsApp).

Reconstruye, a partir de los leads estructurados (origen, anuncio, etapa, fechas),
el mismo reporte que las asistentes arman a mano, por sede y período.
"""
import re

from .models import Lead

MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
E = Lead.Estado
FUENTE_LABEL = dict(Lead.Fuente.choices)

# Avance del embudo: si la misma persona tiene varias filas de lead (costumbre de
# registrar la consulta o el proceso como fila nueva), vale la más avanzada.
_AVANCE = {
    E.GANADO: 12, E.PENDIENTE_PAGO: 11, E.EVALUANDO: 10,
    # "Consulta realizada" va sobre los "agendó…" (la consulta ya ocurrió) y bajo
    # "evaluando inicio" (ahí ya se está decidiendo si empieza el proceso).
    E.CONSULTA_REALIZADA: 9,
    E.AGENDO_ESPERA_PAGO: 8, E.AGENDO_NO_PAGO: 7, E.AGENDADO: 6,
    E.NO_REALIZADA: 5, E.SEGUIMIENTO: 4, E.RECONTACTO: 3, E.CONTACTADO: 2,
    E.NUEVO: 1, E.PERDIDO: 0,
}


def clave_persona(lead):
    """Identifica a la persona detrás del lead: teléfono (últimos 9 dígitos) o,
    si no hay, el nombre normalizado. Sin nada, cada fila cuenta por sí sola."""
    tel = re.sub(r"\D", "", lead.telefono or "")[-9:]
    if tel:
        return "t:" + tel
    nombre = re.sub(r"\s+", " ", (lead.nombre or "").strip().lower())
    if nombre:
        return "n:" + nombre
    return f"id:{lead.pk}"


def personas_unicas(leads):
    """Colapsa filas duplicadas de la misma persona; se queda con la fila más
    avanzada del embudo (y ante empate, la más reciente). Así 'total leads' son
    personas, y las consultas/procesos son subconjuntos, no sumandos.

    El ORIGEN (anuncio y pauta) se hereda de cualquier fila de esa persona que lo
    traiga, aunque no sea la ganadora: el equipo registra el avance como fila
    nueva y ahí ya no vuelve a elegir el anuncio. Sin esto, la consulta contaba
    pero se perdía de qué anuncio vino, y el reporte mostraba un puñado de
    anuncios en vez de todos.
    """
    por_persona = {}
    con_origen = {}  # persona -> primera fila suya que sí trae anuncio/pauta
    for l in leads:
        k = clave_persona(l)
        if k not in con_origen and (l.anuncio_id or l.es_pauta):
            con_origen[k] = l
        prev = por_persona.get(k)
        if prev is None:
            por_persona[k] = l
            continue
        mejor = _AVANCE.get(l.estado, 1) > _AVANCE.get(prev.estado, 1) or (
            _AVANCE.get(l.estado, 1) == _AVANCE.get(prev.estado, 1)
            and l.creado_en > prev.creado_en
        )
        if mejor:
            por_persona[k] = l

    for k, ganador in por_persona.items():
        fuente_origen = con_origen.get(k)
        if fuente_origen is None or fuente_origen is ganador:
            continue
        if not ganador.anuncio_id and fuente_origen.anuncio_id:
            ganador.anuncio = fuente_origen.anuncio
        ganador.es_pauta = ganador.es_pauta or fuente_origen.es_pauta
    return list(por_persona.values())


def _rango_txt(desde, hasta):
    if desde.month == hasta.month and desde.year == hasta.year:
        return f"{desde.day:02d}–{hasta.day:02d} de {MESES[desde.month]} {desde.year}"
    return f"{desde.day:02d} {MESES[desde.month]} – {hasta.day:02d} {MESES[hasta.month]} {hasta.year}"


def generar_reporte_pauta(clinica, sede, desde, hasta):
    """Devuelve {texto, datos} con el reporte de captación de la sede en el período."""
    base = Lead.objects.filter(clinica=clinica)
    if sede:
        base = base.filter(sede=sede)

    # Leads que llegaron en el período. Se cuentan PERSONAS únicas: si la consulta
    # o el proceso se registró como fila aparte, no se suma de nuevo (los que
    # avanzan salen del mismo total, no se agregan encima).
    leads_periodo = base.filter(creado_en__date__gte=desde, creado_en__date__lte=hasta)
    total_leads = len(personas_unicas(list(leads_periodo)))

    # Consultas: leads cuya consulta ocurrió en el período (incluye recontactos de
    # antes). También sin duplicar persona.
    consultas = personas_unicas(list(
        base.filter(fecha_consulta__gte=desde, fecha_consulta__lte=hasta).select_related("anuncio")
    ))
    total_consultas = len(consultas)

    def cuenta(estado):
        return sum(1 for c in consultas if c.estado == estado)

    proceso = cuenta(E.GANADO)
    evaluando = cuenta(E.EVALUANDO)
    pendiente = cuenta(E.PENDIENTE_PAGO)
    agendo_no_pago = cuenta(E.AGENDO_NO_PAGO)
    agendo_espera = cuenta(E.AGENDO_ESPERA_PAGO)
    por_desarrollarse = cuenta(E.AGENDADO) + agendo_no_pago + agendo_espera
    no_realizada = cuenta(E.NO_REALIZADA)
    consulta_realizada = cuenta(E.CONSULTA_REALIZADA)
    # La consulta ya se desarrolló, aunque todavía no se sepa si inicia proceso.
    desarrolladas = proceso + evaluando + pendiente + consulta_realizada
    recontactos = sum(1 for c in consultas if c.creado_en.date() < desde)

    # Consultas por origen.
    por_origen = {}
    for c in consultas:
        k = FUENTE_LABEL.get(c.fuente, c.fuente)
        por_origen[k] = por_origen.get(k, 0) + 1
    por_origen = sorted(por_origen.items(), key=lambda x: -x[1])

    # Procesos confirmados en el período (por fecha de cierre), sin duplicar persona.
    procesos = personas_unicas(list(
        base.filter(estado=E.GANADO, fecha_cierre__gte=desde, fecha_cierre__lte=hasta)
    ))
    procesos_total = len(procesos)
    procesos_mes = sum(
        1 for p in procesos
        if p.fecha_consulta and desde <= p.fecha_consulta <= hasta
    )
    procesos_prev = procesos_total - procesos_mes

    # Procesos por origen (mismo desglose que ya se hace con las consultas: marketing
    # necesita saber de qué canal salieron los que SÍ iniciaron proceso, no solo
    # cuántos fueron).
    por_origen_procesos = {}
    for p in procesos:
        k = FUENTE_LABEL.get(p.fuente, p.fuente)
        por_origen_procesos[k] = por_origen_procesos.get(k, 0) + 1
    por_origen_procesos = sorted(por_origen_procesos.items(), key=lambda x: -x[1])

    # Publicidad que atrajo consultas.
    # Tener un anuncio elegido YA significa que vino de pauta: si el lead se
    # registró con un origen que no está marcado como pauta (p. ej. "WhatsApp
    # directo"), su anuncio igual tiene que contar.
    consultas_pauta = [c for c in consultas if c.es_pauta or c.anuncio_id]
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
    if por_origen_procesos:
        L.append("Por origen:")
        for nombre, n in por_origen_procesos:
            L.append(f"* {nombre}: {n}")
    L.append("")
    L.append("_Detalle de citas_")
    L.append(f"{total_consultas} consultas agendadas")
    L.append(f"{desarrolladas} consultas desarrolladas")
    L.append(f"_{por_desarrollarse} por desarrollarse_")
    if no_realizada:
        L.append(f"_{no_realizada} no se realizaron_")
    L.append("")
    L.append("Estado de las consultas:")
    if consulta_realizada:
        L.append(f"* {consulta_realizada} consulta realizada")
    L.append(f"* {proceso} iniciaron proceso")
    L.append(f"* {evaluando} evaluando inicio")
    L.append(f"* {pendiente} pendientes de pago")
    L.append(f"* {por_desarrollarse} por desarrollarse")
    if agendo_no_pago:
        L.append(f"* {agendo_no_pago} agendaron y no pagaron")
    if agendo_espera:
        L.append(f"* {agendo_espera} agendaron, esperando pago")
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
        "agendo_no_pago": agendo_no_pago, "agendo_espera_pago": agendo_espera,
        "proceso": proceso, "evaluando": evaluando, "pendiente_pago": pendiente,
        "consulta_realizada": consulta_realizada,
        "no_realizada": no_realizada, "procesos_total": procesos_total,
        "procesos_mes": procesos_mes, "procesos_prev": procesos_prev,
        "consultas_por_publicidad": total_pauta, "recontactos": recontactos,
        "por_origen": [{"origen": k, "n": v} for k, v in por_origen],
        "por_origen_procesos": [{"origen": k, "n": v} for k, v in por_origen_procesos],
        "anuncios": [{"nombre": k[0], "link": k[1], "n": v} for k, v in anuncios],
    }
    return {"texto": texto, "datos": datos}
