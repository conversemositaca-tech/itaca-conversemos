"""Pruebas de la segmentación por procesos (reinicio de proceso / sesión real).

El equipo numera las sesiones POR PROCESO: cuando alguien termina su primer
proceso en la sesión 6 y vuelve, la siguiente es la sesión 1 del segundo.
Hasta el 10 sep 2026 `resolver_sesion_real` tomaba el máximo de toda la vida
del paciente y mezclaba los dos procesos (medido por el PR #71 en producción:
104 pacientes en la cola solo por eso, 17 urgentes escondidos).

Regla implementada (alternativa A, aprobada el 10 sep): una bajada del número
es solo un CANDIDATO a reinicio; se acepta con respaldo estructurado (la nueva
sesión es la 1; DP de cierre en el tramo anterior; consulta o DP de consulta
entre medias; cambio de etapa; lead convertido). El tiempo nunca decide solo:
solo refuerza una bajada a la sesión 1 o 2. Una bajada sin respaldo (S1…S6,
S5) es continuidad + marca de numeración inconsistente.

    python manage.py test core.tests_proceso
"""
from datetime import date, datetime, timedelta

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from core import continuidad as C
from core.tests_continuidad_cola import _Base, _dt
from leads.models import Lead
from pacientes.models import Cita, GestionContinuidad, HistorialContinuidad, Paciente, SeguimientoSesion
from usuarios.models import Profesional, Usuario


def _c(n, hace, decision="", estado="asistio", _id=[0]):
    """Una cita como dict (lo que `.values()` le da a la cola), `hace` días atrás."""
    _id[0] += 1
    inicio = timezone.make_aware(datetime(2026, 9, 10, 10, 0)) - timedelta(days=hace)
    return {"id": _id[0], "n_sesion": n, "inicio": inicio, "estado": estado, "decision": decision}


