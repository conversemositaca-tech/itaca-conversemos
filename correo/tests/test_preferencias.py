"""Preferencias: token UUID, bloqueos sumados por persona; destinatario.

    python manage.py test correo.tests.test_preferencias
"""
import uuid

from correo.models import ConsentimientoComunicacion as CC
from correo.services import consentimiento, preferencias
from correo.services.destinatario import Destinatario

from .base import BaseCorreo


class PreferenciasTests(BaseCorreo):
    def test_token_es_uuid4_y_unico(self):
        a = preferencias.de_persona(Destinatario.de_paciente(self.paciente()))
        b = preferencias.de_persona(Destinatario.de_lead(self.lead(nombre="Otra", email="o@t.pe")))
        self.assertEqual(a.token.version, 4)
        self.assertNotEqual(a.token, b.token)

    def test_de_persona_reusa_la_fila(self):
        d = Destinatario.de_paciente(self.paciente())
        self.assertEqual(preferencias.de_persona(d).pk, preferencias.de_persona(d).pk)

    def test_token_invalido_no_revienta(self):
        self.assertIsNone(preferencias.por_token("no-es-uuid"))
        self.assertIsNone(preferencias.por_token(uuid.uuid4()))

    def test_baja_en_el_lead_bloquea_al_paciente(self):
        p = self.paciente()
        lead = self.lead(paciente=p)
        consentimiento.revocar(Destinatario.de_lead(lead), CC.Origen.BAJA_UN_CLIC)
        self.assertTrue(preferencias.bloqueos(Destinatario.de_paciente(p))["marketing"])

    def test_rebote_y_spam(self):
        d = Destinatario.de_paciente(self.paciente())
        preferencias.marcar_rebote_duro(d)
        preferencias.marcar_spam(d)
        b = preferencias.bloqueos(d)
        self.assertTrue(b["rebote_duro"] and b["spam"] and b["marketing"])

    def test_correo_enmascarado(self):
        self.assertEqual(preferencias.correo_enmascarado("mirai@gmail.com"), "m***@gmail.com")
        self.assertEqual(preferencias.correo_enmascarado(""), "")


class DestinatarioTests(BaseCorreo):
    def test_menor_de_14_por_fecha_de_nacimiento(self):
        self.assertTrue(Destinatario.de_paciente(self.menor()).es_menor())
        self.assertFalse(Destinatario.tutor_de(self.menor()).es_menor())
        self.assertFalse(Destinatario.de_paciente(self.paciente()).es_menor())

    def test_correo_del_paciente_cae_al_del_lead(self):
        p = self.paciente(email="")
        self.lead(paciente=p, email="reserva@test.pe")
        self.assertEqual(Destinatario.de_paciente(p).correo(), "reserva@test.pe")

    def test_correo_del_tutor(self):
        self.assertEqual(Destinatario.tutor_de(self.menor()).correo(), "mama@test.pe")

    def test_nombre_de_pila(self):
        self.assertEqual(
            Destinatario.de_paciente(self.paciente(nombre="rosa maría pérez")).nombre(), "Rosa")
