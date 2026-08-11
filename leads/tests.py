"""Pruebas de la lectura automática de los mensajes de WhatsApp.

Son los casos reales que trajo el equipo (corrección #3): la persona pregunta
por terapia de pareja y costos, o pide cita en "Miraflores, Lima".

    python manage.py test leads
"""
from django.test import SimpleTestCase

from leads.models import Lead
from leads.whatsapp_auto import analizar


class AnalizarMensajeTests(SimpleTestCase):
    """`analizar` no toca la base de datos: es solo lectura del texto."""

    def test_pregunta_por_pareja_y_costos(self):
        a = analizar("Hola, hacen terapia de pareja? cuanto cuesta la sesion?")
        self.assertEqual(a["tipo_servicio"], Lead.TipoServicio.PAREJA)
        self.assertTrue(a["es_pareja"])
        self.assertIn("servicios", a["intenciones"])
        self.assertIn("precios", a["intenciones"])

    def test_pide_cita_en_miraflores(self):
        a = analizar("Buenas, quiero reservar una cita en Miraflores, Lima")
        self.assertEqual(a["ubicacion"], "Miraflores")
        self.assertEqual(a["sede"], Lead.Sede.LIMA)
        self.assertTrue(a["pide_cita"])

    def test_distrito_mas_especifico_gana(self):
        # "San Juan de Miraflores" no debe leerse como "Miraflores" ni "Lima".
        a = analizar("Vivo en San Juan de Miraflores")
        self.assertEqual(a["ubicacion"], "San Juan de Miraflores")
        self.assertEqual(a["sede"], Lead.Sede.LIMA)

    def test_reconoce_piura_y_sin_acentos(self):
        a = analizar("Estoy en Castilla, atienden ninos?")
        self.assertEqual(a["sede"], Lead.Sede.PIURA)
        self.assertEqual(a["tipo_servicio"], Lead.TipoServicio.NINOS)

    def test_adolescente_no_se_confunde_con_nino(self):
        a = analizar("Es para mi hija adolescente")
        self.assertEqual(a["tipo_servicio"], Lead.TipoServicio.ADOLESCENTES)

    def test_modalidad_online(self):
        a = analizar("Las sesiones son online? que precio tienen")
        self.assertEqual(a["modalidad"], "online")
        self.assertIn("precios", a["intenciones"])

    def test_saludo_suelto_no_dispara_respuesta(self):
        a = analizar("Hola buenas tardes")
        self.assertEqual(a["intenciones"], [])
        self.assertFalse(a["pide_cita"])
        self.assertEqual(a["tipo_servicio"], "")

    def test_mensaje_vacio(self):
        a = analizar("")
        self.assertEqual(a["intenciones"], [])
        self.assertEqual(a["ubicacion"], "")
