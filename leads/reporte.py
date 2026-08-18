"""Generador del reporte de pauta/captación en texto (listo para WhatsApp).

Reconstruye, a partir de los leads estructurados (origen, anuncio, etapa, fechas),
el mismo reporte que las asistentes arman a mano, por sede y período.

Todo se calcula sobre la PERSONA completa, no sobre una fila suelta: el equipo
registra cada avance como una fila nueva, y esas filas no siempre repiten lo
anterior (la fecha de consulta, el anuncio). Mirando una sola fila, el mismo
recorrido daba números distintos según cómo se tipeó el avance: quien registró
"inició proceso" sin repetir la fecha de consulta hacía que esa persona
apareciera como "consulta realizada" y como proceso "de períodos anteriores".
De ahí venía que el reporte no cuadrara con el conteo manual.
"""
import re

from .models import Lead

MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
E = Lead.Estado
FUENTE_LABEL = dict(Lead.Fuente.choices)
SEDE_LABEL = dict(Lead.Sede.choices)

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


def nombre_corto(nombre):
    """Deja el nombre de pila y la inicial del apellido: Ana María Pérez Loayza
    queda como Ana María P.

    El reporte se reenvía por WhatsApp, así que lleva lo justo para reconocer a
    la persona en el tablero, sin pasear el nombre completo ni el teléfono.
    """
    partes = [p for p in re.split(r"\s+", (nombre or "").strip()) if p]
    if not partes:
        return "(sin nombre)"
    if len(partes) == 1:
        return partes[0]
    # Con tres o más palabras se asume que las dos últimas son apellidos, así se
    # conservan los nombres compuestos (María Fernanda, Juan Carlos).
    corte = max(1, len(partes) - 2) if len(partes) >= 3 else 1
    return " ".join(partes[:corte]) + " " + partes[corte][0].upper() + "."


class Persona:
    """Una persona del embudo, con todas sus filas consolidadas.

    Cada dato se toma de donde exista, no de la fila más avanzada: la fecha de
    consulta puede estar en la fila vieja y el estado en la nueva.
    """

    def __init__(self, filas):
        self.filas = sorted(filas, key=lambda l: l.creado_en)
        principal = max(filas, key=lambda l: (_AVANCE.get(l.estado, 1), l.creado_en))
        self.principal = principal
        self.estado = principal.estado
        self.nombre = principal.nombre or next((f.nombre for f in self.filas if f.nombre), "")
        self.sede = next((f.sede for f in self.filas if f.sede), "")
        self.primer_contacto = self.filas[0].creado_en
        self.fechas_consulta = sorted({f.fecha_consulta for f in self.filas if f.fecha_consulta})
        self.fechas_cierre = sorted({f.fecha_cierre for f in self.filas if f.fecha_cierre})
        # El origen se hereda de cualquier fila que lo traiga: al registrar el
        # avance ya no se vuelve a elegir el anuncio.
        con_anuncio = next((f for f in self.filas if f.anuncio_id), None)
        self.anuncio = con_anuncio.anuncio if con_anuncio else None
        self.anuncio_id = con_anuncio.anuncio_id if con_anuncio else None
        self.es_pauta = any(f.es_pauta for f in self.filas) or bool(self.anuncio_id)
        # La fuente es CÓMO LLEGÓ: la de su primera fila.
        self.fuente = self.filas[0].fuente

    @property
    def fecha_consulta(self):
        return self.fechas_consulta[0] if self.fechas_consulta else None

    @property
    def fuente_label(self):
        return FUENTE_LABEL.get(self.fuente, self.fuente)

    @property
    def sede_label(self):
        return SEDE_LABEL.get(self.sede, "")

    @property
    def estado_label(self):
        return self.principal.get_estado_display()

    def consulto_entre(self, desde, hasta):
        return any(desde <= f <= hasta for f in self.fechas_consulta)

    def cerro_entre(self, desde, hasta):
        return any(desde <= f <= hasta for f in self.fechas_cierre)


def personas_de(leads):
    """Agrupa las filas por persona. Devuelve [Persona]."""
    por_clave = {}
    for l in leads:
        por_clave.setdefault(clave_persona(l), []).append(l)
    return [Persona(filas) for filas in por_clave.values()]


def personas_unicas(leads):
    """Compatibilidad: una fila representativa por persona (la más avanzada), con
    el origen ya heredado. El reporte usa `personas_de`."""
    out = []
    for p in personas_de(leads):
        fila = p.principal
        if not fila.anuncio_id and p.anuncio_id:
            fila.anuncio = p.anuncio
        fila.es_pauta = fila.es_pauta or p.es_pauta
        out.append(fila)
    return out


def _rango_txt(desde, hasta):
    if desde.month == hasta.month and desde.year == hasta.year:
        return f"{desde.day:02d}–{hasta.day:02d} de {MESES[desde.month]} {desde.year}"
    return (f"{desde.day:02d} de {MESES[desde.month]} – "
            f"{hasta.day:02d} de {MESES[hasta.month]} {hasta.year}")


