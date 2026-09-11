# Product Marketing Context — Ítaca Conversemos

**Document version:** v1
**Last updated:** 2026-09-11

> Documento de contexto que leen las skills de marketing (`revops`, `churn-prevention`,
> `analytics`, `onboarding`, `customer-research`, `sales-enablement` y el resto).
> Describe el negocio y el sistema **tal como existen**, no como un SaaS genérico.
>
> **Cómo está marcada cada afirmación:**
> - **[V]** verificado en el código, en los datos de producción o en la documentación del repo
>   (`CLAUDE.md`, `docs/auditoria-continuidad.md`, `docs/marca-exportables.md`).
> - **[I]** inferencia operativa razonable a partir de lo verificado; no está escrita en ningún lado.
> - **[P]** pendiente de validar con el equipo, con datos o con `customer-research`.
>
> Si una skill necesita un dato marcado **[P]**, debe preguntarlo, no asumirlo.

---

## 0. Cómo leer este documento (traducción de vocabulario)

Las skills están escritas para SaaS/B2B. En Conversemos los conceptos existen, pero significan otra cosa. Esta tabla manda sobre cualquier definición genérica de las skills. **[V]** salvo donde se indica.

| Vocabulario de las skills | Qué es en Conversemos | Dónde vive en el sistema |
|---|---|---|
| Lead | Persona que pide información o atención y todavía no inició terapia. | `leads.Lead` (13 estados, 21 fuentes) |
| MQL / SQL / Opportunity | No existen como tales. El embudo del lead es: nuevo → contactado → seguimiento/recontacto → consulta agendada → consulta realizada → evaluando inicio → **inició proceso** (ganado) / perdido. | `Lead.Estado` |
| Conversión principal inicial | Lead que llega a la **primera sesión**: consulta inicial con decisión **DP-01 "Inicia proceso"** y conversión a `Paciente`. | `Cita.Decision`, `leads.api.convertir_lead_en_paciente` |
| Customer / cuenta | **Paciente** (en el sitio: "consultante"). | `pacientes.Paciente` |
| Onboarding / activación | Recorrido desde el contacto inicial hasta la primera sesión e incorporación al proceso terapéutico. | Agenda pública `/agendar/<token>`, recordatorios, consentimiento, DP-01 |
| Retención / continuidad | Mantenimiento del proceso terapéutico después de iniciado: bloques de 6 sesiones con decisión clínica al cierre. | `core/continuidad.py` |
| Churn / abandono | Interrupción o pérdida de continuidad del paciente. No hay suscripción que cancelar. | Riesgo S3, cierre sin decisión, DP-09/14/15/16, frecuencia "en pausa" |
| Riesgo de abandono | Señales operativas que el sistema detecta **antes** del abandono: la cola del Centro de Continuidad. | `EstadoCierre` |
| Recuperación / win-back | Seguimiento que reactiva o confirma continuidad: contacto por WhatsApp desde el caso + registro del resultado. | Gestión del caso + `core/contacto_continuidad.py` |
| CRM | Capa operativa para gestionar contacto, seguimiento, responsables, acciones, historial y resultados. **No** es un CRM comercial ni hay pipeline de ventas. | Centro de Continuidad + Gestión del caso + bitácora de mensajes |
| Pipeline / deal | La "venta" es una decisión clínica registrada (código DP), no una negociación. | `Cita.decision` |
| Canal principal | **WhatsApp** por Evolution API, con una línea por sede. | `mensajes/` |
| Analytics | No hay GA4/GTM ni analítica web. Las métricas salen del propio sistema. | `core/gerencia.py`, `core/metricas.py`, `core/reportes.py` |
| Ventas / sales enablement | No hay equipo de ventas. Quien "vende" es **coordinación** (por WhatsApp) y el psicólogo en la consulta inicial. | Roles `asistente` y `medico` |

---

## 1. Product Overview

**One-liner:** **[V]** Centro de psicología con sedes en Lima y Piura que brinda terapia presencial y online, y un sistema propio de gestión (agenda, historia clínica, captación, continuidad, WhatsApp y gerencia).

**What it does:** **[V]** Ítaca Conversemos atiende terapia psicológica individual (adultos), de niños y adolescentes, de pareja, familiar, de lenguaje y evaluaciones psicológicas, en dos sedes físicas y de forma online. Lema del sitio: *"Hablamos de salud mental en un espacio seguro para sanar, brindando terapia presencial y online."* Lema de marca: **"Te cambia la vida"**.

**El sistema** **[V]**: aplicación web propia (Django + React, desplegada en Railway) usada por gerencia, coordinación de cada sede, psicólogos y Dirección Clínica. Reemplazó a AgendaPro y a un Excel operativo por sede desde el **15 de julio de 2026** ("era Ítaca"); el histórico anterior está importado.

**Product category:** **[V]** Servicio de salud mental (psicología clínica). Categoría en la que la gente busca: "psicólogo en Lima/Piura", "terapia online", "terapia de pareja", "psicólogo para niños".

**Product type:** **[V]** Servicio profesional presencial y online, pagado por sesión.

