"""Pruebas de las alertas de continuidad (riesgo de abandono en S3, fin de
bloque de sesiones sin decisión) y de su exposición en /api/hoy/.

    python manage.py test core
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from core.continuidad import (
    FIN_BLOQUE_SIN_DECISION, RIESGO_ABANDONO_S3, evaluar, proxima_meta,
)
from core.models import Clinica
from pacientes.models import Atencion, Cita, Paciente
from usuarios.models import Usuario


class ProximaMetaTests(TestCase):
    def test_sin_total_fijado_cuenta_de_6_en_6(self):
        self.assertEqual(proxima_meta(5, 0), 6)
        self.assertEqual(proxima_meta(11, 0), 12)

    def test_con_total_fijado_apunta_al_total(self):
        self.assertEqual(proxima_meta(7, 8), 8)

    def test_una_vez_superado_el_total_sigue_contando_de_6_en_6(self):
        """Antes del fix, pasado el total fijado el aviso no volvía nunca más
        (el caso 'Juanito': confirma seguir tras su bloque de 6)."""
        self.assertEqual(proxima_meta(7, 6), 12)
        self.assertEqual(proxima_meta(12, 6), 12)
        self.assertEqual(proxima_meta(13, 6), 18)


class EvaluarTests(TestCase):
    def test_riesgo_abandono_en_sesion_3_sin_proxima(self):
        self.assertEqual(
            evaluar(3, 0, tiene_proxima=False, ultima_decision="", frecuencia="semanal"),
            [RIESGO_ABANDONO_S3],
        )

    def test_sesion_3_con_proxima_no_es_riesgo(self):
        self.assertEqual(
            evaluar(3, 0, tiene_proxima=True, ultima_decision="", frecuencia="semanal"), [],
        )

    def test_fin_de_bloque_sin_decision(self):
        self.assertEqual(
            evaluar(6, 6, tiene_proxima=True, ultima_decision="", frecuencia="semanal"),
            [FIN_BLOQUE_SIN_DECISION],
        )

    def test_fin_de_bloque_con_decision_ya_registrada_no_avisa(self):
        self.assertEqual(
            evaluar(6, 6, tiene_proxima=True, ultima_decision="DP-08", frecuencia="semanal"), [],
        )

    def test_frecuencia_cerrada_no_avisa_nada(self):
        self.assertEqual(
            evaluar(3, 0, tiene_proxima=False, ultima_decision="", frecuencia="alta"), [],
        )
        self.assertEqual(
            evaluar(6, 6, tiene_proxima=True, ultima_decision="", frecuencia="en_pausa"), [],
        )

    def test_sin_sesion_no_avisa(self):
        self.assertEqual(evaluar(0, 0, True, "", "semanal"), [])


class HoyContinuidadViewTests(TestCase):
    """Integración: /api/hoy/ con datos reales, por rol."""

    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-continuidad")
        self.admin = Usuario.objects.create_user(
            email="gerencia@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ADMIN,
        )
        self.coord_lima = Usuario.objects.create_user(
            email="ayvi@test.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.ASISTENTE, sede=Usuario.Sede.LIMA,
        )
        self.coord_piura = Usuario.objects.create_user(
            email="yazmin@test.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.ASISTENTE, sede=Usuario.Sede.PIURA,
        )

    def _paciente(self, nombre, sede, n_sesion, sesiones_proceso=0, frecuencia="semanal"):
        return Paciente.objects.create(
            clinica=self.clinica, nombre=nombre, sede=sede,
            n_sesion=n_sesion, sesiones_proceso=sesiones_proceso, frecuencia=frecuencia,
        )

    def _cita(self, paciente, dias, estado=Cita.Estado.AGENDADA, decision=""):
        return Cita.objects.create(
            clinica=self.clinica, paciente=paciente,
            inicio=timezone.now() + timedelta(days=dias), estado=estado, decision=decision,
        )

    def _hoy(self, usuario):
        self.client.force_login(usuario)
        r = self.client.get("/api/hoy/")
        self.assertEqual(r.status_code, 200)
        return r.json()

    def test_riesgo_abandono_s3_sin_proxima_cita(self):
        p = self._paciente("Sin próxima en S3", "lima", n_sesion=3)
        datos = self._hoy(self.coord_lima)
        nombres = [x["nombre"] for x in datos["riesgo_abandono"]]
        self.assertIn(p.nombre, nombres)
        self.assertNotIn(p.nombre, [x["nombre"] for x in datos["por_continuidad"]])

    def test_s3_con_proxima_cita_no_es_riesgo(self):
        p = self._paciente("Con próxima en S3", "lima", n_sesion=3)
        self._cita(p, dias=2)
        datos = self._hoy(self.coord_lima)
        self.assertNotIn(p.nombre, [x["nombre"] for x in datos["riesgo_abandono"]])

    def test_fin_de_bloque_sin_decision_registrada(self):
        p = self._paciente("Fin de bloque sin decidir", "lima", n_sesion=6, sesiones_proceso=6)
        self._cita(p, dias=-1, estado=Cita.Estado.ATENDIDA, decision="")
        datos = self._hoy(self.coord_lima)
        self.assertIn(p.nombre, [x["nombre"] for x in datos["por_continuidad"]])

    def test_fin_de_bloque_con_decision_ya_no_avisa(self):
        p = self._paciente("Fin de bloque ya decidido", "lima", n_sesion=6, sesiones_proceso=6)
        self._cita(p, dias=-1, estado=Cita.Estado.ATENDIDA, decision="DP-08")
        datos = self._hoy(self.coord_lima)
        self.assertNotIn(p.nombre, [x["nombre"] for x in datos["por_continuidad"]])

    def test_coordinadora_de_lima_no_ve_pacientes_de_piura(self):
        """Antes de este fix, la tarjeta de continuidad no filtraba por sede
        para el rol asistente: Ayvi (Lima) veía también a los de Piura."""
        de_piura = self._paciente("Paciente de Piura", "piura", n_sesion=3)
        datos_lima = self._hoy(self.coord_lima)
        nombres = [x["nombre"] for x in datos_lima["riesgo_abandono"]]
        self.assertNotIn(de_piura.nombre, nombres)
        datos_piura = self._hoy(self.coord_piura)
        self.assertIn(de_piura.nombre, [x["nombre"] for x in datos_piura["riesgo_abandono"]])

    def test_admin_ve_todas_las_sedes(self):
        de_lima = self._paciente("Ana de Lima", "lima", n_sesion=3)
        de_piura = self._paciente("Beto de Piura", "piura", n_sesion=3)
        datos = self._hoy(self.admin)
        nombres = [x["nombre"] for x in datos["riesgo_abandono"]]
        self.assertIn(de_lima.nombre, nombres)
        self.assertIn(de_piura.nombre, nombres)

    def test_historia_pendiente_si_tuvo_sesion_y_no_tiene_historia(self):
        p = self._paciente("Sin historia registrada", "lima", n_sesion=1)
        datos = self._hoy(self.coord_lima)
        self.assertIn(p.nombre, [x["nombre"] for x in datos["historias_pendientes"]])

    def test_sin_sesion_todavia_no_aparece_como_pendiente(self):
        p = self._paciente("Recién agendado", "lima", n_sesion=0)
        datos = self._hoy(self.coord_lima)
        self.assertNotIn(p.nombre, [x["nombre"] for x in datos["historias_pendientes"]])

    def test_con_historia_ya_registrada_no_aparece(self):
        p = self._paciente("Con historia al día", "lima", n_sesion=1)
        Atencion.objects.create(clinica=self.clinica, paciente=p, tipo=Atencion.Tipo.HISTORIA)
        datos = self._hoy(self.coord_lima)
        self.assertNotIn(p.nombre, [x["nombre"] for x in datos["historias_pendientes"]])
