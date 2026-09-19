"""Un tamizaje rojo nunca se pierde, aunque el aviso falle.

El protocolo que firma el colegio promete que una señal de riesgo se atiende el
mismo día. Esa promesa se sostiene en que la detección quede registrada ANTES de
intentar avisar: si el orden se invirtiera, un error de red o una línea de
WhatsApp mal configurada borrarían de un plumazo al estudiante que había que
llamar, y nadie se enteraría.

    python manage.py test faro.tests_registro
"""
from unittest import mock

from django.test import TestCase

from core.models import Clinica
from faro import instrumentos as ins
from faro.models import Alerta, Aplicacion, Respuesta
from faro.registro import registrar


def contesta(**kw):
    d = {i["id"]: 0 for i in ins.ORDEN}
    d.update(kw)
    return d


class RegistroTests(TestCase):
    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Ítaca", slug="itaca-faro-registro")
        self.ap = Aplicacion.objects.create(
            clinica=self.clinica, institucion="I.E. San Martín", ciudad="Piura")

    def test_guarda_el_tamizaje_con_su_puntaje_ya_calculado(self):
        r, a = registrar(self.ap, nombre="Rosa Delgado", grado="3.° secundaria",
                         seccion="B", respuestas=contesta(gad1=3, gad2=3, gad3=3, gad4=1))
        self.assertEqual(r.nombre, "Rosa Delgado")
        self.assertEqual(r.gad_total, 10)
        self.assertEqual(r.nivel, ins.AMBAR)
        self.assertTrue(r.completa)
        self.assertIsNone(a)

    def test_un_rojo_crea_su_alerta(self):
        r, a = registrar(self.ap, nombre="Luis Paredes", respuestas=contesta(asq3=1))
        self.assertEqual(r.nivel, ins.ROJO)
        self.assertIsNotNone(a)
        self.assertEqual(a.respuesta, r)
        self.assertTrue(any("ASQ positivo" in m for m in a.motivos))

    def test_el_verde_no_genera_alerta(self):
        r, a = registrar(self.ap, nombre="Ana Ríos", respuestas=contesta())
        self.assertEqual(r.nivel, ins.VERDE)
        self.assertIsNone(a)
        self.assertEqual(Alerta.objects.count(), 0)

    def test_sin_numero_configurado_la_alerta_igual_queda(self):
        # Apagado por defecto: ninguna línea empieza a mandar mensajes sola.
        # Pero el caso tiene que aparecer en el panel del psicólogo igual.
        _, a = registrar(self.ap, nombre="Luis Paredes", respuestas=contesta(phq9=2))
        self.assertEqual(a.aviso, Alerta.Aviso.SIN_CANAL)
        self.assertEqual(Alerta.objects.count(), 1)

    def test_si_el_aviso_falla_la_alerta_sobrevive(self):
        # Es el test que más importa de este archivo. Si alguien mueve el envío
        # antes de guardar, o lo mete dentro de la transacción, este cae.
        self.ap.avisar_whatsapp = "987654321"
        self.ap.save(update_fields=["avisar_whatsapp"])
        with mock.patch("mensajes.evolution.enviar_texto",
                        side_effect=RuntimeError("se cayó la red")):
            r, a = registrar(self.ap, nombre="Luis Paredes", respuestas=contesta(asq1=1))
        self.assertEqual(Respuesta.objects.count(), 1)
        self.assertEqual(Alerta.objects.count(), 1)
        self.assertEqual(a.aviso, Alerta.Aviso.FALLIDO)
        self.assertIn("se cayó la red", a.aviso_detalle)
        self.assertEqual(r.nivel, ins.ROJO)

    def test_si_evolution_rechaza_queda_como_fallido_y_no_como_enviado(self):
        self.ap.avisar_whatsapp = "987654321"
        self.ap.save(update_fields=["avisar_whatsapp"])
        with mock.patch("mensajes.evolution.enviar_texto",
                        return_value={"estado": "fallido", "detalle": "sin instancia"}):
            _, a = registrar(self.ap, nombre="Luis Paredes", respuestas=contesta(asq1=1))
        self.assertEqual(a.aviso, Alerta.Aviso.FALLIDO)
        self.assertIsNone(a.avisado_en)

    def test_un_aviso_bueno_se_marca_con_su_hora(self):
        self.ap.avisar_whatsapp = "987654321"
        self.ap.save(update_fields=["avisar_whatsapp"])
        with mock.patch("mensajes.evolution.enviar_texto",
                        return_value={"estado": "enviado", "detalle": "ok"}) as env:
            _, a = registrar(self.ap, nombre="Luis Paredes", grado="4.° secundaria",
                             respuestas=contesta(asq1=1))
        self.assertEqual(a.aviso, Alerta.Aviso.ENVIADO)
        self.assertIsNotNone(a.avisado_en)
        texto = env.call_args[0][2]
        self.assertIn("I.E. San Martín", texto)
        self.assertIn("Luis Paredes", texto)
        self.assertIn("4.° secundaria", texto)

    def test_el_aviso_no_lleva_las_respuestas_del_estudiante(self):
        # Por WhatsApp va lo justo para actuar: quién y por qué. El detalle
        # clínico vive en el panel, no en el chat de la coordinadora.
        self.ap.avisar_whatsapp = "987654321"
        self.ap.save(update_fields=["avisar_whatsapp"])
        with mock.patch("mensajes.evolution.enviar_texto",
                        return_value={"estado": "enviado"}) as env:
            registrar(self.ap, nombre="Luis Paredes", respuestas=contesta(asq1=1, gad1=3))
        texto = env.call_args[0][2]
        self.assertNotIn("gad", texto.lower())
        self.assertNotIn("¿has deseado estar muerto?", texto.lower())

    def test_un_cuestionario_a_medias_queda_marcado(self):
        r, _ = registrar(self.ap, nombre="Ana Ríos", respuestas={"gad1": 2})
        self.assertFalse(r.completa)
        self.assertEqual(r.gad_total, 2)

    def test_las_respuestas_crudas_se_guardan_enteras(self):
        # Sin ellas, corregir un punto de corte obligaría a volver a aplicar el
        # tamizaje a todo el colegio.
        r, _ = registrar(self.ap, nombre="Ana Ríos", respuestas=contesta(ebipq4=3))
        self.assertEqual(r.respuestas["ebipq4"], 3)
        self.assertEqual(len(r.respuestas), len(ins.ORDEN))
