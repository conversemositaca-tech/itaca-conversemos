"""Pruebas de la lectura automática de los mensajes de WhatsApp.

Son los casos reales que trajo el equipo (corrección #3): la persona pregunta
por terapia de pareja y costos, o pide cita en "Miraflores, Lima".

    python manage.py test leads
"""
from datetime import date, datetime, time as dtime, timedelta

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from decimal import Decimal

from core.models import Clinica
from finanzas.models import Servicio
from pacientes.models import Cita, Paciente
from usuarios.models import Usuario
from leads.models import Anuncio, Lead
from leads.reporte import generar_reporte_pauta
from leads.whatsapp_auto import analizar


class AnalizarMensajeTests(SimpleTestCase):
    """`analizar` no toca la base de datos: es solo lectura del texto."""

    def test_pregunta_por_pareja_y_costos(self):
        a = analizar("Hola, hacen terapia de pareja? cuanto cuesta la sesion?")
        self.assertEqual(a["tipo_servicio"], Lead.TipoServicio.PAREJA)
        self.assertTrue(a["es_pareja"])
        self.assertIn("servicios", a["intenciones"])
        self.assertIn("precios", a["intenciones"])

    def test_pide_cita_en_miraflores(self):
        a = analizar("Buenas, quiero reservar una cita en Miraflores, Lima")
        self.assertEqual(a["ubicacion"], "Miraflores")
        self.assertEqual(a["sede"], Lead.Sede.LIMA)
        self.assertTrue(a["pide_cita"])

    def test_distrito_mas_especifico_gana(self):
        # "San Juan de Miraflores" no debe leerse como "Miraflores" ni "Lima".
        a = analizar("Vivo en San Juan de Miraflores")
        self.assertEqual(a["ubicacion"], "San Juan de Miraflores")
        self.assertEqual(a["sede"], Lead.Sede.LIMA)

    def test_reconoce_piura_y_sin_acentos(self):
        a = analizar("Estoy en Castilla, atienden ninos?")
        self.assertEqual(a["sede"], Lead.Sede.PIURA)
        self.assertEqual(a["tipo_servicio"], Lead.TipoServicio.NINOS)

    def test_adolescente_no_se_confunde_con_nino(self):
        a = analizar("Es para mi hija adolescente")
        self.assertEqual(a["tipo_servicio"], Lead.TipoServicio.ADOLESCENTES)

    def test_modalidad_online(self):
        a = analizar("Las sesiones son online? que precio tienen")
        self.assertEqual(a["modalidad"], "online")
        self.assertIn("precios", a["intenciones"])

    def test_saludo_suelto_no_dispara_respuesta(self):
        a = analizar("Hola buenas tardes")
        self.assertEqual(a["intenciones"], [])
        self.assertFalse(a["pide_cita"])
        self.assertEqual(a["tipo_servicio"], "")

    def test_mensaje_vacio(self):
        a = analizar("")
        self.assertEqual(a["intenciones"], [])
        self.assertEqual(a["ubicacion"], "")


