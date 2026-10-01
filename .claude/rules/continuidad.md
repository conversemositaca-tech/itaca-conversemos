---
paths:
  - "core/continuidad*.py"
  - "core/gestion_continuidad.py"
  - "core/contacto_continuidad.py"
  - "core/notas_operativas.py"
  - "core/tests_*continuidad*.py"
  - "core/tests_proceso.py"
  - "core/tests_cierres.py"
  - "pacientes/signals.py"
---
# Centro de Continuidad

- **Una sola regla**: `core/continuidad.py::evaluar_paciente` decide el estado de un paciente; la cola, la tarjeta de Hoy y el dry-run de fusión la llaman. No reimplementes la regla en otro sitio.
- **Tramos**: `segmentar_procesos` / `proceso_actual` parten la historia en procesos. Una bajada de `n_sesion` solo es candidata a reinicio; se acepta con respaldo estructurado (nueva sesión = 1, DP de cierre en el tramo anterior, consulta o DP inicial, cambio de etapa, lead convertido). El tiempo solo refuerza, nunca decide solo. Sin respaldo = `numeracion_inconsistente`.
- La cola trabaja solo con el **tramo actual**; procesos previos sin DP van a "Calidad de registro", nunca a acción.
- **La decisión de cada cierre se evalúa contra la cita de ESE bloque**, no contra la última cita.
- El cierre "vigente" es el **último que quedó atrás**, no el próximo (`cierres_del_proceso`).
- Registrar DP: **un selector por cierre**, nunca "marcar todos igual". Lo hace coordinación (el `medico` no puede: se descarta `decision`).
- `core/notas_operativas.py` resume notas en señales operativas y **nunca decide nada clínico** (una mención de alta solo produce "verificar registro formal").
- **Gestión** (`GestionContinuidad` + `HistorialContinuidad`): una abierta por (paciente, tipo, meta); abrir el panel no escribe. "Resuelto" no silencia la cola si la fuente sigue detectando el caso. `pacientes/signals.py` reconcilia al guardar/borrar citas; una resolución manual nunca se pisa.
- **Permisos**: `PuedeGestionarContinuidad` = admin, asistente, analista, SOLO en `PATCH /api/continuidad/caso/<id>/gestion/`. El psicólogo **no** gestiona (ve sus casos). Contactar pacientes: solo admin + asistente.
- Alcance por `pacientes_del_rol` (usa `Usuario.sede`; no lo reutilices como permiso de pantalla).
- `update()` masivo no dispara señales: llama a `gestion_continuidad.reconciliar()`.

Más contexto: `docs/auditoria-continuidad.md`; ítems 30 y 45 del archivo histórico. La fase 2 (app `continuidad`) vive en `feat/direccion-clinica`.
