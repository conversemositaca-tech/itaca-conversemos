"""Los cuatro instrumentos del tamizaje Faro, y cómo se leen sus puntajes.

Este archivo es la pieza más delicada del proyecto. Un ítem mal transcrito o un
punto de corte mal puesto no se ve: el cuestionario funciona igual, el puntaje
sale igual de creíble, y el error aparece recién el día que un estudiante en
riesgo queda clasificado en verde. Por eso el texto NO se escribe de memoria y
cada corte lleva su fuente al lado.

Los ítems viven en código y no en la base a propósito: así quedan versionados,
y cambiar una palabra deja rastro en el historial en lugar de modificar en
silencio un instrumento ya aplicado a cientos de estudiantes.

FUENTES
· PHQ-A — PHQ-9 modificado para adolescentes (phqscreeners). Ortografía
  corregida respecto de la copia que circula ("se seinte", "concetrarse") y
  pasado a tuteo: el original está en tercera persona formal porque se escribió
  para que lo administrara un clínico. Las dos son modificaciones deliberadas.
· GAD-7 — versión en castellano (CIBERSAM). Adaptada al tuteo por lo mismo.
· ASQ — Ask Suicide-Screening Questions, NIMH, versión oficial en español.
  Dominio público. Validado para administración por un profesional; aquí se
  autoaplica, que es una desviación consciente del modo de administración.
· EBIPQ — validación al castellano de Ortega-Ruiz, Del Rey y Casas (2016),
  recuperada del estudio ecuatoriano (2025). Se usa "ofensivas" donde el
  original dice "malsonantes": es la adaptación documentada en la validación
  peruana de Lima.
"""

# ── Escalas de respuesta ────────────────────────────────────────────────────
ESC_DIAS = ["Ningún día", "Varios días", "Más de la mitad de los días", "Casi todos los días"]
ESC_QUINCE = ["Nunca", "Menos de la mitad de los días", "Más de la mitad de los días",
              "Casi todos los días"]
ESC_SI_NO = ["No", "Sí"]
ESC_EBIPQ = ["No, nunca", "Sí, una o dos veces", "Sí, una o dos veces al mes",
             "Sí, alrededor de una vez a la semana", "Sí, más de una vez a la semana"]
ESC_APOYO = ["Sí, varias personas", "Sí, una persona", "No estoy seguro", "No"]
ESC_AMBIENTE = ["Bueno", "Más o menos", "Tenso", "Malo"]
ESC_SEGURO = ["Siempre", "Casi siempre", "A veces", "Casi nunca"]
ESC_SABRIA = ["Sí", "Más o menos", "No"]


def _items(prefijo, marco, escala, textos, riesgo=()):
    return [
        {"id": f"{prefijo}{i + 1}", "marco": marco, "texto": t, "escala": escala,
         "riesgo": (i + 1) in riesgo}
        for i, t in enumerate(textos)
    ]


# ── EBIPQ · acoso escolar · 14 ítems, 0–4, ventana de dos meses ─────────────
MARCO_EBIPQ = "En los últimos dos meses, ¿con qué frecuencia ha pasado esto?"
EBIPQ = _items("ebipq", MARCO_EBIPQ, ESC_EBIPQ, [
    # Victimización (1–7)
    "Alguien me ha golpeado, me ha pateado o me ha empujado.",
    "Alguien me ha insultado.",
    "Alguien les ha dicho a otras personas palabras ofensivas sobre mí.",
    "Alguien me ha amenazado.",
    "Alguien me ha robado o roto mis cosas.",
    "He sido excluido o ignorado por otras personas.",
    "Alguien ha difundido rumores sobre mí.",
    # Agresión (8–14)
    "He golpeado, pateado o empujado a alguien.",
    "He insultado y he dicho palabras ofensivas a alguien.",
    "He dicho a otras personas palabras ofensivas sobre alguien.",
    "He amenazado a alguien.",
    "He robado o he estropeado algo de alguien.",
    "He excluido o ignorado a alguien.",
    "He difundido rumores sobre alguien.",
])

# ── PHQ-A · estado de ánimo · 9 ítems que puntúan, 0–3 ─────────────────────
MARCO_PHQ = "En las últimas dos semanas, ¿con qué frecuencia te ha pasado esto?"
PHQ_A = _items("phq", MARCO_PHQ, ESC_DIAS, [
    "Te has sentido deprimido, irritado o sin esperanza.",
    "Has tenido poco interés o placer para hacer cosas.",
    "Has tenido dificultad para dormirte, para quedarte dormido, o has dormido demasiado.",
    "Has tenido poco apetito, has perdido peso, o has comido demasiado.",
    "Te has sentido cansado o con poca energía.",
    "Te has sentido mal contigo mismo, o has sentido que eres un fracasado, "
    "o que le has fallado a tu familia o a ti mismo.",
    "Has tenido problemas para concentrarte en cosas como las tareas del colegio, "
    "leer o ver televisión.",
    "Te has movido o has hablado tan lento que otras personas pudieron notarlo. "
    "O al contrario: has estado tan inquieto que te has movido más de lo normal.",
    "Has tenido pensamientos de que estarías mejor muerto, o de hacerte daño de alguna manera.",
], riesgo=(9,))

