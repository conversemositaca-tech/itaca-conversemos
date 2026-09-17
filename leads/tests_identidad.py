"""El teléfono no identifica a una persona.

Reportado por Coordinación Lima: una consulta nueva terminó agendada bajo otra
paciente y apareció en SU historial. La causa era la regla anterior —"mismo
teléfono, misma persona"— aplicada sobre una realidad donde el número suele ser
de quien gestiona la atención: la madre, el padre, un hermano mayor, un familiar
que lleva a varios.

En la base de esta clínica hay 140 números compartidos por 307 fichas. Con la
regla vieja, cualquier lead nuevo con uno de esos números se colgaba de la
primera ficha por orden alfabético.

Lo que se sostiene aquí:

- Un menor puede existir sin teléfono propio.
- El número del padre, de la madre o del tutor es un CANAL, nunca una identidad.
- Ante la duda se separa: una ficha repetida se corrige; dos historias clínicas
  mezcladas, no.

    python manage.py test leads.tests_identidad
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.models import Clinica
from leads.models import Lead
from pacientes.models import Cita, Paciente
from usuarios.models import Usuario


class _Base(TestCase):
    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-ident")
        self.coord = Usuario.objects.create_user(
            email="coord-ident@test.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.ASISTENTE)
        self.psico = Usuario.objects.create_user(
            email="psico-ident@test.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.MEDICO)
        self.manana = timezone.localdate() + timedelta(days=1)
        self.client.force_login(self.coord)

    def crear_lead(self, **extra):
        datos = {
            "nombre": "Mateo Pérez", "telefono": "987654321", "sede": "piura",
            "fuente": "whatsapp", "estado": "agendado", "agendo_consulta": True,
            "fecha_consulta": self.manana.isoformat(), "hora_consulta": "10:00",
            "medico": self.psico.id, "especialidad": "Terapia individual",
            **extra,
        }
        return self.client.post("/api/leads/", datos, content_type="application/json")

    def paciente(self, nombre, telefono="", sede="piura", **extra):
        return Paciente.objects.create(clinica=self.clinica, nombre=nombre,
                                       telefono=telefono, sede=sede, **extra)


class IdentidadDelPacienteTests(_Base):
    """Quién es el paciente no lo decide el número de teléfono."""

    def test_1_menor_sin_telefono_se_registra(self):
        r = self.crear_lead(telefono="", contacto_nombre="Rosa Pérez",
                            contacto_parentesco="madre", contacto_telefono="987654321",
                            tipo_servicio="ninos")
        self.assertEqual(r.status_code, 201)
        p = Paciente.objects.get()
        self.assertEqual(p.nombre, "Mateo Pérez")
        self.assertEqual(p.telefono, "")

    def test_2_el_telefono_del_tutor_no_se_copia_al_menor(self):
        self.crear_lead(telefono="", contacto_nombre="Rosa Pérez",
                        contacto_parentesco="madre", contacto_telefono="987654321")
        p = Paciente.objects.get()
        self.assertEqual(p.telefono, "")
        self.assertEqual(p.tutor_telefono, "987654321")
        self.assertEqual(p.tutor_nombre, "Rosa Pérez")
        self.assertEqual(p.tutor_parentesco, "madre")

    def test_2b_un_contacto_no_convierte_al_tutor_en_paciente(self):
        """La madre no pasa a ser la paciente por ser quien escribe."""
        self.crear_lead(contacto_nombre="Rosa Pérez", contacto_telefono="987654321")
        self.assertEqual(Paciente.objects.count(), 1)
        self.assertEqual(Paciente.objects.get().nombre, "Mateo Pérez")

    def test_3_madre_e_hijo_con_el_mismo_telefono_son_fichas_distintas(self):
        madre = self.paciente("Rosa Pérez", telefono="987654321")
        self.crear_lead()                       # Mateo, mismo número
        self.assertEqual(Paciente.objects.count(), 2)
        self.assertNotEqual(Cita.objects.get().paciente_id, madre.id)

    def test_4_dos_hermanos_con_el_mismo_telefono_son_fichas_distintas(self):
        hermana = self.paciente("Lucía Pérez", telefono="987654321")
        self.crear_lead()                       # Mateo, mismo número
        self.assertEqual(Paciente.objects.count(), 2)
        self.assertEqual(hermana.citas.count(), 0)

    def test_5_el_telefono_de_otro_paciente_no_cruza_su_historial(self):
        otra = self.paciente("Carla Ramírez", telefono="987654321")
        Cita.objects.create(clinica=self.clinica, paciente=otra, medico=self.psico,
                            inicio=timezone.now() - timedelta(days=7),
                            estado=Cita.Estado.ATENDIDA, n_sesion=1)
        self.crear_lead()
        self.assertEqual(otra.citas.count(), 1)          # la suya y solo la suya
        nuevo = Paciente.objects.exclude(pk=otra.pk).get()
        self.assertEqual(nuevo.citas.count(), 1)

    def test_6_mismo_telefono_y_nombre_distinto_crea_paciente_nuevo(self):
        self.paciente("Rosa Pérez", telefono="987654321")
        self.crear_lead()
        self.assertEqual(
            sorted(Paciente.objects.values_list("nombre", flat=True)),
            ["Mateo Pérez", "Rosa Pérez"])

    def test_7_con_dos_fichas_del_mismo_numero_no_se_elige_ninguna(self):
        """Ni la primera, ni la alfabética: ante la ambigüedad no se decide sola."""
        a = self.paciente("Mateo Pérez", telefono="987654321")
        b = self.paciente("Mateo Pérez", telefono="+51 987 654 321")
        self.crear_lead()
        cita = Cita.objects.get()
        self.assertNotIn(cita.paciente_id, (a.id, b.id))
        self.assertEqual(Paciente.objects.count(), 3)

    def test_8_la_misma_persona_no_se_duplica(self):
        ya = self.paciente("MATEO  PÉREZ", telefono="+51 987 654 321")
        self.crear_lead()
        self.assertEqual(Paciente.objects.count(), 1)
        self.assertEqual(Cita.objects.get().paciente_id, ya.id)

    def test_9_repetir_el_alta_es_idempotente(self):
        self.crear_lead()
        lead = Lead.objects.get()
        primera = lead.paciente_id
        # El mismo lead se vuelve a guardar (Coordinación corrige un dato).
        self.client.patch(f"/api/leads/{lead.id}/", {"observaciones": "llamó de nuevo"},
                          content_type="application/json")
        lead.refresh_from_db()
        self.assertEqual(lead.paciente_id, primera)
        self.assertEqual(Paciente.objects.count(), 1)

    def test_9b_un_lead_ya_enlazado_manda_sobre_cualquier_coincidencia(self):
        elegido = self.paciente("Otro Nombre", telefono="900000000")
        otro_con_el_numero = self.paciente("Mateo Pérez", telefono="987654321")
        self.crear_lead()
        lead = Lead.objects.get()
        lead.paciente = elegido
        lead.save(update_fields=["paciente"])
        lead.estado = Lead.Estado.GANADO
        lead.save(update_fields=["estado"])
        self.client.patch(f"/api/leads/{lead.id}/", {"estado": "ganado"},
                          content_type="application/json")
        lead.refresh_from_db()
        self.assertEqual(lead.paciente_id, elegido.id)
        self.assertNotEqual(lead.paciente_id, otro_con_el_numero.id)

    def test_10_no_se_fusiona_entre_sedes(self):
        limena = self.paciente("Mateo Pérez", telefono="987654321", sede="lima")
        self.crear_lead(sede="piura")
        self.assertEqual(Paciente.objects.count(), 2)
        self.assertEqual(limena.citas.count(), 0)

    def test_10b_una_ficha_sin_sede_no_cuenta_como_sede_distinta(self):
        """Falta el dato, no contradice: si no, se duplicaría media base vieja."""
        antigua = self.paciente("Mateo Pérez", telefono="987654321", sede="")
        self.crear_lead(sede="piura")
        self.assertEqual(Paciente.objects.count(), 1)
        self.assertEqual(Cita.objects.get().paciente_id, antigua.id)

    def test_11_la_cita_pertenece_al_paciente_del_lead(self):
        self.paciente("Rosa Pérez", telefono="987654321")
        self.crear_lead()
        cita = Cita.objects.get()
        self.assertEqual(cita.paciente.nombre, "Mateo Pérez")

    def test_12_la_agenda_muestra_el_nombre_del_paciente(self):
        self.paciente("Rosa Pérez", telefono="987654321")
        self.crear_lead()
        r = self.client.get("/api/citas/")
        self.assertEqual(r.status_code, 200)
        filas = r.json()
        filas = filas.get("results", filas) if isinstance(filas, dict) else filas
        nombres = [c.get("paciente") or "" for c in filas]
        self.assertIn("Mateo Pérez", nombres)
        self.assertNotIn("Rosa Pérez", nombres)

    def test_13_el_historial_de_una_no_recibe_citas_de_la_otra(self):
        madre = self.paciente("Rosa Pérez", telefono="987654321")
        self.crear_lead()
        hijo = Paciente.objects.exclude(pk=madre.pk).get()
        self.assertEqual(list(madre.citas.all()), [])
        self.assertEqual(hijo.citas.count(), 1)

    def test_17_un_telefono_corto_no_genera_coincidencias(self):
        """Un dato incompleto no puede servir para identificar a nadie."""
        self.paciente("Mateo Pérez", telefono="123")
        self.crear_lead(telefono="123")
        self.assertEqual(Paciente.objects.count(), 2)


class MenorConTelefonoDelTutorTests(_Base):
    """Al menor que ya tiene ficha hay que poder RECONOCERLO.

    El fix #86 sacó el número del tutor de `Paciente.telefono` para que madre e
    hijo dejaran de confundirse. Pero la búsqueda seguía mirando solo ese campo,
    así que una ficha de menor quedaba inencontrable: cada lead suyo abría una
    ficha nueva y su historia se partía. Ahora el número del tutor también sirve
    para reconocerlo — nunca para identificarlo por sí solo, porque el NOMBRE
    sigue siendo lo que decide.
    """

    def test_el_menor_que_vuelve_no_abre_otra_ficha(self):
        menor = self.paciente("Mateo Pérez", telefono="", tutor_telefono="987654321")
        self.crear_lead(telefono="", contacto_nombre="Rosa Pérez",
                        contacto_parentesco="madre", contacto_telefono="987654321")
        self.assertEqual(Paciente.objects.count(), 1)
        self.assertEqual(Paciente.objects.get().pk, menor.pk)

    def test_la_madre_sigue_siendo_otra_persona(self):
        """Lo que cerró el fix #86 no se reabre: el nombre manda."""
        self.paciente("Mateo Pérez", telefono="", tutor_telefono="987654321")
        self.crear_lead(nombre="Rosa Pérez", telefono="987654321")
        self.assertEqual(Paciente.objects.count(), 2)

    def test_un_hermano_con_el_mismo_tutor_es_otra_ficha(self):
        self.paciente("Mateo Pérez", telefono="", tutor_telefono="987654321")
        self.crear_lead(nombre="Lucía Pérez", telefono="",
                        contacto_nombre="Rosa Pérez", contacto_telefono="987654321")
        self.assertEqual(Paciente.objects.count(), 2)

    def test_reconoce_aunque_el_numero_este_en_lados_distintos(self):
        """La ficha lo tiene como propio y el lead lo trae como del tutor."""
        adulto = self.paciente("Mateo Pérez", telefono="987654321")
        self.crear_lead(telefono="", contacto_nombre="Rosa Pérez",
                        contacto_telefono="987654321")
        self.assertEqual(Paciente.objects.count(), 1)
        self.assertEqual(Paciente.objects.get().pk, adulto.pk)

    def test_con_dos_menores_del_mismo_nombre_y_tutor_no_se_elige_ninguno(self):
        self.paciente("Mateo Pérez", telefono="", tutor_telefono="987654321")
        self.paciente("Mateo Pérez", telefono="", tutor_telefono="987654321")
        self.crear_lead(telefono="", contacto_telefono="987654321",
                        contacto_nombre="Rosa Pérez")
        self.assertEqual(Paciente.objects.count(), 3)   # ante la duda, se separa

    def test_un_tutor_con_numero_corto_no_reconoce_a_nadie(self):
        self.paciente("Mateo Pérez", telefono="", tutor_telefono="12345")
        self.crear_lead(telefono="", contacto_telefono="12345",
                        contacto_nombre="Rosa Pérez")
        self.assertEqual(Paciente.objects.count(), 2)


