from django.contrib.auth import authenticate, login, logout
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.tenant import get_clinica_actual

from .models import Usuario
from .serializers import UsuarioSerializer


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
    """Lista de médicos de la clínica activa (para asignar como 'doctor de la pauta')."""

    def get(self, request):
        from core.tenant import get_clinica_actual

        from .models import Usuario

        clinica = get_clinica_actual()
        medicos = Usuario.objects.filter(
            clinica=clinica, rol=Usuario.Rol.MEDICO, is_active=True
        ).order_by("nombre")
        return Response([
            {"id": m.id, "nombre": m.nombre or str(m), "especialidad": m.especialidad}
            for m in medicos
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
