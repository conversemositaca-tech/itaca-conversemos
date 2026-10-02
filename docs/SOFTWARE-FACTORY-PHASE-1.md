# Ítaca Software Factory — Fase 1: Integrate, Harden & Standardize

> Rama `chore/software-factory-phase-0` (worktree `C:\projects\itaca-factory-p0`), rebasada sobre `origin/main` `9ed776c`.
> Solo commits locales: **sin push, sin PR, sin merge, sin deploy**.
> Detalle en [`docs/software-factory-phase-1/`](software-factory-phase-1/).

## Resultado

| Objetivo | Estado | Evidencia |
|---|---|---|
| Integración | **Parcial a propósito** | Fase 0 rebasada sobre el `main` nuevo (con #138 y #141). Dirección Clínica la integra otra sesión en `itaca-continuidad-2`; no se duplicó |
| RBAC más centralizado | Hecho | `core/politicas.py` por capas; 6 `_es_admin` + 5 `_solo_admin` + 5 bloques de alcance + 3 `_solo_clinico` migrados; comparaciones de rol en línea fuera de `permisos.py`: 37 → 24 |
| Brechas conocidas | Corregidas o documentadas | Leads y cobros corregidos; FK sin tenant (5 serializers) corregidos; paquetes corregidos. Faro documentado como decisión D1 |
| Tests de campos sensibles | Hecho | `core/tests_campos_por_rol.py` (paciente, lead, consentimiento, bitácora, historia) |
| Validación de entrada | Inventario + P0 de dinero | `core.serializadores.validar()` + `CobroEntradaSerializer` |
| Fuente única "cita realizada" | Hecho (sin mover cifras) | `ESTADOS_REALIZADA`; 8 copias eliminadas; guardián `tests_fuentes_unicas` |
| Postgres en CI | Hecho | Job `postgres`; ya encontró un bug real (`86da86a`) |
| Frontend base | Hecho (primer uso) | Confirmar al cancelar cita, avisos tipados, `Modal` + `BotonGuardar` en `CobroModal` |
| Doble cobro | Investigado y corregido | Bloqueo + 409 + botón; probado con 4 hilos en Postgres |
| IA clínica | Clasificada; la crítica tiene revisión humana | Riesgo (Fase 0) y resumen/objetivo: la IA ya no pisa texto humano |
| Auditoría | Hecho | `RegistroAuditoria` en 12 acciones sensibles |
| Respaldo | Hecho | Test: toda app con modelos está en `APPS` |

## Gate de la Fase 1

| Condición | Resultado |
|---|---|
| STANDARD | ✔ verde (132,9 s) |
| FULL | ✔ verde (91 s; 1 aviso `security.W021`) |
| Postgres (suite completa, local) | ✔ **1.131 tests OK, 0 saltados**, 158 s |
| CI | Configurado (4 jobs); sin corrida real porque no hay push |
| Seguridad sin regresiones | ✔ matriz 210 celdas, campos por rol, P0-S 24 tests |

## Commits de la Fase 1

| Commit | Cambio |
|---|---|
| `b9f62a8` | rbac: `core/politicas.py` |
| `76b5d74` | core: `RegistroAuditoria` + `auditar()` |
| `07e0ec0` | security: FK escribibles acotados a la clínica |
| `be2cb81` | security(finanzas): doble cobro, roles, auditoría |
| `dedd1d3` | security: contacto de leads, consentimiento inmutable, tests por campo |
| `85f4f17` | backend: `ESTADOS_REALIZADA` + guardián |
| `80291b9` | security(ia): no pisar texto clínico humano |
| `ecb5085` | backend: auditoría de acciones sensibles + paquete una sola vez + test de respaldo |
| `708ee17` | ci: job de PostgreSQL + pruebas de carreras |
| `86da86a` | fix(finanzas): `select_for_update(of=self)` (encontrado por Postgres) |
| `bf479d6` | ux: confirmar cancelación, avisos tipados, Modal base |
| `243dbea` | ci: tests de frontend con `node --test` |
| `fe3aaf0` | tests(permisos): matriz con cobros, consentimiento y paquetes |
| `44fa747` | backend: entrada de cobros validada; vender paquete = caja |
| (este) | docs + rules de la Fase 1 |

## Decisiones que quedan para Max

Ver [04-decisiones-para-max.md](software-factory-phase-1/04-decisiones-para-max.md): D1 alertas de Faro, D2 KPI de asistencia, D3 recordatorios, D4 "reprogramada", D5 transiciones de cita, D6 adjuntos para coordinación y analista, D7 constraint de cobro en la base, D8 Idempotency-Key, D9 tokens y despliegue.
