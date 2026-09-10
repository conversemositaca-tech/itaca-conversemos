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

## Lo que sigue siendo decisión de Gaby / Dirección Clínica, no de código

- Si el backlog heredado (277 casos, casi todos de antes del 15 jul) se cierra
  en bloque con un código nuevo tipo "histórico — no aplica", se archiva, o se
  deja tal cual visible en "Cierres antiguos".
- Si "continuó sin decisión" (70 casos) debe generar una tarea para
  coordinación o basta con que quede visible como calidad de registro.
- Si alguna de las 16 decisiones DP debe, además de anotarse, actualizar
  automáticamente `Paciente.frecuencia` (p. ej. DP-10 "Alta terapéutica" →
  frecuencia "alta"). Hoy son dos campos independientes.
