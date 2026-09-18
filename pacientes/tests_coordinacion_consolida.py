"""Coordinación consolida, y la sede reparte el trabajo sin cerrar puertas.

Dos decisiones que conviene no perder:

- Consolidar elimina la ficha de una persona real. Pasó de gerencia a
  coordinación porque gerencia no entraba a hacerlo y el trabajo se paraba.
- El reparto Piura/Lima es un FILTRO de pantalla, no un permiso. Las dos
  coordinadoras se cubren entre sí: quitarles la otra sede les quitaría media
  operación. Por eso NO se usa `Usuario.sede`, que sí acota de verdad en todas
  las pantallas.
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

    def _usuario(self, rol, nombre="X"):
        return Usuario.objects.create_user(
            email=f"{rol}{nombre}@demo.pe", password="clave-larga-1",
            nombre=nombre, rol=rol, clinica=self.clinica)

    def test_coordinacion_puede(self):
        # El cambio pedido: gerencia no entraba a hacerlo y había 31 grupos
        # esperando. Quien sabe si dos fichas son la misma persona es quien la
        # atiende por teléfono.
        self.assertTrue(permisos.puede_fusionar_pacientes(
            self._usuario("asistente", "Yaz")))

    def test_gerencia_sigue_pudiendo(self):
        self.assertTrue(permisos.puede_fusionar_pacientes(self._usuario("admin")))

    def test_el_psicologo_sigue_fuera(self):
        # Ve solo a sus pacientes y no gestiona identidad.
        self.assertFalse(permisos.puede_fusionar_pacientes(self._usuario("medico")))

    def test_la_analista_sigue_fuera(self):
        # Es solo lectura: no elimina nada.
        self.assertFalse(permisos.puede_fusionar_pacientes(self._usuario("analista")))

    def test_el_comercial_sigue_fuera(self):
        self.assertFalse(permisos.puede_fusionar_pacientes(self._usuario("comercial")))


class LaSedeNoCierraPuertasTests(TestCase):
    """La sede reparte, no bloquea: cualquiera de las dos alcanza ambas."""

    @classmethod
    def setUpTestData(cls):
        cls.clinica = Clinica.objects.create(nombre="Ítaca", ciudad="Piura",
                                             slug="itaca-coord2", token_captacion="tok-coord2")
        cls.yaz = Usuario.objects.create_user(
            email="yaz@demo.pe", password="clave-larga-1", nombre="Yaz",
            rol=Usuario.Rol.ASISTENTE, clinica=cls.clinica)
        cls.piura = Paciente.objects.create(clinica=cls.clinica, nombre="P A", sede="piura")
        cls.lima = Paciente.objects.create(clinica=cls.clinica, nombre="L A", sede="lima")

    def test_una_coordinadora_alcanza_las_dos_sedes(self):
        # Se cubren entre ellas; el reparto lo hace el selector de la pantalla.
        self.assertTrue(permisos.puede_fusionar_pacientes(self.yaz))

    def test_no_se_toca_el_campo_sede_del_usuario(self):
        # `Usuario.sede` acota de verdad en TODAS las pantallas
        # (`pacientes_del_rol`). Usarlo aquí les habría quitado media operación,
        # así que el permiso no depende de él.
        self.assertFalse((self.yaz.sede or "").strip())
        self.assertTrue(permisos.puede_fusionar_pacientes(self.yaz))


class ElFiltroDeSedeTests(TestCase):
    """El selector de la pantalla acota la lista, y solo la lista."""

    @classmethod
    def setUpTestData(cls):
        cls.clinica = Clinica.objects.create(nombre="Ítaca", ciudad="Piura",
                                             slug="itaca-coord3", token_captacion="tok-coord3")
        cls.coord = Usuario.objects.create_user(
            email="coord@demo.pe", password="clave-larga-1", nombre="Coord",
            rol=Usuario.Rol.ASISTENTE, clinica=cls.clinica)
        # Un par claro en cada sede: mismo nombre y mismo teléfono.
        for sede, tel in (("piura", "987111222"), ("lima", "987333444")):
            for i in (1, 2):
                Paciente.objects.create(clinica=cls.clinica, nombre=f"Ana Torres {sede}",
                                        sede=sede, telefono=tel)

    def _pedir(self, sede=""):
        self.client.force_login(self.coord)
        url = "/api/duplicados/?confianza=alta" + (f"&sede={sede}" if sede else "")
        return self.client.get(url).json()

    @staticmethod
    def _sedes(grupos):
        # La sede vive en cada ficha del grupo, no en el grupo.
        return {(f.get("sede") or "") for g in grupos for f in g.get("fichas", [])}

    def test_sin_filtro_llegan_las_dos_sedes(self):
        sedes = self._sedes(self._pedir().get("grupos", []))
        self.assertIn("piura", sedes)
        self.assertIn("lima", sedes)

    def test_filtrando_por_piura_no_salen_los_de_lima(self):
        sedes = self._sedes(self._pedir("piura").get("grupos", []))
        self.assertIn("piura", sedes)
        self.assertNotIn("lima", sedes)

    def test_y_al_reves(self):
        sedes = self._sedes(self._pedir("lima").get("grupos", []))
        self.assertIn("lima", sedes)
        self.assertNotIn("piura", sedes)

    def test_un_filtro_inventado_no_acota_nada(self):
        # Vale más devolver de más que esconder un caso por un typo en la URL.
        todos = len(self._pedir().get("grupos", []))
        self.assertEqual(len(self._pedir("marte").get("grupos", [])), todos)


class LaSesionDiceElPermisoTests(TestCase):
    """La pantalla no deduce quién puede consolidar: se lo pregunta al servidor."""

    @classmethod
    def setUpTestData(cls):
        cls.clinica = Clinica.objects.create(nombre="Ítaca", ciudad="Piura",
                                             slug="itaca-coord4", token_captacion="tok-coord4")

    def _me(self, rol):
        u = Usuario.objects.create_user(
            email=f"me{rol}@demo.pe", password="clave-larga-1",
            nombre="N", rol=rol, clinica=self.clinica)
        self.client.force_login(u)
        return self.client.get("/api/auth/me/").json()

    def test_coordinacion_recibe_el_permiso(self):
        self.assertTrue(self._me(Usuario.Rol.ASISTENTE)["puede_consolidar"])

    def test_gerencia_lo_recibe(self):
        self.assertTrue(self._me(Usuario.Rol.ADMIN)["puede_consolidar"])

    def test_el_psicologo_no(self):
        self.assertFalse(self._me(Usuario.Rol.MEDICO)["puede_consolidar"])
