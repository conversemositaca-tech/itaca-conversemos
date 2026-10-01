"""La casilla de comunicaciones en los formularios públicos y el panel interno.

    python manage.py test correo.tests.test_captura
"""
from faro.models import Aplicacion, Autorizacion
from leads.models import Lead
from pacientes.models import Consentimiento
from pacientes.tests_reserva_web import _Base as BaseReserva

from correo.models import ConsentimientoComunicacion as CC
from correo.services.destinatario import Destinatario
from correo.services import consentimiento

from .base import BaseCorreo


class ReservaWebTests(BaseReserva):
    def setUp(self):
        super().setUp()
        self.ficha.horario_semanal = {str(d): [9, 10, 11, 15, 16, 17] for d in range(7)}
        self.ficha.save(update_fields=["horario_semanal"])

    def _un_slot(self):
        r = self.client.get(f"/api/agendamiento/{self.token}/slots/",
                            {"profesional": self.ficha.id, "dias": 14})
        for dia in r.json()["dias"]:
            if dia["slots"]:
                return dia["slots"][0]["inicio"]
        self.fail("sin horario libre")

    def _reservar(self, **extra):
        datos = {"profesional_id": self.ficha.id, "inicio": self._un_slot(),
                 "nombre": "Mateo Pérez", "telefono": "987654321",
                 "servicio": "Consulta inicial - Adultos", "modalidad": "presencial", **extra}
        return self.client.post(f"/api/agendamiento/{self.token}/reservar/", datos,
                                content_type="application/json")

    def test_casilla_marcada_con_correo_registra_en_el_lead(self):
        r = self._reservar(email="mateo@test.pe", acepta_comunicaciones=True)
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.json()["consentimiento_registrado"])
        ev = CC.objects.get()
        self.assertEqual((ev.origen, ev.estado, ev.lead, ev.correo),
                         ("RESERVA_WEB", "OTORGADO", Lead.objects.get(), "mateo@test.pe"))

    def test_sin_casilla_no_hay_consentimiento(self):
        r = self._reservar(email="mateo@test.pe")
        self.assertEqual(r.status_code, 201)
        self.assertFalse(CC.objects.exists())

    def test_casilla_como_texto_false_no_cuenta(self):
        self._reservar(email="mateo@test.pe", acepta_comunicaciones="false")
        self.assertFalse(CC.objects.exists())

    def test_casilla_sin_correo_no_bloquea_la_reserva(self):
        r = self._reservar(acepta_comunicaciones=True)
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.json()["consentimiento_sin_correo"])
        self.assertFalse(CC.objects.exists())
        self.assertEqual(Lead.objects.count(), 1)

    def test_solicitud_ayudenme_a_elegir(self):
        r = self.client.post(f"/api/agendamiento/{self.token}/solicitar/", {
            "sede": "piura", "nombre": "Lucía Ramos", "telefono": "912345678",
            "email": "lucia@test.pe", "acepta_comunicaciones": True,
        }, content_type="application/json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(CC.objects.get().origen, "AYUDA_ELEGIR")


class FaroYConsentimientoInformadoTests(BaseCorreo):
    def test_autorizacion_faro_con_casilla(self):
        ap = Aplicacion.objects.create(clinica=self.clinica, institucion="I.E. Prueba",
                                       estado=Aplicacion.Estado.AUTORIZANDO)
        r = self.client.post(f"/api/faro/autorizacion/{ap.token_apoderado}/", {
            "estudiante": "José Pérez", "grado": "3", "seccion": "B", "apoderado": "Rosa Ramírez",
            "parentesco": "madre", "correo": "rosa@correo.com", "autoriza": True,
            "acepta_comunicaciones": True}, content_type="application/json")
        self.assertEqual(r.status_code, 201)
        ev = CC.objects.get()
        self.assertEqual((ev.origen, ev.autorizacion), ("AUTORIZACION_FARO", Autorizacion.objects.get()))

    def test_autorizacion_faro_sin_casilla(self):
        ap = Aplicacion.objects.create(clinica=self.clinica, institucion="I.E. Prueba",
                                       estado=Aplicacion.Estado.AUTORIZANDO)
        self.client.post(f"/api/faro/autorizacion/{ap.token_apoderado}/", {
            "estudiante": "José Pérez", "apoderado": "Rosa Ramírez", "correo": "rosa@correo.com",
            "autoriza": True}, content_type="application/json")
        self.assertFalse(CC.objects.exists())

    def _firmar(self, paciente, **extra):
        c = Consentimiento.objects.create(clinica=self.clinica, paciente=paciente,
                                          token=Consentimiento.nuevo_token(), texto="x")
        return self.client.post(f"/api/consentimiento/{c.token}/aceptar/",
                                {"nombre": "Rosa Pérez", **extra}, content_type="application/json")

    def test_consentimiento_informado_adulto(self):
        p = self.paciente()
        self.assertEqual(self._firmar(p, acepta_comunicaciones=True).status_code, 200)
        ev = CC.objects.get()
        self.assertEqual((ev.origen, ev.paciente, ev.es_tutor), ("CONSENTIMIENTO_INFORMADO", p, False))

    def test_consentimiento_informado_de_menor_queda_a_nombre_del_tutor(self):
        m = self.menor()
        self._firmar(m, acepta_comunicaciones=True)
        self.assertTrue(CC.objects.get().es_tutor)


class PanelCorreoTests(BaseCorreo):
    def url(self, p, extra=""):
        return f"/api/correo/pacientes/{p.id}/{extra}"

    def test_coordinacion_ve_y_registra_por_whatsapp(self):
        p = self.paciente()
        self.client.force_login(self.coord)
        r = self.client.get(self.url(p))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["paciente"]["marketing"]["estado"], "NO_OTORGADO")
        r = self.client.post(self.url(p, "consentimiento/"), {
            "accion": "otorgar", "origen": "PANEL_WHATSAPP", "confirmo": True},
            content_type="application/json")
        self.assertEqual(r.status_code, 200)
        ev = CC.objects.get()
        self.assertEqual((ev.origen, ev.registrado_por), ("PANEL_WHATSAPP", self.coord))

    def test_sin_confirmacion_explicita_no_registra(self):
        p = self.paciente()
        self.client.force_login(self.admin)
        r = self.client.post(self.url(p, "consentimiento/"), {
            "accion": "otorgar", "origen": "PANEL_PRESENCIAL"}, content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(CC.objects.exists())

    def test_revocar_desde_el_panel(self):
        p = self.paciente()
        consentimiento.otorgar(Destinatario.de_paciente(p), CC.Origen.RESERVA_WEB)
        self.client.force_login(self.coord)
        r = self.client.post(self.url(p, "consentimiento/"), {
            "accion": "revocar", "origen": "PANEL_PRESENCIAL"}, content_type="application/json")
        self.assertEqual(r.json()["marketing"]["estado"], "REVOCADO")

    def test_menor_no_otorga_por_si_mismo_pero_su_tutor_si(self):
        m = self.menor()
        self.client.force_login(self.coord)
        cuerpo = {"accion": "otorgar", "origen": "PANEL_WHATSAPP", "confirmo": True}
        r = self.client.post(self.url(m, "consentimiento/"), cuerpo, content_type="application/json")
        self.assertEqual(r.status_code, 400)
        r = self.client.post(self.url(m, "consentimiento/"), {**cuerpo, "para_tutor": True},
                             content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(CC.objects.get().es_tutor)

    def test_psicologo_y_direccion_clinica_no_tienen_acceso(self):
        p = self.paciente()
        for u in (self.psico, self.analista):
            self.client.force_login(u)
            self.assertEqual(self.client.get(self.url(p)).status_code, 403)
            r = self.client.post(self.url(p, "consentimiento/"), {
                "accion": "otorgar", "origen": "PANEL_WHATSAPP", "confirmo": True},
                content_type="application/json")
            self.assertEqual(r.status_code, 403)
        self.assertFalse(CC.objects.exists())

    def test_otra_clinica_no_ve_al_paciente(self):
        from core.models import Clinica
        from usuarios.models import Usuario
        otra = Clinica.objects.create(nombre="Otra", slug="otra-correo")
        ajeno = Usuario.objects.create_user(email="ajeno@test.pe", password="x", clinica=otra,
                                            rol=Usuario.Rol.ADMIN)
        self.client.force_login(ajeno)
        self.assertEqual(self.client.get(self.url(self.paciente())).status_code, 404)

    def test_psicologo_no_ve_el_correo_del_tutor_en_la_ficha(self):
        from usuarios.models import Profesional
        ficha = Profesional.objects.create(clinica=self.clinica, usuario=self.psico, nombre="Lic. Ana")
        m = self.menor(profesional=ficha)
        self.client.force_login(self.psico)
        r = self.client.get(f"/api/pacientes/{m.id}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["tutor_correo"], "")
