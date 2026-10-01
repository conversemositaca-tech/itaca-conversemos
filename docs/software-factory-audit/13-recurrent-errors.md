# 13 · Errores y decisiones que estamos pagando más de una vez

> Fuente: clasificación de los 121 PR mergeados y de los commits de corrección (`git log --all`, cuerpos de commit, `gh pr list`), contrastada con el código de `origin/main`. Hashes y PR citados son verificables con `git show <hash>` / `gh pr view <n>`.
> ~38 de 121 PR mergeados (**~31 %**) son correcciones. En septiembre, 1 de cada 4 commits es un arreglo.

## Resumen

| # | Patrón | Categoría | Señales | Costo relativo | Automatizable |
|---|---|---|---|---|---|
| 1 | El teléfono decide quién es el paciente | DATABASE · LOGIC | ≥10 | **Muy alto** (historias clínicas mezcladas) | Parcial: test de contrato + detector nocturno |
| 2 | "Sesión N" con varias fuentes de verdad | LOGIC · REGRESSION | ≥8 | **Muy alto** (cola, liquidación, KPIs) | Sí: guard que prohíba leer el campo legado |
| 3 | Supuestos sobre terceros sin verificar | DEPLOY/INFRA · VALIDATION | ≥11 | Alto (caídas totales, mensajes que no llegan) | Sí: smoke post-deploy, fixtures reales |
| 4 | Regla de negocio copiada en varios sitios | ARCHITECTURE · REGRESSION | ≥9 | Alto (500 a un rol, paneles vacíos) | Sí: test de humo por rol, lint |
| 5 | Tablas nuevas fuera del respaldo | DATABASE | 3 + 11 tablas previas | Medio (ya lo caza un test) | Sí: derivar la lista de los modelos |
| 6 | Documentación que queda mintiendo / PR mergeado con versión vieja | DOCUMENTATION · COMMUNICATION | ≥6 | Medio | Sí: separar registro de reglas, merge solo tras CI y push |
| 7 | "Hoy" con el reloj del cliente | LOGIC | 3 | Bajo | Sí: regla + helper único |
| 8 | Consultas N+1 y payloads pesados | PERFORMANCE | 5 | Medio | Sí: `assertNumQueries` en endpoints de listas |
| 9 | Fugas de privacidad | PERMISSIONS | ≥6 | **Alto en riesgo** (Ley 29733) | Sí: hook de PII + tests de serializer por rol |
| 10 | UX visible solo al usarlo | UX | ≥6 | Medio | Parcial: checklist de estados + QA de navegador por skill |
| 11 | Datos importados mal marcados | DATABASE · VALIDATION | 3 | Medio | Parcial: dry-run con reporte obligatorio |

---

## 1 · El teléfono decide quién es el paciente — DATABASE / LOGIC

- **SYMPTOM:** pacientes duplicados; la cita de una consulta nueva quedó colgada en la ficha de otra persona (historia clínica mezclada); menores sin celular "inencontrables"; un lead perdido con la etiqueta "Ya es paciente"; reservas web que no creaban lead.
- **ROOT CAUSE:** la premisa "mismo teléfono = misma persona" es falsa en un servicio con infantojuvenil (140 números compartidos por 307 fichas, 19 %). Además el match vivía en varios flujos con criterios distintos (agendar consulta sí, cerrar lead no, reserva web otro). Las importaciones no tenían clave de identidad estable. La nota de procesos contó **5 criterios de deduplicación** distintos.
- **SIGNALS (≥10):** `7b231df`, #32, #52, #65, #86, #90, #93 (+`5ebd73a`), #99, #103 (+`6cfcf60`), docs #94 y #100.
- **HOW TO PREVENT EARLIER:** definir el modelo de identidad (persona vs contacto vs tutor) antes de importar o crear el primer flujo de alta; una sola función `resolver_identidad()` usada por todos los puntos de creación.
- **AUTOMATION:** test de contrato que recorra todos los puntos de creación de `Paciente` (lead, reserva web, importador, cierre de lead) contra la misma batería de casos (madre e hijo, hermanos, teléfono corto, menor sin celular). Comando nocturno de detección de duplicados con reporte (no de fusión: la fusión sigue siendo humana).
- **Lección para la fábrica:** la identidad de la persona atendida es una pieza de **core** que todo sistema de servicios necesita. Se diseña una vez.

## 2 · "Sesión N" con varias fuentes de verdad — LOGIC / REGRESSION

