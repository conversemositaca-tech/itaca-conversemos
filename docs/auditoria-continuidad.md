# Auditoría de "Evaluar continuidad" (9 sep 2026)

Antes de rediseñar la tarjeta se auditó, **de solo lectura contra producción**
(`railway ssh`, sin escribir nada), de dónde salían los 391 pacientes que
mostraba la alerta. No se asumió que 391 fuera el universo correcto: se
reconstruyó la consulta exacta que hacía `core/gerencia.py` y se cruzó con la
fecha real de cada cierre. Esto documenta el resultado, tal como pide el
encargo de rediseño (ver el hilo con Mirai del 9 sep).

## El criterio exacto que hacía aparecer a un paciente

`core/continuidad.py::evaluar()` marcaba `fin_bloque_sin_decision` cuando, **sin
mirar ninguna fecha**:

1. la frecuencia del paciente no era `alta` ni `en_pausa`;
2. tenía al menos una cita asistida en TODA su historia;
3. su "sesión real" `n` caía en `meta - 1 <= n <= meta` (meta = el múltiplo de
   6 que le toca): o sea 2 de cada 6 valores posibles, para siempre;
4. la última cita realizada de su historia tenía `decision` vacío.

Ningún paso filtraba por fecha, por origen (importado vs. nativo) ni por
actividad reciente. La consulta barría las ~8.800 citas completas, la mayoría
del volcado de AgendaPro (14 jul 2026); el sistema propio de Ítaca arrancó el
15 jul 2026.

## Los 391, desglosados (producción, 9 sep 2026)

| Corte | Resultado |
|---|---|
| Antigüedad de la última sesión asistida | 25 en ≤7 días · 22 en 8-30 · 41 en 31-90 · 244 en 91-365 · 59 en más de un año |
| Era | 11 nativos de Ítaca (empezaron ≥ 15 jul 2026) · **380 heredados** de AgendaPro |
| Con próxima cita ya agendada (o sea, ya siguieron) | 27 |
| **Más de 90 días sin pisar el consultorio** | **303 de 391** |
| Citas con decisión (código DP) registrada en TODA la base | 125 de 8.823 |
| Por sede | 206 Piura · 185 Lima |

Reclasificando por la **fecha real del cierre** (no solo el número de sesión):

| Estado nuevo | Cuántos | Nota |
|---|---|---|
| `hoy` | 1 | cierra hoy, sin decisión |
| `vencido` (cierre en la era Ítaca, ≤90 días) | 22 | mediana 16 días, máximo 53 |
| `proximo` (próxima cita dentro de 7 días) | 9 | |
| `sin_agendar` (a una sesión de cerrar, sin próxima cita) | 76 | 73 heredados; solo 11 vinieron en los últimos 30 días |
| `continuo_sin_decision` (pasó un cierre y siguió viniendo) | 70 | calidad de registro, no urgencia; 54 activos (≤30 días) |
| `backlog` (cierre hace más de 90 días) | 277 | el 99% heredado |

**Confiabilidad de la fecha de cierre:** en 304 de 308 casos post-cierre
(99%), la fecha sale de la cita que trae el número exacto del bloque
(`Cita.n_sesion == meta`); solo 4 se estiman por posición. La cifra de "días
vencido" es confiable, no una aproximación.

## Conclusión

De 391 "pendientes", **32 pedían algo hoy** (1 hoy + 22 vencidos recientes +
9 próximos). El resto — 277 backlog + 76 sin agendar mayormente heredados + 70
de calidad de registro más 6 sin clasificar — no es la operación del día: es
historia del sistema anterior o un problema de qué tan bien se anota la
decisión, no de a quién hay que llamar hoy.

## Qué cambió

- `core/continuidad.py`: `cola_de_continuidad()` clasifica por la fecha real
  del cierre (`hoy` / `vencido` / `proximo` / `sin_agendar` /
  `continuo_sin_decision` / `backlog`), con ventanas configurables
  (`DIAS_PROXIMOS=7`, `DIAS_BACKLOG=90`) y `pacientes_del_rol()` centraliza el
  alcance por rol (antes repetido en `gerencia.py`).
- `/api/hoy/` → `continuidad`: el resumen (conteos) y los 5 casos más
  urgentes. Ya no manda la lista completa.
- `/api/continuidad/pendientes/` (nuevo): la cola completa, con filtros
  `estado`, `sede`, `medico`, `bloque`, `dias_proximos`.
- `Cita.decision_registrada_en` / `decision_registrada_por` (migración
  `0033`): para poder medir, de aquí en adelante, cuánto tarda coordinación en
  cerrar un bloque y comparar antes/después de este cambio.
