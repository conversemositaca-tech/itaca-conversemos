import React, { useState, useMemo, useEffect } from "react";
import {
  Home, Calendar, Users, Receipt, Search, Plus, Clock, ChevronLeft,
  Phone, Cake, X, Stethoscope, MessageCircle, Check, Pencil, UserPlus, FileText,
  TrendingUp, Download, AlertTriangle, Megaphone, LogOut,
  Paperclip, Trash2, Activity, Pill, HeartPulse, Copy, BarChart3, UserCog, KeyRound, MapPin,
} from "lucide-react";
import { api } from "./api";
import Login from "./Login";

const TIPOS_DOC = [
  { v: "dni", l: "DNI" }, { v: "ce", l: "Carné de extranjería" },
  { v: "pasaporte", l: "Pasaporte" }, { v: "ruc", l: "RUC" },
];
const GENEROS = [
  { v: "", l: "—" }, { v: "femenino", l: "Femenino" },
  { v: "masculino", l: "Masculino" }, { v: "otro", l: "Otro" },
];

// ---- Especialidades (estilo Notion: pastel suave) ----
const SPECIALTY = {
  "Terapia individual": { bg: "#D7F4FA", fg: "#0A7D92", dot: "🗣️" },
  "Terapia de pareja": { bg: "#FCE7EF", fg: "#9C4670", dot: "💞" },
  "Terapia familiar": { bg: "#E3F0E8", fg: "#2F6B4F", dot: "🏠" },
  "Terapia infantil/adolescente": { bg: "#FFF1DA", fg: "#9C6B2E", dot: "🧸" },
  "Evaluación psicológica": { bg: "#EDE6F4", fg: "#6B4E96", dot: "📋" },
};

// ---- Plantillas de nota por especialidad ----
const TEMPLATES = {
  "Terapia individual": "Motivo de consulta:\n\nEstado de ánimo:\n\nTemas trabajados:\n\nAvances / observaciones:\n\nTarea para la próxima sesión:\n\nPróxima sesión:",
  "Terapia de pareja": "Asistentes a la sesión:\n\nMotivo / conflicto principal:\n\nDinámica observada:\n\nAcuerdos de la sesión:\n\nTarea para casa:\n\nPróxima sesión:",
  "Terapia familiar": "Participantes:\n\nMotivo de consulta:\n\nDinámica familiar observada:\n\nIntervenciones:\n\nAcuerdos / tareas:\n\nPróxima sesión:",
  "Terapia infantil/adolescente": "Motivo de consulta:\n\nObservación (juego / conducta):\n\nTemas trabajados:\n\nIndicaciones a los padres:\n\nTarea:\n\nPróxima sesión:",
  "Evaluación psicológica": "Motivo de la evaluación:\n\nPruebas aplicadas:\n\nObservaciones:\n\nResultados / hallazgos:\n\nConclusiones y recomendaciones:",
};

// Estados de cita (claves = códigos del backend).
const STATUS = {
  confirmada: { bg: "#E9F1ED", fg: "#3E7A65" },
  por_confirmar: { bg: "#F7ECDD", fg: "#9C6B2E" },
  atendida: { bg: "#EFEDE8", fg: "#7C7870" },
  cancelada: { bg: "#F7E5E5", fg: "#9C4646" },
};

const MENSAJE_ESTADO = {
  enviado: { bg: "#E9F1ED", fg: "#3E7A65" },
  fallido: { bg: "#F7E5E5", fg: "#9C4646" },
  no_configurado: { bg: "#F7ECDD", fg: "#9C6B2E" },
};

const LEAD_ESTADOS = [
  { v: "nuevo", l: "Nuevo" },
  { v: "contactado", l: "Contactado" },
  { v: "agendado", l: "Sesión agendada" },
  { v: "ganado", l: "Inició tratamiento" },
  { v: "perdido", l: "Perdido" },
];
const LEAD_ESTADO_COLOR = {
  nuevo: { bg: "#EFEDE8", fg: "#7C7870" },
  contactado: { bg: "#E2ECF5", fg: "#2E5C86" },
  agendado: { bg: "#F7ECDD", fg: "#9C6B2E" },
  ganado: { bg: "#E9F1ED", fg: "#3E7A65" },
  perdido: { bg: "#F7E5E5", fg: "#9C4646" },
};
const FUENTES = [
  { v: "instagram", l: "Instagram" }, { v: "facebook", l: "Facebook" },
  { v: "tiktok", l: "TikTok" }, { v: "referido", l: "Referido" },
  { v: "whatsapp", l: "WhatsApp" }, { v: "web", l: "Web" },
  { v: "convenio", l: "Convenio" }, { v: "otro", l: "Otro" },
];

// ---- Helpers de fecha (zona local) ----
const _MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "set", "oct", "nov", "dic"];
const pad2 = (n) => String(n).padStart(2, "0");
const aISO = (d) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
const dDeISO = (iso) => { const [y, m, d] = iso.split("-").map(Number); return new Date(y, m - 1, d); };
const sumarDias = (iso, n) => { const d = dDeISO(iso); d.setDate(d.getDate() + n); return aISO(d); };
const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);
const HOY_ISO = aISO(new Date());
// fecha_corta del backend ("12 jun 2026"), para resaltar la atención de hoy en la ficha.
const HOY_FECHA = (() => { const h = new Date(); return `${h.getDate()} ${_MESES[h.getMonth()]} ${h.getFullYear()}`; })();

function semanaDe(iso) {
  const d = dDeISO(iso);
  const lunesOffset = (d.getDay() + 6) % 7; // 0 = lunes
  const lunes = sumarDias(iso, -lunesOffset);
  return Array.from({ length: 7 }, (_, i) => sumarDias(lunes, i));
}
const labelLargo = (iso) => cap(dDeISO(iso).toLocaleDateString("es-PE", { weekday: "long", day: "numeric", month: "long" }));
const labelDiaSemana = (iso) => cap(dDeISO(iso).toLocaleDateString("es-PE", { weekday: "short" }).replace(".", ""));
const labelNumMes = (iso) => { const d = dDeISO(iso); return `${d.getDate()} ${_MESES[d.getMonth()]}`; };

// ---- Reporte semanal (datos de ejemplo · módulo en construcción) ----
const FIN = {
  semana: "Semana 1 · Junio 2026",
  servicios: [
    { esp: "Terapia individual", tarifa: 80, unidades: 28 },
    { esp: "Psicología", tarifa: 95, unidades: 22 },
    { esp: "Pediatría", tarifa: 90, unidades: 14 },
    { esp: "Dermatología", tarifa: 100, unidades: 11 },
    { esp: "Cardiología", tarifa: 120, unidades: 9 },
    { esp: "Nutrición", tarifa: 70, unidades: 6 },
  ],
  acumuladoMes: 8190,
  metaMin: 45000,
  metaIdeal: 65000,
  ocupacion: [
    { nombre: "Dra. Castro", esp: "Terapia individual", horas: 30, atenciones: 24, comision: 0.5 },
    { nombre: "Lic. Rojas", esp: "Psicología", horas: 24, atenciones: 18, comision: 0.6 },
    { nombre: "Dr. Salas", esp: "Pediatría", horas: 25, atenciones: 15, comision: 0.55 },
    { nombre: "Dr. Núñez", esp: "Terapia individual", horas: 20, atenciones: 8, comision: 0.5 },
    { nombre: "Lic. Paredes", esp: "Psicología", horas: 16, atenciones: 5, comision: 0.6 },
  ],
  pacientesActivos: 67,
  sinProxima: 5,
};

const tarifaDe = (esp) => ((FIN.servicios.find((s) => s.esp === esp) || {}).tarifa || 0);

// ---- Datos de Marketing / Captación (datos de ejemplo) ----
const MKT = {
  leads: 54,
  consultas: 18,
  inicios: 6,
  fuentes: [
    { fuente: "Instagram", n: 22 },
    { fuente: "Referidos", n: 14 },
    { fuente: "TikTok", n: 8 },
    { fuente: "Convenios", n: 6 },
    { fuente: "Otros", n: 4 },
  ],
  alianzas: [
    { con: "Tondero", tipo: "Colaboración", estado: "Activo" },
    { con: "DGALLIA", tipo: "Convenio", estado: "Activo" },
    { con: "Nexo Club", tipo: "Alianza", estado: "Negociación" },
  ],
};
const ESTADO_ALIANZA = {
  Activo: { bg: "#E9F1ED", fg: "#3E7A65" },
  "Negociación": { bg: "#F7ECDD", fg: "#9C6B2E" },
};

const semColor = (pct) => (pct >= 0.7 ? "#4F8A77" : pct >= 0.4 ? "#C9923A" : "#B4564E");
const money = (n) => "S/ " + Math.round(n).toLocaleString("es-PE");

// Exporta filas a un CSV descargable (con BOM para que Excel lea bien las tildes).
function descargarCSV(nombre, headers, filas) {
  const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const csv = [headers.map(esc).join(","), ...filas.map((f) => f.map(esc).join(","))].join("\r\n");
  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = nombre; a.click();
  URL.revokeObjectURL(url);
}

