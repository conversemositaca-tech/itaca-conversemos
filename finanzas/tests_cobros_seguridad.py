"""Cobros: doble cobro, quién cobra, quién corrige, auditoría y aislamiento
entre clínicas (Fase 1 de la Software Factory).

    python manage.py test finanzas.tests_cobros_seguridad
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.models import Clinica, RegistroAuditoria
from finanzas.models import Cobro
from leads.models import Lead
from pacientes.models import Cita, Paciente
from usuarios.models import Profesional, Usuario


class _Base(TestCase):
    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="cobros-seg")
        crear = Usuario.objects.create_user
        self.admin = crear(email="a@c.pe", password="x", clinica=self.clinica, rol="admin")
        self.coord = crear(email="c@c.pe", password="x", clinica=self.clinica, rol="asistente")
        self.psico = crear(email="p@c.pe", password="x", clinica=self.clinica, rol="medico")
        self.otro_psico = crear(email="p2@c.pe", password="x", clinica=self.clinica, rol="medico")
        self.comercial = crear(email="m@c.pe", password="x", clinica=self.clinica, rol="comercial")
        ficha = Profesional.objects.create(clinica=self.clinica, usuario=self.psico, nombre="P1")
        otra = Profesional.objects.create(clinica=self.clinica, usuario=self.otro_psico, nombre="P2")
        self.mio = Paciente.objects.create(clinica=self.clinica, nombre="Ana", profesional=ficha)
        self.ajeno = Paciente.objects.create(clinica=self.clinica, nombre="Luis", profesional=otra)
        self.cita = Cita.objects.create(
            clinica=self.clinica, paciente=self.mio, medico=self.psico,
            inicio=timezone.now() - timedelta(hours=2), estado=Cita.Estado.ATENDIDA)

    def como(self, u):
        self.client.force_login(u)
        return self.client

    def cobrar(self, usuario, **extra):
        cuerpo = {"paciente": self.mio.id, "cita": self.cita.id, "monto": "80", "estado": "pagado",
                  "medio_pago": "efectivo", **extra}
        return self.como(usuario).post("/api/cobros/", cuerpo, content_type="application/json")


class DobleCobroTests(_Base):
    def test_una_cita_no_se_cobra_dos_veces(self):
        self.assertEqual(self.cobrar(self.coord).status_code, 201)
        r = self.cobrar(self.coord)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(Cobro.objects.filter(cita=self.cita).count(), 1)
        self.assertIn("cobro", r.json())

    def test_si_se_anulo_se_puede_volver_a_cobrar(self):
        self.cobrar(self.coord)
        Cobro.objects.filter(cita=self.cita).update(estado=Cobro.Estado.ANULADO)
        self.assertEqual(self.cobrar(self.coord).status_code, 201)

    def test_la_cita_tiene_que_ser_del_paciente(self):
        self.assertEqual(self.cobrar(self.coord, paciente=self.ajeno.id).status_code, 400)

    def test_marcar_pagado_solo_desde_pendiente(self):
        r = self.cobrar(self.coord, estado="pendiente")
        cid = r.json()["id"]
        url = f"/api/cobros/{cid}/marcar_pagado/"
        self.assertEqual(self.client.post(url, {"medio_pago": "yape"}, content_type="application/json").status_code, 200)
        fecha = Cobro.objects.get(pk=cid).fecha
        self.assertEqual(self.client.post(url, {"medio_pago": "yape"}, content_type="application/json").status_code, 409)
        self.assertEqual(Cobro.objects.get(pk=cid).fecha, fecha, "un segundo clic no mueve el ingreso de día")


class QuienCobraTests(_Base):
    def test_psicologo_y_comercial_no_registran_pagos(self):
        self.assertEqual(self.cobrar(self.psico).status_code, 403)
        self.assertEqual(self.cobrar(self.comercial).status_code, 403)

    def test_alcance_de_lectura(self):
        Cobro.objects.create(clinica=self.clinica, paciente=self.mio, monto=10, concepto="a")
        Cobro.objects.create(clinica=self.clinica, paciente=self.ajeno, monto=20, concepto="b")
        self.assertEqual(len(self.como(self.coord).get("/api/cobros/").json()), 2)
        self.assertEqual([c["paciente"] for c in self.como(self.psico).get("/api/cobros/").json()], [self.mio.id])
        self.assertEqual(self.como(self.comercial).get("/api/cobros/").json(), [])

    def test_coordinacion_corrige_descripcion_pero_no_el_monto(self):
        cid = self.cobrar(self.coord).json()["id"]
        url = f"/api/cobros/{cid}/"
        self.assertEqual(self.client.patch(url, {"concepto": "Sesión 4"}, content_type="application/json").status_code, 200)
        self.assertEqual(self.client.patch(url, {"monto": "1"}, content_type="application/json").status_code, 403)
        self.assertEqual(str(Cobro.objects.get(pk=cid).monto), "80.00")

    def test_gerencia_corrige_el_monto_y_queda_auditado(self):
        cid = self.cobrar(self.coord).json()["id"]
        r = self.como(self.admin).patch(f"/api/cobros/{cid}/", {"monto": "70", "paciente": self.ajeno.id},
                                        content_type="application/json")
        self.assertEqual(r.status_code, 200)
        cobro = Cobro.objects.get(pk=cid)
        self.assertEqual((str(cobro.monto), cobro.paciente_id), ("70.00", self.mio.id))
        reg = RegistroAuditoria.objects.get(accion="cobro.editar", objeto_id=str(cid))
        self.assertEqual((reg.actor_id, reg.cambios["monto"]), (self.admin.id, ["80.00", "70.00"]))
        self.assertTrue(RegistroAuditoria.objects.filter(accion="cobro.crear", objeto_id=str(cid)).exists())


class AislamientoEntreClinicasTests(_Base):
    """Un id de otra clínica no se acepta en ningún FK escribible."""

    def setUp(self):
        super().setUp()
        otra = Clinica.objects.create(nombre="Otra", slug="otra-clinica")
        self.paciente_otra = Paciente.objects.create(clinica=otra, nombre="Ajena")
        self.medico_otra = Usuario.objects.create_user(email="x@otra.pe", password="x", clinica=otra, rol="medico")

    def test_cita_no_se_reasigna_a_paciente_ni_psicologo_de_otra_clinica(self):
        c = self.como(self.coord)
        r = c.patch(f"/api/citas/{self.cita.id}/", {"pacienteId": self.paciente_otra.id}, content_type="application/json")
        self.assertEqual(r.status_code, 400)
        r = c.patch(f"/api/citas/{self.cita.id}/", {"medicoId": self.medico_otra.id}, content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.cita.refresh_from_db()
        self.assertEqual((self.cita.paciente_id, self.cita.medico_id), (self.mio.id, self.psico.id))

    def test_lead_no_se_asigna_a_un_psicologo_de_otra_clinica(self):
        lead = Lead.objects.create(clinica=self.clinica, nombre="Interesada")
        r = self.como(self.coord).patch(f"/api/leads/{lead.id}/", {"medico": self.medico_otra.id},
                                        content_type="application/json")
        self.assertEqual(r.status_code, 400)


class EntradaDeCobroTests(_Base):
    """POST /api/cobros/ valida con CobroEntradaSerializer (core.serializadores.validar)."""

    def _post(self, **cuerpo):
        base = {"paciente": self.mio.id, "monto": "80", "estado": "pendiente"}
        return self.como(self.coord).post("/api/cobros/", {**base, **cuerpo}, content_type="application/json")

    def test_acepta_coma_decimal(self):
        r = self._post(monto="80,50")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["monto"], "80.50")

    def test_rechaza_con_mensaje_legible(self):
        casos = [
            ({"monto": "-1"}, "El monto debe ser mayor a 0."),
            ({"monto": "ochenta"}, "Escribe el monto como número"),
            ({"estado": "regalado"}, "estado:"),
            ({"estado": "pagado", "medio_pago": ""}, "Elige el medio de pago."),
        ]
        for cuerpo, texto in casos:
            with self.subTest(cuerpo=cuerpo):
                r = self._post(**cuerpo)
                self.assertEqual(r.status_code, 400)
                self.assertIn(texto, r.json()["detail"])
        self.assertEqual(Cobro.objects.count(), 0)

    def test_paciente_de_otra_clinica_no_existe(self):
        otra = Clinica.objects.create(nombre="Otra", slug="otra-entrada")
        ajena = Paciente.objects.create(clinica=otra, nombre="Ajena")
        r = self._post(paciente=ajena.id)
        self.assertEqual((r.status_code, r.json()["detail"]), (400, "paciente: Paciente no encontrado."))

    def test_solo_caja_vende_paquetes(self):
        cuerpo = {"paciente": self.mio.id, "sesiones_total": 4, "monto": "200"}
        for u in (self.psico, self.comercial):
            r = self.como(u).post("/api/paquetes/", cuerpo, content_type="application/json")
            self.assertEqual(r.status_code, 403)
        r = self.como(self.coord).post("/api/paquetes/", cuerpo, content_type="application/json")
        self.assertEqual(r.status_code, 201)
