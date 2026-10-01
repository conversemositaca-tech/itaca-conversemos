# Email 1.0 — DNS del dominio de envío

Objetivo: que Brevo envíe como `hola@conversemos.itaca.com.pe` con SPF, DKIM y
DMARC alineados, **sin tocar el correo que ya usa el equipo**.

El envío se separa en el subdominio `mail.conversemos.itaca.com.pe`. El correo
del equipo y el dominio raíz no cambian.

## Antes de empezar

- Entrar al panel DNS del dominio (Cloudflare u otro).
- Exportar o fotografiar los registros actuales. Sirve para volver atrás.
- Crear la cuenta de Brevo y agregar el dominio en Senders, Domains & Dedicated
  IPs → Domains.

## 1. Verificación del dominio y DKIM

Brevo genera los valores reales de la cuenta: un TXT de verificación
(`brevo-code:…`) y uno o dos registros DKIM (CNAME o TXT).

**No inventar ni copiar valores de ejemplo.** Copiarlos literalmente desde la
pantalla de Brevo, con el host exacto que indique.

## 2. SPF

- No crear un segundo registro SPF: un host solo puede tener uno.
- Si Brevo pide SPF para `mail.conversemos.itaca.com.pe`, usar el valor exacto
  que muestre la cuenta.
- No tocar el SPF del dominio raíz. Si algún día hubiera que agregar Brevo
  ahí, se suma su `include` al registro existente, nunca se reemplaza.

## 3. DMARC

| Campo | Valor |
| --- | --- |
| Tipo | TXT |
| Host | `_dmarc.mail.conversemos.itaca.com.pe` |
| Valor | `v=DMARC1; p=none; rua=mailto:rua@dmarc.brevo.com` |

`p=none` solo observa: no rechaza ni manda a spam. **No avanzar a
`quarantine` ni `reject`** en Email 1.0.

Si el dominio raíz ya tiene un DMARC propio, no se toca.

## 4. Verificar

1. En Brevo, pulsar "Verify" hasta que todo quede en verde.
2. Comprobar desde una terminal:

```bash
nslookup -type=TXT _dmarc.mail.conversemos.itaca.com.pe
nslookup -type=TXT mail.conversemos.itaca.com.pe
```

3. Enviar la reserva de prueba a una cuenta Gmail. En Gmail, "Mostrar
   original" debe decir SPF, DKIM y DMARC: PASS.

## Volver atrás

Borrar solo los registros creados en estos pasos. No se tocó nada del dominio
raíz ni del correo del equipo.
