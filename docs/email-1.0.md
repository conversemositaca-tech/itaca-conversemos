# Email 1.0 — Arquitectura

Infraestructura de correo de Ítaca Conversemos. WhatsApp sigue siendo el canal
principal; el correo complementa. Email 1.0 activa solo dos flujos:

1. **Confirmación de reserva web** (SERVICE).
2. **Secuencia DP-02** a los días 1, 7 y 21 (MARKETING).

Todo vive en la app `correo/`. Las tres banderas vienen apagadas: desplegar no
envía nada (ver [operación](email-1.0-operacion.md)).

## Principios

- **Django decide, Brevo entrega.** Brevo no es CRM ni fuente de verdad. No se
  sincronizan pacientes, leads, listas ni segmentos. No se usa la API de
  contactos. Cada correo se envía individualmente por `POST /v3/smtp/email`.
- **Nada clínico sale.** El payload lleva solo remitente, destinatario,
  responder-a, asunto, cuerpo y la etiqueta opaca `correo:<uuid>`. Un
  armado con claves como `motivo`, `decision`, `riesgo` o `nps` falla antes
  de enviar (`render.CLAVES_PROHIBIDAS`).
- **El consentimiento es un historial.** Cada otorgamiento o revocación es una
  fila nueva; el estado vigente es el último evento.
- **La elegibilidad se evalúa al enviar**, no al programar.
- **La base histórica no recibe nada comercial.** No se migró ningún
  consentimiento; solo cuenta uno nuevo, explícito y demostrable.

## Flujo de un envío

```text
disparador (señal post-commit) ─► programar (idempotente) ─► procesar
                                                            │
  plantilla vigente ◄─ destinatario ◄─ elegibilidad ◄───────┘
        │
        ▼
  bitácora (CorreoEnviado) ─► armar HTML/texto ─► Brevo ─► ENVIADO / ERROR
                                                             │
  webhook de Brevo ─► EventoCorreoProveedor ─► estado + bloqueos de la persona
```

`correo.services.envio.enviar_correo` es la única puerta de salida.

## Modelos (`correo/models.py`)

| Modelo | Qué guarda |
| --- | --- |
| `ConsentimientoComunicacion` | Historial append-only: finalidad (MARKETING/ASISTENCIAL), estado (OTORGADO/REVOCADO), origen, versión y texto aceptado, correo, fecha, IP, user agent, quién lo registró, evento previo. |
| `PreferenciaCorreo` | Token público UUID v4 y bloqueos: comerciales, rebote duro, spam. |
| `PlantillaCorreo` | Texto versionado por `(clave, version)`. Una versión ya enviada no se reescribe. |
| `CorreoEnviado` | Bitácora: plantilla, categoría, dirección, asunto, estado, message-id de Brevo, error. Sin HTML ni contexto. |
| `EventoCorreoProveedor` | Avisos del webhook normalizados y deduplicados. Sin payload. |
| `EnvioProgramadoCorreo` | Envíos futuros con clave de idempotencia única, intentos y estado. |

**Identidad.** Cada fila apunta a exactamente una de: `paciente`, `lead` o
`autorizacion` (apoderado de Faro), con restricciones en la base. El tutor de
un menor se expresa como `paciente` + `es_tutor=True`.

**Una persona, varias filas.** Un paciente y los leads que se le convirtieron
son la misma persona: el permiso dado al reservar (en el lead) vale cuando
luego se le escribe como paciente, y una baja en cualquiera bloquea a todos.

## Categorías y elegibilidad (`services/elegibilidad.py`)

| Categoría | Requiere | Bloquea |
| --- | --- | --- |
| SERVICE | Nada comercial | Sin correo, menor sin tutor, rebote duro, spam |
| CARE (preparado, sin flujos) | ASISTENCIAL otorgado | Lo de SERVICE + exclusiones clínicas |
| MARKETING | MARKETING otorgado y vigente | Lo de SERVICE + baja/revocación + exclusiones clínicas |

Exclusiones clínicas: última respuesta NPS de 0 a 6, alguna DP-16, alta o
pausa (por frecuencia o última decisión DP-10/DP-09), riesgo moderado o alto.
Se registran solo como `EXCLUSION_SEGURIDAD`.

Códigos: `OK`, `SIN_CORREO`, `MENOR_SIN_TUTOR`, `SIN_CONSENTIMIENTO`, `BAJA`,
`REBOTE_DURO`, `SPAM`, `EXCLUSION_SEGURIDAD`, `PLANTILLA_INACTIVA`,
`DESTINATARIO_INVALIDO`.

**Menores de 14.** Nunca reciben directo: el correo va a `tutor_correo` de la
ficha. Sin tutor con correo, `MENOR_SIN_TUTOR`. MARKETING exige el
consentimiento del tutor. La edad sale de la fecha de nacimiento; sin ella se
asume adulto.

## Captura del consentimiento

