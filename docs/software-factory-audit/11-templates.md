# 11 · Templates y boilerplates

> Solo se proponen templates de estructuras que **ya** se construyeron varias veces en este repo o en la agencia. Para cada uno: qué contiene, qué varía, cuántas veces aparece y el riesgo de sobre-abstraer.
> Regla de corte: si el template tiene más parámetros que líneas ahorradas, no se hace.

| # | Template | Apariciones reales | Prioridad |
|---|---|---|---|
| T1 | App Django de dominio | Faro, correo, continuidad (+ 6 apps anteriores) | P1 |
| T2 | Endpoint con alcance por rol | ≥5 `get_queryset` con el mismo esqueleto; 57 checks en línea | P0 (va con RBAC) |
| T3 | Factories de test + matriz por rol | 49 archivos de test creando datos a mano | P0 |
| T4 | Máquina de estados auditada | `continuidad` (rama); falta en `Cita`, `Lead`, Faro | P1 |
| T5 | Pantalla de lista | ~12 pantallas | P1 |
| T6 | Ficha con pestañas | 3 (Paciente, Profesional, Lead) | P2 |
| T7 | Modal de formulario | 40 modales | P0 (va con UI base) |
| T8 | Integración externa | Evolution, Meta, Brevo, OpenAI, Calendar, Soto | P2 |
| T9 | Importador con dry-run | 5 importadores | P2 |
| T10 | Repo nuevo (proyecto) | 8 sistemas, cada uno distinto | P1 (es el bootstrap) |
| T11 | Plantilla de PR + brief de feature | 0 hoy; 129 PR sin plantilla | P0 |

---

### T1 · App Django de dominio

- **WHAT IT CONTAINS:** `models.py` con `ModeloTenant`; `services.py` (lógica, transacciones, eventos); `api.py` con `RolPermission` y serializers de **entrada** (`is_valid()`); `urls.py`; `admin.py` mínimo; `factories.py`; `tests/` con aislamiento por tenant, matriz por rol y casos del servicio; `docs/<app>.md` (≤1 página: propósito, entidades, estados, reglas); `.claude/rules/<app>.md` (≤30 líneas con `paths:`).
- **WHAT REMAINS VARIABLE:** entidades, estados, reglas, matriz de permisos.
- **HOW OFTEN:** 9 apps en `main` + `continuidad`. Las tres últimas (Faro, correo, continuidad) siguieron la misma secuencia y las tres olvidaron el respaldo.
- **RISK OF OVER-ABSTRACTION:** bajo, si es solo esqueleto. Alto si intenta generar modelos desde YAML: no hacerlo.

### T2 · Endpoint con alcance por rol

- **CONTAINS:** `get_queryset` = tenant → alcance del rol → filtros de query; `permission_classes = [RolPermission.de(lectura=[...], escritura=[...])]`; serializer de salida por rol (campos sensibles fuera para roles sin contacto).
- **VARIABLE:** roles, campos sensibles, filtros.
- **HOW OFTEN:** ≥5 esqueletos idénticos en `pacientes/api.py` (líneas 222, 445, 869, 1013, 1071); 6 `_es_admin`, 6 `_solo_admin`, 57 checks en línea.
- **RISK:** bajo. Es un mixin, no un framework.

### T3 · Factories de test + matriz por rol

- **CONTAINS:** `factories.py` (clínica, sede, usuario por rol, paciente adulto/menor con tutor, cita en cada estado, lead); helper `como(rol)`; test parametrizado endpoint × rol que compara contra `docs/permisos.md`.
- **VARIABLE:** la matriz esperada.
- **HOW OFTEN:** cada uno de los 49 archivos de test arma sus datos a mano. El 500 de "Hoy" para psicólogos (`6a5fe11`) lo habría cazado la matriz.
- **RISK:** bajo.

### T4 · Máquina de estados auditada

- **CONTAINS:** modelo `Proceso` con `estado`; modelo `Evento` append-only (quién, cuándo, de→a, motivo); `transicionar()` con tabla de transiciones permitidas, `select_for_update` e idempotencia; catálogo de motivos como datos; métricas derivadas de eventos.
- **VARIABLE:** estados, transiciones, motivos.
- **HOW OFTEN:** 1 bien hecha (`continuidad` en la rama). Hace falta en `Cita` (`POST /citas/<id>/estado/` acepta cualquier valor desde cualquier estado, `pacientes/api.py:762-783`), en `Lead` (pasar a GANADO no llena `fecha_cierre`) y en Faro.
- **RISK:** medio. No convertirlo en motor de workflows configurable; basta con una tabla de transiciones en código.

