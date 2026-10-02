"""Doble cobro y doble descuento de paquete con peticiones SIMULTÁNEAS.

SQLite serializa todas las escrituras y no puede reproducir la carrera; en
PostgreSQL dos peticiones llegan a la vez de verdad. Corre en el job
`postgres` del CI; en local se salta.

    DATABASE_URL=postgres://... python manage.py test finanzas.tests_concurrencia_pg
"""
import threading
import unittest
from datetime import timedelta

from django.db import connection, connections
from django.test import Client, TransactionTestCase
from django.utils import timezone

from core.models import Clinica
from finanzas.models import Cobro, Paquete
from pacientes.models import Cita, Paciente
from usuarios.models import Usuario


def _a_la_vez(n, funcion):
    """Lanza `funcion` en n hilos que arrancan juntos; devuelve sus resultados."""
    barrera = threading.Barrier(n)
    resultados = [None] * n

    def correr(i):
        try:
            barrera.wait()
            resultados[i] = funcion()
        finally:
            connections.close_all()

    hilos = [threading.Thread(target=correr, args=(i,)) for i in range(n)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    return resultados


@unittest.skipUnless(connection.vendor == "postgresql", "Solo en PostgreSQL (concurrencia real).")
class ConcurrenciaCobrosTests(TransactionTestCase):
    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="pg-cobros")
        self.coord = Usuario.objects.create_user(email="c@pg.pe", password="x", clinica=self.clinica, rol="asistente")
        self.medico = Usuario.objects.create_user(email="m@pg.pe", password="x", clinica=self.clinica, rol="medico")
        self.paciente = Paciente.objects.create(clinica=self.clinica, nombre="Ana")
        self.cita = Cita.objects.create(clinica=self.clinica, paciente=self.paciente, medico=self.medico,
                                        inicio=timezone.now() - timedelta(hours=1), estado=Cita.Estado.ATENDIDA)

    def _cliente(self):
        c = Client()
        c.force_login(self.coord)
        return c

    def test_dos_cobros_simultaneos_de_la_misma_cita_dejan_uno(self):
        def cobrar():
            return self._cliente().post("/api/cobros/", {
                "paciente": self.paciente.id, "cita": self.cita.id, "monto": "80",
                "estado": "pagado", "medio_pago": "efectivo"}, content_type="application/json").status_code

        codigos = sorted(_a_la_vez(4, cobrar))
        self.assertEqual(codigos.count(201), 1, codigos)
        self.assertEqual(Cobro.objects.filter(cita=self.cita).count(), 1)

    def test_atender_dos_veces_a_la_vez_descuenta_una_sesion(self):
        Cita.objects.filter(pk=self.cita.pk).update(estado=Cita.Estado.CONFIRMADA)
        paq = Paquete.objects.create(clinica=self.clinica, paciente=self.paciente, nombre="4",
                                     sesiones_total=4, monto=200)

        def marcar():
            return self._cliente().post(f"/api/citas/{self.cita.id}/estado/", {"estado": "atendida"},
                                        content_type="application/json").status_code

        _a_la_vez(4, marcar)
        paq.refresh_from_db()
        self.assertEqual(paq.sesiones_usadas, 1)
