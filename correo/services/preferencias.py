"""Preferencias de correo: bloqueos por baja, rebote duro o spam, y el token público.

Una persona puede tener varias filas (paciente + leads, o tras una fusión).
Se lee siempre la SUMA: basta un bloqueo en cualquiera para no enviar.
"""
from django.db import transaction
from django.utils import timezone

from correo.models import PreferenciaCorreo


def de_persona(dest):
    """La fila propia de esta identidad exacta; se crea si no existe."""
    ident = dest.identidad()
    fila = (PreferenciaCorreo.objects.filter(
        paciente=ident["paciente"], lead=ident["lead"], autorizacion=ident["autorizacion"],
        es_tutor=ident["es_tutor"]).order_by("id").first())
    if fila is None:
        fila = PreferenciaCorreo.objects.create(**ident)
    return fila


def relacionadas(dest):
    return PreferenciaCorreo.objects.filter(dest.filtro(), clinica=dest.clinica)


def bloqueos(dest):
    """{'marketing': bool, 'rebote_duro': bool, 'spam': bool} sumando todas las filas."""
    filas = list(relacionadas(dest).values("marketing_bloqueado", "rebote_duro", "marcado_spam"))
    return {
        "marketing": any(f["marketing_bloqueado"] for f in filas),
        "rebote_duro": any(f["rebote_duro"] for f in filas),
        "spam": any(f["marcado_spam"] for f in filas),
    }


def bloquear_marketing(dest):
    fila = de_persona(dest)
    if not fila.marketing_bloqueado:
        fila.marketing_bloqueado = True
        fila.marketing_bloqueado_en = timezone.now()
        fila.save(update_fields=["marketing_bloqueado", "marketing_bloqueado_en", "actualizado_en"])
    return fila


def desbloquear_marketing(dest):
    """Un consentimiento nuevo levanta las bajas previas de toda la persona."""
    relacionadas(dest).filter(marketing_bloqueado=True).update(
        marketing_bloqueado=False, marketing_bloqueado_en=None, actualizado_en=timezone.now())


def marcar_rebote_duro(dest):
    fila = de_persona(dest)
    if not fila.rebote_duro:
        fila.rebote_duro, fila.rebote_duro_en = True, timezone.now()
        fila.save(update_fields=["rebote_duro", "rebote_duro_en", "actualizado_en"])
    return fila


def marcar_spam(dest):
    """Quien marca spam deja de recibir comerciales: bloqueo + revocación."""
    from correo.models import ConsentimientoComunicacion as CC
    from correo.services import consentimiento
    with transaction.atomic():
        fila = de_persona(dest)
        if not fila.marcado_spam:
            fila.marcado_spam, fila.marcado_spam_en = True, timezone.now()
            fila.save(update_fields=["marcado_spam", "marcado_spam_en", "actualizado_en"])
        consentimiento.revocar(dest, CC.Origen.WEBHOOK_PROVEEDOR)
    return fila


def por_token(token):
    try:
        return (PreferenciaCorreo.objects.select_related("paciente", "lead", "autorizacion", "clinica")
                .get(token=token))
    except (PreferenciaCorreo.DoesNotExist, ValueError, TypeError):
        return None
    except Exception:  # token con formato que el UUIDField no acepta
        return None


def correo_enmascarado(correo):
    """m***@gmail.com — para mostrar en la página pública sin exponer la dirección."""
    correo = (correo or "").strip()
    if "@" not in correo:
        return ""
    usuario, dominio = correo.split("@", 1)
    return f"{usuario[:1]}***@{dominio}"
