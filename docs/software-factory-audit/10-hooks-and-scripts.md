# 10 · Hooks y scripts: automatización determinista

> Objetivo: que ninguna comprobación dependa de la memoria de Max o de Claude, y que el razonamiento que siempre da el mismo resultado deje de costar tokens.
> Mediciones hechas en esta auditoría sobre una copia de `origin/main` en un scratchpad (sin tocar el repo ni ninguna base real):

| Medición | Resultado |
|---|---|
| `manage.py test` con el hasher por defecto (PBKDF2, ~1 M iteraciones, ~0,9 s por `create_user`) | **Abortado a los 55 min** sin terminar |
| `manage.py test` con `PASSWORD_HASHERS = [MD5PasswordHasher]` **solo en settings de test** | **1.043 tests OK en 63 s** + 44 s de creación de BD = **112 s en total** |
| `manage.py test --parallel` en Windows | Falla con `PermissionError: [WinError 5] Acceso denegado` (multiprocessing spawn). Coincide con la advertencia enterrada en el ítem 42 de `CLAUDE.md` |
| `manage.py check` | Sin problemas |
| CI (`tests.yml`, últimas 30 corridas) | Mediana **8,4 min**, máximo 11,3; 28 OK, 2 fallos |
| `npm run build` (Vite) | 1,4 s; bundle principal **1,1 MB** (287 KB gzip) en un solo chunk, más `exceljs` 930 KB y `pptxgen` 368 KB |
| `eslint .` | **74 errores + 38 avisos** (109 en `App.jsx`): `exhaustive-deps` 37, `set-state-in-effect` 31, `static-components` 20, `no-unused-vars` 17. **No corre en CI**; `CLAUDE.md` compara a mano contra "106 avisos de main" en ~16 ítems |
| Linters de Python (ruff, flake8, black), pre-commit, tipado | **No existen** |
| Tests de frontend (Vitest, Playwright versionado) | **No existen** |
| CI | `makemigrations --check`, tests (en **SQLite**; producción es Postgres), build. Sin ESLint, sin `check --deploy`, sin smoke post-deploy |

**Hallazgo principal de esta sección:**

- **FINDING:** la suite es lenta por el hasher de contraseñas, no por su tamaño.
- **EVIDENCE:** 112 s con el hasher MD5 de test frente a más de 55 minutos con el hasher por defecto en la misma máquina. La memoria del repo registra "811 pruebas, ~22 min", y `CLAUDE.md` pide correrlas a archivo, sin `--parallel` y "con paciencia".
- **WHY IT MATTERS:** con una suite de 2 minutos se puede correr en el hook `Stop` y antes de cada PR. Con una de 20 a 55 minutos, Claude y Max la saltan o la dejan para el CI, y los errores se descubren tarde.
- **PROPOSED MECHANISM:** `config/settings_test.py` (o un `if "test" in sys.argv`) con `PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]`. Es la práctica estándar de Django para tests y **no** afecta a producción.
- **EXPECTED BENEFIT:** el CI baja de ~8 a ~3 minutos (**HIPÓTESIS**: el runner de Linux es más rápido que Windows, pero la proporción del hasher es la misma). Lo más importante: la verificación completa pasa a ser barata en cada turno de Claude.

---

## 1. Hooks

Los hooks de Claude Code se declaran en `.claude/settings.json` del proyecto. Los de git (pre-commit, pre-push) pueden ser hooks de git o reglas de protección de rama en GitHub; se indica cuál conviene.

### 1.1 PRE-EDIT (`PreToolUse`)

| Hook | TRIGGER | COMMAND | PURPOSE | FAIL CONDITION | BLOCKING / WARNING | COST |
|---|---|---|---|---|---|---|
| `bloquear-pii` | Write/Edit/Bash sobre cualquier ruta | `.claude/hooks/bloquear-pii.ps1` (revisa ruta y contenido) | Cumplir Ley 29733; no repetir #48, #72, #88 | Escribir `*.xlsx`, `*.sqlite3` o `datos_pacientes_reales*` dentro del repo; teléfonos de 9 dígitos o DNI en `docs/`, `.claude/`, `CLAUDE.md`; leer `.env` | **Bloquea** | <1 s |
| `bloquear-main` | Bash con `git` | `.claude/hooks/bloquear-main.ps1` | Push a `main` = deploy a producción | `git push` a `main`; `--force` a ramas compartidas; `git checkout`/`switch` en la carpeta principal | **Bloquea** | <1 s |
| `aviso-claude-md` | Edit/Write en `CLAUDE.md` | script de 5 líneas | Que `CLAUDE.md` deje de ser bitácora (40 commits lo tocan) | Siempre | Aviso | <1 s |
| `aviso-lista-manual` | Edit en `core/respaldo.py`, `config/urls.py` | script | Hotspots con listas a mano | Siempre | Aviso ("¿se puede derivar?") | <1 s |

