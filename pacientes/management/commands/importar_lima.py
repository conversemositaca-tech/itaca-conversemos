"""Importa el registro real de Conversemos LIMA desde el Excel operativo
("LEADS LIMA-CONVER.xlsx", hoja LEADS) al sistema.

Cada fila del Excel se reparte en tres tablas:
  - leads.Lead          -> el embudo de captación (nombre, teléfono, fuente, estado)
  - pacientes.Paciente  -> si el lead se volvió paciente (con su psicólogo y sede)
  - finanzas.Cobro      -> el historial de pagos (consulta + cada pago de cada proceso)

Por defecto REEMPLAZA solo los datos de la sede Lima (borra cobros/atenciones/citas/
adjuntos/leads/pacientes de Lima) y deja Piura intacta. Lee el xlsx con la librería
estándar (un .xlsx es un zip de XML), así no hace falta instalar nada.

    python manage.py importar_lima --dry-run     # solo muestra los conteos proyectados
    python manage.py importar_lima               # importa (reemplaza Lima)
    python manage.py importar_lima --keep         # no borra; solo agrega
    python manage.py importar_lima --archivo "C:\\ruta\\al.xlsx"
"""
import re
import unicodedata
import zipfile
from datetime import date, datetime, time, timedelta
from xml.etree import ElementTree as ET

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import Clinica
from finanzas.models import Cobro
from leads.models import Lead
from pacientes.models import Adjunto, Atencion, Cita, Paciente
from usuarios.models import Profesional

DEFAULT_PATH = r"C:\Users\mirai\Downloads\LEADS LIMA-CONVER.xlsx"

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

# Ordinales de proceso (para reconocer la columna "X proceso" por su nombre).
ORD_MAP = [
    ("doceav", "doceavo"), ("onceav", "onceavo"), ("decim", "decimo"),
    ("noven", "noveno"), ("octav", "octavo"), ("septim", "septimo"),
    ("sext", "sexto"), ("quint", "quinto"), ("cuart", "cuarto"),
    ("tercer", "tercero"), ("segund", "segundo"), ("primer", "primero"),
]

EXCEL_EPOCH = date(1899, 12, 30)  # base del sistema de fechas de Excel (Windows)

# Variantes de nombre del Excel -> nombre tal como está en el directorio.
ALIAS_PROFE = {
    "mariveth rojas": "meriveth rojas",
    "mariveth": "meriveth",
}


# --------------------------------------------------------------------------- #
# Lectura del .xlsx con librería estándar
# --------------------------------------------------------------------------- #
def leer_hoja(path, nombre_hoja="LEADS"):
    """Devuelve (encabezados, filas) de la hoja indicada. Cada fila es una lista
    de strings alineada por columna."""
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
    filas_raw = []
    maxcol = 0
    for r in data.findall(f"{NS}row"):
        cells = {}
        for c in r.findall(f"{NS}c"):
            i = col_idx(c.get("r"))
            cells[i] = valor(c)
            maxcol = max(maxcol, i)
        filas_raw.append(cells)

    ncols = maxcol + 1

    def to_list(cells):
        out = []
        for i in range(ncols):
            val = cells.get(i, "")
            out.append(val.strip() if isinstance(val, str) else val)
        return out

    if not filas_raw:
        return [], []
    encabezados = to_list(filas_raw[0])
    filas = [to_list(c) for c in filas_raw[1:]]
    return encabezados, filas


# --------------------------------------------------------------------------- #
# Parsers de datos sucios
# --------------------------------------------------------------------------- #
def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()


def limpiar_nombre(raw):
    """Quita paréntesis ('(30 años)'), notas de agenda pegadas al nombre
    ('Danicca - reprogramada', 'Alessio reprograma') y espacios sobrantes."""
    n = re.sub(r"\(.*?\)", " ", str(raw or ""))
    n = re.split(r"\s*[-–]\s+", n)[0]   # "Danicca - reprogramada", "Quevedo- Ingrid"
    n = re.split(r"\s+(?:px|no\s+se|se\s+cobr|pero)\b", n, flags=re.I)[0]  # notas pegadas
    n = re.sub(r"\b(reprogramad[ao]?|reprograma|cancelad[ao]|no\s+asist\w*)\b", " ", n, flags=re.I)
    return re.sub(r"\s+", " ", n).strip()


def nombre_valido(n):
    """Descarta basura tipo '20 años', números sueltos o cadenas sin letras."""
    n = (n or "").strip()
    if len(n) < 3:
        return False
    if not re.search(r"[A-Za-zÁÉÍÓÚáéíóúÑñ]{2,}", n):
        return False
    if re.fullmatch(r"\d+\s*a[ñn]os?", n.lower()):
        return False
    return True


