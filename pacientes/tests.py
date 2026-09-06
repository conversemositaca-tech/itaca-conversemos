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
from io import StringIO

from django.core.management import call_command

from django.test import TestCase
from django.utils import timezone

from core.models import Clinica
from pacientes.models import Cita, Paciente, Tarea
from usuarios.models import Profesional, Usuario


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


class RangoDeAgendaTests(TestCase):
    """La agenda se pide por tramo de fechas.

    Antes `/api/citas/` devolvía la agenda ENTERA de la clínica —incluido todo el
    histórico importado de AgendaPro, con sus cobros— en cada carga de la página.
    La respuesta pesaba tanto que a veces no llegaba, y el equipo reportó que
    "algunos pacientes no aparecen hasta que actualizamos 3-4 veces la página".
    """

    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-rango")
        self.coord = Usuario.objects.create_user(
            email="coord@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ASISTENTE,
        )
        self.psico = Usuario.objects.create_user(
            email="psi@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.MEDICO,
        )
        self.paciente = Paciente.objects.create(clinica=self.clinica, nombre="Ana Pérez")
        self.hoy = timezone.localdate()
        self._cita(self.hoy)                             # hoy
        self._cita(self.hoy - timedelta(days=400))       # histórico viejo
        self._cita(self.hoy + timedelta(days=200))       # muy a futuro
        self.client.force_login(self.coord)

    def _cita(self, fecha):
        return Cita.objects.create(
            clinica=self.clinica, paciente=self.paciente, medico=self.psico,
            inicio=timezone.make_aware(datetime.combine(fecha, time(10, 0))),
            estado=Cita.Estado.AGENDADA, especialidad="Terapia individual",
        )

    def test_el_tramo_pedido_deja_fuera_el_historico(self):
        r = self.client.get("/api/citas/", {
            "desde": (self.hoy - timedelta(days=15)).isoformat(),
            "hasta": (self.hoy + timedelta(days=45)).isoformat(),
        })
        self.assertEqual(r.status_code, 200)
        fechas = [c["fecha"] for c in r.json()]
        self.assertEqual(fechas, [self.hoy.isoformat()])  # solo la de hoy

    def test_se_puede_pedir_el_historico_a_proposito(self):
        r = self.client.get("/api/citas/", {
            "desde": (self.hoy - timedelta(days=500)).isoformat(),
            "hasta": self.hoy.isoformat(),
        })
        self.assertEqual(len(r.json()), 2)  # la vieja y la de hoy

    def test_sin_rango_siguen_saliendo_todas(self):
        """Compatibilidad: quien no manda fechas recibe la agenda completa."""
        self.assertEqual(len(self.client.get("/api/citas/").json()), 3)


