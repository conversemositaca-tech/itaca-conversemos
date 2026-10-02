from django.test import SimpleTestCase

from continuidad.inferencia import (
    ABANDONO_INFERIDO, ACTIVO_CON_PROXIMA, ACTIVO_SIN_PROXIMA, NO_APLICA, desviacion_frecuencia,
    evaluar_estado_inferido, frecuencia_efectiva,
)
from continuidad.models import Estado, Frecuencia


class InferenciaTests(SimpleTestCase):
    def ev(self, **kw):
        base = dict(estado_formal=Estado.ACTIVO, tiene_proxima=False, dias_sin_sesion=10)
        base.update(kw)
        return evaluar_estado_inferido(**base)

    def test_reglas(self):
        self.assertEqual(self.ev(), ACTIVO_SIN_PROXIMA)
        self.assertEqual(self.ev(tiene_proxima=True, dias_sin_sesion=200), ACTIVO_CON_PROXIMA)
        self.assertEqual(self.ev(dias_sin_sesion=46), ABANDONO_INFERIDO)
        self.assertEqual(self.ev(dias_sin_sesion=46, dias_abandono=60), ACTIVO_SIN_PROXIMA)
        self.assertEqual(self.ev(estado_formal=Estado.SIN_REGISTRO, dias_sin_sesion=46), ABANDONO_INFERIDO)

    def test_pausa_alta_y_cierre_excluyen_la_inferencia(self):
        for e in (Estado.PAUSA, Estado.ALTA, Estado.ABANDONO, Estado.CERRADO):
            self.assertEqual(self.ev(estado_formal=e, dias_sin_sesion=400), NO_APLICA, e)
        self.assertEqual(self.ev(estado_formal=Estado.SIN_REGISTRO, dias_sin_sesion=400, evidencia_legacy=True),
                         NO_APLICA)


class FrecuenciaTests(SimpleTestCase):
    def test_intervalos(self):
        casos = [(Frecuencia.SEMANAL, None, 7), (Frecuencia.QUINCENAL, None, 14),
                 (Frecuencia.MENSUAL, None, 30), (Frecuencia.PERSONALIZADA, 21, 21)]
        for frec, intervalo, dias in casos:
            self.assertEqual(frecuencia_efectiva(frec, intervalo, "")[1:], (dias, "proceso"))

    def test_no_definida_usa_la_ficha_como_respaldo_y_lo_dice(self):
        self.assertEqual(frecuencia_efectiva(Frecuencia.NO_DEFINIDA, None, "semanal"),
                         (Frecuencia.SEMANAL, 7, "ficha_legacy"))
        self.assertEqual(frecuencia_efectiva(Frecuencia.NO_DEFINIDA, None, "esporadico"),
                         (Frecuencia.NO_DEFINIDA, None, ""))
        self.assertEqual(frecuencia_efectiva(None, None, "alta")[0], Frecuencia.NO_DEFINIDA)

    def test_desviacion(self):
        self.assertEqual(desviacion_frecuencia(21, 14),
                         {"dias_sin_sesion": 21, "intervalo": 14, "razon": 1.5, "atraso_dias": 7, "excede": True})
        self.assertFalse(desviacion_frecuencia(7, 14)["excede"])
        self.assertIsNone(desviacion_frecuencia(None, 14))   # sin última sesión
        self.assertIsNone(desviacion_frecuencia(20, None))   # sin frecuencia
