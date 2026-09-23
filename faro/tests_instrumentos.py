"""Los puntajes y los cortes del tamizaje Faro.

Es el archivo de tests más importante del proyecto. Un corte mal puesto no se
nota: el cuestionario funciona, el puntaje sale igual de creíble, y el error
aparece el día que un estudiante en riesgo queda clasificado en verde y nadie
lo llama.

Cada test dice de dónde sale el criterio que comprueba.

    python manage.py test faro.tests_instrumentos
"""
from django.test import SimpleTestCase

from faro import instrumentos as ins


def resp(**kw):
    """Respuestas en cero salvo lo que se indique."""
    d = {f"ebipq{i}": 0 for i in range(1, 15)}
    d.update({f"phq{i}": 0 for i in range(1, 10)})
    d.update({f"gad{i}": 0 for i in range(1, 8)})
    d.update({f"asq{i}": 0 for i in range(1, 5)})
    d.update(kw)
    return d


class CatalogoTests(SimpleTestCase):
    def test_estan_los_treinta_y_ocho_items(self):
        self.assertEqual(len(ins.EBIPQ), 14)
        self.assertEqual(len(ins.PHQ_A), 9)
        self.assertEqual(len(ins.GAD_7), 7)
        self.assertEqual(len(ins.ASQ), 4)
        self.assertEqual(len(ins.CONTEXTUALES), 4)
        # 38 y no 42: los cuatro ítems extra del PHQ-A quedan fuera a
        # propósito (dos duplican el ASQ). Ver instrumentos.py.
        self.assertEqual(len(ins.ORDEN), 38)

    def test_ningun_identificador_se_repite(self):
        ids = [i["id"] for i in ins.ORDEN]
        self.assertEqual(len(ids), len(set(ids)))

    def test_ningun_item_quedo_vacio_ni_como_marcador(self):
        for i in ins.ORDEN:
            self.assertTrue(i["texto"].strip(), i["id"])
            self.assertNotIn("[", i["texto"], f"{i['id']} parece un marcador de posición")
            self.assertTrue(i["escala"], i["id"])

    def test_los_items_de_riesgo_estan_marcados(self):
        # Son los que disparan la ruta roja del protocolo. Si alguno pierde la
        # marca, deja de tratarse como riesgo sin que nadie lo note.
        riesgo = {i["id"] for i in ins.ORDEN if i["riesgo"]}
        self.assertEqual(riesgo, {"phq9", "asq1", "asq2", "asq3", "asq4"})

    def test_el_riesgo_no_va_al_final_del_cuestionario(self):
        # Al final se responde apurado. Y nadie debería salir del tamizaje con
        # una pregunta sobre suicidio como última cosa leída.
        ids = [i["id"] for i in ins.ORDEN]
        self.assertTrue(ids[-1].startswith("ctx"))
        ultimo_riesgo = max(ids.index(x) for x in ("phq9", "asq4"))
        self.assertLess(ultimo_riesgo, len(ids) - 1)


class PhqATests(SimpleTestCase):
    """Cortes del propio instrumento: 0–4 · 5–9 · 10–14 · 15–19 · 20–27."""

    def test_los_cinco_rangos_de_severidad(self):
        casos = [(0, "Mínimo"), (4, "Mínimo"), (5, "Leve"), (9, "Leve"),
                 (10, "Moderado"), (14, "Moderado"), (15, "Moderadamente severo"),
                 (19, "Moderadamente severo"), (20, "Severo"), (24, "Severo")]
        for total, sev in casos:
            # Se reparte el total entre los ítems 1–8 para no tocar el 9.
            r = resp(**{f"phq{i + 1}": min(3, max(0, total - 3 * i)) for i in range(8)})
            self.assertEqual(ins.puntuar_phq_a(r)["severidad"], sev, f"total {total}")

    def test_el_item_9_manda_sobre_el_total(self):
        # Un estudiante puede tener todo lo demás en cero y aun así ser rojo.
        # Es la instrucción del instrumento: toda respuesta positiva al ítem 9
        # se sigue con entrevista clínica.
        r = resp(phq9=1)
        p = ins.puntuar_phq_a(r)
        self.assertEqual(p["total"], 1)
        self.assertEqual(p["severidad"], "Mínimo")
        self.assertEqual(p["nivel"], ins.ROJO)

    def test_sin_item_9_el_rojo_empieza_en_veinte(self):
        self.assertEqual(ins.puntuar_phq_a(resp(**{f"phq{i}": 2 for i in range(1, 9)}))["nivel"],
                         ins.AMBAR)  # 16 puntos
        self.assertEqual(ins.puntuar_phq_a(resp(**{f"phq{i}": 3 for i in range(1, 9)}))["nivel"],
                         ins.ROJO)   # 24 puntos

    def test_de_diez_a_diecinueve_es_ambar(self):
        r = resp(**{f"phq{i}": 2 for i in range(1, 6)})  # 10
        self.assertEqual(ins.puntuar_phq_a(r)["nivel"], ins.AMBAR)


