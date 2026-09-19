"""Un colegio que pide información sobre Faro no entra al embudo de pacientes.

Faro es el tamizaje escolar: el cliente es la institución, no una persona que
viene a terapia. Guardar estas solicitudes como `Lead` las metería en la tasa de
cierre, el CAC y el reporte de captación, que se calculan sobre gente que
reserva una consulta. Un colegio que tarda tres meses en firmar un convenio
aparecería como un lead frío y hundiría los números del embudo sin que nadie
entendiera por qué.

    python manage.py test leads.tests_faro
"""
import json

from django.test import TestCase, override_settings

from core.models import Clinica
from leads.models import Lead, SolicitudInstitucional


@override_settings(SITIO_CLINICA_TOKEN="tok-faro")
class FaroTests(TestCase):
    def setUp(self):
        self.clinica = Clinica.objects.create(
            nombre="Ítaca Conversemos", slug="itaca-faro", token_captacion="tok-faro")

    def pedir(self, **extra):
        cuerpo = {
            "institucion": "I.E. San Martín", "responsable": "Ana Chávez",
            "cargo": "Dirección", "estudiantes": "320", "nivel": "secundaria",
            "interes": "tamizaje", "whatsapp": "987654321",
            "correo": "direccion@sanmartin.edu.pe", "mensaje": "Nos interesa para este año.",
        }
        cuerpo.update(extra)
        return self.client.post("/api/sitio/faro/", data=json.dumps(cuerpo),
                                content_type="application/json")

    def test_guarda_la_solicitud_con_lo_que_hace_falta_para_llamar(self):
        r = self.pedir()
        self.assertEqual(r.status_code, 201, r.content)
        s = SolicitudInstitucional.objects.get()
        self.assertEqual(s.institucion, "I.E. San Martín")
        self.assertEqual(s.responsable, "Ana Chávez")
        self.assertEqual(s.estudiantes, 320)
        self.assertEqual(s.nivel, "secundaria")
        self.assertEqual(s.interes, "tamizaje")
        self.assertEqual(s.estado, SolicitudInstitucional.Estado.NUEVA)
        self.assertEqual(s.clinica, self.clinica)

    def test_no_ensucia_el_embudo_de_pacientes(self):
        self.pedir()
        self.assertEqual(Lead.objects.count(), 0)

    def test_sin_institucion_no_entra(self):
        r = self.pedir(institucion="   ")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(SolicitudInstitucional.objects.count(), 0)

    def test_sin_persona_de_contacto_no_entra(self):
        r = self.pedir(responsable="")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(SolicitudInstitucional.objects.count(), 0)

    def test_sin_ningun_canal_de_respuesta_no_entra(self):
        # Sin WhatsApp ni correo la solicitud es un papel sin destinatario.
        r = self.pedir(whatsapp="", correo="")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(SolicitudInstitucional.objects.count(), 0)

    def test_basta_con_uno_de_los_dos_canales(self):
        self.assertEqual(self.pedir(correo="").status_code, 201)
        self.assertEqual(self.pedir(whatsapp="", institucion="I.E. Otro").status_code, 201)
        self.assertEqual(SolicitudInstitucional.objects.count(), 2)

    def test_un_nivel_inventado_se_descarta_en_vez_de_guardarse(self):
        # Si alguien manipula el formulario, el campo queda vacío y no con basura
        # que después rompa los filtros del panel.
        self.pedir(nivel="universidad", interes="otra-cosa")
        s = SolicitudInstitucional.objects.get()
        self.assertEqual(s.nivel, "")
        self.assertEqual(s.interes, "")

    def test_un_numero_de_estudiantes_que_no_es_numero_no_rompe_nada(self):
        for valor in ["muchos", "", "-5", "999999"]:
            SolicitudInstitucional.objects.all().delete()
            r = self.pedir(estudiantes=valor)
            self.assertEqual(r.status_code, 201, valor)
            self.assertIsNone(SolicitudInstitucional.objects.get().estudiantes, valor)

    @override_settings(SITIO_CLINICA_TOKEN="")
    def test_con_una_sola_clinica_funciona_sin_declarar_token(self):
        # Es el caso real hoy: hay una clínica y el sitio la resuelve sola.
        self.assertEqual(self.pedir().status_code, 201)

    @override_settings(SITIO_CLINICA_TOKEN="")
    def test_con_varias_clinicas_y_sin_token_no_se_guarda_nada(self):
        # Aislamiento multitenant: si no se puede saber de quién es el sitio, la
        # solicitud no se guarda en la clínica equivocada. Se rechaza.
        Clinica.objects.create(nombre="Otra clínica", slug="otra", token_captacion="tok-otra")
        r = self.pedir()
        self.assertEqual(r.status_code, 404)
        self.assertEqual(SolicitudInstitucional.objects.count(), 0)
