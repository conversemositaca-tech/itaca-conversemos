"""Pruebas del rol `analista` (Dirección Clínica / experiencia del paciente).

Es un rol de SOLO LECTURA: ve pacientes y alertas de ambas sedes, los
indicadores de Gerencia/Ocupación y las cifras de Finanzas, pero no escribe
nada, no envía mensajes y no ve el contacto de los pacientes. El guard central
vive en core/permisos.py y se engancha en settings.REST_FRAMEWORK.

    python manage.py test usuarios
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from core.models import Clinica
from finanzas.models import Cobro, Egreso, Servicio
from leads.models import Lead
from pacientes.models import Cita, Paciente
from usuarios.models import Profesional, Usuario


class _Base(TestCase):
    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-analista")
        self.admin = Usuario.objects.create_user(
            email="gerencia-a@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ADMIN,
        )
        self.coord_lima = Usuario.objects.create_user(
            email="ayvi-a@test.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.ASISTENTE, sede=Usuario.Sede.LIMA,
        )
        self.analista = Usuario.objects.create_user(
            email="mirai@test.pe", password="clave-larga", clinica=self.clinica,
            rol=Usuario.Rol.ANALISTA, sede="",  # sede vacía = ambas sedes
        )
        self.lima = Paciente.objects.create(
            clinica=self.clinica, nombre="Paciente de Lima", sede="lima", n_sesion=3,
            frecuencia="semanal", telefono="999111222", email="lima@test.pe",
            direccion="Av. Larco 123", numero_documento="12345678",
            tutor_nombre="Mamá de Lima", tutor_telefono="988777666", tutor_documento="87654321",
        )
        self.piura = Paciente.objects.create(
            clinica=self.clinica, nombre="Paciente de Piura", sede="piura", n_sesion=3,
            frecuencia="semanal", telefono="977333444",
        )
        self.cita = Cita.objects.create(
            clinica=self.clinica, paciente=self.lima,
            inicio=timezone.now() - timedelta(days=1), estado=Cita.Estado.ATENDIDA,
        )
        self.cobro = Cobro.objects.create(
            clinica=self.clinica, paciente=self.lima, concepto="Sesión",
            monto=Decimal("120"), estado=Cobro.Estado.PENDIENTE,
        )
        self.egreso = Egreso.objects.create(
            clinica=self.clinica, concepto="Luz", monto=Decimal("50"),
            categoria=Egreso.Categoria.OTRO,
        )

    def _como_analista(self):
        self.client.force_login(self.analista)


class GuardDeEscrituraTests(_Base):
    """Toda escritura devuelve 403, aunque el endpoint no chequee rol por sí mismo."""

    def _post(self, url, data=None):
        return self.client.post(url, data or {}, content_type="application/json")

    def _patch(self, url, data=None):
        return self.client.patch(url, data or {}, content_type="application/json")

    def test_pacientes_y_citas(self):
        self._como_analista()
        antes = Paciente.objects.count()
        self.assertEqual(self._post("/api/pacientes/", {"nombre": "Nuevo"}).status_code, 403)
        self.assertEqual(self._patch(f"/api/pacientes/{self.lima.id}/", {"nombre": "Otro"}).status_code, 403)
        self.assertEqual(self._post(f"/api/pacientes/{self.lima.id}/mensaje/", {"texto": "hola"}).status_code, 403)
        self.assertEqual(self._post("/api/citas/", {"pacienteId": self.lima.id, "hora": "10:00"}).status_code, 403)
        self.assertEqual(self._patch(f"/api/citas/{self.cita.id}/", {"notas": "x"}).status_code, 403)
        for accion in ("estado", "cancelar", "mover", "confirmar", "recordar", "atender"):
            self.assertEqual(self._post(f"/api/citas/{self.cita.id}/{accion}/", {"estado": "asistio"}).status_code, 403, accion)
        self.assertEqual(self.client.delete(f"/api/citas/{self.cita.id}/").status_code, 403)
        self.assertEqual(Paciente.objects.count(), antes)
        self.lima.refresh_from_db()
        self.assertEqual(self.lima.nombre, "Paciente de Lima")

    def test_dinero(self):
        self._como_analista()
        self.assertEqual(self._post("/api/cobros/", {"monto": 10}).status_code, 403)
        self.assertEqual(self._post(f"/api/cobros/{self.cobro.id}/marcar_pagado/", {"medio_pago": "yape"}).status_code, 403)
        self.assertEqual(self._post("/api/paquetes/", {"paciente": self.lima.id}).status_code, 403)
        self.assertEqual(self._post("/api/egresos/", {"concepto": "x", "monto": 5}).status_code, 403)
        self.assertEqual(self._post("/api/servicios/", {"nombre": "x"}).status_code, 403)
        self.cobro.refresh_from_db()
        self.assertEqual(self.cobro.estado, Cobro.Estado.PENDIENTE)

    def test_captacion_agenda_y_configuracion(self):
        self._como_analista()
        antes = Paciente.objects.count()
        self.assertEqual(self._post("/api/leads/", {"nombre": "Lead"}).status_code, 403)
        self.assertEqual(self._patch("/api/leads/999999/", {"estado": "ganado"}).status_code, 403)
        self.assertEqual(self._post("/api/bloqueos/", {}).status_code, 403)
        self.assertEqual(self._post("/api/sugerencias/", {"texto": "idea"}).status_code, 403)
        self.assertEqual(self._patch("/api/clinica/", {"nombre": "Otra"}).status_code, 403)
        self.assertEqual(self._post("/api/eliminaciones/revisar-todas/").status_code, 403)
        self.assertEqual(self._post("/api/usuarios/", {"email": "x@x.pe"}).status_code, 403)
        self.assertEqual(Paciente.objects.count(), antes)


class LoginSigueFuncionandoTests(_Base):
    """El guard no debe romper login/logout/me/cambio de contraseña."""

    def test_login_me_cambiar_password_logout(self):
        r = self.client.post("/api/auth/login/", {"email": "mirai@test.pe", "password": "clave-larga"},
                             content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["rol"], "analista")

        r = self.client.get("/api/auth/me/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["autenticado"])
        self.assertIn("csrftoken", r.cookies)

        r = self.client.post("/api/auth/cambiar-password/", {"actual": "clave-larga", "nueva": "otra-clave-larga"},
                             content_type="application/json")
        self.assertEqual(r.status_code, 200)

        self.assertEqual(self.client.post("/api/auth/logout/").status_code, 204)


class LecturasConcedidasTests(_Base):
    def test_indicadores_y_finanzas(self):
        self._como_analista()
        r = self.client.get("/api/gerencia/resumen/", {"periodo": "mes"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("operacion", r.json())
        self.assertIn("captacion", r.json())
        for sede in ("lima", "piura", ""):
            self.assertEqual(self.client.get("/api/gerencia/resumen/", {"sede": sede}).status_code, 200, sede)
        self.assertEqual(self.client.get("/api/ocupacion/").status_code, 200)
        self.assertEqual(self.client.get("/api/metricas/").status_code, 200)
        self.assertEqual(self.client.get("/api/reportes-semanales/").status_code, 200)
        r = self.client.get("/api/finanzas/caja/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("utilidad", r.json())
        self.assertEqual(self.client.get("/api/egresos/").status_code, 200)
        self.assertEqual(self.client.get("/api/cobros/resumen/").status_code, 200)
        self.assertEqual(self.client.get("/api/leads/").status_code, 200)
        self.assertEqual(self.client.get("/api/nps/").status_code, 200)

    def test_pacientes_de_ambas_sedes(self):
        self._como_analista()
        r = self.client.get("/api/pacientes/")
        self.assertEqual(r.status_code, 200)
        nombres = {p["nombre"] for p in r.json()}
        self.assertIn("Paciente de Lima", nombres)
        self.assertIn("Paciente de Piura", nombres)
        self.assertEqual(self.client.get(f"/api/pacientes/{self.piura.id}/").status_code, 200)
        self.assertEqual(self.client.get("/api/citas/").status_code, 200)


class LecturasDenegadasTests(_Base):
    def test_lo_que_no_es_su_area(self):
        self._como_analista()
        self.assertEqual(self.client.get("/api/finanzas/liquidacion/").status_code, 403)
        self.assertEqual(self.client.get("/api/espacios/consultorios/").status_code, 403)
        self.assertEqual(self.client.get("/api/usuarios/").status_code, 403)
        self.assertEqual(self.client.get("/api/captacion/config/").status_code, 403)
        # La bitácora de mensajes (trae teléfonos) y los contratos llegan vacíos.
        self.assertEqual(self.client.get("/api/mensajes/").json(), [])
        self.assertEqual(self.client.get("/api/documentos-legales/").json(), [])


class HoyPayloadTests(_Base):
    def test_forma_exacta_para_la_analista(self):
        self._como_analista()
        r = self.client.get("/api/hoy/").json()
        self.assertIn("ingresos_hoy", r)
        self.assertIn("pendiente_hoy", r)
        self.assertNotIn("eliminaciones", r)          # auditoría: solo gerencia
        self.assertNotIn("eliminaciones_total", r)
        self.assertIn("recordatorios", r)
        self.assertEqual(r["meta"]["sede"], "")        # meta TOTAL, no por sede
        self.assertEqual(r["meta"]["sede_label"], "Total")
        self.assertNotIn("metas", r)
        self.assertFalse(r["es_admin"])
        self.assertTrue(r["ve_dinero"])
        # Ambas sedes en las alertas de continuidad.
        nombres = {x["nombre"] for x in r["riesgo_abandono"]}
        self.assertIn("Paciente de Lima", nombres)
        self.assertIn("Paciente de Piura", nombres)

    def test_los_roles_existentes_no_cambian(self):
        self.client.force_login(self.admin)
        r = self.client.get("/api/hoy/").json()
        self.assertIn("metas", r)
        self.assertIn("eliminaciones", r)
        self.assertTrue(r["es_admin"])

        self.client.force_login(self.coord_lima)
        r = self.client.get("/api/hoy/").json()
        self.assertEqual(r["meta"]["sede"], "lima")
        self.assertNotIn("ingresos_hoy", r)
        self.assertFalse(r["ve_dinero"])
        self.assertNotIn("Paciente de Piura", {x["nombre"] for x in r["riesgo_abandono"]})


class PrivacidadTests(_Base):
    CAMPOS = ("tel", "email", "direccion", "numero_documento", "tutor_telefono", "tutor_documento")

    def test_la_analista_no_ve_contacto(self):
        self._como_analista()
        d = self.client.get(f"/api/pacientes/{self.lima.id}/").json()
        for k in self.CAMPOS:
            self.assertEqual(d[k], "", k)
        self.assertEqual(d["nombre"], "Paciente de Lima")
        self.assertEqual(d["tutor_nombre"], "Mamá de Lima")
        self.assertEqual(d["sede"], "lima")
        fila = [p for p in self.client.get("/api/pacientes/").json() if p["id"] == self.lima.id][0]
        self.assertEqual(fila["tel"], "")
        self.assertEqual(fila["numero_documento"], "")

    def test_la_coordinadora_sigue_viendo_contacto(self):
        self.client.force_login(self.coord_lima)
        d = self.client.get(f"/api/pacientes/{self.lima.id}/").json()
        self.assertEqual(d["tel"], "999111222")
        self.assertEqual(d["numero_documento"], "12345678")


class ViasAlternasCerradasTests(_Base):
    """Rodeos que la revisión adversarial encontró y que quedaron cerrados:
    el mismo dato enmascarado en un endpoint no puede salir por otro."""

    def setUp(self):
        super().setUp()
        self.prof = Profesional.objects.create(
            clinica=self.clinica, nombre="Ángelo Villa", dni="44556677",
            porcentaje_liquidacion=Decimal("40"),
        )
        self.servicio = Servicio.objects.create(
            clinica=self.clinica, nombre="Terapia individual",
            precio=Decimal("120"), monto_terapeuta=Decimal("60"),
        )
        self.lead = Lead.objects.create(
            clinica=self.clinica, nombre="WhatsApp 961211614", telefono="961211614",
            email="lead@test.pe",
        )

    def test_consentimientos_no_se_entregan(self):
        """Cada fila traía el token de firma: con él se leía el documento del
        paciente por el endpoint público y hasta se podía firmar en su nombre."""
        self._como_analista()
        r = self.client.get("/api/consentimientos/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [])

    def test_profesionales_sin_datos_laborales(self):
        self._como_analista()
        fila = [p for p in self.client.get("/api/profesionales/").json() if p["id"] == self.prof.id][0]
        self.assertEqual(fila["nombre"], "Ángelo Villa")     # lo público del directorio sigue
        self.assertIsNone(fila["dni"])
        self.assertIsNone(fila["porcentaje_liquidacion"])
        self.assertIsNone(fila["contrato_vencimiento"])
        self.assertEqual(fila["documentos"], [])
        # Control: gerencia lo sigue viendo completo.
        self.client.force_login(self.admin)
        fila = [p for p in self.client.get("/api/profesionales/").json() if p["id"] == self.prof.id][0]
        self.assertEqual(fila["dni"], "44556677")

    def test_servicios_sin_pago_al_terapeuta(self):
        """Con monto_terapeuta y la ocupación se reconstruía la liquidación."""
        self._como_analista()
        fila = [s for s in self.client.get("/api/servicios/").json() if s["id"] == self.servicio.id][0]
        self.assertEqual(float(fila["precio"]), 120.0)
        self.assertIsNone(fila["monto_terapeuta"])
        self.client.force_login(self.coord_lima)
        fila = [s for s in self.client.get("/api/servicios/").json() if s["id"] == self.servicio.id][0]
        self.assertEqual(float(fila["monto_terapeuta"]), 60.0)

    def test_lead_de_whatsapp_no_cuela_el_telefono_por_el_nombre(self):
        self._como_analista()
        fila = [l for l in self.client.get("/api/leads/").json() if l["id"] == self.lead.id][0]
        self.assertEqual(fila["telefono"], "")
        self.assertEqual(fila["email"], "")
        self.assertEqual(fila["nombre"], "Lead de WhatsApp")
        # La coordinadora lo sigue viendo tal cual.
        self.client.force_login(self.coord_lima)
        fila = [l for l in self.client.get("/api/leads/").json() if l["id"] == self.lead.id][0]
        self.assertEqual(fila["nombre"], "WhatsApp 961211614")
        self.assertEqual(fila["telefono"], "961211614")

    def test_el_buscador_de_leads_no_es_un_oraculo(self):
        """Buscar por dígitos o por correo revelaría, fila a fila, el contacto
        que el serializer acaba de enmascarar."""
        self._como_analista()
        self.assertEqual(self.client.get("/api/leads/", {"q": "961211614"}).json(), [])
        self.assertEqual(self.client.get("/api/leads/", {"q": "lead@test.pe"}).json(), [])
        # Por nombre sí (es lo que ve en pantalla).
        self.assertEqual(len(self.client.get("/api/leads/", {"q": "WhatsApp"}).json()), 1)
        # La coordinadora conserva el buscador completo.
        self.client.force_login(self.coord_lima)
        self.assertEqual(len(self.client.get("/api/leads/", {"q": "961211614"}).json()), 1)
