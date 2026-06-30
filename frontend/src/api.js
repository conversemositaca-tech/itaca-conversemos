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

// Query string de los filtros de Finanzas: rango personalizado (desde/hasta)
// o preset (periodo), + sede + estado.
function finanzasQS(f = {}) {
  const p = new URLSearchParams();
  if (f.desde && f.hasta) { p.set("desde", f.desde); p.set("hasta", f.hasta); }
  else p.set("periodo", f.periodo || "mes");
  if (f.sede) p.set("sede", f.sede);
  if (f.estado) p.set("estado", f.estado);
  return p.toString();
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
  // Bloqueos de horario (sin paciente)
  bloqueos: () => req("/api/bloqueos/"),
  crearBloqueo: (data) => req("/api/bloqueos/", { method: "POST", body: JSON.stringify(data) }),
  borrarBloqueo: (id) => req(`/api/bloqueos/${id}/`, { method: "DELETE" }),
  // `datos` = { motivo, presion_arterial, frecuencia_cardiaca, temperatura, peso,
  //             talla, diagnostico, indicaciones, nota } (todos opcionales).
  atenderCita: (id, datos) =>
    req(`/api/citas/${id}/atender/`, { method: "POST", body: JSON.stringify(datos) }),
  recordarCita: (id, texto) =>
    req(`/api/citas/${id}/recordar/`, { method: "POST", body: JSON.stringify({ texto }) }),
  // Transcribe un audio de la sesión (Whisper) y, si hay OpenAI, lo estructura.
  // Devuelve { transcripcion, estructura: {motivo,diagnostico,indicaciones,nota}|null }.
  transcribirAudio: (file, tipo) => {
    const fd = new FormData();
    fd.append("audio", file);
    if (tipo) fd.append("tipo", tipo);
    return req("/api/transcribir/", { method: "POST", body: fd });
  },
  confirmarCita: (id) => req(`/api/citas/${id}/confirmar/`, { method: "POST" }),
  setEstadoCita: (id, estado) => req(`/api/citas/${id}/estado/`, { method: "POST", body: JSON.stringify({ estado }) }),

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
  enviarMensajePaciente: (id, texto, tipo, plantillaId) =>
    req(`/api/pacientes/${id}/mensaje/`, { method: "POST", body: JSON.stringify({ texto, tipo, plantilla_id: plantillaId || null }) }),
  // Plantillas de mensaje (con variables). pacienteId opcional → trae preview sustituido.
  plantillas: (pacienteId) => req(`/api/plantillas/${pacienteId ? `?paciente=${pacienteId}` : ""}`),
  actualizarPlantilla: (id, data) => req(`/api/plantillas/${id}/`, { method: "PATCH", body: JSON.stringify(data) }),

  // Consentimiento informado (firma digital del paciente)
  consentimientos: (pacienteId) => req(`/api/consentimientos/?paciente=${pacienteId}`),
  crearConsentimiento: (paciente, tipo) => req("/api/consentimientos/", { method: "POST", body: JSON.stringify({ paciente, tipo }) }),
  consentimientoPublico: (token) => req(`/api/consentimiento/${token}/`),
  aceptarConsentimiento: (token, data) => req(`/api/consentimiento/${token}/aceptar/`, { method: "POST", body: JSON.stringify(data) }),

  // Leads / captación
  medicos: () => req("/api/medicos/"),
  leads: () => req("/api/leads/"),
  reportesLeads: () => req("/api/leads/reportes/"),
  crearLead: (data) => req("/api/leads/", { method: "POST", body: JSON.stringify(data) }),
  actualizarLead: (id, data) => req(`/api/leads/${id}/`, { method: "PATCH", body: JSON.stringify(data) }),
  convertirLead: (id) => req(`/api/leads/${id}/convertir/`, { method: "POST" }),
  leadSeguimiento: (id, nota) => req(`/api/leads/${id}/seguimiento/`, { method: "POST", body: JSON.stringify({ nota }) }),
  reportePauta: ({ sede, desde, hasta }) => {
    const qs = new URLSearchParams();
    if (sede) qs.set("sede", sede);
    if (desde) qs.set("desde", desde);
    if (hasta) qs.set("hasta", hasta);
    return req(`/api/leads/reporte-pauta/?${qs.toString()}`);
  },
  reporteCierre: ({ desde, hasta } = {}) => {
    const qs = new URLSearchParams();
    if (desde) qs.set("desde", desde);
    if (hasta) qs.set("hasta", hasta);
    return req(`/api/leads/reporte-cierre/?${qs.toString()}`);
  },
  // Catálogo de anuncios (pauta)
  anuncios: () => req("/api/anuncios/"),
  crearAnuncio: (data) => req("/api/anuncios/", { method: "POST", body: JSON.stringify(data) }),
  actualizarAnuncio: (id, data) => req(`/api/anuncios/${id}/`, { method: "PATCH", body: JSON.stringify(data) }),
  eliminarAnuncio: (id) => req(`/api/anuncios/${id}/`, { method: "DELETE" }),

  // Inicio (datos reales del día) + panel de gerencia (solo admin)
  hoy: () => req("/api/hoy/"),
  gerenciaResumen: (periodo, sede) => req(`/api/gerencia/resumen/?periodo=${periodo || "mes"}${sede ? `&sede=${sede}` : ""}`),

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
  // Documentos legales (contratos / adendas)
  documentosLegales: (profId) => req(`/api/documentos-legales/${profId ? `?profesional=${profId}` : ""}`),
  subirDocumentoLegal: (data) => {
    const fd = new FormData();
    Object.entries(data).forEach(([k, v]) => { if (v != null && v !== "") fd.append(k, v); });
    return req("/api/documentos-legales/", { method: "POST", body: fd });
  },
  borrarDocumentoLegal: (id) => req(`/api/documentos-legales/${id}/`, { method: "DELETE" }),
  urlDocumentoLegal: (id) => `/api/documentos-legales/${id}/archivo/`,
  pacientesDeProfesional: (profId) => req(`/api/pacientes/?profesional=${profId}`),
  registrarSesion: (id, data) => req(`/api/pacientes/${id}/registrar-sesion/`, { method: "POST", body: JSON.stringify(data) }),

  // Histórico mensual de marketing por sede (Gerencia)
  metricas: () => req("/api/metricas/"),
  crearMetrica: (data) => req("/api/metricas/", { method: "POST", body: JSON.stringify(data) }),
  actualizarMetrica: (id, data) => req(`/api/metricas/${id}/`, { method: "PATCH", body: JSON.stringify(data) }),
  eliminarMetrica: (id) => req(`/api/metricas/${id}/`, { method: "DELETE" }),

  // Reporte semanal ejecutivo (Directorio)
  reportesSemanales: () => req("/api/reportes-semanales/"),
  crearReporte: (data) => req("/api/reportes-semanales/", { method: "POST", body: JSON.stringify(data) }),
  actualizarReporte: (id, data) => req(`/api/reportes-semanales/${id}/`, { method: "PATCH", body: JSON.stringify(data) }),
  eliminarReporte: (id) => req(`/api/reportes-semanales/${id}/`, { method: "DELETE" }),
  sugerirReporte: ({ desde, hasta, anio, mes, semana }) => {
    const qs = new URLSearchParams();
    if (desde) qs.set("desde", desde);
    if (hasta) qs.set("hasta", hasta);
    if (anio) qs.set("anio", anio);
    if (mes) qs.set("mes", mes);
    if (semana) qs.set("semana", semana);
    return req(`/api/reportes-semanales/sugerir/?${qs.toString()}`);
  },
  ocupacion: ({ anio, mes, semana } = {}) => {
    const qs = new URLSearchParams();
    if (anio) qs.set("anio", anio);
    if (mes) qs.set("mes", mes);
    if (semana) qs.set("semana", semana);
    return req(`/api/ocupacion/?${qs.toString()}`);
  },

  // Finanzas (catálogo de precios + cobros)
  servicios: () => req("/api/servicios/"),
  crearServicio: (data) => req("/api/servicios/", { method: "POST", body: JSON.stringify(data) }),
  actualizarServicio: (id, data) => req(`/api/servicios/${id}/`, { method: "PATCH", body: JSON.stringify(data) }),
  eliminarServicio: (id) => req(`/api/servicios/${id}/`, { method: "DELETE" }),
  cobros: (f) => req(`/api/cobros/?${finanzasQS(f)}`),
  crearCobro: (data) => req("/api/cobros/", { method: "POST", body: JSON.stringify(data) }),
  marcarCobroPagado: (id, medio) =>
    req(`/api/cobros/${id}/marcar_pagado/`, { method: "POST", body: JSON.stringify({ medio_pago: medio }) }),
  resumenFinanzas: (f) => req(`/api/cobros/resumen/?${finanzasQS(f)}`),
  // Egresos (gastos) y caja — solo admin
  egresos: (f) => req(`/api/egresos/?${finanzasQS(f)}`),
  crearEgreso: (data) => req("/api/egresos/", { method: "POST", body: JSON.stringify(data) }),
  eliminarEgreso: (id) => req(`/api/egresos/${id}/`, { method: "DELETE" }),
  cajaFinanzas: (f) => req(`/api/finanzas/caja/?${finanzasQS(f)}`),
  // Consolidado de Soto (tablero financiero externo)
  sotoResumen: (mes) => req(`/api/finanzas/soto/${mes ? `?mes=${mes}` : ""}`),
  sotoPrueba: () => req("/api/finanzas/soto/prueba/", { method: "POST" }),
  // Conexión WhatsApp Cloud API (Meta)
  whatsappConfig: () => req("/api/whatsapp/config/"),
  guardarWhatsappConfig: (data) => req("/api/whatsapp/config/", { method: "POST", body: JSON.stringify(data) }),
  borrarWhatsappNumero: (id) => req(`/api/whatsapp/config/?id=${id}`, { method: "DELETE" }),
  // Paquetes de sesiones prepagadas
  paquetes: (pacienteId) => req(`/api/paquetes/${pacienteId ? `?paciente=${pacienteId}` : ""}`),
  crearPaquete: (data) => req("/api/paquetes/", { method: "POST", body: JSON.stringify(data) }),
  anularPaquete: (id) => req(`/api/paquetes/${id}/anular/`, { method: "POST" }),

  // --- Edición genérica tipo hoja de cálculo (cualquier endpoint del router) ---
  hojaListar: (endpoint, qs = "") => req(`/api/${endpoint}/${qs}`),
  hojaActualizar: (endpoint, id, data) =>
    req(`/api/${endpoint}/${id}/`, { method: "PATCH", body: JSON.stringify(data) }),
  hojaCrear: (endpoint, data) =>
    req(`/api/${endpoint}/`, { method: "POST", body: JSON.stringify(data) }),
  hojaBorrar: (endpoint, id) => req(`/api/${endpoint}/${id}/`, { method: "DELETE" }),

  // Ingreso automático de leads (URL/token de captación)
  captacionConfig: () => req("/api/captacion/config/"),
  regenerarTokenCaptacion: () => req("/api/captacion/regenerar/", { method: "POST" }),
  // Envía un lead a la URL pública (se usa para el botón "Probar"; es la misma
  // que pegarías en tu web o en Zapier).
  enviarLeadCaptacion: (path, data) => req(path, { method: "POST", body: JSON.stringify(data) }),
};
