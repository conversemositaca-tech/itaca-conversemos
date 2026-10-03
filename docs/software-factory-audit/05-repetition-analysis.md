# 05 · Qué estamos repitiendo

> Fuentes: conteos con `grep` sobre el snapshot de `origin/main` (1 oct 2026), historia git, comparación con los repos hermanos (`clinica-saas`, `mont-sinai-conversemos`, `beauty-spa-saas`, `life-wellness`, `bonos-descuentos`, `mirai-saas`, bots). Todas las cifras son conteos reales; donde se estima, se dice.

La repetición aparece en tres escalas:

1. **Dentro de un archivo o una app**: el mismo helper copiado.
2. **Entre apps de Conversemos**: la misma regla en 5 a 11 lugares.
3. **Entre proyectos de la agencia**: la misma pieza (auth, agenda, caja, cliente de WhatsApp) reconstruida 5 a 17 veces en 3 stacks.

La tercera es la más cara y la que motiva la fábrica.

---

## A. Código

### A.1 Backend

| Patrón | Ocurrencias | Evidencia | Mecanismo propuesto |
|---|---|---|---|
| `_es_admin(user)` con cuerpo idéntico | 6 | `core/buzon.py:42`, `core/recursos.py:29`, `core/whatsapp_cloud.py:25`, `espacios/api.py:32`, `finanzas/api.py:33`, `mensajes/monitor_evolution.py:32` | Una `RolPermission(roles=…)` declarativa |
| `_solo_admin()` | 6 (el de `mensajes/api.py:51` deja pasar también a asistente) | `core/metricas.py:46`, `core/reportes.py:209`, `finanzas/api.py:98`, `usuarios/api.py:264,354` | Ídem |
| Comparación de rol escrita en línea | **57** | `pacientes/api.py` 17, `core/gerencia.py` 10 | Ídem + test de matriz endpoint × rol |
| `solo_digitos` redefinido | 7 + 24 `"".join(c for c in x if c.isdigit())` en 17 archivos | `core/integraciones.py:32`, `leads/captacion.py:30`, `pacientes/agendamiento.py:40` | Un módulo `identidad` (core) |
| Sufijo de 9 dígitos `[-9:]` como identidad | 14 en 9 archivos | `leads/identidad.py:29`, `mensajes/webhook_evolution.py:114`, … | Ídem |
| Normalizadores "oficiales" de teléfono que no coinciden | 2 | `leads.identidad.norm_tel` (últimos 9) vs `mensajes.evolution.normalizar_numero` (E.164) | Ídem |
| `_parse_fecha` | 6 | `espacios/api.py:37`, `finanzas/api.py:57`, `leads/api.py:29`, … | Serializers de entrada |
| `_rango(periodo)` | 2 copias que **divergen** (por defecto "hoy" vs "mes") | `core/gerencia.py:33` vs `finanzas/api.py:38` | Capa común de métricas |
| Conjunto "cita realizada" | **3 constantes + 8 listas en línea** (11 lugares) | `core/continuidad.py:17`, `pacientes/api.py:74`, `finanzas/liquidacion.py:60`, `core/gerencia.py:222`, `core/mi_panel.py:64` | Una constante de dominio + guard |
| Enum `Sede` | **9** | — | Modelo `Sede` como dato, no enum |
| Enum `Frecuencia` | 3 incompatibles | `Paciente`, `Lead`, `continuidad` | Máquina de estados única |
| Validación a mano de `request.data` | 282 lecturas; **0 `is_valid()`**; 18 `isinstance(request.data, dict)`; 61 `.strip()[:N]` | todo el backend | Serializers de entrada como convención del template |
| Esqueleto de `get_queryset` (tenant → rol → paciente) | ≥5 | `pacientes/api.py:222, 445, 869, 1013, 1071` | Mixin `AlcancePorRol` |
| Lectores de xlsx propios | 3 | importadores de AgendaPro y Lima | Utilidad `importar_xlsx` con dry-run |
| Envío de email | 2 caminos (Brevo y SMTP en `faro/informes.py`) | — | Una sola puerta (`correo.services`) |
| Envío de WhatsApp | 1 puerta + 1 desvío (`faro/registro.py:52` llama a Evolution directo) | — | Una sola puerta (`mensajes.services`) |
| Paginación | **0** en DRF; truncados a mano `[:300]`, `[:200]` | `faro/api.py:344, 481` | Paginación por defecto en el template |

