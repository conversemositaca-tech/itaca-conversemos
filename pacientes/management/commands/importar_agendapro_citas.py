"""Importa el export de RESERVAS/CITAS de AgendaPro (.xlsx) como Citas de Itaca.

    python manage.py importar_agendapro_citas --archivo "C:\\ruta\\reservas.xlsx"
    python manage.py importar_agendapro_citas --dry-run          # no escribe, solo reporta
    python manage.py importar_agendapro_citas --hoja "Reservas"   # fuerza la hoja
    python manage.py importar_agendapro_citas --sede lima         # fuerza la sede de todas
    python manage.py importar_agendapro_citas --reemplazar         # borra las citas antes

Mapea por NOMBRE de columna (no por posición). Enlaza cada cita a su paciente por
documento (DNI/RUC) o por nombre; si no existe, lo crea con lo que traiga la fila.
El psicólogo se enlaza por nombre a un usuario del sistema (si no matchea, la cita
queda sin médico y el nombre del profesional se guarda en las notas). Idempotente:
NO duplica una cita que ya exista para el mismo paciente y la misma fecha/hora.
"""
import re
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, datetime, time

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import Clinica
from pacientes.models import Cita, Paciente
from usuarios.models import Profesional, Usuario

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
DEFAULT_PATH = r"C:\Users\mirai\Downloads\reservas.xlsx"
# Nombres de hoja habituales del export de AgendaPro (se prueba en orden).
HOJAS = ["Reservas", "Citas", "Agenda", "Reservas y citas", "Hoja1"]


# --------------------------------------------------------------------------- #
# Lectura de una hoja del .xlsx con librería estándar (un .xlsx es un zip de XML)
# --------------------------------------------------------------------------- #
def leer_hoja(path, nombre_hoja=None):
    """(nombre_real, encabezados, filas) de la hoja pedida (o la 1ª que exista)."""
    z = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall(f"{NS}si"):
            shared.append("".join(t.text or "" for t in si.iter(f"{NS}t")))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    sheets = [(s.get("name"), s.get(f"{RNS}id")) for s in wb.find(f"{NS}sheets")]
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}

    nombre_real, rid = sheets[0]
    if nombre_hoja:
        rid = next((r for name, r in sheets if name.lower() == nombre_hoja.lower()), None)
        nombre_real = nombre_hoja
        if rid is None:
            return None, [], []
    else:
        for cand in HOJAS:
            hit = next(((name, r) for name, r in sheets if name.lower() == cand.lower()), None)
            if hit:
                nombre_real, rid = hit
                break

    target = rels[rid]
    if not target.startswith("xl/"):
        target = "xl/" + target

    def col_idx(ref):
        letters = re.match(r"[A-Z]+", ref).group(0)
        n = 0
        for ch in letters:
            n = n * 26 + (ord(ch) - 64)
        return n - 1

    def valor(c):
        t = c.get("t")
        v = c.find(f"{NS}v")
        if t == "s":
            return shared[int(v.text)] if v is not None else ""
        if t == "inlineStr":
            is_ = c.find(f"{NS}is")
            return "".join(x.text or "" for x in is_.iter(f"{NS}t")) if is_ is not None else ""
        return v.text if v is not None else ""

    sheet = ET.fromstring(z.read(target))
    data = sheet.find(f"{NS}sheetData")
    raw, maxcol = [], 0
    for r in data.findall(f"{NS}row"):
        cells = {}
        for c in r.findall(f"{NS}c"):
            i = col_idx(c.get("r"))
            cells[i] = valor(c)
            maxcol = max(maxcol, i)
        raw.append(cells)
    ncols = maxcol + 1

    def to_list(cells):
        return [(cells.get(i, "") or "").strip() for i in range(ncols)]

    if not raw:
        return nombre_real, [], []
    return nombre_real, to_list(raw[0]), [to_list(c) for c in raw[1:] if any(v for v in c.values())]


# --------------------------------------------------------------------------- #
# Parsers / helpers
# --------------------------------------------------------------------------- #
def solo_digitos(s):
    return "".join(ch for ch in (s or "") if ch.isdigit())