**Business model:** **[V]**
- Pago **por sesión** (no hay suscripción). La primera consulta dura 30–45 minutos; el sitio público muestra el precio del catálogo real (`finanzas.Servicio`, editable por gerencia) y, si no hay uno cargado, **S/ 50**. **[P]** Los precios vigentes por tipo de terapia y por psicólogo no están en el código: el bot de captación responde *"el costo depende del tipo de terapia y del profesional"*.
- **Paquetes de sesiones prepagadas** (`finanzas.Paquete`, estilo AgendaPro) opcionales.
- Medios de pago registrados: efectivo, Yape, Plin, tarjeta, transferencia, Mercado Pago. Comprobantes: boleta, factura, recibo por honorarios, nota de venta. **[V]** Fuera de alcance por decisión: comprobantes electrónicos SUNAT e IGV.
- Los psicólogos **liquidan por sesión atendida** (monto por sesión definido en el servicio / porcentaje en la ficha del profesional).
- Metas de facturación mensual por defecto: **S/ 20 000 mínima / S/ 30 000 ideal**, configurables por sede.
- Contacto público del sitio: `conversemos.itaca@gmail.com` · teléfono 965 337 290 · botón de WhatsApp del sitio +51 961 350 844. **[P]** `CLAUDE.md` menciona además una "línea WhatsApp oficial +51 941 697 769" en una etapa anterior; hay que confirmar cuál es el número vigente para "Tengo más preguntas".

**Sedes** **[V]**:
| Sede | Dirección | Teléfono | Coordinación (responsable de la línea de WhatsApp) |
|---|---|---|---|
| Lima | Av. Arequipa 4130, Of. 205 — Miraflores | +51 980 453 832 | Ayvi |
| Piura | Av. Bolognesi 582, Of. 201 — Piura | +51 983 292 173 | Yazmín |

**Equipo clínico** **[V]**: 14 psicólogos en el directorio (8 Lima, 6 Piura), todos con número de colegiatura (C.Ps.P.) visible en la agenda pública. Enfoques declarados: conductual-contextual, sistémico y terapias de tercera generación, cognitivo-conductual y racional-emotivo, terapia de esquemas e integrativo. Modalidad por profesional: presencial, virtual o ambas, con horario semanal y modalidad por hora.

---

## 2. Target Audience

**Target "companies":** No aplica. Es B2C: personas y familias. **[V]** Existe una fuente de lead "Convenio / Empresa" (`DP-07`, `Fuente.CONVENIO`), así que hay algo de atención por convenios; **[P]** no está documentado su peso ni cómo opera.

**Decision-makers (quién decide iniciar):** **[I]** la propia persona adulta; el padre/madre o tutor en niños y adolescentes (el sistema guarda `tutor_telefono`); ambos miembros en pareja.

**Primary use case:** **[V]** Recibir acompañamiento psicológico —presencial u online— por un motivo de consulta, con un psicólogo colegiado elegido por la persona o sugerido por coordinación.

**Segmentos de servicio** **[V]** (son los `Lead.TipoServicio` y `Cita.Categoria` del sistema): adultos · niños · adolescentes · pareja · familia · lenguaje · evaluación psicológica (informes, constancias).

**Cobertura geográfica** **[V]**: el bot de captación asigna sede por distrito mencionado. Lima: Miraflores, San Isidro, Surco, Barranco, San Borja, La Molina, Jesús María, Lince, Magdalena, Pueblo Libre, San Miguel, Surquillo, Chorrillos, La Victoria, Rímac, Breña, Cercado, SMP, Los Olivos, Independencia, Comas, Carabayllo, Puente Piedra, SJL, SJM, VES, VMT, Ate, Santa Anita, El Agustino, Callao. Piura: Castilla, Sullana, Talara, Paita, Catacaos, 26 de Octubre, Chulucanas, Tambogrande, Sechura, La Unión. Online: cualquier lugar.

**Jobs to be done** **[I]** (derivados de las FAQ del sitio y los motivos de consulta detectados por el bot):
- "Quiero empezar terapia pero no sé si es para mí ni cuánto cuesta" → una primera consulta barata y corta para conocer al psicólogo.
- "Necesito ayuda para mi hijo/a o para mi pareja" → atención especializada por segmento.
- "Ya estoy en terapia pero no conecto con mi psicóloga" → cambiar de profesional sin salir del centro.
- "No puedo ir presencial" → terapia online con la misma atención.

**Use cases del sistema** **[V]**: agendar consulta inicial desde el sitio; recordar y confirmar sesiones por WhatsApp; registrar la historia clínica (incluida nota por voz); detectar y gestionar pacientes en riesgo de abandono; cobrar y liquidar; ver indicadores por sede y período.

---

## 3. Personas

Hay dos familias de personas: **quien recibe el servicio** (el paciente) y **quien usa el sistema** (el equipo). Las skills de `onboarding` y `churn-prevention` trabajan sobre la primera; `revops`, `analytics` y `sales-enablement` sobre la segunda.

### 3a. Del lado del paciente **[I]** (perfiles inferidos de segmentos y FAQ; **[P]** validar con `customer-research`)

| Persona | Le importa | Su reto | Lo que Conversemos le promete |
|---|---|---|---|
| Adulto que da el primer paso | Confidencialidad, que le toque un buen psicólogo, no gastar de más | Vergüenza/duda de si "es para tanto"; no saber cuánto durará | Primera consulta corta y económica para conocer al psicólogo; puede elegirlo o cambiar |
| Padre / madre | Que el profesional sepa de niños/adolescentes; horarios; qué le dirán | Involucrarse sin invadir | Psicólogos con especialidad infanto-juvenil; indicaciones a los padres |
| Pareja | Neutralidad, que ambos se sientan escuchados | Coordinar dos agendas | Terapia de pareja con profesional específico |
| Paciente online | Que funcione igual que presencial; link claro | Distancia, tecnología | Link de Zoom el día de la sesión; "la misma atención que en consultorio" |

