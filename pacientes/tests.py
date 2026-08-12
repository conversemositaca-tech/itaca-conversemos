"""Pruebas de la agenda: choque de horarios y enlace de videollamada.

Los dos casos vienen de correcciones reales que reportó el equipo:

- "El sistema permite agendar a 2 pacientes al mismo tiempo, sin ningún aviso.
  Que no permita." Antes solo se comparaba la hora exacta, así que un cruce de
  10:00 con 10:30 pasaba sin avisar.
- "Colocó virtual y el link de Meet que usamos, pero no redirige." El enlace se
  guardaba sin `https://` y el navegador lo abría como ruta del propio sistema.

    python manage.py test pacientes
"""
from datetime import datetime, time, timedelta

from django.test import TestCase
from django.utils import timezone

from core.models import Clinica
from pacientes.models import Cita, Paciente
from usuarios.models import Usuario


class AgendarCitaTests(TestCase):
    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-test")
        self.coord = Usuario.objects.create_user(
            email="coordinacion@test.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.ASISTENTE,
        )
        self.psico = Usuario.objects.create_user(
            email="psico@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.MEDICO,
        )
        self.otro_psico = Usuario.objects.create_user(
            email="psico2@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.MEDICO,
        )
        self.paciente = Paciente.objects.create(clinica=self.clinica, nombre="Ana Pérez")
        self.otro_paciente = Paciente.objects.create(clinica=self.clinica, nombre="Luis Gómez")
        self.manana = timezone.localdate() + timedelta(days=1)
        self.client.force_login(self.coord)

    # -- utilidades ---------------------------------------------------------
    def _agendar(self, hora, medico=None, paciente=None, **extra):
        return self.client.post(
            "/api/citas/",
            {
                "pacienteId": (paciente or self.paciente).id,
                "medicoId": (medico or self.psico).id,
                "fecha": self.manana.isoformat(),
                "hora": hora,
                "especialidad": "Terapia individual",
                **extra,
            },
            content_type="application/json",
        )

    def _cita_existente(self, hora, medico=None, estado=Cita.Estado.AGENDADA):
        h, m = [int(x) for x in hora.split(":")]
        inicio = timezone.make_aware(datetime.combine(self.manana, time(h, m)))
        return Cita.objects.create(
            clinica=self.clinica, paciente=self.paciente, medico=medico or self.psico,
            inicio=inicio, estado=estado, especialidad="Terapia individual",
        )

    # -- choque de horarios -------------------------------------------------
    def test_no_deja_dos_pacientes_a_la_misma_hora(self):
        self._cita_existente("10:00")
        r = self._agendar("10:00", paciente=self.otro_paciente)
        self.assertEqual(r.status_code, 409)
        self.assertIn("Ana Pérez", r.json()["detail"])  # dice con quién choca
        self.assertEqual(Cita.objects.count(), 1)       # no se creó

    def test_detecta_el_cruce_de_media_hora(self):
        """10:00 y 10:30 se pisan: la sesión dura una hora."""
        self._cita_existente("10:00")
        self.assertEqual(self._agendar("10:30", paciente=self.otro_paciente).status_code, 409)

    def test_se_puede_forzar_el_sobrecupo(self):
        """El paciente ya llegó, o es una doble sesión pactada: se confirma y entra."""
        self._cita_existente("10:00")
        r = self._agendar("10:00", paciente=self.otro_paciente, forzar=True)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Cita.objects.count(), 2)

    def test_otro_psicologo_a_la_misma_hora_si_puede(self):
        self._cita_existente("10:00")
        r = self._agendar("10:00", medico=self.otro_psico, paciente=self.otro_paciente)
        self.assertEqual(r.status_code, 201)

    def test_una_hora_despues_no_choca(self):
        self._cita_existente("10:00")
        self.assertEqual(self._agendar("11:00", paciente=self.otro_paciente).status_code, 201)

    def test_una_cita_cancelada_no_bloquea_el_horario(self):
        self._cita_existente("10:00", estado=Cita.Estado.CANCELADA)
        self.assertEqual(self._agendar("10:00", paciente=self.otro_paciente).status_code, 201)

    def test_mover_una_cita_encima_de_otra_tambien_avisa(self):
        self._cita_existente("10:00")
        movible = self._cita_existente("15:00")
        r = self.client.post(
            f"/api/citas/{movible.id}/mover/",
            {"fecha": self.manana.isoformat(), "hora": "10:00"},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 409)
        movible.refresh_from_db()
        self.assertEqual(timezone.localtime(movible.inicio).hour, 15)  # no se movió

    # -- enlace de videollamada ---------------------------------------------
    def test_el_enlace_se_guarda_con_https(self):
        """Se pega 'meet.google.com/abc' sin esquema y debe quedar abrible."""
        r = self._agendar("09:00", modalidad="virtual", enlace="meet.google.com/abc-defg-hij")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["enlace"], "https://meet.google.com/abc-defg-hij")

    def test_un_enlace_que_ya_trae_https_no_se_toca(self):
        r = self._agendar("09:00", modalidad="virtual", enlace="https://meet.google.com/xyz")
        self.assertEqual(r.json()["enlace"], "https://meet.google.com/xyz")

    def test_una_cita_presencial_no_guarda_enlace(self):
        r = self._agendar("09:00", modalidad="presencial", enlace="meet.google.com/abc")
        self.assertEqual(r.json()["enlace"], "")
