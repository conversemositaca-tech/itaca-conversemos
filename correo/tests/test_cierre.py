"""Cierre técnico de Email 1.0: rebote por dirección y envíos atascados.

    python manage.py test correo.tests.test_cierre
"""
from datetime import timedelta
from unittest import mock

from django.test import override_settings
from django.utils import timezone

from correo.models import (
    CorreoEnviado, EnvioProgramadoCorreo as EPC, PlantillaCorreo, PreferenciaCorreo,
)
from correo.services import preferencias, programacion
from correo.services.destinatario import Destinatario
from correo.services.elegibilidad import Codigo, evaluar_elegibilidad_correo

from .base import BaseCorreo
from .test_servicio import ENCENDIDO, respuesta


class ReboteDuroPorDireccionTests(BaseCorreo):
    def test_bloquea_la_direccion_que_reboto(self):
        p = self.paciente(email="vieja@test.pe")
        d = Destinatario.de_paciente(p)
        preferencias.marcar_rebote_duro(d, correo="vieja@test.pe")
        self.assertEqual(evaluar_elegibilidad_correo(d, "SERVICE").codigo, Codigo.REBOTE_DURO)

    def test_corregir_el_correo_levanta_el_bloqueo(self):
        p = self.paciente(email="vieja@test.pe")
        preferencias.marcar_rebote_duro(Destinatario.de_paciente(p), correo="vieja@test.pe")
        p.email = "nueva@test.pe"
        p.save(update_fields=["email"])
        d = Destinatario.de_paciente(p)
        self.assertEqual(evaluar_elegibilidad_correo(d, "SERVICE").codigo, Codigo.OK)

    def test_mayusculas_no_cuentan_como_otra_direccion(self):
        p = self.paciente(email="Rosa@Test.pe")
        d = Destinatario.de_paciente(p)
        preferencias.marcar_rebote_duro(d, correo="rosa@test.pe")
        self.assertTrue(preferencias.bloqueos(d)["rebote_duro"])

    def test_filas_antiguas_sin_direccion_bloquean_igual(self):
        p = self.paciente()
        PreferenciaCorreo.objects.create(clinica=self.clinica, paciente=p, rebote_duro=True)
        self.assertTrue(preferencias.bloqueos(Destinatario.de_paciente(p))["rebote_duro"])

    @override_settings(BREVO_WEBHOOK_TOKEN="t")
    def test_el_webhook_guarda_la_direccion_que_reboto(self):
        p = self.paciente(email="vieja@test.pe")
        d = Destinatario.de_paciente(p)
        fila = CorreoEnviado.objects.create(
            **d.identidad(), plantilla=PlantillaCorreo.objects.get(clave="reserva_confirmada"),
            categoria="SERVICE", destinatario_correo="vieja@test.pe", estado="ENVIADO",
            brevo_message_id="<m1>")
        self.client.post("/api/correo/webhooks/brevo/",
                         {"event": "hard_bounce", "message-id": "<m1>", "ts_event": 1},
                         content_type="application/json", HTTP_AUTHORIZATION="Bearer t")
        self.assertEqual(PreferenciaCorreo.objects.get(paciente=p).rebote_duro_correo, "vieja@test.pe")
        self.assertIsNotNone(fila)


@override_settings(**ENCENDIDO)
class EnviosAtascadosTests(BaseCorreo):
    def setUp(self):
        super().setUp()
        self.d = Destinatario.de_paciente(self.paciente())
        self.hace_una_hora = timezone.now() - timedelta(hours=1)

    def envio(self, clave="k1", intentos=1):
        e, _ = programacion.programar(plantilla_clave="reserva_confirmada", destinatario=self.d,
                                      ejecutar_en=self.hace_una_hora, clave_idempotencia=clave)
        EPC.objects.filter(pk=e.pk).update(estado="PROCESANDO", intentos=intentos,
                                           ultimo_intento_en=self.hace_una_hora)
        return e

    def correo(self, clave, estado):
        return CorreoEnviado.objects.create(
            **self.d.identidad(), plantilla=PlantillaCorreo.objects.get(clave="reserva_confirmada"),
            categoria="SERVICE", estado=estado, clave_idempotencia=clave,
            envio_iniciado_en=self.hace_una_hora)

    def test_si_nunca_llego_a_brevo_vuelve_a_la_cola(self):
        e = self.envio()
        r = programacion.recuperar_atascados()
        e.refresh_from_db()
        self.assertEqual((e.estado, r["recuperados"]), ("PENDIENTE", 1))

    def test_si_quedo_enviando_no_se_reenvia(self):
        e = self.envio()
        self.correo("k1", "ENVIANDO")
        r = programacion.recuperar_atascados()
        e.refresh_from_db()
        self.assertEqual((e.estado, e.error_detalle, r["inciertos"]), ("ERROR", "ESTADO_INCIERTO", 1))
        self.assertEqual(CorreoEnviado.objects.get().error_codigo, "ESTADO_INCIERTO")

    def test_si_ya_salio_se_marca_enviado(self):
        e = self.envio()
        self.correo("k1", "ENVIADO")
        programacion.recuperar_atascados()
        e.refresh_from_db()
        self.assertEqual(e.estado, "ENVIADO")

    def test_sin_intentos_disponibles_pasa_a_error(self):
        e = self.envio(intentos=programacion.MAX_INTENTOS)
        programacion.recuperar_atascados()
        e.refresh_from_db()
        self.assertEqual((e.estado, e.error_detalle), ("ERROR", "ATASCADO"))

    def test_lo_reciente_no_se_toca(self):
        e = self.envio()
        EPC.objects.filter(pk=e.pk).update(ultimo_intento_en=timezone.now())
        programacion.recuperar_atascados()
        e.refresh_from_db()
        self.assertEqual(e.estado, "PROCESANDO")

    def test_correo_suelto_enviando_pasa_a_incierto(self):
        fila = self.correo(None, "ENVIANDO")
        programacion.recuperar_atascados()
        fila.refresh_from_db()
        self.assertEqual((fila.estado, fila.error_codigo), ("ERROR", "ESTADO_INCIERTO"))

    def test_la_tarea_programada_recupera_y_despacha(self):
        self.envio()
        with mock.patch("correo.services.brevo.requests.post", return_value=respuesta()):
            r = programacion.procesar_pendientes()
        self.assertEqual(r["recuperados"], 1)
        self.assertEqual(r["tomados"], 1)
