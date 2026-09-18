"""Los cierres de bloque de un proceso, con su cita y su decisión.

De 585 sesiones de cierre medidas en producción, 558 no tienen decisión
registrada: el 95 %. No es que nadie sepa qué pasó — es que anotarlo obliga a
salir del Centro de Continuidad, buscar la cita en la Agenda y editarla ahí.

Esta lista es lo que permite registrarlo donde el caso ya está a la vista. Si
señala la cita equivocada, el DP se escribe en la sesión que no es y el bloque
sigue reclamando, así que aquí se fija a qué cita apunta cada cierre.
"""
from django.test import TestCase

from core import continuidad


def cita(id, n_sesion, decision="", inicio=None):
    """Una cita asistida como la entrega el queryset de continuidad."""
    return {"id": id, "n_sesion": n_sesion, "decision": decision,
            "inicio": inicio, "estado": "asistio",
            "decision_registrada_en": None, "decision_registrada_por__nombre": ""}


class CierresDelProcesoTests(TestCase):
    def test_en_la_sesion_7_el_cierre_pendiente_es_el_6(self):
        citas = [cita(i, i) for i in range(1, 8)]
        cierres = continuidad.cierres_del_proceso(citas, 7, None)
        self.assertEqual([c["meta"] for c in cierres], [6])
        self.assertEqual(cierres[0]["cita_id"], 6)

    def test_en_la_sesion_13_hay_dos_cierres(self):
        citas = [cita(i, i) for i in range(1, 14)]
        cierres = continuidad.cierres_del_proceso(citas, 13, None)
        self.assertEqual([c["meta"] for c in cierres], [6, 12])

    def test_el_cierre_vigente_va_marcado(self):
        # Es el único sobre el que alguien puede decir algo con criterio hoy.
        citas = [cita(i, i) for i in range(1, 7)]
        cierres = continuidad.cierres_del_proceso(citas, 6, None)
        self.assertEqual(len(cierres), 1)
        self.assertTrue(cierres[0]["vigente"])

    def test_los_anteriores_no_van_marcados_como_vigentes(self):
        citas = [cita(i, i) for i in range(1, 14)]
        cierres = continuidad.cierres_del_proceso(citas, 13, None)
        por_meta = {c["meta"]: c for c in cierres}
        self.assertFalse(por_meta[6]["vigente"])
        self.assertTrue(por_meta[12]["vigente"])

    def test_trae_la_decision_que_ya_estaba(self):
        citas = [cita(i, i) for i in range(1, 8)]
        citas[5]["decision"] = "DP-08"   # la sesión 6
        cierres = continuidad.cierres_del_proceso(citas, 7, None)
        self.assertEqual(cierres[0]["decision"], "DP-08")

    def test_sin_decision_viene_vacia_y_no_None(self):
        # La pantalla distingue "sin registrar" de un valor raro.
        citas = [cita(i, i) for i in range(1, 8)]
        self.assertEqual(continuidad.cierres_del_proceso(citas, 7, None)[0]["decision"], "")

    def test_apunta_a_la_sesion_mas_reciente_con_ese_numero(self):
        # Si el proceso se reinició, la sesión 6 vigente es la última, no la del
        # proceso anterior: escribir el DP en la vieja no cerraría nada.
        citas = [cita(10, 6), cita(20, 6)]
        cierres = continuidad.cierres_del_proceso(citas, 6, None)
        self.assertEqual(cierres[0]["cita_id"], 20)

    def test_respeta_un_total_de_proceso_distinto_de_6(self):
        # Hay procesos pactados a 10 sesiones: el cierre es la 10, no la 6.
        citas = [cita(i, i) for i in range(1, 11)]
        cierres = continuidad.cierres_del_proceso(citas, 10, 10)
        self.assertEqual([c["meta"] for c in cierres], [10])

    def test_antes_del_primer_cierre_no_hay_nada_que_registrar(self):
        citas = [cita(i, i) for i in range(1, 4)]
        self.assertEqual(continuidad.cierres_del_proceso(citas, 3, None), [])

    def test_un_cierre_sin_cita_se_informa_igual(self):
        # Sin cita no hay dónde escribir el DP, pero esconderlo haría parecer
        # que el cierre no existe.
        citas = [cita(i, i) for i in (1, 2)]
        cierres = continuidad.cierres_del_proceso(citas, 7, None)
        self.assertEqual(len(cierres), 1)
        self.assertIsNone(cierres[0]["cita_id"])
