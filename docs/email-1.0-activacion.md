# Email 1.0 — Checklist de activación

Orden exacto para pasar de "código desplegado y apagado" a "correos saliendo".
Cada paso dice cómo comprobarlo. No saltar pasos: varios dependen del anterior.

Estado de partida (1 oct 2026): código en `main`, banderas apagadas, ninguna
variable de Brevo en Railway, casillas de consentimiento ya en vivo.

## 0. Requisitos de código

- [ ] PR #138 mergeado (la dirección `.up.railway.app` siempre permitida).
- [ ] PR de cierre técnico de Email 1.0 mergeado (rebote por dirección,
      reserva fuera de la petición, envíos atascados, paneles de lead y Faro,
      logo en `/static/`, envío bloqueado sin dirección pública).
- **Comprobar:** GitHub Actions en verde en `main`.

## 1. Dominios de la web (Soto + Railway)

- [ ] Soto creó los CNAME y TXT de `www.` y `sistema.conversemos.itaca.com.pe`.
- [ ] Railway muestra los dos dominios en verde.
- [ ] Variables en Railway: `SITIO_DOMINIO`, `SISTEMA_DOMINIO`,
      `SITIO_URL_PUBLICA=https://www.conversemos.itaca.com.pe`.
- **Comprobar:** `https://www.conversemos.itaca.com.pe/static/itaca-logo-h.png`
  abre la imagen del logo (no una página).

## 2. Brevo

- [ ] Cuenta con teléfono verificado.
- [ ] Dominio `conversemos.itaca.com.pe` autenticado: registros de
      [email-1.0-dns.md](email-1.0-dns.md) creados por Soto y en verde en Brevo.
- [ ] Remitente `hola@conversemos.itaca.com.pe`, nombre "Equipo Conversemos".
- [ ] Clave de API creada y pegada **solo** en Railway como `BREVO_API_KEY`.
- [ ] En Brevo, seguimiento de aperturas desactivado (no se usa) y seguimiento
      de clics a criterio (si se activa, Brevo reescribe los enlaces).

## 3. Variables de correo en Railway (banderas todavía en 0)

```text
BREVO_API_KEY=<de Brevo>
BREVO_WEBHOOK_TOKEN=<cadena larga aleatoria>
CORREO_BASE_URL_PUBLICA=https://www.conversemos.itaca.com.pe
CORREO_HABILITADO=0
CORREO_RESERVA_HABILITADO=0
CORREO_DP02_HABILITADO=0
```

- **Importante:** sin `CORREO_BASE_URL_PUBLICA` (o `SITIO_URL_PUBLICA`) el
  sistema se niega a enviar (`SIN_URL_PUBLICA`): el logo y la baja saldrían
  rotos.

## 4. Webhook y cron

- [ ] Brevo → Transactional → Webhooks: URL
      `https://www.conversemos.itaca.com.pe/api/correo/webhooks/brevo/`,
      autenticación Bearer = `BREVO_WEBHOOK_TOKEN`, eventos delivered, hard
      bounce, soft bounce, blocked, click, unsubscribed, spam, error.
- [ ] Cron externo cada 5 minutos:
      `POST /api/correo/tareas/procesar-pendientes/` con
      `X-Integracion-Token: $ITACA_INTEGRACION_TOKEN`.
- **Comprobar:** el cron recibe `{"apagado": true}` (todavía apagado).

## 5. Prueba de humo: confirmación de reserva

- [ ] `CORREO_HABILITADO=1` y `CORREO_RESERVA_HABILITADO=1`.
- [ ] Reservar desde la web con un correo propio y un psicólogo con horario,
      como paciente ya conocido (o confirmar la cita desde la Agenda).
- **Comprobar, en este orden:**
  1. A los pocos minutos llega "Tu reserva está confirmada".
  2. La ficha → Correo → bitácora dice Enviado y luego Entregado (webhook).
  3. En Gmail, "Mostrar original": SPF, DKIM y DMARC = PASS.
  4. El logo se ve; el pie muestra las direcciones de las sedes.

## 6. QA de clientes de correo (manual)

Enviar la reserva de prueba a cuentas propias y revisar:

| Cliente | Qué mirar |
| --- | --- |
| Gmail web | Logo, caja celeste, sin "[Mensaje recortado]" |
| Gmail app (Android/iPhone) | Ancho completo, sin scroll horizontal |
| Outlook escritorio (Windows) | Tabla de 600 px, botón y caja con su color |
| Outlook web / Hotmail | Logo y pie |
| Apple Mail (iPhone) | Modo oscuro legible |

## 7. Datos legales (antes de cualquier MARKETING)

- [ ] `CORREO_RAZON_SOCIAL`, `CORREO_DOMICILIO_LEGAL`, `CORREO_CANAL_ARCO`,
      `CORREO_URL_PRIVACIDAD` en Railway.
- [ ] Aprobación legal de la casilla y de los textos DP-02.
- **Comprobar:** el pie de un DP-02 de prueba ya no muestra corchetes.

## 8. Encender DP-02

- [ ] `CORREO_DP02_HABILITADO=1`.
- [ ] Prueba controlada: una persona de prueba con consentimiento, registrar
      DP-02 en la Agenda y verificar en el admin de Django (Envíos programados)
      los tres envíos a 1, 7 y 21 días.
- [ ] Probar la baja de un clic desde el correo del día 1: la persona queda
      "Revocado" en su ficha y no recibe el del día 7.

## Apagar

`CORREO_HABILITADO=0` detiene todo al instante. Ver
[email-1.0-operacion.md](email-1.0-operacion.md).
