"""Consolidación de pacientes duplicados: detectar, avisar, fusionar sin perder nada.

Sale de una auditoría real de producción (set. 2026): 65 grupos de confianza
ALTA, 76 fichas de más sobre 1.646 pacientes, 34 personas con su próxima cita
en la ficha que Coordinación no estaba mirando. La causa dominante fue el
formulario de crear paciente, que guardaba sin comprobar nada.

Lo delicado de estas pruebas no es que la fusión funcione: es que NO fusione de
más (homónimos, familiares con el mismo celular, expedientes de pareja) y que,
cuando fusiona, no se pierda ni una fila.

    python manage.py test pacientes.tests_duplicados
"""
from datetime import date, timedelta

from django.db import transaction
from django.test import TestCase
from django.utils import timezone

from core import continuidad as cont
from core.models import Clinica
from finanzas.models import Cobro
from leads.models import Lead
from mensajes.models import Mensaje
from pacientes import duplicados, fusion
from pacientes.models import (
    AplicacionEscala, Atencion, Cita, Consentimiento, ContactoProfesional,
    GestionContinuidad, HistorialContinuidad, ObjetivoTerapeutico, Paciente,
    RegistroFusionPaciente, RespuestaNPS, RevisionDuplicado, SeguimientoSesion, Tarea,
)
from usuarios.models import Profesional, Usuario


