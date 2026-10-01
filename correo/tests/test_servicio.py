"""Servicio central: elegibilidad, Brevo (simulado), armado, programación.

Ningún test llama a Brevo de verdad: `requests.post` está simulado y además
no hay BREVO_API_KEY real en el entorno de pruebas.

    python manage.py test correo.tests.test_servicio
"""
import json
from datetime import timedelta
from unittest import mock

import requests
from django.test import override_settings
from django.utils import timezone

from pacientes.models import Cita, Paciente, RespuestaNPS
from correo.models import (
    ConsentimientoComunicacion as CC, CorreoEnviado, EnvioProgramadoCorreo as EPC, PlantillaCorreo,
)
from correo.services import brevo, consentimiento, preferencias, programacion, render
from correo.services.destinatario import Destinatario
from correo.services.elegibilidad import Codigo, evaluar_elegibilidad_correo
from correo.services.envio import enviar_correo

from .base import BaseCorreo

ENCENDIDO = dict(CORREO_HABILITADO=True, BREVO_API_KEY="clave-de-prueba",
                 CORREO_BASE_URL_PUBLICA="https://conversemos.test")


def respuesta(status=201, cuerpo=None):
    r = mock.Mock()
    r.status_code = status
    r.json.return_value = cuerpo if cuerpo is not None else {"messageId": "<abc@smtp-relay.mailin.fr>"}
    return r


