"""Ingreso automático de leads (sin sesión), identificado por el token de la clínica.

Dos puertas públicas, protegidas por el token secreto de la clínica en la URL:
- Web / campañas (formularios, landings, Meta Lead Ads vía Zapier/Make).
- WhatsApp (webhook de Evolution: el primer mensaje de un número desconocido).

Más dos endpoints autenticados para que la clínica vea/regenere su token.
La clínica se resuelve por el token (no hay usuario logueado), por eso se fija
`clinica=` explícitamente al crear el lead (aislamiento multitenant · Ley 29733).
"""
from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.models import Clinica
from core.tenant import get_clinica_actual
from pacientes.models import Paciente

from .models import Lead

FUENTES_VALIDAS = {c[0] for c in Lead.Fuente.choices}


def _solo_digitos(s):
    return "".join(ch for ch in (s or "") if ch.isdigit())


def _lead_existente(clinica, telefono, dias=30):
    """Lead abierto (no perdido) reciente con ese teléfono, para no duplicar."""
    digs = _solo_digitos(telefono)
    if len(digs) < 6:
        return None
    suf = digs[-9:]
    desde = timezone.now() - timedelta(days=dias)
    qs = Lead.objects.filter(clinica=clinica, creado_en__gte=desde).exclude(estado=Lead.Estado.PERDIDO)
    for lead in qs:
        if _solo_digitos(lead.telefono).endswith(suf):
            return lead
    return None


def _es_paciente(clinica, telefono):
    digs = _solo_digitos(telefono)
    if len(digs) < 6:
        return False
    suf = digs[-9:]
    for p in Paciente.objects.filter(clinica=clinica).exclude(telefono=""):
        if _solo_digitos(p.telefono).endswith(suf):
            return True
    return False


def _clinica_por_token(token):
    if not token:
        return None
    return Clinica.objects.filter(token_captacion=token, activo=True).first()


def _agregar_nota(lead, texto):
    if not texto:
        return
    extra = f"[{timezone.localtime():%d/%m %H:%M}] {texto}"
    lead.notas = (lead.notas + "\n" + extra).strip() if lead.notas else extra
    lead.save(update_fields=["notas"])


def _urls(token):
    return {
        "token": token,
        "path_web": f"/api/captacion/{token}/",
        "path_whatsapp": f"/api/captacion/whatsapp/{token}/",
    }


# --- Endpoints autenticados (configuración) ---

class CaptacionConfigView(APIView):
    """Devuelve el token y las rutas para conectar la web / Evolution."""

    def get(self, request):
        clinica = get_clinica_actual()
        if clinica is None:
            return Response({"detail": "Sin clínica en contexto."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_urls(clinica.asegurar_token_captacion()))


class RegenerarTokenView(APIView):
    """Genera un token nuevo (invalida las URLs anteriores). Solo admin."""

    def post(self, request):
        from usuarios.models import Usuario

        if getattr(request.user, "rol", None) != Usuario.Rol.ADMIN:
            return Response({"detail": "Solo un administrador puede regenerar el token."},
                            status=status.HTTP_403_FORBIDDEN)
        clinica = get_clinica_actual()
        if clinica is None:
            return Response({"detail": "Sin clínica en contexto."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_urls(clinica.regenerar_token_captacion()))


# --- Endpoints públicos (ingreso) ---

class _IntakeBase(APIView):
    authentication_classes = []          # público: sin sesión ni CSRF
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "captacion"


class IntakeWebView(_IntakeBase):
    """Ingreso de un lead desde web / campañas / Zapier. Protegido por el token."""

    def post(self, request, token):
        clinica = _clinica_por_token(token)
        if clinica is None:
            return Response({"detail": "Token inválido."}, status=status.HTTP_404_NOT_FOUND)

        d = request.data if isinstance(request.data, dict) else {}
        nombre = str(d.get("nombre") or "").strip()[:200]
        telefono = str(d.get("telefono") or d.get("tel") or "").strip()[:40]
        if not nombre and not telefono:
            return Response({"detail": "Falta el nombre o el teléfono."}, status=status.HTTP_400_BAD_REQUEST)
        nombre = nombre or "Lead sin nombre"

        fuente = str(d.get("fuente") or "").strip().lower()
        if fuente not in FUENTES_VALIDAS:
            fuente = Lead.Fuente.WEB
        mensaje = str(d.get("mensaje") or d.get("notas") or "").strip()

        existente = _lead_existente(clinica, telefono) if telefono else None
        if existente:
            _agregar_nota(existente, f"Volvió a entrar por {fuente}." + (f" {mensaje}" if mensaje else ""))
            return Response({"ok": True, "duplicado": True, "lead_id": existente.id})

        lead = Lead.objects.create(
            clinica=clinica,
            nombre=nombre,
            telefono=telefono,
            fuente=fuente,
            es_pauta=bool(d.get("es_pauta")),
            campania=str(d.get("campania") or d.get("campaña") or "").strip()[:120],
            especialidad=str(d.get("especialidad") or "").strip()[:120],
            notas=mensaje,
            estado=Lead.Estado.NUEVO,
        )
        return Response({"ok": True, "duplicado": False, "lead_id": lead.id}, status=status.HTTP_201_CREATED)


def _parse_evolution(payload):
    """Extrae (numero, texto, nombre) de un evento MESSAGES_UPSERT de Evolution.
    Devuelve numero=None cuando hay que ignorar (saliente, grupo, sin número)."""
    if not isinstance(payload, dict):
        return None, "", ""
    data = payload.get("data")
    if isinstance(data, list):
        data = data[0] if data else {}
    if not isinstance(data, dict):
        return None, "", ""
    key = data.get("key") or {}
    if key.get("fromMe"):
        return None, "", ""  # mensaje saliente: no es un lead
    jid = key.get("remoteJid") or ""
    if "@g.us" in jid:
        return None, "", ""  # grupo: ignorar
    numero = jid.split("@")[0].split(":")[0]
    msg = data.get("message") or {}
    texto = (
        msg.get("conversation")
        or (msg.get("extendedTextMessage") or {}).get("text")
        or (msg.get("imageMessage") or {}).get("caption")
        or (msg.get("videoMessage") or {}).get("caption")
        or ""
    )
    return numero, str(texto).strip(), str(data.get("pushName") or "").strip()


class IntakeWhatsappView(_IntakeBase):
    """Webhook de Evolution: registra como lead el primer mensaje de un número
    desconocido. Siempre responde 200 para que Evolution no reintente."""

    def post(self, request, token):
        clinica = _clinica_por_token(token)
        if clinica is None:
            return Response({"detail": "Token inválido."}, status=status.HTTP_404_NOT_FOUND)

        numero, texto, nombre = _parse_evolution(request.data)
        if not numero:
            return Response({"ok": True, "ignorado": "evento_no_aplica"})
        if _es_paciente(clinica, numero):
            return Response({"ok": True, "ignorado": "ya_es_paciente"})

        existente = _lead_existente(clinica, numero, dias=60)
        if existente:
            _agregar_nota(existente, f"WhatsApp: {texto}" if texto else "Volvió a escribir por WhatsApp.")
            return Response({"ok": True, "duplicado": True, "lead_id": existente.id})

        lead = Lead.objects.create(
            clinica=clinica,
            nombre=nombre[:200] or f"WhatsApp {numero[-9:]}",
            telefono=numero,
            fuente=Lead.Fuente.WHATSAPP,
            notas=texto,
            estado=Lead.Estado.NUEVO,
        )
        return Response({"ok": True, "duplicado": False, "lead_id": lead.id}, status=status.HTTP_201_CREATED)
