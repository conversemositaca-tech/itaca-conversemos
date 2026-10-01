"""Panel de correo para leads y para apoderados de Faro.

    python manage.py test correo.tests.test_panel_lead_faro
"""
from faro.models import Aplicacion, Autorizacion

from correo.models import ConsentimientoComunicacion as CC
from correo.services import consentimiento
from correo.services.destinatario import Destinatario

from .base import BaseCorreo

CUERPO = {"accion": "otorgar", "origen": "PANEL_WHATSAPP", "confirmo": True}


class PanelLeadTests(BaseCorreo):
    def url(self, lead, extra=""):
        return f"/api/correo/leads/{lead.id}/{extra}"

    def test_coordinacion_ve_y_registra(self):
        lead = self.lead()
        self.client.force_login(self.coord)
        r = self.client.get(self.url(lead))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["lead"]["marketing"]["estado"], "NO_OTORGADO")
        r = self.client.post(self.url(lead, "consentimiento/"), CUERPO, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        ev = CC.objects.get()
        self.assertEqual((ev.lead, ev.origen, ev.registrado_por), (lead, "PANEL_WHATSAPP", self.coord))

    def test_revocar_lo_que_dio_en_la_web(self):
        lead = self.lead()
        consentimiento.otorgar(Destinatario.de_lead(lead), CC.Origen.RESERVA_WEB)
        self.client.force_login(self.admin)
        r = self.client.post(self.url(lead, "consentimiento/"),
                             {"accion": "revocar", "origen": "PANEL_PRESENCIAL"},
                             content_type="application/json")
        self.assertEqual(r.json()["marketing"]["estado"], "REVOCADO")

    def test_sin_confirmacion_no_registra(self):
        lead = self.lead()
        self.client.force_login(self.coord)
        r = self.client.post(self.url(lead, "consentimiento/"),
                             {**CUERPO, "confirmo": False}, content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_lead_convertido_comparte_estado_con_su_paciente(self):
        p = self.paciente()
        lead = self.lead(paciente=p)
        consentimiento.otorgar(Destinatario.de_paciente(p), CC.Origen.PANEL_PRESENCIAL)
        self.client.force_login(self.coord)
        d = self.client.get(self.url(lead)).json()
        self.assertEqual((d["lead"]["marketing"]["estado"], d["paciente_id"]), ("OTORGADO", p.id))

    def test_psicologo_y_direccion_clinica_sin_acceso(self):
        lead = self.lead()
        for u in (self.psico, self.analista):
            self.client.force_login(u)
            self.assertEqual(self.client.get(self.url(lead)).status_code, 403)
            self.assertEqual(self.client.post(self.url(lead, "consentimiento/"), CUERPO,
                                              content_type="application/json").status_code, 403)

    def test_coordinacion_de_otra_sede_no_lo_ve(self):
        lead = self.lead()
        lead.sede = "lima"
        lead.save(update_fields=["sede"])
        self.coord.sede = "piura"
        self.coord.save(update_fields=["sede"])
        self.client.force_login(self.coord)
        self.assertEqual(self.client.get(self.url(lead)).status_code, 404)


class PanelFaroTests(BaseCorreo):
    def setUp(self):
        super().setUp()
        self.ap = Aplicacion.objects.create(clinica=self.clinica, institucion="I.E. Prueba")
        self.aut = Autorizacion.objects.create(
            clinica=self.clinica, aplicacion=self.ap, estudiante="José Pérez",
            apoderado="Rosa Ramírez", correo="rosa@correo.com", autoriza=True)
        consentimiento.otorgar(Destinatario.de_autorizacion(self.aut), CC.Origen.AUTORIZACION_FARO)

    def test_gerencia_ve_el_estado_con_correo_enmascarado(self):
        self.client.force_login(self.admin)
        r = self.client.get(f"/api/correo/faro/aplicaciones/{self.ap.id}/")
        self.assertEqual(r.status_code, 200)
        fila = r.json()["apoderados"][0]
        self.assertEqual((fila["correo"], fila["marketing"]["estado"]), ("r***@correo.com", "OTORGADO"))

    def test_gerencia_revoca(self):
        self.client.force_login(self.admin)
        r = self.client.post(f"/api/correo/faro/autorizaciones/{self.aut.id}/revocar/",
                             {"origen": "PANEL_WHATSAPP"}, content_type="application/json")
        self.assertEqual(r.json()["marketing"]["estado"], "REVOCADO")

    def test_nadie_mas_entra(self):
        for u in (self.coord, self.psico, self.analista):
            self.client.force_login(u)
            self.assertEqual(self.client.get(f"/api/correo/faro/aplicaciones/{self.ap.id}/").status_code, 403)
            self.assertEqual(self.client.post(
                f"/api/correo/faro/autorizaciones/{self.aut.id}/revocar/",
                {"origen": "PANEL_WHATSAPP"}, content_type="application/json").status_code, 403)
