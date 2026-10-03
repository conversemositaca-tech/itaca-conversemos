"""Fase 1: auditoría de acciones sensibles, IA que no pisa texto clínico
escrito por personas, paquete que descuenta una sola vez y respaldo que
cubre toda app con modelos.

    python manage.py test core.tests_auditoria_ia_respaldo
"""
from datetime import timedelta
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from core.models import Clinica, RegistroAuditoria
from core.respaldo import APPS
from finanzas.models import Paquete
from pacientes.models import Cita, Paciente, SugerenciaRiesgo
from usuarios.models import Profesional, Usuario


class _Base(TestCase):
    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="fase1-aud")
        crear = Usuario.objects.create_user
        self.admin = crear(email="a@f1.pe", password="x", clinica=self.clinica, rol="admin")
        self.coord = crear(email="c@f1.pe", password="x", clinica=self.clinica, rol="asistente")
        self.psico = crear(email="p@f1.pe", password="x", clinica=self.clinica, rol="medico", telefono="987000222")
        ficha = Profesional.objects.create(clinica=self.clinica, usuario=self.psico, nombre="P")
        self.paciente = Paciente.objects.create(clinica=self.clinica, nombre="Ana", profesional=ficha)
        self.cita = Cita.objects.create(clinica=self.clinica, paciente=self.paciente, medico=self.psico,
                                        inicio=timezone.now() + timedelta(days=1))

    def como(self, u):
        self.client.force_login(u)
        return self.client


class AuditoriaTests(_Base):
    def test_cancelar_y_cambiar_estado_de_cita_quedan_auditados(self):
        self.como(self.coord).post(f"/api/citas/{self.cita.id}/estado/", {"estado": "confirmada"},
                                   content_type="application/json")
        self.client.post(f"/api/citas/{self.cita.id}/cancelar/")
        regs = list(RegistroAuditoria.objects.filter(accion="cita.estado", objeto_id=str(self.cita.id))
                    .order_by("creado_en").values_list("cambios", flat=True))
        self.assertEqual([r["estado"][1] for r in regs], ["confirmada", "cancelada"])
        self.assertTrue(all(r.actor_id == self.coord.id for r in RegistroAuditoria.objects.filter(accion="cita.estado")))

    def test_resolver_riesgo_queda_auditado(self):
        s = SugerenciaRiesgo.objects.create(clinica=self.clinica, paciente=self.paciente, valor_sugerido="alto")
        self.como(self.psico).post(f"/api/sugerencias-riesgo/{s.id}/resolver/", {"decision": "confirmar"},
                                   content_type="application/json")
        reg = RegistroAuditoria.objects.get(accion="riesgo.resolver")
        self.assertEqual((reg.actor_id, reg.cambios["riesgo"]), (self.psico.id, ["", "alto"]))

    def test_cambio_de_rol_queda_auditado(self):
        self.como(self.admin).patch(f"/api/usuarios/{self.coord.id}/", {"rol": "analista"},
                                    content_type="application/json")
        reg = RegistroAuditoria.objects.get(accion="usuario.permisos")
        self.assertEqual(reg.cambios["rol"], ["asistente", "analista"])

    def test_la_auditoria_no_guarda_secretos(self):
        from core.auditoria import auditar
        r = auditar(self.admin, "x", self.paciente, {"token": ["a", "b"], "api_password": [1, 2], "nombre": ["a", "b"]})
        self.assertEqual(list(r.cambios), ["nombre"])


class IANoPisaTextoHumanoTests(_Base):
    URL = "/api/integraciones/nota-voz/"

    def _nota(self, resumen, objetivos):
        with self.settings(ITACA_INTEGRACION_TOKEN="t", ITACA_TOKEN_ELI=""):
            return self.client.post(self.URL, {
                "telefono": "51987000222", "paciente_id": self.paciente.id, "tipo": "historia",
                "campos": {"resumen": resumen, "objetivos": objetivos, "riesgo": ""},
            }, content_type="application/json", HTTP_X_INTEGRACION_TOKEN="t")

    def test_completa_campos_vacios(self):
        self.assertEqual(self._nota("Consulta por ansiedad", "Dormir mejor").status_code, 201)
        self.paciente.refresh_from_db()
        self.assertEqual((self.paciente.resumen_clinico, self.paciente.objetivo_principal),
                         ("Consulta por ansiedad", "Dormir mejor"))

    def test_no_pisa_lo_que_escribio_el_psicologo(self):
        self.paciente.resumen_clinico = "Escrito por la psicóloga"
        self.paciente.objetivo_principal = "Objetivo acordado"
        self.paciente.save()
        self._nota("Otro resumen de la IA", "Otro objetivo")
        self.paciente.refresh_from_db()
        self.assertEqual((self.paciente.resumen_clinico, self.paciente.objetivo_principal),
                         ("Escrito por la psicóloga", "Objetivo acordado"))
        reg = RegistroAuditoria.objects.get(accion="ia.propuesta_no_aplicada")
        self.assertEqual(reg.cambios["resumen_clinico"][1], "Otro resumen de la IA")


class PaqueteUnaSolaVezTests(_Base):
    def test_marcar_atendida_dos_veces_descuenta_una_sesion(self):
        paq = Paquete.objects.create(clinica=self.clinica, paciente=self.paciente, nombre="4 sesiones",
                                     sesiones_total=4, monto=200)
        c = self.como(self.coord)
        for _ in range(2):
            c.post(f"/api/citas/{self.cita.id}/estado/", {"estado": "atendida"}, content_type="application/json")
        paq.refresh_from_db()
        self.assertEqual(paq.sesiones_usadas, 1)
        c.post(f"/api/citas/{self.cita.id}/cancelar/")
        paq.refresh_from_db()
        self.assertEqual(paq.sesiones_usadas, 0)


class RespaldoCubreTodaAppTests(SimpleTestCase):
    """Una app nueva con modelos (p. ej. `continuidad`) no puede nacer fuera del
    respaldo: la lista APPS de core/respaldo.py tiene que incluirla."""

    def test_toda_app_propia_con_modelos_esta_en_el_respaldo(self):
        raiz = Path(settings.BASE_DIR).resolve()
        propias = [a for a in apps.get_app_configs()
                   if Path(a.path).resolve().parent == raiz and list(a.get_models())]
        faltan = sorted(a.label for a in propias if a.label not in APPS)
        self.assertFalse(faltan, f"Apps con modelos fuera de core/respaldo.APPS: {faltan}")
