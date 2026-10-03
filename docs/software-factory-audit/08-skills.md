# 08 · Skills candidatas

> Criterio de admisión: una skill solo existe si (a) resuelve un procedimiento que **ya** se repitió varias veces en este repo, (b) requiere juicio (si no lo requiere, es un script) y (c) cuesta menos mantenerla que repetir el trabajo.
> Hoy el repo tiene **50 skills, todas de marketing** (invocadas 7 veces en total) y **0 de ingeniería**. Las personales `criterio-de-diseno` (16 usos) y `listo-para-produccion` (2 usos) son las únicas de método.

Resumen:

| Prioridad | Skill | Patrón real que resuelve | Evidencia de repetición |
|---|---|---|---|
| **P0** | `feature` | La secuencia modelo → servicio → API → tests → pantalla → QA → respaldo → docs, hoy reinventada en cada feature | Faro #113, Fase 2 #139, Email #129–#135; "ajustes tras el QA" |
| **P0** | `qa-navegador` | Montar base demo aislada + seeds + Playwright + recorrido por rol y ancho | `CLAUDE.md` ítems 30, 31, 41, 43, 46–48; script fuera del repo |
| **P0** | `pr` | Rama, commit, PR, apilado, auto-merge, no tocar `main` | 87/339 commits con convención; #71 mergeado con versión vieja |
| **P1** | `nueva-app` | Crear app Django con tenant, permisos, respaldo, tests, rutas | Faro, correo, continuidad: 3 olvidos del respaldo |
| **P1** | `permisos-por-rol` | Auditar qué ve y qué hace cada rol en un endpoint o pantalla | 57 comparaciones en línea; fugas en adjuntos, cobros, contacto |
| **P1** | `fuente-unica` | Antes de tocar una noción de dominio, listar todos sus consumidores | "Sesión N" en 5 pantallas; "realizada" en 11 lugares |
| **P1** | `prod-solo-lectura` | Consultar producción por `railway ssh` sin escribir | Memoria del repo (no cargada); cifras de producción en commits |
| **P2** | `importador` | Importar Excel/AgendaPro con dry-run, reporte y aprobación | 5 importadores; 217 citas mal marcadas |
| **P2** | `manual-operativo` | Generar manual de recepción desde capturas reales | Mont' Sinai y Aldanna a mano el mismo día |
| **P2** | `integracion-externa` | Integrar un proveedor (WhatsApp, correo, pagos) con contrato "aceptado ≠ entregado" y smoke real | ≥11 señales de supuestos sobre terceros |

**Descartadas a propósito:** `new-crud` (el CRUD no es el cuello de botella; el template lo cubre), `release-notes` (sale de `git log` con un script), `ux-review` genérica (la cubre `criterio-de-diseno` + el checklist de `feature`), `security-review` propia (ya existe una skill integrada y un subagente es mejor, ver [09-agents.md](09-agents.md)).

---

## P0

### `feature`

| Campo | Valor |
|---|---|
| **PRIORITY** | P0 |
| **PROBLEM SOLVED** | Cada feature grande sigue la misma secuencia pero la reinventa: discovery en un `App.jsx` de 16 mil líneas, olvidos (respaldo, rol, estados de UI), QA ad hoc, documentación en `CLAUDE.md`. ~31 % de los PR son arreglos posteriores |
| **WHEN TO USE** | Cualquier cambio que toque modelo o API y pantalla, o que Max describa como "feature", "módulo", "pantalla nueva" |
| **TRIGGER** | Pedido de feature; o `/feature <descripción>` |
| **INPUTS** | Pedido de Max (puede ser un audio transcrito); `docs/<dominio>.md`; rules del dominio |
| **PROCESS** | 1. **Brief de 1 página** (`docs/features/<slug>.md`): problema, actor, criterios de aceptación, estados de UI, roles que ven/hacen qué, datos sensibles, fuera de alcance. 2. **Impacto**: ejecutar `scripts/mapa.py --consumidores <noción>` y listar archivos tocados. 3. **Contrato de API** (request/response + permisos) escrito antes de implementar → habilita paralelismo backend/frontend. 4. Clasificar decisiones según [14-future-workflow.md](14-future-workflow.md) §autonomía: solo las de HUMAN APPROVAL se preguntan, todas juntas, una vez. 5. Implementar en worktree. 6. Tests: unitarios + matriz por rol + estado. 7. `scripts/verificar.ps1`. 8. Invocar `qa-navegador`. 9. Invocar subagentes de revisión en paralelo (seguridad/datos y UX). 10. PR vía skill `pr` con la Definition of Done marcada |
| **OUTPUT** | Brief, código, tests, reporte de QA con capturas, PR con DoD marcado; `docs/<dominio>.md` actualizado si cambió una regla |
| **DEPENDENCIES** | `scripts/verificar.ps1`, `scripts/mapa.py`, skills `qa-navegador` y `pr`, rules por dominio, subagentes `revisor-seguridad-datos` y `revisor-ux` |
| **FAILURE CONDITIONS** | Brief sin criterios de aceptación; contrato de API sin permisos por rol; `verificar` en rojo; QA con errores de consola; un revisor reporta CRÍTICO |
| **HUMAN APPROVAL** | Sí, **una sola vez**: el brief (si incluye decisiones de negocio o datos clínicos) y el merge de cambios de esquema |
| **TIME SAVED** | Alto. Elimina la ronda de "ajustes tras el QA" y gran parte del ~31 % de arreglos posteriores (HIPÓTESIS: −30 a −50 % del retrabajo) |
| **CONTEXT SAVED** | Medio: el brief y las rules sustituyen la lectura de `CLAUDE.md` y del monolito |

