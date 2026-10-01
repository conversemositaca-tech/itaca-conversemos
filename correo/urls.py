"""Rutas de Email 1.0, montadas bajo /api/correo/."""
from django.urls import path

from .api_panel import CorreoConsentimientoPanelView, CorreoPacienteView
from .api_publica import BajaUnClicView, PreferenciasView
from .api_tareas import ProcesarPendientesView
from .api_webhook import BrevoWebhookView

urlpatterns = [
    path("pacientes/<int:pk>/", CorreoPacienteView.as_view(), name="correo-paciente"),
    path("pacientes/<int:pk>/consentimiento/", CorreoConsentimientoPanelView.as_view(),
         name="correo-paciente-consentimiento"),
    path("tareas/procesar-pendientes/", ProcesarPendientesView.as_view(),
         name="correo-procesar-pendientes"),
    path("webhooks/brevo/", BrevoWebhookView.as_view(), name="correo-webhook-brevo"),
    path("preferencias/<str:token>/", PreferenciasView.as_view(), name="correo-preferencias"),
    path("baja/<str:token>/", BajaUnClicView.as_view(), name="correo-baja"),
]