def parse_money(raw):
    """Extrae el monto de una celda con texto mezclado. Quita referencias de
    sesión (s17), paréntesis y fechas dd/mm antes de tomar el primer número."""
    s = str(raw or "")
    s = re.sub(r"\(.*?\)", " ", s)                    # (s43, 44 - 45)
    s = re.sub(r"\b[sS]\d+\b", " ", s)                # s17, S3
    s = re.sub(r"\d{1,2}/\d{1,2}(?:/\d{2,4})?", " ", s)  # 28/12, 9/07
    m = re.search(r"\d+(?:[.,]\d+)?", s)
    if not m:
        return None
    val = float(m.group(0).replace(",", "."))
    # Tope anti-basura: no hay pagos reales sobre S/5000 (los reales son ≤ S/1000);
    # valores ~44000+ son fechas-serie de Excel mal tipeadas en la celda de monto.
    if val <= 0 or val > 5000:
        return None
    return round(val, 2)


def parse_fecha(raw):
    """Convierte una fecha-serie de Excel (p. ej. '45293.0') a date."""
    try:
        f = float(str(raw))
    except (TypeError, ValueError):
        return None
    if f < 20000 or f > 80000:   # rango plausible (~1954..2119); descarta '6 sesiones'
        return None
    return EXCEL_EPOCH + timedelta(days=int(f))


def edad_a_fnac(raw):
    m = re.search(r"\d{1,3}", str(raw or ""))
    if not m:
        return None
    a = int(m.group(0))
    if a <= 0 or a > 110:
        return None
    return date(date.today().year - a, 1, 1)


def map_fuente(raw):
    t = norm(raw)
    campania = ""
    if "whatsapp" in t or "wsp" in t:
        f = Lead.Fuente.WHATSAPP
    elif "insta" in t:
        f = Lead.Fuente.INSTAGRAM
    elif "face" in t or t == "fb":
        f = Lead.Fuente.FACEBOOK
    elif "tiktok" in t or "tik tok" in t:
        f = Lead.Fuente.TIKTOK
    elif "referid" in t or "recomend" in t:
        f = Lead.Fuente.REFERIDO
    elif "agendapro" in t:
        f = Lead.Fuente.AGENDAPRO
    elif "linkedin" in t:
        f = Lead.Fuente.LINKEDIN
    elif "convenio" in t:
        f = Lead.Fuente.CONVENIO
    elif "deriv" in t:
        f = Lead.Fuente.DERIVADO
    elif "web" in t or "pagina" in t or "página" in t:
        f = Lead.Fuente.WEB
    else:
        f = Lead.Fuente.OTRO
        campania = (raw or "").strip()   # conserva "Itaca Kids", etc.
    return f, campania


def map_estado_lead(raw, convertido):
    if convertido:
        return Lead.Estado.GANADO
    t = norm(raw)
    if not t:
        return Lead.Estado.NUEVO
    if "no realiz" in t or "no asist" in t or "no vino" in t or "no se present" in t:
        return Lead.Estado.NO_REALIZADA
    if "perd" in t or "descart" in t or "no interes" in t or "no contesta" in t or "no respond" in t:
        return Lead.Estado.PERDIDO
    if "confirm" in t or "agend" in t:
        return Lead.Estado.AGENDADO
    if "evalu" in t or "pend" in t:
        return Lead.Estado.EVALUANDO
    if "contact" in t or "seguim" in t:
        return Lead.Estado.CONTACTADO
    return Lead.Estado.CONTACTADO


def map_medio(raw):
    t = norm(raw)
    if "yape" in t:
        return Cobro.Medio.YAPE
    if "plin" in t:
        return Cobro.Medio.PLIN
    if "efectiv" in t:
        return Cobro.Medio.EFECTIVO
    if "tarjeta" in t or "pos" in t or "visa" in t:
        return Cobro.Medio.TARJETA
    if "transfer" in t or "mercado" in t or "bcp" in t or "interbank" in t or "deposito" in t:
        # Mercado Pago / depósitos los tratamos como transferencia (no hay medio propio).
        return Cobro.Medio.TRANSFERENCIA
    return ""


def aware(d):
    """date -> datetime con hora 12:00 en la zona de la clínica."""
    return timezone.make_aware(datetime.combine(d, time(12, 0)))


def proceso_ord(label):
    """'Primer proceso' -> 'primero'. '' si no es un encabezado de proceso."""
    n = norm(label)
    for k, v in ORD_MAP:
        if k in n:
            return v
    return ""


