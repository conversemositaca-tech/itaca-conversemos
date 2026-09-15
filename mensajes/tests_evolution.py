"""Pruebas de las líneas de WhatsApp por sede (Evolution API).

Lo que se juega aquí:

- Que el mensaje salga por la línea de SU sede. Si Lima escribiera desde el
  número de Piura, el paciente vería un número desconocido y la coordinadora que
  no lleva ese caso recibiría la respuesta.
- Que el webhook de los números oficiales NO conteste solo. Esas líneas son de
  personas (Lima: Ayvi, Piura: Yazmín) y una respuesta automática saliendo a
  nombre de ellas es un problema, no una mejora.
- Que un reintento de Evolution no duplique nada, y que un acuse que llega tarde
  no borre un "leído" que ya pasó.

    python manage.py test mensajes.tests_evolution
"""
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from core.models import Clinica, InstanciaEvolution
from mensajes import evolution
from mensajes.models import Mensaje
from mensajes.services import registrar_y_enviar, reintentar_comunicacion
from pacientes.models import Paciente
from usuarios.models import Usuario


class RespuestaFalsa:
    """Imita lo justo de requests.Response que usa el código."""

    def __init__(self, status_code=200, data=None, text=""):
        self.status_code = status_code
        self._data = data if data is not None else {"key": {"id": "MSG-EXTERNO-1"}}
        self.text = text

    def json(self):
        if self._data is None:
            raise ValueError("sin json")
        return self._data


class _Base(TestCase):
    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-evo")
        self.lima = InstanciaEvolution.objects.create(
            clinica=self.clinica, sede="lima", nombre_instancia="conversemoslima")
        self.piura = InstanciaEvolution.objects.create(
            clinica=self.clinica, sede="piura", nombre_instancia="conversemospiura")

    def _paciente(self, nombre="Ana", sede="lima", telefono="987654321"):
        return Paciente.objects.create(
            clinica=self.clinica, nombre=nombre, sede=sede, telefono=telefono)


class SeleccionDeInstanciaTests(_Base):
    """La línea correcta para cada sede (y el respaldo cuando no hay ninguna)."""

    def _capturar_envio(self, paciente):
        """Envía y devuelve la URL a la que se hizo el POST."""
        with self.settings(EVOLUTION_API_URL="https://evo.example",
                           EVOLUTION_API_KEY="clave-de-prueba",
                           EVOLUTION_INSTANCE="legacy_env"):
            with patch("mensajes.evolution.estado_en_vivo", return_value="open"), \
                 patch("mensajes.evolution.requests.post",
                       return_value=RespuestaFalsa()) as post:
                mensaje, resultado, _ = registrar_y_enviar(
                    self.clinica, telefono=paciente.telefono, texto="Hola",
                    tipo=Mensaje.Tipo.RECORDATORIO, paciente=paciente)
        return post.call_args, mensaje, resultado

    def test_lima_sale_por_la_instancia_de_lima(self):
        llamada, mensaje, resultado = self._capturar_envio(self._paciente(sede="lima"))
        self.assertIn("/message/sendText/conversemoslima", llamada.args[0])
        self.assertEqual(resultado["estado"], "enviado")
        self.assertEqual(mensaje.instancia, "conversemoslima")
        self.assertEqual(mensaje.sede, "lima")
        self.assertEqual(mensaje.proveedor, Mensaje.Proveedor.EVOLUTION)
        self.assertEqual(mensaje.direccion, Mensaje.Direccion.SALIENTE)
        # El id externo se guarda: sin él los acuses de entrega no tienen con qué casar.
        self.assertEqual(mensaje.external_message_id, "MSG-EXTERNO-1")

    def test_piura_sale_por_la_instancia_de_piura(self):
        llamada, mensaje, _ = self._capturar_envio(self._paciente(nombre="Luis", sede="piura"))
        self.assertIn("/message/sendText/conversemospiura", llamada.args[0])
        self.assertEqual(mensaje.instancia, "conversemospiura")
        self.assertEqual(mensaje.sede, "piura")

    def test_nunca_usa_la_linea_de_la_otra_sede(self):
        """Si la línea de Piura está apagada, NO se cae a la de Lima."""
        self.piura.activo = False
        self.piura.save(update_fields=["activo"])
        llamada, _, _ = self._capturar_envio(self._paciente(nombre="Luis", sede="piura"))
        self.assertNotIn("conversemoslima", llamada.args[0])
        self.assertIn("legacy_env", llamada.args[0])

    def test_sin_instancias_cae_al_camino_de_siempre(self):
        """Compatibilidad: la instancia de la clínica sigue mandando si no hay líneas."""
        InstanciaEvolution.objects.all().delete()
        self.clinica.whatsapp_instance = "conversemositaca"
        self.clinica.save(update_fields=["whatsapp_instance"])
        llamada, mensaje, _ = self._capturar_envio(self._paciente())
        self.assertIn("/message/sendText/conversemositaca", llamada.args[0])
        self.assertEqual(mensaje.instancia, "conversemositaca")

    def test_sin_instancias_ni_clinica_usa_la_del_entorno(self):
        InstanciaEvolution.objects.all().delete()
        llamada, _, _ = self._capturar_envio(self._paciente())
        self.assertIn("/message/sendText/legacy_env", llamada.args[0])

    def test_instancia_marcada_ambas_sirve_de_respaldo(self):
        InstanciaEvolution.objects.all().delete()
        InstanciaEvolution.objects.create(
            clinica=self.clinica, sede="ambas", nombre_instancia="conversemostodo")
        llamada, _, _ = self._capturar_envio(self._paciente(sede="piura"))
        self.assertIn("/message/sendText/conversemostodo", llamada.args[0])

    def test_la_api_key_no_aparece_en_la_respuesta(self):
        """El resultado del envío se guarda en la bitácora y viaja al frontend."""
        _, mensaje, resultado = self._capturar_envio(self._paciente())
        self.assertNotIn("clave-de-prueba", str(resultado))
        self.assertNotIn("clave-de-prueba", mensaje.detalle)