class ReportePautaTests(TestCase):
    """De qué anuncio vino cada consulta.

    Caso real que reportó el equipo de marketing: "del 1 al 9, si son cinco citas
    agendadas, debería aparecer de qué video llegaron, pero el sistema solo me
    arroja una, en ambas sedes".

    Pasaba por dos motivos que se sumaban: el equipo registra cada etapa del
    embudo como una fila NUEVA, y al agrupar por persona ganaba la fila más
    avanzada —que ya no trae el anuncio—; y el reporte solo miraba los leads con
    `es_pauta`, cuando la pauta de Meta hace que la gente escriba por WhatsApp.
    """

    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-rep")
        self.anuncio = Anuncio.objects.create(
            clinica=self.clinica, nombre="Reaccionas y luego te arrepientes",
            plataforma=Anuncio.Plataforma.INSTAGRAM, sede=Anuncio.Sede.PIURA,
        )
        self.hoy = timezone.localdate()

    def _lead(self, nombre, telefono, estado, anuncio=None, es_pauta=False, fuente=Lead.Fuente.WHATSAPP):
        return Lead.objects.create(
            clinica=self.clinica, nombre=nombre, telefono=telefono, sede=Lead.Sede.PIURA,
            fuente=fuente, es_pauta=es_pauta, anuncio=anuncio,
            estado=estado, fecha_consulta=self.hoy,
        )

    def _reporte(self):
        return generar_reporte_pauta(self.clinica, Lead.Sede.PIURA, self.hoy, self.hoy)["datos"]

    def test_el_anuncio_no_se_pierde_cuando_la_persona_avanza_de_etapa(self):
        """Dos filas de la misma persona: la vieja trae el anuncio, la nueva no."""
        self._lead("Ana Pérez", "987654321", Lead.Estado.AGENDADO, anuncio=self.anuncio, es_pauta=True)
        self._lead("Ana Pérez", "987654321", Lead.Estado.GANADO)  # fila de avance, sin anuncio
        datos = self._reporte()
        self.assertEqual(datos["total_consultas"], 1)          # una persona, no dos
        self.assertEqual(datos["consultas_por_publicidad"], 1)  # y sabemos de qué anuncio vino
        self.assertEqual(datos["anuncios"][0]["nombre"], "Reaccionas y luego te arrepientes")

    def test_cuenta_el_anuncio_aunque_el_origen_no_sea_de_pauta(self):
        """La pauta de Meta manda a WhatsApp: el lead se registra como 'WhatsApp
        directo' pero eligieron el anuncio. Ese anuncio tiene que contar."""
        self._lead("Luis Gómez", "912345678", Lead.Estado.AGENDADO, anuncio=self.anuncio, es_pauta=False)
        datos = self._reporte()
        self.assertEqual(datos["consultas_por_publicidad"], 1)
        self.assertEqual(datos["anuncios"][0]["n"], 1)

    def test_las_cinco_consultas_reportan_su_anuncio(self):
        """El caso tal cual lo describió marketing: cinco consultas del anuncio,
        cada una con su fila de avance encima. Antes se reportaba una."""
        for i in range(5):
            tel = f"98700000{i}"
            self._lead(f"Paciente {i}", tel, Lead.Estado.AGENDADO, anuncio=self.anuncio, es_pauta=True)
            self._lead(f"Paciente {i}", tel, Lead.Estado.GANADO)
        datos = self._reporte()
        self.assertEqual(datos["total_consultas"], 5)
        self.assertEqual(datos["consultas_por_publicidad"], 5)
        self.assertEqual(datos["anuncios"][0]["n"], 5)

    def test_una_consulta_sin_anuncio_no_inventa_pauta(self):
        self._lead("Sin anuncio", "900000000", Lead.Estado.AGENDADO)
        datos = self._reporte()
        self.assertEqual(datos["total_consultas"], 1)
        self.assertEqual(datos["consultas_por_publicidad"], 0)


class LeadCreaLaCitaTests(TestCase):
    """Registrar la consulta en Marketing tiene que dejarla en la Agenda.

    Reportado: "cuando la coordinadora registra en marketing el lead, en agenda no
    lo registra y la coordi tiene que hacer un doble registro". Ese doble registro
    era además el origen de los pacientes repetidos que descuadraban el conteo.
    """

    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-l2c")
        self.coord = Usuario.objects.create_user(
            email="coord3@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ASISTENTE,
        )
        self.psico = Usuario.objects.create_user(
            email="p3@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.MEDICO,
        )
        self.manana = timezone.localdate() + timedelta(days=1)
        self.client.force_login(self.coord)

    def _crear_lead(self, **extra):
        datos = {
            "nombre": "Ana Pérez", "telefono": "987654321", "sede": "piura",
            "fuente": "whatsapp", "estado": "agendado",
            "agendo_consulta": True,
            "fecha_consulta": self.manana.isoformat(), "hora_consulta": "10:00",
            "medico": self.psico.id, "especialidad": "Terapia individual",
            **extra,
        }
        return self.client.post("/api/leads/", datos, content_type="application/json")

    def test_registrar_el_lead_deja_la_cita_en_la_agenda(self):
        r = self._crear_lead()
        self.assertEqual(r.status_code, 201)
        cita = Cita.objects.get()
        self.assertEqual(cita.paciente.nombre, "Ana Pérez")
        self.assertEqual(cita.medico, self.psico)
        self.assertEqual(timezone.localtime(cita.inicio).hour, 10)
        self.assertEqual(Lead.objects.get().cita_id, cita.id)

    def test_no_duplica_al_paciente_que_ya_existe(self):
        """El mismo teléfono, aunque esté escrito distinto, es la misma persona."""
        ya = Paciente.objects.create(clinica=self.clinica, nombre="Ana P.", telefono="+51 987 654 321")
        self._crear_lead()
        self.assertEqual(Paciente.objects.count(), 1)
        self.assertEqual(Cita.objects.get().paciente_id, ya.id)

    def test_sin_consulta_agendada_no_crea_nada(self):
        r = self._crear_lead(agendo_consulta=False, fecha_consulta=None, hora_consulta=None)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Cita.objects.count(), 0)
        self.assertEqual(Paciente.objects.count(), 0)

    def test_sin_hora_no_crea_la_cita(self):
        """Falta el dato para ponerla en la agenda: no se inventa una hora."""
        self._crear_lead(hora_consulta=None)
        self.assertEqual(Cita.objects.count(), 0)

    def test_corregir_la_fecha_mueve_la_cita_en_vez_de_duplicarla(self):
        self._crear_lead()
        lead = Lead.objects.get()
        nueva = self.manana + timedelta(days=2)
        r = self.client.patch(f"/api/leads/{lead.id}/",
                              {"fecha_consulta": nueva.isoformat(), "hora_consulta": "16:00"},
                              content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Cita.objects.count(), 1)  # se movió, no se duplicó
        cita = Cita.objects.get()
        self.assertEqual(timezone.localtime(cita.inicio).date(), nueva)
        self.assertEqual(timezone.localtime(cita.inicio).hour, 16)

    def test_avisa_si_el_horario_ya_estaba_ocupado(self):
        otro = Paciente.objects.create(clinica=self.clinica, nombre="Luis Gómez")
        Cita.objects.create(
            clinica=self.clinica, paciente=otro, medico=self.psico,
            inicio=timezone.make_aware(datetime.combine(self.manana, dtime(10, 0))),
            estado=Cita.Estado.AGENDADA, especialidad="Terapia individual",
        )
        r = self._crear_lead()
        self.assertEqual(r.status_code, 201)
        self.assertIn("Luis Gómez", r.json()["aviso"])  # se registra igual, pero avisa

    def test_agendar_la_consulta_no_marca_el_lead_como_cerrado(self):
        """Agendar no es iniciar proceso: el embudo no se debe inflar solo."""
        self._crear_lead()
        self.assertEqual(Lead.objects.get().estado, Lead.Estado.AGENDADO)