class TelefonoRepetidoNoBloqueaTests(_Base):
    """Registrar a un hermano con el número de la madre tiene que poder hacerse."""

    def test_16_el_telefono_repetido_ya_no_devuelve_409(self):
        primera = self.crear_lead(nombre="Lucía Pérez")
        self.assertEqual(primera.status_code, 201)
        segunda = self.crear_lead(nombre="Mateo Pérez")   # mismo número, otro hermano
        self.assertEqual(segunda.status_code, 201)
        self.assertEqual(Lead.objects.count(), 2)

    def test_16b_pero_avisa_de_que_el_numero_ya_estaba(self):
        self.crear_lead(nombre="Lucía Pérez")
        segunda = self.crear_lead(nombre="Mateo Pérez")
        self.assertIn("aviso_telefono", segunda.json())
        self.assertIn("Lucía Pérez", segunda.json()["aviso_telefono"])

    def test_16c_la_misma_persona_repetida_no_genera_aviso(self):
        self.crear_lead(nombre="Mateo Pérez")
        segunda = self.crear_lead(nombre="Mateo Pérez")
        self.assertNotIn("aviso_telefono", segunda.json())


class CanalDeContactoTests(_Base):
    """El tutor es por dónde se le escribe, no quién es."""

    def test_14_un_paciente_sin_telefono_es_valido(self):
        p = self.paciente("Mateo Pérez", telefono="")
        self.assertEqual(p.canal_contacto(), ("", ""))
        self.assertFalse(p.tiene_canal)

    def test_15_el_telefono_del_tutor_es_el_canal_cuando_no_hay_otro(self):
        p = self.paciente("Mateo Pérez", telefono="", tutor_telefono="987654321",
                          tutor_nombre="Rosa Pérez", tutor_parentesco="madre")
        numero, fuente = p.canal_contacto()
        self.assertEqual(numero, "987654321")
        self.assertEqual(fuente, Paciente.FUENTE_TUTOR)
        self.assertTrue(p.tiene_canal)

    def test_15b_el_del_paciente_manda_sobre_el_del_tutor(self):
        p = self.paciente("Ana Adulta", telefono="900111222", tutor_telefono="987654321")
        self.assertEqual(p.canal_contacto(), ("900111222", Paciente.FUENTE_PACIENTE))

    def test_15c_el_tutor_nunca_es_la_identidad(self):
        """Su número es canal: no lo vuelve paciente ni cambia de quién es la ficha."""
        p = self.paciente("Mateo Pérez", telefono="", tutor_telefono="987654321",
                          tutor_nombre="Rosa Pérez")
        self.assertEqual(p.nombre, "Mateo Pérez")
        self.assertEqual(p.telefono, "")
        self.assertFalse(Paciente.objects.filter(nombre="Rosa Pérez").exists())

    def test_el_centro_de_continuidad_escribe_por_el_canal_del_tutor(self):
        from core import contacto_continuidad as cc

        p = self.paciente("Mateo Pérez", telefono="", tutor_telefono="987654321",
                          tutor_nombre="Rosa Pérez", tutor_parentesco="madre")
        canal = cc.canal_de(p)
        self.assertEqual(canal["telefono"], "987654321")
        self.assertEqual(canal["fuente_contacto"], Paciente.FUENTE_TUTOR)
        self.assertEqual(canal["tutor_nombre"], "Rosa Pérez")
        self.assertEqual(canal["tutor_parentesco"], "madre")

    def test_sin_ningun_numero_el_contacto_queda_bloqueado(self):
        from core import contacto_continuidad as cc

        p = self.paciente("Mateo Pérez", telefono="")
        with self.assertRaises(cc.ContactoBloqueado):
            cc.canal_de(p)

    def test_un_adulto_normal_sigue_funcionando_igual(self):
        from core import contacto_continuidad as cc

        p = self.paciente("Ana Adulta", telefono="900111222")
        canal = cc.canal_de(p)
        self.assertEqual(canal["telefono"], "900111222")
        self.assertEqual(canal["fuente_contacto"], Paciente.FUENTE_PACIENTE)
        self.assertEqual(canal["tutor_nombre"], "")
