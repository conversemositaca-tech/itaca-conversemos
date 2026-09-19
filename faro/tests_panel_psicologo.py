"""Quién puede ver los casos del tamizaje escolar, y qué se le exige para cerrarlos.

Faro guarda datos de salud mental de MENORES que confía un colegio. El acceso es
más estrecho que el de cualquier otro módulo del panel: coordinación agenda y
contacta pacientes todo el día, pero no lee el tamizaje de un alumno de
secundaria — no le corresponde y el convenio no lo autoriza.

    python manage.py test faro.tests_panel_psicologo
"""
import json

from django.test import TestCase

from core.models import Clinica
from faro import instrumentos as ins
from faro.models import Alerta, Aplicacion
from faro.registro import registrar
from usuarios.models import Usuario


def contesta(**kw):
    d = {i["id"]: 0 for i in ins.ORDEN}
    d.update(kw)
    return d


class _Base(TestCase):
    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Ítaca", slug="itaca-faro-panelps")
        self.ap = Aplicacion.objects.create(
            clinica=self.clinica, institucion="I.E. San Martín", ciudad="Piura")
        self.resp, self.alerta = registrar(
            self.ap, nombre="Luis Paredes", grado="4.° secundaria", seccion="A",
            respuestas=contesta(asq1=1))

    def usuario(self, rol, correo=None):
        u = Usuario.objects.create_user(
            email=correo or f"{rol}@test.pe", password="x", clinica=self.clinica, rol=rol)
        self.client.force_login(u)
        return u


class PermisosTests(_Base):
    def test_el_psicologo_y_gerencia_entran(self):
        for rol in (Usuario.Rol.MEDICO, Usuario.Rol.ADMIN):
            self.usuario(rol, f"{rol}-ok@test.pe")
            self.assertEqual(self.client.get("/api/faro/panel/alertas/").status_code, 200, rol)

    def test_coordinacion_comercial_y_analista_no_entran(self):
        # No es desconfianza: es que el convenio con el colegio limita quién ve
        # el detalle individual de un menor, y el informe agregado ya cubre lo
        # que esos perfiles necesitan.
        for rol in (Usuario.Rol.ASISTENTE, Usuario.Rol.COMERCIAL, Usuario.Rol.ANALISTA):
            self.usuario(rol, f"{rol}-no@test.pe")
            self.assertEqual(self.client.get("/api/faro/panel/alertas/").status_code, 403, rol)

    def test_sin_sesion_no_se_ve_nada(self):
        self.assertIn(self.client.get("/api/faro/panel/alertas/").status_code, (401, 403))


class AlertasTests(_Base):
    def setUp(self):
        super().setUp()
        self.usuario(Usuario.Rol.MEDICO)

    def test_lista_el_caso_con_lo_que_hace_falta_para_actuar(self):
        d = self.client.get("/api/faro/panel/alertas/").json()
        self.assertEqual(d["pendientes"], 1)
        a = d["alertas"][0]
        self.assertEqual(a["estudiante"], "Luis Paredes")
        self.assertEqual(a["institucion"], "I.E. San Martín")
        self.assertEqual(a["grado"], "4.° secundaria")
        self.assertTrue(a["asq_positivo"])
        self.assertTrue(any("ASQ positivo" in m for m in a["motivos"]))
        self.assertFalse(a["atendida"])

    def test_avisa_cuando_la_alerta_no_llego_a_nadie(self):
        # Sin canal configurado el aviso no salió. Si eso no se ve en el panel,
        # el caso queda esperando a alguien que nunca fue avisado.
        d = self.client.get("/api/faro/panel/alertas/").json()
        self.assertEqual(d["sin_avisar"], 1)
        self.assertEqual(d["alertas"][0]["aviso"], Alerta.Aviso.SIN_CANAL)

    def test_lo_pendiente_va_primero(self):
        self.alerta.atendida = True
        self.alerta.save(update_fields=["atendida"])
        _, nueva = registrar(self.ap, nombre="Ana Ríos", respuestas=contesta(phq9=3))
        d = self.client.get("/api/faro/panel/alertas/").json()
        self.assertEqual(d["alertas"][0]["id"], nueva.id)
        self.assertEqual(d["pendientes"], 1)

    def test_se_puede_filtrar_solo_lo_pendiente(self):
        self.alerta.atendida = True
        self.alerta.save(update_fields=["atendida"])
        d = self.client.get("/api/faro/panel/alertas/?pendientes=1").json()
        self.assertEqual(d["alertas"], [])