class ElegibilidadTests(BaseCorreo):
    def evaluar(self, dest, cat):
        return evaluar_elegibilidad_correo(dest, cat)

    # --- SERVICE ---
    def test_service_no_necesita_consentimiento_comercial(self):
        self.assertEqual(self.evaluar(Destinatario.de_paciente(self.paciente()), "SERVICE").codigo, Codigo.OK)

    def test_service_sin_correo(self):
        r = self.evaluar(Destinatario.de_paciente(self.paciente(email="")), "SERVICE")
        self.assertEqual(r.codigo, Codigo.SIN_CORREO)

    def test_service_correo_invalido(self):
        r = self.evaluar(Destinatario.de_paciente(self.paciente(email="no-es-correo")), "SERVICE")
        self.assertEqual(r.codigo, Codigo.DESTINATARIO_INVALIDO)

    def test_service_rebote_y_spam_bloquean(self):
        d = Destinatario.de_paciente(self.paciente())
        preferencias.marcar_rebote_duro(d)
        self.assertEqual(self.evaluar(d, "SERVICE").codigo, Codigo.REBOTE_DURO)
        d2 = Destinatario.de_paciente(self.paciente(nombre="Otra", email="otra@test.pe"))
        preferencias.marcar_spam(d2)
        self.assertEqual(self.evaluar(d2, "SERVICE").codigo, Codigo.SPAM)

    def test_service_no_lo_bloquea_la_baja_comercial_ni_el_proceso(self):
        p = self.paciente(frecuencia=Paciente.Frecuencia.ALTA, riesgo=Paciente.Riesgo.ALTO)
        d = Destinatario.de_paciente(p)
        consentimiento.revocar(d, CC.Origen.BAJA_UN_CLIC)
        RespuestaNPS.objects.create(clinica=self.clinica, paciente=p, puntaje=2, fecha=timezone.localdate())
        self.assertEqual(self.evaluar(d, "SERVICE").codigo, Codigo.OK)

    # --- MARKETING ---
    def _consentido(self, **extra):
        p = self.paciente(**extra)
        d = Destinatario.de_paciente(p)
        consentimiento.otorgar(d, CC.Origen.RESERVA_WEB)
        return p, d

    def test_marketing_requiere_consentimiento(self):
        d = Destinatario.de_paciente(self.paciente())
        self.assertEqual(self.evaluar(d, "MARKETING").codigo, Codigo.SIN_CONSENTIMIENTO)
        consentimiento.otorgar(d, CC.Origen.RESERVA_WEB)
        self.assertEqual(self.evaluar(d, "MARKETING").codigo, Codigo.OK)

    def test_marketing_revocado_es_baja(self):
        _, d = self._consentido()
        consentimiento.revocar(d, CC.Origen.PREFERENCIAS_WEB)
        self.assertEqual(self.evaluar(d, "MARKETING").codigo, Codigo.BAJA)

    def test_marketing_spam_y_rebote(self):
        _, d = self._consentido()
        preferencias.marcar_rebote_duro(d)
        self.assertEqual(self.evaluar(d, "MARKETING").codigo, Codigo.REBOTE_DURO)

    def test_marketing_exclusiones_clinicas_no_revelan_motivo(self):
        casos = [
            dict(frecuencia=Paciente.Frecuencia.ALTA),
            dict(frecuencia=Paciente.Frecuencia.EN_PAUSA),
            dict(riesgo=Paciente.Riesgo.MODERADO),
            dict(riesgo=Paciente.Riesgo.ALTO),
        ]
        for i, extra in enumerate(casos):
            _, d = self._consentido(nombre=f"Persona {i}", email=f"p{i}@test.pe", **extra)
            self.assertEqual(self.evaluar(d, "MARKETING").codigo, Codigo.EXCLUSION_SEGURIDAD, extra)

    def test_marketing_detractor_nps(self):
        p, d = self._consentido()
        RespuestaNPS.objects.create(clinica=self.clinica, paciente=p, puntaje=5, fecha=timezone.localdate())
        self.assertEqual(self.evaluar(d, "MARKETING").codigo, Codigo.EXCLUSION_SEGURIDAD)

    def test_marketing_dp16_dp10_dp09(self):
        for i, dp in enumerate((Cita.Decision.DP16, Cita.Decision.DP10, Cita.Decision.DP09)):
            p, d = self._consentido(nombre=f"Persona {i}", email=f"d{i}@test.pe")
            Cita.objects.create(clinica=self.clinica, paciente=p, inicio=timezone.now(), decision=dp)
            self.assertEqual(self.evaluar(d, "MARKETING").codigo, Codigo.EXCLUSION_SEGURIDAD, dp)

    # --- CARE ---
    def test_care_requiere_consentimiento_asistencial(self):
        d = Destinatario.de_paciente(self.paciente())
        consentimiento.otorgar(d, CC.Origen.RESERVA_WEB)  # comercial no basta
        self.assertEqual(self.evaluar(d, "CARE").codigo, Codigo.SIN_CONSENTIMIENTO)
        consentimiento.otorgar(d, CC.Origen.PANEL_PRESENCIAL, finalidad=CC.Finalidad.ASISTENCIAL)
        self.assertEqual(self.evaluar(d, "CARE").codigo, Codigo.OK)

    # --- Menores ---
    def test_menor_nunca_recibe_directo(self):
        m = self.menor()
        r = self.evaluar(Destinatario.de_paciente(m), "SERVICE")
        self.assertTrue(r.permitido)
        self.assertTrue(r.destinatario.es_tutor)
        self.assertEqual(r.destinatario.correo(), "mama@test.pe")

    def test_menor_sin_tutor(self):
        m = self.menor(tutor_correo="")
        self.assertEqual(self.evaluar(Destinatario.de_paciente(m), "SERVICE").codigo, Codigo.MENOR_SIN_TUTOR)

    def test_marketing_de_menor_requiere_consentimiento_del_tutor(self):
        m = self.menor()
        d = Destinatario.de_paciente(m)
        self.assertEqual(self.evaluar(d, "MARKETING").codigo, Codigo.SIN_CONSENTIMIENTO)
        consentimiento.otorgar(Destinatario.tutor_de(m), CC.Origen.CONSENTIMIENTO_INFORMADO)
        self.assertEqual(self.evaluar(d, "MARKETING").codigo, Codigo.OK)

    def test_plantilla_inactiva(self):
        pl = PlantillaCorreo.objects.get(clave="reserva_confirmada", version=1)
        pl.activa = False
        r = evaluar_elegibilidad_correo(Destinatario.de_paciente(self.paciente()), "SERVICE", pl)
        self.assertEqual(r.codigo, Codigo.PLANTILLA_INACTIVA)


