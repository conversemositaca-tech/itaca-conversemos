from datetime import date, timedelta
from types import SimpleNamespace as NS

from continuidad.models import Estado, EventoContinuidad, ProcesoContinuidad
from continuidad.reconciliacion import emparejar, reconciliar_paciente
from pacientes.models import Cita

from .base import REGISTRO_DESDE_SIEMPRE, Base

D = date(2026, 3, 1)


def tramo(ids, inicio, fin=None):
    return {"ids": ids, "s1_fecha": inicio, "fin": fin or inicio}


def fila(id, ancla, inicio, fin=None):
    return NS(id=id, cita_inicio_id=ancla, fecha_inicio=inicio, fecha_inicio_original=inicio, fin_observado=fin)


class EmparejarTests(Base):
    def test_por_ancla_aunque_ya_no_sea_la_s1(self):
        asig, nuevos, marcas, _ = emparejar([tramo([5, 10, 11], D)], [fila(1, 10, D)])
        self.assertEqual((asig[0].id, nuevos, marcas), (1, [], {}))

    def test_dos_registrados_en_un_tramo_es_fusion_potencial(self):
        asig, _, marcas, _ = emparejar([tramo([10, 20], D)], [fila(1, 10, D), fila(2, 20, D + timedelta(7))])
        self.assertEqual(asig[0].id, 1)
        self.assertEqual(marcas, {2: "fusion_potencial"})

    def test_ancla_perdida_se_reubica_por_fecha_con_un_solo_candidato(self):
        asig, _, marcas, _ = emparejar([tramo([30], D + timedelta(5))], [fila(1, 99, D)])
        self.assertEqual((asig[0].id, marcas), (1, {}))

    def test_ancla_perdida_con_varios_candidatos_es_ambigua(self):
        asig, nuevos, marcas, _ = emparejar(
            [tramo([30], D + timedelta(3)), tramo([40], D - timedelta(3))], [fila(1, 99, D)])
        self.assertEqual((asig, sorted(nuevos), marcas), ({}, [0, 1], {1: "inicio_ambiguo"}))

    def test_sin_tramo(self):
        _, _, marcas, _ = emparejar([tramo([30], D + timedelta(100))], [fila(1, 99, D)])
        self.assertEqual(marcas, {1: "sin_tramo"})

    def test_division_potencial(self):
        _, nuevos, _, division = emparejar(
            [tramo([10], D, D + timedelta(7)), tramo([20], D + timedelta(14))],
            [fila(1, 10, D, fin=D + timedelta(21))])
        self.assertEqual((nuevos, division), ([1], {1}))


class ReconciliarTests(Base):
    def test_legacy_nace_sin_estado_y_no_se_duplica(self):
        p = self.paciente()
        self.sesiones(p, [300, 293])
        reconciliar_paciente(p.pk)
        reconciliar_paciente(p.pk)
        proc = ProcesoContinuidad.objects.get(paciente=p)
        self.assertEqual((proc.estado, proc.eventos.count()), (Estado.SIN_REGISTRO, 0))

    @REGISTRO_DESDE_SIEMPRE
    def test_corregir_la_fecha_de_la_s1_conserva_la_identidad(self):
        p = self.paciente()
        s1, *_ = self.sesiones(p, [30, 23])
        uuid = self.proceso(p).uuid
        Cita.objects.filter(pk=s1.pk).update(inicio=s1.inicio - timedelta(days=2))
        self.assertEqual(self.proceso(p).uuid, uuid)
        self.assertEqual(ProcesoContinuidad.objects.count(), 1)

    @REGISTRO_DESDE_SIEMPRE
    def test_anular_la_s1_reubica_por_fecha(self):
        p = self.paciente()
        s1, s2 = self.sesiones(p, [30, 25])
        uuid = self.proceso(p).uuid
        Cita.objects.filter(pk=s1.pk).update(estado=Cita.Estado.CANCELADA)
        proc = self.proceso(p)
        self.assertEqual((proc.uuid, proc.cita_inicio_id, proc.requiere_revision), (uuid, s2.pk, ""))

    @REGISTRO_DESDE_SIEMPRE
    def test_sin_citas_queda_para_revision_y_no_se_borra(self):
        p = self.paciente()
        (s1,) = self.sesiones(p, [30])
        proc = self.proceso(p)
        Cita.objects.filter(pk=s1.pk).update(estado=Cita.Estado.CANCELADA)
        reconciliar_paciente(p.pk)
        proc.refresh_from_db()
        self.assertEqual(proc.requiere_revision, "sin_tramo")
        self.assertEqual(EventoContinuidad.objects.filter(proceso=proc).count(), 1)

    @REGISTRO_DESDE_SIEMPRE
    def test_la_senal_de_la_agenda_crea_el_proceso(self):
        p = self.paciente()
        with self.captureOnCommitCallbacks(execute=True):
            self.cita(p, 3)
        self.assertEqual(ProcesoContinuidad.objects.filter(paciente=p).count(), 1)

    def test_la_agenda_no_se_cae_si_la_reconciliacion_falla(self):
        from unittest import mock
        p = self.paciente()
        with mock.patch("continuidad.reconciliacion.reconciliar_paciente", side_effect=RuntimeError("x")), \
                self.assertLogs("continuidad.reconciliacion", level="ERROR"), \
                self.captureOnCommitCallbacks(execute=True):
            self.cita(p, 3)
        self.assertEqual(Cita.objects.filter(paciente=p).count(), 1)


class FechaDeCorteTests(Base):
    """La fecha de corte se fija sola: nadie configura una variable."""

    def test_clinica_sin_configuracion_toma_el_primer_dia_de_uso(self):
        from django.utils import timezone

        from continuidad.models import ConfiguracionContinuidad
        viejo, nuevo = self.paciente("Viejo"), self.paciente("Nuevo")
        self.sesiones(viejo, [3])
        reconciliar_paciente(viejo.pk)
        conf = ConfiguracionContinuidad.objects.get(clinica=self.clinica)
        self.assertEqual(conf.registro_formal_desde, timezone.localdate())
        self.assertEqual(ProcesoContinuidad.objects.get(paciente=viejo).estado, Estado.SIN_REGISTRO)
        self.cita(nuevo, 0)  # S1 hoy: ya es registro formal
        reconciliar_paciente(nuevo.pk)
        self.assertEqual(ProcesoContinuidad.objects.get(paciente=nuevo).estado, Estado.ACTIVO)

    def test_la_fecha_no_se_mueve_despues(self):
        from continuidad.models import ConfiguracionContinuidad
        ConfiguracionContinuidad.objects.create(clinica=self.clinica, registro_formal_desde=date(2026, 1, 1))
        p = self.paciente()
        self.sesiones(p, [3])
        reconciliar_paciente(p.pk)
        self.assertEqual(ConfiguracionContinuidad.objects.get(clinica=self.clinica).registro_formal_desde,
                         date(2026, 1, 1))
        self.assertEqual(ProcesoContinuidad.objects.get(paciente=p).estado, Estado.ACTIVO)

    @REGISTRO_DESDE_SIEMPRE
    def test_el_setting_sobrescribe(self):
        p = self.paciente()
        self.sesiones(p, [300])
        self.assertEqual(self.proceso(p).estado, Estado.ACTIVO)
