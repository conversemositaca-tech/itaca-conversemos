# 06 · Contexto: `CLAUDE.md = MAPA, NO HISTORIA`

## Medición

| | Antes | Después |
|---|---|---|
| `CLAUDE.md` (en disco) | **85.671 bytes**, 1.089 líneas | **6.023 bytes**, 74 líneas |
| Tokens aproximados (bytes / 4) | **~21.400** | **~1.500** |
| Reducción | — | **−93 %** (≈ −19.900 tokens fijos por sesión y en cada ejecución del Action `claude.yml`) |
| Reglas por dominio | 0 | 8 archivos en `.claude/rules/` (18,9 KB en total; solo se carga la que corresponde a los archivos que se tocan, 1,8–2,9 KB cada una) |
| Bitácora | Dentro de `CLAUDE.md` | `docs/historial/CLAUDE-bitacora-hasta-2026-10-01.md`, copia íntegra (verificada línea a línea) con un encabezado de advertencia; no se carga |

## Qué quedó en `CLAUDE.md`

- Qué es el sistema y que **push a `main` = producción**.
- Las 9 apps y para qué sirve cada una (`continuidad` vive en otra rama).
- Comandos: levantar la app (con los puertos reales de `vite.config.js`) y `verificar.ps1` FAST/STANDARD/FULL; no usar `--parallel` en Windows.
- Invariantes: multitenant, Ley 29733, historia clínica auditada, la IA no escribe el riesgo, la matriz de permisos es la política, tokens por alcance, hosts explícitos, nunca push a `main`, respaldo cubierto por test, no leer `.env`.
- Roles reales, con lo que puede cada uno.
- Convenciones, incluida "no escribir bitácora aquí".
- Mapa de la documentación.

## Reglas por dominio (`.claude/rules/`, frontmatter `paths:`)

| Regla | Se carga al tocar | Ejemplos de invariantes recuperados de la bitácora |
|---|---|---|
| `historia-clinica.md` | `pacientes/**` | La historia no se borra; ediciones auditadas; alcance clínico por rol |
| `identidad-duplicados.md` | identidad, duplicados, fusión | Orden obligatorio de la fusión; el teléfono del tutor no identifica; mínimo de 9 dígitos con una sola constante |
| `continuidad.md` | `core/continuidad*`, etc. | La decisión del cierre se evalúa contra la cita de ese bloque; el psicólogo no gestiona |
| `mensajeria.md` | `mensajes/**` | Un mensaje con `external_message_id` nunca se reenvía; aceptado ≠ entregado; el enlace de firma se oculta |
| `sitio-rutas.md` | `main.jsx`, `rutas.js`, `Sitio.jsx`, `seo.py`, `dominios.py` | `SITE_ROUTES` es la única fuente; no tapar `/gestion`; robots y sitemap antes del comodín |
| `finanzas.md` | `finanzas/**` | Egresos solo admin; `marcar_pagado` mueve la fecha al pago real |
| `integraciones-seguridad.md` | `api.py`, `serializers.py`, `permisos.py`, `integraciones.py`, `settings.py` | Tokens por alcance; la matriz es la política; nunca comodines de hosts |
| `frontend-ui.md` | `frontend/src/**` | Checklist de factores humanos de la auditoría |

Formato confirmado con la documentación oficial de Claude Code (memory, "path-scoped rules"): frontmatter YAML con `paths:` y una lista de globs.

## Correcciones de contenido

La versión anterior contenía datos que un agente podía obedecer y que eran falsos:

- ruta `clinica-saas` y "estado: arranque";
- deploy "a definir";
- prototipo inexistente y paleta equivocada;
- "sin tests";
- "Finanzas, Marketing e IA fuera de alcance";
- identidad de otro cliente;
- puertos contradictorios.

El mapa nuevo no los arrastra. Al revisarlo se corrigieron además dos errores del primer borrador: los puertos reales de Vite y que coordinación **ve** la historia clínica (no la edita).

## Advertencias

- El archivo histórico conserva nombres, teléfonos y rutas de backups que ya estaban en el repo (hallazgo F4 de la auditoría). El encabezado lo advierte. Limpiarlos o no es **decisión de Max**: borrarlos del archivo no los quita del historial de git.
- Las reglas y el Stop hook solo se cargan si Claude Code se lanza **desde la carpeta del repo**. Desde `C:\Users\mirai`, la ganancia de contexto existe igual (porque `CLAUDE.md` es más chico), pero las reglas no se activan.
- Conflicto seguro al integrar `feat/direccion-clinica`, que agrega los ítems 46–48 al `CLAUDE.md` viejo. Ver [08-bloqueos-y-siguiente-fase.md](08-bloqueos-y-siguiente-fase.md).
