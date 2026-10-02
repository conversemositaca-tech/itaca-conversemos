"""Carga histórica conservadora: solo lo inequívoco, nada inventado."""
from io import StringIO

from django.core.management import call_command

from continuidad import historico
from continuidad.models import Estado, EventoContinuidad, Origen, ProcesoContinuidad
from pacientes.models import Cita

from .base import Base


class HistoricoTests(Base):
    def setUp(self):
        super().setUp()
        self.alta_dp = self.paciente("Alta DP")
        self.sesiones(self.alta_dp, [300, 293])
        self.cita(self.alta_dp, 286, decision="DP-10")
        self.derivado = self.paciente("Derivado")
        self.sesiones(self.derivado, [300])
        self.cita(self.derivado, 293, decision="DP-12")
        self.alta_ficha = self.paciente("Alta ficha", frecuencia="alta")
        self.sesiones(self.alta_ficha, [200])
        self.pausa_ficha = self.paciente("Pausa ficha", frecuencia="en_pausa")
        self.sesiones(self.pausa_ficha, [200])
        self.dp09 = self.paciente("DP09")
        self.cita(self.dp09, 200, decision="DP-09")
        self.se_fue = self.paciente("Se fue")          # solo inferencia
        self.sesiones(self.se_fue, [200, 193])
        self.contradice = self.paciente("Contradice", frecuencia="alta")
        self.sesiones(self.contradice, [100])
        self.cita(self.contradice, -5, estado=Cita.Estado.AGENDADA)

    def estado(self, p):
        # Sin evidencia la carga no escribe nada: ni siquiera crea el proceso.
        fila = ProcesoContinuidad.objects.filter(paciente=p).first()
        return fila.estado if fila else Estado.SIN_REGISTRO

    def test_auditoria_no_escribe(self):
        plan, conteo = historico.planificar(self.clinica)
        self.assertEqual(ProcesoContinuidad.objects.count(), 0)
        self.assertEqual(conteo["migrable:dp10"], 1)
        self.assertEqual(conteo["migrable:dp12"], 1)
        self.assertEqual(conteo["migrable:ficha_alta"], 1)
        self.assertEqual(conteo["migrable:ficha_pausa"], 1)
        self.assertEqual(conteo["omitido:dp09_ambiguo"], 1)
        self.assertEqual(conteo["omitido:sin_evidencia"], 1)
        self.assertEqual(conteo["omitido:conflicto_alta_con_proxima_cita"], 1)
        self.assertEqual(len(plan), 4)

    def test_aplica_solo_lo_inequivoco(self):
        call_command("migrar_continuidad_historica", "--aplicar", stdout=StringIO())
        self.assertEqual(self.estado(self.alta_dp), Estado.ALTA)
        self.assertEqual(self.estado(self.derivado), Estado.CERRADO)
        self.assertEqual(self.estado(self.alta_ficha), Estado.ALTA)
        self.assertEqual(self.estado(self.pausa_ficha), Estado.PAUSA)
        pausa = EventoContinuidad.objects.get(proceso__paciente=self.pausa_ficha)
        self.assertEqual((pausa.motivo.codigo, pausa.origen, pausa.registrado_por), ("SIN_INFORMACION", Origen.IMPORTACION, None))
        # Nada se inventa: ni el DP-09 ambiguo, ni el que solo tiene días sin venir,
        # ni el que contradice (alta con próxima cita).
        for p in (self.se_fue, self.contradice):
            self.assertEqual(self.estado(p), Estado.SIN_REGISTRO)
        self.assertFalse(EventoContinuidad.objects.filter(tipo="abandono_confirmado").exists())

    def test_es_idempotente(self):
        call_command("migrar_continuidad_historica", "--aplicar", stdout=StringIO())
        n = EventoContinuidad.objects.count()
        call_command("migrar_continuidad_historica", "--aplicar", stdout=StringIO())
        self.assertEqual(EventoContinuidad.objects.count(), n)
        self.assertEqual(n, 4)