class RespuestasAutomaticasTests(_Base):
    """Las líneas oficiales NO contestan solas.

    `leads.whatsapp_auto` responde las preguntas frecuentes de un lead y ya pasa
    la sede al enviar. Sin este freno, esa respuesta saldría a nombre de la
    coordinadora de esa sede — que es exactamente lo que no debe pasar.
    """

    def _enviar(self, tipo, sede="lima"):
        # Cada envío lleva su propio id de WhatsApp: dos mensajes distintos no
        # pueden compartirlo (lo impide el constraint de deduplicación).
        respuesta = RespuestaFalsa(data={"key": {"id": f"MSG-{tipo}"}})
        with self.settings(EVOLUTION_API_URL="https://evo.example",
                           EVOLUTION_API_KEY="k", EVOLUTION_INSTANCE="conversemositaca"):
            with patch("mensajes.evolution.estado_en_vivo", return_value="open"), \
                 patch("mensajes.evolution.requests.post", return_value=respuesta) as post:
                registrar_y_enviar(self.clinica, telefono="987654321", texto="Hola",
                                   tipo=tipo, sede=sede)
        return post.call_args.args[0]

    def test_la_respuesta_automatica_no_sale_por_la_linea_oficial(self):
        url = self._enviar(Mensaje.Tipo.AUTOMATICO)
        self.assertNotIn("conversemoslima", url)
        self.assertIn("conversemositaca", url)

    def test_las_automatizaciones_autorizadas_si_usan_la_linea_de_la_sede(self):
        """Recordatorios, NPS y mensajes de coordinación sí salen por su sede."""
        for tipo in (Mensaje.Tipo.RECORDATORIO, Mensaje.Tipo.CONFIRMACION,
                     Mensaje.Tipo.SEGUIMIENTO, Mensaje.Tipo.MANUAL):
            with self.subTest(tipo=tipo):
                self.assertIn("conversemoslima", self._enviar(tipo))

    def test_solo_responde_sola_si_alguien_lo_enciende_a_proposito(self):
        self.lima.respuestas_automaticas = True
        self.lima.save(update_fields=["respuestas_automaticas"])
        self.assertIn("conversemoslima", self._enviar(Mensaje.Tipo.AUTOMATICO))


