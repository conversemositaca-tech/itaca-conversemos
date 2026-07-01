"""Rutas del proyecto. La API vive bajo /api/."""
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import TemplateView
from rest_framework.routers import DefaultRouter

from core.buzon import SugerenciaViewSet
from core.recursos import RecursoViewSet
from core.gerencia import ClinicaConfigView, GerenciaResumenView, HoyResumenView
from core.integraciones import NotaVozView, PacientesBuscarView, PsicologoView
from core.metricas import MetricaMensualViewSet
from core.ocupacion import OcupacionView
from core.reportes import ReporteSemanalViewSet
from core.whatsapp_cloud import WhatsappConfigView, WhatsappWebhookView
from finanzas.api import (
    CajaView,
    CobroViewSet,
    EgresoViewSet,
    PaqueteViewSet,
    ServicioViewSet,
    SotoPruebaView,
    SotoResumenView,
)
from finanzas.liquidacion import LiquidacionView
from leads.api import AnuncioViewSet, LeadViewSet
from leads.captacion import (
    CaptacionConfigView,
    IntakeWebView,
    IntakeWhatsappView,
    RegenerarTokenView,
)
from mensajes.api import MensajeViewSet, PlantillaMensajeViewSet
from pacientes.api import AdjuntoViewSet, AtencionViewSet, BloqueoAgendaViewSet, CitaViewSet, PacienteViewSet, TranscribirView
from pacientes.consentimiento import (
    AceptarConsentimientoView,
    ConsentimientoPublicoView,
    ConsentimientoViewSet,
)
from usuarios.api import (
    CambiarPasswordView,
    DocumentoLegalViewSet,
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
router.register(r"bloqueos", BloqueoAgendaViewSet, basename="bloqueo")
router.register(r"atenciones", AtencionViewSet, basename="atencion")
router.register(r"adjuntos", AdjuntoViewSet, basename="adjunto")
router.register(r"servicios", ServicioViewSet, basename="servicio")
router.register(r"cobros", CobroViewSet, basename="cobro")
router.register(r"paquetes", PaqueteViewSet, basename="paquete")
router.register(r"egresos", EgresoViewSet, basename="egreso")
router.register(r"usuarios", UsuarioViewSet, basename="usuario")
router.register(r"profesionales", ProfesionalViewSet, basename="profesional")
router.register(r"documentos-legales", DocumentoLegalViewSet, basename="documento-legal")
router.register(r"metricas", MetricaMensualViewSet, basename="metrica")
router.register(r"reportes-semanales", ReporteSemanalViewSet, basename="reporte-semanal")
router.register(r"mensajes", MensajeViewSet, basename="mensaje")
router.register(r"plantillas", PlantillaMensajeViewSet, basename="plantilla")
router.register(r"consentimientos", ConsentimientoViewSet, basename="consentimiento")
router.register(r"leads", LeadViewSet, basename="lead")
router.register(r"sugerencias", SugerenciaViewSet, basename="sugerencia")
router.register(r"recursos", RecursoViewSet, basename="recurso")
router.register(r"anuncios", AnuncioViewSet, basename="anuncio")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/login/", LoginView.as_view(), name="login"),
    path("api/auth/logout/", LogoutView.as_view(), name="logout"),
    path("api/auth/me/", MeView.as_view(), name="me"),
    path("api/auth/cambiar-password/", CambiarPasswordView.as_view(), name="cambiar-password"),
    path("api/medicos/", MedicosView.as_view(), name="medicos"),
    path("api/transcribir/", TranscribirView.as_view(), name="transcribir"),
    path("api/hoy/", HoyResumenView.as_view(), name="hoy-resumen"),
    path("api/clinica/", ClinicaConfigView.as_view(), name="clinica-config"),
    path("api/gerencia/resumen/", GerenciaResumenView.as_view(), name="gerencia-resumen"),
    path("api/finanzas/caja/", CajaView.as_view(), name="finanzas-caja"),
    path("api/finanzas/liquidacion/", LiquidacionView.as_view(), name="finanzas-liquidacion"),
    # WhatsApp Cloud API (Meta): configuración (admin) + webhook público de Meta.
    path("api/whatsapp/config/", WhatsappConfigView.as_view(), name="whatsapp-config"),
    path("api/webhook/whatsapp", WhatsappWebhookView.as_view(), name="whatsapp-webhook"),
    path("api/finanzas/soto/", SotoResumenView.as_view(), name="finanzas-soto"),
    path("api/finanzas/soto/prueba/", SotoPruebaView.as_view(), name="finanzas-soto-prueba"),

    path("api/ocupacion/", OcupacionView.as_view(), name="ocupacion"),
    # Captación de leads. Las rutas específicas van ANTES del comodín <token>.
    path("api/captacion/config/", CaptacionConfigView.as_view(), name="captacion-config"),
    path("api/captacion/regenerar/", RegenerarTokenView.as_view(), name="captacion-regenerar"),
    path("api/captacion/whatsapp/<str:token>/", IntakeWhatsappView.as_view(), name="captacion-whatsapp"),
    path("api/captacion/<str:token>/", IntakeWebView.as_view(), name="captacion-web"),
    # Integración con Eli (notas clínicas por voz desde WhatsApp). Token compartido.
    path("api/integraciones/psicologo/", PsicologoView.as_view(), name="integ-psicologo"),
    path("api/integraciones/pacientes/", PacientesBuscarView.as_view(), name="integ-pacientes"),
    path("api/integraciones/nota-voz/", NotaVozView.as_view(), name="integ-nota-voz"),
    # Consentimiento informado: aceptación pública por token (sin login).
    path("api/consentimiento/<str:token>/aceptar/", AceptarConsentimientoView.as_view(), name="consentimiento-aceptar"),
    path("api/consentimiento/<str:token>/", ConsentimientoPublicoView.as_view(), name="consentimiento-publico"),
    path("api/", include(router.urls)),
    # Catch-all: cualquier otra ruta sirve la app React (index.html). En producción
    # Django entrega el SPA; en desarrollo el SPA lo sirve Vite (5173), no Django.
    re_path(r"^(?!api/|admin/|static/|media/).*$",
            TemplateView.as_view(template_name="index.html"), name="spa"),
]
