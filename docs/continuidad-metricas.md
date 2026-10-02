# Continuidad: métricas de la fase 2

Bloque `formal` de `GET /api/direccion-clinica/` (`continuidad/metricas.py`),
con los mismos filtros que el resto del panel (período, sede, psicólogo,
categoría, modalidad, etapa). Todo porcentaje es un KPI completo: numerador,
denominador, N, no evaluables cuando aplica y rótulo neutral «muestra
pequeña» con menos de 10 evaluables (regla técnica de la fase 1.5, sin
cambios). Sin score, ranking, semáforo ni benchmark.

## Cómo se clasifica cada proceso

`core/direccion_clinica.clasificar`:

1. **Formal** registrado: alta, cierre, pausa o abandono **confirmado**.
2. **Legacy**, solo si no hay registro formal: DP-10 o ficha en alta → alta;
   ficha en pausa → pausa; otro DP de cierre → cierre.
3. **Inferido**: activo, abandono **inferido** o reinicio. Un proceso con
   estado formal ACTIVO que dejó de venir aparece como abandono inferido: lo
   inferido se muestra al lado, no reemplaza lo registrado.

> **Cambio respecto de la fase 1.5**: la ficha «en pausa» se contaba como
> «cierre registrado»; ahora se cuenta como **pausa**. No cambia ningún
> denominador (sigue siendo un proceso terminado sin abandono), solo la
> etiqueta. El embudo suma la columna «abandono confirmado»; «alta / pausa /
> cierre / reinicio» ya no la incluye.

## KPIs

| KPI | Numerador | Denominador | N / no evaluables |
| --- | --- | --- | --- |
| Con estado registrado | procesos con estado formal | procesos del período | — |
| Activo / pausa / alta / abandono confirmado / cerrado | procesos en ese estado formal | procesos **con estado registrado** | N = período; no evaluables = sin estado registrado |
| Abandono inferido (resumen) | inferidos | terminados | no evaluables = activos |
| Abandono confirmado (resumen) | confirmados | terminados | no evaluables = activos |
| Reactivados tras una salida | procesos con reactivación | procesos con alguna salida registrada (pausa, alta, abandono, cierre) | — |
| Con cambio de profesional | procesos con ≥ 1 cambio | procesos del período | — |
| Siguen en el centro tras el cambio | cambios con una sesión posterior | cambios evaluables (con sesión posterior o proceso ya terminado) | no evaluables = sin sesión aún, proceso activo y dentro de la ventana |
| Activos hoy sin próxima cita | activos sin próxima cita | activos hoy | — |
| Dentro de su frecuencia esperada | activos con días sin sesión ≤ intervalo | activos con frecuencia (del proceso o, de respaldo, de la ficha) | no evaluables = activos sin frecuencia |
| Registros con motivo conocido | eventos con motivo distinto de «Sin información» | eventos que llevan motivo (pausa, alta, abandono, cierre, cambio de profesional) en el período | — |
| **Sin continuidad registrada** | confirmados + inferidos | terminados | rotulado así a propósito: **no** es una tasa de abandono |

Reactivaciones se informan **por origen**: desde pausa, desde abandono, desde
alta o cierre (por el estado anterior del evento). No se mezclan.

## Motivos

Distribución de los eventos con motivo del período: por categoría y por
motivo, con N y **porcentaje sobre los motivos conocidos**. «Sin información»
va aparte, con su N y su porcentaje sobre el total: nunca se esconde. Se usa
el motivo vigente (el de la última corrección).

## Frecuencia

Activos hoy por frecuencia esperada (semanal, quincenal, mensual,
personalizada, no definida), indicando cuántas vienen de la ficha. La
desviación es `días sin sesión / intervalo` y el atraso en días: sirven para
priorizar una revisión, no para calificar. Ninguna frecuencia es «mejor».

## Calidad del registro formal

Procesos sin estado registrado (KPI) · solo con inferencia · con estado de
evidencia anterior (legacy) · estados de la carga histórica · activos sin
frecuencia esperada (KPI) · salidas sin motivo · motivos «Sin información» ·
cambios de profesional sin sesión posterior (> 14 días) · procesos que la
reconciliación no pudo ubicar.

## Lista para revisión de continuidad

`GET /api/continuidad/revision/` (admin, coordinación, analista; alcance por
rol). Razones: activo sin próxima cita · pasó el intervalo esperado ·
pausa con fecha de revisión vencida · cambio de profesional sin sesión
posterior (> 14 días) · abandono inferido sin confirmar (si el proceso es
formalmente activo, o si su última sesión es de los últimos 180 días) ·
sesión después de un cierre sin reactivación · identidad del proceso por
revisar. Solo información: no contacta a nadie ni cambia estados.

## Por psicólogo, sede, categoría y modalidad

Las tablas existentes suman pausas, abandono confirmado, cambios de
profesional y reactivados (orden alfabético o fijo, sin ranking, sin texto
libre). El proceso se sigue atribuyendo al psicólogo de la S1 (regla
histórica): un cambio de profesional cuenta en la fila del psicólogo de la S1
como «cambio», **no** como abandono. La atribución retroactiva no se inventa.

## Qué NO concluir

- Abandono (confirmado o inferido) no implica mala calidad de la atención.
- Un cambio de profesional no es pérdida del centro.
- Alta y pausa no son abandono.
- Más sesiones no significa mejor resultado.
- Menos continuidad no demuestra causa: los motivos son operativos y la
  mayoría del histórico no tiene registro.
- Con muestra pequeña no hay conclusiones fuertes.
- Los porcentajes de estado formal describen a los procesos **con registro**;
  mientras el registro sea parcial no representan a todos.

## Rendimiento

Dos consultas más que la fase 1.5 (procesos persistidos y eventos), sin
importar cuántos pacientes, eventos o psicólogos haya: lo fija
`continuidad/tests/test_dashboard.py::test_consultas_no_crecen_con_eventos`.
