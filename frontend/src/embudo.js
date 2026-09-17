// Cuánta gente llega y dónde se queda.
//
// La reserva ya dice de dónde vino quien reservó. Lo que falta es lo anterior:
// cuántos entraron, cuántos hicieron clic y cuántos abandonaron el formulario.
// Sin eso, una campaña que trae 100 visitas y una reserva se ve igual que otra
// que trae 10 y una reserva.
//
// Esto NO sigue a nadie. Manda el paso, la página y de qué campaña venía la
// visita. No manda nada de la persona, y el identificador de visita es un
// número al azar que muere al cerrar la pestaña: sirve para no contar cinco
// veces a quien mira cinco páginas, nada más.
//
// Si algo aquí falla, falla en silencio. Medir nunca puede estorbarle a alguien
// que está intentando pedir una cita.

import { origenGuardado } from "./origen";

const DESTINO = "/api/embudo/";
const LLAVE = "itaca_visita";

export const PASOS = {
  VISITA: "visita",
  CLIC_RESERVAR: "clic_reservar",
  ABRE_AGENDA: "abre_agenda",
};

function idDeVisita() {
  try {
    let id = window.sessionStorage.getItem(LLAVE);
    if (!id) {
      id = Math.random().toString(36).slice(2, 12) + Date.now().toString(36);
      window.sessionStorage.setItem(LLAVE, id);
    }
    return id;
  } catch {
    // Almacenamiento bloqueado: se mide igual, solo que la visita no se puede
    // deduplicar y contará como varias.
    return "";
  }
}

export function registrar(paso, ruta) {
  try {
    const cuerpo = JSON.stringify({
      tipo: paso,
      ruta: ruta || window.location.pathname,
      sesion: idDeVisita(),
      atribucion: origenGuardado(),
    });

    // Al hacer clic en "Pide tu cita" la página se va de inmediato y un fetch
    // normal se cancelaría a medias: sendBeacon existe justo para eso, el
    // navegador lo entrega aunque ya esté cargando la página siguiente.
    if (navigator.sendBeacon) {
      navigator.sendBeacon(DESTINO, new Blob([cuerpo], { type: "application/json" }));
      return;
    }
    fetch(DESTINO, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: cuerpo,
      keepalive: true,
    }).catch(() => {});
  } catch {
    /* medir nunca puede romper la web */
  }
}
