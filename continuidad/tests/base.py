from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from continuidad.models import MotivoContinuidad, ProcesoContinuidad
from continuidad.motivos import asegurar_catalogo
from continuidad.reconciliacion import reconciliar_paciente
from core.models import Clinica
from pacientes.models import Cita, Paciente
from usuarios.models import Profesional, Usuario

# Por defecto, un proceso nuevo nace ACTIVO (registro formal desde siempre).
# Las pruebas de procesos "legacy" lo sobrescriben.
REGISTRO_DESDE_SIEMPRE = override_settings(CONTINUIDAD_REGISTRO_FORMAL_DESDE="2000-01-01")


class Base(TestCase):
    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conv-continuidad")
        self.admin = self.usuario("gerencia-c2@test.pe", Usuario.Rol.ADMIN)
        self.coord = self.usuario("coord-c2@test.pe", Usuario.Rol.ASISTENTE)
        self.analista = self.usuario("dc-c2@test.pe", Usuario.Rol.ANALISTA)
        self.u_ana = self.usuario("ana-c2@test.pe", Usuario.Rol.MEDICO, nombre="Ana")
        self.ana = Profesional.objects.create(clinica=self.clinica, nombre="Ana Ruiz", usuario=self.u_ana)
        self.beto = Profesional.objects.create(clinica=self.clinica, nombre="Beto Paz")
        asegurar_catalogo(self.clinica)

    def usuario(self, email, rol, **kw):
        return Usuario.objects.create_user(email=email, password="x", clinica=self.clinica, rol=rol, **kw)

    def motivo(self, codigo):
        return MotivoContinuidad.objects.get(clinica=self.clinica, codigo=codigo)

    def paciente(self, nombre="P", sede="piura", **kw):
        return Paciente.objects.create(clinica=self.clinica, nombre=nombre, sede=sede, **kw)

    def cita(self, p, hace, estado=Cita.Estado.ASISTIO, decision="", medico=None, servicio="Terapia individual", **kw):
        return Cita.objects.create(clinica=self.clinica, paciente=p, inicio=timezone.now() - timedelta(days=hace),
                                   estado=estado, decision=decision, medico=medico, especialidad=servicio, **kw)

    def sesiones(self, p, dias, **kw):
        return [self.cita(p, d, **kw) for d in dias]

    def proceso(self, p):
        """Reconcilia y devuelve el ProcesoContinuidad más reciente del paciente."""
        pares = reconciliar_paciente(p.pk)
        return ProcesoContinuidad.objects.get(pk=pares[-1][1].pk)
