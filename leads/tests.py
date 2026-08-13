"""Pruebas de la lectura automática de los mensajes de WhatsApp.

Son los casos reales que trajo el equipo (corrección #3): la persona pregunta
por terapia de pareja y costos, o pide cita en "Miraflores, Lima".

    python manage.py test leads
"""
from datetime import timedelta

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from core.models import Clinica
from leads.models import Anuncio, Lead
from leads.reporte import generar_reporte_pauta
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


class ReportePautaTests(TestCase):
    """De qué anuncio vino cada consulta.

    Caso real que reportó el equipo de marketing: "del 1 al 9, si son cinco citas
    agendadas, debería aparecer de qué video llegaron, pero el sistema solo me
    arroja una, en ambas sedes".

    Pasaba por dos motivos que se sumaban: el equipo registra cada etapa del
    embudo como una fila NUEVA, y al agrupar por persona ganaba la fila más
    avanzada —que ya no trae el anuncio—; y el reporte solo miraba los leads con
    `es_pauta`, cuando la pauta de Meta hace que la gente escriba por WhatsApp.
    """

    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-rep")
        self.anuncio = Anuncio.objects.create(
            clinica=self.clinica, nombre="Reaccionas y luego te arrepientes",
            plataforma=Anuncio.Plataforma.INSTAGRAM, sede=Anuncio.Sede.PIURA,
        )
        self.hoy = timezone.localdate()

    def _lead(self, nombre, telefono, estado, anuncio=None, es_pauta=False, fuente=Lead.Fuente.WHATSAPP):
        return Lead.objects.create(
            clinica=self.clinica, nombre=nombre, telefono=telefono, sede=Lead.Sede.PIURA,
            fuente=fuente, es_pauta=es_pauta, anuncio=anuncio,
            estado=estado, fecha_consulta=self.hoy,
        )

    def _reporte(self):
        return generar_reporte_pauta(self.clinica, Lead.Sede.PIURA, self.hoy, self.hoy)["datos"]

    def test_el_anuncio_no_se_pierde_cuando_la_persona_avanza_de_etapa(self):
        """Dos filas de la misma persona: la vieja trae el anuncio, la nueva no."""
        self._lead("Ana Pérez", "987654321", Lead.Estado.AGENDADO, anuncio=self.anuncio, es_pauta=True)
        self._lead("Ana Pérez", "987654321", Lead.Estado.GANADO)  # fila de avance, sin anuncio
        datos = self._reporte()
        self.assertEqual(datos["total_consultas"], 1)          # una persona, no dos
        self.assertEqual(datos["consultas_por_publicidad"], 1)  # y sabemos de qué anuncio vino
        self.assertEqual(datos["anuncios"][0]["nombre"], "Reaccionas y luego te arrepientes")

    def test_cuenta_el_anuncio_aunque_el_origen_no_sea_de_pauta(self):
        """La pauta de Meta manda a WhatsApp: el lead se registra como 'WhatsApp
        directo' pero eligieron el anuncio. Ese anuncio tiene que contar."""
        self._lead("Luis Gómez", "912345678", Lead.Estado.AGENDADO, anuncio=self.anuncio, es_pauta=False)
        datos = self._reporte()
        self.assertEqual(datos["consultas_por_publicidad"], 1)
        self.assertEqual(datos["anuncios"][0]["n"], 1)

    def test_las_cinco_consultas_reportan_su_anuncio(self):
        """El caso tal cual lo describió marketing: cinco consultas del anuncio,
        cada una con su fila de avance encima. Antes se reportaba una."""
        for i in range(5):
            tel = f"98700000{i}"
            self._lead(f"Paciente {i}", tel, Lead.Estado.AGENDADO, anuncio=self.anuncio, es_pauta=True)
            self._lead(f"Paciente {i}", tel, Lead.Estado.GANADO)
        datos = self._reporte()
        self.assertEqual(datos["total_consultas"], 5)
        self.assertEqual(datos["consultas_por_publicidad"], 5)
        self.assertEqual(datos["anuncios"][0]["n"], 5)

    def test_una_consulta_sin_anuncio_no_inventa_pauta(self):
        self._lead("Sin anuncio", "900000000", Lead.Estado.AGENDADO)
        datos = self._reporte()
        self.assertEqual(datos["total_consultas"], 1)
        self.assertEqual(datos["consultas_por_publicidad"], 0)
