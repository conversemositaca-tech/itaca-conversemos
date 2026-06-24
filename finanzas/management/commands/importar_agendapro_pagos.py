"""Importa el export de PAGOS de AgendaPro (hoja 'Pagos') como Cobros (estado=pagado).

    python manage.py importar_agendapro_pagos --archivo "C:\\ruta\\reporte_de_ventas.xlsx"
    python manage.py importar_agendapro_pagos --dry-run
    python manage.py importar_agendapro_pagos --reemplazar   # borra los cobros existentes antes

Enlaza cada pago a su paciente por documento (DNI/RUC) o, si no, por nombre exacto;
si no existe, crea el paciente con los datos del pago. Carga en bloque (bulk).
"""
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import Clinica
from finanzas.models import Cobro
from pacientes.models import Paciente

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
DEFAULT_PATH = r"C:\Users\mirai\Downloads\reporte_de_ventas_377127_2026-06-24T15_12_46+00_00.xlsx"


def leer_hoja(path, nombre_hoja):
    """(encabezados, filas) de la hoja indicada, con librería estándar."""
    z = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall(f"{NS}si"):
            shared.append("".join(t.text or "" for t in si.iter(f"{NS}t")))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    sheets = [(s.get("name"), s.get(f"{RNS}id")) for s in wb.find(f"{NS}sheets")]
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    rid = next((rid for name, rid in sheets if name == nombre_hoja), sheets[0][1])
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
    to_list = lambda cells: [(cells.get(i, "") or "").strip() for i in range(ncols)]
    if not raw:
        return [], []
    return to_list(raw[0]), [to_list(c) for c in raw[1:] if any(v for v in c.values())]


def solo_digitos(s):
    return "".join(ch for ch in (s or "") if ch.isdigit())


def parse_monto(s):
    try:
        return Decimal(str(s).strip().replace(",", "."))
    except (InvalidOperation, ValueError, TypeError):
        return None


def parse_dt(s):
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}):(\d{2}))?", (s or "").strip())
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hh, mm = int(m.group(4) or 9), int(m.group(5) or 0)
    try:
        return timezone.make_aware(datetime(y, mo, d, hh, mm))
    except ValueError:
        return None


class Command(BaseCommand):
    help = "Importa los pagos de AgendaPro (hoja 'Pagos') como cobros pagados."

    def add_arguments(self, parser):
        parser.add_argument("--archivo", default=DEFAULT_PATH)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--reemplazar", action="store_true",
                            help="Borra los cobros existentes de la clínica antes de importar.")

    def handle(self, *args, **opt):
        clinica = Clinica.objects.filter(slug="itaca").first() or Clinica.objects.first()
        if clinica is None:
            self.stderr.write("No hay clínica.")
            return
        header, filas = leer_hoja(opt["archivo"], "Pagos")
        if not filas:
            self.stderr.write("La hoja 'Pagos' no tiene datos.")
            return
        low = [h.lower() for h in header]

        def idx(*subs):
            for sub in subs:
                for i, h in enumerate(low):
                    if sub in h:
                        return i
            return -1

        c_fecha = idx("fecha de pago", "fecha")
        c_local = idx("local", "sede")
        c_nombre = idx("nombre cliente", "cliente")
        c_doc = idx("dni", "ruc", "documento")
        c_email = idx("email")
        c_tel = idx("teléfono", "telefono")
        c_monto = idx("monto")
        celda = lambda f, i: f[i].strip() if 0 <= i < len(f) else ""

        # Índice de pacientes existentes (por documento y por nombre).
        by_doc, by_name = {}, {}
        for p in Paciente.objects.filter(clinica=clinica):
            if p.numero_documento:
                by_doc[solo_digitos(p.numero_documento)] = p
            by_name[p.nombre.strip().lower()] = p

        parsed, nuevos = [], {}
        for f in filas:
            nombre = celda(f, c_nombre)
            monto = parse_monto(celda(f, c_monto))
            if not nombre or monto is None or monto <= 0:
                continue
            doc = solo_digitos(celda(f, c_doc))
            fecha = parse_dt(celda(f, c_fecha)) or timezone.now()
            local = celda(f, c_local).lower()
            sede = "lima" if "lima" in local else ("piura" if "piura" in local else "")
            p = (by_doc.get(doc) if doc else None) or by_name.get(nombre.lower())
            parsed.append({"doc": doc, "nombre": nombre, "monto": monto, "fecha": fecha, "paciente": p})
            if not p:
                key = doc or ("n:" + nombre.lower())
                nuevos.setdefault(key, dict(
                    nombre=nombre[:200], numero_documento=doc, telefono=celda(f, c_tel),
                    email=celda(f, c_email), sede=sede,
                    tipo_documento=("ruc" if len(doc) == 11 else "dni"),
                ))

        self.stdout.write(f"Clínica: {clinica.nombre} | filas: {len(filas)} | "
                          f"cobros a crear: {len(parsed)} | pacientes nuevos: {len(nuevos)}")
        if opt["dry_run"]:
            self.stdout.write(self.style.WARNING("DRY-RUN: no se escribe nada."))
            for it in parsed[:3]:
                self.stdout.write(f"  {it['nombre']} | doc {it['doc'] or '-'} | S/{it['monto']} | "
                                  f"{it['fecha']:%d/%m/%Y} | {'existe' if it['paciente'] else 'NUEVO'}")
            return

        with transaction.atomic():
            if opt["reemplazar"]:
                n = Cobro.objects.filter(clinica=clinica).count()
                self.stdout.write(self.style.WARNING(f"--reemplazar: se borran {n} cobros existentes."))
                Cobro.objects.filter(clinica=clinica).delete()

            if nuevos:
                objs = [Paciente(clinica=clinica, **d) for d in nuevos.values()]
                Paciente.objects.bulk_create(objs, batch_size=500)
                for o in objs:
                    if o.numero_documento:
                        by_doc[solo_digitos(o.numero_documento)] = o
                    by_name[o.nombre.strip().lower()] = o

            cobros = []
            for it in parsed:
                p = it["paciente"] or (by_doc.get(it["doc"]) if it["doc"] else None) or by_name.get(it["nombre"].lower())
                if p is None:
                    continue
                cobros.append(Cobro(
                    clinica=clinica, paciente=p, concepto="Consulta", monto=it["monto"],
                    estado=Cobro.Estado.PAGADO, fecha=it["fecha"],
                ))
            Cobro.objects.bulk_create(cobros, batch_size=500)

        self.stdout.write(self.style.SUCCESS(
            f"Listo. Cobros creados: {len(cobros)} | pacientes nuevos: {len(nuevos)}"))
