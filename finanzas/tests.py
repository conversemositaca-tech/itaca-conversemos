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
from finanzas.models import Cobro, Paquete, Servicio
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


class DescuentoDePaqueteTests(TestCase):
    """El paquete de sesiones se descuenta UNA vez por cita, venga por donde venga.

    Antes el descuento vivía solo dentro de "registrar la ficha clínica": si
    Coordinación marcaba "Atendida" desde el selector de la agenda, el paquete no
    bajaba y el paciente consumía sesiones que el sistema seguía dando por
    disponibles. Y si la cita se re-atendía, descontaba dos veces.
    """

    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-paq")
        self.coord = Usuario.objects.create_user(
            email="coordp@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ASISTENTE,
        )
        self.psico = Usuario.objects.create_user(
            email="psicop@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.MEDICO,
        )
        self.paciente = Paciente.objects.create(clinica=self.clinica, nombre="Ana Pérez")
        self.paquete = Paquete.objects.create(
            clinica=self.clinica, paciente=self.paciente, nombre="Paquete de 4 sesiones",
            sesiones_total=4, monto=Decimal("420"),
        )
        self.cita = Cita.objects.create(
            clinica=self.clinica, paciente=self.paciente, medico=self.psico,
            inicio=timezone.now(), estado=Cita.Estado.AGENDADA, especialidad="Terapia individual",
        )
        self.client.force_login(self.coord)

    def _estado(self, nuevo, cita=None):
        return self.client.post(f"/api/citas/{(cita or self.cita).id}/estado/",
                                {"estado": nuevo}, content_type="application/json")

    def _usadas(self):
        self.paquete.refresh_from_db()
        return self.paquete.sesiones_usadas

    def test_marcar_atendida_desde_la_agenda_descuenta(self):
        """El caso que no funcionaba: coordinación marca el estado a mano."""
        self._estado("atendida")
        self.assertEqual(self._usadas(), 1)

    def test_marcar_asistio_tambien_descuenta(self):
        self._estado("asistio")
        self.assertEqual(self._usadas(), 1)

    def test_no_descuenta_dos_veces_la_misma_cita(self):
        self._estado("asistio")
        self._estado("atendida")   # la misma cita avanza de estado
        self.assertEqual(self._usadas(), 1)

    def test_cancelar_devuelve_la_sesion(self):
        self._estado("atendida")
        self.assertEqual(self._usadas(), 1)
        self.client.post(f"/api/citas/{self.cita.id}/cancelar/")
        self.assertEqual(self._usadas(), 0)
        self.cita.refresh_from_db()
        self.assertIsNone(self.cita.paquete_id)

    def test_una_cita_agendada_no_consume_nada(self):
        self._estado("confirmada")
        self.assertEqual(self._usadas(), 0)

    def test_el_paquete_agotado_no_queda_en_negativo(self):
        self.paquete.sesiones_total = 1
        self.paquete.save(update_fields=["sesiones_total"])
        self._estado("atendida")
        otra = Cita.objects.create(
            clinica=self.clinica, paciente=self.paciente, medico=self.psico,
            inicio=timezone.now(), estado=Cita.Estado.AGENDADA, especialidad="Terapia individual",
        )
        self._estado("atendida", cita=otra)
        self.assertEqual(self._usadas(), 1)          # no pasa de su total
        otra.refresh_from_db()
        self.assertIsNone(otra.paquete_id)           # esa cita se cobra aparte
        self.paquete.refresh_from_db()
        self.assertEqual(self.paquete.estado, Paquete.Estado.AGOTADO)


class MarcarPagadoFechaTests(TestCase):
    """`Cobro.fecha` debe reflejar cuándo se CONFIRMA el pago, no cuándo se creó
    como pendiente — si no, un cobro atendido hoy y pagado mañana nunca aparece
    en los ingresos del día en que realmente se cobró (decidido con Gabriela)."""

    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-fecha-pago")
        self.coord = Usuario.objects.create_user(
            email="coordfp@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ASISTENTE,
        )
        self.paciente = Paciente.objects.create(clinica=self.clinica, nombre="Deudor de prueba")
        self.cobro = Cobro.objects.create(
            clinica=self.clinica, paciente=self.paciente, concepto="Sesión de ayer",
            monto=Decimal("120"), estado=Cobro.Estado.PENDIENTE,
            fecha=timezone.now() - timedelta(days=1),
        )
        self.client.force_login(self.coord)

    def test_marcar_pagado_actualiza_la_fecha_a_hoy(self):
        fecha_original = self.cobro.fecha
        r = self.client.post(f"/api/cobros/{self.cobro.id}/marcar_pagado/", {"medio_pago": "yape"})
        self.assertEqual(r.status_code, 200)
        self.cobro.refresh_from_db()
        self.assertGreater(self.cobro.fecha, fecha_original)
        self.assertEqual(timezone.localdate(self.cobro.fecha), timezone.localdate())

    def test_el_cobro_aparece_en_el_resumen_del_dia_en_que_se_pago(self):
        """Antes del fix, este cobro se quedaba contabilizado bajo AYER."""
        self.client.post(f"/api/cobros/{self.cobro.id}/marcar_pagado/", {"medio_pago": "efectivo"})
        r = self.client.get("/api/cobros/resumen/", {"periodo": "hoy"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["cobrado"], 120.0)
