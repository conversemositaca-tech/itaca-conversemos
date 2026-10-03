---
paths:
  - "frontend/src/main.jsx"
  - "frontend/src/rutas.js"
  - "frontend/src/Sitio.jsx"
  - "frontend/src/sitio-textos.js"
  - "frontend/src/paginas.json"
  - "frontend/src/embudo.js"
  - "frontend/src/origen.js"
  - "core/seo.py"
  - "core/dominios.py"
  - "core/sitio.py"
  - "config/urls.py"
---
# Sitio público, rutas, SEO y dominios

- **`SITE_ROUTES` (`rutas.js`) es la ÚNICA fuente de destinos internos.** Ningún componente escribe una ruta a mano. El token de `agendar` va fijo ahí: si se regenera desde Captación, se actualiza AHÍ.
- **No tapar `/gestion`**: `main.jsx` enruta `/consentimiento/<token>` · `/agendar/<token>` · `/gestion[/...]` → `<App />` · páginas del sitio · resto. `esRutaSitio()` consulta primero `esRutaReservada()` (`RESERVADAS`: /gestion, /agendar, /consentimiento, /api, /admin, /static, /media). Una página nueva del sitio nunca debe pisar una reservada.
- `propsEnlace()` hace navegación REAL (no `pushState`) para rutas reservadas: son otras apps del mismo dominio. Por ahí pasan todos los enlaces (y la medición del clic).
- Canónica `/preguntas-frecuentes`; `/preguntas` es alias publicado (`ALIAS_RUTAS`), no lo borres.
- `MOSTRAR_WORDPRESS = false`: blog y test del WordPress ocultos (certificado vencido). No enlaces al WordPress.
- **SEO** (`core/seo.py`, `SpaView`): título, descripción, canónica y Open Graph por ruta en el HTML del servidor (WhatsApp/Facebook no ejecutan JS). `/gestion`, `/agendar/…`, `/consentimiento/…` van con `noindex` y sin preview. Textos en `paginas.json`, que leen Django y React (una sola fuente).
- `/robots.txt` y `/sitemap.xml` son vistas propias registradas ANTES del comodín de `config/urls.py`; cualquier ruta nueva de servidor también.
- Imagen de preview por `static()` (`/static/sitio/...`); una ruta "a mano" cae en el comodín y sale sin foto.
- `core/tests_seo` lee el `index.html` CONSTRUIDO: tras cambiar `frontend/`, corre el build antes de la suite (verificar.ps1 lo hace).
- **Dominios** (`core/dominios.py`, `docs/dominios.md`): sitio y sistema separados por `SITIO_DOMINIO`/`SISTEMA_DOMINIO`; nunca redirigir `/api/`, `/admin/`, `/static/`, `/media/`; los enlaces públicos ya enviados (`/agendar/`, `/consentimiento/`, `/faro/`, `/preferencias/correo/`) funcionan en ambos. `SITIO_URL_PUBLICA` fija la URL canónica.
- `/api/sitio/` es público y resuelve la clínica por `SITIO_CLINICA_TOKEN`; con varias clínicas activas responde 404 en vez de adivinar.
- **Contenido**: no publicar cifras que la base no sostenga ni prometer resultados; fotos reales, nada generado con IA.
- **Atribución/embudo**: `origen.js` guarda el primer origen solo en `sessionStorage`; `fbclid` no prueba pauta (solo `gclid` o `utm_medium`). `EventoSitio` sin IP, user-agent, cookies ni relación con `Lead` (un test lo fija). La reserva nunca depende de la atribución.

Más contexto: ítems 31, 33–37, 39–41 del archivo histórico.
