# Email 1.0 — Operación

Cómo se enciende, se vigila y se apaga. Nada de esto requiere tocar código.

## Variables de entorno (Railway)

| Variable | Valor | Obligatoria para enviar |
| --- | --- | --- |
| `BREVO_API_KEY` | Clave de API de Brevo (SMTP & API → API keys) | Sí |
| `BREVO_WEBHOOK_TOKEN` | Cadena larga aleatoria; la misma va en el webhook de Brevo | Sí, para recibir avisos |
| `BREVO_REMITENTE_NOMBRE` | `Equipo Conversemos` (por defecto) | No |
| `BREVO_REMITENTE_EMAIL` | `hola@conversemos.itaca.com.pe` (por defecto) | No |
| `BREVO_REPLY_TO` | `conversemos.itaca@gmail.com` (por defecto) | No |
| `BREVO_API_BASE_URL` | `https://api.brevo.com/v3` (por defecto) | No |
| `CORREO_BASE_URL_PUBLICA` | `https://conversemos.itaca.com.pe` (o el dominio de Railway) | Sí: logo, preferencias y baja |
| `ITACA_INTEGRACION_TOKEN` | Ya existe (recordatorios de WhatsApp); lo usa la tarea programada | Sí |
| `CORREO_RAZON_SOCIAL` | Razón social exacta | Sí, antes de MARKETING |
| `CORREO_DOMICILIO_LEGAL` | Domicilio legal | Sí, antes de MARKETING |
| `CORREO_CANAL_ARCO` | Canal oficial ARCO | Sí, antes de MARKETING |
| `CORREO_URL_PRIVACIDAD` | URL de la política de privacidad | Recomendada |
| `CORREO_HABILITADO` | `0` por defecto | Interruptor general |
| `CORREO_RESERVA_HABILITADO` | `0` por defecto | Confirmación de reserva |
| `CORREO_DP02_HABILITADO` | `0` por defecto | Secuencia DP-02 |

Mientras falten los tres datos legales, el pie de MARKETING muestra
`[RAZÓN SOCIAL]`, `[DOMICILIO]` y `[CANAL ARCO]`. **No encender DP-02 con
marcadores.**

## Tarea programada

Cada 15 minutos, desde el mismo cron externo que dispara los recordatorios de
WhatsApp:

```bash
curl -X POST https://<dominio>/api/correo/tareas/procesar-pendientes/ \
  -H "X-Integracion-Token: $ITACA_INTEGRACION_TOKEN"
```

Responde un resumen: `tomados`, `enviados`, `cancelados`, `reintento`, `error`.
Con `CORREO_HABILITADO` apagado responde `{"apagado": true}` sin tocar nada.
Lote máximo de 100. Dos ejecuciones paralelas nunca toman el mismo envío.

## Webhook de Brevo

En Brevo → Transactional → Settings → Webhooks:

- URL: `https://<dominio>/api/correo/webhooks/brevo/`
- Autenticación: Bearer token = `BREVO_WEBHOOK_TOKEN`
- Eventos: delivered, hard bounce, soft bounce, blocked, click,
  unsubscribed, spam, error.

## Orden de encendido

1. Mergear los PR en orden (1 → 7). Las migraciones son aditivas.
2. Configurar DNS ([email-1.0-dns.md](email-1.0-dns.md)) y verificar el
   dominio en Brevo.
3. Cargar las variables de entorno con las banderas en `0`.
4. Configurar el webhook y el cron.
5. Prueba de humo: `CORREO_HABILITADO=1` y `CORREO_RESERVA_HABILITADO=1`.
   Hacer una reserva de prueba con un correo propio y revisar la bitácora en
   la ficha.
6. Cargar los datos legales. Recién entonces `CORREO_DP02_HABILITADO=1`.

## Vigilancia

- **Ficha del paciente → Correo → Ver bitácora**: cada correo con estado y
  último evento.
- **Admin de Django → Correo**: bitácora, eventos, envíos programados y
  consentimientos (solo lectura).
- Envíos programados en `ERROR`: revisar `error_detalle`. `ESTADO_INCIERTO` e
  `INESPERADO` significan que no se sabe si salió; no se reenvían solos.
- Un `ENVIANDO` que no avanza indica que el proceso se cortó en pleno envío:
  revisar en Brevo (Logs) si salió antes de hacer nada.

## Solución de problemas

| Síntoma | Causa probable |
| --- | --- |
| La bitácora dice `SIN_CORREO` | La reserva o la ficha no tienen correo. |
| `MENOR_SIN_TUTOR` | Ficha con fecha de nacimiento de menor de 14 y sin correo del tutor. |
| `SIN_CONSENTIMIENTO` en DP-02 | Nunca marcó la casilla ni se registró en la ficha. Es lo esperado. |
| `EXCLUSION_SEGURIDAD` | Hay un motivo de cuidado (NPS, DP-16, alta, pausa, riesgo). No se muestra cuál, a propósito. |
| `SIN_CONFIGURAR` | Falta `BREVO_API_KEY`. |
| `HTTP_401` | Clave de Brevo inválida. |
| El webhook responde 401 | `BREVO_WEBHOOK_TOKEN` no coincide con el de Brevo. |
| El logo no aparece | `CORREO_BASE_URL_PUBLICA` vacía o mal escrita. |

## Apagar y volver atrás

- **Detener todo envío al instante:** `CORREO_HABILITADO=0`. Lo programado
  queda pendiente; al volver a encender, lo vencido se re-evalúa antes de
  salir.
- **Apagar un flujo:** su bandera en `0`. Lo pendiente de ese flujo se
  cancela al llegar su hora.
- **Revertir código:** revertir los merge en orden inverso. Las migraciones
  solo agregan tablas y el campo `tutor_correo`; se pueden dejar aplicadas.