class AgendarNoEsSerPacienteTests(TestCase):
    """Agendar la consulta abría la ficha y la persona salía como paciente.

    Reportado por las dos sedes: leads en "Perdido" mostraban igual la etiqueta
    verde "Ya es paciente", y nadie podía quitarla. La ficha se crea igual —la
    cita tiene que colgar de alguien— pero nace `provisional`: paciente es quien
    inicia proceso, no quien reserva la primera consulta.
    """

    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-prov")
        self.coord = Usuario.objects.create_user(
            email="coord4@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ASISTENTE,
        )
        self.psico = Usuario.objects.create_user(
            email="p4@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.MEDICO,
        )
        self.manana = timezone.localdate() + timedelta(days=1)
        self.client.force_login(self.coord)

    def _agendar(self, **extra):
        datos = {
            "nombre": "Sebastián Gamboa", "telefono": "987654321", "sede": "piura",
            "fuente": "whatsapp", "estado": "agendado", "agendo_consulta": True,
            "fecha_consulta": self.manana.isoformat(), "hora_consulta": "10:00",
            "medico": self.psico.id, "especialidad": "Terapia individual",
            **extra,
        }
        r = self.client.post("/api/leads/", datos, content_type="application/json")
        self.assertEqual(r.status_code, 201)
        return Lead.objects.get()

    def test_la_ficha_que_deja_la_consulta_nace_provisional(self):
        lead = self._agendar()
        self.assertIsNotNone(lead.paciente_id)          # la cita necesita la ficha
        self.assertTrue(lead.paciente.provisional)      # pero no es paciente aún

    def test_el_lead_perdido_no_queda_contado_como_paciente(self):
        """El caso de la captura: agendó, no vino, lo pasan a Perdido."""
        lead = self._agendar()
        r = self.client.patch(f"/api/leads/{lead.id}/", {"estado": "perdido"},
                              content_type="application/json")
        self.assertEqual(r.status_code, 200)
        lead.refresh_from_db()
        self.assertEqual(lead.estado, Lead.Estado.PERDIDO)
        self.assertTrue(lead.paciente.provisional)
        self.assertEqual(Paciente.objects.filter(provisional=False).count(), 0)

    def test_iniciar_proceso_asciende_la_ficha(self):
        lead = self._agendar()
        r = self.client.patch(f"/api/leads/{lead.id}/", {"estado": "ganado"},
                              content_type="application/json")
        self.assertEqual(r.status_code, 200)
        lead.refresh_from_db()
        lead.paciente.refresh_from_db()
        self.assertFalse(lead.paciente.provisional)
        self.assertEqual(Paciente.objects.filter(provisional=False).count(), 1)

    def test_el_boton_convertir_no_se_bloquea_por_la_ficha_provisional(self):
        """Antes devolvía "ya es paciente" y no hacía nada: el lead se quedaba
        agendado para siempre y sin forma de cerrarlo desde la lista."""
        lead = self._agendar()
        r = self.client.post(f"/api/leads/{lead.id}/convertir/", content_type="application/json")
        self.assertEqual(r.status_code, 201)
        lead.refresh_from_db()
        lead.paciente.refresh_from_db()
        self.assertEqual(lead.estado, Lead.Estado.GANADO)
        self.assertFalse(lead.paciente.provisional)
        self.assertEqual(Paciente.objects.count(), 1)   # no creó una segunda ficha

    def test_la_fila_que_entra_ya_como_proceso_es_paciente_de_una(self):
        """El avance de etapa se registra como fila NUEVA, no editando la anterior."""
        lead = self._agendar(estado="ganado")
        self.assertFalse(lead.paciente.provisional)


