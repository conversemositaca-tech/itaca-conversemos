"""Biblioteca de material compartible y envío de varias imágenes.

Lo que se prueba aquí es lo que puede salir caro en producción:

- que una imagen que ya salió NUNCA se reenvíe (el paciente no debe recibir la
  misma pieza dos veces al pulsar "reintentar");
- que una comunicación a medias no se informe como enviada;
- que el archivo se valide por su CONTENIDO, no por su nombre;
- que una pieza de otra clínica no se pueda enviar (Ley 29733).
"""
import base64
import io
import shutil
import struct
import tempfile
import zlib
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from core.models import Clinica, InstanciaEvolution
from core.tenant import set_clinica_actual
from mensajes import materiales as mat
from mensajes import services
from mensajes.models import Material, Mensaje
from pacientes.models import Paciente
from usuarios.models import Usuario

MEDIA_TMP = tempfile.mkdtemp(prefix="itaca-material-")


# --- fixtures de imagen -------------------------------------------------------
# JPEG, PNG y WEBP REALES, producidos por un encoder de verdad (ffmpeg: libjpeg,
# libpng, libwebp) y empotrados en base64 para que la prueba no dependa de
# ningún archivo del disco.
#
# El JPEG es el fixture que importa. Tiene cabecera JFIF y tablas de
# cuantización reales, así que su SOF —el marcador donde están el ancho y el
# alto— cae en el byte 293. Esa es exactamente la forma que tiene cualquier foto
# de teléfono, y el caso que el validador rechazaba con un "puede estar dañada"
# que era falso. Una imagen sintética mínima NO lo reproduce: en ella el SOF cae
# en el byte 20 y la prueba pasa aunque el código esté roto.
JPEG_SOF_OFFSET = 293

JPEG_REAL_B64 = """\
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"""

PNG_REAL_B64 = """\
iVBORw0KGgoAAAANSUhEUgAAADAAAAAgCAIAAADbtmxLAAAACXBIWXMAAAABAAAAAQBPJcTWAAAA9klEQVR4
nNWYAQ6CMAxFf5N/D/CmehOv4k3gJDVjAoOSYaaM8tIQXdbup21Ih8CgZkUUKotlsV66XrN7bGx7Fje81mrU
nFWISggkamV8LUiyzmWoSCYsK6vZ1bRfssqwfnrySeIpauYeNwddoWRSJT2RoW56qQzp396ChUlyn6HTIZxB
OINwBuEMwhmEMwhnEM4gnEE4FyRbQ9OhrMeP8K9d2kvCs0GHj911/t3DOgQTJJtS6+dNj8ShCXG64CPP1MF9
yU6HcAbhDIaBNfbTyNT0t7H/7VS7/bEhtqvZM4VP4wxXiVZThyio+BKOHyi82x+kKR/wDeFmZe30sYI3AAAA
AElFTkSuQmCC"""

WEBP_REAL_B64 = """\
UklGRjACAABXRUJQVlA4ICQCAACwDgCdASowACAAPnkykkekoyGhOrzIAJAPCWwAnTlBWh34/K/x35AlwPwD
8I/vH5Lf4DgAP0P3AH6zfsB7AH+Z/x3YAfrt1gHoAfwD+cdZl+2Ho0XeF9VsgHx6cQBj8mYB+tw5Oz4RFxND
a2Lx7OjC8uoPiti3/ycMJQnsfQAA/v4WurRUM71qE0pPinw/Ty+FUN9sDeZkSg+VQl1FRHolT9Xl6Xr71+Uj
PDOWkDyAgQcJkv4T6V75vqz0+LHyquazUYeNzrrQxULv/qPZWkSPaQ3/rJa15+D8VV/+zoerK08W0WHl/68Y
HQn65B+lB/14wOhP/rkH6SLTZ86ry/tMTzNrH/Ov7TCpgK7Ls5OfHRuYJd/pMZXDvwj3JXmaLmkb8+f931xI
Xduvajx92ienssDSuR/r0/HEBUQlHVgEautPnkTe8oFW95V762Y5cP9ZJ/ORbyaxiXnKBy3aVwsLAwd33Yf1
7VV2PKHh8+W2P+reF9iIi8GROtdrVpP0/fs7cMLv51v0T/G8zd60//f11RzBLf201TPiDM7n8sP//qNI7qxR
WjK3EVPOYGaPaeLqv0wNoiNZHKM53/S07073jiyKLpMpjK+5dZ/pZ1/OY8iXU6SHdS1iuwws4ESfP0A+ejES
6lu0S+Za84NIUUiN+uRggGdmpiDb7wBc/JlTqSV/Ug5v/B38lO4V7MxezYsagrFcu/kX+P/+19wXnMLg7MAA
AA=="""


