"""Pruebas de las alertas de continuidad (riesgo de abandono en S3, fin de
bloque de sesiones sin decisión) y de su exposición en /api/hoy/.

    python manage.py test core
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from core.continuidad import (
    FIN_BLOQUE_SIN_DECISION, RIESGO_ABANDONO_S3, evaluar, proxima_meta,
)
from core.models import Clinica
from pacientes.models import Cita, Paciente
from usuarios.models import Usuario


class ProximaMetaTests(TestCase):
    def test_sin_total_fijado_cuenta_de_6_en_6(self):
        self.assertEqual(proxima_meta(5, 0), 6)
        self.assertEqual(proxima_meta(11, 0), 12)

    def test_con_total_fijado_apunta_al_total(self):
        self.assertEqual(proxima_meta(7, 8), 8)

    def test_una_vez_superado_el_total_sigue_contando_de_6_en_6(self):
        """Antes del fix, pasado el total fijado el aviso no volvía nunca más
        (el caso 'Juanito': confirma seguir tras su bloque de 6)."""
        self.assertEqual(proxima_meta(7, 6), 12)
        self.assertEqual(proxima_meta(12, 6), 12)
        self.assertEqual(proxima_meta(13, 6), 18)


class EvaluarTests(TestCase):
    def test_riesgo_abandono_en_sesion_3_sin_proxima(self):
        self.assertEqual(
            evaluar(3, 0, tiene_proxima=False, ultima_decision="", frecuencia="semanal"),
            [RIESGO_ABANDONO_S3],
        )

    def test_sesion_3_con_proxima_no_es_riesgo(self):
        self.assertEqual(
            evaluar(3, 0, tiene_proxima=True, ultima_decision="", frecuencia="semanal"), [],
        )

    def test_fin_de_bloque_sin_decision(self):
        self.assertEqual(
            evaluar(6, 6, tiene_proxima=True, ultima_decision="", frecuencia="semanal"),
            [FIN_BLOQUE_SIN_DECISION],
        )

    def test_fin_de_bloque_con_decision_ya_registrada_no_avisa(self):
        self.assertEqual(
            evaluar(6, 6, tiene_proxima=True, ultima_decision="DP-08", frecuencia="semanal"), [],
        )

    def test_frecuencia_cerrada_no_avisa_nada(self):
        self.assertEqual(
            evaluar(3, 0, tiene_proxima=False, ultima_decision="", frecuencia="alta"), [],
        )
        self.assertEqual(
            evaluar(6, 6, tiene_proxima=True, ultima_decision="", frecuencia="en_pausa"), [],
        )

    def test_sin_sesion_no_avisa(self):
        self.assertEqual(evaluar(0, 0, True, "", "semanal"), [])


class HoyContinuidadViewTests(TestCase):
    """Integración: /api/hoy/ con datos reales, por rol."""

    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-continuidad")
        self.admin = Usuario.objects.create_user(
            email="gerencia@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ADMIN,
        )
        self.coord_lima = Usuario.objects.create_user(
            email="ayvi@test.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.ASISTENTE, sede=Usuario.Sede.LIMA,
        )
        self.coord_piura = Usuario.objects.create_user(
            email="yazmin@test.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.ASISTENTE, sede=Usuario.Sede.PIURA,
        )

    def _paciente(self, nombre, sede, n_sesion, sesiones_proceso=0, frecuencia="semanal"):
        p = Paciente.objects.create(
            clinica=self.clinica, nombre=nombre, sede=sede,
            n_sesion=n_sesion, sesiones_proceso=sesiones_proceso, frecuencia=frecuencia,
        )
        if n_sesion:
            # La sesión real ahora sale de una cita asistida, no del contador
            # manual que se le pone al paciente (ver AlertaUsaSesionRealTests
            # en pacientes/tests.py). Bien atrás en el tiempo para no competir
            # con las citas que cada test agrega aparte (última/próxima).
            Cita.objects.create(
                clinica=self.clinica, paciente=p, n_sesion=n_sesion, estado=Cita.Estado.ASISTIO,
                inicio=timezone.now() - timedelta(days=30),
            )
        return p

    def _cita(self, paciente, dias, estado=Cita.Estado.AGENDADA, decision=""):
        return Cita.objects.create(
            clinica=self.clinica, paciente=paciente,
            inicio=timezone.now() + timedelta(days=dias), estado=estado, decision=decision,
        )

    def _hoy(self, usuario):
        self.client.force_login(usuario)
        r = self.client.get("/api/hoy/")
        self.assertEqual(r.status_code, 200)
        return r.json()

    def test_riesgo_abandono_s3_sin_proxima_cita(self):
        p = self._paciente("Sin próxima en S3", "lima", n_sesion=3)
        datos = self._hoy(self.coord_lima)
        nombres = [x["nombre"] for x in datos["riesgo_abandono"]]
        self.assertIn(p.nombre, nombres)
        self.assertNotIn(p.nombre, [x["nombre"] for x in datos["por_continuidad"]])

    def test_s3_con_proxima_cita_no_es_riesgo(self):
        p = self._paciente("Con próxima en S3", "lima", n_sesion=3)
        self._cita(p, dias=2)
        datos = self._hoy(self.coord_lima)
        self.assertNotIn(p.nombre, [x["nombre"] for x in datos["riesgo_abandono"]])

    def test_fin_de_bloque_sin_decision_registrada(self):
        p = self._paciente("Fin de bloque sin decidir", "lima", n_sesion=6, sesiones_proceso=6)
        self._cita(p, dias=-1, estado=Cita.Estado.ATENDIDA, decision="")
        datos = self._hoy(self.coord_lima)
        self.assertIn(p.nombre, [x["nombre"] for x in datos["por_continuidad"]])

    def test_fin_de_bloque_con_decision_ya_no_avisa(self):
        p = self._paciente("Fin de bloque ya decidido", "lima", n_sesion=6, sesiones_proceso=6)
        self._cita(p, dias=-1, estado=Cita.Estado.ATENDIDA, decision="DP-08")
        datos = self._hoy(self.coord_lima)
        self.assertNotIn(p.nombre, [x["nombre"] for x in datos["por_continuidad"]])

    def test_coordinadora_de_lima_no_ve_pacientes_de_piura(self):
        """Antes de este fix, la tarjeta de continuidad no filtraba por sede
        para el rol asistente: Ayvi (Lima) veía también a los de Piura."""
        de_piura = self._paciente("Paciente de Piura", "piura", n_sesion=3)
        datos_lima = self._hoy(self.coord_lima)
        nombres = [x["nombre"] for x in datos_lima["riesgo_abandono"]]
        self.assertNotIn(de_piura.nombre, nombres)
        datos_piura = self._hoy(self.coord_piura)
        self.assertIn(de_piura.nombre, [x["nombre"] for x in datos_piura["riesgo_abandono"]])

    def test_admin_ve_todas_las_sedes(self):
        de_lima = self._paciente("Ana de Lima", "lima", n_sesion=3)
        de_piura = self._paciente("Beto de Piura", "piura", n_sesion=3)
        datos = self._hoy(self.admin)
        nombres = [x["nombre"] for x in datos["riesgo_abandono"]]
        self.assertIn(de_lima.nombre, nombres)
        self.assertIn(de_piura.nombre, nombres)


class RespaldoTests(TestCase):
    """Un respaldo sirve si se puede volver a cargar. Eso es lo que se prueba.

    Railway guarda la base, pero si se borra algo por error no hay de dónde
    sacarlo. Y un respaldo que nadie probó a restaurar no es un respaldo.
    """

    URL = "/api/integraciones/respaldo/"
    TOKEN = "token-de-prueba"

    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-resp")
        self.psico = Usuario.objects.create_user(
            email="psicoresp@test.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.MEDICO,
        )
        self.paciente = Paciente.objects.create(
            clinica=self.clinica, nombre="Ana Pérez", telefono="987111222")

    def test_sin_token_no_entrega_nada(self):
        """Es un volcado de TODA la base: la puerta tiene que estar cerrada."""
        with self.settings(ITACA_INTEGRACION_TOKEN=""):
            self.assertEqual(self.client.get(self.URL).status_code, 403)
        with self.settings(ITACA_INTEGRACION_TOKEN=self.TOKEN):
            self.assertEqual(self.client.get(self.URL).status_code, 403)
            self.assertEqual(
                self.client.get(self.URL, HTTP_X_INTEGRACION_TOKEN="otro").status_code, 403)

    def test_el_respaldo_se_puede_volver_a_cargar(self):
        import gzip
        from django.core import serializers
        with self.settings(ITACA_INTEGRACION_TOKEN=self.TOKEN):
            r = self.client.get(self.URL, HTTP_X_INTEGRACION_TOKEN=self.TOKEN)
        self.assertEqual(r.status_code, 200)
        crudo = gzip.decompress(r.content).decode("utf-8")
        objetos = list(serializers.deserialize("json", crudo))
        nombres = [o.object.nombre for o in objetos
                   if o.object.__class__.__name__ == "Paciente"]
        self.assertIn("Ana Pérez", nombres)

    def test_lo_restaurado_devuelve_al_paciente_borrado(self):
        """La prueba de fuego: se borra al paciente y el respaldo lo trae de vuelta."""
        import gzip
        from django.core import serializers
        with self.settings(ITACA_INTEGRACION_TOKEN=self.TOKEN):
            r = self.client.get(self.URL, HTTP_X_INTEGRACION_TOKEN=self.TOKEN)
        crudo = gzip.decompress(r.content).decode("utf-8")

        Paciente.objects.all().delete()
        self.assertEqual(Paciente.objects.count(), 0)

        for o in serializers.deserialize("json", crudo):
            o.save()
        self.assertEqual(Paciente.objects.filter(nombre="Ana Pérez").count(), 1)

    def test_el_resumen_dice_cuantas_filas_trae(self):
        """Para poder mirar de un vistazo que el respaldo no salió vacío."""
        with self.settings(ITACA_INTEGRACION_TOKEN=self.TOKEN):
            d = self.client.get(self.URL + "?resumen=1",
                                HTTP_X_INTEGRACION_TOKEN=self.TOKEN).json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["filas"]["Paciente"], 1)
        self.assertGreater(d["bytes"], 0)

    def test_cubre_todas_las_tablas_del_negocio(self):
        """Una tabla que no entra al respaldo es un dato que no se puede
        recuperar. Por eso la lista no se escribe a mano: se compara contra
        todo modelo que no sea de Django."""
        from django.apps import apps
        from core.respaldo import modelos_a_respaldar
        propias = {m for m in apps.get_models() if not m.__module__.startswith("django.")}
        self.assertEqual(set(modelos_a_respaldar()), propias)
