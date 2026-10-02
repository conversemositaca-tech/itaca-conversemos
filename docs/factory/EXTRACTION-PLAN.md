# EXTRACTION-PLAN · Cómo sale el core de Conversemos sin copiar el repo

## Principios

1. **Se extraen conceptos probados, no carpetas.** El template se escribe de nuevo, en genérico, tomando como referencia las piezas de Conversemos que tienen tests. Nada del template importa código de Conversemos.
2. **Una pieza entra si:** tiene tests, su API se entiende en una línea, no depende de detalles accidentales (nombres de roles, modelos de psicología) y existe un segundo uso real o inmediato.
3. **Lo acoplado se especifica antes de extraerse.** Agenda, identidad, mensajería y caja salen como spec + tests de contrato, y solo después como código.
4. **Conversemos no se reescribe** para usar el template: lo hará cuando una pieza del template madure como paquete (fase futura) y valga la pena migrar.

## Ola 1 — Template mínimo (Fase 3, ahora)

| Pieza del template | Referencia en Conversemos | Cambios al generalizar |
|---|---|---|
| `core/tenant.py`, `ModeloTenant`, middleware | Idénticos en concepto | La organización se llama `Organizacion` (no `Clinica`) |
| `usuarios.Usuario` (email, rol, organización) + login con throttle IP/cuenta | `usuarios/models.py`, `LoginView`, throttles | Roles desde `settings.ROLES`; sin campos clínicos |
| `core/politicas.py` | Mismas capas | Roles configurables; `acotar_por_propietario(qs, user, campo)` en vez de "ficha del psicólogo" |
| `core/auditoria.py` + `RegistroAuditoria` | Igual | — |
| `core/serializadores.py` (`RelacionesDelTenant`, `validar`) | Igual | — |
| Hasher de tests + `tests_hasher` | Igual | — |
| Hosts por variable, sin comodines | Bloque de Railway | `DOMINIO_SERVICIO` |
| `/api/salud/` | `core/reloj.py` | + chequeo de BD y versión |
| Respaldo + test de cobertura | `core/respaldo.py` | `APPS` derivada de las apps propias del proyecto |
| Matriz rol × endpoint + campos por rol | Tests de Conversemos | Motor genérico + matriz del módulo de ejemplo |
| Módulo de ejemplo con dueño (p. ej. `notas`) | Patrón de adjuntos/atenciones | Demuestra alcance por propietario, campo sensible, auditoría y validación de entrada |
| `scripts/verificar.ps1` + `eslint-sin-deuda.mjs` | Igual | Rutas relativas al proyecto |
| `.claude/` (Stop hook, rules base), `CLAUDE.md` mapa | Igual | Contenido con huecos |
| CI (backend, seguridad, Postgres, frontend) | Igual | — |
| Frontend: Vite + React, login, `ui/Modal`, `confirmar`, `aviso`, `InputClave` | Igual | CSS mínimo propio |

## Ola 2 — Specs + tests de contrato (fase futura, cuando el 2.º proyecto lo pida)

| Pieza | Por qué espera |
|---|---|
| Identidad (persona / contacto / tutor, duplicados, fusión) | La lección más cara (≥10 PR) merece una spec primero; `fusion.py` tiene 700 líneas acopladas |
| Agenda (slots, bloqueos, estados con fuente única, reserva pública) | Depende de "profesional" y "servicio" del dominio |
| Mensajería (adaptador Evolution/Meta, "aceptado ≠ entregado") | ~17 clientes en la agencia: es el mayor ahorro, pero exige definir el contrato |
| Caja (cobro vigente único, `marcar_pagado`, paquetes) | Los patrones ya están probados; falta separarlos del paciente clínico |
| Correo con consentimiento | `ConIdentidad` apunta a 3 modelos concretos |
| Sugerencia de IA con revisión | Generalizar cuando exista el 2.º campo |

## Ola 3 — Paquetes versionados (fase futura)

Cuando 2 proyectos usen la misma pieza del template, se convierte en paquete (`itaca-core`, `itaca-ui`) para propagar arreglos por versión, en vez de en N PR.

## Qué NO se extrae

Faro, DP, Dirección Clínica, gerencia, Brújula, gamificación, `espacios`, sitio público, importadores de AgendaPro y Soto.

## Riesgos y cómo se controlan

| Riesgo | Control |
|---|---|
| El template envejece y Conversemos diverge | El template tiene su propio smoke test y CI; las mejoras de Conversemos que sean universales se portan con un PR al template (regla en la skill `pr`) |
| Abstracción prematura | Solo se extrae lo que está en la Ola 1; el resto espera un segundo uso |
| Stack | El template es Django + React porque es lo probado; la decisión Django vs Next.js está en [STACK-EVIDENCE.md](STACK-EVIDENCE.md), no se fuerza aquí |
