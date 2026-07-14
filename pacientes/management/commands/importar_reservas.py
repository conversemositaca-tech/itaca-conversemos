"""Importa el export de RESERVAS de AgendaPro (hoja 'Reservas') al sistema.

Cada fila del Excel es una CITA. Se crea/reutiliza el paciente y se agrega su cita:
  - Paciente: se busca por DNI (o, si no hay, por los últimos 9 dígitos del
    teléfono). Si existe, se REUTILIZA (solo se rellenan campos vacíos); si no,
    se crea. Nunca se borra ni se pisa data existente (estrategia "add-only").
  - Cita: se crea con fecha/hora, sede, servicio, categoría, estado y N° de sesión.
    Es IDEMPOTENTE: si ya existe una cita del mismo paciente a la misma hora, se
    salta (se puede re-ejecutar sin duplicar).

Lee el .xlsx con librería estándar (reusa `leer_hoja` de importar_lima), así no
hace falta instalar openpyxl en el servidor.

    python manage.py importar_reservas --dry-run          # solo conteos, no escribe
    python manage.py importar_reservas                    # importa (add-only)
    python manage.py importar_reservas --archivo "/ruta/reservas.xlsx"
    python manage.py importar_reservas --limit 50 --dry-run   # prueba con 50 filas
"""
import re
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import Clinica
from pacientes.models import Cita, Paciente
from usuarios.models import Profesional
from pacientes.management.commands.importar_lima import leer_hoja, norm

DEFAULT_PATH = r"C:\Users\mirai\Downloads\reservas_377127_1784004364.xlsx"

# --- Índices de columna (por si el orden cambia, se remapea por nombre) ---
COLS = {
    "fecha": "Fecha de realización", "local": "Local", "ncliente": "N° de Cliente",
    "nombre": "Nombre", "apellido": "Apellido", "email": "E-mail", "telefono": "Teléfono",
    "doc": "DNI o RUC", "servicio": "Servicio", "nsesion": "Nº de sesión",
    "prestador": "Prestador", "estado": "Estado", "estado_pago": "Estado de pago",
    "comentario": "Comentario interno", "origen": "Origen",
}

ESTADO_MAP = {
    "asiste": Cita.Estado.ASISTIO,
    "confirmado": Cita.Estado.CONFIRMADA,
    "cancelado": Cita.Estado.CANCELADA,
    "no asiste": Cita.Estado.NO_ASISTIO,
    "reservado": Cita.Estado.AGENDADA,
}


def solo_dig(s):
    return "".join(c for c in str(s or "") if c.isdigit())


def limpiar_doc(raw):
    """DNI peruano = 8 dígitos; RUC = 11. Un 'DNI' de 9 dígitos (suele ser un
    teléfono mal puesto en la columna) NO se toma como documento."""
    d = solo_dig(raw)
    return d if len(d) in (8, 11) else ""


def sin_titulo(s):
    """'Psic. Sofia Ferreyra' -> 'sofia ferreyra' (para comparar prestadores)."""
    n = norm(s)
    n = re.sub(r"^(lic|ps|psic|dr|dra|mg|mtro|mtra)\.?\s+", "", n)
    return n.strip()


def parse_dt(s):
    """'11/07/2026 13:00' -> datetime aware. None si no parsea."""
    s = str(s or "").strip()
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(s, fmt)
            return timezone.make_aware(dt, timezone.get_current_timezone())
        except ValueError:
            continue
    return None


def sede_de(local):
    n = norm(local)
    if "piura" in n:
        return "piura"
    if "lima" in n:
        return "lima"
    return ""


def categoria_de(serv):
    n = norm(serv)
    if "constancia" in n or "informe" in n:
        return Cita.Categoria.CONSTANCIAS
    if "pareja" in n:
        return Cita.Categoria.PAREJAS
    if "infantojuvenil" in n or "nino" in n or "nin" in n or "adolescent" in n:
        return Cita.Categoria.INFANTOJUVENIL
    if "adulto" in n:
        return Cita.Categoria.ADULTOS
    return ""


