"""Pruebas del contacto por WhatsApp desde el Centro de Continuidad.

Lo que se juega aquí:

  - **Cada sede escribe desde su línea.** Si Piura saliera por el número de
    Lima, el paciente vería un número desconocido y la respuesta le llegaría a
    la coordinadora que no lleva el caso.
  - **Sin sede no se envía.** Es el motivo entero de tener una instancia por
    sede: ante la duda, no se escribe. Y el intento queda como incidencia, no
    como un aviso que se pierde al cerrar la pantalla.
  - **Enviar no cierra casos.** Ni siquiera cuando el paciente dice que no
    sigue: eso lo apaga el DP registrado en la Agenda, no una conversación de
    WhatsApp. La alerta de "resuelto pero pendiente" tiene que seguir viva.
  - **Contactar no es gestionar.** El psicólogo no ve teléfonos y la analista
    no contacta pacientes, aunque ambos puedan gestionar el caso.
  - Y que nada de esto toque Meta ni el flujo de captación.

Ningún test sale a la red: `requests` está mockeado en todos.

    python manage.py test core.tests_contacto_continuidad
"""
from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

from core import contacto_continuidad as cc
from core import gestion_continuidad as gc
from core.models import InstanciaEvolution
from core.tests_continuidad_cola import _Base
from mensajes.models import Mensaje, PlantillaMensaje
from pacientes.models import GestionContinuidad, HistorialContinuidad
from usuarios.models import Profesional, Usuario

G = GestionContinuidad
Ev = HistorialContinuidad.Evento


class _RespuestaOK:
    """Lo justo de requests.Response que mira el código de envío."""

    status_code = 200
    text = ""

    def __init__(self, msg_id="WA-CONT-1"):
        self._id = msg_id

    def json(self):
        return {"key": {"id": self._id}}


