"""Concurrencia real del procesador de envíos: solo en PostgreSQL.

En SQLite `SELECT … FOR UPDATE SKIP LOCKED` no existe y este test se omite.
Para correrlo:

    DATABASE_URL=postgres://usuario@host:puerto/base \
        python manage.py test correo.tests.test_concurrencia_pg

Dos ciclos del cron corren a la vez en hilos con conexiones propias. Brevo
(simulado) tarda, para que los dos ciclos se pisen. Cada envío debe salir una
sola vez.
"""
import threading
import time
import unittest
from datetime import timedelta
from unittest import mock

from django.db import connection, connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from core.models import Clinica
from pacientes.models import Paciente
from correo.models import CorreoEnviado, EnvioProgramadoCorreo as EPC
from correo.services import programacion
from correo.services.destinatario import Destinatario

from .test_servicio import ENCENDIDO, respuesta

N_ENVIOS = 12


@unittest.skipUnless(connection.vendor == "postgresql", "Solo en PostgreSQL (SKIP LOCKED).")
@override_settings(**ENCENDIDO)
class ConcurrenciaPostgresTests(TransactionTestCase):
    # La migración de datos siembra las plantillas: hay que conservarlas.
    serialized_rollback = True

    def setUp(self):
        clinica = Clinica.objects.create(nombre="Conversemos", slug="concurrencia-pg")
        hace_un_rato = timezone.now() - timedelta(minutes=1)
        for i in range(N_ENVIOS):
            p = Paciente.objects.create(clinica=clinica, nombre=f"Persona {i}",
                                        email=f"p{i}@test.pe", sede="piura")
            programacion.programar(plantilla_clave="reserva_confirmada",
                                   destinatario=Destinatario.de_paciente(p),
                                   ejecutar_en=hace_un_rato, clave_idempotencia=f"pg:{i}")
        programacion._CONSTRUCTORES["reserva_confirmada"] = lambda e: (
            Destinatario.de_fila(e), {"fecha": "x", "hora": "y", "modalidad": "z"}, "prueba")

    def tearDown(self):
        from correo.flujos import reserva  # vuelve a registrar el constructor real
        programacion._CONSTRUCTORES["reserva_confirmada"] = reserva.construir

    def test_dos_ciclos_a_la_vez_no_envian_dos_veces(self):
        llamadas = []
        candado = threading.Lock()

        def brevo_lento(*args, **kwargs):
            with candado:
                llamadas.append(kwargs["json"]["to"][0]["email"])
            time.sleep(0.05)
            return respuesta()

        resultados, errores = [], []

        def ciclo():
            try:
                resultados.append(programacion.procesar_pendientes())
            except Exception as e:  # noqa: BLE001 — se reporta en la aserción
                errores.append(e)
            finally:
                connections.close_all()

        with mock.patch("correo.services.brevo.requests.post", side_effect=brevo_lento):
            hilos = [threading.Thread(target=ciclo) for _ in range(3)]
            for h in hilos:
                h.start()
            for h in hilos:
                h.join(timeout=60)

        self.assertEqual(errores, [])
        self.assertEqual(sorted(llamadas), sorted(set(llamadas)), "un correo salió dos veces")
        self.assertEqual(len(llamadas), N_ENVIOS)
        self.assertEqual(sum(r["tomados"] for r in resultados), N_ENVIOS)
        self.assertEqual(EPC.objects.filter(estado="ENVIADO").count(), N_ENVIOS)
        self.assertEqual(CorreoEnviado.objects.filter(estado="ENVIADO").count(), N_ENVIOS)

    def test_control_sin_bloqueo_los_ciclos_si_se_pisan(self):
        """Prueba que el test de arriba es sensible: sin FOR UPDATE SKIP LOCKED,
        dos ciclos toman los mismos envíos. (La clave de idempotencia evita el
        doble envío a Brevo, pero el trabajo se duplica.)"""
        def tomar_sin_bloqueo(qs, ahora):
            ids = list(qs.values_list("id", flat=True))
            time.sleep(0.3)  # ventana para que el otro ciclo lea lo mismo
            EPC.objects.filter(id__in=ids).update(estado=EPC.Estado.PROCESANDO, ultimo_intento_en=ahora)
            return ids

        tomados = []

        def ciclo():
            try:
                tomados.append(programacion.procesar_pendientes()["tomados"])
            finally:
                connections.close_all()

        with mock.patch.object(programacion, "_tomar", tomar_sin_bloqueo), \
                mock.patch("correo.services.brevo.requests.post", return_value=respuesta()) as post:
            hilos = [threading.Thread(target=ciclo) for _ in range(2)]
            for h in hilos:
                h.start()
            for h in hilos:
                h.join(timeout=60)
        self.assertGreater(sum(tomados), N_ENVIOS, "sin bloqueo se esperaba que se pisaran")
        # Aun así, la clave de idempotencia de la bitácora impide el doble envío.
        self.assertEqual(post.call_count, N_ENVIOS)
