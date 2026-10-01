---
paths:
  - "frontend/src/**"
---
# Frontend: factores humanos (resumen de `docs/software-factory-audit/04-human-factors.md` §6)

- **Destructivos con confirmación y consecuencia escrita** (borrar, cancelar, "no asistió", desactivar, enviar a terceros, marcar en lote); preferir "Deshacer" si es reversible.
- **Envíos a terceros** (mensajes/correos masivos, informes): paso de revisión con destinatarios y excepciones.
- **Modales que no pierden datos**: no cerrar por clic fuera ni Escape si hay cambios; borrador local en notas largas.
- **Toasts con tipo explícito** (ok/error/aviso), nunca inferido del texto; nada de JSON crudo; `aria-live`.
- **Guardar con bloqueo real**: `disabled` nativo mientras envía y cuando falta algo, con el motivo visible.
- **Valores por defecto honestos**: nada que alimente dinero o atribución nace con un valor "probable".
- **Textos de ayuda verdaderos**: el texto de éxito refleja lo que devolvió el servidor, no lo que se espera.
- **Búsqueda de persona** por nombre, teléfono y DNI, tolerante a tildes; reutilizar `AvisoDuplicado` en toda alta.
- **Estados vacío / carga / error** con "Reintentar"; prohibido `.catch(() => {})`.
- **Accesibilidad**: `<form>` (Enter envía), clicables como `<button>`, `:focus-visible`, `<label htmlFor>`, contraste AA en los tokens, mínimo 12 px.
- **Una sola vía por acción** y un solo estado por concepto (no `asistio` y `atendida`); una sola fuente de tokens de diseño (marca turquesa `#0A7D92`; ver `docs/marca-exportables.md`).
- **Permisos y "hoy" vienen del servidor** (`/api/auth/me/`, fecha del backend); no deducir rol ni fecha en el cliente. Nada de datos de pacientes en `localStorage`.

ESLint: ninguna deuda nueva contra `scripts/eslint-baseline.json`. QA en navegador con el recorrido del rol, registrado en el PR.