def norm(s):
    """minúsculas sin tildes, para comparar nombres/estados."""
    s = (s or "").strip().lower()
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def parse_fecha(s):
    """'07/05/2025' o '2025-05-07' -> date. None si no parsea."""
    s = (s or "").strip()
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
        if not m:
            return None
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def parse_hora(s):
    """'10:30', '10:30 AM', '2:00 p.m.' -> (hh, mm). Default (9, 0) si no hay."""
    s = (s or "").strip()
    m = re.search(r"(\d{1,2}):(\d{2})", s)
    if not m:
        return 9, 0
    hh, mm = int(m.group(1)), int(m.group(2))
    low = s.lower()
    if ("p" in low and "m" in low and low.index("p") > m.start()) and hh < 12:
        hh += 12
    if ("a" in low and "m" in low) and hh == 12:
        hh = 0
    hh = min(hh, 23)
    return hh, mm


def parse_dt_combinado(s):
    """'07/05/2025 10:30' en una sola celda -> datetime aware. None si no parsea."""
    f = parse_fecha(s)
    if not f:
        return None
    hh, mm = parse_hora(s)
    try:
        return timezone.make_aware(datetime.combine(f, time(hh, mm)))
    except (ValueError, OverflowError):
        return None


def map_estado(s):
    """Estado de AgendaPro -> Estado de Cita de Itaca."""
    n = norm(s)
    if not n:
        return Cita.Estado.AGENDADA
    if "cancel" in n or "anul" in n:
        return Cita.Estado.CANCELADA
    if "no asis" in n or "no show" in n or "noshow" in n or "ausente" in n or "no lleg" in n or "no vino" in n:
        return Cita.Estado.NO_ASISTIO
    if "reprogram" in n:
        return Cita.Estado.REPROGRAMADA
    if any(k in n for k in ("atend", "finaliz", "complet", "realiz", "asisti", "lleg", "presente", "vino")):
        return Cita.Estado.ASISTIO
    if "confirm" in n:
        return Cita.Estado.CONFIRMADA
    if "espera" in n:
        return Cita.Estado.EN_ESPERA
    return Cita.Estado.AGENDADA


