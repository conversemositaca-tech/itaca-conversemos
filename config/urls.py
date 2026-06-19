"""Rutas del proyecto. La API vive bajo /api/."""
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import TemplateView
from rest_framework.routers import DefaultRouter

from core.gerencia import ClinicaConfigView, GerenciaResumenView, HoyResumenView
from core.metricas import MetricaMensualViewSet
from core.ocupacion import OcupacionView
from core.reportes import ReporteSemanalViewSet
from finanzas.api import CajaView, CobroViewSet, EgresoViewSet, ServicioViewSet
from leads.api import AnuncioViewSet, LeadViewSet
from leads.captacion import (
    CaptacionConfigView,
    IntakeWebView,
    IntakeWhatsappView,
    RegenerarTokenView,
)
from mensajes.api import MensajeViewSet
from pacientes.api import AdjuntoViewSet, CitaViewSet, PacienteViewSet
from usuarios.api import (
    CambiarPasswordView,
    LoginView,
    LogoutView,
    MedicosView,
    MeView,
    ProfesionalViewSet,
    UsuarioViewSet,
)

router = DefaultRouter()
router.register(r"pacientes", PacienteViewSet, basename="paciente")
router.register(r"citas", CitaViewSet, basename="cita")
router.register(r"adjuntos", AdjuntoViewSet, basename="adjunto")
router.register(r"servicios", ServicioViewSet, basename="servicio")
router.register(r"cobros", CobroViewSet, basename="cobro")
router.register(r"egresos", EgresoViewSet, basename="egreso")
router.register(r"usuarios", UsuarioViewSet, basename="usuario")
router.register(r"profesionales", ProfesionalViewSet, basename="profesional")
router.register(r"metricas", MetricaMensualViewSet, basename="metrica")
router.register(r"reportes-semanales", ReporteSemanalViewSet, basename="reporte-semanal")
router.register(r"mensajes", MensajeViewSet, basename="mensaje")
router.register(r"leads", LeadViewSet, basename="lead")
router.register(r"anuncios", AnuncioViewSet, basename="anuncio")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/login/", LoginView.as_view(), name="login"),
    path("api/auth/logout/", LogoutView.as_view(), name="logout"),
    path("api/auth/me/", MeView.as_view(), name="me"),
    path("api/auth/cambiar-password/", CambiarPasswordView.as_view(), name="cambiar-password"),
    path("api/medicos/", MedicosView.as_view(), name="medicos"),
    path("api/hoy/", HoyResumenView.as_view(), name="hoy-resumen"),
    path("api/clinica/", ClinicaConfigView.as_view(), name="clinica-config"),
    path("api/gerencia/resumen/", GerenciaResumenView.as_view(), name="gerencia-resumen"),
    path("api/finanzas/caja/", CajaView.as_view(), name="finanzas-caja"),
    path("api/ocupacion/", OcupacionView.as_view(), name="ocupacion"),
    # Captación de leads. Las rutas específicas van ANTES del comodín <token>.
    path("api/captacion/config/", CaptacionConfigView.as_view(), name="captacion-config"),
    path("api/captacion/regenerar/", RegenerarTokenView.as_view(), name="captacion-regenerar"),
    path("api/captacion/whatsapp/<str:token>/", IntakeWhatsappView.as_view(), name="captacion-whatsapp"),
    path("api/captacion/<str:token>/", IntakeWebView.as_view(), name="captacion-web"),
    path("api/", include(router.urls)),
    # Catch-all: cualquier otra ruta sirve la app React (index.html). En producción
    # Django entrega el SPA; en desarrollo el SPA lo sirve Vite (5173), no Django.
    re_path(r"^(?!api/|admin/|static/|media/).*$",
            TemplateView.as_view(template_name="index.html"), name="spa"),
]
