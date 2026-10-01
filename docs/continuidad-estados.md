# Continuidad: estados, eventos, transiciones y motivos

Reglas en `continuidad/servicios.py` (una sola fuente; el frontend solo
muestra las acciones que el servidor devuelve).

## Estados formales

| Estado | Significado |
| --- | --- |
| `sin_registro` | Proceso anterior al registro formal, o nadie registró su estado. No es «activo» ni «abandono» |
| `activo` | En curso |
| `pausa` | Pausa acordada; sin fecha de fin obligatoria, con fecha tentativa de revisión opcional |
| `alta` | Alta del proceso |
| `abandono` | Abandono **confirmado**: consta que se interrumpió sin alta, pausa ni cambio de profesional |
| `cerrado` | Cerrado por otra decisión acordada (p. ej. derivación externa) |

**Reactivación** y **cambio de profesional** son eventos, no estados: el
proceso vuelve a, o sigue en, `activo`. Así un cambio de profesional nunca
aparece como pérdida del paciente.

**Estados operativos derivados** (no se guardan, `continuidad/inferencia.py`):
activo con próxima cita · activo sin próxima cita · abandono **inferido**
(última sesión hace más de N días, sin próxima cita y sin desenlace
registrado) · no aplica (pausa, alta, abandono confirmado, cierre o evidencia
legacy).

## Transiciones permitidas

| Evento | Desde | Hacia | Motivo |
| --- | --- | --- | --- |
| `inicio_proceso` | (nuevo) | activo | — · solo el sistema |
| `continuacion_confirmada` | sin_registro | activo | no lleva |
| `pausa_iniciada` | activo, sin_registro | pausa | **obligatorio** |
| `reactivacion` | pausa, abandono, alta, cerrado | activo | no lleva |
| `alta` | activo, sin_registro | alta | opcional |
| `abandono_confirmado` | activo, sin_registro, pausa | abandono | **obligatorio** («Sin información» vale) |
| `cierre` | activo, sin_registro, pausa | cerrado | **obligatorio** |
| `cambio_profesional` | activo, sin_registro | activo | opcional · exige profesional nuevo activo, de la clínica y distinto del actual |
| `cambio_frecuencia` | sin_registro, activo, pausa | (igual) | no lleva |
| `correccion_motivo` | cualquiera | (igual) | el correcto · apunta al evento corregido |

Lo que no está en la tabla se rechaza (400). En particular:
- **alta → pausa**, **alta → activo sin reactivación**, **abandono → activo
  sin reactivación**: no.
- **pausa → alta**: no; primero se reactiva (el alta es una decisión del
  proceso en curso).
- El **fin de una pausa** es el evento que sale de ella (reactivación,
  abandono confirmado o cierre); la historia lo marca `finaliza_pausa`. No hay
  un evento «pausa finalizada» aparte: duplicaría el mismo hecho.
- `abandono_inferido` no es un evento: es cálculo y nunca se escribe.

Validaciones comunes: fecha no futura, no anterior al inicio del proceso ni al
último registro; fecha de revisión ≥ inicio de la pausa; detalle ≤ 280
caracteres; motivo activo, de la clínica y aplicable a ese evento.

## Concurrencia e idempotencia

`transicionar_proceso` corre en `transaction.atomic()` con
`select_for_update()` sobre el proceso (y la reconciliación bloquea al
paciente). Además:
- **estado esperado**: el formulario manda el estado que vio; si otra persona
  lo cambió entretanto, 409 en vez de pisarlo;
- **clave de idempotencia**: una por formulario abierto; un doble clic o
  reintento devuelve el mismo evento (200, `repetido: true`) sin crear otro.
  Restricción única `(clínica, clave)` en la base.

## Historial append-only

`EventoContinuidad.save()` sobre una fila existente y `delete()` lanzan error;
el admin es de solo lectura; el motivo de un evento usado está protegido
(`PROTECT`). Un motivo equivocado se corrige con `correccion_motivo`: el
original queda tal cual y las métricas usan el de la última corrección.

## Motivos (catálogo inicial)

Operativos, nunca clínicos. Administrables en el admin de Django; un motivo se
**desactiva** (`activo=False`), no se borra.

| Categoría | Motivos |
| --- | --- |
| Barrera externa | Economía (DP-14), Horario (DP-15), Disponibilidad de tiempo, Viaje, Mudanza, Salud general, Modalidad, Otra barrera externa |
| Percepción del servicio | No percibe necesidad, Expectativa diferente, No percibe avance, Prefiere otra alternativa |
| Experiencia | No conectó con el profesional, No se sintió escuchado, La metodología no encajó, Solicita cambio de profesional, Inconformidad con la atención (DP-16), Otra experiencia |
| Operación | Dificultad con la agenda, Demora en la respuesta, Pago, Error administrativo, Otra causa operativa |
| Decisión acordada | Pausa acordada, Alta (DP-10), Cambio de profesional acordado, Derivación externa (DP-12), Otra decisión acordada |
| Otro | Otro |
| Desconocido | Sin información |

Cada motivo declara a qué eventos aplica (pausa / alta / abandono / cierre /
cambio de profesional).

### Compatibilidad con los DP (según su uso real en el código)

| DP | Relación |
| --- | --- |
| DP-14, DP-15 | Equivalencia exacta con Economía y Horario |
| DP-16 | «Inconformidad con la atención» (Experiencia), sin forzar un motivo más específico |
| DP-10, DP-12 | Alta y Derivación externa |
| DP-02 | **No se mapea**: es una decisión de la consulta inicial (grupo `DP_INICIO`), no un motivo de salida |
| DP-09 | **No se mapea**: cubre «suspende temporalmente» y «finaliza» |
| DP-11 | **No crea** un cambio de profesional: no dice a quién |

Ningún DP histórico se reescribe; `codigos_dp` solo documenta la equivalencia.
