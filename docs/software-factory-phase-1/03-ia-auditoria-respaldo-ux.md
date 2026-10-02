# 03 · IA clínica, auditoría, respaldo y experiencia de uso

## IA clínica: inventario y clasificación

Hay **un solo modelo de lenguaje**: `core/estructurar_nota.py` → OpenAI `gpt-4o-mini`. Whisper (transcripción) corre local.

| # | Dónde | Qué hace | Clase | Antes | Ahora |
|---|---|---|---|---|---|
| 1 | `TranscribirView` (`/api/transcribir/`) | Transcribe y estructura; **no guarda**; el psicólogo revisa en "Atender" | A/B | Revisión humana previa | Sin cambio (correcto) |
| 2 | Nota de voz de Eli → `Atencion` | Crea la atención con el texto estructurado, marcada "Registrado por voz vía WhatsApp" | B | Registro del propio psicólogo, editable y auditado (`EdicionAtencion`) | Sin cambio: es la nota del psicólogo, formateada; queda trazable |
| 3 | Eli → `Paciente.riesgo` | Nivel de riesgo | **C** | Escribía el valor oficial | `SugerenciaRiesgo` pendiente → revisión humana (Fase 0) + auditoría (Fase 1) |
| 4 | Eli → `resumen_clinico`, `objetivo_principal` | Tarjetas del perfil | **B** | **Sobrescribía** lo escrito por el psicólogo | Solo completa campos vacíos; si difiere, queda como `ia.propuesta_no_aplicada` en la auditoría |
| 5 | Eli → `ObjetivoTerapeutico` | Agrega objetivos nuevos (sin duplicar) | B | Aditivo | Sin cambio |
| 6 | Respuesta automática a leads por WhatsApp (`leads/whatsapp_auto.py`) | **Sin IA** (reglas + plantillas FAQ), envía sin intervención humana, 1 vez cada 12 h | D (no LLM) | Política comercial vigente | Documentado; no se tocó |
| 7 | Consultas de Eli (`_responder_consulta`) | Búsqueda por palabras clave, sin LLM | A | — | — |

**Regla aplicada:** A se automatiza; B queda revisable y trazable; C exige una persona; D no se ejecuta sin una acción humana explícita (o, como en el #6, es una política de negocio ya decidida).

**Ningún mensaje a pacientes o familias lo redacta un LLM.** Los informes de Faro a familias los envía una persona (botón).

## Auditoría

Modelo `core.RegistroAuditoria` (append-only: actor, acción, modelo, id, `cambios` {campo: [antes, después]}, fecha). Se escribe con `core.auditoria.auditar()`, que descarta cualquier campo con nombre de secreto.

| Acción | Código |
|---|---|
| Crear, editar, cobrar y eliminar un cobro | `cobro.crear`, `cobro.editar`, `cobro.marcar_pagado`, `cobro.eliminar` |
| Anular un paquete | `paquete.anular` |
| Cambiar el estado de una cita o cancelarla | `cita.estado` |
| Marcar un consentimiento como aceptado | `consentimiento.marcar_aceptado` |
| Resolver el riesgo sugerido por IA | `riesgo.resolver` |
| Propuesta de la IA no aplicada | `ia.propuesta_no_aplicada` |
| Borrar un adjunto clínico | `adjunto.eliminar` |
| Cambiar rol, sede o activo de un usuario | `usuario.permisos` |

**Ya existían y se conservan:** `EdicionAtencion` (historia clínica), `RegistroEliminacion` (pagos y citas borrados), `RegistroFusionPaciente`, `SugerenciaRiesgo.revisado_por`.

**Pendiente:** una pantalla para consultarla. Hoy se lee desde el admin de Django o la base.

## Respaldo

- `core/respaldo.APPS` ya derivaba los modelos de cada app. El riesgo que quedaba era que **una app nueva** (p. ej. `continuidad`) no se agregara a la lista.
- Nuevo test `RespaldoCubreTodaAppTests`: toda app propia con modelos tiene que estar en `APPS`. Las tablas nuevas de esta fase (`SugerenciaRiesgo`, `RegistroAuditoria`) entran solas.

## Experiencia de uso

| Problema | Arreglo | Dónde |
|---|---|---|
| Cancelar o marcar "no asistió" con un solo cambio del desplegable | Confirmación explícita con paciente, fecha y consecuencia; foco en "No, dejarla como está" | `setEstadoCita` (un solo punto para la agenda y el detalle) |
| Errores mostrados con check verde ("No se pudo…") | Aviso con tipo (`success`, `info`, `warning`, `error`), clasificado por texto si no se indica; `role=alert` en errores | `frontend/src/ui/aviso.js` |
| Un aviso viejo borraba al nuevo | Cada aviso con id | `showToast` |
| Modales que pierden lo escrito | `Modal` tipo `formulario`: sin cierre por clic fuera; pide confirmación si hay cambios | `frontend/src/ui/Modal.jsx` |
| Doble clic al cobrar | `BotonGuardar` deshabilitado de verdad mientras envía | `CobroModal` |

**Alcance honesto:** `Modal` y `BotonGuardar` se aplicaron a `CobroModal`. Los otros ~39 modales se migran por uso, empezando por la nota clínica, el alta de paciente y el registro de lead. **QA en navegador no automatizado en esta fase:** el build compila, ESLint no tiene errores nuevos y los tests de `aviso.js` pasan, pero no hubo recorrido con Playwright. Esa es la skill `qa-browser` de la Fase 4.
