"""La consulta inicial no es la sesión 1.

Reportado por Coordinación Lima (Ayvi): una persona reservaba por la web, se le
atendía su primera consulta y la agenda ya decía "Sesión N° 1". La consulta es
el paso ANTERIOR —de ella sale el plan de terapia—, dura menos y se liquida
distinto: el equipo la llama "consulta 0".

El fallo no era solo el rótulo. Las consultas casi nunca llevan número (14 de
1496 en la base real), así que caían en el conteo automático de
`resolver_sesion_real` y corrían TODO el proceso en uno: el aviso de abandono de
la sesión 3 saltaba en la 2 y el cierre de bloque de la 6, en la 5.

    python manage.py test core.tests_consulta_no_es_sesion
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core import continuidad as C
from core.models import Clinica
from pacientes.models import Cita, Paciente
from usuarios.models import Usuario

CONSULTA = "Consulta inicial - Adultos"
SESION = "Terapia individual"


class EsConsultaTests(TestCase):
    """Se reconoce por el servicio, el mismo criterio con el que se crea."""

    def test_los_nombres_reales_del_catalogo_se_reconocen(self):
        for nombre in ("Consulta inicial - Adultos",
                       "Consulta inicial - niños/adolescentes",
                       "Consulta inicial - pareja",
                       "Consulta inicial adultos",
                       "CONSULTA INICIAL"):
            self.assertTrue(C.es_consulta({"especialidad": nombre}), nombre)

    def test_una_sesion_no_es_una_consulta(self):
        for nombre in ("Terapia individual", "Sesión individual adulto",
                       "2 sesiones terapia individual adultos", ""):
            self.assertFalse(C.es_consulta({"especialidad": nombre}), nombre)

    def test_una_cita_sin_servicio_cuenta_como_sesion(self):
        """Lo que no consta no se descuenta: casi todo el histórico viene así."""
        self.assertFalse(C.es_consulta({}))
        self.assertEqual(C.cuantas_sesiones([{"especialidad": ""}, {}]), 2)

    def test_el_conteo_descuenta_las_consultas(self):
        citas = [{"especialidad": CONSULTA}, {"especialidad": SESION},
                 {"especialidad": SESION}]
        self.assertEqual(C.cuantas_sesiones(citas), 2)


class ProcesoConConsultaTests(TestCase):
    """El número que ve la agenda y que mueve el Centro de Continuidad."""

    def _cita(self, dia, *, servicio=SESION, n=None, decision=""):
        return {"id": dia, "n_sesion": n, "estado": "atendida", "decision": decision,
                "inicio": timezone.now() - timedelta(days=90 - dia),
                "especialidad": servicio}

    def test_solo_la_consulta_atendida_deja_el_proceso_en_cero(self):
        """El caso reportado: se atiende la consulta y NO hay sesión 1 todavía."""
        self.assertEqual(C.proceso_actual([self._cita(1, servicio=CONSULTA)])["n"], 0)

    def test_consulta_mas_una_sesion_es_la_sesion_1(self):
        citas = [self._cita(1, servicio=CONSULTA), self._cita(2)]
        self.assertEqual(C.proceso_actual(citas)["n"], 1)

    def test_consulta_mas_tres_sesiones_es_la_3_no_la_4(self):
        """Aquí es donde se decide el aviso de riesgo de abandono."""
        citas = [self._cita(1, servicio=CONSULTA)] + [self._cita(i) for i in (2, 3, 4)]
        self.assertEqual(C.proceso_actual(citas)["n"], 3)

    def test_sin_consulta_el_conteo_no_cambia(self):
        citas = [self._cita(i) for i in (1, 2, 3)]
        self.assertEqual(C.proceso_actual(citas)["n"], 3)

    def test_un_numero_escrito_a_mano_sigue_mandando(self):
        """Si alguien numeró la sesión, ese número gana: no se recalcula nada."""
        citas = [self._cita(1, servicio=CONSULTA), self._cita(2, n=7)]
        self.assertEqual(C.proceso_actual(citas)["n"], 7)


class AgendaMuestraConsultaTests(TestCase):
    """Lo que Ayvi ve en la fila de la agenda."""

    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-cons")
        self.coord = Usuario.objects.create_user(
            email="coord-cons@test.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.ASISTENTE)
        self.psico = Usuario.objects.create_user(
            email="psico-cons@test.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.MEDICO)
        self.paciente = Paciente.objects.create(
            clinica=self.clinica, nombre="Persona Nueva", sede="piura", telefono="987000111")
        self.client.force_login(self.coord)

    def _crear(self, servicio, *, estado=Cita.Estado.ATENDIDA, dias=1):
        return Cita.objects.create(
            clinica=self.clinica, paciente=self.paciente, medico=self.psico,
            inicio=timezone.now() - timedelta(days=dias), estado=estado,
            especialidad=servicio, sede="piura", agendado_web=True)

    def _fila(self, cita):
        r = self.client.get("/api/citas/")
        self.assertEqual(r.status_code, 200)
        filas = r.json()
        filas = filas.get("results", filas) if isinstance(filas, dict) else filas
        return next(f for f in filas if f["id"] == cita.id)

    def test_la_consulta_atendida_no_dice_sesion_1(self):
        fila = self._fila(self._crear(CONSULTA))
        self.assertTrue(fila["es_consulta"])
        self.assertEqual(fila["n_sesion_efectivo"], 0)

    def test_la_primera_sesion_despues_de_la_consulta_es_la_1(self):
        self._crear(CONSULTA, dias=8)
        sesion = self._crear(SESION, dias=1)
        fila = self._fila(sesion)
        self.assertFalse(fila["es_consulta"])
        self.assertEqual(fila["n_sesion_efectivo"], 1)

    def test_una_consulta_de_reingreso_tampoco_lleva_numero(self):
        """Ya tuvo sesiones, vuelve con otra consulta: sigue sin ser una sesión."""
        self._crear(SESION, dias=30)
        self._crear(SESION, dias=23)
        fila = self._fila(self._crear(CONSULTA, dias=1))
        self.assertTrue(fila["es_consulta"])
        self.assertEqual(fila["n_sesion_efectivo"], 0)
