# 17 · Métricas para saber si la optimización funciona

> Regla: no se inventan números actuales. Si la línea base puede calcularse con datos que ya existen (git, `gh`, CI), se indica cómo y, cuando se calculó en esta auditoría, el valor. Si no, **BASELINE NOT AVAILABLE** y cómo empezar a medirla.
> Todas se miden **por mes** y se comparan antes y después de cada iniciativa P0.

## 1. Tabla de métricas

| Métrica | Definición operativa | Fuente | Línea base | Valor al 1 oct 2026 | Meta tras P0 (HIPÓTESIS) |
|---|---|---|---|---|---|
| **PROMPTS / FEATURE** | Mensajes de Max en las sesiones que produjeron un PR de feature | Transcripciones `~/.claude/projects/*/*.jsonl` cruzadas con la rama del PR | BASELINE NOT AVAILABLE (las transcripciones existen pero hay que asociarlas a PR; las sesiones lanzadas desde `C:\Users\mirai` mezclan proyectos) | — | Medir 1 mes y luego −30 % |
| **HUMAN INTERRUPTIONS / FEATURE** | Veces que Claude se detiene a preguntar durante una feature | Transcripciones (turnos de Claude que terminan en pregunta) | BASELINE NOT AVAILABLE | — | ≤1 por feature (la tanda del brief) |
| **HUMAN DECISIONS / FEATURE** | Decisiones registradas como HUMAN APPROVAL en el brief | `docs/features/*.md` (no existe aún) | BASELINE NOT AVAILABLE | — | Registrar; no es para bajar sino para hacerlo explícito |
| **REWORK** | % de PR mergeados que son correcciones de algo mergeado antes | `gh pr list` + clasificación por título (`fix`, "arregla", "corrige", "ajustes tras") | BASELINE AVAILABLE | **~31 %** (38 de 121); setiembre: 1 de cada 4 commits | ≤15 % |
| **BUGS FOUND AFTER IMPLEMENTATION** | Commits con "Reportado por <persona>" o fix que referencia un PR anterior | `git log --grep` | BASELINE AVAILABLE (parcial) | 15 commits con "Reportado por" (el resto no lo declara) | Convención obligatoria en `pr` para medir bien |
| **REGRESSION RATE** | PR de corrección cuyo bug lo introdujo un PR de los 30 días previos | Cruce de archivos tocados (`git log --name-only`) | BASELINE AVAILABLE (cálculo pendiente) | No calculado en esta auditoría | — |
| **QA AUTOMATION RATE** | % de PR con evidencia de QA automatizado (tests nuevos + QA de navegador) | Diff de PR (archivos `tests*.py`) + reporte de `qa-navegador` | BASELINE AVAILABLE (tests) / NOT AVAILABLE (navegador) | Archivos de test tocados: jul 0, ago 43, sep 102 | 100 % con tests; 100 % de PR con UI con reporte de QA |
| **CONTEXT REUSE** | Tokens fijos por sesión y % relevante para la tarea | Medición de `CLAUDE.md` + memoria + listado de skills | BASELINE AVAILABLE | **≈31 K tokens fijos; 5–7 % relevante** | ≈3 K fijos; rules por ruta |
| **CODE REUSE** | % de LOC de un proyecto nuevo que viene de paquetes del core | `cloc` del proyecto vs del paquete | BASELINE AVAILABLE (por copia) | Conversemos heredó 7 % de `clinica-saas`; Mont' Sinai 75 % de Conversemos (por copia, con drift) | Próximo proyecto: ≥40 % por dependencia, 0 % por copia |
| **TIME TO FEATURE** | Primer commit de la rama → merge | `git log` + `gh pr view --json mergedAt` | BASELINE AVAILABLE | PR abierto → merge: mediana **8 min** (no mide la feature completa: falta el primer commit) | Medir primer commit → merge |
| **TIME TO FIX** | Reporte del equipo → merge del arreglo | Requiere registrar la hora del reporte | BASELINE NOT AVAILABLE | — | Registrar el reporte como issue o en el brief |
| **BUILD FAILURE RATE** | % de corridas de CI fallidas | `gh run list` | BASELINE AVAILABLE | **2 de 30** últimas corridas (~7 %); mediana 8,4 min | <5 %; duración ~3 min con hasher de test |
| **AUTONOMOUS COMPLETION RATE** | % de features que llegan a PR verde sin intervención de Max fuera del brief | Transcripciones + PR | BASELINE NOT AVAILABLE | — | ≥60 % en 3 meses |
| **TIEMPO DE SUITE LOCAL** (adicional) | Duración de `manage.py test` | `scripts/test.ps1` registra el tiempo | BASELINE AVAILABLE | >55 min con hasher por defecto (abortado); **112 s** con hasher de test | ≤2 min |
| **FUGAS DE ACCESO ABIERTAS** (adicional) | Hallazgos CRÍTICO/ALTO de seguridad sin cerrar | `docs/software-factory-audit/01-current-system.md` §7 + `revisor-seguridad-datos` | BASELINE AVAILABLE | Ver doc 01: 14 hallazgos, 3 críticos | 0 críticos |
| **PROPAGACIÓN DE ARREGLOS** (adicional) | PR necesarios para llevar un arreglo universal a todos los sistemas | Conteo manual | BASELINE AVAILABLE | Ojito: 8 PR + Apps Script | 1 PR al core + subir versión |
| **ESLINT** (adicional) | Errores y avisos en el frontend | `eslint .` | BASELINE AVAILABLE | **74 errores + 38 avisos** | No sube nunca (baseline en CI); baja con la extracción de componentes |

## 2. Cómo instrumentarlas sin burocracia

| Necesidad | Mecanismo | Costo |
|---|---|---|
| Rework, regresión, CI, time to merge | `scripts/metricas.py` mensual sobre `git log`, `gh pr list` y `gh run list` | Una tarde para escribirlo; 0 después |
| Prompts, interrupciones, autonomía | Script que lee las transcripciones `.jsonl` de las sesiones lanzadas **desde el repo** y las asocia a la rama del worktree | Requiere lanzar Claude desde la carpeta del repo (también recomendado en [06-context-audit.md](06-context-audit.md)) |
| Decisiones humanas | Sección "Decisiones de Max" en el brief | 0 |
| Time to fix | El reporte del equipo entra como issue de GitHub (o línea en el brief con fecha) | Bajo |
| Contexto | `scripts/contexto.py`: mide tamaño de `CLAUDE.md`, rules y listado de skills | 0 |

## 3. Tablero mínimo (una vez por mes)

1. Rework % (meta ≤15 %).
2. Duración del CI y tasa de fallo.
3. Tokens fijos por sesión.
4. Interrupciones por feature.
5. Fugas críticas abiertas.
6. LOC del próximo proyecto que vienen del core.

Si una iniciativa P0 no mueve ninguna de estas seis en dos meses, se revisa o se retira.
