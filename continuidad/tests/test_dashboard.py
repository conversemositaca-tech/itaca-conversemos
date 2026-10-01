"""Dirección Clínica con el estado formal: confirmado e inferido separados."""
from datetime import timedelta

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from continuidad.models import TipoEvento as T
from continuidad.servicios import transicionar_proceso

from .base import REGISTRO_DESDE_SIEMPRE, Base

URL = "/api/direccion-clinica/"


@REGISTRO_DESDE_SIEMPRE
class DashboardFormalTests(Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.analista)

    def get(self, **params):
        r = self.client.get(URL, params)
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def registrar(self, p, tipo, **kw):
        return transicionar_proceso(self.proceso(p), tipo, self.coord, **kw)

    def test_pausa_formal_no_es_abandono_inferido(self):
        p = self.paciente()
        self.sesiones(p, [120, 113])
        self.registrar(p, T.PAUSA_INICIADA, motivo=self.motivo("VIAJE"),
                       fecha_efectiva=timezone.localdate() - timedelta(days=100))
        r = self.get()["resumen"]
        self.assertEqual((r["abandono_inferido"], r["pausas"]), (0, 1))

    def test_confirmado_e_inferido_por_separado(self):
        conf = self.paciente("Confirmado")
        self.sesiones(conf, [120])
        self.registrar(conf, T.ABANDONO_CONFIRMADO, motivo=self.motivo("ECONOMIA"))
        inf = self.paciente("Inferido")  # formal ACTIVO, pero no volvió
        self.sesiones(inf, [120])
        self.proceso(inf)
        d = self.get()
        r = d["resumen"]
        self.assertEqual((r["abandono_inferido"], r["abandono_confirmado"]), (1, 1))
        self.assertEqual(r["kpis"]["abandono_inferido"]["numerador"], 1)
        self.assertEqual(r["kpis"]["abandono_confirmado"]["numerador"], 1)
        s1 = d["embudo"][0]
        self.assertEqual((s1["cayeron"], s1["cayeron_confirmado"]), (1, 1))
        # El combinado existe, pero con otro nombre: nunca "abandono".
        sin = d["formal"]["kpis"]["sin_continuidad_registrada"]
        self.assertEqual((sin["numerador"], sin["denominador"]), (2, 2))
        kf = d["formal"]["kpis"]
        self.assertEqual((kf["abandono_confirmado"]["numerador"], kf["activo"]["numerador"]), (1, 1))

    def test_alta_formal_y_legacy(self):
        a = self.paciente("Alta formal")
        self.sesiones(a, [120])
        self.registrar(a, T.ALTA)
        self.get()
        b = self.paciente("Alta legacy", frecuencia="alta")  # sin proceso persistido
        self.sesiones(b, [120])
        d = self.get()
        self.assertEqual(d["resumen"]["altas_registradas"], 2)
        self.assertEqual(d["formal"]["calidad"]["procesos_estado_legacy"], 1)
        self.assertEqual(d["formal"]["kpis"]["con_estado_formal"]["numerador"], 1)

    def test_reactivacion_desde_pausa_y_desde_abandono(self):
        a, b = self.paciente("A"), self.paciente("B")
        self.sesiones(a, [60])
        self.sesiones(b, [60])
        self.registrar(a, T.PAUSA_INICIADA, motivo=self.motivo("VIAJE"))
        self.registrar(a, T.REACTIVACION)
        self.registrar(b, T.ABANDONO_CONFIRMADO, motivo=self.motivo("SIN_INFORMACION"))
        self.registrar(b, T.REACTIVACION)
        f = self.get()["formal"]
        self.assertEqual(f["reactivaciones_desde"], {"pausa": 1, "abandono": 1, "alta_o_cierre": 0})
        self.assertEqual((f["kpis"]["reactivacion"]["numerador"], f["kpis"]["reactivacion"]["denominador"]), (2, 2))

    def test_continuidad_del_centro_tras_cambio(self):
        p = self.paciente(profesional=self.ana)
        self.sesiones(p, [60, 53], medico=self.u_ana)
        self.registrar(p, T.CAMBIO_PROFESIONAL, profesional_nuevo=self.beto,
                       fecha_efectiva=timezone.localdate() - timedelta(days=40))
        self.cita(p, 30)  # vuelve al centro después del cambio
        f = self.get()["formal"]
        k = f["continuidad_centro_post_cambio"]["kpi"]
        self.assertEqual((k["numerador"], k["denominador"]), (1, 1))
        self.assertEqual(f["kpis"]["cambio_profesional"]["numerador"], 1)
        self.assertEqual(self.get()["resumen"]["abandono_confirmado"], 0)

    def test_motivos_con_sin_informacion_visible(self):
        for i, codigo in enumerate(("ECONOMIA", "ECONOMIA", "HORARIO", "SIN_INFORMACION")):
            p = self.paciente(f"M{i}")
            self.sesiones(p, [90])
            self.registrar(p, T.ABANDONO_CONFIRMADO, motivo=self.motivo(codigo))
        m = self.get()["formal"]["motivos"]
        self.assertEqual((m["total"], m["conocidos"], m["desconocidos"]), (4, 3, 1))
        eco = next(x for x in m["por_motivo"] if x["codigo"] == "ECONOMIA")
        self.assertEqual((eco["n"], eco["pct_sobre_conocidos"]), (2, 66.7))
        self.assertEqual(m["kpi_conocidos"]["pct"], 75.0)

    def test_filtros_aplican_al_bloque_formal(self):
        a = self.paciente("Lima", sede="lima")
        self.sesiones(a, [90])
        self.registrar(a, T.ALTA)
        b = self.paciente("Piura", sede="piura")
        self.sesiones(b, [90])
        self.registrar(b, T.PAUSA_INICIADA, motivo=self.motivo("VIAJE"))
        f = self.get(sede="lima")["formal"]["kpis"]
        self.assertEqual((f["alta"]["numerador"], f["pausa"]["numerador"], f["alta"]["n"]), (1, 0, 1))

    def test_activos_sin_proxima_y_frecuencia(self):
        p = self.paciente()
        self.sesiones(p, [20])
        transicionar_proceso(self.proceso(p), T.CAMBIO_FRECUENCIA, self.coord, frecuencia="semanal")
        f = self.get()["formal"]
        self.assertEqual(f["kpis"]["activos_sin_proxima_cita"]["numerador"], 1)
        k = f["kpis"]["frecuencia_cumplida"]
        self.assertEqual((k["numerador"], k["denominador"]), (0, 1))  # 20 días > 7
        razones = {r["clave"]: r["n"] for r in f["revision"]["por_razon"]}
        self.assertEqual((razones["activo_sin_proxima"], razones["excede_frecuencia"]), (1, 1))

    def test_consultas_no_crecen_con_eventos(self):
        def contar():
            with CaptureQueriesContext(connection) as ctx:
                self.get(periodo="todo")
            return len(ctx)
        p = self.paciente("Uno")
        self.sesiones(p, [60])
        self.registrar(p, T.PAUSA_INICIADA, motivo=self.motivo("VIAJE"))
        base = contar()
        for i in range(8):
            q = self.paciente(f"P{i}")
            self.sesiones(q, [80, 70])
            self.registrar(q, T.ABANDONO_CONFIRMADO, motivo=self.motivo("PAGO"))
            self.registrar(q, T.REACTIVACION)
        self.assertEqual(contar(), base)
