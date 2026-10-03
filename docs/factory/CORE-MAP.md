# CORE-MAP · Qué de Ítaca Conversemos es reutilizable

> Fase 2 de la Software Factory (1 oct 2026). Medido sobre la rama `chore/software-factory-phase-0` (base `origin/main` `9ed776c`).
> **Madurez:**
> - **A**: probada en producción **y** con tests propios.
> - **B**: con tests, poca historia.
> - **C**: funciona, pero acoplada o sin tests.
>
> **Reutilizable:** **SÍ** se extrae al template ahora · **ADAPTAR** el concepto sirve pero hay que generalizarlo · **NO** se queda en Conversemos.
> "Imports de dominio" = imports desde `pacientes`, `leads`, `finanzas`, `faro`, `correo`, `mensajes`, `espacios` o `usuarios` (medido con grep).

## Universal core

| Componente | Archivos | Capa | Madurez | Dependencias | Reutilizable | Acción |
|---|---|---|---|---|---|---|
| Tenant por fila | `core/tenant.py` (21 líneas), `ModeloTenant` + `TenantQuerySet` (`core/models.py`), `TenantActualMiddleware` | Universal | A | 0 de dominio | **SÍ** | Al template tal cual |
| Políticas de autorización por capas | `core/politicas.py` (162) | Universal | B | `core.permisos` (nombres de roles) | **ADAPTAR** | Template: mismas capas con roles configurables (`ROLES` en settings) |
| Listas de roles + clases DRF | `core/permisos.py` (200) | Universal | A | 0 | **ADAPTAR** | El patrón (constante + función + clase + porqué) va al template; los roles concretos no |
| Matriz rol × endpoint | `core/tests_matriz_permisos.py` | Universal | B | Modelos de Conversemos en el setup | **ADAPTAR** | Template: motor de matriz + matriz de ejemplo |
| Visibilidad por campo | `core/tests_campos_por_rol.py` | Universal | B | Ídem | **ADAPTAR** | Ídem |
| Auditoría append-only | `core/auditoria.py` (24) + `RegistroAuditoria` | Universal | B | 0 | **SÍ** | Al template |
| FK acotados al tenant + `validar()` de entrada | `core/serializadores.py` (49) | Universal | B | 0 | **SÍ** | Al template |
| Hasher barato solo en tests + su guardia | `config/settings.py` (bloque `EJECUTANDO_TESTS`), `core/tests_hasher.py` | Universal | B | 0 | **SÍ** | Al template |
| Hosts sin comodín compartido | bloque `RAILWAY_DOMINIO_SERVICIO` de settings + tests | Universal | B | 0 | **SÍ** | Al template (genérico: `DOMINIO_SERVICIO`) |
| Dominios sitio/sistema | `core/dominios.py` (78) | Universal | B | 0 | **ADAPTAR** | Solo si el proyecto tiene sitio público |
| Reloj del servidor / health | `core/reloj.py` (`/api/hora/`) | Universal | A | 0 | **SÍ** | Al template como `/api/salud/` (con versión y chequeo de BD) |
| Respaldo lógico + restaurar | `core/respaldo.py` (54) + comando `restaurar` + `RespaldoCubreTodaAppTests` | Universal | A | Lista `APPS` del proyecto | **ADAPTAR** | Template: `APPS` derivada de las apps propias + exclusión de secretos |
| Tokens de integración por alcance | `TokenIntegracion` y `tokens_validos` en `core/integraciones.py` | Universal | B | El archivo mezcla las vistas de Eli (4 imports de dominio) | **ADAPTAR** | Extraer solo la clase y la función a `core/integraciones_auth.py` del template |
| Fuente única con guardián | `core/tests_fuentes_unicas.py` | Universal | B | Regla concreta | **ADAPTAR** | El patrón "test que prohíbe copiar una regla" va a la skill `feature` |
| Verificación local | `scripts/verificar.ps1` (232), `scripts/eslint-sin-deuda.mjs`, `scripts/eslint-baseline.json` | Universal | B | 0 | **SÍ** | Al template |
| Stop hook | `.claude/settings.json`, `.claude/hooks/stop-verificar.ps1` | Universal | B | `verificar.ps1` | **SÍ** | Al template |
| CI 4 jobs | `.github/workflows/tests.yml` | Universal | B (sin corrida real aún) | 0 | **SÍ** | Al template |
| UI base | `frontend/src/ui/Modal.jsx` (72), `confirmar.js` (23), `DialogoConfirmar.jsx`, `aviso.js` (27) + `aviso.test.js` | Universal | B | Clases CSS `ca-*` | **SÍ** | Al template con su CSS mínimo |
| Ojito de contraseña | `frontend/src/InputClave.jsx` (41) | Universal | A | 0 | **SÍ** | Al template |
| Login por email + throttle IP/cuenta | `usuarios/api.py` (`LoginView`), throttles `login_ip`/`login_cuenta` | Universal | A | Modelo `Usuario` del proyecto | **ADAPTAR** | Template: `Usuario` mínimo (email, rol, clínica) + login + throttle |
| `CLAUDE.md` como mapa + rules por ruta | `CLAUDE.md`, `.claude/rules/` | Universal | B | Contenido de Conversemos | **ADAPTAR** | Template con secciones vacías + 2 rules genéricas |

## Business ops core

