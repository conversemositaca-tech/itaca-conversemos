# Dirección Clínica — cómo se calculan las cifras

Pantalla de solo lectura para gerencia (`admin`) y Dirección Clínica
(`analista`). Código: `core/direccion_clinica.py` (API
`GET /api/direccion-clinica/`) y `frontend/src/DireccionClinica.jsx`.
Pruebas: `core/tests_direccion_clinica.py` y `core/tests_direccion_clinica_1_5.py`.

Este documento explica **de dónde sale cada número y qué no se puede concluir
de él**. Si una cifra se usa para decidir algo, léelo antes.

---

## 1. Fuente de datos

- **Sesión realizada** = una `Cita` en estado `asistio` o `atendida` que **no**
  es la consulta inicial (`continuidad.es_consulta`: el servicio contiene
  «consulta»).
- **No cuentan**: citas canceladas, inasistencias, citas futuras y las fichas
  clínicas (`Atencion`) sin cita. Estas últimas son, en su mayoría, las sesiones
  del Excel 2024 – feb 2026: sin cita no hay estado de asistencia ni orden
  confiable. La pantalla dice cuántas son («De dónde salen estos datos»).
- Pacientes provisionales: fuera.
- Alcance: la clínica del usuario (`pacientes_del_rol`), nunca otra.

## 2. Qué es un proceso

Los procesos **no se reconstruyen en esta pantalla**: salen de
`core/continuidad.segmentar_procesos`, la misma regla del Centro de
Continuidad. Una bajada en `Cita.n_sesion` solo parte el proceso si hay
respaldo (nueva sesión = 1, DP de cierre previo, consulta entre medias, cambio
de etapa, lead convertido). Sin respaldo es el mismo proceso con la marca
«numeración inconsistente».

Solo cuentan los tramos con al menos una sesión que no sea consulta: una
consulta que no siguió no es un proceso.

**S1, S2…** es el **orden** de la sesión realizada dentro del proceso, no el
número escrito en la cita (que falta o se reinicia).

## 3. Estado de cada proceso

| Estado | Regla |
| --- | --- |
| Activo | Proceso en curso con próxima cita, o con última sesión hace ≤ N días. |
| **Abandono inferido** | Última sesión hace > N días, sin próxima cita y sin alta ni cierre registrado. N = 45 por defecto (configurable 15–365). |
| Alta registrada | DP-10 en la última cita, o ficha en «alta» (solo el proceso actual). |
| Cierre registrado | Otro DP de cierre (DP-04, DP-09, DP-11, DP-12) o ficha «en pausa». |
| Reinicio | Proceso anterior cortado porque la numeración volvió a empezar a menos de N días. |

### El abandono es inferido, no confirmado

Hoy no existe un estado formal de abandono y ~95 % de los cierres no lleva su
DP. Por eso «abandono inferido» **incluye altas que nadie registró** y
pausas acordadas que no se anotaron. Sirve para ver **dónde** se cortan los
procesos, nunca **por qué**. La pantalla lo rotula así en todos lados.

## 4. KPI = numerador + denominador + N

Ningún porcentaje viaja solo. Cada KPI (`kpi()` en el backend) trae:

- `numerador` — los que cumplen.
- `denominador` — los **evaluables**: aquellos cuyo desenlace ya se conoce.
- `n` — el universo del que salen.
- `no_evaluables` — los que aún no pueden contarse («aún en curso»).
- `pct` — `None` si el denominador es 0 (nunca se divide entre cero).
- `muestra_pequena` — `true` si hay entre 1 y 9 evaluables (ver §8).

Ejemplo en pantalla: **«Pasan de S1 a S3 · 75 % · 66 de 88 evaluables · 2 aún en curso»**.

### Evaluables y «aún en curso»

Para un paso Sk → Sm:

- **Llegaron (N)**: procesos con al menos k sesiones.
- **Pasaron**: llegaron a m.
- **Terminaron antes de m**: abandono inferido, alta, cierre o reinicio.
- **Evaluables** = pasaron + terminaron antes de m.
- **Aún en curso** = activos que todavía no llegan a m. **No entran en el
  denominador**: no tuvieron tiempo; contarlos como caída inflaría el abandono.

