# Continuidad formal (fase 2): modelo, fuente de verdad y privacidad

App `continuidad`. Complementos:
[estados y transiciones](continuidad-estados.md) ·
[métricas](continuidad-metricas.md) ·
[Dirección Clínica](direccion-clinica.md).

## 1. Qué resuelve

Hasta la fase 1.5 la continuidad solo se **observaba**: los procesos salían de
la agenda (`core/continuidad.segmentar_procesos`) y el desenlace se adivinaba
con DP sueltos, la ficha (`Paciente.frecuencia`) o una regla de días
("abandono inferido"). La fase 2 permite **registrar** el desenlace de forma
explícita: pausa, alta, abandono confirmado, cierre por otra decisión,
reactivación, cambio de profesional y frecuencia esperada, con motivo
operativo, fecha, quién lo registró y desde dónde.

Continuidad **no** es retener al paciente el mayor número de sesiones. Es que
su trayectoria esté bien comprendida y registrada. Alta, pausa acordada y
cambio de profesional son finales o tránsitos correctos, no abandonos.

## 2. Modelo

```text
Paciente ──< ProcesoContinuidad (uuid, cita_inicio = ancla, estado, frecuencia)
                    │
                    └──< EventoContinuidad (append-only: tipo, estado anterior → nuevo,
                                fecha efectiva, motivo, detalle operativo, profesional
                                anterior/nuevo, frecuencia, quién, origen, clave de idempotencia)
                                      │
                                      └──> MotivoContinuidad (catálogo por clínica)
```

| Modelo | Qué guarda | Qué NO guarda |
| --- | --- | --- |
| `ProcesoContinuidad` | Identidad estable (UUID), ancla (primera sesión), fechas de inicio, estado formal vigente, frecuencia esperada, marca de revisión | Sede, modalidad, contacto, psicólogo, nada clínico: todo eso tiene su propia fuente |
| `EventoContinuidad` | Cada cosa que pasó, sin editar ni borrar | Texto clínico. El detalle operativo es de 280 caracteres y no entra en métricas |
| `MotivoContinuidad` | Catálogo operativo administrable | Diagnósticos: los motivos son de barrera, percepción del servicio, experiencia, operación o decisión acordada |

**El abandono inferido no es una fila.** Es un cálculo
(`continuidad/inferencia.py`) que se muestra al lado del estado formal y nunca
lo cambia.

## 3. Fuente de verdad (transición decidida en la fase 2)

| Dato | Desde la fase 2 | Antes |
| --- | --- | --- |
| Estado del proceso (activo, pausa, alta, abandono confirmado, cierre) | `ProcesoContinuidad.estado` + su historia | `Paciente.frecuencia` = alta / en_pausa, DP de la última cita, inferencia |
| Psicólogo asignado | `Paciente.profesional` (sigue siendo la fuente). El cambio formal lo actualiza y el evento guarda el antes y el después | Igual, sin historia |
| Frecuencia esperada | `ProcesoContinuidad.frecuencia_esperada` | `Paciente.frecuencia` = semanal / quincenal (se lee como respaldo y se rotula «de la ficha») |
| DP de las citas | Siguen intactos, con su significado de siempre | — |

`Paciente.frecuencia` = `alta` / `en_pausa` queda como **evidencia legacy**:
- se usa en la carga histórica (si es inequívoca) y como respaldo para
  clasificar procesos **sin registro formal**;
- no se escribe estado nuevo ahí y sus valores no se borran ni se "limpian".

Precedencia al clasificar un proceso (`core/direccion_clinica.clasificar`):
**formal → legacy (DP / ficha) → inferido**.

## 4. Frontera con el Centro de Continuidad

`pacientes.GestionContinuidad` / `HistorialContinuidad` (fase 1) siguen
siendo la **gestión operativa de un caso puntual**: «¿se revisó el cierre 6?,
¿quién llama?, ¿qué contestó?». Su propio diseño prohíbe guardar alta, DP o
estado clínico, y una gestión «resuelta» no silencia la condición.

La app `continuidad` es la **verdad longitudinal del proceso**. No se tocan ni
se duplican: un resultado operativo «pausa temporal» en una gestión **no**
cambia el estado formal; quien quiera registrar la pausa lo hace desde la
ficha y queda como evento.

## 5. Identidad del proceso y reconciliación

Los procesos se siguen **detectando** con `segmentar_procesos`. La fila
persistida les da identidad para colgar estado e historia. Emparejamiento
(`continuidad/reconciliacion.py`):

1. **Ancla**: la primera sesión del tramo cuando se detectó (`cita_inicio`).
   Si esa cita sigue siendo una sesión de algún tramo, ese es el proceso,
   aunque se le corrija la fecha o se agregue una sesión anterior.