class AnalistaNoEnviaTests(_Base):
    """El rol de solo lectura no contacta pacientes, ni con las líneas nuevas."""

    def test_analista_no_puede_enviar(self):
        analista = Usuario.objects.create_user(
            email="analista@test.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.ANALISTA)
        paciente = self._paciente()
        with patch("mensajes.evolution.estado_en_vivo", return_value="open"), \
             patch("mensajes.evolution.requests.post") as post:
            with self.assertRaises(PermissionDenied):
                registrar_y_enviar(self.clinica, telefono=paciente.telefono, texto="Hola",
                                   tipo=Mensaje.Tipo.MANUAL, paciente=paciente,
                                   usuario=analista)
        post.assert_not_called()
        self.assertEqual(Mensaje.objects.count(), 0)


def _upsert(instancia="conversemoslima", *, msg_id="WA-1", from_me=False,
            jid="51987654321@s.whatsapp.net", texto="Hola, quiero una cita", extra_key=None):
    key = {"remoteJid": jid, "fromMe": from_me, "id": msg_id}
    if extra_key:
        key.update(extra_key)
    return {
        "event": "messages.upsert",
        "instance": instancia,
        "apikey": "SECRETO-DE-EVOLUTION",
        "data": {
            "key": key,
            "pushName": "Ana",
            "message": {"conversation": texto},
            "messageType": "conversation",
            "messageTimestamp": 1750000000,
        },
    }


def _update(instancia="conversemoslima", *, msg_id="WA-1", estado="READ"):
    return {
        "event": "messages.update",
        "instance": instancia,
        "apikey": "SECRETO-DE-EVOLUTION",
        "data": {"keyId": msg_id, "remoteJid": "51987654321@s.whatsapp.net",
                 "fromMe": True, "status": estado},
    }


class WebhookEvolutionTests(_Base):
    """El webhook de las líneas oficiales: escucha y registra, nada más."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.token = self.clinica.asegurar_token_webhook_evolution()
        self.url = reverse("evolution-webhook", args=[self.token])

    def _post(self, payload, url=None):
        return self.client.post(url or self.url, payload, format="json")

    # --- Puerta de entrada ---

    def test_token_invalido_no_procesa(self):
        r = self._post(_upsert(), url=reverse("evolution-webhook", args=["token-que-no-existe"]))
        self.assertEqual(r.status_code, 404)
        self.assertEqual(Mensaje.objects.count(), 0)

    def test_instancia_desconocida_no_procesa(self):
        """La línea de Eli (u otra clínica) no debe escribir en esta bitácora."""
        r = self._post(_upsert(instancia="conversemositaca"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json().get("ignorado"), "instancia_desconocida")
        self.assertEqual(Mensaje.objects.count(), 0)

    def test_instancia_apagada_no_procesa(self):
        self.lima.activo = False
        self.lima.save(update_fields=["activo"])
        r = self._post(_upsert())
        self.assertEqual(r.json().get("ignorado"), "instancia_inactiva")
        self.assertEqual(Mensaje.objects.count(), 0)

    def test_los_grupos_se_ignoran(self):
        r = self._post(_upsert(jid="120363000000@g.us"))
        self.assertEqual(r.json().get("ignorado"), "grupo")
        self.assertEqual(Mensaje.objects.count(), 0)

    # --- Entrantes ---

    def test_entrante_conocido_se_registra_una_vez(self):
        paciente = self._paciente(telefono="987654321")
        r = self._post(_upsert())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Mensaje.objects.count(), 1)
        m = Mensaje.objects.get()
        self.assertEqual(m.paciente_id, paciente.id)
        self.assertEqual(m.direccion, Mensaje.Direccion.ENTRANTE)
        self.assertEqual(m.estado, Mensaje.Estado.RECIBIDO)
        self.assertEqual(m.proveedor, Mensaje.Proveedor.EVOLUTION)
        self.assertEqual(m.sede, "lima")
        self.assertEqual(m.instancia, "conversemoslima")
        self.assertEqual(m.external_message_id, "WA-1")
        self.assertEqual(m.telefono, "51987654321")

    def test_entrante_desconocido_se_registra_sin_crear_lead(self):
        from leads.models import Lead

        r = self._post(_upsert())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Mensaje.objects.count(), 1)
        self.assertIsNone(Mensaje.objects.get().paciente_id)
        # Esta puerta NO capta: la captación es la de Eli, con su propio endpoint.
        self.assertEqual(Lead.objects.count(), 0)

    def test_reintento_del_mismo_mensaje_no_duplica(self):
        self._post(_upsert())
        r = self._post(_upsert())
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json().get("duplicado"))
        self.assertEqual(Mensaje.objects.count(), 1)

    def test_lid_sin_numero_real_no_inventa_telefono(self):
        r = self._post(_upsert(jid="123456789@lid"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Mensaje.objects.get().telefono, "")

    def test_lid_con_remote_jid_alt_resuelve_el_numero(self):
        r = self._post(_upsert(jid="123456789@lid",
                               extra_key={"remoteJidAlt": "51987654321@s.whatsapp.net"}))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Mensaje.objects.get().telefono, "51987654321")

    def test_from_me_se_registra_pero_no_se_reenvia(self):
        with patch("mensajes.evolution.estado_en_vivo", return_value="open"), \
             patch("mensajes.evolution.requests.post") as post:
            r = self._post(_upsert(from_me=True, msg_id="WA-SALIENTE"))
        self.assertEqual(r.status_code, 200)
        post.assert_not_called()
        m = Mensaje.objects.get()
        self.assertEqual(m.direccion, Mensaje.Direccion.SALIENTE)
        self.assertEqual(m.estado, Mensaje.Estado.ENVIADO)

    # --- Lo que NO debe pasar ---

    def test_no_responde_automaticamente(self):
        """Ni FAQs, ni IA, ni ningún envío: estas líneas las atiende una persona."""
        with patch("leads.whatsapp_auto.procesar_lead") as auto, \
             patch("mensajes.services.registrar_y_enviar") as enviar, \
             patch("mensajes.evolution.estado_en_vivo", return_value="open"), \
             patch("mensajes.evolution.requests.post") as post, \
             patch("core.estructurar_nota.estructurar") as ia:
            r = self._post(_upsert(texto="¿Cuánto cuesta la terapia de pareja?"))
        self.assertEqual(r.status_code, 200)
        auto.assert_not_called()
        enviar.assert_not_called()
        post.assert_not_called()
        ia.assert_not_called()

    def test_el_modulo_no_importa_whatsapp_auto_ni_openai(self):
        """Un vistazo al código: la puerta silenciosa no debe tener ese cable.

        Se mira el árbol de sintaxis y no el texto: los comentarios del módulo
        nombran `whatsapp_auto` justamente para explicar por qué NO se usa.
        """
        import ast
        import io
        from pathlib import Path

        arbol = ast.parse(io.open(
            Path(__file__).with_name("webhook_evolution.py"), encoding="utf-8").read())
        importados = []
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                importados += [a.name for a in nodo.names]
            elif isinstance(nodo, ast.ImportFrom):
                importados += [f"{nodo.module or ''}.{a.name}" for a in nodo.names]
        prohibidos = ("whatsapp_auto", "openai", "estructurar_nota", "transcripcion",
                      "captacion", "cloud_api")
        for modulo in importados:
            for malo in prohibidos:
                self.assertNotIn(malo, modulo,
                                 f"El webhook silencioso no debe importar {modulo}")
        # Tampoco debe llamar a nada que envíe: registrar_y_enviar, enviar_texto…
        llamadas = {getattr(n.func, "attr", getattr(n.func, "id", ""))
                    for n in ast.walk(arbol) if isinstance(n, ast.Call)}
        for prohibida in ("registrar_y_enviar", "enviar_texto", "procesar_lead",
                          "armar_respuesta", "post"):
            self.assertNotIn(prohibida, llamadas,
                             f"El webhook silencioso no debe llamar a {prohibida}()")

    def test_no_registra_el_payload_en_el_log(self):
        """El body de Evolution trae su apikey y el texto del paciente."""
        with self.assertLogs("mensajes.webhook_evolution", level="DEBUG") as capturado:
            self._post(_upsert(instancia="instancia-fantasma", texto="dato sensible"))
        registrado = "\n".join(capturado.output)
        self.assertNotIn("SECRETO-DE-EVOLUTION", registrado)
        self.assertNotIn("dato sensible", registrado)

    # --- Acuses de entrega ---

    def test_update_actualiza_el_estado(self):
        self._post(_upsert(from_me=True, msg_id="WA-9"))
        r = self._post(_update(msg_id="WA-9", estado="DELIVERY_ACK"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Mensaje.objects.get().estado, Mensaje.Estado.ENTREGADO)

    def test_el_estado_no_retrocede_de_leido_a_entregado(self):
        self._post(_upsert(from_me=True, msg_id="WA-9"))
        self._post(_update(msg_id="WA-9", estado="READ"))
        self.assertEqual(Mensaje.objects.get().estado, Mensaje.Estado.LEIDO)
        # El acuse de "entregado" llega tarde (WhatsApp no garantiza el orden).
        r = self._post(_update(msg_id="WA-9", estado="DELIVERY_ACK"))
        self.assertFalse(r.json().get("cambio"))
        self.assertEqual(Mensaje.objects.get().estado, Mensaje.Estado.LEIDO)

    def test_error_marca_el_mensaje_como_fallido(self):
        self._post(_upsert(from_me=True, msg_id="WA-9"))
        self._post(_update(msg_id="WA-9", estado="ERROR"))
        m = Mensaje.objects.get()
        self.assertEqual(m.estado, Mensaje.Estado.FALLIDO)
        self.assertEqual(m.error_codigo, "ERROR")

    def test_estado_desconocido_no_se_traduce_a_ciegas(self):
        self._post(_upsert(from_me=True, msg_id="WA-9"))
        r = self._post(_update(msg_id="WA-9", estado="PENDING"))
        self.assertEqual(r.json().get("ignorado"), "estado_no_mapeado")
        self.assertEqual(Mensaje.objects.get().estado, Mensaje.Estado.ENVIADO)

    def test_update_de_un_mensaje_que_no_conocemos_no_crea_nada(self):
        r = self._post(_update(msg_id="WA-QUE-NO-EXISTE"))
        self.assertEqual(r.json().get("ignorado"), "desconocido")
        self.assertEqual(Mensaje.objects.count(), 0)

    # --- Conexión ---

    def test_connection_update_deja_la_ultima_senal(self):
        r = self.client.post(self.url, {
            "event": "connection.update", "instance": "conversemoslima",
            "data": {"instance": "conversemoslima", "state": "open"},
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.lima.refresh_from_db()
        self.assertEqual(self.lima.ultimo_estado, "open")
        self.assertIsNotNone(self.lima.ultimo_evento_en)

    def test_evento_no_pedido_se_ignora(self):
        r = self._post({"event": "contacts.update", "instance": "conversemoslima", "data": {}})
        self.assertEqual(r.json().get("ignorado"), "evento_no_aplica")
        self.assertEqual(Mensaje.objects.count(), 0)


class MonitorEvolutionTests(_Base):
    """El tablero de gerencia: solo admin y sin secretos."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.admin = Usuario.objects.create_user(
            email="admin@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ADMIN)
        self.asistente = Usuario.objects.create_user(
            email="asis@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ASISTENTE)

    def test_estado_es_solo_para_admin(self):
        self.client.force_login(self.asistente)
        self.assertEqual(self.client.get(reverse("evolution-estado")).status_code, 403)
        self.assertEqual(self.client.get(reverse("evolution-instancias")).status_code, 403)

    def test_estado_no_devuelve_la_api_key(self):
        self.client.force_login(self.admin)
        with self.settings(EVOLUTION_API_URL="https://evo.example",
                           EVOLUTION_API_KEY="CLAVE-SUPER-SECRETA"):
            with patch("mensajes.monitor_evolution.requests.get",
                       return_value=RespuestaFalsa(data={"instance": {"state": "open"}})):
                r = self.client.get(reverse("evolution-estado"))
        self.assertEqual(r.status_code, 200)
        cuerpo = r.content.decode()
        self.assertNotIn("CLAVE-SUPER-SECRETA", cuerpo)
        self.assertNotIn("evo.example", cuerpo)
        self.assertIn("conversemoslima", cuerpo)
        self.assertEqual(r.json()["instancias"][0]["conexion"]["estado"], "open")

    def test_estado_no_devuelve_la_url_del_webhook(self):
        """La URL del webhook lleva el token secreto de la clínica dentro."""
        self.client.force_login(self.admin)
        token = self.clinica.asegurar_token_webhook_evolution()
        respuesta_webhook = RespuestaFalsa(data={
            "enabled": True,
            "url": f"https://testserver/api/webhook/evolution/{token}/",
            "events": ["MESSAGES_UPSERT", "MESSAGES_UPDATE", "CONNECTION_UPDATE"],
        })
        # Por cada linea el monitor consulta, en este orden: estado de conexion,
        # perfil (numero y nombre; trae tambien el token de la instancia) y webhook.
        respuesta_perfil = RespuestaFalsa(data=[{
            "name": "conversemoslima", "connectionStatus": "open",
            "ownerJid": "51987000111@s.whatsapp.net", "profileName": "Itaca Lima",
            "token": "TOKEN-DE-INSTANCIA-SECRETO",
        }])
        with self.settings(EVOLUTION_API_URL="https://evo.example", EVOLUTION_API_KEY="k"):
            with patch("mensajes.monitor_evolution.requests.get",
                       side_effect=[RespuestaFalsa(data={"instance": {"state": "open"}}),
                                    respuesta_perfil, respuesta_webhook] * 2):
                r = self.client.get(reverse("evolution-estado"))
        cuerpo = r.content.decode()
        self.assertNotIn(token, cuerpo)
        # El token de la instancia que devuelve fetchInstances tampoco sale.
        self.assertNotIn("TOKEN-DE-INSTANCIA-SECRETO", cuerpo)
        self.assertEqual(r.json()["instancias"][0]["perfil"]["numero"], "+51987000111")
        self.assertEqual(r.json()["instancias"][0]["perfil"]["perfil"], "Itaca Lima")
        webhook = r.json()["instancias"][0]["webhook"]
        self.assertTrue(webhook["configurado"])
        self.assertTrue(webhook["apunta_aqui"])
        self.assertEqual(webhook["faltan_eventos"], [])

    def test_instancias_no_sale_a_internet(self):
        self.client.force_login(self.admin)
        with patch("mensajes.monitor_evolution.requests.get") as get:
            r = self.client.get(reverse("evolution-instancias"))
        get.assert_not_called()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["instancias"]), 2)
        self.assertFalse(r.json()["instancias"][0]["respuestas_automaticas"])


