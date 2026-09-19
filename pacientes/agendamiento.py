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
from leads import atribucion
from leads import captacion
from leads import identidad
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


def _match_paciente(clinica, documento, telefono, nombre="", sede=""):
    """La ficha que es SIN DUDA de quien reserva, o None.

    Antes bastaba con que el teléfono terminara igual que el de CUALQUIER ficha
    de la clínica para darla por suya. Con el número de una madre que gestiona
    la atención de dos hijos, eso colgaba la reserva de la persona equivocada —y
    de paso saltaba el registro de captación (ver `leads.identidad`).
    """
    return identidad.ficha_que_calza(
        clinica, nombre=nombre, telefono=telefono, sede=sede, documento=documento)


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
            for s in Servicio.objects.filter(clinica=clinica, activo=True, reservable_web=True).order_by("nombre")
        ]
        return Response({
            "clinica": clinica.nombre,
            "hay_agenda": bool(profs),
            "servicios": servicios,
            "profesionales": [{
                "id": p.id,
                "nombre": p.nombre,
                "titulo": p.titulo,
                # N° de colegiatura (C.Ps.P.): el sitio lo muestra bajo cada
                # psicólogo y es lo primero que mira quien desconfía.
                "colegiatura": p.colegiatura,
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
                # Video de presentación, ya convertido a enlace de reproductor.
                # Va resuelto desde aquí para que la landing y la página de
                # psicólogos no interpreten el enlace cada una a su manera.
                "video": p.video_embed_url,
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
        # Un movil peruano tiene 9 digitos. Con menos, el numero no sirve para
        # reconocer a quien vuelve: se le abriria una ficha nueva cada vez y su
        # historia quedaria partida. Antes se aceptaban desde 6.
        if not nombre or len(_solo_digitos(telefono)) < identidad.MIN_DIGITOS_TELEFONO:
            return Response(
                {"detail": "Necesitamos tu nombre y un celular de 9 dígitos."},
                status=status.HTTP_400_BAD_REQUEST)
        documento = _solo_digitos(d.get("documento"))[:12]
        email = str(d.get("email") or "").strip()[:200]
        servicio = str(d.get("servicio") or "").strip()[:120]
        modalidad = (Cita.Modalidad.VIRTUAL
                     if str(d.get("modalidad") or "").strip().lower().startswith("virt")
                     else Cita.Modalidad.PRESENCIAL)
        mensaje = str(d.get("mensaje") or "").strip()[:1000]
        # De dónde venía quien reservó (campaña, anuncio, página de entrada).
        # Es opcional: si no llega nada, la reserva funciona igual que siempre.
        origen = atribucion.campos_de_lead(d.get("atribucion"))
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

            paciente = _match_paciente(clinica, documento, telefono,
                                       nombre=nombre, sede=prof.sede)
            conocido = paciente is not None
            if not conocido:
                paciente = Paciente.objects.create(
                    clinica=clinica, nombre=nombre, telefono=telefono, email=email, sede=prof.sede,
                    numero_documento=documento,
                    tipo_documento=("ruc" if len(documento) == 11 else "dni") if documento else "dni",
                    # Reservó por la web, todavía no vino: la ficha existe para
                    # sostener la cita, pero no cuenta como paciente hasta que
                    # inicie proceso (lo confirma el DP-01 de la consulta).
                    provisional=True)

            # A quien ya conocemos no hay que confirmarle nada: su cita entra
            # agendada. La de alguien nuevo queda pendiente de que Coordinación
            # la confirme, como hasta ahora.
            cita = Cita.objects.create(
                clinica=clinica, paciente=paciente, medico=usuario, inicio=inicio,
                especialidad=servicio, categoria=categoria, sede=prof.sede,
                estado=Cita.Estado.AGENDADA if conocido else Cita.Estado.PENDIENTE,
                modalidad=modalidad, motivo_consulta=mensaje, agendado_web=True,
                notas=("Reserva online." if conocido
                       else "Reserva online — paciente nuevo, confirmar.") + nota_ayuda)

            # El lead se crea SIEMPRE, también para quien ya tenía ficha: es el
            # registro de CAPTACIÓN de esta reserva, no un registro de identidad.
            # Sin él, la consulta no existía para Marketing ni para el reporte de
            # pauta, y Coordinación terminaba borrando la reserva y volviéndola a
            # crear a mano para que el sistema la contara.
            lead = Lead.objects.create(
                clinica=clinica, nombre=nombre, telefono=telefono, email=email, sede=prof.sede,
                fuente=Lead.Fuente.WEB, agendo_consulta=True,
                fecha_consulta=timezone.localtime(inicio).date(), especialidad=servicio,
                medico=usuario, estado=Lead.Estado.AGENDADO, motivo_consulta=mensaje,
                paciente=paciente, cita=cita,
                notas="Reserva online." if conocido else "Reserva online (paciente nuevo).",
                **origen)
            # Con `cita` enlazada desde el principio, editar el lead en Marketing
            # MUEVE esta reserva en vez de crear una segunda cita.
            cita.notas = f"{cita.notas} Lead #{lead.id}."
            cita.save(update_fields=["notas"])
            return Response({
                "ok": True,
                "tipo": "existente" if conocido else "nuevo",
                "estado": "agendada" if conocido else "pendiente",
                "profesional": prof.nombre,
                "inicio_label": timezone.localtime(inicio).strftime("%d/%m/%Y a las %H:%M"),
            }, status=status.HTTP_201_CREATED)


# ── Rama "ayúdenme a encontrar al indicado" ──────────────────────────────────
# Esta vía NO muestra psicólogos ni reserva horario: recoge preferencias y deja
# un lead para que coordinación llame y asigne. Antes compartía pantalla con
# "quiero elegir yo" y terminaba listando a todo el equipo — justo lo que viene
# a evitar quien entra por aquí porque no sabe a quién elegir.

# Preferencia horaria. Se guarda como etiqueta y no como rango de horas: quien
# llama necesita saber "prefiere tarde", no un intervalo que todavía nadie ha
# cuadrado con la agenda del psicólogo que aún no se le asigna.
_TURNOS = {
    "manana": "Mañana",
    "mañana": "Mañana",
    "tarde": "Tarde",
    "noche": "Noche",
}

# Qué vino a pedir. La Brújula es una sesión de orientación de 45 minutos que no
# da cualquiera del equipo, así que esta vía solo recoge el interés: la
# coordinadora confirma con quien la atiende antes de dar fecha.
_TIPOS = {
    "consulta": "Primera consulta",
    "brujula": "Sesión Brújula",
}

# Población elegida -> tipo de servicio del lead, para que estas solicitudes
# cuenten en los reportes de Marketing junto con las demás y no caigan en "otro".
_TIPO_SERVICIO_MAP = {
    "adultos": Lead.TipoServicio.ADULTOS,
    "ninos": Lead.TipoServicio.NINOS,
    "niños": Lead.TipoServicio.NINOS,
    "adolescentes": Lead.TipoServicio.ADOLESCENTES,
    "parejas": Lead.TipoServicio.PAREJA,
}


class AgendamientoSolicitarView(_PublicBase):
    """POST /api/agendamiento/<token>/solicitar/ → deja un lead SIN cita.

    body: {sede, categoria, turno, modalidad, tipo, nombre, telefono, email,
           mensaje, atribucion}

    A propósito no crea Cita ni Paciente: nadie eligió horario todavía. Una cita
    tentativa obligaría a Coordinación a borrarla al asignar al psicólogo de
    verdad, y mientras tanto ocuparía un hueco real en la agenda de alguien que
    ni siquiera fue elegido.
    """

    def post(self, request, token):
        clinica = _clinica_por_token(token)
        if clinica is None:
            return Response({"detail": "Enlace no válido."}, status=status.HTTP_404_NOT_FOUND)
        d = request.data if isinstance(request.data, dict) else {}

        nombre = str(d.get("nombre") or "").strip()[:200]
        telefono = str(d.get("telefono") or "").strip()[:40]
        # Mismo mínimo que al reservar: con menos de 9 dígitos el número no sirve
        # para devolver la llamada, que es todo lo que esta vía promete.
        if not nombre or len(_solo_digitos(telefono)) < identidad.MIN_DIGITOS_TELEFONO:
            return Response({"detail": "Necesitamos tu nombre y un celular de 9 dígitos."},
                            status=status.HTTP_400_BAD_REQUEST)

        sede = str(d.get("sede") or "").strip().lower()
        if sede not in dict(Lead.Sede.choices):
            return Response({"detail": "Elige una sede."}, status=status.HTTP_400_BAD_REQUEST)

        categoria = str(d.get("categoria") or "").strip().lower()
        turno = _TURNOS.get(str(d.get("turno") or "").strip().lower(), "")
        modalidad = ("virtual" if str(d.get("modalidad") or "").strip().lower().startswith("virt")
                     else "presencial")
        tipo_key = "brujula" if str(d.get("tipo") or "").strip().lower() == "brujula" else "consulta"
        tipo = _TIPOS[tipo_key]

        email = str(d.get("email") or "").strip()[:200]
        mensaje = str(d.get("mensaje") or "").strip()[:1000]
        origen = atribucion.campos_de_lead(d.get("atribucion"))

        # Lo que coordinación necesita leer de un vistazo antes de marcar.
        preferencias = " · ".join(x for x in [
            f"Pidió: {tipo}",
            f"Para: {categoria}" if categoria else "",
            f"Turno: {turno}" if turno else "",
            f"Modalidad: {modalidad.capitalize()}",
        ] if x)

        # Quien ya escribió hace poco no se duplica: se le suma la nota a su lead
        # abierto. Si no, la misma persona aparece dos veces en la bandeja y dos
        # coordinadoras terminan llamándola.
        existente = captacion._lead_existente(clinica, telefono)
        if existente:
            captacion._agregar_nota(existente, f"Volvió a solicitar por la web. {preferencias}.")
            return Response({"ok": True, "duplicado": True, "tipo": tipo_key})

        Lead.objects.create(
            clinica=clinica, nombre=nombre, telefono=telefono, email=email, sede=sede,
            fuente=Lead.Fuente.WEB,
            # No agendó nada: vino precisamente a que le ayudemos a elegir.
            agendo_consulta=False,
            estado=Lead.Estado.NUEVO,
            especialidad=tipo,
            tipo_servicio=_TIPO_SERVICIO_MAP.get(categoria, Lead.TipoServicio.OTRO),
            modalidad_consulta=modalidad,
            motivo_consulta=mensaje,
            notas=f"Solicitud web — pidió ayuda para elegir psicólogo/a. {preferencias}.",
            **origen)
        return Response({"ok": True, "duplicado": False, "tipo": tipo_key},
                        status=status.HTTP_201_CREATED)
