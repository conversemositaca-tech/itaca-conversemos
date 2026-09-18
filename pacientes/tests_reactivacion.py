"""A quién llamar primero: los días sin venir.

La lista de "sin próxima sesión" tiene más de mil personas. Lo único que
distingue a quien todavía se puede recuperar de quien cerró su proceso hace
años es hace cuánto dejó de venir, así que ese número tiene que ser exacto.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.models import Clinica
from pacientes.models import Cita, Paciente
from pacientes.serializers import PacienteSerializer
from usuarios.models import Profesional, Usuario


class DiasSinVenirTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clinica = Clinica.objects.create(nombre="Ítaca", ciudad="Piura",
                                             slug="itaca-react", token_captacion="tok-react")
        cls.user = Usuario.objects.create_user(
            email="psi@react.pe", password="x", nombre="Psi",
            rol=Usuario.Rol.MEDICO, clinica=cls.clinica)
        cls.prof = Profesional.objects.create(clinica=cls.clinica, nombre="Psi",
                                              usuario=cls.user, sede="piura", activo=True)

    def _paciente(self, nombre):
        return Paciente.objects.create(clinica=self.clinica, nombre=nombre, sede="piura")

    def _sesion(self, paciente, hace_dias, estado="asistio"):
        return Cita.objects.create(
            clinica=self.clinica, paciente=paciente, medico=self.user,
            inicio=timezone.now() - timedelta(days=hace_dias), estado=estado)

    def _leer(self, paciente):
        return PacienteSerializer(paciente).data

    def test_cuenta_los_dias_desde_la_ultima_sesion(self):
        p = self._paciente("Ana")
        self._sesion(p, hace_dias=40)
        self.assertEqual(self._leer(p)["dias_sin_venir"], 40)

    def test_manda_la_sesion_mas_reciente(self):
        p = self._paciente("Beto")
        self._sesion(p, hace_dias=200)
        self._sesion(p, hace_dias=12)
        self.assertEqual(self._leer(p)["dias_sin_venir"], 12)

    def test_quien_nunca_vino_no_es_alguien_que_dejo_de_venir(self):
        # No es lo mismo "abandonó" que "todavía no tuvo su primera sesión":
        # confundirlos pondría a gente nueva en la lista de reactivación.
        p = self._paciente("Carla")
        self.assertIsNone(self._leer(p)["dias_sin_venir"])

    def test_una_cita_cancelada_no_cuenta_como_haber_venido(self):
        p = self._paciente("Dina")
        self._sesion(p, hace_dias=5, estado="cancelada")
        self.assertIsNone(self._leer(p)["dias_sin_venir"])

    def test_una_cita_a_la_que_no_asistio_tampoco(self):
        p = self._paciente("Elena")
        self._sesion(p, hace_dias=5, estado="no_asistio")
        self.assertIsNone(self._leer(p)["dias_sin_venir"])

    def test_los_tramos_separan_a_quien_se_puede_recuperar(self):
        # El corte de los 90 días es el que usa la pantalla para priorizar.
        reciente = self._paciente("Fabi")
        self._sesion(reciente, hace_dias=20)
        antiguo = self._paciente("Gabo")
        self._sesion(antiguo, hace_dias=400)
        self.assertLess(self._leer(reciente)["dias_sin_venir"], 90)
        self.assertGreater(self._leer(antiguo)["dias_sin_venir"], 180)

    def test_el_campo_viaja_en_la_lista_de_pacientes(self):
        # Si no sale en el serializer, la pantalla no puede ordenar por él.
        p = self._paciente("Hugo")
        self._sesion(p, hace_dias=3)
        self.assertIn("dias_sin_venir", self._leer(p))