### 3b. Del lado del equipo **[V]** (son los roles del sistema)

| Rol en el sistema | Quién | Qué ve / puede | Le importa |
|---|---|---|---|
| `admin` (Gerencia) | Gerencia / dueña; en la práctica Gaby y Mirai | Todo: ambas sedes, dinero, equipo, conexión de WhatsApp, editor Excel | Facturación vs. meta por sede, captación, retención, productividad por psicólogo |
| `asistente` (Coordinación) | Ayvi (Lima), Yazmín (Piura) | Solo su sede. Agenda, pacientes, leads, cobros, plantillas; **contacta pacientes por WhatsApp**; gestiona casos de continuidad | Que nadie se le pierda: leads sin responder, citas sin confirmar, pacientes sin próxima sesión |
| `medico` (Psicólogo/a) | Los 14 del directorio | Solo sus pacientes; **no ve teléfonos** ni contacto (Ley 29733); escribe historia clínica y registra la decisión DP; gestiona sus casos de continuidad pero **no** contacta | Prepararse para la sesión, mantener la historia al día, que el paciente sepa su siguiente paso |
| `analista` (Dirección Clínica) | Dirección Clínica | Solo lectura en todo; ambas sedes; ve dinero; **única escritura**: gestión de casos de continuidad; no ve contacto ni contacta | Calidad del registro clínico, continuidad, indicadores |
| `comercial` | — | No ve pacientes; ve marketing/captación | Campañas y leads |

---

## 4. Problems & Pain Points

### Del paciente **[I]** (a partir de las FAQ del sitio; **[P]** validar verbatim con entrevistas/encuestas)

**Core problem:** dar el paso de empezar terapia con dudas sobre costo, duración, confidencialidad y si "el psicólogo me va a entender".

**Por qué las alternativas fallan (inferido):** no ir a terapia deja el problema igual; buscar por redes sin filtro no garantiza colegiatura ni especialidad; la terapia online genérica no ofrece coordinación humana.

**Qué le cuesta:** tiempo sin resolver el motivo de consulta; **[I]** el abandono temprano (antes de la sesión 3) deja el proceso a medias.

**Tensión emocional** **[V]** (el sitio la nombra): *"no necesitas tener todo claro ni saber qué decir. Es normal sentir nervios o dudas"*; miedo a no conectar con la psicóloga; duda de que alguien más sepa lo que cuenta.

### De la operación **[V]** (documentado en `docs/auditoria-continuidad.md` y en `CLAUDE.md`)

