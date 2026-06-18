// Cliente de la API de Django. En desarrollo, Vite reenvía /api a :8000.

function getCookie(name) {
  const m = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
  return m ? decodeURIComponent(m.pop()) : "";
}

async function req(url, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const esForm = options.body instanceof FormData;
  // Para subir archivos (FormData) dejamos que el navegador ponga el
  // Content-Type con su boundary; solo forzamos JSON cuando no es un form.
  const headers = { ...(esForm ? {} : { "Content-Type": "application/json" }), ...(options.headers || {}) };
  // Django exige el token CSRF en peticiones que modifican datos (sesión iniciada).
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    headers["X-CSRFToken"] = getCookie("csrftoken");
  }
  const res = await fetch(url, { credentials: "same-origin", ...options, headers });
  if (!res.ok) {
    let detalle = `Error ${res.status}`;
    try {
      const data = await res.json();
      detalle = data.detail || JSON.stringify(data);
    } catch {
      // respuesta sin cuerpo JSON
    }
    const err = new Error(detalle);
    err.status = res.status;
    throw err;
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  // Autenticación
  me: () => req("/api/auth/me/"),
  login: (email, password) =>
    req("/api/auth/login/", { method: "POST", body: JSON.stringify({ email, password }) }),
  logout: () => req("/api/auth/logout/", { method: "POST" }),

  // Pacientes
  pacientes: () => req("/api/pacientes/"),
  crearPaciente: (data) => req("/api/pacientes/", { method: "POST", body: JSON.stringify(data) }),
  actualizarPaciente: (id, data) =>
    req(`/api/pacientes/${id}/`, { method: "PATCH", body: JSON.stringify(data) }),

  // Citas
  citas: () => req("/api/citas/"),
  // data = { pacienteId | nuevoNombre, especialidad, fecha (YYYY-MM-DD), hora (HH:MM) }
  agendarCita: (data) => req("/api/citas/", { method: "POST", body: JSON.stringify(data) }),
  moverCita: (id, fecha, hora) =>
    req(`/api/citas/${id}/mover/`, { method: "POST", body: JSON.stringify({ fecha, hora }) }),
  cancelarCita: (id) => req(`/api/citas/${id}/cancelar/`, { method: "POST" }),
  // `datos` = { motivo, presion_arterial, frecuencia_cardiaca, temperatura, peso,
  //             talla, diagnostico, indicaciones, nota } (todos opcionales).
  atenderCita: (id, datos) =>
    req(`/api/citas/${id}/atender/`, { method: "POST", body: JSON.stringify(datos) }),
  recordarCita: (id, texto) =>
    req(`/api/citas/${id}/recordar/`, { method: "POST", body: JSON.stringify({ texto }) }),
  confirmarCita: (id) => req(`/api/citas/${id}/confirmar/`, { method: "POST" }),

  // Adjuntos (archivos clínicos: laboratorios, ecografías, PDFs, imágenes)
  subirAdjunto: (pacienteId, file, nombre, atencionId) => {
    const fd = new FormData();
    fd.append("archivo", file);
    fd.append("paciente", pacienteId);
    if (nombre) fd.append("nombre", nombre);
    if (atencionId) fd.append("atencion", atencionId);
    return req("/api/adjuntos/", { method: "POST", body: fd });
  },
  eliminarAdjunto: (id) => req(`/api/adjuntos/${id}/`, { method: "DELETE" }),
  urlAdjunto: (id) => `/api/adjuntos/${id}/descargar/`,

  // Mensajes (WhatsApp)
  mensajes: () => req("/api/mensajes/"),
  enviarMensajePaciente: (id, texto, tipo) =>
    req(`/api/pacientes/${id}/mensaje/`, { method: "POST", body: JSON.stringify({ texto, tipo }) }),

  // Leads / captación
  medicos: () => req("/api/medicos/"),
  leads: () => req("/api/leads/"),
  reportesLeads: () => req("/api/leads/reportes/"),
  crearLead: (data) => req("/api/leads/", { method: "POST", body: JSON.stringify(data) }),
  actualizarLead: (id, data) => req(`/api/leads/${id}/`, { method: "PATCH", body: JSON.stringify(data) }),
  convertirLead: (id) => req(`/api/leads/${id}/convertir/`, { method: "POST" }),

  // Inicio (datos reales del día) + panel de gerencia (solo admin)
  hoy: () => req("/api/hoy/"),
  gerenciaResumen: (periodo) => req(`/api/gerencia/resumen/?periodo=${periodo || "mes"}`),

  // Datos de la clínica (editar solo admin)
  clinicaConfig: () => req("/api/clinica/"),
  actualizarClinica: (data) => req("/api/clinica/", { method: "PATCH", body: JSON.stringify(data) }),

  // Equipo / usuarios (solo admin)
  usuarios: () => req("/api/usuarios/"),
  crearUsuario: (data) => req("/api/usuarios/", { method: "POST", body: JSON.stringify(data) }),
  actualizarUsuario: (id, data) => req(`/api/usuarios/${id}/`, { method: "PATCH", body: JSON.stringify(data) }),
  desactivarUsuario: (id) => req(`/api/usuarios/${id}/`, { method: "DELETE" }),
  resetPasswordUsuario: (id, password) =>
    req(`/api/usuarios/${id}/password/`, { method: "POST", body: JSON.stringify({ password }) }),
  // Cambiar la propia contraseña (cualquier usuario)
  cambiarMiPassword: (actual, nueva) =>
    req("/api/auth/cambiar-password/", { method: "POST", body: JSON.stringify({ actual, nueva }) }),

  // Directorio de profesionales (psicólogos)
  profesionales: () => req("/api/profesionales/"),
  crearProfesional: (data) => req("/api/profesionales/", { method: "POST", body: JSON.stringify(data) }),
  actualizarProfesional: (id, data) => req(`/api/profesionales/${id}/`, { method: "PATCH", body: JSON.stringify(data) }),
  eliminarProfesional: (id) => req(`/api/profesionales/${id}/`, { method: "DELETE" }),
  subirFotoProfesional: (id, file) => {
    const fd = new FormData();
    fd.append("foto", file);
    return req(`/api/profesionales/${id}/foto/`, { method: "POST", body: fd });
  },
  urlFotoProfesional: (id) => `/api/profesionales/${id}/foto/`,

  // Histórico mensual de marketing por sede (Gerencia)
  metricas: () => req("/api/metricas/"),
  crearMetrica: (data) => req("/api/metricas/", { method: "POST", body: JSON.stringify(data) }),
  actualizarMetrica: (id, data) => req(`/api/metricas/${id}/`, { method: "PATCH", body: JSON.stringify(data) }),
  eliminarMetrica: (id) => req(`/api/metricas/${id}/`, { method: "DELETE" }),

  // Finanzas (catálogo de precios + cobros)
  servicios: () => req("/api/servicios/"),
  crearServicio: (data) => req("/api/servicios/", { method: "POST", body: JSON.stringify(data) }),
  actualizarServicio: (id, data) => req(`/api/servicios/${id}/`, { method: "PATCH", body: JSON.stringify(data) }),
  eliminarServicio: (id) => req(`/api/servicios/${id}/`, { method: "DELETE" }),
  cobros: (periodo, estado) => req(`/api/cobros/?periodo=${periodo || "mes"}${estado ? "&estado=" + estado : ""}`),
  crearCobro: (data) => req("/api/cobros/", { method: "POST", body: JSON.stringify(data) }),
  marcarCobroPagado: (id, medio) =>
    req(`/api/cobros/${id}/marcar_pagado/`, { method: "POST", body: JSON.stringify({ medio_pago: medio }) }),
  resumenFinanzas: (periodo) => req(`/api/cobros/resumen/?periodo=${periodo || "mes"}`),
  // Egresos (gastos) y caja — solo admin
  egresos: (periodo) => req(`/api/egresos/?periodo=${periodo || "mes"}`),
  crearEgreso: (data) => req("/api/egresos/", { method: "POST", body: JSON.stringify(data) }),
  eliminarEgreso: (id) => req(`/api/egresos/${id}/`, { method: "DELETE" }),
  cajaFinanzas: (periodo) => req(`/api/finanzas/caja/?periodo=${periodo || "mes"}`),

  // Ingreso automático de leads (URL/token de captación)
  captacionConfig: () => req("/api/captacion/config/"),
  regenerarTokenCaptacion: () => req("/api/captacion/regenerar/", { method: "POST" }),
  // Envía un lead a la URL pública (se usa para el botón "Probar"; es la misma
  // que pegarías en tu web o en Zapier).
  enviarLeadCaptacion: (path, data) => req(path, { method: "POST", body: JSON.stringify(data) }),
};
