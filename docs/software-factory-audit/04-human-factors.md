# 04 · Factores humanos, UX y ergonomía operativa

## 0. Alcance y método

- **Snapshot auditado:** `origin/main` al **1 oct 2026** (último merge `ae759b8`, PR #137). Rama adicional `origin/feat/direccion-clinica` (HEAD `832a754`, **sin mergear**), marcada **[rama DC]**.
- **Rutas:** `App.jsx:N` = `frontend/src/App.jsx` en main. Las demás rutas son relativas a la raíz del repo (`leads/api.py:189`).
- **Método:** lectura del código y del historial de git. **No hubo observación en sitio**, ni entrevistas, ni medición de tiempos, ni acceso a la base de datos.
  - Los **clics** salen de contar los pasos que el código exige; son estimaciones.
  - Las **frecuencias** ("decenas al día", "semanal") son **estimaciones** a partir del rol y del proceso descrito en `03-business-processes.md`. Cuando no hay nada en el código que las respalde, van marcadas **HIPÓTESIS**.
  - Los **conteos** (35 modales, 286 etiquetas, 93 clicables…) salen de búsquedas sobre el snapshot y sí son cifras del código.
- **Pregunta guía:** ¿qué le pasa a quien opera el sistema 8 horas al día, con prisa, interrupciones y la red de la sede?
- **Fuera de alcance:** el sitio público (salvo como comparación), Eli, Brújula en Apps Script.

---

## 1. Resumen: las 8 fricciones más graves

| # | Fricción | Rol afectado | Riesgo | Frecuencia (estimada) | Severidad |
|---|---|---|---|---|---|
| 1 | **Cancelar o marcar "No asistió" una cita con un solo cambio de desplegable, sin confirmación** (`App.jsx:7647`, `8119`). La confirmación existía y se perdió en `ed5c439` | Recepción / Coordinación | Cita cancelada por error, paquete devuelto, asistencia y liquidación alteradas | Decenas de cambios de estado al día por coordinadora (HIPÓTESIS sobre el volumen) | **Crítica** |
| 2 | **35 modales se cierran con un clic fuera y pierden lo escrito**: nota clínica con dictado (`AtenderModal`, `App.jsx:8323`), alta de paciente de 32 campos (`14105`), lead de ~30 campos (`9509`) | Psicólogo, Recepción | Pérdida de texto clínico y de datos de captación; rehacer trabajo | Diaria (todos los ingresos de datos pasan por modales) | **Crítica** |
| 3 | **El toast decide si es error mirando si el texto empieza por "Error"** (`App.jsx:1952`): ≈33 mensajes de fallo salen con **check verde**; además un toast viejo borra al nuevo (`App.jsx:845`) | Todos | La persona cree que algo se guardó o se envió cuando no | Cada fallo de red o validación | **Crítica** |
| 4 | **Doble cobro posible**: ~24 de 34 modales no bloquean el botón mientras guardan; el cobro nace en **efectivo + pagado** por defecto (`App.jsx:12155-12156`) | Recepción, Administración | Dos cobros, cobro con medio equivocado, pendiente registrado como pagado | Cada cobro (el valor por defecto); doble clic: baja por evento | **Alta** (dinero) |
| 5 | **Pacientes duplicados al agendar a alguien "nuevo"**: el buscador solo busca por nombre y "Crear paciente nuevo" siempre está visible; `agendarCita` crea la ficha sin el aviso de duplicado (`App.jsx:1005`) | Recepción | Historia clínica partida en dos fichas | Diaria | **Alta** (dato clínico) |
| 6 | **"Con esto la cita queda en la agenda" es falso si no se elige psicólogo** (`App.jsx:9682`; default "Sin asignar" `9644`; el backend exige médico `leads/api.py:189`) | Recepción, Comercial | El consultante llega y nadie lo espera | Cada lead con consulta sin psicólogo | **Alta** |
| 7 | **Acciones peligrosas sin confirmar**: borrar adjunto clínico, egreso, servicio; desactivar usuario; enviar informes Faro a familias; "OK a todo"; cambiar etapa de lead | Administración, Recepción, Psicólogo (Faro) | Borrados irreversibles, correos a familias de menores sin revisión final | Semanal (HIPÓTESIS) | **Alta** |
| 8 | **Navegación sin URL** (`useState("hoy")`, `App.jsx:595`): Atrás saca del sistema, F5 vuelve a "Hoy"; el **Centro de Continuidad no está en el menú** | Todos, sobre todo Coordinación | Desorientación, trabajo perdido, la cola diaria escondida | Constante | **Media-alta** |

Fuera del top 8 pero también relevantes: lead que nace como **TikTok Ads + pauta = sí** (§2.1, F-R7), el botón **"Cobrar" que solo aparece si la cita está "atendida"** (§2.1, F-R8) y la **accesibilidad** del sistema interno (§3).

---

## 2. Por rol

Roles del código (`usuarios/models.py:43-51`): `asistente` = Recepción / Coordinación, `admin` = Gerencia / Administración, `analista` = Dirección Clínica, `medico` = Psicólogo, `comercial`. Personas reales según `03-business-processes.md` §1.

### 2.1 Recepción / Coordinación (`asistente`)

Es el rol que **más horas pasa en el sistema**: agenda, leads, cobros, continuidad y mensajes.

**Tareas frecuentes y recorrido estimado (leyendo el código)**

| Tarea | Recorrido | Clics aprox. | Frecuencia (estimada) |
|---|---|---|---|
| Confirmar / marcar asistencia | Agenda (Día) → desplegable de estado de la fila → opción. Se guarda al instante | **2** por cita | Varias veces por cita, todo el día |
| Agendar sesión a paciente existente | Agenda → "Agendar sesión" → escribir nombre → clic en resultado (autorrellena psicólogo, servicio, sede) → fecha → hora → Agendar | **7-8** | Decenas al día (HIPÓTESIS) |
| Agendar la siguiente sesión | Fila → "Duplicar" (+7 días) → revisar → Agendar | **3** (buen atajo) | Diaria |
| Agendar desde un hueco | Vista Terapeutas → clic en hueco (precarga fecha, hora y psicólogo; `App.jsx:1262-1273`) → paciente → Agendar | ~5 | Diaria |
| Cobrar | Fila (solo si `atendida`, `App.jsx:7666`) → modal: servicio → medio → comprobante → Guardar | ~6 | Cada sesión atendida |
| Recordatorio por WhatsApp | Fila → "Mensaje" → cambiar plantilla de "seguimiento" a "Recordatorio" (`App.jsx:8608`) → Enviar | 4 | Diaria |
| Registrar lead | Marketing → "+ Nuevo lead" (`App.jsx:9071`) → modal de ~30 campos → Guardar | 2 + 6-10 campos + 1 | Diaria |
| Encontrar un lead | Marketing → scroll hasta la lista (`App.jsx:9275`), debajo de 7 bloques de analítica y configuración | scroll largo | Diaria |
| Revisar continuidad | Hoy → tarjeta de Continuidad (`App.jsx:3898, 3937`) → "Ver todos" → tabla de 9 columnas con scroll horizontal → fila → panel | 3-4 | Diaria |

**Fricciones**

**F-R1. Cancelar una cita desde el desplegable, sin confirmación.**
- **Causa:** `CitaRow` muestra el estado como `<select>` que persiste en `onChange` (`App.jsx:7647-7651`); las opciones incluyen "Cancelada" y "No asistió" (`App.jsx:119-129`). `CitaDetalleModal` hace lo mismo (`App.jsx:8119`). El `ConfirmModal` de cancelar solo se alcanza desde un botón del modal de detalle (`App.jsx:1940-1946`, `8170`). El commit `ed5c439` (1 jul 2026) quitó la "X" con confirmación "porque ya lo maneja el desplegable".
- **Impacto humano:** un select enfocado cambia con la rueda del mouse o con una flecha del teclado. Un descuido cancela la cita, devuelve la sesión del paquete (`pacientes/api.py:779`) y altera asistencia y liquidación. Nadie avisa; el error se descubre cuando el paciente llega.
- **Frecuencia:** el select se toca decenas de veces al día (estimación); el error, ocasional (HIPÓTESIS).
- **Posible solución:** el select aplica de inmediato solo estados "suaves" (confirmada, en espera, asistió); "Cancelada" y "No asistió" piden confirmación con el nombre del paciente y la hora, o muestran "Deshacer" durante 5-10 s.

**F-R2. Alta de paciente y lead se pierden con un clic fuera.**
- **Causa:** `<div className="ca-modal-bg" onClick={onClose}>` en 35 de 40 modales, entre ellos `PacienteModal` (`App.jsx:14105`, 32 campos), `CrearLeadModal` (`9509`, ~30 campos), `AgendarModal` (`7360`) y `CobroModal` (`12192`). No hay detección de cambios, ni borrador, ni Escape.
- **Impacto humano:** con una llamada entrante o un clic fuera de lugar se pierde el formulario completo; la recepcionista lo rehace mientras la persona espera en el teléfono. Se aprende a desconfiar del sistema.
- **Frecuencia:** diaria (HIPÓTESIS sobre cuántas pérdidas reales; el riesgo está en cada apertura).
- **Posible solución:** `<Modal>` base que no cierra por clic en el fondo si el formulario está sucio, y pide confirmación al salir.

**F-R3. El toast miente y se pisa.**
- **Causa:** `esError = /^error\b/i.test(toast)` (`App.jsx:1952`). Unos 29 mensajes de `App.jsx` empiezan por "No se pudo…", "Falta…", "Escribe…" (p. ej. `672`, `693`, `914`, `1700`, `4887`, `5445`, `9772`) y 4 de `Duplicados.jsx` (`134`, `146`, `159`, `405`) pasan `e.message` sin prefijo: ≈33 fallos con **check verde**. Además `setTimeout(() => setToast(""), 2800)` sin `clearTimeout` (`App.jsx:845`): el timer de un toast viejo borra el nuevo antes de tiempo. Cuando el backend devuelve errores por campo, el toast muestra JSON crudo (`api.js:8-37`).
- **Impacto humano:** "No se pudo enviar el WhatsApp" con check verde se lee como "enviado". Con dos acciones seguidas (confirmar, luego mover) el segundo mensaje casi no se ve.
- **Frecuencia:** cada error de red o validación; los toasts encadenados son frecuentes en la agenda (estimación).
- **Posible solución:** `toast.ok()` / `toast.error()` con tipo explícito, cola, más duración para errores, `aria-live`.

**F-R4. Doble cobro y valores por defecto peligrosos en el cobro.**
- **Causa:** ~24 de 34 modales con formulario (`CobroModal`, `VenderPaqueteModal`, `PagarModal`, `EgresoModal`, `PacienteModal`, `CrearLeadModal`, `AtenderModal`…) no tienen estado `enviando`; el botón solo se atenúa si `!canSave`. El "deshabilitado" es `pointerEvents:none` (23 casos, p. ej. `App.jsx:12290`): con Tab + Enter sigue funcionando. El cobro nace con `useState("pagado")` y `useState("efectivo")` (`App.jsx:12155-12156`; también `11971`, `11997`, `12054`). Un monto con coma ("80,50") da `NaN` y el botón queda gris sin explicación.
- **Impacto humano:** con la red lenta, un segundo clic crea un segundo cobro. Un Yape registrado como efectivo descuadra la caja al cierre del día; un pago pendiente queda como cobrado.
- **Frecuencia:** el valor por defecto actúa en **cada cobro**; el doble clic, baja por evento.
- **Posible solución:** `<BotonGuardar busy>` con `disabled` real; medio de pago sin preseleccionar y obligatorio; coma aceptada como decimal; resumen antes de guardar.

**F-R5. Duplicados al agendar paciente nuevo; buscador solo por nombre.**
- **Causa:** el selector filtra solo `p.nombre` y muestra 4 resultados (`App.jsx:7318-7321`; igual en `CobroModal`, `12163-12166`). La fila "Crear paciente nuevo: '…'" aparece siempre. `agendarCita` llama a `api.crearPaciente` **sin** pasar por `AvisoDuplicado` (`App.jsx:1005`); si el backend responde 409 por posible duplicado, se ve "Error: {json}" en vez de la comparación lado a lado que sí tiene `guardarPaciente` (`App.jsx:983-992`). El propio código dice que 57 de 76 duplicados nacieron "guardando sin mirar" (`App.jsx:984-987`).
- **Impacto humano:** con un nombre escrito distinto ("Ma. José" / "María José") o un homónimo, la recepcionista no ve a la persona y crea otra ficha. La historia clínica se parte y luego alguien tiene que fusionar a mano.
- **Frecuencia:** diaria (agendar es la tarea central).
- **Posible solución:** `<SelectorPaciente>` único que busque por nombre, teléfono y DNI, navegable con teclado, y que reutilice `AvisoDuplicado`.

**F-R6. "La cita queda en la agenda" falso sin psicólogo.**
- **Causa:** texto fijo en `App.jsx:9682`; el psicólogo arranca en "Sin asignar" (`App.jsx:9644`); `sincronizar_cita_del_lead` exige `medico_id` y devuelve `None` en silencio si falta (`leads/api.py:189`).
- **Impacto humano:** la recepcionista confía en el texto, le dice al consultante que está agendado, y el día de la consulta no hay cita.
- **Frecuencia:** cada lead con consulta en el que no se elige psicólogo (no medible desde el código).
- **Posible solución:** psicólogo obligatorio cuando "¿Agendó?" = Sí; texto condicional; aviso del backend que el toast muestre.

**F-R7. Lead nace como TikTok Ads + pauta = sí.**
- **Causa:** `fuente: lead?.fuente || "tiktok_ads"`, `es_pauta: lead ? lead.es_pauta : true` (`App.jsx:9415`, `9418`); sede por defecto "lima" para gerencia (`9414`).
- **Impacto humano:** no hace falta equivocarse: basta con no tocar el campo para que el dato sea falso. Infla el retorno de la pauta y el reporte de cierre que luego se usa para decidir inversión.
- **Frecuencia:** cada lead registrado a mano.
- **Posible solución:** origen vacío y obligatorio, o recordar el último usado por esa persona.

**F-R8. "Cobrar" solo si la cita está "atendida".**
- **Causa:** `c.estado === "atendida"` (`App.jsx:7666`). Coordinación marca "Asistió" (estado distinto, `asistio`); "atendida" la pone el psicólogo al registrar la sesión. Son dos estados para la misma idea (`03-business-processes.md` §3.2).
- **Impacto humano:** el botón no aparece cuando la persona espera verlo; el cobro se olvida o se registra desde "Venta" sin vincular la cita, lo que rompe la marca "Cobrada" y la conciliación.
- **Frecuencia:** diaria.
- **Posible solución:** mostrar "Cobrar" también con `asistio`.

**F-R9. Recordatorio que abre con texto de seguimiento.**
- **Causa:** desde una cita, `MensajePacienteModal` precarga el texto de seguimiento y `tipoSel="seguimiento"` (`App.jsx:8608`). Previsualizar las plantillas "consentimiento"/"políticas" **crea un consentimiento en el servidor** (`App.jsx:8624-8628`).
- **Impacto humano:** se envía el mensaje equivocado o la cita no queda marcada como recordada; quedan consentimientos huérfanos.
- **Frecuencia:** diaria.
- **Posible solución:** preseleccionar "Recordatorio" cuando se abre desde una cita; crear el consentimiento solo al enviar.

**F-R10. Fila de cita sobrecargada y dos modelos de guardado.**
- **Causa:** cada `CitaRow` muestra hasta 2 selects (estado y "¿Qué pasó?" con 85 códigos DP) + 7 botones (`App.jsx:7642-7699`); encima, 3 franjas de chips y 4 selects (`7836-7932`). En `CitaDetalleModal` el estado se guarda al instante pero el resto espera "Guardar" (`App.jsx:8119`).
- **Impacto humano:** la pantalla más usada es la más densa; "Eliminar" queda junto a "Duplicar". Con dos modelos de guardado, la persona cree que "Cerrar" deshace el cambio de estado.
- **Frecuencia:** constante.
- **Posible solución:** acciones secundarias en un menú "⋯"; la acción principal según el estado; un solo modelo de guardado por modal.

**F-R11. Lead: etapa que cambia sin confirmar y lista enterrada.**
- **Causa:** `<select className="ca-tplsel" onChange={moverEstado}>` (`App.jsx:9337`), incluido "perdido". La lista está al final de Marketing (`App.jsx:9275`), después de pauta, autoagenda, embudo, cierre, fuentes y anuncios; el token de captación queda a la vista a diario.
- **Impacto humano:** un lead marcado "perdido" por error sale de la cola de seguimiento y nadie lo vuelve a llamar.
- **Frecuencia:** diaria.
- **Posible solución:** igual que F-R1 para "perdido"; pestañas Leads (por defecto) / Reportes / Configuración.

**F-R12. Centro de Continuidad fuera del menú y sin URL.**
- **Causa:** la vista `continuidad` no tiene ítem en la barra lateral; solo se entra desde la tarjeta de Hoy (`App.jsx:3898`, `3937`). La navegación es `useState` (`App.jsx:595`).
- **Impacto humano:** la cola de trabajo diaria de Coordinación depende de una tarjeta que puede no cargar (ver F-T3 en §2.2 sobre errores silenciosos). Al recargar (o con la recarga automática de medianoche, `App.jsx:855-868`) se vuelve a "Hoy".
- **Frecuencia:** diaria.
- **Posible solución:** ítem propio en el menú y URL `/gestion/continuidad`.

**F-R13. Al convertir un lead se vuelve a teclear.**
- **Causa:** DNI, fecha de nacimiento y tutor se piden otra vez en `PacienteModal`; el paciente creado desde "Agendar" queda solo con nombre y teléfono (`App.jsx:7426`) y nada recuerda completarlo; el motivo se pide en el lead **y** en `AgendarModal`; el cobro no hereda el servicio de la cita salvo coincidencia exacta (`App.jsx:12152`).
- **Impacto humano:** doble digitación, errores de transcripción y fichas incompletas (sin fecha de nacimiento un menor se trata como adulto en correo, `correo/services/destinatario.py:112-122`).
- **Frecuencia:** cada conversión y cada cobro.
- **Posible solución:** precargar desde el lead; tarjeta "Ficha incompleta" en Hoy.

### 2.2 Administración / Gerencia (`admin`)

**Tareas frecuentes:** revisar Hoy e Indicadores, cobros y caja, egresos, liquidación, servicios y precios, usuarios, alertas de eliminaciones, Faro, espacios. Ve **20 ítems** en la barra lateral, sin agrupar (más un ítem "Pronto" de Facturación SUNAT que no hace nada).

**F-A1. Borrados y cambios irreversibles sin confirmar.**
- **Causa:** sin confirmación: eliminar egreso (`App.jsx:11769-11772`), eliminar servicio de precios (`12340-12343`), desactivar usuario (`13914-13917`), "OK a todo" sobre las alertas de eliminaciones (`3675` → `marcarTodasEliminacionesRevisadas`, `3611`).
- **Impacto humano:** borrar un servicio rompe la liquidación, que empareja por nombre (`finanzas/liquidacion.py:55-90`). Desactivar al usuario equivocado deja a una coordinadora fuera en plena jornada. "OK a todo" borra de un clic la trazabilidad del control antifraude de borrados de citas y pagos.
- **Frecuencia:** semanal (HIPÓTESIS).
- **Posible solución:** `useConfirm()` con la consecuencia escrita ("Se marcarán 14 avisos como revisados").

**F-A2. 20 ítems planos y una pantalla Hoy con 9 bloques.**
- **Causa:** menú sin grupos; Hoy apila hasta 9 bloques antes de "Próximas sesiones", que muestra solo 3 (`slice(0,3)`, `App.jsx:839`).
- **Impacto humano:** búsqueda visual constante; lo urgente queda al fondo.
- **Frecuencia:** constante.
- **Posible solución:** agrupar el menú (Operación / Clínica / Comercial / Finanzas / Configuración) y ordenar Hoy según el rol.

**F-A3. Errores que no se ven.**
- **Causa:** 45 `.catch(() => {})`. En Hoy, si `api.hoy()` falla, las tarjetas quedan en "…" para siempre (`App.jsx:3581-3583`). Así estuvo la pantalla inicial de los psicólogos con un 500 hasta `6a5fe11` (13 set).
- **Impacto humano:** se espera sin saber que hubo un error, y se toman decisiones con números que no cargaron.
- **Frecuencia:** con mala conexión o fallo del backend.
- **Posible solución:** estado de error con "Reintentar" en un componente común.

### 2.3 Dirección Clínica (`analista`)

**Tareas frecuentes:** lectura de indicadores, continuidad (única escritura permitida, `core/permisos.py:49`), y en la rama, la pantalla Dirección Clínica.

**F-D1. En main no tiene pantalla propia ni enlace compartible.**
- **Causa:** sin router; el analista navega las mismas vistas que gerencia en solo lectura. **[rama DC]** `DireccionClinica.jsx` añade `?vista=direccion` y filtros en la URL.
- **Impacto humano:** no puede mandar "mira este corte" a nadie; cada reunión empieza reconstruyendo filtros.
- **Frecuencia:** semanal (HIPÓTESIS).
- **Posible solución:** mergear el patrón de la rama y generalizarlo a todas las vistas.

**F-D2. Cifras que no cuadran entre pantallas.**
- **Causa:** "asistió", "abandono", "próxima cita", "activo" se calculan con reglas distintas en Hoy, Gerencia, Centro de Continuidad y Dirección Clínica (`03-business-processes.md` §3.3 y §8.1; D1-D3 de la rama).
- **Impacto humano:** carga cognitiva y pérdida de confianza: la persona tiene que recordar qué pantalla "cuenta bien". Es un problema de factores humanos aunque su causa sea de backend.
- **Frecuencia:** cada revisión de indicadores.
- **Posible solución:** una definición única por noción, y cada porcentaje con su base visible (la rama ya lo hace con `kpi()`).

### 2.4 Psicólogo (`medico`)

**Tareas frecuentes:** ver su agenda, abrir la ficha antes o durante la sesión, registrar la sesión (texto o dictado), Faro si participa.

| Tarea | Recorrido | Clics aprox. |
|---|---|---|
| Registrar sesión | Agenda → "Registrar sesión" → tipo de ficha → escribir o dictar → Guardar | 3 + texto |
| Ver historia clínica | Pacientes → buscar → clic → una página larga con ~18 secciones; "Historia clínica" en la posición ~17 (`App.jsx:6944-7278`) | scroll |

**F-P1. La nota clínica (con dictado) se pierde con un clic fuera.**
- **Causa:** `AtenderModal` cierra con clic en el fondo (`App.jsx:8323`); sin borrador ni aviso.
- **Impacto humano:** es el peor caso de F-R2: texto clínico redactado o dictado y transcrito, a veces justo al terminar la sesión, desaparece. Rehacerlo de memoria baja la calidad del registro.
- **Frecuencia:** cada sesión registrada en la app está expuesta (pérdidas reales: HIPÓTESIS).
- **Posible solución:** modal que no se cierra si hay texto; borrador local por cita.

**F-P2. Cambiar el tipo de ficha descarta campos en silencio.**
- **Causa:** `guardar()` solo envía `fichaCampos` del tipo actual (`App.jsx:8314-8318`).
- **Impacto humano:** contenido clínico perdido sin aviso.
- **Frecuencia:** ocasional.
- **Posible solución:** avisar al cambiar de tipo si hay texto, o conservarlo.

**F-P3. Ficha sin estructura navegable.**
- **Causa:** ~18 secciones en una columna, sin pestañas ni índice (`App.jsx:6944-7278`).
- **Impacto humano:** tiempo y atención gastados justo antes o durante la sesión.
- **Frecuencia:** cada sesión.
- **Posible solución:** pestañas por rol (Resumen · Clínica · Proceso · Agenda y pagos · Archivos).

**F-P4. Eliminar un adjunto clínico sin confirmación.**
- **Causa:** `App.jsx:899-903`, `5986`.
- **Impacto humano:** borrado irreversible de un documento clínico con un clic.
- **Frecuencia:** baja (HIPÓTESIS).
- **Posible solución:** confirmación con el nombre del archivo.

**F-P5. Faro: enviar informes a las familias sin confirmación.**
- **Causa:** un solo botón (`App.jsx:12479-12483`). El emparejamiento puede ser "solo por nombre" (`faro/registro.py:69-83`) y no hay excepción intrafamiliar (`faro/informes.py:211-241`).
- **Impacto humano:** correos con resultados de salud mental de **menores** que salen sin una revisión final; con homónimos, a la familia equivocada.
- **Frecuencia:** por aplicación de Faro (pocas veces al año, alto impacto).
- **Posible solución:** paso de revisión que liste destinatarios y excepciones antes de enviar; nunca un envío de un clic.

### 2.5 Comercial (`comercial`)

Sin persona asignada hoy (`03-business-processes.md` §1). Comparte con Recepción el registro y seguimiento de leads, así que hereda **F-R2** (lead de ~30 campos que se pierde), **F-R6** (cita falsa), **F-R7** (TikTok Ads por defecto), **F-R11** (etapa sin confirmar, lista enterrada) y los **5 caminos de WhatsApp** (§4). Para un rol nuevo, la curva de aprendizaje de Marketing (7 bloques antes de la lista) es la primera barrera (HIPÓTESIS: no hay registro de capacitación de este rol).

### 2.6 Analista (rol `analista`) y transversales

El rol `analista` del código **es** Dirección Clínica (§2.3). Fricciones que afectan a todos los roles:

- **F-T1. Sin URL por pantalla** (`App.jsx:595`): Atrás sale del sistema, F5 vuelve a Hoy, no hay enlaces a una ficha. La recarga automática de medianoche (`App.jsx:855-868`) también devuelve a Hoy.
- **F-T2. Dos scrolls y 12 % de altura perdida**: el sistema es una tarjeta de `height:88vh` dentro de un `#root` con padding (`App.jsx:1188`). En una laptop de recepción eso es espacio útil perdido.
- **F-T3. Errores silenciosos** (45 `.catch(() => {})`, ver F-A3).
- **F-T4. Cerrar sesión desaparece en móvil**: `.ca-profile { display:none }` por debajo de 720 px (`App.jsx:1614`). En un celular compartido no se puede salir de un sistema con datos de salud mental.
- **F-T5. Lista de pacientes sin paginar**: renderiza todas las filas (`App.jsx:1779`) y cada guardado recarga la lista completa (`App.jsx:732`). Lentitud en equipos modestos (HIPÓTESIS: no se midió).
- **F-T6. Información crítica en `title=`** (122 usos): no existe en pantallas táctiles.

---

## 3. Accesibilidad (sistema interno)

| Aspecto | Cifra / evidencia | Consecuencia práctica |
|---|---|---|
| Etiquetas | **286** `<div className="ca-label">` sin `<label>`; **0** `htmlFor` | Los campos no tienen nombre accesible; clic en la etiqueta no enfoca el campo |
| Clicables sin teclado | **93** `div`/`tr` con `onClick` (`ca-pickrow`, filas de Continuidad `App.jsx:5730`, celdas del mes, `ca-wkhd`) | No se pueden usar con Tab/Enter; el buscador de paciente no se navega con flechas |
| Formularios | Sin `<form>` salvo Login: Enter no envía | Más ratón, más tiempo |
| Modales | 0 `role="dialog"` en modales internos, 0 con Escape, sin foco atrapado ni devuelto | El foco queda detrás del modal; un lector de pantalla no anuncia nada |
| Botones de cerrar | 34 "X" sin `aria-label`; 26 `ca-iconbtn` sin `aria-label` | Botones sin nombre |
| Falso disabled | 23 `pointerEvents:none` | Se activan con teclado (F-R4) |
| Foco visible | `.ca-input` con `outline:none` y solo 1 px de cambio de borde (`App.jsx:1460-1461`); solo 3 reglas `:focus-visible` en todo el sistema interno | Quien usa teclado no sabe dónde está |
| Toast | Sin `aria-live` | Los mensajes no se anuncian |
| Contraste (WCAG, calculado) | Loader `#9B968D`/`#FBFAF8` = **2,82:1**; ámbar `#C9923A` = **2,74:1**; chip "Sin próxima sesión" `#B0822F` = **3,45:1**; `.ca-mini.done` `#2F8F5B`/`#E6F4EC` = **3,56:1**; tag de modalidad `#7C7870`/`#EFEDE8` = **3,76:1** (mínimo AA 4,5:1) | Estados importantes poco legibles, sobre todo con brillo bajo o reflejo |
| Texto pequeño | 103 líneas con 9-11 px | Fatiga visual en jornadas largas |
| A favor | `prefers-reduced-motion` respetado (`App.jsx:1357`, `1456`, `1524`, `1604`); empty states bien redactados (51) | — |

**Comparación:** el sitio público y el agendamiento tienen `:focus-visible`, `role="alert"` y 42 `aria-*`; el código nuevo de la rama usa `<label>`, `aria-label`, `role="dialog"` y `aria-modal`. **La deuda está concentrada en el sistema interno heredado**, que es justamente el que se usa 8 horas al día.

---

## 4. Consistencia y carga cognitiva

- **4 paletas paralelas**: tokens de `.clinica-app` (`--accent:#0A7D92`, `App.jsx:1183-1185`), su copia con prefijo `--wa-*` (`3983-3985`), la de la agenda pública (`--acento:#00788C`, `14801-14819`) y objetos `const C` en `Login.jsx` y `PreferenciasCorreo.jsx`. Además **851 colores hex sueltos** y **dos rojos de "peligro"** distintos en uso (`#B4564E` y `#9C4646`, 43 veces cada uno). Un mismo significado no siempre tiene el mismo color.
- **5 caminos para mandar WhatsApp**, cada uno con su lógica y su texto por defecto:
  1. `MensajePacienteModal` (Agenda y Ficha);
  2. `RecordarModal` (renderizado en `App.jsx:1914` pero **nadie lo abre** desde `ed5c439`: código muerto);
  3. `WhatsappModal` (Continuidad, 451 líneas);
  4. `EnviarRecursoModal` (Herramientas);
  5. enlace `wa.me` directo (`App.jsx:8761`) y respaldo `window.open(r.wa_url)` (`906`).
  La persona aprende cinco formas de hacer lo mismo y no sabe cuál deja registro de qué.
- **Tablas y filtros distintos**: `ca-table` (12) y `ca-tbl` (8), listas con `ca-row`, 23 `<table>` a mano; sin orden por columna salvo en Continuidad; ~25 barras de filtros de chips + selects; las sedes "lima/piura" escritas a mano 10 veces. Cada pantalla se lee distinto.
- **Confirmaciones de 4 tipos**: `window.confirm` (24), `window.prompt` para datos de negocio (2: descripción de pago `App.jsx:7131`, nota de seguimiento `9043`), `ConfirmModal` (1 uso) y el flujo de dos pasos de Duplicados. El mismo nivel de riesgo se trata distinto.
- **Dos modelos de guardado** en el mismo modal (F-R10) y **dos estados de asistencia** (`asistio` / `atendida`, F-R8).
- **Densidad**: la fila de cita (2 selects + 7 botones), Hoy (9 bloques), Marketing (7 bloques antes de la lista), la Ficha (~18 secciones). Emojis como señal semántica (🚩, 🔔, ⏰) junto al color: ayudan a la vista, pero no son legibles por lector de pantalla.
- **Componentes base casi inexistentes**: 40 modales escritos a mano, 22 cabeceras de modal copiadas, 1.927 líneas con `style={{…}}`. Por eso cada arreglo de UX se hace pantalla por pantalla (§5).

---

## 5. Cómo se descubre la UX hoy

**Patrón observado en git:** la UX se valida **en producción, con el equipo**, y se corrige **por lotes**.

- 8 commits mencionan explícitamente a la coordinadora o la capacitación ("Correcciones de Gaby (SE EXIGENTE)" `ed5c439`, "Lote UX" `0c78801`, correcciones de capacitación `56872e4`, `3c406c3`, `562440b`).
- **El aviso (toast) se arregló 3 veces** en un día: no se veía por `overflow:hidden` (`5360d7d`), tardaba y salía abajo (`744c519`), verde/rojo con la regex que hoy clasifica mal (`f293943`). El tercer arreglo creó F-R3.
- **El resumen de la Agenda se iteró 4 veces** (`6830f93`, `817fd59`, `702ff50`, `831b8e0`): diseño a prueba y error.
- Bugs vistos por la persona antes que por el equipo: fecha congelada ("5 de julio" el día 8, `0c78801`); nota que se partía letra por letra (`f8b82f2`); modal "angosto y muy alto" ensanchado de 440 a 760 px (`8cb7203`); Hoy de los psicólogos caída con un 500 sin mensaje (`6a5fe11`).
- **Permisos ajustados después de que la gente los vio** (`56872e4`, `562440b`).
- Un "arreglo" quitó una salvaguarda: `ed5c439` bajó la densidad de la fila y **eliminó la confirmación de cancelar** (F-R1).
- **Ningún commit registra QA en navegador** hasta septiembre (0 coincidencias); no hay tests de frontend ni prototipos.

**Por qué se repite:** sin componentes base no hay un lugar donde corregir una sola vez; cada pantalla vuelve a cometer el mismo error.

**El patrón nuevo que ya funciona mejor [rama DC]:** `DireccionClinica.jsx` (811 líneas) y `ContinuidadFicha.jsx` (355) son la **primera pantalla fuera de `App.jsx`**, y traen:
- `<label>`, `aria-label`, `role="dialog"` y `role="alert"`;
- modal que no se cierra mientras guarda (`onClick={enviando ? undefined : onClose}`, `ContinuidadFicha.jsx:137`);
- filtros y vista en la URL (`?vista=direccion`);
- cada porcentaje con su base (numerador, denominador, muestra pequeña);
- concurrencia: si el estado cambió entretanto, 409 en vez de pisar (`continuidad/servicios.py`).

Es la plantilla natural para extraer los componentes del §6.

---

## 6. Patrones UX que deben ser estándar en cualquier sistema futuro

Checklist para la fábrica. Cada punto nace de una fricción concreta de este sistema.

- [ ] **Confirmación de destructivos, con la consecuencia escrita.** Todo lo que borra, cancela, desactiva, envía a terceros o marca en lote pasa por `useConfirm({ titulo, consecuencia, peligro })`. Los estados destructivos dentro de un select (cancelada, no asistió, perdido) también. Preferir "Deshacer" cuando sea reversible. *(F-R1, F-R11, F-A1, F-P4, F-P5)*
- [ ] **Envíos a terceros con paso de revisión.** Correos o mensajes masivos (informes, campañas) muestran destinatarios y excepciones antes de salir. *(F-P5)*
- [ ] **Modales que no pierden datos.** `<Modal dirty busy>`: no cierra por clic en el fondo si hay cambios; Escape con la misma regla; borrador local en notas largas. *(F-R2, F-P1)*
- [ ] **Toasts con tipo explícito.** `toast.ok` / `toast.error` / `toast.aviso`; nunca inferir por el texto; cola sin pisarse; errores con más duración; `aria-live`; nada de JSON crudo. *(F-R3)*
- [ ] **Botón guardar con bloqueo real.** `<BotonGuardar busy disabled motivo>`: `disabled` nativo durante el envío y cuando falta algo, con el motivo visible. Idempotencia en el backend para cobros. *(F-R4)*
- [ ] **Valores por defecto honestos.** Ningún campo que alimente dinero o atribución nace con un valor "probable" (medio de pago, estado pagado, origen del lead): vacío y obligatorio, o el último usado por esa persona. *(F-R4, F-R7)*
- [ ] **Textos de ayuda que dicen la verdad.** Un texto que promete un efecto ("la cita queda en la agenda") se condiciona al caso real o se reemplaza por el resultado que devuelve el servidor. *(F-R6)*
- [ ] **URL por pantalla y por registro.** `/gestion/:vista/:id` con filtros en la query; Atrás y F5 funcionan; todo lo que se usa a diario está en el menú. *(F-T1, F-R12)*
- [ ] **Buscador de persona por nombre, teléfono y DNI**, tolerante a tildes, navegable con teclado, con aviso de duplicado reutilizado en todos los altas. *(F-R5)*
- [ ] **Estados vacío / carga / error en un solo componente**, con "Reintentar"; prohibido `.catch(() => {})` en la UI. *(F-A3, F-T3)*
- [ ] **Teclado.** `<form>` (Enter envía); todo clicable es `<button>` o tiene `role` y `tabIndex`; foco visible (`:focus-visible`) en botones, chips y menú; foco atrapado y devuelto en modales. *(§3)*
- [ ] **Etiquetas reales.** `<Campo label>` con `<label htmlFor>`, error por campo, nunca solo placeholder. *(§3)*
- [ ] **Contraste AA (4,5:1) validado en los tokens**, no color por color; tamaño mínimo 12 px en el sistema interno. *(§3)*
- [ ] **Un solo modelo de guardado por formulario** y **un solo estado por concepto** (no `asistio` y `atendida`). *(F-R8, F-R10)*
- [ ] **Una sola vía por acción** (un composer de WhatsApp, un formulario de cobro). *(§4)*
- [ ] **Una sola fuente de tokens de diseño.** *(§4)*
- [ ] **Pantalla de lista estándar**: lo operativo arriba, analítica y configuración en pestañas aparte, paginación. *(F-R11, F-T5)*
- [ ] **Ficha con pestañas por rol.** *(F-P3)*
- [ ] **Precarga de lo ya conocido** (lead → paciente, cita → cobro). *(F-R13)*
- [ ] **QA en navegador registrado en el PR** con el recorrido del rol que lo va a usar, antes de capacitar. *(§5)*

---

## 7. Priorización

**P0: riesgo de error humano con datos clínicos o dinero** (hacer primero; la mayoría son cambios pequeños)

| # | Acción | Fricciones | Esfuerzo (estimado) |
|---|---|---|---|
| 1 | Confirmación o "Deshacer" para Cancelada / No asistió en los selects de cita (`App.jsx:7647`, `8119`) | F-R1 | Bajo |
| 2 | Modales con formulario que no se cierran por clic fuera si hay cambios: empezar por `AtenderModal`, `PacienteModal`, `CrearLeadModal`, `CobroModal`, `AgendarModal` | F-R2, F-P1 | Bajo-medio |
| 3 | Toast con tipo explícito y timer que se limpia (`App.jsx:845`, `1952`) | F-R3 | Bajo-medio (278 llamadas) |
| 4 | Bloqueo de envío y `disabled` real en cobros, paquetes, pagos y egresos; medio de pago sin preseleccionar | F-R4 | Bajo |
| 5 | `agendarCita` con `AvisoDuplicado` (`App.jsx:1005`) y búsqueda por teléfono/DNI en el selector | F-R5 | Medio |
| 6 | Psicólogo obligatorio cuando el lead agendó, o texto condicional (`App.jsx:9682`) | F-R6 | Bajo |
| 7 | Confirmación en adjunto clínico, egreso, servicio, desactivar usuario, "OK a todo"; paso de revisión en el envío de informes Faro | F-A1, F-P4, F-P5 | Bajo |
| 8 | Avisar antes de descartar campos al cambiar el tipo de ficha clínica | F-P2 | Bajo |

**P1: errores de dato y fricción diaria alta**

| # | Acción | Fricciones |
|---|---|---|
| 9 | Origen del lead vacío y obligatorio (`App.jsx:9415`, `9418`) | F-R7 |
| 10 | "Cobrar" también con `asistio` (`App.jsx:7666`) | F-R8 |
| 11 | Recordatorio preseleccionado desde una cita; consentimiento creado solo al enviar | F-R9 |
| 12 | Confirmar "perdido" en leads; lista de leads en primera pestaña | F-R11 |
| 13 | Centro de Continuidad en el menú; router mínimo con URL por vista (extender el patrón de la rama) | F-R12, F-T1, F-D1 |
| 14 | Estado de error con "Reintentar" en Hoy y en las cargas principales | F-A3, F-T3 |
| 15 | Cerrar sesión visible en móvil (`App.jsx:1614`) | F-T4 |

**P2: carga cognitiva, accesibilidad y base para la fábrica**

| # | Acción | Fricciones |
|---|---|---|
| 16 | Componentes base (`Modal`, `Campo`, `BotonGuardar`, `SelectorPaciente`, `Estado`, `Tabla`) extraídos desde la rama DC | §4, §6 |
| 17 | Etiquetas reales, teclado, foco visible y contraste AA en tokens | §3 |
| 18 | Un solo composer de WhatsApp; borrar `RecordarModal` | §4 |
| 19 | Fila de cita con menú "⋯"; Hoy y menú ordenados por rol; ficha con pestañas | F-R10, F-A2, F-P3 |
| 20 | Precarga lead → paciente y cita → cobro; aviso de ficha incompleta | F-R13 |
| 21 | Paginación de pacientes y refresco puntual | F-T5 |
| 22 | QA en navegador por rol como requisito de merge | §5 |

**Nota final.** Las frecuencias de este documento son estimaciones a partir del código. Antes de ordenar dentro de cada nivel conviene **media jornada de observación en recepción** (Lima y Piura) y en una sesión de registro clínico, contando cuántas veces se cambia el estado de una cita, se abre un modal de alta y aparece un error. Eso convierte las HIPÓTESIS en cifras.
