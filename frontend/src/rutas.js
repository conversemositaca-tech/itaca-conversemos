// Rutas públicas del sitio y la navegación entre ellas.
//
// Vive aparte de App.jsx a propósito: la cabecera (que está en App.jsx, junto al
// agendamiento) necesita saber a dónde llevan sus enlaces, y las páginas del
// sitio necesitan la cabecera. Con este módulo en medio no hay import circular.

/**
 * ÚNICA fuente de verdad de los destinos internos. Ningún componente debe
 * escribir una ruta a mano: si un enlace no sale de aquí, es un bug.
 *
 * `agendar` lleva el token de captación público de la clínica. Va fijo a
 * propósito —es el enlace que ya se reparte por WhatsApp y campañas— así que
 * si alguna vez se regenera desde Captación, hay que actualizarlo AQUÍ.
 */
import { PASOS, registrar } from "./embudo";

export const SITE_ROUTES = Object.freeze({
  inicio: "/",
  quienesSomos: "/quienes-somos",
  psicologos: "/psicologos",
  terapias: "/terapias-online",
  preguntas: "/preguntas-frecuentes",
  // Faro: tamizaje escolar. El cliente aquí es el colegio, no el paciente.
  faro: "/faro",
  agendar: "/agendar/PmFaG9KH4EOQF2BZ2MCHcupVu70rUxZG",
  gestion: "/gestion",
});

export const SITIO_WP = "https://conversemos.itaca.com.pe";

/**
 * El blog y los tres test siguen en el WordPress, pero su certificado venció el
 * 6 de enero de 2026: cualquiera que los abra choca con la advertencia de sitio
 * no seguro. Hasta que se renueve, NO se enlazan desde aquí.
 * Para volver a mostrarlos basta poner esto en true.
 */
export const MOSTRAR_WORDPRESS = false;

const ENLACES_WP = [
  { label: "Blog", href: `${SITIO_WP}/blog/`, externo: true },
];

export const TESTS_SITIO = MOSTRAR_WORDPRESS ? [
  { label: "Test de Ansiedad", href: `${SITIO_WP}/test-de-ansiedad/`, externo: true },
  { label: "Test de Dependencia Emocional", href: `${SITIO_WP}/test-de-dependencia-emocional/`, externo: true },
  { label: "Test de Depresión", href: `${SITIO_WP}/test-de-depresion/`, externo: true },
] : [];

// Menú del sitio. Todos los destinos salen de SITE_ROUTES.
export const MENU_SITIO = [
  { label: "Inicio", href: SITE_ROUTES.inicio },
  { label: "Quienes Somos", href: SITE_ROUTES.quienesSomos },
  { label: "Psicólogos", href: SITE_ROUTES.psicologos },
  { label: "Terapias", href: SITE_ROUTES.terapias },
  { label: "Preguntas", href: SITE_ROUTES.preguntas },
  { label: "Colegios", href: SITE_ROUTES.faro },
  // Reservar, también arriba: es la acción que la gente viene a hacer y ocupa
  // el lugar que dejó el Blog.
  { label: "Agendar", href: SITE_ROUTES.agendar },
  ...(MOSTRAR_WORDPRESS ? ENLACES_WP : []),
];

// Rutas que sirve el sitio público. `/preguntas` se mantiene como alias: era la
// dirección publicada antes de que la canónica pasara a `/preguntas-frecuentes`,
// y romperla dejaría enlaces muertos fuera de nuestro control.
export const ALIAS_RUTAS = Object.freeze({ "/preguntas": SITE_ROUTES.preguntas });

export const RUTAS_SITIO = [
  SITE_ROUTES.inicio, SITE_ROUTES.quienesSomos, SITE_ROUTES.psicologos,
  SITE_ROUTES.terapias, SITE_ROUTES.preguntas, SITE_ROUTES.faro, ...Object.keys(ALIAS_RUTAS),
];

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

/** Devuelve la dirección canónica de una ruta (resuelve alias y barra final). */
export function rutaCanonica(pathname) {
  const p = normalizarRuta(pathname);
  return ALIAS_RUTAS[p] || p;
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
  if (externo) return { href, target: "_blank", rel: "noopener noreferrer" };
  // El agendamiento y el panel son otras aplicaciones dentro del mismo dominio:
  // un pushState no las montaría, así que aquí se navega de verdad.
  if (esRutaReservada(href)) {
    // Todo enlace a reservar pasa por aquí —cabecera, portada, pie, FAQ—, así
    // que el clic se cuenta una sola vez y en un solo sitio: si mañana se
    // agrega otro botón, queda medido sin acordarse de nada.
    if (href === SITE_ROUTES.agendar) {
      return { href, onClick: () => registrar(PASOS.CLIC_RESERVAR) };
    }
    return { href };
  }
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
