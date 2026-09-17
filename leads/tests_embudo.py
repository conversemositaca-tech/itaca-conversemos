"""El embudo web: que cuente bien y que no guarde de más.

Dos cosas se protegen aquí. Que los números digan la verdad —una campaña que
trae mucha gente que no reserva tiene que distinguirse de una que trae poca que
sí— y que medir no convierta el sistema en un rastreador: es una web de
psicología y las páginas que alguien mira no pueden quedar atadas a su nombre.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.models import Clinica
from leads import embudo
from leads.models import EventoSitio, Lead

NAVEGADOR = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"


class RegistrarPasoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clinica = Clinica.objects.create(nombre="Ítaca", ciudad="Piura",
                                             slug="itaca-emb", token_captacion="tok-emb")

    def _mandar(self, cuerpo, ua=NAVEGADOR):
        return self.client.post("/api/embudo/", cuerpo, content_type="application/json",
                                HTTP_USER_AGENT=ua)

    def test_guarda_el_paso_con_su_origen(self):
        r = self._mandar({"tipo": "visita", "ruta": "/psicologos", "sesion": "abc123",
                          "atribucion": {"utm_source": "instagram", "utm_medium": "cpc",
                                         "utm_campaign": "setiembre"}})
        self.assertEqual(r.status_code, 204)
        e = EventoSitio.objects.get()
        self.assertEqual((e.tipo, e.ruta, e.canal, e.campania),
                         ("visita", "/psicologos", "instagram", "setiembre"))

    def test_un_paso_inventado_no_entra(self):
        self._mandar({"tipo": "borrar_todo", "ruta": "/"})
        self.assertEqual(EventoSitio.objects.count(), 0)

    def test_los_rastreadores_no_cuentan_como_visitas(self):
        # Google y Meta ejecutan JavaScript; sin esto inflarían el embudo y cada
        # campaña parecería convertir peor de lo que realmente convierte.
        for ua in ("Googlebot/2.1", "facebookexternalhit/1.1", "python-requests/2.31", ""):
            self._mandar({"tipo": "visita", "ruta": "/"}, ua=ua)
        self.assertEqual(EventoSitio.objects.count(), 0)

    def test_nunca_falla_hacia_afuera(self):
        # Medir no puede estorbar a quien está intentando reservar, ni revelar
        # qué hay detrás según el error que devuelve.
        for basura in ({}, {"tipo": None}, {"tipo": "visita", "atribucion": "no-soy-dict"}):
            self.assertEqual(self._mandar(basura).status_code, 204)

    def test_la_pagina_se_guarda_sin_lo_que_venga_pegado_detras(self):
        # El navegador manda solo el camino, pero el endpoint lo llama cualquiera.
        self._mandar({"tipo": "visita", "ruta": "/psicologos?dni=12345678#x"})
        self.assertEqual(EventoSitio.objects.get().ruta, "/psicologos")

    def test_no_guarda_nada_que_identifique(self):
        self._mandar({"tipo": "visita", "ruta": "/terapias-online", "sesion": "xyz"})
        campos = {f.name for f in EventoSitio._meta.get_fields()}
        for prohibido in ("ip", "direccion_ip", "user_agent", "navegador", "lead",
                          "paciente", "telefono", "email", "nombre"):
            self.assertNotIn(prohibido, campos, f"el embudo no debe guardar {prohibido}")


class ContarElEmbudoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clinica = Clinica.objects.create(nombre="Ítaca", ciudad="Piura",
                                             slug="itaca-emb2", token_captacion="tok-emb2")

    def _evento(self, tipo, sesion, canal="", medio="", campania=""):
        return EventoSitio.objects.create(clinica=self.clinica, tipo=tipo, sesion=sesion,
                                          canal=canal, medio=medio, campania=campania)

    def _ventana(self):
        ahora = timezone.now()
        return ahora - timedelta(days=1), ahora + timedelta(days=1)

    def test_una_persona_que_mira_cuatro_paginas_es_una_persona(self):
        # Si no, el sitio parecería convertir cuatro veces peor de lo que es.
        for _ in range(4):
            self._evento("visita", "misma-sesion", canal="instagram")
        desde, hasta = self._ventana()
        r = embudo.resumen(self.clinica, desde, hasta)
        self.assertEqual(r["total"]["personas"], 1)
        self.assertEqual(r["total"]["paginas"], 4)

    def test_el_embudo_completo_de_una_campana(self):
        self._evento("visita", "s1", canal="instagram", medio="cpc", campania="ansiedad")
        self._evento("visita", "s2", canal="instagram", medio="cpc", campania="ansiedad")
        self._evento("clic_reservar", "s1", canal="instagram", medio="cpc", campania="ansiedad")
        self._evento("abre_agenda", "s1", canal="instagram", medio="cpc", campania="ansiedad")
        Lead.objects.create(clinica=self.clinica, nombre="Ana", fuente=Lead.Fuente.WEB,
                            origen_canal="instagram", origen_medio="cpc", campania="ansiedad")
        desde, hasta = self._ventana()
        fila = embudo.resumen(self.clinica, desde, hasta)["por_origen"][0]
        self.assertEqual(fila["origen"], "instagram · cpc · ansiedad")
        self.assertEqual((fila["personas"], fila["clic_reservar"], fila["abre_agenda"],
                          fila["reservas"]), (2, 1, 1, 1))
        self.assertEqual(fila["tasa"], 50.0)

    def test_la_campana_que_trae_menos_pero_convierte_se_distingue(self):
        # El punto de todo esto: 10 visitas y 1 reserva NO es lo mismo que 1 y 1.
        for i in range(10):
            self._evento("visita", f"mucha-{i}", canal="meta", medio="cpc")
        self._evento("visita", "poca-1", canal="google", medio="organic")
        Lead.objects.create(clinica=self.clinica, nombre="A", fuente=Lead.Fuente.WEB,
                            origen_canal="meta", origen_medio="cpc")
        Lead.objects.create(clinica=self.clinica, nombre="B", fuente=Lead.Fuente.WEB,
                            origen_canal="google", origen_medio="organic")
        desde, hasta = self._ventana()
        filas = embudo.resumen(self.clinica, desde, hasta)["por_origen"]
        por_origen = {f["origen"]: f for f in filas}
        self.assertEqual(por_origen["meta · cpc"]["tasa"], 10.0)
        self.assertEqual(por_origen["google · organic"]["tasa"], 100.0)

    def test_lo_que_llega_sin_etiqueta_se_llama_directo(self):
        self._evento("visita", "s1")
        desde, hasta = self._ventana()
        fila = embudo.resumen(self.clinica, desde, hasta)["por_origen"][0]
        self.assertEqual(fila["origen"], "directo")

    def test_sin_visitas_medidas_lo_dice_en_vez_de_fingir_un_cero(self):
        # Los primeros días tras desplegar no habrá visitas medidas pero sí
        # reservas: mostrar "0 % de conversión" sería mentir.
        Lead.objects.create(clinica=self.clinica, nombre="Ana", fuente=Lead.Fuente.WEB)
        desde, hasta = self._ventana()
        total = embudo.resumen(self.clinica, desde, hasta)["total"]
        self.assertFalse(total["midiendo"])
        self.assertEqual(total["reservas"], 1)
        self.assertIsNone(total["tasa"])

    def test_no_se_mezcla_lo_de_otra_clinica(self):
        otra = Clinica.objects.create(nombre="Otra", ciudad="Lima", slug="otra-emb",
                                      token_captacion="tok-otra")
        EventoSitio.objects.create(clinica=otra, tipo="visita", sesion="ajena")
        self._evento("visita", "propia")
        desde, hasta = self._ventana()
        self.assertEqual(embudo.resumen(self.clinica, desde, hasta)["total"]["personas"], 1)

    def test_lo_de_otro_periodo_no_cuenta(self):
        viejo = self._evento("visita", "vieja")
        EventoSitio.objects.filter(pk=viejo.pk).update(
            creado_en=timezone.now() - timedelta(days=40))
        self._evento("visita", "nueva")
        desde, hasta = self._ventana()
        self.assertEqual(embudo.resumen(self.clinica, desde, hasta)["total"]["personas"], 1)
