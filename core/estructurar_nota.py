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

SYSTEM = (
    "Eres un asistente clínico para psicólogos. A partir del relato (transcrito de "
    "un audio) de una sesión de psicoterapia, devuelve SOLO un JSON con estas claves, "
    "en español, conciso y profesional, sin inventar datos que no estén en el relato:\n"
    '  "motivo": motivo de consulta o tema central de la sesión.\n'
    '  "diagnostico": impresión diagnóstica o problemática a trabajar (vacío si no se menciona).\n'
    '  "indicaciones": próximos pasos + tareas/actividades asignadas.\n'
    '  "nota": resumen de la sesión y puntos importantes a recordar, en prosa breve.\n'
    "Devuelve únicamente el JSON, sin texto adicional."
)


def disponible():
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def estructurar(texto):
    """Devuelve {motivo, diagnostico, indicaciones, nota} o None si no se pudo."""
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key or not (texto or "").strip():
        return None
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
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": texto.strip()[:6000]},
                ],
            },
            timeout=40,
        )
        r.raise_for_status()
        contenido = r.json()["choices"][0]["message"]["content"]
        datos = json.loads(contenido)
        # Solo las claves que conocemos, como strings.
        return {k: str(datos.get(k, "") or "").strip()
                for k in ("motivo", "diagnostico", "indicaciones", "nota")}
    except (requests.RequestException, KeyError, ValueError, json.JSONDecodeError):
        return None
