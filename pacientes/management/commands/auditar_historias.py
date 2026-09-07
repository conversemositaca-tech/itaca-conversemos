"""Audita el registro clinico de la primera sesion, SEPARANDO la era AgendaPro
de la era Itaca.

Por que la separacion es obligatoria: el 14-jul-2026 se importaron ~7.500 citas
historicas de AgendaPro. Esas citas entran como "asistio" pero nunca trajeron
ficha clinica, asi que cuentan como "sin historia" por construccion. Medir sin
separarlas da 99% y no dice nada de como se trabaja hoy; separando da 5% sobre
los pacientes que si empezaron con Itaca.

Ademas mide POR QUE CAMINO se cerro cada sesion, que es lo que explica el
numero: marcar "Asistio" desde el desplegable de la agenda no crea ninguna
ficha; pasar por el boton "Atender" si.

SOLO LECTURA. No escribe ni modifica nada.

    python manage.py auditar_historias
    python manage.py auditar_historias --sede piura
    python manage.py auditar_historias --dias-import 2026-07-13 2026-07-14

Antes de fiarse de --dias-import, correr `auditar_calidad_citas`: imprime los
dias con mas citas creadas de golpe, que es la huella de una migracion.
"""
from collections import defaultdict
from datetime import date, datetime

from django.core.management.base import BaseCommand
from django.db.models import Q

from core.models import Clinica
from pacientes.models import Atencion, Cita, Paciente

# Dias de carga masiva confirmados en produccion (auditar_calidad_citas, 6-sep-2026):
# 2026-07-14 con 7.689 citas y 2026-07-13 con 101, ambas con sesiones repartidas
# en meses, que es la firma de un import y no de actividad diaria.
DIAS_IMPORT_DEFECTO = ["2026-07-13", "2026-07-14"]
MARCADOR_NOTAS = "Importado de AgendaPro."
CAMPOS_FICHA = ["brujula_motivo", "brujula_hipotesis", "brujula_objetivos",
                "antecedentes", "resumen_clinico", "objetivo_principal"]


