"""El sitio público no debe filtrar entre clínicas ni publicar fichas retiradas."""
from django.test import TestCase, override_settings

from core.models import Clinica
from usuarios.models import Profesional


class SitioPublicoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = Clinica.objects.create(nombre="Ítaca Conversemos", ciudad="Piura",
                                       slug="itaca", token_captacion="tok-a")
        cls.b = Clinica.objects.create(nombre="Otra clínica", ciudad="Lima",
                                       slug="otra", token_captacion="tok-b")
        cls.visible = Profesional.objects.create(
            clinica=cls.a, nombre="Lic. Gabriela Rentería", colegiatura="45307",
            frase="Atrevernos a pedir ayuda es un acto de puro valor.", sede="lima")
        Profesional.objects.create(clinica=cls.a, nombre="Psicóloga retirada",
                                   frase="ya no atiende", activo=False)
        Profesional.objects.create(clinica=cls.a, nombre="Ficha sin nada que mostrar")
        cls.ajena = Profesional.objects.create(clinica=cls.b, nombre="De otra clínica",
                                               frase="no debe salir")

    @override_settings(SITIO_CLINICA_TOKEN="tok-a")
    def test_publica_solo_el_equipo_activo_de_su_clinica(self):
        d = self.client.get("/api/sitio/").json()
        self.assertEqual(d["clinica"], "Ítaca Conversemos")
        self.assertEqual(d["token_agenda"], "tok-a")
        nombres = [p["nombre"] for p in d["equipo"]]
        self.assertEqual(nombres, ["Lic. Gabriela Rentería"])
        p = d["equipo"][0]
        self.assertEqual(p["colegiatura"], "45307")
        self.assertFalse(p["agendable"])          # sin usuario ni horario

    @override_settings(SITIO_CLINICA_TOKEN="tok-b")
    def test_el_token_manda_que_clinica_se_publica(self):
        d = self.client.get("/api/sitio/").json()
        self.assertEqual(d["clinica"], "Otra clínica")
        self.assertEqual([p["nombre"] for p in d["equipo"]], ["De otra clínica"])

    @override_settings(SITIO_CLINICA_TOKEN="")
    def test_con_varias_clinicas_y_sin_token_no_adivina(self):
        self.assertEqual(self.client.get("/api/sitio/").status_code, 404)

    @override_settings(SITIO_CLINICA_TOKEN="tok-a")
    def test_no_sirve_la_foto_de_una_ficha_de_otra_clinica(self):
        self.assertEqual(self.client.get(f"/api/sitio/foto/{self.ajena.id}/").status_code, 404)

    @override_settings(SITIO_CLINICA_TOKEN="tok-a")
    def test_sin_foto_cargada_responde_404_y_no_revienta(self):
        self.assertEqual(self.client.get(f"/api/sitio/foto/{self.visible.id}/").status_code, 404)

    @override_settings(SITIO_CLINICA_TOKEN="tok-a")
    def test_es_publico_sin_sesion(self):
        self.assertEqual(self.client.get("/api/sitio/").status_code, 200)