class ServicioDeLaConsultaTests(TestCase):
    """La cita que nace de un lead es una CONSULTA, no una sesión de terapia.

    Reportado por Gaby: "se automatiza ya, pero como sesión, y es consulta".
    No es cosmético: la liquidación se calcula por el NOMBRE del servicio, y la
    consulta inicial y la sesión individual no se pagan igual.
    """

    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-serv")
        self.coord = Usuario.objects.create_user(
            email="coord4@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ASISTENTE,
        )
        self.psico = Usuario.objects.create_user(
            email="p4@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.MEDICO,
        )
        self.manana = timezone.localdate() + timedelta(days=1)
        self.client.force_login(self.coord)

    def _servicio(self, nombre, terapeuta):
        return Servicio.objects.create(
            clinica=self.clinica, nombre=nombre, precio=Decimal("100"),
            monto_terapeuta=Decimal(terapeuta),
        )

    def _crear_lead(self, **extra):
        datos = {
            "nombre": "Ayvi Torres", "telefono": "987000111", "sede": "piura",
            "fuente": "whatsapp", "estado": "agendado", "agendo_consulta": True,
            "fecha_consulta": self.manana.isoformat(), "hora_consulta": "16:00",
            "medico": self.psico.id, "especialidad": "Terapia individual",
            **extra,
        }
        return self.client.post("/api/leads/", datos, content_type="application/json")

    def test_la_cita_entra_como_consulta_no_como_terapia(self):
        self._servicio("Consulta inicial adultos", 20)
        self._servicio("Terapia individual", 38)
        self._crear_lead()
        self.assertEqual(Cita.objects.get().especialidad, "Consulta inicial adultos")

    def test_elige_la_consulta_que_calza_con_el_tipo_de_servicio(self):
        self._servicio("Consulta inicial adultos", 20)
        self._servicio("Consulta inicial niños", 20)
        self._crear_lead(tipo_servicio="ninos")
        self.assertEqual(Cita.objects.get().especialidad, "Consulta inicial niños")

    def test_sin_consultas_en_el_catalogo_usa_lo_que_traiga_el_lead(self):
        self._servicio("Terapia individual", 38)
        self._crear_lead()
        self.assertEqual(Cita.objects.get().especialidad, "Terapia individual")

    def test_la_categoria_sale_del_tipo_de_servicio(self):
        self._servicio("Consulta inicial", 20)
        self._crear_lead(tipo_servicio="adolescentes")
        self.assertEqual(Cita.objects.get().categoria, Cita.Categoria.INFANTOJUVENIL)