class AtenderTests(_Base):
    def setUp(self):
        super().setUp()
        self.yo = self.usuario(Usuario.Rol.MEDICO)
        self.url = f"/api/faro/panel/alertas/{self.alerta.id}/"

    def test_registra_quien_atendio_y_que_hizo(self):
        r = self.client.post(self.url, data=json.dumps(
            {"acciones": "Entrevista de contención. Se llamó a la madre y se derivó a evaluación."}),
            content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content)
        self.alerta.refresh_from_db()
        self.assertTrue(self.alerta.atendida)
        self.assertEqual(self.alerta.atendida_por, self.yo)
        self.assertIsNotNone(self.alerta.atendida_en)
        self.assertIn("contención", self.alerta.acciones)

    def test_no_se_puede_cerrar_sin_decir_que_se_hizo(self):
        # Una casilla marcada no sostiene nada si alguien cuestiona la actuación
        # meses después. El registro es el respaldo del psicólogo, no un trámite.
        for vacio in ["", "   ", "ok"]:
            r = self.client.post(self.url, data=json.dumps({"acciones": vacio}),
                                 content_type="application/json")
            self.assertEqual(r.status_code, 400, repr(vacio))
        self.alerta.refresh_from_db()
        self.assertFalse(self.alerta.atendida)

    def test_una_alerta_de_otra_clinica_no_se_toca(self):
        otra = Clinica.objects.create(nombre="Otra", slug="otra-faro")
        ap2 = Aplicacion.objects.create(clinica=otra, institucion="Ajeno")
        _, ajena = registrar(ap2, nombre="X", respuestas=contesta(asq1=1))
        r = self.client.post(f"/api/faro/panel/alertas/{ajena.id}/",
                             data=json.dumps({"acciones": "intento de acceso cruzado"}),
                             content_type="application/json")
        self.assertEqual(r.status_code, 404)


class CrearAplicacionTests(_Base):
    """Abrir un colegio se hace desde el panel, no desde el admin de Django.

    El admin exige `is_staff`, que abre TODAS las tablas del sistema, y encima
    no filtra por clínica. Pedirle eso a alguien para dar de alta un colegio es
    entregar una llave de servidor por una tarea de rutina.
    """

    def setUp(self):
        super().setUp()
        self.yo = self.usuario(Usuario.Rol.MEDICO)

    def crear(self, **kw):
        cuerpo = {"institucion": "I.E. José Olaya", "ciudad": "Piura"}
        cuerpo.update(kw)
        return self.client.post("/api/faro/panel/aplicaciones/", data=json.dumps(cuerpo),
                                content_type="application/json")

    def test_crea_el_colegio_y_devuelve_sus_dos_enlaces(self):
        r = self.crear(avisar_whatsapp="51983292173", autorizados=40)
        self.assertEqual(r.status_code, 201, r.content)
        d = r.json()
        ap = Aplicacion.objects.get(institucion="I.E. José Olaya")
        self.assertEqual(ap.clinica, self.clinica)
        self.assertEqual(ap.autorizados, 40)
        self.assertEqual(ap.avisar_whatsapp, "51983292173")
        self.assertIn(ap.token_estudiante, d["enlace_estudiante"])
        self.assertIn(ap.token, d["enlace_colegio"])
        self.assertNotEqual(d["enlace_estudiante"], d["enlace_colegio"])

    def test_nace_preparando_si_no_se_dice_otra_cosa(self):
        self.crear()
        self.assertEqual(Aplicacion.objects.get(institucion="I.E. José Olaya").estado,
                         Aplicacion.Estado.PREPARANDO)

    def test_sin_nombre_de_colegio_no_se_crea(self):
        antes = Aplicacion.objects.count()
        for malo in ["", "   ", "IE"]:
            self.assertEqual(self.crear(institucion=malo).status_code, 400, repr(malo))
        self.assertEqual(Aplicacion.objects.count(), antes)

    def test_un_estado_inventado_no_pasa(self):
        self.assertEqual(self.crear(estado="lo_que_sea").status_code, 400)

    def test_los_totales_tienen_que_ser_numeros(self):
        self.assertEqual(self.crear(autorizados="cuarenta").status_code, 400)

    def test_coordinacion_no_puede_abrir_colegios(self):
        self.usuario(Usuario.Rol.ASISTENTE, "asis-crea@test.pe")
        self.assertEqual(self.crear().status_code, 403)


class ResultadosTests(_Base):
    def setUp(self):
        super().setUp()
        self.usuario(Usuario.Rol.MEDICO)
        registrar(self.ap, nombre="Ana Ríos", grado="3.° secundaria",
                  respuestas=contesta(gad1=3, gad2=3, gad3=3, gad4=1))
        registrar(self.ap, nombre="Sofía Vera", grado="3.° secundaria", respuestas=contesta())

    def test_entrega_la_hoja_con_una_fila_por_estudiante(self):
        d = self.client.get(f"/api/faro/panel/resultados/{self.ap.id}/").json()
        self.assertEqual(d["institucion"], "I.E. San Martín")
        self.assertEqual(d["totales"], {"evaluados": 3, "rojo": 1, "ambar": 1,
                                        "verde": 1, "incompletos": 0})
        nombres = [f["estudiante"] for f in d["filas"]]
        self.assertEqual(sorted(nombres), ["Ana Ríos", "Luis Paredes", "Sofía Vera"])

    def test_cada_fila_explica_por_que_quedo_en_ese_nivel(self):
        d = self.client.get(f"/api/faro/panel/resultados/{self.ap.id}/").json()
        rojo = next(f for f in d["filas"] if f["nivel"] == "rojo")
        self.assertIn("ASQ positivo", rojo["motivos"])

    def test_una_aplicacion_de_otra_clinica_no_se_ve(self):
        otra = Clinica.objects.create(nombre="Otra", slug="otra-faro-res")
        ap2 = Aplicacion.objects.create(clinica=otra, institucion="Ajeno")
        self.assertEqual(
            self.client.get(f"/api/faro/panel/resultados/{ap2.id}/").status_code, 404)