2. Dos procesos persistidos en el mismo tramo → se queda el de ancla en la S1
   (o el más antiguo); el otro queda **`fusion_potencial`**.
3. Ancla perdida (cita anulada o borrada) → tramo libre a **±14 días** de su
   inicio: uno solo, se re-ancla; varios, **`inicio_ambiguo`**; ninguno,
   **`sin_tramo`**.
4. Tramo sin proceso → proceso nuevo; si empieza dentro del período observado
   de otro, nace **`division_potencial`**.

Nunca se fusiona ni se borra un proceso o su historia: las marcas son para
revisión humana y se recalculan en cada reconciliación. La reconciliación
corre al guardar o borrar una cita (al confirmar la transacción y sin poder
romper la Agenda), antes de cada registro y en la carga histórica. Dirección
Clínica usa el mismo emparejamiento **sin escribir**.

Un proceso nuevo nace:
- **ACTIVO** con evento `inicio_proceso` (origen Sistema) si su S1 es igual o
  posterior a la **fecha de corte** de la clínica
  (`ConfiguracionContinuidad.registro_formal_desde`). La fija sola la migración
  `continuidad.0003` con la fecha en que se aplica, es decir, el día del
  despliegue; una clínica nueva recibe la fecha en que se usa por primera vez.
  No hay que configurar nada. El setting `CONTINUIDAD_REGISTRO_FORMAL_DESDE`,
  si existe, la sobrescribe (pruebas o una corrección puntual);
- **Sin estado formal** si es anterior: no se le inventa un estado.

La consolidación de duplicados (`pacientes/fusion.py`) mueve los procesos al
paciente principal como cualquier otra relación (no hay restricciones únicas
sobre `paciente`). Si después dos procesos caen en el mismo tramo, quedan
marcados `fusion_potencial`.

## 6. Permisos (least privilege)

| Rol | Ver estado e historia | Registrar | Lista de revisión |
| --- | --- | --- | --- |
| admin (gerencia) | Sí | Sí | Sí |
| asistente (coordinación) | Sí, su sede | Sí, su sede | Sí |
| analista (Dirección Clínica) | Sí | No (solo lectura, igual que con el DP) | Sí |
| medico (psicólogo) | Solo sus pacientes | No (tampoco registra DP hoy) | No |
| comercial | No | No | No |

Registra quien hoy registra el DP en la Agenda. El origen del evento sale del
rol en el servidor (`gerencia` / `coordinacion`), no del formulario. No se
expone contacto ni contenido clínico.

## 7. Privacidad (Ley 29733)

- Sin diagnóstico, historia clínica, notas de sesión, escalas ni riesgo.
- Motivos operativos o de experiencia de servicio; ninguno describe un cuadro
  clínico (hay un test que lo vigila).
- Detalle operativo de 280 caracteres, rotulado «no es una nota clínica»; no
  se usa en métricas ni se muestra en tablas.
- Nada se envía fuera: la fase 2 no manda WhatsApp, correos ni
  notificaciones.

## 8. Carga histórica

Comando `python manage.py migrar_continuidad_historica` — **solo audita**;
con `--aplicar` registra. Es comando y no migración a propósito: el despliegue
corre `migrate` solo, y escribir estados sin revisar antes los conteos sería
crear certezas sin auditoría.

| Evidencia | Se registra como |
| --- | --- |
| DP-10 en la última cita del proceso | ALTA (motivo «Alta») |
| DP-12 en la última cita | CERRADO (motivo «Derivación externa») |
| Ficha en `alta` (proceso en curso) | ALTA (fecha = última sesión; la real no consta) |
| Ficha en `en_pausa` (proceso en curso) | PAUSA (motivo «Sin información») |

**No se registra**: DP-09 (cubre pausa y fin), DP-11 (no dice a quién se
derivó), DP-04 (no es un proceso con sesiones), contradicciones (alta o pausa
con próxima cita, ficha en pausa con DP-10, ficha en alta con otro DP de
cierre) y todo lo que solo tenga días sin venir. Idempotente (clave
`hist:<uuid>`), origen «Carga histórica», sin usuario.

Auditoría sobre la base demo (90 procesos): 7 DP-10 registrables, 4 DP-09
omitidos por ambiguos, 79 sin evidencia. **En producción hay que correr
primero el modo auditoría** y revisar los conteos antes de `--aplicar`.

## 9. Limitaciones conocidas

- Lo anterior al registro formal queda «sin estado formal»: es lo honesto con
  el ~95 % de cierres sin DP.
- La lista de revisión y el dashboard calculan todo en memoria con un número
  fijo de consultas; con muchos más pacientes convendrá pasar a agregados.
- El psicólogo no registra estados (como hoy no registra DP). Abrirle la
  frecuencia esperada es una decisión de producto pendiente.
- `Cita.modalidad` sigue teniendo «presencial» por defecto (ver fase 1.5).