class ConstraintsTests(_Base):
    """Las reglas que sostiene la base de datos, no un `if`."""

    def test_no_hay_dos_lineas_activas_para_la_misma_sede(self):
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                InstanciaEvolution.objects.create(
                    clinica=self.clinica, sede="lima", nombre_instancia="otra-de-lima")

    def test_si_la_anterior_esta_apagada_si_se_puede_registrar_otra(self):
        self.lima.activo = False
        self.lima.save(update_fields=["activo"])
        InstanciaEvolution.objects.create(
            clinica=self.clinica, sede="lima", nombre_instancia="conversemoslima2")
        self.assertEqual(evolution.instancia_para(self.clinica, "lima").nombre_instancia,
                         "conversemoslima2")

    def test_el_mismo_id_externo_no_entra_dos_veces(self):
        from django.db import IntegrityError, transaction

        datos = dict(clinica=self.clinica, texto="x", tipo=Mensaje.Tipo.MANUAL,
                     estado=Mensaje.Estado.ENVIADO, external_message_id="ABC")
        Mensaje.objects.create(**datos)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Mensaje.objects.create(**datos)

    def test_los_mensajes_sin_id_externo_no_chocan(self):
        """Los históricos y los que fallan antes de salir no tienen id."""
        for _ in range(3):
            Mensaje.objects.create(clinica=self.clinica, texto="x", tipo=Mensaje.Tipo.MANUAL,
                                   estado=Mensaje.Estado.FALLIDO)
        self.assertEqual(Mensaje.objects.count(), 3)


