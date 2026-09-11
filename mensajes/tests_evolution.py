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
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from core.models import Clinica, InstanciaEvolution
from mensajes import evolution
from mensajes.models import Mensaje
from mensajes.services import registrar_y_enviar
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
            with patch("mensajes.evolution.requests.post",
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
            with patch("mensajes.evolution.requests.post", return_value=respuesta) as post:
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
        with patch("mensajes.evolution.requests.post") as post:
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
        with patch("mensajes.evolution.requests.post") as post:
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
