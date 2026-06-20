"""Sincronización (opcional) de las citas con Google Calendar.

Se activa SOLO si hay credenciales de *service account* configuradas y la
librería de Google instalada. Si no, todas las funciones son **no-op** (igual que
el envío por WhatsApp cae a un enlace wa.me): nunca rompen la operación de la cita.

Configuración (ver settings.GOOGLE_CALENDAR_*):
  1. Crear un service account en Google Cloud con la Calendar API activada.
  2. Compartir cada calendario (uno por sede) con el email del service account,
     dándole permiso de "Hacer cambios en los eventos".
  3. Poner el JSON del service account en GOOGLE_CALENDAR_CREDENTIALS (ruta o
     contenido) y el ID de cada calendario en GOOGLE_CALENDAR_LIMA / _PIURA.

El evento usa un id determinístico por cita (itacacita<ID>), así que crear/mover/
cancelar siempre apunta al mismo evento sin necesidad de guardar nada en la BD.
"""
import json
import os
from datetime import timedelta

from django.conf import settings

DURACION_MIN = 60  # duración por defecto de una sesión (minutos)

_service_cache = None
_intentado = False


def _credenciales():
    raw = (getattr(settings, "GOOGLE_CALENDAR_CREDENTIALS", "") or "").strip()
    if not raw:
        return None
    try:
        from google.oauth2 import service_account
    except ImportError:
        return None
    try:
        if os.path.isfile(raw):
            with open(raw, "r", encoding="utf-8") as f:
                info = json.load(f)
        else:
            info = json.loads(raw)
        return service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/calendar"]
        )
    except (ValueError, OSError):
        return None


def _service():
    global _service_cache, _intentado
    if _service_cache is not None:
        return _service_cache
    if _intentado:
        return None
    _intentado = True
    creds = _credenciales()
    if creds is None:
        return None
    try:
        from googleapiclient.discovery import build
        _service_cache = build("calendar", "v3", credentials=creds, cache_discovery=False)
    except Exception:
        _service_cache = None
    return _service_cache


def _calendar_id(cita):
    sede = getattr(cita.paciente, "sede", "") or ""
    ids = getattr(settings, "GOOGLE_CALENDAR_IDS", {}) or {}
    return (ids.get(sede) or getattr(settings, "GOOGLE_CALENDAR_DEFAULT", "") or "").strip()


def _evento_id(cita):
    return f"itacacita{cita.id}"


def disponible(cita):
    """¿Está la sincronización lista para esta cita (credenciales + calendario)?"""
    return bool(_calendar_id(cita)) and _service() is not None


def _cuerpo(cita):
    inicio = cita.inicio
    fin = inicio + timedelta(minutes=DURACION_MIN)
    tz = getattr(cita.clinica, "zona_horaria", "") or "America/Lima"
    medico = str(cita.medico) if cita.medico_id else ""
    emoji = {"confirmada": "✅", "por_confirmar": "🕓", "atendida": "✔️"}.get(cita.estado, "")
    resumen = f"{emoji} {cita.paciente.nombre}".strip()
    if cita.especialidad:
        resumen += f" · {cita.especialidad}"
    desc = "\n".join(x for x in [
        f"Paciente: {cita.paciente.nombre}",
        f"Teléfono: {cita.paciente.telefono}" if cita.paciente.telefono else "",
        f"Psicólogo: {medico}" if medico else "",
        f"Estado: {cita.get_estado_display()}",
        "(Itaca Conversemos · Gestión)",
    ] if x)
    return {
        "id": _evento_id(cita),
        "summary": resumen,
        "description": desc,
        "start": {"dateTime": inicio.isoformat(), "timeZone": tz},
        "end": {"dateTime": fin.isoformat(), "timeZone": tz},
    }


def sync_cita(cita):
    """Crea o actualiza el evento de la cita. Best-effort: nunca lanza.
    Devuelve True si se sincronizó, False si está apagado o falló."""
    try:
        svc = _service()
        cal = _calendar_id(cita)
        if not svc or not cal:
            return False
        from googleapiclient.errors import HttpError
        cuerpo = _cuerpo(cita)
        try:
            svc.events().update(calendarId=cal, eventId=cuerpo["id"], body=cuerpo).execute()
        except HttpError as e:
            status = getattr(getattr(e, "resp", None), "status", None)
            if status in (404, 410):
                svc.events().insert(calendarId=cal, body=cuerpo).execute()
            else:
                raise
        return True
    except Exception:
        return False


def eliminar_cita(cita):
    """Borra el evento de la cita (p. ej. al cancelar). Best-effort: nunca lanza."""
    try:
        svc = _service()
        cal = _calendar_id(cita)
        if not svc or not cal:
            return False
        from googleapiclient.errors import HttpError
        try:
            svc.events().delete(calendarId=cal, eventId=_evento_id(cita)).execute()
        except HttpError as e:
            status = getattr(getattr(e, "resp", None), "status", None)
            if status not in (404, 410):
                raise
        return True
    except Exception:
        return False
