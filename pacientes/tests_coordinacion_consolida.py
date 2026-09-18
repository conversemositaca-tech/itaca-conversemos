"""Coordinación consolida, pero solo en su sede.

Consolidar elimina la ficha de una persona real. Al abrir el permiso a
coordinación, lo que impide que se vaya de las manos es que cada una solo
alcance su sede, y que sin sede asignada no alcance nada. Eso se comprueba en
el SERVIDOR: el endpoint es alcanzable con cualquier sesión que tenga el
permiso, no solo desde el botón de la pantalla.
"""
from django.test import TestCase

from core import permisos
from core.models import Clinica
from pacientes.models import Paciente
from usuarios.models import Usuario


class QuienPuedeConsolidarTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clinica = Clinica.objects.create(nombre="Ítaca", ciudad="Piura",
                                             slug="itaca-coord", token_captacion="tok-coord")

    def _usuario(self, rol, sede="", nombre="X"):
        u = Usuario.objects.create_user(
            email=f"{rol}{sede or 'sin'}{nombre}@demo.pe", password="x",
            nombre=nombre, rol=rol, clinica=self.clinica)
        u.sede = sede
        u.save(update_fields=["sede"])
        return u

    def test_gerencia_consolida_sin_limite_de_sede(self):
        admin = self._usuario("admin")
        self.assertTrue(permisos.puede_fusionar_pacientes(admin))
        self.assertEqual(permisos.sede_que_consolida(admin), "")

    def test_coordinacion_con_sede_si_puede(self):
        # El cambio pedido: gerencia no entraba a hacerlo y el trabajo se paraba.
        coord = self._usuario("asistente", sede="piura", nombre="Yaz")
        self.assertTrue(permisos.puede_fusionar_pacientes(coord))
        self.assertEqual(permisos.sede_que_consolida(coord), "piura")

    def test_coordinacion_SIN_sede_no_puede(self):
        # Así el permiso no alcanza a recepción ni a cuentas de prueba solo por
        # compartir el rol.
        recepcion = self._usuario("asistente", nombre="Recep")
        self.assertFalse(permisos.puede_fusionar_pacientes(recepcion))

    def test_el_psicologo_sigue_fuera(self):
        self.assertFalse(permisos.puede_fusionar_pacientes(self._usuario("medico")))

    def test_la_analista_sigue_fuera(self):
        # Es solo lectura: no elimina nada.
        self.assertFalse(permisos.puede_fusionar_pacientes(self._usuario("analista")))


class SoloFichasDeSuSedeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clinica = Clinica.objects.create(nombre="Ítaca", ciudad="Piura",
                                             slug="itaca-coord2", token_captacion="tok-coord2")
        cls.yaz = Usuario.objects.create_user(
            email="yaz@demo.pe", password="x", nombre="Yaz",
            rol=Usuario.Rol.ASISTENTE, clinica=cls.clinica)
        cls.yaz.sede = "piura"
        cls.yaz.save(update_fields=["sede"])
        cls.ayvi = Usuario.objects.create_user(
            email="ayvi@demo.pe", password="x", nombre="Ayvi",
            rol=Usuario.Rol.ASISTENTE, clinica=cls.clinica)
        cls.ayvi.sede = "lima"
        cls.ayvi.save(update_fields=["sede"])
        cls.admin = Usuario.objects.create_user(
            email="ger@demo.pe", password="x", nombre="Ger",
            rol=Usuario.Rol.ADMIN, clinica=cls.clinica)

        cls.piura_a = Paciente.objects.create(clinica=cls.clinica, nombre="P A", sede="piura")
        cls.piura_b = Paciente.objects.create(clinica=cls.clinica, nombre="P B", sede="piura")
        cls.lima_a = Paciente.objects.create(clinica=cls.clinica, nombre="L A", sede="lima")
        cls.lima_b = Paciente.objects.create(clinica=cls.clinica, nombre="L B", sede="lima")

    def test_cada_una_consolida_lo_suyo(self):
        self.assertTrue(permisos.puede_consolidar_estas_fichas(
            self.yaz, self.piura_a, self.piura_b))
        self.assertTrue(permisos.puede_consolidar_estas_fichas(
            self.ayvi, self.lima_a, self.lima_b))

    def test_ninguna_alcanza_la_sede_de_la_otra(self):
        self.assertFalse(permisos.puede_consolidar_estas_fichas(
            self.yaz, self.lima_a, self.lima_b))
        self.assertFalse(permisos.puede_consolidar_estas_fichas(
            self.ayvi, self.piura_a, self.piura_b))

    def test_un_par_a_caballo_entre_sedes_no_lo_toca_coordinacion(self):
        # Una ficha en cada sede es justo el caso que pide criterio: queda para
        # gerencia, que ve las dos.
        self.assertFalse(permisos.puede_consolidar_estas_fichas(
            self.yaz, self.piura_a, self.lima_a))
        self.assertTrue(permisos.puede_consolidar_estas_fichas(
            self.admin, self.piura_a, self.lima_a))

    def test_gerencia_alcanza_cualquier_sede(self):
        self.assertTrue(permisos.puede_consolidar_estas_fichas(
            self.admin, self.lima_a, self.lima_b))
        self.assertTrue(permisos.puede_consolidar_estas_fichas(
            self.admin, self.piura_a, self.piura_b))


