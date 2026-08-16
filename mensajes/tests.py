"""Pruebas del envío de recordatorios de cita.

Son los mensajes que bajan las faltas: si un día dejan de salir, hoy nadie se
entera hasta que un paciente no llega. El envío lo dispara algo de FUERA del
servidor (un cron en la nube, o una tarea programada), así que la lógica
conviene tenerla amarrada.

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

ENVIAR = "pacientes.recordatorios.registrar_y_enviar"


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


class RecordatoriosPorEndpointTests(TestCase):
    """El mismo envío, disparado desde la nube en vez de una computadora.

    Manda WhatsApps a pacientes reales sin que haya nadie mirando, así que lo
    que se prueba aquí es sobre todo lo que NO debe pasar: que quede abierto y
    que alguien reciba el recordatorio dos veces.
    """

    URL = "/api/integraciones/recordatorios/"
    TOKEN = "token-de-prueba"

    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-ep")
        self.psico = Usuario.objects.create_user(
            email="psicoep@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.MEDICO,
        )

    def _cita(self, nombre="Ana Pérez", telefono="987654321", hora=10):
        p = Paciente.objects.create(clinica=self.clinica, nombre=nombre, telefono=telefono)
        return Cita.objects.create(
            clinica=self.clinica, paciente=p, medico=self.psico,
            inicio=timezone.make_aware(datetime.combine(timezone.localdate(), time(hora, 0))),
            estado=Cita.Estado.AGENDADA, especialidad="Terapia individual",
        )

    def _llamar(self, token=TOKEN, envio=_ok, **body):
        cab = {"HTTP_X_INTEGRACION_TOKEN": token} if token is not None else {}
        with patch(ENVIAR, side_effect=envio):
            return self.client.post(self.URL, body, content_type="application/json", **cab)

    # -- que no quede abierto ------------------------------------------------
    def test_sin_token_configurado_en_el_servidor_no_manda_nada(self):
        """Si falta la variable de entorno, la puerta queda cerrada, no abierta."""
        cita = self._cita()
        with self.settings(ITACA_INTEGRACION_TOKEN=""):
            self.assertEqual(self._llamar().status_code, 403)
        cita.refresh_from_db()
        self.assertFalse(cita.recordatorio_enviado)

    def test_con_token_equivocado_no_manda_nada(self):
        cita = self._cita()
        with self.settings(ITACA_INTEGRACION_TOKEN=self.TOKEN):
            self.assertEqual(self._llamar(token="otro").status_code, 403)
        cita.refresh_from_db()
        self.assertFalse(cita.recordatorio_enviado)

    def test_sin_cabecera_no_manda_nada(self):
        self._cita()
        with self.settings(ITACA_INTEGRACION_TOKEN=self.TOKEN):
            self.assertEqual(self._llamar(token=None).status_code, 403)

    # -- que funcione y no se repita ----------------------------------------
    def test_con_el_token_correcto_manda_y_marca(self):
        cita = self._cita()
        with self.settings(ITACA_INTEGRACION_TOKEN=self.TOKEN):
            r = self._llamar()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["enviados"], 1)
        cita.refresh_from_db()
        self.assertTrue(cita.recordatorio_enviado)

    def test_llamarlo_dos_veces_el_mismo_dia_no_reenvia(self):
        """Lo que protege de que el cron y la tarea de Windows corran juntos y
        el paciente reciba el recordatorio por duplicado."""
        self._cita()
        with self.settings(ITACA_INTEGRACION_TOKEN=self.TOKEN):
            self.assertEqual(self._llamar().json()["enviados"], 1)
            self.assertEqual(self._llamar().json()["enviados"], 0)
        self.assertEqual(Mensaje.objects.filter(tipo=Mensaje.Tipo.RECORDATORIO).count(), 0)

    def test_el_dry_no_manda_ni_marca(self):
        cita = self._cita()
        with self.settings(ITACA_INTEGRACION_TOKEN=self.TOKEN):
            r = self._llamar(dry=True)
        self.assertEqual(r.json()["enviados"], 0)
        self.assertEqual(r.json()["detalle"][0]["estado"], "se_enviaria")
        cita.refresh_from_db()
        self.assertFalse(cita.recordatorio_enviado)

    def test_devuelve_el_detalle_de_lo_que_paso(self):
        """El cron guarda esta respuesta: si un día falla, ahí está el porqué."""
        self._cita(nombre="Ana Pérez")
        self._cita(nombre="Sin teléfono", telefono="", hora=11)
        with self.settings(ITACA_INTEGRACION_TOKEN=self.TOKEN):
            d = self._llamar(envio=_falla).json()
        self.assertEqual((d["fallidos"], d["omitidos"]), (1, 1))
        motivos = {x["paciente"]: x["estado"] for x in d["detalle"]}
        self.assertEqual(motivos["Ana Pérez"], "falló")
        self.assertEqual(motivos["Sin teléfono"], "sin_telefono")


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
