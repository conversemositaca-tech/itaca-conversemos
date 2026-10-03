"""El informe que se le manda a la familia, y los frenos para mandarlo.

Es la última promesa del consentimiento: el apoderado que autorizó recibe el
resultado por correo. Lo que se prueba es sobre todo lo que NO debe pasar: que
un rojo no salga antes de la llamada, que nadie lo reciba dos veces, y que el
correo no lleve las respuestas una por una.

    python manage.py test faro.tests_informes
"""
from django.core import mail
from django.test import TestCase, override_settings

from core.models import Clinica
from faro import informes
from faro import instrumentos as ins
from faro.models import Aplicacion
from faro.registro import registrar
from usuarios.models import Usuario


def contesta(**kw):
    d = {i["id"]: 0 for i in ins.ORDEN}
    d.update(kw)
    return d


class _Base(TestCase):
    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Ítaca", slug="itaca-faro-informes")
        self.ap = Aplicacion.objects.create(
            clinica=self.clinica, institucion="I.E. San Martín", ciudad="Piura",
            estado=Aplicacion.Estado.AUTORIZANDO)

    def firmar(self, estudiante="Ana Ríos", **campos):
        datos = {"estudiante": estudiante, "grado": "3.°", "seccion": "B",
                 "apoderado": "Rosa Ríos", "correo": "rosa@correo.com", "autoriza": True}
        datos.update(campos)
        r = self.client.post(f"/api/faro/autorizacion/{self.ap.token_apoderado}/",
                             datos, content_type="application/json")
        self.assertEqual(r.status_code, 201, r.content)

    def responder(self, nombre="Ana Ríos", **items):
        return registrar(self.ap, nombre=nombre, grado="3.°", seccion="B",
                         respuestas=contesta(**items))


class InformeTests(_Base):
    def test_el_pdf_es_un_pdf_y_el_correo_no_lleva_respuestas_crudas(self):
        self.firmar()
        r, _ = self.responder(gad1=3, gad2=3, gad3=3, gad4=2)
        self.assertTrue(informes.pdf(r).startswith(b"%PDF"))
        cuerpo = informes.cuerpo(r)
        self.assertIn("Ana Ríos", cuerpo)
        self.assertIn("Rosa Ríos", cuerpo)
        for id_item in ("gad1", "phq1", "asq1", "ebipq1", "ciber1"):
            self.assertNotIn(id_item, cuerpo)

    def test_los_indicadores_salen_de_los_puntajes_guardados(self):
        self.firmar()
        r, _ = self.responder(gad1=3, gad2=3, gad3=3, gad4=2, ciber3=3)
        areas = {a: v for a, v, _ in informes.indicadores(r)}
        self.assertEqual(areas["Ansiedad"], "11 de 21 · Moderada")
        self.assertEqual(areas["Convivencia por internet"], "Cibervíctima")
        self.assertEqual(areas["Convivencia escolar"], "No involucrado")
        self.assertEqual(areas["Señales de riesgo"], "Sin señales")


class EnvioTests(_Base):
    def test_envia_a_quien_autorizo_con_correo_y_deja_constancia(self):
        self.firmar()
        r, _ = self.responder()
        d = informes.enviar_pendientes(self.ap)
        self.assertEqual(d["enviados"], 1)
        self.assertEqual(len(mail.outbox), 1)
        m = mail.outbox[0]
        self.assertEqual(m.to, ["rosa@correo.com"])
        self.assertIn("Ana Ríos", m.subject)
        self.assertEqual(len(m.attachments), 1)
        self.assertTrue(m.attachments[0][0].endswith(".pdf"))
        r.autorizacion.refresh_from_db()
        self.assertIsNotNone(r.autorizacion.enviado_en)
        self.assertEqual(r.autorizacion.envio_detalle, "Enviado")

    def test_nadie_lo_recibe_dos_veces(self):
        self.firmar()
        self.responder()
        informes.enviar_pendientes(self.ap)
        d = informes.enviar_pendientes(self.ap)
        self.assertEqual(d["enviados"], 0)
        self.assertEqual(d["omitidos"]["ya_enviado"], 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_un_rojo_espera_a_que_la_alerta_este_atendida(self):
        # La familia se entera por la llamada del psicólogo, no por un adjunto.
        self.firmar()
        r, alerta = self.responder(asq1=1)
        d = informes.enviar_pendientes(self.ap)
        self.assertEqual(d["enviados"], 0)
        self.assertEqual(d["omitidos"]["rojo_pendiente"], 1)
        self.assertEqual(len(mail.outbox), 0)

        alerta.atendida = True
        alerta.save(update_fields=["atendida"])
        d = informes.enviar_pendientes(self.ap)
        self.assertEqual(d["enviados"], 1)
        self.assertIn("Riesgo que se atendió", informes.cuerpo(r))

    def test_sin_autorizacion_emparejada_no_hay_a_donde_mandar(self):
        self.firmar(estudiante="Ana Ríos")
        self.responder(nombre="Otro Alumno")
        d = informes.enviar_pendientes(self.ap)
        self.assertEqual(d["enviados"], 0)
        self.assertEqual(d["omitidos"]["sin_autorizacion"], 1)

    def test_quien_no_autorizo_no_recibe_nada(self):
        self.firmar(autoriza=False, correo="")
        self.responder()
        d = informes.enviar_pendientes(self.ap)
        self.assertEqual(d["enviados"], 0)
        self.assertEqual(d["omitidos"]["sin_autorizacion"], 1)
        self.assertEqual(len(mail.outbox), 0)


class EndpointTests(_Base):
    def entrar(self, rol):
        u = Usuario.objects.create_user(
            email=f"{rol}@test.pe", password="x", clinica=self.clinica, rol=rol)
        self.client.force_login(u)

    def test_lo_dispara_el_equipo_clinico_y_devuelve_el_recuento(self):
        self.firmar()
        self.responder()
        self.entrar(Usuario.Rol.MEDICO)
        r = self.client.post(f"/api/faro/panel/enviar/{self.ap.pk}/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["enviados"], 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_otros_perfiles_no_pueden(self):
        self.entrar(Usuario.Rol.ASISTENTE)
        r = self.client.post(f"/api/faro/panel/enviar/{self.ap.pk}/")
        self.assertEqual(r.status_code, 403)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend", DEBUG=False)
    def test_sin_correo_configurado_avisa_en_vez_de_marcar_como_enviado(self):
        # Con el backend de consola el correo "sale" a los logs y nadie lo recibe,
        # pero la autorización quedaría marcada como enviada. Mejor negarse.
        self.firmar()
        self.responder()
        self.entrar(Usuario.Rol.MEDICO)
        r = self.client.post(f"/api/faro/panel/enviar/{self.ap.pk}/")
        self.assertEqual(r.status_code, 503)
        self.assertIn("EMAIL_HOST", r.json()["detail"])