class ElServidorLoHaceCumplirTests(TestCase):
    """No basta con esconder el botón: el endpoint se puede llamar directo."""

    @classmethod
    def setUpTestData(cls):
        cls.clinica = Clinica.objects.create(nombre="Ítaca", ciudad="Piura",
                                             slug="itaca-coord3", token_captacion="tok-coord3")
        cls.yaz = Usuario.objects.create_user(
            email="yaz3@demo.pe", password="clave-larga-1", nombre="Yaz",
            rol=Usuario.Rol.ASISTENTE, clinica=cls.clinica)
        cls.yaz.sede = "piura"
        cls.yaz.save(update_fields=["sede"])
        cls.lima_a = Paciente.objects.create(clinica=cls.clinica, nombre="L A", sede="lima")
        cls.lima_b = Paciente.objects.create(clinica=cls.clinica, nombre="L B", sede="lima")

    def test_consolidar_fichas_de_otra_sede_devuelve_403(self):
        self.client.force_login(self.yaz)
        r = self.client.post("/api/duplicados/fusionar/", {
            "principal": self.lima_a.id, "secundario": self.lima_b.id,
            "confirmar": True, "motivo": "prueba",
        }, content_type="application/json")
        self.assertEqual(r.status_code, 403, r.content[:200])
        # Y sobre todo: no se borró nada.
        self.assertTrue(Paciente.objects.filter(id=self.lima_b.id).exists())


class LaSesionDiceElPermisoTests(TestCase):
    """La pantalla no deduce quién puede consolidar: se lo pregunta al servidor."""

    @classmethod
    def setUpTestData(cls):
        cls.clinica = Clinica.objects.create(nombre="Ítaca", ciudad="Piura",
                                             slug="itaca-coord4", token_captacion="tok-coord4")

    def _me(self, rol, sede=""):
        u = Usuario.objects.create_user(
            email=f"me{rol}{sede or 'sin'}@demo.pe", password="clave-larga-1",
            nombre="N", rol=rol, clinica=self.clinica)
        if sede:
            u.sede = sede
            u.save(update_fields=["sede"])
        self.client.force_login(u)
        return self.client.get("/api/auth/me/").json()

    def test_coordinacion_con_sede_recibe_el_permiso(self):
        self.assertTrue(self._me(Usuario.Rol.ASISTENTE, "piura")["puede_consolidar"])

    def test_coordinacion_sin_sede_no_lo_recibe(self):
        self.assertFalse(self._me(Usuario.Rol.ASISTENTE)["puede_consolidar"])

    def test_gerencia_lo_recibe(self):
        self.assertTrue(self._me(Usuario.Rol.ADMIN)["puede_consolidar"])

    def test_el_psicologo_no(self):
        self.assertFalse(self._me(Usuario.Rol.MEDICO)["puede_consolidar"])
