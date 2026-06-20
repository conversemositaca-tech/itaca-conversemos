"""Importa el HISTORIAL DE SESIONES de Conversemos Lima desde el Excel operativo,
como registros de `pacientes.Atencion` (la línea de tiempo clínica de cada paciente).

Lee DOS hojas (cubren periodos distintos → se complementan):
  - "Atenciones": bloques por psicólogo (MES, Fecha, N° sesión, Paciente, Monto).
    Trae el N° de sesión y el psicólogo. (~feb 2024 – mar 2025, 4 psicólogos.)
  - "Atenc de pacientes": pares (Fecha, Paciente) sin psicólogo ni N° de sesión.
    (~nov 2025 – feb 2026.)
Se combinan y se **deduplican** por (paciente, fecha).

IMPORTANTE: NO crea cobros. El dinero ya se cargó desde la hoja LEADS
(`importar_lima`); volver a cargarlo aquí duplicaría los ingresos.

Empareja cada nombre con los pacientes de Lima ya cargados (match exacto y por
nombre+apellido). Los que no encuentra se crean como paciente nuevo de Lima.

Por defecto REEMPLAZA las atenciones de Lima (idempotente). `--keep` solo agrega.

    python manage.py importar_atenciones_lima --dry-run
    python manage.py importar_atenciones_lima
"""
import re
import zipfile
from xml.etree import ElementTree as ET

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import Clinica
from pacientes.models import Atencion, Paciente
from pacientes.management.commands.importar_lima import (
    norm, parse_fecha, limpiar_nombre, aware, nombre_valido,
)

DEFAULT_PATH = r"C:\Users\mirai\Downloads\LEADS LIMA-CONVER.xlsx"
HOJA_GRUPOS = "Atenciones"          # bloques por psicólogo (con N° de sesión)
HOJA_PARES = "Atenc de pacientes"   # pares Fecha/Paciente (reciente)

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def leer_filas(path, nombre_hoja):
    """Devuelve TODAS las filas (incluidos encabezados) como listas de strings."""
    z = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall(f"{NS}si"):
            shared.append("".join(t.text or "" for t in si.iter(f"{NS}t")))

    wb = ET.fromstring(z.read("xl/workbook.xml"))
    sheets = [(s.get("name"), s.get(f"{RNS}id")) for s in wb.find(f"{NS}sheets")]
    rels = {}
    for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels")):
        rels[r.get("Id")] = r.get("Target")

    objetivo = nombre_hoja.strip().lower()
    rid = next((rid for nm, rid in sheets if nm.strip().lower() == objetivo), None)
    if rid is None:
        raise KeyError(f"Hoja no encontrada: {nombre_hoja}")
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
        t = c.get("t"); v = c.find(f"{NS}v")
        if t == "s":
            return shared[int(v.text)] if v is not None else ""
        if t == "inlineStr":
            is_ = c.find(f"{NS}is")
            return "".join(x.text or "" for x in is_.iter(f"{NS}t")) if is_ is not None else ""
        return v.text if v is not None else ""

    sheet = ET.fromstring(z.read(target))
    data = sheet.find(f"{NS}sheetData")
    filas = []
    maxcol = 0
    for r in data.findall(f"{NS}row"):
        cells = {}
        for c in r.findall(f"{NS}c"):
            i = col_idx(c.get("r")); cells[i] = valor(c); maxcol = max(maxcol, i)
        filas.append(cells)
    ncols = maxcol + 1
    return [[str(c.get(i, "") or "").strip() for i in range(ncols)] for c in filas]


def fmt_sesion(raw):
    t = (raw or "").strip().lower()
    if not t:
        return "Sesión"
    if "consulta" in t:
        return "Consulta inicial"
    m = re.search(r"\d+", t)
    return f"Sesión {m.group(0)}" if m else f"Sesión {raw.strip()}"


def _subheader_idx(filas, needle="paciente"):
    return next((i for i, f in enumerate(filas[:8])
                 if any(norm(x) == needle for x in f)), None)


def leer_grupos(filas):
    """Hoja con bloques por psicólogo -> [(nombre, fecha, sesion, psico)] + info de bloques."""
    sub_i = _subheader_idx(filas)
    if sub_i is None:
        return [], []
    sub = filas[sub_i]
    # La fila de nombres de psicólogo es la primera (arriba de meses/subencabezados).
    cab = filas[0] if filas else [""] * len(sub)
    bloques = []
    for p, v in enumerate(sub):
        if norm(v) != "paciente":
            continue
        fecha_col = next((i for i in range(p - 1, -1, -1) if norm(sub[i]) == "fecha"), None)
        sesion_col = next((i for i in range(p - 1, -1, -1) if "sesion" in norm(sub[i])), None)
        psico = ""
        for i in range(p, -1, -1):
            if i < len(cab) and cab[i].strip():
                psico = cab[i].strip(); break
        bloques.append({"p": p, "fecha": fecha_col, "sesion": sesion_col, "psico": psico})

    regs = []
    for fila in filas[sub_i + 1:]:
        for b in bloques:
            if b["p"] >= len(fila):
                continue
            nombre = limpiar_nombre(fila[b["p"]])
            if not nombre_valido(nombre):
                continue
            fecha = parse_fecha(fila[b["fecha"]]) if (b["fecha"] is not None and b["fecha"] < len(fila)) else None
            sesion = fila[b["sesion"]] if (b["sesion"] is not None and b["sesion"] < len(fila)) else ""
            regs.append((nombre, fecha, sesion, b["psico"]))
    return regs, bloques


