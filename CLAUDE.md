# Ítaca Conversemos — mapa para Claude

Sistema de gestión de **Ítaca Conversemos**, centro de psicología en Perú (sedes **Lima** y **Piura**): agenda, historia clínica, captación, finanzas, mensajería y sitio público en una sola app. **Django 5.2 + DRF** (API bajo `/api/`) + **React/Vite** (`frontend/`), **PostgreSQL en Railway**. **Push a `main` = despliegue a producción.**

> Este archivo es un MAPA, no una historia. La bitácora anterior está archivada en `docs/historial/`. Las reglas de cada dominio viven en `.claude/rules/` y se cargan solo al tocar sus archivos.

## Apps

| App | Para qué |
|---|---|
| `core` | Tenant/middleware, permisos (`permisos.py`), Hoy y Gerencia, Centro de Continuidad, integraciones (Eli y otros), sitio/SEO/dominios, respaldo, WhatsApp Cloud |
| `usuarios` | Usuario con rol, profesionales, equipo |
| `pacientes` | Pacientes, citas, historia clínica (atenciones auditadas), adjuntos, consentimiento, agendamiento público, duplicados/fusión, sugerencias de riesgo |
| `finanzas` | Servicios (catálogo), cobros, paquetes, egresos, caja |
| `leads` | Captación, identidad por teléfono, atribución de origen, embudo web |
| `mensajes` | Bitácora de mensajes, envío Meta → Evolution → wa.me, plantillas, biblioteca de imágenes |
| `espacios` | Alquiler de consultorios a profesionales externos |
| `faro` | Tamizaje escolar (datos de menores, separado a propósito de `pacientes`) |
| `correo` | Email 1.0 (Brevo), consentimiento como historial; banderas apagadas por defecto |

La app `continuidad` (Dirección Clínica fase 2: proceso con eventos, transiciones y motivos) acompaña a `core/continuidad.py`.

## Comandos

- App: `./dev.ps1` (levanta los dos) o `.\.venv\Scripts\python.exe manage.py runserver` + `cd frontend; npm run dev` (Vite en 5174; reenvía `/api` a `127.0.0.1:8001` salvo que definas `VITE_API_TARGET`; ver `frontend/vite.config.js`).
- Verificar: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verificar.ps1 -Modo FAST|STANDARD|FULL`
  - **FAST** en el ciclo de edición (~20–45 s) · **STANDARD** para declarar algo terminado (~2,5 min: suite completa ~1.071 tests en ~100 s, build, ESLint) · **FULL** antes de integrar (desde cero + `check --deploy`).
  - Los tests corren SIEMPRE en SQLite temporal. El hasher barato solo aplica bajo `manage.py test`.
  - **No uses `--parallel` en Windows** (falla con WinError 5 y tapa errores reales).
  - Un hook `Stop` (`.claude/settings.json`) corre STANDARD antes de dejarte terminar.
- ESLint: "ninguna deuda nueva" contra `scripts/eslint-baseline.json` (`scripts/eslint-sin-deuda.mjs`).
- Migraciones: `python manage.py makemigrations <app>` y luego `makemigrations --check` (lo hace verificar.ps1).

## Invariantes (no negociables)

- **Multitenant:** toda tabla con datos de una clínica lleva `clinica_id` y toda consulta se filtra por él. Sin FK que crucen clínicas.
- **Ley 29733 (datos de salud):** no hay URL pública de media (archivos solo por endpoint autenticado y con scope); **nada de PII** (nombres de pacientes, teléfonos, DNI, exportes) en el repo, `docs/`, `.claude/`, commits ni chat.
- **Historia clínica:** no se borra; se corrige y cada cambio queda en `EdicionAtencion`. Adjuntos clínicos con el mismo alcance.
- **IA:** no escribe `Paciente.riesgo` ni decide nada clínico; propone (`SugerenciaRiesgo`) y una persona resuelve.
- **Permisos por rol** en `core/permisos.py`; la matriz `core/tests_matriz_permisos.py` es la política: cambiar una celda requiere aprobación de la dirección.
- **Integraciones** con token por alcance (`ITACA_TOKEN_*`), nunca un token global nuevo.
- **Hosts:** dominio de Railway explícito (`RAILWAY_DOMINIO_SERVICIO`), nunca comodines `*.up.railway.app`.
- **Git:** nunca push a `main`; siempre rama + PR. Toda app nueva entra en `core/respaldo.py` (lo exige un test).
- **No leas `.env`.** Si hace falta un valor, pídele a la persona que lo confirme.

## Roles (`usuarios.Usuario.Rol`)

| Rol | Quién | Puede |
|---|---|---|
| `admin` | Dirección / gerencia | Todo, incluidos egresos, equipo y config |
| `medico` | Psicólogo/a | Sus pacientes; historia clínica; no ve contacto |
| `asistente` | Coordinación / recepción | Agenda, pacientes, cobros, DP, duplicados, mensajes; ve la historia clínica pero no la edita |
| `comercial` | Captación | Leads; nada clínico |
| `analista` | Dirección Clínica | Solo lectura (salvo gestión de continuidad); sin contacto |

## Convenciones

- Español peruano con tuteo (tú/tienes), nunca voseo. Zona `America/Lima`; la fecha "hoy" viene del servidor, no del navegador.
- Commits `tipo(ámbito): frase en español` + línea `Co-Authored-By`.
- Antes de crear modelos o migraciones, muestra el esquema y espera el visto bueno. Una tarea a la vez; no te adelantes al alcance.
- **No escribas bitácora en este archivo.** El registro va en commits y PR; el conocimiento de dominio, en `docs/` o `.claude/rules/`.
- Si un hecho lo puede comprobar un test o generarlo un script, no lo escribas en un archivo de contexto.

## Documentación

- `README.md`, `DEPLOY.md` — arranque y despliegue (parcialmente desactualizados; manda el código).
- `docs/dominios.md` — sitio y sistema en dominios separados (`core/dominios.py`).
- `docs/marca-exportables.md` — identidad visual de Excel/PDF/Word que genera el sistema.
- `docs/auditoria-continuidad.md` — auditoría de "Evaluar continuidad" (set 2026).
- `docs/continuidad.md`, `docs/continuidad-estados.md`, `docs/continuidad-metricas.md`, `docs/direccion-clinica.md` — continuidad y Dirección Clínica (definiciones y cifras).
- `docs/email-1.0.md`, `docs/email-1.0-operacion.md`, `docs/email-1.0-dns.md` — diseño, operación y DNS del correo.
- `docs/SOFTWARE-FACTORY-AUDIT.md` + `docs/software-factory-audit/` (01–18) — auditoría de la fábrica de software.
- `docs/SOFTWARE-FACTORY-PHASE-0.md` — fase 0 de la fábrica (verificación, hooks, rules).
- `docs/historial/` — bitácora archivada (obsoleta en partes; no se carga).
- `.claude/skills/` (feature, qa-browser, pr, security-review) y `.claude/agents/` (domain-explorer, security-data-reviewer, ux-reviewer, regression-reviewer) — método de trabajo; flujo en `docs/factory/` y en el repo de la fábrica.
- `.claude/rules/` — reglas por dominio: historia-clinica, identidad-duplicados, continuidad, mensajeria, sitio-rutas, finanzas, integraciones-seguridad, frontend-ui.