class SegmentacionPuraTests(SimpleTestCase):
    """`segmentar_procesos` / `proceso_actual` sobre dicts, sin base de datos."""

    def _tramos(self, citas, senales=()):
        return [[c["n_sesion"] for c in t["citas"]] for t in C.segmentar_procesos(citas, senales)]

    def test_sin_reinicio_es_un_solo_tramo(self):
        citas = [_c(i, 70 - 7 * i) for i in range(1, 7)]
        self.assertEqual(self._tramos(citas), [[1, 2, 3, 4, 5, 6]])
        self.assertEqual(C.proceso_actual(citas)["n"], 6)

    def test_bajada_a_1_reinicia_sin_mas_respaldo(self):
        citas = [_c(i, 90 - 7 * i) for i in range(1, 7)] + [_c(1, 10), _c(2, 3)]
        self.assertEqual(self._tramos(citas), [[1, 2, 3, 4, 5, 6], [1, 2]])
        pa = C.proceso_actual(citas)
        self.assertEqual((pa["n"], pa["numero"], pa["motivo"]), (2, 2, "n=1"))

    def test_typo_6_a_5_sin_respaldo_no_reinicia_y_se_marca(self):
        """S1…S6 y después una "S5" mal tipeada, una semana después, sin DP ni consulta."""
        citas = [_c(i, 70 - 7 * i) for i in range(1, 7)] + [_c(5, 21)]
        self.assertEqual(self._tramos(citas), [[1, 2, 3, 4, 5, 6, 5]])
        pa = C.proceso_actual(citas)
        self.assertEqual((pa["n"], pa["numero"]), (6, 1))          # no baja a 5, no abre proceso
        self.assertTrue(pa["numeracion_inconsistente"])

    def test_bajada_a_3_sin_respaldo_tampoco_reinicia(self):
        citas = [_c(i, 70 - 7 * i) for i in range(1, 7)] + [_c(3, 21)]
        self.assertEqual(len(self._tramos(citas)), 1)
        self.assertTrue(C.proceso_actual(citas)["numeracion_inconsistente"])

    def test_dp_de_cierre_respalda_una_bajada_a_cualquier_numero(self):
        """Alta en la S6; después alguien empieza numerando en 3 (raro, pero el DP manda)."""
        citas = [_c(i, 70 - 7 * i) for i in range(1, 6)] + [_c(6, 28, decision="DP-10"), _c(3, 7)]
        self.assertEqual(self._tramos(citas), [[1, 2, 3, 4, 5, 6], [3]])
        self.assertIn("dp_cierre", C.proceso_actual(citas)["motivo"])

    def test_dp_de_cierre_abre_tramo_aunque_no_haya_bajada_numerica(self):
        """Alta en la S6 y la siguiente asistida viene sin número: es otro proceso."""
        citas = [_c(i, 70 - 7 * i) for i in range(1, 6)] + [_c(6, 28, decision="DP-10"), _c(None, 7)]
        self.assertEqual(self._tramos(citas), [[1, 2, 3, 4, 5, 6], [None]])
        self.assertEqual(C.proceso_actual(citas)["n"], 1)         # una sesión del proceso nuevo

    def test_dp_de_cierre_seguido_de_s7_es_dp_mal_puesto_no_reinicio(self):
        citas = [_c(i, 70 - 7 * i) for i in range(1, 6)] + [_c(6, 28, decision="DP-10"), _c(7, 21)]
        self.assertEqual(self._tramos(citas), [[1, 2, 3, 4, 5, 6, 7]])
        self.assertTrue(C.proceso_actual(citas)["numeracion_inconsistente"])

    def test_consulta_entre_tramos_respalda_la_bajada(self):
        """S1…S6, una consulta (asistida sin número) y S3: hubo consulta de por medio."""
        citas = [_c(i, 90 - 7 * i) for i in range(1, 7)] + [_c(None, 20), _c(3, 5)]
        self.assertEqual(self._tramos(citas), [[1, 2, 3, 4, 5, 6], [None, 3]])
        self.assertIn("consulta", C.proceso_actual(citas)["motivo"])

    def test_dp_de_consulta_respalda_la_bajada(self):
        citas = [_c(i, 90 - 7 * i) for i in range(1, 7)] + [_c(2, 5, decision="DP-01")]
        self.assertEqual(len(self._tramos(citas)), 2)
        self.assertIn("dp_inicio", C.proceso_actual(citas)["motivo"])

    def test_senal_externa_lead_convertido_respalda(self):
        citas = [_c(i, 90 - 7 * i) for i in range(1, 7)] + [_c(2, 5)]
        sin = C.proceso_actual(citas)
        self.assertEqual(sin["numero"], 1)                          # 6 → 2 sin nada: se ignora
        con = C.proceso_actual(citas, senales=[{"fecha": date(2026, 9, 1), "tipo": "lead"}])
        self.assertEqual((con["numero"], con["motivo"]), (2, "lead"))

    def test_el_tiempo_solo_refuerza_una_bajada_a_1_o_2(self):
        """6 → 2 con 90 días de hueco reinicia (n≤2 + gap); 6 → 3 con 90 días NO."""
        base = [_c(i, 200 - 7 * i) for i in range(1, 7)]
        self.assertEqual(C.proceso_actual(base + [_c(2, 10)])["numero"], 2)
        self.assertEqual(C.proceso_actual(base + [_c(2, 10)])["motivo"], "gap")
        self.assertEqual(C.proceso_actual(base + [_c(3, 10)])["numero"], 1)

    def test_pausa_larga_sin_bajada_es_el_mismo_proceso(self):
        """S1…S4, cinco meses sin venir, S5 y S6: la numeración siguió."""
        citas = [_c(i, 200 - 7 * i) for i in range(1, 5)] + [_c(5, 10), _c(6, 3)]
        self.assertEqual(self._tramos(citas), [[1, 2, 3, 4, 5, 6]])
        self.assertEqual(C.proceso_actual(citas)["n"], 6)

    def test_sin_numeros_cuenta_solo_el_tramo(self):
        citas = [_c(None, 30), _c(None, 20), _c(None, 10)]
        self.assertEqual(C.proceso_actual(citas)["n"], 3)

    def test_ultima_sin_numero_no_rompe(self):
        citas = [_c(1, 20), _c(2, 13), _c(None, 6)]
        self.assertEqual(C.proceso_actual(citas)["n"], 2)

    def test_anteriores_sin_cierre_se_cuentan(self):
        p1 = [_c(i, 300 - 7 * i) for i in range(1, 7)]                  # sin DP al final
        p2 = [_c(i, 200 - 7 * i) for i in range(1, 7)]; p2[-1]["decision"] = "DP-10"
        p3 = [_c(1, 10), _c(2, 3)]
        pa = C.proceso_actual(p1 + p2 + p3)
        self.assertEqual((pa["numero"], pa["total"], pa["anteriores_sin_cierre"]), (3, 3, 1))
        self.assertEqual([a["cierre_registrado"] for a in pa["anteriores"]], [False, True])

    def test_solo_cuenta_asistidas_y_ordena_aunque_lleguen_desordenadas(self):
        citas = [_c(2, 3), _c(1, 10), _c(9, 1, estado="cancelada"), _c(6, 60), _c(5, 67)]
        self.assertEqual(self._tramos(citas), [[5, 6], [1, 2]])