class EditarCitaTests(TestCase):
    """Reasignar el psicólogo y numerar la sesión sin borrar la cita.

    Pedido de las coordinadoras: "que se pueda cambiar el psicólogo asignado a
    una cita sin necesidad de eliminarla y crear una nueva", y "que se pueda
    modificar el número de la cita o, en caso de no tenerlo, agregarlo después".
    """

    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-edit")
        self.coord = Usuario.objects.create_user(
            email="coord2@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ASISTENTE,
        )
        self.psico = Usuario.objects.create_user(
            email="p1@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.MEDICO,
        )
        self.otro = Usuario.objects.create_user(
            email="p2@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.MEDICO,
        )
        self.paciente = Paciente.objects.create(clinica=self.clinica, nombre="Ana Pérez", n_sesion=3)
        self.manana = timezone.localdate() + timedelta(days=1)
        self.cita = self._cita("10:00", self.psico)
        self.client.force_login(self.coord)

    def _cita(self, hora, medico, paciente=None):
        h, m = [int(x) for x in hora.split(":")]
        return Cita.objects.create(
            clinica=self.clinica, paciente=paciente or self.paciente, medico=medico,
            inicio=timezone.make_aware(datetime.combine(self.manana, time(h, m))),
            estado=Cita.Estado.AGENDADA, especialidad="Terapia individual",
        )

    def _patch(self, datos):
        return self.client.patch(f"/api/citas/{self.cita.id}/", datos, content_type="application/json")

    def test_cambiar_el_psicologo_de_una_cita(self):
        r = self._patch({"medicoId": self.otro.id})
        self.assertEqual(r.status_code, 200)
        self.cita.refresh_from_db()
        self.assertEqual(self.cita.medico, self.otro)

    def test_no_reasigna_encima_de_otra_cita_del_nuevo_psicologo(self):
        otro_paciente = Paciente.objects.create(clinica=self.clinica, nombre="Luis Gómez")
        self._cita("10:00", self.otro, paciente=otro_paciente)  # el nuevo ya está ocupado
        r = self._patch({"medicoId": self.otro.id})
        self.assertEqual(r.status_code, 409)
        self.cita.refresh_from_db()
        self.assertEqual(self.cita.medico, self.psico)  # se quedó con el suyo

    def test_reasignar_con_sobrecupo_confirmado(self):
        otro_paciente = Paciente.objects.create(clinica=self.clinica, nombre="Luis Gómez")
        self._cita("10:00", self.otro, paciente=otro_paciente)
        r = self._patch({"medicoId": self.otro.id, "forzar": True})
        self.assertEqual(r.status_code, 200)

    def test_poner_el_numero_de_sesion_despues(self):
        r = self._patch({"n_sesion": 7})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["n_sesion"], 7)
        self.assertEqual(r.json()["n_sesion_efectivo"], 7)

    def test_sin_numero_propio_se_muestra_el_del_paciente(self):
        r = self.client.get("/api/citas/")
        cita = r.json()[0]
        self.assertIsNone(cita["n_sesion"])
        self.assertEqual(cita["n_sesion_efectivo"], 3)  # el del paciente

    def test_el_psicologo_no_puede_reasignar_la_cita(self):
        self.client.force_login(self.psico)
        self._patch({"medicoId": self.otro.id})
        self.cita.refresh_from_db()
        self.assertEqual(self.cita.medico, self.psico)  # se ignora, no se reasigna


class FusionarPorTelefonoTests(TestCase):
    """Limpieza de los pacientes repetidos que dejó el doble registro.

    Lo delicado no es fusionar, es NO fusionar de más: en la clínica se atiende a
    menores y madre e hijo comparten celular, así que el mismo número no significa
    la misma persona.
    """

    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Itaca", slug="itaca")
        self.psico = Usuario.objects.create_user(
            email="p9@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.MEDICO,
        )

    def _paciente(self, nombre, telefono, **extra):
        return Paciente.objects.create(clinica=self.clinica, nombre=nombre, telefono=telefono, **extra)

    def _fusionar(self, aplicar=True):
        call_command("fusionar_por_telefono", *(["--aplicar"] if aplicar else []), stdout=StringIO())

    def test_fusiona_a_la_misma_persona_y_le_mueve_todo(self):
        rico = self._paciente("Ana María Pérez Gómez", "987654321")
        pobre = self._paciente("Ana Pérez", "+51 987 654 321", email="ana@correo.pe")
        Cita.objects.create(
            clinica=self.clinica, paciente=pobre, medico=self.psico,
            inicio=timezone.now() + timedelta(days=1), estado=Cita.Estado.AGENDADA,
        )
        # Lo que el comando viejo se llevaba por delante al borrar el duplicado:
        Tarea.objects.create(clinica=self.clinica, paciente=pobre, texto="Traer registro de emociones")

        self._fusionar()

        self.assertEqual(Paciente.objects.count(), 1)
        queda = Paciente.objects.get()
        self.assertEqual(Cita.objects.get().paciente_id, queda.id)
        self.assertEqual(Tarea.objects.get().paciente_id, queda.id)  # NO se borró
        self.assertEqual(queda.email, "ana@correo.pe")           # hereda lo que faltaba
        self.assertEqual(queda.nombre, "Ana María Pérez Gómez")  # y el nombre completo

    def test_no_fusiona_a_madre_e_hijo_con_el_mismo_celular(self):
        self._paciente("Lucía Torres", "987111222")      # hija
        self._paciente("Carmen Sánchez", "987111222")    # mamá, mismo celular
        self._fusionar()
        self.assertEqual(Paciente.objects.count(), 2)

    def test_no_fusiona_el_expediente_de_pareja_con_el_individual(self):
        """'Andrea Zapata y Roy Pozo' es un proceso de pareja, no un duplicado."""
        self._paciente("Andrea Zapata", "987333444")
        self._paciente("Andrea Zapata y Roy Pozo", "987333444")
        self._fusionar()
        self.assertEqual(Paciente.objects.count(), 2)

    def test_sin_aplicar_no_toca_nada(self):
        self._paciente("Ana María Pérez", "987654321")
        self._paciente("Ana Pérez", "987654321")
        self._fusionar(aplicar=False)
        self.assertEqual(Paciente.objects.count(), 2)


