# Dominios: sitio público y sistema separados

La aplicación sigue siendo una sola en Railway. Se separan las direcciones:

| Dirección | Qué muestra |
| --- | --- |
| `www.conversemos.itaca.com.pe` | La landing (sitio público) |
| `sistema.conversemos.itaca.com.pe` | El panel interno |
| `conversemos.itaca.com.pe` | Redirige a `www` |

Los enlaces de reserva, consentimiento, Faro y preferencias de correo
funcionan en las dos direcciones, porque ya hay enlaces enviados.

## Por qué la landing va en `www` y no en `conversemos.itaca.com.pe`

Railway solo se conecta con un registro **CNAME**; no da una IP fija para un
registro A. Un CNAME no puede convivir con otros registros en el mismo nombre,
y `conversemos.itaca.com.pe` ya tiene un TXT (SPF) y va a tener los TXT de
Brevo para el correo. El DNS está en el hosting de Namecheap (cPanel), que no
ofrece ALIAS. Por eso la web va en `www` y el nombre corto queda para el correo
y una redirección.

## Pasos

1. En Railway → servicio → Settings → Networking → Custom Domain, agregar
   `www.conversemos.itaca.com.pe` y `sistema.conversemos.itaca.com.pe`.
   Railway muestra, para cada uno, un CNAME (y a veces un TXT de verificación).
2. Soto crea esos registros en Namecheap, copiados tal cual.
3. Soto deja `conversemos.itaca.com.pe` con su registro A actual y configura
   en el cPanel una redirección 301 a `https://www.conversemos.itaca.com.pe`.
   El cPanel debe renovar el certificado (AutoSSL) para que la redirección
   funcione con https.
4. En Railway, variables:

```text
SITIO_DOMINIO=www.conversemos.itaca.com.pe
SISTEMA_DOMINIO=sistema.conversemos.itaca.com.pe
SITIO_URL_PUBLICA=https://www.conversemos.itaca.com.pe
CORREO_BASE_URL_PUBLICA=https://www.conversemos.itaca.com.pe
```

5. Avisar al equipo que el panel ahora se abre en
   `https://sistema.conversemos.itaca.com.pe`. Cada persona vuelve a iniciar
   sesión una vez (la sesión es por dirección).
6. Actualizar las URL que apuntan a la dirección de Railway: webhooks de
   Evolution y de Meta, el cron de kira-bot y el webhook de Brevo. Siguen
   funcionando con la dirección de Railway, así que esto puede esperar.

## Sin las variables

`SITIO_DOMINIO` y `SISTEMA_DOMINIO` vacías = nada cambia: todo sigue en la
dirección por la que entre la visita.
