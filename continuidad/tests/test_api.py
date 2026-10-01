"""API y permisos (least privilege: nadie ve ni escribe más que hoy)."""
from continuidad.models import Estado, EventoContinuidad, TipoEvento as T

from .base import REGISTRO_DESDE_SIEMPRE, Base


def url(p, accion="procesos"):
    return f"/api/continuidad/paciente/{p.pk}/{accion}/"


@REGISTRO_DESDE_SIEMPRE
class ApiTests(Base):
    def setUp(self):
        super().setUp()
        self.p = self.paciente(profesional=self.ana, telefono="999888777", email="x@y.pe")
        self.sesiones(self.p, [30, 23])
        self.otro = self.paciente("Otro", profesional=self.beto)
        self.sesiones(self.otro, [30])
        self.proceso(self.p)  # lo que hace la señal de la Agenda al guardar las citas

    def post(self, usuario, p=None, **data):
        self.client.force_login(usuario)
        return self.client.post(url(p or self.p, "transicion"), data, content_type="application/json")

    def test_ver_por_rol(self):
        esperado = {self.admin: 200, self.coord: 200, self.analista: 200, self.u_ana: 200}
        for u, code in esperado.items():
            self.client.force_login(u)
            self.assertEqual(self.client.get(url(self.p)).status_code, code, u.rol)
        comercial = self.usuario("com-c2@test.pe", "comercial")
        self.client.force_login(comercial)
        self.assertEqual(self.client.get(url(self.p)).status_code, 403)
        # El psicólogo solo ve a sus pacientes.
        self.client.force_login(self.u_ana)
        self.assertEqual(self.client.get(url(self.otro)).status_code, 404)

    def test_registrar_por_rol(self):
        datos = dict(evento=T.PAUSA_INICIADA, motivo="VIAJE")
        self.assertEqual(self.post(self.analista, **datos).status_code, 403)  # solo lectura
        self.assertEqual(self.post(self.u_ana, **datos).status_code, 403)     # no registra DP hoy
        self.assertEqual(self.post(self.coord, **datos).status_code, 201)
        self.assertEqual(self.post(self.admin, evento=T.REACTIVACION).status_code, 201)

    def test_coordinacion_de_otra_sede_no_alcanza(self):
        lima = self.usuario("coord-lima@test.pe", "asistente", sede="lima")
        self.assertEqual(self.post(lima, evento=T.PAUSA_INICIADA, motivo="VIAJE").status_code, 404)

    def test_sin_datos_de_contacto_ni_clinicos(self):
        self.client.force_login(self.coord)
        txt = self.client.get(url(self.p)).content.decode()
        for prohibido in ("999888777", "x@y.pe", "diagnostico", "nota"):
            self.assertNotIn(prohibido, txt)

    def test_flujo_completo_e_idempotente(self):
        self.client.force_login(self.coord)
        d = self.client.get(url(self.p)).json()
        proc = d["procesos"][0]
        self.assertEqual(proc["estado_formal"], Estado.ACTIVO)
        self.assertIn(T.PAUSA_INICIADA, [a["tipo"] for a in proc["acciones"]])
        datos = dict(proceso=proc["uuid"], evento=T.PAUSA_INICIADA, motivo="VIAJE",
                     estado_esperado="activo", clave_idempotencia="modal-1")
        r1, r2 = self.post(self.coord, **datos), self.post(self.coord, **datos)
        self.assertEqual((r1.status_code, r2.status_code), (201, 200))
        self.assertTrue(r2.json()["repetido"])
        self.assertEqual(EventoContinuidad.objects.filter(tipo=T.PAUSA_INICIADA).count(), 1)
        historia = r1.json()["procesos"][0]["eventos"]
        self.assertEqual([e["tipo"] for e in historia], [T.INICIO_PROCESO, T.PAUSA_INICIADA])
        self.assertEqual(historia[1]["registrado_por"], self.coord.nombre)
        # Otro formulario abierto con el estado viejo → 409, no pisa.
        r3 = self.post(self.coord, proceso=proc["uuid"], evento=T.ALTA, estado_esperado="activo")
        self.assertEqual(r3.status_code, 409)

    def test_errores_de_validacion_son_400(self):
        self.assertEqual(self.post(self.coord, evento=T.PAUSA_INICIADA).status_code, 400)          # sin motivo
        self.assertEqual(self.post(self.coord, evento=T.PAUSA_INICIADA, motivo="NO_EXISTE").status_code, 400)
        self.assertEqual(self.post(self.coord, evento="inventado").status_code, 400)
        self.assertEqual(self.post(self.coord, evento=T.ALTA, fecha_efectiva="ayer").status_code, 400)
        self.assertEqual(self.post(self.coord, evento=T.CAMBIO_PROFESIONAL, profesional_nuevo=99999).status_code, 400)

    def test_cambio_de_profesional_por_api(self):
        r = self.post(self.coord, evento=T.CAMBIO_PROFESIONAL, profesional_nuevo=self.beto.pk)
        self.assertEqual(r.status_code, 201)
        ev = r.json()["procesos"][0]["eventos"][-1]
        self.assertEqual((ev["profesional_anterior"], ev["profesional_nuevo"]), ("Ana Ruiz", "Beto Paz"))

    def test_motivos_y_profesionales(self):
        self.client.force_login(self.coord)
        d = self.client.get("/api/continuidad/motivos/").json()
        self.assertIn("SIN_INFORMACION", [m["codigo"] for m in d["motivos"]])
        self.assertIn("profesionales", d)
        self.client.force_login(self.analista)
        self.assertNotIn("profesionales", self.client.get("/api/continuidad/motivos/").json())

    def test_revision_solo_gestion(self):
        for u, code in ((self.admin, 200), (self.coord, 200), (self.analista, 200), (self.u_ana, 403)):
            self.client.force_login(u)
            self.assertEqual(self.client.get("/api/continuidad/revision/").status_code, code, u.rol)
