from datetime import timedelta

from django.utils import timezone

from continuidad.models import Estado, EventoContinuidad, Frecuencia, Origen, TipoEvento as T
from continuidad.servicios import ConflictoEstado, ErrorTransicion, motivo_vigente, transicionar_proceso

from .base import REGISTRO_DESDE_SIEMPRE, Base


@REGISTRO_DESDE_SIEMPRE
class TransicionesTests(Base):
    def setUp(self):
        super().setUp()
        self.p = self.paciente(profesional=self.ana)
        self.sesiones(self.p, [30, 23, 16])
        self.proc = self.proceso(self.p)
        self.hoy = timezone.localdate()

    def t(self, tipo, usuario=None, **kw):
        return transicionar_proceso(self.proc, tipo, usuario or self.coord, **kw)

    def estado(self):
        self.proc.refresh_from_db()
        return self.proc.estado

    def tipos(self):
        return list(self.proc.eventos.values_list("tipo", flat=True))

    def test_nace_activo_con_evento_de_inicio(self):
        self.assertEqual(self.estado(), Estado.ACTIVO)
        self.assertEqual(self.tipos(), [T.INICIO_PROCESO])
        self.assertEqual(self.proc.eventos.get().origen, Origen.SISTEMA)

    def test_pausa_y_reactivacion_conservan_el_historial(self):
        r = self.t(T.PAUSA_INICIADA, motivo=self.motivo("VIAJE"), fecha_revision=self.hoy + timedelta(days=30))
        self.assertEqual((self.estado(), r.evento.estado_anterior), (Estado.PAUSA, Estado.ACTIVO))
        self.assertEqual(r.evento.origen, Origen.COORDINACION)
        r2 = self.t(T.REACTIVACION, usuario=self.admin)
        self.assertEqual((self.estado(), r2.evento.estado_anterior), (Estado.ACTIVO, Estado.PAUSA))
        self.assertEqual(r2.evento.origen, Origen.GERENCIA)
        self.assertEqual(self.tipos(), [T.INICIO_PROCESO, T.PAUSA_INICIADA, T.REACTIVACION])
        pausa = self.proc.eventos.get(tipo=T.PAUSA_INICIADA)
        self.assertEqual(pausa.motivo.codigo, "VIAJE")  # intacta

    def test_pausa_exige_motivo_y_no_fecha_fin(self):
        with self.assertRaises(ErrorTransicion):
            self.t(T.PAUSA_INICIADA)
        self.t(T.PAUSA_INICIADA, motivo=self.motivo("SIN_INFORMACION"))
        self.assertEqual(self.estado(), Estado.PAUSA)

    def test_alta_y_lo_que_no_se_puede_despues(self):
        self.t(T.ALTA, motivo=self.motivo("ALTA"))
        self.assertEqual(self.estado(), Estado.ALTA)
        for tipo, kw in ((T.PAUSA_INICIADA, {"motivo": self.motivo("VIAJE")}),
                         (T.CONTINUACION_CONFIRMADA, {}),
                         (T.CAMBIO_PROFESIONAL, {"profesional_nuevo": self.beto})):
            with self.subTest(tipo=tipo), self.assertRaises(ErrorTransicion):
                self.t(tipo, **kw)
        self.t(T.REACTIVACION)
        self.assertEqual(self.estado(), Estado.ACTIVO)

    def test_pausa_no_pasa_a_alta_sin_reactivar(self):
        self.t(T.PAUSA_INICIADA, motivo=self.motivo("VIAJE"))
        with self.assertRaises(ErrorTransicion):
            self.t(T.ALTA)

    def test_abandono_confirmado_y_reactivacion(self):
        self.t(T.ABANDONO_CONFIRMADO, motivo=self.motivo("ECONOMIA"))
        self.assertEqual(self.estado(), Estado.ABANDONO)
        with self.assertRaises(ErrorTransicion):
            self.t(T.CONTINUACION_CONFIRMADA)  # no vuelve a activo sin reactivación
        r = self.t(T.REACTIVACION)
        self.assertEqual((self.estado(), r.evento.estado_anterior), (Estado.ACTIVO, Estado.ABANDONO))

    def test_abandono_sin_motivo_conocido_se_registra_como_sin_informacion(self):
        with self.assertRaises(ErrorTransicion):
            self.t(T.ABANDONO_CONFIRMADO)
        self.t(T.ABANDONO_CONFIRMADO, motivo=self.motivo("SIN_INFORMACION"))
        self.assertEqual(self.estado(), Estado.ABANDONO)

    def test_cambio_de_profesional_sigue_activo_y_actualiza_la_ficha(self):
        r = self.t(T.CAMBIO_PROFESIONAL, profesional_nuevo=self.beto, motivo=self.motivo("HORARIO"))
        self.assertEqual(self.estado(), Estado.ACTIVO)
        self.assertEqual((r.evento.profesional_anterior, r.evento.profesional_nuevo), (self.ana, self.beto))
        self.p.refresh_from_db()
        self.assertEqual(self.p.profesional, self.beto)
        self.assertFalse(EventoContinuidad.objects.filter(tipo=T.ABANDONO_CONFIRMADO).exists())

    def test_cambio_de_profesional_invalido(self):
        from core.models import Clinica
        from usuarios.models import Profesional
        otra = Clinica.objects.create(nombre="Otra", slug="otra-c2")
        ajeno = Profesional.objects.create(clinica=otra, nombre="Ajeno")
        inactivo = Profesional.objects.create(clinica=self.clinica, nombre="Ido", activo=False)
        for prof in (None, ajeno, inactivo, self.ana):
            with self.subTest(prof=prof), self.assertRaises(ErrorTransicion):
                self.t(T.CAMBIO_PROFESIONAL, profesional_nuevo=prof)

    def test_cambio_de_frecuencia(self):
        r = self.t(T.CAMBIO_FRECUENCIA, frecuencia=Frecuencia.QUINCENAL)
        self.proc.refresh_from_db()
        self.assertEqual((r.evento.frecuencia_anterior, r.evento.frecuencia_nueva),
                         (Frecuencia.NO_DEFINIDA, Frecuencia.QUINCENAL))
        self.assertEqual(self.proc.intervalo_esperado, 14)
        with self.assertRaises(ErrorTransicion):
            self.t(T.CAMBIO_FRECUENCIA, frecuencia=Frecuencia.QUINCENAL)  # ya es esa
        with self.assertRaises(ErrorTransicion):
            self.t(T.CAMBIO_FRECUENCIA, frecuencia=Frecuencia.PERSONALIZADA)  # falta intervalo
        self.t(T.CAMBIO_FRECUENCIA, frecuencia=Frecuencia.PERSONALIZADA, intervalo_dias=21)
        self.proc.refresh_from_db()
        self.assertEqual(self.proc.intervalo_esperado, 21)

    def test_motivo_invalido(self):
        inactivo = self.motivo("MUDANZA")
        inactivo.activo = False
        inactivo.save()
        casos = [
            (T.PAUSA_INICIADA, self.motivo("NO_CONECTO_CON_PROFESIONAL")),  # no aplica a pausa
            (T.PAUSA_INICIADA, inactivo),
            (T.CONTINUACION_CONFIRMADA, self.motivo("VIAJE")),  # no lleva motivo
        ]
        for tipo, m in casos:
            with self.subTest(m=m.codigo), self.assertRaises(ErrorTransicion):
                self.t(tipo, motivo=m)

    def test_fechas(self):
        with self.assertRaises(ErrorTransicion):
            self.t(T.PAUSA_INICIADA, motivo=self.motivo("VIAJE"), fecha_efectiva=self.hoy + timedelta(days=1))
        with self.assertRaises(ErrorTransicion):
            self.t(T.PAUSA_INICIADA, motivo=self.motivo("VIAJE"), fecha_efectiva=self.proc.fecha_inicio - timedelta(days=1))
        with self.assertRaises(ErrorTransicion):
            self.t(T.PAUSA_INICIADA, motivo=self.motivo("VIAJE"), fecha_revision=self.hoy - timedelta(days=1))

    def test_estado_cambiado_entretanto_da_conflicto(self):
        self.t(T.PAUSA_INICIADA, motivo=self.motivo("VIAJE"))
        with self.assertRaises(ConflictoEstado):
            self.t(T.ALTA, estado_esperado=Estado.ACTIVO)

    def test_idempotencia_doble_clic(self):
        a = self.t(T.PAUSA_INICIADA, motivo=self.motivo("VIAJE"), clave_idempotencia="abc")
        b = self.t(T.PAUSA_INICIADA, motivo=self.motivo("VIAJE"), clave_idempotencia="abc")
        self.assertTrue(b.repetido)
        self.assertEqual(a.evento.pk, b.evento.pk)
        self.assertEqual(self.proc.eventos.filter(tipo=T.PAUSA_INICIADA).count(), 1)

    def test_correccion_de_motivo_es_un_evento_nuevo(self):
        r = self.t(T.ABANDONO_CONFIRMADO, motivo=self.motivo("ECONOMIA"))
        c = self.t(T.CORRECCION_MOTIVO, motivo=self.motivo("HORARIO"), corrige=r.evento)
        r.evento.refresh_from_db()
        self.assertEqual(r.evento.motivo.codigo, "ECONOMIA")  # el original no se toca
        self.assertEqual(self.estado(), Estado.ABANDONO)
        self.assertEqual(motivo_vigente(r.evento, {r.evento.id: [c.evento]}).codigo, "HORARIO")

    def test_inicio_no_lo_registra_una_persona(self):
        with self.assertRaises(ErrorTransicion):
            self.t(T.INICIO_PROCESO)


class LegacyTests(Base):
    """Procesos anteriores al registro formal: nacen sin estado formal."""

    def test_proceso_legacy_puede_formalizarse(self):
        p = self.paciente()
        self.sesiones(p, [300, 293])
        proc = self.proceso(p)
        self.assertEqual((proc.estado, proc.eventos.count()), (Estado.SIN_REGISTRO, 0))
        transicionar_proceso(proc, T.CONTINUACION_CONFIRMADA, self.coord)
        proc.refresh_from_db()
        self.assertEqual(proc.estado, Estado.ACTIVO)
