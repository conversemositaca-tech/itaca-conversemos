# 04 · Decisiones que son de Max (no se tomaron por él)

Cada una cambia cifras, la operación del equipo o una política. El código quedó **preparado y documentado**, sin decidir.

## D1 · Alertas de Faro: ¿pool o asignación?

- **Hoy:** cualquier psicólogo (rol `medico`) ve, atiende y envía informes de **todas** las alertas del tamizaje escolar. No existe ningún campo "psicólogo asignado" ni una relación psicólogo-colegio (`faro/models.py`).
- **Por qué no se restringió:** sin un modelo de asignación, restringir dejaría alertas rojas (riesgo en menores) sin nadie que las vea. El protocolo exige llegar al estudiante el mismo día (`faro/api.py`, comentario del panel interno).
- **Opciones:**
  - (a) mantener el pool y documentarlo como política;
  - (b) agregar "psicólogo responsable por colegio" y restringir (requiere migración y definir el reemplazo en ausencias);
  - (c) mantener el pool, pero dejar que solo el responsable envíe informes a familias.
- La celda `faro.alertas · medico = 200` queda marcada como **brecha conocida** en la matriz.

## D2 · KPI "asistencia %" de gerencia

- **Hoy:** `core/gerencia.py` calcula atendidas / (atendidas + canceladas). **No cuenta `asistio`**, que es la mayoría de las citas (las marcadas desde la agenda y todas las importadas), y no incluye `no_asistio` en el denominador.
- **Propuesta:** `ESTADOS_REALIZADA / (ESTADOS_REALIZADA + no_asistio + cancelada)`. Ya existe `ESTADOS_CERRADA`.
- **Efecto:** el número que ve gerencia **cambia de forma notable**. Por eso no se tocó.

## D3 · Recordatorios de citas ya resueltas

- **Hoy:** `pacientes/recordatorios.py` y `core/gerencia.py` excluyen solo {atendida, cancelada}. Una cita del día ya marcada `asistio` o `no_asistio` sigue contando como recordatorio pendiente.
- **Efecto del cambio:** se enviarían menos mensajes y bajaría el contador de "pendientes de recordar".

## D4 · ¿"Reprogramada" ocupa el horario?

- **Hoy:** `_choque_de_horario` no la cuenta (puede agendarse otra cita encima), pero el agendamiento público sí la cuenta como ocupada. La secuencia de correo DP-02 tampoco la considera "reservó".
- **Efecto del cambio:** aparecerían conflictos 409 nuevos al agendar y se cortarían más secuencias.

## D5 · Matriz de transiciones de estado de cita

- **Hoy:** `POST /api/citas/<id>/estado/` acepta cualquier transición: cancelada → atendida, atendida → agendada, etc. Desde la Fase 1 cada cambio **queda auditado** y cancelar o marcar "no asistió" pide confirmación en la interfaz.
- **Decisión pendiente:** qué transiciones se permiten y quién puede salir de "cancelada". Corregir errores del equipo es legítimo, así que una matriz rígida puede estorbar más que ayudar.

## D6 · Coordinación y analista sobre adjuntos clínicos

- Hoy ven todos los adjuntos, igual que la historia clínica. Mínimo privilegio sugiere revisarlo. Es política clínica.

## D7 · Constraint de un cobro vigente por cita en la base

- La Fase 1 lo garantiza en la aplicación (bloqueo + 409, probado con 4 hilos en Postgres).
- Una `UniqueConstraint` condicional en la base sería la red final, pero **fallaría al migrar** si ya existen duplicados en producción (importaciones antiguas).
- **Paso previo:** contar duplicados en producción (consulta de solo lectura) y decidir cómo limpiarlos.

## D8 · Idempotency-Key para vender paquetes

- Vender un paquete no tiene clave natural (a diferencia del cobro de una cita). Hoy lo protege el permiso de caja más el botón. Un `Idempotency-Key` en la API cerraría también los reintentos de red. Es un cambio menor, pero de contrato con el frontend.

## D9 · Tokens por alcance y despliegue (vienen de la Fase 0)

- Configurar `ITACA_TOKEN_RESPALDO`, `ITACA_TOKEN_TAREAS` e `ITACA_TOKEN_ELI` en Railway, kira-bot y Eli.
- Regenerar los tokens de los consentimientos pendientes tras el despliegue.
