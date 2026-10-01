# 05 · Stop hook y CI

## Stop hook (`.claude/settings.json` → `.claude/hooks/stop-verificar.ps1`)

Objetivo: Claude no puede cerrar una tarea con código sin verificar.

| Situación | Qué hace | Tiempo medido |
|---|---|---|
| El árbol (HEAD + diff + archivos nuevos) ya pasó la verificación | Sale en silencio | **1 s** |
| Solo cambió documentación (`*.md`, `docs/`) | Sale en silencio | ~1 s |
| Hay código sin verificar | Corre `verificar.ps1 -Modo STANDARD -Silencioso` | ~105–110 s |
| STANDARD pasa | Guarda la huella; silencio | — |
| STANDARD falla | **Código 2**: Claude Code no deja cerrar y le muestra a Claude el paso y el test que fallaron | probado con un test roto |
| Falla 3 veces sobre el mismo árbol | Deja cerrar, pero con un `systemMessage` visible para la persona | evita bucles infinitos |

- FULL **nunca** corre en el hook: es manual, antes de integrar o publicar.
- Determinista: la huella es un SHA-256 del árbol; el estado se guarda en `%TEMP%\itaca-verificar\stop-<repo>`.
- Se registra en el `settings.json` del **proyecto**, así que se activa en sesiones de Claude Code lanzadas **desde la carpeta del repo** (o del worktree). Las sesiones lanzadas desde `C:\Users\mirai` no lo cargan, y por eso la auditoría recomienda lanzar desde el repo.
- El comando usa una ruta relativa (`.claude/hooks/stop-verificar.ps1`): asume que la sesión arranca en la raíz del repo. **HIPÓTESIS** sin probar: si arranca en una subcarpeta, el hook falla con un error no bloqueante.

## CI (`.github/workflows/tests.yml`)

| Antes | Después |
|---|---|
| 1 job secuencial: migraciones → tests → node → build | **3 jobs en paralelo**: `test` (backend completo), `seguridad` (P0-S, matriz, hasher), `frontend` (build y ESLint sin deuda nueva) |
| ESLint no corría | Corre con la regla "ninguna deuda nueva" (`scripts/eslint-sin-deuda.mjs`) |
| Sin `manage.py check` | `check` antes de los tests |
| Suite con PBKDF2: **460 s** el paso de pruebas | Suite con el hasher de pruebas |
| Corridas viejas seguían al hacer push nuevo | `concurrency` cancela la corrida anterior de la misma rama |

- El job `test` **conserva su nombre** por si es un check requerido en la protección de `main`.
- **Antes / después:**
  - Antes, medido: mediana de **8,4 min** en las últimas 30 corridas (460 s de pruebas).
  - Después: **no medido**, porque esta fase no hace push. Estimación (**HIPÓTESIS**): ~2 min de tiempo calendario. El job `test` sería ~1,5 min (16 s de instalar dependencias + suite con hasher barato; en local la suite pasó de >55 min a 103 s); `seguridad` ~1 min y `frontend` ~1 min, en paralelo.
- Validación del YAML: revisado a mano. No había ningún parser de YAML instalado y no se instalaron dependencias, así que GitHub lo validará en el primer push.

## Gates

| Gate | Dónde | Bloquea |
|---|---|---|
| Backend tests | CI `test`, verificar STANDARD/FULL, Stop hook | Sí |
| Validación frontend (build + ESLint sin deuda nueva) | CI `frontend`, verificar | Sí |
| Migraciones (`makemigrations --check`) | CI `test`, verificar (todos los modos) | Sí |
| Permisos críticos (matriz de 168 celdas) | CI `seguridad`, verificar (todos los modos) | Sí |
| Regresiones P0-S (24 tests) | CI `seguridad`, verificar (todos los modos) | Sí |
| `check --deploy` | verificar FULL | Errores sí; avisos no |
