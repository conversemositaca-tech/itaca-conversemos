"""Contexto operativo a partir de las notas de agenda (`Cita.notas`).

Por qué existe: coordinación ya escribe en la nota de la cita lo que explica el
caso ("se olvidó", "reprogramada", "viaja la próxima semana"). Hoy esa
información solo se ve abriendo cada cita una por una, así que en la práctica
no se usa para priorizar. Este módulo la resume en una etiqueta corta para que
el Centro de Continuidad la muestre en la fila.

REGLA INNEGOCIABLE — las notas NO deciden nada clínico.
    Una nota es texto libre de coordinación, no un registro clínico. Por eso
    este módulo:
      · nunca devuelve ni sugiere un código DP;
      · nunca marca alta, continuidad, derivación ni suspensión;
      · cuando detecta una palabra clínica, lo único que produce es un aviso de
        REGISTRO ("verificar registro formal"), que le pide a una persona ir a
        mirar la fuente oficial. Ver `MENCIONES_CLINICAS`.
    La decisión sigue viniendo de `Cita.decision`, escrita por quien tiene
    permiso, desde la Agenda. Ver core/continuidad.py.

Se detecta de forma conservadora: se prefiere no marcar nada antes que marcar
mal. Los patrones piden frases, no palabras sueltas, y se comparan sobre el
texto normalizado (sin tildes, en minúsculas) porque el equipo escribe indistinto.
"""
import re
import unicodedata

# Cuántas señales se muestran en la etiqueta corta de la fila. Más que esto
# deja de ser un resumen y hay que abrir el detalle del caso.
MAX_EN_RESUMEN = 2


def normalizar(texto):
    """minúsculas y sin tildes: 'Olvidó' y 'olvido' son la misma señal."""
    if not texto:
        return ""
    plano = unicodedata.normalize("NFD", str(texto))
    plano = "".join(c for c in plano if unicodedata.category(c) != "Mn")
    return plano.lower()


# (clave, etiqueta que ve el usuario, patrón)
#
# El patrón se prueba contra el texto ya normalizado. Se usan frases y límites
# de palabra a propósito: "falta" sola aparece en demasiados contextos ("falta
# confirmar"), así que se pide "falto" / "no vino" / "inasistencia".
SEÑALES = (
    ("olvido", "Olvido",
     r"\bolvid\w*|se le (?:paso|olvido)|no se acordo|no recordaba"),
    ("confusion_fecha", "Confundió fecha",
     r"\bconfundi\w*|se equivoco de (?:dia|fecha|hora)|penso que era (?:el|la|otro)|creyo que era"),
    ("inasistencia", "Inasistencia",
     r"\bno asisti\w*|\bno vino\b|\bno llego\b|\bfalto\b|\binasistenc\w*|\bno se presento\b"),
    ("reprogramacion", "Reprogramación",
     r"\breprogram\w*|\breagend\w*|cambio de (?:cita|hora|fecha|dia)|movio la (?:cita|hora)"),
    ("horario_fijo", "Horario fijo",
     r"horario fijo|hora fija|siempre (?:a las|los)|mismo (?:horario|dia y hora)|horario estable"),
    ("dificultad_horario", "Dificultad de horario",
     r"(?:dificultad|problema|cruce|choque)\w* (?:con el |de )?horario|no (?:puede|le queda) (?:en |a )?(?:ese|este) horario|se le cruza"),
    ("no_responde", "No responde",
     r"no (?:responde|contesta)|sin respuesta|no (?:se pudo |logro )?contact\w*|buzon de voz"),
    ("viaje", "Viaje",
     r"\bde viaje\b|\bviaja\b|\bviajara\b|fuera (?:de la ciudad|del pais)|se va (?:de|a) viaje"),
    ("pausa", "Posible pausa — verificar",
     r"\bpausa\b|\bpausar\b|parar un tiempo|detener el proceso|tomarse un (?:tiempo|descanso)|receso"),
    ("limitacion_economica", "Limitación económica",
     # "costo" a secas queda fuera a propósito: "se explicó el costo" no es una
     # limitación. Se pide que la nota diga que el dinero es un problema.
     r"\beconomic\w*|no puede pagar|tema de dinero|falta de dinero|presupuesto"),
    ("precierre", "Pre-cierre mencionado",
     # "última sesión" NO entra: en la nota de agenda casi siempre significa
     # "la cita anterior", no el cierre del bloque. Se pide el número explícito
     # o la palabra bloque/proceso.
     r"\bs\s?-?\s?5\s?/\s?6\b|\bs\s?-?\s?11\s?/\s?12\b|\bs\s?-?\s?17\s?/\s?18\b"
     r"|sesion \d+ de \d+|cierre de (?:bloque|proceso)|ultima (?:sesion )?del (?:bloque|proceso)"),
    ("primer_proceso", "Primer proceso",
     r"primer proceso|primera vez en terapia|recien (?:inicia|empieza)|inicio de proceso"),
)

# Palabras que pertenecen a la HISTORIA CLÍNICA, no a la agenda. Detectarlas NO
# clasifica el caso: solo produce un aviso para que una persona verifique si la
# decisión está registrada donde corresponde. Nunca se convierten en estado ni
# en DP. Ver la regla innegociable del encabezado.
MENCIONES_CLINICAS = (
    ("alta", "posible alta", r"\bdada? de alta\b|\balta terapeutica\b|\bse le dio de alta\b"),
    ("derivacion", "posible derivación", r"\bderiv\w*"),
    ("suspension", "posible suspensión", r"\bsuspend\w*|\bsuspension\b|\bfinaliza\w* el proceso\b"),
    ("continuidad", "continuidad ya conversada", r"\bcontinua\w* (?:el |su )?proceso\b|\bseguira en terapia\b"),
    ("codigo_dp", "un código DP", r"\bdp\s?-?\s?\d{1,2}\b"),
)

_COMPILADAS = tuple((c, e, re.compile(p)) for c, e, p in SEÑALES)
_CLINICAS = tuple((c, e, re.compile(p)) for c, e, p in MENCIONES_CLINICAS)


def analizar(textos):
    """Lee las notas de agenda de un paciente y devuelve su contexto operativo.

    `textos` es cualquier iterable de notas (las de sus citas). Devuelve:
        claves   – señales detectadas, en el orden de SEÑALES
        etiquetas– las mismas, legibles
        resumen  – etiqueta corta para la fila ("Olvido / Reprogramación")
        avisos   – menciones clínicas, SIEMPRE como "verificar registro formal"

    Todo puede venir vacío: no detectar nada es un resultado válido y frecuente.
    """
    plano = " · ".join(normalizar(t) for t in textos if t and str(t).strip())
    if not plano:
        return {"claves": [], "etiquetas": [], "resumen": "", "avisos": []}

    claves, etiquetas = [], []
    for clave, etiqueta, patron in _COMPILADAS:
        if patron.search(plano):
            claves.append(clave)
            etiquetas.append(etiqueta)

    avisos = []
    for _clave, que, patron in _CLINICAS:
        if patron.search(plano):
            # Nunca "el paciente está de alta": siempre "verificar el registro".
            avisos.append(f"Nota menciona {que} — verificar registro formal")

    return {
        "claves": claves,
        "etiquetas": etiquetas,
        "resumen": " / ".join(etiquetas[:MAX_EN_RESUMEN]),
        "avisos": avisos,
    }


def vacio():
    """Contexto neutro, para cuando no se pidió analizar notas."""
    return {"claves": [], "etiquetas": [], "resumen": "", "avisos": []}