class ListaDePacientesLivianaTests(TestCase):
    """La lista no arrastra la historia clínica de los 1.875 pacientes.

    Son ~2 MB en cada carga de la página, y además es información clínica saliendo
    del servidor sin que nadie la esté mirando. Todo eso llega al abrir la ficha.
    """

    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-lista")
        self.coord = Usuario.objects.create_user(
            email="coordl@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ASISTENTE,
        )
        self.paciente = Paciente.objects.create(
            clinica=self.clinica, nombre="Ana Pérez", telefono="987654321",
            direccion="Av. Grau 123", alergias="Ninguna",
            resumen_clinico="Trabaja duelo por pérdida reciente.",
            medicacion_habitual="Sertralina 50mg",
            tutor_nombre="Carmen Sánchez", brujula_plan="Sesiones semanales.",
        )
        self.client.force_login(self.coord)

    def test_la_lista_no_trae_la_historia_clinica(self):
        fila = self.client.get("/api/pacientes/").json()[0]
        for campo in ("resumen_clinico", "medicacion_habitual", "alergias",
                      "brujula_plan", "tutor_nombre", "notas_internas"):
            self.assertNotIn(campo, fila, f"'{campo}' no debería viajar en la lista")

    def test_la_lista_conserva_lo_que_muestran_las_filas_y_el_export(self):
        fila = self.client.get("/api/pacientes/").json()[0]
        for campo in ("id", "nombre", "tel", "sede", "especialidad", "ultima",
                      "proxima", "cuenta", "direccion", "numero_documento", "edad"):
            self.assertIn(campo, fila, f"'{campo}' hace falta en la lista")

    def test_la_ficha_sigue_trayendo_todo(self):
        ficha = self.client.get(f"/api/pacientes/{self.paciente.id}/").json()
        self.assertEqual(ficha["resumen_clinico"], "Trabaja duelo por pérdida reciente.")
        self.assertEqual(ficha["medicacion_habitual"], "Sertralina 50mg")
        self.assertEqual(ficha["tutor_nombre"], "Carmen Sánchez")
        self.assertEqual(ficha["brujula_plan"], "Sesiones semanales.")


class EliminarPacienteTests(TestCase):
    """Quién puede eliminar un paciente.

    Pregunta del equipo: "¿la coordinadora puede eliminar pacientes?". En pantalla
    no hay botón, pero el endpoint aceptaba DELETE de cualquiera con sesión. Las
    citas y los pagos ya estaban protegidos; los pacientes no.
    """

    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-del")
        self.admin = Usuario.objects.create_user(
            email="ger@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ADMIN,
        )
        self.coord = Usuario.objects.create_user(
            email="coordd@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ASISTENTE,
        )
        self.psico = Usuario.objects.create_user(
            email="psicod@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.MEDICO,
        )
        self.paciente = Paciente.objects.create(clinica=self.clinica, nombre="Ana Pérez")

    def _borrar(self, quien):
        self.client.force_login(quien)
        return self.client.delete(f"/api/pacientes/{self.paciente.id}/")

    def test_la_coordinadora_no_puede(self):
        self.assertEqual(self._borrar(self.coord).status_code, 403)
        self.assertEqual(Paciente.objects.count(), 1)

    def test_el_psicologo_tampoco(self):
        self.assertEqual(self._borrar(self.psico).status_code, 403)

    def test_gerencia_si_puede_y_queda_constancia(self):
        from pacientes.models import RegistroEliminacion
        self.assertEqual(self._borrar(self.admin).status_code, 204)
        self.assertEqual(Paciente.objects.count(), 0)
        reg = RegistroEliminacion.objects.get()
        self.assertEqual(reg.tipo, RegistroEliminacion.Tipo.PACIENTE)
        self.assertEqual(reg.paciente_nombre, "Ana Pérez")
        self.assertEqual(reg.usuario, self.admin)