### `qa-navegador`

| Campo | Valor |
|---|---|
| **PRIORITY** | P0 |
| **PROBLEM SOLVED** | El QA en navegador se monta desde cero cada vez (base SQLite aislada en el scratchpad, `seed_continuidad_2.py`, puertos 8032…, `VITE_API_TARGET`), y el script de auditoría de navegación vive en un scratchpad temporal. Ningún commit antes de septiembre registra QA de navegador |
| **WHEN TO USE** | Tras cualquier cambio de pantalla; antes de pedir merge |
| **TRIGGER** | Llamada desde `feature`; `/qa <pantallas>` |
| **INPUTS** | Lista de pantallas o flujo; roles a probar; anchos (390 y 1366 px) |
| **PROCESS** | 1. `scripts/qa-entorno.ps1` levanta base demo aislada con seed por dominio. 2. Playwright: por rol, recorre las pantallas, prueba estados (vacío, cargando, error forzado, mucho dato), destructivos (¿confirma?), modales (¿pierden datos?), teclado básico. 3. Captura consola y red. 4. Genera reporte con capturas |
| **OUTPUT** | `qa/<fecha>-<slug>/reporte.md` + capturas (ignorado por git o adjunto al PR) |
| **DEPENDENCIES** | Playwright, `scripts/qa-entorno.ps1`, seeds versionados (hoy en `C:\projects\itaca-demo-data`, fuera del repo) |
| **FAILURE CONDITIONS** | Error de consola; 4xx/5xx; acción destructiva sin confirmación; modal que pierde datos |
| **HUMAN APPROVAL** | No |
| **TIME SAVED** | Alto (el montaje es lo más lento del QA) |
| **CONTEXT SAVED** | Alto: la receta sale de 6 ítems de `CLAUDE.md` |

### `pr`