def jpeg_real(ancho=None, alto=None):
    """El JPEG de ffmpeg (64x48 px).

    Con `ancho` o `alto` se reescriben las medidas declaradas en su SOF, para
    poder probar los topes de tamaño sin empotrar un archivo de varios MB. Todo
    lo demás sigue siendo el archivo real.
    """
    datos = bytearray(base64.b64decode(JPEG_REAL_B64))
    if ancho is None and alto is None:
        return bytes(datos)
    i = datos.index(b"\xff\xc0")
    alto_actual, ancho_actual = struct.unpack(">HH", datos[i + 5:i + 9])
    datos[i + 5:i + 9] = struct.pack(">HH", alto or alto_actual, ancho or ancho_actual)
    return bytes(datos)


def png_real():
    return base64.b64decode(PNG_REAL_B64)


def webp_real():
    return base64.b64decode(WEBP_REAL_B64)


def png(ancho=300, alto=200):
    """Un PNG sintético del tamaño que haga falta, con su IHDR bien formado."""
    def trozo(tipo, datos):
        return (struct.pack(">I", len(datos)) + tipo + datos
                + struct.pack(">I", zlib.crc32(tipo + datos) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", ancho, alto, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00" * (ancho * 3 + 1) * alto, 1)
    return (b"\x89PNG\r\n\x1a\n" + trozo(b"IHDR", ihdr)
            + trozo(b"IDAT", idat) + trozo(b"IEND", b""))


def subida(nombre="pieza.png", contenido=None, tipo="image/png"):
    return SimpleUploadedFile(nombre, contenido if contenido is not None else png(), tipo)


class LeerCabeceraTests(TestCase):
    """El tipo y las dimensiones salen del CONTENIDO, no del nombre.

    Se le pasa el archivo entero, que es lo que hace el endpoint: recortarlo
    reconocía el formato pero perdía las medidas de todo JPEG real.
    """

    def test_jpeg_real_con_sof_despues_del_byte_64(self):
        """Regresión del bug de produccion.

        El SOF de este JPEG está en el byte 293. Con la versión que leía solo
        una cabecera de 64 bytes, esto devolvía ("image/jpeg", 0, 0) y el
        endpoint contestaba "puede estar dañada" a una imagen perfecta.
        """
        datos = jpeg_real()
        self.assertGreater(JPEG_SOF_OFFSET, 64)
        self.assertEqual(mat.inspeccionar(datos), ("image/jpeg", 64, 48))

    def test_una_cabecera_recortada_no_alcanza_para_jpeg(self):
        """Deja constancia de POR QUÉ hay que pasar el archivo entero."""
        self.assertEqual(mat.inspeccionar(jpeg_real()[:64]), ("image/jpeg", 0, 0))

    def test_png_real_da_tipo_y_medidas(self):
        self.assertEqual(mat.inspeccionar(png_real()), ("image/png", 48, 32))

    def test_webp_real_da_tipo_y_medidas(self):
        self.assertEqual(mat.inspeccionar(webp_real()), ("image/webp", 48, 32))

    def test_png_sintetico_de_cualquier_medida(self):
        self.assertEqual(mat.inspeccionar(png(640, 480)), ("image/png", 640, 480))

    def test_webp_lossy_se_reconoce(self):
        cuerpo = (b"VP8 " + struct.pack("<I", 20) + b"\x00" * 3
                  + b"\x9d\x01\x2a" + struct.pack("<HH", 400, 300))
        webp = b"RIFF" + struct.pack("<I", len(cuerpo) + 4) + b"WEBP" + cuerpo
        self.assertEqual(mat.inspeccionar(webp), ("image/webp", 400, 300))

    def test_jpeg_truncado_antes_del_sof_no_pasa(self):
        """Un archivo cortado a la mitad se reconoce pero no da medidas."""
        self.assertEqual(mat.inspeccionar(jpeg_real()[:200]), ("image/jpeg", 0, 0))

    def test_jpeg_con_longitudes_corruptas_no_cuelga(self):
        """Longitudes de segmento imposibles: se descarta, no se recorre entero."""
        roto = bytearray(jpeg_real())
        roto[4:6] = b"\x00\x00"          # el APP0 declara largo 0
        self.assertEqual(mat.inspeccionar(bytes(roto)), ("image/jpeg", 0, 0))

    def test_jpeg_de_basura_no_recorre_el_archivo_entero(self):
        """Firma de JPEG y detrás un megabyte de ruido: se corta enseguida."""
        basura = b"\xff\xd8\xff" + b"\x37" * (1024 * 1024)
        self.assertEqual(mat.inspeccionar(basura), ("image/jpeg", 0, 0))

    def test_un_pdf_renombrado_a_png_no_pasa(self):
        """Renombrar la extensión no convierte un archivo en imagen."""
        self.assertEqual(mat.inspeccionar(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")[0], None)

    def test_un_script_renombrado_a_jpg_no_pasa(self):
        self.assertEqual(mat.inspeccionar(b"<?php system($_GET['c']); ?>")[0], None)

    def test_heic_y_avif_se_rechazan_con_claridad(self):
        """Un iPhone puede dar HEIC. No se acepta, pero el motivo es honesto:
        no es un formato soportado, no es que esté dañado."""
        for cabecera in (b"\x00\x00\x00\x18ftypheic" + b"\x00" * 40,
                         b"\x00\x00\x00\x1cftypavif" + b"\x00" * 40):
            self.assertEqual(mat.inspeccionar(cabecera)[0], None)

@override_settings(MEDIA_ROOT=MEDIA_TMP)
class BibliotecaTests(TestCase):
    """Subir, deduplicar y retirar piezas."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_TMP, ignore_errors=True)

    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Ítaca", slug="itaca")
        set_clinica_actual(self.clinica)
        self.coord = Usuario.objects.create_user(
            email="coord@itaca.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.ASISTENTE, nombre="Yazmín", sede="piura")
        self.client.force_login(self.coord)

    def _subir(self, **extra):
        datos = {"archivo": subida(), "nombre": "Horarios", "categoria": "horarios"}
        datos.update(extra)
        return self.client.post("/api/materiales/", datos)

    def test_subir_guarda_tipo_medidas_y_hash(self):
        r = self._subir()
        self.assertEqual(r.status_code, 201, r.content[:300])
        m = Material.objects.get()
        self.assertEqual((m.mime, m.ancho, m.alto), ("image/png", 300, 200))
        self.assertEqual(len(m.hash), 64)
        self.assertEqual(m.subido_por, self.coord)

    def test_el_archivo_en_disco_no_lleva_el_nombre_del_usuario(self):
        """Un nombre con acentos o barras no puede decidir la ruta en disco."""
        self._subir(archivo=subida("../../etc/pásame esto.png"))
        m = Material.objects.get()
        self.assertTrue(m.archivo.name.startswith(f"material/clinica_{self.clinica.id}/"))
        self.assertNotIn("..", m.archivo.name)
        self.assertNotIn(" ", m.archivo.name)

    def test_la_misma_imagen_no_se_duplica(self):
        self._subir()
        r = self._subir(nombre="Horarios otra vez")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["duplicada"])
        self.assertEqual(Material.objects.count(), 1)

    def test_dos_imagenes_distintas_conviven(self):
        self._subir()
        self._subir(archivo=subida(contenido=png(320, 240)), nombre="Tarifas")
        self.assertEqual(Material.objects.count(), 2)

    def test_rechaza_lo_que_no_es_imagen(self):
        r = self._subir(archivo=subida("virus.png", b"MZ\x90\x00 ejecutable"))
        self.assertEqual(r.status_code, 400)
        self.assertIn("PNG", r.json()["detail"])
        self.assertEqual(Material.objects.count(), 0)

    def test_rechaza_una_imagen_enorme_de_lado(self):
        r = self._subir(archivo=subida(contenido=png(4200, 100)))
        self.assertEqual(r.status_code, 400)
        self.assertIn("4000", r.json()["detail"])

    def test_rechaza_un_archivo_que_pesa_de_mas(self):
        # Un PNG válido con relleno detrás: pesa de más aunque su cabecera esté
        # bien, que es justo el caso que hay que rechazar.
        relleno = png() + b"\x00" * (mat.MAX_MB * 1024 * 1024)
        r = self._subir(archivo=subida("gordo.png", relleno))
        self.assertEqual(r.status_code, 400)
        self.assertIn("MB", r.json()["detail"])

    # --- el endpoint completo, con imágenes de un encoder real ---------------

    def test_subir_un_jpeg_real_por_el_endpoint(self):
        """Regresión del bug de producción, de punta a punta.

        Es el caso exacto que falló: una foto de WhatsApp, cuyo SOF está pasado
        el byte 64. Antes devolvía 400 "puede estar dañada".
        """
        r = self._subir(archivo=subida("WhatsApp Image 2026-09-10 at 15.51.47.jpeg",
                                       jpeg_real(), "image/jpeg"))
        self.assertEqual(r.status_code, 201, r.content[:300])
        m = Material.objects.get()
        self.assertEqual((m.mime, m.ancho, m.alto), ("image/jpeg", 64, 48))
        self.assertTrue(m.archivo.name.endswith(".jpg"))

    def test_subir_un_png_real_por_el_endpoint(self):
        r = self._subir(archivo=subida("pieza.png", png_real(), "image/png"))
        self.assertEqual(r.status_code, 201, r.content[:300])
        m = Material.objects.get()
        self.assertEqual((m.mime, m.ancho, m.alto), ("image/png", 48, 32))

    def test_subir_un_webp_real_por_el_endpoint(self):
        r = self._subir(archivo=subida("pieza.webp", webp_real(), "image/webp"))
        self.assertEqual(r.status_code, 201, r.content[:300])
        m = Material.objects.get()
        self.assertEqual((m.mime, m.ancho, m.alto), ("image/webp", 48, 32))

    def test_un_jpeg_con_extension_y_tipo_equivocados_se_guarda_como_jpeg(self):
        """Manda el CONTENIDO, no el nombre ni lo que declare el navegador.

        Se acepta porque es una imagen de verdad, y en disco queda con la
        extensión que le corresponde a su tipo real.
        """
        r = self._subir(archivo=subida("captura.png", jpeg_real(), "image/png"))
        self.assertEqual(r.status_code, 201, r.content[:300])
        m = Material.objects.get()
        self.assertEqual(m.mime, "image/jpeg")
        self.assertTrue(m.archivo.name.endswith(".jpg"))

    def test_rechaza_un_jpeg_corrupto(self):
        """Cortado antes del SOF: aquí el mensaje de "dañada" sí es cierto."""
        r = self._subir(archivo=subida("rota.jpg", jpeg_real()[:200], "image/jpeg"))
        self.assertEqual(r.status_code, 400)
        self.assertIn("dañada", r.json()["detail"])
        self.assertEqual(Material.objects.count(), 0)

    def test_rechaza_un_ejecutable_con_firma_de_jpeg(self):
        """Los tres bytes de la firma no bastan: sin SOF no hay imagen."""
        disfraz = b"\xff\xd8\xff" + b"MZ\x90\x00 ejecutable" * 200
        r = self._subir(archivo=subida("foto.jpg", disfraz, "image/jpeg"))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Material.objects.count(), 0)

    def test_rechaza_un_jpeg_enorme_de_lado(self):
        r = self._subir(archivo=subida("panoramica.jpg", jpeg_real(ancho=4200),
                                       "image/jpeg"))
        self.assertEqual(r.status_code, 400)
        self.assertIn("4000", r.json()["detail"])
        self.assertEqual(Material.objects.count(), 0)

    def test_rechaza_un_jpeg_que_pesa_de_mas(self):
        gordo = jpeg_real() + b"\x00" * (mat.MAX_MB * 1024 * 1024)
        r = self._subir(archivo=subida("gorda.jpg", gordo, "image/jpeg"))
        self.assertEqual(r.status_code, 400)
        self.assertIn("MB", r.json()["detail"])
        self.assertEqual(Material.objects.count(), 0)

    def test_retirar_es_baja_logica(self):
        """Borrar de verdad rompería el historial de lo ya enviado."""
        self._subir()
        m = Material.objects.get()
        self.assertEqual(self.client.delete(f"/api/materiales/{m.id}/").status_code, 204)
        m.refresh_from_db()
        self.assertFalse(m.activo)
        self.assertNotIn(m.id, [x["id"] for x in self.client.get("/api/materiales/").json()])

    def test_volver_a_subir_una_retirada_la_reactiva(self):
        self._subir()
        m = Material.objects.get()
        self.client.delete(f"/api/materiales/{m.id}/")
        r = self._subir(nombre="Horarios 2026")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Material.objects.count(), 1)
        m.refresh_from_db()
        self.assertTrue(m.activo)
        self.assertEqual(m.nombre, "Horarios 2026")

    def test_filtrar_por_categoria_y_por_nombre(self):
        self._subir(nombre="Horarios Piura", categoria="horarios")
        self._subir(archivo=subida(contenido=png(320, 240)),
                    nombre="Tarifas 2026", categoria="tarifas")
        self.assertEqual(len(self.client.get("/api/materiales/?categoria=tarifas").json()), 1)
        self.assertEqual(len(self.client.get("/api/materiales/?q=horar").json()), 1)

    def test_no_se_ve_la_biblioteca_de_otra_clinica(self):
        """Aislamiento entre clínicas: requisito legal, no preferencia."""
        self._subir()
        otra = Clinica.objects.create(nombre="Otra", slug="otra")
        set_clinica_actual(otra)
        ajeno = Usuario.objects.create_user(
            email="a@otra.pe", password="x", clinica=otra, rol=Usuario.Rol.ASISTENTE)
        self.client.force_login(ajeno)
        self.assertEqual(self.client.get("/api/materiales/").json(), [])
        mio = Material.objects.filter(clinica=self.clinica).first()
        self.assertEqual(self.client.get(f"/api/materiales/{mio.id}/imagen/").status_code, 404)

    def test_la_imagen_solo_se_sirve_con_sesion(self):
        """No hay URL pública de media: la descarga pasa por el endpoint."""
        self._subir()
        m = Material.objects.get()
        self.client.logout()
        self.assertIn(self.client.get(f"/api/materiales/{m.id}/imagen/").status_code,
                      (401, 403))


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class EnvioDeVariasImagenesTests(TestCase):
    """Una comunicación = varias partes. Orden, fallo parcial y reintento."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_TMP, ignore_errors=True)

    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Ítaca", slug="itaca2")
        set_clinica_actual(self.clinica)
        InstanciaEvolution.objects.create(
            clinica=self.clinica, sede="piura", nombre_instancia="conversemospiura",
            entorno=InstanciaEvolution.Entorno.OFICIAL, activo=True)
        self.coord = Usuario.objects.create_user(
            email="c2@itaca.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.ASISTENTE, nombre="Yazmín", sede="piura")
        self.paciente = Paciente.objects.create(
            clinica=self.clinica, nombre="Paciente Prueba",
            telefono="987654321", sede="piura")
        self.imagenes = [self._material(f"Pieza {i}", png(100 + i, 80)) for i in range(3)]

    def _id(self):
        """Un id externo distinto por mensaje, como los que devuelve WhatsApp."""
        self._n = getattr(self, "_n", 0) + 1
        return f"WA{self._n:04d}"

    def _material(self, nombre, contenido):
        m = Material(clinica=self.clinica, nombre=nombre, categoria="otros",
                     mime="image/png", tamano=len(contenido), ancho=100, alto=80,
                     hash=nombre)
        m.archivo.save(f"{nombre}.png", io.BytesIO(contenido), save=False)
        m.save()
        return m

    def _enviar(self, materiales, texto="Hola", media=None, texto_res=None):
        """Envía con los proveedores simulados. NUNCA sale nada a la red."""
        ok = {"estado": "enviado", "detalle": "ok", "instancia": "conversemospiura"}
        media = media or (lambda *a, **k: {**ok, "external_message_id": self._id()})
        texto_res = texto_res or (lambda *a, **k: {**ok, "external_message_id": self._id()})
        with patch("mensajes.services.enviar_media_evolution", side_effect=media), \
             patch("mensajes.services.enviar_evolution", side_effect=texto_res):
            return services.enviar_comunicacion(
                self.clinica, telefono=self.paciente.telefono, texto=texto,
                tipo=Mensaje.Tipo.CONTINUIDAD, materiales=materiales,
                paciente=self.paciente, usuario=self.coord, sede="piura",
                dormir=lambda s: None)

    def test_una_imagen_viaja_con_el_texto_como_pie(self):
        """Como lo mandaría una persona: un solo mensaje, no dos."""
        vistos = []

        def media(clinica, tel, **kw):
            vistos.append(kw["caption"])
            return {"estado": "enviado", "detalle": "ok", "instancia": "i",
                    "external_message_id": "IMG1"}

        partes, resumen = self._enviar(self.imagenes[:1], texto="Hola Mirai", media=media)
        self.assertEqual(len(partes), 1)
        self.assertEqual(vistos, ["Hola Mirai"])
        self.assertEqual(resumen["estado"], "enviado")

    def test_varias_imagenes_van_primero_y_el_texto_al_final(self):
        partes, resumen = self._enviar(self.imagenes, texto="Hola")
        self.assertEqual([p.orden for p in partes], [1, 2, 3, 4])
        self.assertEqual([p.material_id for p in partes],
                         [m.id for m in self.imagenes] + [None])
        self.assertEqual(partes[-1].texto, "Hola")
        self.assertEqual((resumen["estado"], resumen["imagenes"], resumen["textos"]),
                         ("enviado", 3, 1))

    def test_las_imagenes_no_llevan_pie_cuando_son_varias(self):
        """Un pie pegado a una sola de tres se lee como un error."""
        pies = []

        def media(clinica, tel, **kw):
            pies.append(kw["caption"])
            return {"estado": "enviado", "detalle": "ok", "instancia": "i",
                    "external_message_id": self._id()}

        self._enviar(self.imagenes, texto="Hola", media=media)
        self.assertEqual(pies, ["", "", ""])

    def test_todas_comparten_el_mismo_grupo(self):
        partes, _ = self._enviar(self.imagenes, texto="Hola")
        grupos = {p.grupo_envio for p in partes}
        self.assertEqual(len(grupos), 1)
        self.assertIsNotNone(partes[0].grupo_envio)

    def test_se_detiene_en_el_primer_fallo(self):
        """La parte 3 falla: la 4 no se intenta siquiera."""
        intentos = []

        def media(clinica, tel, **kw):
            intentos.append(kw["nombre_archivo"])
            if len(intentos) == 3:
                return {"estado": "fallido", "detalle": "Evolution respondió 500",
                        "instancia": "i", "external_message_id": "", "error_codigo": "500"}
            return {"estado": "enviado", "detalle": "ok", "instancia": "i",
                    "external_message_id": f"IMG{len(intentos)}"}

        llamadas_texto = []

        def texto(*a, **k):
            llamadas_texto.append(1)
            return {"estado": "enviado", "detalle": "ok", "instancia": "i",
                    "external_message_id": self._id()}

        partes, resumen = self._enviar(self.imagenes, media=media, texto_res=texto)
        self.assertEqual(len(intentos), 3)
        self.assertEqual(llamadas_texto, [])           # el texto no se intentó
        self.assertEqual(resumen["estado"], "parcial")
        self.assertEqual((resumen["enviadas"], resumen["total"]), (2, 4))
        self.assertEqual(partes[3].estado, Mensaje.Estado.PENDIENTE)

    def test_reintentar_no_reenvia_lo_que_ya_salio(self):
        """La garantía central: el paciente no recibe dos veces la misma imagen."""
        fallar_en = {"n": 3}
        enviados = []

        def media(clinica, tel, **kw):
            enviados.append(kw["nombre_archivo"])
            if len(enviados) == fallar_en["n"]:
                return {"estado": "fallido", "detalle": "500", "instancia": "i",
                        "external_message_id": "", "error_codigo": "500"}
            return {"estado": "enviado", "detalle": "ok", "instancia": "i",
                    "external_message_id": f"IMG{len(enviados)}"}

        partes, _ = self._enviar(self.imagenes, media=media)
        grupo = partes[0].grupo_envio
        ya_enviadas = enviados[:2]

        # Segundo intento: ahora el proveedor responde bien a todo.
        enviados.clear()
        fallar_en["n"] = 0
        ok = {"estado": "enviado", "detalle": "ok", "instancia": "i"}
        with patch("mensajes.services.enviar_media_evolution",
                   side_effect=lambda c, t, **k: (enviados.append(k["nombre_archivo"])
                                                  or {**ok, "external_message_id": self._id()})), \
             patch("mensajes.services.enviar_evolution",
                   side_effect=lambda *a, **k: {**ok, "external_message_id": self._id()}):
            partes, resumen = services.reintentar_comunicacion(
                self.clinica, grupo, usuario=self.coord, dormir=lambda s: None)

        self.assertEqual(enviados, ["Pieza 2"])        # solo la que faltaba
        for nombre in ya_enviadas:
            self.assertNotIn(nombre, enviados)
        self.assertEqual(resumen["estado"], "enviado")
        self.assertEqual(resumen["enviadas"], 4)

    def test_los_ids_de_las_partes_ya_enviadas_no_cambian(self):
        """Si cambiaran, se perdería el rastro del acuse de WhatsApp."""
        def media(clinica, tel, **kw):
            if kw["nombre_archivo"] == "Pieza 1":
                return {"estado": "fallido", "detalle": "500", "instancia": "i",
                        "external_message_id": "", "error_codigo": "500"}
            return {"estado": "enviado", "detalle": "ok", "instancia": "i",
                    "external_message_id": "ORIGINAL"}

        partes, _ = self._enviar(self.imagenes, media=media)
        grupo, primera = partes[0].grupo_envio, partes[0]
        self.assertEqual(primera.external_message_id, "ORIGINAL")

        nuevo = {"estado": "enviado", "detalle": "ok", "instancia": "i"}
        with patch("mensajes.services.enviar_media_evolution",
                   side_effect=lambda *a, **k: {**nuevo, "external_message_id": self._id()}), \
             patch("mensajes.services.enviar_evolution",
                   side_effect=lambda *a, **k: {**nuevo, "external_message_id": self._id()}):
            services.reintentar_comunicacion(self.clinica, grupo, usuario=self.coord,
                                             dormir=lambda s: None)
        primera.refresh_from_db()
        self.assertEqual(primera.external_message_id, "ORIGINAL")

    def test_sin_imagenes_usa_el_camino_de_siempre(self):
        """Un mensaje de solo texto no cambia: una fila, sin grupo."""
        with patch("mensajes.services.enviar_evolution",
                   return_value={"estado": "enviado", "detalle": "ok", "instancia": "i",
                                 "external_message_id": "T1"}):
            partes, resumen = services.enviar_comunicacion(
                self.clinica, telefono=self.paciente.telefono, texto="Solo texto",
                tipo=Mensaje.Tipo.CONTINUIDAD, paciente=self.paciente,
                usuario=self.coord, sede="piura")
        self.assertEqual(len(partes), 1)
        self.assertIsNone(partes[0].grupo_envio)
        self.assertEqual(resumen["estado"], "enviado")

    def test_la_pausa_entre_partes_se_respeta(self):
        """Sin pausa, WhatsApp puede mostrar las imágenes desordenadas."""
        pausas = []
        ok = {"estado": "enviado", "detalle": "ok", "instancia": "i"}
        with patch("mensajes.services.enviar_media_evolution",
                   side_effect=lambda *a, **k: {**ok, "external_message_id": self._id()}), \
             patch("mensajes.services.enviar_evolution",
                   side_effect=lambda *a, **k: {**ok, "external_message_id": self._id()}):
            services.enviar_comunicacion(
                self.clinica, telefono=self.paciente.telefono, texto="Hola",
                tipo=Mensaje.Tipo.CONTINUIDAD, materiales=self.imagenes,
                paciente=self.paciente, usuario=self.coord, sede="piura",
                dormir=pausas.append)
        self.assertEqual(pausas, [services.PAUSA_ENTRE_PARTES] * 3)

    def test_una_pieza_de_otra_clinica_no_se_envia(self):
        from core import contacto_continuidad as cc

        otra = Clinica.objects.create(nombre="Otra", slug="otra2")
        ajena = Material.objects.create(
            clinica=otra, nombre="Ajena", categoria="otros", mime="image/png",
            hash="ajena", archivo="material/clinica_9/x.png")
        elegidas = cc.materiales_validos(self.clinica,
                                         [self.imagenes[0].id, ajena.id])
        self.assertEqual([m.id for m in elegidas], [self.imagenes[0].id])

    def test_se_conserva_el_orden_que_eligio_la_coordinadora(self):
        from core import contacto_continuidad as cc

        al_reves = [m.id for m in reversed(self.imagenes)]
        self.assertEqual([m.id for m in cc.materiales_validos(self.clinica, al_reves)],
                         al_reves)

    def test_no_se_repite_la_misma_imagen(self):
        from core import contacto_continuidad as cc

        uno = self.imagenes[0].id
        self.assertEqual([m.id for m in cc.materiales_validos(self.clinica, [uno, uno, uno])],
                         [uno])

    def test_hay_tope_de_imagenes_por_comunicacion(self):
        from core import contacto_continuidad as cc

        muchas = [m.id for m in self.imagenes] * 10
        elegidas = cc.materiales_validos(self.clinica, muchas)
        self.assertLessEqual(len(elegidas), mat.MAX_POR_COMUNICACION)

    def test_el_historial_muestra_una_comunicacion_no_cuatro(self):
        from core import contacto_continuidad as cc
        from pacientes.models import GestionContinuidad

        # La gestión se crea directamente: aquí se prueba cómo se agrupa el
        # historial, no cómo se detecta el caso (eso vive en su propio módulo).
        gestion = GestionContinuidad.objects.create(
            clinica=self.clinica, paciente=self.paciente,
            tipo=GestionContinuidad.Tipo.values[0], meta=6)
        partes, _ = self._enviar(self.imagenes, texto="Hola")
        Mensaje.objects.filter(id__in=[p.id for p in partes]).update(
            gestion_continuidad=gestion)

        filas = cc.contactos_de(gestion)
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]["resumen"]["total"], 4)
        self.assertEqual(len(filas[0]["imagenes"]), 3)
        self.assertEqual(filas[0]["texto"], "Hola")
        self.assertFalse(filas[0]["puede_reintentar"])

    def test_una_comunicacion_a_medias_no_se_informa_como_enviada(self):
        from core import contacto_continuidad as cc

        def media(clinica, tel, **kw):
            if kw["nombre_archivo"] == "Pieza 2":
                return {"estado": "fallido", "detalle": "500", "instancia": "i",
                        "external_message_id": "", "error_codigo": "500"}
            return {"estado": "enviado", "detalle": "ok", "instancia": "i",
                    "external_message_id": self._id()}

        partes, resumen = self._enviar(self.imagenes, media=media)
        salida = cc._resultado_de(partes, resumen)
        self.assertEqual(salida["estado"], "fallido")
        self.assertEqual(salida["comunicacion"], "parcial")
        self.assertIn("2 de 4", salida["detalle"])


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class EndpointDelCompositorTests(TestCase):
    """El camino real: la pantalla manda ids de la biblioteca al endpoint.

    Nunca sale nada a la red: el proveedor está simulado en las dos pruebas.
    """

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_TMP, ignore_errors=True)

    def setUp(self):
        from django.utils import timezone

        from pacientes.models import Cita

        self.clinica = Clinica.objects.create(nombre="Ítaca", slug="itaca3")
        set_clinica_actual(self.clinica)
        InstanciaEvolution.objects.create(
            clinica=self.clinica, sede="piura", nombre_instancia="conversemospiura",
            entorno=InstanciaEvolution.Entorno.OFICIAL, activo=True)
        self.coord = Usuario.objects.create_user(
            email="c3@itaca.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.ADMIN, nombre="Yazmín", sede="piura")
        self.paciente = Paciente.objects.create(
            clinica=self.clinica, nombre="Paciente Caso", telefono="987654321",
            sede="piura")
        # Tres sesiones asistidas y sin próxima cita: la condición "riesgo S3",
        # que es la que hace que el caso exista en la cola.
        ahora = timezone.now()
        for n in (1, 2, 3):
            Cita.objects.create(
                clinica=self.clinica, paciente=self.paciente, sede="piura", n_sesion=n,
                inicio=ahora - timezone.timedelta(days=30 - n * 7),
                estado=Cita.Estado.ATENDIDA, especialidad="Psicología")
        self.imagenes = [self._material(f"Pieza {i}") for i in range(3)]
        self.client.force_login(self.coord)
        self.n = 0

    def _material(self, nombre):
        contenido = png(120, 90)
        m = Material(clinica=self.clinica, nombre=nombre, categoria="otros",
                     mime="image/png", tamano=len(contenido), ancho=120, alto=90,
                     hash=nombre)
        m.archivo.save(f"{nombre}.png", io.BytesIO(contenido), save=False)
        m.save()
        return m

    def _id(self):
        self.n += 1
        return f"WA{self.n:04d}"

    def _ok(self, *a, **k):
        return {"estado": "enviado", "detalle": "ok", "instancia": "conversemospiura",
                "external_message_id": self._id()}

    def _url(self, sufijo=""):
        return f"/api/continuidad/caso/{self.paciente.id}/whatsapp/{sufijo}"

    def test_el_endpoint_envia_las_imagenes_en_el_orden_pedido(self):
        enviadas = []

        def media(clinica, tel, **kw):
            enviadas.append(kw["nombre_archivo"])
            return self._ok()

        orden = [self.imagenes[2].id, self.imagenes[0].id, self.imagenes[1].id]
        with patch("mensajes.services.enviar_media_evolution", side_effect=media), \
             patch("mensajes.services.enviar_evolution", side_effect=self._ok), \
             patch("mensajes.services._dormir", lambda s: None):
            r = self.client.post(self._url(), {"texto": "Hola", "materiales": orden},
                                 content_type="application/json")

        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertEqual(enviadas, ["Pieza 2", "Pieza 0", "Pieza 1"])
        envio = r.json()["envio"]
        self.assertEqual(envio["estado"], "enviado")
        self.assertEqual((envio["resumen"]["enviadas"], envio["resumen"]["total"]), (4, 4))

    def test_el_endpoint_informa_el_fallo_parcial_y_el_reintento_completa(self):
        def media(clinica, tel, **kw):
            if kw["nombre_archivo"] == "Pieza 1":
                return {"estado": "fallido", "detalle": "Evolution respondió 500",
                        "instancia": "i", "external_message_id": "", "error_codigo": "500"}
            return self._ok()

        with patch("mensajes.services.enviar_media_evolution", side_effect=media), \
             patch("mensajes.services.enviar_evolution", side_effect=self._ok), \
             patch("mensajes.services._dormir", lambda s: None):
            r = self.client.post(
                self._url(), {"texto": "Hola",
                              "materiales": [m.id for m in self.imagenes]},
                content_type="application/json")

        envio = r.json()["envio"]
        self.assertEqual(envio["comunicacion"], "parcial")
        self.assertEqual((envio["resumen"]["enviadas"], envio["resumen"]["total"]), (1, 4))
        self.assertTrue(envio["grupo"])
        # La primera parte salió: en el reintento no puede volver a mandarse.
        ya_salio = [p["material_nombre"] for p in envio["partes"] if p["enviada"]]
        self.assertEqual(ya_salio, ["Pieza 0"])

        reenviadas = []
        with patch("mensajes.services.enviar_media_evolution",
                   side_effect=lambda c, t, **k: (reenviadas.append(k["nombre_archivo"])
                                                  or self._ok())), \
             patch("mensajes.services.enviar_evolution", side_effect=self._ok), \
             patch("mensajes.services._dormir", lambda s: None):
            r2 = self.client.post(self._url("reintentar/"), {"grupo": envio["grupo"]},
                                  content_type="application/json")

        self.assertEqual(r2.status_code, 200, r2.content[:300])
        self.assertEqual(reenviadas, ["Pieza 1", "Pieza 2"])   # nunca "Pieza 0"
        self.assertEqual(r2.json()["envio"]["resumen"]["enviadas"], 4)

    def test_el_reintento_rechaza_un_grupo_que_no_existe(self):
        r = self.client.post(self._url("reintentar/"), {"grupo": "no-es-un-uuid"},
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_el_psicologo_no_puede_enviar_por_este_camino(self):
        """Contactar pacientes es de coordinación y gerencia, no del clínico."""
        psico = Usuario.objects.create_user(
            email="p3@itaca.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.MEDICO, nombre="Psicóloga", sede="piura")
        self.client.force_login(psico)
        r = self.client.post(self._url(), {"texto": "Hola",
                                           "materiales": [self.imagenes[0].id]},
                             content_type="application/json")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(Mensaje.objects.count(), 0)
