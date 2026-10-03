"""Webhook de Brevo, centro de preferencias y baja de un clic.

    python manage.py test correo.tests.test_webhook_preferencias
"""
from django.test import override_settings

from correo.models import (
    ConsentimientoComunicacion as CC, CorreoEnviado, EventoCorreoProveedor as ECP, PlantillaCorreo,
)
from correo.services import consentimiento, preferencias
from correo.services.destinatario import Destinatario
from correo.services.elegibilidad import Codigo, evaluar_elegibilidad_correo

from .base import BaseCorreo

TOKEN = "token-webhook-prueba"
URL = "/api/correo/webhooks/brevo/"
MID = "<202610010001.1234@smtp-relay.mailin.fr>"


@override_settings(BREVO_WEBHOOK_TOKEN=TOKEN)
class WebhookTests(BaseCorreo):
    def setUp(self):
        super().setUp()
        self.p = self.paciente()
        self.d = Destinatario.de_paciente(self.p)
        consentimiento.otorgar(self.d, CC.Origen.RESERVA_WEB)
        self.fila = CorreoEnviado.objects.create(
            **self.d.identidad(), plantilla=PlantillaCorreo.objects.get(clave="dp02_dia_1"),
            categoria="MARKETING", destinatario_correo="rosa@test.pe", estado="ENVIADO",
            brevo_message_id=MID)

    def avisar(self, evento, token=TOKEN, **extra):
        cuerpo = {"event": evento, "email": "rosa@test.pe", "message-id": MID,
                  "ts_event": 1790000000, "tags": [f"correo:{self.fila.uuid}"], **extra}
        return self.client.post(URL, cuerpo, content_type="application/json",
                                HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_token_obligatorio(self):
        self.assertEqual(self.avisar("delivered", token="otro").status_code, 401)
        r = self.client.post(URL, {"event": "delivered"}, content_type="application/json")
        self.assertEqual(r.status_code, 401)
        self.assertFalse(ECP.objects.exists())

    @override_settings(BREVO_WEBHOOK_TOKEN="")
    def test_sin_token_configurado_queda_cerrado(self):
        self.assertEqual(self.avisar("delivered", token="").status_code, 401)

    def test_entregado(self):
        self.assertEqual(self.avisar("delivered").status_code, 200)
        self.fila.refresh_from_db()
        self.assertEqual(self.fila.estado, "ENTREGADO")
        self.assertIsNotNone(self.fila.entregado_en)

    def test_rebote_duro_bloquea_a_la_persona(self):
        self.avisar("hard_bounce")
        self.fila.refresh_from_db()
        self.assertEqual(self.fila.estado, "REBOTE_DURO")
        self.assertTrue(preferencias.bloqueos(self.d)["rebote_duro"])

    def test_rebote_suave_no_bloquea(self):
        self.avisar("soft_bounce")
        self.assertFalse(preferencias.bloqueos(self.d)["rebote_duro"])

    def test_bloqueado_no_es_rebote_duro(self):
        self.avisar("blocked")
        self.fila.refresh_from_db()
        self.assertEqual(self.fila.estado, "BLOQUEADO")
        self.assertFalse(preferencias.bloqueos(self.d)["rebote_duro"])

    def test_baja_revoca_marketing(self):
        self.avisar("unsubscribed")
        ev = CC.objects.order_by("-id").first()
        self.assertEqual((ev.estado, ev.origen), ("REVOCADO", "WEBHOOK_PROVEEDOR"))
        self.assertTrue(preferencias.bloqueos(self.d)["marketing"])

    def test_spam_marca_y_revoca(self):
        self.avisar("spam")
        self.assertTrue(preferencias.bloqueos(self.d)["spam"])
        self.assertEqual(consentimiento.estado_vigente(self.d, "MARKETING"), "REVOCADO")

    def test_clic_guarda_url_sin_cambiar_estado(self):
        self.avisar("click", link="https://conversemos.itaca.com.pe/")
        ev = ECP.objects.get()
        self.assertEqual((ev.tipo, ev.url), ("CLIC", "https://conversemos.itaca.com.pe/"))
        self.fila.refresh_from_db()
        self.assertEqual(self.fila.estado, "ENVIADO")

    def test_aviso_repetido_se_procesa_una_vez(self):
        self.avisar("delivered")
        r = self.avisar("delivered")
        self.assertEqual(r.json().get("repetido"), 1)
        self.assertEqual(ECP.objects.count(), 1)

    def test_correlaciona_por_etiqueta_si_no_hay_message_id(self):
        self.fila.brevo_message_id = ""
        self.fila.save()
        self.avisar("delivered", **{"message-id": ""})
        self.fila.refresh_from_db()
        self.assertEqual(self.fila.estado, "ENTREGADO")

    def test_no_correlaciona_por_correo(self):
        self.client.post(URL, {"event": "hard_bounce", "email": "rosa@test.pe", "ts_event": 1},
                         content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
        self.assertFalse(preferencias.bloqueos(self.d)["rebote_duro"])

    def test_entregado_tardio_no_pisa_rebote_duro_ni_baja(self):
        self.avisar("unsubscribed")
        self.avisar("soft_bounce", ts_event=1790000999)
        self.fila.refresh_from_db()
        self.assertEqual(self.fila.estado, "DADO_DE_BAJA")

    def test_no_guarda_payload(self):
        campos = {f.name for f in ECP._meta.get_fields()}
        self.assertFalse({"payload", "cuerpo", "datos", "email"} & campos)


class PreferenciasYBajaTests(BaseCorreo):
    def setUp(self):
        super().setUp()
        self.d = Destinatario.de_paciente(self.paciente())
        consentimiento.otorgar(self.d, CC.Origen.RESERVA_WEB)
        self.token = preferencias.de_persona(self.d).token

    def test_pagina_muestra_solo_correo_enmascarado(self):
        r = self.client.get(f"/api/correo/preferencias/{self.token}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"correo": "r***@test.pe", "marketing": True,
                                    "texto": r.json()["texto"]})
        self.assertNotIn("Rosa", r.content.decode())

    def test_desmarcar_y_volver_a_marcar_crea_historial(self):
        url = f"/api/correo/preferencias/{self.token}/"
        r = self.client.post(url, {"marketing": False}, content_type="application/json")
        self.assertFalse(r.json()["marketing"])
        r = self.client.post(url, {"marketing": True}, content_type="application/json")
        self.assertTrue(r.json()["marketing"])
        self.assertEqual(list(CC.objects.order_by("id").values_list("origen", flat=True)),
                         ["RESERVA_WEB", "PREFERENCIAS_WEB", "PREFERENCIAS_WEB"])

    def test_token_invalido(self):
        self.assertEqual(self.client.get("/api/correo/preferencias/no-es-uuid/").status_code, 404)
        self.assertEqual(self.client.post("/api/correo/baja/00000000-0000-4000-8000-000000000000/").status_code, 404)

    def test_baja_un_clic_inmediata_e_idempotente(self):
        url = f"/api/correo/baja/{self.token}/"
        self.assertEqual(self.client.post(url).status_code, 200)
        self.assertEqual(self.client.post(url).status_code, 200)
        self.assertEqual(CC.objects.filter(estado="REVOCADO").count(), 1)
        self.assertEqual(CC.objects.get(estado="REVOCADO").origen, "BAJA_UN_CLIC")
        self.assertEqual(evaluar_elegibilidad_correo(self.d, "MARKETING").codigo, Codigo.BAJA)

    def test_baja_no_afecta_correos_de_servicio(self):
        self.client.post(f"/api/correo/baja/{self.token}/")
        self.assertEqual(evaluar_elegibilidad_correo(self.d, "SERVICE").codigo, Codigo.OK)

    def test_baja_sin_consentimiento_previo_igual_bloquea(self):
        d = Destinatario.de_lead(self.lead(nombre="Otro", email="otro@test.pe"))
        token = preferencias.de_persona(d).token
        self.assertEqual(self.client.post(f"/api/correo/baja/{token}/").status_code, 200)
        self.assertTrue(preferencias.bloqueos(d)["marketing"])

    def test_reactivar_levanta_la_baja(self):
        self.client.post(f"/api/correo/baja/{self.token}/")
        self.client.post(f"/api/correo/preferencias/{self.token}/", {"marketing": True},
                         content_type="application/json")
        self.assertEqual(evaluar_elegibilidad_correo(self.d, "MARKETING").codigo, Codigo.OK)
