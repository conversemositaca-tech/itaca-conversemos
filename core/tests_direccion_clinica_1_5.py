"""Dirección Clínica · fase 1.5: KPIs con numerador/denominador/N, cohortes
evaluables, medianas, modalidad, rango personalizado, filtros combinados,
calidad del dato y número de consultas.

    python manage.py test core.tests_direccion_clinica_1_5
"""
from datetime import timedelta

from django.db import connection
from django.test import SimpleTestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from core import direccion_clinica as dc
from core.tests_direccion_clinica import URL, _Base
from pacientes.models import Cita
from usuarios.models import Usuario


class KpiYEstadisticaTests(SimpleTestCase):
    def test_kpi_trae_numerador_denominador_n_y_no_evaluables(self):
        k = dc.kpi(43, 56, n=58, no_evaluables=2)
        self.assertEqual(k, {"numerador": 43, "denominador": 56, "pct": 76.8, "n": 58,
                             "muestra_pequena": False, "no_evaluables": 2})

    def test_denominador_cero_no_divide(self):
        k = dc.kpi(0, 0)
        self.assertIsNone(k["pct"])
        self.assertEqual((k["numerador"], k["denominador"], k["n"]), (0, 0, 0))
        self.assertFalse(k["muestra_pequena"])  # sin dato no hay muestra que rotular

    def test_muestra_pequena_es_regla_tecnica(self):
        self.assertTrue(dc.kpi(3, dc.MUESTRA_PEQUENA - 1)["muestra_pequena"])
        self.assertFalse(dc.kpi(3, dc.MUESTRA_PEQUENA)["muestra_pequena"])

    def test_mediana_impar_par_y_vacia(self):
        self.assertEqual(dc.estadistica([1, 3, 9]), {"media": 4.3, "mediana": 3, "n": 3})
        self.assertEqual(dc.estadistica([1, 2, 3, 10])["mediana"], 2.5)
        self.assertEqual(dc.estadistica([]), {"media": None, "mediana": None, "n": 0})

    def test_tramos_de_la_distribucion(self):
        d = dc._distribucion([1, 2, 3, 4, 6, 7, 12, 13, 40], dc.TRAMOS_SESIONES)
        self.assertEqual([x["n"] for x in d], [1, 2, 2, 2, 2])

    def test_modalidad_del_proceso(self):
        self.assertEqual(dc._modalidad_proceso([{"modalidad": "virtual"}] * 2), "virtual")
        self.assertEqual(dc._modalidad_proceso([{"modalidad": "virtual"}, {"modalidad": "presencial"}]), "mixta")
        self.assertEqual(dc._modalidad_proceso([{"modalidad": ""}]), dc.SIN_MODALIDAD)


class _Base15(_Base):
    def cita(self, p, hace, modalidad=None, notas="", **kw):
        c = super().cita(p, hace, **kw)
        cambios = {}
        if modalidad is not None:
            cambios["modalidad"] = modalidad
        if notas:
            cambios["notas"] = notas
        if cambios:
            Cita.objects.filter(pk=c.pk).update(**cambios)
        return c