@override_settings(**ENCENDIDO)
class BrevoTests(BaseCorreo):
    def test_payload_minimo_sin_datos_clinicos_ni_contactos(self):
        with mock.patch("correo.services.brevo.requests.post", return_value=respuesta()) as post:
            mid = brevo.enviar(para_correo="rosa@test.pe", para_nombre="Rosa", asunto="Hola",
                               html="<p>x</p>", texto="x", etiqueta="correo:abc")
        self.assertEqual(mid, "<abc@smtp-relay.mailin.fr>")
        url = post.call_args.args[0]
        self.assertTrue(url.endswith("/smtp/email"))
        self.assertNotIn("contacts", url)
        self.assertNotIn("lists", url)
        payload = post.call_args.kwargs["json"]
        self.assertEqual(set(payload), {"sender", "to", "replyTo", "subject", "htmlContent",
                                        "textContent", "tags"})
        self.assertNotIn("params", payload)
        self.assertEqual(payload["tags"], ["correo:abc"])
        self.assertEqual(post.call_args.kwargs["headers"]["api-key"], "clave-de-prueba")

    def test_timeout_de_conexion_es_reintentable(self):
        with mock.patch("correo.services.brevo.requests.post", side_effect=requests.exceptions.ConnectTimeout):
            with self.assertRaises(brevo.ErrorBrevo) as e:
                brevo.enviar(para_correo="a@b.pe", para_nombre="", asunto="a", html="a", texto="a", etiqueta="t")
        self.assertTrue(e.exception.reintentable)

    def test_timeout_de_respuesta_no_se_reintenta(self):
        """Brevo pudo haberlo aceptado: reintentar duplicaría el correo."""
        with mock.patch("correo.services.brevo.requests.post", side_effect=requests.exceptions.ReadTimeout):
            with self.assertRaises(brevo.ErrorBrevo) as e:
                brevo.enviar(para_correo="a@b.pe", para_nombre="", asunto="a", html="a", texto="a", etiqueta="t")
        self.assertFalse(e.exception.reintentable)

    def test_4xx_no_reintentable_5xx_si(self):
        for status, esperado in ((400, False), (401, False), (500, True), (503, True), (429, True)):
            with mock.patch("correo.services.brevo.requests.post",
                            return_value=respuesta(status, {"code": "x", "message": "y"})):
                with self.assertRaises(brevo.ErrorBrevo) as e:
                    brevo.enviar(para_correo="a@b.pe", para_nombre="", asunto="a", html="a", texto="a", etiqueta="t")
            self.assertEqual(e.exception.reintentable, esperado, status)

    @override_settings(BREVO_API_KEY="")
    def test_sin_clave_no_llama(self):
        with mock.patch("correo.services.brevo.requests.post") as post:
            with self.assertRaises(brevo.ErrorBrevo):
                brevo.enviar(para_correo="a@b.pe", para_nombre="", asunto="a", html="a", texto="a", etiqueta="t")
        post.assert_not_called()