class ProcesoEnLaColaTests(_Base):
    """Los 12 casos obligatorios (10 sep), sobre la cola real."""

    def _s(self, p, n, hace, decision="", **kw):
        return Cita.objects.create(clinica=self.clinica, paciente=p, medico=kw.pop("medico", self.psico),
                                   n_sesion=n, estado=Cita.Estado.ASISTIO, inicio=_dt(-hace),
                                   decision=decision, **kw)

    def _proceso(self, p, n, ultima_hace, decision_ultima="", desde=1, **kw):
        for i in range(desde, n + 1):
            self._s(p, i, ultima_hace + 7 * (n - i), decision_ultima if i == n else "", **kw)

    def _cola_ind(self, **kw):
        """La cola más los indicadores de calidad (procesos anteriores, numeración)."""
        ind = {}
        filas = C.cola_de_continuidad(Paciente.objects.filter(clinica=self.clinica), indicadores=ind, **kw)
        return filas, ind

    # 1
    def test_1_proceso_1_s6_y_proceso_2_s3_da_riesgo_s3(self):
        p = self._paciente("Rosa")
        self._proceso(p, 6, ultima_hace=120, decision_ultima="DP-10")
        self._proceso(p, 3, ultima_hace=4)
        self.assertEqual(C.sesion_real_por_pacientes([p.id])[p.id], 3)
        f = self._fila(p)
        self.assertEqual((f["estado"], f["n_sesion"], f["proceso"]["numero"]), (C.EstadoCierre.RIESGO_S3, 3, 2))
        self.assertEqual(f["evento"]["cita_referencia"], Cita.objects.get(paciente=p, n_sesion=3, inicio__gt=_dt(-30)).id)

    # 2
    def test_2_proceso_viejo_s6_sin_dp_y_proceso_nuevo_s1_s2_no_es_backlog(self):
        p = self._paciente("Julio")
        self._proceso(p, 6, ultima_hace=240)                 # sin DP: antes → backlog
        self._proceso(p, 2, ultima_hace=3)
        filas, ind = self._cola_ind()
        self.assertIsNone(next((f for f in filas if f["id"] == p.id), None))   # S2: nada pendiente HOY
        self.assertEqual(ind["procesos_anteriores_sin_cierre"], 1)
        fila_ant = ind["filas_procesos_anteriores"][0]
        self.assertEqual((fila_ant["estado"], fila_ant["grupo"], fila_ant["meta"], fila_ant["n_sesion"]),
                         (C.EstadoCierre.PROCESO_ANTERIOR, C.GRUPO_CALIDAD, 6, 2))
        self.assertNotIn(fila_ant["estado"], C.EstadoCierre.ACCIONABLES)

    # 3
    def test_3_typo_6_a_5_no_reinicia(self):
        p = self._paciente("Typo")
        self._proceso(p, 6, ultima_hace=10)
        self._s(p, 5, 3)                                      # debía ser S7
        filas, ind = self._cola_ind()
        f = next(f for f in filas if f["id"] == p.id)
        self.assertEqual((f["n_sesion"], f["proceso"]["numero"]), (6, 1))
        self.assertTrue(f["proceso"]["numeracion_inconsistente"])
        self.assertEqual(ind["numeracion_inconsistente"], 1)
        self.assertEqual(f["estado"], C.EstadoCierre.VENCIDO)   # cierre 6 hace 10 días, sin DP: como debe ser

    # 4
    def test_4_pausa_de_5_meses_s4_a_s5_es_el_mismo_proceso(self):
        p = self._paciente("Pausa")
        self._proceso(p, 4, ultima_hace=160)
        self._s(p, 5, 8); self._s(p, 6, 1)
        f = self._fila(p)
        self.assertEqual((f["n_sesion"], f["proceso"]["numero"], f["estado"]), (6, 1, C.EstadoCierre.VENCIDO))

    # 5
    def test_5_agendapro_con_varios_procesos_solo_el_tramo_vigente(self):
        p = self._paciente("Importada")
        m = C.MARCADOR_IMPORTADO_AGENDAPRO
        self._proceso(p, 6, ultima_hace=400, decision_ultima="DP-10", notas=m)
        self._proceso(p, 6, ultima_hace=250, notas=m)                       # 2.º proceso, sin cierre
        for i, hace in ((1, 30), (2, 23), (None, 16), (4, 9), (5, 2)):      # 3.º, con un hueco sin número
            self._s(p, i, hace, notas=m)
        f = self._fila(p)
        self.assertEqual((f["n_sesion"], f["proceso"]["numero"], f["proceso"]["total"]), (5, 3, 3))
        self.assertEqual(f["estado"], C.EstadoCierre.SIN_AGENDAR)
        self.assertTrue(f["migrado_sin_actividad"])
        self.assertEqual(f["proceso"]["anteriores_sin_cierre"], 1)

    # 6
    def test_6_cambio_de_psicologo_s4_a_s5_es_el_mismo_proceso(self):
        otro = Usuario.objects.create_user(email="otro-ps@test.pe", password="x", clinica=self.clinica,
                                           rol=Usuario.Rol.MEDICO)
        p = self._paciente("Cambia de psicólogo")
        self._proceso(p, 4, ultima_hace=24)
        self._s(p, 5, 10, medico=otro); self._s(p, 6, 3, medico=otro)
        f = self._fila(p)
        self.assertEqual((f["n_sesion"], f["proceso"]["numero"]), (6, 1))

    # 7
    def test_7_cierre_dp10_y_nuevo_s1_es_reinicio(self):
        p = self._paciente("Alta y vuelve")
        self._proceso(p, 6, ultima_hace=90, decision_ultima="DP-10")
        self._s(p, 1, 2)
        pa = C.proceso_actual(list(Cita.objects.filter(paciente=p)))
        self.assertEqual((pa["numero"], pa["n"]), (2, 1))
        self.assertIn("dp_cierre", pa["motivo"])

    # 8
    def test_8_consulta_entre_tramos_es_reinicio(self):
        p = self._paciente("Consulta entre medias")
        self._proceso(p, 6, ultima_hace=90)                                  # sin DP
        Cita.objects.create(clinica=self.clinica, paciente=p, medico=self.psico, estado=Cita.Estado.ASISTIO,
                            inicio=_dt(-20), especialidad="Consulta")        # consulta: sin número
        self._s(p, 3, 5)
        pa = C.proceso_actual(list(Cita.objects.filter(paciente=p)))
        self.assertEqual((pa["numero"], pa["n"]), (2, 3))
        self.assertIn("consulta", pa["motivo"])

    # 9
    def test_9_dos_s6_de_procesos_diferentes_cita_de_sesion_usa_la_vigente(self):
        p = self._paciente("Dos seis")
        self._proceso(p, 6, ultima_hace=200, decision_ultima="DP-10")
        self._proceso(p, 6, ultima_hace=4)
        vieja = Cita.objects.get(paciente=p, n_sesion=6, inicio__lt=_dt(-100))
        nueva = Cita.objects.get(paciente=p, n_sesion=6, inicio__gt=_dt(-100))
        f = self._fila(p)
        self.assertEqual((f["estado"], f["dias"]), (C.EstadoCierre.VENCIDO, 4))
        self.assertEqual(f["evento"]["cita_referencia"], nueva.id)
        self.assertNotIn(vieja.id, f["evento"]["anclas"])

    # 10
    def test_10_la_gestion_del_proceso_anterior_no_se_reabre_por_el_proceso_nuevo(self):
        from core import gestion_continuidad as gc
        coord = Usuario.objects.create_user(email="coord-pr@test.pe", password="x", clinica=self.clinica,
                                            rol=Usuario.Rol.ASISTENTE, sede=Usuario.Sede.PIURA)
        p = self._paciente("Gestionado antes")
        self._proceso(p, 6, ultima_hace=20)                                  # vencido, sin DP
        gc.guardar(p, coord, {"estado_revision": "en_seguimiento", "responsable": "coordinacion"})
        g = GestionContinuidad.objects.get(paciente=p)
        # Empieza un proceso nuevo (bajada a 1): la señal reconcilia.
        self._s(p, 1, 3)
        g.refresh_from_db()
        self.assertTrue(g.resuelta_por_sistema)
        self.assertEqual(HistorialContinuidad.objects.get(gestion=g, evento="auto_resuelto").despues, "proceso_nuevo")
        # El proceso nuevo llega a su propia S6 sin DP: es OTRO evento, no se reabre el viejo.
        for i in range(2, 7):
            self._s(p, i, 0)
        g.refresh_from_db()
        self.assertFalse(g.abierta)
        self.assertEqual(GestionContinuidad.objects.filter(paciente=p).count(), 1)   # nada reabierto ni duplicado
        f = self._fila(p)
        self.assertIsNone(gc.gestion_de(f))                                    # el nuevo S6 no tiene gestión
        gc.guardar(p, coord, {"estado_revision": "en_seguimiento"})
        self.assertEqual(GestionContinuidad.objects.filter(paciente=p).count(), 2)
        nueva = GestionContinuidad.objects.filter(paciente=p).order_by("-id").first()
        self.assertNotEqual(nueva.cita_referencia_id, g.cita_referencia_id)

    # 11
    def test_11_anteriores_sin_decision_no_contamina_el_proceso_actual(self):
        p = self._paciente("Doce en el segundo")
        self._proceso(p, 6, ultima_hace=300)                                 # proceso 1 sin DP
        self._proceso(p, 12, ultima_hace=3)                                  # proceso 2, cierres 6 y 12 sin DP
        f = self._fila(p)
        self.assertEqual((f["estado"], f["meta"], f["proceso"]["numero"]), (C.EstadoCierre.VENCIDO, 12, 2))
        self.assertEqual(f["anteriores_sin_decision"], [6])                  # solo el 6 DEL PROCESO 2
        s6_nueva = Cita.objects.get(paciente=p, n_sesion=6, inicio__gt=_dt(-100))
        self.assertEqual(f["anteriores_evento"][0]["cita_referencia"], s6_nueva.id)
        self.assertEqual(f["proceso"]["anteriores_sin_cierre"], 1)           # el proceso 1, aparte

    # 12
    def test_12_la_plantilla_n_sesion_muestra_la_sesion_del_proceso_vigente(self):
        p = self._paciente("Plantilla")
        self._proceso(p, 6, ultima_hace=120, decision_ultima="DP-10")
        self._proceso(p, 2, ultima_hace=3)
        from mensajes.models import render_plantilla
        self.assertEqual(render_plantilla("Vamos por tu sesión {n_sesion}", paciente=p), "Vamos por tu sesión 2")


