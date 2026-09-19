"""La vía "ayúdenme a encontrar al indicado" deja un lead, no una cita.

Antes esa vía compartía pantalla con "quiero elegir yo": filtraba por población
y, si nadie calzaba, mostraba igual a TODO el equipo de la sede. Quien entraba
por ahí porque no sabía a quién elegir terminaba viendo la misma lista que venía
a evitar, y si reservaba, elegía a ciegas.

Ahora recoge preferencias (población, turno, modalidad y si quiere primera
consulta o Sesión Brújula) y deja la asignación en manos de coordinación.

    python manage.py test pacientes.tests_solicitud_web
"""
import json

from django.test import TestCase

from core.models import Clinica
from leads.models import Lead
from pacientes.models import Cita, Paciente


class SolicitudWebTests(TestCase):
    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-solicitud")
        self.token = self.clinica.asegurar_token_captacion()

    def solicitar(self, **extra):
        cuerpo = {
            "sede": "piura", "categoria": "adultos", "turno": "tarde",
            "modalidad": "virtual", "tipo": "consulta",
            "nombre": "Rosa Delgado", "telefono": "987654321",
            "email": "rosa@test.pe", "mensaje": "No sé por dónde empezar.",
        }
        cuerpo.update(extra)
        return self.client.post(
            f"/api/agendamiento/{self.token}/solicitar/",
            data=json.dumps(cuerpo), content_type="application/json")

    def test_deja_lead_y_no_toca_la_agenda(self):
        r = self.solicitar()
        self.assertEqual(r.status_code, 201, r.content)

        lead = Lead.objects.get()
        self.assertEqual(lead.nombre, "Rosa Delgado")
        self.assertEqual(lead.sede, "piura")
        self.assertEqual(lead.fuente, Lead.Fuente.WEB)
        self.assertEqual(lead.estado, Lead.Estado.NUEVO)
        self.assertEqual(lead.tipo_servicio, Lead.TipoServicio.ADULTOS)
        self.assertEqual(lead.modalidad_consulta, "virtual")
        self.assertEqual(lead.motivo_consulta, "No sé por dónde empezar.")
        # No agendó: vino a que le ayuden a elegir.
        self.assertIs(lead.agendo_consulta, False)

        # Lo que importa: nadie ocupó un horario de un psicólogo que aún no se
        # le asigna, y no se abrió ficha de paciente por una llamada pendiente.
        self.assertEqual(Cita.objects.count(), 0)
        self.assertEqual(Paciente.objects.count(), 0)

    def test_la_nota_dice_lo_que_coordinacion_necesita_antes_de_llamar(self):
        self.solicitar()
        notas = Lead.objects.get().notas
        self.assertIn("Primera consulta", notas)
        self.assertIn("adultos", notas)
        self.assertIn("Tarde", notas)
        self.assertIn("Virtual", notas)

    def test_la_brujula_queda_registrada_como_brujula(self):
        self.solicitar(tipo="brujula")
        lead = Lead.objects.get()
        self.assertEqual(lead.especialidad, "Sesión Brújula")
        self.assertIn("Sesión Brújula", lead.notas)

    def test_un_tipo_desconocido_cae_en_primera_consulta(self):
        # Si alguien manipula el formulario, no se inventa un servicio nuevo.
        self.solicitar(tipo="cualquier-cosa")
        self.assertEqual(Lead.objects.get().especialidad, "Primera consulta")

    def test_no_se_duplica_a_quien_ya_escribio(self):
        self.solicitar()
        r = self.solicitar(tipo="brujula")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["duplicado"])
        # Un solo lead, con la segunda visita anotada encima.
        self.assertEqual(Lead.objects.count(), 1)
        self.assertIn("Volvió a solicitar", Lead.objects.get().notas)

    def test_sin_celular_de_nueve_digitos_no_entra(self):
        # Con menos, no hay forma de devolver la llamada, que es todo lo que
        # esta vía promete.
        r = self.solicitar(telefono="4321")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Lead.objects.count(), 0)

    def test_sede_invalida_no_entra(self):
        r = self.solicitar(sede="trujillo")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Lead.objects.count(), 0)

    def test_token_ajeno_no_entra(self):
        r = self.client.post(
            "/api/agendamiento/token-inventado/solicitar/",
            data=json.dumps({"nombre": "X", "telefono": "987654321", "sede": "lima"}),
            content_type="application/json")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(Lead.objects.count(), 0)
