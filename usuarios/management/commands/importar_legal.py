"""Importa la data legal del Excel "SEGUIMIENTO CONTRATOS Y ADENDAS" a las fichas
de Profesional (match por nombre). Lee 3 hojas:

- DATOS EQUIPO: DNI, FECHA NACIMIENTO, EMAIL, NOMBRES, APELLIDOS
- ACTUALES:     Psicologo, próximo vencimiento, última firma
- ANTIGUOS:     Psicologo, CONTRATO, ADENDA 1..8 (historial de fechas)

Las fechas vienen como número de serie de Excel. Idempotente (no duplica adendas).

    python manage.py importar_legal --archivo "C:\\ruta\\SEGUIMIENTO ...xlsx"
    python manage.py importar_legal --dry-run
"""
import re
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from core.models import Clinica
from usuarios.models import DocumentoLegal, Profesional

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
DEFAULT_PATH = r"C:\Users\mirai\Downloads\SEGUIMIENTO CONTRATOS Y ADENDAS.xlsx"
EXCEL_EPOCH = date(1899, 12, 30)


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()


def _serial_a_fecha(v):
    try:
        n = int(float(v))
    except (ValueError, TypeError):
        return None
    if n <= 0 or n > 80000:
        return None
    return EXCEL_EPOCH + timedelta(days=n)


def _dni(v):
    try:
        return str(int(float(v)))
    except (ValueError, TypeError):
        d = re.sub(r"\D", "", str(v or ""))
        return d or ""


def leer_hojas(path):
    """Devuelve {nombre_hoja: [ [celda,...], ... ]} con todas las hojas."""
    z = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall(f"{NS}si"):
            shared.append("".join(t.text or "" for t in si.iter(f"{NS}t")))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    sheets = [(s.get("name"), s.get(f"{RNS}id")) for s in wb.find(f"{NS}sheets")]
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}

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

    out = {}
    for name, rid in sheets:
        target = rels[rid]
        if not target.startswith("xl/"):
            target = "xl/" + target
        sheet = ET.fromstring(z.read(target))
        data = sheet.find(f"{NS}sheetData")
        filas, maxcol = [], 0
        for r in data.findall(f"{NS}row"):
            cells = {}
            for c in r.findall(f"{NS}c"):
                i = col_idx(c.get("r"))
                cells[i] = valor(c)
                maxcol = max(maxcol, i)
            filas.append(cells)
        ncols = maxcol + 1
        out[name] = [[(c.get(i, "") or "").strip() for i in range(ncols)] for c in filas]
    return out


class Command(BaseCommand):
    help = "Importa la data legal (contratos/adendas/datos) a las fichas de profesionales."

    def add_arguments(self, parser):
        parser.add_argument("--archivo", default=DEFAULT_PATH)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opt):
        clinica = Clinica.objects.filter(slug="itaca").first() or Clinica.objects.first()
        if clinica is None:
            self.stderr.write("No hay clínica.")
            return
        hojas = leer_hojas(opt["archivo"])
        dry = opt["dry_run"]

        # Índice de profesionales por nombre normalizado (y por apellidos para match parcial).
        profs = list(Profesional.objects.filter(clinica=clinica))
        def buscar(nombre):
            n = _norm(nombre)
            toks = [t for t in n.split() if len(t) > 2]
            if not toks:
                return None
            scored = []
            for p in profs:
                pn = _norm(p.nombre)
                score = sum(1 for t in toks if t in pn)
                if score:
                    scored.append((score, p))
            if not scored:
                return None
            scored.sort(key=lambda x: -x[0])
            best_score, best = scored[0]
            if best_score >= 2:
                return best
            # un solo token coincide: aceptar solo si ese candidato es ÚNICO (sin empate)
            top = [p for s, p in scored if s == best_score]
            return best if len(top) == 1 else None

        # 1) DATOS EQUIPO → dni + fecha_nacimiento
        datos = hojas.get("DATOS EQUIPO", [])
        actualizados = set()
        no_match = []
        if datos:
            for row in datos[1:]:
                if len(row) < 5 or not (row[3] or row[4]):
                    continue
                nombre = f"{row[3]} {row[4]}".strip()
                p = buscar(nombre)
                if not p:
                    no_match.append(nombre)
                    continue
                p.dni = _dni(row[0]) or p.dni
                nac = _serial_a_fecha(row[1])
                if nac:
                    p.fecha_nacimiento = nac
                if not dry:
                    p.save(update_fields=["dni", "fecha_nacimiento"])
                actualizados.add(p.id)

        # 2) ACTUALES → vencimiento + última firma
        actuales = hojas.get("ACTUALES", [])
        for row in actuales[2:]:
            if len(row) < 4 or not row[1]:
                continue
            p = buscar(row[1])
            if not p:
                no_match.append(row[1])
                continue
            ven = _serial_a_fecha(row[2])
            fir = _serial_a_fecha(row[3])
            if ven:
                p.contrato_vencimiento = ven
            if fir:
                p.contrato_ultima_firma = fir
            if not p.fecha_ingreso:
                # Sin fecha de ingreso real: usar la fecha del contrato más antiguo (se calcula abajo).
                pass
            if not dry:
                p.save(update_fields=["contrato_vencimiento", "contrato_ultima_firma"])
            actualizados.add(p.id)

        # 3) ANTIGUOS → historial de contrato + adendas (DocumentoLegal, sin archivo)
        antiguos = hojas.get("ANTIGUOS", [])
        docs_creados = 0
        ingreso_por_prof = {}
        if antiguos:
            cabec = antiguos[1] if len(antiguos) > 1 else []
            for row in antiguos[2:]:
                if len(row) < 3 or not row[1]:
                    continue
                p = buscar(row[1])
                if not p:
                    no_match.append(row[1])
                    continue
                for col in range(2, len(row)):
                    fecha = _serial_a_fecha(row[col])
                    if not fecha:
                        continue
                    etiqueta = (cabec[col] if col < len(cabec) else "").strip() or "Documento"
                    tipo = DocumentoLegal.Tipo.CONTRATO if "contrato" in etiqueta.lower() else DocumentoLegal.Tipo.ADENDA
                    # primera fecha (contrato) = fecha de ingreso tentativa
                    cur = ingreso_por_prof.get(p.id)
                    if cur is None or fecha < cur:
                        ingreso_por_prof[p.id] = fecha
                    if not dry:
                        _, creado = DocumentoLegal.objects.get_or_create(
                            clinica=clinica, profesional=p, tipo=tipo, fecha=fecha,
                            descripcion=etiqueta.title(),
                        )
                        docs_creados += int(creado)
                    else:
                        docs_creados += 1
                actualizados.add(p.id)

        # fecha_ingreso = contrato más antiguo (si no la tenían)
        if not dry:
            for pid, ing in ingreso_por_prof.items():
                Profesional.objects.filter(pk=pid, fecha_ingreso__isnull=True).update(fecha_ingreso=ing)

        self.stdout.write(self.style.SUCCESS(
            f"{'DRY-RUN. ' if dry else ''}Profesionales actualizados: {len(actualizados)} | "
            f"documentos (contrato/adenda) creados: {docs_creados}"))
        if no_match:
            self.stdout.write(self.style.WARNING(
                f"Sin match ({len(set(no_match))}): {sorted(set(no_match))}"))
