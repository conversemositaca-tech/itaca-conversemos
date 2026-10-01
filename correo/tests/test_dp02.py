"""Secuencia DP-02: programa días 1/7/21, cancela si la persona decide, re-evalúa al salir.

    python manage.py test correo.tests.test_dp02
"""
from datetime import timedelta
from unittest import mock

from django.test import override_settings
from django.utils import timezone

from leads.models import Lead
from pacientes.models import Cita, Paciente
from correo.models import ConsentimientoComunicacion as CC, EnvioProgramadoCorreo as EPC
from correo.services import consentimiento, programacion
from correo.services.destinatario import Destinatario

from .base import BaseCorreo
from .test_servicio import ENCENDIDO, respuesta

FLUJO = dict(ENCENDIDO, CORREO_DP02_HABILITADO=True)
POST = "correo.services.brevo.requests.post"


@override_settings(**FLUJO)
class SecuenciaDP02Tests(BaseCorreo):
    def setUp(self):
        super().setUp()
        self.p = self.paciente()
        self.d = Destinatario.de_paciente(self.p)
        consentimiento.otorgar(self.d, CC.Origen.RESERVA_WEB)
        self.consulta = Cita.objects.create(
            clinica=self.clinica, paciente=self.p, medico=self.psico,
            inicio=timezone.now() - timedelta(hours=2), estado=Cita.Estado.ATENDIDA)

    def registrar_dp(self, cita, dp, cuando=None):
        with self.captureOnCommitCallbacks(execute=True):
            cita.decision = dp
            cita.decision_registrada_en = cuando or timezone.now()
            cita.save()

    def vencer_todo(self):
        EPC.objects.filter(estado="PENDIENTE").update(ejecutar_en=timezone.now() - timedelta(minutes=1))

    def test_programa_tres_envios_a_1_7_21_dias(self):
        self.registrar_dp(self.consulta, "DP-02")
        base = Cita.objects.get(pk=self.consulta.pk).decision_registrada_en
        envios = list(EPC.objects.order_by("ejecutar_en"))
        self.assertEqual([e.plantilla_clave for e in envios], ["dp02_dia_1", "dp02_dia_7", "dp02_dia_21"])
        self.assertEqual([(e.ejecutar_en - base).days for e in envios], [1, 7, 21])
        self.assertTrue(all(e.paciente_id == self.p.id for e in envios))

    def test_no_duplica_al_volver_a_guardar(self):
        self.registrar_dp(self.consulta, "DP-02")
        cita = Cita.objects.get(pk=self.consulta.pk)
        for _ in range(3):
            with self.captureOnCommitCallbacks(execute=True):
                cita.save()
        self.assertEqual(EPC.objects.count(), 3)

    def test_dp02_historica_no_programa(self):
        self.registrar_dp(self.consulta, "DP-02", cuando=timezone.now() - timedelta(days=30))
        self.assertFalse(EPC.objects.exists())

    def test_dp02_sin_fecha_de_registro_no_programa(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.consulta.decision = "DP-02"
            self.consulta.save()
        self.assertFalse(EPC.objects.exists())

    @override_settings(CORREO_DP02_HABILITADO=False)
    def test_bandera_apagada_no_programa(self):
        self.registrar_dp(self.consulta, "DP-02")
        self.assertFalse(EPC.objects.exists())

    def test_dp01_posterior_cancela(self):
        self.registrar_dp(self.consulta, "DP-02")
        siguiente = Cita.objects.create(clinica=self.clinica, paciente=self.p,
                                        inicio=timezone.now() - timedelta(hours=1), estado="atendida")
        self.registrar_dp(siguiente, "DP-01")
        self.assertEqual(set(EPC.objects.values_list("estado", flat=True)), {"CANCELADO"})
        self.assertEqual(EPC.objects.count(), 3)  # no se borra nada

    def test_dp04_en_la_misma_cita_cancela(self):
        self.registrar_dp(self.consulta, "DP-02")
        self.registrar_dp(self.consulta, "DP-04")
        self.assertEqual(set(EPC.objects.values_list("estado", flat=True)), {"CANCELADO"})

    def test_reservar_otra_cita_cancela(self):
        self.registrar_dp(self.consulta, "DP-02")
        with self.captureOnCommitCallbacks(execute=True):
            Cita.objects.create(clinica=self.clinica, paciente=self.p,
                                inicio=timezone.now() + timedelta(days=3), estado="agendada")
        self.assertEqual(set(EPC.objects.values_list("estado", flat=True)), {"CANCELADO"})

    def test_lead_ganado_cancela(self):
        self.registrar_dp(self.consulta, "DP-02")
        lead = Lead.objects.create(clinica=self.clinica, nombre="Rosa", paciente=self.p)
        with self.captureOnCommitCallbacks(execute=True):
            lead.estado = Lead.Estado.GANADO
            lead.save()
        self.assertEqual(set(EPC.objects.values_list("estado", flat=True)), {"CANCELADO"})

    def test_envia_cuando_vence_con_baja_un_clic(self):
        self.registrar_dp(self.consulta, "DP-02")
        self.vencer_todo()
        with mock.patch(POST, return_value=respuesta()) as post:
            r = programacion.procesar_pendientes()
        self.assertEqual(r["enviados"], 3)
        asuntos = [c.kwargs["json"]["subject"] for c in post.call_args_list]
        self.assertEqual(sorted(asuntos), sorted(["Gracias por conversar con nosotros",
                                                  "¿Te quedó alguna duda?", "Seguimos por aquí"]))
        for c in post.call_args_list:
            self.assertIn("List-Unsubscribe", c.kwargs["json"]["headers"])
            self.assertNotIn("DP-02", c.kwargs["json"]["htmlContent"])

    def test_reevalua_consentimiento_al_salir(self):
        self.registrar_dp(self.consulta, "DP-02")
        consentimiento.revocar(self.d, CC.Origen.BAJA_UN_CLIC)
        self.vencer_todo()
        with mock.patch(POST) as post:
            programacion.procesar_pendientes()
        post.assert_not_called()
        self.assertEqual(set(EPC.objects.values_list("cancelado_motivo", flat=True)), {"BAJA"})

    def test_sin_consentimiento_no_sale(self):
        otra = self.paciente(nombre="Sin Permiso", email="sp@test.pe")
        c = Cita.objects.create(clinica=self.clinica, paciente=otra,
                                inicio=timezone.now() - timedelta(hours=1), estado="atendida")
        self.registrar_dp(c, "DP-02")
        self.vencer_todo()
        with mock.patch(POST) as post:
            programacion.procesar_pendientes()
        post.assert_not_called()

    def test_exclusion_que_aparece_despues_frena(self):
        self.registrar_dp(self.consulta, "DP-02")
        Paciente.objects.filter(pk=self.p.pk).update(riesgo=Paciente.Riesgo.ALTO)
        self.vencer_todo()
        with mock.patch(POST) as post:
            programacion.procesar_pendientes()
        post.assert_not_called()
        self.assertEqual(set(EPC.objects.values_list("cancelado_motivo", flat=True)),
                         {"EXCLUSION_SEGURIDAD"})

    def test_cron_concurrente_no_duplica(self):
        """Dos ejecuciones: la segunda no encuentra nada que tomar."""
        self.registrar_dp(self.consulta, "DP-02")
        self.vencer_todo()
        with mock.patch(POST, return_value=respuesta()) as post:
            programacion.procesar_pendientes()
            programacion.procesar_pendientes()
        self.assertEqual(post.call_count, 3)

    def test_tomados_en_paralelo_quedan_fuera(self):
        self.registrar_dp(self.consulta, "DP-02")
        self.vencer_todo()
        EPC.objects.update(estado="PROCESANDO")  # otra ejecución ya los tomó
        self.assertEqual(programacion.procesar_pendientes()["tomados"], 0)
