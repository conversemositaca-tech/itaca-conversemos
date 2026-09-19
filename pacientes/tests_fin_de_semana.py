"""Un psicólogo puede atender sábado y domingo, y la web lo ofrece.

El motor de agenda siempre entendió los siete días (`fecha.weekday() + 1`), pero
la grilla donde gerencia marca el horario de cada profesional solo dibujaba de
lunes a sábado. El domingo era inalcanzable: no por una regla de negocio, sino
porque faltaba la columna para marcarlo.

Esto lo cubre desde el lado que importa: que un horario de fin de semana
guardado en la ficha se convierta en horas reservables en la página pública.

    python manage.py test pacientes.tests_fin_de_semana
"""
from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from core.models import Clinica
from usuarios.models import Profesional, Usuario


class FinDeSemanaTests(TestCase):
    def setUp(self):
        self.clinica = Clinica.objects.create(nombre="Conversemos", slug="conversemos-finde")
        self.token = self.clinica.asegurar_token_captacion()
        self.psico = Usuario.objects.create_user(
            email="finde@test.pe", password="x", clinica=self.clinica,
            rol=Usuario.Rol.MEDICO, nombre="Lic. Fin de Semana")

    def ficha(self, horario):
        return Profesional.objects.create(
            clinica=self.clinica, usuario=self.psico, nombre="Lic. Fin de Semana",
            sede="piura", horario_semanal=horario)

    def dias_con_slots(self, prof, dias=30):
        r = self.client.get(
            f"/api/agendamiento/{self.token}/slots/?profesional={prof.id}&dias={dias}")
        self.assertEqual(r.status_code, 200, r.content)
        return {date.fromisoformat(d["fecha"]) for d in r.json()["dias"] if d["slots"]}

    def test_el_domingo_se_puede_reservar(self):
        # 7 = domingo. Antes no había forma de marcarlo en la ficha, así que
        # ningún psicólogo podía ofrecer ese día aunque quisiera.
        prof = self.ficha({"7": [10, 11]})
        fechas = self.dias_con_slots(prof)
        self.assertTrue(fechas, "El domingo no generó ni un horario reservable.")
        # isoweekday(): 7 es domingo.
        self.assertTrue(all(f.isoweekday() == 7 for f in fechas),
                        f"Se ofrecieron días que no son domingo: {sorted(fechas)}")

    def test_el_sabado_se_puede_reservar(self):
        prof = self.ficha({"6": [9]})
        fechas = self.dias_con_slots(prof)
        self.assertTrue(fechas)
        self.assertTrue(all(f.isoweekday() == 6 for f in fechas))

    def test_quien_atiende_solo_fin_de_semana_no_aparece_entre_semana(self):
        prof = self.ficha({"6": [10], "7": [10]})
        fechas = self.dias_con_slots(prof)
        self.assertTrue(fechas)
        self.assertFalse([f for f in fechas if f.isoweekday() < 6],
                         "Apareció con horario entre semana sin tenerlo puesto.")

    def test_cada_dia_de_la_semana_es_alcanzable(self):
        # Si algún día quedara fuera del mapeo, este test lo caza: los siete
        # tienen que poder ofrecer al menos una hora en un mes.
        for dia in range(1, 8):
            with self.subTest(dia=dia):
                prof = self.ficha({str(dia): [15]})
                fechas = self.dias_con_slots(prof)
                self.assertTrue(fechas, f"El día {dia} no generó horarios.")
                self.assertTrue(all(f.isoweekday() == dia for f in fechas))
                prof.delete()

    def test_el_horario_de_fin_de_semana_se_guarda_tal_cual(self):
        # La ficha acepta el 7 sin transformarlo: el panel escribe la clave "7"
        # y el motor la lee igual.
        prof = self.ficha({"6": [9, 10], "7": [16]})
        prof.refresh_from_db()
        self.assertEqual(prof.horario_semanal, {"6": [9, 10], "7": [16]})