Casilla opcional, desmarcada, separada de cualquier otra aceptación, con el
texto de la versión `EMAIL-MKT-2026-01`:

> Quiero recibir por correo contenidos, novedades, talleres y comunicaciones
> de Ítaca Conversemos. Puedo retirar mi consentimiento en cualquier momento.

| Dónde | Origen | Queda a nombre de |
| --- | --- | --- |
| Reserva web | `RESERVA_WEB` | El lead de la reserva |
| "Ayúdenme a elegir" | `AYUDA_ELEGIR` | El lead |
| Autorización de Faro | `AUTORIZACION_FARO` | El apoderado |
| Consentimiento informado | `CONSENTIMIENTO_INFORMADO` | El paciente, o su tutor si es menor de 14 |
| Ficha del paciente | `PANEL_WHATSAPP` / `PANEL_PRESENCIAL` | Paciente o tutor, con confirmación explícita |

Si marca la casilla sin correo, no se registra nada y el formulario avisa. El
correo sigue siendo opcional en la reserva.

## Flujos

**Confirmación de reserva** (`flujos/reserva.py`). Sale cuando la cita web
queda agendada o confirmada: al reservar si ya era paciente; si es una persona
nueva, cuando coordinación confirma la cita. Va a quien reservó. Una vez por
cita.

**DP-02** (`flujos/dp02.py`). Al registrar una DP-02 en la Agenda se programan
tres correos desde la fecha de registro. Solo DP-02 de las últimas 48 horas.
Se cancelan si después hay otra decisión distinta de DP-03, otra cita
reservada, la DP-02 cambia o el lead pasa a "inició proceso".

## Webhook, preferencias y baja

- `POST /api/correo/webhooks/brevo/` con `Authorization: Bearer`. Correlaciona
  por message-id y luego por la etiqueta; nunca por dirección. Rebote duro
  bloquea; rebote suave no; bloqueado no se convierte en rebote duro; baja y
  spam revocan MARKETING; el clic guarda URL y fecha sin puntaje.
- `/preferencias/correo/<uuid>/`: correo enmascarado y la casilla.
- `POST /api/correo/baja/<token>/`: RFC 8058, sin confirmación, idempotente,
  200 aunque ya estuviera de baja. Los correos MARKETING llevan
  `List-Unsubscribe` y `List-Unsubscribe-Post`. El enlace del pie abre la
  página con `?baja=1`, que da de baja por JavaScript para que los escáneres de
  enlaces no lo disparen.

## Panel interno

En la ficha del paciente, sección "Correo", solo para gerencia y coordinación:
estado del consentimiento comercial, último cambio y origen, rebote duro,
spam, comerciales bloqueados, bitácora y las acciones registrar, revocar y
abrir preferencias. Psicólogo y Dirección Clínica no ven nada de esto, como
ya no veían el contacto.

## Diseño de los correos

`correo/templates/correo/base.html`, según el manual de marca:

- Logo oficial horizontal (`frontend/public/itaca-logo-h.png`) a 200 px; el
  manual pide mínimo 170 px. Sin redibujarlo ni alterarlo.
- Paleta oficial: `#00B8D8`, `#D7F4FA`, `#6E6E6E`, `#343434`, `#FFFFFF`.
- Montserrat con respaldo `Arial, Helvetica, sans-serif`.
- Tablas, CSS en línea, contenedor fluido hasta 600 px y tabla fija solo para
  Outlook. Preencabezado oculto y versión de texto plano.

## Decisiones y adaptaciones respecto de la especificación

| Especificación | Implementación | Por qué |
| --- | --- | --- |
| Modelo `TutorPaciente` | `Paciente.tutor_correo` + `es_tutor` en las filas | El tutor ya vivía en la ficha; la regla era no duplicar. La ficha admite un solo tutor, que es el responsable. |
| Identidad paciente/lead/tutor | Paciente, lead o autorización de Faro | El apoderado de Faro no es paciente ni lead. |
| `EnvioProgramadoCorreo.plantilla` (FK) | `plantilla_clave` | Al enviar se usa la versión activa de ese momento. |
| `PreferenciaCorreo` única por persona | Sin restricción única | La fusión de fichas se bloquea ante restricciones únicas sobre `paciente`; se suman las filas. |
| Reserva: correo al crear la reserva | Al quedar la cita agendada/confirmada | Una cita de persona nueva queda "pendiente"; "Tu reserva quedó confirmada" no sería verdad. |
| Virtual: `Acceso: {enlace}` | Si aún no hay enlace: "te enviaremos el enlace antes de la cita" | La reserva web no tiene enlace todavía. |
| Reintento de timeouts | Solo el de conexión | En un timeout de respuesta Brevo pudo haberlo enviado; reintentar lo duplicaría. |
| Baja desde el pie | Página con `?baja=1` | Un GET al endpoint lo dispararían los escáneres de enlaces. |
