# Ítaca Software Factory — Fase 0: Secure & Accelerate

> **Rama:** `chore/software-factory-phase-0` · **Worktree:** `C:\projects\itaca-factory-p0`
> **Base:** `origin/main` `ae759b8`, igual al SHA auditado: `origin/main` no avanzó.
> **Estado:** commits locales. **Sin push, sin PR, sin merge, sin deploy.**
> Detalle en [`docs/software-factory-phase-0/`](software-factory-phase-0/).

## Resumen

La Fase 0 cerró los riesgos de seguridad críticos de la auditoría y abarató la verificación al punto de poder exigirla en cada tarea.

1. **Seguridad**
   - Adjuntos clínicos, tokens de consentimiento, riesgo clínico escrito por IA y hosts de Railway: corregidos con tests.
   - Token de integración: mitigado. El cierre total requiere configurar 3 variables en Railway y en los bots.
2. **Velocidad:** la suite completa pasó de más de 55 minutos sin terminar a **103 s**. El cambio de fondo es una línea: un hasher de contraseñas barato que solo existe bajo `manage.py test`.
3. **Automatización**
   - `scripts/verificar.ps1` (FAST, STANDARD, FULL).
   - Stop hook que no deja cerrar una tarea con código sin verificar.
   - CI en 3 jobs paralelos, con ESLint "ninguna deuda nueva".
   - Matriz de 168 combinaciones rol × endpoint que detecta escalamientos de privilegio.
4. **Contexto:** `CLAUDE.md` pasó de 85,7 KB a 6,0 KB (−93 %, ≈ −19.900 tokens por sesión). La bitácora se archivó íntegra y ~20 invariantes pasaron a reglas que se cargan por ruta.

## Commits (sobre `ae759b8`)

| # | Commit | Responsabilidad |
|---|---|---|
| 1 | `9f25d07` | docs: auditoría preservada (solo `docs/`) |
| 2 | `542c0c5` | test(dx): hasher barato solo en `manage.py test` |
| 3 | `83674fc` | fix(seguridad): adjuntos clínicos (P0-S1) |
| 4 | `d25157a` | fix(seguridad): tokens de consentimiento (P0-S2) |
| 5 | `d6332b4` | fix(seguridad): token de integración por alcance (P0-S3) |
| 6 | `f49302f` | fix(clínico): riesgo sugerido por IA con revisión humana (P0-S4) |
| 7 | `f1a29a6` | fix(deploy): dirección de Railway sin comodín (P0-S5) |
| 8 | `176e313` | test(permisos): matriz rol × endpoint |
| 9 | `d9868c5` | chore(dx): `verificar.ps1` |
| 10 | `bab5269` | fix(dx): base de prueba en memoria (lección `--keepdb`) |
| 11 | `3c129ba` | chore(claude): Stop hook |
| 12 | `d1e4da9` | fix(dx): stderr de git en PowerShell 5.1 y regla ESLint común |
| 13 | `026f4f9` | ci: 3 jobs en paralelo |
| 14 | `b47992b` | docs(claude): `CLAUDE.md` como mapa + rules + bitácora archivada |
| 15 | (este) | docs: reporte de la Fase 0 |

Cada commit es pequeño y se puede revertir por separado. Todos dejan la suite en verde.

## Seguridad

| Riesgo | Estado | Qué cambió |
|---|---|---|
| Adjuntos clínicos | **FIXED** | Comercial no ve ninguno; el psicólogo solo los de sus pacientes, en listar, descargar, borrar y subir |
| Tokens de consentimiento | **FIXED** | Solo admin y coordinación reciben el token. Se cerraron también la respuesta de crear/marcar sin contexto y el enlace en la bitácora de mensajes |
| Token de integración | **MITIGATED** · cierre **BLOCKED** externo | Alcances eli / tareas / respaldo con token propio opcional, `compare_digest` y throttle. Compatible: sin tokens nuevos, nada se corta |
| Riesgo clínico de Eli | **FIXED** | La IA crea una `SugerenciaRiesgo` pendiente; el psicólogo del paciente o un admin confirma, modifica o rechaza desde la ficha; queda quién y cuándo |
| Railway / PR #138 | **FIXED** (reemplaza #138) | Dominio exacto del servicio en hosts y CSRF; sin `*.up.railway.app` |