class Command(BaseCommand):
    help = "Importa las reservas/citas de AgendaPro como Citas de la agenda."

    def add_arguments(self, parser):
        parser.add_argument("--archivo", default=DEFAULT_PATH, help="Ruta del .xlsx de reservas/citas")
        parser.add_argument("--hoja", default="", help="Nombre exacto de la hoja (si no, se autodetecta)")
        parser.add_argument("--dry-run", action="store_true", help="No escribe; solo reporta.")
        parser.add_argument("--reemplazar", action="store_true",
                            help="Borra TODAS las citas de la clínica antes de importar.")
        parser.add_argument("--sede", choices=["lima", "piura"], default="",
                            help="Fuerza la sede de TODAS las citas (ignora la columna Local).")

    def handle(self, *args, **opt):
        clinica = Clinica.objects.filter(slug="itaca").first() or Clinica.objects.first()
        if clinica is None:
            self.stderr.write("No hay clínica. Corre primero el bootstrap/seed.")
            return

        nombre_hoja, header, filas = leer_hoja(opt["archivo"], opt["hoja"] or None)
        if not filas:
            self.stderr.write(f"La hoja {'«'+opt['hoja']+'»' if opt['hoja'] else '(autodetectada)'} no tiene filas.")
            return
        low = [h.lower() for h in header]

        def idx(*subs):
            for sub in subs:
                for i, h in enumerate(low):
                    if sub in h:
                        return i
            return -1

        c_dt = idx("fecha y hora", "fecha/hora", "fecha reserva", "inicio")
        c_fecha = idx("fecha")
        c_hora = idx("hora")
        c_nombre = idx("nombre cliente", "cliente", "paciente", "nombre")
        c_doc = idx("dni o ruc", "dni", "ruc", "documento")
        c_tel = idx("teléfono", "telefono", "celular")
        c_email = idx("email", "correo")
        c_prof = idx("profesional", "especialista", "terapeuta", "psic", "atiende", "recurso")
        c_serv = idx("servicio", "prestación", "prestacion", "tipo de cita", "motivo")
        c_estado = idx("estado", "status")
        c_local = idx("local", "sede", "sucursal")
        c_notas = idx("comentario", "nota", "observ")
        celda = lambda f, i: f[i].strip() if 0 <= i < len(f) else ""

        # Índice de médicos: nombre normalizado -> Usuario (rol medico).
        medicos = {}
        for prof in Profesional.objects.filter(clinica=clinica, usuario__isnull=False).select_related("usuario"):
            if getattr(prof.usuario, "rol", None) == Usuario.Rol.MEDICO:
                medicos[norm(prof.nombre)] = prof.usuario
        for u in Usuario.objects.filter(rol=Usuario.Rol.MEDICO):
            nom = norm(getattr(u, "nombre", "") or "")
            if nom and nom not in medicos:
                medicos[nom] = u

        def buscar_medico(nombre):
            n = norm(nombre)
            if not n:
                return None
            if n in medicos:
                return medicos[n]
            # match laxo: el nombre del archivo contiene o está contenido en uno del sistema
            for k, u in medicos.items():
                if k and (k in n or n in k):
                    return u
            # por primer token (nombre de pila)
            tok = n.split()[0] if n.split() else ""
            for k, u in medicos.items():
                if tok and tok in k.split():
                    return u
            return None

        # Índice de pacientes existentes (por documento y por nombre).
        by_doc, by_name = {}, {}
        for p in Paciente.objects.filter(clinica=clinica):
            if p.numero_documento:
                by_doc[solo_digitos(p.numero_documento)] = p
            by_name[norm(p.nombre)] = p

        self.stdout.write(f"Clínica: {clinica.nombre}  |  hoja: {nombre_hoja}  |  filas: {len(filas)}")
        self.stdout.write(
            "Columnas detectadas → "
            f"fecha={header[c_fecha] if c_fecha >= 0 else '-'} | hora={header[c_hora] if c_hora >= 0 else '-'} | "
            f"dt={header[c_dt] if c_dt >= 0 else '-'} | cliente={header[c_nombre] if c_nombre >= 0 else '-'} | "
            f"prof={header[c_prof] if c_prof >= 0 else '-'} | servicio={header[c_serv] if c_serv >= 0 else '-'} | "
            f"estado={header[c_estado] if c_estado >= 0 else '-'} | local={header[c_local] if c_local >= 0 else '-'}")
        if c_nombre < 0 or (c_dt < 0 and c_fecha < 0):
            self.stderr.write("No encuentro columna de cliente y/o de fecha. Revisa el archivo o pasa --hoja.")
            return

        # 1) Parsear filas (sin tocar la BD).
        parsed, nuevos, sin_medico = [], {}, {}
        saltadas_sin_fecha = 0
        for f in filas:
            nombre = celda(f, c_nombre)
            if not nombre:
                continue
            inicio = parse_dt_combinado(celda(f, c_dt)) if c_dt >= 0 else None
            if inicio is None and c_fecha >= 0:
                fch = parse_fecha(celda(f, c_fecha))
                if fch:
                    hh, mm = parse_hora(celda(f, c_hora)) if c_hora >= 0 else (9, 0)
                    try:
                        inicio = timezone.make_aware(datetime.combine(fch, time(hh, mm)))
                    except (ValueError, OverflowError):
                        inicio = None
            if inicio is None:
                saltadas_sin_fecha += 1
                continue

            doc = solo_digitos(celda(f, c_doc))
            if len(doc) > 12:
                doc = ""
            prof_nombre = celda(f, c_prof)
            servicio = celda(f, c_serv)
            estado = map_estado(celda(f, c_estado))
            local = norm(celda(f, c_local))
            sede = opt["sede"] or ("lima" if "lima" in local else "piura" if "piura" in local else "")
            medico = buscar_medico(prof_nombre)
            if prof_nombre and medico is None:
                sin_medico[norm(prof_nombre)] = prof_nombre
            notas = celda(f, c_notas)
            if prof_nombre and medico is None:
                notas = (f"Profesional (AgendaPro): {prof_nombre}. " + notas).strip()
            modal = Cita.Modalidad.VIRTUAL if any(
                k in norm(servicio + " " + notas) for k in ("virtual", "online", "zoom", "meet")
            ) else Cita.Modalidad.PRESENCIAL

            p = (by_doc.get(doc) if doc else None) or by_name.get(norm(nombre))
            parsed.append(dict(doc=doc, nombre=nombre, inicio=inicio, medico=medico, especialidad=servicio[:120],
                               estado=estado, sede=sede, modalidad=modal, notas=notas[:2000], paciente=p))
            if not p:
                key = doc or ("n:" + norm(nombre))
                nuevos.setdefault(key, dict(
                    nombre=nombre[:200], numero_documento=doc, telefono=celda(f, c_tel),
                    email=celda(f, c_email), sede=sede,
                    tipo_documento=("ruc" if len(doc) == 11 else "dni"),
                ))

        self.stdout.write(
            f"\ncitas a evaluar: {len(parsed)} | pacientes nuevos: {len(nuevos)} | "
            f"filas sin fecha válida (saltadas): {saltadas_sin_fecha}")
        if sin_medico:
            muestra = list(sin_medico.values())[:8]
            self.stdout.write(self.style.WARNING(
                f"Profesionales SIN match en el sistema ({len(sin_medico)}): {muestra}"
                + (" …" if len(sin_medico) > 8 else "")
                + "  (esas citas quedan sin médico; el nombre va en las notas)"))

        if opt["dry_run"]:
            self.stdout.write(self.style.WARNING("\nDRY-RUN: no se escribe nada. Muestra (primeras 5):"))
            for it in parsed[:5]:
                self.stdout.write(
                    f"  {it['inicio']:%d/%m/%Y %H:%M} | {it['nombre']} | doc {it['doc'] or '-'} | "
                    f"{it['especialidad'] or '-'} | {it['estado']} | "
                    f"médico {(it['medico'] and getattr(it['medico'], 'nombre', 'sí')) or '—'} | "
                    f"{'paciente existe' if it['paciente'] else 'paciente NUEVO'}")
            return

        # 2) Cargar.
        creadas = duplicadas = 0
        with transaction.atomic():
            if opt["reemplazar"]:
                n = Cita.objects.filter(clinica=clinica).count()
                self.stdout.write(self.style.WARNING(f"--reemplazar: se borran {n} citas existentes."))
                Cita.objects.filter(clinica=clinica).delete()

            if nuevos:
                objs = [Paciente(clinica=clinica, **d) for d in nuevos.values()]
                Paciente.objects.bulk_create(objs, batch_size=500)
                for o in objs:
                    if o.numero_documento:
                        by_doc[solo_digitos(o.numero_documento)] = o
                    by_name[norm(o.nombre)] = o

            # Citas ya existentes (paciente_id, minuto de inicio) para no duplicar.
            existentes = set()
            if not opt["reemplazar"]:
                for pid, ini in Cita.objects.filter(clinica=clinica).values_list("paciente_id", "inicio"):
                    existentes.add((pid, timezone.localtime(ini).strftime("%Y%m%d%H%M")))

            nuevas_citas, vistos = [], set()
            for it in parsed:
                p = it["paciente"] or (by_doc.get(it["doc"]) if it["doc"] else None) or by_name.get(norm(it["nombre"]))
                if p is None:
                    continue
                clave = (p.id, timezone.localtime(it["inicio"]).strftime("%Y%m%d%H%M"))
                if clave in existentes or clave in vistos:
                    duplicadas += 1
                    continue
                vistos.add(clave)
                nuevas_citas.append(Cita(
                    clinica=clinica, paciente=p, medico=it["medico"], inicio=it["inicio"],
                    especialidad=it["especialidad"], estado=it["estado"], sede=it["sede"],
                    modalidad=it["modalidad"], notas=it["notas"],
                ))
            Cita.objects.bulk_create(nuevas_citas, batch_size=500)
            creadas = len(nuevas_citas)

        self.stdout.write(self.style.SUCCESS(
            f"\nListo. Citas creadas: {creadas} | omitidas por duplicado: {duplicadas} | "
            f"pacientes nuevos: {len(nuevos)}"))