Lo mismo para el **abandono inferido**: se calcula sobre los procesos **ya
terminados**; los activos van a no evaluables.

> **Cambio respecto de la fase 1 (PR #127):** allí la tasa de abandono inferido
> se dividía entre *todos* los procesos iniciados, incluidos los activos. Eso
> la diluía más cuanto más reciente era el período (en la base demo, a 3 meses
> daba 20 % cuando, sobre los que ya tienen desenlace, es 75 % — con muestra
> pequeña: 3 de 4). Ahora el denominador es
> el de los terminados.

## 5. Dos universos

- **Cohorte del período**: procesos cuya **S1** cae en el período. De aquí
  salen el embudo, las tasas, medianas y las tablas.
- **Vigente hoy**: procesos activos ahora, empezaran cuando empezaran
  («Procesos activos hoy», «Carga activa hoy»).
- **Sesiones en el período** (por psicólogo y calidad del dato): sesiones cuya
  fecha cae en el período, atribuidas a quien atendió cada una.

## 6. Media vs mediana

Para sesiones por proceso, días entre sesiones consecutivas y días de S1 a
abandono inferido (hasta la última sesión) se dan **media, mediana y N**.
La **mediana es la referencia**: un solo proceso de 60 sesiones mueve la media,
no la mediana.

«Sesiones por proceso (todos)» incluye procesos activos que siguen sumando
sesiones (dato censurado): subestima. Por eso se muestra aparte la de los
**terminados**, que a su vez, en períodos cortos, se sesga hacia los procesos
cortos (los largos todavía no terminaron).

Distribuciones (solo conteos, sin lectura clínica):
sesiones por proceso en tramos 1 · 2–3 · 4–6 · 7–12 · 13+ (terminados y
activos por separado) y días entre sesiones en 0–7 · 8–14 · 15–30 · 31–60 · 61+.

## 7. Filtros

Todos se combinan con AND y se aplican **antes** de calcular cualquier
denominador.

| Parámetro | Valores | Nota |
| --- | --- | --- |
| `periodo` | `30d`, `90d`, `180d`, `365d` (defecto), `todo` | |
| `desde` / `hasta` | `AAAA-MM-DD` | Ganan sobre `periodo`. Formato ilegible o `desde > hasta` → **400**. Solo una de las dos: la otra se completa (2000-01-01 / hoy). |
| `sede` | `lima`, `piura` | Filtra por la sede del paciente. |
| `psicologo` | clave del selector | Psicólogo de la **S1** (si la cita no lo dice, el asignado en la ficha; si no, «Sin asignar»). |
| `categoria` | categorías de `Cita` o `sin_categoria` | Categoría de la cita de la **S1**. |
| `modalidad` | `presencial`, `virtual`, `mixta`, `sin_informacion` | Ver abajo. |
| `etapa` | `1`…`5`, `6+` | Sesiones que lleva el proceso. |
| `dias_abandono` | 15–365 | Ventana del abandono inferido. |

Un valor desconocido de `sede`, `modalidad` o `etapa` **no acota** (se ignora).

**Modalidad del proceso**: si todas sus sesiones dicen lo mismo, esa; si hay
presenciales y virtuales, «mixta»; si ninguna lo dice, «sin información».
Ojo: `Cita.modalidad` vale «presencial» **por defecto**, así que una cita que
nadie marcó también dice presencial. «Sin información» solo aparece en citas
importadas con el campo vacío; el faltante real está subestimado.

En la pantalla los filtros viven en la URL
(`/gestion?vista=direccion&sede=piura&modalidad=virtual…`): recargar,
compartir el enlace o volver atrás conserva el contexto. Solo se escriben los
que difieren del valor por defecto. «Limpiar filtros» vuelve al estado inicial.

## 8. Tablas

- **Por psicólogo**: orden alfabético, «Sin asignar» al final. **Sin ranking,
  sin score, sin colores de bueno/malo.** Procesos, activos, S1→S2 y S1→S3
  (% y num/den), mediana de sesiones (y media), abandono inferido (sobre
  terminados), altas/cierres, sesiones en el período y carga activa hoy.
- **Por sede / categoría / modalidad**: mismas columnas, **orden fijo** (no
  por volumen ni por resultado); lo que no tiene dato va al final y nunca se
  oculta.
- **Muestra pequeña**: regla **técnica**, no clínica — un porcentaje con menos
  de 10 evaluables (`MUESTRA_PEQUENA`) lleva un rótulo gris neutro. No colorea
  ni juzga; avisa que un caso más o menos mueve mucho la cifra.

## 9. Calidad del dato

Se mide sobre el recorte filtrado (excepto «sesiones históricas», que solo
filtra por sede) y siempre con su N:

- sesiones con / sin psicólogo, con / sin N° de sesión, sin modalidad;
- sesiones importadas de AgendaPro vs registradas en el sistema propio — se
  reconoce por la marca `Importado de AgendaPro.` que el importador deja al
  inicio de las notas (si alguien la borró, la cita cuenta como propia);
- cierres de bloque (S6, S12…) con y sin DP;
- procesos terminados solo por inferencia vs con alta/cierre registrado vs por
  reinicio;
- procesos sin psicólogo, con psicólogo tomado de la ficha, sin categoría, sin
  modalidad y con numeración inconsistente;
- sesiones anteriores al 15/07/2026 (época AgendaPro) sin psicólogo.

## 10. Qué NO debe concluirse

- Que un proceso en «abandono inferido» fue un abandono. Puede ser un alta o
  una pausa no registradas.
- Que un psicólogo, sede o categoría es «mejor» que otro. Cambian la población,
  la carga, la modalidad y, sobre todo, **qué tan completo está el registro**.
- Causas: la pantalla no tiene motivo de cancelación, de inasistencia ni de
  cierre. No hay causalidad posible con estos datos.
- Tendencias con muestra pequeña o con períodos donde casi todo sigue activo
  (mira siempre «aún en curso»).
- Comparaciones con la fase 1 sin leer §4: la tasa de abandono cambió de
  denominador.

## 11. Limitaciones conocidas (fase 2 / dependencia de modelo)

**Resuelto en la fase 2** (ver §13): estado formal del proceso con su
historia, motivos estructurados de pausa / alta / abandono / cierre, frecuencia
esperada, cambio de psicólogo y reactivación como eventos propios.

**Sigue pendiente** (requiere otro modelo o una decisión de producto):

- historial de estados de la **cita** y motivo de cancelación / inasistencia;
- modalidad sin valor por defecto (distinguir «presencial» de «no registrado»);
- `Cita.profesional` para atribuir el histórico de AgendaPro;
- motivo de consulta codificado, NPS por sesión, encuestas de utilidad y
  progreso.

## 12. Rendimiento

`construir_procesos` trae todo en un número fijo de consultas (citas
asistidas, próximas citas, señales de reinicio, profesionales y usuarios) y
calcula en memoria. Un test (`PermisosYConsultasTests.test_sin_n_mas_uno`)
verifica que el número de consultas no crece con los pacientes ni con los
psicólogos.

## 13. Fase 2: estado registrado

Desde la fase 2 (app `continuidad`) el desenlace de un proceso puede estar
**registrado** (pausa, alta, abandono confirmado, cierre por otra decisión,
reactivación, cambio de profesional, frecuencia esperada). Lo que cambia aquí:

- **Precedencia**: estado formal → evidencia anterior (DP / ficha) →
  inferencia. Pausa, alta, cierre y abandono confirmado registrados no se
  infieren.
- **Abandono confirmado e inferido van siempre por separado** (resumen,
  embudo, tablas). El combinado solo aparece como «sin continuidad
  registrada», rotulado.
- La ficha «en pausa» pasa de «cierre registrado» a **pausa** (misma base,
  otra etiqueta).
- Nuevo bloque «Estado registrado de los procesos», «Calidad del registro
  formal» y «Para revisión de continuidad».
- Las tablas suman pausas, abandono confirmado, cambios de profesional y
  reactivados.

Definiciones completas: [continuidad.md](continuidad.md),
[continuidad-estados.md](continuidad-estados.md) y
[continuidad-metricas.md](continuidad-metricas.md).