class LineaDesconectadaTests(TestCase):
    """No se intenta enviar por una línea sin sesión de WhatsApp.

    Sin sesión, Evolution revienta por dentro con un error de JavaScript —
    `onWhatsApp` para un texto, `waUploadToServer` para una imagen— que llegaba
    tal cual a la pantalla de la coordinadora. Son el mismo problema: la
    instancia nunca se emparejó. Preguntar antes convierte ese volcado en una
    frase que dice qué pasó.
    """

    def setUp(self):
        evolution.limpiar_memo_estado()
        self.clinica = Clinica.objects.create(nombre="Ítaca", slug="itaca-linea")
        InstanciaEvolution.objects.create(
            clinica=self.clinica, sede="piura", nombre_instancia="conversemospiura",
            entorno=InstanciaEvolution.Entorno.OFICIAL, activo=True)

    def tearDown(self):
        evolution.limpiar_memo_estado()

    def _ajustes(self):
        return self.settings(EVOLUTION_API_URL="https://evo.example",
                             EVOLUTION_API_KEY="clave-de-prueba")

    # --- 1. conectada: se intenta el envío -----------------------------------

    def test_linea_conectada_deja_enviar_texto(self):
        with self._ajustes(), \
             patch("mensajes.evolution.estado_en_vivo", return_value="open"), \
             patch("mensajes.evolution.requests.post",
                   return_value=RespuestaFalsa()) as post:
            r = evolution.enviar_texto(self.clinica, "987654321", "Hola", sede="piura")
        self.assertEqual(r["estado"], "enviado")
        self.assertEqual(post.call_count, 1)

    def test_linea_conectada_deja_enviar_imagen(self):
        with self._ajustes(), \
             patch("mensajes.evolution.estado_en_vivo", return_value="open"), \
             patch("mensajes.evolution.requests.post",
                   return_value=RespuestaFalsa()) as post:
            r = evolution.enviar_media(self.clinica, "987654321", contenido=b"\x89PNG..",
                                       mimetype="image/png", nombre_archivo="a.png",
                                       sede="piura")
        self.assertEqual(r["estado"], "enviado")
        self.assertEqual(post.call_count, 1)

    # --- 2. desconectada: ni se intenta --------------------------------------

    def test_linea_cerrada_no_llama_a_sendtext(self):
        with self._ajustes(), \
             patch("mensajes.evolution.estado_en_vivo", return_value="close"), \
             patch("mensajes.evolution.requests.post") as post:
            r = evolution.enviar_texto(self.clinica, "987654321", "Hola", sede="piura")
        self.assertEqual(r["estado"], "fallido")
        self.assertEqual(post.call_count, 0, "no debe intentarse el envío")

    def test_linea_cerrada_no_llama_a_sendmedia(self):
        """Aquí importa más: se ahorra armar varios MB de base64 para nada."""
        with self._ajustes(), \
             patch("mensajes.evolution.estado_en_vivo", return_value="close"), \
             patch("mensajes.evolution.requests.post") as post:
            r = evolution.enviar_media(self.clinica, "987654321", contenido=b"\x89PNG..",
                                       mimetype="image/png", nombre_archivo="a.png",
                                       sede="piura")
        self.assertEqual(r["estado"], "fallido")
        self.assertEqual(post.call_count, 0, "no debe intentarse el envío")

    def test_estado_intermedio_tambien_bloquea(self):
        """`connecting` no es `open`: el envío fallaría igual."""
        with self._ajustes(), \
             patch("mensajes.evolution.estado_en_vivo", return_value="connecting"), \
             patch("mensajes.evolution.requests.post") as post:
            r = evolution.enviar_texto(self.clinica, "987654321", "Hola", sede="piura")
        self.assertEqual(r["estado"], "fallido")
        self.assertEqual(post.call_count, 0)

    # --- 3. el mensaje nombra la sede ----------------------------------------

    def test_el_mensaje_dice_de_que_sede_es_la_linea(self):
        for sede, etiqueta in (("piura", "Piura"), ("lima", "Lima")):
            with self.subTest(sede=sede):
                evolution.limpiar_memo_estado()
                InstanciaEvolution.objects.update_or_create(
                    clinica=self.clinica, sede=sede,
                    defaults={"nombre_instancia": f"conversemos{sede}",
                              "entorno": InstanciaEvolution.Entorno.OFICIAL,
                              "activo": True})
                with self._ajustes(), \
                     patch("mensajes.evolution.estado_en_vivo", return_value="close"), \
                     patch("mensajes.evolution.requests.post"):
                    r = evolution.enviar_texto(self.clinica, "987654321", "Hola", sede=sede)
                self.assertEqual(
                    r["detalle"],
                    f"La línea de WhatsApp de {etiqueta} no está conectada. "
                    "El mensaje no fue enviado.")

    def test_el_codigo_permite_distinguirlo_en_la_interfaz(self):
        with self._ajustes(), \
             patch("mensajes.evolution.estado_en_vivo", return_value="close"), \
             patch("mensajes.evolution.requests.post"):
            r = evolution.enviar_texto(self.clinica, "987654321", "Hola", sede="piura")
        self.assertEqual(r["error_codigo"], "linea_desconectada")

    # --- 4. el error técnico no llega a la pantalla --------------------------

    def test_la_traza_de_javascript_no_llega_al_frontend(self):
        """El caso real: Evolution devolvía 500 con un TypeError de Baileys."""
        traza = ('{"status":500,"error":"Internal Server Error","response":'
                 '{"message":["TypeError: Cannot read properties of undefined '
                 "(reading 'waUploadToServer')\"]}}")
        respuesta = RespuestaFalsa(status_code=500, text=traza)
        with self._ajustes(), \
             patch("mensajes.evolution.estado_en_vivo", return_value="open"), \
             patch("mensajes.evolution.requests.post", return_value=respuesta):
            r = evolution.enviar_media(self.clinica, "987654321", contenido=b"\x89PNG..",
                                       mimetype="image/png", nombre_archivo="a.png",
                                       sede="piura")
        self.assertEqual(r["estado"], "fallido")
        for filtrado in ("TypeError", "waUploadToServer", "undefined",
                         "Internal Server Error", "status"):
            self.assertNotIn(filtrado, r["detalle"])
        self.assertIn("no pudo enviar el mensaje", r["detalle"])
        self.assertIn("Piura", r["detalle"])

    def test_el_error_tecnico_queda_en_el_log(self):
        """Lo que se le oculta a la coordinadora tiene que seguir estando."""
        respuesta = RespuestaFalsa(status_code=500, text="TypeError: waUploadToServer")
        with self._ajustes(), \
             patch("mensajes.evolution.estado_en_vivo", return_value="open"), \
             patch("mensajes.evolution.requests.post", return_value=respuesta):
            with self.assertLogs("mensajes.evolution", level="WARNING") as registro:
                evolution.enviar_texto(self.clinica, "987654321", "Hola", sede="piura")
        self.assertIn("waUploadToServer", "\n".join(registro.output))

    def test_un_corte_de_red_tampoco_ensena_la_excepcion(self):
        import requests as _requests

        with self._ajustes(), \
             patch("mensajes.evolution.estado_en_vivo", return_value="open"), \
             patch("mensajes.evolution.requests.post",
                   side_effect=_requests.ConnectionError("https://evo.example roto")):
            r = evolution.enviar_texto(self.clinica, "987654321", "Hola", sede="piura")
        self.assertEqual(r["estado"], "fallido")
        self.assertNotIn("evo.example", r["detalle"])
        self.assertIn("No se pudo conectar con el servidor de WhatsApp", r["detalle"])

    # --- que no se pregunte una vez por cada parte ---------------------------

    def test_el_estado_se_consulta_una_sola_vez_por_comunicacion(self):
        """Cuatro partes no son cuatro consultas: en ese rato nada cambia."""
        with self._ajustes(), \
             patch("mensajes.evolution.estado_en_vivo", return_value="open") as consulta, \
             patch("mensajes.evolution.requests.post", return_value=RespuestaFalsa()):
            for _ in range(4):
                evolution.enviar_texto(self.clinica, "987654321", "Hola", sede="piura")
        self.assertEqual(consulta.call_count, 1)

    def test_si_no_se_puede_preguntar_el_envio_se_intenta_igual(self):
        """No se puede afirmar que la línea esté mal: se deja que falle solo.

        Bloquear aquí inventaría una avería a partir de no haber podido
        preguntar, y rompería el respaldo por wa.me de toda la vida.
        """
        with self._ajustes(), \
             patch("mensajes.evolution.estado_en_vivo", return_value=""), \
             patch("mensajes.evolution.requests.post",
                   return_value=RespuestaFalsa()) as post:
            r = evolution.enviar_texto(self.clinica, "987654321", "Hola", sede="piura")
        self.assertEqual(r["estado"], "enviado")
        self.assertEqual(post.call_count, 1)


