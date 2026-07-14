"""Auto-agendamiento público (sin login), protegido por el token de la clínica.

El paciente abre /agendar/<token>, elige psicólogo y un horario libre y reserva:
- Si YA es paciente (match por documento o teléfono): la cita entra directo a la
  agenda (estado "agendada").
- Si es NUEVO: se crea un Lead (captación, fuente web) + una cita TENTATIVA
  (estado "pendiente") para que coordinación la confirme.

Los horarios libres salen de `Profesional.horario_semanal` menos las citas ya
tomadas y los bloqueos de agenda. La clínica se resuelve por su token de captación
(no hay usuario logueado), por eso se fija `clinica=` explícitamente al crear todo
(aislamiento multitenant · Ley 29733).
"""
from datetime import datetime, time, timedelta

from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.models import Clinica
from finanzas.models import Servicio
from leads.models import Lead
from pacientes.models import BloqueoAgenda, Cita, Paciente
from usuarios.models import Profesional, Usuario


def _solo_digitos(s):
    return "".join(ch for ch in (s or "") if ch.isdigit())


# Categoría elegida en la rama "necesito ayuda" -> categoría clínica de la Cita.
_CAT_MAP = {
    "adultos": Cita.Categoria.ADULTOS,
    "ninos": Cita.Categoria.INFANTOJUVENIL,
    "niños": Cita.Categoria.INFANTOJUVENIL,
    "adolescentes": Cita.Categoria.INFANTOJUVENIL,
    "parejas": Cita.Categoria.PAREJAS,
}


def _clinica_por_token(token):
    if not token:
        return None
    return Clinica.objects.filter(token_captacion=token, activo=True).first()


def _parse_iso(s):
    """ISO '2026-07-15T15:00:00-05:00' -> datetime aware. None si no parsea."""
    s = (s or "").strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt


def _hkey(dt):
    """Clave por hora local (para comparar slot con cita/otro slot)."""
    return timezone.localtime(dt).strftime("%Y%m%d%H")


def _profesionales_agendables(clinica):
    """Psicólogos con cuenta de agenda y horario semanal configurado."""
    out = []
    for p in (Profesional.objects.filter(clinica=clinica, activo=True, usuario__isnull=False)
              .select_related("usuario").order_by("orden", "nombre")):
        if getattr(p.usuario, "rol", None) != Usuario.Rol.MEDICO:
            continue
        if not (p.horario_semanal or {}):
            continue
        out.append(p)
    return out


def _slots_libres(clinica, prof, dias=14, min_lead_min=30):
    """Lista [(date, [datetime aware, …]), …] de horas libres del profesional en los
    próximos `dias` días: su horario semanal menos citas tomadas y bloqueos."""
    usuario = prof.usuario
    horario = prof.horario_semanal or {}
    if usuario is None or not horario:
        return []
    tz = timezone.get_current_timezone()
    ahora = timezone.localtime()
    limite = ahora + timedelta(days=dias + 1)

    ocupadas = set()
    for ini in (Cita.objects.filter(clinica=clinica, medico=usuario, inicio__gte=ahora, inicio__lte=limite)
                .exclude(estado=Cita.Estado.CANCELADA).values_list("inicio", flat=True)):
        ocupadas.add(_hkey(ini))

    bloqueos = list(
        BloqueoAgenda.objects.filter(clinica=clinica, fin__gte=ahora, inicio__lte=limite)
        .filter(Q(medico=usuario) | Q(medico__isnull=True, sede=prof.sede))
        .values_list("inicio", "fin"))

    fuera = []
    for d in range(dias + 1):
        fecha = (ahora + timedelta(days=d)).date()
        key = str(fecha.weekday() + 1)  # 1=Lunes … 7=Domingo
        horas = horario.get(key) or []
        libres = []
        for h in sorted({int(x) for x in horas if str(x).strip().isdigit() and 0 <= int(x) <= 23}):
            inicio = timezone.make_aware(datetime.combine(fecha, time(h, 0)), tz)
            if inicio <= ahora + timedelta(minutes=min_lead_min):
                continue
            if _hkey(inicio) in ocupadas:
                continue
            fin_slot = inicio + timedelta(hours=1)
            if any(bi < fin_slot and inicio < bf for bi, bf in bloqueos):
                continue
            libres.append(inicio)
        if libres:
            fuera.append((fecha, libres))
    return fuera


