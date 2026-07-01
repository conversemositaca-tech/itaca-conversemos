from django.contrib.auth import authenticate, login, logout
from django.http import FileResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.tenant import get_clinica_actual

from .models import DocumentoLegal, Profesional, Usuario
from .serializers import DocumentoLegalSerializer, ProfesionalSerializer, UsuarioSerializer


class EsAdmin(BasePermission):
    message = "Solo un administrador puede gestionar el equipo."

    def has_permission(self, request, view):
        return getattr(request.user, "rol", None) == Usuario.Rol.ADMIN


def datos_usuario(user):
    """Forma del usuario que consume el frontend (incluye clínica y rol)."""
    clinica = user.clinica
    return {
        "id": user.id,
        "email": user.email,
        "nombre": user.nombre or user.email,
        "rol": user.rol,
        "rol_label": user.get_rol_display(),
        "especialidad": user.especialidad,
        "clinica": (
            {"nombre": clinica.nombre, "ciudad": clinica.ciudad} if clinica else None
        ),
        # El perfil del pie de la barra lateral es el propio usuario logueado.
        "profesional": {"nombre": user.nombre or user.email, "especialidad": user.especialidad},
    }


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        password = request.data.get("password") or ""
        user = authenticate(request, username=email, password=password)
        if user is None:
            return Response(
                {"detail": "Correo o contraseña incorrectos."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if user.clinica_id is None and not user.is_superuser:
            return Response(
                {"detail": "Tu usuario no está asignado a ninguna clínica."},
                status=status.HTTP_403_FORBIDDEN,
            )
        login(request, user)
        return Response(datos_usuario(user))


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MedicosView(APIView):
    """Lista de psicólogos con los que se puede agendar: solo los que tienen
    ficha ACTIVA en el directorio (los que atienden hoy), con su sede.

    Se ordena por nombre y se devuelve el id del Usuario (que es lo que guardan
    las citas en el campo `medico`)."""

    def get(self, request):
        from core.tenant import get_clinica_actual

        from .models import Profesional, Usuario

        clinica = get_clinica_actual()
        fichas = (
            Profesional.objects.filter(
                clinica=clinica, activo=True, usuario__isnull=False,
                usuario__rol=Usuario.Rol.MEDICO, usuario__is_active=True,
            )
            .select_related("usuario")
            .order_by("usuario__nombre")
        )
        return Response([
            {
                "id": f.usuario_id,
                "nombre": f.usuario.nombre or str(f.usuario),
                "especialidad": f.usuario.especialidad,
                "sede": f.sede,
                "horario": f.horario_semanal or {},
            }
            for f in fichas
        ])


class UsuarioViewSet(viewsets.ModelViewSet):
    """Gestión del equipo de la clínica (solo admin). Crear, editar rol/especialidad,
    activar/desactivar y resetear contraseña. No se borran: se desactivan."""

    serializer_class = UsuarioSerializer
    permission_classes = [IsAuthenticated, EsAdmin]

    def get_queryset(self):
        return (
            Usuario.objects.filter(clinica=get_clinica_actual(), is_superuser=False)
            .order_by("nombre", "email")
        )

    def create(self, request, *args, **kwargs):
        d = request.data
        email = (d.get("email") or "").strip().lower()
        if not email:
            return Response({"detail": "El correo es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)
        if Usuario.objects.filter(email=email).exists():
            return Response({"detail": "Ya existe un usuario con ese correo."}, status=status.HTTP_400_BAD_REQUEST)
        password = d.get("password") or ""
        if len(password) < 6:
            return Response({"detail": "La contraseña debe tener al menos 6 caracteres."}, status=status.HTTP_400_BAD_REQUEST)
        rol = d.get("rol") if d.get("rol") in dict(Usuario.Rol.choices) else Usuario.Rol.ASISTENTE
        user = Usuario.objects.create_user(
            email=email, password=password, clinica=get_clinica_actual(),
            nombre=(d.get("nombre") or "").strip(), rol=rol,
            telefono=(d.get("telefono") or "").strip(),
            especialidad=(d.get("especialidad") or "").strip(), is_active=True,
        )
        return Response(UsuarioSerializer(user).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        user = self.get_object()
        if user == request.user:
            quita_admin = request.data.get("rol") and request.data.get("rol") != Usuario.Rol.ADMIN
            se_desactiva = request.data.get("is_active") is False
            if quita_admin or se_desactiva:
                return Response({"detail": "No puedes cambiar tu propio rol ni desactivarte."}, status=status.HTTP_400_BAD_REQUEST)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        if user == request.user:
            return Response({"detail": "No puedes desactivarte a ti mismo."}, status=status.HTTP_400_BAD_REQUEST)
        user.is_active = False
        user.save(update_fields=["is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def password(self, request, pk=None):
        user = self.get_object()
        nueva = request.data.get("password") or ""
        if len(nueva) < 6:
            return Response({"detail": "La contraseña debe tener al menos 6 caracteres."}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(nueva)
        user.save(update_fields=["password"])
        return Response({"ok": True})


class CambiarPasswordView(APIView):
    """Cualquier usuario logueado cambia SU PROPIA contraseña (pide la actual)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        actual = request.data.get("actual") or ""
        nueva = request.data.get("nueva") or ""
        if not request.user.check_password(actual):
            return Response({"detail": "Tu contraseña actual no es correcta."}, status=status.HTTP_400_BAD_REQUEST)
        if len(nueva) < 6:
            return Response({"detail": "La nueva contraseña debe tener al menos 6 caracteres."}, status=status.HTTP_400_BAD_REQUEST)
        request.user.set_password(nueva)
        request.user.save(update_fields=["password"])
        # Mantener la sesión viva tras cambiar la contraseña.
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(request, request.user)
        return Response({"ok": True})


@method_decorator(ensure_csrf_cookie, name="dispatch")
class MeView(APIView):
    """Devuelve el usuario logueado. También fija la cookie CSRF para que el
    frontend pueda enviar el token en las peticiones que modifican datos."""

    permission_classes = [AllowAny]

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({"autenticado": False})
        return Response({"autenticado": True, **datos_usuario(request.user)})


class ProfesionalViewSet(viewsets.ModelViewSet):
    """Directorio de profesionales (psicólogos). Lo VEN todos los del equipo;
    crear/editar/eliminar y subir foto es solo del gerente (admin)."""

    serializer_class = ProfesionalSerializer

    def get_queryset(self):
        return Profesional.objects.del_tenant_actual().order_by("orden", "nombre")

    def _solo_admin(self):
        if getattr(self.request.user, "rol", None) != Usuario.Rol.ADMIN:
            raise PermissionDenied("Solo el gerente (admin) puede editar el directorio de profesionales.")

    def perform_create(self, serializer):
        self._solo_admin()
        serializer.save(clinica=get_clinica_actual())

    def perform_update(self, serializer):
        self._solo_admin()
        serializer.save()

    def perform_destroy(self, instance):
        self._solo_admin()
        if instance.foto:
            instance.foto.delete(save=False)
        instance.delete()

    @action(detail=True, methods=["get", "post"])
    def foto(self, request, pk=None):
        prof = self.get_object()
        if request.method == "POST":
            self._solo_admin()
            archivo = request.FILES.get("foto")
            if archivo is None:
                return Response({"detail": "No se recibió ninguna imagen."}, status=status.HTTP_400_BAD_REQUEST)
            if archivo.size > 8 * 1024 * 1024:
                return Response({"detail": "La imagen supera el límite de 8 MB."}, status=status.HTTP_400_BAD_REQUEST)
            prof.foto = archivo
            prof.save(update_fields=["foto"])
            return Response(ProfesionalSerializer(prof).data)
        # GET: sirve la imagen para mostrarla (inline)
        if not prof.foto:
            return Response({"detail": "Sin foto."}, status=status.HTTP_404_NOT_FOUND)
        return FileResponse(prof.foto.open("rb"))


class DocumentoLegalViewSet(viewsets.ModelViewSet):
    """Documentos legales (contratos/adendas) de un profesional. Solo admin.
    Subida con multipart: campos profesional, tipo, fecha, descripcion, archivo."""

    serializer_class = DocumentoLegalSerializer

    def _solo_admin(self):
        if getattr(self.request.user, "rol", None) != Usuario.Rol.ADMIN:
            raise PermissionDenied("Solo el gerente (admin) puede gestionar documentos legales.")

    def get_queryset(self):
        qs = DocumentoLegal.objects.del_tenant_actual().order_by("-fecha", "-id")
        prof = self.request.query_params.get("profesional")
        if prof:
            qs = qs.filter(profesional_id=prof)
        return qs

    def create(self, request, *args, **kwargs):
        self._solo_admin()
        clinica = get_clinica_actual()
        prof = Profesional.objects.del_tenant_actual().filter(pk=request.data.get("profesional")).first()
        if prof is None:
            return Response({"detail": "Profesional no encontrado."}, status=status.HTTP_400_BAD_REQUEST)
        archivo = request.FILES.get("archivo")
        if archivo is not None and archivo.size > 15 * 1024 * 1024:
            return Response({"detail": "El archivo supera el límite de 15 MB."}, status=status.HTTP_400_BAD_REQUEST)
        tipo = request.data.get("tipo") if request.data.get("tipo") in dict(DocumentoLegal.Tipo.choices) else DocumentoLegal.Tipo.CONTRATO
        doc = DocumentoLegal.objects.create(
            clinica=clinica, profesional=prof, tipo=tipo,
            fecha=(request.data.get("fecha") or None),
            descripcion=(request.data.get("descripcion") or "").strip()[:200],
            archivo=archivo,
        )
        return Response(DocumentoLegalSerializer(doc).data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        self._solo_admin()
        if instance.archivo:
            instance.archivo.delete(save=False)
        instance.delete()

    @action(detail=True, methods=["get"])
    def archivo(self, request, pk=None):
        doc = self.get_object()
        if not doc.archivo:
            return Response({"detail": "Sin archivo."}, status=status.HTTP_404_NOT_FOUND)
        return FileResponse(doc.archivo.open("rb"))
