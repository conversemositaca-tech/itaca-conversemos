# 01 · Punto de partida y validación de la auditoría

## Preservación y base

| Dato | Valor |
|---|---|
| SHA auditado | `ae759b81264f6d6b9a798e62d995082addc4406d` (`origin/main`, merge del PR #137) |
| SHA base de la implementación | `ae759b81264f6d6b9a798e62d995082addc4406d`. **Es el mismo**: `git fetch` del 1 oct 2026 confirmó que `origin/main` no avanzó |
| Rama | `chore/software-factory-phase-0`, **sin upstream** (se quitó a propósito para que un `git push` accidental no apunte a `main`) |
| Worktree | `C:\projects\itaca-factory-p0` (creado con `git worktree add` desde `origin/main`; sin checkout sobre la carpeta principal) |
| Auditoría | Respaldada con checksums MD5 en el scratchpad, copiada al worktree (19 archivos, checksums idénticos) y commiteada sola en `9f25d07`. `git diff --name-only origin/main` en ese commit: solo `docs/` |
| Carpeta original | `C:\projects\itaca-conversemos` (rama `feat/direccion-clinica`) **intacta**: los 19 documentos siguen ahí sin trackear, no se borraron ni movieron |

## Validación de las cifras de la auditoría contra el HEAD

| Cifra de la auditoría | Valor en `ae759b8` | Tras la Fase 0 | Veredicto |
|---|---|---|---|
| 9 apps Django | 9: core, correo, espacios, faro, finanzas, leads, mensajes, pacientes, usuarios | 9 | ✔ |
| 54 modelos | 54 | 55 (+`SugerenciaRiesgo`) | ✔ |
| 124 migraciones | 124 | 125 (+`pacientes/0039`) | ✔ |
| ~95 vistas | no revalidado | — | no se tocó |
| `App.jsx` ≈ 16.075 líneas | 16.075 | 16.077 (+2: importar y montar el aviso de riesgo) | ✔ |
| `App.jsx` en ~60 % de los commits | 205 de 290 commits sin merge de `main` (**71 %**). El 60 % contaba todas las ramas (255/432) | — | ✔ (matiz) |
| 1.043 tests | 1.043 | **1.071** (+24 seguridad, +2 matriz, +2 hasher) | ✔ |
| Suite local >55 min | No terminó: corrida de la auditoría abortada a los 55 min; en esta fase, 528/1.043 tests en ~116 min con carga concurrente | 103 s | ✔ (peor de lo estimado) |
| Suite con hasher rápido ~112 s | — | **103 s** (64 s de ejecución + 36 s de crear la base) | ✔ |
| ESLint 74 errores + 38 avisos | 74 / 38 (71/38 en `App.jsx`, 1 en `InputClave.jsx`, 1 en `Login.jsx`, 1 en `vite.config.js`) | 74 / 38 | ✔ |
| CI mediana ~8,4 min | 8,4 min (30 corridas); el paso de pruebas solo: **460 s** | ver [05-hook-y-ci.md](05-hook-y-ci.md) | ✔ |
| `CLAUDE.md` ≈ 85 KB, ~93 % bitácora | 84.582 bytes (blob git, LF) / 85.671 en disco (CRLF), 1.089 líneas | ver [06-contexto-claude-md.md](06-contexto-claude-md.md) | ✔ |
| Permisos en ~3 mecanismos | Confirmado por lectura (`core/permisos.py`, helpers copiados, comparaciones en línea) | Sin unificar (fuera de alcance) | ✔ |
| "realizada" en ~11 lugares; ~17 implementaciones de WhatsApp | No revalidado: fuera del alcance de la Fase 0 | — | — |

## Medición "antes" de la suite

| Entorno | Hasher | Resultado |
|---|---|---|
| Local Windows, auditoría (1 oct, 14:xx) | PBKDF2 por defecto | Abortada a los 3.322 s (~55 min) sin terminar |
| Local Windows, Fase 0 (1 oct, 16:20–18:17) | PBKDF2 por defecto | 528 de 1.043 tests en ~116 min (con otra carga en la máquina); se detuvo manualmente |
| GitHub Actions (Linux) | PBKDF2 por defecto | 460 s el paso de pruebas; 8,4 min el job (mediana) |

**Por qué Windows es tanto más lento que Linux** (**HIPÓTESIS**): PBKDF2 con ~1 M iteraciones por usuario de prueba, CPU de laptop y el antivirus inspeccionando los archivos temporales. La causa raíz, el hasher, está medida: con MD5 la misma suite tarda 103 s.
