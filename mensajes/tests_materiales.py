"""Biblioteca de material compartible y envío de varias imágenes.

Lo que se prueba aquí es lo que puede salir caro en producción:

- que una imagen que ya salió NUNCA se reenvíe (el paciente no debe recibir la
  misma pieza dos veces al pulsar "reintentar");
- que una comunicación a medias no se informe como enviada;
- que el archivo se valide por su CONTENIDO, no por su nombre;
- que una pieza de otra clínica no se pueda enviar (Ley 29733).
"""
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


def png(ancho=300, alto=200):
    """Un PNG real y mínimo, con su IHDR bien formado."""
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
    """El tipo y las dimensiones salen del contenido, no del nombre."""

    def test_png_da_tipo_y_medidas(self):
        self.assertEqual(mat.inspeccionar(png(640, 480)[:64]), ("image/png", 640, 480))

    def test_jpeg_se_reconoce(self):
        # SOI + SOF0 con alto 120 y ancho 250.
        jpeg = (b"\xff\xd8\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00" + b"\x00" * 9
                + b"\xff\xc0" + struct.pack(">H", 17) + b"\x08"
                + struct.pack(">HH", 120, 250) + b"\x03" + b"\x00" * 9)
        self.assertEqual(mat.inspeccionar(jpeg[:64]), ("image/jpeg", 250, 120))

    def test_webp_lossy_se_reconoce(self):
        cuerpo = (b"VP8 " + struct.pack("<I", 20) + b"\x00" * 3
                  + b"\x9d\x01\x2a" + struct.pack("<HH", 400, 300))
        webp = b"RIFF" + struct.pack("<I", len(cuerpo) + 4) + b"WEBP" + cuerpo
        self.assertEqual(mat.inspeccionar(webp[:64]), ("image/webp", 400, 300))

    def test_un_pdf_renombrado_a_png_no_pasa(self):
        """Renombrar la extensión no convierte un archivo en imagen."""
        self.assertEqual(mat.inspeccionar(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")[0], None)

    def test_un_script_renombrado_a_jpg_no_pasa(self):
        self.assertEqual(mat.inspeccionar(b"<?php system($_GET['c']); ?>")[0], None)


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