class EstadoRealDelEnvioTests(_Base):
    """Aceptado no es enviado.

    Un 200 de Evolution solo dice que la API recibió la petición. En producción
    un mensaje salió con 200 y su `key.id`, la pantalla dijo "enviado" y WhatsApp
    no lo confirmó jamás: no llegó ni el primer ✓. Estas pruebas sostienen la
    diferencia entre lo que el proveedor acepta y lo que WhatsApp confirma.

    Evolution 2.3.7 no registra `SERVER_ACK`, así que lo normal es saltar de
    "aceptado" a "entregado" sin pasar por "enviado". Eso es válido y está
    probado abajo.
    """

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.token = self.clinica.asegurar_token_webhook_evolution()
        self.url = reverse("evolution-webhook", args=[self.token])

    def _enviar(self, status_code=200, data=None, sede="piura"):
        """Un envío real por Evolution, con la respuesta del proveedor simulada."""
        paciente = self._paciente(sede=sede)
        with self.settings(EVOLUTION_API_URL="https://evo.example",
                           EVOLUTION_API_KEY="clave-de-prueba"):
            with patch("mensajes.evolution.estado_en_vivo", return_value="open"), \
                 patch("mensajes.evolution.requests.post",
                       return_value=RespuestaFalsa(status_code=status_code, data=data)):
                return registrar_y_enviar(
                    self.clinica, telefono=paciente.telefono, texto="Hola",
                    tipo=Mensaje.Tipo.RECORDATORIO, paciente=paciente)

    def _mensaje_en(self, estado, *, msg_id="WA-ACK", clinica=None, **extra):
        return Mensaje.objects.create(
            clinica=clinica or self.clinica, telefono="51987654321", texto="Hola",
            tipo=Mensaje.Tipo.CONTINUIDAD, estado=estado,
            direccion=Mensaje.Direccion.SALIENTE, proveedor=Mensaje.Proveedor.EVOLUTION,
            sede="piura", instancia="conversemospiura", external_message_id=msg_id,
            **extra)

    def _acuse(self, estado, msg_id="WA-ACK"):
        return self.client.post(
            self.url, _update("conversemospiura", msg_id=msg_id, estado=estado),
            format="json")

    # --- 1. Lo que el proveedor acepta -----------------------------------

    def test_1_http_200_se_guarda_como_aceptado(self):
        mensaje, resultado, _ = self._enviar(200, {"key": {"id": "WA-1"}, "status": "PENDING"})
        self.assertEqual(mensaje.estado, Mensaje.Estado.ACEPTADO)
        self.assertEqual(mensaje.external_message_id, "WA-1")
        # El `status` del proveedor se guarda tal cual: es su palabra, no la nuestra.
        self.assertEqual(mensaje.proveedor_status, "PENDING")
        self.assertIsNotNone(mensaje.aceptado_en)
        # El contrato interno con el resto del sistema NO cambia: para los
        # módulos que solo preguntan si salió, un 200 sigue siendo "enviado".
        self.assertEqual(resultado["estado"], "enviado")

    def test_1b_http_201_tambien_se_guarda_como_aceptado(self):
        mensaje, _, _ = self._enviar(201, {"key": {"id": "WA-2"}})
        self.assertEqual(mensaje.estado, Mensaje.Estado.ACEPTADO)

    def test_1c_una_respuesta_sin_status_no_inventa_ninguno(self):
        mensaje, _, _ = self._enviar(200, {"key": {"id": "WA-3"}})
        self.assertEqual(mensaje.proveedor_status, "")
        self.assertEqual(mensaje.estado, Mensaje.Estado.ACEPTADO)

    def test_1d_un_fallo_del_proveedor_sigue_siendo_fallido(self):
        mensaje, _, _ = self._enviar(500, {"error": "boom"})
        self.assertEqual(mensaje.estado, Mensaje.Estado.FALLIDO)
        self.assertIsNone(mensaje.aceptado_en)

    # --- 2 a 5. Cada acuse mueve al escalón que le toca ------------------

    def test_2_server_ack_pasa_a_enviado(self):
        m = self._mensaje_en(Mensaje.Estado.ACEPTADO)
        self.assertEqual(self._acuse("SERVER_ACK").status_code, 200)
        m.refresh_from_db()
        self.assertEqual(m.estado, Mensaje.Estado.ENVIADO)

    def test_3_delivery_ack_pasa_a_entregado(self):
        m = self._mensaje_en(Mensaje.Estado.ENVIADO)
        self._acuse("DELIVERY_ACK")
        m.refresh_from_db()
        self.assertEqual(m.estado, Mensaje.Estado.ENTREGADO)

    def test_4_read_pasa_a_leido(self):
        m = self._mensaje_en(Mensaje.Estado.ENTREGADO)
        self._acuse("READ")
        m.refresh_from_db()
        self.assertEqual(m.estado, Mensaje.Estado.LEIDO)

    def test_5_error_pasa_a_fallido(self):
        m = self._mensaje_en(Mensaje.Estado.ACEPTADO)
        self._acuse("ERROR")
        m.refresh_from_db()
        self.assertEqual(m.estado, Mensaje.Estado.FALLIDO)
        self.assertEqual(m.error_codigo, "ERROR")

    # --- 6 y 7. Evolution puede saltarse escalones ----------------------

    def test_6_aceptado_mas_delivery_ack_es_entregado(self):
        """El camino REAL en producción: nunca llega SERVER_ACK."""
        m = self._mensaje_en(Mensaje.Estado.ACEPTADO)
        self._acuse("DELIVERY_ACK")
        m.refresh_from_db()
        self.assertEqual(m.estado, Mensaje.Estado.ENTREGADO)

    def test_7_aceptado_mas_read_es_leido(self):
        m = self._mensaje_en(Mensaje.Estado.ACEPTADO)
        self._acuse("READ")
        m.refresh_from_db()
        self.assertEqual(m.estado, Mensaje.Estado.LEIDO)

    # --- 8 y 9. Nunca hacia atrás ---------------------------------------

    def test_8_leido_mas_delivery_ack_sigue_leido(self):
        m = self._mensaje_en(Mensaje.Estado.LEIDO)
        self._acuse("DELIVERY_ACK")
        m.refresh_from_db()
        self.assertEqual(m.estado, Mensaje.Estado.LEIDO)

    def test_9_entregado_mas_server_ack_sigue_entregado(self):
        m = self._mensaje_en(Mensaje.Estado.ENTREGADO)
        self._acuse("SERVER_ACK")
        m.refresh_from_db()
        self.assertEqual(m.estado, Mensaje.Estado.ENTREGADO)

    def test_9b_el_estado_nunca_vuelve_a_aceptado(self):
        m = self._mensaje_en(Mensaje.Estado.LEIDO)
        self.assertFalse(m.avanzar_estado(Mensaje.Estado.ACEPTADO))
        m.refresh_from_db()
        self.assertEqual(m.estado, Mensaje.Estado.LEIDO)

    # --- 10. El aviso de que nadie confirmó nada -------------------------

    def test_10_aceptado_hace_mas_de_dos_minutos_queda_sin_confirmacion(self):
        reciente = self._mensaje_en(Mensaje.Estado.ACEPTADO, msg_id="WA-NUEVO",
                                    aceptado_en=timezone.now())
        viejo = self._mensaje_en(Mensaje.Estado.ACEPTADO, msg_id="WA-VIEJO",
                                 aceptado_en=timezone.now() - timedelta(minutes=3))
        self.assertFalse(reciente.sin_confirmacion)
        self.assertTrue(viejo.sin_confirmacion)

    def test_10b_un_mensaje_confirmado_nunca_avisa(self):
        entregado = self._mensaje_en(Mensaje.Estado.ENTREGADO, msg_id="WA-OK",
                                     aceptado_en=timezone.now() - timedelta(hours=2))
        self.assertFalse(entregado.sin_confirmacion)

    # --- 11. Aceptado bloquea el reenvío --------------------------------

    def test_11_una_parte_aceptada_no_se_vuelve_a_enviar(self):
        """Falta el acuse, pero el mensaje SALIÓ: reenviarlo lo duplicaría."""
        paciente = self._paciente(sede="piura")
        grupo = uuid.uuid4()
        Mensaje.objects.create(
            clinica=self.clinica, paciente=paciente, telefono=paciente.telefono,
            texto="Hola", tipo=Mensaje.Tipo.CONTINUIDAD,
            estado=Mensaje.Estado.ACEPTADO, direccion=Mensaje.Direccion.SALIENTE,
            proveedor=Mensaje.Proveedor.EVOLUTION, sede="piura",
            instancia="conversemospiura", external_message_id="WA-YA-SALIO",
            grupo_envio=grupo, orden=1, aceptado_en=timezone.now())
        with self.settings(EVOLUTION_API_URL="https://evo.example",
                           EVOLUTION_API_KEY="clave-de-prueba"):
            with patch("mensajes.evolution.requests.post") as post:
                _partes, resumen = reintentar_comunicacion(self.clinica, grupo)
        post.assert_not_called()
        self.assertEqual(resumen["estado"], Mensaje.Estado.ACEPTADO)
        self.assertEqual(resumen["faltan"], 0)

    # --- 12 y 13. Los indicadores de gerencia ---------------------------

    def _recordatorio(self, estado, msg_id):
        return Mensaje.objects.create(
            clinica=self.clinica, telefono="51987654321", texto="Su cita es mañana",
            tipo=Mensaje.Tipo.RECORDATORIO, estado=estado,
            direccion=Mensaje.Direccion.SALIENTE, proveedor=Mensaje.Proveedor.EVOLUTION,
            sede="piura", instancia="conversemospiura", external_message_id=msg_id)

    def _resumen_gerencia(self):
        admin = Usuario.objects.create_user(
            email="gerencia@test.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.ADMIN)
        self.client.force_login(admin)
        r = self.client.get(reverse("gerencia-resumen"), {"periodo": "mes"})
        self.assertEqual(r.status_code, 200)
        return r.json()["operacion"]

    def test_12_el_kpi_de_recordatorios_no_cuenta_los_aceptados(self):
        """Contar un aceptado como enviado rearmaría el mismo espejismo."""
        self._recordatorio(Mensaje.Estado.ENVIADO, "R-1")
        self._recordatorio(Mensaje.Estado.ENTREGADO, "R-2")
        self._recordatorio(Mensaje.Estado.LEIDO, "R-3")
        self._recordatorio(Mensaje.Estado.ACEPTADO, "R-4")
        self._recordatorio(Mensaje.Estado.FALLIDO, "R-5")
        self.assertEqual(self._resumen_gerencia()["recordatorios"], 3)

    def test_13_los_aceptados_se_cuentan_aparte(self):
        self._recordatorio(Mensaje.Estado.ENTREGADO, "R-1")
        self._recordatorio(Mensaje.Estado.ACEPTADO, "R-2")
        self._recordatorio(Mensaje.Estado.ACEPTADO, "R-3")
        operacion = self._resumen_gerencia()
        self.assertEqual(operacion["recordatorios"], 1)
        self.assertEqual(operacion["recordatorios_sin_confirmar"], 2)

    # --- 14. El acuse cae en el mensaje correcto ------------------------

    def test_14_el_acuse_casa_por_external_message_id(self):
        objetivo = self._mensaje_en(Mensaje.Estado.ACEPTADO, msg_id="WA-OBJETIVO")
        senuelo = self._mensaje_en(Mensaje.Estado.ACEPTADO, msg_id="WA-OTRO")
        otra_clinica = Clinica.objects.create(nombre="Otra", slug="otra-evo")
        ajeno = self._mensaje_en(Mensaje.Estado.ACEPTADO, msg_id="WA-OBJETIVO",
                                 clinica=otra_clinica)

        self._acuse("DELIVERY_ACK", msg_id="WA-OBJETIVO")

        objetivo.refresh_from_db()
        senuelo.refresh_from_db()
        ajeno.refresh_from_db()
        self.assertEqual(objetivo.estado, Mensaje.Estado.ENTREGADO)
        self.assertEqual(senuelo.estado, Mensaje.Estado.ACEPTADO)
        # El mismo id en otra clínica no se toca: el webhook es por clínica.
        self.assertEqual(ajeno.estado, Mensaje.Estado.ACEPTADO)

    def test_14b_un_acuse_de_un_mensaje_que_no_registramos_se_ignora(self):
        r = self._acuse("DELIVERY_ACK", msg_id="WA-QUE-NO-EXISTE")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json().get("ignorado"), "desconocido")


