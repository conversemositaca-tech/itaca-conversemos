# Software Factory v1 + Security Hardening

Endurecimiento de seguridad e integridad de Ítaca Conversemos, más la base de la Software Factory (verificación, CI, permisos como contrato, skills y agentes). Sin features nuevas de negocio.

## Qué entra

| Clase | Resumen |
|---|---|
| **P0 seguridad** | Adjuntos clínicos y consentimientos con alcance por rol · token de firma solo para quien lo envía (también oculto en la bitácora) · tokens de integración por alcance (eli / tareas / respaldo) con `compare_digest` y throttle · la IA ya no escribe el riesgo clínico (sugerencia + revisión humana) · los FK ya no aceptan ids de otra clínica · cobros: alcance por rol, solo caja registra, solo gerencia corrige montos · contacto de leads oculto a psicólogo y analista · consentimiento inmutable por API · dirección de Railway exacta, sin `*.up.railway.app` |
| **P1 integridad** | Una cita no se cobra dos veces (bloqueo + 409, probado con 4 hilos en Postgres) · `marcar_pagado` solo desde pendiente · el paquete descuenta una sola vez · auditoría de acciones sensibles (`RegistroAuditoria`) · "sesión realizada" con una sola fuente + test guardián · la IA no pisa texto clínico humano · el respaldo cubre toda app con modelos |
| **P2 arquitectura** | `core/politicas.py` (permisos por capas) · `validar()` para la entrada · UI base `frontend/src/ui/` (Modal, confirmar, avisos tipados) · confirmación al cancelar cita |
| **P3 tooling** | Hasher barato solo en tests (suite: >55 min → ~100 s) · `scripts/verificar.ps1` FAST/STANDARD/FULL · Stop hook · CI de 4 jobs (backend, seguridad, **Postgres**, frontend) · ESLint sin deuda nueva · `CLAUDE.md` como mapa (85 → 6 KB) + rules por ruta · 4 skills y 4 agentes · docs de la fábrica |

## Migraciones
`core/0021_registro_auditoria` y `pacientes/0039_sugerencia_riesgo`: solo `CreateModel` (clase A, aditivas). Se aplican solas al arrancar el contenedor.

## Variables
`ITACA_TOKEN_ELI`, `ITACA_TOKEN_TAREAS` e `ITACA_TOKEN_RESPALDO` son **opcionales**: si faltan, se acepta el `ITACA_INTEGRACION_TOKEN` actual. Se configuran **después** del deploy, una a la vez. `RAILWAY_DOMINIO_SERVICIO` ya tiene por defecto el dominio real.

## Verificación local
- SQLite: STANDARD y FULL verdes, 1.131 tests.
- PostgreSQL 17: 1.131 OK, 0 saltados.
- Frontend: tests de `node --test`, build y ESLint (74/38 = línea base, 0 errores nuevos).
- Ensayo de merge con #127 (Dirección Clínica): 1.241 tests verdes.

## Cambios visibles para el equipo
Psicólogo y comercial ven menos (contacto de leads, cobros y mensajes ajenos). Solo coordinación y gerencia cobran y anulan. Cancelar o marcar "no asistió" pide confirmación. Los consentimientos no se editan por API.

## Orden recomendado
**#127 primero, luego este PR rebasado.** Detalle, rollback y riesgos en `docs/release/RELEASE-SOFTWARE-FACTORY-V1.md`.

## Decisiones fuera de este PR
D1, D3–D8 en `docs/software-factory-phase-1/04-decisiones-para-max.md` (D2 lo resuelve #127).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
