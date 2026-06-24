"""Importa el export de CLIENTES de AgendaPro (.xlsx) como Pacientes de Itaca.

El .xlsx se lee con librería estándar (un .xlsx es un zip de XML), sin instalar
nada. El mapeo es por NOMBRE de columna (no por posición), así aguanta cambios
de orden.

    python manage.py importar_agendapro_clientes --archivo "C:\\ruta\\clientes.xlsx"
    python manage.py importar_agendapro_clientes --dry-run        # no escribe, solo reporta
    python manage.py importar_agendapro_clientes --reemplazar      # borra pacientes/citas/
                                                                   # atenciones/cobros del demo antes

Dedup por documento (DNI/RUC); si no hay documento, por nombre. Idempotente.
"""
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, datetime, time

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import Clinica
from pacientes.models import Atencion, Cita, Paciente, SeguimientoSesion

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
DEFAULT_PATH = r"C:\Users\mirai\Downloads\clientes_377127_1782266869.xlsx"


# --------------------------------------------------------------------------- #
# Lectura del .xlsx (primera hoja) con librería estándar
# --------------------------------------------------------------------------- #
def leer_primera_hoja(path):
    z = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall(f"{NS}si"):
            shared.append("".join(t.text or "" for t in si.iter(f"{NS}t")))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    sheets = [(s.get("name"), s.get(f"{RNS}id")) for s in wb.find(f"{NS}sheets")]
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    target = rels[sheets[0][1]]
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
        return [], []
    return to_list(raw[0]), [to_list(c) for c in raw[1:] if any(v for v in c.values())]


# --------------------------------------------------------------------------- #
# Parsers
# --------------------------------------------------------------------------- #
def solo_digitos(s):
    return "".join(ch for ch in (s or "") if ch.isdigit())


def parse_fecha_ddmmaa(s):
    """'07/05/2025' -> date(2025, 5, 7). None si no parsea."""
    s = (s or "").strip()
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def parse_nacimiento(dia, mes, anio):
    try:
        d, mo, y = int(dia or 0), int(mes or 0), int(anio or 0)
    except (TypeError, ValueError):
        return None
    if y < 1900 or not (1 <= mo <= 12) or not (1 <= d <= 31):
        return None
    try:
        return date(y, mo, d)
    except ValueError:
        return None