| Componente | Archivos | Capa | Madurez | Dependencias | Reutilizable | Acción |
|---|---|---|---|---|---|---|
| Agenda (cita, slots, bloqueos, reserva pública) | `pacientes/models.py` (`Cita`, `BloqueoAgenda`), `pacientes/agendamiento.py` | Business ops | A | Paciente, Profesional, sede, psicología | **ADAPTAR** (fase futura) | Spec + tests de contrato antes que código |
| Estados de cita como fuente única | `ESTADOS_REALIZADA`, `ESTADOS_CERRADA` | Business ops | B | `Cita.Estado` | **SÍ (concepto)** | Template: módulo de estados con guardián |
| Cobros / paquetes / caja | `finanzas/` | Business ops | A (endurecido en Fase 1) | Paciente, Cita, Servicio | **ADAPTAR** | Patrones: un cobro vigente por cita, `marcar_pagado` 409, auditoría, serializer de entrada |
| Leads + identidad + duplicados + fusión | `leads/identidad.py`, `pacientes/duplicados.py`, `pacientes/fusion.py` | Business ops | A | Muy acoplado (fusion: 700 líneas) | **NO por ahora** | Primero una spec de identidad (persona / contacto / tutor) |
| WhatsApp (Evolution + Meta) | `mensajes/` | Business ops | A | Paciente, Cita, sede | **ADAPTAR** | El cliente más maduro de los ~17 de la agencia: extraer el adaptador con el contrato "aceptado ≠ entregado" |
| Correo con consentimiento (Brevo) | `correo/` | Business ops | A (cerrado en #141) | `ConIdentidad` → Paciente/Lead/Faro | **ADAPTAR** | Hacer `ConIdentidad` genérico |
| Recordatorios | `pacientes/recordatorios.py` + cron externo | Business ops | A | Cita | **NO** | Sin scheduler propio todavía |
| Exportes | `frontend/src/exportGerencia.js` (901) | Business ops | A | KPIs de Ítaca | **NO** | Solo como ejemplo |

## Clinical core

| Componente | Archivos | Capa | Madurez | Dependencias | Reutilizable | Acción |
|---|---|---|---|---|---|---|
| Alcance clínico por profesional | `acotar_clinico` (`core/politicas.py`) | Clínico | B | `Paciente.profesional` | **SÍ (concepto)** | Template clínico: `campo` configurable |
| Historia clínica auditada | `Atencion` + `EdicionAtencion`, `AtencionViewSet` | Clínico | A | Paciente | **ADAPTAR** | Patrón "no se borra, se corrige con bitácora" |
| Adjuntos privados | `Adjunto`, `AdjuntoViewSet.descargar` | Clínico | A (endurecido en Fase 0) | Paciente | **ADAPTAR** | Patrón "sin URL pública + alcance por rol" |
| Consentimiento por token | `pacientes/consentimiento.py` | Clínico | A | Paciente, textos legales | **ADAPTAR** | Inmutable una vez firmado; token solo a quien envía |
| Revisión humana de sugerencias de IA | `SugerenciaRiesgo` + `pacientes/riesgo.py` + `SugerenciaRiesgo.jsx` | Clínico | B | Paciente.riesgo | **ADAPTAR** | Generalizar a `SugerenciaIA(campo, valor)` cuando haya un segundo caso (ya hay candidato: resumen clínico) |
| Proceso con eventos (continuidad) | rama `feat/direccion-clinica` | Clínico | B | DP-xx | **ADAPTAR** (cuando llegue a `main`) | — |

## Project specific (se queda en Conversemos)

Faro (tamizaje escolar), códigos DP-01…16, bloque de 6 sesiones y S3, Dirección Clínica y KPIs de gerencia, Brújula, Mentalidad Ítaca y gamificación, `espacios` (alquiler de consultorios), sitio público y textos, integración Soto, roles concretos (`medico` = psicólogo, etc.), importadores de AgendaPro.

## Duplicación entre repositorios (de la auditoría, sin cambios en esta fase)

| Pieza | Veces en la agencia | Fuente candidata |
|---|---|---|
| Cliente de Evolution API | ~17 (3 Python, 14 JS) | `mensajes/evolution.py` de Conversemos |
| Límite de intentos de login | 2 implementaciones distintas (Conversemos, Mont' Sinai) | `LoginPorIP` + `LoginPorCuenta` de Conversemos |
| Ojito de contraseña | 8 repos + Apps Script | `InputClave.jsx` |
| Respaldo | 5 distintos; Mont' Sinai sin respaldo | `core/respaldo.py` + test de cobertura |
| Auth y roles | 8 de 8 sistemas | Template de la Fase 3 |
| Auditoría | 4 variantes | `core/auditoria.py` |

## Gate de la Fase 2

**Criterio:** el core no debe depender de detalles exclusivos de Conversemos.

| Pieza que va al template | ¿Depende de Conversemos? |
|---|---|
| tenant, auditoria, serializadores, hasher, hosts, health, verificar, eslint, Stop hook, CI, UI base, InputClave | **No** (0 imports de dominio) |
| politicas, permisos, matriz, campos por rol, respaldo, login | Por nombres de roles, modelos o lista de apps → **se reescriben genéricas en el template**, no se copian |

**Resultado: VERDE para un template mínimo.** Agenda, finanzas, mensajería, correo e identidad **no** entran al template todavía (madurez A, pero acoplados). Su ruta es spec + tests de contrato (ver [EXTRACTION-PLAN.md](EXTRACTION-PLAN.md)).
