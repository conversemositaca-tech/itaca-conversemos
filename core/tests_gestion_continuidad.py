"""Pruebas de la gestión operativa del Centro de Continuidad (Parte 2).

Lo que se demuestra aquí:
  - guardar estado / resultado / responsable / observación deja auditoría e
    historial, y abrir el panel NO escribe nada;
  - "resuelto" no silencia una condición real: el caso sigue en la cola y
    lleva alerta;
  - cuando la fuente oficial resuelve (se agenda la siguiente cita, se
    registra el DP), la gestión se cierra sola con historial, y si la
    corrección se revierte, se reabre;
  - la identidad del evento: un proceso nuevo abre otra gestión; S6 y S12
    nunca comparten; no hay dos abiertas del mismo evento;
  - permisos: el analista SOLO puede escribir gestión; coordinación solo su
    sede; el psicólogo solo sus pacientes;
  - el modelo no duplica datos oficiales.

    python manage.py test core.tests_gestion_continuidad
"""
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from core import continuidad as C
from core import gestion_continuidad as gc
from core.tests_continuidad_cola import _Base, _dt
from pacientes.models import Cita, GestionContinuidad, HistorialContinuidad, Paciente
from usuarios.models import Profesional, Usuario

G = GestionContinuidad
Rev = G.Revision


