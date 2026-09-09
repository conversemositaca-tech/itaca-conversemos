"""Audita el hito S6: la evaluacion de continuidad, ¿ocurre, se registra y se concreta?

SOLO LECTURA. No escribe ni modifica nada.

Cruza las tres fuentes que registran el mismo momento:
  - Cita.decision (codigo DP-xx)      -> lo registra coordinacion
  - Atencion.tipo = continuidad       -> lo registra el psicologo
  - Mensaje.tipo = seguimiento        -> el contacto posterior

    python manage.py auditar_s6 --desde 2026-01-01
    python manage.py auditar_s6 --desde 2026-01-01 --sede piura
    python manage.py auditar_s6 --desde 2026-01-01 --csv s6.csv
"""
import csv
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand

from core.models import Clinica
from mensajes.models import Mensaje
from pacientes.models import Atencion, Cita

VENTANA_FICHA_DIAS = 7  # margen para aceptar la ficha como "de esta sesion"


class Command(BaseCommand):
    help = "Audita el hito S6 cruzando decision de coordinacion, ficha del psicologo y seguimiento."

    def add_arguments(self, parser):
        parser.add_argument("--desde", required=True, help="Fecha inicial YYYY-MM-DD.")
        parser.add_argument("--hasta", default="", help="Fecha final YYYY-MM-DD (opcional).")
        parser.add_argument("--sede", default="", choices=["", "piura", "lima"])
        parser.add_argument("--sesion", type=int, default=6, help="N de sesion a auditar (default 6).")
        parser.add_argument("--csv", default="", help="Ruta para volcar el detalle paciente por paciente.")

    def handle(self, *args, **opt):
        clinica = Clinica.objects.filter(slug="itaca").first() or Clinica.objects.first()
        if clinica is None:
            self.stderr.write("No hay clinica.")
            return

        desde = datetime.strptime(opt["desde"], "%Y-%m-%d").date()
        hasta = datetime.strptime(opt["hasta"], "%Y-%m-%d").date() if opt["hasta"] else None
        n = opt["sesion"]

        citas = (
            Cita.objects.filter(clinica=clinica, n_sesion=n, inicio__date__gte=desde)
            .filter(estado__in=[Cita.Estado.ASISTIO, Cita.Estado.ATENDIDA])
            .select_related("paciente", "medico")
            .order_by("inicio")
        )
        if hasta:
            citas = citas.filter(inicio__date__lte=hasta)
        if opt["sede"]:
            citas = citas.filter(sede=opt["sede"])

        filas = []
        for c in citas:
            pac = c.paciente

            ficha = Atencion.objects.filter(
                clinica=clinica,
                paciente=pac,
                tipo__in=[Atencion.Tipo.CONTINUIDAD, Atencion.Tipo.INFORME_CONTINUIDAD],
                fecha__gte=c.inicio - timedelta(days=VENTANA_FICHA_DIAS),
            ).exists()

            msg = (
                Mensaje.objects.filter(
                    clinica=clinica,
                    paciente=pac,
                    tipo=Mensaje.Tipo.SEGUIMIENTO,
                    creado_en__gte=c.inicio,
                )
                .order_by("creado_en")
                .first()
            )
            dias_msg = (msg.creado_en - c.inicio).days if msg else None

            siguiente = (
                Cita.objects.filter(clinica=clinica, paciente=pac, inicio__gt=c.inicio)
                .order_by("inicio")
                .first()
            )
            dias_sig = (siguiente.inicio - c.inicio).days if siguiente else None

            filas.append(
                {
                    "paciente": pac.nombre,
                    "sede": c.sede or pac.sede,
                    "psicologo": str(c.medico) if c.medico else "",
                    "fecha_s6": c.inicio.date().isoformat(),
                    "dp": c.decision or "",
                    "dp_texto": c.get_decision_display() if c.decision else "",
                    "ficha_continuidad": "si" if ficha else "no",
                    "seguimiento": "si" if msg else "no",
                    "dias_hasta_seguimiento": dias_msg if dias_msg is not None else "",
                    "cita_posterior": "si" if siguiente else "no",
                    "dias_hasta_cita_posterior": dias_sig if dias_sig is not None else "",
                }
            )

        total = len(filas)
        w = self.stdout.write
        if total == 0:
            w("Sin citas de sesion %d en el rango." % n)
            return

        def pct(x):
            return "%.0f%%" % (100.0 * x / total)

        w("")
        w("=" * 62)
        w(
            "AUDITORIA HITO S%d  |  %s  |  desde %s%s"
            % (n, clinica.nombre, desde, (" hasta " + str(hasta)) if hasta else "")
        )
        w("=" * 62)
        w("Citas de S%d atendidas: %d" % (n, total))
        w("")

        # --- Los cuatro cuadrantes ---
        cuad = {"ambos": 0, "solo_ficha": 0, "solo_dp": 0, "ninguno": 0}
        for f in filas:
            tiene_ficha = f["ficha_continuidad"] == "si"
            tiene_dp = bool(f["dp"])
            if tiene_ficha and tiene_dp:
                cuad["ambos"] += 1
            elif tiene_ficha:
                cuad["solo_ficha"] += 1
            elif tiene_dp:
                cuad["solo_dp"] += 1
            else:
                cuad["ninguno"] += 1

        w("REGISTRO DEL HITO (ficha del psicologo x decision de coordinacion)")
        w("  Ficha SI + DP SI ... %4d  %-5s  el proceso funciono" % (cuad["ambos"], pct(cuad["ambos"])))
        w("  Ficha SI + DP NO ... %4d  %-5s  evaluo, no se cerro el circulo" % (cuad["solo_ficha"], pct(cuad["solo_ficha"])))
        w("  Ficha NO + DP SI ... %4d  %-5s  se registro sin evaluacion clinica" % (cuad["solo_dp"], pct(cuad["solo_dp"])))
        w("  Ficha NO + DP NO ... %4d  %-5s  el hito no ocurrio" % (cuad["ninguno"], pct(cuad["ninguno"])))
        w("")

        # --- Distribucion de decisiones ---
        dps = {}
        for f in filas:
            k = f["dp_texto"] or "(sin registrar)"
            dps[k] = dps.get(k, 0) + 1
        w("DECISION REGISTRADA (DP)")
        for k in sorted(dps, key=lambda x: -dps[x]):
            w("  %-46s %4d  %s" % (k[:46], dps[k], pct(dps[k])))
        w("")

        # --- La continuidad, ¿se concreto? ---
        cont = [f for f in filas if f["dp"] == Cita.Decision.DP08]
        if cont:
            con_cita = [f for f in cont if f["cita_posterior"] == "si"]
            w("DE LOS QUE DECIDIERON CONTINUAR (DP-08): %d" % len(cont))
            w("  con cita posterior ..... %d  (%.0f%%)" % (len(con_cita), 100.0 * len(con_cita) / len(cont)))
            w("  sin cita posterior ..... %d   <- fuga con decision tomada" % (len(cont) - len(con_cita)))
            dd = sorted(f["dias_hasta_cita_posterior"] for f in con_cita if f["dias_hasta_cita_posterior"] != "")
            if dd:
                w("  dias hasta la siguiente cita: mediana %d, maximo %d" % (dd[len(dd) // 2], dd[-1]))
            w("")

        # --- Demora del seguimiento ---
        con_msg = [f for f in filas if f["seguimiento"] == "si"]
        w("SEGUIMIENTO POSTERIOR (Mensaje tipo=seguimiento)")
        w("  con seguimiento registrado ... %d  %s" % (len(con_msg), pct(len(con_msg))))
        ds = sorted(f["dias_hasta_seguimiento"] for f in con_msg if f["dias_hasta_seguimiento"] != "")
        if ds:
            w("  dias decision -> seguimiento: mediana %d, maximo %d" % (ds[len(ds) // 2], ds[-1]))
        w("  OJO: solo cuenta lo enviado desde el sistema, no desde un celular personal.")
        w("")

        # --- Por sede y psicologo ---
        w("POR PSICOLOGO (hito no registrado = ficha NO + DP NO)")
        por = {}
        for f in filas:
            k = (f["sede"] or "?") + " | " + (f["psicologo"] or "(sin psicologo)")
            d = por.setdefault(k, {"t": 0, "sin": 0})
            d["t"] += 1
            if f["ficha_continuidad"] == "no" and not f["dp"]:
                d["sin"] += 1
        for k in sorted(por, key=lambda x: -por[x]["t"]):
            d = por[k]
            w("  %-34s n=%-4d sin registro=%-4d %.0f%%" % (k[:34], d["t"], d["sin"], 100.0 * d["sin"] / d["t"]))
        w("")

        # --- Calidad del dato ---
        sin_nsesion = Cita.objects.filter(
            clinica=clinica, inicio__date__gte=desde, n_sesion__isnull=True
        ).count()
        w("CALIDAD DEL DATO")
        w("  Citas sin n_sesion en el rango: %d  (no entran en esta auditoria)" % sin_nsesion)
        w("")

        if opt["csv"]:
            with open(opt["csv"], "w", newline="", encoding="utf-8-sig") as fh:
                wr = csv.DictWriter(fh, fieldnames=list(filas[0].keys()))
                wr.writeheader()
                wr.writerows(filas)
            w("Detalle escrito en %s (%d filas)." % (opt["csv"], len(filas)))
