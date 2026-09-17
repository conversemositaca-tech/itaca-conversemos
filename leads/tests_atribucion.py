"""De dónde vino la reserva: limpieza del origen y su llegada al Lead.

Lo que se protege aquí es que la reserva NUNCA dependa de esto: si no llega
origen, o llega basura, la consulta tiene que entrar igual.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.models import Clinica
from leads import atribucion
from leads.models import Lead
from pacientes.models import Cita
from usuarios.models import Profesional, Usuario


class LimpiezaDelOrigenTests(TestCase):
    def test_solo_pasan_las_claves_conocidas(self):
        limpio = atribucion.limpiar({"utm_source": "meta", "password": "x", "otra": "y"})
        self.assertEqual(limpio, {"utm_source": "meta"})

    def test_lo_vacio_no_se_guarda(self):
        self.assertEqual(atribucion.limpiar({"utm_source": "   ", "utm_medium": None}), {})

    def test_no_revienta_con_lo_que_no_es_un_diccionario(self):
        for basura in (None, "utm_source=meta", 42, []):
            self.assertEqual(atribucion.limpiar(basura), {})

    def test_recorta_valores_largos(self):
        limpio = atribucion.limpiar({"utm_campaign": "x" * 500, "landing": "/y" * 500})
        self.assertEqual(len(limpio["utm_campaign"]), atribucion.LARGO_MAX)
        self.assertEqual(len(limpio["landing"]), atribucion.LARGO_URL)

    def test_reconoce_lo_pagado_por_el_medio(self):
        self.assertTrue(atribucion.es_pagado({"utm_medium": "cpc"}))
        self.assertTrue(atribucion.es_pagado({"utm_medium": "paid-social"}))
        self.assertFalse(atribucion.es_pagado({"utm_medium": "organic"}))

    def test_gclid_si_prueba_que_se_pago(self):
        # Google Ads lo añade solo a sus anuncios; una búsqueda orgánica no lo trae.
        self.assertTrue(atribucion.es_pagado({"gclid": "abc"}))

    def test_fbclid_solo_no_prueba_que_se_pago(self):
        # Meta lo cuelga de TODO clic que sale de Instagram o Facebook, también
        # del enlace de la bio, que no cuesta nada.
        self.assertFalse(atribucion.es_pagado({"fbclid": "abc"}))

    def test_el_medio_declarado_manda_sobre_el_identificador_de_clic(self):
        # La bio etiquetada llega con fbclid y NO es pauta.
        self.assertFalse(atribucion.es_pagado({"utm_medium": "bio", "fbclid": "abc"}))
        # El anuncio etiquetado llega igual y SÍ lo es.
        self.assertTrue(atribucion.es_pagado({"utm_medium": "cpc", "fbclid": "abc"}))

    def test_la_visita_organica_de_instagram_no_ensucia_el_reporte_de_pauta(self):
        # Caso real: alguien entra por la bio sin etiquetar y reserva. Queda el
        # rastro de Meta para cruzar, pero sin marcar una pauta que no existió.
        campos = atribucion.campos_de_lead({"fbclid": "abc", "landing": "/"})
        self.assertNotIn("es_pauta", campos)
        self.assertEqual(campos["origen_detalle"]["fbclid"], "abc")

    def test_llena_los_campos_que_el_reporte_ya_lee(self):
        campos = atribucion.campos_de_lead({
            "utm_source": "instagram", "utm_medium": "cpc",
            "utm_campaign": "ansiedad-piura", "utm_content": "video-15s",
        })
        self.assertEqual(campos["campania"], "ansiedad-piura")   # campo que ya existía
        self.assertTrue(campos["es_pauta"])                      # marcado solo
        self.assertEqual(campos["subfuente"], "instagram · cpc")
        self.assertEqual(campos["origen_canal"], "instagram")
        self.assertEqual(campos["origen_contenido"], "video-15s")

    def test_organico_no_se_marca_como_pauta(self):
        campos = atribucion.campos_de_lead({"utm_source": "google", "utm_medium": "organic"})
        self.assertNotIn("es_pauta", campos)

    def test_sin_origen_no_toca_ningun_campo(self):
        self.assertEqual(atribucion.campos_de_lead({}), {})
        self.assertEqual(atribucion.campos_de_lead(None), {})


class ReservaConOrigenTests(TestCase):
    """La reserva pública completa, con y sin origen."""

    @classmethod
    def setUpTestData(cls):
        cls.clinica = Clinica.objects.create(nombre="Ítaca", ciudad="Piura",
                                             slug="itaca-orig", token_captacion="tok-orig")
        cls.user = Usuario.objects.create_user(
            email="psi@demo.pe", password="x", nombre="Psi", rol=Usuario.Rol.MEDICO,
            clinica=cls.clinica)
        # Atiende todos los días a las horas que usa el test.
        horario = {str(d): list(range(8, 20)) for d in range(1, 8)}
        cls.prof = Profesional.objects.create(
            clinica=cls.clinica, nombre="Psi", usuario=cls.user, sede="piura",
            horario_semanal=horario, activo=True)

    def _reservar(self, extra=None):
        manana = timezone.localtime() + timedelta(days=2)
        inicio = manana.replace(hour=15, minute=0, second=0, microsecond=0)
        cuerpo = {
            "profesional_id": self.prof.id, "inicio": inicio.isoformat(),
            "nombre": "Ana Pérez", "telefono": "987654321",
        }
        if extra:
            cuerpo.update(extra)
        return self.client.post("/api/agendamiento/tok-orig/reservar/", cuerpo,
                                content_type="application/json")

    def test_la_reserva_guarda_de_donde_vino(self):
        r = self._reservar({"atribucion": {
            "utm_source": "meta", "utm_medium": "cpc", "utm_campaign": "piura-set",
            "fbclid": "ABC123", "landing": "/", "referrer": "https://l.instagram.com/",
        }})
        self.assertEqual(r.status_code, 201, r.content[:300])
        lead = Lead.objects.get(clinica=self.clinica)
        self.assertEqual(lead.origen_canal, "meta")
        self.assertEqual(lead.campania, "piura-set")
        self.assertTrue(lead.es_pauta)
        self.assertEqual(lead.origen_detalle["referrer"], "https://l.instagram.com/")
        # Y lo de siempre sigue igual: la captación queda enlazada a la cita.
        self.assertEqual(lead.fuente, Lead.Fuente.WEB)
        self.assertIsNotNone(lead.cita)
        self.assertTrue(Cita.objects.filter(clinica=self.clinica, agendado_web=True).exists())

    def test_sin_origen_la_reserva_entra_igual(self):
        r = self._reservar()
        self.assertEqual(r.status_code, 201, r.content[:300])
        lead = Lead.objects.get(clinica=self.clinica)
        self.assertEqual(lead.origen_canal, "")
        self.assertEqual(lead.origen_detalle, {})
        self.assertFalse(lead.es_pauta)
        self.assertIsNotNone(lead.cita)

    def test_un_origen_corrupto_no_impide_reservar(self):
        # Alguien pega la URL con basura, o un bot manda cualquier cosa.
        r = self._reservar({"atribucion": "utm_source=meta"})
        self.assertEqual(r.status_code, 201, r.content[:300])
        self.assertEqual(Lead.objects.get(clinica=self.clinica).origen_detalle, {})
