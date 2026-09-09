"""Pruebas de la pantalla Equipo (directorio de profesionales).

    python manage.py test usuarios
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.models import Clinica
from pacientes.models import Cita, Paciente
from usuarios.models import Profesional, Usuario


class PacientesStatsUsaSesionRealTests(TestCase):
    """"Equipo" muestra cuántos pacientes tiene "en proceso" cada profesional
    (los que están en curso pero aún sin frecuencia marcada). Contaba con el
    contador manual `Paciente.n_sesion` — auditado el 9 sep: los 22
    profesionales con caseload real mostraban ahí un 0, o casi."""

    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-equipo")
        self.admin = Usuario.objects.create_user(
            email="gerencia-eq@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ADMIN,
        )
        self.psico = Usuario.objects.create_user(
            email="p-eq@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.MEDICO,
        )
        self.ficha = Profesional.objects.create(clinica=self.clinica, usuario=self.psico, nombre="Psico Equipo")
        self.client.force_login(self.admin)

    def test_cuenta_a_los_que_asistieron_de_verdad_sin_frecuencia_marcada(self):
        # Sin frecuencia, contador manual en 0, pero con una sesión real ya asistida.
        p = Paciente.objects.create(
            clinica=self.clinica, nombre="Con sesión real", profesional=self.ficha,
            frecuencia="", n_sesion=0,
        )
        Cita.objects.create(
            clinica=self.clinica, paciente=p, medico=self.psico, n_sesion=2,
            estado=Cita.Estado.ASISTIO, inicio=timezone.now() - timedelta(days=5),
        )
        # Sin frecuencia y SIN ninguna sesión asistida: de verdad no cuenta.
        Paciente.objects.create(
            clinica=self.clinica, nombre="Sin ninguna sesión", profesional=self.ficha,
            frecuencia="", n_sesion=0,
        )
        r = self.client.get("/api/profesionales/")
        fila = next(x for x in r.json() if x["id"] == self.ficha.id)
        self.assertEqual(fila["pacientes_stats"]["sin_frecuencia"], 1)  # antes: 0
        self.assertEqual(fila["pacientes_stats"]["activos"], 1)