class CohorteEvaluableTests(_Base15):
    def test_aun_en_curso_no_es_fuga_y_terminado_si_es_evaluable(self):
        reciente = self.paciente("Reciente")
        self.sesiones(reciente, [5])                          # activo, sin S2 todavía
        alta = self.paciente("Alta en S1")
        self.cita(alta, 100, decision="DP-10")               # terminó en S1 con alta
        se_fue = self.paciente("Se fue")
        self.sesiones(se_fue, [120])                          # abandono inferido en S1
        siguio = self.paciente("Siguió")
        self.sesiones(siguio, [90, 83])                       # pasó a S2 (y luego se fue)
        k = self.get()["resumen"]["kpis"]["s1_s2"]
        self.assertEqual((k["numerador"], k["denominador"], k["n"], k["no_evaluables"]), (1, 3, 4, 1))
        self.assertEqual(k["pct"], 33.3)

    def test_abandono_inferido_sobre_terminados_no_sobre_iniciados(self):
        activo = self.paciente("Activo")
        self.sesiones(activo, [20, 13])
        self.cita(activo, -3, estado=Cita.Estado.AGENDADA)
        se_fue = self.paciente("Se fue")
        self.sesiones(se_fue, [120])
        r = self.get()["resumen"]
        k = r["kpis"]["abandono_inferido"]
        self.assertEqual((k["numerador"], k["denominador"], k["n"], k["no_evaluables"]), (1, 1, 2, 1))
        self.assertEqual(r["tasa_abandono_inferido"], 100.0)  # antes 50 %: el activo no tiene desenlace

    def test_s5_a_s6_en_curso_no_entra_al_denominador(self):
        p = self.paciente()
        self.sesiones(p, [36, 29, 22, 15, 8])
        self.cita(p, -2, estado=Cita.Estado.AGENDADA)
        s5 = {e["etapa"]: e for e in self.get()["embudo"]}["S5"]
        self.assertEqual((s5["llegaron"], s5["en_curso"], s5["evaluables"]), (1, 1, 0))
        self.assertIsNone(s5["kpi"]["pct"])
        self.assertEqual(s5["kpi"]["no_evaluables"], 1)

    def test_cada_paso_del_embudo_trae_kpi(self):
        p = self.paciente()
        self.sesiones(p, [200, 193, 186])  # llegó a S3 y se fue
        for e in self.get()["embudo"][:-1]:
            self.assertEqual(set(e["kpi"]), {"numerador", "denominador", "pct", "n", "muestra_pequena", "no_evaluables"})
        emb = {e["etapa"]: e for e in self.get()["embudo"]}
        self.assertEqual(emb["S2"]["kpi"]["numerador"], 1)   # S2→S3: pasó
        self.assertEqual(emb["S3"]["kpi_caida"]["numerador"], 1)  # S3→S4: abandono inferido


class MedianasTests(_Base15):
    def test_medianas_y_distribucion_de_sesiones(self):
        for nombre, dias in [("Uno", [200]), ("Dos", [200, 193]), ("Seis", [200, 193, 186, 179, 172, 165])]:
            self.sesiones(self.paciente(nombre), dias)
        d = self.get()
        est = d["resumen"]["estadisticas"]
        self.assertEqual(est["sesiones_por_proceso"], {"media": 3, "mediana": 2, "n": 3})
        self.assertEqual(est["sesiones_por_proceso_terminados"]["n"], 3)
        self.assertEqual(est["dias_entre_sesiones"]["n"], 6)     # 1 + 5 intervalos
        self.assertEqual(est["dias_entre_sesiones"]["mediana"], 7)
        self.assertEqual(est["dias_s1_a_abandono"]["mediana"], 7)  # 0, 7, 35
        dist = {x["label"]: x for x in d["distribuciones"]["sesiones_por_proceso"]}
        self.assertEqual((dist["1"]["terminados"], dist["2–3"]["terminados"], dist["4–6"]["terminados"]), (1, 1, 1))
        self.assertEqual({x["label"]: x["n"] for x in d["distribuciones"]["dias_entre_sesiones"]}["0–7 días"], 6)

    def test_sin_datos_no_hay_mediana(self):
        est = self.get()["resumen"]["estadisticas"]
        self.assertEqual(est["sesiones_por_proceso"], {"media": None, "mediana": None, "n": 0})


