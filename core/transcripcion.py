"""Transcripción de audio con Whisper (local, gratis) usando faster-whisper.

El modelo se carga una sola vez (perezoso) y se reutiliza. La primera vez descarga
el modelo (~base/small) de Hugging Face; luego queda en caché local. Decodifica
.ogg/.opus/.m4a/.mp3/.wav directamente (PyAV trae ffmpeg), así que sirve para las
notas de voz de WhatsApp.

Config por entorno:
  WHISPER_MODEL   tamaño del modelo (tiny|base|small|medium). Default "small".
  WHISPER_DEVICE  "cpu" (default) o "cuda".
"""
import os
import tempfile

_modelo = None


def disponible():
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def _get_modelo():
    global _modelo
    if _modelo is None:
        from faster_whisper import WhisperModel
        size = os.getenv("WHISPER_MODEL", "small")
        device = os.getenv("WHISPER_DEVICE", "cpu")
        compute = "float16" if device == "cuda" else "int8"
        _modelo = WhisperModel(size, device=device, compute_type=compute)
    return _modelo


def transcribir_archivo(archivo, idioma="es"):
    """Transcribe un UploadedFile (o cualquier file-like) a texto en español.
    Devuelve el texto; lanza si Whisper no está instalado."""
    suf = os.path.splitext(getattr(archivo, "name", "") or "")[1] or ".ogg"
    tmp = tempfile.NamedTemporaryFile(suffix=suf, delete=False)
    try:
        if hasattr(archivo, "chunks"):
            for chunk in archivo.chunks():
                tmp.write(chunk)
        else:
            tmp.write(archivo.read())
        tmp.close()
        segmentos, _ = _get_modelo().transcribe(
            tmp.name, language=idioma, vad_filter=True
        )
        return " ".join(s.text.strip() for s in segmentos).strip()
    finally:
        try:
            os.remove(tmp.name)
        except OSError:
            pass