### 1.2 POST-EDIT (`PostToolUse`)

| Hook | TRIGGER | COMMAND | PURPOSE | FAIL CONDITION | BLOCKING / WARNING | COST |
|---|---|---|---|---|---|---|
| `formato-py` | Edit en `*.py` | `ruff format <archivo>; ruff check <archivo>` | Estilo y errores obvios sin gastar razonamiento | Errores de ruff | Aviso (inyecta el resultado) | ~0,3 s |
| `migraciones` | Edit en `*/models.py` | `python manage.py makemigrations --check --dry-run` | Detectar la migración olvidada al editar, no en el CI | Cambios sin migración | Aviso | ~3 s |
| `lint-front` | Edit en `frontend/src/**/*.{js,jsx}` | `npx eslint <archivo>` | Hooks de React mal usados (68 errores hoy) | Errores **nuevos** en el archivo | Aviso | ~2 s |

### 1.3 PRE-COMMIT (hook de git o paso de la skill `pr`)

| Hook | COMMAND | PURPOSE | FAIL | BLOCKING | COST |
|---|---|---|---|---|---|
| `pii-staged` | Escaneo de `git diff --cached` con las mismas reglas de `bloquear-pii` | Segunda red (por si se escribió fuera de Claude) | PII en el diff | **Bloquea** | <1 s |
| `ruff-staged` | `ruff check` de los `.py` staged | — | Errores | **Bloquea** | ~1 s |

### 1.4 PRE-PUSH

| Hook | COMMAND | PURPOSE | FAIL | BLOCKING | COST |
|---|---|---|---|---|---|
| `no-main` | Rechaza el push si la rama destino es `main` | Producción | Push a `main` | **Bloquea** | <1 s |
| `verificar-rapido` | `scripts/verificar.ps1 -Rapido` (check + migraciones + tests de las apps tocadas) | Evitar CI rojo | Fallo | **Bloquea** | 30–90 s |

### 1.5 STOP / FINAL VALIDATION (`Stop`)

| Hook | TRIGGER | COMMAND | PURPOSE | FAIL CONDITION | BLOCKING / WARNING | COST |
|---|---|---|---|---|---|---|
| `stop-verificar` | Claude intenta terminar el turno con cambios de código sin verificar desde la última edición | `scripts/verificar.ps1 -Rapido` | Que "terminado" signifique verificado | `check`, migraciones o tests de las apps tocadas en rojo | **Bloquea** (Claude debe arreglar o explicar) | 30–120 s gracias al hasher rápido |
| (existente) texto a voz | — | `leer-en-voz-alta.ps1` | — | — | — | Mantener |

### 1.6 CI y GitHub (no son hooks de Claude, pero cierran el circuito)