class PortadosDelPR71Tests(_Base):
    """Los tests de `fix/reinicio-proceso-sesion-real` (PR #71), reimplementados
    sobre la segmentación con respaldo. Mismos escenarios, misma expectativa."""

    def _cita(self, p, n_sesion, hace_dias, estado=Cita.Estado.ASISTIO, notas=""):
        return Cita.objects.create(clinica=self.clinica, paciente=p, medico=self.psico, n_sesion=n_sesion,
                                   estado=estado, inicio=_dt(-hace_dias), notas=notas)

    def test_toma_la_sesion_del_proceso_actual_no_el_maximo_historico(self):
        p = self._paciente("Segundo proceso")
        for i, hace in zip(range(1, 7), [90, 83, 76, 69, 62, 55]):
            self._cita(p, i, hace)
        self._cita(p, 1, hace_dias=10)
        self._cita(p, 2, hace_dias=3)
        self.assertEqual(C.sesion_real_por_pacientes([p.id])[p.id], 2)

    def test_lo_mismo_calculado_desde_la_lista_de_citas_de_un_solo_paciente(self):
        p = self._paciente("Segundo proceso (ficha)")
        for i, hace in zip(range(1, 7), [90, 83, 76, 69, 62, 55]):
            self._cita(p, i, hace)
        self._cita(p, 1, hace_dias=10)
        self._cita(p, 2, hace_dias=3)
        citas = list(Cita.objects.filter(paciente=p).order_by("?"))
        self.assertEqual(C.sesion_real(citas), 2)

    def test_la_cola_ya_no_los_mete_a_backlog_por_error(self):
        p = self._paciente("No debe ser backlog")
        for i, hace in zip(range(1, 7), [95, 88, 81, 74, 67, 60]):
            self._cita(p, i, hace)
        for i, hace in zip(range(1, 6), [30, 23, 16, 9, 3]):
            self._cita(p, i, hace)
        f = self._fila(p)
        self.assertNotEqual(f["estado"], C.EstadoCierre.BACKLOG)
        self.assertEqual((f["n_sesion"], f["estado"]), (5, C.EstadoCierre.SIN_AGENDAR))

    def test_una_cita_sin_numero_al_final_no_rompe_el_calculo(self):
        p = self._paciente("Última sin número")
        self._cita(p, 1, hace_dias=20)
        self._cita(p, 2, hace_dias=13)
        self._cita(p, None, hace_dias=6)
        self.assertEqual(C.sesion_real_por_pacientes([p.id])[p.id], 2)

    MARCADOR = C.MARCADOR_IMPORTADO_AGENDAPRO

    def _importada(self, p, n, hace, estado=Cita.Estado.ASISTIO):
        return self._cita(p, n, hace, estado=estado, notas=f"{self.MARCADOR} comentario original")

    def test_si_todas_sus_citas_son_del_volcado_queda_marcado(self):
        p = self._paciente("Solo AgendaPro")
        for i in range(6):
            self._importada(p, i + 1, 200 - 7 * i)
        self.assertTrue(self._fila(p)["migrado_sin_actividad"])

    def test_una_sola_cita_nativa_ya_lo_saca_de_la_etiqueta(self):
        p = self._paciente("Con algo nativo")
        for i in range(6):
            self._importada(p, i + 1, 200 - 7 * i)
        self.assertTrue(self._fila(p)["migrado_sin_actividad"])
        self._cita(p, None, 30, estado=Cita.Estado.CANCELADA)      # nativa, aunque cancelada
        self.assertFalse(self._fila(p)["migrado_sin_actividad"])

    def test_un_paciente_nativo_normal_nunca_lleva_la_etiqueta(self):
        p = self._paciente("Nativo de Ítaca")
        self._asistidas(p, 6, ultima_hace=200)
        self.assertFalse(self._fila(p)["migrado_sin_actividad"])

    def test_aplica_tambien_a_vencidos_y_no_solo_a_backlog(self):
        p = self._paciente("Vencido pero migrado")
        for i in range(6):
            self._importada(p, i + 1, 16 - i)
        f = self._fila(p)
        self.assertEqual(f["estado"], C.EstadoCierre.VENCIDO)
        self.assertTrue(f["migrado_sin_actividad"])