def _match_paciente(clinica, documento, telefono):
    """Paciente existente por documento (exacto) o por los últimos 9 dígitos del tel."""
    doc = _solo_digitos(documento)
    if doc:
        p = Paciente.objects.filter(clinica=clinica, numero_documento=doc).first()
        if p:
            return p
    digs = _solo_digitos(telefono)
    if len(digs) >= 6:
        suf = digs[-9:]
        for p in Paciente.objects.filter(clinica=clinica).exclude(telefono=""):
            if _solo_digitos(p.telefono).endswith(suf):
                return p
    return None


class _PublicBase(APIView):
    authentication_classes = []          # público: sin sesión ni CSRF
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "captacion"


class AgendamientoInfoView(_PublicBase):
    """GET /api/agendamiento/<token>/ → datos para armar el formulario público."""

    def get(self, request, token):
        clinica = _clinica_por_token(token)
        if clinica is None:
            return Response({"detail": "Enlace no válido."}, status=status.HTTP_404_NOT_FOUND)
        profs = _profesionales_agendables(clinica)
        servicios = [
            {"nombre": s.nombre, "especialidad": s.especialidad, "precio": str(s.precio)}
            for s in Servicio.objects.filter(clinica=clinica, activo=True).order_by("nombre")
        ]
        return Response({
            "clinica": clinica.nombre,
            "hay_agenda": bool(profs),
            "servicios": servicios,
            "profesionales": [{
                "id": p.id,
                "nombre": p.nombre,
                "titulo": p.titulo,
                "sede": p.sede,
                "sede_label": p.get_sede_display(),
                "modalidad": p.modalidad,
                "modalidad_label": p.get_modalidad_display(),
                "enfoque": (p.enfoque or "")[:600],
                "poblaciones": p.poblaciones,
                "problematicas": (p.problematicas or "")[:800],
                "formacion": (p.formacion or "")[:800],
                "trayectoria": (p.trayectoria or "")[:800],
                "frase": p.frase,
                # La foto se sirve por un endpoint público propio (Django no publica /media).
                "foto": (request.build_absolute_uri(f"/api/agendamiento/{token}/foto/{p.id}/")
                         if p.foto else ""),
            } for p in profs],
        })


