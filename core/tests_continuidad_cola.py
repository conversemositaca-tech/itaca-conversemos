"""Pruebas de la cola de trabajo de "Evaluar continuidad".

La tarjeta original listaba todos los cierres de bloque sin decisión de la
historia del sistema (391 en producción el 9 sep 2026; 303 de ellos llevaban
más de 90 días sin venir). Ahora se clasifica cada caso por la FECHA real del
cierre — hoy, vencido, próximo, sin agendar, continuó sin decisión, antiguo —
y la pantalla "Hoy" muestra solo lo que pide acción.

    python manage.py test core.tests_continuidad_cola
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core import continuidad as C
from core.models import Clinica
from pacientes.models import Cita, Paciente
from usuarios.models import Profesional, Usuario


def _dt(dias):
    """Un datetime a `dias` días de hoy (negativo = pasado), a las 10:00 locales."""
    base = timezone.localtime(timezone.now()).replace(hour=10, minute=0, second=0, microsecond=0)
    return base + timedelta(days=dias)


class _Base(TestCase):
    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-cola")
        self.psico = Usuario.objects.create_user(
            email="psico-cola@test.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.MEDICO, sede=Usuario.Sede.PIURA,
        )
        self.ficha = Profesional.objects.create(
            clinica=self.clinica, usuario=self.psico, nombre="Angi Demo", sede="piura")
        self.hoy = timezone.localdate()

    def _paciente(self, nombre, sede="piura", ficha=None, **kw):
        kw.setdefault("frecuencia", "semanal")
        return Paciente.objects.create(
            clinica=self.clinica, nombre=nombre, sede=sede, profesional=ficha or self.ficha, **kw)

    def _asistidas(self, p, n, ultima_hace, decision_ultima=""):
        """`n` sesiones asistidas, semanales, la última hace `ultima_hace` días."""
        for i in range(n):
            Cita.objects.create(
                clinica=self.clinica, paciente=p, medico=self.psico, n_sesion=i + 1,
                estado=Cita.Estado.ASISTIO, inicio=_dt(-ultima_hace - 7 * (n - 1 - i)),
                decision=decision_ultima if i == n - 1 else "",
            )

    def _agendada(self, p, en_dias, n_sesion=None):
        return Cita.objects.create(
            clinica=self.clinica, paciente=p, medico=self.psico, n_sesion=n_sesion,
            estado=Cita.Estado.AGENDADA, inicio=_dt(en_dias),
        )

    def _cola(self, **kw):
        return C.cola_de_continuidad(Paciente.objects.filter(clinica=self.clinica), **kw)

    def _fila(self, p, **kw):
        return next((f for f in self._cola(**kw) if f["id"] == p.id), None)


class ClasificacionTests(_Base):
    """Cada estado de la cola, con un paciente de ejemplo."""

    def test_cierra_hoy_sin_decision(self):
        p = self._paciente("Cierra hoy")
        self._asistidas(p, 6, ultima_hace=0)
        f = self._fila(p)
        self.assertEqual((f["estado"], f["dias"], f["meta"]), (C.EstadoCierre.HOY, 0, 6))
        self.assertEqual(f["fecha_cierre"], self.hoy.isoformat())

    def test_vencido_cuenta_los_dias_desde_el_cierre(self):
        p = self._paciente("Vencido")
        self._asistidas(p, 6, ultima_hace=16)
        f = self._fila(p)
        self.assertEqual((f["estado"], f["dias"]), (C.EstadoCierre.VENCIDO, 16))

    def test_proximo_si_la_sesion_de_cierre_ya_esta_agendada(self):
        p = self._paciente("Cierra el jueves")
        self._asistidas(p, 5, ultima_hace=2)
        self._agendada(p, en_dias=3, n_sesion=6)
        f = self._fila(p)
        self.assertEqual((f["estado"], f["dias"]), (C.EstadoCierre.PROXIMO, -3))
        self.assertTrue(f["tiene_proxima"])

    def test_proximo_tambien_si_la_cita_agendada_no_trae_numero(self):
        p = self._paciente("Cita sin número")
        self._asistidas(p, 5, ultima_hace=4)
        self._agendada(p, en_dias=1)
        self.assertEqual(self._fila(p)["estado"], C.EstadoCierre.PROXIMO)

    def test_a_una_sesion_de_cerrar_y_sin_cita_es_sin_agendar(self):
        p = self._paciente("Sin agendar")
        self._asistidas(p, 5, ultima_hace=3)
        f = self._fila(p)
        self.assertEqual(f["estado"], C.EstadoCierre.SIN_AGENDAR)
        self.assertIsNone(f["fecha_cierre"])

    def test_mas_alla_de_la_ventana_todavia_no_aparece(self):
        p = self._paciente("Cierra en tres semanas")
        self._asistidas(p, 5, ultima_hace=2)
        self._agendada(p, en_dias=20, n_sesion=6)
        self.assertIsNone(self._fila(p))
        # Con una ventana más ancha sí entra: la ventana es configurable.
        self.assertEqual(self._fila(p, dias_proximos=30)["estado"], C.EstadoCierre.PROXIMO)

    def test_la_decision_registrada_lo_saca_de_la_cola(self):
        p = self._paciente("Ya decidido")
        self._asistidas(p, 6, ultima_hace=3, decision_ultima="DP-08")
        self.assertIsNone(self._fila(p))

    def test_continuo_sin_decision_es_calidad_de_registro_no_urgencia(self):
        """Pasó el cierre de la 6 sin decisión y siguió viniendo (va por la 9).
        El evento pendiente es el cierre de la 6 —meta 6, anclado en la cita de
        la sesión 6—, no un cierre de la 12 que todavía no existe."""
        p = self._paciente("Siguió viniendo")
        self._asistidas(p, 9, ultima_hace=2)
        f = self._fila(p)
        self.assertEqual((f["estado"], f["meta"]), (C.EstadoCierre.CONTINUO_SIN_DECISION, 6))
        s6 = Cita.objects.get(paciente=p, n_sesion=6)
        self.assertEqual(f["evento"]["cita_referencia"], s6.id)

    def test_un_cierre_de_hace_meses_es_backlog_no_operacion_del_dia(self):
        p = self._paciente("Heredado")
        self._asistidas(p, 6, ultima_hace=120)
        f = self._fila(p)
        self.assertEqual((f["estado"], f["dias"]), (C.EstadoCierre.BACKLOG, 120))
        # El umbral también es configurable.
        self.assertEqual(self._fila(p, dias_backlog=200)["estado"], C.EstadoCierre.VENCIDO)

    def test_frecuencia_cerrada_no_entra(self):
        p = self._paciente("De alta", frecuencia="alta")
        self._asistidas(p, 6, ultima_hace=1)
        self.assertIsNone(self._fila(p))

    def test_sin_citas_asistidas_no_entra(self):
        p = self._paciente("Solo agendado")
        self._agendada(p, en_dias=1)
        self.assertIsNone(self._fila(p))

    def test_la_fecha_del_cierre_sale_de_la_cita_con_ese_numero(self):
        """Si la sesión 6 se asistió hace 10 días y luego hubo una 'extra'
        sin número hace 2, el cierre sigue siendo el de hace 10."""
        p = self._paciente("Con extra")
        self._asistidas(p, 6, ultima_hace=10)
        Cita.objects.create(clinica=self.clinica, paciente=p, medico=self.psico,
                            estado=Cita.Estado.ASISTIO, inicio=_dt(-2))
        f = self._fila(p)
        self.assertEqual((f["estado"], f["dias"], f["origen_fecha"]), (C.EstadoCierre.VENCIDO, 10, "numero"))


class DecisionPorBloqueTests(_Base):
    """La decisión de cada cierre se evalúa contra la cita que cierra ESE
    bloque, no contra la última cita asistida. Que S7 no traiga DP no significa
    que falte la decisión del cierre 6; que S6 sí la traiga cierra ese bloque
    aunque el paciente siga viniendo."""

    def _sesiones(self, p, n, ultima_hace, decisiones=None):
        """n sesiones numeradas, semanales; `decisiones` = {n_sesion: "DP-xx"}."""
        decisiones = decisiones or {}
        for i in range(1, n + 1):
            Cita.objects.create(
                clinica=self.clinica, paciente=p, medico=self.psico, n_sesion=i,
                estado=Cita.Estado.ASISTIO, inicio=_dt(-ultima_hace - 7 * (n - i)),
                decision=decisiones.get(i, ""),
            )

    def _s(self, p, k):
        return Cita.objects.get(paciente=p, n_sesion=k)

    def test_s6_con_dp_y_s7_sin_dp_no_reclama_nada(self):
        p = self._paciente("Decidió en la 6")
        self._sesiones(p, 7, ultima_hace=2, decisiones={6: "DP-08"})
        self.assertIsNone(self._fila(p))          # ni "continuó", ni pendiente de la 12

    def test_s6_sin_dp_y_s7_es_continuo_del_cierre_6(self):
        p = self._paciente("Siguió sin decidir")
        self._sesiones(p, 7, ultima_hace=2)
        f = self._fila(p)
        self.assertEqual((f["estado"], f["meta"]), (C.EstadoCierre.CONTINUO_SIN_DECISION, 6))
        self.assertEqual(f["evento"]["cita_referencia"], self._s(p, 6).id)

    def test_s6_sin_dp_con_s7_y_s8_sigue_siendo_el_mismo_evento(self):
        p = self._paciente("Va por la 8")
        self._sesiones(p, 7, ultima_hace=9)
        antes = self._fila(p)["evento"]
        Cita.objects.create(clinica=self.clinica, paciente=p, medico=self.psico, n_sesion=8,
                            estado=Cita.Estado.ASISTIO, inicio=_dt(-2))
        filas = [f for f in self._cola() if f["id"] == p.id]
        self.assertEqual(len(filas), 1)           # una sola fila, no una por sesión extra
        despues = filas[0]["evento"]
        self.assertEqual((antes["tipo"], antes["meta"], antes["cita_referencia"]),
                         (despues["tipo"], despues["meta"], despues["cita_referencia"]))
        self.assertEqual(filas[0]["n_sesion"], 8)

    def test_s6_con_dp_y_s7_s8_s9_sin_alerta_del_cierre_6(self):
        p = self._paciente("Decidió y siguió")
        self._sesiones(p, 9, ultima_hace=1, decisiones={6: "DP-08"})
        self.assertIsNone(self._fila(p))

    def test_al_acercarse_al_cierre_12_aplican_las_reglas_del_bloque_12(self):
        p = self._paciente("Camino a la 12")
        self._sesiones(p, 11, ultima_hace=3, decisiones={6: "DP-08"})
        f = self._fila(p)                          # a una sesión del cierre 12, sin cita
        self.assertEqual((f["estado"], f["meta"]), (C.EstadoCierre.SIN_AGENDAR, 12))
        self.assertEqual(f["evento"]["cita_referencia"], self._s(p, 11).id)
        self.assertEqual(f["evento"]["referencia_origen"], "pre_cierre")
        self.assertEqual(f["anteriores_sin_decision"], [])   # la 6 sí se decidió
        Cita.objects.create(clinica=self.clinica, paciente=p, medico=self.psico, n_sesion=12,
                            estado=Cita.Estado.ASISTIO, inicio=_dt(0))
        f = self._fila(p)                          # cerró hoy la 12
        self.assertEqual((f["estado"], f["meta"]), (C.EstadoCierre.HOY, 12))
        self.assertEqual(f["evento"]["cita_referencia"], self._s(p, 12).id)

    def test_cierre_12_vigente_con_la_6_sin_decidir_muestra_la_12_y_anota_la_6(self):
        """Dos cierres sin decisión: manda el vigente (acción), y el anterior
        no se pierde: viaja en `anteriores_sin_decision` para el detalle."""
        p = self._paciente("Doble pendiente")
        self._sesiones(p, 12, ultima_hace=3)
        f = self._fila(p)
        self.assertEqual((f["estado"], f["meta"]), (C.EstadoCierre.VENCIDO, 12))
        self.assertEqual(f["anteriores_sin_decision"], [6])

    def test_decidida_la_12_sube_el_cierre_6_que_quedo_sin_decidir(self):
        p = self._paciente("Decidió la 12, no la 6")
        self._sesiones(p, 12, ultima_hace=3, decisiones={12: "DP-08"})
        f = self._fila(p)
        self.assertEqual((f["estado"], f["meta"]), (C.EstadoCierre.CONTINUO_SIN_DECISION, 6))

    def test_una_decision_en_la_ultima_sesion_cierra_el_bloque_vigente(self):
        """Regresión: "finaliza proceso" en la 5 significa que no habrá cierre
        de la 6 que evaluar. Esa regla se conserva para el bloque vigente."""
        p = self._paciente("Terminó en la 5")
        self._sesiones(p, 5, ultima_hace=2, decisiones={5: "DP-09"})
        self.assertIsNone(self._fila(p))

    def test_s3_con_decision_en_esa_sesion_no_es_riesgo(self):
        p = self._paciente("No inicia")
        self._sesiones(p, 3, ultima_hace=2, decisiones={3: "DP-04"})
        self.assertIsNone(self._fila(p))


class IdentidadDelEventoTests(_Base):
    """La identidad de un evento (tipo, meta, cita de referencia) sale de la
    condición detectada y es la misma la abra quien la abra y cuando la abra.
    Estos son los tests de la clave de gestión, ANTES de que exista el modelo."""

    def _sesiones(self, p, n, ultima_hace, decisiones=None, desde=1):
        decisiones = decisiones or {}
        for i in range(desde, n + 1):
            Cita.objects.create(
                clinica=self.clinica, paciente=p, medico=self.psico, n_sesion=i,
                estado=Cita.Estado.ASISTIO, inicio=_dt(-ultima_hace - 7 * (n - i)),
                decision=decisiones.get(i, ""),
            )

    def _identidad(self, p):
        f = self._fila(p)
        return f and (f["evento"]["tipo"], f["evento"]["meta"], f["evento"]["cita_referencia"])

    def _s(self, p, k, **filtro):
        return Cita.objects.filter(paciente=p, n_sesion=k, **filtro).order_by("inicio")

    def test_s6_del_primer_proceso_y_s6_de_uno_posterior_no_colisionan(self):
        p = self._paciente("Dos procesos")
        self._sesiones(p, 6, ultima_hace=300, decisiones={6: "DP-10"})   # proceso 1, con alta
        self._sesiones(p, 6, ultima_hace=4)                              # proceso 2, sin decidir
        vieja, nueva = self._s(p, 6)
        identidad = self._identidad(p)
        self.assertEqual(identidad, (C.TIPO_CIERRE_BLOQUE, 6, nueva.id))
        self.assertNotEqual(identidad[2], vieja.id)
        self.assertEqual(self._fila(p)["estado"], C.EstadoCierre.VENCIDO)

    def test_s6_sin_dp_que_llega_a_s7_y_s8_es_un_solo_evento(self):
        p = self._paciente("Un solo evento")
        self._sesiones(p, 6, ultima_hace=16)
        en_6 = self._identidad(p)
        self._sesiones(p, 8, ultima_hace=2, desde=7)
        en_8 = self._identidad(p)
        self.assertEqual(en_6, en_8)
        self.assertEqual(en_8[2], self._s(p, 6).get().id)

    def test_cerrar_y_reabrir_la_misma_condicion_da_la_misma_identidad(self):
        p = self._paciente("Reversión")
        self._sesiones(p, 6, ultima_hace=5)
        antes = self._identidad(p)
        s6 = self._s(p, 6).get()
        s6.decision = "DP-08"; s6.save(update_fields=["decision"])
        self.assertIsNone(self._identidad(p))      # resuelto por la fuente oficial
        s6.decision = ""; s6.save(update_fields=["decision"])
        self.assertEqual(self._identidad(p), antes)  # misma identidad: no es un evento nuevo

    def test_un_nuevo_proceso_da_identidad_nueva(self):
        p = self._paciente("Proceso nuevo")
        self._sesiones(p, 6, ultima_hace=200)
        primera = self._identidad(p)
        s6 = self._s(p, 6).get(); s6.decision = "DP-10"; s6.save(update_fields=["decision"])
        self._sesiones(p, 6, ultima_hace=3)
        segunda = self._identidad(p)
        self.assertEqual((primera[0], primera[1]), (segunda[0], segunda[1]))   # mismo tipo y meta…
        self.assertNotEqual(primera[2], segunda[2])                            # …pero otra cita

    def test_s6_y_s12_nunca_comparten_identidad(self):
        p = self._paciente("Seis y doce")
        self._sesiones(p, 12, ultima_hace=3)
        f = self._fila(p)
        self.assertEqual(f["evento"]["meta"], 12)
        self.assertEqual(f["evento"]["cita_referencia"], self._s(p, 12).get().id)
        s12 = self._s(p, 12).get(); s12.decision = "DP-08"; s12.save(update_fields=["decision"])
        f = self._fila(p)                          # ahora sube el cierre 6 pendiente
        self.assertEqual(f["evento"]["meta"], 6)
        self.assertEqual(f["evento"]["cita_referencia"], self._s(p, 6).get().id)

    def test_pre_cierre_y_cierre_del_mismo_bloque_comparten_anclas(self):
        """A la 5 el evento se ancla en la 5; cuando llega la 6 se ancla en la
        6, pero la 5 sigue entre sus anclas: es el mismo evento avanzando."""
        p = self._paciente("Avanza")
        self._sesiones(p, 5, ultima_hace=3)
        f5 = self._fila(p)
        s5 = self._s(p, 5).get()
        self.assertEqual((f5["estado"], f5["evento"]["cita_referencia"]), (C.EstadoCierre.SIN_AGENDAR, s5.id))
        self.assertEqual(f5["evento"]["anclas"], [s5.id])
        self._sesiones(p, 6, ultima_hace=0, desde=6)
        f6 = self._fila(p)
        s6 = self._s(p, 6).get()
        self.assertEqual((f6["estado"], f6["evento"]["cita_referencia"]), (C.EstadoCierre.HOY, s6.id))
        self.assertIn(s5.id, f6["evento"]["anclas"])
        self.assertIn(s6.id, f6["evento"]["anclas"])

    def test_riesgo_s3_se_ancla_en_la_cita_de_la_sesion_3(self):
        p = self._paciente("S3")
        self._sesiones(p, 3, ultima_hace=4)
        f = self._fila(p)
        s3 = self._s(p, 3).get()
        self.assertEqual((f["evento"]["tipo"], f["evento"]["meta"], f["evento"]["cita_referencia"]),
                         (C.TIPO_RIESGO_S3, 3, s3.id))
        self.assertEqual(f["evento"]["anclas"], [s3.id])

    def test_la_identidad_no_depende_del_momento_en_que_se_mira(self):
        """Abrirlo hoy o dentro de tres días da la misma referencia."""
        from datetime import timedelta
        p = self._paciente("Cuando sea")
        self._sesiones(p, 6, ultima_hace=2)
        hoy = C.cola_de_continuidad(Paciente.objects.filter(pk=p.pk))[0]["evento"]
        luego = C.cola_de_continuidad(Paciente.objects.filter(pk=p.pk),
                                      hoy=self.hoy + timedelta(days=3))[0]["evento"]
        self.assertEqual(hoy, luego)


class OrdenYResumenTests(_Base):
    def test_orden_primero_lo_vencido_mas_viejo_luego_hoy_luego_proximos(self):
        viejo = self._paciente("Vencido 30"); self._asistidas(viejo, 6, ultima_hace=30)
        reciente = self._paciente("Vencido 5"); self._asistidas(reciente, 6, ultima_hace=5)
        hoy = self._paciente("Hoy"); self._asistidas(hoy, 6, ultima_hace=0)
        prox = self._paciente("Próximo"); self._asistidas(prox, 5, ultima_hace=2); self._agendada(prox, 2, 6)
        siguio = self._paciente("Siguió"); self._asistidas(siguio, 9, ultima_hace=1)
        antiguo = self._paciente("Antiguo"); self._asistidas(antiguo, 6, ultima_hace=200)
        orden = [f["paciente"] for f in self._cola()]
        self.assertEqual(orden, ["Vencido 30", "Vencido 5", "Hoy", "Próximo", "Siguió", "Antiguo"])

    def test_resumen_cuenta_por_estado_y_lo_accionable(self):
        a = self._paciente("A"); self._asistidas(a, 6, ultima_hace=30)
        b = self._paciente("B"); self._asistidas(b, 6, ultima_hace=0)
        c = self._paciente("C"); self._asistidas(c, 9, ultima_hace=1)
        d = self._paciente("D"); self._asistidas(d, 6, ultima_hace=200)
        r = C.resumen_de_cola(self._cola())
        self.assertEqual(r[C.EstadoCierre.VENCIDO], 1)
        self.assertEqual(r[C.EstadoCierre.HOY], 1)
        self.assertEqual(r[C.EstadoCierre.CONTINUO_SIN_DECISION], 1)
        self.assertEqual(r[C.EstadoCierre.BACKLOG], 1)
        self.assertEqual(r["accionables"], 2)


class PrioritariosDeLaTarjetaTests(_Base):
    """La mini-tabla de "Hoy" muestra como mucho cinco casos, elegidos para que
    ninguna categoría accionable quede invisible detrás de los vencidos. La cola
    completa NO cambia: sigue en orden de urgencia pura."""

    def _vencido(self, nombre, hace):
        p = self._paciente(nombre); self._asistidas(p, 6, ultima_hace=hace); return p

    def _hoy(self, nombre):
        p = self._paciente(nombre); self._asistidas(p, 6, ultima_hace=0); return p

    def _s3(self, nombre, hace=4):
        p = self._paciente(nombre); self._asistidas(p, 3, ultima_hace=hace); return p

    def _precierre(self, nombre, hace=3):
        p = self._paciente(nombre); self._asistidas(p, 5, ultima_hace=hace); return p

    def _proximo(self, nombre):
        p = self._paciente(nombre); self._asistidas(p, 5, ultima_hace=2); self._agendada(p, 2, 6); return p

    def _tarjeta(self, **kw):
        return C.prioritarios_para_tarjeta(self._cola(), **kw)

    def test_con_las_cuatro_categorias_aparece_al_menos_una_de_cada(self):
        for i in range(6):                       # seis vencidos: antes llenaban los cinco lugares
            self._vencido(f"Vencido {i}", hace=10 + i)
        self._hoy("Cierra hoy"); self._s3("En S3"); self._precierre("Pre-cierre")
        estados = {f["estado"] for f in self._tarjeta()}
        self.assertEqual(estados, {C.EstadoCierre.VENCIDO, C.EstadoCierre.HOY,
                                   C.EstadoCierre.RIESGO_S3, C.EstadoCierre.SIN_AGENDAR})

    def test_el_representante_de_cada_categoria_es_su_caso_mas_urgente(self):
        self._vencido("Vencido 5", hace=5); self._vencido("Vencido 40", hace=40)
        self._s3("S3 reciente", hace=2); self._s3("S3 viejo", hace=20)
        nombres = [f["paciente"] for f in self._tarjeta(maximo=2)]
        # Con solo dos lugares entran el vencido más viejo y el S3 más viejo.
        self.assertEqual(nombres, ["Vencido 40", "S3 viejo"])

    def test_si_falta_una_categoria_el_lugar_se_rellena_con_el_siguiente_mas_urgente(self):
        for i in range(6):
            self._vencido(f"Vencido {i}", hace=10 + i)
        self._hoy("Cierra hoy")                  # sin S3 ni pre-cierre
        filas = self._tarjeta()
        self.assertEqual(len(filas), 5)
        self.assertEqual([f["paciente"] for f in filas],
                         ["Vencido 5", "Vencido 4", "Vencido 3", "Vencido 2", "Cierra hoy"])
        self.assertNotIn(C.EstadoCierre.RIESGO_S3, {f["estado"] for f in filas})

    def test_nunca_mas_de_cinco(self):
        for i in range(4):
            self._vencido(f"Vencido {i}", hace=10 + i); self._s3(f"S3 {i}", hace=i + 1)
            self._precierre(f"Pre {i}", hace=i + 1)
        self._hoy("Cierra hoy A"); self._hoy("Cierra hoy B")
        self.assertEqual(len(self._tarjeta()), 5)

    def test_sin_duplicados(self):
        for i in range(3):
            self._vencido(f"Vencido {i}", hace=10 + i)
        self._hoy("Cierra hoy"); self._s3("En S3"); self._precierre("Pre-cierre")
        ids = [f["id"] for f in self._tarjeta()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_seguimiento_y_calidad_no_entran_mientras_haya_accionables(self):
        self._vencido("Vencido", hace=10)
        self._proximo("Próximo")                                    # seguimiento
        siguio = self._paciente("Siguió"); self._asistidas(siguio, 9, ultima_hace=1)   # calidad
        antiguo = self._paciente("Antiguo"); self._asistidas(antiguo, 6, ultima_hace=200)  # backlog
        filas = self._tarjeta()
        self.assertEqual([f["paciente"] for f in filas], ["Vencido"])
        # Ni siquiera con lugares libres: sobran cuatro y no se rellenan con seguimiento.
        self.assertTrue(all(f["estado"] in C.EstadoCierre.ACCIONABLES for f in filas))

    def test_sin_accionables_no_hay_prioritarios(self):
        self._proximo("Solo próximo")
        self.assertEqual(self._tarjeta(), [])

    def test_conserva_el_orden_real_de_la_cola(self):
        """La selección puede saltarse vencidos para dar lugar a otras categorías,
        pero lo que muestra va en el orden de urgencia de la cola, no en el
        orden en que se eligió."""
        for i in range(6):
            self._vencido(f"Vencido {i}", hace=10 + i)
        self._hoy("Cierra hoy"); self._s3("En S3"); self._precierre("Pre-cierre")
        cola = self._cola()
        posicion = {f["id"]: i for i, f in enumerate(cola)}
        filas = C.prioritarios_para_tarjeta(cola)
        self.assertEqual([posicion[f["id"]] for f in filas], sorted(posicion[f["id"]] for f in filas))
        # Y la cola completa sigue en orden puro: todos los vencidos antes que "hoy".
        estados_cola = [f["estado"] for f in cola]
        self.assertEqual(estados_cola[:6], [C.EstadoCierre.VENCIDO] * 6)

    def test_el_endpoint_de_hoy_usa_la_seleccion_hibrida(self):
        admin = Usuario.objects.create_user(email="adm-tarjeta@test.pe", password="x",
                                            clinica=self.clinica, rol=Usuario.Rol.ADMIN)
        for i in range(6):
            self._vencido(f"Vencido {i}", hace=10 + i)
        self._s3("En S3")
        self.client.force_login(admin)
        c = self.client.get("/api/hoy/").json()["continuidad"]
        self.assertEqual(len(c["prioritarios"]), 5)
        self.assertIn("En S3", [f["paciente"] for f in c["prioritarios"]])
        self.assertEqual(c["riesgo_s3"], 1)          # el contador llega a la tarjeta
        self.assertEqual(c["accionables"], 7)


class AlcancePorRolTests(_Base):
    """Las mismas reglas que ya tenía la tarjeta de Hoy, ahora en un solo sitio."""

    def setUp(self):
        super().setUp()
        self.otra = Profesional.objects.create(clinica=self.clinica, nombre="Otra Psicóloga", sede="lima")
        self.mio = self._paciente("Mío de Piura", sede="piura", ficha=self.ficha)
        self.ajeno = self._paciente("De Lima", sede="lima", ficha=self.otra)

    def _ver(self, usuario):
        return set(C.pacientes_del_rol(Paciente.objects.filter(clinica=self.clinica), usuario)
                   .values_list("nombre", flat=True))

    def test_psicologo_solo_los_suyos(self):
        self.assertEqual(self._ver(self.psico), {"Mío de Piura"})

    def test_coordinadora_solo_su_sede(self):
        coord = Usuario.objects.create_user(email="coord-cola@test.pe", password="x", clinica=self.clinica,
                                            rol=Usuario.Rol.ASISTENTE, sede=Usuario.Sede.LIMA)
        self.assertEqual(self._ver(coord), {"De Lima"})

    def test_admin_y_analista_ambas_sedes(self):
        for rol, mail in ((Usuario.Rol.ADMIN, "adm-cola@test.pe"), (Usuario.Rol.ANALISTA, "ana-cola@test.pe")):
            u = Usuario.objects.create_user(email=mail, password="x", clinica=self.clinica, rol=rol)
            self.assertEqual(self._ver(u), {"Mío de Piura", "De Lima"}, rol)

    def test_comercial_nada(self):
        u = Usuario.objects.create_user(email="com-cola@test.pe", password="x", clinica=self.clinica,
                                        rol=Usuario.Rol.COMERCIAL)
        self.assertEqual(self._ver(u), set())


class EndpointsTests(_Base):
    """/api/hoy/ trae el resumen y cinco casos; /api/continuidad/pendientes/ trae todo con filtros."""

    def setUp(self):
        super().setUp()
        self.admin = Usuario.objects.create_user(email="adm-ep@test.pe", password="x",
                                                 clinica=self.clinica, rol=Usuario.Rol.ADMIN)
        self.otra = Profesional.objects.create(clinica=self.clinica, nombre="Psicóloga Lima", sede="lima")
        for i in range(7):   # siete vencidos en Piura, de 7 a 49 días
            p = self._paciente(f"Vencido {i}")
            self._asistidas(p, 6, ultima_hace=7 * (i + 1))
        p = self._paciente("Lima doce", sede="lima", ficha=self.otra)
        self._asistidas(p, 12, ultima_hace=3)
        p = self._paciente("Antiguo Lima", sede="lima", ficha=self.otra)
        self._asistidas(p, 6, ultima_hace=300)

    def test_hoy_trae_el_resumen_y_como_mucho_cinco_prioritarios(self):
        self.client.force_login(self.admin)
        c = self.client.get("/api/hoy/").json()["continuidad"]
        self.assertEqual((c["vencidos"], c["backlog"], c["accionables"]), (8, 1, 8))
        self.assertEqual(len(c["prioritarios"]), 5)
        self.assertEqual(c["prioritarios"][0]["paciente"], "Vencido 6")   # 49 días: el más viejo primero
        self.assertNotIn("por_continuidad", self.client.get("/api/hoy/").json())

    def test_pendientes_por_defecto_solo_lo_accionable(self):
        self.client.force_login(self.admin)
        d = self.client.get("/api/continuidad/pendientes/").json()
        self.assertEqual(d["total"], 8)
        self.assertTrue(all(f["estado"] == "vencido" for f in d["filas"]))
        self.assertEqual(d["conteo"]["backlog"], 1)

    def test_filtros_estado_sede_y_bloque(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get("/api/continuidad/pendientes/?estado=backlog").json()["total"], 1)
        self.assertEqual(self.client.get("/api/continuidad/pendientes/?sede=lima").json()["total"], 1)
        self.assertEqual(self.client.get("/api/continuidad/pendientes/?bloque=12").json()["total"], 1)
        self.assertEqual(self.client.get("/api/continuidad/pendientes/?medico=" + str(self.otra.id)).json()["total"], 1)
        self.assertEqual(self.client.get("/api/continuidad/pendientes/?estado=todos").json()["total"], 9)

    def test_la_coordinadora_no_puede_saltarse_su_sede_con_el_filtro(self):
        coord = Usuario.objects.create_user(email="coord-ep@test.pe", password="x", clinica=self.clinica,
                                            rol=Usuario.Rol.ASISTENTE, sede=Usuario.Sede.PIURA)
        self.client.force_login(coord)
        self.assertEqual(self.client.get("/api/continuidad/pendientes/").json()["total"], 7)
        self.assertEqual(self.client.get("/api/continuidad/pendientes/?sede=lima").json()["total"], 0)

    def test_el_psicologo_ve_solo_sus_pacientes(self):
        self.client.force_login(self.psico)
        self.assertEqual(self.client.get("/api/continuidad/pendientes/").json()["total"], 7)

    def test_el_comercial_no_ve_nada(self):
        u = Usuario.objects.create_user(email="com-ep@test.pe", password="x", clinica=self.clinica,
                                        rol=Usuario.Rol.COMERCIAL)
        self.client.force_login(u)
        self.assertEqual(self.client.get("/api/continuidad/pendientes/?estado=todos").json()["total"], 0)


class TrazabilidadDeLaDecisionTests(_Base):
    """Cuándo y quién registró la decisión: sin esto no se puede medir cuánto
    tarda coordinación en cerrar un bloque, ni comparar antes y después."""

    def setUp(self):
        super().setUp()
        self.coord = Usuario.objects.create_user(email="coord-tz@test.pe", password="x", clinica=self.clinica,
                                                 rol=Usuario.Rol.ASISTENTE, sede=Usuario.Sede.PIURA)
        p = self._paciente("Con cita")
        self.cita = Cita.objects.create(clinica=self.clinica, paciente=p, medico=self.psico,
                                        estado=Cita.Estado.ASISTIO, inicio=_dt(-1))

    def _patch(self, usuario, datos):
        self.client.force_login(usuario)
        return self.client.patch(f"/api/citas/{self.cita.id}/", datos, content_type="application/json")

    def test_registrar_la_decision_deja_fecha_y_autor(self):
        antes = timezone.now()
        self.assertEqual(self._patch(self.coord, {"decision": "DP-08"}).status_code, 200)
        self.cita.refresh_from_db()
        self.assertEqual(self.cita.decision, "DP-08")
        self.assertEqual(self.cita.decision_registrada_por, self.coord)
        self.assertGreaterEqual(self.cita.decision_registrada_en, antes)

    def test_cambiar_otra_cosa_no_toca_la_trazabilidad(self):
        self._patch(self.coord, {"decision": "DP-08"})
        self.cita.refresh_from_db()
        cuando = self.cita.decision_registrada_en
        self._patch(self.coord, {"notas": "otra nota"})
        self.cita.refresh_from_db()
        self.assertEqual(self.cita.decision_registrada_en, cuando)

    def test_borrar_la_decision_limpia_la_trazabilidad(self):
        self._patch(self.coord, {"decision": "DP-08"})
        self._patch(self.coord, {"decision": ""})
        self.cita.refresh_from_db()
        self.assertEqual(self.cita.decision, "")
        self.assertIsNone(self.cita.decision_registrada_en)
        self.assertIsNone(self.cita.decision_registrada_por)

    def test_el_psicologo_no_registra_decisiones(self):
        self._patch(self.psico, {"decision": "DP-08"})
        self.cita.refresh_from_db()
        self.assertEqual(self.cita.decision, "")
        self.assertIsNone(self.cita.decision_registrada_por)

    def test_la_decision_registrada_saca_al_paciente_de_la_cola(self):
        p = self.cita.paciente
        for i in range(5):
            Cita.objects.create(clinica=self.clinica, paciente=p, medico=self.psico, n_sesion=i + 1,
                                estado=Cita.Estado.ASISTIO, inicio=_dt(-40 + 7 * i))
        self.cita.n_sesion = 6
        self.cita.save(update_fields=["n_sesion"])
        self.assertIsNotNone(self._fila(p))
        self._patch(self.coord, {"decision": "DP-10"})
        self.assertIsNone(self._fila(p))
