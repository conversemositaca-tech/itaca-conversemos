"""Regresión de los riesgos P0-S de la auditoría Software Factory (1 oct 2026).

Cada clase fija un riesgo cerrado; si alguno vuelve a abrirse, el CI falla.

    python manage.py test core.tests_seguridad_p0
"""
import json
import shutil
import subprocess
import sys
import tempfile
from unittest import mock

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings

from core.models import Clinica
from mensajes.models import Mensaje
from pacientes.models import Adjunto, Consentimiento, Paciente
from usuarios.models import Profesional, Usuario


class _Clinica(TestCase):
    """Una clínica con un usuario por rol y dos pacientes: uno del psicólogo
    `psico` y otro del psicólogo `otro_psico`."""

    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-p0s")
        crear = Usuario.objects.create_user
        self.admin = crear(email="admin@p0s.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ADMIN)
        self.asistente = crear(email="asis@p0s.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ASISTENTE)
        self.comercial = crear(email="com@p0s.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.COMERCIAL)
        self.analista = crear(email="ana@p0s.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ANALISTA)
        self.psico = crear(email="psico@p0s.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.MEDICO,
                           telefono="987000111")
        self.otro_psico = crear(email="psico2@p0s.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.MEDICO)
        self.ficha = Profesional.objects.create(clinica=self.clinica, usuario=self.psico, nombre="Psico Uno")
        self.otra_ficha = Profesional.objects.create(clinica=self.clinica, usuario=self.otro_psico, nombre="Psico Dos")
        self.mio = Paciente.objects.create(clinica=self.clinica, nombre="Ana Mía", profesional=self.ficha,
                                           telefono="987222333")
        self.ajeno = Paciente.objects.create(clinica=self.clinica, nombre="Luis Ajeno", profesional=self.otra_ficha,
                                             telefono="987444555")

    def como(self, usuario):
        self.client.force_login(usuario)
        return self.client


_MEDIA = tempfile.mkdtemp(prefix="itaca-p0s-")


@override_settings(MEDIA_ROOT=_MEDIA)
class AdjuntosClinicosTests(_Clinica):
    """P0-S1: nadie descarga adjuntos clínicos fuera de su alcance."""

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.adj_mio = Adjunto.objects.create(
            clinica=self.clinica, paciente=self.mio, nombre="eco.pdf", tipo="pdf",
            archivo=SimpleUploadedFile("eco.pdf", b"%PDF-mio"))
        self.adj_ajeno = Adjunto.objects.create(
            clinica=self.clinica, paciente=self.ajeno, nombre="lab.pdf", tipo="pdf",
            archivo=SimpleUploadedFile("lab.pdf", b"%PDF-ajeno"))

    def _ids(self, usuario):
        r = self.como(usuario).get("/api/adjuntos/")
        self.assertEqual(r.status_code, 200)
        return {a["id"] for a in r.json()}

    def test_comercial_no_ve_ni_descarga_ninguno(self):
        self.assertEqual(self._ids(self.comercial), set())
        for adj in (self.adj_mio, self.adj_ajeno):
            self.assertEqual(self.client.get(f"/api/adjuntos/{adj.id}/descargar/").status_code, 404)
            self.assertEqual(self.client.get(f"/api/adjuntos/{adj.id}/").status_code, 404)

    def test_psicologo_solo_los_de_sus_pacientes(self):
        self.assertEqual(self._ids(self.psico), {self.adj_mio.id})
        self.assertEqual(self.client.get(f"/api/adjuntos/{self.adj_ajeno.id}/descargar/").status_code, 404)
        r = self.client.get(f"/api/adjuntos/{self.adj_mio.id}/descargar/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(b"".join(r.streaming_content), b"%PDF-mio")

    def test_psicologo_no_borra_el_de_otro(self):
        self.como(self.psico)
        self.assertEqual(self.client.delete(f"/api/adjuntos/{self.adj_ajeno.id}/").status_code, 404)
        self.assertTrue(Adjunto.objects.filter(pk=self.adj_ajeno.pk).exists())

    def test_subir_queda_dentro_del_alcance(self):
        archivo = SimpleUploadedFile("x.pdf", b"%PDF", content_type="application/pdf")
        r = self.como(self.psico).post("/api/adjuntos/", {"archivo": archivo, "paciente": self.ajeno.id})
        self.assertEqual(r.status_code, 400)
        archivo = SimpleUploadedFile("x.pdf", b"%PDF", content_type="application/pdf")
        r = self.como(self.comercial).post("/api/adjuntos/", {"archivo": archivo, "paciente": self.mio.id})
        self.assertEqual(r.status_code, 403)

    def test_coordinacion_y_admin_conservan_el_acceso(self):
        for u in (self.admin, self.asistente):
            self.assertEqual(self._ids(u), {self.adj_mio.id, self.adj_ajeno.id})


class TokensDeConsentimientoTests(_Clinica):
    """P0-S2: el token de firma solo llega a quien envía el enlace."""

    def setUp(self):
        super().setUp()
        self.doc_ajeno = Consentimiento.objects.create(
            clinica=self.clinica, paciente=self.ajeno, texto="t", token=Consentimiento.nuevo_token())

    def test_crear_como_psicologo_no_devuelve_el_token(self):
        r = self.como(self.psico).post("/api/consentimientos/", {"paciente": self.mio.id},
                                       content_type="application/json")
        self.assertIn(r.status_code, (200, 201))
        self.assertEqual(r.json()["token"], "")
        self.assertEqual(r.json()["url"], "")

    def test_psicologo_no_genera_ni_lista_los_de_pacientes_ajenos(self):
        r = self.como(self.psico).post("/api/consentimientos/", {"paciente": self.ajeno.id},
                                       content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.client.get(f"/api/consentimientos/?paciente={self.ajeno.id}").json(), [])

    def test_comercial_no_recibe_ninguno(self):
        self.assertEqual(self.como(self.comercial).get("/api/consentimientos/").json(), [])

    def test_coordinacion_si_recibe_el_enlace_para_enviarlo(self):
        r = self.como(self.asistente).post("/api/consentimientos/", {"paciente": self.mio.id},
                                           content_type="application/json")
        self.assertTrue(r.json()["token"])
        self.assertTrue(r.json()["url"].startswith("/consentimiento/"))

    def test_la_bitacora_de_mensajes_no_filtra_el_enlace(self):
        texto = f"Léelo aquí: https://x.pe/consentimiento/{self.doc_ajeno.token}"
        Mensaje.objects.create(clinica=self.clinica, paciente=self.mio, telefono="51987222333", texto=texto)
        Mensaje.objects.create(clinica=self.clinica, paciente=self.ajeno, telefono="51987444555", texto=texto)

        filas = self.como(self.psico).get("/api/mensajes/").json()
        self.assertEqual([f["paciente"] for f in filas], [self.mio.id])
        self.assertNotIn(self.doc_ajeno.token, json.dumps(filas))
        self.assertEqual(filas[0]["telefono"], "")

        filas = self.como(self.comercial).get("/api/mensajes/").json()
        self.assertNotIn(self.doc_ajeno.token, json.dumps(filas))

        filas = self.como(self.asistente).get("/api/mensajes/").json()
        self.assertIn(self.doc_ajeno.token, json.dumps(filas))


