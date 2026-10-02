# 03 · Verificación rápida y `scripts/verificar.ps1`

## Hasher de pruebas

- `config/settings.py`: bajo `EJECUTANDO_TESTS` (`sys.argv[1] == "test"`), `PASSWORD_HASHERS = [MD5PasswordHasher]`.
- **Imposible en producción:** el servidor arranca con gunicorn (`sys.argv[0]` = gunicorn, sin "test"). `core/tests_hasher.py` lo comprueba cargando la configuración en un proceso aparte con argv de gunicorn, runserver y migrate, y exige el hasher por defecto de Django.
- Resultado: **1.071 tests en 103 s** (64 s de ejecución + 36 s de crear y migrar la base en memoria). Antes: más de 55 minutos sin terminar en local.

## `scripts/verificar.ps1`

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verificar.ps1 -Modo FAST      # ciclo de edición
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verificar.ps1 -Modo STANDARD  # declarar terminado
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verificar.ps1 -Modo FULL      # integrar / publicar
```

| Paso | FAST | STANDARD | FULL | Falla si… |
|---|---|---|---|---|
| `manage.py check` | ✔ | ✔ | ✔ | hay errores de configuración |
| `makemigrations --check --dry-run` | ✔ | ✔ | ✔ | falta una migración |
| Tests backend | apps con cambios **sin commitear** + `tests_seguridad_p0` + `tests_matriz_permisos` (si se toca `config/`, todo `core`) | suite completa | suite completa | falla un test |
| ESLint "ninguna deuda nueva" | solo los JS/JSX cambiados | todo el frontend | todo el frontend | un archivo tiene **más errores** que su línea base (más avisos = AVISO) |
| `npm run build` | — | ✔ | ✔ | no compila |
| `check --deploy` con `DEBUG=False` | — | — | ✔ | errores (los `security.W*` son AVISO) |

- **Siempre SQLite temporal.** El script fija `DATABASE_URL` a un archivo en `%TEMP%`, aunque exista un `.env` con la base de producción; `load_dotenv` no pisa variables ya definidas.
- Una carpeta de trabajo por worktree: dos sesiones en paralelo no comparten base ni logs.
- Códigos de salida: `0` OK (puede haber avisos), `1` algún paso falló, `2` entorno incompleto (falta Python o Node).
- Salida: una línea por paso con su tiempo. `-Silencioso` imprime solo las fallas, y lo usa el Stop hook.
- Comandos descubiertos en el repo, no supuestos: `.venv` del worktree o del repo principal (`git rev-parse --git-common-dir`), `npm run build` y `eslint` de `frontend/package.json`.

## Mediciones (1 oct 2026, misma máquina, sin otra carga)

| Modo | Tiempo | Detalle |
|---|---|---|
| FAST, solo cambios en `scripts/` | **20,7 s** | 341 tests de `core` (cambió `config/`) |
| FAST, cambio en un `.jsx` | **44,7 s** | 26 tests de seguridad + ESLint del archivo (detectó el error nuevo) |
| STANDARD | **141 s** | 1.071 tests (97,6 s), ESLint 37 s, build 2,8 s |
| FULL | **138 s** | lo mismo + `check --deploy`: 1 aviso (`security.W021`, HSTS preload) |

## Lección registrada: `--keepdb` en archivo es contraproducente en Windows

Se probó reutilizar la base de prueba (`--keepdb` sobre un archivo SQLite) para ahorrar los ~36 s de creación. Resultado medido: **1.071 tests en 2.908 s** contra 64 s en memoria. Se quitó (`bab5269`). **HIPÓTESIS** de la causa: cada test escribe a disco y el antivirus inspecciona `%TEMP%`.

## Lección registrada: PowerShell 5.1 y stderr

Con `$ErrorActionPreference = "Stop"`, cualquier línea de git en stderr, incluido el aviso de finales de línea, abortaba el script. En el Stop hook eso equivalía a "dejar terminar sin verificar". Ambos scripts usan `Continue` (`d1e4da9`).

## Controles manuales que dejan de serlo

| Antes (texto repetido en ~16 ítems de `CLAUDE.md`) | Ahora |
|---|---|
| "`manage.py check`" | paso 1 automático |
| "`makemigrations --check`" | paso 2 automático (también en CI) |
| "N tests nuevos. Suite: M" (correr a mano, a archivo, sin `--parallel`, sin `\| tail`) | paso 3; tiempos y conteo en el resumen |
| "build de Vite" | paso 5 automático (también en CI) |
| "ESLint idéntico a main (106 avisos)", comparado a ojo | paso 4 contra `scripts/eslint-baseline.json` (también en CI) |