def mapear_columnas(encabezados):
    """Ubica las columnas por NOMBRE de encabezado (no por posición), para que el
    mismo import funcione con layouts distintos (Lima vs Piura). Devuelve:
      - cols: dict campo -> índice de columna (o None)
      - pagos: lista de (proceso_ordinal, col_pago, col_medio|None, col_fecha|None)
    """
    H = [norm(h) for h in encabezados]
    n = len(H)

    def uno(*cands):
        for i, h in enumerate(H):
            if h in cands:
                return i
        return None

    def empieza(pref):
        for i, h in enumerate(H):
            if h.startswith(pref):
                return i
        return None

    cols = {
        "fecha": uno("fecha"),                       # primera FECHA = fecha del lead
        "nombre": uno("nombre completo leads", "nombres", "nombre"),
        "lead_de": uno("lead de"),
        "celular": uno("celular"),
        "motivo": uno("motivo"),
        "paciente": uno("paciente"),
        "edad": uno("edad"),
        "celular_pac": uno("celular paciente"),
        "distrito": uno("distrito"),
        "info": empieza("informacion"),
        "psico": uno("psicologo asignado"),
        "modalidad": uno("modalidad"),
        "fecha_consulta": uno("fecha de consulta"),
        "pago_consulta": uno("pago consulta"),
        "medio_pago": uno("medio de pago"),
        "estado_lead": uno("estado lead", "estado"),
        "estado_pac": uno("estado paciente"),
    }

    pagos = []
    proc = ""
    i = 0
    while i < n:
        h = H[i]
        if "proceso" in h:
            proc = proceso_ord(encabezados[i]) or proc
        elif h.startswith("pago") and "consulta" not in h:
            medio_col = fecha_col = None
            j = i + 1
            while j < n:
                hj = H[j]
                if hj.startswith("pago") or "proceso" in hj:
                    break
                if hj == "medio" and medio_col is None:
                    medio_col = j
                if hj == "fecha" and fecha_col is None:
                    fecha_col = j
                j += 1
            pagos.append((proc, i, medio_col, fecha_col))
        i += 1
    return cols, pagos


