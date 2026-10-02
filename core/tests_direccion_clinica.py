"""Pruebas de Dirección Clínica (continuidad y abandono inferido) y de las
métricas de Gerencia que pasaron a leer citas asistidas en vez de fichas.

    python manage.py test core.tests_direccion_clinica
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.models import Clinica
from pacientes.models import Atencion, Cita, Paciente
from usuarios.models import Profesional, Usuario

URL = "/api/direccion-clinica/"


class _Base(TestCase):
    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-dc")
        self.admin = Usuario.objects.create_user(
            email="gerencia-dc@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ADMIN)
        self.ps_ana = Usuario.objects.create_user(
            email="ana@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.MEDICO, nombre="Ana")
        self.ficha_ana = Profesional.objects.create(clinica=self.clinica, nombre="Ana Ruiz", usuario=self.ps_ana)
        self.ficha_beto = Profesional.objects.create(clinica=self.clinica, nombre="Beto Paz", sede="lima")
        self.client.force_login(self.admin)

    def paciente(self, nombre="P", sede="piura", **kw):
        return Paciente.objects.create(clinica=self.clinica, nombre=nombre, sede=sede, **kw)

    def cita(self, p, hace, estado=Cita.Estado.ASISTIO, n=None, servicio="Terapia individual",
             decision="", medico=None, categoria=""):
        return Cita.objects.create(
            clinica=self.clinica, paciente=p, inicio=timezone.now() - timedelta(days=hace),
            estado=estado, n_sesion=n, especialidad=servicio, decision=decision,
            medico=medico, categoria=categoria,
        )

    def sesiones(self, p, dias_atras, **kw):
        """Una sesión asistida por cada valor de `dias_atras` (en orden)."""
        for d in dias_atras:
            self.cita(p, d, **kw)

    def get(self, **params):
        r = self.client.get(URL, params)
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()


class PermisosTests(_Base):
    def test_analista_ve_y_coordinacion_no(self):
        analista = Usuario.objects.create_user(
            email="dc@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ANALISTA)
        self.client.force_login(analista)
        self.assertEqual(self.client.get(URL).status_code, 200)
        for rol in (Usuario.Rol.ASISTENTE, Usuario.Rol.MEDICO, Usuario.Rol.COMERCIAL):
            u = Usuario.objects.create_user(email=f"{rol}@test.pe", password="x", clinica=self.clinica, rol=rol)
            self.client.force_login(u)
            self.assertEqual(self.client.get(URL).status_code, 403, rol)

    def test_no_escribe_nada(self):
        p = self.paciente()
        self.sesiones(p, [100, 93])
        antes = (Cita.objects.count(), Paciente.objects.count(), list(Cita.objects.values_list("estado", "decision")))
        self.get(periodo="todo")
        self.assertEqual(antes, (Cita.objects.count(), Paciente.objects.count(),
                                 list(Cita.objects.values_list("estado", "decision"))))


class PosicionYConsultaTests(_Base):
    def test_la_posicion_cuenta_aunque_nadie_numere(self):
        p = self.paciente()
        self.sesiones(p, [40, 33, 26])  # sin n_sesion
        self.cita(p, -3, estado=Cita.Estado.AGENDADA)  # próxima cita: sigue activo
        emb = {e["etapa"]: e for e in self.get()["embudo"]}
        self.assertEqual(emb["S3"]["llegaron"], 1)
        self.assertEqual(emb["S4"]["llegaron"], 0)

    def test_la_consulta_inicial_no_es_la_s1(self):
        p = self.paciente()
        self.cita(p, 50, servicio="Consulta inicial - Adultos")
        self.sesiones(p, [43, 36])
        self.cita(p, -2, estado=Cita.Estado.AGENDADA)
        d = self.get()
        self.assertEqual(d["embudo"][0]["llegaron"], 1)
        self.assertEqual(d["embudo"][2]["llegaron"], 0)  # 2 sesiones, no 3
        self.assertEqual(d["resumen"]["promedio_sesiones"], 2)

    def test_cancelada_e_inasistencia_no_son_sesion(self):
        p = self.paciente()
        self.sesiones(p, [40])
        self.cita(p, 33, estado=Cita.Estado.NO_ASISTIO)
        self.cita(p, 26, estado=Cita.Estado.CANCELADA)
        self.cita(p, -1, estado=Cita.Estado.AGENDADA)
        self.assertEqual(self.get()["resumen"]["promedio_sesiones"], 1)

    def test_dos_procesos_cuentan_por_separado(self):
        p = self.paciente()
        for i, d in enumerate([300, 293, 286], start=1):
            self.cita(p, d, n=i)
        for i, d in enumerate([100, 93], start=1):  # vuelve a S1: segundo proceso
            self.cita(p, d, n=i)
        d = self.get(periodo="todo")
        self.assertEqual(d["resumen"]["procesos_iniciados"], 2)
        self.assertEqual(d["resumen"]["pacientes_nuevos"], 1)
        self.assertEqual(d["resumen"]["reingresos"], 1)


class AbandonoInferidoTests(_Base):
    def test_recientes_no_cuentan_como_caida(self):
        """S1 hace 5 días, sin próxima cita: todavía no tuvo tiempo de volver."""
        reciente = self.paciente("Reciente")
        self.sesiones(reciente, [5])
        viejo = self.paciente("Se fue")
        self.sesiones(viejo, [100])
        s1 = self.get()["embudo"][0]
        self.assertEqual(s1["llegaron"], 2)
        self.assertEqual(s1["evaluables"], 1)
        self.assertEqual(s1["en_curso"], 1)
        self.assertEqual(s1["cayeron"], 1)
        self.assertEqual(s1["pct_caida"], 100.0)

    def test_proxima_cita_mantiene_activo(self):
        p = self.paciente()
        self.sesiones(p, [100])
        self.cita(p, -7, estado=Cita.Estado.CONFIRMADA)
        r = self.get()["resumen"]
        self.assertEqual((r["abandono_inferido"], r["procesos_activos_hoy"]), (0, 1))

    def test_alta_registrada_no_es_abandono(self):
        con_dp = self.paciente("Alta DP")
        self.sesiones(con_dp, [200, 193])
        self.cita(con_dp, 186, decision="DP-10")
        por_ficha = self.paciente("Alta ficha", frecuencia="alta")
        self.sesiones(por_ficha, [150])
        suspende = self.paciente("Suspende")
        self.cita(suspende, 120, decision="DP-09")
        r = self.get()["resumen"]
        self.assertEqual(r["abandono_inferido"], 0)
        self.assertEqual(r["altas_registradas"], 2)
        self.assertEqual(r["cierres_registrados"], 1)

    def test_dias_configurables_45_por_defecto(self):
        p = self.paciente()
        self.sesiones(p, [80, 60])
        d = self.get()
        self.assertEqual(d["filtros"]["dias_abandono"], 45)
        self.assertEqual(d["resumen"]["abandono_inferido"], 1)
        self.assertEqual(d["resumen"]["promedio_dias_s1_a_abandono"], 20)
        self.assertEqual(self.get(dias_abandono=90)["resumen"]["abandono_inferido"], 0)
        self.assertEqual(self.get(dias_abandono=5)["filtros"]["dias_abandono"], 15)  # tope inferior

    def test_dias_entre_sesiones(self):
        p = self.paciente()
        self.sesiones(p, [40, 33, 19])
        self.cita(p, -1, estado=Cita.Estado.AGENDADA)
        r = self.get()["resumen"]
        self.assertEqual(r["promedio_dias_entre_sesiones"], 10.5)  # (7 + 14) / 2


class PsicologoYCalidadTests(_Base):
    def test_psicologo_de_la_s1_y_sin_asignar_visible(self):
        a = self.paciente("De Ana")
        self.sesiones(a, [40, 33], medico=self.ps_ana)
        self.cita(a, -2, estado=Cita.Estado.AGENDADA)
        b = self.paciente("Ficha de Beto", profesional=self.ficha_beto)
        self.sesiones(b, [40])  # cita sin psicólogo: se usa el asignado
        c = self.paciente("Nadie")
        self.sesiones(c, [40])
        d = self.get()
        filas = {f["clave"]: f for f in d["por_psicologo"]}
        self.assertEqual(filas[f"p{self.ficha_ana.id}"]["sesiones_realizadas"], 2)
        self.assertEqual(filas[f"p{self.ficha_ana.id}"]["carga_activos_hoy"], 1)
        self.assertEqual(filas[f"p{self.ficha_beto.id}"]["por_ficha_asignada"], 1)
        self.assertEqual(filas["sin_asignar"]["nuevos"], 1)
        # Orden alfabético, "Sin asignar" al final: no hay ranking.
        self.assertEqual([f["psicologo"] for f in d["por_psicologo"]], ["Ana Ruiz", "Beto Paz", "Sin asignar"])
        cal = d["calidad"]
        self.assertEqual(cal["sesiones_periodo"], 4)
        self.assertEqual(cal["sesiones_sin_psicologo"], 2)
        self.assertEqual(cal["pct_con_psicologo"], 50.0)
        self.assertEqual(cal["procesos_sin_psicologo"], 1)

    def test_filtro_por_psicologo_sede_categoria_y_etapa(self):
        a = self.paciente("Ana adultos", sede="lima")
        self.sesiones(a, [40, 33], medico=self.ps_ana, categoria="adultos")
        b = self.paciente("Otro", sede="piura")
        self.sesiones(b, [40], categoria="parejas")
        self.assertEqual(self.get(psicologo=f"p{self.ficha_ana.id}")["resumen"]["procesos_iniciados"], 1)
        self.assertEqual(self.get(sede="piura")["resumen"]["procesos_iniciados"], 1)
        self.assertEqual(self.get(categoria="parejas")["resumen"]["procesos_iniciados"], 1)
        self.assertEqual(self.get(etapa="2")["resumen"]["procesos_iniciados"], 1)
        cats = {f["clave"] for f in self.get()["por_categoria"]}
        self.assertEqual(cats, {"adultos", "parejas"})

    def test_cierres_con_dp_y_fichas_sin_cita(self):
        p = self.paciente()
        for i, d in enumerate([90, 83, 76, 69, 62, 55], start=1):
            self.cita(p, d, n=i, decision="DP-08" if i == 6 else "")
        Atencion.objects.create(clinica=self.clinica, paciente=p, nota="Importada del Excel")
        d = self.get()
        self.assertEqual((d["calidad"]["cierres_bloque"], d["calidad"]["cierres_con_dp"]), (1, 1))
        self.assertEqual(d["universo"]["fichas_sin_cita"], 1)


class GerenciaUsaCitasAsistidasTests(_Base):
    def test_asistencia_cuenta_asistio_e_inasistencias(self):
        p = self.paciente()
        self.cita(p, 0, estado=Cita.Estado.ASISTIO)
        self.cita(p, 0, estado=Cita.Estado.ATENDIDA)
        self.cita(p, 0, estado=Cita.Estado.NO_ASISTIO)
        self.cita(p, 0, estado=Cita.Estado.CANCELADA)
        op = self.client.get("/api/gerencia/resumen/", {"periodo": "hoy"}).json()["operacion"]
        self.assertEqual((op["atendidas"], op["no_asistio"], op["canceladas"]), (2, 1, 1))
        self.assertEqual((op["asistencia_pct"], op["inasistencia_pct"], op["cancelacion_pct"]), (50, 25, 25))

    def test_retencion_y_curva_salen_de_citas_no_de_fichas(self):
        p = self.paciente()
        self.sesiones(p, [20, 13, 6])   # viene cada semana, sin dejar ficha
        self.cita(p, 30, servicio="Consulta inicial - Adultos")
        d = self.client.get("/api/gerencia/resumen/").json()
        self.assertEqual((d["retencion"]["con_sesiones"], d["retencion"]["verde"]), (1, 1))
        curva = d["diagnostico"]["continuidad"]
        self.assertEqual(curva["procesos"], 1)
        self.assertEqual({x["label"]: x["valor"] for x in curva["por_sesiones"]}["3"], 1)
        self.assertEqual(curva["terminados"], 0)
        self.assertEqual(curva["abandono_1_2_pct"], 0)
