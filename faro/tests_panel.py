"""El panel del colegio entra por token, y qué puede y qué no puede mostrar.

Faro aplica un tamizaje de salud mental a menores dentro de un colegio. Lo que
la institución recibe está limitado por escrito en el consentimiento que firman
los apoderados y en el convenio, y este endpoint es donde esa promesa se cumple
o se rompe.

Ese límite se movió en setiembre de 2026 por decisión de la dirección clínica.
Antes el colegio veía SOLO agregados y había un test que fallaba si aparecía un
nombre. Ahora ve la lista nominal con el nivel y los puntajes de cada
estudiante, y la frontera pasó a estar un paso más allá: las RESPUESTAS una por
una no salen. El colegio lee "ASQ positivo"; nunca "¿has pensado en suicidarte?
→ sí".

    python manage.py test faro.tests_panel
"""
import datetime as dt
import json

from django.test import TestCase

from core.models import Clinica
from faro import instrumentos as ins
from faro.models import Aplicacion
from faro.registro import registrar


class PanelFaroTests(TestCase):
    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Ítaca Conversemos", slug="itaca-faro-panel")
        self.ap = Aplicacion.objects.create(
            clinica=self.clinica, institucion="I.E. San Martín", ciudad="Piura",
            contacto="Ana Chávez", matriculados=400, autorizados=25,
            estado=Aplicacion.Estado.CERRADA,
            fecha_aplicacion=dt.date(2026, 9, 10), fecha_informe=dt.date(2026, 9, 25))
        # Los evaluados se CUENTAN de las respuestas reales. Antes este test los
        # escribía a mano y pasaba en verde mientras en producción el panel
        # anunciaba "todavía no hay resultados" con el colegio entero contestado.
        self.responden(23)

    def responden(self, cuantos):
        vacias = {i["id"]: 0 for i in ins.ORDEN}
        for n in range(cuantos):
            registrar(self.ap, nombre=f"Estudiante {n}", grado="3.° secundaria",
                      respuestas=vacias)

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
        self.assertEqual(d["evaluados"], 23)
        self.assertEqual(d["autorizados"], 25)
        self.assertEqual(d["estado_label"], "Informe entregado")
        self.assertTrue(d["hay_datos"])

    def test_la_participacion_se_mide_sobre_los_autorizados(self):
        # Sobre matriculados (400) daría 6% y castigaría al colegio por una
        # decisión de las familias. Sobre autorizados (25) da 92%, que es lo
        # que la institución sí puede mover.
        self.assertEqual(self.panel().json()["participacion"], 92)

    def test_sin_autorizados_la_participacion_no_es_cero_sino_nada(self):
        # Decir 0% da a entender que fue mal. Todavía no empezó.
        self.ap.autorizados = 0
        self.ap.save(update_fields=["autorizados"])
        self.ap.respuestas.all().delete()
        self.assertIsNone(self.panel().json()["participacion"])

    def test_sin_aplicar_avisa_que_no_hay_datos(self):
        self.ap.respuestas.all().delete()
        d = self.panel().json()
        self.assertFalse(d["hay_datos"])
        self.assertEqual(d["grados"], [])

    def test_en_cuanto_alguien_contesta_el_panel_deja_de_decir_que_no_hay_nada(self):
        # El error que se vio en producción: el panel interno mostraba el caso
        # y el del colegio seguía anunciando que el tamizaje no se había
        # aplicado. Dos verdades sobre lo mismo, y el cliente veía la falsa.
        self.ap.respuestas.all().delete()
        self.assertFalse(self.panel().json()["hay_datos"])
        self.responden(1)
        d = self.panel().json()
        self.assertTrue(d["hay_datos"])
        self.assertEqual(d["evaluados"], 1)

    def test_el_colegio_ve_la_lista_nominal(self):
        # Esto estuvo PROHIBIDO hasta setiembre de 2026 y había un test que lo
        # impedía. Se abrió por decisión de la dirección clínica: el colegio es
        # quien acompaña el día a día y no podía actuar sobre un porcentaje.
        d = self.panel().json()
        self.assertEqual(len(d["estudiantes"]), 23)
        uno = d["estudiantes"][0]
        for clave in ("nombre", "grado", "seccion", "nivel",
                      "phq_total", "gad_total", "asq_positivo", "ebipq_rol", "ciber_rol"):
            self.assertIn(clave, uno, f"Al colegio le falta {clave} para poder actuar")

    def test_el_colegio_no_ve_las_respuestas_una_por_una(self):
        """La frontera que reemplazó a la anterior, y la que hay que defender.

        Se revisa el cuerpo ENTERO y no solo las claves de primer nivel: si algo
        se filtrara, se filtraría dentro de la lista de estudiantes. Que el
        colegio sepa que un chico dio positivo en el ASQ le permite convocarlo;
        que lea sus respuestas literales sobre suicidio no agrega nada que
        pueda usar, y sí convierte una sala de profesores en el peor lugar
        donde puede estar esa frase.
        """
        cuerpo = json.dumps(self.panel().json(), ensure_ascii=False)
        for item in ("asq1", "asq3", "asq4", "phq9", "gad7", "ebipq1"):
            self.assertNotIn(item, cuerpo, f"El panel del colegio expone el ítem {item}")
        self.assertNotIn("respuestas", cuerpo,
                         "El panel del colegio expone las respuestas crudas")

    def test_los_agregados_van_por_grado_y_por_seccion(self):
        # Un director decide por grado y un tutor por sección: las dos miradas
        # tienen que venir armadas, no sumadas a mano por quien lee.
        self.ap.respuestas.all().delete()
        vacias = {i["id"]: 0 for i in ins.ORDEN}
        for sec, cuantos in (("A", 2), ("B", 3)):
            for n in range(cuantos):
                registrar(self.ap, nombre=f"Estudiante {sec}{n}", grado="3.°",
                          seccion=sec, respuestas=vacias)

        grados = self.panel().json()["grados"]
        self.assertEqual(len(grados), 1)
        self.assertEqual(grados[0]["grado"], "3.°")
        self.assertEqual(grados[0]["evaluados"], 5)
        self.assertEqual([s["seccion"] for s in grados[0]["secciones"]], ["A", "B"])
        self.assertEqual([s["evaluados"] for s in grados[0]["secciones"]], [2, 3])

    def test_un_token_inventado_no_llega_a_ningun_panel(self):
        self.assertEqual(self.panel("token-inventado").status_code, 404)