class AgendamientoFotoView(APIView):
    """GET /api/agendamiento/<token>/foto/<pk>/ → foto pública del psicólogo.

    Django no publica /media (los adjuntos clínicos son privados · Ley 29733), pero
    la foto de perfil del psicólogo SÍ es pública para la página de reservas. Se
    sirve solo por este endpoint, acotado por el token de la clínica. Sin throttle:
    se cargan varias imágenes por vista.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, token, pk):
        clinica = _clinica_por_token(token)
        if clinica is None:
            raise Http404
        prof = Profesional.objects.filter(clinica=clinica, id=pk, activo=True).first()
        if prof is None or not prof.foto:
            raise Http404
        try:
            return FileResponse(prof.foto.open("rb"))
        except (FileNotFoundError, ValueError, OSError):
            raise Http404


class AgendamientoSlotsView(_PublicBase):
    """GET /api/agendamiento/<token>/slots/?profesional=<id>&dias=14 → horas libres."""

    def get(self, request, token):
        clinica = _clinica_por_token(token)
        if clinica is None:
            return Response({"detail": "Enlace no válido."}, status=status.HTTP_404_NOT_FOUND)
        prof = (Profesional.objects.filter(clinica=clinica, id=request.query_params.get("profesional"), activo=True)
                .select_related("usuario").first())
        if prof is None or prof.usuario is None:
            return Response({"detail": "Psicólogo no disponible."}, status=status.HTTP_404_NOT_FOUND)
        try:
            dias = min(max(int(request.query_params.get("dias", 14)), 1), 30)
        except (TypeError, ValueError):
            dias = 14
        dias_out = [{
            "fecha": fecha.isoformat(),
            "slots": [{"inicio": s.isoformat(), "hora": timezone.localtime(s).strftime("%H:%M")} for s in libres],
        } for fecha, libres in _slots_libres(clinica, prof, dias)]
        return Response({"profesional": prof.nombre, "dias": dias_out})


class AgendamientoReservarView(_PublicBase):
    """POST /api/agendamiento/<token>/reservar/ → crea la cita (y el lead si es nuevo).
    body: {profesional_id, inicio, nombre, telefono, documento, email, servicio,
           modalidad, mensaje}."""

    def post(self, request, token):
        clinica = _clinica_por_token(token)
        if clinica is None:
            return Response({"detail": "Enlace no válido."}, status=status.HTTP_404_NOT_FOUND)
        d = request.data if isinstance(request.data, dict) else {}

        prof = (Profesional.objects.filter(clinica=clinica, id=d.get("profesional_id"), activo=True)
                .select_related("usuario").first())
        if prof is None or prof.usuario is None:
            return Response({"detail": "Ese psicólogo ya no está disponible."}, status=status.HTTP_400_BAD_REQUEST)

        inicio = _parse_iso(d.get("inicio"))
        if inicio is None:
            return Response({"detail": "El horario elegido no es válido."}, status=status.HTTP_400_BAD_REQUEST)

        nombre = str(d.get("nombre") or "").strip()[:200]
        telefono = str(d.get("telefono") or "").strip()[:40]
        if not nombre or len(_solo_digitos(telefono)) < 6:
            return Response({"detail": "Necesitamos tu nombre y un teléfono válido."},
                            status=status.HTTP_400_BAD_REQUEST)
        documento = _solo_digitos(d.get("documento"))[:12]
        email = str(d.get("email") or "").strip()[:200]
        servicio = str(d.get("servicio") or "").strip()[:120]
        modalidad = (Cita.Modalidad.VIRTUAL
                     if str(d.get("modalidad") or "").strip().lower().startswith("virt")
                     else Cita.Modalidad.PRESENCIAL)
        mensaje = str(d.get("mensaje") or "").strip()[:1000]
        categoria = _CAT_MAP.get(str(d.get("categoria") or "").strip().lower(), "")
        # El paciente pidió que el equipo le ayude a elegir el psicólogo ideal.
        ayuda = bool(d.get("ayuda"))
        nota_ayuda = " El consultante pidió ayuda para elegir psicólogo/a — verificar idoneidad." if ayuda else ""
        usuario = prof.usuario

        with transaction.atomic():
            # Revalidar que el slot siga libre (evita choques por reservas simultáneas).
            libres = {_hkey(s) for _f, ss in _slots_libres(clinica, prof) for s in ss}
            if _hkey(inicio) not in libres:
                return Response({"detail": "Justo tomaron ese horario. Elige otro, por favor."},
                                status=status.HTTP_409_CONFLICT)

            paciente = _match_paciente(clinica, documento, telefono)
            if paciente is not None:
                # Paciente existente → cita directa en la agenda.
                Cita.objects.create(
                    clinica=clinica, paciente=paciente, medico=usuario, inicio=inicio,
                    especialidad=servicio, categoria=categoria, estado=Cita.Estado.AGENDADA, sede=prof.sede,
                    modalidad=modalidad, motivo_consulta=mensaje, notas="Reserva online." + nota_ayuda)
                return Response({
                    "ok": True, "tipo": "existente", "estado": "agendada",
                    "profesional": prof.nombre,
                    "inicio_label": timezone.localtime(inicio).strftime("%d/%m/%Y a las %H:%M"),
                }, status=status.HTTP_201_CREATED)

            # Nuevo → lead (captación) + paciente mínimo + cita tentativa por confirmar.
            lead = Lead.objects.create(
                clinica=clinica, nombre=nombre, telefono=telefono, email=email, sede=prof.sede,
                fuente=Lead.Fuente.WEB, agendo_consulta=True,
                fecha_consulta=timezone.localtime(inicio).date(), especialidad=servicio,
                medico=usuario, estado=Lead.Estado.AGENDADO, motivo_consulta=mensaje,
                notas="Reserva online (paciente nuevo).")
            paciente = Paciente.objects.create(
                clinica=clinica, nombre=nombre, telefono=telefono, email=email, sede=prof.sede,
                numero_documento=documento,
                tipo_documento=("ruc" if len(documento) == 11 else "dni") if documento else "dni")
            lead.paciente = paciente
            lead.save(update_fields=["paciente"])
            Cita.objects.create(
                clinica=clinica, paciente=paciente, medico=usuario, inicio=inicio,
                especialidad=servicio, categoria=categoria, estado=Cita.Estado.PENDIENTE, sede=prof.sede,
                modalidad=modalidad, motivo_consulta=mensaje,
                notas=f"Reserva online — paciente nuevo, confirmar. Lead #{lead.id}.{nota_ayuda}")
            return Response({
                "ok": True, "tipo": "nuevo", "estado": "pendiente",
                "profesional": prof.nombre,
                "inicio_label": timezone.localtime(inicio).strftime("%d/%m/%Y a las %H:%M"),
            }, status=status.HTTP_201_CREATED)
