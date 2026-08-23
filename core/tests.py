from django.test import TestCase

from core.models import Clinica
from pacientes.models import Paciente
from usuarios.models import Usuario
# Create your tests here.


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