def leer_pares(filas):
    """Hoja con pares (Fecha, Paciente) -> [(nombre, fecha, '', '')]."""
    sub_i = _subheader_idx(filas)
    if sub_i is None:
        return []
    sub = filas[sub_i]
    pac_cols = [i for i, v in enumerate(sub) if norm(v) == "paciente"]
    regs = []
    for fila in filas[sub_i + 1:]:
        for p in pac_cols:
            if p >= len(fila):
                continue
            nombre = limpiar_nombre(fila[p])
            if not nombre_valido(nombre):
                continue
            fecha = parse_fecha(fila[p - 1]) if p - 1 >= 0 else None
            regs.append((nombre, fecha, "", ""))
    return regs


class Command(BaseCommand):
    help = "Importa el historial de sesiones de Lima (hojas Atenciones + Atenc de pacientes)."

    def add_arguments(self, parser):
        parser.add_argument("--archivo", default=DEFAULT_PATH)
        parser.add_argument("--sede", default="lima", choices=["lima", "piura"])
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--keep", action="store_true", help="No borra; solo agrega.")

    def handle(self, *args, **opt):
        sede = opt["sede"]
        clinica = Clinica.objects.filter(slug="itaca").first() or Clinica.objects.first()
        if clinica is None:
            self.stderr.write("No hay clínica. Corre primero: bootstrap_itaca / importar_lima")
            return

        try:
            grupos, bloques = leer_grupos(leer_filas(opt["archivo"], HOJA_GRUPOS))
        except (FileNotFoundError, KeyError):
            grupos, bloques = [], []
        try:
            pares = leer_pares(leer_filas(opt["archivo"], HOJA_PARES))
        except (FileNotFoundError, KeyError):
            pares = []
        if not grupos and not pares:
            self.stderr.write(f"No pude leer las hojas de sesiones en {opt['archivo']}")
            return

        self.stdout.write(
            f"Leídas: {len(grupos)} sesiones de '{HOJA_GRUPOS}' ({len(bloques)} psicólogos) "
            f"+ {len(pares)} de '{HOJA_PARES}'."
        )

        # --- Combinar y deduplicar por (paciente, fecha) ------------------ #
        dd = {}
        sin_fecha = 0
        for nombre, fecha, sesion, psico in grupos + pares:
            # Una sesión sin fecha real no sirve para la línea de tiempo (y ensuciaría
            # la retención al caer a "hoy"). Se omite.
            if not fecha:
                sin_fecha += 1
                continue
            key = (norm(nombre), fecha.isoformat())
            cur = dd.get(key)
            # Preferir el registro que trae N° de sesión / psicólogo.
            if cur is None or (not cur[2] and sesion):
                dd[key] = (nombre, fecha, sesion, psico)
        registros = list(dd.values())
        if sin_fecha:
            self.stdout.write(self.style.WARNING(f"Sesiones omitidas por no tener fecha: {sin_fecha}"))

        # --- Emparejar con pacientes Lima existentes ---------------------- #
        pacientes = list(Paciente.objects.filter(clinica=clinica, sede=sede))
        index = {}
        for pac in pacientes:
            toks = norm(pac.nombre).split()
            for k in {norm(pac.nombre), " ".join(toks[:2]) if len(toks) >= 2 else norm(pac.nombre)}:
                index.setdefault(k, pac)

        def emparejar(nombre):
            n = norm(nombre); toks = n.split()
            for k in [n, " ".join(toks[:2]) if len(toks) >= 2 else n]:
                if k in index:
                    return index[k]
            return None

        matched = sum(1 for r in registros if emparejar(r[0]))
        nuevos = sorted({r[0] for r in registros if not emparejar(r[0])})
        fechas = [r[1] for r in registros if r[1]]
        self.stdout.write(self.style.HTTP_INFO(
            f"Sesiones únicas: {len(registros)} | con paciente existente: {matched} | "
            f"pacientes nuevos a crear: {len(nuevos)}"
        ))
        if fechas:
            self.stdout.write(f"Rango de fechas: {min(fechas)} -> {max(fechas)}")
        if nuevos:
            self.stdout.write(self.style.WARNING(f"Ejemplos sin match ({len(nuevos)}): {nuevos[:12]}"))

        if opt["dry_run"]:
            self.stdout.write(self.style.SUCCESS("DRY-RUN: no se escribió nada."))
            return

        # --- Persistir ---------------------------------------------------- #
        with transaction.atomic():
            if not opt["keep"]:
                n = Atencion.objects.filter(clinica=clinica, paciente__sede=sede).delete()[0]
                self.stdout.write(f"Atenciones de la sede '{sede}' borradas: {n}")

            creados_pac = {}
            atenciones = []
            for nombre, fecha, sesion, psico in registros:
                pac = emparejar(nombre)
                if pac is None:
                    k = norm(nombre)
                    if k not in creados_pac:
                        nuevo = Paciente.objects.create(
                            clinica=clinica, sede=sede, nombre=nombre,
                            especialidad_habitual="Terapia individual",
                        )
                        creados_pac[k] = nuevo
                        toks = norm(nombre).split()
                        for kk in {norm(nombre), " ".join(toks[:2]) if len(toks) >= 2 else norm(nombre)}:
                            index.setdefault(kk, nuevo)
                    pac = creados_pac[k]
                nota = fmt_sesion(sesion)
                if psico:
                    nota = f"{nota} · {psico}"
                atenciones.append(Atencion(
                    clinica=clinica, paciente=pac,
                    fecha=aware(fecha) if fecha else timezone.now(),
                    especialidad=pac.especialidad_habitual or "",
                    nota=nota,
                ))
            Atencion.objects.bulk_create(atenciones, batch_size=500)

        self.stdout.write(self.style.SUCCESS(
            f"Listo: {len(atenciones)} atenciones cargadas, "
            f"{len(creados_pac)} pacientes nuevos creados."
        ))