# El PHQ-A completo trae cuatro ítems más: distimia, deterioro funcional, y dos
# sobre suicidio (pensamientos en el último mes, e intento alguna vez). Quedan
# FUERA a propósito:
#   · Los dos de suicidio duplican los ítems 3 y 4 del ASQ. Preguntarle a un
#     adolescente dos veces si ha intentado matarse no mejora la detección y sí
#     empeora la experiencia.
#   · El de deterioro funcional sirve para diagnosticar depresión mayor, y este
#     tamizaje no diagnostica.
#   · El de distimia mira el último año, que no es la ventana del tamizaje.
# Por eso el cuestionario tiene 38 ítems y no 42.

# ── GAD-7 · ansiedad · 7 ítems, 0–3 ────────────────────────────────────────
MARCO_GAD = "En los últimos 15 días, ¿con qué frecuencia has tenido este problema?"
GAD_7 = _items("gad", MARCO_GAD, ESC_QUINCE, [
    "Te has sentido nervioso, ansioso o muy alterado.",
    "No has podido dejar de preocuparte.",
    "Te has preocupado excesivamente por diferentes cosas.",
    "Has tenido dificultad para relajarte.",
    "Te has sentido tan intranquilo que no podías estarte quieto.",
    "Te has irritado o molestado con facilidad.",
    "Has sentido miedo, como si fuera a suceder algo terrible.",
])

# ── ASQ · riesgo suicida · 4 ítems, sí/no ──────────────────────────────────
# El quinto ítem del ASQ (agudeza: "¿Está pensando en suicidarse en este
# momento?") NO va en el formulario: el propio instrumento lo reserva para
# preguntarlo cara a cara cuando el tamizaje sale positivo. Lo hace el psicólogo
# en la entrevista de contención del mismo día, según el protocolo.
MARCO_ASQ = "Contesta sí o no."
ASQ = _items("asq", MARCO_ASQ, ESC_SI_NO, [
    "En las últimas semanas, ¿has deseado estar muerto?",
    "En las últimas semanas, ¿has sentido que tú o tu familia estarían mejor si estuvieras muerto?",
    "En la última semana, ¿has estado pensando en suicidarte?",
    "¿Alguna vez has intentado suicidarte?",
], riesgo=(1, 2, 3, 4))

# ── Contextuales · no clínicas, no puntúan ─────────────────────────────────
# Enriquecen el informe institucional: son las que un equipo directivo puede
# accionar la semana siguiente, a diferencia de un porcentaje de ansiedad.
MARCO_CTX = "Sobre tu colegio."
CONTEXTUALES = [
    {"id": "ctx1", "marco": MARCO_CTX, "escala": ESC_APOYO, "riesgo": False,
     "texto": "¿Sientes que tienes a alguien a quien acudir cuando tienes un problema?"},
    {"id": "ctx2", "marco": MARCO_CTX, "escala": ESC_AMBIENTE, "riesgo": False,
     "texto": "¿Cómo describirías el ambiente de tu salón?"},
    {"id": "ctx3", "marco": MARCO_CTX, "escala": ESC_SEGURO, "riesgo": False,
     "texto": "¿Te sientes seguro dentro del colegio?"},
    {"id": "ctx4", "marco": MARCO_CTX, "escala": ESC_SABRIA, "riesgo": False,
     "texto": "Si necesitaras ayuda en el colegio, ¿sabrías a quién pedírsela?"},
]

# El orden importa y no es alfabético. Empieza por convivencia, que es lo menos
# íntimo; el riesgo va hacia el medio y no al final, cuando ya se responde
# apurado; y cierra con las contextuales para que nadie salga del cuestionario
# con la última pregunta sobre suicidio en la cabeza.
ORDEN = EBIPQ + PHQ_A + GAD_7 + ASQ + CONTEXTUALES

VERDE, AMBAR, ROJO = "verde", "ambar", "rojo"
# El nivel de un estudiante es el más alto de todos sus instrumentos: nada se
# promedia. Un ASQ positivo con todo lo demás en cero sigue siendo rojo.
_PESO = {VERDE: 0, AMBAR: 1, ROJO: 2}


def _suma(resp, prefijo, n):
    return sum(int(resp.get(f"{prefijo}{i + 1}", 0) or 0) for i in range(n))


