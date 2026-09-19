"""El cuestionario del estudiante: qué entrega y qué se niega a entregar.

Dos reglas que no son de código sino del protocolo firmado, y que aquí se
comprueban:

  · El enlace del estudiante NO abre el panel del colegio. Se reparte en un aula
    entera, así que se asume semipúblico.
  · Al terminar, la pantalla NO le dice al estudiante en qué nivel quedó.
    Enterarse por una pantalla de que uno "salió en rojo", solo y en un salón,
    es justo lo que el protocolo evita: eso se conversa en persona.

    python manage.py test faro.tests_cuestionario
"""
import json

from django.test import TestCase

from core.models import Clinica
from faro import instrumentos as ins
from faro.models import Alerta, Aplicacion, Respuesta


class CuestionarioTests(TestCase):
    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Ítaca", slug="itaca-faro-cuest")
        self.ap = Aplicacion.objects.create(
            clinica=self.clinica, institucion="I.E. San Martín", ciudad="Piura",
            estado=Aplicacion.Estado.EN_CURSO)
        self.url = f"/api/faro/cuestionario/{self.ap.token_estudiante}/"

    def enviar(self, **kw):
        cuerpo = {"nombre": "Rosa Delgado", "grado": "3.° secundaria", "seccion": "B",
                  "respuestas": {i["id"]: 0 for i in ins.ORDEN}}
        cuerpo.update(kw)
        return self.client.post(self.url, data=json.dumps(cuerpo),
                                content_type="application/json")

    def test_entrega_los_treinta_y_ocho_items_con_su_escala(self):
        d = self.client.get(self.url).json()
        self.assertEqual(d["institucion"], "I.E. San Martín")
        self.assertEqual(len(d["items"]), 38)
        primero = d["items"][0]
        self.assertTrue(primero["texto"])
        self.assertEqual(len(primero["escala"]), 5)  # EBIPQ va de 0 a 4

    def test_guarda_el_tamizaje(self):
        r = self.enviar()
        self.assertEqual(r.status_code, 201, r.content)
        resp = Respuesta.objects.get()
        self.assertEqual(resp.nombre, "Rosa Delgado")
        self.assertEqual(resp.grado, "3.° secundaria")
        self.assertEqual(resp.nivel, ins.VERDE)

    def test_no_le_dice_al_estudiante_en_que_nivel_quedo(self):
        # La prueba que sostiene la promesa del asentimiento. Si alguien agrega
        # el nivel a esta respuesta "para que sepa", este test cae.
        r = self.enviar(respuestas={**{i["id"]: 0 for i in ins.ORDEN}, "asq1": 1})
        self.assertEqual(Respuesta.objects.get().nivel, ins.ROJO)
        cuerpo = r.json()
        self.assertEqual(cuerpo, {"ok": True})
        self.assertNotIn("rojo", json.dumps(cuerpo).lower())

    def test_un_rojo_deja_su_alerta(self):
        self.enviar(respuestas={**{i["id"]: 0 for i in ins.ORDEN}, "phq9": 1})
        self.assertEqual(Alerta.objects.count(), 1)

    def test_el_enlace_del_estudiante_no_abre_el_panel_del_colegio(self):
        # Se reparte en un aula entera: si sirviera para las dos cosas, el
        # primer alumno curioso vería el panorama de todo su colegio.
        r = self.client.get(f"/api/faro/{self.ap.token_estudiante}/")
        self.assertEqual(r.status_code, 404)

    def test_el_token_del_colegio_no_abre_el_cuestionario(self):
        r = self.client.get(f"/api/faro/cuestionario/{self.ap.token}/")
        self.assertEqual(r.status_code, 404)

    def test_los_dos_tokens_son_distintos(self):
        self.assertNotEqual(self.ap.token, self.ap.token_estudiante)

    def test_sin_nombre_no_entra(self):
        # Sin nombre no hay a quién llamar si sale rojo, y el tamizaje entero
        # pierde sentido.
        self.assertEqual(self.enviar(nombre="Jo").status_code, 400)
        self.assertEqual(Respuesta.objects.count(), 0)

    def test_sin_respuestas_no_entra(self):
        self.assertEqual(self.enviar(respuestas={}).status_code, 400)
        self.assertEqual(Respuesta.objects.count(), 0)

    def test_lo_que_venga_de_mas_se_descarta(self):
        self.enviar(respuestas={"gad1": 2, "inventado": 9, "phq9": 0})
        guardadas = Respuesta.objects.get().respuestas
        self.assertIn("gad1", guardadas)
        self.assertNotIn("inventado", guardadas)

    def test_cerrado_el_tamizaje_ya_no_se_puede_responder(self):
        self.ap.estado = Aplicacion.Estado.CERRADA
        self.ap.save(update_fields=["estado"])
        r = self.enviar()
        self.assertEqual(r.status_code, 409)
        self.assertEqual(Respuesta.objects.count(), 0)

    def test_un_token_inventado_no_llega_a_ningun_cuestionario(self):
        r = self.client.get("/api/faro/cuestionario/token-inventado/")
        self.assertEqual(r.status_code, 404)
