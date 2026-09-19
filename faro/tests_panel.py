"""El panel del colegio entra por token y nunca muestra un estudiante.

Faro aplica un tamizaje de salud mental a menores dentro de un colegio. Lo que la
institución recibe está limitado por escrito en dos documentos que firma: el
consentimiento de los apoderados y el convenio. Los dos dicen lo mismo —el
colegio ve agregados, nunca nombres junto a resultados— y este endpoint es donde
esa promesa se cumple o se rompe.

    python manage.py test faro.tests_panel
"""
import datetime as dt

from django.test import TestCase

from core.models import Clinica
from faro.models import Aplicacion


class PanelFaroTests(TestCase):
    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Ítaca Conversemos", slug="itaca-faro-panel")
        self.ap = Aplicacion.objects.create(
            clinica=self.clinica, institucion="I.E. San Martín", ciudad="Piura",
            contacto="Ana Chávez", matriculados=400, autorizados=350, evaluados=322,
            estado=Aplicacion.Estado.CERRADA,
            fecha_aplicacion=dt.date(2026, 9, 10), fecha_informe=dt.date(2026, 9, 25))

    def panel(self, token=None):
        return self.client.get(f"/api/faro/{token or self.ap.token}/")

    def test_el_token_se_genera_solo_y_no_es_adivinable(self):
        # Con el nombre del colegio no se llega al panel de nadie.
        self.assertTrue(self.ap.token)
        self.assertGreaterEqual(len(self.ap.token), 24)
        otra = Aplicacion.objects.create(clinica=self.clinica, institucion="I.E. San Martín")
        self.assertNotEqual(self.ap.token, otra.token)

    def test_devuelve_el_panorama_de_la_institucion(self):
        d = self.panel().json()
        self.assertEqual(d["institucion"], "I.E. San Martín")
        self.assertEqual(d["ciudad"], "Piura")
        self.assertEqual(d["evaluados"], 322)
        self.assertEqual(d["autorizados"], 350)
        self.assertEqual(d["estado_label"], "Informe entregado")
        self.assertTrue(d["hay_datos"])

    def test_la_participacion_se_mide_sobre_los_autorizados(self):
        # Sobre matriculados (400) daría 81% y castigaría al colegio por una
        # decisión de las familias. Sobre autorizados (350) da 92%, que es lo
        # que la institución sí puede mover.
        self.assertEqual(self.panel().json()["participacion"], 92)

    def test_sin_autorizados_la_participacion_no_es_cero_sino_nada(self):
        # Decir 0% da a entender que fue mal. Todavía no empezó.
        self.ap.autorizados = 0
        self.ap.evaluados = 0
        self.ap.save(update_fields=["autorizados", "evaluados"])
        self.assertIsNone(self.panel().json()["participacion"])

    def test_sin_aplicar_avisa_que_no_hay_datos(self):
        self.ap.evaluados = 0
        self.ap.save(update_fields=["evaluados"])
        d = self.panel().json()
        self.assertFalse(d["hay_datos"])
        self.assertEqual(d["grados"], [])

    def test_no_se_filtra_ningun_estudiante(self):
        # La prueba que importa: en TODO el cuerpo no puede aparecer nada que
        # identifique a un menor. Hoy no existe el modelo de respuestas; este
        # test queda para que el día que exista, agregarlo aquí rompa a
        # propósito si alguien expone un nombre.
        d = self.panel().json()
        prohibidos = {"estudiantes", "alumnos", "respuestas", "casos", "nombres",
                      "dni", "riesgo", "alertas"}
        self.assertFalse(prohibidos & set(d.keys()),
                         f"El panel expone claves que no debería: {prohibidos & set(d.keys())}")

    def test_un_token_inventado_no_llega_a_ningun_panel(self):
        self.assertEqual(self.panel("token-inventado").status_code, 404)
