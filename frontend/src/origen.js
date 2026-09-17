// De dónde llegó quien está navegando.
//
// Los parámetros de campaña llegan en la URL de entrada (…/?utm_source=meta&…),
// pero la reserva ocurre varias páginas después y en otra aplicación
// (/agendar/<token>): para entonces la URL ya no los lleva. Por eso se guardan
// en cuanto la persona entra y se recuperan al enviar la reserva.
//
// Se usa sessionStorage a propósito: dura lo que dura la visita y no sigue a
// nadie entre sesiones. No guarda nada de la persona, solo el origen del
// tráfico. Si el navegador lo bloquea, la reserva funciona igual, sin origen.

const LLAVE = "itaca_origen";

const CLAVES_URL = [
  "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
  "gclid", "fbclid", "variante",
];

function leerGuardado() {
  try {
    const crudo = window.sessionStorage.getItem(LLAVE);
    return crudo ? JSON.parse(crudo) : null;
  } catch {
    return null;
  }
}

/**
 * Se llama una vez al arrancar. Si la URL trae parámetros de campaña, los
 * guarda junto con la página de entrada y el sitio que refirió.
 *
 * El primer origen manda: si alguien llega por un anuncio, se va a leer las
 * preguntas y vuelve, lo que trajo la consulta sigue siendo el anuncio.
 */
export function recordarOrigen() {
  try {
    const params = new URLSearchParams(window.location.search);
    const datos = {};
    CLAVES_URL.forEach((k) => {
      const v = params.get(k);
      if (v) datos[k] = v;
    });

    const yaHabia = leerGuardado();
    if (yaHabia && !Object.keys(datos).length) return yaHabia;
    if (yaHabia && yaHabia.utm_source && !datos.utm_source) return yaHabia;

    // El referente solo cuenta si viene de fuera: navegar dentro del sitio no
    // es "haber llegado desde" ningún lado.
    const ref = document.referrer || "";
    if (ref && !ref.startsWith(window.location.origin)) datos.referrer = ref;
    datos.landing = window.location.pathname;

    if (!Object.keys(datos).length) return null;
    window.sessionStorage.setItem(LLAVE, JSON.stringify(datos));
    return datos;
  } catch {
    return null;
  }
}

/** Lo que se envía junto con la reserva. `null` si no se sabe de dónde vino. */
export function origenGuardado() {
  return leerGuardado();
}