### A.2 Frontend

| Patrón | Ocurrencias | Mecanismo propuesto |
|---|---|---|
| Modales a mano (`ca-modal-bg`) | **40** (22 cabeceras copiadas, 34 X sin `aria-label`, 35 se cierran con clic fuera) | `<Modal dirty busy>` |
| Falsas etiquetas `<div className="ca-label">` | **286** (0 `htmlFor`) | `<Campo>` |
| Ciclo de carga copiado (`useState(cargando)` → `useEffect(api…)` → `.catch(()=>{})`) | **34** pantallas; 45 errores tragados | `useRecurso()` + `<Estado>` |
| `showToast(...)` | 278 (128 con "Error:" como prefijo para decidir el tipo) | `toast.ok / toast.error` |
| `window.confirm` / `prompt` | 24 + 2, y ≥8 acciones destructivas **sin** confirmación | `useConfirm()` |
| Estilos inline | **1.927** `style={{`; 851 colores hex; 4 juegos de tokens paralelos | `tokens.css` |
| Buscador de paciente | 5 copias de la misma lógica `matches` | `<SelectorPaciente>` |
| Barras de filtros | ~25 (30 `ca-fchip`, 10 listas literales lima/piura) | `<BarraFiltros>` |
| Tablas / listas | ~23 tablas, 2 clases CSS distintas (`ca-table`, `ca-tbl`) | `<Tabla>` |
| Formularios de dinero | 5 (`CobroModal`, `PagarModal`, `VenderPaqueteModal`, `EspPagoModal`, `EgresoModal`) | `<FormularioCobro>` |
| Tarjetas KPI | 5 variantes (`StatCard`, `RepCard`, `NumeroConEtiqueta`, `RecordCard`, `Stat`) | `<KPI>` |
| Caminos para mandar WhatsApp | **5** (uno es código muerto) | `<ComposerWhatsApp>` |

### A.3 Entre proyectos (lo más caro)

