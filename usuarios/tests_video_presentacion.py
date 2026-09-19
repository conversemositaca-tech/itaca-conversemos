"""El video de presentación del psicólogo sale del enlace que pega gerencia.

Se guarda el ENLACE y no el archivo: servir video desde el contenedor obligaría
a implementar envío por tramos (sin eso, Safari en iPhone no reproduce) y ataría
un worker de Gunicorn durante toda la descarga.

Como el enlace lo pega una persona a mano, llega en cualquiera de las formas que
YouTube reparte —el botón "Compartir", la barra de direcciones, un Short— y el
reproductor necesita una sola. Convertirlo en el modelo evita que la landing de
reservas y la página de psicólogos lo interpreten cada una a su manera.

    python manage.py test usuarios.tests_video_presentacion
"""
from django.test import TestCase, override_settings

from core.models import Clinica
from usuarios.models import Profesional


class VideoEmbedTests(TestCase):
    def embed(self, url):
        return Profesional(video_url=url).video_embed_url

    def test_reconoce_las_formas_en_que_youtube_reparte_un_enlace(self):
        esperado = "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?rel=0&modestbranding=1"
        for url in [
            "https://youtu.be/dQw4w9WgXcQ",                        # botón "Compartir"
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",          # barra de direcciones
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30s",    # compartido desde un minuto
            "https://www.youtube.com/watch?list=PL1&v=dQw4w9WgXcQ", # abierto desde una lista
            "https://youtube.com/shorts/dQw4w9WgXcQ",               # subido como Short
            "https://www.youtube.com/embed/dQw4w9WgXcQ",            # ya venía incrustable
        ]:
            self.assertEqual(self.embed(url), esperado, url)

    def test_usa_el_dominio_sin_cookies(self):
        # En un sitio de salud mental, quien solo mira el perfil de un psicólogo
        # no tiene por qué quedar registrado por Google antes de darle play.
        self.assertIn("youtube-nocookie.com", self.embed("https://youtu.be/dQw4w9WgXcQ"))

    def test_corta_los_videos_sugeridos_al_terminar(self):
        # Sin rel=0, al acabar el video aparecen recomendaciones de YouTube
        # dentro de la web de la clínica.
        self.assertIn("rel=0", self.embed("https://youtu.be/dQw4w9WgXcQ"))

    def test_un_enlace_que_no_es_de_youtube_no_se_incrusta(self):
        # Mejor no mostrar nada que incrustar un dominio cualquiera que alguien
        # haya pegado en ese campo.
        for url in ["https://vimeo.com/123456789",
                    "https://drive.google.com/file/d/abc/view",
                    "https://ejemplo.pe/video.mp4",
                    "no es una url",
                    ""]:
            self.assertEqual(self.embed(url), "", url)

    def test_sin_enlace_no_hay_video(self):
        self.assertEqual(Profesional().video_embed_url, "")


class VideoEnLasPaginasPublicasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clinica = Clinica.objects.create(
            nombre="Ítaca Conversemos", slug="itaca-video", token_captacion="tok-video")
        cls.con = Profesional.objects.create(
            clinica=cls.clinica, nombre="Lic. Con Video", sede="lima",
            frase="Conversemos.", video_url="https://youtu.be/dQw4w9WgXcQ")
        cls.sin = Profesional.objects.create(
            clinica=cls.clinica, nombre="Lic. Sin Video", sede="lima",
            frase="Aqui estoy.")
        # Ficha que solo tiene el video: sin foto, sin frase y sin enfoque.
        cls.solo_video = Profesional.objects.create(
            clinica=cls.clinica, nombre="Lic. Solo Video", sede="piura",
            video_url="https://youtu.be/dQw4w9WgXcQ")

    @override_settings(SITIO_CLINICA_TOKEN="tok-video")
    def test_la_pagina_de_psicologos_lo_entrega_listo_para_reproducir(self):
        equipo = {p["nombre"]: p for p in self.client.get("/api/sitio/").json()["equipo"]}
        self.assertIn("youtube-nocookie.com/embed/dQw4w9WgXcQ", equipo["Lic. Con Video"]["video"])
        # Quien no grabó el suyo no muestra un botón roto.
        self.assertEqual(equipo["Lic. Sin Video"]["video"], "")

    @override_settings(SITIO_CLINICA_TOKEN="tok-video")
    def test_una_ficha_que_solo_tiene_video_igual_se_publica(self):
        # El sitio muestra al equipo que tenga "algo que mostrar". Grabar una
        # presentacion es algo que mostrar: antes esa ficha quedaba invisible.
        nombres = [p["nombre"] for p in self.client.get("/api/sitio/").json()["equipo"]]
        self.assertIn("Lic. Solo Video", nombres)

    def test_el_enlace_crudo_no_se_publica(self):
        # Lo que sale es la URL del reproductor, no la que pegó gerencia: así la
        # web nunca ofrece un salto a youtube.com.
        with override_settings(SITIO_CLINICA_TOKEN="tok-video"):
            equipo = self.client.get("/api/sitio/").json()["equipo"]
        for p in equipo:
            self.assertNotIn("youtu.be", p["video"])
            self.assertNotIn("www.youtube.com/watch", p["video"])
