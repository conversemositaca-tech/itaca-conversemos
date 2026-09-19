"""Datos públicos del sitio web (sin login y sin token en la URL).

Las páginas públicas —inicio, quiénes somos, psicólogos, terapias, preguntas—
se arman con estos datos, así que el equipo que ya está en el sistema es el
que se ve en la web: si entra o sale un psicólogo, la web cambia sola.

Multitenant (Ley 29733): sin token no hay clínica en la URL, así que la clínica
del sitio se declara en `SITIO_CLINICA_TOKEN`. Solo si hay UNA sola clínica
activa se resuelve sola, que es el caso de desarrollo. Nunca se adivina entre
varias: antes se devuelve 404.

Lo que se publica es lo que el propio equipo puso para mostrarse (nombre,
título, colegiatura, sede, enfoque, frase, foto). Nada de datos de pacientes.
"""
from django.conf import settings
from django.http import FileResponse, Http404

from core import rangos
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Clinica
from finanzas.models import Servicio
from pacientes.agendamiento import _profesionales_agendables
from usuarios.models import Profesional


def clinica_del_sitio():
    """Clínica cuyo sitio público servimos, o None si no se puede saber."""
    token = (getattr(settings, "SITIO_CLINICA_TOKEN", "") or "").strip()
    if token:
        return Clinica.objects.filter(token_captacion=token, activo=True).first()
    activas = list(Clinica.objects.filter(activo=True)[:2])
    return activas[0] if len(activas) == 1 else None


def _publicables(clinica):
    """Equipo que se muestra en la web: fichas activas con algo que mostrar.

    Se incluye también a quien no tiene agenda en línea (el sitio presenta al
    equipo completo, no solo a quien se puede reservar hoy); esas fichas van
    marcadas con `agendable: False` para que la web ofrezca escribir por WhatsApp
    en vez de un horario que no existe.
    """
    fichas = (Profesional.objects.filter(clinica=clinica, activo=True)
              .select_related("usuario").order_by("orden", "nombre"))
    return [p for p in fichas if (p.foto or p.frase or p.enfoque or p.video)]


class _SitioBase(APIView):
    authentication_classes = []          # público: sin sesión ni CSRF
    permission_classes = [AllowAny]


class SitioInfoView(_SitioBase):
    """GET /api/sitio/ → lo que necesitan las páginas públicas del sitio."""

    def get(self, request):
        clinica = clinica_del_sitio()
        if clinica is None:
            return Response({"detail": "Sitio no configurado."}, status=404)

        agendables = {p.id for p in _profesionales_agendables(clinica)}
        equipo = _publicables(clinica)
        servicios = [
            {"nombre": s.nombre, "especialidad": s.especialidad, "precio": str(s.precio)}
            for s in (Servicio.objects.filter(clinica=clinica, activo=True, reservable_web=True)
                      .order_by("precio", "nombre"))
        ]
        return Response({
            "clinica": clinica.nombre,
            # El mismo enlace público que ya se reparte: con él la web arma el
            # botón de reservar sin que nadie tenga que pegar la URL a mano.
            "token_agenda": clinica.token_captacion or "",
            "servicios": servicios,
            "equipo": [{
                "id": p.id,
                "nombre": p.nombre,
                "titulo": p.titulo,
                "colegiatura": p.colegiatura,
                "sede": p.sede,
                "sede_label": p.get_sede_display(),
                "modalidad": p.modalidad,
                "modalidad_label": p.get_modalidad_display(),
                "frase": p.frase,
                "enfoque": (p.enfoque or "")[:600],
                "poblaciones": p.poblaciones,
                "problematicas": (p.problematicas or "")[:800],
                "formacion": (p.formacion or "")[:800],
                "trayectoria": (p.trayectoria or "")[:800],
                "agendable": p.id in agendables,
                "foto": (request.build_absolute_uri(f"/api/sitio/foto/{p.id}/") if p.foto else ""),
                # El video se sirve por un endpoint propio que entiende Range
                # (Django no publica /media). Sin Range, iPhone no reproduce.
                "video": (request.build_absolute_uri(f"/api/sitio/video/{p.id}/") if p.video else ""),
            } for p in equipo],
        })


class SitioVideoView(_SitioBase):
    """GET /api/sitio/video/<pk>/ → video de presentación del psicólogo.

    Responde por tramos (`Range`). Safari en iPhone pide los primeros bytes para
    leer la cabecera del archivo y abandona si le llega el archivo entero de
    golpe: sin esto el reproductor se queda en negro en medio iPhone del Perú.
    """

    def get(self, request, pk):
        clinica = clinica_del_sitio()
        if clinica is None:
            raise Http404
        prof = Profesional.objects.filter(clinica=clinica, id=pk, activo=True).first()
        if prof is None or not prof.video:
            raise Http404
        try:
            return rangos.respuesta_de_archivo(request, prof.video)
        except (FileNotFoundError, ValueError, OSError):
            raise Http404


class SitioFotoView(_SitioBase):
    """GET /api/sitio/foto/<pk>/ → foto del psicólogo para la web.

    Django no publica /media (los adjuntos clínicos son privados · Ley 29733);
    la foto de perfil sí es pública y sale solo por aquí, acotada a la clínica
    del sitio. Sin throttle: una página carga quince de estas.
    """

    def get(self, request, pk):
        clinica = clinica_del_sitio()
        if clinica is None:
            raise Http404
        prof = Profesional.objects.filter(clinica=clinica, id=pk, activo=True).first()
        if prof is None or not prof.foto:
            raise Http404
        try:
            return FileResponse(prof.foto.open("rb"))
        except (FileNotFoundError, ValueError, OSError):
            raise Http404