| Pieza | Veces construida | Stacks |
|---|---|---|
| Cliente de Evolution API | **~17** (3 en Python, 14 `evolution.js` distintos; solo dos bots comparten uno idéntico) | Django, Node |
| Auth + roles | 8 de 8 sistemas | Django, Next+Prisma, Next+Supabase |
| Agenda / citas | ≥7 | 3 stacks + bots que agendan por chat |
| Caja / cobros | ≥7 | 3 stacks |
| Recordatorios | ≥8 | sistemas + bots |
| Respaldo | 5 implementaciones distintas; **Mont' Sinai no tiene** | — |
| Límite de intentos de login | 2 implementaciones distintas en 11 días (Mont' Sinai 29 ago, Conversemos 9 set) | Django ×2 |
| "Ojito" de contraseña | 8 commits y 8 PR en 3 minutos + Apps Script a mano | todos |
| `App.jsx` monolítico | Conversemos 16.075, Mont' Sinai 11.611 (comparten ~9.360) | React |

---

## B. Arquitectura

| Repetición | Evidencia | Consecuencia |
|---|---|---|
| Cada KPI recalcula por su cuenta "realizadas", rango y sede | `core/gerencia.py`, `mi_panel.py`, `ocupacion.py`, `finanzas/liquidacion.py`, y en la rama `continuidad/metricas.py` | Cifras distintas para la misma pregunta; el patrón 2 de errores |
| El estado de continuidad se representa de **4 formas** | `Paciente.frecuencia`, cola calculada en `core/continuidad.py`, `GestionContinuidad`, `ProcesoContinuidad` (rama) | "Pausa" tiene tres representaciones |
| Permisos por **3 mecanismos** mezclados | `core/permisos.py` + helpers copiados + 57 comparaciones en línea | Fugas confirmadas (adjuntos, cobros, contacto) |
| `core/` como cajón | 22 módulos que dependen de todas las apps, y todas dependen de `core.models`; imports dentro de funciones para evitar ciclos | No se puede extraer core sin limpiarlo |
| Señales sobre `Cita.post_save` | 3 receptores (4 con la rama), estilos de error opuestos | Cada guardado de cita es más caro y frágil |
| Integraciones con "degradación elegante" | 4 (`estructurar_nota`, `gcalendar`, `soto`, `transcripcion`), cada una a su manera | Buen patrón sin contrato común |
| Estructura de una app nueva | Faro, correo y continuidad repiten: modelos → services → api → urls → tests → **respaldo** → docs | Es un template implícito (ver [11-templates.md](11-templates.md)) |

---

## C. UX

| Patrón repetido | Dónde | Problema |
|---|---|---|
| "Pantalla de lista" (encabezado + acciones + filtros + tabla + vacío + exportar) | ~12 pantallas: Pacientes, Leads, Continuidad, Profesionales, Finanzas, Espacios, Recursos, Faro… | Cada una con jerarquía y filtros propios |
| "Ficha con pestañas" | Paciente (~18 secciones), Profesional, Lead | Navegación distinta en cada una |
| Selector de estado que persiste al cambiar | `CitaRow` (`App.jsx:7647`), `CitaDetalle` (`8119`), lead (`9337`) | Cancelar sin confirmación |
| Modal de alta con buscador | Agendar, Cobro, Vender paquete | El de Agendar se salta el aviso de duplicado (`App.jsx:1005`) |
| Confirmación nativa del navegador | 24 lugares | Sin contexto de la consecuencia |

---

## D. QA

| Repetición | Evidencia | Mecanismo |
|---|---|---|
| Cada archivo de test crea a mano clínica, usuario por rol, sede, paciente y cita | 49 archivos de test; 1.043 tests | `factories.py` compartido (template de test) |
| Tests de permisos ad hoc, uno por bug | `fix(roles)…`, `fix(hoy)…` cada uno con su test | Test de matriz endpoint × rol generado |
| QA en navegador con Playwright contra una base demo aislada en el scratchpad | `CLAUDE.md` ítems 30, 31, 41, 43, 46–48; el script de auditoría de navegación vive **fuera del repo** | Skill `qa-navegador` + script versionado |
| "Verificado: check, makemigrations --check, tests, build, ESLint igual a main (106 avisos)" | ~16 ítems de `CLAUDE.md` | `scripts/verificar.ps1` + job de ESLint |
| Arreglar el test de respaldo cada vez que nace una app | `06f96c4`, `e6142d0`, `609d953` | Lista derivada de los modelos |

---

## E. Producto

| Repetición | Evidencia | Mecanismo |
|---|---|---|
| Reglas de identidad decididas de nuevo en cada flujo | 5 criterios de deduplicación; ≥10 PR (ver [13-recurrent-errors.md](13-recurrent-errors.md)) | Especificación de identidad como pieza de core |
| "¿Qué cuenta como sesión / asistencia / activo / retención?" | 2 a 5 implementaciones por noción | Glosario de dominio ejecutable (funciones + tests) |
| Criterios de aceptación implícitos | Ningún PR tiene checklist; el "done" se declara en el cuerpo del commit | Definition of Done ([14-future-workflow.md](14-future-workflow.md)) |
| Estados sin máquina | `Cita` acepta cualquier transición (`pacientes/api.py:762-783`); la Fase 2 sí tiene transiciones validadas | Template "máquina de estados auditada" (el de `continuidad`) |
| Consentimiento y canal por persona | Consentimiento clínico, de correo (correo 1.0) y autorización de Faro: 3 modelos parecidos | Pieza de core "consentimiento" |

---

## F. Documentación

| Repetición | Evidencia |
|---|---|
| El mismo hecho en `CLAUDE.md`, `docs/`, memoria y cuerpo de commit | Email 1.0 está en 4 lugares; embudo y atribución, casi literal en `CLAUDE.md` y en commits |
| Manual de recepción | Hecho a mano 2 veces el mismo día en proyectos distintos (Mont' Sinai 17 láminas, Aldanna 29 páginas, 1 oct) |
| Reglas de la casa (Ley 29733, append-only, tenant) | Repartidas en 3 `CLAUDE.md` Django y 4 `.coderabbit.yaml` distintos |
| `CLAUDE.md` heredado por copia | 325 líneas largas repetidas entre `CLAUDE.md` de la familia Django; Conversemos todavía habla de Mont' Sinai y Medlink |
| "Cómo correr la suite" | `CLAUDE.md` ítem 42 + memoria; no está en README |

---

## G. Proceso con Claude (lo que Claude vuelve a hacer en cada feature)

| Claude vuelve a… | Evidencia | Costo | Qué lo elimina |
|---|---|---|---|
| **Investigar** dónde está cada cosa en un `App.jsx` de 16.075 líneas | Tocado en 255 commits; 134 componentes en un archivo | Muy alto: cada feature de UI empieza con exploración | Partir `App.jsx` por módulo + mapa generado |
| **Leer** 21 K tokens de `CLAUDE.md`, de los que sirve el 5–7 % | [06-context-audit.md](06-context-audit.md) | Alto, en cada sesión y tras cada compactación | `CLAUDE.md` corto + rules por ruta |
| **Interpretar** contradicciones (8000 vs 8001, append-only vs editable, quién consolida) | Ídem | Medio, y con riesgo de error | Eliminar lo obsoleto; generar lo generable |
| **Decidir** de nuevo convenciones: nombre de rama, formato de commit, si apilar PR, dónde documentar | 87 de 339 commits usan `feat(`/`fix(`; el resto, frases libres | Medio | Skill `pr` + hook |
| **Recordar** que la app nueva va al respaldo, que el build va antes de la suite, que no se toca `main` | 3 olvidos del respaldo; aviso de entorno en el ítem 42 | Medio | Test derivado, script, hook |
| **Comprobar** a mano: check, migraciones, tests, build, ESLint contra `main` | ~16 ítems repiten el ritual | Medio, y tarda (~22 min la suite) | `scripts/verificar.ps1` + CI |
| **Montar** el QA en navegador desde cero (base demo, seeds, puertos, Playwright) | Ítems 30, 31, 41, 43, 46–48 | Alto | Skill `qa-navegador` |
| **Corregir** después del QA o del uso real | "Ajustes tras el QA en navegador" (`aeea09a`); ~31 % de PR son arreglos | Muy alto | Shift-left: checklist de estados, test por rol, smoke post-deploy |
| **Documentar** escribiendo un ítem nuevo en `CLAUDE.md` | 40 commits | Medio, y genera conflictos | Registro generado desde git |
| **Preguntar** a Max cosas que están en la memoria del repo, que ya no se carga | Sesiones lanzadas desde `C:\Users\mirai` | Ping-pong evitable | Lanzar desde el repo o pasar la memoria a rules |
| **Propagar** a mano un arreglo universal a N repos | Ojito: 8 PR; límite de login resuelto dos veces | Alto, y crece con cada cliente | Core compartido versionado |

---

## Conclusión

| Escala | Qué se repite | Mecanismo de mayor palanca |
|---|---|---|
| Dentro de Conversemos (backend) | Permisos, identidad, "realizada", rangos, validación | Tres módulos de dominio (`permisos`, `identidad`, `metricas`) + serializers de entrada |
| Dentro de Conversemos (frontend) | Modal, campo, carga, toast, confirmación, filtros, tabla | 8 componentes base (los primeros 8 de la tabla A.2) |
| En el proceso con Claude | Discovery, contexto, ritual de verificación, QA | `CLAUDE.md` corto, scripts, 3 skills, hooks |
| Entre proyectos | Auth, agenda, caja, WhatsApp, respaldo, recordatorios, manual | Core versionado por capas (ver [07-reusable-core.md](07-reusable-core.md)) |

No todo lo repetido merece abstracción. Los criterios de qué extraer y qué no están en [11-templates.md](11-templates.md) y en el principio anti-sobreingeniería de [18-roadmap.md](18-roadmap.md).