class ArmadoTests(BaseCorreo):
    def test_contexto_con_dato_clinico_se_rechaza(self):
        pl = PlantillaCorreo.objects.get(clave="dp02_dia_1")
        for clave in ("motivo_consulta", "decision", "riesgo", "nps", "especialidad"):
            with self.assertRaises(render.ContextoNoPermitido):
                render.armar(pl, {"nombre": "Rosa", clave: "x"})

    @override_settings(CORREO_BASE_URL_PUBLICA="https://conversemos.test")
    def test_marketing_lleva_pie_legal_preferencias_y_baja_un_clic(self):
        pl = PlantillaCorreo.objects.get(clave="dp02_dia_7")
        asunto, html, texto, cab = render.armar(pl, {"nombre": "Rosa"}, token_preferencias="tok")
        self.assertEqual(asunto, "¿Te quedó alguna duda?")
        self.assertIn("[RAZÓN SOCIAL]", html)
        self.assertIn("[CANAL ARCO]", texto)
        self.assertIn("https://conversemos.test/preferencias/correo/tok/", html)
        self.assertEqual(cab["List-Unsubscribe"], "<https://conversemos.test/api/correo/baja/tok/>")
        self.assertEqual(cab["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click")
        self.assertIn("https://conversemos.test/itaca-logo-h.png", html)
        self.assertIn("#00B8D8", html)

    def test_service_no_lleva_baja(self):
        pl = PlantillaCorreo.objects.get(clave="reserva_confirmada")
        asunto, html, texto, cab = render.armar(pl, {
            "nombre": "Rosa", "fecha": "lunes 6 de octubre", "hora": "10:00", "modalidad": "Presencial",
            "es_virtual": False, "direccion_sede": "Av. Bolognesi 582, Of. 201, Piura"})
        self.assertEqual(cab, {})
        self.assertNotIn("Cancelar suscripción", html)
        self.assertIn("Lugar: Av. Bolognesi 582", texto)
        for palabra in ("terapia", "psicolog"):
            self.assertNotIn(palabra, asunto.lower())

    def test_el_html_escapa_lo_que_viene_del_sistema(self):
        pl = PlantillaCorreo.objects.get(clave="dp02_dia_1")
        _, html, _, _ = render.armar(pl, {"nombre": "<script>x</script>"})
        self.assertNotIn("<script>x", html)


@override_settings(**ENCENDIDO)
class EnviarCorreoTests(BaseCorreo):
    def enviar(self, dest, clave="dp02_dia_1", **kw):
        return enviar_correo(plantilla_clave=clave, destinatario=dest, contexto={}, origen="prueba", **kw)

    @override_settings(CORREO_HABILITADO=False)
    def test_apagado_no_crea_ni_llama(self):
        with mock.patch("correo.services.brevo.requests.post") as post:
            self.assertIsNone(self.enviar(Destinatario.de_paciente(self.paciente())))
        post.assert_not_called()
        self.assertFalse(CorreoEnviado.objects.exists())

    def test_no_elegible_queda_en_bitacora_sin_llamar(self):
        with mock.patch("correo.services.brevo.requests.post") as post:
            fila = self.enviar(Destinatario.de_paciente(self.paciente()))
        post.assert_not_called()
        self.assertEqual((fila.estado, fila.error_codigo), ("CANCELADO_ELEGIBILIDAD", "SIN_CONSENTIMIENTO"))

    def test_envio_ok_registra_message_id_y_no_guarda_html(self):
        d = Destinatario.de_paciente(self.paciente())
        consentimiento.otorgar(d, CC.Origen.RESERVA_WEB)
        with mock.patch("correo.services.brevo.requests.post", return_value=respuesta()) as post:
            fila = self.enviar(d)
        self.assertEqual(fila.estado, "ENVIADO")
        self.assertEqual(fila.brevo_message_id, "<abc@smtp-relay.mailin.fr>")
        self.assertEqual(fila.asunto, "Gracias por conversar con nosotros")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["tags"], [f"correo:{fila.uuid}"])
        self.assertIn("List-Unsubscribe", payload["headers"])
        texto_payload = json.dumps(payload)
        for prohibido in (str(d.paciente.id), "DP-02", "riesgo"):
            self.assertNotIn(f'"{prohibido}"', texto_payload)
        campos = {f.name for f in CorreoEnviado._meta.get_fields()}
        self.assertFalse({"html", "cuerpo_html", "payload", "contexto"} & campos)

    def test_misma_clave_no_envia_dos_veces(self):
        d = Destinatario.de_paciente(self.paciente())
        with mock.patch("correo.services.brevo.requests.post", return_value=respuesta()) as post:
            a = self.enviar(d, clave="reserva_confirmada", clave_idempotencia="k1")
            b = self.enviar(d, clave="reserva_confirmada", clave_idempotencia="k1")
        self.assertEqual(a.pk, b.pk)
        self.assertEqual(post.call_count, 1)

    def test_error_reintentable_marca_error(self):
        d = Destinatario.de_paciente(self.paciente())
        with mock.patch("correo.services.brevo.requests.post", return_value=respuesta(503, {})):
            fila = self.enviar(d, clave="reserva_confirmada")
        self.assertEqual(fila.estado, "ERROR")
        self.assertTrue(fila.reintentable)

    def test_menor_se_envia_al_tutor(self):
        m = self.menor()
        with mock.patch("correo.services.brevo.requests.post", return_value=respuesta()) as post:
            fila = self.enviar(Destinatario.de_paciente(m), clave="reserva_confirmada")
        self.assertTrue(fila.es_tutor)
        self.assertEqual(post.call_args.kwargs["json"]["to"][0]["email"], "mama@test.pe")


