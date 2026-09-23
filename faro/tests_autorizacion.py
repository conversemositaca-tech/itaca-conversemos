"""La autorización de la familia: firmarla, y que llegue a la respuesta correcta.

Es la pieza legal del tamizaje. Sin una autorización firmada el estudiante no
debería participar, y sin el correo del apoderado no hay a dónde mandarle el
resultado individual que el consentimiento le promete.

Lo que más se prueba aquí es el EMPAREJAMIENTO, porque es donde esto se rompe
en la vida real: el apoderado escribe "José Pérez Ramírez" desde su casa y el
chico teclea "jose perez ramirez" en un celular prestado, con el grado puesto
de otra forma. Si eso no empareja, el informe no se envía y la familia se queda
esperando algo que firmó.

    python manage.py test faro.tests_autorizacion
"""
from django.test import TestCase

from core.models import Clinica
from faro import instrumentos as ins
from faro.models import Aplicacion, Autorizacion
from faro.registro import registrar


class _Base(TestCase):
    def setUp(self):
        self.clinica = Clinica.objects.create(
            nombre="Ítaca Conversemos", slug="itaca-faro-aut")
        self.ap = Aplicacion.objects.create(
            clinica=self.clinica, institucion="I.E. San Martín", ciudad="Piura",
            estado=Aplicacion.Estado.AUTORIZANDO)
        self.url = f"/api/faro/autorizacion/{self.ap.token_apoderado}/"

    def firmar(self, **campos):
        datos = {
            "estudiante": "José Pérez Ramírez", "grado": "3.°", "seccion": "B",
            "apoderado": "Rosa Ramírez", "documento": "44556677",
            "parentesco": "madre", "correo": "rosa@correo.com",
            "celular": "987654321", "autoriza": True,
        }
        datos.update(campos)
        return self.client.post(self.url, datos, content_type="application/json")

    def contesta(self, **campos):
        datos = {"nombre": "José Pérez Ramírez", "grado": "3.°", "seccion": "B"}
        datos.update(campos)
        return registrar(self.ap, respuestas={i["id"]: 0 for i in ins.ORDEN}, **datos)[0]


class FirmaTests(_Base):
    def test_firmar_guarda_la_autorizacion_con_los_datos_del_apoderado(self):
        self.assertEqual(self.firmar().status_code, 201)
        a = Autorizacion.objects.get()
        self.assertEqual(a.apoderado, "Rosa Ramírez")
        self.assertEqual(a.correo, "rosa@correo.com")
        self.assertTrue(a.autoriza)

    def test_se_guarda_la_version_del_texto_que_se_firmo(self):
        # Un "sí" suelto no sirve para defender nada: el alcance de lo que ve
        # el colegio ya cambió una vez y va a volver a cambiar. Hay que poder
        # decir qué se le prometió exactamente a cada familia.
        self.firmar()
        self.assertTrue(Autorizacion.objects.get().version_texto)

    def test_el_no_tambien_se_guarda(self):
        # Borrar los "no" confundiría a quien no quiso con quien nunca
        # respondió, y el colegio necesita distinguirlos.
        self.assertEqual(self.firmar(autoriza=False, correo="").status_code, 201)
        self.assertFalse(Autorizacion.objects.get().autoriza)

    def test_a_quien_autoriza_se_le_exige_correo(self):
        r = self.firmar(correo="")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Autorizacion.objects.exists())

    def test_a_quien_no_autoriza_no_se_le_exige_correo(self):
        # Pedirle datos a quien dice que no es ponerle un obstáculo para decir
        # que no, y eso vicia el consentimiento.
        self.assertEqual(self.firmar(autoriza=False, correo="").status_code, 201)

    def test_reenviar_el_formulario_corrige_en_vez_de_duplicar(self):
        self.firmar()
        self.firmar(correo="rosa.nueva@correo.com")
        self.assertEqual(Autorizacion.objects.count(), 1)
        self.assertEqual(Autorizacion.objects.get().correo, "rosa.nueva@correo.com")

    def test_falta_el_nombre_del_estudiante(self):
        self.assertEqual(self.firmar(estudiante="Jo").status_code, 400)

    def test_un_token_inventado_no_llega_a_ningun_formulario(self):
        r = self.client.post("/api/faro/autorizacion/inventado/", {},
                             content_type="application/json")
        self.assertEqual(r.status_code, 404)

    def test_el_token_del_aula_no_sirve_para_firmar(self):
        # Tres audiencias, tres enlaces. Que se filtre el del aula —que se
        # reparte a un salón entero— no puede dar acceso a los datos de los
        # apoderados.
        r = self.client.post(f"/api/faro/autorizacion/{self.ap.token_estudiante}/", {},
                             content_type="application/json")
        self.assertEqual(r.status_code, 404)

    def test_cuenta_como_autorizado_para_la_participacion(self):
        self.firmar()
        self.firmar(estudiante="Ana Torres", correo="ana@correo.com")
        self.firmar(estudiante="Luis Díaz", autoriza=False, correo="")
        self.ap.refresh_from_db()
        self.assertEqual(self.ap.autorizados_efectivos, 2)


class EmparejamientoTests(_Base):
    def test_la_respuesta_encuentra_su_autorizacion(self):
        self.firmar()
        self.assertEqual(self.contesta().autorizacion, Autorizacion.objects.get())

    def test_empareja_sin_tildes_ni_mayusculas(self):
        self.firmar()
        self.assertIsNotNone(self.contesta(nombre="jose perez ramirez").autorizacion)

    def test_empareja_aunque_el_grado_se_escriba_distinto(self):
        # El apoderado pone "3.°" y el chico "3ro B". Esa diferencia no puede
        # costar la entrega de un informe.
        self.firmar()
        r = self.contesta(grado="3ro", seccion="b")
        self.assertIsNotNone(r.autorizacion)

    def test_sin_autorizacion_la_respuesta_se_guarda_igual(self):
        # Un tipeo en el aula NO puede impedir que un chico conteste. Queda sin
        # emparejar y se resuelve a mano desde el panel interno.
        r = self.contesta(nombre="Quien No Firmó Nada")
        self.assertIsNone(r.autorizacion)
        self.assertEqual(r.nombre, "Quien No Firmó Nada")

    def test_no_empareja_con_quien_dijo_que_no(self):
        self.firmar(autoriza=False, correo="")
        self.assertIsNone(self.contesta().autorizacion)

    def test_con_dos_homonimos_no_adivina(self):
        # Dos "José Pérez" en grados distintos: emparejar al azar mandaría el
        # informe de un chico a la familia del otro.
        self.firmar(seccion="B")
        self.firmar(seccion="C", correo="otra@correo.com")
        self.assertIsNone(self.contesta(grado="", seccion="").autorizacion)