// Abre una ventana con la historia clínica formateada para imprimir o guardar en PDF.
function imprimirHistoria(p, clinica) {
  const w = window.open("", "_blank", "width=840,height=920");
  if (!w) return;
  const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const vit = (h) => {
    const v = [];
    if (h.presion_arterial) v.push(`PA ${h.presion_arterial}`);
    if (h.frecuencia_cardiaca != null) v.push(`FC ${h.frecuencia_cardiaca} lpm`);
    if (h.temperatura != null) v.push(`T° ${numeroLimpio(h.temperatura)} °C`);
    if (h.peso != null) v.push(`Peso ${numeroLimpio(h.peso)} kg`);
    if (h.talla != null) v.push(`Talla ${h.talla} cm`);
    return v.join(" · ");
  };
  const ats = (p.historial || []).map((h) => `
    <div class="at">
      <div class="meta">${esc(h.fecha)} · ${esc(h.medico || "")}${h.especialidad ? " · " + esc(h.especialidad) : ""}</div>
      ${h.motivo ? `<p><b>Motivo:</b> ${esc(h.motivo)}</p>` : ""}
      ${vit(h) ? `<p><b>Signos vitales:</b> ${esc(vit(h))}</p>` : ""}
      ${h.diagnostico ? `<p><b>Diagnóstico:</b> ${esc(h.diagnostico)}</p>` : ""}
      ${h.indicaciones ? `<p><b>Indicaciones:</b> ${esc(h.indicaciones)}</p>` : ""}
      ${h.nota ? `<p>${esc(h.nota).replace(/\n/g, "<br>")}</p>` : ""}
    </div>`).join("");
  w.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>Historia clínica · ${esc(p.nombre)}</title>
    <style>
      body{font-family:Inter,Arial,sans-serif;color:#32302C;max-width:720px;margin:28px auto;padding:0 16px;line-height:1.5}
      .head{display:flex;justify-content:space-between;align-items:baseline;border-bottom:2px solid #4F8A77;padding-bottom:8px;margin-bottom:16px}
      h1{font-size:20px;margin:0} .sub{color:#777;font-size:13px;margin-bottom:18px}
      .box{border:1px solid #e5e0d8;border-radius:8px;padding:12px 14px;margin-bottom:16px}
      .lbl{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:#999;margin-bottom:6px}
      .at{border-top:1px solid #eee;padding:10px 0} .at:first-child{border-top:none}
      .meta{font-size:12px;color:#888;margin-bottom:4px} p{margin:4px 0;font-size:14px}
      @media print{ .noprint{display:none} }
    </style></head><body>
    <div class="head"><h1>${esc(clinica || "Clínica")}</h1><div>Historia clínica</div></div>
    <h1>${esc(p.nombre)}</h1>
    <div class="sub">${p.edad != null ? p.edad + " años · " : ""}${esc(p.tel || "")}${p.especialidad ? " · " + esc(p.especialidad) : ""}</div>
    <div class="box"><div class="lbl">Antecedentes</div>
      <p><b>Alergias:</b> ${esc(p.alergias || "—")}</p>
      <p><b>Antecedentes:</b> ${esc(p.antecedentes || "—")}</p>
      <p><b>Medicación habitual:</b> ${esc(p.medicacion_habitual || "—")}</p>
    </div>
    <div class="lbl">Atenciones</div>
    ${ats || "<p>Sin atenciones registradas.</p>"}
    <button class="noprint" onclick="window.print()" style="margin-top:18px;padding:9px 16px;border:none;border-radius:7px;background:#4F8A77;color:#fff;font-size:14px;cursor:pointer">Imprimir / Guardar PDF</button>
    </body></html>`);
  w.document.close();
}

function Tag({ children, colors }) {
  const c = colors || { bg: "#EFEDE8", fg: "#7C7870" };
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "2px 9px", borderRadius: 999,
      fontSize: 12.5, fontWeight: 500, background: c.bg, color: c.fg, whiteSpace: "nowrap" }}>
      {children}
    </span>
  );
}
function SpecialtyTag({ name }) {
  const c = SPECIALTY[name] || { bg: "#EFEDE8", fg: "#7C7870", dot: "•" };
  return (<Tag colors={c}><span style={{ fontSize: 11 }}>{c.dot}</span>{name}</Tag>);
}
const iniciales = (n) => (n || "").split(" ").map((w) => w[0]).slice(0, 2).join("");

export default function ClinicaApp() {
  const [view, setView] = useState("hoy");
  const [pacientes, setPacientes] = useState([]);
  const [citas, setCitas] = useState([]);
  const [mensajes, setMensajes] = useState([]);
  const [servicios, setServicios] = useState([]);
  const [waPaciente, setWaPaciente] = useState(null);
  const [usuario, setUsuario] = useState(null);
  const [iniciando, setIniciando] = useState(true);
  const [query, setQuery] = useState("");
  const [filterEsp, setFilterEsp] = useState(null);
  const [soloSinProxima, setSoloSinProxima] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [adding, setAdding] = useState(false);
  const [atender, setAtender] = useState(null);
  const [recordar, setRecordar] = useState(null);
  const [reagendar, setReagendar] = useState(null);
  const [cancelando, setCancelando] = useState(null);
  const [cobrando, setCobrando] = useState(null);
  const [cambiarPass, setCambiarPass] = useState(false);
  const [agendarPara, setAgendarPara] = useState(null);
  const [agendaFecha, setAgendaFecha] = useState(HOY_ISO);
  const [agendaVista, setAgendaVista] = useState("dia");
  const [editingPaciente, setEditingPaciente] = useState(null);
  const [toast, setToast] = useState("");

  async function cargarDatos() {
    const [pac, cit, msg, srv] = await Promise.all([api.pacientes(), api.citas(), api.mensajes(), api.servicios()]);
    setPacientes(pac); setCitas(cit); setMensajes(msg); setServicios(srv);
  }
  async function iniciar() {
    const d = await api.me();
    if (d.autenticado) { setUsuario(d); await cargarDatos(); }
    else setUsuario(null);
  }
  useEffect(() => {
    iniciar().catch(() => setUsuario(null)).finally(() => setIniciando(false));
  }, []);

  async function handleLogin(email, password) {
    const d = await api.login(email, password);
    setUsuario(d);
    await cargarDatos();
  }
  async function handleLogout() {
    try { await api.logout(); } catch { /* sin conexión: limpiamos igual */ }
    setUsuario(null); setPacientes([]); setCitas([]); setView("hoy"); setSelectedId(null);
  }
  async function cambiarMiPassword(actual, nueva) {
    await api.cambiarMiPassword(actual, nueva);
    setCambiarPass(false);
    showToast("Contraseña actualizada ✓");
  }

  const refrescarPacientes = async () => setPacientes(await api.pacientes());
  const refrescarCitas = async () => setCitas(await api.citas());
  const refrescarMensajes = async () => setMensajes(await api.mensajes());

  const selected = pacientes.find((p) => p.id === selectedId) || null;
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return pacientes.filter((p) =>
      (!q || p.nombre.toLowerCase().includes(q) || (p.tel || "").toLowerCase().includes(q) || (p.numero_documento || "").toLowerCase().includes(q)) &&
      (!filterEsp || p.especialidad === filterEsp) &&
      (!soloSinProxima || !p.proxima));
  }, [pacientes, query, filterEsp, soloSinProxima]);

  const nav = [
    { id: "hoy", label: "Hoy", icon: Home },
    // El panel de Gerencia lo ve solo el dueño/admin.
    ...(usuario?.rol === "admin" ? [{ id: "gerencia", label: "Gerencia", icon: BarChart3 }] : []),
    { id: "agenda", label: "Agenda", icon: Calendar },
    { id: "pacientes", label: "Pacientes", icon: Users },
    { id: "profesionales", label: "Profesionales", icon: HeartPulse },
    { id: "mensajes", label: "Mensajes", icon: MessageCircle },
    { id: "marketing", label: "Marketing", icon: Megaphone },
    { id: "finanzas", label: "Finanzas", icon: TrendingUp },
    ...(usuario?.rol === "admin" ? [{ id: "equipo", label: "Equipo", icon: UserCog }] : []),
  ];

  const citasHoy = citas.filter((c) => c.fecha === HOY_ISO && c.estado !== "cancelada");
  const cumpleHoy = useMemo(() => {
    const t = new Date(), mm = t.getMonth() + 1, dd = t.getDate();
    return pacientes.filter((p) => {
      if (!p.fecha_nacimiento) return false;
      const [, m, d] = p.fecha_nacimiento.split("-").map(Number);
      return m === mm && d === dd;
    });
  }, [pacientes]);
  const proximas = citasHoy.filter((c) => c.estado !== "atendida").slice(0, 3);
  const porConfirmar = citasHoy.filter((c) => c.estado === "por_confirmar").length;
  const atendidas = citasHoy.filter((c) => c.estado === "atendida").length;

  function showToast(msg) { setToast(msg); setTimeout(() => setToast(""), 2800); }
  function go(v) { setView(v); setSelectedId(null); }
  function openFicha(id) { if (!id) return; setView("pacientes"); setSelectedId(id); }

  async function guardarAtencion(cita, datos) {
    try {
      await api.atenderCita(cita.id, datos);
      await Promise.all([refrescarCitas(), refrescarPacientes()]);
      setAtender(null);
      showToast("Atención guardada en la historia clínica ✓");
    } catch (e) { showToast("Error: " + e.message); }
  }

  async function subirAdjunto(paciente, file) {
    try {
      await api.subirAdjunto(paciente.id, file, file.name);
      await refrescarPacientes();
      showToast("Archivo adjuntado ✓");
    } catch (e) { showToast("Error: " + e.message); }
  }

  async function eliminarAdjunto(id) {
    try {
      await api.eliminarAdjunto(id);
      await refrescarPacientes();
      showToast("Archivo eliminado");
    } catch (e) { showToast("Error: " + e.message); }
  }

  function manejarResultadoEnvio(r, okMsg) {
    if (r.estado === "enviado") {
      showToast(okMsg);
    } else if (r.wa_url) {
      window.open(r.wa_url, "_blank");
      showToast("Abrimos WhatsApp para enviarlo a mano 📲");
    } else {
      showToast("No se pudo enviar: " + (r.detalle || "revisa el teléfono"));
    }
  }

  async function enviarRecordatorio(cita, texto) {
    try {
      const r = await api.recordarCita(cita.id, texto);
      await Promise.all([refrescarCitas(), refrescarMensajes()]);
      setRecordar(null);
      manejarResultadoEnvio(r, "Recordatorio enviado por WhatsApp ✓");
    } catch (e) { showToast("Error: " + e.message); }
  }

  async function enviarMensajePaciente(paciente, texto, tipo) {
    try {
      const r = await api.enviarMensajePaciente(paciente.id, texto, tipo);
      await refrescarMensajes();
      setWaPaciente(null);
      manejarResultadoEnvio(r, "Mensaje enviado por WhatsApp ✓");
    } catch (e) { showToast("Error: " + e.message); }
  }

  async function guardarPaciente(data) {
    const payload = {
      nombre: data.nombre,
      fecha_nacimiento: data.fecha_nacimiento || null,
      tel: data.tel || "",
      especialidad: data.especialidad || "",
      tipo_documento: data.tipo_documento || "dni",
      numero_documento: data.numero_documento || "",
      direccion: data.direccion || "",
      genero: data.genero || "",
      alergias: data.alergias || "",
      antecedentes: data.antecedentes || "",
      medicacion_habitual: data.medicacion_habitual || "",
    };
    try {
      if (data.id) {
        await api.actualizarPaciente(data.id, payload);
        await refrescarPacientes();
        showToast("Datos actualizados ✓");
      } else {
        const nuevo = await api.crearPaciente(payload);
        await refrescarPacientes();
        setSelectedId(nuevo.id);
        showToast("Paciente agregado ✓");
      }
      setEditingPaciente(null);
    } catch (e) { showToast("Error: " + e.message); }
  }

  async function agendarCita(data) {
    try {
      let pacienteId = data.pacienteId;
      if (data.nuevoNombre) {
        const nuevo = await api.crearPaciente({ nombre: data.nuevoNombre, especialidad: data.especialidad });
        pacienteId = nuevo.id;
      }
      const r = await api.agendarCita({ pacienteId, fecha: data.fecha, hora: data.hora, especialidad: data.especialidad });
      await Promise.all([refrescarCitas(), refrescarPacientes()]);
      setAdding(false);
      if (data.fecha) setAgendaFecha(data.fecha); // saltar al día de la cita recién creada
      showToast(r?.aviso ? r.aviso : "Sesión agendada ✓");
    } catch (e) { showToast("Error: " + e.message); }
  }

  async function moverCita(cita, fecha, hora) {
    try {
      await api.moverCita(cita.id, fecha, hora);
      await refrescarCitas();
      setReagendar(null);
      setAgendaFecha(fecha);
      showToast("Sesión reagendada ✓");
    } catch (e) { showToast("Error: " + e.message); }
  }

  async function cancelarCita(cita) {
    try {
      await api.cancelarCita(cita.id);
      await refrescarCitas();
      setCancelando(null);
      showToast("Sesión cancelada");
    } catch (e) { showToast("Error: " + e.message); }
  }

  async function guardarCobro(data) {
    try {
      await api.crearCobro(data);
      await refrescarCitas();
      setCobrando(null);
      showToast("Cobro registrado ✓");
    } catch (e) { showToast("Error: " + e.message); }
  }

  async function confirmarCita(cita) {
    try {
      await api.confirmarCita(cita.id);
      await refrescarCitas();
      showToast("Sesión confirmada ✓");
    } catch (e) { showToast("Error: " + e.message); }
  }

  const nombreClinica = usuario?.clinica?.nombre || "Clínica";
  const ciudadClinica = usuario?.clinica?.ciudad || "";
  const esAsistente = usuario?.rol === "asistente";

  if (iniciando) {
    return (
      <div style={{
        minHeight: "88vh", display: "flex", alignItems: "center", justifyContent: "center",
        background: "#FBFAF8", border: "1px solid #ECE8E1", borderRadius: 14, color: "#9B968D",
        fontFamily: "'Inter',system-ui,sans-serif",
      }}>Cargando…</div>
    );
  }
  if (!usuario) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <div className="clinica-app">
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;450;500;600;700&display=swap');
        .clinica-app {
          --bg:#F4FBFD; --surface:#FFFFFF; --ink:#343434; --ink-soft:#555555;
          --muted:#6E6E6E; --line:#DCEBEF; --accent:#0A7D92; --accent-soft:#D7F4FA;
          --hover:#EAF9FC; --wa:#2F8F5B; --wa-soft:#E6F4EC;
          font-family:'Inter',-apple-system,system-ui,sans-serif;
          background:var(--bg); color:var(--ink);
          display:flex; min-height:640px; height:88vh; border-radius:14px;
          overflow:hidden; border:1px solid var(--line);
          -webkit-font-smoothing:antialiased; letter-spacing:-0.01em;
        }
        .clinica-app * { box-sizing:border-box; }
        .ca-side { width:236px; flex-shrink:0; background:#F7F5F1; border-right:1px solid var(--line);
          padding:14px 10px; display:flex; flex-direction:column; gap:2px; }
        .ca-ws { display:flex; align-items:center; gap:9px; padding:8px 8px 14px; }
        .ca-ws-logo { width:30px; height:30px; border-radius:8px; background:var(--accent-soft);
          display:flex; align-items:center; justify-content:center; font-size:16px; }
        .ca-ws-name { font-weight:600; font-size:14.5px; line-height:1.15; }
        .ca-ws-sub { font-size:11.5px; color:var(--muted); }
        .ca-navitem { display:flex; align-items:center; gap:10px; padding:7px 9px; border-radius:7px;
          font-size:14px; color:var(--ink-soft); cursor:pointer; border:none; background:none; width:100%;
          text-align:left; font-family:inherit; transition:background .12s; }
        .ca-navitem:hover { background:var(--hover); }
        .ca-navitem.active { background:var(--hover); color:var(--ink); font-weight:500; }
        .ca-navitem.soft { color:var(--muted); cursor:default; }
        .ca-navitem.soft:hover { background:none; }
        .ca-sectlabel { font-size:11px; font-weight:600; color:var(--muted); text-transform:uppercase;
          letter-spacing:.06em; padding:14px 9px 6px; }
        .ca-soonbadge { margin-left:auto; font-size:10px; background:#EFEDE8; color:var(--muted);
          padding:1px 7px; border-radius:999px; font-weight:500; }
        .ca-main { flex:1; overflow-y:auto; padding:34px 40px 60px; }
        .ca-h1 { font-size:25px; font-weight:600; letter-spacing:-0.02em; margin:0; }
        .ca-sub { color:var(--ink-soft); font-size:14px; margin-top:5px; }
        .ca-stats { display:flex; gap:12px; margin:26px 0 34px; flex-wrap:wrap; }
        .ca-stats { display:flex; gap:12px; flex-wrap:wrap; }
        .ca-profgrid { display:grid; grid-template-columns:repeat(auto-fill, minmax(300px, 1fr)); gap:14px; margin-top:16px; }
        .ca-profcard { background:var(--surface); border:1px solid var(--line); border-radius:12px; padding:16px; }
        .ca-proffoto { width:54px; height:54px; border-radius:12px; object-fit:cover; flex-shrink:0; }
        .ca-demo { display:grid; grid-template-columns:1fr 1fr; gap:18px; }
        @media (max-width:760px){ .ca-demo { grid-template-columns:1fr; } }
        .ca-stat { flex:1; min-width:130px; background:var(--surface); border:1px solid var(--line);
          border-radius:11px; padding:15px 17px; }
        .ca-stat-n { font-size:26px; font-weight:600; letter-spacing:-0.02em; }
        .ca-stat-l { font-size:13px; color:var(--ink-soft); margin-top:2px; }
        .ca-secth { font-size:13px; font-weight:600; color:var(--muted); text-transform:uppercase;
          letter-spacing:.05em; margin:0 0 12px; }
        .ca-row { display:flex; align-items:center; gap:14px; padding:13px 14px; background:var(--surface);
          border:1px solid var(--line); border-radius:10px; margin-bottom:8px; transition:border-color .12s, background .12s; }
        .ca-row.click { cursor:pointer; }
        .ca-row.click:hover { background:#FDFCFA; border-color:#DED9D0; }
        .ca-time { display:flex; align-items:center; gap:6px; font-variant-numeric:tabular-nums;
          font-weight:600; font-size:14px; width:62px; flex-shrink:0; }
        .ca-pname { font-weight:500; font-size:14.5px; }
        .ca-pnamebtn { background:none; border:none; padding:0; font-family:inherit; color:var(--ink);
          font-weight:500; font-size:14.5px; cursor:pointer; text-align:left; }
        .ca-pnamebtn:hover { color:var(--accent); text-decoration:underline; }
        .ca-pmeta { font-size:12.5px; color:var(--muted); margin-top:1px; }
        .ca-btn { display:inline-flex; align-items:center; gap:7px; background:var(--accent); color:#fff;
          border:none; padding:8px 14px; border-radius:8px; font-size:13.5px; font-weight:500;
          cursor:pointer; font-family:inherit; transition:filter .12s; }
        .ca-btn:hover { filter:brightness(1.06); }
        .ca-btn.ghost { background:var(--surface); color:var(--ink-soft); border:1px solid var(--line); }
        .ca-btn.ghost:hover { background:var(--hover); }
        .ca-tophead { display:flex; align-items:center; justify-content:space-between; gap:16px; margin-bottom:8px; }
        .ca-actions { display:flex; align-items:center; gap:7px; margin-left:auto; }
        .ca-mini { display:flex; align-items:center; gap:6px; background:none; border:1px solid var(--line);
          color:var(--accent); padding:5px 11px; border-radius:7px; font-size:12.5px; font-weight:500;
          cursor:pointer; font-family:inherit; transition:background .12s; }
        .ca-mini:hover { background:var(--accent-soft); }
        .ca-mini.wa { color:var(--wa); }
        .ca-mini.wa:hover { background:var(--wa-soft); }
        .ca-mini.done { color:var(--wa); border-color:var(--wa-soft); background:var(--wa-soft); cursor:default; }
        .ca-search { display:flex; align-items:center; gap:9px; background:var(--surface); border:1px solid var(--line);
          border-radius:9px; padding:9px 13px; max-width:340px; margin-bottom:18px; }
        .ca-search input { border:none; outline:none; font-size:14px; font-family:inherit; width:100%;
          color:var(--ink); background:none; }
        .ca-avatar { width:34px; height:34px; border-radius:9px; flex-shrink:0; display:flex; align-items:center;
          justify-content:center; font-weight:600; font-size:13.5px; color:var(--accent); background:var(--accent-soft); }
        .ca-empty { text-align:center; padding:50px 20px; color:var(--muted); }
        .ca-back { display:inline-flex; align-items:center; gap:5px; background:none; border:none;
          color:var(--ink-soft); font-size:13.5px; cursor:pointer; font-family:inherit; padding:4px 0; margin-bottom:16px; }
        .ca-back:hover { color:var(--ink); }
        .ca-card { background:var(--surface); border:1px solid var(--line); border-radius:12px; padding:22px; }
        .ca-field { display:flex; align-items:center; gap:8px; font-size:13.5px; color:var(--ink-soft); }
        .ca-hist { border-left:2px solid var(--line); padding-left:16px; margin-left:6px; }
        .ca-histitem { position:relative; padding-bottom:18px; }
        .ca-histitem:last-child { padding-bottom:0; }
        .ca-histitem::before { content:''; position:absolute; left:-21px; top:5px; width:8px; height:8px;
          border-radius:50%; background:var(--accent); }
        .ca-histitem.nuevo::before { box-shadow:0 0 0 4px var(--accent-soft); }
        .ca-histnota { font-size:14px; line-height:1.5; white-space:pre-wrap; }
        .ca-anteced { display:grid; grid-template-columns:repeat(3,1fr); gap:18px; }
        .ca-antlabel { display:flex; align-items:center; gap:6px; font-size:11.5px; font-weight:600; color:var(--muted);
          text-transform:uppercase; letter-spacing:.03em; margin-bottom:5px; }
        .ca-antval { font-size:14px; line-height:1.5; }
        .ca-hcampo { font-size:14px; line-height:1.5; margin-bottom:4px; }
        .ca-hlabel { font-weight:600; color:var(--ink-soft); margin-right:5px; }
        .ca-hval { white-space:pre-wrap; }
        .ca-vitales { display:flex; flex-wrap:wrap; gap:6px; margin:6px 0; }
        .ca-vital { font-size:12.5px; background:var(--accent-soft); color:var(--accent); border-radius:6px;
          padding:3px 9px; font-variant-numeric:tabular-nums; }
        .ca-vital b { font-weight:600; margin-right:3px; }
        .ca-vitgrid { display:grid; grid-template-columns:repeat(5,1fr); gap:8px; }
        .ca-vitin { display:flex; flex-direction:column; }
        .ca-vitin > span { font-size:11px; color:var(--muted); }
        .ca-vitin .ca-input { margin-top:3px; padding:7px 6px; font-size:13px; text-align:center; }
        .ca-adjrow { display:flex; align-items:center; gap:11px; padding:10px 12px; border:1px solid var(--line);
          border-radius:9px; background:var(--surface); }
        .ca-adjname { font-size:14px; font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .ca-adjchip { display:inline-flex; align-items:center; gap:5px; font-size:12px; color:var(--accent);
          background:var(--accent-soft); border-radius:6px; padding:3px 8px; text-decoration:none; }
        .ca-adjchip:hover { filter:brightness(.97); }
        .ca-upload { display:inline-flex; align-items:center; gap:7px; cursor:pointer; background:var(--accent-soft);
          color:var(--accent); border:1px dashed var(--accent); padding:9px 14px; border-radius:9px;
          font-size:13.5px; font-weight:500; }
        .ca-upload:hover { filter:brightness(.98); }
        .ca-iconbtn { background:none; border:1px solid var(--line); color:var(--muted); border-radius:7px;
          padding:6px; cursor:pointer; display:inline-flex; }
        .ca-iconbtn:hover { color:#9C4646; border-color:#E6C9C9; background:#FBF1F1; }
        .ca-urlbox { display:flex; align-items:center; gap:10px; background:var(--bg); border:1px solid var(--line);
          border-radius:9px; padding:7px 9px; }
        .ca-urlbox code { flex:1; min-width:0; font-size:12.5px; color:var(--ink-soft); overflow:hidden;
          text-overflow:ellipsis; white-space:nowrap; font-family:ui-monospace,Menlo,Consolas,monospace; }
        .ca-agnav { display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-top:6px; }
        .ca-navgrp { display:flex; align-items:center; gap:6px; }
        .ca-navbtn { display:inline-flex; align-items:center; justify-content:center; gap:4px; min-width:34px; height:34px;
          padding:0 11px; border:1px solid var(--line); background:var(--surface); color:var(--ink-soft); border-radius:8px;
          font-size:13px; font-weight:500; font-family:inherit; cursor:pointer; }
        .ca-navbtn:hover { background:var(--hover); }
        .ca-navbtn.on { background:var(--accent-soft); color:var(--accent); border-color:var(--accent-soft); }
        .ca-datein { border:1px solid var(--line); border-radius:8px; padding:7px 10px; font-size:13.5px; font-family:inherit;
          color:var(--ink); background:var(--surface); outline:none; }
        .ca-datein:focus { border-color:var(--accent); }
        .ca-seg { display:inline-flex; border:1px solid var(--line); border-radius:8px; overflow:hidden; margin-left:auto; }
        .ca-seg button { border:none; background:var(--surface); color:var(--ink-soft); font-size:13px; font-weight:500;
          font-family:inherit; padding:7px 15px; cursor:pointer; }
        .ca-seg button.on { background:var(--accent); color:#fff; }
        .ca-wk { display:grid; grid-template-columns:repeat(7,minmax(0,1fr)); gap:8px; margin-top:18px; }
        .ca-wkcol { background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:8px; min-height:130px; }
        .ca-wkcol.hoy { border-color:var(--accent); background:var(--accent-soft); }
        .ca-wkhd { text-align:center; margin-bottom:8px; cursor:pointer; border-radius:6px; padding:2px 0; }
        .ca-wkhd:hover { background:rgba(0,0,0,.03); }
        .ca-wkhd .d { font-size:11px; color:var(--muted); text-transform:capitalize; }
        .ca-wkhd .n { font-weight:600; font-size:15px; line-height:1.2; }
        .ca-wkempty { text-align:center; color:var(--muted); font-size:13px; padding:8px 0; }
        .ca-evt { border-radius:7px; padding:5px 7px; margin-bottom:5px; cursor:pointer; border-left:3px solid transparent; overflow:hidden; }
        .ca-evt:hover { filter:brightness(.97); }
        .ca-evt .h { font-size:11.5px; font-weight:600; font-variant-numeric:tabular-nums; }
        .ca-evt .p { font-size:11.5px; color:var(--ink); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .ca-evt.cancel { opacity:.55; }
        .ca-evt.cancel .p { text-decoration:line-through; }
        @media (max-width:640px){ .ca-anteced { grid-template-columns:1fr; gap:14px; } }
        @media (max-width:560px){ .ca-vitgrid { grid-template-columns:repeat(3,1fr); } }
        @media (max-width:820px){ .ca-wk { grid-auto-flow:column; grid-template-columns:none; grid-auto-columns:minmax(118px,1fr);
          overflow-x:auto; padding-bottom:4px; } .ca-seg { margin-left:0; } }
        .ca-modal-bg { position:fixed; inset:0; background:rgba(40,38,34,.30); display:flex; align-items:center;
          justify-content:center; padding:20px; z-index:30; }
        .ca-modal { background:var(--surface); border-radius:14px; width:100%; max-width:430px; padding:22px;
          border:1px solid var(--line); box-shadow:0 12px 40px rgba(40,38,34,.16); max-height:90vh; overflow-y:auto; }
        .ca-input { width:100%; border:1px solid var(--line); border-radius:8px; padding:9px 11px; font-size:14px;
          font-family:inherit; color:var(--ink); outline:none; margin-top:5px; background:var(--surface); }
        .ca-input:focus { border-color:var(--accent); }
        .ca-textarea { min-height:150px; resize:vertical; line-height:1.55; }
        .ca-label { font-size:12.5px; font-weight:500; color:var(--ink-soft); }
        .ca-pos { position:relative; }
        .ca-tplbar { display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin:6px 0 4px; }
        .ca-tplchip { display:inline-flex; align-items:center; gap:6px; background:var(--accent-soft);
          color:var(--accent); border:none; padding:5px 11px; border-radius:7px; font-size:12.5px; font-weight:500;
          cursor:pointer; font-family:inherit; }
        .ca-tplchip:hover { filter:brightness(.98); }
        .ca-tplsel { border:1px solid var(--line); border-radius:7px; padding:5px 8px; font-size:12.5px;
          font-family:inherit; color:var(--ink-soft); background:var(--surface); outline:none; }
        .ca-pick { border:1px solid var(--line); border-radius:8px; margin-top:6px; overflow:hidden; }
        .ca-pickrow { display:flex; align-items:center; gap:10px; padding:8px 11px; cursor:pointer; }
        .ca-pickrow:hover { background:var(--hover); }
        .ca-pickrow + .ca-pickrow { border-top:1px solid var(--line); }
        .ca-newrow { display:flex; align-items:center; gap:8px; padding:9px 11px; cursor:pointer;
          color:var(--accent); font-size:13px; border-top:1px solid var(--line); }
        .ca-newrow:hover { background:var(--hover); }
        .ca-chipsel { display:flex; align-items:center; gap:10px; padding:9px 11px; background:var(--accent-soft);
          border-radius:8px; margin-top:6px; }
        .ca-link { background:none; border:none; color:var(--ink-soft); font-size:12px; cursor:pointer;
          font-family:inherit; text-decoration:underline; margin-left:auto; }
        .ca-wapreview { background:var(--wa-soft); border-radius:10px; padding:13px 15px; font-size:13.5px;
          line-height:1.55; color:#2A4A38; border:1px solid #D4E9DC; }
        .ca-tbl { width:100%; border-collapse:collapse; background:var(--surface); border:1px solid var(--line);
          border-radius:11px; overflow:hidden; margin-bottom:10px; }
        .ca-tbl th { text-align:left; font-size:11px; font-weight:600; color:var(--muted); text-transform:uppercase;
          letter-spacing:.04em; padding:11px 14px; border-bottom:1px solid var(--line); }
        .ca-tbl td { padding:11px 14px; font-size:13.5px; border-bottom:1px solid var(--line); }
        .ca-tbl tr:last-child td { border-bottom:none; }
        .ca-tbl .num { text-align:right; font-variant-numeric:tabular-nums; }
        .ca-tbl .tot td { font-weight:600; background:#FBFAF8; }
        .ca-dot { display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:6px; vertical-align:middle; }
        .ca-alert { display:flex; align-items:flex-start; gap:11px; background:#FBF1E3; border:1px solid #F0DDBF;
          color:#8A5A1E; border-radius:11px; padding:13px 15px; font-size:13.5px; margin-bottom:24px; line-height:1.5; }
        .ca-bar { height:8px; background:var(--line); border-radius:999px; overflow:hidden; margin-top:10px; }
        .ca-bar > div { height:100%; background:var(--accent); border-radius:999px; }
        .ca-glance { display:grid; grid-template-columns:repeat(2,1fr); gap:12px; margin:26px 0 34px; }
        .ca-gcard { text-align:left; background:var(--surface); border:1px solid var(--line); border-radius:12px;
          padding:16px 18px; cursor:pointer; font-family:inherit; transition:border-color .12s, transform .12s, box-shadow .12s; }
        .ca-gcard:hover { border-color:#DCD7CE; transform:translateY(-1px); box-shadow:0 4px 16px rgba(40,38,34,.05); }
        .ca-ghead { display:flex; align-items:center; gap:7px; font-size:11.5px; color:var(--muted); font-weight:600;
          text-transform:uppercase; letter-spacing:.04em; margin-bottom:9px; }
        .ca-gmain { font-size:21px; font-weight:600; letter-spacing:-0.02em; }
        .ca-gsub { font-size:12.5px; color:var(--ink-soft); margin-top:2px; }
        .ca-profile { margin-top:auto; display:flex; align-items:center; gap:9px; padding:11px 8px 4px;
          border-top:1px solid var(--line); }
        .ca-fchips { display:flex; gap:7px; flex-wrap:wrap; margin-bottom:18px; }
        .ca-fchip { border:1px solid var(--line); background:var(--surface); color:var(--ink-soft); border-radius:999px;
          padding:5px 13px; font-size:12.5px; font-weight:500; cursor:pointer; font-family:inherit; transition:background .12s, color .12s, border-color .12s; }
        .ca-fchip:hover { background:var(--hover); }
        .ca-fchip.on { background:var(--ink); color:#fff; border-color:var(--ink); }
        .ca-toast { position:fixed; bottom:26px; left:50%; transform:translateX(-50%); background:#32302C; color:#fff;
          padding:11px 18px; border-radius:10px; font-size:13.5px; font-weight:500; z-index:40;
          box-shadow:0 8px 28px rgba(40,38,34,.28); display:flex; align-items:center; gap:8px; animation:caUp .22s ease; }
        @keyframes caUp { from { opacity:0; transform:translate(-50%,8px); } to { opacity:1; transform:translate(-50%,0); } }
        @media (prefers-reduced-motion: reduce) { .ca-toast { animation:none; } }
        @media (max-width:720px) {
          .clinica-app { flex-direction:column; height:auto; }
          .ca-side { width:100%; flex-direction:row; overflow-x:auto; border-right:none;
            border-bottom:1px solid var(--line); padding:10px; align-items:center; }
          .ca-ws { padding:4px 8px 4px 4px; }
          .ca-ws-sub, .ca-sectlabel { display:none; }
          .ca-navitem { width:auto; white-space:nowrap; }
          .ca-main { padding:24px 18px 50px; }
          .ca-row { flex-wrap:wrap; }
          .ca-actions { width:100%; margin-left:0; }
          .ca-profile { display:none; }
          .ca-glance { grid-template-columns:1fr; }
        }
      `}</style>

      {/* ---- Sidebar ---- */}
      <aside className="ca-side">
        <div className="ca-ws">
          <div className="ca-ws-logo">🩺</div>
          <div>
            <div className="ca-ws-name">{nombreClinica}</div>
            <div className="ca-ws-sub">{ciudadClinica}</div>
          </div>
        </div>
        {nav.map((n) => {
          const Icon = n.icon;
          return (
            <button key={n.id} className={`ca-navitem ${view === n.id ? "active" : ""}`} onClick={() => go(n.id)}>
              <Icon size={17} strokeWidth={1.9} />{n.label}
            </button>
          );
        })}
        <div className="ca-sectlabel">Pronto</div>
        <div className="ca-navitem soft">
          <Receipt size={17} strokeWidth={1.9} />Facturación<span className="ca-soonbadge">SUNAT</span>
        </div>
        {usuario && (
          <div className="ca-profile">
            <div className="ca-avatar" style={{ width: 30, height: 30, fontSize: 12 }}>{iniciales(usuario.nombre)}</div>
            <div style={{ lineHeight: 1.2, flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{usuario.nombre}</div>
              <div style={{ fontSize: 11.5, color: "var(--muted)" }}>{usuario.especialidad || usuario.rol_label}</div>
            </div>
            <button onClick={() => setCambiarPass(true)} title="Cambiar mi contraseña"
              style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)", padding: 4, display: "flex" }}>
              <KeyRound size={15} strokeWidth={2} />
            </button>
            <button onClick={handleLogout} title="Cerrar sesión"
              style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)", padding: 4, display: "flex" }}>
              <LogOut size={16} strokeWidth={2} />
            </button>
          </div>
        )}
      </aside>

      {/* ---- Main ---- */}
      <main className="ca-main ca-pos">
        {view === "hoy" && (
          <Hoy proximas={proximas} citasHoy={citasHoy.length} porConfirmar={porConfirmar} atendidas={atendidas} onOpen={openFicha} onGo={go}
            onRetencion={() => { setSoloSinProxima(true); go("pacientes"); }} cumple={cumpleHoy} esAdmin={usuario?.rol === "admin"} />
        )}

        {view === "agenda" && (
          <Agenda
            citas={citas} fecha={agendaFecha} setFecha={setAgendaFecha}
            vista={agendaVista} setVista={setAgendaVista} esAsistente={esAsistente}
            onAgendar={() => setAdding(true)} onAtender={setAtender} onRecordar={setRecordar}
            onReagendar={setReagendar} onCancelar={setCancelando} openFicha={openFicha}
            onConfirmar={confirmarCita}
            onCobrar={(c) => setCobrando({ pacienteId: c.pacienteId, paciente: c.paciente, citaId: c.id, especialidad: c.especialidad })}
          />
        )}

        {view === "pacientes" && !selected && (
          <>
            <div className="ca-tophead">
              <div>
                <h1 className="ca-h1">Pacientes</h1>
                <div className="ca-sub">{pacientes.length} en total</div>
              </div>
              <div style={{ display: "flex", gap: 9, alignItems: "center" }}>
                <button className="ca-btn ghost" disabled={filtered.length === 0}
                  onClick={() => descargarCSV("pacientes.csv", ["Nombre", "Documento", "Numero", "Edad", "Genero", "Telefono", "Direccion", "Especialidad", "Ultima visita", "Proxima sesion", "Pendiente S/"],
                    filtered.map((p) => [p.nombre, p.tipo_documento_label || "", p.numero_documento || "", p.edad ?? "", p.genero_label || "", p.tel, p.direccion || "", p.especialidad, p.ultima, p.proxima ? `${p.proxima.fecha} ${p.proxima.hora}` : "", p.cuenta?.pendiente || 0]))}>
                  <Download size={15} strokeWidth={2} /> CSV
                </button>
                <button className="ca-btn" onClick={() => setEditingPaciente({ new: true })}>
                  <UserPlus size={16} strokeWidth={2.1} /> Nuevo paciente
                </button>
              </div>
            </div>
            <div className="ca-search" style={{ marginTop: 22 }}>
              <Search size={16} strokeWidth={2} style={{ color: "var(--muted)" }} />
              <input placeholder="Buscar por nombre o teléfono…" value={query} onChange={(e) => setQuery(e.target.value)} />
            </div>
            <div className="ca-fchips">
              <button className={`ca-fchip ${!filterEsp ? "on" : ""}`} onClick={() => setFilterEsp(null)}>Todas</button>
              {Object.keys(SPECIALTY).map((s) => (
                <button key={s} className={`ca-fchip ${filterEsp === s ? "on" : ""}`} onClick={() => setFilterEsp(s)}>{s}</button>
              ))}
              <button className={`ca-fchip ${soloSinProxima ? "on" : ""}`} onClick={() => setSoloSinProxima((v) => !v)}
                style={{ marginLeft: 6, color: soloSinProxima ? undefined : "#B0822F" }}>⏰ Sin próxima sesión</button>
            </div>
            {filtered.length === 0 ? (
              <div className="ca-empty">No encontramos a nadie con ese nombre. Prueba con otro o agrégalo arriba.</div>
            ) : (
              filtered.map((p) => (
                <div key={p.id} className="ca-row click" onClick={() => setSelectedId(p.id)}>
                  <div className="ca-avatar">{iniciales(p.nombre)}</div>
                  <div style={{ flex: 1 }}>
                    <div className="ca-pname">{p.nombre}</div>
                    <div className="ca-pmeta">{p.numero_documento ? `${p.tipo_documento_label} ${p.numero_documento} · ` : ""}{p.edad != null ? `${p.edad} años · ` : ""}{p.proxima ? `próxima ${p.proxima.fecha}` : `última visita ${p.ultima}`}</div>
                  </div>
                  {p.cuenta?.pendiente > 0 && <Tag colors={ESTADO_COBRO_COLOR.pendiente}>Debe {money(p.cuenta.pendiente)}</Tag>}
                  <SpecialtyTag name={p.especialidad} />
                </div>
              ))
            )}
          </>
        )}

        {view === "pacientes" && selected && (
          <Ficha p={selected} onBack={() => setSelectedId(null)} onEdit={() => setEditingPaciente(selected)}
            onWhatsApp={() => setWaPaciente(selected)} clinica={nombreClinica} onAgendar={() => setAgendarPara(selected)}
            onSubirAdjunto={(file) => subirAdjunto(selected, file)}
            onEliminarAdjunto={eliminarAdjunto} puedeEliminar={usuario?.rol === "medico" || usuario?.rol === "admin"} />
        )}

        {view === "gerencia" && <Gerencia showToast={showToast} />}

        {view === "equipo" && <Equipo showToast={showToast} miId={usuario?.id} />}

        {view === "profesionales" && <Profesionales showToast={showToast} esAdmin={usuario?.rol === "admin"} />}

        {view === "mensajes" && <Mensajes mensajes={mensajes} />}

        {view === "marketing" && <Marketing showToast={showToast} onConvertir={refrescarPacientes} esAdmin={usuario?.rol === "admin"} />}

        {view === "finanzas" && <Finanzas showToast={showToast} esAdmin={usuario?.rol === "admin"} />}

        {adding && <AgendarModal pacientes={pacientes} fechaInicial={agendaFecha} onClose={() => setAdding(false)} onSave={agendarCita} />}
        {agendarPara && (
          <AgendarModal pacientes={pacientes} fechaInicial={agendaFecha}
            pacienteFijo={{ id: agendarPara.id, nombre: agendarPara.nombre, especialidad: agendarPara.especialidad }}
            onClose={() => setAgendarPara(null)} onSave={async (d) => { await agendarCita(d); setAgendarPara(null); }} />
        )}
        {atender && <AtenderModal cita={atender} servicios={servicios} onClose={() => setAtender(null)} onSave={(datos) => guardarAtencion(atender, datos)} />}
        {recordar && <RecordarModal cita={recordar} clinica={nombreClinica} onClose={() => setRecordar(null)} onSend={(texto) => enviarRecordatorio(recordar, texto)} />}
        {reagendar && <ReagendarModal cita={reagendar} onClose={() => setReagendar(null)} onSave={moverCita} />}
        {cobrando && <CobroModal prefill={cobrando} pacientes={pacientes} servicios={servicios} onClose={() => setCobrando(null)} onSave={guardarCobro} />}
        {cancelando && (
          <ConfirmModal
            titulo="Cancelar sesión"
            mensaje={`¿Cancelar la sesión de ${cancelando.paciente} del ${labelLargo(cancelando.fecha)} a las ${cancelando.hora}? Quedará registrada como cancelada.`}
            confirmLabel="Sí, cancelar" peligro
            onConfirm={() => cancelarCita(cancelando)} onClose={() => setCancelando(null)}
          />
        )}
        {waPaciente && <MensajePacienteModal paciente={waPaciente} onClose={() => setWaPaciente(null)} onSend={(texto, tipo) => enviarMensajePaciente(waPaciente, texto, tipo)} />}
        {editingPaciente && (
          <PacienteModal paciente={editingPaciente.new ? null : editingPaciente}
            onClose={() => setEditingPaciente(null)} onSave={guardarPaciente} />
        )}
      </main>

      {cambiarPass && <CambiarPasswordModal onClose={() => setCambiarPass(false)} onSave={cambiarMiPassword} />}
      {toast && <div className="ca-toast">{toast}</div>}
    </div>
  );
}

const GEN_COLOR = { "Femenino": "#D96B8F", "Masculino": "#4F8A77", "Otro": "#9C6B2E", "Sin registro": "#9B968D" };

function BarrasH({ data, color = "var(--accent)", colorPor }) {
  if (!data || data.length === 0) return <div style={{ color: "var(--muted)", fontSize: 14 }}>Sin datos.</div>;
  const max = Math.max(1, ...data.map((d) => d.valor));
  const total = data.reduce((s, d) => s + d.valor, 0) || 1;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
      {data.map((d) => (
        <div key={d.label} style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 92, fontSize: 13, color: "var(--ink-soft)", flexShrink: 0 }}>{d.label}</div>
          <div style={{ flex: 1, height: 16, background: "var(--line)", borderRadius: 999, overflow: "hidden" }}>
            <div style={{ height: "100%", width: `${(d.valor / max) * 100}%`, background: (colorPor && colorPor[d.label]) || color, borderRadius: 999, minWidth: d.valor ? 4 : 0, transition: "width .2s" }} />
          </div>
          <div style={{ width: 70, textAlign: "right", fontSize: 13, fontVariantNumeric: "tabular-nums", flexShrink: 0 }}>
            {d.valor} <span style={{ color: "var(--muted)", fontSize: 12 }}>{Math.round((d.valor / total) * 100)}%</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function StatCard({ label, valor, sub, color }) {
  return (
    <div className="ca-stat">
      <div className="ca-stat-n" style={color ? { color } : undefined}>{valor}</div>
      <div className="ca-stat-l">{label}</div>
      {sub && <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

// Tendencia vs período anterior (texto con flecha).
function deltaTxt(cur, prev) {
  if (!prev && !cur) return "sin cambios";
  if (!prev) return "▲ nuevo";
  const d = Math.round(((cur - prev) / prev) * 100);
  if (d === 0) return "= igual al anterior";
  return `${d > 0 ? "▲" : "▼"} ${Math.abs(d)}% vs anterior`;
}

// Barras simples (SVG-less) para series cortas.
function MiniBars({ data, valor, etiqueta, color = "#4F8A77", alto = 96, fmt = money }) {
  const max = Math.max(1, ...data.map(valor));
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 6, height: alto }}>
      {data.map((d, i) => (
        <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4, minWidth: 0 }}>
          <div title={`${etiqueta(d)}: ${fmt(valor(d))}`}
            style={{ width: "100%", maxWidth: 36, height: `${(valor(d) / max) * (alto - 22)}px`, minHeight: 2, background: color, borderRadius: "4px 4px 0 0" }} />
          <div style={{ fontSize: 10, color: "var(--muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: "100%" }}>{etiqueta(d)}</div>
        </div>
      ))}
    </div>
  );
}

// Barras de doble serie (p. ej. ingresos vs egresos) sin librerías.
function MiniBarsDuo({ data, a, b, etiqueta, labelA, labelB, colorA = "#4F8A77", colorB = "#B4564E", alto = 130, fmt = money }) {
  const max = Math.max(1, ...data.map((d) => Math.max(a(d), b(d))));
  const h = (v) => `${(v / max) * (alto - 26)}px`;
  return (
    <div>
      <div style={{ display: "flex", gap: 16, marginBottom: 12, fontSize: 12, color: "var(--ink-soft)" }}>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}><span style={{ width: 10, height: 10, borderRadius: 2, background: colorA }} /> {labelA}</span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}><span style={{ width: 10, height: 10, borderRadius: 2, background: colorB }} /> {labelB}</span>
      </div>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 8, height: alto }}>
        {data.map((d, i) => (
          <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "flex-end", gap: 3, height: alto - 18 }}>
              <div title={`${labelA}: ${fmt(a(d))}`} style={{ width: 11, height: h(a(d)), minHeight: a(d) ? 2 : 0, background: colorA, borderRadius: "3px 3px 0 0" }} />
              <div title={`${labelB}: ${fmt(b(d))}`} style={{ width: 11, height: h(b(d)), minHeight: b(d) ? 2 : 0, background: colorB, borderRadius: "3px 3px 0 0" }} />
            </div>
            <div style={{ fontSize: 10, color: "var(--muted)", whiteSpace: "nowrap" }}>{etiqueta(d)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// Línea de evolución (sparkline) para una serie numérica.
function Sparkline({ valores, color = "#4F8A77", alto = 42, ancho = 200 }) {
  if (!valores || valores.length < 2) return null;
  const max = Math.max(...valores), min = Math.min(...valores), rango = max - min || 1;
  const pts = valores.map((v, i) => {
    const x = (i / (valores.length - 1)) * (ancho - 6) + 3;
    const y = alto - 3 - ((v - min) / rango) * (alto - 6);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return (
    <svg width={ancho} height={alto} style={{ display: "block" }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      {valores.map((v, i) => {
        const x = (i / (valores.length - 1)) * (ancho - 6) + 3;
        const y = alto - 3 - ((v - min) / rango) * (alto - 6);
        return <circle key={i} cx={x} cy={y} r="2.5" fill={color} />;
      })}
    </svg>
  );
}

function ConfigClinica({ showToast }) {
  const [cfg, setCfg] = useState(null);
  const [nombre, setNombre] = useState("");
  const [ciudad, setCiudad] = useState("");
  useEffect(() => {
    api.clinicaConfig().then((c) => { setCfg(c); setNombre(c.nombre); setCiudad(c.ciudad || ""); }).catch(() => {});
  }, []);
  async function guardar() {
    try { const c = await api.actualizarClinica({ nombre, ciudad }); setCfg(c); showToast("Datos de la clínica actualizados ✓"); }
    catch (e) { showToast("Error: " + e.message); }
  }
  if (!cfg) return null;
  const cambiado = nombre.trim() && (nombre !== cfg.nombre || ciudad !== (cfg.ciudad || ""));
  return (
    <>
      <h2 className="ca-secth" style={{ marginTop: 4 }}>Datos de la clínica</h2>
      <div className="ca-card" style={{ marginBottom: 26 }}>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end" }}>
          <div style={{ flex: 2, minWidth: 180 }}>
            <div className="ca-label">Nombre</div>
            <input className="ca-input" value={nombre} onChange={(e) => setNombre(e.target.value)} />
          </div>
          <div style={{ flex: 1, minWidth: 120 }}>
            <div className="ca-label">Ciudad</div>
            <input className="ca-input" value={ciudad} onChange={(e) => setCiudad(e.target.value)} />
          </div>
          <button className="ca-btn" style={{ opacity: cambiado ? 1 : 0.5, pointerEvents: cambiado ? "auto" : "none" }} onClick={guardar}>Guardar</button>
        </div>
      </div>
    </>
  );
}

function Gerencia({ showToast }) {
  const [periodo, setPeriodo] = useState("mes");
  const [data, setData] = useState(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    let vivo = true;
    setCargando(true);
    api.gerenciaResumen(periodo)
      .then((d) => { if (vivo) setData(d); })
      .catch((e) => showToast("Error: " + e.message))
      .finally(() => { if (vivo) setCargando(false); });
    return () => { vivo = false; };
  }, [periodo]);

  const op = data?.operacion, cap = data?.captacion, pac = data?.pacientes;

  return (
    <div>
      <div className="ca-tophead">
        <div>
          <h1 className="ca-h1">Gerencia</h1>
          <div className="ca-sub">
            {data ? `${data.periodo.label} · ${labelNumMes(data.periodo.desde)} – ${labelNumMes(data.periodo.hasta)}` : "Cargando…"}
          </div>
        </div>
        <div className="ca-seg">
          {[["hoy", "Hoy"], ["semana", "Semana"], ["mes", "Mes"]].map(([v, l]) => (
            <button key={v} className={periodo === v ? "on" : ""} onClick={() => setPeriodo(v)}>{l}</button>
          ))}
        </div>
      </div>

      {!data ? (
        <div className="ca-empty">{cargando ? "Cargando…" : "Sin datos."}</div>
      ) : (
        <div style={{ opacity: cargando ? 0.5 : 1, transition: "opacity .15s" }}>
          <h2 className="ca-secth" style={{ marginTop: 26 }}>Operación</h2>
          <div className="ca-stats">
            <StatCard label="Sesiones en el período" valor={op.citas} sub={data.anterior ? deltaTxt(op.citas, data.anterior.citas) : undefined} />
            <StatCard label="Atendidas" valor={op.atendidas} color="#4F8A77" />
            <StatCard label="% Asistencia" valor={`${op.asistencia_pct}%`} sub={`${op.cancelacion_pct}% canceladas`} color={op.asistencia_pct >= 80 ? "#4F8A77" : "#B4564E"} />
            <StatCard label="Recordatorios enviados" valor={op.recordatorios} />
          </div>

          {op.por_dia && op.por_dia.length > 1 && (
            <div className="ca-card" style={{ marginTop: 14 }}>
              <div className="ca-label" style={{ marginBottom: 10 }}>Sesiones por día</div>
              <MiniBars data={op.por_dia} valor={(d) => d.citas} etiqueta={(d) => dDeISO(d.fecha).getDate()}
                color="#6E86A8" fmt={(n) => `${n} ${n === 1 ? "sesión" : "sesiones"}`} />
            </div>
          )}

          <h2 className="ca-secth" style={{ marginTop: 28 }}>Captación</h2>
          <div className="ca-stats">
            <StatCard label="Leads recibidos" valor={cap.recibidos} sub={`${cap.pauta_pct}% de pauta`} />
            <StatCard label="Cierres (iniciaron)" valor={cap.cierres} color="#4F8A77" />
            <StatCard label="Tasa de cierre" valor={`${cap.tasa_cierre}%`} color={cap.tasa_cierre >= 15 ? "#4F8A77" : "#C9923A"} />
            <StatCard label="Mejor fuente" valor={cap.top_fuente} />
          </div>
          <div style={{ fontSize: 12.5, color: "var(--muted)", marginTop: 6 }}>
            Mejor campaña del período: <strong>{cap.top_campania}</strong>.
          </div>

          <h2 className="ca-secth" style={{ marginTop: 28 }}>Pacientes</h2>
          <div className="ca-stats">
            <StatCard label="Pacientes totales" valor={pac.total} />
            <StatCard label="Nuevos en el período" valor={pac.nuevos} color="#4F8A77" />
            <StatCard label="Sin próxima sesión" valor={pac.sin_proxima} sub="para reactivar" color={pac.sin_proxima > 0 ? "#C9923A" : "#4F8A77"} />
          </div>

          {data.demografia && (
            <div className="ca-demo">
              <div>
                <h2 className="ca-secth" style={{ marginTop: 24 }}>Pacientes por género</h2>
                <div className="ca-card"><BarrasH data={data.demografia.genero.filter((d) => d.valor > 0)} colorPor={GEN_COLOR} /></div>
              </div>
              <div>
                <h2 className="ca-secth" style={{ marginTop: 24 }}>Pacientes por edad</h2>
                <div className="ca-card"><BarrasH data={data.demografia.edad} color="#6E86A8" /></div>
              </div>
            </div>
          )}

          <h2 className="ca-secth" style={{ marginTop: 28 }}>Dinero</h2>
          <div className="ca-stats">
            <StatCard label="Ingresos (cobrado)" valor={money(data.finanzas?.cobrado || 0)} color="#4F8A77"
              sub={data.anterior ? deltaTxt(data.finanzas?.cobrado || 0, data.anterior.cobrado) : undefined} />
            <StatCard label="Egresos (gastos)" valor={money(data.finanzas?.egresos || 0)} color="#B4564E" />
            <StatCard label="Utilidad (neto)" valor={money(data.finanzas?.utilidad || 0)}
              color={(data.finanzas?.utilidad || 0) >= 0 ? "#3E7A65" : "#B4564E"} />
            <StatCard label="Pendiente por cobrar" valor={money(data.finanzas?.pendiente || 0)} color={(data.finanzas?.pendiente || 0) > 0 ? "#C9923A" : "#7C7870"} />
          </div>

          <h2 className="ca-secth" style={{ marginTop: 28 }}>Productividad por médico</h2>
          <table className="ca-tbl">
            <thead>
              <tr>
                <th>Médico</th>
                <th className="num">Sesiones</th>
                <th className="num">Atenciones</th>
                <th className="num">Leads</th>
                <th className="num">Cierres</th>
              </tr>
            </thead>
            <tbody>
              {data.productividad.length === 0 ? (
                <tr><td colSpan={5} style={{ color: "var(--muted)" }}>Sin actividad en el período.</td></tr>
              ) : data.productividad.map((m) => (
                <tr key={m.medico}>
                  <td style={{ fontWeight: 500 }}>{m.medico}</td>
                  <td className="num">{m.citas}</td>
                  <td className="num">{m.atenciones}</td>
                  <td className="num">{m.leads}</td>
                  <td className="num">{m.cierres}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>
            Panel visible solo para gerencia. Todos los números son reales del período seleccionado.
          </div>
        </div>
      )}
    </div>
  );
}

function Hoy({ proximas, citasHoy, porConfirmar, atendidas, onOpen, onGo, onRetencion, cumple, esAdmin }) {
  const [r, setR] = useState(null);
  useEffect(() => { api.hoy().then(setR).catch(() => {}); }, []);
  return (
    <>
      <h1 className="ca-h1">Buenos días 🌞</h1>
      <div className="ca-sub">{labelLargo(HOY_ISO)} · Aquí está tu día, sin sorpresas.</div>

      <div className="ca-glance">
        <button className="ca-gcard" onClick={() => onGo("agenda")}>
          <div className="ca-ghead"><Calendar size={14} strokeWidth={2} /> Agenda</div>
          <div className="ca-gmain">{citasHoy} sesiones hoy</div>
          <div className="ca-gsub">{atendidas} atendidas · {citasHoy - atendidas} por venir</div>
        </button>
        <button className="ca-gcard" onClick={() => onGo("marketing")}>
          <div className="ca-ghead"><Megaphone size={14} strokeWidth={2} /> Captación</div>
          <div className="ca-gmain">{r ? `${r.leads_nuevos} leads` : "…"}</div>
          <div className="ca-gsub">{r ? `nuevos sin contactar · ${r.leads_hoy} hoy` : "cargando…"}</div>
        </button>
        {esAdmin ? (
          <button className="ca-gcard" onClick={() => onGo("finanzas")}>
            <div className="ca-ghead"><TrendingUp size={14} strokeWidth={2} /> Ingresos hoy</div>
            <div className="ca-gmain">{r && r.ingresos_hoy != null ? money(r.ingresos_hoy) : "…"}</div>
            <div className="ca-gsub">{r && r.pendiente_hoy ? `${money(r.pendiente_hoy)} por cobrar` : "cobrado hoy"}</div>
          </button>
        ) : (
          <button className="ca-gcard" onClick={() => onGo("agenda")}>
            <div className="ca-ghead"><Clock size={14} strokeWidth={2} /> Por confirmar</div>
            <div className="ca-gmain">{porConfirmar} sesiones</div>
            <div className="ca-gsub">pendientes de confirmar hoy</div>
          </button>
        )}
        <button className="ca-gcard" onClick={onRetencion} style={{ borderColor: "#F0DDBF" }}>
          <div className="ca-ghead" style={{ color: "#B0822F" }}><AlertTriangle size={14} strokeWidth={2} /> Retención</div>
          <div className="ca-gmain">{r ? `${r.sin_proxima} pacientes` : "…"}</div>
          <div className="ca-gsub">sin próxima sesión · reactivar</div>
        </button>
      </div>

      {cumple && cumple.length > 0 && (
        <div className="ca-card" style={{ marginBottom: 18, borderColor: "#EAD9F2", background: "#FBF7FE" }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>🎂 Cumpleaños de hoy</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {cumple.map((p) => (
              <button key={p.id} className="ca-mini" onClick={() => onOpen(p.id)}>{p.nombre}{p.edad != null ? ` · ${p.edad} años` : ""}</button>
            ))}
          </div>
          <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 8 }}>Un saludo por WhatsApp fideliza. Abre la ficha para enviarlo.</div>
        </div>
      )}

      <h2 className="ca-secth">Próximas sesiones</h2>
      {proximas.length === 0 ? (
        <div className="ca-empty">Todo atendido por hoy. Buen trabajo 🌿</div>
      ) : (
        proximas.map((c) => (
          <div key={c.id} className="ca-row">
            <div className="ca-time"><Clock size={13} strokeWidth={2} style={{ color: "var(--muted)" }} />{c.hora}</div>
            <div style={{ flex: 1 }}>
              <button className="ca-pnamebtn" onClick={() => onOpen(c.pacienteId)}>{c.paciente}</button>
              <div className="ca-pmeta">{c.medico}</div>
            </div>
            <SpecialtyTag name={c.especialidad} />
          </div>
        ))
      )}
    </>
  );
}

// --- Helpers de la historia clínica ---
const numeroLimpio = (s) => { const n = Number(s); return Number.isFinite(n) ? String(n) : s; };

function vitalesDe(h) {
  const v = [];
  if (h.presion_arterial) v.push(["PA", h.presion_arterial]);
  if (h.frecuencia_cardiaca != null) v.push(["FC", `${h.frecuencia_cardiaca} lpm`]);
  if (h.temperatura != null) v.push(["T°", `${numeroLimpio(h.temperatura)} °C`]);
  if (h.peso != null) v.push(["Peso", `${numeroLimpio(h.peso)} kg`]);
  if (h.talla != null) v.push(["Talla", `${h.talla} cm`]);
  return v;
}

function Campo({ etiqueta, children }) {
  return (
    <div className="ca-hcampo"><span className="ca-hlabel">{etiqueta}:</span><span className="ca-hval">{children}</span></div>
  );
}

function AntItem({ icon: Icon, label, valor, alerta }) {
  const vacio = !valor || !valor.trim();
  const color = vacio ? "var(--muted)" : (alerta ? "#9C4646" : "var(--ink)");
  return (
    <div>
      <div className="ca-antlabel"><Icon size={14} strokeWidth={2} style={{ color: alerta && !vacio ? "#9C4646" : "var(--muted)" }} /> {label}</div>
      <div className="ca-antval" style={{ color, whiteSpace: "pre-wrap" }}>{vacio ? "—" : valor}</div>
    </div>
  );
}

function UploaderAdjunto({ onSubir }) {
  const [subiendo, setSubiendo] = useState(false);
  async function elegir(e) {
    const f = e.target.files[0];
    e.target.value = "";
    if (!f) return;
    setSubiendo(true);
    try { await onSubir(f); } finally { setSubiendo(false); }
  }
  return (
    <label className="ca-upload" style={{ opacity: subiendo ? 0.6 : 1, pointerEvents: subiendo ? "none" : "auto" }}>
      <Paperclip size={14} strokeWidth={2} /> {subiendo ? "Subiendo…" : "Adjuntar archivo"}
      <input type="file" hidden onChange={elegir} />
    </label>
  );
}

function AdjuntoRow({ a, puedeEliminar, onEliminar }) {
  return (
    <div className="ca-adjrow">
      <FileText size={16} strokeWidth={1.9} style={{ color: "var(--accent)", flexShrink: 0 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="ca-adjname">{a.nombre}</div>
        <div className="ca-pmeta">{a.fecha}{a.subido_por ? ` · ${a.subido_por}` : ""}{a.tipo ? ` · ${a.tipo.toUpperCase()}` : ""}</div>
      </div>
      <a className="ca-mini" style={{ textDecoration: "none" }} href={api.urlAdjunto(a.id)} target="_blank" rel="noreferrer" download>
        <Download size={13} strokeWidth={2} /> Descargar
      </a>
      {puedeEliminar && (
        <button className="ca-iconbtn" title="Eliminar archivo" onClick={() => onEliminar(a.id)}><Trash2 size={14} strokeWidth={2} /></button>
      )}
    </div>
  );
}

function Ficha({ p, onBack, onEdit, onWhatsApp, onSubirAdjunto, onEliminarAdjunto, puedeEliminar, clinica, onAgendar }) {
  return (
    <div>
      <button className="ca-back" onClick={onBack}><ChevronLeft size={16} strokeWidth={2} /> Pacientes</button>
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 22 }}>
        <div className="ca-avatar" style={{ width: 52, height: 52, fontSize: 18, borderRadius: 13 }}>{iniciales(p.nombre)}</div>
        <div style={{ flex: 1 }}>
          <h1 className="ca-h1" style={{ fontSize: 22 }}>{p.nombre}</h1>
          <div style={{ marginTop: 7 }}><SpecialtyTag name={p.especialidad} /></div>
        </div>
        <button className="ca-mini" onClick={onAgendar}><Calendar size={13} strokeWidth={2} /> Agendar</button>
        <button className="ca-mini wa" onClick={onWhatsApp}><MessageCircle size={13} strokeWidth={2} /> WhatsApp</button>
        <button className="ca-mini" onClick={() => imprimirHistoria(p, clinica)}><FileText size={13} strokeWidth={2} /> Imprimir</button>
        <button className="ca-mini" onClick={onEdit}><Pencil size={13} strokeWidth={2} /> Editar</button>
      </div>

      <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginBottom: 26 }}>
        <div className="ca-field"><Cake size={15} strokeWidth={1.9} style={{ color: "var(--muted)" }} /> {p.edad != null ? `${p.edad} años` : "Edad no registrada"}{p.genero_label ? ` · ${p.genero_label}` : ""}</div>
        {p.numero_documento && <div className="ca-field"><FileText size={15} strokeWidth={1.9} style={{ color: "var(--muted)" }} /> {p.tipo_documento_label} {p.numero_documento}</div>}
        <div className="ca-field"><Phone size={15} strokeWidth={1.9} style={{ color: "var(--muted)" }} /> {p.tel || "Sin teléfono"}</div>
        {p.direccion && <div className="ca-field"><MapPin size={15} strokeWidth={1.9} style={{ color: "var(--muted)" }} /> {p.direccion}</div>}
        <div className="ca-field"><Clock size={15} strokeWidth={1.9} style={{ color: "var(--muted)" }} /> Última visita: {p.ultima}</div>
        {p.proxima && (
          <div className="ca-field" style={{ color: "var(--accent)" }}><Calendar size={15} strokeWidth={1.9} /> Próxima: {p.proxima.fecha} · {p.proxima.hora}</div>
        )}
      </div>

      {(() => {
        const pesos = [...p.historial].reverse().filter((h) => h.peso != null).map((h) => Number(h.peso));
        if (pesos.length < 2) return null;
        return (
          <div className="ca-card" style={{ marginBottom: 26, display: "flex", alignItems: "center", gap: 22, flexWrap: "wrap" }}>
            <div>
              <div className="ca-antlabel"><Activity size={14} strokeWidth={2} style={{ color: "var(--muted)" }} /> Evolución de peso</div>
              <div style={{ fontSize: 20, fontWeight: 600, marginTop: 4 }}>{numeroLimpio(pesos[pesos.length - 1])} kg <span style={{ fontSize: 12, color: "var(--muted)", fontWeight: 400 }}>último</span></div>
            </div>
            <Sparkline valores={pesos} />
          </div>
        );
      })()}

      <h2 className="ca-secth">Antecedentes</h2>
      <div className="ca-card" style={{ marginBottom: 26 }}>
        <div className="ca-anteced">
          <AntItem icon={AlertTriangle} label="Alergias" valor={p.alergias} alerta />
          <AntItem icon={HeartPulse} label="Antecedentes / condiciones" valor={p.antecedentes} />
          <AntItem icon={Pill} label="Medicación habitual" valor={p.medicacion_habitual} />
        </div>
        <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 14 }}>Edita los antecedentes desde el botón «Editar» del paciente.</div>
      </div>

      {p.cuenta && (p.cuenta.items.length > 0 || p.cuenta.pendiente > 0) && (
        <>
          <h2 className="ca-secth">Estado de cuenta</h2>
          <div className="ca-card" style={{ marginBottom: 26 }}>
            <div style={{ display: "flex", gap: 28, flexWrap: "wrap", marginBottom: p.cuenta.items.length ? 12 : 0 }}>
              <div><div style={{ fontSize: 20, fontWeight: 600, color: "#4F8A77" }}>{money(p.cuenta.cobrado)}</div><div className="ca-pmeta">Pagado</div></div>
              <div><div style={{ fontSize: 20, fontWeight: 600, color: p.cuenta.pendiente > 0 ? "#C9923A" : "var(--muted)" }}>{money(p.cuenta.pendiente)}</div><div className="ca-pmeta">Pendiente</div></div>
            </div>
            {p.cuenta.items.map((c) => (
              <div key={c.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 0", borderTop: "1px solid var(--line)", fontSize: 13.5 }}>
                <span style={{ color: "var(--muted)", width: 86, flexShrink: 0 }}>{c.fecha}</span>
                <span style={{ flex: 1, minWidth: 0 }}>{c.concepto}</span>
                <span style={{ fontVariantNumeric: "tabular-nums", fontWeight: 500 }}>{money(c.monto)}</span>
                <Tag colors={ESTADO_COBRO_COLOR[c.estado]}>{c.estado === "pagado" ? (c.medio || "Pagado") : "Pendiente"}</Tag>
              </div>
            ))}
          </div>
        </>
      )}

      <h2 className="ca-secth">Historia clínica</h2>
      <div className="ca-card">
        {p.historial.length === 0 ? (
          <div style={{ color: "var(--muted)", fontSize: 14 }}>Aún no hay atenciones registradas. Aparecerán aquí después de la primera consulta.</div>
        ) : (
          <div className="ca-hist">
            {p.historial.map((h, i) => (
              <div key={h.id ?? i} className={`ca-histitem ${h.fecha === HOY_FECHA && i === 0 ? "nuevo" : ""}`}>
                <div style={{ fontSize: 12.5, color: "var(--muted)", marginBottom: 6 }}>{h.fecha} · {h.medico || "—"}{h.especialidad ? ` · ${h.especialidad}` : ""}</div>
                {h.motivo && <Campo etiqueta="Motivo">{h.motivo}</Campo>}
                {vitalesDe(h).length > 0 && (
                  <div className="ca-vitales">
                    {vitalesDe(h).map(([k, val]) => <span key={k} className="ca-vital"><b>{k}</b> {val}</span>)}
                  </div>
                )}
                {h.diagnostico && <Campo etiqueta="Diagnóstico">{h.diagnostico}</Campo>}
                {h.indicaciones && <Campo etiqueta="Indicaciones">{h.indicaciones}</Campo>}
                {h.nota && <div className="ca-histnota" style={{ marginTop: 6 }}>{h.nota}</div>}
                {h.adjuntos && h.adjuntos.length > 0 && (
                  <div style={{ marginTop: 8, display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {h.adjuntos.map((a) => (
                      <a key={a.id} className="ca-adjchip" href={api.urlAdjunto(a.id)} target="_blank" rel="noreferrer" download>
                        <Paperclip size={11} strokeWidth={2} /> {a.nombre}
                      </a>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <h2 className="ca-secth" style={{ marginTop: 28 }}>Archivos adjuntos</h2>
      <div className="ca-card">
        <UploaderAdjunto onSubir={onSubirAdjunto} />
        <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 9 }}>Laboratorios, ecografías, PDFs o imágenes. Máx. 25 MB. Descarga protegida (solo personal de la clínica).</div>
        {p.adjuntos.length === 0 ? (
          <div style={{ color: "var(--muted)", fontSize: 14, marginTop: 14 }}>Aún no hay archivos para este paciente.</div>
        ) : (
          <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 8 }}>
            {p.adjuntos.map((a) => <AdjuntoRow key={a.id} a={a} puedeEliminar={puedeEliminar} onEliminar={onEliminarAdjunto} />)}
          </div>
        )}
      </div>
    </div>
  );
}

function AgendarModal({ pacientes, fechaInicial, pacienteFijo, onClose, onSave }) {
  const [busca, setBusca] = useState("");
  const [sel, setSel] = useState(pacienteFijo || null);
  const [nuevo, setNuevo] = useState(false);
  const [fecha, setFecha] = useState(fechaInicial || HOY_ISO);
  const [hora, setHora] = useState("");
  const [esp, setEsp] = useState(pacienteFijo?.especialidad || "Terapia individual");

  const matches = useMemo(
    () => (busca.trim() ? pacientes.filter((p) => p.nombre.toLowerCase().includes(busca.toLowerCase())).slice(0, 4) : []),
    [busca, pacientes]
  );

  function elegir(p) { setSel(p); setNuevo(false); setEsp(p.especialidad || "Terapia individual"); setBusca(""); }
  function elegirNuevo() { setNuevo(true); setSel(null); }
  function limpiar() { setSel(null); setNuevo(false); setBusca(""); }

  const canSave = (sel || (nuevo && busca.trim())) && fecha && hora.trim();

  function guardar() {
    if (sel) onSave({ pacienteId: sel.id, paciente: sel.nombre, especialidad: esp, fecha, hora });
    else if (nuevo) onSave({ nuevoNombre: busca.trim(), especialidad: esp, fecha, hora });
  }

  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 390 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <strong style={{ fontSize: 16 }}>Nueva sesión</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>

        <div style={{ marginBottom: 13 }}>
          <div className="ca-label">Paciente</div>
          {sel ? (
            <div className="ca-chipsel">
              <div className="ca-avatar" style={{ width: 28, height: 28, fontSize: 11 }}>{iniciales(sel.nombre)}</div>
              <div style={{ fontSize: 14, fontWeight: 500 }}>{sel.nombre}</div>
              {!pacienteFijo && <button className="ca-link" onClick={limpiar}>cambiar</button>}
            </div>
          ) : nuevo ? (
            <div className="ca-chipsel">
              <UserPlus size={16} strokeWidth={2} style={{ color: "var(--accent)" }} />
              <div style={{ fontSize: 14, fontWeight: 500 }}>{busca.trim()} <span style={{ color: "var(--muted)", fontWeight: 400 }}>· nuevo</span></div>
              <button className="ca-link" onClick={limpiar}>cambiar</button>
            </div>
          ) : (
            <>
              <input className="ca-input" value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar paciente por nombre…" autoFocus />
              {busca.trim() && (
                <div className="ca-pick">
                  {matches.map((p) => (
                    <div key={p.id} className="ca-pickrow" onClick={() => elegir(p)}>
                      <div className="ca-avatar" style={{ width: 28, height: 28, fontSize: 11 }}>{iniciales(p.nombre)}</div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 14, fontWeight: 500 }}>{p.nombre}</div>
                        <div className="ca-pmeta">{p.edad != null ? `${p.edad} años · ` : ""}{p.especialidad}</div>
                      </div>
                    </div>
                  ))}
                  <div className="ca-newrow" onClick={elegirNuevo}>
                    <UserPlus size={15} strokeWidth={2} /> Crear paciente nuevo: “{busca.trim()}”
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
          <div style={{ flex: 1.3 }}>
            <div className="ca-label">Fecha</div>
            <input className="ca-input" type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
          </div>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Hora</div>
            <input className="ca-input" type="time" value={hora} onChange={(e) => setHora(e.target.value)} placeholder="14:30" />
          </div>
        </div>
        <div style={{ marginBottom: 20 }}>
          <div className="ca-label">Especialidad</div>
          <select className="ca-input" value={esp} onChange={(e) => setEsp(e.target.value)}>
            {Object.keys(SPECIALTY).map((s) => <option key={s}>{s}</option>)}
          </select>
        </div>

        <div style={{ display: "flex", gap: 9, justifyContent: "flex-end" }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" style={{ opacity: canSave ? 1 : 0.5, pointerEvents: canSave ? "auto" : "none" }} onClick={guardar}>
            Agendar
          </button>
        </div>
      </div>
    </div>
  );
}

function CitaRow({ c, esAsistente, onAtender, onRecordar, onReagendar, onCancelar, onConfirmar, onCobrar, openFicha }) {
  const activa = c.estado !== "atendida" && c.estado !== "cancelada";
  return (
    <div className="ca-row">
      <div className="ca-time"><Clock size={13} strokeWidth={2} style={{ color: "var(--muted)" }} />{c.hora}</div>
      <div style={{ flex: 1, minWidth: 150 }}>
        <button className="ca-pnamebtn" onClick={() => openFicha(c.pacienteId)}>{c.paciente}</button>
        <div className="ca-pmeta">{c.medico}</div>
      </div>
      <SpecialtyTag name={c.especialidad} />
      <Tag colors={STATUS[c.estado]}>{c.estado_label}</Tag>
      <div className="ca-actions">
        {c.estado === "por_confirmar" && (
          <button className="ca-mini" onClick={() => onConfirmar(c)} title="Marcar confirmada"><Check size={13} strokeWidth={2.2} /> Confirmar</button>
        )}
        {c.estado === "por_confirmar" && (c.recordado ? (
          <span className="ca-mini done"><Check size={13} strokeWidth={2.4} /> Recordado</span>
        ) : (
          <button className="ca-mini wa" onClick={() => onRecordar(c)}><MessageCircle size={13} strokeWidth={2} /> Recordar</button>
        ))}
        {activa && !esAsistente && (
          <button className="ca-mini" onClick={() => onAtender(c)}><Stethoscope size={13} strokeWidth={2} /> Atender</button>
        )}
        {c.estado === "atendida" && (c.cobrada ? (
          <span className="ca-mini done"><Check size={13} strokeWidth={2.4} /> Cobrada</span>
        ) : (
          <button className="ca-mini" onClick={() => onCobrar(c)} title="Registrar cobro"><Receipt size={13} strokeWidth={2} /> Cobrar</button>
        ))}
        {activa && (
          <>
            <button className="ca-mini" onClick={() => onReagendar(c)} title="Reagendar"><Calendar size={13} strokeWidth={2} /> Mover</button>
            <button className="ca-iconbtn" onClick={() => onCancelar(c)} title="Cancelar sesión"><X size={14} strokeWidth={2} /></button>
          </>
        )}
      </div>
    </div>
  );
}

function Agenda({ citas, fecha, setFecha, vista, setVista, esAsistente, onAgendar, onAtender, onRecordar, onReagendar, onCancelar, onConfirmar, onCobrar, openFicha }) {
  const [filtroMedico, setFiltroMedico] = useState("");
  const medicos = useMemo(() => [...new Set(citas.map((c) => c.medico).filter(Boolean))].sort(), [citas]);
  const semana = vista === "semana" ? semanaDe(fecha) : null;
  const delDia = (iso) => citas
    .filter((c) => c.fecha === iso && (!filtroMedico || c.medico === filtroMedico))
    .sort((a, b) => a.hora.localeCompare(b.hora));
  const visibles = vista === "semana" ? citas.filter((c) => semana.includes(c.fecha)) : delDia(fecha);
  const activas = visibles.filter((c) => c.estado !== "cancelada");
  const subt = vista === "semana" ? `${labelNumMes(semana[0])} – ${labelNumMes(semana[6])}` : labelLargo(fecha);
  const paso = vista === "semana" ? 7 : 1;

  return (
    <>
      <div className="ca-tophead">
        <div>
          <h1 className="ca-h1">Agenda</h1>
          <div className="ca-sub">{subt} · {activas.length} {activas.length === 1 ? "sesión" : "sesiones"}</div>
        </div>
        <button className="ca-btn" onClick={onAgendar}><Plus size={16} strokeWidth={2.2} /> Agendar sesión</button>
      </div>

      <div className="ca-agnav">
        <div className="ca-navgrp">
          <button className="ca-navbtn" onClick={() => setFecha(sumarDias(fecha, -paso))} aria-label="Anterior"><ChevronLeft size={16} strokeWidth={2.2} /></button>
          <button className={`ca-navbtn ${fecha === HOY_ISO ? "on" : ""}`} onClick={() => setFecha(HOY_ISO)}>Hoy</button>
          <button className="ca-navbtn" onClick={() => setFecha(sumarDias(fecha, paso))} aria-label="Siguiente"><ChevronLeft size={16} strokeWidth={2.2} style={{ transform: "rotate(180deg)" }} /></button>
        </div>
        <input className="ca-datein" type="date" value={fecha} onChange={(e) => e.target.value && setFecha(e.target.value)} />
        {medicos.length > 1 && (
          <select className="ca-datein" value={filtroMedico} onChange={(e) => setFiltroMedico(e.target.value)}>
            <option value="">Todos los médicos</option>
            {medicos.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        )}
        <div className="ca-seg">
          <button className={vista === "dia" ? "on" : ""} onClick={() => setVista("dia")}>Día</button>
          <button className={vista === "semana" ? "on" : ""} onClick={() => setVista("semana")}>Semana</button>
        </div>
      </div>

      {vista === "dia" ? (
        <div style={{ marginTop: 18 }}>
          {delDia(fecha).length === 0 ? (
            <div className="ca-empty">No hay sesiones para este día. Usa «Agendar sesión» para reservar una.</div>
          ) : (
            delDia(fecha).map((c) => (
              <CitaRow key={c.id} c={c} esAsistente={esAsistente}
                onAtender={onAtender} onRecordar={onRecordar} onReagendar={onReagendar}
                onCancelar={onCancelar} onConfirmar={onConfirmar} onCobrar={onCobrar} openFicha={openFicha} />
            ))
          )}
        </div>
      ) : (
        <div className="ca-wk">
          {semana.map((iso) => (
            <div key={iso} className={`ca-wkcol ${iso === HOY_ISO ? "hoy" : ""}`}>
              <div className="ca-wkhd" onClick={() => { setFecha(iso); setVista("dia"); }}>
                <div className="d">{labelDiaSemana(iso)}</div>
                <div className="n">{dDeISO(iso).getDate()}</div>
              </div>
              {delDia(iso).length === 0 ? (
                <div className="ca-wkempty">·</div>
              ) : (
                delDia(iso).map((c) => {
                  const col = STATUS[c.estado] || STATUS.por_confirmar;
                  return (
                    <div key={c.id} className={`ca-evt ${c.estado === "cancelada" ? "cancel" : ""}`}
                      style={{ background: col.bg, borderLeftColor: col.fg }}
                      onClick={() => { setFecha(iso); setVista("dia"); }} title={`${c.hora} · ${c.paciente} · ${c.especialidad}`}>
                      <div className="h" style={{ color: col.fg }}>{c.hora}</div>
                      <div className="p">{c.paciente}</div>
                    </div>
                  );
                })
              )}
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function ReagendarModal({ cita, onClose, onSave }) {
  const [fecha, setFecha] = useState(cita.fecha || HOY_ISO);
  const [hora, setHora] = useState(cita.hora || "");
  const canSave = fecha && hora.trim();
  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 380 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <strong style={{ fontSize: 16 }}>Reagendar sesión</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>
        <div className="ca-chipsel" style={{ marginBottom: 14 }}>
          <div className="ca-avatar" style={{ width: 28, height: 28, fontSize: 11 }}>{iniciales(cita.paciente)}</div>
          <div style={{ fontSize: 14, fontWeight: 500 }}>{cita.paciente}</div>
          <span style={{ fontSize: 12.5, color: "var(--muted)", marginLeft: "auto" }}>antes: {labelNumMes(cita.fecha)} {cita.hora}</span>
        </div>
        <div style={{ display: "flex", gap: 11, marginBottom: 16 }}>
          <div style={{ flex: 1.3 }}>
            <div className="ca-label">Nueva fecha</div>
            <input className="ca-input" type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
          </div>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Nueva hora</div>
            <input className="ca-input" type="time" value={hora} onChange={(e) => setHora(e.target.value)} />
          </div>
        </div>
        <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 16 }}>La sesión volverá a «Por confirmar» para que puedas avisar de nuevo al paciente.</div>
        <div style={{ display: "flex", gap: 9, justifyContent: "flex-end" }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" style={{ opacity: canSave ? 1 : 0.5, pointerEvents: canSave ? "auto" : "none" }} onClick={() => onSave(cita, fecha, hora.trim())}>Reagendar</button>
        </div>
      </div>
    </div>
  );
}

function ConfirmModal({ titulo, mensaje, confirmLabel, peligro, onConfirm, onClose }) {
  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 380 }} onClick={(e) => e.stopPropagation()}>
        <strong style={{ fontSize: 16 }}>{titulo}</strong>
        <div style={{ fontSize: 14, color: "var(--ink-soft)", lineHeight: 1.55, margin: "12px 0 20px" }}>{mensaje}</div>
        <div style={{ display: "flex", gap: 9, justifyContent: "flex-end" }}>
          <button className="ca-btn ghost" onClick={onClose}>Volver</button>
          <button className="ca-btn" style={peligro ? { background: "#9C4646" } : undefined} onClick={onConfirm}>{confirmLabel || "Confirmar"}</button>
        </div>
      </div>
    </div>
  );
}

function AtenderModal({ cita, servicios, onClose, onSave }) {
  const [motivo, setMotivo] = useState("");
  const [pa, setPa] = useState("");
  const [fc, setFc] = useState("");
  const [temp, setTemp] = useState("");
  const [peso, setPeso] = useState("");
  const [talla, setTalla] = useState("");
  const [diag, setDiag] = useState("");
  const [indic, setIndic] = useState("");
  const [nota, setNota] = useState("");
  const [tplEsp, setTplEsp] = useState(cita.especialidad in TEMPLATES ? cita.especialidad : "Terapia individual");

  const serviciosActivos = (servicios || []).filter((s) => s.activo);
  const servDef = serviciosActivos.find((s) => s.especialidad === cita.especialidad);
  const [cobrar, setCobrar] = useState(false);
  const [cobServicio, setCobServicio] = useState(servDef ? String(servDef.id) : "");
  const [cobMonto, setCobMonto] = useState(servDef ? String(servDef.precio) : "");
  const [cobEstado, setCobEstado] = useState("pagado");
  const [cobMedio, setCobMedio] = useState("efectivo");

  const canSave = [motivo, diag, indic, nota].some((v) => v.trim().length > 0);

  function insertarPlantilla() {
    const t = TEMPLATES[tplEsp] || "";
    setNota((prev) => (prev.trim() ? prev + "\n\n" + t : t));
  }

  function guardar() {
    const datos = {
      motivo: motivo.trim(),
      presion_arterial: pa.trim(),
      frecuencia_cardiaca: fc.trim(),
      temperatura: temp.trim(),
      peso: peso.trim(),
      talla: talla.trim(),
      diagnostico: diag.trim(),
      indicaciones: indic.trim(),
      nota: nota.trim(),
    };
    if (cobrar && cobMonto && Number(cobMonto) > 0) {
      datos.cobro_monto = cobMonto;
      datos.cobro_servicio = cobServicio || null;
      datos.cobro_estado = cobEstado;
      datos.cobro_medio = cobEstado === "pagado" ? cobMedio : "";
    }
    onSave(datos);
  }

  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 520 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
          <strong style={{ fontSize: 16 }}>Atender a {cita.paciente}</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>
        <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
          <SpecialtyTag name={cita.especialidad} />
          <span style={{ fontSize: 13, color: "var(--muted)", alignSelf: "center" }}>{cita.hora} · {cita.medico}</span>
        </div>

        <div style={{ marginBottom: 14 }}>
          <div className="ca-label">Motivo de consulta</div>
          <input className="ca-input" value={motivo} onChange={(e) => setMotivo(e.target.value)}
            placeholder="¿Por qué viene el paciente?" autoFocus />
        </div>

        <div className="ca-label" style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <Activity size={13} strokeWidth={2} style={{ color: "var(--muted)" }} /> Signos vitales <span style={{ color: "var(--muted)", fontWeight: 400 }}>· opcional</span>
        </div>
        <div className="ca-vitgrid" style={{ marginTop: 6 }}>
          <label className="ca-vitin"><span>P. arterial</span><input className="ca-input" value={pa} onChange={(e) => setPa(e.target.value)} placeholder="120/80" /></label>
          <label className="ca-vitin"><span>FC (lpm)</span><input className="ca-input" value={fc} onChange={(e) => setFc(e.target.value)} placeholder="72" inputMode="numeric" /></label>
          <label className="ca-vitin"><span>Temp (°C)</span><input className="ca-input" value={temp} onChange={(e) => setTemp(e.target.value)} placeholder="36.5" inputMode="decimal" /></label>
          <label className="ca-vitin"><span>Peso (kg)</span><input className="ca-input" value={peso} onChange={(e) => setPeso(e.target.value)} placeholder="70" inputMode="decimal" /></label>
          <label className="ca-vitin"><span>Talla (cm)</span><input className="ca-input" value={talla} onChange={(e) => setTalla(e.target.value)} placeholder="170" inputMode="numeric" /></label>
        </div>

        <div style={{ margin: "16px 0 13px" }}>
          <div className="ca-label">Diagnóstico</div>
          <textarea className="ca-input" style={{ minHeight: 60, resize: "vertical", lineHeight: 1.5 }} value={diag} onChange={(e) => setDiag(e.target.value)} placeholder="Impresión diagnóstica…" />
        </div>
        <div style={{ marginBottom: 13 }}>
          <div className="ca-label">Indicaciones / receta</div>
          <textarea className="ca-input" style={{ minHeight: 60, resize: "vertical", lineHeight: 1.5 }} value={indic} onChange={(e) => setIndic(e.target.value)} placeholder="Medicamentos, dosis, recomendaciones…" />
        </div>

        <div className="ca-label">Nota / evolución</div>
        <div className="ca-tplbar">
          <button className="ca-tplchip" onClick={insertarPlantilla}><FileText size={13} strokeWidth={2} /> Insertar plantilla</button>
          <select className="ca-tplsel" value={tplEsp} onChange={(e) => setTplEsp(e.target.value)}>
            {Object.keys(TEMPLATES).map((s) => <option key={s}>{s}</option>)}
          </select>
        </div>
        <textarea className="ca-input ca-textarea" style={{ minHeight: 110 }} value={nota} onChange={(e) => setNota(e.target.value)}
          placeholder="Evolución, observaciones… o inserta una plantilla para no empezar de cero." />
        <div style={{ fontSize: 12, color: "var(--muted)", margin: "8px 0 14px" }}>Se guarda en la historia clínica con fecha de hoy. Llena al menos motivo, diagnóstico, indicaciones o nota.</div>

        <div style={{ border: "1px solid var(--line)", borderRadius: 10, padding: "11px 13px", marginBottom: 16 }}>
          <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 13.5, fontWeight: 500 }}>
            <input type="checkbox" checked={cobrar} onChange={(e) => setCobrar(e.target.checked)} />
            <Receipt size={14} strokeWidth={2} style={{ color: "var(--accent)" }} /> Registrar cobro de esta atención
          </label>
          {cobrar && (
            <div style={{ marginTop: 12 }}>
              <div style={{ display: "flex", gap: 10, marginBottom: 10 }}>
                <div style={{ flex: 1.4 }}>
                  <div className="ca-label">Servicio</div>
                  <select className="ca-input" value={cobServicio} onChange={(e) => { setCobServicio(e.target.value); const s = serviciosActivos.find((x) => String(x.id) === e.target.value); if (s) setCobMonto(String(s.precio)); }}>
                    <option value="">— Personalizado —</option>
                    {serviciosActivos.map((s) => <option key={s.id} value={s.id}>{s.nombre} (S/ {s.precio})</option>)}
                  </select>
                </div>
                <div style={{ width: 96 }}>
                  <div className="ca-label">Monto S/.</div>
                  <input className="ca-input" value={cobMonto} onChange={(e) => setCobMonto(e.target.value)} inputMode="decimal" placeholder="80" />
                </div>
              </div>
              <div style={{ display: "flex", gap: 10 }}>
                <div style={{ flex: 1 }}>
                  <div className="ca-label">Estado</div>
                  <select className="ca-input" value={cobEstado} onChange={(e) => setCobEstado(e.target.value)}>
                    <option value="pagado">Pagado</option>
                    <option value="pendiente">Pendiente</option>
                  </select>
                </div>
                {cobEstado === "pagado" && (
                  <div style={{ flex: 1 }}>
                    <div className="ca-label">Medio</div>
                    <select className="ca-input" value={cobMedio} onChange={(e) => setCobMedio(e.target.value)}>
                      {MEDIOS_PAGO.map((m) => <option key={m.v} value={m.v}>{m.l}</option>)}
                    </select>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        <div style={{ display: "flex", gap: 9, justifyContent: "flex-end" }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" style={{ opacity: canSave ? 1 : 0.5, pointerEvents: canSave ? "auto" : "none" }} onClick={guardar}>
            Guardar atención
          </button>
        </div>
      </div>
    </div>
  );
}

function RecordarModal({ cita, clinica, onClose, onSend }) {
  const primer = cita.paciente.split(" ")[0];
  const inicial = `Hola ${primer} 👋 Te recordamos tu sesión en ${clinica} hoy a las ${cita.hora} con ${cita.medico} (${cita.especialidad}). ¿Confirmas tu asistencia? Responde SÍ para confirmar 🌿`;
  const [texto, setTexto] = useState(inicial);
  const [enviando, setEnviando] = useState(false);
  const canSend = texto.trim().length > 0 && !enviando;

  async function enviar() {
    setEnviando(true);
    try { await onSend(texto.trim()); } finally { setEnviando(false); }
  }

  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <strong style={{ fontSize: 16, display: "flex", alignItems: "center", gap: 8 }}>
            <MessageCircle size={17} strokeWidth={2} style={{ color: "var(--wa)" }} /> Recordatorio por WhatsApp
          </strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>
        <div className="ca-label" style={{ marginBottom: 6 }}>Para {cita.paciente}</div>
        <textarea className="ca-input ca-textarea" style={{ minHeight: 120 }} value={texto}
          onChange={(e) => setTexto(e.target.value)} />
        <div style={{ fontSize: 12, color: "var(--muted)", margin: "8px 0 4px" }}>
          Puedes ajustar el mensaje antes de enviarlo. Se envía por WhatsApp al paciente.
        </div>
        <div style={{ display: "flex", gap: 9, justifyContent: "flex-end", marginTop: 16 }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" style={{ background: "var(--wa)", opacity: canSend ? 1 : 0.5, pointerEvents: canSend ? "auto" : "none" }} onClick={enviar}>
            <MessageCircle size={15} strokeWidth={2.1} /> {enviando ? "Enviando…" : "Enviar"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Mensajes({ mensajes }) {
  return (
    <div>
      <h1 className="ca-h1">Mensajes</h1>
      <div className="ca-sub">Bitácora de WhatsApp · {mensajes.length} en total</div>
      {mensajes.length === 0 ? (
        <div className="ca-empty">Aún no se han enviado mensajes. Los recordatorios y seguimientos que envíes aparecerán aquí.</div>
      ) : (
        <table className="ca-tbl" style={{ marginTop: 22 }}>
          <thead>
            <tr>
              <th>Fecha</th>
              <th>Paciente</th>
              <th>Tipo</th>
              <th>Estado</th>
              <th>Mensaje</th>
            </tr>
          </thead>
          <tbody>
            {mensajes.map((m) => (
              <tr key={m.id}>
                <td style={{ whiteSpace: "nowrap", color: "var(--ink-soft)" }}>{m.fecha}</td>
                <td style={{ fontWeight: 500 }}>{m.paciente_nombre || m.telefono || "—"}</td>
                <td style={{ color: "var(--ink-soft)" }}>{m.tipo_label}</td>
                <td><Tag colors={MENSAJE_ESTADO[m.estado]}>{m.estado_label}</Tag></td>
                <td style={{ color: "var(--ink-soft)", maxWidth: 360 }}>{m.texto}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function MensajePacienteModal({ paciente, onClose, onSend }) {
  const primer = (paciente.nombre || "").split(" ")[0];
  const inicial = `Hola ${primer} 👋 Desde Itaca Conversemos queremos saber cómo te encuentras. Si lo deseas, podemos agendar tu próxima sesión. Estamos para ayudarte 🌿`;
  const [texto, setTexto] = useState(inicial);
  const [enviando, setEnviando] = useState(false);
  const sinTel = !paciente.tel || paciente.tel === "—";
  const canSend = texto.trim().length > 0 && !sinTel && !enviando;

  async function enviar() {
    setEnviando(true);
    try { await onSend(texto.trim(), "seguimiento"); } finally { setEnviando(false); }
  }

  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <strong style={{ fontSize: 16, display: "flex", alignItems: "center", gap: 8 }}>
            <MessageCircle size={17} strokeWidth={2} style={{ color: "var(--wa)" }} /> Mensaje por WhatsApp
          </strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>
        <div className="ca-label" style={{ marginBottom: 6 }}>
          Para {paciente.nombre} {sinTel ? "" : `· ${paciente.tel}`}
        </div>
        {sinTel ? (
          <div className="ca-wapreview" style={{ background: "#F7E5E5", borderColor: "#EBC9C9", color: "#9C4646" }}>
            Este paciente no tiene teléfono registrado. Agrégalo en “Editar” para poder enviarle WhatsApp.
          </div>
        ) : (
          <textarea className="ca-input ca-textarea" style={{ minHeight: 120 }} value={texto}
            onChange={(e) => setTexto(e.target.value)} autoFocus />
        )}
        <div style={{ display: "flex", gap: 9, justifyContent: "flex-end", marginTop: 16 }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" style={{ background: "var(--wa)", opacity: canSend ? 1 : 0.5, pointerEvents: canSend ? "auto" : "none" }} onClick={enviar}>
            <MessageCircle size={15} strokeWidth={2.1} /> {enviando ? "Enviando…" : "Enviar"}
          </button>
        </div>
      </div>
    </div>
  );
}

function UrlBox({ label, url, onCopy, copiado }) {
  return (
    <div style={{ marginBottom: 10 }}>
      <div className="ca-label" style={{ marginBottom: 5 }}>{label}</div>
      <div className="ca-urlbox">
        <code>{url}</code>
        <button className="ca-mini" onClick={onCopy}>
          {copiado ? <><Check size={13} strokeWidth={2.4} /> Copiado</> : <><Copy size={13} strokeWidth={2} /> Copiar</>}
        </button>
      </div>
    </div>
  );
}

function Marketing({ showToast, onConvertir, esAdmin }) {
  const [leads, setLeads] = useState([]);
  const [rep, setRep] = useState(null);
  const [medicos, setMedicos] = useState([]);
  const [cfg, setCfg] = useState(null);
  const [copiado, setCopiado] = useState("");
  const [probando, setProbando] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [creando, setCreando] = useState(false);
  const origen = window.location.origin;

  async function cargar() {
    const [l, r, m, c] = await Promise.all([api.leads(), api.reportesLeads(), api.medicos(), api.captacionConfig()]);
    setLeads(l); setRep(r); setMedicos(m); setCfg(c);
  }
  useEffect(() => {
    cargar().catch((err) => showToast("Error: " + err.message)).finally(() => setCargando(false));
  }, []);

  function copiar(texto, etiqueta) {
    navigator.clipboard?.writeText(texto).then(() => { setCopiado(etiqueta); setTimeout(() => setCopiado(""), 1800); });
  }
  async function probar() {
    if (!cfg) return;
    setProbando(true);
    try {
      await api.enviarLeadCaptacion(cfg.path_web, {
        nombre: "Lead de prueba", telefono: "999 000 111", fuente: "web",
        es_pauta: true, campania: "Prueba de conexión", mensaje: "Quiero información (lead de prueba).",
      });
      await cargar();
      showToast("Entró un lead de prueba ✓");
    } catch (err) { showToast("Error: " + err.message); }
    finally { setProbando(false); }
  }
  async function regenerar() {
    try { const c = await api.regenerarTokenCaptacion(); setCfg(c); showToast("Token regenerado ✓"); }
    catch (err) { showToast("Error: " + err.message); }
  }

  async function moverEstado(lead, estado) {
    try { await api.actualizarLead(lead.id, { estado }); await cargar(); }
    catch (err) { showToast("Error: " + err.message); }
  }
  async function asignarMedico(lead, medicoId) {
    try { await api.actualizarLead(lead.id, { medico: medicoId || null }); await cargar(); showToast("Médico asignado ✓"); }
    catch (err) { showToast("Error: " + err.message); }
  }
  async function convertir(lead) {
    try {
      await api.convertirLead(lead.id);
      await cargar();
      onConvertir && onConvertir();
      showToast(`${lead.nombre} ahora es paciente ✓`);
    } catch (err) { showToast("Error: " + err.message); }
  }
  async function crearLead(data) {
    try { await api.crearLead(data); await cargar(); setCreando(false); showToast("Lead captado ✓"); }
    catch (err) { showToast("Error: " + err.message); }
  }

  if (cargando) return <div className="ca-empty">Cargando…</div>;

  const emb = rep?.embudo || { recibidos: 0, contactados: 0, agendados: 0, iniciaron: 0, perdidos: 0 };
  const pasos = [
    { label: "Leads recibidos", n: emb.recibidos, color: "#9B968D" },
    { label: "Contactados", n: emb.contactados, color: "#6E86A8" },
    { label: "Sesión agendada", n: emb.agendados, color: "#C9923A" },
    { label: "Iniciaron tratamiento", n: emb.iniciaron, color: "#4F8A77" },
  ];
  const base = emb.recibidos || 1;

  return (
    <div>
      <div className="ca-tophead">
        <div>
          <h1 className="ca-h1">Captación</h1>
          <div className="ca-sub">Leads, embudo y cierre por doctor</div>
        </div>
        <div style={{ display: "flex", gap: 9, alignItems: "center" }}>
          <button className="ca-btn ghost" disabled={leads.length === 0}
            onClick={() => descargarCSV("leads.csv", ["Nombre", "Telefono", "Fuente", "Pauta", "Campaña", "Especialidad", "Medico", "Estado", "Creado"],
              leads.map((l) => [l.nombre, l.telefono, l.fuente_label, l.es_pauta ? "Si" : "No", l.campania, l.especialidad, l.medico_nombre, l.estado_label, l.creado]))}>
            <Download size={15} strokeWidth={2} /> CSV
          </button>
          <button className="ca-btn" onClick={() => setCreando(true)}>
            <Plus size={16} strokeWidth={2.2} /> Captar lead
          </button>
        </div>
      </div>

      {cfg && (
        <>
          <h2 className="ca-secth" style={{ marginTop: 26 }}>Recibir leads automáticamente</h2>
          <div className="ca-card">
            <div style={{ fontSize: 13.5, color: "var(--ink-soft)", lineHeight: 1.55, marginBottom: 14 }}>
              Pega estas direcciones en tu <strong>web</strong>, en un <strong>landing de campaña</strong> o en
              conectores como <strong>Meta Lead Ads → Zapier/Make</strong>, y los leads entrarán solos al embudo,
              con su fuente y campaña.
            </div>
            <UrlBox label="Web / campañas (formularios, Zapier)" url={origen + cfg.path_web}
              onCopy={() => copiar(origen + cfg.path_web, "web")} copiado={copiado === "web"} />
            <UrlBox label="WhatsApp (webhook de Evolution)" url={origen + cfg.path_whatsapp}
              onCopy={() => copiar(origen + cfg.path_whatsapp, "wa")} copiado={copiado === "wa"} />
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center", marginTop: 14 }}>
              <button className="ca-btn ghost" onClick={probar} style={{ opacity: probando ? 0.6 : 1, pointerEvents: probando ? "none" : "auto" }}>
                <Plus size={14} strokeWidth={2.2} /> {probando ? "Enviando…" : "Probar con un lead de ejemplo"}
              </button>
              {esAdmin && <button className="ca-link" onClick={regenerar}>Regenerar token</button>}
            </div>
            <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 12, lineHeight: 1.5 }}>
              ⚠️ Para recibir leads reales desde internet, el sistema debe estar publicado (hoy corre local).
              El botón «Probar» ya funciona, porque la prueba sale desde esta misma pantalla.
            </div>
          </div>
        </>
      )}

      <h2 className="ca-secth" style={{ marginTop: 30 }}>Embudo de captación</h2>
      <div className="ca-card">
        {pasos.map((s, i) => (
          <div key={s.label} style={{ marginBottom: 13 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13.5 }}>
              <span style={{ fontWeight: 500 }}>{s.label}</span>
              <span style={{ fontVariantNumeric: "tabular-nums" }}>
                {s.n}
                {i > 0 && emb.recibidos > 0 && <span style={{ color: "var(--muted)", marginLeft: 8 }}>{Math.round((s.n / emb.recibidos) * 100)}%</span>}
              </span>
            </div>
            <div style={{ height: 8, borderRadius: 999, background: "var(--line)", marginTop: 6 }}>
              <div style={{ height: "100%", width: `${(s.n / base) * 100}%`, background: s.color, borderRadius: 999 }} />
            </div>
          </div>
        ))}
        <div style={{ marginTop: 8, fontSize: 13, color: (rep?.tasa_global || 0) < 15 ? "#B4564E" : "#4F8A77" }}>
          Tasa de cierre global: <strong>{rep?.tasa_global || 0}%</strong> · {emb.perdidos} perdidos.
        </div>
      </div>

      <h2 className="ca-secth" style={{ marginTop: 30 }}>Cierre por doctor</h2>
      <table className="ca-tbl">
        <thead>
          <tr>
            <th>Doctor</th>
            <th className="num">Leads</th>
            <th className="num">Agendados</th>
            <th className="num">Cierres</th>
            <th className="num">% cierre</th>
          </tr>
        </thead>
        <tbody>
          {(rep?.por_medico || []).map((m) => (
            <tr key={m.medico}>
              <td style={{ fontWeight: 500 }}>{m.medico}</td>
              <td className="num">{m.leads}</td>
              <td className="num">{m.agendados}</td>
              <td className="num">{m.cierres}</td>
              <td className="num"><span className="ca-dot" style={{ background: semColor(m.tasa / 100) }} />{m.tasa}%</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ fontSize: 12.5, color: "var(--muted)", marginTop: 4 }}>
        Cuántos leads llegan por cada doctor (de pauta u orgánico) y cuántos cierran.
      </div>

      <h2 className="ca-secth" style={{ marginTop: 30 }}>Leads por fuente</h2>
      <table className="ca-tbl">
        <thead>
          <tr>
            <th>Fuente</th>
            <th className="num">Leads</th>
            <th className="num">Cierres</th>
            <th className="num">% cierre</th>
          </tr>
        </thead>
        <tbody>
          {(rep?.por_fuente || []).map((f) => (
            <tr key={f.fuente}>
              <td style={{ fontWeight: 500 }}>{f.fuente}</td>
              <td className="num">{f.leads}</td>
              <td className="num">{f.cierres}</td>
              <td className="num">{f.tasa}%</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2 className="ca-secth" style={{ marginTop: 30 }}>Leads ({leads.length})</h2>
      {leads.length === 0 ? (
        <div className="ca-empty">Aún no hay leads. Capta el primero con el botón de arriba.</div>
      ) : (
        leads.map((lead) => (
          <div key={lead.id} className="ca-row">
            <div style={{ flex: 1, minWidth: 160 }}>
              <div className="ca-pname">
                {lead.nombre}
                {lead.es_pauta && (
                  <span style={{ marginLeft: 8, fontSize: 10.5, background: "#EDE6F4", color: "#6B4E96", padding: "1px 7px", borderRadius: 999, fontWeight: 600, verticalAlign: "middle" }}>PAUTA</span>
                )}
              </div>
              <div className="ca-pmeta">
                {lead.fuente_label}{lead.especialidad ? ` · ${lead.especialidad}` : ""}{lead.medico_nombre ? ` · ${lead.medico_nombre}` : ""}{lead.campania ? ` · ${lead.campania}` : ""}
              </div>
            </div>
            <select className="ca-tplsel" value={lead.medico || ""} onChange={(ev) => asignarMedico(lead, ev.target.value)} title="Médico asignado">
              <option value="">Sin médico</option>
              {medicos.map((m) => <option key={m.id} value={m.id}>{m.nombre}</option>)}
            </select>
            <select className="ca-tplsel" value={lead.estado} onChange={(ev) => moverEstado(lead, ev.target.value)}>
              {LEAD_ESTADOS.map((s) => <option key={s.v} value={s.v}>{s.l}</option>)}
            </select>
            {lead.paciente_nombre ? (
              <Tag colors={LEAD_ESTADO_COLOR.ganado}>Ya es paciente</Tag>
            ) : (
              <button className="ca-mini" onClick={() => convertir(lead)}>
                <UserPlus size={13} strokeWidth={2} /> Convertir
              </button>
            )}
          </div>
        ))
      )}

      {creando && <CrearLeadModal medicos={medicos} onClose={() => setCreando(false)} onSave={crearLead} />}
    </div>
  );
}

function CrearLeadModal({ medicos, onClose, onSave }) {
  const [nombre, setNombre] = useState("");
  const [telefono, setTelefono] = useState("");
  const [fuente, setFuente] = useState("instagram");
  const [esPauta, setEsPauta] = useState(true);
  const [campania, setCampania] = useState("");
  const [especialidad, setEspecialidad] = useState(Object.keys(SPECIALTY)[0]);
  const [medico, setMedico] = useState("");
  const canSave = nombre.trim().length > 0;

  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 400 }} onClick={(ev) => ev.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <strong style={{ fontSize: 16 }}>Captar lead</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>
        <div style={{ marginBottom: 12 }}>
          <div className="ca-label">Nombre</div>
          <input className="ca-input" value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre del interesado" autoFocus />
        </div>
        <div style={{ display: "flex", gap: 11, marginBottom: 12 }}>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Teléfono</div>
            <input className="ca-input" value={telefono} onChange={(e) => setTelefono(e.target.value)} placeholder="987 654 321" />
          </div>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Fuente</div>
            <select className="ca-input" value={fuente} onChange={(e) => setFuente(e.target.value)}>
              {FUENTES.map((f) => <option key={f.v} value={f.v}>{f.l}</option>)}
            </select>
          </div>
        </div>
        <label style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12, fontSize: 13.5, color: "var(--ink-soft)", cursor: "pointer" }}>
          <input type="checkbox" checked={esPauta} onChange={(e) => setEsPauta(e.target.checked)} />
          Vino de pauta (anuncio pagado)
        </label>
        <div style={{ marginBottom: 12 }}>
          <div className="ca-label">Campaña (opcional)</div>
          <input className="ca-input" value={campania} onChange={(e) => setCampania(e.target.value)} placeholder="ej. Pauta Gastro Junio" />
        </div>
        <div style={{ display: "flex", gap: 11, marginBottom: 18 }}>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Especialidad</div>
            <select className="ca-input" value={especialidad} onChange={(e) => setEspecialidad(e.target.value)}>
              {Object.keys(SPECIALTY).map((s) => <option key={s}>{s}</option>)}
            </select>
          </div>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Doctor de la pauta</div>
            <select className="ca-input" value={medico} onChange={(e) => setMedico(e.target.value)}>
              <option value="">Sin asignar</option>
              {medicos.map((m) => <option key={m.id} value={m.id}>{m.nombre}</option>)}
            </select>
          </div>
        </div>
        <div style={{ display: "flex", gap: 9, justifyContent: "flex-end" }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" style={{ opacity: canSave ? 1 : 0.5, pointerEvents: canSave ? "auto" : "none" }}
            onClick={() => onSave({ nombre: nombre.trim(), telefono: telefono.trim(), fuente, es_pauta: esPauta, campania: campania.trim(), especialidad, medico: medico ? Number(medico) : null })}>
            Captar
          </button>
        </div>
      </div>
    </div>
  );
}

const MEDIOS_PAGO = [
  { v: "efectivo", l: "Efectivo" }, { v: "yape", l: "Yape" }, { v: "plin", l: "Plin" },
  { v: "tarjeta", l: "Tarjeta" }, { v: "transferencia", l: "Transferencia" },
];
const ESTADO_COBRO_COLOR = {
  pagado: { bg: "#E9F1ED", fg: "#3E7A65" },
  pendiente: { bg: "#F7ECDD", fg: "#9C6B2E" },
  anulado: { bg: "#EFEDE8", fg: "#7C7870" },
};

const EGRESO_CATEGORIAS = [
  { v: "insumos", l: "Insumos / materiales" },
  { v: "sueldos", l: "Sueldos / honorarios" },
  { v: "alquiler", l: "Alquiler / servicios" },
  { v: "equipos", l: "Equipos" },
  { v: "marketing", l: "Marketing / pauta" },
  { v: "otro", l: "Otro" },
];

function Finanzas({ showToast, esAdmin }) {
  const [periodo, setPeriodo] = useState("mes");
  const [res, setRes] = useState(null);
  const [cobros, setCobros] = useState([]);
  const [servicios, setServicios] = useState([]);
  const [pacientes, setPacientes] = useState([]);
  const [caja, setCaja] = useState(null);
  const [egresos, setEgresos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [nuevo, setNuevo] = useState(null);
  const [nuevoEgreso, setNuevoEgreso] = useState(false);
  const [pagando, setPagando] = useState(null);
  const [precios, setPrecios] = useState(false);

  async function cargar() {
    const base = [api.resumenFinanzas(periodo), api.cobros(periodo), api.servicios(), api.pacientes()];
    const extra = esAdmin ? [api.cajaFinanzas(periodo), api.egresos(periodo)] : [];
    const [r, c, s, p, cj, eg] = await Promise.all([...base, ...extra]);
    setRes(r); setCobros(c); setServicios(s); setPacientes(p);
    if (esAdmin) { setCaja(cj); setEgresos(eg); }
  }
  useEffect(() => {
    setCargando(true);
    cargar().catch((e) => showToast("Error: " + e.message)).finally(() => setCargando(false));
  }, [periodo]);

  async function registrar(data) {
    try { await api.crearCobro(data); await cargar(); setNuevo(null); showToast("Cobro registrado ✓"); }
    catch (e) { showToast("Error: " + e.message); }
  }
  async function pagar(cobro, medio) {
    try { await api.marcarCobroPagado(cobro.id, medio); await cargar(); setPagando(null); showToast("Cobro pagado ✓"); }
    catch (e) { showToast("Error: " + e.message); }
  }
  async function registrarEgreso(data) {
    try { await api.crearEgreso(data); await cargar(); setNuevoEgreso(false); showToast("Egreso registrado ✓"); }
    catch (e) { showToast("Error: " + e.message); }
  }
  async function borrarEgreso(eg) {
    try { await api.eliminarEgreso(eg.id); await cargar(); showToast("Egreso eliminado"); }
    catch (e) { showToast("Error: " + e.message); }
  }

  return (
    <div>
      <div className="ca-tophead">
        <div>
          <h1 className="ca-h1">Finanzas</h1>
          <div className="ca-sub">Ingresos reales · Soles (S/.)</div>
        </div>
        <div style={{ display: "flex", gap: 9, alignItems: "center" }}>
          <button className="ca-btn ghost" disabled={cobros.length === 0}
            onClick={() => descargarCSV(`cobros_${periodo}.csv`, ["Fecha", "Paciente", "Concepto", "Monto", "Estado", "Medio"],
              cobros.map((c) => [c.fecha_label, c.paciente_nombre, c.concepto, c.monto, c.estado_label, c.medio_label]))}>
            <Download size={15} strokeWidth={2} /> CSV
          </button>
          {esAdmin && <button className="ca-btn ghost" onClick={() => setPrecios(true)}>Precios</button>}
          <button className="ca-btn" onClick={() => setNuevo({})}><Plus size={16} strokeWidth={2.2} /> Registrar cobro</button>
        </div>
      </div>

      <div className="ca-agnav" style={{ justifyContent: "flex-end" }}>
        <div className="ca-seg">
          {[["hoy", "Hoy"], ["semana", "Semana"], ["mes", "Mes"]].map(([v, l]) => (
            <button key={v} className={periodo === v ? "on" : ""} onClick={() => setPeriodo(v)}>{l}</button>
          ))}
        </div>
      </div>

      {!res ? (
        <div className="ca-empty">{cargando ? "Cargando…" : "Sin datos."}</div>
      ) : (
        <div style={{ opacity: cargando ? 0.5 : 1, transition: "opacity .15s" }}>
          {esAdmin && caja && (
            <>
              <h2 className="ca-secth" style={{ marginTop: 16 }}>Caja del período</h2>
              <div className="ca-stats">
                <StatCard label="Ingresos (cobrado)" valor={money(caja.ingresos)} color="#4F8A77" />
                <StatCard label="Egresos (gastos)" valor={money(caja.egresos)} sub={`${caja.n_egresos} gastos`} color="#B4564E" />
                <StatCard label="Utilidad (neto)" valor={money(caja.utilidad)} color={caja.utilidad >= 0 ? "#3E7A65" : "#B4564E"} />
                <StatCard label="Pendiente por cobrar" valor={money(caja.pendiente)} color={caja.pendiente > 0 ? "#C9923A" : "#7C7870"} />
              </div>
              {caja.egresos_por_categoria.length > 0 && (
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
                  {caja.egresos_por_categoria.map((c) => (
                    <span key={c.categoria} className="ca-vital" style={{ background: "#F7E9E7", color: "#B4564E" }}><b>{c.categoria}</b> {money(c.monto)}</span>
                  ))}
                </div>
              )}
            </>
          )}

          <div className="ca-stats" style={{ marginTop: esAdmin && caja ? 22 : 16 }}>
            {!(esAdmin && caja) && <StatCard label="Cobrado en el período" valor={money(res.cobrado)} color="#4F8A77" />}
            {!(esAdmin && caja) && <StatCard label="Pendiente por cobrar" valor={money(res.pendiente)} sub={`${res.n_pendientes} cobros`} color={res.pendiente > 0 ? "#C9923A" : "#7C7870"} />}
            <StatCard label="Cobros pagados" valor={res.n_cobros} />
            <StatCard label="Ticket promedio" valor={money(res.ticket_promedio)} />
          </div>

          {res.por_medio.length > 0 && (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
              {res.por_medio.map((m) => (
                <span key={m.medio} className="ca-vital"><b>{m.medio}</b> {money(m.monto)}</span>
              ))}
            </div>
          )}

          {!(esAdmin && caja) && res.por_dia && res.por_dia.length > 1 && (
            <>
              <h2 className="ca-secth" style={{ marginTop: 26 }}>Ingresos por día</h2>
              <div className="ca-card">
                <MiniBars data={res.por_dia} valor={(d) => d.monto} etiqueta={(d) => dDeISO(d.fecha).getDate()} />
              </div>
            </>
          )}

          {esAdmin && caja && caja.por_dia && caja.por_dia.length > 1 && (
            <>
              <h2 className="ca-secth" style={{ marginTop: 26 }}>Flujo de caja (ingresos vs egresos)</h2>
              <div className="ca-card">
                <MiniBarsDuo data={caja.por_dia} a={(d) => d.ingresos} b={(d) => d.egresos}
                  labelA="Ingresos" labelB="Egresos" etiqueta={(d) => dDeISO(d.fecha).getDate()} fmt={money} />
              </div>
            </>
          )}

          {esAdmin && (
            <>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 30, marginBottom: 12 }}>
                <h2 className="ca-secth" style={{ margin: 0 }}>Egresos del período ({egresos.length})</h2>
                <button className="ca-mini" onClick={() => setNuevoEgreso(true)}><Plus size={13} strokeWidth={2.2} /> Agregar egreso</button>
              </div>
              {egresos.length === 0 ? (
                <div className="ca-empty" style={{ padding: "26px 20px" }}>Aún no hay gastos registrados en este período.</div>
              ) : (
                <table className="ca-tbl">
                  <thead><tr><th>Fecha</th><th>Concepto</th><th>Categoría</th><th className="num">Monto</th><th></th></tr></thead>
                  <tbody>
                    {egresos.map((e) => (
                      <tr key={e.id}>
                        <td>{e.fecha_label}</td>
                        <td style={{ fontWeight: 500 }}>{e.concepto}{e.proveedor ? <span style={{ color: "var(--muted)", fontWeight: 400 }}> · {e.proveedor}</span> : ""}</td>
                        <td>{e.categoria_label}</td>
                        <td className="num" style={{ color: "#B4564E" }}>{money(e.monto)}</td>
                        <td className="num"><button className="ca-iconbtn" title="Eliminar egreso" onClick={() => borrarEgreso(e)}><Trash2 size={14} strokeWidth={2} /></button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}

          <h2 className="ca-secth" style={{ marginTop: 28 }}>Cobros del período ({cobros.length})</h2>
          {cobros.length === 0 ? (
            <div className="ca-empty">No hay cobros en este período. Registra uno con el botón de arriba.</div>
          ) : (
            <table className="ca-tbl">
              <thead>
                <tr>
                  <th>Fecha</th><th>Paciente</th><th>Concepto</th>
                  <th className="num">Monto</th><th>Estado</th><th></th>
                </tr>
              </thead>
              <tbody>
                {cobros.map((c) => (
                  <tr key={c.id}>
                    <td>{c.fecha_label}</td>
                    <td style={{ fontWeight: 500 }}>{c.paciente_nombre}</td>
                    <td>{c.concepto}</td>
                    <td className="num">{money(c.monto)}</td>
                    <td><Tag colors={ESTADO_COBRO_COLOR[c.estado]}>{c.estado_label}{c.estado === "pagado" && c.medio_label ? ` · ${c.medio_label}` : ""}</Tag></td>
                    <td className="num">
                      {c.estado === "pendiente" && (
                        <button className="ca-mini" onClick={() => setPagando(c)}><Check size={13} strokeWidth={2.2} /> Marcar pagado</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {nuevo && <CobroModal prefill={nuevo} pacientes={pacientes} servicios={servicios} onClose={() => setNuevo(null)} onSave={registrar} />}
      {nuevoEgreso && <EgresoModal onClose={() => setNuevoEgreso(false)} onSave={registrarEgreso} />}
      {pagando && <PagarModal cobro={pagando} onClose={() => setPagando(null)} onSave={(medio) => pagar(pagando, medio)} />}
      {precios && <PreciosModal onClose={() => setPrecios(false)} showToast={showToast} />}
    </div>
  );
}

function PagarModal({ cobro, onClose, onSave }) {
  const [medio, setMedio] = useState("efectivo");
  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 360 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <strong style={{ fontSize: 16 }}>Marcar pagado</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>
        <div style={{ fontSize: 14, color: "var(--ink-soft)", marginBottom: 12 }}>{cobro.concepto} · <strong>{money(cobro.monto)}</strong></div>
        <div className="ca-label" style={{ marginBottom: 5 }}>Medio de pago</div>
        <select className="ca-input" value={medio} onChange={(e) => setMedio(e.target.value)}>
          {MEDIOS_PAGO.map((m) => <option key={m.v} value={m.v}>{m.l}</option>)}
        </select>
        <div style={{ display: "flex", gap: 9, justifyContent: "flex-end", marginTop: 18 }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" onClick={() => onSave(medio)}>Confirmar pago</button>
        </div>
      </div>
    </div>
  );
}

function EgresoModal({ onClose, onSave }) {
  const [concepto, setConcepto] = useState("");
  const [categoria, setCategoria] = useState("insumos");
  const [monto, setMonto] = useState("");
  const [medio, setMedio] = useState("efectivo");
  const [proveedor, setProveedor] = useState("");
  const canSave = concepto.trim() && monto && Number(monto) > 0;
  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 400 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <strong style={{ fontSize: 16 }}>Registrar egreso</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>
        <div style={{ marginBottom: 13 }}>
          <div className="ca-label">Concepto</div>
          <input className="ca-input" value={concepto} onChange={(e) => setConcepto(e.target.value)} placeholder="Ej. Compra de guantes" autoFocus />
        </div>
        <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
          <div style={{ flex: 1.4 }}>
            <div className="ca-label">Categoría</div>
            <select className="ca-input" value={categoria} onChange={(e) => setCategoria(e.target.value)}>
              {EGRESO_CATEGORIAS.map((c) => <option key={c.v} value={c.v}>{c.l}</option>)}
            </select>
          </div>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Monto (S/.)</div>
            <input className="ca-input" value={monto} onChange={(e) => setMonto(e.target.value)} placeholder="0.00" inputMode="decimal" />
          </div>
        </div>
        <div style={{ display: "flex", gap: 11, marginBottom: 18 }}>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Medio de pago</div>
            <select className="ca-input" value={medio} onChange={(e) => setMedio(e.target.value)}>
              {MEDIOS_PAGO.map((m) => <option key={m.v} value={m.v}>{m.l}</option>)}
            </select>
          </div>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Proveedor <span style={{ color: "var(--muted)", fontWeight: 400 }}>(opcional)</span></div>
            <input className="ca-input" value={proveedor} onChange={(e) => setProveedor(e.target.value)} placeholder="Nombre" />
          </div>
        </div>
        <div style={{ display: "flex", gap: 9, justifyContent: "flex-end" }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" style={{ opacity: canSave ? 1 : 0.5, pointerEvents: canSave ? "auto" : "none" }}
            onClick={() => onSave({ concepto: concepto.trim(), categoria, monto, medio_pago: medio, proveedor: proveedor.trim() })}>
            Guardar egreso
          </button>
        </div>
      </div>
    </div>
  );
}

function CobroModal({ prefill, pacientes, servicios, onClose, onSave }) {
  const [busca, setBusca] = useState("");
  const [sel, setSel] = useState(prefill?.pacienteId ? { id: prefill.pacienteId, nombre: prefill.paciente } : null);
  const serviciosActivos = (servicios || []).filter((s) => s.activo);
  const servDefault = prefill?.especialidad ? serviciosActivos.find((s) => s.especialidad === prefill.especialidad) : null;
  const [servicio, setServicio] = useState(servDefault ? String(servDefault.id) : "");
  const [monto, setMonto] = useState(servDefault ? String(servDefault.precio) : "");
  const [estado, setEstado] = useState("pagado");
  const [medio, setMedio] = useState("efectivo");
  const [concepto, setConcepto] = useState(prefill?.concepto || (servDefault ? servDefault.nombre : ""));

  const matches = useMemo(
    () => (busca.trim() ? (pacientes || []).filter((p) => p.nombre.toLowerCase().includes(busca.toLowerCase())).slice(0, 4) : []),
    [busca, pacientes]
  );

  function elegirServicio(id) {
    setServicio(id);
    const s = serviciosActivos.find((x) => String(x.id) === String(id));
    if (s) { setMonto(String(s.precio)); setConcepto(s.nombre); }
  }

  const canSave = sel && monto && Number(monto) > 0;
  function guardar() {
    onSave({
      paciente: sel.id,
      cita: prefill?.citaId || null,
      servicio: servicio || null,
      concepto: concepto.trim() || undefined,
      monto, estado,
      medio_pago: estado === "pagado" ? medio : "",
    });
  }

  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 400 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <strong style={{ fontSize: 16 }}>Registrar cobro</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>

        <div style={{ marginBottom: 13 }}>
          <div className="ca-label">Paciente</div>
          {sel ? (
            <div className="ca-chipsel">
              <div className="ca-avatar" style={{ width: 28, height: 28, fontSize: 11 }}>{iniciales(sel.nombre)}</div>
              <div style={{ fontSize: 14, fontWeight: 500 }}>{sel.nombre}</div>
              {!prefill?.pacienteId && <button className="ca-link" onClick={() => setSel(null)}>cambiar</button>}
            </div>
          ) : (
            <>
              <input className="ca-input" value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar paciente…" autoFocus />
              {busca.trim() && (
                <div className="ca-pick">
                  {matches.map((p) => (
                    <div key={p.id} className="ca-pickrow" onClick={() => { setSel(p); setBusca(""); }}>
                      <div className="ca-avatar" style={{ width: 28, height: 28, fontSize: 11 }}>{iniciales(p.nombre)}</div>
                      <div style={{ fontSize: 14, fontWeight: 500 }}>{p.nombre}</div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>

        <div style={{ marginBottom: 13 }}>
          <div className="ca-label">Servicio</div>
          <select className="ca-input" value={servicio} onChange={(e) => elegirServicio(e.target.value)}>
            <option value="">— Otro / personalizado —</option>
            {serviciosActivos.map((s) => <option key={s.id} value={s.id}>{s.nombre} (S/ {s.precio})</option>)}
          </select>
        </div>

        <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Monto (S/.)</div>
            <input className="ca-input" value={monto} onChange={(e) => setMonto(e.target.value)} placeholder="80" inputMode="decimal" />
          </div>
          <div style={{ flex: 1.2 }}>
            <div className="ca-label">Estado</div>
            <select className="ca-input" value={estado} onChange={(e) => setEstado(e.target.value)}>
              <option value="pagado">Pagado</option>
              <option value="pendiente">Pendiente</option>
            </select>
          </div>
        </div>

        {estado === "pagado" && (
          <div style={{ marginBottom: 13 }}>
            <div className="ca-label">Medio de pago</div>
            <select className="ca-input" value={medio} onChange={(e) => setMedio(e.target.value)}>
              {MEDIOS_PAGO.map((m) => <option key={m.v} value={m.v}>{m.l}</option>)}
            </select>
          </div>
        )}

        <div style={{ marginBottom: 18 }}>
          <div className="ca-label">Concepto</div>
          <input className="ca-input" value={concepto} onChange={(e) => setConcepto(e.target.value)} placeholder="Consulta / procedimiento…" />
        </div>

        <div style={{ display: "flex", gap: 9, justifyContent: "flex-end" }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" style={{ opacity: canSave ? 1 : 0.5, pointerEvents: canSave ? "auto" : "none" }} onClick={guardar}>Guardar cobro</button>
        </div>
      </div>
    </div>
  );
}

function PreciosModal({ onClose, showToast }) {
  const [lista, setLista] = useState(null);
  const [nombre, setNombre] = useState("");
  const [esp, setEsp] = useState("");
  const [precio, setPrecio] = useState("");

  async function cargar() { setLista(await api.servicios()); }
  useEffect(() => { cargar().catch((e) => showToast("Error: " + e.message)); }, []);

  async function guardarPrecio(s, nuevoPrecio) {
    try { await api.actualizarServicio(s.id, { precio: nuevoPrecio }); await cargar(); showToast("Precio actualizado ✓"); }
    catch (e) { showToast("Error: " + e.message); }
  }
  async function agregar() {
    if (!nombre.trim() || !precio) return;
    try {
      await api.crearServicio({ nombre: nombre.trim(), especialidad: esp.trim(), precio });
      setNombre(""); setEsp(""); setPrecio(""); await cargar(); showToast("Servicio agregado ✓");
    } catch (e) { showToast("Error: " + e.message); }
  }
  async function eliminar(s) {
    try { await api.eliminarServicio(s.id); await cargar(); }
    catch (e) { showToast("Error: " + e.message); }
  }

  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 470 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <strong style={{ fontSize: 16 }}>Catálogo de precios</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>
        {!lista ? <div className="ca-empty">Cargando…</div> : (
          <>
            <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: "46vh", overflowY: "auto", marginBottom: 14 }}>
              {lista.map((s) => (
                <div key={s.id} className="ca-adjrow">
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 14, fontWeight: 500 }}>{s.nombre}</div>
                    {s.especialidad && <div className="ca-pmeta">{s.especialidad}</div>}
                  </div>
                  <span style={{ fontSize: 12.5, color: "var(--muted)" }}>S/</span>
                  <input className="ca-input" style={{ width: 78, marginTop: 0, textAlign: "right" }} defaultValue={s.precio}
                    onBlur={(e) => { if (e.target.value && String(e.target.value) !== String(s.precio)) guardarPrecio(s, e.target.value); }} inputMode="decimal" />
                  <button className="ca-iconbtn" title="Eliminar" onClick={() => eliminar(s)}><Trash2 size={14} strokeWidth={2} /></button>
                </div>
              ))}
            </div>
            <div className="ca-label" style={{ marginBottom: 6 }}>Agregar servicio</div>
            <div style={{ display: "flex", gap: 8 }}>
              <input className="ca-input" style={{ flex: 1.6, marginTop: 0 }} value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre (ej. Ecografía)" />
              <input className="ca-input" style={{ width: 84, marginTop: 0 }} value={precio} onChange={(e) => setPrecio(e.target.value)} placeholder="S/" inputMode="decimal" />
              <button className="ca-btn" onClick={agregar}>Añadir</button>
            </div>
            <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 12 }}>Edita un precio y haz clic afuera para guardarlo. Solo el admin puede cambiar precios.</div>
          </>
        )}
      </div>
    </div>
  );
}

const ROLES = [
  { v: "medico", l: "Psicólogo/a" },
  { v: "asistente", l: "Asistente" },
  { v: "admin", l: "Administrador" },
];
const ROL_COLOR = {
  admin: { bg: "#EDE6F4", fg: "#6B4E96" },
  medico: { bg: "#E3F0E8", fg: "#2F6B4F" },
  asistente: { bg: "#E2ECF5", fg: "#2E5C86" },
};

const SEDES = [{ v: "piura", l: "Piura" }, { v: "lima", l: "Lima" }];
const MODALIDADES = [
  { v: "presencial", l: "Presencial" }, { v: "virtual", l: "Virtual" }, { v: "ambas", l: "Presencial y virtual" },
];

function Profesionales({ showToast, esAdmin }) {
  const [lista, setLista] = useState(null);
  const [editar, setEditar] = useState(null);
  const [sede, setSede] = useState(null);

  async function cargar() { setLista(await api.profesionales()); }
  useEffect(() => { cargar().catch((e) => showToast("Error: " + e.message)); }, []);

  async function guardar(data, foto) {
    try {
      const prof = data.id ? await api.actualizarProfesional(data.id, data) : await api.crearProfesional(data);
      if (foto) await api.subirFotoProfesional(prof.id, foto);
      await cargar();
      setEditar(null);
      showToast(data.id ? "Ficha actualizada ✓" : "Profesional agregado ✓");
    } catch (e) { showToast("Error: " + e.message); }
  }
  async function eliminar(p) {
    if (!window.confirm(`¿Eliminar a ${p.nombre} del directorio?`)) return;
    try { await api.eliminarProfesional(p.id); await cargar(); showToast("Profesional eliminado"); }
    catch (e) { showToast("Error: " + e.message); }
  }

  const filtradas = (lista || []).filter((p) => !sede || p.sede === sede);

  return (
    <div>
      <div className="ca-tophead">
        <div>
          <h1 className="ca-h1">Profesionales</h1>
          <div className="ca-sub">Directorio del equipo{lista ? ` · ${lista.length}` : ""}</div>
        </div>
        {esAdmin && <button className="ca-btn" onClick={() => setEditar({ new: true })}><Plus size={16} strokeWidth={2.2} /> Nuevo profesional</button>}
      </div>

      <div className="ca-fchips" style={{ marginTop: 18 }}>
        <button className={`ca-fchip ${!sede ? "on" : ""}`} onClick={() => setSede(null)}>Todos</button>
        {SEDES.map((s) => <button key={s.v} className={`ca-fchip ${sede === s.v ? "on" : ""}`} onClick={() => setSede(s.v)}>{s.l}</button>)}
      </div>

      {!lista ? <div className="ca-empty">Cargando…</div> : filtradas.length === 0 ? (
        <div className="ca-empty">No hay profesionales{sede ? " en esta sede" : ""} todavía.</div>
      ) : (
        <div className="ca-profgrid">
          {filtradas.map((p) => (
            <div key={p.id} className="ca-profcard" style={{ opacity: p.activo ? 1 : 0.55 }}>
              <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 10 }}>
                {p.foto_url
                  ? <img src={p.foto_url} alt={p.nombre} className="ca-proffoto" />
                  : <div className="ca-avatar" style={{ width: 54, height: 54, fontSize: 18, borderRadius: 12 }}>{iniciales(p.nombre)}</div>}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 15.5 }}>{p.nombre}</div>
                  <div className="ca-pmeta">{p.titulo}{p.colegiatura ? ` · C.PS.P ${p.colegiatura}` : ""}</div>
                  <div style={{ display: "flex", gap: 6, marginTop: 5, flexWrap: "wrap" }}>
                    <Tag colors={{ bg: "var(--accent-soft)", fg: "var(--accent)" }}>{p.sede_label}</Tag>
                    <Tag colors={{ bg: "#EFEDE8", fg: "#7C7870" }}>{p.modalidad_label}</Tag>
                    {!p.activo && <Tag colors={{ bg: "#F7E5E5", fg: "#9C4646" }}>Inactivo</Tag>}
                  </div>
                </div>
              </div>
              {p.enfoque && <div style={{ fontSize: 13, color: "var(--ink-soft)", lineHeight: 1.5, marginBottom: 6 }}>{p.enfoque}</div>}
              {p.poblaciones && <div className="ca-pmeta" style={{ marginBottom: 6 }}><b>Atiende:</b> {p.poblaciones}</div>}
              {p.frase && <div style={{ fontSize: 12.5, fontStyle: "italic", color: "var(--muted)", marginTop: 4 }}>“{p.frase}”</div>}
              {esAdmin && (
                <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                  <button className="ca-mini" onClick={() => setEditar(p)}><Pencil size={13} strokeWidth={2} /> Editar ficha</button>
                  <button className="ca-iconbtn" title="Eliminar" onClick={() => eliminar(p)}><Trash2 size={14} strokeWidth={2} /></button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {editar && <ProfesionalModal prof={editar.new ? null : editar} onClose={() => setEditar(null)} onSave={guardar} />}
    </div>
  );
}

function ProfesionalModal({ prof, onClose, onSave }) {
  const [f, setF] = useState({
    nombre: prof?.nombre || "", titulo: prof?.titulo || "Lic. Psicología", colegiatura: prof?.colegiatura || "",
    sede: prof?.sede || "piura", modalidad: prof?.modalidad || "ambas",
    enfoque: prof?.enfoque || "", poblaciones: prof?.poblaciones || "",
    problematicas: prof?.problematicas || "", formacion: prof?.formacion || "", trayectoria: prof?.trayectoria || "",
    frase: prof?.frase || "", activo: prof?.activo ?? true,
  });
  const [foto, setFoto] = useState(null);
  const set = (k) => (e) => setF((prev) => ({ ...prev, [k]: e.target.value }));
  const canSave = f.nombre.trim().length > 0;
  const ta = { minHeight: 70, resize: "vertical", lineHeight: 1.5 };

  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 560 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <strong style={{ fontSize: 16 }}>{prof ? "Editar ficha" : "Nuevo profesional"}</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>

        <div style={{ display: "flex", gap: 11, marginBottom: 12 }}>
          <div style={{ flex: 2 }}><div className="ca-label">Nombre</div><input className="ca-input" value={f.nombre} onChange={set("nombre")} autoFocus /></div>
          <div style={{ flex: 1 }}><div className="ca-label">C.PS.P</div><input className="ca-input" value={f.colegiatura} onChange={set("colegiatura")} placeholder="25662" /></div>
        </div>
        <div style={{ display: "flex", gap: 11, marginBottom: 12 }}>
          <div style={{ flex: 1.4 }}><div className="ca-label">Título</div><input className="ca-input" value={f.titulo} onChange={set("titulo")} /></div>
          <div style={{ flex: 1 }}><div className="ca-label">Sede</div><select className="ca-input" value={f.sede} onChange={set("sede")}>{SEDES.map((s) => <option key={s.v} value={s.v}>{s.l}</option>)}</select></div>
          <div style={{ flex: 1 }}><div className="ca-label">Modalidad</div><select className="ca-input" value={f.modalidad} onChange={set("modalidad")}>{MODALIDADES.map((m) => <option key={m.v} value={m.v}>{m.l}</option>)}</select></div>
        </div>
        <div style={{ marginBottom: 12 }}><div className="ca-label">Enfoque</div><textarea className="ca-input" style={ta} value={f.enfoque} onChange={set("enfoque")} placeholder="Psicoterapeuta clínica con enfoque…" /></div>
        <div style={{ marginBottom: 12 }}><div className="ca-label">Poblaciones que atiende</div><input className="ca-input" value={f.poblaciones} onChange={set("poblaciones")} placeholder="Niños, adolescentes, adultos, parejas" /></div>
        <div style={{ marginBottom: 12 }}><div className="ca-label">Problemáticas que acompaña</div><textarea className="ca-input" style={ta} value={f.problematicas} onChange={set("problematicas")} /></div>
        <div style={{ marginBottom: 12 }}><div className="ca-label">Formación / especialidades</div><textarea className="ca-input" style={ta} value={f.formacion} onChange={set("formacion")} /></div>
        <div style={{ marginBottom: 12 }}><div className="ca-label">Trayectoria</div><textarea className="ca-input" style={ta} value={f.trayectoria} onChange={set("trayectoria")} /></div>
        <div style={{ marginBottom: 12 }}><div className="ca-label">Frase / lema</div><input className="ca-input" value={f.frase} onChange={set("frase")} /></div>
        <div style={{ display: "flex", gap: 16, alignItems: "center", marginBottom: 18, flexWrap: "wrap" }}>
          <label className="ca-upload" style={{ cursor: "pointer" }}>
            <Paperclip size={14} strokeWidth={2} /> {foto ? foto.name : "Subir foto"}
            <input type="file" accept="image/*" hidden onChange={(e) => setFoto(e.target.files[0] || null)} />
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 13.5, color: "var(--ink-soft)", cursor: "pointer" }}>
            <input type="checkbox" checked={f.activo} onChange={(e) => setF((prev) => ({ ...prev, activo: e.target.checked }))} /> Activo
          </label>
        </div>

        <div style={{ display: "flex", gap: 9, justifyContent: "flex-end" }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" style={{ opacity: canSave ? 1 : 0.5, pointerEvents: canSave ? "auto" : "none" }}
            onClick={() => onSave({ ...(prof?.id ? { id: prof.id } : {}), ...f, nombre: f.nombre.trim() }, foto)}>Guardar</button>
        </div>
      </div>
    </div>
  );
}

function CambiarPasswordModal({ onClose, onSave }) {
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [rep, setRep] = useState("");
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const canSave = actual && nueva.length >= 6 && nueva === rep && !guardando;

  async function guardar() {
    if (nueva !== rep) { setError("Las contraseñas nuevas no coinciden."); return; }
    setGuardando(true); setError("");
    try { await onSave(actual, nueva); }
    catch (e) { setError(e.message); setGuardando(false); }
  }

  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 360 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <strong style={{ fontSize: 16 }}>Cambiar mi contraseña</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>
        <div style={{ marginBottom: 12 }}>
          <div className="ca-label">Contraseña actual</div>
          <input className="ca-input" type="password" value={actual} onChange={(e) => setActual(e.target.value)} autoFocus />
        </div>
        <div style={{ marginBottom: 12 }}>
          <div className="ca-label">Nueva contraseña</div>
          <input className="ca-input" type="password" value={nueva} onChange={(e) => setNueva(e.target.value)} placeholder="mínimo 6 caracteres" />
        </div>
        <div style={{ marginBottom: 14 }}>
          <div className="ca-label">Repetir nueva contraseña</div>
          <input className="ca-input" type="password" value={rep} onChange={(e) => setRep(e.target.value)} />
        </div>
        {error && <div style={{ fontSize: 13, color: "#B4564E", marginBottom: 12 }}>{error}</div>}
        <div style={{ display: "flex", gap: 9, justifyContent: "flex-end" }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" style={{ opacity: canSave ? 1 : 0.5, pointerEvents: canSave ? "auto" : "none" }} onClick={guardar}>
            {guardando ? "Guardando…" : "Cambiar"}
          </button>
        </div>
      </div>
    </div>
  );
}

const FILTROS_ROL = [
  { v: null, l: "Todos" }, { v: "medico", l: "Médicos" },
  { v: "asistente", l: "Asistentes" }, { v: "admin", l: "Administradores" },
  { v: "inactivos", l: "Inactivos" },
];

function Equipo({ showToast, miId }) {
  const [lista, setLista] = useState(null);
  const [editar, setEditar] = useState(null);
  const [q, setQ] = useState("");
  const [filtroRol, setFiltroRol] = useState(null);

  const filtradas = (lista || []).filter((u) => {
    const t = q.trim().toLowerCase();
    const okQ = !t || (u.nombre || "").toLowerCase().includes(t) || u.email.toLowerCase().includes(t) || (u.telefono || "").toLowerCase().includes(t);
    const okR = !filtroRol ? true : filtroRol === "inactivos" ? !u.is_active : u.rol === filtroRol;
    return okQ && okR;
  });

  async function cargar() { setLista(await api.usuarios()); }
  useEffect(() => { cargar().catch((e) => showToast("Error: " + e.message)); }, []);

  async function guardar(data) {
    try {
      if (data.id) {
        const { id, password, ...rest } = data;
        await api.actualizarUsuario(id, rest);
        if (password) await api.resetPasswordUsuario(id, password);
        showToast("Usuario actualizado ✓");
      } else {
        await api.crearUsuario(data);
        showToast("Usuario creado ✓");
      }
      await cargar(); setEditar(null);
    } catch (e) { showToast("Error: " + e.message); }
  }
  async function desactivar(u) {
    try { await api.desactivarUsuario(u.id); await cargar(); showToast("Usuario desactivado"); }
    catch (e) { showToast("Error: " + e.message); }
  }
  async function reactivar(u) {
    try { await api.actualizarUsuario(u.id, { is_active: true }); await cargar(); showToast("Usuario reactivado ✓"); }
    catch (e) { showToast("Error: " + e.message); }
  }

  return (
    <div>
      <div className="ca-tophead">
        <div>
          <h1 className="ca-h1">Equipo</h1>
          <div className="ca-sub">Médicos, asistentes y administradores de la clínica</div>
        </div>
        <button className="ca-btn" onClick={() => setEditar({ new: true })}><UserPlus size={16} strokeWidth={2.1} /> Nuevo usuario</button>
      </div>

      <ConfigClinica showToast={showToast} />

      <div className="ca-card" style={{ marginTop: 22 }}>
        <div className="ca-secth" style={{ margin: "0 0 10px" }}>¿Qué puede hacer cada rol?</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 9, fontSize: 13.5, color: "var(--ink-soft)", lineHeight: 1.5 }}>
          <div><Tag colors={ROL_COLOR.admin}>Administrador</Tag> <span style={{ marginLeft: 4 }}>Ve todo: gerencia, finanzas (ingresos y egresos), equipo y configuración. Gestiona usuarios y precios.</span></div>
          <div><Tag colors={ROL_COLOR.medico}>Psicólogo/a</Tag> <span style={{ marginLeft: 4 }}>Atiende sesiones y registra la historia clínica. Ve agenda, pacientes y cobros; no ve gerencia ni egresos.</span></div>
          <div><Tag colors={ROL_COLOR.asistente}>Asistente</Tag> <span style={{ marginLeft: 4 }}>Agenda sesiones, gestiona pacientes y registra cobros. No escribe historia clínica ni ve egresos/gerencia.</span></div>
        </div>
      </div>

      <div className="ca-search" style={{ marginTop: 22 }}>
        <Search size={16} strokeWidth={2} style={{ color: "var(--muted)" }} />
        <input placeholder="Buscar por nombre, correo o teléfono…" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <div className="ca-fchips">
        {FILTROS_ROL.map((f) => (
          <button key={f.l} className={`ca-fchip ${filtroRol === f.v ? "on" : ""}`} onClick={() => setFiltroRol(f.v)}>{f.l}</button>
        ))}
      </div>

      {!lista ? <div className="ca-empty">Cargando…</div> : (
        <div style={{ marginTop: 18 }}>
          {filtradas.length === 0 ? (
            <div className="ca-empty">{lista.length === 0 ? "Aún no hay usuarios. Crea el primero con el botón de arriba." : "Ningún usuario con ese filtro o búsqueda."}</div>
          ) : filtradas.map((u) => (
            <div key={u.id} className="ca-row" style={{ opacity: u.is_active ? 1 : 0.55 }}>
              <div className="ca-avatar">{iniciales(u.nombre || u.email)}</div>
              <div style={{ flex: 1, minWidth: 150 }}>
                <div className="ca-pname">{u.nombre || u.email}</div>
                <div className="ca-pmeta">{u.email}{u.telefono ? ` · ${u.telefono}` : ""}{u.especialidad ? ` · ${u.especialidad}` : ""}</div>
              </div>
              <Tag colors={ROL_COLOR[u.rol]}>{u.rol_label}</Tag>
              {!u.is_active && <Tag colors={{ bg: "#F7E5E5", fg: "#9C4646" }}>Inactivo</Tag>}
              <div className="ca-actions">
                <button className="ca-mini" onClick={() => setEditar(u)}><Pencil size={13} strokeWidth={2} /> Editar</button>
                {u.id !== miId && (u.is_active ? (
                  <button className="ca-iconbtn" title="Desactivar" onClick={() => desactivar(u)}><X size={14} strokeWidth={2} /></button>
                ) : (
                  <button className="ca-mini" onClick={() => reactivar(u)}><Check size={13} strokeWidth={2.2} /> Reactivar</button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {editar && <UsuarioModal usuario={editar.new ? null : editar} onClose={() => setEditar(null)} onSave={guardar} />}
    </div>
  );
}

function UsuarioModal({ usuario, onClose, onSave }) {
  const [nombre, setNombre] = useState(usuario?.nombre || "");
  const [email, setEmail] = useState(usuario?.email || "");
  const [rol, setRol] = useState(usuario?.rol || "medico");
  const [esp, setEsp] = useState(usuario?.especialidad || "");
  const [telefono, setTelefono] = useState(usuario?.telefono || "");
  const [password, setPassword] = useState("");
  const esNuevo = !usuario;
  const canSave = nombre.trim() && (esNuevo ? (email.trim() && password.length >= 6) : true);

  function guardar() {
    const data = {
      ...(usuario?.id ? { id: usuario.id } : {}),
      nombre: nombre.trim(), rol, telefono: telefono.trim(),
      especialidad: rol === "medico" ? esp.trim() : "",
    };
    if (esNuevo) { data.email = email.trim(); data.password = password; }
    else if (password) data.password = password;
    onSave(data);
  }

  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 400 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <strong style={{ fontSize: 16 }}>{esNuevo ? "Nuevo usuario" : "Editar usuario"}</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>

        <div style={{ marginBottom: 13 }}>
          <div className="ca-label">Nombre completo</div>
          <input className="ca-input" value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre y apellidos" autoFocus />
        </div>
        <div style={{ marginBottom: 13 }}>
          <div className="ca-label">Correo {esNuevo ? "(será su usuario)" : ""}</div>
          <input className="ca-input" value={email} disabled={!esNuevo} onChange={(e) => setEmail(e.target.value)}
            placeholder="correo@clinica.pe" style={{ opacity: esNuevo ? 1 : 0.6 }} />
        </div>
        <div style={{ marginBottom: 13 }}>
          <div className="ca-label">Teléfono <span style={{ color: "var(--muted)", fontWeight: 400 }}>(opcional)</span></div>
          <input className="ca-input" value={telefono} onChange={(e) => setTelefono(e.target.value)} placeholder="987 654 321" />
        </div>
        <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Rol</div>
            <select className="ca-input" value={rol} onChange={(e) => setRol(e.target.value)}>
              {ROLES.map((r) => <option key={r.v} value={r.v}>{r.l}</option>)}
            </select>
          </div>
          {rol === "medico" && (
            <div style={{ flex: 1.2 }}>
              <div className="ca-label">Especialidad</div>
              <select className="ca-input" value={esp || Object.keys(SPECIALTY)[0]} onChange={(e) => setEsp(e.target.value)}>
                {Object.keys(SPECIALTY).map((s) => <option key={s}>{s}</option>)}
              </select>
            </div>
          )}
        </div>
        <div style={{ marginBottom: 20 }}>
          <div className="ca-label">{esNuevo ? "Contraseña" : "Nueva contraseña (opcional)"}</div>
          <input className="ca-input" type="text" value={password} onChange={(e) => setPassword(e.target.value)}
            placeholder={esNuevo ? "mínimo 6 caracteres" : "dejar en blanco para no cambiar"} />
        </div>

        <div style={{ display: "flex", gap: 9, justifyContent: "flex-end" }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" style={{ opacity: canSave ? 1 : 0.5, pointerEvents: canSave ? "auto" : "none" }} onClick={guardar}>Guardar</button>
        </div>
      </div>
    </div>
  );
}

function PacienteModal({ paciente, onClose, onSave }) {
  const [nombre, setNombre] = useState(paciente?.nombre || "");
  const [fechaNac, setFechaNac] = useState(paciente?.fecha_nacimiento || "");
  const [tel, setTel] = useState(paciente?.tel && paciente.tel !== "—" ? paciente.tel : "");
  const [esp, setEsp] = useState(paciente?.especialidad || "Terapia individual");
  const [tipoDoc, setTipoDoc] = useState(paciente?.tipo_documento || "dni");
  const [numDoc, setNumDoc] = useState(paciente?.numero_documento || "");
  const [direccion, setDireccion] = useState(paciente?.direccion || "");
  const [genero, setGenero] = useState(paciente?.genero || "");
  const [alergias, setAlergias] = useState(paciente?.alergias || "");
  const [antecedentes, setAntecedentes] = useState(paciente?.antecedentes || "");
  const [medicacion, setMedicacion] = useState(paciente?.medicacion_habitual || "");
  const canSave = nombre.trim().length > 0;

  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 440 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <strong style={{ fontSize: 16 }}>{paciente ? "Editar paciente" : "Nuevo paciente"}</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>
        <div style={{ marginBottom: 13 }}>
          <div className="ca-label">Nombre completo</div>
          <input className="ca-input" value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre y apellidos" />
        </div>
        <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
          <div style={{ flex: 1.2 }}>
            <div className="ca-label">Fecha de nacimiento</div>
            <input className="ca-input" type="date" value={fechaNac || ""} onChange={(e) => setFechaNac(e.target.value)} />
          </div>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Teléfono</div>
            <input className="ca-input" value={tel} onChange={(e) => setTel(e.target.value)} placeholder="987 654 321" />
          </div>
        </div>
        <div style={{ marginBottom: 16 }}>
          <div className="ca-label">Especialidad habitual</div>
          <select className="ca-input" value={esp} onChange={(e) => setEsp(e.target.value)}>
            {Object.keys(SPECIALTY).map((s) => <option key={s}>{s}</option>)}
          </select>
        </div>

        <div className="ca-secth" style={{ margin: "4px 0 12px" }}>Identificación</div>
        <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Tipo de documento</div>
            <select className="ca-input" value={tipoDoc} onChange={(e) => setTipoDoc(e.target.value)}>
              {TIPOS_DOC.map((t) => <option key={t.v} value={t.v}>{t.l}</option>)}
            </select>
          </div>
          <div style={{ flex: 1.2 }}>
            <div className="ca-label">Número</div>
            <input className="ca-input" value={numDoc} onChange={(e) => setNumDoc(e.target.value)} placeholder="Ej. 12345678" inputMode="numeric" />
          </div>
        </div>
        <div style={{ display: "flex", gap: 11, marginBottom: 20 }}>
          <div style={{ flex: 2 }}>
            <div className="ca-label">Dirección</div>
            <input className="ca-input" value={direccion} onChange={(e) => setDireccion(e.target.value)} placeholder="Calle, urbanización, distrito…" />
          </div>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Género</div>
            <select className="ca-input" value={genero} onChange={(e) => setGenero(e.target.value)}>
              {GENEROS.map((g) => <option key={g.v} value={g.v}>{g.l}</option>)}
            </select>
          </div>
        </div>

        <div className="ca-secth" style={{ margin: "4px 0 12px" }}>Antecedentes</div>
        <div style={{ marginBottom: 13 }}>
          <div className="ca-label">Alergias</div>
          <textarea className="ca-input" style={{ minHeight: 52, resize: "vertical", lineHeight: 1.5 }} value={alergias}
            onChange={(e) => setAlergias(e.target.value)} placeholder="Penicilina, mariscos… (vacío si no se conocen)" />
        </div>
        <div style={{ marginBottom: 13 }}>
          <div className="ca-label">Antecedentes / condiciones</div>
          <textarea className="ca-input" style={{ minHeight: 52, resize: "vertical", lineHeight: 1.5 }} value={antecedentes}
            onChange={(e) => setAntecedentes(e.target.value)} placeholder="Enfermedades crónicas, cirugías previas, antecedentes familiares…" />
        </div>
        <div style={{ marginBottom: 20 }}>
          <div className="ca-label">Medicación habitual</div>
          <textarea className="ca-input" style={{ minHeight: 52, resize: "vertical", lineHeight: 1.5 }} value={medicacion}
            onChange={(e) => setMedicacion(e.target.value)} placeholder="Medicamentos que toma de forma habitual…" />
        </div>

        <div style={{ display: "flex", gap: 9, justifyContent: "flex-end" }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" style={{ opacity: canSave ? 1 : 0.5, pointerEvents: canSave ? "auto" : "none" }}
            onClick={() => onSave({ ...(paciente?.id ? { id: paciente.id } : {}), nombre: nombre.trim(), fecha_nacimiento: fechaNac || null, tel: tel.trim(), especialidad: esp, tipo_documento: tipoDoc, numero_documento: numDoc.trim(), direccion: direccion.trim(), genero, alergias: alergias.trim(), antecedentes: antecedentes.trim(), medicacion_habitual: medicacion.trim() })}>
            Guardar
          </button>
        </div>
      </div>
    </div>
  );
}