class _ConGestion(_Base):
    def setUp(self):
        super().setUp()
        self.coord = Usuario.objects.create_user(
            email="coord-g@test.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.ASISTENTE, sede=Usuario.Sede.PIURA, nombre="Yazmín Coordinación")
        self.analista = Usuario.objects.create_user(
            email="ana-g@test.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.ANALISTA, nombre="Mirai Analista")
        self.admin = Usuario.objects.create_user(
            email="adm-g@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ADMIN)

    def _s6_vencido(self, nombre="Vencido", hace=10, **kw):
        p = self._paciente(nombre, **kw)
        self._asistidas(p, 6, ultima_hace=hace)
        return p

    def _s3(self, nombre="En S3", hace=4, **kw):
        p = self._paciente(nombre, **kw)
        self._asistidas(p, 3, ultima_hace=hace)
        return p

    def _patch(self, usuario, paciente, datos):
        self.client.force_login(usuario)
        return self.client.patch(f"/api/continuidad/caso/{paciente.id}/gestion/", datos,
                                 content_type="application/json")

    def _get(self, usuario, paciente):
        self.client.force_login(usuario)
        return self.client.get(f"/api/continuidad/caso/{paciente.id}/")

    def _gestion(self, paciente):
        return G.objects.filter(paciente=paciente).order_by("-id").first()

    def _eventos(self, paciente):
        return list(HistorialContinuidad.objects.filter(gestion__paciente=paciente)
                    .order_by("id").values_list("evento", flat=True))


class GuardarTests(_ConGestion):
    def test_abrir_el_panel_no_escribe(self):
        p = self._s6_vencido()
        r = self._get(self.coord, p)
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json()["gestion"])
        self.assertEqual(G.objects.count(), 0)

    def test_guardar_cada_campo(self):
        p = self._s6_vencido()
        r = self._patch(self.coord, p, {
            "estado_revision": "en_seguimiento", "resultado_operativo": "pendiente_real",
            "responsable": "coordinacion", "observacion_operativa": "Llamar el lunes.",
        })
        self.assertEqual(r.status_code, 200)
        g = self._gestion(p)
        self.assertEqual((g.estado_revision, g.resultado_operativo, g.responsable, g.observacion_operativa),
                         ("en_seguimiento", "pendiente_real", "coordinacion", "Llamar el lunes."))
        self.assertEqual((g.tipo, g.meta), (C.TIPO_CIERRE_BLOQUE, 6))
        self.assertEqual(g.cita_referencia, Cita.objects.get(paciente=p, n_sesion=6))
        d = r.json()
        self.assertEqual(d["gestion"]["estado_revision"], "en_seguimiento")
        self.assertTrue(d["en_cola"])

    def test_auditoria_usuario_y_fechas(self):
        p = self._s6_vencido()
        antes = timezone.now()
        self._patch(self.coord, p, {"estado_revision": "en_seguimiento"})
        g = self._gestion(p)
        self.assertEqual(g.revisado_por, self.coord)
        self.assertEqual(g.actualizado_por, self.coord)
        self.assertGreaterEqual(g.revisado_en, antes)
        self.assertEqual(g.revisado_en, g.actualizado_en)
        self.assertIsNone(g.resuelto_en)

    def test_primera_revision_solo_en_el_primer_guardado(self):
        p = self._s6_vencido()
        self._patch(self.coord, p, {"estado_revision": "en_seguimiento"})
        g = self._gestion(p)
        primera, quien = g.revisado_en, g.revisado_por
        self._patch(self.admin, p, {"responsable": "psicologo"})
        g.refresh_from_db()
        self.assertEqual((g.revisado_en, g.revisado_por), (primera, quien))   # no se mueve
        self.assertEqual(g.actualizado_por, self.admin)                     # esto sí
        self.assertGreater(g.actualizado_en, primera)
        self.assertEqual(G.objects.filter(paciente=p).count(), 1)

    def test_historial_registra_cada_cambio_sin_copiar_la_observacion(self):
        p = self._s6_vencido()
        self._patch(self.coord, p, {"estado_revision": "en_seguimiento", "responsable": "coordinacion",
                                    "observacion_operativa": "texto sensible que no debe copiarse"})
        self.assertEqual(self._eventos(p), ["revision_iniciada", "estado", "responsable", "observacion"])
        h = HistorialContinuidad.objects.get(gestion__paciente=p, evento="observacion")
        self.assertEqual((h.antes, h.despues), ("", ""))
        h = HistorialContinuidad.objects.get(gestion__paciente=p, evento="responsable")
        self.assertEqual((h.antes, h.despues, h.origen, h.usuario), ("", "coordinacion", "usuario", self.coord))
        self.assertNotIn("sensible", str(HistorialContinuidad.objects.filter(gestion__paciente=p).values()))
        # La pantalla lo recibe legible.
        textos = [x["texto"] for x in self._get(self.coord, p).json()["historial_gestion"]]
        self.assertEqual(textos, ["Revisión iniciada", "Estado → En seguimiento",
                                  "Responsable → Coordinación", "Observación actualizada"])

    def test_guardar_sin_cambios_no_agrega_historial(self):
        p = self._s6_vencido()
        self._patch(self.coord, p, {"estado_revision": "en_seguimiento"})
        n = HistorialContinuidad.objects.count()
        self._patch(self.coord, p, {"estado_revision": "en_seguimiento"})
        self.assertEqual(HistorialContinuidad.objects.count(), n)

    def test_el_patch_ignora_campos_que_no_son_de_gestion(self):
        """Aunque manden decision, n_sesion o próxima cita, nada de eso se toca."""
        p = self._s6_vencido()
        s6 = Cita.objects.get(paciente=p, n_sesion=6)
        r = self._patch(self.coord, p, {"estado_revision": "en_seguimiento", "decision": "DP-10",
                                        "n_sesion": 99, "frecuencia": "alta"})
        self.assertEqual(r.status_code, 200)
        s6.refresh_from_db(); p.refresh_from_db()
        self.assertEqual((s6.decision, s6.n_sesion, p.frecuencia), ("", 6, "semanal"))

    def test_valor_invalido_es_400(self):
        p = self._s6_vencido()
        self.assertEqual(self._patch(self.coord, p, {"estado_revision": "cerrado_x"}).status_code, 400)
        self.assertEqual(self._patch(self.coord, p, {}).status_code, 400)

    def test_caso_que_ya_no_esta_pendiente_es_409(self):
        p = self._paciente("Decidido")
        self._asistidas(p, 6, ultima_hace=3, decision_ultima="DP-08")
        self.assertEqual(self._patch(self.coord, p, {"estado_revision": "en_seguimiento"}).status_code, 409)


class ResueltoNoSilenciaTests(_ConGestion):
    def test_marcar_resuelto_no_saca_el_caso_de_la_cola(self):
        p = self._s6_vencido("Resuelto a mano")
        r = self._patch(self.coord, p, {"estado_revision": "resuelto"})
        self.assertEqual(r.status_code, 200)
        g = self._gestion(p)
        self.assertEqual((g.resuelto_por, g.estado_revision), (self.coord, "resuelto"))
        self.assertIsNotNone(g.resuelto_en)
        # La condición real sigue: la cola la detecta y la pantalla lo dice.
        self.assertIsNotNone(self._fila(p))
        self.assertEqual(r.json()["gestion"]["alerta"], gc.ALERTA_RESUELTO_PENDIENTE)
        self.client.force_login(self.admin)
        filas = self.client.get("/api/continuidad/pendientes/?estado=vencido").json()["filas"]
        fila = next(f for f in filas if f["id"] == p.id)
        self.assertTrue(fila["gestion"]["alerta"])
        # Y sigue entre los prioritarios de Hoy.
        prio = self.client.get("/api/hoy/").json()["continuidad"]["prioritarios"]
        self.assertIn(p.id, [f["id"] for f in prio])

    def test_filtro_resueltos_incluye_el_pendiente_con_alerta(self):
        p = self._s6_vencido("Resuelto a mano")
        self._patch(self.coord, p, {"estado_revision": "resuelto"})
        self.client.force_login(self.admin)
        d = self.client.get("/api/continuidad/pendientes/?estado=todos&revision=resuelto").json()
        self.assertEqual([f["paciente"] for f in d["filas"]], ["Resuelto a mano"])

    def test_volver_a_guardar_reabre_la_gestion_con_historial(self):
        p = self._s6_vencido()
        self._patch(self.coord, p, {"estado_revision": "resuelto"})
        self._patch(self.coord, p, {"estado_revision": "en_seguimiento"})
        g = self._gestion(p)
        self.assertTrue(g.abierta)
        self.assertEqual(G.objects.filter(paciente=p).count(), 1)     # no duplica
        self.assertIn("reabierto", self._eventos(p))


class ResolucionAutomaticaTests(_ConGestion):
    def test_s3_se_resuelve_sola_al_agendar_la_siguiente_cita(self):
        p = self._s3()
        self._patch(self.coord, p, {"estado_revision": "en_seguimiento", "responsable": "coordinacion"})
        self.assertIsNotNone(self._fila(p))
        # Coordinación agenda desde la Agenda (fuente oficial), no desde la gestión.
        self.client.force_login(self.coord)
        fecha = (self.hoy + timedelta(days=3)).isoformat()
        r = self.client.post("/api/citas/", {"pacienteId": p.id, "especialidad": "Terapia", "fecha": fecha,
                                            "hora": "10:00", "forzar": True}, content_type="application/json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIsNone(self._fila(p))                    # la condición desapareció
        g = self._gestion(p)
        self.assertEqual((g.estado_revision, g.resuelto_por), ("resuelto", None))
        self.assertIsNotNone(g.resuelto_en)
        self.assertTrue(g.resuelta_por_sistema)
        h = HistorialContinuidad.objects.get(gestion=g, evento="auto_resuelto")
        self.assertEqual((h.origen, h.usuario, h.antes, h.despues), ("sistema", None, "en_seguimiento", "proxima_cita"))
        texto = self._get(self.coord, p).json()["historial_gestion"][-1]["texto"]
        self.assertIn("Próxima cita detectada", texto)
        self.assertIn("resuelta automáticamente", texto)

    def test_s6_se_resuelve_sola_al_registrar_el_dp(self):
        p = self._s6_vencido()
        self._patch(self.analista, p, {"estado_revision": "en_seguimiento", "responsable": "psicologo"})
        s6 = Cita.objects.get(paciente=p, n_sesion=6)
        self.client.force_login(self.coord)
        r = self.client.patch(f"/api/citas/{s6.id}/", {"decision": "DP-08"}, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(self._fila(p))
        g = self._gestion(p)
        self.assertTrue(g.resuelta_por_sistema)
        h = HistorialContinuidad.objects.get(gestion=g, evento="auto_resuelto")
        self.assertEqual(h.despues, "decision_registrada")

    def test_si_se_revierte_el_dp_la_gestion_se_reabre_y_conserva_el_historial(self):
        p = self._s6_vencido()
        self._patch(self.coord, p, {"estado_revision": "en_seguimiento"})
        s6 = Cita.objects.get(paciente=p, n_sesion=6)
        self.client.force_login(self.coord)
        self.client.patch(f"/api/citas/{s6.id}/", {"decision": "DP-08"}, content_type="application/json")
        n_hist = HistorialContinuidad.objects.filter(gestion__paciente=p).count()
        self.client.patch(f"/api/citas/{s6.id}/", {"decision": ""}, content_type="application/json")
        g = self._gestion(p)
        self.assertTrue(g.abierta)
        self.assertEqual(g.estado_revision, "sin_revisar")
        self.assertEqual(G.objects.filter(paciente=p).count(), 1)
        self.assertEqual(self._eventos(p)[-2:], ["auto_resuelto", "reabierto"])
        self.assertEqual(HistorialContinuidad.objects.filter(gestion__paciente=p).count(), n_hist + 1)

    def test_una_resolucion_manual_no_se_reabre_sola(self):
        p = self._s6_vencido()
        self._patch(self.coord, p, {"estado_revision": "resuelto"})
        # Cualquier cambio en la Agenda que no resuelva la condición no toca la decisión humana.
        Cita.objects.create(clinica=self.clinica, paciente=p, medico=self.psico, estado=Cita.Estado.AGENDADA,
                            inicio=_dt(30))
        g = self._gestion(p)
        self.assertFalse(g.abierta)
        self.assertEqual(g.resuelto_por, self.coord)
        self.assertNotIn("reabierto", self._eventos(p))

    def test_cerrar_el_proceso_en_el_paciente_tambien_resuelve(self):
        p = self._s6_vencido()
        self._patch(self.coord, p, {"estado_revision": "en_seguimiento"})
        p.frecuencia = "alta"; p.save(update_fields=["frecuencia"])
        g = self._gestion(p)
        self.assertTrue(g.resuelta_por_sistema)
        self.assertEqual(HistorialContinuidad.objects.get(gestion=g, evento="auto_resuelto").despues, "proceso_cerrado")

    def test_el_cierre_anterior_sin_decidir_no_se_cierra_solo_al_avanzar(self):
        """Gestión del cierre 6; el paciente sigue a la 7 sin decidir la 6. La
        condición sigue (ahora como 'continuó'): la gestión se mantiene abierta."""
        p = self._s6_vencido()
        self._patch(self.coord, p, {"estado_revision": "en_seguimiento"})
        Cita.objects.create(clinica=self.clinica, paciente=p, medico=self.psico, n_sesion=7,
                            estado=Cita.Estado.ASISTIO, inicio=_dt(-1))
        g = self._gestion(p)
        self.assertTrue(g.abierta)
        self.assertEqual(self._fila(p)["estado"], C.EstadoCierre.CONTINUO_SIN_DECISION)
        self.assertEqual(self._get(self.coord, p).json()["gestion"]["estado_revision"], "en_seguimiento")


class IdentidadDeGestionTests(_ConGestion):
    def test_un_nuevo_proceso_abre_otra_gestion(self):
        p = self._paciente("Dos procesos")
        self._asistidas(p, 6, ultima_hace=200)
        self._patch(self.coord, p, {"estado_revision": "en_seguimiento"})
        s6_vieja = Cita.objects.get(paciente=p, n_sesion=6)
        self.client.force_login(self.coord)
        self.client.patch(f"/api/citas/{s6_vieja.id}/", {"decision": "DP-10"}, content_type="application/json")
        self.assertTrue(self._gestion(p).resuelta_por_sistema)
        # Meses después, proceso nuevo S1..S6 sin decidir.
        for i in range(6):
            Cita.objects.create(clinica=self.clinica, paciente=p, medico=self.psico, n_sesion=i + 1,
                                estado=Cita.Estado.ASISTIO, inicio=_dt(-40 + 7 * i))
        self._patch(self.coord, p, {"estado_revision": "en_seguimiento"})
        gs = list(G.objects.filter(paciente=p).order_by("id"))
        self.assertEqual(len(gs), 2)
        self.assertEqual(gs[0].cita_referencia, s6_vieja)
        self.assertFalse(gs[0].abierta)
        self.assertTrue(gs[1].abierta)
        self.assertNotEqual(gs[1].cita_referencia_id, s6_vieja.id)
        self.assertEqual((gs[1].tipo, gs[1].meta), (C.TIPO_CIERRE_BLOQUE, 6))

    def test_s6_y_s12_son_gestiones_distintas(self):
        p = self._paciente("Seis y doce")
        self._asistidas(p, 12, ultima_hace=3)          # vigente: cierre 12; anterior sin decidir: 6
        self._patch(self.coord, p, {"estado_revision": "en_seguimiento"})
        g12 = self._gestion(p)
        self.assertEqual(g12.meta, 12)
        s12 = Cita.objects.get(paciente=p, n_sesion=12)
        self.client.force_login(self.coord)
        self.client.patch(f"/api/citas/{s12.id}/", {"decision": "DP-08"}, content_type="application/json")
        g12.refresh_from_db()
        self.assertTrue(g12.resuelta_por_sistema)       # el 12 se cerró
        self.assertEqual(self._fila(p)["meta"], 6)      # sube el 6
        self._patch(self.coord, p, {"estado_revision": "en_seguimiento"})
        g6 = self._gestion(p)
        self.assertNotEqual(g6.id, g12.id)
        self.assertEqual((g6.meta, g6.cita_referencia.n_sesion), (6, 6))

    def test_pre_cierre_y_cierre_son_la_misma_gestion_y_la_referencia_avanza(self):
        p = self._paciente("Avanza")
        self._asistidas(p, 5, ultima_hace=3)
        self._patch(self.coord, p, {"estado_revision": "en_seguimiento"})
        g = self._gestion(p)
        self.assertEqual(g.cita_referencia.n_sesion, 5)
        Cita.objects.create(clinica=self.clinica, paciente=p, medico=self.psico, n_sesion=6,
                            estado=Cita.Estado.ASISTIO, inicio=_dt(0))
        self._patch(self.coord, p, {"responsable": "coordinacion"})
        self.assertEqual(G.objects.filter(paciente=p).count(), 1)
        g.refresh_from_db()
        self.assertEqual(g.cita_referencia.n_sesion, 6)
        self.assertIn("referencia", self._eventos(p))

    def test_no_puede_haber_dos_abiertas_del_mismo_evento(self):
        p = self._s6_vencido()
        G.objects.create(clinica=self.clinica, paciente=p, tipo=C.TIPO_CIERRE_BLOQUE, meta=6)
        with self.assertRaises(IntegrityError), transaction.atomic():
            G.objects.create(clinica=self.clinica, paciente=p, tipo=C.TIPO_CIERRE_BLOQUE, meta=6)
        # Resuelta + abierta sí conviven: es la historia.
        G.objects.filter(paciente=p).update(resuelto_en=timezone.now())
        G.objects.create(clinica=self.clinica, paciente=p, tipo=C.TIPO_CIERRE_BLOQUE, meta=6)
        self.assertEqual(G.objects.filter(paciente=p).count(), 2)

    def test_el_modelo_no_duplica_datos_oficiales(self):
        campos = {f.name for f in G._meta.get_fields()}
        for prohibido in ("proxima_cita", "decision", "asistencia", "n_sesion", "profesional",
                          "psicologo", "estado_clinico", "alta", "derivacion", "condicion_resuelta"):
            self.assertNotIn(prohibido, campos, prohibido)
        self.assertNotIn("proxima", " ".join(campos))


class PermisosTests(_ConGestion):
    def setUp(self):
        super().setUp()
        self.p = self._s6_vencido("De Piura")                       # ficha = self.ficha (Piura)
        self.otra = Profesional.objects.create(clinica=self.clinica, nombre="Psicóloga Lima", sede="lima")
        self.p_lima = self._s6_vencido("De Lima", sede="lima", ficha=self.otra)

    def test_analista_si_puede_guardar_gestion(self):
        r = self._patch(self.analista, self.p, {"estado_revision": "en_seguimiento", "responsable": "coordinacion"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._gestion(self.p).revisado_por, self.analista)

    def test_analista_no_puede_escribir_nada_mas(self):
        self.client.force_login(self.analista)
        s6 = Cita.objects.get(paciente=self.p, n_sesion=6)
        casos = [
            ("PATCH cita/DP", self.client.patch(f"/api/citas/{s6.id}/", {"decision": "DP-08"}, content_type="application/json")),
            ("PATCH paciente", self.client.patch(f"/api/pacientes/{self.p.id}/", {"frecuencia": "alta"}, content_type="application/json")),
            ("POST cita", self.client.post("/api/citas/", {"pacienteId": self.p.id, "especialidad": "T", "hora": "10:00", "forzar": True}, content_type="application/json")),
            ("DELETE cita", self.client.delete(f"/api/citas/{s6.id}/")),
        ]
        for nombre, r in casos:
            self.assertEqual(r.status_code, 403, nombre)
        s6.refresh_from_db(); self.p.refresh_from_db()
        self.assertEqual((s6.decision, self.p.frecuencia), ("", "semanal"))

    def test_coordinacion_solo_su_sede(self):
        self.assertEqual(self._patch(self.coord, self.p, {"estado_revision": "en_seguimiento"}).status_code, 200)
        self.assertEqual(self._patch(self.coord, self.p_lima, {"estado_revision": "en_seguimiento"}).status_code, 404)
        self.assertEqual(self._get(self.coord, self.p_lima).status_code, 404)
        self.assertFalse(G.objects.filter(paciente=self.p_lima).exists())

    def test_psicologo_solo_sus_pacientes(self):
        self.assertEqual(self._patch(self.psico, self.p, {"estado_revision": "en_seguimiento"}).status_code, 200)
        self.assertEqual(self._patch(self.psico, self.p_lima, {"estado_revision": "en_seguimiento"}).status_code, 404)

    def test_admin_ambas_sedes_y_comercial_nada(self):
        self.assertEqual(self._patch(self.admin, self.p_lima, {"estado_revision": "en_seguimiento"}).status_code, 200)
        com = Usuario.objects.create_user(email="com-g@test.pe", password="x", clinica=self.clinica,
                                          rol=Usuario.Rol.COMERCIAL)
        self.assertEqual(self._patch(com, self.p, {"estado_revision": "en_seguimiento"}).status_code, 403)

    def test_sin_sesion_es_403(self):
        r = self.client.patch(f"/api/continuidad/caso/{self.p.id}/gestion/", {"estado_revision": "en_seguimiento"},
                              content_type="application/json")
        self.assertIn(r.status_code, (401, 403))

    def test_el_detalle_dice_si_puede_gestionar(self):
        self.assertTrue(self._get(self.analista, self.p).json()["puede_gestionar"])
        self.assertTrue(self._get(self.coord, self.p).json()["puede_gestionar"])


class FiltrosDeRevisionTests(_ConGestion):
    def setUp(self):
        super().setUp()
        self.a = self._s6_vencido("Sin revisar", hace=20)
        self.b = self._s6_vencido("En seguimiento", hace=15)
        self.c = self._s6_vencido("Resuelto a mano", hace=10)
        self._patch(self.coord, self.b, {"estado_revision": "en_seguimiento", "responsable": "coordinacion"})
        self._patch(self.coord, self.c, {"estado_revision": "resuelto"})

    def _nombres(self, usuario, revision):
        self.client.force_login(usuario)
        d = self.client.get(f"/api/continuidad/pendientes/?estado=todos&revision={revision}").json()
        return sorted(f["paciente"] for f in d["filas"])

    def test_filtros(self):
        self.assertEqual(self._nombres(self.admin, ""), ["En seguimiento", "Resuelto a mano", "Sin revisar"])
        self.assertEqual(self._nombres(self.admin, "sin_revisar"), ["Sin revisar"])
        self.assertEqual(self._nombres(self.admin, "en_seguimiento"), ["En seguimiento"])
        self.assertEqual(self._nombres(self.admin, "resuelto"), ["Resuelto a mano"])

    def test_requiere_mi_atencion(self):
        # Coordinación: lo sin revisar, lo asignado a coordinación y lo resuelto-pero-pendiente.
        self.assertEqual(self._nombres(self.coord, "atencion"), ["En seguimiento", "Resuelto a mano", "Sin revisar"])
        # Analista (Dirección Clínica): no tiene nada asignado → sin revisar + alerta.
        self.assertEqual(self._nombres(self.analista, "atencion"), ["Resuelto a mano", "Sin revisar"])

    def test_resueltos_lista_lo_que_el_sistema_cerro_aunque_ya_no_este_en_la_cola(self):
        s6 = Cita.objects.get(paciente=self.b, n_sesion=6)
        self.client.force_login(self.coord)
        self.client.patch(f"/api/citas/{s6.id}/", {"decision": "DP-08"}, content_type="application/json")
        self.assertIsNone(self._fila(self.b))
        self.client.force_login(self.admin)
        d = self.client.get("/api/continuidad/pendientes/?estado=todos&revision=resuelto").json()
        fila = next(f for f in d["filas"] if f["paciente"] == "En seguimiento")
        self.assertEqual(fila["estado"], "cerrado")
        self.assertTrue(fila["gestion"]["resuelta_por_sistema"])
        self.assertFalse(fila["gestion"]["alerta"])
