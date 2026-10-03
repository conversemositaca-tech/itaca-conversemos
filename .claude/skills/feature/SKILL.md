---
name: feature
description: Proceso estándar para construir una feature en un proyecto de la Ítaca Software Factory (Conversemos o generado por el template). Úsala cuando la tarea toque modelo/API y pantalla, o cuando te pidan "una feature", "un módulo", "una pantalla nueva". Junta las decisiones humanas en una sola tanda, implementa con tests desde el inicio y no declara terminado sin STANDARD verde.
---

# Feature

Objetivo: la feature sale bien la primera vez. En Conversemos ~31 % de los PR eran correcciones de algo recién mergeado; esta skill existe para que eso no se repita.

## 1. Entender el dominio (antes de escribir nada)
- Lee `CLAUDE.md` (mapa) y las `.claude/rules/` de los archivos que vas a tocar.
- Si el área es grande o no la conoces, delega en el subagente `domain-explorer` con la pregunta concreta ("qué toca la noción X"). Pide un mapa de ≤40 líneas, no lecturas completas.
- **Busca reglas existentes antes de crear una nueva**: ¿ya hay una constante, política o función para esto? (estados, permisos, montos, fechas). Si existe, úsala; si está copiada en varios lugares, unifícala primero (patrón fuente única + test guardián).

## 2. Plan mínimo (una pantalla de texto, en la respuesta o en `docs/features/<slug>.md` si es grande)
- Problema y actor. Criterios de aceptación verificables.
- **Matriz de rol**: quién ve, quién crea, quién edita, quién borra. Campos sensibles y quién los ve.
- Estados de UI: vacío, cargando, error, mucho dato, móvil. Acciones destructivas → `confirmar()`.
- Datos: modelos/migraciones (muestra el esquema), auditoría necesaria, respaldo.
- **Decisiones que no son tuyas** (nivel 3–4 de autonomía, ver `docs/AUTONOMIA.md`): júntalas todas y pregunta UNA vez. No preguntes lo que puedes descubrir en el repo.

## 3. Implementar
- Backend: alcance con `core/politicas.py` (nunca `rol == "..."` suelto); entrada con serializer + `validar()`; FK con `RelacionesDelTenant`; acciones sensibles con `auditar()`.
- Frontend: `ui/Modal` (tipo correcto), `BotonGuardar`, `confirmar()`, `showToast(texto, tipo)`. Nada de `window.confirm`, `.catch(() => {})` ni estilos de error inferidos.
- Integraciones externas: adapter + config + test con respuesta real grabada + contrato documentado (ver `docs/SUPUESTOS-EXTERNOS.md`).

## 4. Tests (en el mismo cambio, no después)
- Unitarios del servicio/regla.
- Una fila nueva en la **matriz rol × endpoint** por endpoint nuevo.
- Una fila en **campos por rol** por campo sensible nuevo.
- Si hay estados/transiciones: tests de transición.
- Si hay dinero o contadores: test de doble envío (y de concurrencia en Postgres si hay carrera posible).

## 5. Seguridad y QA
- Toca permisos, datos personales, dinero o integraciones → subagente `security-data-reviewer` sobre el diff.
- Toca pantallas → skill `qa-browser` (o subagente `ux-reviewer` si no hay navegador disponible).
- Ambos pueden correr en paralelo.

## 6. Verificar y cerrar
- `scripts/verificar.ps1 -Modo FAST` mientras editas; `-Modo STANDARD` antes de declarar terminado (el Stop hook lo exige).
- Skill `pr` para preparar el PR. No hagas push ni merge sin autorización.
- Si al terminar encontraste un patrón que se repite (una regla copiada, un error que ya pasó), anótalo en el PR como candidato a core.

## Salida
Resumen de 10 líneas: qué cambió, qué tests se agregaron (con conteo), resultado de STANDARD con tiempo, decisiones tomadas por ti (nivel 2) y lo que queda para la persona.
