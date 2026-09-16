"""Una reserva web entra UNA vez y queda bien puesta en todos lados.

Reportado por Ayvi: alguien reservaba desde la web, la cita aparecía en la
Agenda, Coordinación confirmaba que iniciaba proceso… y la persona no salía en
Pacientes, no entraba en el reporte de captación y seguía figurando como lead
abierto. La salida era borrar la reserva y volver a crearla desde Marketing.

Tres cosas lo causaban:

1. Si el teléfono ya estaba en cualquier ficha, la reserva NO creaba lead: la
   captación no existía para Marketing ni para los reportes.
2. `lead.cita` no se enlazaba nunca, así que editar el lead después creaba una
   SEGUNDA cita.
3. Registrar "DP-01 · Inicia proceso" en la consulta no movía nada fuera de la
   cita: el lead seguía abierto y la ficha, provisional.

    python manage.py test pacientes.tests_reserva_web
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.models import Clinica
from leads.models import Lead
from pacientes.models import Cita, Paciente
from usuarios.models import Profesional, Usuario


class _Base(TestCase):
    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-web")
        self.psico = Usuario.objects.create_user(
            email="psico-web@test.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.MEDICO, nombre="Lic. Ana Torres")
        self.ficha = Profesional.objects.create(
            clinica=self.clinica, usuario=self.psico, nombre="Lic. Ana Torres",
            sede="piura", horario_semanal={"1": [10, 11]})
        self.token = self.clinica.asegurar_token_captacion()
        self.coord = Usuario.objects.create_user(
            email="coord-web@test.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.ASISTENTE)

    def paciente(self, nombre, telefono="", sede="piura", **extra):
        return Paciente.objects.create(clinica=self.clinica, nombre=nombre,
                                       telefono=telefono, sede=sede, **extra)


class IdentidadEnLaReservaWebTests(_Base):
    """A quién se le cuelga la reserva. El teléfono no decide solo."""

    def _match(self, *, nombre, telefono="", documento="", sede="piura"):
        from pacientes.agendamiento import _match_paciente

        return _match_paciente(self.clinica, documento, telefono,
                               nombre=nombre, sede=sede)

    def test_7_mismo_telefono_y_nombre_distinto_no_reutiliza(self):
        """El número de la madre no convierte la reserva del hijo en suya."""
        self.paciente("Rosa Pérez", telefono="987654321")
        self.assertIsNone(self._match(nombre="Mateo Pérez", telefono="987654321"))

    def test_8_dos_fichas_con_el_mismo_numero_no_eligen_ninguna(self):
        self.paciente("Mateo Pérez", telefono="987654321")
        self.paciente("Mateo Pérez", telefono="+51 987 654 321")
        self.assertIsNone(self._match(nombre="Mateo Pérez", telefono="987654321"))

    def test_9_sede_distinta_no_mezcla(self):
        self.paciente("Mateo Pérez", telefono="987654321", sede="lima")
        self.assertIsNone(self._match(nombre="Mateo Pérez", telefono="987654321",
                                      sede="piura"))

    def test_10_un_telefono_corto_no_sirve_para_identificar(self):
        self.paciente("Mateo Pérez", telefono="123")
        self.assertIsNone(self._match(nombre="Mateo Pérez", telefono="123"))

    def test_11_el_documento_exacto_si_identifica(self):
        p = self.paciente("Mateo Pérez", telefono="900000000", numero_documento="70123456")
        self.assertEqual(self._match(nombre="M. Pérez", documento="70123456"), p)

    def test_11b_el_mismo_documento_en_dos_fichas_no_elige(self):
        self.paciente("Mateo Pérez", numero_documento="70123456")
        self.paciente("Mateo Perez", numero_documento="70123456")
        self.assertIsNone(self._match(nombre="Mateo Pérez", documento="70123456"))

    def test_la_misma_persona_si_se_reconoce(self):
        p = self.paciente("MATEO  PÉREZ", telefono="+51 987 654 321")
        self.assertEqual(self._match(nombre="Mateo Pérez", telefono="987654321"), p)


class DP01SincronizaTests(_Base):
    """"Inicia proceso" registrado en la consulta vale también para Marketing."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.coord)

    def _caso(self, *, provisional=True):
        """Una reserva web ya creada: paciente + cita + lead enlazados."""
        paciente = self.paciente("Mateo Pérez", telefono="987654321",
                                 provisional=provisional)
        cita = Cita.objects.create(
            clinica=self.clinica, paciente=paciente, medico=self.psico,
            inicio=timezone.now() - timedelta(days=1), estado=Cita.Estado.ATENDIDA,
            especialidad="Consulta inicial - Adultos", sede="piura", agendado_web=True)
        lead = Lead.objects.create(
            clinica=self.clinica, nombre="Mateo Pérez", telefono="987654321",
            sede="piura", fuente=Lead.Fuente.WEB, es_pauta=True,
            estado=Lead.Estado.AGENDADO, paciente=paciente, cita=cita)
        return paciente, cita, lead

    def _decidir(self, cita, dp):
        return self.client.patch(f"/api/citas/{cita.id}/", {"decision": dp},
                                 content_type="application/json")

    def test_12_dp01_marca_el_lead_como_ganado(self):
        _p, cita, lead = self._caso()
        self.assertEqual(self._decidir(cita, "DP-01").status_code, 200)
        lead.refresh_from_db()
        self.assertEqual(lead.estado, Lead.Estado.GANADO)

    def test_13_dp01_quita_el_provisional(self):
        paciente, cita, _l = self._caso()
        self._decidir(cita, "DP-01")
        paciente.refresh_from_db()
        self.assertFalse(paciente.provisional)

    def test_14_dp01_no_crea_otra_cita(self):
        _p, cita, _l = self._caso()
        self._decidir(cita, "DP-01")
        self.assertEqual(Cita.objects.count(), 1)

    def test_15_dp01_no_crea_otro_paciente(self):
        _p, cita, _l = self._caso()
        self._decidir(cita, "DP-01")
        self.assertEqual(Paciente.objects.count(), 1)

    def test_16_dp01_conserva_la_atribucion(self):
        _p, cita, lead = self._caso()
        self._decidir(cita, "DP-01")
        lead.refresh_from_db()
        self.assertEqual(lead.fuente, Lead.Fuente.WEB)
        self.assertTrue(lead.es_pauta)

    def test_17_dp01_repetido_es_idempotente(self):
        _p, cita, lead = self._caso()
        self._decidir(cita, "DP-01")
        self._decidir(cita, "")
        self._decidir(cita, "DP-01")
        lead.refresh_from_db()
        self.assertEqual(Lead.objects.count(), 1)
        self.assertEqual(Paciente.objects.count(), 1)
        self.assertEqual(lead.estado, Lead.Estado.GANADO)

    def test_18_dp02_no_marca_ganado(self):
        """Pidió tiempo para decidir: todavía no empezó nada."""
        paciente, cita, lead = self._caso()
        self._decidir(cita, "DP-02")
        lead.refresh_from_db()
        paciente.refresh_from_db()
        self.assertEqual(lead.estado, Lead.Estado.AGENDADO)
        self.assertTrue(paciente.provisional)

    def test_19_dp03_no_marca_ganado(self):
        paciente, cita, lead = self._caso()
        self._decidir(cita, "DP-03")
        lead.refresh_from_db()
        paciente.refresh_from_db()
        self.assertEqual(lead.estado, Lead.Estado.AGENDADO)
        self.assertTrue(paciente.provisional)

    def test_20_una_decision_de_cierre_tampoco_convierte(self):
        paciente, cita, lead = self._caso()
        self._decidir(cita, "DP-04")          # no inicia proceso
        lead.refresh_from_db()
        paciente.refresh_from_db()
        self.assertEqual(lead.estado, Lead.Estado.AGENDADO)
        self.assertTrue(paciente.provisional)

    def test_una_cita_sin_lead_detras_no_inventa_uno(self):
        paciente = self.paciente("Sin Lead", telefono="900111222")
        cita = Cita.objects.create(
            clinica=self.clinica, paciente=paciente, medico=self.psico,
            inicio=timezone.now() - timedelta(days=1), estado=Cita.Estado.ATENDIDA,
            especialidad="Consulta inicial - Adultos", sede="piura")
        self._decidir(cita, "DP-01")
        self.assertEqual(Lead.objects.count(), 0)

    def test_25_tras_dp01_el_lead_cuenta_como_cierre(self):
        """Lo que mira el reporte de captación: estado ganado."""
        _p, cita, _l = self._caso()
        self._decidir(cita, "DP-01")
        self.assertEqual(
            Lead.objects.filter(fuente=Lead.Fuente.WEB, estado=Lead.Estado.GANADO).count(), 1)

    def test_28_el_flujo_de_marketing_sigue_funcionando(self):
        """Marcar ganado desde Marketing convierte igual que antes."""
        paciente, _c, lead = self._caso()
        r = self.client.patch(f"/api/leads/{lead.id}/", {"estado": "ganado"},
                              content_type="application/json")
        self.assertEqual(r.status_code, 200)
        paciente.refresh_from_db()
        self.assertFalse(paciente.provisional)

    def test_marketing_no_escribe_una_decision_que_nadie_tomo(self):
        """La sincronización va en una sola dirección, a propósito."""
        _p, cita, lead = self._caso()
        self.client.patch(f"/api/leads/{lead.id}/", {"estado": "ganado"},
                          content_type="application/json")
        cita.refresh_from_db()
        self.assertEqual(cita.decision, "")


