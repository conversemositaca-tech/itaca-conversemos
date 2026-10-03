"""Regresiones encontradas en la revisión del PR #143 (release Software Factory v1).

    python manage.py test core.tests_release_revision
"""
from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.throttling import ScopedRateThrottle

from core.models import Clinica
from correo.services.destinatario import Destinatario
from correo.services.elegibilidad import exclusion_clinica
from pacientes.models import Cita, Paciente, SugerenciaRiesgo
from usuarios.models import Profesional, Usuario


class _Base(TestCase):
    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="rev-143")
        self.coord = Usuario.objects.create_user(email="c@r.pe", password="x", clinica=self.clinica, rol="asistente")
        self.psico = Usuario.objects.create_user(email="p@r.pe", password="x", clinica=self.clinica, rol="medico")
        ficha = Profesional.objects.create(clinica=self.clinica, usuario=self.psico, nombre="P")
        self.paciente = Paciente.objects.create(clinica=self.clinica, nombre="Ana", profesional=ficha,
                                                email="ana@x.pe")


class RiesgoSugeridoExcluyeDeCorreoTests(_Base):
    """Antes Eli escribía el riesgo oficial y eso excluía de correos. Desde que
    la IA solo sugiere, una sugerencia pendiente de riesgo también excluye:
    mientras una persona no la descarta, se trata como cierta."""

    def _excluido(self):
        return exclusion_clinica(Destinatario.de_paciente(self.paciente))

    def test_pendiente_moderado_o_alto_excluye(self):
        self.assertFalse(self._excluido())
        SugerenciaRiesgo.objects.create(clinica=self.clinica, paciente=self.paciente, valor_sugerido="alto")
        self.assertTrue(self._excluido())

    def test_pendiente_bajo_o_ya_rechazada_no_excluye(self):
        SugerenciaRiesgo.objects.create(clinica=self.clinica, paciente=self.paciente, valor_sugerido="bajo")
        SugerenciaRiesgo.objects.create(clinica=self.clinica, paciente=self.paciente, valor_sugerido="alto",
                                        estado=SugerenciaRiesgo.Estado.RECHAZADA)
        self.assertFalse(self._excluido())


class LimiteAntesDelPermisoTests(TestCase):
    """Un token inválido ahora también cuenta para el límite: probar tokens se frena."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_token_invalido_termina_en_429(self):
        with mock.patch.object(ScopedRateThrottle, "THROTTLE_RATES", {"integracion": "3/min"}), \
                self.settings(ITACA_INTEGRACION_TOKEN="bueno"):
            codigos = [self.client.get("/api/integraciones/psicologo/?telefono=1",
                                       HTTP_X_INTEGRACION_TOKEN="malo").status_code for _ in range(5)]
        self.assertEqual(codigos[:3], [403, 403, 403])
        self.assertEqual(codigos[3:], [429, 429])

    def test_una_peticion_valida_cuenta_una_sola_vez(self):
        with mock.patch.object(ScopedRateThrottle, "THROTTLE_RATES", {"integracion": "2/min"}), \
                self.settings(ITACA_INTEGRACION_TOKEN="bueno"):
            codigos = [self.client.get("/api/integraciones/psicologo/?telefono=1",
                                       HTTP_X_INTEGRACION_TOKEN="bueno").status_code for _ in range(3)]
        self.assertEqual(codigos, [200, 200, 429])

    def test_tambien_frena_el_despacho_de_correo(self):
        with mock.patch.object(ScopedRateThrottle, "THROTTLE_RATES", {"integracion": "1/min"}), \
                self.settings(ITACA_INTEGRACION_TOKEN="bueno"):
            codigos = [self.client.post("/api/correo/tareas/procesar-pendientes/", {}, content_type="application/json",
                                        HTTP_X_INTEGRACION_TOKEN="malo").status_code for _ in range(2)]
        self.assertEqual(codigos, [403, 429])


class FechaDeCobroVaciaTests(_Base):
    def test_fecha_vacia_es_hoy_y_errores_en_espanol(self):
        self.client.force_login(self.coord)
        r = self.client.post("/api/cobros/", {"paciente": self.paciente.id, "monto": "50", "fecha": ""},
                             content_type="application/json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["fecha"][:10], timezone.localdate().isoformat()[:10])
        r = self.client.post("/api/cobros/", {"paciente": self.paciente.id, "monto": "50", "cita": 999999},
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("No existe ese registro (cita)", r.json()["detail"])


class ResolverDosVecesTests(_Base):
    def test_la_segunda_revision_recibe_409(self):
        s = SugerenciaRiesgo.objects.create(clinica=self.clinica, paciente=self.paciente, valor_sugerido="alto")
        self.client.force_login(self.psico)
        url = f"/api/sugerencias-riesgo/{s.id}/resolver/"
        self.assertEqual(self.client.post(url, {"decision": "rechazar"}, content_type="application/json").status_code, 200)
        self.assertEqual(self.client.post(url, {"decision": "confirmar"}, content_type="application/json").status_code, 409)


class PaqueteConEstadoDeLaBaseTests(_Base):
    def test_sincronizar_usa_el_estado_guardado(self):
        from finanzas.models import Paquete
        from pacientes.api import sincronizar_paquete
        paq = Paquete.objects.create(clinica=self.clinica, paciente=self.paciente, nombre="4", sesiones_total=4, monto=1)
        cita = Cita.objects.create(clinica=self.clinica, paciente=self.paciente, medico=self.psico,
                                   inicio=timezone.now() + timedelta(days=1), estado=Cita.Estado.CANCELADA)
        cita.estado = Cita.Estado.ATENDIDA     # objeto en memoria desactualizado
        with mock.patch("pacientes.api.get_clinica_actual", return_value=self.clinica), \
                mock.patch("core.tenant.get_clinica_actual", return_value=self.clinica):
            sincronizar_paquete(cita)
        paq.refresh_from_db()
        self.assertEqual(paq.sesiones_usadas, 0, "la cita está cancelada en la base: no se descuenta")
