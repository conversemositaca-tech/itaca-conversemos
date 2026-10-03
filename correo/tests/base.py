"""Datos mínimos compartidos por los tests de correo."""
from datetime import date

from django.test import TestCase

from core.models import Clinica
from leads.models import Lead
from pacientes.models import Paciente
from usuarios.models import Usuario


class BaseCorreo(TestCase):
    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-correo")
        self.admin = Usuario.objects.create_user(
            email="admin-correo@test.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.ADMIN, nombre="Gerencia")
        self.coord = Usuario.objects.create_user(
            email="coord-correo@test.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.ASISTENTE, nombre="Ayvi")
        self.psico = Usuario.objects.create_user(
            email="psico-correo@test.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.MEDICO, nombre="Lic. Ana")
        self.analista = Usuario.objects.create_user(
            email="analista-correo@test.pe", password="x", clinica=self.clinica,
            rol="analista", nombre="Dirección Clínica")

    def paciente(self, nombre="Rosa Pérez", email="rosa@test.pe", **extra):
        return Paciente.objects.create(clinica=self.clinica, nombre=nombre, email=email,
                                       telefono="987654321", sede="piura", **extra)

    def menor(self, tutor_correo="mama@test.pe", **extra):
        hoy = date.today()
        return self.paciente(nombre="Lucas Pérez", email="",
                             fecha_nacimiento=date(hoy.year - 9, 1, 1),
                             tutor_nombre="Carmen Pérez", tutor_correo=tutor_correo, **extra)

    def lead(self, nombre="Rosa Pérez", email="rosa@test.pe", **extra):
        return Lead.objects.create(clinica=self.clinica, nombre=nombre, email=email,
                                   telefono="987654321", sede="piura", **extra)