def _por_origen(personas):
    d = {}
    for p in personas:
        d[p.fuente_label] = d.get(p.fuente_label, 0) + 1
    return sorted(d.items(), key=lambda x: -x[1])


def generar_reporte_pauta(clinica, sede, desde, hasta):
    """Devuelve {texto, datos} con el reporte de captación de la sede en el período."""
    base = Lead.objects.filter(clinica=clinica)
    if sede:
        base = base.filter(sede=sede)

    # Una sola pasada: todas las filas, agrupadas por persona. Los subtotales de
    # abajo son subconjuntos de esta misma lista, así que no pueden contradecirse.
    personas = personas_de(list(base.select_related("anuncio")))

    total_leads = sum(1 for p in personas if desde <= p.primer_contacto.date() <= hasta)

    # Consultas: personas cuya consulta ocurrió en el período (incluye
    # recontactos de antes).
    consultas = sorted(
        [p for p in personas if p.consulto_entre(desde, hasta)],
        key=lambda p: (p.fecha_consulta, p.nombre.lower()),
    )
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

    # Recontactos: la persona ya existía antes del período.
    de_antes = [c for c in consultas if c.primer_contacto.date() < desde]
    recontactos = len(de_antes)

    por_origen = _por_origen(consultas)
    por_origen_antes = _por_origen(de_antes)

    # Procesos confirmados en el período (por fecha de cierre).
    procesos = [p for p in personas if p.estado == E.GANADO and p.cerro_entre(desde, hasta)]
    procesos_total = len(procesos)
    procesos_mes = sum(1 for p in procesos if p.consulto_entre(desde, hasta))
    procesos_prev = procesos_total - procesos_mes
    por_origen_procesos = _por_origen(procesos)

    # Publicidad que atrajo consultas. Tener un anuncio elegido YA significa que
    # vino de pauta, aunque el origen registrado no esté marcado como tal.
    consultas_pauta = [c for c in consultas if c.es_pauta]
    total_pauta = len(consultas_pauta)
    por_anuncio = {}
    for c in consultas_pauta:
        key = (c.anuncio.nombre, c.anuncio.link) if c.anuncio_id else ("(sin anuncio especificado)", "")
        d = por_anuncio.setdefault(key, {"n": 0, "sedes": {}})
        d["n"] += 1
        etiqueta = c.sede_label or "sin sede"
        d["sedes"][etiqueta] = d["sedes"].get(etiqueta, 0) + 1
    anuncios = sorted(por_anuncio.items(), key=lambda x: -x[1]["n"])

    sede_txt = SEDE_LABEL.get(sede, "").upper() or "TODAS LAS SEDES"
    rango = _rango_txt(desde, hasta)
    # Sin filtro de sede, cada anuncio dice de dónde vino cada consulta: con las
    # dos sedes juntas no había forma de saber cuál era de Piura y cuál de Lima.
    detallar_sede = not sede

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
        for nombre, n in por_origen_antes:
            L.append(f"_* {nombre}: {n}_")
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
        for (nombre, link), d in anuncios:
            detalle = ""
            if detallar_sede and d["sedes"]:
                partes = ", ".join(f"{s} {n}" for s, n in sorted(d["sedes"].items(), key=lambda x: -x[1]))
                detalle = f" · {partes}"
            L.append(f"* {nombre}{(' — ' + link) if link else ''} ({d['n']}{detalle})")

    # Lead por lead, para poder cuadrar el número de arriba contra el tablero.
    if consultas:
        L.append("")
        L.append(f"_Las {total_consultas} consultas, una por una_")
        for i, c in enumerate(consultas, 1):
            trozos = [c.fuente_label]
            if c.anuncio_id:
                trozos.append(c.anuncio.nombre)
            if detallar_sede and c.sede_label:
                trozos.append(c.sede_label)
            marca = " · viene de antes" if c.primer_contacto.date() < desde else ""
            L.append(f"{i}. {nombre_corto(c.nombre)} — {c.fecha_consulta:%d/%m} · "
                     f"{' · '.join(trozos)} → {c.estado_label}{marca}")

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
        "por_origen_recontacto": [{"origen": k, "n": v} for k, v in por_origen_antes],
        "por_origen_procesos": [{"origen": k, "n": v} for k, v in por_origen_procesos],
        "anuncios": [{
            "nombre": k[0], "link": k[1], "n": v["n"],
            "por_sede": [{"sede": s, "n": n} for s, n in sorted(v["sedes"].items(), key=lambda x: -x[1])],
        } for k, v in anuncios],
        "consultas_detalle": [{
            "nombre": nombre_corto(c.nombre),
            "fecha": c.fecha_consulta.isoformat() if c.fecha_consulta else "",
            "origen": c.fuente_label,
            "anuncio": c.anuncio.nombre if c.anuncio_id else "",
            "sede": c.sede_label,
            "estado": c.estado_label,
            "de_antes": c.primer_contacto.date() < desde,
        } for c in consultas],
    }
    return {"texto": texto, "datos": datos}