- **SYMPTOM:** "Sesión 0"; línea de tiempo vacía; alertas S3 que saltaban en S2; retención S3+ calculada sobre 7 pacientes en vez de 769; cola de continuidad con 104 pacientes de más; la consulta inicial contada como sesión 1 y **liquidada como sesión** (S/20 vs S/38).
- **ROOT CAUSE:** tres orígenes del número (`Paciente.n_sesion` manual, `Cita.n_sesion`, conteo de asistidas) más la numeración acumulada de AgendaPro. La consulta no era un tipo distinto. Se arregló pantalla por pantalla.
- **SIGNALS (≥8):** #34 `6934cb8`, #67, #68, #69 ("otras cinco pantallas seguían leyendo el contador manual"), `ce8c3c6`/`ce3f723` (81 de 391 pacientes mal), #71 (commits que no llegaron a producción), #89 (127 de 244 citas web mal contadas), #139 (estado formal del proceso).
- **HOW TO PREVENT EARLIER:** un único *resolver* de dominio desde el inicio; antes de declarar un arreglo, buscar todos los consumidores del campo viejo; deprecar y eliminar el campo legado.
- **AUTOMATION:** test o lint que falle si se lee `Paciente.n_sesion` fuera del resolver; tests de propiedad sobre secuencias de citas (consulta, procesos sucesivos, importadas).
- **Lección:** la regla "una noción, una función" vale también para asistencia, riesgo, retención, "activo" y facturación, que hoy tienen entre 2 y 5 implementaciones cada una (ver [03-business-processes.md](03-business-processes.md)).

## 3 · Supuestos sobre terceros sin verificar — DEPLOY/INFRA / VALIDATION

- **SYMPTOM:** imágenes que nunca llegan (200 con estado PENDING); "WhatsApp enviado ✓" sin entrega real; TypeError crudo mostrado a la coordinadora; JPEG rechazado como "dañado"; sistema completo en 400 tras cambiar de dominio; estáticos rotos en producción; deploy que no se dispara; PDFs sin color; tests con 429 en CI.
- **ROOT CAUSE:** confiar en el código de respuesta o en una variable del proveedor (HTTP 200 = enviado, mimetype del cuerpo, `RAILWAY_PUBLIC_DOMAIN` estable, el navegador imprime fondos) sin probarlo contra el entorno real.
- **SIGNALS (≥11):** `a7dd1f2` (SSL de BD), `9245c42` (forzar redeploy), `e7232db` (BASE_URL), #77, #78, #84, #85, #54, `604532e`, `66ff1b4`/#138 (**sin mergear**), #81.
- **HOW TO PREVENT EARLIER:** smoke test después de cada deploy contra todos los hosts; checklist de cambio de dominio; para Evolution, prueba con acuse real antes de declarar listo.
- **AUTOMATION:** job post-deploy con `curl` a un endpoint de salud en cada host (Railway + dominios propios), esperando 200; test de `ALLOWED_HOSTS` que incluya `.up.railway.app`; fixtures con medios reales de WhatsApp.

## 4 · Regla de negocio copiada en varios sitios — ARCHITECTURE / REGRESSION

- **SYMPTOM:** 500 en la pantalla "Hoy" de los psicólogos (regla de alcance repetida a mano con una variable inexistente); panel del colegio diciendo "no hay resultados" habiéndolos (campo `evaluados` que nadie llenaba); criterio de rol víctima/agresor en dos copias; rutas del sitio escritas a mano (enlaces a WordPress, enlaces muertos); frontend que omitía campos que el backend aceptaba; panel que no mostraba lo que la API ya devolvía; sede comparada en minúscula pero escrita a mano ("Lima").
- **ROOT CAUSE:** reglas (rol, rutas, sede) copiadas en un monolito frontend de 16.075 líneas sin capa compartida; backend y frontend cambian en PR distintos; datos derivados guardados en vez de calculados.
- **SIGNALS (≥9):** `6a5fe11`, #117, #122, `b5a8333`, #119, `6e82ec2` ("el test pasaba porque llamaba la API directo"), #125, #118 (**sin mergear**), `2424a89`.
- **HOW TO PREVENT EARLIER:** una sola fuente por regla (`pacientes_del_rol`, `SITE_ROUTES`, `normalizar_sede` en el borde); campos derivados calculados; partir `App.jsx` por módulo.
- **AUTOMATION:** test de humo por rol que llame cada endpoint con cada rol (habría cazado el 500); pruebas mínimas de frontend sobre payloads; ESLint en CI.

## 5 · Tablas nuevas fuera del respaldo — DATABASE

- **SYMPTOM:** apps nuevas sin respaldo ("la lista dejó fuera once tablas entre agosto y septiembre").
- **ROOT CAUSE:** `core/respaldo.py` con la lista `APPS` escrita a mano.
- **SIGNALS:** `06f96c4` (Faro), `e6142d0` (Email), `609d953` (Continuidad fase 2) + las once tablas previas.
- **HOW TO PREVENT EARLIER / AUTOMATION:** ya existe `RespaldoTests.test_cubre_todas_las_tablas_del_negocio`, así que hoy se paga barato (un commit por app). Siguiente paso: derivar la lista de `apps.get_models()` con exclusiones explícitas. Mont' Sinai **no tiene respaldo**: es la prueba de que esta pieza debe ser core, no copia.

## 6 · Documentación que queda mintiendo / PR mergeado con versión vieja — DOCUMENTATION / COMMUNICATION