### T5 · Pantalla de lista

- **CONTAINS:** encabezado con acción primaria; `<BarraFiltros>` con filtros en la URL; `<Tabla>` con paginación del servidor, filas operables por teclado; estados vacío/carga/error; exportar.
- **VARIABLE:** columnas, filtros, acciones por fila.
- **HOW OFTEN:** ~12 pantallas (Pacientes, Leads, Continuidad, Profesionales, Finanzas, Espacios, Recursos, Faro…).
- **RISK:** medio. Mantenerlo como composición de componentes, no como "pantalla genérica configurable por JSON".

### T6 · Ficha con pestañas

- **CONTAINS:** cabecera con identidad y acciones; pestañas con URL; secciones visibles por rol.
- **HOW OFTEN:** 3. **RISK:** medio-alto; con 3 apariciones, mejor un patrón documentado que un componente.

### T7 · Modal de formulario

- **CONTAINS:** `<Modal dirty busy>` (Escape, foco, `role="dialog"`, no cierra con clic fuera si hay cambios, no cierra mientras guarda), `<Campo>`, `<BotonGuardar busy>`, error por campo, resumen antes de confirmar en operaciones de dinero.
- **HOW OFTEN:** 40 modales; 35 pierden datos con clic fuera; ~24 sin bloqueo al guardar (riesgo de doble cobro).
- **RISK:** bajo.

### T8 · Integración externa

- **CONTAINS:** cliente con timeout y reintentos; `disponible()` y degradación elegante; estados "aceptado / entregado / fallido" separados; webhook con verificación de firma; nada de PII en logs; fixtures reales del proveedor; smoke manual documentado.
- **HOW OFTEN:** 6 integraciones en Conversemos, ~17 clientes de Evolution en la agencia.
- **RISK:** bajo como checklist + esqueleto; alto si se intenta un "cliente universal de proveedores".

### T9 · Importador con dry-run

- **CONTAINS:** `--dry-run` por defecto; lector xlsx/csv común; reporte de conteos por categoría y muestras anonimizadas; escritura en transacción por lotes; marca de origen en cada fila.
- **HOW OFTEN:** 5 importadores (3 lectores xlsx distintos).
- **RISK:** bajo.

### T10 · Repo nuevo

- **CONTAINS:** esqueleto del stack elegido + dependencia de los paquetes de core; `CLAUDE.md` ≤5 KB con huecos a llenar; `.claude/` mínimo (rules, skills `feature`/`qa-navegador`/`pr`, agentes, hooks); `scripts/` (`dev`, `test`, `verificar`, `qa-entorno`, `mapa`, `smoke`); CI; `.env.example` generado; plantilla de PR; `docs/` con `permisos.md`, `identidad.md`, `glosario.md`.
- **HOW OFTEN:** 8 sistemas arrancados de 8 maneras.
- **RISK:** el template envejece. Usar una herramienta con "update" (p. ej. Copier) para traer mejoras a proyectos ya creados.

### T11 · Plantilla de PR + brief de feature

- **PR:** resumen; Definition of Done marcada; riesgos; migraciones y rollback; cómo probar; capturas de QA.
- **Brief (`docs/features/<slug>.md`):** problema; actor; criterios de aceptación; estados de UI; matriz de rol; datos sensibles; fuera de alcance; decisiones que requieren a Max.
- **HOW OFTEN:** 129 PR sin plantilla; las decisiones y el "done" hoy viven en cuerpos de commit de 27 líneas promedio.
- **RISK:** bajo; si el brief pasa de una página, se recorta.

---

## Qué NO convertir en template

- KPIs y paneles de gerencia: cada negocio mide distinto; se reutiliza la **capa de métricas**, no el panel.
- El sitio público: la estructura (rutas en una fuente, SEO, dominios) sí; el diseño no (lo cubre `criterio-de-diseno`).
- Faro, DP, Dirección Clínica: producto.
