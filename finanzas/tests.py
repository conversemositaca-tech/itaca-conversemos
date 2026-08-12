"""Pruebas de la liquidación de honorarios (lo que se le paga al psicólogo).

Es la regla de dinero más delicada del sistema y la que gerencia decidió a mano:
se paga por **sesión atendida × monto del servicio**, NO por un porcentaje de lo
cobrado, porque los descuentos al paciente los asume la clínica y no deben
reducir el pago al profesional.

    python manage.py test finanzas
"""
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from core.models import Clinica
from finanzas.models import Cobro, Servicio
from pacientes.models import Cita, Paciente
from usuarios.models import Usuario


class LiquidacionTests(TestCase):
    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-test")
        self.admin = Usuario.objects.create_user(
            email="gerencia@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ADMIN,
        )
        self.psico = Usuario.objects.create_user(
            email="psico@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.MEDICO,
        )
        self.paciente = Paciente.objects.create(clinica=self.clinica, nombre="Paciente de prueba")
        # El paciente paga 120; al psicólogo se le pagan 60 por sesión atendida.
        self.servicio = Servicio.objects.create(
            clinica=self.clinica, nombre="Terapia individual",
            precio=Decimal("120"), monto_terapeuta=Decimal("60"),
        )
        self.hoy = timezone.localdate()

    # -- utilidades ---------------------------------------------------------
    def _cita(self, hora, estado=Cita.Estado.ATENDIDA, servicio=None):
        inicio = timezone.make_aware(datetime.combine(self.hoy, time(hora, 0)))
        return Cita.objects.create(
            clinica=self.clinica, paciente=self.paciente, medico=self.psico,
            inicio=inicio, estado=estado,
            especialidad=(servicio or self.servicio).nombre,
        )

    def _liquidacion(self):
        self.client.force_login(self.admin)
        r = self.client.get(
            "/api/finanzas/liquidacion/",
            {"desde": self.hoy.isoformat(), "hasta": self.hoy.isoformat()},
        )
        self.assertEqual(r.status_code, 200)
        return r.json()

    # -- casos --------------------------------------------------------------
    def test_paga_por_sesion_atendida(self):
        self._cita(9)
        self._cita(10)
        datos = self._liquidacion()
        self.assertEqual(datos["total_sesiones"], 2)
        self.assertEqual(datos["total_a_pagar"], 120.0)  # 2 × 60

    def test_un_descuento_al_paciente_no_baja_el_pago_al_psicologo(self):
        """La clínica asume el descuento: el psicólogo cobra igual.

        Es la razón por la que la liquidación NO se calcula sobre lo cobrado.
        """
        cita = self._cita(9)
        Cobro.objects.create(  # se cobró la mitad del precio de lista
            clinica=self.clinica, paciente=self.paciente, cita=cita, servicio=self.servicio,
            concepto="Sesión con descuento", monto=Decimal("60"), estado=Cobro.Estado.PAGADO,
        )
        self.assertEqual(self._liquidacion()["total_a_pagar"], 60.0)

    def test_una_sesion_sin_cobrar_igual_se_paga(self):
        """El psicólogo atendió: que Coordinación no haya cobrado es otro problema."""
        self._cita(9)
        self.assertEqual(self._liquidacion()["total_a_pagar"], 60.0)

    def test_asistio_cuenta_y_cancelada_o_falta_no(self):
        self._cita(9, estado=Cita.Estado.ASISTIO)      # vino: se paga
        self._cita(10, estado=Cita.Estado.CANCELADA)   # no se paga
        self._cita(11, estado=Cita.Estado.NO_ASISTIO)  # no se paga
        self._cita(12, estado=Cita.Estado.AGENDADA)    # todavía no ocurre
        datos = self._liquidacion()
        self.assertEqual(datos["total_sesiones"], 1)
        self.assertEqual(datos["total_a_pagar"], 60.0)

    def test_servicio_sin_monto_configurado_se_avisa(self):
        """No se inventa un monto: paga 0 y el servicio sale listado en `sin_monto`,
        para que gerencia lo cargue en Finanzas → Precios."""
        otro = Servicio.objects.create(
            clinica=self.clinica, nombre="Taller nuevo", precio=Decimal("80"),
            monto_terapeuta=Decimal("0"),
        )
        self._cita(9, servicio=otro)
        datos = self._liquidacion()
        self.assertEqual(datos["total_a_pagar"], 0.0)
        self.assertIn("Taller nuevo", datos["sin_monto"])

    def test_fuera_del_rango_no_entra(self):
        pasado = timezone.make_aware(
            datetime.combine(self.hoy - timedelta(days=10), time(9, 0))
        )
        Cita.objects.create(
            clinica=self.clinica, paciente=self.paciente, medico=self.psico,
            inicio=pasado, estado=Cita.Estado.ATENDIDA, especialidad=self.servicio.nombre,
        )
        self.assertEqual(self._liquidacion()["total_sesiones"], 0)

    def test_el_psicologo_no_puede_ver_la_liquidacion(self):
        """Solo gerencia: son los honorarios de todo el equipo."""
        self.client.force_login(self.psico)
        r = self.client.get("/api/finanzas/liquidacion/")
        self.assertEqual(r.status_code, 403)