class Command(BaseCommand):
    help = "Importa el export de clientes de AgendaPro como Pacientes."

    def add_arguments(self, parser):
        parser.add_argument("--archivo", default=DEFAULT_PATH, help="Ruta del .xlsx de clientes")
        parser.add_argument("--dry-run", action="store_true", help="No escribe; solo reporta.")
        parser.add_argument("--reemplazar", action="store_true",
                            help="Borra pacientes/citas/atenciones/cobros del demo antes de importar.")

    def handle(self, *args, **opt):
        clinica = Clinica.objects.filter(slug="itaca").first() or Clinica.objects.first()
        if clinica is None:
            self.stderr.write("No hay clínica. Corre primero el bootstrap/seed.")
            return

        encabezados, filas = leer_primera_hoja(opt["archivo"])
        if not filas:
            self.stderr.write("El archivo no tiene filas de datos.")
            return

        # Índices de columna por nombre (case-insensitive, por substring).
        low = [h.lower() for h in encabezados]

        def idx(*subs):
            for sub in subs:
                for i, h in enumerate(low):
                    if sub in h:
                        return i
            return -1

        c_email = idx("email", "correo")
        c_nombres = idx("nombres", "nombre")
        c_apellidos = idx("apellidos", "apellido")
        c_doc = idx("dni o ruc", "dni", "documento")
        c_tel = idx("teléfono", "telefono", "celular")
        c_ciudad = idx("ciudad")
        c_distrito = idx("distrito")
        c_dir = idx("dirección", "direccion")
        c_gen = idx("género", "genero", "sexo")
        c_dia = idx("día del nac", "dia del nac")
        c_mes = idx("mes del nac")
        c_anio = idx("año de nac", "ano de nac")
        c_creado = idx("fecha de creación", "fecha de creacion", "creación", "creacion")

        def celda(fila, i):
            return fila[i].strip() if 0 <= i < len(fila) else ""

        self.stdout.write(f"Clínica: {clinica.nombre}  |  filas en el archivo: {len(filas)}")
        if opt["dry_run"]:
            self.stdout.write(self.style.WARNING("DRY-RUN: no se escribe nada."))

        creados = actualizados = sin_doc = 0
        muestras = []

        with transaction.atomic():
            if opt["reemplazar"]:
                from finanzas.models import Cobro
                from pacientes.models import Adjunto
                n_cob = Cobro.objects.filter(clinica=clinica).count()
                n_adj = Adjunto.objects.filter(clinica=clinica).count()
                n_at = Atencion.objects.filter(clinica=clinica).count()
                n_ci = Cita.objects.filter(clinica=clinica).count()
                n_se = SeguimientoSesion.objects.filter(clinica=clinica).count()
                n_pa = Paciente.objects.filter(clinica=clinica).count()
                self.stdout.write(self.style.WARNING(
                    f"--reemplazar: se borrarían cobros={n_cob} adjuntos={n_adj} "
                    f"atenciones={n_at} citas={n_ci} seguimientos={n_se} pacientes={n_pa}"))
                if not opt["dry_run"]:
                    Cobro.objects.filter(clinica=clinica).delete()
                    Adjunto.objects.filter(clinica=clinica).delete()
                    Atencion.objects.filter(clinica=clinica).delete()
                    Cita.objects.filter(clinica=clinica).delete()
                    SeguimientoSesion.objects.filter(clinica=clinica).delete()
                    Paciente.objects.filter(clinica=clinica).delete()

            for fila in filas:
                nombre = " ".join(p for p in [celda(fila, c_nombres), celda(fila, c_apellidos)] if p).strip()
                if not nombre:
                    continue
                doc = solo_digitos(celda(fila, c_doc))
                tipo_doc = "ruc" if len(doc) == 11 else "dni"
                tel = celda(fila, c_tel)
                email = celda(fila, c_email)
                ciudad = celda(fila, c_ciudad).lower()
                sede = "lima" if "lima" in ciudad else ("piura" if "piura" in ciudad else "")
                direccion = celda(fila, c_dir) or celda(fila, c_distrito)
                g = celda(fila, c_gen)
                genero = "femenino" if g == "1" else ("masculino" if g == "2" else "")
                fnac = parse_nacimiento(celda(fila, c_dia), celda(fila, c_mes), celda(fila, c_anio))
                creado = parse_fecha_ddmmaa(celda(fila, c_creado))

                datos = dict(
                    nombre=nombre, telefono=tel, email=email, sede=sede,
                    direccion=direccion[:255], genero=genero, fecha_nacimiento=fnac,
                    numero_documento=doc, tipo_documento=tipo_doc,
                )

                # Dedup: por documento; si no hay, por nombre exacto.
                existente = None
                if doc:
                    existente = Paciente.objects.filter(clinica=clinica, numero_documento=doc).first()
                else:
                    sin_doc += 1
                    existente = Paciente.objects.filter(clinica=clinica, nombre__iexact=nombre,
                                                        numero_documento="").first()

                if len(muestras) < 3:
                    muestras.append(datos)

                if opt["dry_run"]:
                    if existente:
                        actualizados += 1
                    else:
                        creados += 1
                    continue

                if existente:
                    for k, v in datos.items():
                        setattr(existente, k, v)
                    existente.save()
                    pac = existente
                    actualizados += 1
                else:
                    pac = Paciente.objects.create(clinica=clinica, **datos)
                    creados += 1

                # Preservar la fecha de alta de AgendaPro (creado_en es auto_now_add).
                if creado:
                    dt = timezone.make_aware(datetime.combine(creado, time(9, 0)))
                    Paciente.objects.filter(pk=pac.pk).update(creado_en=dt)

        self.stdout.write("\n--- muestra del mapeo (primeras 3) ---")
        for m in muestras:
            self.stdout.write(f"  {m['nombre']} | doc {m['numero_documento'] or '-'} | "
                              f"sede {m['sede'] or '-'} | {m['email'] or '-'} | nac {m['fecha_nacimiento'] or '-'}")

        self.stdout.write(self.style.SUCCESS(
            f"\nListo. creados={creados} actualizados={actualizados} sin_documento={sin_doc} "
            f"(total procesados={creados + actualizados})"))