- **Abandono en la sesión 3:** es el punto donde más procesos se cortan; el sistema lo detecta como `riesgo_s3` (llegó a la 3 y no tiene próxima cita).
- **Cierres de bloque sin decisión registrada:** en la auditoría del 9 sep 2026 solo **125 de 8 823 citas** tenían un código DP; la mayoría del histórico (380 de 391 alertas) venía de AgendaPro sin decisión.
- **Seguimiento fuera del sistema:** hasta ahora coordinación escribía por WhatsApp desde el celular; no quedaba quién contactó, cuándo ni qué respondió el paciente. (Resuelto en la rama de contactabilidad; ver §13.)
- **Adherencia del psicólogo al registro:** se resolvió con notas por voz (Whisper) — *"no pedirles que escriban"* (idea de Emma).
- **Leads que se trababan con el bot:** el mensaje de bienvenida solo pedía el número; se corrigió para responder preguntas frecuentes (corrección #3 de Gaby, ago 2026).

---

## 5. Competitive Landscape

**Regla para esta sección:** aquí solo va lo que se sostiene con información real del repo. No hay nombres de otros centros ni apps porque el código no los menciona y no se han investigado.

**Lo que sí se puede afirmar:**
- **[V]** Alternativa interna al sistema actual: el propio pasado de la clínica — **AgendaPro** (agenda y ficha; de ahí vienen el formato de ficha clínica y los paquetes) y un **Excel operativo por sede** ("LEADS LIMA-CONVER.xlsx", "LEADS PIURA - CONVERSEMOS.xlsx") con hojas de leads, atenciones, ingresos y seguimiento. **Medlink** se usó como referencia para el módulo de finanzas. Estos son referentes de producto, no competidores de la clínica.
- **[I]** Para el paciente, la alternativa más frecuente no es otro centro sino **no iniciar** o **abandonar**: el sistema entero de continuidad existe porque esa es la fuga principal.
- **[V]** La FAQ del sitio responde explícitamente a quien *"ya está en terapia pero no siente conexión con su psicóloga"*: la clínica compite con la opción de cambiar de profesional dentro del mismo centro en vez de irse.

**Pendiente de investigación con `customer-research`** **[P]**:
- Qué otros centros, consultorios independientes o plataformas de terapia online considera un lead en Lima y en Piura antes de escribir.
- Precios de referencia del mercado por segmento.
- Por qué los leads "perdidos" no iniciaron (hoy solo hay el estado `perdido` y notas libres; no hay motivo estructurado).
- Por qué los pacientes con DP-14 (limitación económica), DP-15 (horario) y DP-16 (inconformidad) dejaron el proceso, en sus palabras.

---

## 6. Differentiation

**Key differentiators** **[V]** (todos verificables en el sitio o el sistema):
- Dos sedes físicas (Lima y Piura) **y** online, con la misma agenda.
- La persona **elige a su psicólogo** desde la agenda pública (foto, enfoque, colegiatura C.Ps.P., modalidad y horarios), o coordinación le sugiere uno.
- Primera consulta corta (30–45 min) y de bajo costo, pensada para "conocer al psicólogo y elegir el mejor plan".
- Coordinación humana por WhatsApp: confirma la cita, envía el link de Zoom, reprograma; *"no pagas nada hasta que te confirmemos"*.
- Puede cambiar de profesional sin salir del centro.
- Confidencialidad declarada como obligación legal y garantía absoluta.

**How we do it differently** **[V]**: el sistema propio detecta a quién hay que llamar (riesgo S3, cierre de bloque) y deja rastro de cada contacto; el psicólogo registra una decisión clínica codificada (DP) en cada cierre.

**Why that's better** **[I]**: menos pacientes perdidos por olvido operativo; el paciente recibe un mensaje pertinente (no un spam genérico) desde el número de su sede y firmado por su coordinadora.

**Why customers choose us** **[P]**: no hay encuestas ni testimonios estructurados en el sistema. Existe NPS 0–10 por WhatsApp (`RespuestaNPS`), pero sus resultados no están en el repo.

---

## 7. Objections & Anti-personas

Las objeciones que **sí** se pueden citar son las que el propio sitio responde en sus preguntas frecuentes **[V]** (texto del equipo, en `frontend/src/App.jsx::agendaFaq`):

| Objeción (verbatim del sitio) | Cómo la responde el sitio |
|---|---|
| "¿Cuánto dura cada sesión y cuánto cuesta?" | Primera consulta de 30–45 min con inversión de S/ (precio del catálogo); "nuestra finalidad es que en este primer encuentro conozcas al psicólogo". |
| "¿Cuánto tiempo tendré que estar haciendo terapia?" | "Nos encantaría poder darte una respuesta, pero lo cierto es que esto varía dependiendo de cada persona." |
| "¿Cómo sé que la terapia online es para mí?" | "Permite recibir la misma atención psicológica que recibirías en un consultorio tradicional, pero de forma remota." |
| "¿Alguien más sabrá lo que yo le cuente a mi psicóloga?" | "No. Los psicólogos de Conversemos están obligados por ley a mantener el secreto profesional." |
| "Ya estoy en terapia pero no siento conexión con mi psicóloga" | Se puede cambiar de profesional. |
| "¿Puedo elegir a mi psicóloga?" | Sí, desde la agenda o con ayuda de atención al cliente. |
| "Una vez reservada mi sesión, ¿puedo cambiar el día y la hora?" | Sí, con el asesor de sesiones o directamente con el psicólogo. |
| "¿Con quién tengo que contactar ese día? ¿Me llaman o llamo yo?" | Si es virtual, recibe un link de Zoom; a la hora agendada el psicólogo lo espera en su sala. |

**Objeciones de continuidad (después de iniciar)** **[V]**: están codificadas como decisiones clínicas — **DP-14 Limitación económica**, **DP-15 Limitación de horario**, **DP-16 Inconformidad con la atención**, **DP-09 Suspende temporalmente / Finaliza**. Son las categorías reales de "por qué no sigue".

**Anti-personas** **[I]**: quien necesita atención psiquiátrica/farmacológica o de urgencia (el sistema registra **derivación externa DP-12** e **interconsulta DP-13** con psiquiatra, neurólogo, médico, etc., en la red de profesionales); **[P]** confirmar con Dirección Clínica qué casos no se atienden.

---

## 8. Switching Dynamics (JTBD, cuatro fuerzas)

Para el **paciente** **[I]** (**[P]** validar):
- **Push:** el malestar no mejora; una situación puntual (pareja, hijo, ansiedad — el sitio ofrece tests de ansiedad, dependencia emocional y depresión).
- **Pull:** elegir al psicólogo, primera consulta accesible, online si no puede ir, confidencialidad.
- **Hábito:** "aguantar"; buscar consejo en el entorno; en terapia, quedarse con un psicólogo con quien no conecta.
- **Ansiedad:** costo total desconocido, duración indefinida, "¿y si no me entiende?", que alguien se entere.

Para la **coordinadora** (al adoptar el sistema como CRM) **[I]**:
- **Push:** el Excel y el WhatsApp del celular no dejan rastro de quién contactó a quién.
- **Pull:** la cola le dice a quién llamar hoy y con qué mensaje; el historial queda solo.
- **Hábito:** escribir desde el celular personal, copiar y pegar.
- **Ansiedad:** que el sistema "cierre" casos solo o mande mensajes por su cuenta. **[V]** Por diseño no lo hace: enviar nunca marca "resuelto", y las líneas oficiales no responden automáticamente.

---

## 9. Customer Language

**Cómo describe el sitio el problema/servicio (verbatim)** **[V]**:
- "Hablamos de salud mental en un espacio seguro para sanar."
- "Conversemos es una plataforma dedicada a trabajar la salud mental de forma integral."
- "Tu psicólogo recomendará la frecuencia de las sesiones dependiendo de la complejidad de tus necesidades a trabajar (usualmente iniciamos con una o dos veces por semana)."
- "Algunos buscan trabajar sobre un tema puntual…" (sobre la duración).
- "Si tu sesión es virtual, el día de tu sesión te enviaremos un link de Zoom."

**Cómo habla el equipo por WhatsApp (verbatim de las plantillas del sistema)** **[V]**:
- Bot de captación: "Atendemos *terapia individual* (adultos), *niños y adolescentes*, *terapia de pareja*, *terapia familiar*, *terapia de lenguaje* y *evaluaciones psicológicas*, de forma presencial y online 🌿"
- "El costo depende del tipo de terapia y del profesional. Te lo confirmamos al coordinar tu cita, sin ningún compromiso 🤍"
- Continuidad: "Hola {nombre} 😊 Soy {coordinadora}, del equipo de Ítaca Conversemos. Queríamos saber cómo continúas con tu proceso psicológico y si deseas agendar tu próxima sesión. ¿Te gustaría que revisemos horarios disponibles?"
- Eli (acompañamiento): "Sabemos que no siempre es fácil buscar ayuda, y valoramos mucho que estés dando este paso." · "Este proceso se construye paso a paso." · "Tu espacio terapéutico sigue aquí cuando decidas retomarlo."

**Cómo describen los pacientes el problema (verbatim)** **[P]**: no hay transcripciones ni encuestas en el repo. Lo más cercano son las notas libres de `Lead.notas` y `Cita.notas`/`motivo_consulta` en producción (datos personales: solo consultarlos con permiso y sin exportarlos).

**Palabras que usa la clínica** **[V]**: consultante/paciente (ambos), psicólogo/a, sesión, proceso, consulta inicial, sede, presencial/online (el sistema dice "virtual"), coordinación, "espacio seguro", "a tu ritmo", "acompañarte". Tuteo peruano.

**Palabras a evitar** **[V]/[I]**: voseo argentino (regla del proyecto); vocabulario comercial hacia el paciente ("cliente", "venta", "cerrar", "oferta", "lead"); jerga clínica en mensajes de WhatsApp; nunca afirmar un alta, una derivación o un diagnóstico en un mensaje operativo (regla explícita de `core/notas_operativas.py`).

**Glosario del sistema** **[V]**:

| Término | Significado |
|---|---|
| Sede | Lima o Piura. Cada paciente, lead, psicólogo, coordinadora y línea de WhatsApp tiene una. |
| Consulta inicial | Primera cita (30–45 min). Termina con una decisión DP-01/02/03/04. |
| Sesión N (S1, S3, S6…) | Número de sesión dentro del proceso actual (`Cita.n_sesion`). |
| Bloque | Tramo de **6 sesiones**; al cerrar (S6, S12, S18…) toca registrar una decisión. |
| Riesgo S3 | Paciente que llegó a la sesión 3 y no tiene próxima cita agendada. |
| DP-01 … DP-16 | "Decisión del proceso", código clínico que el psicólogo registra en la cita: 01 inicia · 02 pide tiempo · 03 seguimiento posterior · 04 no inicia · 05 evaluación · 06 informe · 07 convenio/empresa · 08 continúa · 09 suspende/finaliza · 10 alta terapéutica · 11 derivación interna · 12 derivación externa · 13 interconsulta · 14 limitación económica · 15 limitación de horario · 16 inconformidad. |
| Proceso (P1, P2…) | Cada vez que un paciente reinicia terapia con respaldo estructurado, empieza un proceso nuevo; "P2 · S3" = tercera sesión del segundo proceso. |
| Frecuencia | Semanal · quincenal · esporádico · en pausa · alta (estas dos últimas sacan al paciente de la cola). |
| Cola / Centro de Continuidad | Lista priorizada de casos que piden acción, calculada siempre desde citas y decisiones. |
| Gestión del caso | Registro operativo de un caso: estado de revisión, resultado, responsable, observación, historial. |
| Línea | Número de WhatsApp de una sede en Evolution (instancia). |
| Instancia | Nombre técnico de la línea en Evolution (`conversemoslima`, `conversemospiura`; `vibery` = pruebas). |
| Eli | Bot de captación (línea aparte) que responde preguntas frecuentes a leads. |
| Bitácora | Registro de todos los mensajes de WhatsApp enviados y recibidos (`mensajes.Mensaje`). |

---

## 10. Brand Voice

**Tono** **[V]**: cálido, cercano, sin tecnicismos; tutea; emojis suaves y escasos (😊 🌿 🤍 📍 📅); frases cortas. Nunca presiona: "sin ningún compromiso", "a tu ritmo", "cuando decidas retomarlo".

**Estilo** **[V]**: directo y humano. Los mensajes los firma una persona ("Soy Yazmín, del equipo de Ítaca Conversemos"), no "el sistema".

**Personalidad** **[V]** (pilares institucionales, sembrados en el sistema): **Itactividad** — damos soluciones, no problemas · **+1 Sí importa** — cada acción cuenta, siempre la milla extra · **Muro de confianza** — somos directos, nos cuidamos y preguntamos siempre. *"No solo trabajamos con pacientes: cambiamos vidas."*

**Identidad visual** **[V]** (`docs/marca-exportables.md`, Manual de Identidad de Agencia Deb): celeste `#00B8D8` primario, `#D7F4FA` claro, gris `#6E6E6E`, negro `#343434`; Montserrat (Bold títulos, Regular cuerpo); Salsabila solo para el lema en redes; el manual **no** contempla semáforo rojo/verde en exportables. (La app interna usa otra paleta —verde salvia— definida en `CLAUDE.md`; no mezclar.)

---

## 11. Proof Points

**Métricas reales del sistema** **[V]** (importación histórica, jun 2026): 1 874 pacientes (779 Lima · 1 095 Piura) · 7 677 leads · 5 842 cobros por **S/ 903 113** · 2 833 atenciones registradas. Auditoría de continuidad (9 sep 2026): de 391 alertas, 32 pedían acción ese día; 303 pacientes llevaban más de 90 días sin sesión (lista de reactivación).

**Prueba de operación** **[V]**: 11 sep 2026 — envío real de un contacto de continuidad por Evolution desde la instancia de pruebas, con `external_message_id` devuelto por WhatsApp y registro completo en historial.

**Customers / logos:** No aplica (B2C). **[P]** Convenios con empresas: existen como fuente y como DP-07, sin detalle.

**Testimonios** **[P]**: no hay en el repo. Fuente disponible cuando se autorice: respuestas NPS por WhatsApp (`RespuestaNPS`, puntaje 0–10 + comentario) y la encuesta de satisfacción de Eli (Google Forms).

**Value themes** **[V]/[I]**:
| Tema | Prueba |
|---|---|
| Profesionales colegiados y con enfoque declarado | [V] 14 psicólogos con C.Ps.P. visible en la agenda pública |
| Accesible para empezar | [V] primera consulta 30–45 min; "no pagas nada hasta que te confirmemos" |
| Presencial y online, dos ciudades | [V] sedes en Miraflores y Piura + Zoom |
| Nadie se pierde en el camino | [V] cola de continuidad + contacto trazable por sede; [I] impacto en retención aún no medido |

---

## 12. Goals

**Business goal** **[V]**: cumplir la meta de facturación mensual por sede (mínima S/ 20 000 / ideal S/ 30 000 por defecto) sosteniendo la continuidad de los procesos.

**Conversion actions** **[V]** (en orden del embudo):
1. Lead responde y agenda consulta inicial (`Lead.Estado.AGENDADO`).
2. Consulta realizada con **DP-01 Inicia proceso** → paciente (`ganado`).
3. Paciente pasa la sesión 3 con próxima cita agendada (sale de riesgo S3).
4. Cierre de bloque con decisión registrada (DP-08 continúa / DP-10 alta…).

**Current metrics** **[V]** (lo que el sistema ya calcula; valores en producción):
- Gerencia por período: citas, atendidas, canceladas, % asistencia; leads, % pauta, cierres, tasa de cierre, mejor fuente/campaña; pacientes nuevos y sin próxima cita; ingresos/egresos/utilidad; demografía; retención (verde/amarillo/rojo); tendencia vs. período anterior.
- Métricas mensuales de marketing por sede: invertido en pauta, mensajes, citas nuevas, pacientes nuevos, leads → CAC, costo por lead, conversión, ratio mensaje→cita, ratio cita→paciente.
- Reporte semanal para el directorio: facturación por sede vs. meta y proyección, leads por sede, consultas agendadas, pacientes que iniciaron, videos publicados, pacientes activos, **retención S3+**, sin próxima sesión, ocupación de agenda.
- **[P]** Valores actuales y benchmarks (tasa de cierre real, % que pasa S3, NPS) no están en el repo: consultarlos en Gerencia.

---

## 13. Modelo operativo y de datos (lo que las skills deben respetar)

Esta sección es la referencia dura para `revops`, `churn-prevention`, `analytics` y `onboarding`. Todo **[V]** salvo marca contraria.

### 13.1 Ciclo de vida completo

```
CAPTACIÓN            Lead.Estado: nuevo → contactado → seguimiento | recontacto
                     → agendado → agendo_no_pago | agendo_espera_pago
                     → consulta_realizada | no_realizada → evaluando | pendiente_pago
                     → ganado (inició proceso)  |  perdido
                                   │
CONSULTA INICIAL     Cita con decisión DP-01 (inicia) · DP-02 (pide tiempo) · DP-03 (seguimiento) · DP-04 (no inicia)
                                   │  convertir_lead_en_paciente → Paciente (sede, profesional, teléfono, fuente)
PROCESO              S1 S2 S3 S4 S5 S6 | S7 … S12 | …     (bloques de 6; SESION_RIESGO_ABANDONO = 3)
                          ▲ riesgo_s3 si no hay próxima cita
                                           ▲ cierre de bloque: decisión DP-08 continúa · DP-09 suspende/finaliza
                                             · DP-10 alta · DP-11/12 derivación · DP-13 interconsulta
                                             · DP-14 económica · DP-15 horario · DP-16 inconformidad
FRECUENCIA           semanal · quincenal · esporadico · en_pausa · alta  (en_pausa y alta = fuera de la cola)
REINICIO             nuevo proceso (P2, P3…) solo con respaldo estructurado (nueva sesión = 1, DP de cierre previo,
                     consulta o DP-01/02/03 entre medias, cambio de etapa, lead convertido)
```

### 13.2 Umbrales y SLAs que ya están en el código

| Regla | Valor | Dónde |
|---|---|---|
| Semáforo de lead sin contactar | amarillo ≥ 1 día · naranja ≥ 3 · rojo ≥ 5 | `leads/serializers.py::get_semaforo` |
| Bandeja "Solicitudes por WhatsApp" | leads por chat, estado nuevo, sin seguimiento, últimos **30 días** (`DIAS_BANDEJA`) | `leads/whatsapp_auto.py` |
| Respuesta automática del bot (solo línea de captación) | máximo una por lead cada **12 h** (`VENTANA_RESPUESTA_HORAS`) | idem |
| Anti-duplicado de leads por teléfono | lead abierto en 30 días (web) / 60 días (WhatsApp) | `leads/captacion.py` |
| Riesgo de abandono | sesión **3** sin próxima cita | `core/continuidad.py` |
| Bloque | **6** sesiones (`BLOQUE_POR_DEFECTO`), o `Paciente.sesiones_proceso` si está fijado | idem |
| Cierre "próximo" | próxima cita dentro de **7 días** (`DIAS_PROXIMOS`) | idem |
| Backlog (calidad, no acción) | cierre hace más de **90 días** (`DIAS_BACKLOG`) | idem |
| Reinicio por tiempo | 60 días solo refuerza una bajada a S1/S2; nunca decide solo | idem |
| Retención (Gerencia) | días desde la última atención: verde < 8 · amarillo 8–15 · rojo > 15 (regla de la hoja SEG de la clínica) | `core/gerencia.py` |
| NPS por WhatsApp | se acepta la respuesta si empieza con 0–10 y hay encuesta pendiente de ≤ 7 días | `core/whatsapp_cloud.py` |
| Reenvío de contacto de continuidad | pide confirmación si el mismo caso se contactó hace < **24 h** | `core/contacto_continuidad.py` |
| Recordatorios automáticos | comando `enviar_recordatorios` para las citas del día (requiere tarea programada; **[P]** hoy no está programada en producción) | `pacientes/recordatorios.py` |

**[P]** No hay un SLA acordado de "tiempo máximo para responder un lead": el semáforo es informativo (verde hasta 1 día). `revops` puede proponer uno, pero debe presentarlo como propuesta.

### 13.3 Cola del Centro de Continuidad (estados)

| Grupo | Estado | Condición | ¿Pide acción hoy? |
|---|---|---|---|
| Acción | `vencido` | cerró un bloque (≤ 90 días) y no hay decisión | sí |
| Acción | `hoy` | cierra hoy sin decisión | sí |
| Acción | `riesgo_s3` | S3 sin próxima cita | sí |
| Acción | `sin_agendar` | a una sesión de cerrar y sin próxima cita | sí |
| Seguimiento | `proximo` | cierra en ≤ 7 días, ya agendado | no (preparar) |
| Calidad | `continuo_sin_decision` | pasó un cierre y siguió viniendo | no (registro) |
| Calidad | `dato_incompleto` | número de sesión inferido, no registrado | no |
| Calidad | `backlog` | cierre hace > 90 días (99 % heredado) | no |
| Calidad | `proceso_anterior` | un proceso previo terminó sin DP | no |

Alcance por rol (`pacientes_del_rol`): psicólogo → solo sus pacientes; coordinación → solo su sede (**[V]** un paciente sin sede no lo ve ninguna coordinadora, solo gerencia); admin y analista → ambas sedes.

### 13.4 Gestión del caso (el "CRM")

- **Estado de revisión:** sin revisar · en seguimiento · resuelto.
- **Resultado operativo:** pendiente real · ya actualizado · requiere corrección · requiere confirmar · **paciente desea continuar · pausa temporal · no continuará (cierre administrativo) · contactado, sin respuesta**.
- **Responsable:** coordinación · psicólogo · Dirección Clínica · sistema/soporte.
- **Historial** append-only de cada cambio (quién, cuándo, qué), incluidos: WhatsApp enviado, WhatsApp no se pudo enviar, respuesta del paciente, contacto bloqueado, mensaje copiado para envío manual.
- **Regla de oro:** marcar "resuelto" **no** apaga la condición; si la cola la sigue detectando, aparece la alerta *"Gestión marcada como resuelta, pero la condición detectada sigue pendiente"*. La condición solo desaparece cuando la Agenda cambia (próxima cita, DP registrado, frecuencia en pausa/alta), y entonces el sistema cierra la gestión solo y deja historial. Una resolución manual nunca la pisa el sistema.
- **Quién escribe:** gestionar → admin, coordinación, psicólogo, analista. **Contactar por WhatsApp** → solo admin y coordinación.

### 13.5 WhatsApp (canal operativo)

- **Proveedor:** Evolution API v2.3.7 (self-hosted en EasyPanel). Meta Cloud API existe como primera opción si hubiera un número configurado (`NumeroWhatsapp`); hoy no interviene en continuidad.
- **Una línea por sede** (`InstanciaEvolution`): `conversemoslima` (responsable Ayvi) y `conversemospiura` (Yazmín). Estado real al 11 sep 2026: **registradas pero desconectadas** (`close`); `vibery` conectada y marcada como **ambiente de pruebas** (nunca se elige para escribirle a un paciente). Credenciales del servidor en Railway. **[P]** Fecha de conexión de las líneas oficiales (requiere escanear QR) y configuración del webhook: pendientes, son decisión de gerencia.
- **Reglas de envío:** el paciente sin sede no se contacta (queda incidencia); una línea de otra sede nunca se usa; sin línea conectada no se envía y se ofrece copiar el mensaje (queda registrado como envío manual); las líneas oficiales **no responden automáticamente** (ni FAQ ni IA). El bot Eli vive en una línea aparte, solo para captación.
- **Trazabilidad:** cada mensaje guarda proveedor, dirección (entrante/saliente), sede, instancia, id externo de WhatsApp, estado (enviado → entregado → leído; fallido), plantilla usada, texto original si se editó, quién y cuándo. Deduplicación por id externo en base de datos.
- **Plantillas** (editables por gerencia/coordinación en la app; variables `{nombre} {coordinadora} {sede} {clinica} {psicologo} {n_sesion} {fecha} {hora}`): recordatorio, confirmación, pago, ubicación, políticas, consentimiento, NPS, cumpleaños; Eli (recontacto, cita confirmada, bienvenida, pre-sesión, post S1, seguimiento, encuesta, post-alta, ausencia); continuidad (sin próxima cita, riesgo S3, pre-cierre, retomar proceso anterior, confirmación general).
- **Respuesta del paciente:** la clasifica una persona (🟢 continúa · 🕒 más adelante · ❌ no continuará · ⏳ sin respuesta). El sistema **no** interpreta texto de pacientes.
- **Respaldo manual:** en recordatorios y NPS, si no hay línea, se abre `wa.me`; en continuidad, no (solo copiar).

### 13.6 Onboarding real del paciente (paso a paso)

1. Llega por una fuente (Instagram/Facebook/TikTok orgánico o ads, WhatsApp directo, bot, web, referido por paciente o psicólogo, convenio/alianza, Google, LinkedIn) → `Lead` en bandeja.
2. Coordinación (o el bot, si es la línea de captación) responde; agenda consulta inicial — desde el sitio `/agendar/<token>` la persona elige sede, psicólogo y horario y deja nombre y teléfono; "coordinación te escribe para confirmar; no pagas nada hasta que te confirmemos".
3. Recordatorio de cita por WhatsApp; si es virtual, link de Zoom el día de la sesión.
4. Consulta inicial (30–45 min) → el psicólogo registra DP-01/02/03/04.
5. Con DP-01: conversión a paciente; consentimiento informado (aceptación pública por token); frecuencia recomendada "usualmente una o dos veces por semana".
6. S1 … S3 (punto crítico) … S6 (cierre de bloque con decisión).

**[P]** Tiempo mediano lead → consulta y lead → DP-01 no está calculado; hay fechas para hacerlo (`Lead.creado_en`, `ultimo_contacto`, `fecha_consulta`, `fecha_cierre`, `Cita.decision_registrada_en`).

### 13.7 Fuentes de datos para `analytics`

| Endpoint / comando | Qué da |
|---|---|
| `GET /api/hoy/` | citas del día, leads nuevos, sin próxima cita, ingresos del día (admin), continuidad (resumen + 5 prioritarios) |
| `GET /api/gerencia/resumen/?periodo=hoy|7d|semana|30d|mes&sede=` | operación, captación, pacientes, productividad por psicólogo, dinero, demografía, retención, tendencia, por día |
| `GET /api/continuidad/pendientes/?estado&sede&medico&bloque&revision` | la cola completa + indicadores de calidad |
| `GET /api/continuidad/caso/<id>/` | detalle del caso, gestión, historial, contacto |
| `GET /api/metricas/` | métricas mensuales de marketing por sede (CAC, costo por lead, conversión…) |
| `GET /api/reportes-semanales/` | reporte semanal para el directorio |
| `GET /api/finanzas/caja/` · `/api/finanzas/liquidacion/` | caja y liquidación de psicólogos |
| `GET /api/ocupacion/` | ocupación de agenda |
| `GET /api/mensajes/` | bitácora de WhatsApp (no visible para analista) |
| `GET /api/evolution/instancias/` · `/estado/` | estado de las líneas (solo admin) |
| Exportables (Excel, PDF, Word, PPT) | `frontend/src/exportGerencia.js` con la identidad de marca |

### 13.8 Lo que NO existe (para que ninguna skill lo asuma)

- No hay suscripción, plan mensual, trial, cancelación ni pagos recurrentes → no aplica *dunning* ni *cancel flow*.
- No hay puntaje numérico de leads (scoring): la prioridad es el semáforo por días y la bandeja "pide cita".
- No hay CRM externo (HubSpot, etc.), ni GA4/GTM, ni pixel configurado en el repo; **[P]** el equipo lleva Meta Ads por fuera y registra lo invertido a mano en métricas mensuales.
- No hay motivo estructurado de "lead perdido" ni encuesta de salida.
- No hay respuestas automáticas con IA hacia pacientes; la única automatización de texto es el bot de captación con FAQ fijas.
- No hay deal desk, cotizaciones ni descuentos codificados (existen paquetes prepagados).
- Las decisiones DP **no** actualizan automáticamente la frecuencia del paciente (p. ej. DP-10 alta → frecuencia "alta"); **[P]** decisión abierta de Dirección Clínica.
- Sin tests automatizados de frontend; backend con ~376 tests (suite completa pendiente de re-ejecutar en la rama actual).

### 13.9 Decisiones abiertas del negocio (no de código) **[P]**

- Qué hacer con el backlog heredado de AgendaPro (277 casos): cerrarlo con un código "histórico — no aplica", archivarlo o dejarlo visible.
- Si "continuó sin decisión" debe generar tarea para coordinación o solo quedar como calidad de registro.
- Si algún DP debe actualizar `Paciente.frecuencia` automáticamente.
- Cuándo conectar las líneas oficiales de Lima y Piura y activar el webhook.
- SLA de respuesta a leads y a casos de continuidad.
- Precios vigentes por servicio/psicólogo y política de paquetes.

---

## Changelog
*Newest first. One line per revision: what changed and why.*
- v1 (2026-09-11) — Contexto inicial redactado desde el código, los datos de producción y la documentación del repo; vocabulario SaaS traducido al funcionamiento real de Conversemos; competencia limitada a lo verificable y marcada como pendiente de `customer-research`.