class Command(BaseCommand):
    help = "Registro clinico de la primera sesion, separando la era AgendaPro de la era Itaca."

    def add_arguments(self, parser):
        parser.add_argument("--sede", default="", choices=["", "piura", "lima"])
        parser.add_argument("--dias-import", nargs="*", default=DIAS_IMPORT_DEFECTO,
                            help="Fechas YYYY-MM-DD de carga masiva. Confirmar con auditar_calidad_citas.")

    def handle(self, *args, **opt):
        clinica = Clinica.objects.filter(slug="itaca").first() or Clinica.objects.first()
        if clinica is None:
            self.stderr.write("No hay clinica.")
            return

        w = self.stdout.write
        dias = []
        for s in opt["dias_import"]:
            try:
                dias.append(datetime.strptime(s, "%Y-%m-%d").date())
            except ValueError:
                self.stderr.write("Fecha invalida (usar YYYY-MM-DD): %s" % s)
                return

        es_import = Q(notas__startswith=MARCADOR_NOTAS) | Q(creado_en__date__in=dias)
        realizada = Q(estado__in=[Cita.Estado.ASISTIO, Cita.Estado.ATENDIDA])

        citas = Cita.objects.filter(clinica=clinica).filter(realizada)
        if opt["sede"]:
            citas = citas.filter(sede=opt["sede"])

        # Por paciente: sesiones reales (era Itaca) e historicas (importadas)
        reales = defaultdict(list)
        historicas = defaultdict(int)
        for cid, pid, inicio, estado in citas.exclude(es_import).values_list(
                "id", "paciente_id", "inicio", "estado"):
            reales[pid].append((inicio, cid, estado))
        for pid in citas.filter(es_import).values_list("paciente_id", flat=True):
            historicas[pid] += 1

        no_prov = set(Paciente.objects.filter(clinica=clinica, provisional=False)
                      .values_list("id", flat=True))
        cohorte_a = [p for p in reales if p in no_prov and historicas.get(p, 0) == 0]
        cohorte_b = [p for p in reales if p in no_prov and historicas.get(p, 0) > 0]
        cohorte_c = [p for p in historicas if p in no_prov and p not in reales]

        w("")
        w("=" * 68)
        w("HISTORIA CLINICA POR ERA  |  %s" % clinica.nombre)
        w("=" * 68)
        w("Corte de migracion: %s  (+ notas que empiezan por '%s')"
          % (", ".join(str(d) for d in dias), MARCADOR_NOTAS))
        w("")
        w("A - empezaron con Itaca (ninguna cita importada): %d" % len(cohorte_a))
        w("B - continuadores (venian de AgendaPro y siguen): %d" % len(cohorte_b))
        w("C - solo historico (nunca una sesion en Itaca):   %d" % len(cohorte_c))
        w("    total = %d" % (len(cohorte_a) + len(cohorte_b) + len(cohorte_c)))
        w("")

        con_historia = set(Atencion.objects.filter(clinica=clinica, tipo=Atencion.Tipo.HISTORIA)
                           .values_list("paciente_id", flat=True))
        con_algo = set(Atencion.objects.filter(clinica=clinica)
                       .values_list("paciente_id", flat=True))
        con_ficha_paciente = set()
        for row in Paciente.objects.filter(clinica=clinica).values("id", *CAMPOS_FICHA):
            if any((row[k] or "").strip() for k in CAMPOS_FICHA):
                con_ficha_paciente.add(row["id"])

        def bloque(nombre, ids):
            n = len(ids)
            if not n:
                w("%s: sin pacientes" % nombre)
                return
            h = len([p for p in ids if p in con_historia])
            a = len([p for p in ids if p in con_algo])
            f = len([p for p in ids if p in con_ficha_paciente])
            nada = len([p for p in ids if p not in con_historia and p not in con_algo
                        and p not in con_ficha_paciente])
            w("%s  (n=%d)" % (nombre, n))
            w("   con ficha tipo 'historia clinica' ... %4d  (%.0f%%)" % (h, 100.0 * h / n))
            w("   con CUALQUIER nota clinica .......... %4d  (%.0f%%)" % (a, 100.0 * a / n))
            w("   con Brujula/antecedentes llenos ..... %4d  (%.0f%%)" % (f, 100.0 * f / n))
            w("   sin NADA de lo anterior ............. %4d  (%.0f%%)" % (nada, 100.0 * nada / n))
            w("")

        bloque("A - empezaron con Itaca  <-- el numero que habla de hoy", cohorte_a)
        bloque("B - continuadores", cohorte_b)
        bloque("C - solo historico  (su ficha vive en AgendaPro o en papel)", cohorte_c)

        # --- Por que camino se cerro cada sesion de la era Itaca ---
        reales_qs = citas.exclude(es_import)
        total_reales = reales_qs.count()
        if total_reales:
            con_ficha_cita = set(Atencion.objects.filter(clinica=clinica, cita__isnull=False)
                                 .values_list("cita_id", flat=True))
            por_estado = defaultdict(lambda: {"n": 0, "ficha": 0})
            for cid, estado in reales_qs.values_list("id", "estado"):
                d = por_estado[estado]
                d["n"] += 1
                if cid in con_ficha_cita:
                    d["ficha"] += 1
            w("CAMINO DE REGISTRO (sesiones de la era Itaca: %d)" % total_reales)
            for est in sorted(por_estado, key=lambda x: -por_estado[x]["n"]):
                d = por_estado[est]
                comose = ("marcada desde el desplegable de la agenda"
                          if est == Cita.Estado.ASISTIO else "paso por el boton Atender")
                w("  %-9s (%s)" % (est, comose))
                w("     sesiones .............. %4d  (%.0f%%)" % (d["n"], 100.0 * d["n"] / total_reales))
                w("     de esas, CON ficha .... %4d  (%.0f%%)" % (d["ficha"], 100.0 * d["ficha"] / d["n"]))
            w("")

            tipos = defaultdict(int)
            for tipo in Atencion.objects.filter(
                    clinica=clinica, cita_id__in=list(reales_qs.values_list("id", flat=True))
            ).values_list("tipo", flat=True):
                tipos[tipo] += 1
            if tipos:
                tot = sum(tipos.values())
                w("CUANDO SI SE ABRE LA FICHA, QUE TIPO SE ELIGE:")
                for t in sorted(tipos, key=lambda x: -tipos[x]):
                    w("   %-22s %4d  (%.0f%%)" % (t, tipos[t], 100.0 * tipos[t] / tot))
                w("")

        # --- Serie mensual de la cohorte A ---
        if cohorte_a:
            w("COHORTE A - por mes de su primera sesion en Itaca")
            por_mes = defaultdict(lambda: {"n": 0, "h": 0})
            for p in cohorte_a:
                m = sorted(reales[p])[0][0].strftime("%Y-%m")
                por_mes[m]["n"] += 1
                if p in con_historia:
                    por_mes[m]["h"] += 1
            for m in sorted(por_mes):
                d = por_mes[m]
                w("   %s  n=%-4d con historia=%-3d (%.0f%%)" % (m, d["n"], d["h"], 100.0 * d["h"] / d["n"]))
            w("")

        w("OJO: si el corte de migracion esta mal, todo lo de arriba esta mal.")
        w("Correr auditar_calidad_citas y confirmar los dias de carga masiva.")
