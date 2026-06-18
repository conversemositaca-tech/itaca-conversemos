# Desplegar el sistema en la nube (link permanente)

Esta guía deja el sistema con una **URL fija con HTTPS, prendida 24/7**, que no depende
de tu PC. Plataforma recomendada: **Railway** (simple y confiable; ~US$5/mes).

El proyecto ya está **listo para producción**:
- `Dockerfile` que compila la app React y la sirve junto con la API (un solo servicio).
- `settings.py` lee la configuración del entorno (base de datos, seguridad, dominio).
- WhiteNoise sirve los archivos estáticos; Gunicorn es el servidor.

> Tú solo creas las cuentas y pegas unas variables. Yo (Claude) te guío en cada clic.

---

## 0. Lo que necesitas (una sola vez)
- Una cuenta en **GitHub** (gratis): https://github.com/signup
- Una cuenta en **Railway** (gratis para empezar): https://railway.app  → "Login with GitHub".
- Una tarjeta para el plan de US$5/mes (Railway lo pide para servicios que no se duermen).

## 1. Subir el código a GitHub
En la carpeta del proyecto (`C:\projects\clinica-saas`):

```bash
git add -A
git commit -m "Listo para desplegar"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/clinica-saas.git
git push -u origin main
```
(Primero crea el repositorio vacío en GitHub: botón **New repository** → nombre `clinica-saas` → **Private**.)

> El archivo `.env` (con tus claves) **no se sube** (está en `.gitignore`). 👍

## 2. Crear el proyecto en Railway
1. En Railway: **New Project** → **Deploy from GitHub repo** → elige `clinica-saas`.
2. Railway detecta el **Dockerfile** y empieza a construir. (La primera vez tarda unos minutos.)

## 3. Agregar la base de datos
1. Dentro del proyecto: **New** → **Database** → **Add PostgreSQL**.
2. Railway crea la variable **`DATABASE_URL`** y la comparte con el servicio automáticamente.

## 4. Agregar un volumen para los archivos (laboratorios, ecografías)
1. En el servicio web: **Settings** → **Volumes** → **New Volume**.
2. Punto de montaje (Mount path): **`/data`**

## 5. Variables de entorno (en el servicio web → pestaña *Variables*)
| Variable | Valor |
|---|---|
| `DJANGO_DEBUG` | `False` |
| `DJANGO_SECRET_KEY` | una clave larga y secreta (genera una abajo) |
| `DJANGO_MEDIA_ROOT` | `/data` |
| `EVOLUTION_API_URL` | (opcional) tu Evolution, para WhatsApp en vivo |
| `EVOLUTION_API_KEY` | (opcional) |
| `EVOLUTION_INSTANCE` | (opcional) |

- **No** hace falta poner `DJANGO_ALLOWED_HOSTS` ni el dominio: el código toma solo el
  dominio que Railway asigna (`RAILWAY_PUBLIC_DOMAIN`) para hosts y CSRF.
- Para generar la `DJANGO_SECRET_KEY`, en tu PC:
  ```bash
  .\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
  ```

## 6. Obtener la URL pública
En **Settings** → **Networking** → **Generate Domain**. Te dará algo como
`https://clinica-saas-production.up.railway.app`. **Ese es el link permanente.**

## 7. Dejar la primera clínica y el usuario admin
El despliegue corre las migraciones solo. Para tener una clínica y poder entrar, abre una
consola del servicio (**Railway → el servicio → … → "Run a command"** o la pestaña Shell) y corre:

```bash
python manage.py seed_demo
```
Eso crea la clínica y las cuentas demo (contraseña `demo1234`):
`admin@sanrafael.pe`, `castro@sanrafael.pe`, `asistente@sanrafael.pe`.

**Importante (seguridad):** entra como `admin@sanrafael.pe`, y:
1. Cambia tu contraseña (botón 🔑 abajo a la izquierda).
2. En **Equipo**, crea los usuarios reales y desactiva las cuentas demo que no uses.
3. En **Equipo → datos de la clínica**, pon el nombre real (Mont' Sinai).

## 8. (Opcional) Dominio propio
Si compras `sistema.montsinai.com`, en Railway **Settings → Networking → Custom Domain**
agrégalo y crea el registro CNAME que te indique. Funciona junto con el de arriba.

---

## Notas importantes
- **Datos de salud (Ley 29733):** ya queda con HTTPS, `DEBUG=False`, cookies seguras y la
  base en la nube. Recomendado: activar **backups** de PostgreSQL en Railway.
- **WhatsApp en vivo:** una vez con dominio fijo, en Evolution apunta el webhook de
  captación a `https://TU-DOMINIO/api/captacion/whatsapp/<token>` (el token sale en
  *Captación → Recibir leads automáticamente*).
- **Actualizaciones:** cada `git push` a `main` vuelve a desplegar solo.