class ReservaWebCreaTodoTests(_Base):
    """Una reserva deja SIEMPRE las tres piezas y sus enlaces.

    Antes, si el teléfono ya estaba en alguna ficha, se creaba solo la cita: la
    captación no existía para Marketing. En producción eso dejó ~90 % de las
    reservas web fuera del reporte, en las dos sedes por igual.
    """

    def setUp(self):
        super().setUp()
        # Horario amplio en toda la semana, para que siempre haya un hueco libre.
        self.ficha.horario_semanal = {str(d): [9, 10, 11, 15, 16, 17] for d in range(7)}
        self.ficha.save(update_fields=["horario_semanal"])

    def _un_slot(self):
        r = self.client.get(f"/api/agendamiento/{self.token}/slots/",
                            {"profesional": self.ficha.id, "dias": 14})
        self.assertEqual(r.status_code, 200)
        for dia in r.json()["dias"]:
            if dia["slots"]:
                return dia["slots"][0]["inicio"]
        self.fail("el profesional de prueba no tiene ningún horario libre")

    def _reservar(self, **extra):
        datos = {
            "profesional_id": self.ficha.id, "inicio": self._un_slot(),
            "nombre": "Mateo Pérez", "telefono": "987654321",
            "servicio": "Consulta inicial - Adultos", "modalidad": "presencial",
            "mensaje": "Quiero empezar terapia", **extra,
        }
        return self.client.post(f"/api/agendamiento/{self.token}/reservar/", datos,
                                content_type="application/json")

    # --- 1 a 6 ---------------------------------------------------------

    def test_1_persona_nueva_crea_lead_paciente_y_cita(self):
        self.assertEqual(self._reservar().status_code, 201)
        self.assertEqual(Lead.objects.count(), 1)
        self.assertEqual(Paciente.objects.count(), 1)
        self.assertEqual(Cita.objects.count(), 1)

    def test_2_paciente_existente_tambien_crea_lead(self):
        """El registro de captación no depende de que la persona sea nueva."""
        ya = self.paciente("Mateo Pérez", telefono="987654321")
        self.assertEqual(self._reservar().status_code, 201)
        self.assertEqual(Paciente.objects.count(), 1)          # no se duplica
        self.assertEqual(Cita.objects.get().paciente_id, ya.id)
        self.assertEqual(Lead.objects.count(), 1)              # y SÍ hay captación

    def test_3_el_lead_apunta_al_paciente_correcto(self):
        self._reservar()
        lead = Lead.objects.get()
        self.assertEqual(lead.paciente_id, Cita.objects.get().paciente_id)

    def test_4_el_lead_apunta_a_la_cita_de_la_reserva(self):
        self._reservar()
        self.assertEqual(Lead.objects.get().cita_id, Cita.objects.get().id)

    def test_5_conserva_la_fuente_web(self):
        self._reservar()
        lead = Lead.objects.get()
        self.assertEqual(lead.fuente, Lead.Fuente.WEB)
        self.assertEqual(lead.sede, "piura")
        self.assertTrue(lead.agendo_consulta)

    def test_6_editar_el_lead_despues_no_crea_una_segunda_cita(self):
        """El motivo por el que Coordinación acababa borrando reservas."""
        self._reservar()
        lead = Lead.objects.get()
        self.client.force_login(self.coord)
        r = self.client.patch(f"/api/leads/{lead.id}/", {"observaciones": "llamó para confirmar"},
                              content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Cita.objects.count(), 1)

    # --- identidad en el camino real ------------------------------------

    def test_el_telefono_de_otra_persona_no_se_lleva_la_reserva(self):
        """El caso de la madre y el hijo, ahora en la reserva web."""
        madre = self.paciente("Rosa Pérez", telefono="987654321")
        self._reservar(nombre="Mateo Pérez")
        self.assertEqual(Paciente.objects.count(), 2)
        self.assertNotEqual(Cita.objects.get().paciente_id, madre.id)
        self.assertEqual(madre.citas.count(), 0)

    def test_21_la_reserva_entra_como_consulta_no_como_sesion(self):
        from core import continuidad

        self._reservar()
        cita = Cita.objects.get()
        self.assertTrue(continuidad.es_consulta(cita))

    def test_22_la_agenda_muestra_al_paciente_de_la_reserva(self):
        self._reservar()
        self.client.force_login(self.coord)
        r = self.client.get("/api/citas/")
        filas = r.json()
        filas = filas.get("results", filas) if isinstance(filas, dict) else filas
        self.assertIn("Mateo Pérez", [f.get("paciente") or "" for f in filas])

    def test_24_la_reserva_queda_disponible_para_el_reporte_de_leads(self):
        self._reservar()
        self.assertEqual(Lead.objects.filter(fuente=Lead.Fuente.WEB).count(), 1)

    def test_26_las_dos_sedes_se_comportan_igual(self):
        self.ficha.sede = "lima"
        self.ficha.save(update_fields=["sede"])
        self._reservar()
        lead = Lead.objects.get()
        self.assertEqual(lead.sede, "lima")
        self.assertEqual(lead.fuente, Lead.Fuente.WEB)
        self.assertIsNotNone(lead.cita_id)

    def test_30_dos_reservas_de_la_misma_persona_no_duplican_la_ficha(self):
        self._reservar()
        self._reservar()
        self.assertEqual(Paciente.objects.count(), 1)
        self.assertEqual(Lead.objects.count(), 2)   # dos captaciones, una persona
        self.assertEqual(Cita.objects.count(), 2)
