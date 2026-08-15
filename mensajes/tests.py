"""Pruebas del envío de recordatorios de cita.

Son los mensajes que bajan las faltas: si un día dejan de salir, hoy nadie se
entera hasta que un paciente no llega. Además el envío lo dispara una tarea
programada FUERA del servidor, así que la lógica conviene tenerla amarrada.

El envío real (Evolution / Cloud API) se simula: aquí se prueba a quién se le
manda, a quién no, y qué pasa cuando el envío falla.

    python manage.py test mensajes
"""
from datetime import datetime, time, timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from core.models import Clinica
from mensajes.models import Mensaje
from pacientes.models import Cita, Paciente
from usuarios.models import Usuario

ENVIAR = "pacientes.management.commands.enviar_recordatorios.registrar_y_enviar"


def _ok(clinica, **kw):
    """Simula un envío que sale bien."""
    return None, {"estado": "enviado", "detalle": ""}, ""


def _falla(clinica, **kw):
    """Simula que WhatsApp no aceptó el mensaje."""
    return None, {"estado": "fallido", "detalle": "instancia desconectada"}, "https://wa.me/51987654321"


class RecordatoriosTests(TestCase):
    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-rec")
        self.psico = Usuario.objects.create_user(
            email="psicor@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.MEDICO,
        )
        self.hoy = timezone.localdate()

    def _paciente(self, nombre, telefono="987654321"):
        return Paciente.objects.create(clinica=self.clinica, nombre=nombre, telefono=telefono)

    def _cita(self, paciente, hora=10, estado=Cita.Estado.AGENDADA, fecha=None, recordada=False):
        return Cita.objects.create(
            clinica=self.clinica, paciente=paciente, medico=self.psico,
            inicio=timezone.make_aware(datetime.combine(fecha or self.hoy, time(hora, 0))),
            estado=estado, especialidad="Terapia individual", recordatorio_enviado=recordada,
        )

    def _correr(self, envio=_ok, **kw):
        salida = StringIO()
        with patch(ENVIAR, side_effect=envio):
            call_command("enviar_recordatorios", stdout=salida, **kw)
        return salida.getvalue()

    # -- a quién se le manda -------------------------------------------------
    def test_manda_el_recordatorio_y_lo_marca(self):
        cita = self._cita(self._paciente("Ana Pérez"))
        self.assertIn("1 enviados", self._correr())
        cita.refresh_from_db()
        self.assertTrue(cita.recordatorio_enviado)

    def test_no_reenvia_a_quien_ya_fue_recordado(self):
        self._cita(self._paciente("Ana Pérez"), recordada=True)
        self.assertIn("0 enviados", self._correr())

    def test_no_manda_a_citas_canceladas_ni_ya_atendidas(self):
        self._cita(self._paciente("Cancelada"), hora=9, estado=Cita.Estado.CANCELADA)
        self._cita(self._paciente("Atendida"), hora=11, estado=Cita.Estado.ATENDIDA)
        self.assertIn("0 enviados", self._correr())

    def test_omite_al_paciente_sin_telefono(self):
        self._cita(self._paciente("Sin teléfono", telefono=""))
        salida = self._correr()
        self.assertIn("0 enviados", salida)
        self.assertIn("1 sin teléfono", salida)

    def test_no_toca_las_citas_de_otro_dia(self):
        self._cita(self._paciente("Mañana"), fecha=self.hoy + timedelta(days=1))
        self.assertIn("0 enviados", self._correr())

    def test_se_puede_pedir_otra_fecha(self):
        self._cita(self._paciente("Mañana"), fecha=self.hoy + timedelta(days=1))
        salida = self._correr(fecha=(self.hoy + timedelta(days=1)).isoformat())
        self.assertIn("1 enviados", salida)

    # -- cuando algo sale mal ------------------------------------------------
    def test_si_el_envio_falla_la_cita_NO_queda_marcada(self):
        """Así el siguiente intento vuelve a probar, en vez de darla por avisada."""
        cita = self._cita(self._paciente("Ana Pérez"))
        salida = self._correr(envio=_falla)
        self.assertIn("1 fallidos", salida)
        cita.refresh_from_db()
        self.assertFalse(cita.recordatorio_enviado)

    def test_el_dry_run_no_manda_ni_marca(self):
        cita = self._cita(self._paciente("Ana Pérez"))
        salida = self._correr(dry_run=True)
        self.assertIn("DRY-RUN", salida)
        cita.refresh_from_db()
        self.assertFalse(cita.recordatorio_enviado)


class AvisoDeRecordatoriosPendientesTests(TestCase):
    """El panel de inicio avisa si a media mañana las citas siguen sin recordar.

    El envío lo dispara una tarea programada fuera del servidor: si un día no
    corre, este aviso es lo único que lo delata.
    """

    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-av")
        self.coord = Usuario.objects.create_user(
            email="coordav@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ASISTENTE,
        )
        self.psico = Usuario.objects.create_user(
            email="psicoav@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.MEDICO,
        )
        self.client.force_login(self.coord)

    def _cita(self, telefono="987654321", recordada=False, estado=Cita.Estado.AGENDADA):
        p = Paciente.objects.create(clinica=self.clinica, nombre="Ana Pérez", telefono=telefono)
        return Cita.objects.create(
            clinica=self.clinica, paciente=p, medico=self.psico,
            inicio=timezone.make_aware(datetime.combine(timezone.localdate(), time(16, 0))),
            estado=estado, especialidad="Terapia individual", recordatorio_enviado=recordada,
        )

    def _hoy(self):
        return self.client.get("/api/hoy/").json()["recordatorios"]

    def test_cuenta_las_citas_de_hoy_sin_recordatorio(self):
        self._cita()
        self.assertEqual(self._hoy()["pendientes"], 1)

    def test_no_cuenta_las_ya_recordadas_ni_las_canceladas(self):
        self._cita(recordada=True)
        self._cita(estado=Cita.Estado.CANCELADA)
        self.assertEqual(self._hoy()["pendientes"], 0)

    def test_no_cuenta_a_quien_no_tiene_telefono(self):
        """No se le puede avisar: no es un recordatorio pendiente."""
        self._cita(telefono="")
        self.assertEqual(self._hoy()["pendientes"], 0)

    def test_temprano_no_avisa_todavia(self):
        self._cita()
        temprano = timezone.localtime().replace(hour=7, minute=30)
        with patch("django.utils.timezone.localtime", return_value=temprano):
            self.assertFalse(self.client.get("/api/hoy/").json()["recordatorios"]["avisar"])