# --------------------------------------------------------------------------- #
# Comando
# --------------------------------------------------------------------------- #
class Command(BaseCommand):
    help = "Importa el registro real de Conversemos Lima desde el Excel operativo."

    def add_arguments(self, parser):
        parser.add_argument("--archivo", default=DEFAULT_PATH, help="Ruta del .xlsx")
        parser.add_argument("--sede", default="lima", choices=["lima", "piura"], help="Sede destino.")
        parser.add_argument("--dry-run", action="store_true", help="Solo muestra conteos; no escribe.")
        parser.add_argument("--keep", action="store_true", help="No borra la sede; solo agrega.")

    def handle(self, *args, **opt):
        clinica = Clinica.objects.filter(slug="itaca").first() or Clinica.objects.first()
        if clinica is None:
            self.stderr.write("No hay clínica. Corre primero: python manage.py bootstrap_itaca")
            return

        try:
            encabezados, filas = leer_hoja(opt["archivo"], "LEADS")
        except FileNotFoundError:
            self.stderr.write(f"No se encontró el archivo: {opt['archivo']}")
            return
        sede = opt["sede"]
        cols, pagos = mapear_columnas(encabezados)
        faltan = [k for k in ("nombre", "paciente", "lead_de") if cols[k] is None]
        if faltan:
            self.stderr.write(f"No encontré columnas clave en el encabezado: {faltan}")
            return
        self.stdout.write(
            f"Leídas {len(filas)} filas de LEADS ({len(encabezados)} cols) para sede '{sede}'. "
            f"Bloques de pago detectados: {len(pagos)}."
        )

        # Índice de psicólogos de Lima por nombre normalizado / primer nombre.
        profes = list(Profesional.objects.filter(clinica=clinica))

        def buscar_profe(raw):
            n = norm(raw)
            if not n:
                return None
            n = ALIAS_PROFE.get(n, n)
            for p in profes:
                if norm(p.nombre) == n:
                    return p
            primer = ALIAS_PROFE.get(n.split()[0], n.split()[0])
            for p in profes:
                if norm(p.nombre).split()[0] == primer:
                    return p
            return None

        # ---- 1) Construir el plan en memoria ----------------------------- #
        leads_plan = []          # dicts de Lead
        pacientes = {}           # norm(nombre) -> dict con datos + cobros
        profes_no_encontrados = set()

        for fila in filas:
            def cell(idx):
                return fila[idx] if (idx is not None and idx < len(fila)) else ""

            nombre_lead = limpiar_nombre(cell(cols["nombre"]))
            nombre_pac = limpiar_nombre(cell(cols["paciente"]))
            telefono = (cell(cols["celular"]) or "").strip()
            tel_pac = (cell(cols["celular_pac"]) or "").strip()
            fuente_raw = cell(cols["lead_de"])
            estado_raw = cell(cols["estado_lead"])
            motivo = (cell(cols["motivo"]) or "").strip()
            distrito = (cell(cols["distrito"]) or "").strip()
            info = (cell(cols["info"]) or "").strip()
            psico_raw = cell(cols["psico"])
            modalidad = (cell(cols["modalidad"]) or "").strip()
            estado_pac = (cell(cols["estado_pac"]) or "").strip()
            edad_raw = cell(cols["edad"])
            f_lead = parse_fecha(cell(cols["fecha"]))
            f_consulta = parse_fecha(cell(cols["fecha_consulta"]))

            # Saltar filas totalmente vacías.
            if not nombre_lead and not nombre_pac:
                continue

            # ---- Cobros de esta fila (consulta + procesos) ----
            cobros = []
            consulta_monto = parse_money(cell(cols["pago_consulta"]))
            if consulta_monto:
                cobros.append({
                    "concepto": "Consulta inicial",
                    "monto": consulta_monto,
                    "medio": map_medio(cell(cols["medio_pago"])),
                    "fecha": f_consulta or f_lead,
                })
            # Pagos de cada proceso (columnas detectadas por encabezado).
            ult_proceso = ""
            cont = {}
            for proc_ord, pago_col, medio_col, fecha_col in pagos:
                monto = parse_money(cell(pago_col))
                if not monto:
                    continue
                cont[proc_ord] = cont.get(proc_ord, 0) + 1
                cobros.append({
                    "concepto": f"Proceso {proc_ord or '?'} · pago {cont[proc_ord]}",
                    "monto": monto,
                    "medio": map_medio(cell(medio_col)) if medio_col is not None else "",
                    "fecha": parse_fecha(cell(fecha_col)) or f_consulta or f_lead,
                })
                if proc_ord:
                    ult_proceso = proc_ord

            convertido = bool(nombre_pac) and (bool(cobros) or bool(ult_proceso) or bool(estado_pac) or bool(f_consulta))

            # ---- Paciente (si convirtió) ----
            pac_key = None
            nom = nombre_pac or nombre_lead
            if not nombre_valido(nom):
                convertido = False   # nombre basura ('20 años'): se queda como lead
            if convertido:
                pac_key = norm(nom)
                prof = buscar_profe(psico_raw)
                if psico_raw and prof is None:
                    profes_no_encontrados.add(psico_raw.strip())
                if pac_key not in pacientes:
                    pacientes[pac_key] = {
                        "nombre": nom,
                        "telefono": tel_pac or telefono,
                        "profesional": prof,
                        "psico_raw": (psico_raw or "").strip(),
                        "especialidad": motivo,
                        "direccion": distrito,
                        "fecha_nacimiento": edad_a_fnac(edad_raw),
                        "proceso": ult_proceso,
                        "cobros": [],
                    }
                else:
                    # Fila repetida del mismo paciente: completar lo que falte.
                    p = pacientes[pac_key]
                    p["telefono"] = p["telefono"] or tel_pac or telefono
                    p["profesional"] = p["profesional"] or prof
                    p["psico_raw"] = p["psico_raw"] or (psico_raw or "").strip()
                    p["direccion"] = p["direccion"] or distrito
                    p["fecha_nacimiento"] = p["fecha_nacimiento"] or edad_a_fnac(edad_raw)
                    if ult_proceso:
                        p["proceso"] = ult_proceso
                pacientes[pac_key]["cobros"].extend(cobros)

            fuente, campania = map_fuente(fuente_raw)
            notas = " · ".join(x for x in [
                f"Motivo: {motivo}" if motivo else "",
                f"Distrito: {distrito}" if distrito else "",
                f"Modalidad: {modalidad}" if modalidad else "",
                f"Estado paciente: {estado_pac}" if estado_pac else "",
                info,
            ] if x)

            leads_plan.append({
                "nombre": nombre_lead or nombre_pac,
                "telefono": telefono or tel_pac,
                "fuente": fuente,
                "campania": campania[:120],
                "especialidad": motivo[:120],
                "estado": map_estado_lead(estado_raw, convertido),
                "fecha_consulta": f_consulta,
                "fecha_cierre": (f_consulta or f_lead) if convertido else None,
                "notas": notas,
                "creado": f_lead,
                "pac_key": pac_key,
            })

        n_cobros = sum(len(p["cobros"]) for p in pacientes.values())
        total = sum(c["monto"] for p in pacientes.values() for c in p["cobros"])

        self.stdout.write(self.style.HTTP_INFO(
            f"Plan: {len(leads_plan)} leads | {len(pacientes)} pacientes | "
            f"{n_cobros} cobros | S/ {total:,.2f} en pagos."
        ))
        if profes_no_encontrados:
            self.stdout.write(self.style.WARNING(
                f"Psicólogos sin match en el directorio ({len(profes_no_encontrados)}): "
                f"{sorted(profes_no_encontrados)}"
            ))

        if opt["dry_run"]:
            self.stdout.write(self.style.SUCCESS("DRY-RUN: no se escribió nada."))
            return

        # ---- 2) Persistir ------------------------------------------------ #
        with transaction.atomic():
            if not opt["keep"]:
                nc = Cobro.objects.filter(clinica=clinica, paciente__sede=sede).delete()[0]
                nat = Atencion.objects.filter(clinica=clinica, paciente__sede=sede).delete()[0]
                nci = Cita.objects.filter(clinica=clinica, paciente__sede=sede).delete()[0]
                nad = Adjunto.objects.filter(clinica=clinica, paciente__sede=sede).delete()[0]
                nl = Lead.objects.filter(clinica=clinica, sede=sede).delete()[0]
                npx = Paciente.objects.filter(clinica=clinica, sede=sede).delete()[0]
                self.stdout.write(
                    f"Sede '{sede}' borrada: {npx} pacientes, {nl} leads, {nci} citas, "
                    f"{nat} atenciones, {nad} adjuntos, {nc} cobros."
                )

            # Psicólogos del Excel que no están en el directorio: se crean como
            # fichas INACTIVAS (fuera del directorio público) para no perder el
            # vínculo psicólogo↔paciente. orden=99 para que queden al final.
            extra_profes = {}

            def resolver_profe(p):
                if p["profesional"]:
                    return p["profesional"]
                raw = p["psico_raw"]
                if not raw:
                    return None
                k = norm(raw)
                if k not in extra_profes:
                    extra_profes[k] = Profesional.objects.create(
                        clinica=clinica, nombre=raw.title(), sede=sede,
                        activo=False, orden=99,
                    )
                return extra_profes[k]

            # Pacientes
            pac_obj = {}
            for key, p in pacientes.items():
                obj = Paciente.objects.create(
                    clinica=clinica, sede=sede, nombre=p["nombre"],
                    telefono=(p["telefono"] or "")[:40],
                    profesional=resolver_profe(p),
                    especialidad_habitual=(p["especialidad"] or "")[:120],
                    direccion=(p["direccion"] or "")[:255],
                    fecha_nacimiento=p["fecha_nacimiento"],
                    proceso=(p["proceso"] or "")[:24],
                )
                pac_obj[key] = obj

            # Cobros
            cobros_creados = 0
            for key, p in pacientes.items():
                paciente = pac_obj[key]
                for c in p["cobros"]:
                    f = c["fecha"]
                    Cobro.objects.create(
                        clinica=clinica, paciente=paciente,
                        concepto=c["concepto"][:200], monto=c["monto"],
                        estado=Cobro.Estado.PAGADO, medio_pago=c["medio"],
                        fecha=aware(f) if f else timezone.now(),
                    )
                    cobros_creados += 1

            # Leads
            leads_creados = 0
            for ld in leads_plan:
                lead = Lead(
                    clinica=clinica, sede=sede, nombre=ld["nombre"][:200],
                    telefono=(ld["telefono"] or "")[:40],
                    fuente=ld["fuente"], campania=ld["campania"],
                    especialidad=ld["especialidad"], estado=ld["estado"],
                    fecha_consulta=ld["fecha_consulta"], fecha_cierre=ld["fecha_cierre"],
                    notas=ld["notas"],
                    paciente=pac_obj.get(ld["pac_key"]) if ld["pac_key"] else None,
                )
                lead.save()
                # creado_en tiene auto_now_add; lo fijamos a la fecha real si la hay.
                if ld["creado"]:
                    Lead.objects.filter(pk=lead.pk).update(creado_en=aware(ld["creado"]))
                leads_creados += 1

        self.stdout.write(self.style.SUCCESS(
            f"Importado en '{clinica.nombre}' (sede {sede}): {len(pac_obj)} pacientes, "
            f"{leads_creados} leads, {cobros_creados} cobros."
        ))
        if extra_profes:
            self.stdout.write(self.style.WARNING(
                f"Se crearon {len(extra_profes)} psicólogos INACTIVOS (no estaban en el "
                f"directorio): {[p.nombre for p in extra_profes.values()]}"
            ))
