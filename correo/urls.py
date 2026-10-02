"""Rutas de Email 1.0, montadas bajo /api/correo/."""
from django.urls import path

from .api_panel import (
    CorreoConsentimientoPanelView, CorreoFaroAplicacionView, CorreoFaroRevocarView,
    CorreoLeadConsentimientoView, CorreoLeadView, CorreoPacienteView,
)
from .api_publica import BajaUnClicView, PreferenciasView
from .api_tareas import ProcesarPendientesView
from .api_webhook import BrevoWebhookView

urlpatterns = [
    path("pacientes/<int:pk>/", CorreoPacienteView.as_view(), name="correo-paciente"),
    path("pacientes/<int:pk>/consentimiento/", CorreoConsentimientoPanelView.as_view(),
         name="correo-paciente-consentimiento"),
    path("leads/<int:pk>/", CorreoLeadView.as_view(), name="correo-lead"),
    path("leads/<int:pk>/consentimiento/", CorreoLeadConsentimientoView.as_view(),
         name="correo-lead-consentimiento"),
    path("faro/aplicaciones/<int:pk>/", CorreoFaroAplicacionView.as_view(),
         name="correo-faro-aplicacion"),
    path("faro/autorizaciones/<int:pk>/revocar/", CorreoFaroRevocarView.as_view(),
         name="correo-faro-revocar"),
    path("tareas/procesar-pendientes/", ProcesarPendientesView.as_view(),
         name="correo-procesar-pendientes"),
    path("webhooks/brevo/", BrevoWebhookView.as_view(), name="correo-webhook-brevo"),
    path("preferencias/<str:token>/", PreferenciasView.as_view(), name="correo-preferencias"),
    path("baja/<str:token>/", BajaUnClicView.as_view(), name="correo-baja"),
]