class FiltrosTests(_Base15):
    def setUp(self):
        super().setUp()
        # Piura · adultos · Ana · virtual · hace ~2 meses
        self.a = self.paciente("A", sede="piura")
        self.sesiones(self.a, [60, 53], medico=self.ps_ana, categoria="adultos", modalidad="virtual")
        # Piura · adultos · Ana · presencial
        self.b = self.paciente("B", sede="piura")
        self.sesiones(self.b, [60, 53], medico=self.ps_ana, categoria="adultos")
        # Piura · adultos · Ana · virtual · hace ~10 meses (fuera de 6 meses)
        self.c = self.paciente("C", sede="piura")
        self.sesiones(self.c, [300, 293], medico=self.ps_ana, categoria="adultos", modalidad="virtual")
        # Lima · parejas · sin psicólogo · mixta
        self.d = self.paciente("D", sede="lima")
        self.cita(self.d, 40, categoria="parejas", modalidad="virtual")
        self.cita(self.d, 33, categoria="parejas")

    def n(self, **params):
        return self.get(**params)["resumen"]["procesos_iniciados"]

    def test_modalidad(self):
        self.assertEqual(self.n(modalidad="virtual"), 2)
        self.assertEqual(self.n(modalidad="presencial"), 1)
        self.assertEqual(self.n(modalidad="mixta"), 1)
        self.assertEqual(self.n(modalidad="inventada"), 4)  # valor desconocido: no acota
        filas = {f["clave"]: f["procesos"] for f in self.get()["por_modalidad"]}
        self.assertEqual(filas, {"virtual": 2, "presencial": 1, "mixta": 1})

    def test_combinados_no_rompen_denominadores(self):
        ana = f"p{self.ficha_ana.id}"
        d = self.get(sede="piura", categoria="adultos", psicologo=ana, modalidad="virtual", periodo="180d")
        self.assertEqual(d["resumen"]["procesos_iniciados"], 1)  # solo A
        k = d["resumen"]["kpis"]["s1_s2"]
        self.assertEqual((k["numerador"], k["denominador"], k["n"]), (1, 1, 1))
        self.assertEqual(d["filtros"]["modalidad"], "virtual")
        self.assertEqual([f["clave"] for f in d["por_sede"]], ["piura"])
        self.assertEqual(d["calidad"]["sesiones_periodo"], 2)  # la calidad sigue al recorte

    def test_rango_personalizado(self):
        hoy = timezone.localdate()
        d = self.get(desde=(hoy - timedelta(days=310)).isoformat(), hasta=(hoy - timedelta(days=200)).isoformat())
        self.assertEqual(d["periodo"]["clave"], "rango")
        self.assertEqual(d["resumen"]["procesos_iniciados"], 1)  # solo C

    def test_rango_invalido_responde_400(self):
        for params in ({"desde": "2026-13-01"}, {"hasta": "ayer"},
                       {"desde": "2026-09-30", "hasta": "2026-09-01"}):
            r = self.client.get(URL, params)
            self.assertEqual(r.status_code, 400, params)
            self.assertIn("detail", r.json())

    def test_cero_resultados_es_estado_vacio_sin_division(self):
        d = self.get(sede="lima", modalidad="presencial")
        self.assertTrue(d["vacio"])
        self.assertEqual(d["resumen"]["procesos_iniciados"], 0)
        for k in d["resumen"]["kpis"].values():
            self.assertIsNone(k["pct"])
            self.assertEqual(k["denominador"], 0)
        self.assertEqual(d["por_psicologo"], [])
        self.assertIsNone(d["calidad"]["kpis"]["sesiones_con_psicologo"]["pct"])