class SinDobleTareaTests(TestCase):
    """Lo que se llena en Marketing no se vuelve a escribir en la Agenda.

    Pedido: "asegúrate que los campos funcionen bien para que las coordinadoras no
    hagan doble tarea". El hueco que quedaba era la modalidad: la cita nacía
    siempre presencial, así que una consulta virtual obligaba a ir a la agenda a
    cambiarla y a pegar el enlace otra vez.
    """

    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-sdt")
        self.coord = Usuario.objects.create_user(
            email="coord5@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ASISTENTE,
        )
        self.psico = Usuario.objects.create_user(
            email="p5@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.MEDICO,
        )
        self.manana = timezone.localdate() + timedelta(days=1)
        self.client.force_login(self.coord)

    def _crear_lead(self, **extra):
        datos = {
            "nombre": "Ana Pérez", "telefono": "987654321", "sede": "piura",
            "fuente": "whatsapp", "estado": "agendado", "agendo_consulta": True,
            "fecha_consulta": self.manana.isoformat(), "hora_consulta": "10:00",
            "medico": self.psico.id, **extra,
        }
        return self.client.post("/api/leads/", datos, content_type="application/json")

    def test_la_consulta_virtual_llega_a_la_agenda_con_su_enlace(self):
        self._crear_lead(modalidad_consulta="virtual", enlace_consulta="meet.google.com/abc-defg-hij")
        cita = Cita.objects.get()
        self.assertEqual(cita.modalidad, Cita.Modalidad.VIRTUAL)
        self.assertEqual(cita.enlace, "https://meet.google.com/abc-defg-hij")  # ya usable

    def test_la_presencial_no_arrastra_enlace(self):
        self._crear_lead(modalidad_consulta="presencial", enlace_consulta="meet.google.com/abc")
        cita = Cita.objects.get()
        self.assertEqual(cita.modalidad, Cita.Modalidad.PRESENCIAL)
        self.assertEqual(cita.enlace, "")

    def test_cambiar_la_modalidad_en_marketing_actualiza_la_cita(self):
        self._crear_lead()
        lead = Lead.objects.get()
        self.client.patch(f"/api/leads/{lead.id}/",
                          {"modalidad_consulta": "virtual", "enlace_consulta": "meet.google.com/xyz"},
                          content_type="application/json")
        cita = Cita.objects.get()
        self.assertEqual(cita.modalidad, Cita.Modalidad.VIRTUAL)
        self.assertEqual(cita.enlace, "https://meet.google.com/xyz")

    def test_el_lead_completa_los_datos_que_le_faltan_a_la_ficha(self):
        """Sin pisar lo que ya estaba cargado en el paciente."""
        p = Paciente.objects.create(clinica=self.clinica, nombre="Ana Pérez",
                                    telefono="987654321", direccion="Av. Grau 123")
        self._crear_lead(email="ana@correo.pe", ubicacion="Castilla")
        p.refresh_from_db()
        self.assertEqual(p.email, "ana@correo.pe")     # lo tomó del lead
        self.assertEqual(p.direccion, "Av. Grau 123")  # y NO pisó lo que ya tenía


class SedeDeLaCitaTests(TestCase):
    """La sesión cuenta en la sede de quien atiende, no en la del paciente.

    Decisión del equipo: "si la psicóloga es de Piura, entonces va a Piura". En
    las consultas virtuales una coordinadora de Lima le agenda a una psicóloga de
    Piura, y esa hora la trabaja Piura. La captación sigue midiendo por el lead.
    """

    def setUp(self):
        from usuarios.models import Profesional
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-sede")
        self.coord = Usuario.objects.create_user(
            email="coordsede@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.ASISTENTE,
        )
        self.psico_piura = Usuario.objects.create_user(
            email="angi@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.MEDICO,
        )
        Profesional.objects.create(
            clinica=self.clinica, nombre="Angi Requena", usuario=self.psico_piura, sede="piura",
        )
        self.manana = timezone.localdate() + timedelta(days=1)
        self.client.force_login(self.coord)

    def _lead_de_lima(self, **extra):
        datos = {
            "nombre": "Paciente de Lima", "telefono": "987222333", "sede": "lima",
            "fuente": "whatsapp", "estado": "agendado", "agendo_consulta": True,
            "fecha_consulta": self.manana.isoformat(), "hora_consulta": "11:00",
            "medico": self.psico_piura.id, **extra,
        }
        return self.client.post("/api/leads/", datos, content_type="application/json")

    def test_la_cita_va_a_la_sede_de_la_psicologa(self):
        self._lead_de_lima(modalidad_consulta="virtual")
        self.assertEqual(Cita.objects.get().sede, "piura")   # la atiende Piura

    def test_el_lead_sigue_siendo_de_su_ciudad(self):
        """La captación mide de dónde llega la gente: eso no cambia."""
        self._lead_de_lima(modalidad_consulta="virtual")
        self.assertEqual(Lead.objects.get().sede, "lima")

    def test_sin_ficha_de_directorio_usa_la_sede_del_lead(self):
        suelto = Usuario.objects.create_user(
            email="sinficha@test.pe", password="x", clinica=self.clinica, rol=Usuario.Rol.MEDICO,
        )
        self._lead_de_lima(medico=suelto.id)
        self.assertEqual(Cita.objects.get().sede, "lima")


