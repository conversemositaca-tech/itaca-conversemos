# Email 1.0 — DNS del correo (Brevo)

> Reemplaza la versión anterior, que proponía autenticar un subdominio
> `mail.conversemos.itaca.com.pe`. Eso no sirve: el remitente es
> `hola@conversemos.itaca.com.pe`, y Brevo autentica **el dominio del
> remitente**. El dominio a autenticar es `conversemos.itaca.com.pe`.

## Qué hay hoy (consultado el 1 oct 2026)

| Nombre | Tipo | Valor | Quién lo usa |
| --- | --- | --- | --- |
| `conversemos.itaca.com.pe` | A | `162.0.209.191` | Hosting viejo de Namecheap (WordPress) |
| `conversemos.itaca.com.pe` | TXT (SPF) | `v=spf1 ip4:162.0.209.190 ip4:162.0.209.201 include:spf.web-hosting.com +a +mx +ip4:192.64.117.37 ~all` | Correo del hosting |
| `conversemos.itaca.com.pe` | MX | — (no tiene) | Nadie recibe en `@conversemos.itaca.com.pe` |
| `_dmarc.conversemos.itaca.com.pe` y `_dmarc.itaca.com.pe` | TXT | — (no hay DMARC) | — |

El DNS de `itaca.com.pe` está en Namecheap (`dns1/dns2.namecheaphosting.com`)
y lo administra Soto. En ese panel los nombres van **relativos a la zona**
`itaca.com.pe`: `conversemos`, `_dmarc.conversemos`, etc.

## Lo que NO se toca

- El registro A de `conversemos.itaca.com.pe` (lo decide la separación de
  dominios, ver [dominios.md](dominios.md)).
- El SPF existente: **no se borra y no se crea un segundo SPF**. Un nombre solo
  puede tener un registro `v=spf1`.
- No se crea un MX. Las respuestas van a `BREVO_REPLY_TO`
  (`conversemos.itaca.com.pe` no recibe correo y no hace falta).
- No se toca `itaca.com.pe` ni ningún otro subdominio.

## Pasos

1. En Brevo: **Remitentes, dominio, IP → Dominios → Añadir un dominio** →
   `conversemos.itaca.com.pe` → autenticación **manual**.
2. Brevo muestra los registros de **esta cuenta**. Copiarlos literalmente;
   no usar valores de ejemplo de ninguna guía. Normalmente son:

| Registro | Tipo | Nombre en Namecheap | Valor |
| --- | --- | --- | --- |
| Código de verificación | TXT | `conversemos` | `brevo-code:…` (el de la cuenta) |
| DKIM | CNAME o TXT, uno o dos | `brevo1._domainkey.conversemos` (el que indique Brevo) | El que indique Brevo |
| DMARC | TXT | `_dmarc.conversemos` | `v=DMARC1; p=none; rua=mailto:rua@dmarc.brevo.com` |

   El TXT `brevo-code` convive sin problema con el SPF en el mismo nombre: un
   nombre puede tener varios TXT, solo no puede tener dos que empiecen por
   `v=spf1`.

3. **SPF**: solo si Brevo lo pide en la pantalla de autenticación. En ese caso
   se agrega su `include` **dentro del registro existente**, antes de `~all`:

```text
v=spf1 ip4:162.0.209.190 ip4:162.0.209.201 include:spf.web-hosting.com include:spf.brevo.com +a +mx +ip4:192.64.117.37 ~all
```

   Usar el `include` exacto que muestre Brevo si es distinto.

4. **DMARC** en `p=none`: solo observa, no rechaza. No avanzar a `quarantine`
   ni `reject` en Email 1.0.

5. En Brevo, pulsar **Verificar / Autenticar** hasta ver todo en verde.

## Verificar

```bash
nslookup -type=TXT conversemos.itaca.com.pe 8.8.8.8
nslookup -type=TXT _dmarc.conversemos.itaca.com.pe 8.8.8.8
nslookup -type=CNAME brevo1._domainkey.conversemos.itaca.com.pe 8.8.8.8
```

Después, con la prueba de humo de [activación](email-1.0-activacion.md),
abrir el correo recibido en Gmail → "Mostrar original": SPF, DKIM y DMARC
deben decir **PASS**.

## Volver atrás

Borrar solo los registros creados aquí (`brevo-code`, DKIM, DMARC) y, si se
editó el SPF, quitar el `include` de Brevo. Nada más cambió.
