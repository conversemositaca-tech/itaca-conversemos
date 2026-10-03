"""Confirmación de reserva web.

La reserva solo PROGRAMA el correo; lo despacha la tarea programada. Así la
petición HTTP nunca espera a Brevo.

    python manage.py test correo.tests.test_reserva
"""
from datetime import date, timedelta
from unittest import mock

from django.test import override_settings
from django.utils import timezone

from leads.models import Lead
from pacientes.models import Cita, Paciente
from pacientes.tests_reserva_web import _Base as BaseReserva

from correo.models import CorreoEnviado, EnvioProgramadoCorreo as EPC
from correo.services import programacion

from .test_servicio import ENCENDIDO, respuesta

FLUJO = dict(ENCENDIDO, CORREO_RESERVA_HABILITADO=True)
POST = "correo.services.brevo.requests.post"


@override_settings(**FLUJO)
class ConfirmacionReservaTests(BaseReserva):
    def setUp(self):
        super().setUp()
        self.ficha.horario_semanal = {str(d): [9, 10, 11, 15, 16, 17] for d in range(7)}
        self.ficha.save(update_fields=["horario_semanal"])

    def _un_slot(self):
        r = self.client.get(f"/api/agendamiento/{self.token}/slots/",
                            {"profesional": self.ficha.id, "dias": 14})
        for dia in r.json()["dias"]:
            if dia["slots"]:
                return dia["slots"][0]["inicio"]
        self.fail("sin horario libre")

    def reservar(self, **extra):
        datos = {"profesional_id": self.ficha.id, "inicio": self._un_slot(),
                 "nombre": "Mateo Pérez", "telefono": "987654321", "email": "mateo@test.pe",
                 "servicio": "Consulta inicial - Adultos", "modalidad": "presencial", **extra}
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(f"/api/agendamiento/{self.token}/reservar/", datos,
                                    content_type="application/json")

    def test_la_peticion_de_reserva_no_llama_a_brevo(self):
        self.paciente("Mateo Pérez", telefono="987654321")
        with mock.patch(POST, return_value=respuesta()) as post:
            r = self.reservar()
        self.assertEqual(r.status_code, 201)
        post.assert_not_called()
        e = EPC.objects.get()
        self.assertEqual((e.estado, e.plantilla_clave), ("PENDIENTE", "reserva_confirmada"))
        self.assertLessEqual(e.ejecutar_en, timezone.now())

    def test_paciente_conocido_recibe_confirmacion_en_el_siguiente_ciclo(self):
        self.paciente("Mateo Pérez", telefono="987654321")
        self.reservar()
        with mock.patch(POST, return_value=respuesta()) as post:
            programacion.procesar_pendientes()
        self.assertEqual(post.call_count, 1)
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["subject"], "Tu reserva está confirmada")
        self.assertEqual(payload["to"][0]["email"], "mateo@test.pe")
        self.assertIn("Av. Bolognesi 582", payload["textContent"])
        self.assertNotIn("headers", payload)  # SERVICE: sin baja de un clic
        fila = CorreoEnviado.objects.get()
        self.assertEqual((fila.categoria, fila.estado, fila.lead), ("SERVICE", "ENVIADO", Lead.objects.get()))

    def test_persona_nueva_recibe_confirmacion_cuando_coordinacion_confirma(self):
        self.reservar()
        self.assertFalse(EPC.objects.exists())  # la cita está "pendiente"
        cita = Cita.objects.get()
        with self.captureOnCommitCallbacks(execute=True):
            cita.estado = Cita.Estado.AGENDADA
            cita.save()
        with self.captureOnCommitCallbacks(execute=True):
            cita.estado = Cita.Estado.CONFIRMADA
            cita.save()
        self.assertEqual(EPC.objects.count(), 1)  # una sola vez por cita
        with mock.patch(POST, return_value=respuesta()) as post:
            programacion.procesar_pendientes()
        self.assertEqual(post.call_count, 1)

    def test_sin_correo_la_reserva_funciona_y_no_se_envia(self):
        self.paciente("Mateo Pérez", telefono="987654321")
        r = self.reservar(email="")
        self.assertEqual(r.status_code, 201)
        with mock.patch(POST, return_value=respuesta()) as post:
            programacion.procesar_pendientes()
        post.assert_not_called()
        self.assertEqual(CorreoEnviado.objects.get().error_codigo, "SIN_CORREO")

    def test_brevo_caido_queda_para_reintento_sin_duplicar(self):
        self.paciente("Mateo Pérez", telefono="987654321")
        self.assertEqual(self.reservar().status_code, 201)
        with mock.patch(POST, return_value=respuesta(503, {})):
            programacion.procesar_pendientes()
        e = EPC.objects.get()
        self.assertEqual((e.estado, e.intentos), ("PENDIENTE", 1))
        EPC.objects.update(ejecutar_en=timezone.now())
        with mock.patch(POST, return_value=respuesta()) as post:
            programacion.procesar_pendientes()
        self.assertEqual(post.call_count, 1)
        self.assertEqual(CorreoEnviado.objects.count(), 1)
        self.assertEqual(CorreoEnviado.objects.get().estado, "ENVIADO")

    def test_excepcion_inesperada_queda_en_error_sin_reintento(self):
        self.paciente("Mateo Pérez", telefono="987654321")
        self.reservar()
        with mock.patch(POST, side_effect=RuntimeError("boom")):
            programacion.procesar_pendientes()
        self.assertEqual(CorreoEnviado.objects.get().error_codigo, "INESPERADO")
        self.assertEqual(EPC.objects.get().estado, "ERROR")

    def test_doble_guardado_no_duplica(self):
        self.paciente("Mateo Pérez", telefono="987654321")
        self.reservar()
        cita = Cita.objects.get()
        for _ in range(3):
            with self.captureOnCommitCallbacks(execute=True):
                cita.save()
        self.assertEqual(EPC.objects.count(), 1)
        with mock.patch(POST, return_value=respuesta()) as post:
            programacion.procesar_pendientes()
            programacion.procesar_pendientes()
        self.assertEqual(post.call_count, 1)

    @override_settings(CORREO_RESERVA_HABILITADO=False)
    def test_bandera_apagada_no_programa(self):
        self.paciente("Mateo Pérez", telefono="987654321")
        self.reservar()
        self.assertFalse(EPC.objects.exists())

    def test_cita_importada_sin_lead_web_no_recibe(self):
        p = self.paciente("Ana Ruiz", telefono="912345678", email="ana@test.pe")
        with self.captureOnCommitCallbacks(execute=True):
            Cita.objects.create(clinica=self.clinica, paciente=p, medico=self.psico,
                                inicio=timezone.now() + timedelta(days=2), agendado_web=True,
                                estado=Cita.Estado.AGENDADA)
        self.assertFalse(EPC.objects.exists())

    def test_virtual_sin_enlace(self):
        self.paciente("Mateo Pérez", telefono="987654321")
        self.reservar(modalidad="virtual")
        with mock.patch(POST, return_value=respuesta()) as post:
            programacion.procesar_pendientes()
        texto = post.call_args.kwargs["json"]["textContent"]
        self.assertIn("Modalidad: Virtual", texto)
        self.assertIn("te enviaremos el enlace antes de la cita", texto)

    def test_menor_conocido_va_al_tutor(self):
        hoy = date.today()
        Paciente.objects.create(clinica=self.clinica, nombre="Mateo Pérez", telefono="987654321",
                                sede="piura", fecha_nacimiento=date(hoy.year - 9, 1, 1),
                                tutor_nombre="Carmen", tutor_correo="carmen@test.pe")
        self.reservar()
        with mock.patch(POST, return_value=respuesta()) as post:
            programacion.procesar_pendientes()
        self.assertEqual(post.call_args.kwargs["json"]["to"][0]["email"], "carmen@test.pe")
