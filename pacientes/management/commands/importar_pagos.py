"""Importa el reporte de VENTAS de AgendaPro (hoja 'Pagos') como Cobros.

Cada fila de 'Pagos' es un pago recibido -> se crea un Cobro (estado Pagado)
enlazado al paciente (match por DNI o por los últimos 9 dígitos del teléfono).
Es IDEMPOTENTE por el Identificador de AgendaPro (Cobro.ref_externa): se puede
re-ejecutar sin duplicar. Add-only: nunca borra ni modifica cobros existentes.
Solo crea el pago si el paciente YA existe (correr antes `importar_reservas`).

    python manage.py importar_pagos --dry-run     # conteos, no escribe
    python manage.py importar_pagos               # carga (add-only)
    python manage.py importar_pagos --archivo "/ruta/reporte_ventas.xlsx"
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import Clinica
from finanzas.models import Cobro
from pacientes.models import Paciente
from pacientes.management.commands.importar_lima import leer_hoja, norm
from pacientes.management.commands.importar_reservas import solo_dig, limpiar_doc, parse_dt

DEFAULT_PATH = r"C:\Users\mirai\Downloads\reporte_de_ventas_377127_2026-07-14T03_39_07+00_00.xlsx"

COLS = {
    "ident": "Identificador", "fecha": "Fecha de pago", "nombre": "Nombre cliente",
    "doc": "DNI o RUC cliente", "email": "Email cliente", "telefono": "Teléfono cliente",
    "monto": "Monto",
}


def parse_monto(raw):
    try:
        return round(float(raw), 2)
    except (TypeError, ValueError):
        return None


class Command(BaseCommand):
    help = "Importa los pagos del reporte de ventas de AgendaPro como Cobros (idempotente)."

    def add_arguments(self, parser):
        parser.add_argument("--archivo", default=DEFAULT_PATH, help="Ruta del .xlsx")
        parser.add_argument("--dry-run", action="store_true", help="Solo conteos; no escribe.")
        parser.add_argument("--limit", type=int, default=0, help="Procesar solo las primeras N filas.")

    def handle(self, *args, **opt):
        clinica = Clinica.objects.filter(slug="itaca").first() or Clinica.objects.first()
        if clinica is None:
            self.stderr.write("No hay clínica. Corre primero: python manage.py bootstrap_itaca")
            return
        try:
            encabezados, filas = leer_hoja(opt["archivo"], "Pagos")
        except FileNotFoundError:
            self.stderr.write(f"No se encontró el archivo: {opt['archivo']}")
            return
        if opt["limit"]:
            filas = filas[: opt["limit"]]

        Hn = [norm(h) for h in encabezados]
        idx = {k: (Hn.index(norm(n)) if norm(n) in Hn else None) for k, n in COLS.items()}
        faltan = [k for k in ("ident", "fecha", "monto") if idx[k] is None]
        if faltan:
            self.stderr.write(f"Faltan columnas clave: {faltan}\nEncabezados: {encabezados}")
            return
        self.stdout.write(f"Leídas {len(filas)} filas de 'Pagos' ({len(encabezados)} columnas).")

        def cell(fila, k):
            i = idx[k]
            return fila[i] if (i is not None and i < len(fila)) else ""

        # Índices de pacientes existentes y de pagos ya importados (idempotencia).
        pac_por_doc, pac_por_tel = {}, {}
        for p in Paciente.objects.filter(clinica=clinica).only("id", "numero_documento", "telefono"):
            if p.numero_documento:
                pac_por_doc.setdefault(p.numero_documento, p)
            t9 = solo_dig(p.telefono)[-9:]
            if len(t9) >= 9:
                pac_por_tel.setdefault(t9, p)
        refs_existentes = set(
            Cobro.objects.filter(clinica=clinica).exclude(ref_externa="")
            .values_list("ref_externa", flat=True)
        )

        cobros_bulk = []
        n_ok = n_ref_dup = n_sin_paciente = n_monto_cero = n_sin_id = 0
        total = 0.0
        vistos = set()
        escribir = not opt["dry_run"]

        for fila in filas:
            ident = str(cell(fila, "ident") or "").strip()
            if not ident:
                n_sin_id += 1
                continue
            if ident in refs_existentes or ident in vistos:
                n_ref_dup += 1
                continue
            vistos.add(ident)
            monto = parse_monto(cell(fila, "monto"))
            if monto is None or monto <= 0:
                n_monto_cero += 1
                continue
            doc = limpiar_doc(cell(fila, "doc"))
            tel9 = solo_dig(cell(fila, "telefono"))[-9:]
            pac = None
            if doc and doc in pac_por_doc:
                pac = pac_por_doc[doc]
            elif len(tel9) >= 9 and tel9 in pac_por_tel:
                pac = pac_por_tel[tel9]
            if pac is None:
                n_sin_paciente += 1
                continue
            fecha = parse_dt(cell(fila, "fecha")) or timezone.now()
            n_ok += 1
            total += monto
            if escribir:
                cobros_bulk.append(Cobro(
                    clinica=clinica, paciente=pac, concepto="Pago (importado de AgendaPro)",
                    monto=monto, estado=Cobro.Estado.PAGADO, fecha=fecha, ref_externa=ident,
                ))

        if escribir and cobros_bulk:
            with transaction.atomic():
                Cobro.objects.bulk_create(cobros_bulk, batch_size=500)

        self.stdout.write(self.style.HTTP_INFO(
            f"\nCobros a crear: {n_ok} · total S/ {total:,.2f}\n"
            f"Saltados: {n_ref_dup} ya importados · {n_sin_paciente} sin paciente en el sistema · "
            f"{n_monto_cero} monto 0 · {n_sin_id} sin identificador."
        ))
        if opt["dry_run"]:
            self.stdout.write(self.style.SUCCESS("\nDRY-RUN: no se escribió nada."))
        else:
            self.stdout.write(self.style.SUCCESS("\nImportación de pagos completada."))
