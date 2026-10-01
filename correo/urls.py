"""Rutas de Email 1.0, montadas bajo /api/correo/."""
from django.urls import path

from .api_panel import CorreoConsentimientoPanelView, CorreoPacienteView
from .api_tareas import ProcesarPendientesView

urlpatterns = [
    path("pacientes/<int:pk>/", CorreoPacienteView.as_view(), name="correo-paciente"),
    path("pacientes/<int:pk>/consentimiento/", CorreoConsentimientoPanelView.as_view(),
         name="correo-paciente-consentimiento"),
    path("tareas/procesar-pendientes/", ProcesarPendientesView.as_view(),
         name="correo-procesar-pendientes"),
]
