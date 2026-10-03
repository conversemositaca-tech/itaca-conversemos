# 02 · Datos: fuentes de verdad, validación de entrada, doble cobro y PostgreSQL

## Fuente única: "la sesión ocurrió"

**Mapa encontrado.** Los estados de cita son: agendada, confirmada, en_espera, pendiente, asistio, no_asistio, atendida, reprogramada, cancelada y por_confirmar (este último es legado).

| Concepto | Conjunto | Dónde estaba | Ahora |
|---|---|---|---|
| A. La sesión ocurrió | {atendida, asistio} | 8 copias: `core/continuidad.py`, `pacientes/api.py`, `finanzas/liquidacion.py`, `core/ocupacion.py`, `core/mi_panel.py` (×2), `core/gerencia.py`, `pacientes/serializers.py` | `pacientes.models.ESTADOS_REALIZADA` y `cita_realizada()` |
| C. Cita con desenlace | A + {no_asistio, cancelada} | `TERMINALES` en `core/gerencia.py` | `ESTADOS_CERRADA` |
| B. KPI asistencia % | solo atendida / (atendida + cancelada) | `core/gerencia.py` | **Sin cambio**: decisión D2 |
| D. Cita vigente | "todo menos cancelada" en 13 lugares | varios | Sin cambio en esta fase (cambiaría cifras) |
| E. Pendiente de recordatorio | excluye {atendida, cancelada} | `recordatorios.py`, `gerencia.py` | **Sin cambio**: decisión D3 |
| F. Reserva confirmable | {agendada, confirmada} | `correo/flujos/reserva.py` | Específico del correo; se queda allí |

**`asistio` vs `atendida`:** la diferencia es solo el camino. `atendida` sale de "Atender" (crea una `Atencion`); `asistio` sale del selector y de los importadores (~7.500 citas históricas). Para los cálculos son lo mismo.

**Guardián:** `core/tests_fuentes_unicas.py` falla si alguien vuelve a escribir el par a mano fuera de `pacientes/models.py`. Contra `ae759b8` detecta las 8 copias.

## Validación de entrada

### Inventario (endpoints que escriben)

| Prioridad | Endpoint | Hoy | Fase 1 |
|---|---|---|---|
| **P0 dinero** | `POST /api/cobros/` | Lectura a mano; estado inválido caía en silencio a "pendiente"; FK sin tenant | **Serializer** `CobroEntradaSerializer` con `validar()` |
| P0 dinero | `PATCH /api/cobros/<id>/` | Reasignaba paciente/cita; cambiaba el monto cualquiera | Alcance, rol, campos por rol, auditoría |
| P0 dinero | `POST /api/cobros/<id>/marcar_pagado/` | Pagaba anulados; movía la fecha con un segundo clic | 409 si no está pendiente; bloqueo de fila |
| P0 dinero | `POST /api/paquetes/`, `…/anular/` | Cualquier rol | Solo caja; anulación auditada |
| **P0 citas** | `POST /api/citas/<id>/estado/` | Valida contra opciones; acepta cualquier transición | Auditado + confirmación en UI; transiciones = D5 |
| P0 citas | `PATCH /api/citas/<id>/` | `pacienteId`/`medicoId` sin tenant | Tenant (`RelacionesDelTenant`) |
| P0 citas | `cancelar`, `atender`, `confirmar`, `mover` | No comprueban el estado previo | Cancelar auditado; resto: fase 2 |
| **P0 consentimiento** | `PUT/PATCH/DELETE /api/consentimientos/<id>/` | Texto firmado alterable; borrable | **Eliminados** (405) |
| P0 consentimiento | `marcar-aceptado` | Sin auditoría | Auditado |
| **P0 identidad** | `PATCH /api/leads/<id>/` (`medico`) | Sin tenant | Tenant |
| **P0 integraciones** | `/api/integraciones/nota-voz/` | `campos` libre; identidad por teléfono | IA sin pisar texto humano; riesgo como sugerencia (Fase 0); identidad: fase 2 |
| P0 comunicaciones | `POST /api/pacientes/<id>/mensaje/` | `tipo` no validado; sin rol | Fase 2 |
| P1 | hijos clínicos (objetivos, tareas, escalas, NPS, red) | Enums a mano | Fase 2 |
| P1 | `BloqueoAgenda.create`, `Cita.create` | Si el psicólogo es inválido, se usa en silencio el primero | Fase 2 |
| P2 | lecturas y filtros | — | — |

### Patrón

`core.serializadores.validar(SerializerDeEntrada, request.data)` devuelve los datos limpios o responde 400 con `{"detail": "campo: mensaje", "campos": {...}}`. El frontend ya muestra `detail`.

## Doble cobro

| Vector | Antes | Ahora | Prueba |
|---|---|---|---|
| Doble clic en "Guardar cobro" | 2 cobros | Botón deshabilitado mientras envía (`BotonGuardar`) **y** 409 en el servidor | `DobleCobroTests` |
| Dos pestañas o un reintento de red | 2 cobros | Transacción + `select_for_update` sobre la cita + 409 si hay un cobro vigente | `ConcurrenciaCobrosTests` (4 hilos en Postgres → 1 solo 201) |
| "Marcar pagado" dos veces | Movía la fecha del ingreso a hoy | 409 si no está pendiente | `test_marcar_pagado_solo_desde_pendiente` |
| Paquete descontado dos veces (Atender + selector) | Posible | Bloqueo de cita y paquete en `sincronizar_paquete` | `PaqueteUnaSolaVezTests` + 4 hilos en Postgres |
| Constraint en la base | No hay | **D7**: requiere contar duplicados en producción primero | — |

## PostgreSQL en CI

- Nuevo job `postgres` (`postgres:17`) con la **suite completa**. Ahí corren las pruebas de concurrencia que SQLite salta: las de correo, que ya existían, y las nuevas de finanzas.
- **Ya pagó su costo:** detectó que `marcar_pagado` con `select_for_update()` sobre un `select_related` de FK nulos **falla en Postgres** ("FOR UPDATE no puede ser aplicado al lado nulable de un outer join"). SQLite lo aceptaba, y en producción habría tumbado "Marcar pagado". Se corrigió con `of=("self",)` (`86da86a`).
- Validado en local con un clúster PostgreSQL 17 desechable (puerto 55432, `trust`, en el scratchpad), sin tocar el servidor existente.
- FAST y STANDARD locales siguen en SQLite (velocidad).
