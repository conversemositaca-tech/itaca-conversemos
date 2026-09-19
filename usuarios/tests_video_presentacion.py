"""El video de presentación se aloja aquí y se sirve por tramos.

Safari en iPhone no reproduce un `<video>` si el servidor no responde la
cabecera `Range`: pide los primeros bytes para leer la cabecera del archivo y,
si le llega el archivo entero con un 200, abandona y deja el recuadro en negro.
Como la mitad de quien entra a reservar lo hace desde el celular, servir el
archivo de golpe equivale a no tener video.

Los tramos son además lo que permite adelantar sin descargar todo, y lo que
evita que quien solo quiere ver el final se traiga el archivo completo.

    python manage.py test usuarios.tests_video_presentacion
"""
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from core.models import Clinica
from usuarios.models import Profesional, Usuario

MEDIA = tempfile.mkdtemp(prefix="test-video-")
CUERPO = bytes(range(256)) * 8  # 2048 bytes con contenido reconocible


def _video(nombre="presentacion.mp4"):
    return SimpleUploadedFile(nombre, CUERPO, content_type="video/mp4")


@override_settings(MEDIA_ROOT=MEDIA)
class _Base(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.clinica = Clinica.objects.create(
            nombre="Ítaca Conversemos", slug="itaca-video", token_captacion="tok-video")
        self.con = Profesional.objects.create(
            clinica=self.clinica, nombre="Lic. Con Video", sede="lima",
            frase="Conversemos.", video=_video())
        self.sin = Profesional.objects.create(
            clinica=self.clinica, nombre="Lic. Sin Video", sede="lima", frase="Aquí estoy.")

    def cuerpo(self, resp):
        return b"".join(resp.streaming_content)


class TramosTests(_Base):
    """Lo que el navegador pide y lo que hay que devolverle."""

    def url(self):
        return f"/api/agendamiento/{self.clinica.token_captacion}/video/{self.con.id}/"

    def test_sin_rango_devuelve_todo_pero_avisa_que_acepta_tramos(self):
        r = self.client.get(self.url())
        self.assertEqual(r.status_code, 200)
        # Sin esta cabecera el navegador ni siquiera intenta pedir tramos.
        self.assertEqual(r["Accept-Ranges"], "bytes")
        self.assertEqual(r["Content-Length"], str(len(CUERPO)))
        self.assertEqual(self.cuerpo(r), CUERPO)

    def test_los_primeros_bytes(self):
        # Es la primera petición que hace Safari: leer la cabecera del archivo.
        r = self.client.get(self.url(), headers={"range": "bytes=0-99"})
        self.assertEqual(r.status_code, 206)
        self.assertEqual(r["Content-Range"], f"bytes 0-99/{len(CUERPO)}")
        self.assertEqual(r["Content-Length"], "100")
        self.assertEqual(self.cuerpo(r), CUERPO[:100])

    def test_desde_un_punto_hasta_el_final(self):
        # Lo que pide el navegador cuando alguien adelanta el video.
        r = self.client.get(self.url(), headers={"range": "bytes=2000-"})
        self.assertEqual(r.status_code, 206)
        self.assertEqual(r["Content-Range"], f"bytes 2000-{len(CUERPO) - 1}/{len(CUERPO)}")
        self.assertEqual(self.cuerpo(r), CUERPO[2000:])

    def test_los_ultimos_bytes(self):
        # "bytes=-10" son los ÚLTIMOS diez, no los primeros. Confundirlo manda
        # el trozo equivocado y el reproductor se queda cargando para siempre.
        r = self.client.get(self.url(), headers={"range": "bytes=-10"})
        self.assertEqual(r.status_code, 206)
        self.assertEqual(self.cuerpo(r), CUERPO[-10:])

    def test_un_tramo_que_no_existe_se_rechaza(self):
        r = self.client.get(self.url(), headers={"range": "bytes=999999-"})
        self.assertEqual(r.status_code, 416)
        self.assertEqual(r["Content-Range"], f"bytes */{len(CUERPO)}")

    def test_un_rango_mal_escrito_devuelve_el_archivo_entero(self):
        # Mejor entregar el video completo que romperse: algún proxy raro puede
        # mandar cualquier cosa en esa cabecera.
        r = self.client.get(self.url(), headers={"range": "paginas=1-2"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.cuerpo(r), CUERPO)

    def test_pedir_mas_alla_del_final_se_recorta(self):
        r = self.client.get(self.url(), headers={"range": "bytes=2040-999999"})
        self.assertEqual(r.status_code, 206)
        self.assertEqual(self.cuerpo(r), CUERPO[2040:])


class AccesoTests(_Base):
    def test_sin_video_no_hay_nada_que_servir(self):
        r = self.client.get(f"/api/agendamiento/{self.clinica.token_captacion}/video/{self.sin.id}/")
        self.assertEqual(r.status_code, 404)

    def test_con_un_token_ajeno_no_se_llega_al_video(self):
        r = self.client.get(f"/api/agendamiento/token-inventado/video/{self.con.id}/")
        self.assertEqual(r.status_code, 404)

    def test_una_ficha_retirada_deja_de_mostrar_su_video(self):
        self.con.activo = False
        self.con.save(update_fields=["activo"])
        r = self.client.get(f"/api/agendamiento/{self.clinica.token_captacion}/video/{self.con.id}/")
        self.assertEqual(r.status_code, 404)


class PaginasPublicasTests(_Base):
    def test_la_landing_de_reservas_apunta_al_endpoint(self):
        # La landing solo lista a quien tiene cuenta de agenda y horario puesto.
        for p, correo in [(self.con, "con@test.pe"), (self.sin, "sin@test.pe")]:
            p.usuario = Usuario.objects.create_user(
                email=correo, password="x", clinica=self.clinica, rol=Usuario.Rol.MEDICO)
            p.horario_semanal = {"1": [10, 11]}
            p.save(update_fields=["usuario", "horario_semanal"])

        d = self.client.get(f"/api/agendamiento/{self.clinica.token_captacion}/").json()
        por_nombre = {p["nombre"]: p for p in d["profesionales"]}
        self.assertIn(f"/video/{self.con.id}/", por_nombre["Lic. Con Video"]["video"])
        # Quien no grabó el suyo no muestra un botón que lleva a un 404.
        self.assertEqual(por_nombre["Lic. Sin Video"]["video"], "")

    @override_settings(SITIO_CLINICA_TOKEN="tok-video")
    def test_la_pagina_de_psicologos_apunta_al_endpoint(self):
        equipo = {p["nombre"]: p for p in self.client.get("/api/sitio/").json()["equipo"]}
        self.assertIn(f"/api/sitio/video/{self.con.id}/", equipo["Lic. Con Video"]["video"])
        self.assertEqual(equipo["Lic. Sin Video"]["video"], "")

    @override_settings(SITIO_CLINICA_TOKEN="tok-video")
    def test_una_ficha_que_solo_tiene_video_igual_se_publica(self):
        # El sitio muestra a quien tenga "algo que mostrar". Grabar una
        # presentación es algo que mostrar: antes esa ficha quedaba invisible.
        Profesional.objects.create(clinica=self.clinica, nombre="Lic. Solo Video",
                                   sede="piura", video=_video("otro.mp4"))
        nombres = [p["nombre"] for p in self.client.get("/api/sitio/").json()["equipo"]]
        self.assertIn("Lic. Solo Video", nombres)


class TipoDeArchivoTests(TestCase):
    def test_reconoce_lo_que_graba_un_celular(self):
        from core.rangos import tipo_de_video
        self.assertEqual(tipo_de_video("clip.mp4"), "video/mp4")
        self.assertEqual(tipo_de_video("CLIP.MOV"), "video/quicktime")
        self.assertEqual(tipo_de_video("clip.webm"), "video/webm")
        # Lo desconocido sale como mp4, que es lo que graba un celular.
        self.assertEqual(tipo_de_video("clip.xyz"), "video/mp4")
        self.assertEqual(tipo_de_video(""), "video/mp4")
