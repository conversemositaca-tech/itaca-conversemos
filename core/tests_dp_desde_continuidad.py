"""Registrar el cierre desde el Centro de Continuidad cierra el caso de verdad.

Lo que se protege: que el DP se escriba en la cita correcta y que la alerta se
apague sola. Si se escribiera en otra sesión, el bloque seguiría reclamando y
coordinación aprendería a ignorar los avisos — que es exactamente el problema
que esto viene a resolver.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core import continuidad
from core.models import Clinica
from pacientes.models import Cita, Paciente
from usuarios.models import Profesional, Usuario


class RegistrarElCierreTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clinica = Clinica.objects.create(nombre="Ítaca", ciudad="Piura",
                                             slug="itaca-dp", token_captacion="tok-dp")
        cls.coord = Usuario.objects.create_user(
            email="coord@dp.pe", password="clave-larga-1", nombre="Coord",
            rol=Usuario.Rol.ASISTENTE, clinica=cls.clinica)
        cls.psico = Usuario.objects.create_user(
            email="psi@dp.pe", password="clave-larga-1", nombre="Psi",
            rol=Usuario.Rol.MEDICO, clinica=cls.clinica)
        Profesional.objects.create(clinica=cls.clinica, nombre="Psi",
                                   usuario=cls.psico, sede="piura", activo=True)

    def setUp(self):
        self.paciente = Paciente.objects.create(
            clinica=self.clinica, nombre="Ana Ruiz", sede="piura")
        # Siete sesiones asistidas: el cierre 6 quedó atrás sin decisión.
        base = timezone.now() - timedelta(days=90)
        self.citas = []
        for i in range(1, 8):
            self.citas.append(Cita.objects.create(
                clinica=self.clinica, paciente=self.paciente, medico=self.psico,
                inicio=base + timedelta(days=i * 7), estado="asistio", n_sesion=i))

    def _citas_dict(self):
        return list(Cita.objects.filter(paciente=self.paciente, estado="asistio")
                    .values("id", "n_sesion", "inicio", "estado", "decision",
                            "decision_registrada_en", "decision_registrada_por__nombre")
                    .order_by("inicio"))

    def test_el_cierre_apunta_a_la_sesion_6_y_no_a_otra(self):
        cierres = continuidad.cierres_del_proceso(self._citas_dict(), 7, None)
        self.assertEqual(len(cierres), 1)
        self.assertEqual(cierres[0]["meta"], 6)
        self.assertEqual(cierres[0]["cita_id"], self.citas[5].id)  # la sesión 6

    def test_coordinacion_registra_el_dp_en_esa_cita(self):
        cita_6 = self.citas[5]
        self.client.force_login(self.coord)
        r = self.client.patch(f"/api/citas/{cita_6.id}/", {"decision": "DP-08"},
                              content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content[:200])
        cita_6.refresh_from_db()
        self.assertEqual(cita_6.decision, "DP-08")

    def test_queda_firmado_quien_y_cuando(self):
        # Sin esto no se puede saber quién cerró un bloque ni cuánto tardó.
        cita_6 = self.citas[5]
        self.client.force_login(self.coord)
        self.client.patch(f"/api/citas/{cita_6.id}/", {"decision": "DP-09"},
                          content_type="application/json")
        cita_6.refresh_from_db()
        self.assertEqual(cita_6.decision_registrada_por, self.coord)
        self.assertIsNotNone(cita_6.decision_registrada_en)

    def test_el_psicologo_no_registra_decisiones(self):
        # Es de coordinación por diseño: el psicólogo no sabe si la persona
        # renovó o no, eso se habla por teléfono.
        cita_6 = self.citas[5]
        self.client.force_login(self.psico)
        self.client.patch(f"/api/citas/{cita_6.id}/", {"decision": "DP-08"},
                          content_type="application/json")
        cita_6.refresh_from_db()
        self.assertEqual(cita_6.decision, "")

    def test_registrado_el_dp_el_cierre_deja_de_estar_pendiente(self):
        # La prueba de que sirve: la lista lo refleja sin que nadie más toque nada.
        cita_6 = self.citas[5]
        self.client.force_login(self.coord)
        self.client.patch(f"/api/citas/{cita_6.id}/", {"decision": "DP-10"},
                          content_type="application/json")
        cierres = continuidad.cierres_del_proceso(self._citas_dict(), 7, None)
        self.assertEqual(cierres[0]["decision"], "DP-10")
        self.assertEqual(cierres[0]["decision_por"], "Coord")

    def test_quitar_la_decision_tambien_se_puede(self):
        # Si alguien se equivoca de código tiene que poder corregirlo.
        cita_6 = self.citas[5]
        self.client.force_login(self.coord)
        self.client.patch(f"/api/citas/{cita_6.id}/", {"decision": "DP-08"},
                          content_type="application/json")
        self.client.patch(f"/api/citas/{cita_6.id}/", {"decision": ""},
                          content_type="application/json")
        cita_6.refresh_from_db()
        self.assertEqual(cita_6.decision, "")
        self.assertIsNone(cita_6.decision_registrada_en)