class Gad7Tests(SimpleTestCase):
    def test_los_cuatro_rangos(self):
        for total, sev in [(0, "Mínima"), (4, "Mínima"), (5, "Leve"), (9, "Leve"),
                           (10, "Moderada"), (14, "Moderada"), (15, "Severa"), (21, "Severa")]:
            r = resp(**{f"gad{i + 1}": min(3, max(0, total - 3 * i)) for i in range(7)})
            self.assertEqual(ins.puntuar_gad_7(r)["severidad"], sev, f"total {total}")

    def test_desde_moderada_se_acompaña(self):
        self.assertEqual(ins.puntuar_gad_7(resp(gad1=3, gad2=3, gad3=3))["nivel"], ins.VERDE)   # 9
        self.assertEqual(ins.puntuar_gad_7(resp(gad1=3, gad2=3, gad3=3, gad4=1))["nivel"],
                         ins.AMBAR)  # 10

    def test_la_ansiedad_nunca_es_roja_por_si_sola(self):
        # El GAD-7 no mide riesgo. Un 21 es grave y se acompaña, pero la ruta
        # del mismo día la disparan el ASQ y el ítem 9, no la ansiedad.
        r = resp(**{f"gad{i}": 3 for i in range(1, 8)})
        self.assertEqual(ins.puntuar_gad_7(r)["nivel"], ins.AMBAR)


class AsqTests(SimpleTestCase):
    def test_un_solo_si_basta(self):
        for i in range(1, 5):
            p = ins.puntuar_asq(resp(**{f"asq{i}": 1}))
            self.assertTrue(p["positivo"], f"asq{i}")
            self.assertEqual(p["nivel"], ins.ROJO)
            self.assertEqual(p["items"], [i])

    def test_todo_en_no_es_verde(self):
        p = ins.puntuar_asq(resp())
        self.assertFalse(p["positivo"])
        self.assertEqual(p["nivel"], ins.VERDE)

    def test_registra_cuales_salieron_positivos(self):
        # El psicólogo necesita saber cuáles para conducir la entrevista.
        self.assertEqual(ins.puntuar_asq(resp(asq1=1, asq4=1))["items"], [1, 4])


class EbipqTests(SimpleTestCase):
    """Criterio de Del Rey et al. (2015): víctima o agresor quien reporta la
    conducta al menos «una o dos veces al mes», que es la opción 2."""

    def test_una_o_dos_veces_no_alcanza_pero_al_mes_si(self):
        self.assertFalse(ins.puntuar_ebipq(resp(ebipq1=1))["es_victima"])
        self.assertTrue(ins.puntuar_ebipq(resp(ebipq1=2))["es_victima"])

    def test_basta_una_sola_conducta_aunque_la_suma_sea_baja(self):
        # A quien amenazan todas las semanas y nada más le pasa, la SUMA le da
        # bajo. Es justo a quien hay que detectar, y por eso se clasifica por el
        # máximo de cada bloque y no por el total.
        p = ins.puntuar_ebipq(resp(ebipq4=4))
        self.assertEqual(p["victimizacion"], 4)
        self.assertTrue(p["es_victima"])
        self.assertEqual(p["nivel"], ins.AMBAR)

    def test_separa_victima_de_agresor(self):
        self.assertEqual(ins.puntuar_ebipq(resp(ebipq2=3))["rol"], "Víctima")
        self.assertEqual(ins.puntuar_ebipq(resp(ebipq9=3))["rol"], "Agresor")
        self.assertEqual(ins.puntuar_ebipq(resp(ebipq2=3, ebipq9=3))["rol"], "Víctima y agresor")
        self.assertEqual(ins.puntuar_ebipq(resp())["rol"], "No involucrado")

    def test_los_siete_de_cada_bloque_cuentan(self):
        for i in range(1, 8):
            self.assertTrue(ins.puntuar_ebipq(resp(**{f"ebipq{i}": 2}))["es_victima"], i)
        for i in range(8, 15):
            self.assertTrue(ins.puntuar_ebipq(resp(**{f"ebipq{i}": 2}))["es_agresor"], i)


