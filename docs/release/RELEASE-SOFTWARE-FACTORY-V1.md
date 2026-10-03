# Release · Software Factory v1 + Security Hardening

PR #143, rama `chore/software-factory-phase-0` → `main`. 44 commits, 115 archivos, +10.053 / −1.415.

## Resultado final (2 oct 2026)

| | |
|---|---|
| Merge | `687b3b5` (merge commit sobre `23264cd`, que trae #127 y #144) · 17:26 UTC |
| CI del merge | `test` 1.249 OK (4 skipped) · `postgres` 1.249 OK sin skips · `seguridad` 60 OK · `frontend` build + 5/5 + ESLint 74/38 (= línea base) |
| Deploy | Railway, exitoso a los ~45 s del merge |
| Migraciones | `core.0021_registro_auditoria` y `pacientes.0039_sugerencia_riesgo` aplicadas al arrancar, sin errores |
| Smoke anónimo | `/api/hora/` y home 200 · pacientes, cobros, sugerencias, leads y Dirección Clínica sin sesión → 403 · integraciones con token falso → 403 · logs sin 500 ni tracebacks |
| Rollback | `git revert -m 1 687b3b5` |

Pendiente de operación (no de código): tokens por alcance en Railway y en los consumidores (Eli y `mia`, ya preparados para caer al token compartido mientras el propio no esté) y el QA de datos con `scripts/qa_prod_readonly.py`.

## Diff clasificado

| Bloque | Clase | Contenido |
|---|---|---|
| Adjuntos clínicos, tokens de consentimiento, token de integración por alcance, riesgo de IA con revisión humana, FK sin tenant, cobros (alcance, doble cobro, quién corrige), contacto de leads, consentimiento inmutable | **P0 seguridad** | `pacientes/api.py`, `pacientes/consentimiento.py`, `pacientes/riesgo.py`, `core/integraciones.py`, `core/serializadores.py`, `finanzas/api.py`, `finanzas/serializers.py`, `leads/serializers.py`, `mensajes/` |
| Paquete que descuenta una vez, `marcar_pagado` 409, fuente única de "sesión realizada", auditoría, respaldo que cubre toda app, la IA no pisa texto humano | **P1 integridad** | `core/auditoria.py`, `core/models.py`, `pacientes/models.py`, `finanzas/models.py`, `core/continuidad.py`, `core/gerencia.py`, `core/mi_panel.py`, `core/ocupacion.py` |
| Políticas por capas (`core/politicas.py`), `validar()`, UI base (`frontend/src/ui/`), confirmación al cancelar, avisos tipados | **P2 arquitectura** | — |
| Hasher de tests, `verificar.ps1`, Stop hook, CI de 4 jobs (con Postgres), ESLint sin deuda, `CLAUDE.md` mapa + rules, skills y agentes, docs de fábrica | **P3 tooling** | `scripts/`, `.claude/`, `.github/`, `docs/` |

## Migraciones

| Migración | Operación | Clase | Notas |
|---|---|---|---|
| `core/0021_registro_auditoria` | `CreateModel RegistroAuditoria` | **A** aditiva | Tabla nueva vacía; FK a `Clinica` y a `Usuario` |
| `pacientes/0039_sugerencia_riesgo` | `CreateModel SugerenciaRiesgo` | **A** aditiva | Tabla nueva vacía; FK a `Paciente`, `Atencion` y `Usuario` |

Sin backfill, sin `RunPython`, sin cambios en columnas existentes. El contenedor migra al arrancar (`Dockerfile`). Las dos tablas entran al respaldo de forma automática (apps `core` y `pacientes`).

## Variables de entorno

| Variable | Consume | Fallback | Si falta | Cuándo |
|---|---|---|---|---|
| `ITACA_TOKEN_ELI` | Backend (`/api/integraciones/*` de Eli) / bot Eli la envía | `ITACA_INTEGRACION_TOKEN` | Eli sigue con el token compartido | **Después** del deploy (opcional) |
| `ITACA_TOKEN_TAREAS` | Backend (recordatorios, `procesar-pendientes` de correo) / kira-bot y el cron de correo la envían | `ITACA_INTEGRACION_TOKEN` | Idem | Después (opcional) |
| `ITACA_TOKEN_RESPALDO` | Backend (`/api/integraciones/respaldo/`) / cron de respaldo la envía | `ITACA_INTEGRACION_TOKEN` | **El token de Eli sigue abriendo el volcado completo** | Después; es la que más importa |
| `RAILWAY_DOMINIO_SERVICIO` | Backend (hosts + CSRF) | `itaca-conversemos-production.up.railway.app` | Se usa el valor por defecto, que es el dominio real (verificado: `/api/hora/` → 200) | No hace falta |

**Orden seguro de los tokens:**

1. Desplegar.
2. Crear el token en Railway **y** en el consumidor (un alcance a la vez).
3. Verificar el consumidor (respaldo: correr `?resumen=1`; Eli: un mensaje de prueba; tareas: un `dry`).
4. Recién entonces el compartido deja de abrir ese alcance.

Al configurar en Railway el token propio de un alcance, el compartido deja de servir **en el mismo instante** para ese alcance: el consumidor debe tener el nuevo antes, o justo después.

## Comportamiento visible que cambia

- El psicólogo deja de ver por API el contacto de los leads, los cobros de pacientes ajenos y los mensajes de pacientes ajenos.
- El comercial deja de recibir consentimientos, adjuntos y cobros.
- Solo coordinación y gerencia registran, cobran, venden paquetes y anulan. Solo gerencia corrige montos.
- Cancelar o marcar "no asistió" desde el desplegable pide confirmación.
- Los consentimientos ya no se editan ni se borran por API (405).
- La dirección `*.up.railway.app` de **otros** servicios deja de ser un host y un origen CSRF aceptados (#138 la había abierto).

## Rollback

| Situación | Acción |
|---|---|
| Falla funcional tras el merge | `git revert -m 1 <merge>` y push a `main` (Railway redespliega). Las tablas nuevas quedan huérfanas sin efecto; **no** hace falta revertir migraciones |
| Hay que revertir migraciones (no debería) | Antes de revertir el código: `python manage.py migrate core 0020` y `python manage.py migrate pacientes 0038` (borran las dos tablas nuevas, con la auditoría y las sugerencias que se hayan generado). Respaldar antes con `/api/integraciones/respaldo/` |
| Un token por alcance rompe un consumidor | Vaciar esa variable en Railway: el alcance vuelve a aceptar el compartido |
| La dirección de Railway da 400 | Agregar el host a `DJANGO_ALLOWED_HOSTS` / `DJANGO_CSRF_ORIGINS` (ya están puestas a mano) o fijar `RAILWAY_DOMINIO_SERVICIO` |
| CI nuevo falla por infraestructura (p. ej. el servicio Postgres) | No se desactivan gates: se corrige en la misma rama |

## Orden respecto de Dirección Clínica (#127)

Ensayo local (`ensayo/dc-mas-sf`): fusionar esta rama sobre `feat/direccion-clinica`. Conflictos solo en `CLAUDE.md` y `App.jsx`, resueltos conservando ambas intenciones. Resultado:

- **1.241 tests OK en SQLite (FULL)**, incluidos los guardianes nuevos sobre el código de Dirección Clínica (fuente única, respaldo con `continuidad`, matriz, campos por rol);
- **suite completa en Postgres**: ver el resultado en el PR;
- ESLint sin deuda nueva.

**Resultado:** #127 se mergeó primero (2 oct 2026, `7eda3f1`) y esta rama lo integró con un merge que reproduce la resolución del ensayo.

**Orden que se recomendó (y se siguió):**

1. **#127 Dirección Clínica**;
2. **luego esta rama**, rebasada sobre el `main` resultante con la misma resolución ya probada.

**Por qué:**

- #127 ya está mergeable y su sesión lo cerró.
- Si entra primero esta rama, los conflictos de `CLAUDE.md` (mapa vs bitácora) le caen a otra sesión, que tiende a escribir bitácora.
- Así, el CI de esta rama valida también el código de Dirección Clínica bajo los guardianes nuevos.

**Nota D2:** #127 ya corrige el KPI de % de asistencia: (asistió + atendida) / (realizadas + no asistió + canceladas). La decisión D2 queda resuelta por ese PR.
