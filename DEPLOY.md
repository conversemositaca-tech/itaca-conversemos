# Desplegar Itaca Conversemos en la nube (link permanente)

Esta guía deja el sistema con una **URL fija con HTTPS, prendida 24/7**, que no depende
de tu PC. Plataforma recomendada: **Railway** (simple y confiable; ~US$5/mes).

El proyecto ya está **listo para producción**:
- `Dockerfile` que compila la app React y la sirve junto con la API (un solo servicio).
- `settings.py` lee la configuración del entorno (base de datos, seguridad, dominio).
- WhiteNoise sirve los estáticos; Gunicorn es el servidor.
- **La primera vez carga TODOS los datos solos** (clínica, equipo, directorio de psicólogos,
  histórico de marketing, los pacientes reales por sede, su seguimiento y el reporte semanal),
  gracias al comando `bootstrap_itaca`. En los siguientes deploys NO se vuelve a tocar la data.

> Los datos de pacientes (`db.sqlite3`) y el `.env` **no se suben** al repo (están en `.gitignore`).
> En la nube se usa PostgreSQL y la data se genera con los seeds. 👍

---

## 0. Lo que necesitas (una sola vez)
- Cuenta en **Railway**: https://railway.app  → "Login with GitHub".
- Una tarjeta para el plan de US$5/mes (Railway lo pide para servicios que no se duermen).

## 1. El código ya está en GitHub
Repositorio (privado): **https://github.com/mirainishimura-maker/itaca-conversemos**
> Cada `git push` a `main` vuelve a desplegar solo.

## 2. Crear el proyecto en Railway
1. En Railway: **New Project** → **Deploy from GitHub repo** → elige `itaca-conversemos`.
2. Railway detecta el **Dockerfile** y empieza a construir. (La primera vez tarda unos minutos.)

## 3. Agregar la base de datos
1. Dentro del proyecto: **New** → **Database** → **Add PostgreSQL**.
2. Railway crea la variable **`DATABASE_URL`** y la comparte con el servicio automáticamente.

## 4. Agregar un volumen para los archivos (fotos de psicólogos, adjuntos)
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

- **No** hace falta `DJANGO_ALLOWED_HOSTS` ni el dominio: el código toma solo el dominio
  que Railway asigna (`RAILWAY_PUBLIC_DOMAIN`) para hosts y CSRF.
- Para generar la `DJANGO_SECRET_KEY`, en tu PC:
  ```bash
  C:\projects\clinica-saas\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
  ```

## 6. Obtener la URL pública
En **Settings** → **Networking** → **Generate Domain**. Te dará algo como
`https://itaca-conversemos-production.up.railway.app`. **Ese es el link permanente.**

## 7. Entrar (la data ya está cargada)
No hace falta correr nada: el primer arranque ejecuta migraciones y `bootstrap_itaca`,
que deja todo cargado. Entra con las cuentas demo (contraseña `demo1234`):
`admin@itaca.pe` (gerente), `lucia@itaca.pe` (psicóloga), `recepcion@itaca.pe`.

**Importante (seguridad):** entra como `admin@itaca.pe` y:
1. Cambia tu contraseña (botón 🔑 abajo a la izquierda).
2. En **Equipo**, crea los usuarios reales y desactiva las cuentas demo que no uses.

## 8. (Opcional) Dominio propio
Si usas un subdominio (p. ej. `sistema.conversemos.pe`), en Railway
**Settings → Networking → Custom Domain** agrégalo y crea el CNAME que te indique.

---

## Notas importantes
- **Datos de salud (Ley 29733):** queda con HTTPS, `DEBUG=False`, cookies seguras y la base
  en la nube. Recomendado: activar **backups** de PostgreSQL en Railway.
- **Dos sedes:** Piura y Lima ya vienen cargadas (histórico, pacientes, ocupación, etc.).
- **WhatsApp en vivo:** con dominio fijo, en Evolution apunta el webhook de captación a
  `https://TU-DOMINIO/api/captacion/whatsapp/<token>` (el token sale en *Captación → Recibir leads*).
- **Reiniciar datos desde cero** (si alguna vez quieres): borra la base, y en el próximo
  arranque `bootstrap_itaca` la vuelve a cargar completa.