Detalle, caminos revisados y riesgos residuales en [02-seguridad-p0s.md](software-factory-phase-0/02-seguridad-p0s.md).

## Medición

| Métrica | Antes | Después |
|---|---|---|
| Tests | 1.043 | 1.071 |
| Suite local | > 55 min sin terminar | **103 s** |
| FAST / STANDARD / FULL | — | 20–45 s / ~141 s / 87–138 s |
| Stop hook | — | 1 s (en caché) · ~110 s (verificando) |
| `CLAUDE.md` | 85.671 B · ~21.400 tokens | 6.023 B · ~1.500 tokens |
| ESLint | 74 / 38 | 74 / 38 (**0 nuevos**) |
| Matriz de permisos | 0 | 168 celdas |
| CI | 8,4 min (mediana; 460 s de pruebas) | no medido sin push; ~2 min estimado |

## Qué necesita Max

1. Revisar la rama y decidir push y PR (nada se publicó).
2. Configurar `ITACA_TOKEN_RESPALDO`, `ITACA_TOKEN_TAREAS` e `ITACA_TOKEN_ELI` en Railway, kira-bot y Eli.
3. Tras desplegar: cerrar el PR #138, regenerar los tokens de los consentimientos pendientes (operación en producción) y ajustar el texto de Eli sobre el riesgo.
4. Decidir las brechas que quedaron fijadas en la matriz para la fase 1: alertas de Faro, leads, cobros, y el alcance de coordinación y analista sobre los adjuntos.
5. Al integrar `feat/direccion-clinica`, resolver `CLAUDE.md` y `core/respaldo.py` como indica [08-bloqueos-y-siguiente-fase.md](software-factory-phase-0/08-bloqueos-y-siguiente-fase.md).
6. Lanzar Claude Code desde la carpeta del repo para que se activen el Stop hook y las reglas.

## Lecciones

- **El cuello de botella de la verificación no era el tamaño de la suite**, sino un parámetro de seguridad (PBKDF2) que no aporta nada en tests.
- **No todo "cacheo" acelera:** `--keepdb` en archivo hizo la suite 45 veces más lenta en Windows. Se midió y se revirtió.
- **PowerShell 5.1** aborta con cualquier línea de stderr si `ErrorActionPreference` es `Stop`; en un hook eso significa fallar abierto. Los scripts usan `Continue`.
- **Una matriz de permisos generada y luego revisada** sirve como contrato: congela la política vigente y hace explícito cualquier cambio.

## Documentos

| Documento | Contenido |
|---|---|
| [01-baseline.md](software-factory-phase-0/01-baseline.md) | Preservación, SHA, validación de las cifras de la auditoría |
| [02-seguridad-p0s.md](software-factory-phase-0/02-seguridad-p0s.md) | Los 5 riesgos: caminos, cambios, residuales, acciones externas |
| [03-verificacion.md](software-factory-phase-0/03-verificacion.md) | Hasher, `verificar.ps1`, mediciones, lecciones |
| [04-matriz-permisos.md](software-factory-phase-0/04-matriz-permisos.md) | Matriz de 168 celdas y brechas conocidas |
| [05-hook-y-ci.md](software-factory-phase-0/05-hook-y-ci.md) | Stop hook, CI y gates |
| [06-contexto-claude-md.md](software-factory-phase-0/06-contexto-claude-md.md) | `CLAUDE.md` como mapa, reglas por ruta |
| [07-metricas.md](software-factory-phase-0/07-metricas.md) | Antes / después |
| [08-bloqueos-y-siguiente-fase.md](software-factory-phase-0/08-bloqueos-y-siguiente-fase.md) | Bloqueos abiertos y candidatos a la fase 1 |