class Base(TestCase):
    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="dup-test")
        self.otra = Clinica.objects.create(nombre="Otra", slug="dup-otra")
        self.admin = Usuario.objects.create_user(
            email="admin@dup.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ADMIN)
        self.coord = Usuario.objects.create_user(
            email="coord@dup.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ASISTENTE)
        self.psico_user = Usuario.objects.create_user(
            email="psico@dup.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.MEDICO)
        self.prof = Profesional.objects.create(
            clinica=self.clinica, nombre="Sofía Ferreyra", usuario=self.psico_user, sede="piura")
        self.ahora = timezone.now()

    def pac(self, nombre, **kw):
        kw.setdefault("clinica", self.clinica)
        return Paciente.objects.create(nombre=nombre, **kw)

    def cita(self, p, dias, n=None, estado="atendida", decision="", servicio="Terapia individual"):
        return Cita.objects.create(
            clinica=p.clinica, paciente=p, medico=self.psico_user,
            inicio=self.ahora + timedelta(days=dias), n_sesion=n, estado=estado,
            decision=decision, especialidad=servicio, sede=p.sede, notas="Sesión.")


# ---------------------------------------------------------------------------
# Detección: lo importante es a quién NO señala
# ---------------------------------------------------------------------------

class DeteccionTests(Base):
    def test_mismo_nombre_y_telefono_es_alta(self):
        a = self.pac("Ariana Belén Martínez Paiva", sede="piura", telefono="987654321")
        b = self.pac("ARIANA BELEN MARTINEZ PAIVA", sede="piura", telefono="+51 987 654 321")
        gs, _ = duplicados.grupos(self.clinica)
        self.assertEqual([sorted([a.pk, b.pk])], [g for g, _s in gs])

    def test_mismo_documento_es_alta_aunque_el_nombre_cambie(self):
        a = self.pac("Elena Vargas Soto", numero_documento="40112233")
        b = self.pac("Elena Vargas", numero_documento="40112233")
        gs, _ = duplicados.grupos(self.clinica)
        self.assertEqual([sorted([a.pk, b.pk])], [g for g, _s in gs])

    def test_homonimos_con_documentos_distintos_no_se_ofrecen(self):
        """Dos DNI válidos y distintos son dos personas: gana al nombre igual."""
        self.pac("Carlos Rojas", sede="piura", numero_documento="44556677", telefono="911111111")
        self.pac("Carlos Rojas", sede="piura", numero_documento="70123456", telefono="911111111")
        todos, _ = duplicados.pares(self.clinica)
        self.assertEqual(todos, [])

    def test_familiares_con_el_mismo_celular_no_son_duplicado(self):
        self.pac("Rosa Díaz Quispe", sede="lima", telefono="955555555")
        self.pac("Luis Mendoza Díaz", sede="lima", telefono="955555555")
        todos, _ = duplicados.pares(self.clinica)
        self.assertEqual(todos, [])

    def test_expediente_de_pareja_no_se_cruza_con_el_individual(self):
        self.pac("Andrea Zapata", sede="lima", telefono="966666666")
        self.pac("Andrea Zapata y Roy Pozo", sede="lima", telefono="966666666")
        todos, _ = duplicados.pares(self.clinica)
        self.assertEqual(todos, [])

    def test_telefono_corto_no_identifica(self):
        """Con menos de 9 dígitos hay un dato a medio cargar, no un identificador."""
        self.pac("Juan Paz Vera", sede="lima", telefono="123456")
        self.pac("Juan Paz Vera", sede="lima", telefono="123456")
        todos, _ = duplicados.pares(self.clinica)
        self.assertTrue(all(r["confianza"] != duplicados.ALTA for r in todos))

    def test_nacimiento_distinto_descarta(self):
        self.pac("Mario Luna", sede="lima", telefono="977777777", fecha_nacimiento=date(1990, 1, 1))
        self.pac("Mario Luna", sede="lima", telefono="977777777", fecha_nacimiento=date(1991, 5, 2))
        todos, _ = duplicados.pares(self.clinica)
        self.assertEqual(todos, [])

    def test_sedes_distintas_bajan_la_confianza(self):
        self.pac("Jorge Ramos Vela", sede="lima", telefono="988888888")
        self.pac("Jorge Ramos Vela", sede="piura", telefono="988888888")
        todos, _ = duplicados.pares(self.clinica)
        self.assertTrue(all(r["confianza"] != duplicados.ALTA for r in todos))

    def test_tutor_telefono_es_pista_no_identidad(self):
        """El número del tutor sirve para MIRAR el par, nunca para darlo por resuelto."""
        self.pac("Luis Mendoza Díaz", sede="lima", tutor_telefono="955555555")
        self.pac("Luis Mendoza Díaz", sede="lima", telefono="955555555")
        todos, _ = duplicados.pares(self.clinica)
        self.assertEqual(len(todos), 1)
        self.assertEqual(todos[0]["confianza"], duplicados.MEDIA)

    def test_no_cruza_clinicas(self):
        self.pac("Ana Torres", sede="lima", telefono="999999999")
        Paciente.objects.create(clinica=self.otra, nombre="Ana Torres", sede="lima",
                                telefono="999999999")
        todos, _ = duplicados.pares(self.clinica)
        self.assertEqual(todos, [])

    def test_descartado_no_se_vuelve_a_ofrecer(self):
        a = self.pac("Pedro Ruiz", sede="lima", telefono="911223344")
        b = self.pac("Pedro Ruiz", sede="lima", telefono="911223344")
        RevisionDuplicado.objects.create(clinica=self.clinica, paciente_a=a, paciente_b=b)
        todos, _ = duplicados.pares(self.clinica)
        self.assertEqual(todos, [])
        con, _ = duplicados.pares(self.clinica, incluir_descartados=True)
        self.assertEqual(len(con), 1)


# ---------------------------------------------------------------------------
# Prevención: el formulario avisa antes de crear
# ---------------------------------------------------------------------------

class AvisoAlCrearTests(Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.coord)

    def test_avisa_cuando_ya_existe_mismo_nombre_y_telefono(self):
        existente = self.pac("Ariana Belén Martínez Paiva", sede="piura", telefono="987654321")
        r = self.client.post("/api/pacientes/", {
            "nombre": "Ariana Belen Martinez Paiva", "telefono": "987 654 321", "sede": "piura",
        }, content_type="application/json")
        self.assertEqual(r.status_code, 409)
        ids = [p["id"] for p in r.json()["posibles_duplicados"]]
        self.assertIn(existente.pk, ids)
        self.assertEqual(Paciente.objects.count(), 1)

    def test_el_aviso_enmascara_el_contacto(self):
        self.pac("Ariana Belén Martínez Paiva", sede="piura", telefono="987654321",
                 numero_documento="70112233")
        r = self.client.post("/api/pacientes/", {
            "nombre": "Ariana Belén Martínez Paiva", "telefono": "987654321", "sede": "piura",
        }, content_type="application/json")
        p = r.json()["posibles_duplicados"][0]
        self.assertTrue(p["telefono"].startswith("*"))
        self.assertTrue(p["telefono"].endswith("321"))
        self.assertNotIn("987654321", str(r.json()))
        self.assertNotIn("70112233", str(r.json()))

    def test_confirmar_nuevo_crea_la_persona_distinta(self):
        self.pac("Ariana Belén Martínez Paiva", sede="piura", telefono="987654321")
        r = self.client.post("/api/pacientes/", {
            "nombre": "Ariana Belén Martínez Paiva", "telefono": "987654321", "sede": "piura",
            "confirmar_nuevo": True,
        }, content_type="application/json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Paciente.objects.count(), 2)

    def test_homonimo_con_otro_documento_no_molesta(self):
        self.pac("Carlos Rojas", sede="piura", numero_documento="44556677")
        r = self.client.post("/api/pacientes/", {
            "nombre": "Carlos Rojas", "sede": "piura", "numero_documento": "70123456",
        }, content_type="application/json")
        self.assertEqual(r.status_code, 201)

    def test_familiar_con_el_mismo_celular_no_molesta(self):
        self.pac("Rosa Díaz Quispe", sede="lima", telefono="955555555")
        r = self.client.post("/api/pacientes/", {
            "nombre": "Luis Mendoza Díaz", "sede": "lima", "telefono": "955555555",
        }, content_type="application/json")
        self.assertEqual(r.status_code, 201)

    def test_telefono_corto_no_dispara_el_aviso(self):
        self.pac("Juan Paz Vera", sede="lima", telefono="123456")
        r = self.client.post("/api/pacientes/", {
            "nombre": "Otro Nombre Distinto", "sede": "lima", "telefono": "123456",
        }, content_type="application/json")
        self.assertEqual(r.status_code, 201)

    def test_tutor_telefono_avisa(self):
        self.pac("Luis Mendoza Díaz", sede="lima", tutor_telefono="955555555")
        r = self.client.post("/api/pacientes/", {
            "nombre": "Luis Mendoza Díaz", "sede": "lima", "tutor_telefono": "955555555",
        }, content_type="application/json")
        self.assertEqual(r.status_code, 409)


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

class DryRunTests(Base):
    def setUp(self):
        super().setUp()
        # El caso Ariana, tal como salió en producción.
        self.a = self.pac("Ariana Belén Martínez Paiva", sede="piura", telefono="987654321",
                          numero_documento="70112870", fecha_nacimiento=date(2008, 12, 1),
                          profesional=self.prof)
        self.b = self.pac("Ariana Belén Martínez Paiva", sede="piura", telefono="987654321")
        self.cita(self.a, -39, n=1, decision="DP-01")
        self.cita(self.a, -28, n=2)
        for i, n in enumerate((3, 4, 5)):
            self.cita(self.b, -18 + i * 7, n=n)
        self.futura = self.cita(self.b, 1, estado="agendada")

    def test_no_escribe_nada(self):
        antes = {m.__name__: m.objects.count() for m in (Paciente, Cita, GestionContinuidad,
                                                         RegistroFusionPaciente)}
        fusion.analizar_fusion(self.a, self.b)
        fusion.analizar_fusion(self.a, self.b)
        despues = {m.__name__: m.objects.count() for m in (Paciente, Cita, GestionContinuidad,
                                                           RegistroFusionPaciente)}
        self.assertEqual(antes, despues)

    def test_es_reproducible(self):
        uno = fusion.analizar_fusion(self.a, self.b)
        dos = fusion.analizar_fusion(self.a, self.b)
        self.assertEqual(uno, dos)

    def test_proyecta_la_historia_unida(self):
        r = fusion.analizar_fusion(self.a, self.b)
        c = r["continuidad"]
        self.assertEqual(c["principal"]["sesion"], 2)
        self.assertEqual(c["secundario"]["sesion"], 5)
        self.assertEqual(c["despues"]["sesion"], 5)          # emerge de la historia, no hardcodeado
        self.assertEqual(c["despues"]["sesiones_asistidas"], 5)
        self.assertIsNone(c["principal"]["proxima_cita"])
        self.assertIsNotNone(c["despues"]["proxima_cita"])

    def test_lista_todas_las_relaciones(self):
        r = fusion.analizar_fusion(self.a, self.b)
        labels = {x["label"] for x in r["relaciones"]}
        for esperado in ("pacientes.Cita", "pacientes.Atencion", "pacientes.Consentimiento",
                         "pacientes.AplicacionEscala", "pacientes.Adjunto",
                         "pacientes.ObjetivoTerapeutico", "pacientes.GestionContinuidad",
                         "pacientes.SeguimientoSesion", "pacientes.Tarea", "finanzas.Cobro",
                         "finanzas.Paquete", "pacientes.RespuestaNPS",
                         "pacientes.ContactoProfesional", "leads.Lead", "mensajes.Mensaje"):
            self.assertIn(esperado, labels)

    def test_recomienda_la_ficha_con_mas_identidad(self):
        r = fusion.analizar_fusion(self.b, self.a)
        self.assertEqual(r["recomendado_id"], self.a.pk)     # tiene documento y psicóloga

    def test_dice_que_id_desaparece(self):
        r = fusion.analizar_fusion(self.a, self.b)
        self.assertEqual(r["id_que_sobrevive"], self.a.pk)
        self.assertEqual(r["id_que_desaparece"], self.b.pk)

    def test_detecta_conflicto_de_documento(self):
        otro = self.pac("Ariana Belén Martínez Paiva", numero_documento="11112222", sede="piura")
        r = fusion.analizar_fusion(self.a, otro)
        self.assertFalse(r["puede_fusionar"])
        self.assertTrue(any("documentos válidos DISTINTOS" in c for c in r["conflictos"]))


# ---------------------------------------------------------------------------
# Fusión real
# ---------------------------------------------------------------------------

class FusionTests(Base):
    def setUp(self):
        super().setUp()
        self.a = self.pac("Ana Pérez", sede="lima", telefono="987000111", profesional=self.prof)
        self.b = self.pac("Ana María Pérez Gómez", sede="lima", telefono="987000111",
                          email="ana@correo.pe", numero_documento="70999888", provisional=True)
        self.ca = self.cita(self.a, -14, n=1)
        self.cb = self.cita(self.b, -7, n=2)

    def _poblar(self, p):
        """Una fila de cada relación que cuelga del paciente."""
        Atencion.objects.create(clinica=self.clinica, paciente=p, medico=self.psico_user,
                                fecha=timezone.localdate(), nota="evolución")
        Consentimiento.objects.create(clinica=self.clinica, paciente=p,
                                      token="tok-%s" % p.pk, texto="Consentimiento informado.")
        AplicacionEscala.objects.create(clinica=self.clinica, paciente=p, escala="phq9",
                                        puntaje=5, fecha=timezone.localdate())
        ObjetivoTerapeutico.objects.create(clinica=self.clinica, paciente=p, texto="objetivo")
        SeguimientoSesion.objects.create(clinica=self.clinica, paciente=p, anio=2026, mes=9,
                                         semana=1 if p.pk == self.a.pk else 2)
        Tarea.objects.create(clinica=self.clinica, paciente=p, texto="tarea")
        RespuestaNPS.objects.create(clinica=self.clinica, paciente=p, puntaje=9,
                                    fecha=timezone.localdate())
        ContactoProfesional.objects.create(clinica=self.clinica, paciente=p, nombre="Dr. X")
        Cobro.objects.create(clinica=self.clinica, paciente=p, concepto="Sesión", monto=80)
        Lead.objects.create(clinica=self.clinica, nombre=p.nombre, paciente=p)
        Mensaje.objects.create(clinica=self.clinica, paciente=p, texto="hola", estado="enviado")

    def test_mueve_todas_las_relaciones_y_borra_la_secundaria(self):
        self._poblar(self.a)
        self._poblar(self.b)
        b_id = self.b.pk
        fusion.fusionar_pacientes(self.a, self.b, self.admin, motivo="misma persona")

        self.assertFalse(Paciente.objects.filter(pk=b_id).exists())
        self.assertTrue(Paciente.objects.filter(pk=self.a.pk).exists())
        self.assertEqual(Paciente.objects.count(), 1)
        for modelo in (Atencion, Consentimiento, AplicacionEscala, ObjetivoTerapeutico,
                       SeguimientoSesion, Tarea, RespuestaNPS, ContactoProfesional, Cobro):
            self.assertEqual(modelo.objects.filter(paciente=self.a).count(), 2,
                             "%s no movió sus filas" % modelo.__name__)
        self.assertEqual(Cita.objects.filter(paciente=self.a).count(), 2)
        self.assertEqual(Lead.objects.filter(paciente=self.a).count(), 2)
        self.assertEqual(Mensaje.objects.filter(paciente=self.a).count(), 2)

    def test_la_cita_conserva_su_id(self):
        """Lo que cuelga de la cita (Lead.cita, el evento de Google Calendar) no
        puede romperse: la cita solo cambia de paciente."""
        fusion.fusionar_pacientes(self.a, self.b, self.admin)
        self.cb.refresh_from_db()
        self.assertEqual(self.cb.paciente_id, self.a.pk)

    def test_hereda_lo_que_faltaba_sin_pisar_lo_cargado(self):
        fusion.fusionar_pacientes(self.a, self.b, self.admin)
        self.a.refresh_from_db()
        self.assertEqual(self.a.email, "ana@correo.pe")
        self.assertEqual(self.a.numero_documento, "70999888")
        self.assertEqual(self.a.profesional_id, self.prof.pk)      # el suyo, no vacío
        self.assertEqual(self.a.nombre, "Ana María Pérez Gómez")   # el más completo

    def test_no_pisa_un_dato_valido_del_principal(self):
        self.b.telefono = "955000222"
        self.b.save()
        fusion.fusionar_pacientes(self.a, self.b, self.admin)
        self.a.refresh_from_db()
        self.assertEqual(self.a.telefono, "987000111")

    def test_texto_clinico_de_las_dos_se_conserva(self):
        self.a.antecedentes = "Ansiedad desde 2024."
        self.a.save()
        self.b.antecedentes = "Refiere duelo reciente."
        self.b.save()
        fusion.fusionar_pacientes(self.a, self.b, self.admin)
        self.a.refresh_from_db()
        self.assertIn("Ansiedad desde 2024.", self.a.antecedentes)
        self.assertIn("Refiere duelo reciente.", self.a.antecedentes)

    def test_deja_de_ser_provisional(self):
        self.a.provisional = True
        self.a.save()
        self.b.provisional = False
        self.b.save()
        fusion.fusionar_pacientes(self.a, self.b, self.admin)
        self.a.refresh_from_db()
        self.assertFalse(self.a.provisional)

    def test_deja_constancia_aunque_la_ficha_desaparezca(self):
        a_id, b_id = self.a.pk, self.b.pk
        fusion.fusionar_pacientes(self.a, self.b, self.admin, motivo="mismo teléfono y nombre")
        r = RegistroFusionPaciente.objects.get()
        self.assertEqual(r.principal_id_original, a_id)
        self.assertEqual(r.secundario_id_eliminado, b_id)
        self.assertEqual(r.fusionado_por, self.admin)
        self.assertEqual(r.motivo, "mismo teléfono y nombre")
        self.assertEqual(r.relaciones_movidas.get("pacientes.Cita"), 1)
        self.assertIsNotNone(r.creado_en)

    def test_el_registro_no_es_un_paciente(self):
        fusion.fusionar_pacientes(self.a, self.b, self.admin)
        self.assertEqual(Paciente.objects.count(), 1)

    def test_seguimiento_de_la_misma_semana_se_une_sin_perder_el_avance(self):
        """Las dos fichas con la misma semana: `uniq_seg_paciente_semana` no
        deja dos filas, así que se conserva el número de sesión más alto."""
        SeguimientoSesion.objects.create(clinica=self.clinica, paciente=self.a, anio=2026,
                                         mes=9, semana=1, n_sesion=2, proceso="primero")
        SeguimientoSesion.objects.create(clinica=self.clinica, paciente=self.b, anio=2026,
                                         mes=9, semana=1, n_sesion=5, proceso="segundo")
        fusion.fusionar_pacientes(self.a, self.b, self.admin)
        quedan = SeguimientoSesion.objects.filter(paciente=self.a)
        self.assertEqual(quedan.count(), 1)
        self.assertEqual(quedan.first().n_sesion, 5)
        self.assertEqual(quedan.first().proceso, "segundo")

    def test_los_descartes_de_la_ficha_borrada_se_limpian(self):  # noqa: D401
        otro = self.pac("Tercera Persona", sede="lima")
        RevisionDuplicado.objects.create(clinica=self.clinica, paciente_a=self.b, paciente_b=otro)
        fusion.fusionar_pacientes(self.a, self.b, self.admin)
        self.assertEqual(RevisionDuplicado.objects.count(), 0)


# ---------------------------------------------------------------------------
# Seguridad: cuándo NO se fusiona, y qué pasa si algo falla
# ---------------------------------------------------------------------------

class SeguridadTests(Base):
    def setUp(self):
        super().setUp()
        self.a = self.pac("Ana Pérez", sede="lima", telefono="987000111")
        self.b = self.pac("Ana Pérez", sede="lima", telefono="987000111")

    def _bloqueada(self, a, b, **kw):
        with self.assertRaises(fusion.FusionBloqueada):
            fusion.fusionar_pacientes(a, b, self.admin, **kw)
        self.assertTrue(Paciente.objects.filter(pk=b.pk).exists())

    def test_clinicas_distintas_bloqueadas(self):
        otra = Paciente.objects.create(clinica=self.otra, nombre="Ana Pérez")
        self._bloqueada(self.a, otra)

    def test_documentos_validos_distintos_bloqueados(self):
        self.a.numero_documento = "44556677"
        self.a.save()
        self.b.numero_documento = "70123456"
        self.b.save()
        self._bloqueada(self.a, self.b)

    def test_nacimiento_distinto_bloqueado(self):
        self.a.fecha_nacimiento = date(1990, 1, 1)
        self.a.save()
        self.b.fecha_nacimiento = date(1991, 1, 1)
        self.b.save()
        self._bloqueada(self.a, self.b)

    def test_sede_distinta_requiere_decision_explicita(self):
        self.b.sede = "piura"
        self.b.save()
        b_id = self.b.pk
        self._bloqueada(self.a, self.b)
        fusion.fusionar_pacientes(self.a, self.b, self.admin, aceptar_sede_distinta=True)
        self.assertFalse(Paciente.objects.filter(pk=b_id).exists())

    def test_misma_ficha_bloqueada(self):
        self._bloqueada(self.a, self.a)

    def test_un_error_intermedio_deshace_todo(self):
        """Si algo revienta después de mover, no puede quedar media fusión."""
        self.cita(self.b, -3, n=1)
        Cobro.objects.create(clinica=self.clinica, paciente=self.b, concepto="S", monto=50)
        original = fusion.RegistroFusionPaciente.objects.create

        def explota(*a, **kw):
            raise RuntimeError("falla simulada al dejar constancia")

        fusion.RegistroFusionPaciente.objects.create = explota
        try:
            with self.assertRaises(RuntimeError):
                fusion.fusionar_pacientes(self.a, self.b, self.admin)
        finally:
            fusion.RegistroFusionPaciente.objects.create = original

        self.assertTrue(Paciente.objects.filter(pk=self.b.pk).exists())
        self.assertEqual(Cita.objects.filter(paciente=self.b).count(), 1)
        self.assertEqual(Cobro.objects.filter(paciente=self.b).count(), 1)
        self.assertEqual(RegistroFusionPaciente.objects.count(), 0)

    def test_hoy_todas_las_relaciones_tienen_manejo(self):
        """Ninguna relación de hoy queda sin saber mover."""
        plan, bloqueos = fusion.plan_de_relaciones(self.a, self.b)
        self.assertEqual(bloqueos, [])
        labels = {r["label"] for r in plan}
        self.assertIn("pacientes.GestionContinuidad", labels)
        self.assertIn("pacientes.SeguimientoSesion", labels)

    def test_una_relacion_sin_manejo_bloquea_en_vez_de_romper(self):
        """El comando viejo reventaba con ProtectedError porque
        GestionContinuidad no estaba en su lista escrita a mano. Ahora, si una
        relación con restricción de unicidad se queda sin manejo propio, la
        fusión se detiene ANTES de tocar nada."""
        original = fusion._handlers
        fusion._handlers = lambda: {}
        try:
            plan, bloqueos = fusion.plan_de_relaciones(self.a, self.b)
            self.assertTrue(any("GestionContinuidad" in b for b in bloqueos))
            self.assertTrue(any("SeguimientoSesion" in b for b in bloqueos))
            with self.assertRaises(fusion.FusionBloqueada):
                fusion.fusionar_pacientes(self.a, self.b, self.admin)
        finally:
            fusion._handlers = original
        self.assertTrue(Paciente.objects.filter(pk=self.b.pk).exists())


# ---------------------------------------------------------------------------
# Continuidad después de fusionar
# ---------------------------------------------------------------------------

class ContinuidadTests(Base):
    def setUp(self):
        super().setUp()
        self.a = self.pac("Ana Pérez", sede="lima", telefono="987000111",
                          profesional=self.prof, sesiones_proceso=6)
        self.b = self.pac("Ana Pérez", sede="lima", telefono="987000111", sesiones_proceso=6)

    def test_la_alerta_falsa_desaparece(self):
        """El caso medido en producción: la cola pide agendar a alguien que ya
        tiene cita, porque la cita está en la otra ficha."""
        for i, n in enumerate((1, 2, 3, 4, 5, 6)):
            self.cita(self.a, -42 + i * 7, n=n)
        self.cita(self.b, 3, estado="agendada")

        cola_antes = cont.cola_de_continuidad(Paciente.objects.filter(pk=self.a.pk))
        self.assertTrue(cola_antes, "la ficha partida debería estar alertada")

        fusion.fusionar_pacientes(self.a, self.b, self.admin)
        cola = cont.cola_de_continuidad(Paciente.objects.filter(clinica=self.clinica))
        estados = [f["estado"] for f in cola]
        self.assertNotIn(cont.EstadoCierre.SIN_AGENDAR, estados)

    def test_las_sesiones_quedan_unificadas(self):
        for i, n in enumerate((1, 2)):
            self.cita(self.a, -30 + i * 7, n=n)
        for i, n in enumerate((3, 4, 5)):
            self.cita(self.b, -14 + i * 4, n=n)
        fusion.fusionar_pacientes(self.a, self.b, self.admin)
        citas = list(Cita.objects.filter(paciente=self.a).order_by("inicio")
                     .values("n_sesion", "inicio", "estado", "decision", "especialidad"))
        self.assertEqual(cont.sesion_real(citas), 5)

    def test_la_ficha_borrada_ya_no_entra_en_la_cola(self):
        for i, n in enumerate((1, 2, 3)):
            self.cita(self.b, -21 + i * 7, n=n)
        b_id = self.b.pk
        fusion.fusionar_pacientes(self.a, self.b, self.admin)
        cola = cont.cola_de_continuidad(Paciente.objects.filter(clinica=self.clinica))
        self.assertEqual(len({f["id"] for f in cola}), len(cola))
        self.assertTrue(all(f["id"] != b_id for f in cola))

    def test_gestion_abierta_repetida_no_rompe_la_restriccion(self):
        """Las dos fichas con el MISMO evento abierto: el comando viejo moría
        con ProtectedError; esto tiene que resolverlo y conservar el historial."""
        for i, n in enumerate((1, 2, 3, 4, 5, 6)):
            self.cita(self.a, -42 + i * 7, n=n)
            self.cita(self.b, -40 + i * 7, n=n)
        g1 = GestionContinuidad.objects.create(clinica=self.clinica, paciente=self.a,
                                               tipo="cierre_bloque", meta=6)
        g2 = GestionContinuidad.objects.create(clinica=self.clinica, paciente=self.b,
                                               tipo="cierre_bloque", meta=6)
        HistorialContinuidad.objects.create(clinica=self.clinica, gestion=g2, evento="estado")

        fusion.fusionar_pacientes(self.a, self.b, self.admin)

        self.assertEqual(GestionContinuidad.objects.filter(paciente=self.a).count(), 2)
        abiertas = GestionContinuidad.objects.filter(paciente=self.a, resuelto_en__isnull=True)
        self.assertEqual(abiertas.count(), 1)
        self.assertEqual(abiertas.first().pk, g1.pk)
        g2.refresh_from_db()
        self.assertIsNotNone(g2.resuelto_en)
        self.assertEqual(HistorialContinuidad.objects.filter(gestion=g2).count(), 2)

    def test_gestion_sin_choque_se_mueve_abierta(self):
        for i, n in enumerate((1, 2, 3)):
            self.cita(self.b, -21 + i * 7, n=n)
        g = GestionContinuidad.objects.create(clinica=self.clinica, paciente=self.b,
                                              tipo="riesgo_s3", meta=3)
        fusion.fusionar_pacientes(self.a, self.b, self.admin)
        g.refresh_from_db()
        self.assertEqual(g.paciente_id, self.a.pk)
        self.assertIsNone(g.resuelto_en)


# ---------------------------------------------------------------------------
# Permisos y endpoints
# ---------------------------------------------------------------------------

class PermisosTests(Base):
    def setUp(self):
        super().setUp()
        self.a = self.pac("Ana Pérez", sede="lima", telefono="987000111")
        self.b = self.pac("Ana Pérez", sede="lima", telefono="987000111")

    def test_coordinacion_revisa_pero_no_fusiona(self):
        self.client.force_login(self.coord)
        self.assertEqual(self.client.get("/api/duplicados/").status_code, 200)
        r = self.client.post("/api/duplicados/analizar/",
                             {"principal": self.a.pk, "secundario": self.b.pk},
                             content_type="application/json")
        self.assertEqual(r.status_code, 200)
        r = self.client.post("/api/duplicados/fusionar/",
                             {"principal": self.a.pk, "secundario": self.b.pk, "confirmar": True},
                             content_type="application/json")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(Paciente.objects.count(), 2)

    def test_el_psicologo_no_entra(self):
        self.client.force_login(self.psico_user)
        self.assertEqual(self.client.get("/api/duplicados/").status_code, 403)

    def test_gerencia_fusiona_pero_exige_confirmacion(self):
        self.client.force_login(self.admin)
        r = self.client.post("/api/duplicados/fusionar/",
                             {"principal": self.a.pk, "secundario": self.b.pk},
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Paciente.objects.count(), 2)

        r = self.client.post("/api/duplicados/fusionar/",
                             {"principal": self.a.pk, "secundario": self.b.pk, "confirmar": True},
                             content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["eliminado_id"], self.b.pk)
        self.assertEqual(Paciente.objects.count(), 1)

    def test_conflicto_devuelve_409_y_no_fusiona(self):
        self.a.numero_documento = "44556677"
        self.a.save()
        self.b.numero_documento = "70123456"
        self.b.save()
        self.client.force_login(self.admin)
        r = self.client.post("/api/duplicados/fusionar/",
                             {"principal": self.a.pk, "secundario": self.b.pk, "confirmar": True},
                             content_type="application/json")
        self.assertEqual(r.status_code, 409)
        self.assertTrue(r.json()["conflictos"])
        self.assertEqual(Paciente.objects.count(), 2)

    def test_descartar_deja_de_ofrecer_el_par(self):
        self.client.force_login(self.coord)
        self.assertEqual(self.client.get("/api/duplicados/").json()["total"], 1)
        r = self.client.post("/api/duplicados/descartar/",
                             {"a": self.a.pk, "b": self.b.pk, "nota": "son hermanas"},
                             content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get("/api/duplicados/").json()["total"], 0)
