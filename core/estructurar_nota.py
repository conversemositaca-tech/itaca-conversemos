"""Estructura el texto de una sesión (transcripción) en los campos de la historia
clínica, usando un LLM (OpenAI) SI está configurado.

Es opcional y con degradación elegante: si no hay OPENAI_API_KEY o falla, devuelve
None y el flujo usa la transcripción cruda (el terapeuta la edita). No agrega
dependencias nuevas: llama a la API con `requests` (ya está en el proyecto).

Config por entorno:
  OPENAI_API_KEY   clave de OpenAI (la misma del bot Eli sirve).
  OPENAI_MODEL     modelo de chat. Default "gpt-4o-mini" (barato y suficiente).
"""
import json
import os

import requests

# Prompts y claves por tipo de ficha (estilo AgendaPro).
_BASE = (
    "Eres un asistente clínico para psicólogos. A partir del relato (transcrito de un "
    "audio) de una sesión de psicoterapia, devuelve SOLO un JSON, en español, conciso y "
    "profesional, SIN inventar datos que no estén en el relato. Claves del JSON:\n"
)
PROMPTS = {
    "evolucion": _BASE + (
        '  "nota": resumen de la sesión, en prosa breve.\n'
        '  "puntos_importantes": puntos importantes a recordar (viñetas en una línea).\n'
        '  "proximos_pasos": próximos pasos a seguir.\n'
        '  "indicaciones": tratamiento / líneas de trabajo / tareas o actividades asignadas.\n'
        "Devuelve únicamente el JSON."
    ),
    "historia": _BASE + (
        '  "motivo": motivo de consulta.\n'
        '  "aspectos_historicos": aspectos históricos relevantes.\n'
        '  "objetivos": objetivos del proceso de terapia.\n'
        '  "diagnostico": impresión diagnóstica / problemática a tratar.\n'
        "Devuelve únicamente el JSON."
    ),
}
CLAVES = {
    "evolucion": ("nota", "puntos_importantes", "proximos_pasos", "indicaciones"),
    "historia": ("motivo", "aspectos_historicos", "objetivos", "diagnostico"),
}


def _a_texto(v):
    """Normaliza el valor a texto. Si el LLM devuelve una lista, la pasa a viñetas."""
    if isinstance(v, list):
        return "\n".join(f"- {str(x).strip()}" for x in v if str(x).strip())
    return str(v if v is not None else "").strip()


def disponible():
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def estructurar(texto, tipo="evolucion"):
    """Estructura el texto en los campos del tipo de ficha (evolucion|historia).
    Devuelve un dict con las claves del tipo, o None si no se pudo."""
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key or not (texto or "").strip():
        return None
    tipo = tipo if tipo in PROMPTS else "evolucion"
    modelo = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": modelo,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": PROMPTS[tipo]},
                    {"role": "user", "content": texto.strip()[:6000]},
                ],
            },
            timeout=40,
        )
        r.raise_for_status()
        datos = json.loads(r.json()["choices"][0]["message"]["content"])
        return {k: _a_texto(datos.get(k)) for k in CLAVES[tipo]}
    except (requests.RequestException, KeyError, ValueError, json.JSONDecodeError):
        return None