class _ConContacto(_Base):
    def setUp(self):
        super().setUp()
        self.coord = Usuario.objects.create_user(
            email="coord-c@test.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.ASISTENTE, sede=Usuario.Sede.PIURA, nombre="Yazmín Requena")
        self.coord_lima = Usuario.objects.create_user(
            email="coordlima-c@test.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.ASISTENTE, sede=Usuario.Sede.LIMA, nombre="Ayvi Coordinación")
        self.admin = Usuario.objects.create_user(
            email="adm-c@test.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.ADMIN, nombre="Gerencia")
        self.analista = Usuario.objects.create_user(
            email="ana-c@test.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.ANALISTA, nombre="Dirección Clínica")
        self.lima = InstanciaEvolution.objects.create(
            clinica=self.clinica, sede="lima", nombre_instancia="conversemoslima")
        self.piura = InstanciaEvolution.objects.create(
            clinica=self.clinica, sede="piura", nombre_instancia="conversemospiura")

    # --- casos de ejemplo ---

    def _caso_s3(self, nombre="Damaris", sede="piura", telefono="987654321", ficha=None):
        """Un paciente en riesgo S3: llegó a la 3 y no tiene próxima cita."""
        p = self._paciente(nombre, sede=sede, telefono=telefono, ficha=ficha)
        self._asistidas(p, 3, ultima_hace=4)
        return p

    # --- utilidades ---

    def _enviar(self, usuario, paciente, **body):
        self.client.force_login(usuario)
        return self.client.post(f"/api/continuidad/caso/{paciente.id}/whatsapp/",
                                body, content_type="application/json")

    def _preview(self, usuario, paciente):
        self.client.force_login(usuario)
        return self.client.get(f"/api/continuidad/caso/{paciente.id}/whatsapp/")

    def _responder(self, usuario, paciente, respuesta):
        self.client.force_login(usuario)
        return self.client.post(f"/api/continuidad/caso/{paciente.id}/whatsapp/respuesta/",
                                {"respuesta": respuesta}, content_type="application/json")

    def _caso(self, usuario, paciente):
        self.client.force_login(usuario)
        return self.client.get(f"/api/continuidad/caso/{paciente.id}/")

    def _eventos(self, paciente):
        return list(HistorialContinuidad.objects.filter(gestion__paciente=paciente)
                    .order_by("id").values_list("evento", flat=True))

    def _con_evolution(self, respuesta=None):
        """Contexto que simula Evolution configurado y devuelve el mock del POST."""
        return patch("mensajes.evolution.requests.post",
                     return_value=respuesta or _RespuestaOK())


# ── 1 y 2 · la línea de cada sede ────────────────────────────────────────────

class LineaPorSedeTests(_ConContacto):
    def _url_usada(self, paciente, usuario):
        with self.settings(EVOLUTION_API_URL="https://evo.example",
                           EVOLUTION_API_KEY="k", EVOLUTION_INSTANCE="conversemositaca"):
            with self._con_evolution() as post:
                r = self._enviar(usuario, paciente)
        self.assertEqual(r.status_code, 200, r.content[:300])
        return post.call_args.args[0]

    def test_paciente_de_piura_usa_la_instancia_de_piura(self):
        p = self._caso_s3(sede="piura")
        url = self._url_usada(p, self.admin)
        self.assertIn("/message/sendText/conversemospiura", url)
        m = Mensaje.objects.get(paciente=p)
        self.assertEqual((m.sede, m.instancia), ("piura", "conversemospiura"))
        self.assertEqual(m.tipo, Mensaje.Tipo.CONTINUIDAD)

    def test_paciente_de_lima_usa_la_instancia_de_lima(self):
        ficha = Profesional.objects.create(
            clinica=self.clinica, nombre="Psico Lima", sede="lima")
        p = self._caso_s3(nombre="Ana Lima", sede="lima", ficha=ficha)
        url = self._url_usada(p, self.admin)
        self.assertIn("/message/sendText/conversemoslima", url)
        self.assertEqual(Mensaje.objects.get(paciente=p).instancia, "conversemoslima")

    def test_nunca_sale_por_la_linea_de_la_otra_sede(self):
        p = self._caso_s3(sede="piura")
        self.assertNotIn("conversemoslima", self._url_usada(p, self.admin))

    def test_el_preview_dice_por_que_linea_saldria(self):
        p = self._caso_s3(sede="piura")
        canal = self._preview(self.coord, p).json()["canal"]
        self.assertEqual(canal["sede"], "piura")
        self.assertEqual(canal["canal"], "WhatsApp Piura")
        self.assertEqual(canal["instancia"], "conversemospiura")
        self.assertTrue(canal["linea_configurada"])

    def test_el_preview_no_escribe_nada(self):
        p = self._caso_s3()
        self.assertEqual(self._preview(self.coord, p).status_code, 200)
        self.assertEqual(G.objects.count(), 0)
        self.assertEqual(Mensaje.objects.count(), 0)


# ── Paciente sin sede: se bloquea y queda incidencia ─────────────────────────

class SinSedeTests(_ConContacto):
    def test_sin_sede_no_se_envia(self):
        p = self._caso_s3(nombre="Sin sede", sede="")
        with self._con_evolution() as post:
            r = self._enviar(self.admin, p)
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["bloqueo"], "sin_sede")
        self.assertIn("asignar sede", r.json()["detail"])
        post.assert_not_called()
        self.assertEqual(Mensaje.objects.count(), 0)

    def test_el_bloqueo_queda_como_incidencia_en_el_historial(self):
        p = self._caso_s3(nombre="Sin sede", sede="")
        self._enviar(self.admin, p)
        self.assertIn(Ev.CONTACTO_BLOQUEADO, self._eventos(p))
        texto = gc.serializar_historial(self._gestion(p))[-1]["texto"]
        self.assertIn("no tiene sede asignada", texto)

    def test_sin_telefono_tampoco_se_envia(self):
        p = self._caso_s3(nombre="Sin tel", telefono="")
        with self._con_evolution() as post:
            r = self._enviar(self.admin, p)
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["bloqueo"], "sin_telefono")
        post.assert_not_called()

    def test_el_preview_avisa_del_bloqueo_antes_de_intentarlo(self):
        p = self._caso_s3(nombre="Sin sede", sede="")
        d = self._preview(self.admin, p).json()
        self.assertEqual(d["bloqueo"], "sin_sede")
        self.assertIn("asignar sede", d["bloqueo_texto"])
        self.assertIsNone(d["canal"])

    def _gestion(self, paciente):
        return G.objects.filter(paciente=paciente).order_by("-id").first()

    def test_un_paciente_sin_sede_no_lo_ve_ninguna_coordinadora(self):
        """Consecuencia de `pacientes_del_rol`: cada coordinadora filtra por SU
        sede, así que un paciente sin sede queda fuera de las dos. La incidencia
        de "falta asignar sede" solo la puede resolver gerencia."""
        p = self._caso_s3(nombre="Sin sede", sede="")
        self.assertEqual(self._preview(self.coord, p).status_code, 404)
        self.assertEqual(self._preview(self.coord_lima, p).status_code, 404)
        self.assertEqual(self._preview(self.admin, p).status_code, 200)


# ── 3 · permisos ─────────────────────────────────────────────────────────────

class PermisosTests(_ConContacto):
    def test_la_analista_no_puede_contactar(self):
        """Gestiona el caso, pero nunca le escribe a un paciente."""
        p = self._caso_s3()
        with self._con_evolution() as post:
            r = self._enviar(self.analista, p)
        self.assertEqual(r.status_code, 403)
        post.assert_not_called()
        self.assertEqual(Mensaje.objects.count(), 0)

    def test_el_psicologo_no_puede_contactar(self):
        """No ve el teléfono de sus pacientes: mal podría escribirles."""
        p = self._caso_s3()
        with self._con_evolution() as post:
            r = self._enviar(self.psico, p)
        self.assertEqual(r.status_code, 403)
        post.assert_not_called()

    def test_coordinacion_y_gerencia_si_pueden(self):
        for usuario in (self.coord, self.admin):
            with self.subTest(rol=usuario.rol):
                p = self._caso_s3(nombre=f"Paciente {usuario.rol}")
                with self.settings(EVOLUTION_API_URL="https://evo.example", EVOLUTION_API_KEY="k"):
                    with self._con_evolution(_RespuestaOK(f"WA-{usuario.rol}")):
                        r = self._enviar(usuario, p)
                self.assertEqual(r.status_code, 200)

    def test_coordinacion_no_contacta_pacientes_de_otra_sede(self):
        p = self._caso_s3(sede="piura")
        with self._con_evolution() as post:
            r = self._enviar(self.coord_lima, p)
        self.assertEqual(r.status_code, 404)     # ni siquiera se confirma que exista
        post.assert_not_called()

    def test_el_panel_se_ve_en_solo_lectura_para_quien_no_contacta(self):
        p = self._caso_s3()
        d = self._caso(self.analista, p).json()["contacto"]
        self.assertFalse(d["puede_contactar"])
        self.assertTrue(self._caso(self.coord, p).json()["contacto"]["puede_contactar"])

    def test_la_respuesta_tambien_es_solo_de_quien_contacta(self):
        p = self._caso_s3()
        self.assertEqual(self._responder(self.analista, p, "continua").status_code, 403)


# ── 4 · el envío genera historial ────────────────────────────────────────────

class HistorialTests(_ConContacto):
    def _enviar_ok(self, paciente, usuario=None, **body):
        with self.settings(EVOLUTION_API_URL="https://evo.example", EVOLUTION_API_KEY="k"):
            with self._con_evolution():
                return self._enviar(usuario or self.admin, paciente, **body)

    def test_enviar_deja_historial_y_bitacora(self):
        p = self._caso_s3()
        r = self._enviar_ok(p)
        self.assertEqual(r.status_code, 200)
        self.assertIn(Ev.WHATSAPP_ENVIADO, self._eventos(p))
        m = Mensaje.objects.get(paciente=p)
        self.assertEqual(m.gestion_continuidad_id, G.objects.get(paciente=p).id)
        self.assertEqual(m.direccion, Mensaje.Direccion.SALIENTE)
        self.assertEqual(m.enviado_por_id, self.admin.id)
        self.assertEqual(m.external_message_id, "WA-CONT-1")

    def test_el_historial_dice_que_plantilla_se_uso(self):
        p = self._caso_s3()
        self._enviar_ok(p)
        textos = [h["texto"] for h in gc.serializar_historial(G.objects.get(paciente=p))]
        self.assertTrue(any("WhatsApp enviado · Confirmación de continuidad" in t for t in textos))

    def test_un_envio_fallido_tambien_queda_registrado(self):
        """Sin Evolution configurado el mensaje no sale, pero el intento consta."""
        p = self._caso_s3()
        with self.settings(EVOLUTION_API_URL="", EVOLUTION_API_KEY=""):
            r = self._enviar(self.admin, p)
        self.assertEqual(r.status_code, 200)
        self.assertIn(Ev.WHATSAPP_FALLIDO, self._eventos(p))
        # Y queda el enlace manual de respaldo, como en el resto del sistema.
        self.assertTrue(r.json()["envio"]["wa_url"])
        self.assertEqual(Mensaje.objects.get(paciente=p).estado, Mensaje.Estado.NO_CONFIGURADO)

    def test_el_contacto_aparece_en_el_detalle_del_caso(self):
        p = self._caso_s3()
        self._enviar_ok(p)
        contacto = self._caso(self.coord, p).json()["contacto"]
        self.assertEqual(len(contacto["enviados"]), 1)
        self.assertEqual(contacto["ultimo"]["estado"], "enviado")
        self.assertEqual(contacto["horas_desde_ultimo"], 0)

    def test_el_texto_lo_escribe_quien_envia(self):
        p = self._caso_s3()
        self._enviar_ok(p, texto="Hola Damaris, te escribo de parte del equipo.")
        self.assertEqual(Mensaje.objects.get(paciente=p).texto,
                         "Hola Damaris, te escribo de parte del equipo.")

    def test_la_plantilla_se_rellena_con_los_datos_del_caso(self):
        PlantillaMensaje.objects.create(
            clinica=self.clinica, clave=cc.CLAVE_PLANTILLA, nombre="Confirmación de continuidad",
            texto="Hola {nombre}, soy {coordinadora} de {clinica}.")
        p = self._caso_s3(nombre="Damaris Nicol")
        texto = self._preview(self.coord, p).json()["texto_sugerido"]
        self.assertEqual(texto, "Hola Damaris, soy Yazmín de Conversemos.")


# ── 5 · la respuesta del paciente cambia el estado ───────────────────────────

class RespuestaTests(_ConContacto):
    def test_si_desea_continuar_queda_registrado_en_seguimiento(self):
        p = self._caso_s3()
        r = self._responder(self.coord, p, "continua")
        self.assertEqual(r.status_code, 200)
        g = G.objects.get(paciente=p)
        self.assertEqual(g.resultado_operativo, G.Resultado.PACIENTE_CONTINUA)
        self.assertEqual(g.estado_revision, G.Revision.EN_SEGUIMIENTO)
        self.assertIn(Ev.RESPUESTA_PACIENTE, self._eventos(p))

    def test_mas_adelante_es_pausa_temporal(self):
        p = self._caso_s3()
        self._responder(self.coord, p, "mas_adelante")
        self.assertEqual(G.objects.get(paciente=p).resultado_operativo,
                         G.Resultado.PAUSA_TEMPORAL)

    def test_no_continuara_no_cierra_el_caso(self):
        """Cierre administrativo es un RESULTADO, no un estado resuelto."""
        p = self._caso_s3()
        r = self._responder(self.coord, p, "no_continua")
        g = G.objects.get(paciente=p)
        self.assertEqual(g.resultado_operativo, G.Resultado.NO_CONTINUARA)
        self.assertEqual(g.estado_revision, G.Revision.EN_SEGUIMIENTO)
        self.assertTrue(g.abierta)
        self.assertIsNone(g.resuelto_en)
        # Y el caso sigue en la cola: lo que falta es el DP en la Agenda.
        self.assertTrue(r.json()["en_cola"])

    def test_una_respuesta_desconocida_se_rechaza(self):
        p = self._caso_s3()
        self.assertEqual(self._responder(self.coord, p, "quizas").status_code, 400)
        self.assertEqual(G.objects.count(), 0)

    def test_los_mensajes_entrantes_se_muestran_para_clasificarlos(self):
        """El webhook registra lo que llegó; la persona decide qué significa."""
        p = self._caso_s3()
        with self.settings(EVOLUTION_API_URL="https://evo.example", EVOLUTION_API_KEY="k"):
            with self._con_evolution():
                self._enviar(self.admin, p)
        Mensaje.objects.create(
            clinica=self.clinica, paciente=p, texto="sí, quiero seguir",
            tipo=Mensaje.Tipo.MANUAL, estado=Mensaje.Estado.RECIBIDO,
            direccion=Mensaje.Direccion.ENTRANTE, external_message_id="WA-IN-1")
        entrantes = self._caso(self.coord, p).json()["contacto"]["respuestas_entrantes"]
        self.assertEqual(len(entrantes), 1)
        self.assertEqual(entrantes[0]["texto"], "sí, quiero seguir")
        # Verlo NO clasifica nada por su cuenta.
        self.assertEqual(G.objects.get(paciente=p).resultado_operativo, "")


# ── 6 · no se puede cerrar en falso ──────────────────────────────────────────

class NoCierraEnFalsoTests(_ConContacto):
    def test_enviar_nunca_deja_el_caso_resuelto(self):
        p = self._caso_s3()
        with self.settings(EVOLUTION_API_URL="https://evo.example", EVOLUTION_API_KEY="k"):
            with self._con_evolution():
                r = self._enviar(self.admin, p)
        g = G.objects.get(paciente=p)
        self.assertEqual(g.estado_revision, G.Revision.EN_SEGUIMIENTO)
        self.assertTrue(g.abierta)
        self.assertTrue(r.json()["en_cola"])

    def test_la_alerta_de_resuelto_pendiente_sigue_viva(self):
        p = self._caso_s3()
        self._responder(self.coord, p, "no_continua")
        # Alguien marca "resuelto" a mano con la condición todavía detectada.
        self.client.force_login(self.coord)
        r = self.client.patch(f"/api/continuidad/caso/{p.id}/gestion/",
                              {"estado_revision": "resuelto"}, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["gestion"]["alerta"], gc.ALERTA_RESUELTO_PENDIENTE)
        self.assertTrue(r.json()["en_cola"])

    def test_cuando_la_agenda_resuelve_el_caso_se_cierra_solo(self):
        """El camino correcto: se agenda la próxima cita y la condición se apaga."""
        p = self._caso_s3()
        self._responder(self.coord, p, "continua")
        self.assertTrue(G.objects.get(paciente=p).abierta)
        self._agendada(p, en_dias=3)          # la señal dispara reconciliar()
        g = G.objects.get(paciente=p)
        self.assertFalse(g.abierta)
        self.assertTrue(g.resuelta_por_sistema)
        self.assertIn(Ev.AUTO_RESUELTO, self._eventos(p))


# ── 5 bis · control de reenvío (24 h) ────────────────────────────────────────

class ReenvioTests(_ConContacto):
    def _enviar_ok(self, p, **body):
        with self.settings(EVOLUTION_API_URL="https://evo.example", EVOLUTION_API_KEY="k"):
            with self._con_evolution(_RespuestaOK(f"WA-{timezone.now().timestamp()}")):
                return self._enviar(self.admin, p, **body)

    def test_reenviar_antes_de_24h_pide_confirmacion(self):
        p = self._caso_s3()
        self.assertEqual(self._enviar_ok(p).status_code, 200)
        r = self._enviar_ok(p)
        self.assertEqual(r.status_code, 400)
        self.assertTrue(r.json()["requiere_confirmacion"])
        self.assertIn("ya fue contactado", r.json()["detail"])
        self.assertEqual(Mensaje.objects.filter(paciente=p).count(), 1)

    def test_con_confirmacion_si_se_reenvia(self):
        p = self._caso_s3()
        self._enviar_ok(p)
        self.assertEqual(self._enviar_ok(p, confirmado=True).status_code, 200)
        self.assertEqual(Mensaje.objects.filter(paciente=p).count(), 2)

    def test_pasadas_24h_no_hace_falta_confirmar(self):
        p = self._caso_s3()
        self._enviar_ok(p)
        viejo = Mensaje.objects.get(paciente=p)
        Mensaje.objects.filter(pk=viejo.pk).update(
            creado_en=timezone.now() - timedelta(hours=25))
        self.assertEqual(self._enviar_ok(p).status_code, 200)

    def test_el_preview_avisa_cuanto_hace_que_se_contacto(self):
        p = self._caso_s3()
        self._enviar_ok(p)
        d = self._preview(self.admin, p).json()
        self.assertTrue(d["requiere_confirmacion"])
        self.assertEqual(d["horas_entre_contactos"], 24)


# ── 7 y 8 · nada de esto rompe lo que ya andaba ──────────────────────────────

class NoRompeNadaTests(_ConContacto):
    def test_no_toca_meta_cloud_api(self):
        p = self._caso_s3()
        with self.settings(EVOLUTION_API_URL="https://evo.example", EVOLUTION_API_KEY="k"):
            with patch("mensajes.cloud_api.requests.post") as meta, self._con_evolution():
                self._enviar(self.admin, p)
        meta.assert_not_called()

    def test_no_pasa_por_el_flujo_de_captacion(self):
        p = self._caso_s3()
        with self.settings(EVOLUTION_API_URL="https://evo.example", EVOLUTION_API_KEY="k"):
            with patch("leads.whatsapp_auto.procesar_lead") as auto, self._con_evolution():
                self._enviar(self.admin, p)
        auto.assert_not_called()
        from leads.models import Lead
        self.assertEqual(Lead.objects.count(), 0)

    def test_el_contacto_no_es_una_respuesta_automatica(self):
        """Las automáticas no pueden usar la línea oficial; este contacto sí,
        porque lo escribe una persona: es una automatización autorizada."""
        p = self._caso_s3(sede="piura")
        with self.settings(EVOLUTION_API_URL="https://evo.example", EVOLUTION_API_KEY="k",
                           EVOLUTION_INSTANCE="conversemositaca"):
            with self._con_evolution() as post:
                self._enviar(self.admin, p)
        self.assertIn("conversemospiura", post.call_args.args[0])

    def test_el_modulo_no_interpreta_la_respuesta_del_paciente(self):
        """Un vistazo al código: clasificar es de la persona, no de una regla."""
        import ast
        import io
        from pathlib import Path

        arbol = ast.parse(io.open(
            Path(__file__).with_name("contacto_continuidad.py"), encoding="utf-8").read())
        importados = []
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                importados += [a.name for a in nodo.names]
            elif isinstance(nodo, ast.ImportFrom):
                importados += [f"{nodo.module or ''}.{a.name}" for a in nodo.names]
        for malo in ("whatsapp_auto", "openai", "estructurar_nota", "transcripcion", "cloud_api"):
            for modulo in importados:
                self.assertNotIn(malo, modulo, f"No debe importar {modulo}")

    def test_la_gestion_manual_de_siempre_sigue_funcionando(self):
        p = self._caso_s3()
        self.client.force_login(self.coord)
        r = self.client.patch(f"/api/continuidad/caso/{p.id}/gestion/",
                              {"estado_revision": "en_seguimiento", "responsable": "coordinacion"},
                              content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["gestion"]["responsable"], "coordinacion")

    def test_un_caso_ya_resuelto_no_se_puede_contactar(self):
        p = self._caso_s3()
        self._agendada(p, en_dias=3)          # deja de estar pendiente
        with self._con_evolution() as post:
            r = self._enviar(self.admin, p)
        self.assertEqual(r.status_code, 409)
        post.assert_not_called()