class SincronizarProfesionalAlReasignarCitaTests(TestCase):
    """Al reasignar una cita a otro psicólogo (p. ej. para cubrir una ausencia),
    el paciente debe pasar a figurar a su cargo (Paciente.profesional). Antes
    no se tocaba ese campo: el paciente seguía apareciendo bajo el psicólogo
    anterior y desaparecía del filtro por psicólogo de quien en la práctica lo
    estaba atendiendo (caso real reportado: "Ángelo" psicólogo, no le
    aparecía uno de sus pacientes al filtrar)."""

    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-sync-prof")
        self.coord = Usuario.objects.create_user(
            email="coordsp@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ASISTENTE,
        )
        self.usuario_titular = Usuario.objects.create_user(
            email="titular@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.MEDICO,
        )
        self.usuario_cobertura = Usuario.objects.create_user(
            email="cobertura@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.MEDICO,
        )
        self.ficha_titular = Profesional.objects.create(
            clinica=self.clinica, nombre="Titular", usuario=self.usuario_titular,
        )
        self.ficha_cobertura = Profesional.objects.create(
            clinica=self.clinica, nombre="Ángelo Villa", usuario=self.usuario_cobertura,
        )
        self.paciente = Paciente.objects.create(
            clinica=self.clinica, nombre="Paciente cubierto", profesional=self.ficha_titular,
        )
        self.cita = Cita.objects.create(
            clinica=self.clinica, paciente=self.paciente, medico=self.usuario_titular,
            inicio=timezone.now() + timedelta(days=1), estado=Cita.Estado.AGENDADA,
        )
        self.client.force_login(self.coord)

    def _reasignar(self):
        return self.client.patch(
            f"/api/citas/{self.cita.id}/", {"medicoId": self.usuario_cobertura.id},
            content_type="application/json",
        )

    def test_reasignar_la_cita_actualiza_el_profesional_a_cargo(self):
        r = self._reasignar()
        self.assertEqual(r.status_code, 200)
        self.paciente.refresh_from_db()
        self.assertEqual(self.paciente.profesional_id, self.ficha_cobertura.id)

    def test_el_paciente_aparece_al_filtrar_por_el_nuevo_profesional(self):
        self._reasignar()
        r = self.client.get("/api/pacientes/", {"profesional": self.ficha_cobertura.id})
        self.assertEqual(r.status_code, 200)
        self.assertIn("Paciente cubierto", [p["nombre"] for p in r.json()])

    def test_sin_reasignar_el_profesional_no_cambia(self):
        r = self.client.patch(
            f"/api/citas/{self.cita.id}/", {"notas": "sin cambio de psicólogo"},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        self.paciente.refresh_from_db()
        self.assertEqual(self.paciente.profesional_id, self.ficha_titular.id)


class AlertasContinuidadEnListaTests(TestCase):
    """El filtro "Riesgo S3" / "Fin de bloque" de la pantalla Pacientes se apoya
    en `alertas_continuidad`, que debe viajar en /api/pacientes/ (la lista) y
    no solo en el detalle de la ficha."""

    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-alertas")
        self.admin = Usuario.objects.create_user(
            email="gerencia2@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ADMIN,
        )
        self.client.force_login(self.admin)

    def _lista(self):
        r = self.client.get("/api/pacientes/")
        self.assertEqual(r.status_code, 200)
        return {p["nombre"]: p for p in r.json()}

    def test_paciente_en_riesgo_s3_trae_la_alerta_en_la_lista(self):
        Paciente.objects.create(
            clinica=self.clinica, nombre="En riesgo", n_sesion=3, frecuencia="semanal",
        )
        fila = self._lista()["En riesgo"]
        self.assertIn("riesgo_abandono_s3", fila["alertas_continuidad"])

    def test_paciente_sin_alerta_trae_lista_vacia(self):
        Paciente.objects.create(
            clinica=self.clinica, nombre="Sin alerta", n_sesion=1, frecuencia="semanal",
        )
        fila = self._lista()["Sin alerta"]
        self.assertEqual(fila["alertas_continuidad"], [])