class ReporteCuadraConElConteoManualTests(TestCase):
    """Que el reporte diga lo mismo que sale de contar lead por lead.

    Lo reportó Gaby: pones un rango, el reporte arroja sus números, pero si
    cuentas a mano en el tablero (cuántos pasaron consulta, cuántos iniciaron
    proceso, de qué canal vino cada uno) no coincide.

    La causa: el equipo registra el avance como una fila NUEVA, y esa fila no
    siempre repite la fecha de la consulta. El reporte clasificaba mirando la
    fila que tenía esa fecha, así que el mismo recorrido daba números distintos
    según cómo se hubiera tipeado el avance.
    """

    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-cuadre")
        self.desde, self.hasta = date(2026, 8, 1), date(2026, 8, 31)

    def _fila(self, nombre, telefono, estado, fecha_consulta=None, fecha_cierre=None,
              dia=5, fuente=Lead.Fuente.WHATSAPP):
        l = Lead.objects.create(
            clinica=self.clinica, nombre=nombre, telefono=telefono, sede=Lead.Sede.PIURA,
            fuente=fuente, estado=estado, fecha_consulta=fecha_consulta, fecha_cierre=fecha_cierre,
        )
        Lead.objects.filter(pk=l.pk).update(
            creado_en=timezone.make_aware(datetime(2026, 8, dia, 10, 0)))
        return l

    def _datos(self, sede=Lead.Sede.PIURA):
        return generar_reporte_pauta(self.clinica, sede, self.desde, self.hasta)["datos"]

    def test_el_avance_en_fila_nueva_no_descuadra_el_estado(self):
        """Consulta el 5, inicia proceso el 20 en otra fila que ya no repite la
        fecha de consulta. Es UNA persona que inició proceso."""
        self._fila("Ana Perez", "987111222", Lead.Estado.CONSULTA_REALIZADA,
                   fecha_consulta=date(2026, 8, 5), dia=5)
        self._fila("Ana Perez", "987111222", Lead.Estado.GANADO,
                   fecha_cierre=date(2026, 8, 20), dia=20)
        d = self._datos()
        self.assertEqual(d["total_consultas"], 1)
        self.assertEqual(d["proceso"], 1)
        self.assertEqual(d["consulta_realizada"], 0)

    def test_el_proceso_cuenta_como_del_periodo_aunque_la_fecha_este_en_otra_fila(self):
        """La sección de procesos decía '0 de consultas del período' y mandaba a
        la persona a 'períodos anteriores', aunque su consulta fue este mes."""
        self._fila("Ana Perez", "987111222", Lead.Estado.CONSULTA_REALIZADA,
                   fecha_consulta=date(2026, 8, 5), dia=5)
        self._fila("Ana Perez", "987111222", Lead.Estado.GANADO,
                   fecha_cierre=date(2026, 8, 20), dia=20)
        d = self._datos()
        self.assertEqual(d["procesos_total"], 1)
        self.assertEqual(d["procesos_mes"], 1)
        self.assertEqual(d["procesos_prev"], 0)

    def test_da_igual_si_la_fila_del_avance_repite_la_fecha(self):
        """El número no puede depender de cómo lo tipeó quien registró."""
        self._fila("Ana Perez", "987111222", Lead.Estado.CONSULTA_REALIZADA,
                   fecha_consulta=date(2026, 8, 5), dia=5)
        self._fila("Ana Perez", "987111222", Lead.Estado.GANADO,
                   fecha_cierre=date(2026, 8, 20), dia=20)
        sin_repetir = self._datos()

        Lead.objects.all().delete()
        self._fila("Ana Perez", "987111222", Lead.Estado.CONSULTA_REALIZADA,
                   fecha_consulta=date(2026, 8, 5), dia=5)
        self._fila("Ana Perez", "987111222", Lead.Estado.GANADO,
                   fecha_consulta=date(2026, 8, 5), fecha_cierre=date(2026, 8, 20), dia=20)
        repitiendo = self._datos()

        for k in ("total_consultas", "proceso", "consulta_realizada",
                  "procesos_total", "procesos_mes", "procesos_prev"):
            self.assertEqual(sin_repetir[k], repitiendo[k], f"'{k}' cambia según el tipeo")

    def test_lista_una_por_una_las_consultas_del_periodo(self):
        self._fila("Ana Perez", "987111222", Lead.Estado.GANADO,
                   fecha_consulta=date(2026, 8, 5), fecha_cierre=date(2026, 8, 20), dia=5)
        self._fila("Luis Gomez Rios", "987333444", Lead.Estado.AGENDADO,
                   fecha_consulta=date(2026, 8, 9), dia=9, fuente=Lead.Fuente.INSTAGRAM)
        d = self._datos()
        self.assertEqual(len(d["consultas_detalle"]), d["total_consultas"])
        detalle = {x["nombre"]: x for x in d["consultas_detalle"]}
        self.assertIn("Ana P.", detalle)          # sin apellidos completos
        self.assertIn("Luis G.", detalle)
        self.assertEqual(detalle["Ana P."]["estado"], "Inició proceso")
        self.assertEqual(detalle["Luis G."]["origen"], "Instagram")

    def test_el_detalle_no_lleva_telefono_ni_apellido_completo(self):
        """El reporte se reenvía por WhatsApp: no puede pasear datos del paciente."""
        self._fila("Ana Maria Perez Loayza", "987111222", Lead.Estado.CONSULTA_REALIZADA,
                   fecha_consulta=date(2026, 8, 5), dia=5)
        texto = generar_reporte_pauta(self.clinica, Lead.Sede.PIURA, self.desde, self.hasta)["texto"]
        self.assertIn("Ana Maria P.", texto)
        self.assertNotIn("987111222", texto)
        self.assertNotIn("Loayza", texto)

    def test_sin_filtro_de_sede_cada_anuncio_dice_de_donde_vino(self):
        """Con las dos sedes juntas no se sabía qué consulta era de Piura."""
        anuncio = Anuncio.objects.create(
            clinica=self.clinica, nombre="Reel ansiedad",
            plataforma=Anuncio.Plataforma.INSTAGRAM, sede=Anuncio.Sede.PIURA,
        )
        for nombre, tel, sede in [("Ana Perez", "987111222", Lead.Sede.PIURA),
                                  ("Luis Gomez", "987333444", Lead.Sede.LIMA)]:
            l = Lead.objects.create(
                clinica=self.clinica, nombre=nombre, telefono=tel, sede=sede,
                fuente=Lead.Fuente.WHATSAPP, es_pauta=True, anuncio=anuncio,
                estado=Lead.Estado.CONSULTA_REALIZADA, fecha_consulta=date(2026, 8, 5),
            )
            Lead.objects.filter(pk=l.pk).update(
                creado_en=timezone.make_aware(datetime(2026, 8, 5, 10, 0)))
        d = self._datos(sede="")
        porsede = {x["sede"]: x["n"] for x in d["anuncios"][0]["por_sede"]}
        self.assertEqual(porsede.get("Piura"), 1)
        self.assertEqual(porsede.get("Lima"), 1)

    def test_muestra_las_dos_fechas_cuando_la_consulta_y_el_proceso_cruzan_de_mes(self):
        """Lo que pidió Mirai: "consultó el 18/7 e inició proceso el 20/8", para
        que se entienda desde los dos lados sin cruzar reportes."""
        # Consultó en julio (fuera del período) e inició proceso en agosto.
        l = Lead.objects.create(
            clinica=self.clinica, nombre="Rosa Diaz Vega", telefono="987555666",
            sede=Lead.Sede.PIURA, fuente=Lead.Fuente.WHATSAPP, estado=Lead.Estado.GANADO,
            fecha_consulta=date(2026, 7, 18), fecha_cierre=date(2026, 8, 20),
        )
        Lead.objects.filter(pk=l.pk).update(
            creado_en=timezone.make_aware(datetime(2026, 7, 18, 10, 0)))
        r = generar_reporte_pauta(self.clinica, Lead.Sede.PIURA, self.desde, self.hasta)

        # Cuenta como proceso del período, pero marcado como consulta de antes.
        self.assertEqual(r["datos"]["procesos_total"], 1)
        self.assertEqual(r["datos"]["procesos_prev"], 1)
        det = r["datos"]["procesos_detalle"][0]
        self.assertEqual(det["fecha_consulta"], "2026-07-18")
        self.assertEqual(det["fecha_proceso"], "2026-08-20")
        self.assertTrue(det["consulta_de_otro_periodo"])
        # Y las dos fechas se leen en el texto que se reenvía.
        self.assertIn("consulta 18/07", r["texto"])
        self.assertIn("inició proceso 20/08", r["texto"])

    def test_el_listado_de_consultas_dice_cuando_inicio_proceso(self):
        self._fila("Ana Perez", "987111222", Lead.Estado.CONSULTA_REALIZADA,
                   fecha_consulta=date(2026, 8, 5), dia=5)
        self._fila("Ana Perez", "987111222", Lead.Estado.GANADO,
                   fecha_cierre=date(2026, 8, 20), dia=20)
        texto = generar_reporte_pauta(self.clinica, Lead.Sede.PIURA, self.desde, self.hasta)["texto"]
        self.assertIn("consulta 05/08", texto)
        self.assertIn("Inició proceso el 20/08", texto)

    def test_los_anuncios_sin_consultas_tambien_salen(self):
        """Lo que pidió Mirai: que salgan TODOS los links, no solo los dos que
        trajeron consulta. Un anuncio que no trajo a nadie es un resultado."""
        trajo = Anuncio.objects.create(
            clinica=self.clinica, nombre="Consulta 50 soles", link="https://instagram.com/reel/abc",
            plataforma=Anuncio.Plataforma.INSTAGRAM, sede=Anuncio.Sede.PIURA)
        Anuncio.objects.create(
            clinica=self.clinica, nombre="No todo es rebeldia", link="https://fb.me/xyz",
            plataforma=Anuncio.Plataforma.FACEBOOK, sede=Anuncio.Sede.PIURA)
        Anuncio.objects.create(
            clinica=self.clinica, nombre="Anuncio apagado", link="https://fb.me/off",
            plataforma=Anuncio.Plataforma.FACEBOOK, sede=Anuncio.Sede.PIURA, activo=False)
        l = Lead.objects.create(
            clinica=self.clinica, nombre="Ana Perez", telefono="987111222", sede=Lead.Sede.PIURA,
            fuente=Lead.Fuente.WHATSAPP, es_pauta=True, anuncio=trajo,
            estado=Lead.Estado.CONSULTA_REALIZADA, fecha_consulta=date(2026, 8, 5))
        Lead.objects.filter(pk=l.pk).update(
            creado_en=timezone.make_aware(datetime(2026, 8, 5, 10, 0)))

        r = generar_reporte_pauta(self.clinica, Lead.Sede.PIURA, self.desde, self.hasta)
        nombres = {a["nombre"]: a for a in r["datos"]["anuncios"]}
        self.assertEqual(nombres["Consulta 50 soles"]["n"], 1)
        self.assertEqual(nombres["No todo es rebeldia"]["n"], 0)   # aparece con 0
        self.assertNotIn("Anuncio apagado", nombres)               # inactivo, no
        self.assertIn("https://fb.me/xyz", r["texto"])
        self.assertIn("Sin consultas en el período", r["texto"])

    def test_distingue_el_anuncio_que_trae_gente_del_que_no_trae_a_nadie(self):
        """Dos anuncios con 0 consultas no son iguales: uno trajo 3 leads que no
        agendaron, el otro no trajo a nadie."""
        con_leads = Anuncio.objects.create(
            clinica=self.clinica, nombre="Trae gente", link="https://fb.me/1",
            plataforma=Anuncio.Plataforma.FACEBOOK, sede=Anuncio.Sede.PIURA)
        Anuncio.objects.create(
            clinica=self.clinica, nombre="No trae nada", link="https://fb.me/2",
            plataforma=Anuncio.Plataforma.FACEBOOK, sede=Anuncio.Sede.PIURA)
        for i in range(3):
            l = Lead.objects.create(
                clinica=self.clinica, nombre=f"Lead {i}", telefono=f"98700000{i}",
                sede=Lead.Sede.PIURA, fuente=Lead.Fuente.WHATSAPP, es_pauta=True,
                anuncio=con_leads, estado=Lead.Estado.CONTACTADO)
            Lead.objects.filter(pk=l.pk).update(
                creado_en=timezone.make_aware(datetime(2026, 8, 3, 10, 0)))
        d = {a["nombre"]: a for a in self._datos()["anuncios"]}
        self.assertEqual((d["Trae gente"]["n"], d["Trae gente"]["leads"]), (0, 3))
        self.assertEqual((d["No trae nada"]["n"], d["No trae nada"]["leads"]), (0, 0))

    def test_el_anuncio_de_ambas_sedes_sale_en_el_reporte_de_cada_una(self):
        Anuncio.objects.create(
            clinica=self.clinica, nombre="Campana nacional", link="https://fb.me/nac",
            plataforma=Anuncio.Plataforma.FACEBOOK, sede=Anuncio.Sede.AMBAS)
        for sede in (Lead.Sede.PIURA, Lead.Sede.LIMA):
            nombres = [a["nombre"] for a in self._datos(sede=sede)["anuncios"]]
            self.assertIn("Campana nacional", nombres, f"falta en {sede}")
