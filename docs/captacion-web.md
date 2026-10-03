# Captación web: de dónde viene una reserva y qué se puede concluir

Cómo se distingue una reserva hecha por el paciente en el sitio de una
registrada por el equipo, qué se corrigió en producción y qué NO se puede
deducir de los datos. El mecanismo de atribución de origen vive en
`leads/atribucion.py`; el embudo del sitio, en `leads.EventoSitio`.

## 1. `Cita.agendado_web` y la limpieza del 17 set. 2026

`agendado_web` marca las citas que nacieron en el agendamiento público
(`pacientes/agendamiento.py`). Es el eje de cualquier reporte que separe la web
del resto.

**217 citas importadas de AgendaPro estaban marcadas como web sin serlo** y
contaminaban esos reportes. Se corrigió en producción el 17 set. 2026, con
autorización.

Cómo se separaron, por **dos vías independientes** que coincidían:

- sus notas dicen «AgendaPro» o «importado»; las reales dicen «Reserva online»;
- arrancan en junio de 2025, y la primera reserva real es del 3 de julio de
  2026, el día en que se publicó el agendamiento.

Control previo: **cero** de las 217 decía «Reserva online». No había zona gris.

Cómo se ejecutó: dry-run primero; después la **lista exacta de 217 ids** — no un
criterio evaluado al vuelo — dentro de `transaction.atomic()`, tocando **solo**
el campo `agendado_web`. Nada de notas, estado, fechas ni datos clínicos.
Verificado después: 0 de la lista siguen marcadas, quedan **28** reservas web
reales y el total de citas no se movió (8.990). Reversible reidentificando por
el mismo criterio de notas.

## 2. Lo que sobrevivió a la limpieza

Al limpiar, los porcentajes casi no se movieron (cancelación global 36,3 % →
35,7 %). Es decir: **las reservas web sí se cancelan más que las del equipo**
—35,7 % contra 12,1 %— y eso **no** era un artefacto de los datos sucios.

Con 28 casos es muy poca muestra para concluir nada. Queda como señal a vigilar
con el embudo del sitio, no como hecho establecido.

## 3. Avisos de método (dos errores ya cometidos)

- **«No tiene lead asociado» NO prueba que una cita sea importada.** De 245
  citas web, solo 1 tenía un lead enlazado — tampoco las reales lo tienen. Ese
  argumento se usó durante el análisis y la conclusión coincidió por
  casualidad, no por el razonamiento. Si vuelve a aparecer, no vale.
- **Una cita cuya nota dice «lead #N» puede no tener ese lead apuntándole, y es
  normal.** El vínculo `Lead.cita` se escribe al crear la cita desde Marketing
  (`leads/api.py`) y existe para **mover** esa cita cuando corrigen la fecha del
  lead, en vez de duplicarla (cubierto por
  `test_corregir_la_fecha_mueve_la_cita_en_vez_de_duplicarla`). Se suelta a
  propósito en un solo punto: si la cita está CANCELADA, el lead agenda una
  nueva y su puntero pasa a esa, dejando la cancelada con su nota original.
  Además el campo es `on_delete=SET_NULL`: borrar una cita anula el puntero.
  Así que la falta de vínculo es el rastro de un cancelar+reagendar, **no** una
  protección caída.
  Hueco conocido: esa rama (cancelada → cita nueva) no tiene test propio.
