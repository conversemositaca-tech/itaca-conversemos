// Rutas públicas del sitio (inicio, quiénes somos, psicólogos, terapias,
// preguntas) y la navegación entre ellas.
//
// Vive aparte de App.jsx a propósito: la cabecera (que está en App.jsx, junto al
// agendamiento) necesita saber a dónde llevan sus enlaces, y las páginas del
// sitio necesitan la cabecera. Con este módulo en medio no hay import circular.
//
// El blog y los tres test siguen en el WordPress: se marcan `externo` para que
// la cabecera los abra allá en vez de dejar una ruta interna rota.

export const SITIO_WP = "https://conversemos.itaca.com.pe";

// Enlace público de reservas. Sale del token de captación que entrega
// `GET /api/sitio/`; esta constante es solo el respaldo para que el botón
// nunca quede muerto si la API todavía no respondió.
export const RUTA_AGENDAR = "/agendar";

export function rutaAgendar(token) {
  return token ? `${RUTA_AGENDAR}/${token}` : "";
}

// Menú del sitio, en el mismo orden que el WordPress. `externo: true` = todavía
// vive allá.
export const MENU_SITIO = [
  { label: "Quienes Somos", href: "/quienes-somos" },
  { label: "Psicólogos", href: "/psicologos" },
  { label: "Terapias Online", href: "/terapias-online" },
  { label: "Preguntas", href: "/preguntas" },
  { label: "Blog", href: `${SITIO_WP}/blog/`, externo: true },
];

export const TESTS_SITIO = [
  { label: "Test de Ansiedad", href: `${SITIO_WP}/test-de-ansiedad/`, externo: true },
  { label: "Test de Dependencia Emocional", href: `${SITIO_WP}/test-de-dependencia-emocional/`, externo: true },
  { label: "Test de Depresión", href: `${SITIO_WP}/test-de-depresion/`, externo: true },
];

// Rutas que sirve el sitio público (el catch-all de Django ya devuelve el SPA
// en cualquiera de ellas).
export const RUTAS_SITIO = ["/", "/quienes-somos", "/psicologos", "/terapias-online", "/preguntas"];

// Prefijos que NO son del sitio: el panel interno, las páginas públicas por
// token y todo lo que resuelve Django. La lista es explícita para que añadir
// una ruta al sitio no pueda volver a dejar sin puerta al sistema de gestión.
export function normalizarRuta(pathname) {
  return (pathname || "/").replace(/\/+$/, "") || "/";
}

export const RESERVADAS = ["/gestion", "/agendar", "/consentimiento", "/api", "/admin", "/static", "/media"];

export function esRutaReservada(pathname) {
  const p = normalizarRuta(pathname);
  return RESERVADAS.some((r) => p === r || p.startsWith(`${r}/`));
}

export function esRutaSitio(pathname) {
  const p = normalizarRuta(pathname);
  if (esRutaReservada(p)) return false;
  return RUTAS_SITIO.includes(p);
}



const EVENTO = "sitio:navegar";

/** Navega sin recargar (la app ya está cargada) y avisa a quien escuche. */
export function navegar(href) {
  if (normalizarRuta(window.location.pathname) === normalizarRuta(href)) {
    window.scrollTo({ top: 0, behavior: "smooth" });
    return;
  }
  window.history.pushState({}, "", href);
  window.dispatchEvent(new CustomEvent(EVENTO));
  window.scrollTo({ top: 0, behavior: "auto" });
}

/** Se suscribe a los cambios de ruta (clic interno o botón atrás del navegador). */
export function alCambiarRuta(fn) {
  window.addEventListener(EVENTO, fn);
  window.addEventListener("popstate", fn);
  return () => {
    window.removeEventListener(EVENTO, fn);
    window.removeEventListener("popstate", fn);
  };
}

/**
 * Props para un enlace interno: navega sin recargar, pero sigue siendo un <a>
 * de verdad (se puede abrir en pestaña nueva, copiar el enlace y tabular).
 */
export function propsEnlace(href, externo = false) {
  if (externo) return { href, target: "_blank", rel: "noopener" };
  return {
    href,
    onClick: (e) => {
      // Respeta ctrl/cmd+clic, clic central y "abrir en pestaña nueva".
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      e.preventDefault();
      navegar(href);
    },
  };
}