def puntuar_phq_a(resp):
    """PHQ-A: 0–27. El ítem 9 manda sobre el total.

    Cortes de severidad del propio instrumento: 0–4 mínimo · 5–9 leve ·
    10–14 moderado · 15–19 moderadamente severo · 20–27 severo.

    El ítem 9 (ideación) pasa a rojo con CUALQUIER valor distinto de cero,
    aunque el total sea bajo. Es la instrucción del instrumento: toda respuesta
    positiva al ítem 9 debe seguirse con entrevista clínica.
    """
    total = _suma(resp, "phq", 9)
    item9 = int(resp.get("phq9", 0) or 0)
    if total <= 4:
        sev = "Mínimo"
    elif total <= 9:
        sev = "Leve"
    elif total <= 14:
        sev = "Moderado"
    elif total <= 19:
        sev = "Moderadamente severo"
    else:
        sev = "Severo"

    if item9 > 0 or total >= 20:
        nivel = ROJO
    elif total >= 10:
        nivel = AMBAR
    else:
        nivel = VERDE
    return {"total": total, "severidad": sev, "item9": item9, "nivel": nivel}


def puntuar_gad_7(resp):
    """GAD-7: 0–21. Cortes del instrumento: 0–4 mínima · 5–9 leve ·
    10–14 moderada · 15–21 severa. Desde moderada se acompaña."""
    total = _suma(resp, "gad", 7)
    if total <= 4:
        sev = "Mínima"
    elif total <= 9:
        sev = "Leve"
    elif total <= 14:
        sev = "Moderada"
    else:
        sev = "Severa"
    return {"total": total, "severidad": sev, "nivel": AMBAR if total >= 10 else VERDE}


def puntuar_asq(resp):
    """ASQ: positivo con UN solo sí en cualquiera de los cuatro ítems.

    No hay puntaje ni gradiente: el instrumento es binario a propósito. Un
    positivo exige valoración de seguridad el mismo día, y por eso es rojo sin
    matices.
    """
    positivos = [i + 1 for i in range(4) if int(resp.get(f"asq{i + 1}", 0) or 0) == 1]
    return {"positivo": bool(positivos), "items": positivos,
            "nivel": ROJO if positivos else VERDE}


def puntuar_ebipq(resp):
    """EBIPQ: rol por frecuencia, no por puntaje total.

    Criterio de Del Rey et al. (2015): es víctima quien reporta haber sufrido
    alguna conducta de victimización al menos "una o dos veces al mes" —la
    opción 2 de la escala— y agresor quien la ha ejercido con esa frecuencia.

    Se clasifica por el MÁXIMO de cada bloque y no por la suma: un estudiante
    al que amenazan todas las semanas pero al que no le pasa nada más tendría
    una suma baja, y es exactamente a quien hay que detectar.
    """
    vic = [int(resp.get(f"ebipq{i + 1}", 0) or 0) for i in range(7)]
    agr = [int(resp.get(f"ebipq{i + 8}", 0) or 0) for i in range(7)]
    es_victima = max(vic, default=0) >= 2
    es_agresor = max(agr, default=0) >= 2

    if es_victima and es_agresor:
        rol = "Víctima y agresor"
    elif es_victima:
        rol = "Víctima"
    elif es_agresor:
        rol = "Agresor"
    else:
        rol = "No involucrado"

    return {"victimizacion": sum(vic), "agresion": sum(agr),
            "es_victima": es_victima, "es_agresor": es_agresor, "rol": rol,
            "nivel": AMBAR if (es_victima or es_agresor) else VERDE}


def clasificar(resp):
    """Puntúa los cuatro instrumentos y devuelve el nivel de atención.

    `resp` es {id_de_item: valor}. Lo que falta cuenta como cero: un estudiante
    que abandona a la mitad no debe hacer caer el sistema, y el protocolo ya
    obliga a revisar los incompletos a mano.
    """
    phq = puntuar_phq_a(resp)
    gad = puntuar_gad_7(resp)
    asq = puntuar_asq(resp)
    ebipq = puntuar_ebipq(resp)
    nivel = max((phq["nivel"], gad["nivel"], asq["nivel"], ebipq["nivel"]), key=_PESO.get)

    # Por qué quedó en ese nivel, en palabras. Va al informe del psicólogo: un
    # nivel sin motivo obliga a reconstruir el razonamiento a mano.
    motivos = []
    if asq["positivo"]:
        motivos.append("ASQ positivo: respondió sí en tamizaje de riesgo suicida.")
    if phq["item9"] > 0:
        motivos.append("PHQ-A ítem 9: reporta pensamientos de muerte o de hacerse daño.")
    if phq["total"] >= 20:
        motivos.append(f"PHQ-A {phq['total']}/27, rango severo.")
    elif phq["total"] >= 10:
        motivos.append(f"PHQ-A {phq['total']}/27, rango {phq['severidad'].lower()}.")
    if gad["total"] >= 10:
        motivos.append(f"GAD-7 {gad['total']}/21, ansiedad {gad['severidad'].lower()}.")
    if ebipq["es_victima"]:
        motivos.append("EBIPQ: reporta victimización al menos una o dos veces al mes.")
    if ebipq["es_agresor"]:
        motivos.append("EBIPQ: reporta ejercer agresión al menos una o dos veces al mes.")

    return {"nivel": nivel, "motivos": motivos,
            "phq_a": phq, "gad_7": gad, "asq": asq, "ebipq": ebipq}
