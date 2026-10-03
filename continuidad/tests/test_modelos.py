"""Modelos, catálogo de motivos y restricciones.

    python manage.py test continuidad
"""
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from continuidad.models import (
    CategoriaMotivo, Estado, EventoContinuidad, Frecuencia, MotivoContinuidad, Origen, ProcesoContinuidad, TipoEvento,
)
from continuidad.motivos import CATALOGO, asegurar_catalogo
from pacientes.fusion import plan_de_relaciones

from .base import REGISTRO_DESDE_SIEMPRE, Base


@REGISTRO_DESDE_SIEMPRE
class ModelosTests(Base):
    def test_historial_append_only(self):
        p = self.paciente()
        self.sesiones(p, [10])
        ev = self.proceso(p).eventos.get()
        ev.detalle_operativo = "otro"
        with self.assertRaises(ValidationError):
            ev.save()
        with self.assertRaises(ValidationError):
            ev.delete()
        self.assertEqual(EventoContinuidad.objects.count(), 1)

    def test_intervalo_solo_con_frecuencia_personalizada(self):
        p = self.paciente()
        self.sesiones(p, [10])
        proc = self.proceso(p)
        for frec, intervalo in ((Frecuencia.PERSONALIZADA, None), (Frecuencia.SEMANAL, 7),
                                (Frecuencia.PERSONALIZADA, 999)):
            with self.subTest(frec=frec, intervalo=intervalo), self.assertRaises(IntegrityError), transaction.atomic():
                ProcesoContinuidad.objects.filter(pk=proc.pk).update(
                    frecuencia_esperada=frec, intervalo_personalizado_dias=intervalo)

    def test_intervalo_esperado(self):
        proc = ProcesoContinuidad(frecuencia_esperada=Frecuencia.QUINCENAL)
        self.assertEqual(proc.intervalo_esperado, 14)
        proc.frecuencia_esperada, proc.intervalo_personalizado_dias = Frecuencia.PERSONALIZADA, 21
        self.assertEqual(proc.intervalo_esperado, 21)
        proc.frecuencia_esperada = Frecuencia.NO_DEFINIDA
        self.assertIsNone(proc.intervalo_esperado)

    def test_clave_de_idempotencia_unica_por_clinica(self):
        p = self.paciente()
        self.sesiones(p, [10])
        proc = self.proceso(p)
        datos = dict(clinica=self.clinica, proceso=proc, tipo=TipoEvento.CAMBIO_FRECUENCIA,
                     estado_nuevo=Estado.ACTIVO, fecha_efectiva=proc.fecha_inicio, origen=Origen.SISTEMA,
                     clave_idempotencia="k1")
        EventoContinuidad.objects.create(**datos)
        with self.assertRaises(IntegrityError), transaction.atomic():
            EventoContinuidad.objects.create(**datos)

    def test_la_fusion_de_duplicados_sabe_mover_los_procesos(self):
        """Ninguna restricción única sobre `paciente`: la consolidación no se bloquea."""
        a, b = self.paciente("A"), self.paciente("A")
        self.sesiones(b, [10])
        self.proceso(b)
        _, bloqueos = plan_de_relaciones(a, b)
        self.assertFalse([x for x in bloqueos if "continuidad" in x.lower()], bloqueos)


class MotivosTests(Base):
    def test_catalogo_completo_e_idempotente(self):
        self.assertEqual(MotivoContinuidad.objects.filter(clinica=self.clinica).count(), len(CATALOGO))
        self.assertEqual(asegurar_catalogo(self.clinica), 0)
        cats = set(MotivoContinuidad.objects.values_list("categoria", flat=True))
        self.assertEqual(cats, set(CategoriaMotivo.values))

    def test_no_pisa_un_motivo_editado_por_la_clinica(self):
        MotivoContinuidad.objects.filter(codigo="VIAJE").update(nombre="Viaje largo", activo=False)
        asegurar_catalogo(self.clinica)
        m = self.motivo("VIAJE")
        self.assertEqual((m.nombre, m.activo), ("Viaje largo", False))

    def test_mapeo_dp_segun_uso_real(self):
        dp = dict(MotivoContinuidad.objects.exclude(codigos_dp="").values_list("codigos_dp", "codigo"))
        self.assertEqual(dp["DP-14"], "ECONOMIA")
        self.assertEqual(dp["DP-15"], "HORARIO")
        self.assertEqual(dp["DP-16"], "INCONFORMIDAD_ATENCION")
        # DP-02 es una decisión de la consulta inicial: no es un motivo de salida.
        self.assertNotIn("DP-02", dp)
        self.assertNotIn("DP-09", dp)  # ambiguo: pausa o fin

    @REGISTRO_DESDE_SIEMPRE
    def test_motivo_usado_no_se_borra(self):
        from continuidad.servicios import transicionar_proceso
        p = self.paciente()
        self.sesiones(p, [10])
        transicionar_proceso(self.proceso(p), TipoEvento.PAUSA_INICIADA, self.coord, motivo=self.motivo("VIAJE"))
        with self.assertRaises(ProtectedError):
            self.motivo("VIAJE").delete()

    def test_ningun_motivo_es_clinico(self):
        palabras = ("diagn", "depres", "ansied", "trastorno", "riesgo", "suicid", "escala")
        for _, nombre, *_ in CATALOGO:
            self.assertFalse(any(w in nombre.lower() for w in palabras), nombre)
