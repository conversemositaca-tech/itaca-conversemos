// Tipos de aviso (toast). Antes el sistema decidía si un mensaje era error
// mirando si empezaba con "Error": "No se pudo enviar…" salía con check verde.
// Se puede pasar el tipo explícito; si no, se clasifica por el texto.

export const TIPOS_AVISO = ["success", "info", "warning", "error"];

const PATRON_ERROR = /^(error\b|no se pudo|no se puede|no puedes|no tienes|no hay conexi[oó]n|fall[oó]|falta[n]?\b|ya tiene|ya est[aá]|ya existe|sin permiso|denegad)/i;
const PATRON_AVISO = /^(atenci[oó]n|ojo\b|cuidado|revisa|pendiente)/i;
const PATRON_INFO = /^(sin cambios|nada que|no hubo cambios)/i;

export function tipoDeAviso(mensaje, explicito) {
  if (explicito && TIPOS_AVISO.includes(explicito)) return explicito;
  const texto = String(mensaje || "").trim();
  if (PATRON_INFO.test(texto)) return "info";
  if (PATRON_ERROR.test(texto)) return "error";
  if (PATRON_AVISO.test(texto)) return "warning";
  return "success";
}

export function textoDeAviso(mensaje) {
  return String(mensaje || "").replace(/^Error:\s*/i, "").replace(/\s*✓\s*$/, "");
}

// Los errores duran más: hay que alcanzar a leerlos.
export function duracionDeAviso(tipo) {
  return tipo === "error" ? 6000 : tipo === "warning" ? 4500 : 2800;
}