- Frontend: la tarjeta de "Hoy" pasa de una lista de chips a un resumen +
  tabla de 5 prioritarios; "Ver todos los pendientes" abre la vista completa
  con los mismos filtros.
- **🕰️ "Migrado de AgendaPro — nunca se le agendó nada acá"** (pedido de
  Mirai el 9 sep, viendo un caso real): se calcula si TODAS las citas del
  paciente (cualquier estado, no solo asistidas) llevan el marcador
  `"Importado de AgendaPro."` que deja `importar_reservas` en `notas` — más
  confiable que una fecha, porque el volcado también trae citas con fecha
  posterior al corte. No es exclusivo del backlog: verificado en producción,
  aparece en 94% de "Cierres antiguos" pero también en 71% de "Sin próxima
  cita", 29% de "Vencidos" y 12% de "Continuó sin decisión" — por eso se
  muestra en cualquier estado, no solo ahí.

## Segundo hallazgo (10 sep): el número de sesión se reinicia por proceso

Mirai pidió cruzar las notas manuales que escribe coordinación ("s5/6",
"s20/24"...) contra el `n_sesion` que guarda el sistema, para verificar que
coincidan. De 1.319 citas con ese patrón de nota:

| | |
|---|---|
| Coinciden con el sistema | 734 |
| El sistema dice OTRO número | 447 (**431 son del volcado de AgendaPro**, 16 son citas nativas) |
| El sistema no tiene ningún número guardado | 39 |

Las 431 discrepancias de AgendaPro se explican solas: la nota preserva la
numeración ORIGINAL de AgendaPro (acumulada de por vida, ej. "SEXTO PROCESO
S31/36" = su sesión 31 de toda la vida), mientras que el importador guardó
`n_sesion` relativo al proceso actual (ese mismo caso: `n_sesion=1`, primera
del sexto proceso). No es un error, son dos convenciones de numeración
distintas. **Las 16 nativas sí son discrepancias reales** (mayormente off-by-one
entre lo que anotó coordinación y lo que quedó en el sistema) — quedan para
que alguien de coordinación las revise, no ameritan un cambio de código.

Pero al construir esa comparación apareció algo más serio: **`n_sesion` se
reinicia cada vez que el paciente empieza un proceso nuevo** (`Paciente.proceso`:
primero, segundo, tercero…) y `resolver_sesion_real()` tomaba el **máximo de
TODA la historia**, no el del proceso en curso. Un paciente que terminó su
primer proceso (sesión 6) hace 90 días y ya va en la sesión 2 de su segundo
proceso aparecía como "sesión 6, cerrado hace 90 días" — es decir, se veía
como backlog viejo cuando en realidad recién está empezando de nuevo.

Verificado en producción, recalculando la cola completa con el criterio
correcto (el número de la cita asistida MÁS RECIENTE, no el más alto):

| | Antes (bug) | Corregido |
|---|---|---|
| Hoy | 2 | 2 |
| Vencidos | 31 | 34 |
| Próximos | 11 | 12 |
| Sin próxima cita | 78 | 81 |
| Continuó sin decisión | 73 | 72 |
| **Cierres antiguos (backlog)** | **265** | **155** |
| **Total en la cola** | **460** | **356** |

**104 pacientes salieron de la cola por completo** (estaban ahí solo por el
error de cálculo: en realidad van bien, recién empezando un proceso nuevo).
Y 17 pacientes que el bug tenía escondidos en "backlog" (baja prioridad)
resultaron ser casos urgentes de verdad — la mayoría pasó a "vencido" o
"próximo", uno incluso debería haberse visto como "cierra hoy". El bug no solo
inflaba la cola: escondía casos reales detrás de ruido histórico.

Arreglado en `core/continuidad.py`: `resolver_sesion_real()` ahora usa el N°
de sesión de la cita MÁS RECIENTE (no el máximo histórico), y `_fecha_de_cierre()`
solo busca dentro del tramo del proceso actual (`_tramo_proceso_actual()`) —
sin esto último, la búsqueda de "la cita que cierra el bloque" podía encontrar
la del proceso ANTERIOR si compartía el mismo número (dos "sesión 6", una de
cada proceso).

## Lo que sigue siendo decisión de Gaby / Dirección Clínica, no de código

- Si el backlog heredado (277 casos, casi todos de antes del 15 jul) se cierra
  en bloque con un código nuevo tipo "histórico — no aplica", se archiva, o se
  deja tal cual visible en "Cierres antiguos".
- Si "continuó sin decisión" (70 casos) debe generar una tarea para
  coordinación o basta con que quede visible como calidad de registro.
- Si alguna de las 16 decisiones DP debe, además de anotarse, actualizar
  automáticamente `Paciente.frecuencia` (p. ej. DP-10 "Alta terapéutica" →
  frecuencia "alta"). Hoy son dos campos independientes.