class NombreDeArchivoMultimediaTests(_Base):
    """El `fileName` que ve Evolution decide el mimetype del mensaje.

    Evolution 2.3.7 ignora el `mimetype` del cuerpo y lo deduce del nombre del
    archivo. Sin extensión resuelve `false`, y WhatsApp descarta el mensaje sin
    un solo acuse: se sube el archivo, se crea el mensaje y no llega nada.

    Pasó en producción con la pieza "material_sin_extension", que se
    envió dos veces y se perdió las dos, con el .jpg correcto en disco.
    """

    IMAGEN = b"\xff\xd8\xff\xe0 bytes de una imagen \x00\x01"

    def _payload(self, *, nombre, mimetype, caption="Hola"):
        """Envía una imagen y devuelve el cuerpo JSON que recibió Evolution."""
        with self.settings(EVOLUTION_API_URL="https://evo.example",
                           EVOLUTION_API_KEY="clave-de-prueba"):
            with patch("mensajes.evolution.estado_en_vivo", return_value="open"), \
                 patch("mensajes.evolution.requests.post",
                       return_value=RespuestaFalsa()) as post:
                evolution.enviar_media(
                    self.clinica, "987654321", contenido=self.IMAGEN,
                    mimetype=mimetype, nombre_archivo=nombre, caption=caption,
                    sede="piura")
        return post.call_args.kwargs["json"]

    # --- 1 a 3. Sin extensión: se le pone la que dice el MIME ------------

    def test_1_jpeg_sin_extension(self):
        self.assertEqual(
            evolution._nombre_con_extension("material_sin_extension", "image/jpeg"),
            "material_sin_extension.jpg")

    def test_2_png_sin_extension(self):
        self.assertEqual(evolution._nombre_con_extension("ubicacion", "image/png"),
                         "ubicacion.png")

    def test_3_webp_sin_extension(self):
        self.assertEqual(evolution._nombre_con_extension("tarifas", "image/webp"),
                         "tarifas.webp")

    # --- 4 y 5. La que ya vale se respeta --------------------------------

    def test_4_jpg_no_se_duplica(self):
        self.assertEqual(evolution._nombre_con_extension("horarios.jpg", "image/jpeg"),
                         "horarios.jpg")

    def test_5_jpeg_es_igual_de_valida(self):
        """`.jpeg` describe el contenido tan bien como `.jpg`: no se toca."""
        self.assertEqual(evolution._nombre_con_extension("horarios.jpeg", "image/jpeg"),
                         "horarios.jpeg")

    # --- 6. La que miente se corrige -------------------------------------

    def test_6_extension_incoherente_se_reemplaza(self):
        """Manda el contenido, no cómo llamaron a la pieza."""
        self.assertEqual(evolution._nombre_con_extension("imagen.png", "image/jpeg"),
                         "imagen.jpg")

    def test_6b_un_punto_en_el_nombre_no_es_una_extension(self):
        self.assertEqual(
            evolution._nombre_con_extension("Horarios 2026. Sede Piura", "image/jpeg"),
            "Horarios 2026. Sede Piura.jpg")

    def test_6c_un_mime_desconocido_no_inventa_extension(self):
        self.assertEqual(evolution._nombre_con_extension("archivo", "application/pdf"),
                         "archivo")

    def test_6d_un_nombre_vacio_sigue_teniendo_nombre(self):
        self.assertEqual(evolution._nombre_con_extension("", "image/jpeg"), "imagen.jpg")

    def test_6e_un_nombre_larguisimo_conserva_la_extension(self):
        nombre = evolution._nombre_con_extension("x" * 300, "image/png")
        self.assertTrue(nombre.endswith(".png"))
        self.assertLessEqual(len(nombre), 120)

    # --- 7 a 9. El payload que sale de verdad ----------------------------

    def test_7_el_payload_lleva_mediatype_mimetype_y_filename_coherentes(self):
        cuerpo = self._payload(nombre="material_sin_extension",
                               mimetype="image/jpeg")
        self.assertEqual(cuerpo["mediatype"], "image")
        self.assertEqual(cuerpo["mimetype"], "image/jpeg")
        self.assertEqual(cuerpo["fileName"], "material_sin_extension.jpg")

    def test_8_los_bytes_enviados_no_cambian(self):
        import base64

        cuerpo = self._payload(nombre="pieza", mimetype="image/jpeg")
        self.assertEqual(base64.b64decode(cuerpo["media"]), self.IMAGEN)

    def test_9_el_pie_de_la_imagen_sigue_intacto(self):
        cuerpo = self._payload(nombre="pieza", mimetype="image/jpeg",
                               caption="Hola Ana, te comparto la ubicación 🩵")
        self.assertEqual(cuerpo["caption"], "Hola Ana, te comparto la ubicación 🩵")