| Campo | Valor |
|---|---|
| **PRIORITY** | P0 |
| **PROBLEM SOLVED** | Convenciones decididas de nuevo en cada sesión (formato de commit, apilado, dónde documentar). PR mergeados a los ~8 min con commits sin pushear (#71). `CLAUDE.md` editado en 40 commits como bitácora |
| **WHEN TO USE** | Al cerrar cualquier trabajo |
| **TRIGGER** | Fin de `feature`/bugfix; `/pr` |
| **INPUTS** | Rama, brief, resultado de `verificar` y `qa-navegador` |
| **PROCESS** | 1. Verifica que no hay commits sin pushear. 2. Commit `tipo(ámbito): frase` en español, cuerpo "por qué". 3. PR con plantilla (resumen, DoD marcado, riesgos, cómo probar, migraciones y rollback). 4. Si es apilado, base = PR anterior. 5. Activa auto-merge (merge solo con CI verde). 6. **No** edita `CLAUDE.md` salvo que cambie una regla permanente |
| **OUTPUT** | PR listo |
| **DEPENDENCIES** | `gh`, plantilla `.github/pull_request_template.md`, hook que bloquea push a `main` |
| **FAILURE CONDITIONS** | CI rojo; commits locales sin pushear; DoD incompleto |
| **HUMAN APPROVAL** | Merge de PR con migraciones o con cambios en datos clínicos o permisos |
| **TIME SAVED** | Medio |
| **CONTEXT SAVED** | Medio |

---

## P1

### `nueva-app`

- **PROBLEM SOLVED:** Faro, correo y continuidad repitieron la misma estructura y las tres olvidaron el respaldo en su primer commit.
- **TRIGGER:** "crear módulo/app nueva".
- **PROCESS:** genera la app desde el template (ver [11-templates.md](11-templates.md)): modelos con `ModeloTenant`, `services.py`, `api.py` con `RolPermission`, serializers de entrada, `urls.py`, `factories.py`, tests de aislamiento por tenant y matriz por rol, entrada en `docs/<app>.md`, rule `.claude/rules/<app>.md`. El respaldo se cubre solo si la lista ya es derivada.
- **OUTPUT:** app compilando con tests verdes.
- **HUMAN APPROVAL:** el esquema de datos (regla vigente de `CLAUDE.md` §2b: "mostrar el esquema antes de migrar").
- **TIME SAVED:** medio. **CONTEXT SAVED:** medio.

### `permisos-por-rol`

- **PROBLEM SOLVED:** permisos aplicados por 3 mecanismos, 57 comparaciones en línea; fugas confirmadas en adjuntos, cobros, contacto, tokens de firma; el 500 de "Hoy" para psicólogos.
- **TRIGGER:** cambio en `api.py`, `serializers.py` o `permisos.py`; `/permisos <endpoint|pantalla>`.
- **PROCESS:** genera la matriz endpoint × rol × acción (desde el router + un recorrido real con cada rol), la compara con la matriz esperada declarada en `docs/permisos.md`, y lista campos sensibles visibles por rol en cada serializer.
- **OUTPUT:** diff de matriz + tests que lo fijan.
- **HUMAN APPROVAL:** cambiar la matriz esperada (es una decisión de negocio y de privacidad).
- **TIME SAVED:** alto en riesgo evitado.

### `fuente-unica`

- **PROBLEM SOLVED:** "Sesión N" se arregló pantalla por pantalla ("otras cinco pantallas seguían leyendo el contador manual", #69). "Realizada" está en 11 lugares; "pausa" tiene 3 representaciones.
- **TRIGGER:** tocar una noción del glosario de dominio (sesión, asistencia, activo, riesgo, retención, sede, teléfono).
- **PROCESS:** `scripts/mapa.py --consumidores <noción>` → lista de lecturas; propone el resolver único; añade el guard que prohíbe leer el campo legado.
- **OUTPUT:** lista de consumidores + plan + guard.
- **HUMAN APPROVAL:** no (técnico), salvo que cambie la definición de negocio.

### `prod-solo-lectura`

- **PROBLEM SOLVED:** las consultas a producción (cifras de commits, auditorías de duplicados) se hacen por `railway ssh` con receta que vive en una memoria que ya no se carga.
- **PROCESS:** solo `SELECT`/ORM de lectura vía un comando de management dedicado; salida agregada, nunca filas con PII al chat.
- **HUMAN APPROVAL:** **sí, siempre**, antes de conectarse.
- **FAILURE CONDITIONS:** cualquier operación de escritura → bloquear.

---

## P2

### `importador`
Importaciones con `--dry-run` obligatorio, reporte de conteos por categoría y aprobación humana antes de escribir. Evidencia: 5 importadores, cortes de proxy, encoding, 217 citas marcadas como web. Útil para el **próximo cliente** (migrar desde AgendaPro, Excel, otro sistema), más que para Conversemos.

### `manual-operativo`
Generar el manual de recepción (o de cualquier rol) a partir de capturas reales del QA y del brief de cada pantalla. Evidencia: dos manuales hechos a mano el 1 oct (Mont' Sinai, Aldanna). Depende de `qa-navegador` (reutiliza sus capturas).

### `integracion-externa`
Checklist + smoke real para un proveedor nuevo: contrato "aceptado ≠ entregado", reintentos, idempotencia, firma de webhooks, nada de PII en logs, degradación elegante. Evidencia: ≥11 señales (Evolution, Railway, Meta, navegador). El cliente de correo (`correo/`) es el ejemplo a seguir.

---

## Lo que NO debe hacerse con skills

- Meter en una skill lo que es determinista (correr tests, comparar migraciones, generar changelog): eso es **script**.
- Duplicar en una skill las reglas de dominio: eso es **rule por ruta**, que se carga sola al tocar los archivos.
- Instalar packs de skills de terceros en el repo de ingeniería: el pack de marketing cuesta ~7 K tokens por sesión y se usó 7 veces.