class SenalesExternasTests(_Base):
    """Lead convertido y cambio de etapa en SeguimientoSesion respaldan un
    reinicio a la sesión 2 (que sola no bastaría)."""

    def _s(self, p, n, hace):
        return Cita.objects.create(clinica=self.clinica, paciente=p, medico=self.psico, n_sesion=n,
                                   estado=Cita.Estado.ASISTIO, inicio=_dt(-hace))

    def test_lead_convertido_entre_tramos(self):
        p = self._paciente("Reingreso por lead")
        for i in range(1, 7):
            self._s(p, i, 100 - 7 * i)
        self._s(p, 2, 5)                                                    # 6 → 2, sin más
        self.assertEqual(C.sesion_real_por_pacientes([p.id])[p.id], 6)      # se ignora (typo)
        Lead.objects.create(clinica=self.clinica, nombre="x", telefono="999", paciente=p,
                            fecha_consulta=self.hoy - timedelta(days=20))
        self.assertEqual(C.sesion_real_por_pacientes([p.id])[p.id], 2)      # ahora sí: hubo consulta

    def test_cambio_de_etapa_en_seguimiento(self):
        p = self._paciente("Segundo según seguimiento")
        for i in range(1, 7):
            self._s(p, i, 100 - 7 * i)
        self._s(p, 2, 5)
        h = self.hoy
        SeguimientoSesion.objects.create(clinica=self.clinica, paciente=p, anio=h.year, mes=h.month, semana=1,
                                         n_sesion=6, proceso="primero")
        # Segunda semana del mes, etapa "segundo": el cambio cae entre las dos citas si hoy es ≥ día 8.
        SeguimientoSesion.objects.create(clinica=self.clinica, paciente=p, anio=h.year, mes=h.month, semana=2,
                                         n_sesion=1, proceso="segundo")
        senales = C.senales_por_paciente([p.id]).get(p.id, [])
        self.assertTrue(any(s["tipo"] == "proceso" for s in senales))