- **SYMPTOM:** el registro decía "ninguna fusión ejecutada" y sí se había hecho; "limpieza pendiente" ya hecha; 6 ítems de `CLAUDE.md` marcados "⏳ SIN desplegar" que están en `main`; commits de #69/#70 que no llegaron a producción porque se mergeó antes de empujar; cambios en datos de producción sin rastro en el repo; un celular personal publicado en la documentación.
- **ROOT CAUSE:** `CLAUDE.md` usado como bitácora (1.198 líneas, 48 ítems) que se edita en cada PR; merge a los ~8 minutos mientras la sesión de Claude sigue produciendo commits.
- **SIGNALS (≥6):** #94, #100, #102 (abierto), #71, #88 (`d3680f0`, `dfa7257`), títulos heredados ("Clínica SaaS").
- **HOW TO PREVENT EARLIER:** separar reglas estables (cortas) de un registro de cambios; cerrar el ítem en el mismo PR que lo ejecuta; no mergear con preguntas abiertas en la sesión.
- **AUTOMATION:** merge solo vía auto-merge tras CI verde; hook que avise si se edita `CLAUDE.md` en ramas `feat/*`; el registro lo genera `git log`, no la IA.

## 7 · "Hoy" con el reloj del cliente — LOGIC

- `0c78801` (fecha congelada), `9fe3ecf` (timer), `d2d571b` (reloj del servidor): tres intentos en cuatro días para el mismo reporte. La causa (reloj del navegador) se identificó al tercero.
- **Prevención:** regla "la fecha de negocio viene del servidor en `America/Lima`" + un helper único. Es core universal para cualquier sistema con agenda.

## 8 · Consultas N+1 y payloads pesados — PERFORMANCE

- `265c798`, `2658e00` (~30 s → segundos), `d827c8d` (N+1 en agenda), `fc2ca0b` + #37 (lista de 2,26 → 1,27 MB), #29 (agenda por tramo). Se resuelven por síntoma, cuando alguien se queja.
- **Prevención:** `assertNumQueries` en tests de los endpoints de listas; serializer "liviano" para listas como convención de template.

## 9 · Fugas de privacidad — PERMISSIONS

- `d839894` (teléfono y documento del tutor visibles al psicólogo; editar borraba el contacto), `bdc6984`/`16a7298`, #63 (Google Calendar con datos clínicos), #48/#72 (datos reales en el repo), #87/#88 (celular personal publicado). La nota de procesos añade: el webhook de Meta guarda PII en el log y `CobroViewSet` no comprueba el rol.
- **Prevención:** tests de serializer por rol ("qué campos ve cada rol"); hook que bloquee escribir `*.xlsx`, `datos_pacientes_reales.json` o exportes fuera de rutas ignoradas; revisión de seguridad por subagente en cada cambio que toque datos personales.

## 10 · UX visible solo al usarlo — UX

- `5360d7d` (toast oculto por overflow), `f8b82f2`, `6830f93`/`817fd59`/`702ff50` (resumen de agenda en tres iteraciones), #50, #109 (faltaba el domingo), `aeea09a` (ajustes tras el QA).
- **Prevención:** checklist de estados (vacío, cargando, error, mucho dato, móvil 390 px) aplicado en el diseño, antes de implementar; QA de navegador como skill reproducible en vez de ad hoc.

## 11 · Datos importados mal marcados — DATABASE / VALIDATION

- `a99cf04` (217 citas de AgendaPro marcadas como web), #96 (bio de Instagram contada como pauta), #28/#46 (reporte de pauta que no cuadraba).
- **Prevención:** todo importador con `--dry-run` obligatorio y reporte de conteos por categoría antes de escribir; aprobación humana del reporte.

---

## Matriz: dónde se detecta hoy y dónde debería detectarse (shift left)

| Problema | Detección actual | Detección ideal | Mecanismo |
|---|---|---|---|
| Identidad / duplicados | Coordinación lo reporta semanas después | Al diseñar el flujo de alta | Pieza core `identidad` + test de contrato |
| Fuente de verdad duplicada (sesión N, riesgo…) | Producción, cifras raras | Al escribir el código | Guard/lint de lectura del campo legado; skill de discovery que liste consumidores |
| Permisos por rol rotos | Un rol entra y ve 500 | En CI | Test de humo endpoint × rol |
| Fuga de PII | Revisión posterior o nunca | Antes de escribir el archivo | Hook PreToolUse de PII + tests de serializer |
| Tabla fuera del respaldo | CI (ya) | Al crear el modelo | Lista derivada de `get_models()` |
| Host / dominio / proveedor | Producción caída | Inmediatamente tras deploy | Smoke post-deploy |
| UX de estados | QA en navegador o usuario | En el diseño | Checklist de estados en la skill de feature |
| Documentación falsa | Semanas después | Nunca existe (generada) | Registro desde git; `CLAUDE.md` sin bitácora |
| Commits que no llegan a `main` | Días después | Al mergear | Auto-merge tras CI y sin commits locales pendientes |
| Migración incompatible | CI (`makemigrations --check`) | Al editar `models.py` | Hook post-edit que corra el check |