class TablasTests(_Base15):
    def test_sede_en_orden_fijo_y_categoria_sin_ocultar(self):
        for i in range(3):
            self.sesiones(self.paciente(f"Piura {i}", sede="piura"), [100], categoria="adultos")
        self.sesiones(self.paciente("Lima", sede="lima"), [100])
        d = self.get()
        # Piura tiene más procesos y aun así Lima va primero: no hay "mejor sede".
        self.assertEqual([f["clave"] for f in d["por_sede"]], ["lima", "piura"])
        self.assertEqual([f["clave"] for f in d["por_categoria"]], ["adultos", "sin_categoria"])

    def test_fila_de_psicologo_trae_n_kpis_y_mediana(self):
        for i, dias in enumerate([[100], [100, 93, 86]]):
            self.sesiones(self.paciente(f"P{i}"), dias, medico=self.ps_ana)
        fila = self.get()["por_psicologo"][0]
        self.assertEqual(fila["procesos"], 2)
        self.assertEqual(fila["mediana_sesiones"], 2)
        self.assertEqual(fila["altas_o_cierres"], 0)
        self.assertEqual(fila["kpis"]["s1_s2"]["denominador"], 2)
        self.assertEqual(fila["kpis"]["s1_s3"]["numerador"], 1)
        self.assertTrue(fila["kpis"]["s1_s2"]["muestra_pequena"])
        self.assertNotIn("ranking", fila)
        self.assertNotIn("score", fila)


class CalidadTests(_Base15):
    def test_faltantes_con_n(self):
        p = self.paciente("Sin nada")
        self.cita(p, 100, modalidad="")
        q = self.paciente("Completo")
        self.sesiones(q, [100, 93], medico=self.ps_ana, categoria="adultos")
        r = self.paciente("Importado")
        self.cita(r, 100, notas="Importado de AgendaPro. Sesión 1", medico=self.ps_ana)
        cal = self.get()["calidad"]
        self.assertEqual(cal["sesiones_periodo"], 4)
        self.assertEqual(cal["sesiones_sin_psicologo"], 1)
        self.assertEqual(cal["sesiones_sin_modalidad"], 1)
        self.assertEqual(cal["sesiones_importadas_agendapro"], 1)
        self.assertEqual(cal["procesos_sin_categoria"], 2)
        self.assertEqual(cal["procesos_sin_modalidad"], 1)
        k = cal["kpis"]["procesos_con_categoria"]
        self.assertEqual((k["numerador"], k["denominador"]), (1, 3))
        inferidos = cal["kpis"]["terminados_solo_inferidos"]
        self.assertEqual((inferidos["numerador"], inferidos["denominador"]), (3, 3))

    def test_numeracion_inconsistente_se_cuenta(self):
        p = self.paciente()
        for i, d in enumerate([60, 53, 46, 39], start=1):
            self.cita(p, d, n=i)
        self.cita(p, 32, n=2)  # baja sin respaldo: sigue siendo el mismo proceso
        cal = self.get()["calidad"]
        self.assertEqual(cal["procesos_numeracion_inconsistente"], 1)
        self.assertEqual(cal["kpis"]["procesos_numeracion_consistente"]["numerador"], 0)


class PermisosYConsultasTests(_Base15):
    def test_roles_intactos_con_los_filtros_nuevos(self):
        analista = Usuario.objects.create_user(
            email="dc15@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ANALISTA)
        self.client.force_login(analista)
        self.assertEqual(self.client.get(URL, {"modalidad": "virtual"}).status_code, 200)
        coord = Usuario.objects.create_user(
            email="coord15@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ASISTENTE)
        self.client.force_login(coord)
        self.assertEqual(self.client.get(URL, {"modalidad": "virtual"}).status_code, 403)
        self.assertEqual(self.client.get(URL, {"desde": "malo"}).status_code, 403)  # el permiso va primero

    def _consultas(self):
        with CaptureQueriesContext(connection) as ctx:
            self.get(periodo="todo")
        return len(ctx)

    def test_sin_n_mas_uno(self):
        """Las consultas no crecen con los pacientes ni con los psicólogos."""
        self.sesiones(self.paciente("Uno"), [50, 43], medico=self.ps_ana)
        pocas = self._consultas()
        for i in range(12):
            medico = None
            if i % 3:
                medico = Usuario.objects.create_user(
                    email=f"ps{i}@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.MEDICO)
            self.sesiones(self.paciente(f"P{i}", sede="lima" if i % 2 else "piura"),
                          [80, 73, 66], medico=medico, categoria="adultos")
        self.assertEqual(self._consultas(), pocas)