class Command(BaseCommand):
    help = "Importa el export de reservas de AgendaPro (add-only, dedup por DNI)."

    def add_arguments(self, parser):
        parser.add_argument("--archivo", default=DEFAULT_PATH, help="Ruta del .xlsx")
        parser.add_argument("--dry-run", action="store_true", help="Solo conteos; no escribe.")
        parser.add_argument("--limit", type=int, default=0, help="Procesar solo las primeras N filas (prueba).")

    def handle(self, *args, **opt):
        clinica = Clinica.objects.filter(slug="itaca").first() or Clinica.objects.first()
        if clinica is None:
            self.stderr.write("No hay clínica. Corre primero: python manage.py bootstrap_itaca")
            return
        try:
            encabezados, filas = leer_hoja(opt["archivo"], "Reservas")
        except FileNotFoundError:
            self.stderr.write(f"No se encontró el archivo: {opt['archivo']}")
            return
        if opt["limit"]:
            filas = filas[: opt["limit"]]

        # Mapea nombre de columna -> índice (tolera pequeñas variantes por norma).
        Hn = [norm(h) for h in encabezados]
        idx = {}
        for k, nombre in COLS.items():
            objetivo = norm(nombre)
            idx[k] = Hn.index(objetivo) if objetivo in Hn else None
        faltan = [k for k in ("fecha", "nombre", "prestador", "estado") if idx[k] is None]
        if faltan:
            self.stderr.write(f"Faltan columnas clave en el encabezado: {faltan}\nEncabezados: {encabezados}")
            return
        self.stdout.write(f"Leídas {len(filas)} filas de 'Reservas' ({len(encabezados)} columnas).")

        def cell(fila, k):
            i = idx[k]
            return fila[i] if (i is not None and i < len(fila)) else ""

        # --- Índices en memoria de lo que YA existe (para no duplicar) ---
        pac_por_doc, pac_por_tel = {}, {}
        for p in Paciente.objects.filter(clinica=clinica).only("id", "numero_documento", "telefono"):
            if p.numero_documento:
                pac_por_doc.setdefault(p.numero_documento, p)
            t9 = solo_dig(p.telefono)[-9:]
            if len(t9) >= 9:
                pac_por_tel.setdefault(t9, p)
        citas_existentes = set(
            Cita.objects.filter(clinica=clinica).values_list("paciente_id", "inicio")
        )

        # Directorio de psicólogos (para enlazar prestador -> Profesional/medico).
        profes = list(Profesional.objects.filter(clinica=clinica).select_related("usuario"))
        prof_por_nombre = {}
        prof_por_primer = {}
        for p in profes:
            prof_por_nombre.setdefault(sin_titulo(p.nombre), p)
            partes = sin_titulo(p.nombre).split()
            if partes:
                prof_por_primer.setdefault(partes[0], p)

        def buscar_prof(raw):
            k = sin_titulo(raw)
            if not k:
                return None
            if k in prof_por_nombre:
                return prof_por_nombre[k]
            primer = k.split()[0] if k.split() else ""
            return prof_por_primer.get(primer)

        # --- Recorrido: plan de creación ---
        nuevos_pac, reusados_pac = {}, set()   # dedup dentro del archivo
        prestadores_sin_match = {}
        extra_profes_creados = {}
        n_citas_nuevas = 0
        n_citas_saltadas = 0
        n_filas_malas = 0
        por_estado = {}

        def resolver_prof(raw, escribir):
            p = buscar_prof(raw)
            if p is not None:
                return p
            raw = (raw or "").strip()
            if not raw:
                return None
            k = sin_titulo(raw)
            prestadores_sin_match[k] = raw
            if not escribir:
                return None
            if k not in extra_profes_creados:
                extra_profes_creados[k] = Profesional.objects.create(
                    clinica=clinica, nombre=raw, sede="", activo=False, orden=99,
                )
            return extra_profes_creados[k]

        escribir = not opt["dry_run"]

        @transaction.atomic
        def procesar():
            nonlocal n_citas_nuevas, n_citas_saltadas, n_filas_malas
            cache_doc = dict(pac_por_doc)
            cache_tel = dict(pac_por_tel)
            for fila in filas:
                inicio = parse_dt(cell(fila, "fecha"))
                nombre = (str(cell(fila, "nombre") or "").strip() + " " + str(cell(fila, "apellido") or "").strip()).strip()
                if inicio is None or len(nombre) < 3:
                    n_filas_malas += 1
                    continue
                doc = limpiar_doc(cell(fila, "doc"))
                tel = str(cell(fila, "telefono") or "").strip()
                tel9 = solo_dig(tel)[-9:]
                email = str(cell(fila, "email") or "").strip()
                sede = sede_de(cell(fila, "local"))
                servicio = str(cell(fila, "servicio") or "").strip()
                categoria = categoria_de(servicio)
                estado = ESTADO_MAP.get(norm(cell(fila, "estado")), Cita.Estado.AGENDADA)
                por_estado[estado] = por_estado.get(estado, 0) + 1
                nses_raw = solo_dig(cell(fila, "nsesion"))
                n_sesion = int(nses_raw) if nses_raw else None
                comentario = str(cell(fila, "comentario") or "").strip()
                agendado_web = norm(cell(fila, "origen")) == "online"

                prof = resolver_prof(cell(fila, "prestador"), escribir)

                # --- Paciente: buscar existente (DNI, luego teléfono) o crear ---
                pac = None
                if doc and doc in cache_doc:
                    pac = cache_doc[doc]
                elif len(tel9) >= 9 and tel9 in cache_tel:
                    pac = cache_tel[tel9]
                if pac is not None:
                    reusados_pac.add(pac.id if getattr(pac, "id", None) else nombre)
                    if escribir:
                        campos = []
                        if not pac.email and email:
                            pac.email = email[:254]; campos.append("email")
                        if not pac.telefono and tel:
                            pac.telefono = tel[:40]; campos.append("telefono")
                        if not pac.profesional_id and prof is not None:
                            pac.profesional = prof; campos.append("profesional")
                        if not pac.numero_documento and doc:
                            pac.numero_documento = doc
                            pac.tipo_documento = "ruc" if len(doc) == 11 else "dni"
                            campos += ["numero_documento", "tipo_documento"]
                        if campos:
                            pac.save(update_fields=campos)
                else:
                    clave = doc or ("tel:" + tel9) or ("nom:" + norm(nombre))
                    nuevos_pac[clave] = nombre
                    if escribir:
                        pac = Paciente.objects.create(
                            clinica=clinica, nombre=nombre[:200], telefono=tel[:40],
                            email=email[:254], sede=sede, numero_documento=doc,
                            tipo_documento=("ruc" if len(doc) == 11 else "dni"),
                            profesional=prof,
                        )
                        if doc:
                            cache_doc[doc] = pac
                        if len(tel9) >= 9:
                            cache_tel[tel9] = pac

                # --- Cita (idempotente por paciente+inicio) ---
                pac_id = getattr(pac, "id", None) if pac is not None else None
                if pac_id is not None and (pac_id, inicio) in citas_existentes:
                    n_citas_saltadas += 1
                    continue
                n_citas_nuevas += 1
                if escribir and pac is not None:
                    Cita.objects.create(
                        clinica=clinica, paciente=pac,
                        medico=(prof.usuario if prof and prof.usuario_id else None),
                        inicio=inicio, especialidad=servicio[:120], categoria=categoria,
                        estado=estado, sede=sede, modalidad=Cita.Modalidad.PRESENCIAL,
                        n_sesion=n_sesion, agendado_web=agendado_web,
                        notas=("Importado de AgendaPro." + (f" {comentario}" if comentario else ""))[:2000],
                    )
                    citas_existentes.add((pac.id, inicio))

            if opt["dry_run"]:
                transaction.set_rollback(True)

        procesar()

        # --- Reporte ---
        self.stdout.write(self.style.HTTP_INFO(
            f"\nPacientes: {len(nuevos_pac)} nuevos · {len(reusados_pac)} reutilizados (ya existían).\n"
            f"Citas: {n_citas_nuevas} a crear · {n_citas_saltadas} saltadas (ya estaban) · "
            f"{n_filas_malas} filas descartadas (sin fecha/nombre)."
        ))
        self.stdout.write("Citas por estado: " + ", ".join(
            f"{Cita.Estado(k).label}={v}" for k, v in sorted(por_estado.items())))
        if prestadores_sin_match:
            self.stdout.write(self.style.WARNING(
                f"Prestadores sin match en el directorio ({len(prestadores_sin_match)}): "
                f"{sorted(prestadores_sin_match.values())}"))
            if escribir:
                self.stdout.write(f"  -> se crearon {len(extra_profes_creados)} psicólogos INACTIVOS para no perder el vínculo.")
        if opt["dry_run"]:
            self.stdout.write(self.style.SUCCESS("\nDRY-RUN: no se escribió nada (rollback)."))
        else:
            self.stdout.write(self.style.SUCCESS("\nImportación completada."))