class FichaYApiTests(_Base):
    def test_el_serializer_expone_proceso_actual_y_sesion_real_del_proceso(self):
        admin = Usuario.objects.create_user(email="adm-pr@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ADMIN)
        p = self._paciente("Ficha")
        for i, hace in zip(range(1, 7), [90, 83, 76, 69, 62, 55]):
            Cita.objects.create(clinica=self.clinica, paciente=p, medico=self.psico, n_sesion=i,
                                estado=Cita.Estado.ASISTIO, inicio=_dt(-hace), decision="DP-10" if i == 6 else "")
        Cita.objects.create(clinica=self.clinica, paciente=p, medico=self.psico, n_sesion=1,
                            estado=Cita.Estado.ASISTIO, inicio=_dt(-3))
        self.client.force_login(admin)
        d = self.client.get(f"/api/pacientes/{p.id}/").json()
        self.assertEqual(d["sesion_real"], 1)
        self.assertEqual((d["proceso_actual"]["numero"], d["proceso_actual"]["total"]), (2, 2))
        self.assertIn("dp_cierre", d["proceso_actual"]["motivo"])

    def test_pendientes_expone_el_indicador_de_procesos_anteriores(self):
        admin = Usuario.objects.create_user(email="adm-pr2@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ADMIN)
        p = self._paciente("Con proceso viejo")
        for i in range(1, 7):
            Cita.objects.create(clinica=self.clinica, paciente=p, medico=self.psico, n_sesion=i,
                                estado=Cita.Estado.ASISTIO, inicio=_dt(-300 + 7 * i))
        Cita.objects.create(clinica=self.clinica, paciente=p, medico=self.psico, n_sesion=1,
                            estado=Cita.Estado.ASISTIO, inicio=_dt(-2))
        self.client.force_login(admin)
        d = self.client.get("/api/continuidad/pendientes/?estado=proceso_anterior").json()
        self.assertEqual(d["conteo"]["proceso_anterior"], 1)
        self.assertEqual([f["paciente"] for f in d["filas"]], ["Con proceso viejo"])
        self.assertEqual(d["filas"][0]["fila_id"], f"proceso_anterior-{p.id}")
        self.assertEqual(self.client.get("/api/continuidad/pendientes/").json()["total"], 0)   # no es acción
        hoy = self.client.get("/api/hoy/").json()["continuidad"]
        self.assertEqual(hoy["proceso_anterior"], 1)
