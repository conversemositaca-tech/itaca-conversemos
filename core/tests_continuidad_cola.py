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


class ReinicioDeProcesoTests(_Base):
    """`n_sesion` se reinicia cada vez que el paciente empieza un proceso
    nuevo (Paciente.proceso: primero, segundo, tercero…). Verificado en
    producción el 9 sep: 81 de 391 pacientes de la cola tenían este patrón, y
    tomar el MÁXIMO histórico los mostraba en el cierre de un proceso ya
    terminado (a veces meses atrás) en vez de en su sesión real de hoy."""

    def _cita(self, p, n_sesion, hace_dias, estado=Cita.Estado.ASISTIO):
        return Cita.objects.create(
            clinica=self.clinica, paciente=p, medico=self.psico, n_sesion=n_sesion,
            estado=estado, inicio=_dt(-hace_dias))

    def test_toma_la_sesion_del_proceso_actual_no_el_maximo_historico(self):
        """Terminó su primer proceso (1..6) y va en la sesión 2 del segundo."""
        p = self._paciente("Segundo proceso")
        for i, hace in zip(range(1, 7), [90, 83, 76, 69, 62, 55]):
            self._cita(p, i, hace)
        self._cita(p, 1, hace_dias=10)
        self._cita(p, 2, hace_dias=3)
        self.assertEqual(C.sesion_real_por_pacientes([p.id])[p.id], 2)  # no 6

    def test_lo_mismo_calculado_desde_la_lista_de_citas_de_un_solo_paciente(self):
        """La misma regla que usa la ficha (PacienteSerializer), sin pasar
        por el agregado masivo — para que no se desalineen entre sí."""
        p = self._paciente("Segundo proceso (ficha)")
        for i, hace in zip(range(1, 7), [90, 83, 76, 69, 62, 55]):
            self._cita(p, i, hace)
        self._cita(p, 1, hace_dias=10)
        self._cita(p, 2, hace_dias=3)
        citas = list(Cita.objects.filter(paciente=p).order_by("?"))  # orden desordenado a propósito
        self.assertEqual(C.sesion_real(citas), 2)

    def test_la_cola_ya_no_los_mete_a_backlog_por_error(self):
        """Antes del fix: sesion_real=6/6 (el cierre del proceso VIEJO, de
        hace 90 días) -> backlog. Con el fix: sesion_real=5 (va en la 5ta del
        proceso actual, a una de cerrar) -> sin_agendar, no backlog."""
        p = self._paciente("No debe ser backlog")
        for i, hace in zip(range(1, 7), [95, 88, 81, 74, 67, 60]):
            self._cita(p, i, hace)
        for i, hace in zip(range(1, 6), [30, 23, 16, 9, 3]):
            self._cita(p, i, hace)
        f = self._fila(p)
        self.assertNotEqual(f["estado"], C.EstadoCierre.BACKLOG)
        self.assertEqual(f["n_sesion"], 5)
        self.assertEqual(f["estado"], C.EstadoCierre.SIN_AGENDAR)

    def test_una_cita_sin_numero_al_final_no_rompe_el_calculo(self):
        """La última cita todavía no tiene n_sesion puesto (recién ocurrió,
        falta que alguien lo llene) — se usa la anterior que sí lo trae."""
        p = self._paciente("Última sin número")
        self._cita(p, 1, hace_dias=20)
        self._cita(p, 2, hace_dias=13)
        Cita.objects.create(clinica=self.clinica, paciente=p, medico=self.psico,
                            estado=Cita.Estado.ASISTIO, inicio=_dt(-6))  # sin n_sesion
        self.assertEqual(C.sesion_real_por_pacientes([p.id])[p.id], 2)


class MigradoSinActividadTests(_Base):
    """La etiqueta "Migrado de AgendaPro — nunca se le agendó nada acá":
    ningún estado (vencido, sin agendar, lo que sea) se creó nunca en el
    sistema nuevo. Pedido por Mirai el 9 sep viendo un caso así en producción."""

    MARCADOR = C.MARCADOR_IMPORTADO_AGENDAPRO

    def _cita_importada(self, p, n_sesion, hace_dias, estado=Cita.Estado.ASISTIO):
        return Cita.objects.create(
            clinica=self.clinica, paciente=p, medico=self.psico, n_sesion=n_sesion,
            estado=estado, inicio=_dt(-hace_dias), notas=f"{self.MARCADOR} comentario original",
        )

    def test_si_todas_sus_citas_son_del_volcado_queda_marcado(self):
        p = self._paciente("Solo AgendaPro")
        for i in range(6):
            self._cita_importada(p, i + 1, hace_dias=200 - 7 * i)
        self.assertTrue(self._fila(p)["migrado_sin_actividad"])

    def test_una_sola_cita_nativa_ya_lo_saca_de_la_etiqueta(self):
        """Aunque el cierre real siga siendo viejo, si en algún momento el
        sistema nuevo SÍ le creó algo, ya no es "nunca se le agendó nada"."""
        p = self._paciente("Con algo nativo")
        for i in range(6):
            self._cita_importada(p, i + 1, hace_dias=200 - 7 * i)
        self.assertTrue(self._fila(p)["migrado_sin_actividad"])
        # Una cita nativa CANCELADA (nunca asistida) igual cuenta como "se intentó".
        Cita.objects.create(clinica=self.clinica, paciente=p, medico=self.psico,
                            estado=Cita.Estado.CANCELADA, inicio=_dt(-30))
        self.assertFalse(self._fila(p)["migrado_sin_actividad"])

    def test_un_paciente_nativo_normal_nunca_lleva_la_etiqueta(self):
        p = self._paciente("Nativo de Ítaca")
        self._asistidas(p, 6, ultima_hace=200)  # sin marcador: notas="" por defecto
        self.assertFalse(self._fila(p)["migrado_sin_actividad"])

    def test_aplica_tambien_a_vencidos_y_no_solo_a_backlog(self):
        """Verificado en producción: 29% de los "vencidos" también vienen
        enteros de AgendaPro, no es un atributo exclusivo del backlog."""
        p = self._paciente("Vencido pero migrado")
        for i in range(6):
            self._cita_importada(p, i + 1, hace_dias=16 - i)
        f = self._fila(p)
        self.assertEqual(f["estado"], C.EstadoCierre.VENCIDO)
        self.assertTrue(f["migrado_sin_actividad"])


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
        Antes no aparecía en ninguna parte: la meta se corría a la 12."""
        p = self._paciente("Siguió viniendo")
        self._asistidas(p, 9, ultima_hace=2)
        f = self._fila(p)
        self.assertEqual((f["estado"], f["meta"]), (C.EstadoCierre.CONTINUO_SIN_DECISION, 12))

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
