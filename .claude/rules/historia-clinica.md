---
paths:
  - "pacientes/**"
---
# Historia clínica y ficha del paciente

Invariantes vigentes (verificados en `pacientes/api.py`, `pacientes/models.py`, `pacientes/riesgo.py`):

- **Una atención no se borra ni se crea por la API genérica.** `AtencionViewSet`: `create` y `destroy` → 405; las atenciones nacen al Atender. Editar contenido: solo `medico`/`admin`.
- **Toda corrección queda auditada**: `perform_update` escribe una fila de `EdicionAtencion` por campo cambiado (antes → después, quién, cuándo). Si agregas un campo clínico, súmalo a la auditoría (`CAMPOS_AUDIT`) y al editor.
- **Alcance clínico**: comercial no ve nada; el psicólogo solo los pacientes de su ficha (`paciente__profesional`); asistente agenda y gestiona pero no escribe en la historia.
- **Adjuntos clínicos (`Adjunto`)**: mismo alcance que la historia. Descarga SOLO por `/api/adjuntos/{id}/descargar/` autenticada (`as_attachment`); **nunca URL pública de media**. Eliminar: médico/admin (borra el archivo).
- `pacientes.Adjunto` (material de UN paciente) y `mensajes.Material` (biblioteca compartible) están separados a propósito: una ecografía nunca debe poder salir en el compositor de WhatsApp.
- **Riesgo clínico**: la IA (Eli, `core/integraciones.py`) NUNCA escribe `Paciente.riesgo`; deja `SugerenciaRiesgo` pendiente. Resolver (`/api/sugerencias-riesgo/<id>/resolver/`): solo el psicólogo del paciente o admin, con trazabilidad.
- Dictado/transcripción (`/api/transcribir/`): no guarda; devuelve texto y el terapeuta revisa y guarda por el flujo normal.
- La decisión de proceso (DP) de una cita la registra coordinación: `CitaViewSet.perform_update` descarta `decision` si edita un `medico`.
- Mover una cita la deja en estado `reprogramada`; cancelar no borra.
- Tipos de ficha: `historia` (una vez) y `evolucion` (cada sesión); cambiar el tipo descarta campos: avisar antes.
- **Agendamiento público** (`pacientes/agendamiento.py`): teléfono mínimo = `leads.identidad.MIN_DIGITOS_TELEFONO` (9), una sola constante en los dos lados.
- Reactivación: `dias_sin_venir` cuenta solo citas asistidas; `None` = nunca vino (no es "abandonó"). Esa lista no sale del sistema (ni exportes ni chats).
- Toda app o modelo nuevo con datos debe entrar en `core/respaldo.py` (lo exige un test).

Más contexto: ítems 7, 24, 25, 27, 28, 42, 43 de `docs/historial/CLAUDE-bitacora-hasta-2026-10-01.md` (el ítem 7 dice "append-only": OBSOLETO).