class ClasificarTests(SimpleTestCase):
    def test_todo_en_cero_es_verde(self):
        d = ins.clasificar(resp())
        self.assertEqual(d["nivel"], ins.VERDE)
        self.assertEqual(d["motivos"], [])

    def test_el_nivel_es_el_mas_alto_y_nada_se_promedia(self):
        # Un ASQ positivo con todo lo demás impecable sigue siendo rojo. Si en
        # algún momento alguien promedia los instrumentos, este test cae.
        d = ins.clasificar(resp(asq3=1))
        self.assertEqual(d["nivel"], ins.ROJO)

    def test_el_ambar_no_tapa_al_rojo(self):
        d = ins.clasificar(resp(gad1=3, gad2=3, gad3=3, gad4=3, ebipq1=3, phq9=2))
        self.assertEqual(d["nivel"], ins.ROJO)

    def test_explica_por_que_quedo_en_ese_nivel(self):
        # Un nivel sin motivo obliga al psicólogo a reconstruir el razonamiento
        # a mano sobre cuatrocientos protocolos.
        d = ins.clasificar(resp(asq1=1, phq9=1, gad1=3, gad2=3, gad3=3, gad4=1, ebipq3=2))
        texto = " ".join(d["motivos"])
        self.assertIn("ASQ positivo", texto)
        self.assertIn("ítem 9", texto)
        self.assertIn("GAD-7", texto)
        self.assertIn("victimización", texto)

    def test_un_cuestionario_a_medias_no_rompe_nada(self):
        # Lo que falta cuenta como cero. El protocolo ya obliga a revisar los
        # incompletos a mano; el sistema no debe caerse antes de eso.
        d = ins.clasificar({"asq1": 1})
        self.assertEqual(d["nivel"], ins.ROJO)
        self.assertEqual(d["phq_a"]["total"], 0)

    def test_los_valores_de_texto_no_lo_tumban(self):
        d = ins.clasificar({"phq1": "2", "gad1": "3", "asq1": "1", "ebipq1": "2"})
        self.assertEqual(d["phq_a"]["total"], 2)
        self.assertEqual(d["nivel"], ins.ROJO)


class CiberacosoPendienteTests(SimpleTestCase):
    """El bloque de ciberacoso existe pero todavía no tiene ítems.

    Se prueba el estado intermedio a propósito. Un instrumento a medio entrar es
    justo donde se cuelan los errores silenciosos: un bloque vacío que suma cero
    y sale verde es indistinguible de un estudiante que contestó bien.
    """

    def test_no_agrega_preguntas_mientras_no_haya_items(self):
        self.assertEqual(len(ins.CIBER), 0)
        self.assertEqual(len(ins.ORDEN), 38)

    def test_no_altera_el_nivel_de_nadie(self):
        self.assertEqual(ins.clasificar({})["nivel"], ins.VERDE)
        # Y tampoco rebaja a quien sí tiene señales por otro lado.
        self.assertEqual(ins.clasificar({"asq1": 1})["nivel"], ins.ROJO)

    def test_el_hueco_queda_marcado_y_no_pasa_por_verde_legitimo(self):
        ciber = ins.clasificar({})["ciber"]
        self.assertTrue(ciber["pendiente"],
                        "Sin ítems, el resultado debe declararse pendiente")
        self.assertEqual(ciber["nivel"], ins.VERDE)

    def test_no_inventa_motivos_de_un_bloque_que_no_se_aplicó(self):
        motivos = " ".join(ins.clasificar({"ebipq1": 3})["motivos"])
        self.assertNotIn("Ciberacoso", motivos)

    def test_el_umbral_es_el_mismo_para_los_dos_instrumentos(self):
        # Vive en una constante para que ajustar el corte del presencial mueva
        # también el del ciber. Con dos literales sueltos, el día que se afine
        # uno el otro se queda atrás y nadie lo nota.
        self.assertEqual(ins.UMBRAL_ROL, 2)
        self.assertFalse(ins.puntuar_ebipq({"ebipq1": ins.UMBRAL_ROL - 1})["es_victima"])
        self.assertTrue(ins.puntuar_ebipq({"ebipq1": ins.UMBRAL_ROL})["es_victima"])

    def test_la_clasificación_no_asume_bloques_simétricos(self):
        # El EBIPQ es 7 y 7, pero el instrumento que entre puede no serlo. Se
        # prueba la función interna porque es el criterio que va a recibir los
        # ítems reales, y tiene que estar bien antes de que lleguen.
        vic = ins._rol_por_frecuencia({"x2": 3}, "x", 2, 3, ins.ROLES_CIBER)
        self.assertTrue(vic["es_victima"])
        self.assertFalse(vic["es_agresor"])
        self.assertEqual(vic["rol"], "Cibervíctima")

        agr = ins._rol_por_frecuencia({"x4": 4}, "x", 2, 3, ins.ROLES_CIBER)
        self.assertFalse(agr["es_victima"])
        self.assertTrue(agr["es_agresor"])
        self.assertEqual(agr["rol"], "Ciberagresor")

    def test_el_rol_ciber_se_nombra_distinto_del_presencial(self):
        # En el informe del psicólogo «Víctima» y «Cibervíctima» son casos que
        # se atienden distinto; que compartan etiqueta los volvería el mismo.
        self.assertNotEqual(ins.ROLES_CIBER["victima"], ins.ROLES_PRESENCIAL["victima"])