@override_settings(**ENCENDIDO)
class ProgramacionTests(BaseCorreo):
    def setUp(self):
        super().setUp()
        self.p = self.paciente()
        self.d = Destinatario.de_paciente(self.p)
        programacion.constructor("prueba_")(lambda e: (Destinatario.de_fila(e), {}, "prueba"))

    def tearDown(self):
        programacion._CONSTRUCTORES.pop("prueba_", None)

    def programar(self, clave="k", minutos=-1):
        # La plantilla es real; el constructor de prueba se engancha por prefijo.
        return programacion.programar(plantilla_clave="reserva_confirmada", destinatario=self.d,
                                      ejecutar_en=timezone.now() + timedelta(minutes=minutos),
                                      clave_idempotencia=clave)

    def test_programar_es_idempotente(self):
        a, creado_a = self.programar()
        b, creado_b = self.programar()
        self.assertEqual((a.pk, creado_a, creado_b), (b.pk, True, False))

    def test_sin_constructor_se_cancela(self):
        e, _ = self.programar()
        with mock.patch("correo.services.brevo.requests.post", return_value=respuesta()):
            r = programacion.procesar_pendientes()
        e.refresh_from_db()
        self.assertEqual((r["cancelados"], e.estado), (1, "CANCELADO"))

    def test_procesar_envia_y_no_repite(self):
        programacion._CONSTRUCTORES["reserva_confirmada"] = lambda e: (
            Destinatario.de_fila(e), {"fecha": "x", "hora": "y", "modalidad": "z"}, "prueba")
        try:
            e, _ = self.programar()
            with mock.patch("correo.services.brevo.requests.post", return_value=respuesta()) as post:
                programacion.procesar_pendientes()
                programacion.procesar_pendientes()
            e.refresh_from_db()
            self.assertEqual((e.estado, post.call_count), ("ENVIADO", 1))
        finally:
            programacion._CONSTRUCTORES.pop("reserva_confirmada", None)

    def test_futuro_no_se_procesa(self):
        self.programar(minutos=60)
        r = programacion.procesar_pendientes()
        self.assertEqual(r["tomados"], 0)

    def test_reintenta_hasta_tres_veces(self):
        programacion._CONSTRUCTORES["reserva_confirmada"] = lambda e: (
            Destinatario.de_fila(e), {"fecha": "x", "hora": "y", "modalidad": "z"}, "prueba")
        try:
            e, _ = self.programar()
            with mock.patch("correo.services.brevo.requests.post", return_value=respuesta(503, {})) as post:
                for _ in range(5):
                    EPC.objects.filter(pk=e.pk, estado="PENDIENTE").update(ejecutar_en=timezone.now())
                    programacion.procesar_pendientes()
            e.refresh_from_db()
            self.assertEqual((e.estado, e.intentos, post.call_count), ("ERROR", 3, 3))
        finally:
            programacion._CONSTRUCTORES.pop("reserva_confirmada", None)

    def test_un_envio_tomado_no_lo_toma_otra_ejecucion(self):
        e, _ = self.programar()
        EPC.objects.filter(pk=e.pk).update(estado="PROCESANDO")
        r = programacion.procesar_pendientes()
        self.assertEqual(r["tomados"], 0)

    @override_settings(CORREO_HABILITADO=False)
    def test_apagado_no_procesa(self):
        self.programar()
        self.assertTrue(programacion.procesar_pendientes().get("apagado"))
        self.assertEqual(EPC.objects.get().estado, "PENDIENTE")

    def test_cancelar_no_borra(self):
        self.programar(clave="g1")
        EPC.objects.update(grupo="grupo-x")
        self.assertEqual(programacion.cancelar_pendientes(grupo="grupo-x", motivo="prueba"), 1)
        self.assertEqual(EPC.objects.get().estado, "CANCELADO")


class TareaProgramadaTests(BaseCorreo):
    url = "/api/correo/tareas/procesar-pendientes/"

    @override_settings(ITACA_INTEGRACION_TOKEN="secreto")
    def test_exige_token(self):
        self.assertEqual(self.client.post(self.url).status_code, 403)
        r = self.client.post(self.url, HTTP_X_INTEGRACION_TOKEN="secreto")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["apagado"])

    @override_settings(ITACA_INTEGRACION_TOKEN="")
    def test_sin_token_configurado_queda_cerrado(self):
        self.assertEqual(self.client.post(self.url, HTTP_X_INTEGRACION_TOKEN="").status_code, 403)
