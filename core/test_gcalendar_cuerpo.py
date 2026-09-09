"""Pruebas del cuerpo del evento que se manda a Google Calendar.

Por defecto el evento no debe llevar nombre ni teléfono del paciente: cualquiera
con acceso al calendario compartido los vería, tenga o no permiso para abrir su
ficha en Ítaca. Ver core/gcalendar.py.

    python manage.py test core.test_gcalendar_cuerpo
"""
from django.test import TestCase, override_settings
from django.utils import timezone

from core.gcalendar import _cuerpo
from core.models import Clinica
from pacientes.models import Cita, Paciente
from usuarios.models import Usuario


class CuerpoEventoTests(TestCase):
    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-gcal")
        self.psico = Usuario.objects.create_user(
            email="psico@test.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.MEDICO, nombre="Ana Ruiz",
        )
        self.paciente = Paciente.objects.create(
            clinica=self.clinica, nombre="Nombre Real Del Paciente",
            telefono="+51999999999", sede="lima",
        )
        self.cita = Cita.objects.create(
            clinica=self.clinica, paciente=self.paciente, medico=self.psico,
            inicio=timezone.now(), estado=Cita.Estado.CONFIRMADA,
        )

    @override_settings(GOOGLE_CALENDAR_MOSTRAR_PACIENTE=False)
    def test_por_defecto_no_lleva_nombre_ni_telefono(self):
        cuerpo = _cuerpo(self.cita)
        self.assertNotIn("Nombre Real Del Paciente", cuerpo["summary"])
        self.assertNotIn("Nombre Real Del Paciente", cuerpo["description"])
        self.assertNotIn("+51999999999", cuerpo["description"])
        self.assertIn("Sesión", cuerpo["summary"])

    @override_settings(GOOGLE_CALENDAR_MOSTRAR_PACIENTE=False)
    def test_por_defecto_si_lleva_psicologo_y_estado(self):
        cuerpo = _cuerpo(self.cita)
        self.assertIn("Ana Ruiz", cuerpo["summary"])
        self.assertIn("Psicólogo: Ana Ruiz", cuerpo["description"])
        self.assertIn("Estado: Confirmada", cuerpo["description"])

    @override_settings(GOOGLE_CALENDAR_MOSTRAR_PACIENTE=True)
    def test_activado_a_proposito_si_lleva_nombre_y_telefono(self):
        cuerpo = _cuerpo(self.cita)
        self.assertIn("Nombre Real Del Paciente", cuerpo["summary"])
        self.assertIn("Paciente: Nombre Real Del Paciente", cuerpo["description"])
        self.assertIn("Teléfono: +51999999999", cuerpo["description"])

    @override_settings(GOOGLE_CALENDAR_MOSTRAR_PACIENTE=False)
    def test_id_del_evento_es_deterministico_por_cita(self):
        self.assertEqual(_cuerpo(self.cita)["id"], f"itacacita{self.cita.id}")