| Gate | Cambio propuesto en `tests.yml` / GitHub | PURPOSE | BLOCKING |
|---|---|---|---|
| Hasher de test | `settings_test.py` | Suite de ~8 a ~3 min | — |
| Postgres en CI | Servicio `postgres:17` en el job | Hoy se prueba en SQLite y se despliega en Postgres | **Bloquea** |
| ESLint | `npm run lint` con baseline: falla solo si sube el número de errores respecto de `main` | Dejar de comparar "106 avisos" a mano | **Bloquea** |
| `check --deploy` | `python manage.py check --deploy` con settings de producción | `DEBUG=True` y `SECRET_KEY` insegura por defecto | **Bloquea** |
| Matriz por rol | Test generado desde `docs/permisos.md` | Fugas y 500 por rol | **Bloquea** |
| Env vars | `scripts/env-check.py` | 56 variables leídas, 23 documentadas | **Bloquea** si falta una nueva |
| Protección de rama | `main` solo por PR con CI verde; auto-merge | Merges a los 8 min con commits sin pushear (#71) | **Bloquea** |
| Smoke post-deploy | Job tras el deploy de Railway: `curl` a `/api/hora/` (o `/healthz`) en cada host | Caída total del 1 oct (#138) | Alerta en el PR (nunca por WhatsApp) |

---

## 2. Scripts: AI TASK → SCRIPT

| Tarea que hoy razona Claude | Script candidato | Qué hace | Por qué no necesita IA | Evidencia |
|---|---|---|---|---|
| "Verificado: check, makemigrations --check, tests, build, ESLint igual a main" | `scripts/verificar.ps1 [-Rapido]` | Corre todo, compara ESLint con la baseline de `main`, devuelve un código de salida y un resumen de 10 líneas | Resultado binario | Repetido en ~16 ítems de `CLAUDE.md` |
| Correr la suite en Windows (build antes si cambió `frontend/`, sin `--parallel`, `--noinput`, salida a archivo, no usar `\| tail`) | `scripts/test.ps1 [apps…]` | Encapsula las trampas | Receta fija | Ítem 42 + memoria |
| Montar entorno de QA (sqlite aislado, seeds, puertos, `VITE_API_TARGET`) | `scripts/qa-entorno.ps1 -Seed <dominio>` | Levanta backend y Vite contra una base demo | Receta fija | Ítems 30, 31, 41, 43, 46–48 |
| Auditoría de navegación del sitio | `scripts/auditoria-navegacion.py` (versionar el que hoy vive en un scratchpad temporal) | Recorre `SITE_ROUTES` y reporta enlaces muertos | Determinista | Ítem 36; #119 |
| "¿Quién lee este campo / esta noción?" | `scripts/mapa.py --consumidores <campo>` | `grep` estructurado por capa (modelo, serializer, vista, componente, test) | Búsqueda | "Otras cinco pantallas seguían leyendo el contador manual" (#69) |
| "¿Qué ve cada rol?" | `scripts/matriz-permisos.py` | Recorre el router, llama cada endpoint con cada rol en una BD de test y compara con `docs/permisos.md` | Comparación | Fugas confirmadas; 500 de "Hoy" |
| Lista de apps del respaldo | Derivar en `core/respaldo.py` desde `apps.get_models()` | Elimina la lista a mano | Determinista | 3 olvidos + 11 tablas; conflicto de merge con la rama DC |
| `.env.example` al día | `scripts/env-check.py` | Extrae `os.environ`/`env(` del código y compara con `.env.example` | Determinista | 56 vs 23 |
| Changelog / registro | `scripts/changelog.py` | Genera el registro desde `git log` y títulos de PR | Determinista | 46 ítems de bitácora en `CLAUDE.md` |
| Estado de despliegue | `railway deployment list` envuelto en `scripts/estado-prod.ps1` | — | Determinista | Ítems "⏳ SIN desplegar" falsos |
| Crear worktree para una sesión paralela | `scripts/nuevo-worktree.ps1 <rama>` | `git worktree add`, junction a `node_modules`, `.venv` compartido, puerto libre | Receta fija | Memoria del repo; 3 worktrees huérfanos |
| Limpiar worktrees huérfanos | `scripts/limpiar-worktrees.ps1` | Lista worktrees cuya rama ya está mergeada | Determinista | 3 huérfanos hoy |
| Detección de duplicados de pacientes | Comando `detectar_duplicados --reporte` (programado) | Reporte, **sin** fusionar | Determinista; la fusión sigue siendo humana | ≥10 PR de identidad |
| Smoke post-deploy | `scripts/smoke.ps1` | 200 en cada host y endpoints clave | Determinista | #138 |
| Mapa del sistema (apps, modelos, endpoints, roles) | `scripts/mapa.py --resumen` | Genera lo que hoy se escribe a mano en `CLAUDE.md` y `README.md` | Generable | `README.md` obsoleto ("3 apps") |

---

## 3. Lo que NO conviene automatizar como hook

| Idea | Por qué no |
|---|---|
| Suite completa en cada edición | Aunque baje a 2 min, en cada Edit es demasiado; va en `Stop` y en pre-push con "-Rapido" |
| Bloquear toda edición de `CLAUDE.md` | A veces cambia una regla permanente; basta con avisar |
| QA de navegador como hook | Necesita juicio sobre qué recorrer: es una skill |
| Revisión de seguridad como hook | Necesita juicio: es un subagente |
| Fusión automática de duplicados | Decisión humana caso por caso (ver [03-business-processes.md](03-business-processes.md) §6) |

---

## 4. Orden de implementación sugerido

1. Hasher de test (una línea; desbloquea todo lo demás).
2. `scripts/test.ps1` y `scripts/verificar.ps1`.
3. Hooks `bloquear-main` y `bloquear-pii`.
4. Protección de rama + auto-merge + ESLint con baseline en CI.
5. Hook `Stop` con `verificar -Rapido`.
6. Respaldo derivado + `env-check` + `check --deploy`.
7. Postgres en CI + matriz por rol.
8. Smoke post-deploy.
