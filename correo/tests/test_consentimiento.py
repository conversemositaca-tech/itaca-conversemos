"""Consentimiento: historial append-only, último evento gana, una identidad por fila.

    python manage.py test correo.tests.test_consentimiento
"""
from django.db import IntegrityError, transaction

from correo import textos
from correo.models import ConsentimientoComunicacion as CC, PreferenciaCorreo
from correo.services import consentimiento, preferencias
from correo.services.destinatario import Destinatario

from .base import BaseCorreo


class ConsentimientoTests(BaseCorreo):
    def test_otorgar_guarda_evidencia_completa(self):
        d = Destinatario.de_paciente(self.paciente())
        ev = consentimiento.otorgar(d, CC.Origen.RESERVA_WEB)
        self.assertEqual(ev.estado, CC.Estado.OTORGADO)
        self.assertEqual(ev.finalidad, CC.Finalidad.MARKETING)
        self.assertEqual(ev.version_texto, "EMAIL-MKT-2026-01")
        self.assertEqual(ev.texto_aceptado, textos.CONSENTIMIENTO_MARKETING_TEXTO)
        self.assertEqual(ev.correo, "rosa@test.pe")
        self.assertTrue(consentimiento.tiene_consentimiento(d, CC.Finalidad.MARKETING))

    def test_sin_correo_no_hay_consentimiento(self):
        d = Destinatario.de_paciente(self.paciente(email=""))
        self.assertIsNone(consentimiento.otorgar(d, CC.Origen.RESERVA_WEB))
        self.assertEqual(CC.objects.count(), 0)

    def test_revocar_crea_evento_nuevo_y_no_edita(self):
        d = Destinatario.de_paciente(self.paciente())
        otorgado = consentimiento.otorgar(d, CC.Origen.RESERVA_WEB)
        revocado = consentimiento.revocar(d, CC.Origen.PREFERENCIAS_WEB)
        self.assertEqual(CC.objects.count(), 2)
        self.assertEqual(revocado.consentimiento_previo, otorgado)
        otorgado.refresh_from_db()
        self.assertEqual(otorgado.estado, CC.Estado.OTORGADO)
        self.assertFalse(consentimiento.tiene_consentimiento(d, CC.Finalidad.MARKETING))

    def test_ultimo_evento_gana(self):
        d = Destinatario.de_paciente(self.paciente())
        consentimiento.otorgar(d, CC.Origen.RESERVA_WEB)
        consentimiento.revocar(d, CC.Origen.BAJA_UN_CLIC)
        consentimiento.otorgar(d, CC.Origen.PREFERENCIAS_WEB)
        self.assertEqual(consentimiento.estado_vigente(d, CC.Finalidad.MARKETING), CC.Estado.OTORGADO)
        self.assertFalse(preferencias.bloqueos(d)["marketing"])

    def test_revocar_dos_veces_no_duplica(self):
        d = Destinatario.de_paciente(self.paciente())
        consentimiento.otorgar(d, CC.Origen.RESERVA_WEB)
        consentimiento.revocar(d, CC.Origen.BAJA_UN_CLIC)
        consentimiento.revocar(d, CC.Origen.BAJA_UN_CLIC)
        self.assertEqual(CC.objects.filter(estado=CC.Estado.REVOCADO).count(), 1)

    def test_un_evento_guardado_no_se_puede_editar(self):
        ev = consentimiento.otorgar(Destinatario.de_paciente(self.paciente()), CC.Origen.RESERVA_WEB)
        ev.estado = CC.Estado.REVOCADO
        with self.assertRaises(ValueError):
            ev.save()

    def test_finalidades_son_independientes(self):
        d = Destinatario.de_paciente(self.paciente())
        consentimiento.otorgar(d, CC.Origen.PANEL_PRESENCIAL, finalidad=CC.Finalidad.ASISTENCIAL)
        self.assertFalse(consentimiento.tiene_consentimiento(d, CC.Finalidad.MARKETING))
        self.assertTrue(consentimiento.tiene_consentimiento(d, CC.Finalidad.ASISTENCIAL))

    def test_registro_por_whatsapp_y_presencial_guarda_usuario(self):
        d = Destinatario.de_paciente(self.paciente())
        a = consentimiento.otorgar(d, CC.Origen.PANEL_WHATSAPP, usuario=self.coord)
        b = consentimiento.otorgar(d, CC.Origen.PANEL_PRESENCIAL, usuario=self.coord)
        self.assertEqual(a.registrado_por, self.coord)
        self.assertEqual(b.origen, CC.Origen.PANEL_PRESENCIAL)

    def test_permiso_dado_en_el_lead_vale_para_el_paciente(self):
        """Quien reservó (lead) y luego es paciente es la misma persona."""
        p = self.paciente()
        lead = self.lead(paciente=p)
        consentimiento.otorgar(Destinatario.de_lead(lead), CC.Origen.RESERVA_WEB)
        self.assertTrue(consentimiento.tiene_consentimiento(
            Destinatario.de_paciente(p), CC.Finalidad.MARKETING))

    def test_permiso_del_tutor_no_es_del_paciente(self):
        m = self.menor()
        consentimiento.otorgar(Destinatario.tutor_de(m), CC.Origen.CONSENTIMIENTO_INFORMADO)
        self.assertTrue(consentimiento.tiene_consentimiento(Destinatario.tutor_de(m), "MARKETING"))
        self.assertFalse(consentimiento.tiene_consentimiento(Destinatario.de_paciente(m), "MARKETING"))

    def test_resumen_para_el_panel(self):
        d = Destinatario.de_paciente(self.paciente())
        self.assertEqual(consentimiento.resumen(d)["estado"], "NO_OTORGADO")
        consentimiento.otorgar(d, CC.Origen.PANEL_WHATSAPP, usuario=self.coord)
        r = consentimiento.resumen(d)
        self.assertEqual((r["estado"], r["origen"]), ("OTORGADO", "PANEL_WHATSAPP"))


class IdentidadExclusivaTests(BaseCorreo):
    def test_fila_sin_identidad_se_rechaza(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            CC.objects.create(clinica=self.clinica, finalidad="MARKETING", estado="OTORGADO",
                              origen="RESERVA_WEB")

    def test_fila_con_dos_identidades_se_rechaza(self):
        p = self.paciente()
        lead = self.lead()
        with self.assertRaises(IntegrityError), transaction.atomic():
            CC.objects.create(clinica=self.clinica, paciente=p, lead=lead,
                              finalidad="MARKETING", estado="OTORGADO", origen="RESERVA_WEB")

    def test_tutor_sin_paciente_se_rechaza(self):
        lead = self.lead()
        with self.assertRaises(IntegrityError), transaction.atomic():
            PreferenciaCorreo.objects.create(clinica=self.clinica, lead=lead, es_tutor=True)

    def test_destinatario_exige_una_persona(self):
        with self.assertRaises(ValueError):
            Destinatario()
        with self.assertRaises(ValueError):
            Destinatario(paciente=self.paciente(), lead=self.lead())
