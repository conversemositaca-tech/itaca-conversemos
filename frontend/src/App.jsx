import React, { useState, useMemo, useEffect } from "react";
import { createPortal } from "react-dom";
import {
  Home, Calendar, Users, Receipt, Search, Plus, Clock, ChevronLeft, ChevronDown,
  Phone, Cake, X, Stethoscope, MessageCircle, Check, Pencil, UserPlus, FileText,
  TrendingUp, Download, AlertTriangle, Megaphone, LogOut,
  Paperclip, Trash2, Activity, Pill, HeartPulse, Copy, BarChart3, UserCog, KeyRound, MapPin,
  Mic, FolderOpen, Lightbulb, ExternalLink, Bell, GraduationCap,
  Building2, DoorOpen, ChevronRight, Compass, Send,
  Shield, Target, Heart, Leaf, Trophy, Award, Sparkles, Landmark,
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
  "Consulta psicológica": { bg: "#E1F0FB", fg: "#2A6FA6", dot: "💬" },
  "Sesión brújula": { bg: "#E8F5E9", fg: "#2E7D52", dot: "🧭" },
  "Constancia de terapia": { bg: "#F3EEE6", fg: "#8A6D3B", dot: "📄" },
  "Reprogramación": { bg: "#FDE9E7", fg: "#B4564E", dot: "🔁" },
};

// ---- Plantillas de nota por especialidad ----
const TEMPLATES = {
  "Terapia individual": "Motivo de consulta:\n\nEstado de ánimo:\n\nTemas trabajados:\n\nAvances / observaciones:\n\nTarea para la próxima sesión:\n\nPróxima sesión:",
  "Terapia de pareja": "Asistentes a la sesión:\n\nMotivo / conflicto principal:\n\nDinámica observada:\n\nAcuerdos de la sesión:\n\nTarea para casa:\n\nPróxima sesión:",
  "Terapia familiar": "Participantes:\n\nMotivo de consulta:\n\nDinámica familiar observada:\n\nIntervenciones:\n\nAcuerdos / tareas:\n\nPróxima sesión:",
  "Terapia infantil/adolescente": "Motivo de consulta:\n\nObservación (juego / conducta):\n\nTemas trabajados:\n\nIndicaciones a los padres:\n\nTarea:\n\nPróxima sesión:",
  "Evaluación psicológica": "Motivo de la evaluación:\n\nPruebas aplicadas:\n\nObservaciones:\n\nResultados / hallazgos:\n\nConclusiones y recomendaciones:",
};

// Guía de notas — Decisión del Paciente (DP). Estandariza cómo se registra la
// decisión del paciente/apoderado/pareja tras la orientación clínica.
// Al elegir un código se inserta "DP-XX | Etiqueta. " en la nota para completar.
const DP_CODES = [
  { cat: "Inicio", items: [
    { c: "DP-01", l: "Inicia proceso" },
    { c: "DP-02", l: "Solicita tiempo para decidir" },
    { c: "DP-03", l: "Seguimiento posterior" },
    { c: "DP-04", l: "No inicia proceso" },
  ] },
  { cat: "Servicios específicos", items: [
    { c: "DP-05", l: "Evaluación psicológica" },
    { c: "DP-06", l: "Informe psicológico" },
    { c: "DP-07", l: "Convenio / Empresa" },
  ] },
  { cat: "Continuidad", items: [
    { c: "DP-08", l: "Continúa proceso" },
    { c: "DP-09", l: "Suspensión temporal / Finaliza proceso" },
    { c: "DP-10", l: "Alta terapéutica" },
  ] },
  { cat: "Derivaciones e interconsultas", items: [
    { c: "DP-11", l: "Derivación interna" },
    { c: "DP-12", l: "Derivación externa" },
    { c: "DP-13", l: "Interconsulta (interna o externa)" },
  ] },
  { cat: "Dificultades o barreras", items: [
    { c: "DP-14", l: "Limitación económica" },
    { c: "DP-15", l: "Limitación de horario" },
    { c: "DP-16", l: "Inconformidad con la atención" },
  ] },
];

// Estados de cita (claves = códigos del backend).
const STATUS = {
  agendada: { bg: "#E7EEF6", fg: "#3D5C82" },
  confirmada: { bg: "#E9F1ED", fg: "#3E7A65" },
  en_espera: { bg: "#FFF4DA", fg: "#9A7B1E" },
  pendiente: { bg: "#F7ECDD", fg: "#9C6B2E" },
  asistio: { bg: "#E1F2E8", fg: "#2E7D52" },
  no_asistio: { bg: "#F7E5E5", fg: "#9C4646" },
  atendida: { bg: "#EFEDE8", fg: "#7C7870" },
  reprogramada: { bg: "#EAE6F2", fg: "#6B5B9C" },
  cancelada: { bg: "#F7E5E5", fg: "#9C4646" },
  por_confirmar: { bg: "#F7ECDD", fg: "#9C6B2E" },
};

// Color de la cita en la agenda por su ESTADO DE PAGO/confirmación (pedido de las
// coordinadoras, como en AgendaPro): verde = pagada, azul = confirmada pero falta
// pago, ámbar = por confirmar (perseguir), gris = cancelada / no asistió.
function colorCita(c) {
  if (!c) return { bg: "#FBEBC7", fg: "#9A6B1E", l: "Por confirmar" };
  if (c.estado === "cancelada" || c.estado === "no_asistio")
    return { bg: "#E8E5E0", fg: "#7C766C", l: "Cancelada / no asistió" };
  if (c.cobrada)
    return { bg: "#CFEEDD", fg: "#1F7A47", l: "Pagada" };
  if (c.estado === "confirmada" || c.estado === "asistio" || c.estado === "atendida")
    return { bg: "#D3E4F7", fg: "#2E5C93", l: "Confirmada · falta pago" };
  return { bg: "#FBEBC7", fg: "#9A6B1E", l: "Por confirmar" };
}
const COLOR_CITA_LEYENDA = [
  { bg: "#CFEEDD", fg: "#1F7A47", l: "Pagada" },
  { bg: "#D3E4F7", fg: "#2E5C93", l: "Confirmada · falta pago" },
  { bg: "#FBEBC7", fg: "#9A6B1E", l: "Por confirmar" },
  { bg: "#E8E5E0", fg: "#7C766C", l: "Cancelada / no asistió" },
];

// Estados que el coordinador puede fijar desde la fila de la agenda.
const ESTADOS_CITA = [
  { v: "agendada", l: "Agendada" },
  { v: "confirmada", l: "Confirmada" },
  { v: "en_espera", l: "En espera" },
  { v: "pendiente", l: "Pendiente" },
  { v: "asistio", l: "Asistió" },
  { v: "no_asistio", l: "No asistió" },
  { v: "atendida", l: "Atendida" },
  { v: "reprogramada", l: "Reprogramada" },
  { v: "cancelada", l: "Cancelada" },
];

const MENSAJE_ESTADO = {
  enviado: { bg: "#E9F1ED", fg: "#3E7A65" },
  fallido: { bg: "#F7E5E5", fg: "#9C4646" },
  no_configurado: { bg: "#F7ECDD", fg: "#9C6B2E" },
};

const LEAD_ESTADOS = [
  { v: "nuevo", l: "Nuevo" },
  { v: "contactado", l: "Contactado" },
  { v: "seguimiento", l: "En seguimiento" },
  { v: "recontacto", l: "Recontactar" },
  { v: "agendado", l: "Consulta agendada" },
  { v: "agendo_no_pago", l: "Agendó, no pagó" },
  { v: "agendo_espera_pago", l: "Agendó, esperando pago" },
  { v: "no_realizada", l: "Consulta no realizada" },
  { v: "evaluando", l: "Evaluando inicio" },
  { v: "pendiente_pago", l: "Pendiente de pago" },
  { v: "ganado", l: "Inició proceso" },
  { v: "perdido", l: "Perdido" },
];
// Semáforo de leads (pedido de Gaby): verde=lead activo ok, amarillo=hacer
// seguimiento, naranja=hay que verificar/recontactar, rojo=seguimiento espaciado.
const _VERDE = { bg: "#E4F3E8", fg: "#1E7D45" };
const _AMARILLO = { bg: "#FCF3D4", fg: "#8A6D14" };
const _NARANJA = { bg: "#FBE7D4", fg: "#B5701F" };
const _ROJO = { bg: "#F7E5E5", fg: "#9C4646" };
const LEAD_ESTADO_COLOR = {
  nuevo: { bg: "#EFEDE8", fg: "#7C7870" },
  agendado: _VERDE,        // consulta agendada
  ganado: _VERDE,          // inició proceso
  agendo_no_pago: _NARANJA,     // agendó pero no pagó: perseguir el pago
  agendo_espera_pago: _AMARILLO, // agendó, esperando confirmación de pago
  contactado: _AMARILLO,
  seguimiento: _AMARILLO,
  evaluando: _AMARILLO,
  pendiente_pago: _AMARILLO,
  recontacto: _NARANJA,
  no_realizada: _ROJO,     // consulta no realizada
  perdido: _ROJO,
};
const LEAD_FRECUENCIAS = [{ v: "", l: "—" }, { v: "semanal", l: "Semanal" }, { v: "quincenal", l: "Quincenal" }];
// Orígenes de captación (lista limpia). Los valores antiguos (instagram, meta_ads,
// etc.) siguen mostrándose bien porque su etiqueta viene del backend; aquí solo se
// listan los que se ofrecen al captar/editar un lead.
const FUENTES = [
  { v: "tiktok_ads", l: "TikTok Ads" }, { v: "facebook_ads", l: "Facebook Ads" },
  { v: "bot", l: "Bot / Chatbot" }, { v: "convenio", l: "Convenio" },
  { v: "referido", l: "Referidos" }, { v: "whatsapp", l: "WhatsApp directo" },
  { v: "instagram_directo", l: "Instagram directo" },
  { v: "otro", l: "Otro" },
];
// Orígenes que son pauta/anuncio pagado (muestran «Vino de pauta» y el anuncio).
const FUENTES_PAUTA = ["tiktok_ads", "facebook_ads", "meta_ads", "google", "instagram", "facebook", "tiktok"];
// Subfuentes (canal concreto) por origen. Solo aplican a estos orígenes.
const SUBFUENTES = {
  tiktok_ads: ["WhatsApp", "Mensajería de TikTok"],
  facebook_ads: ["WhatsApp", "Mensajería de Facebook", "Mensajería de Instagram"],
  bot: ["WhatsApp Piura", "WhatsApp Lima"],
  referido: ["Psicólogos", "Paciente", "Gabi", "Emma", "Ayvi", "Yazmin"],
};
const TIPOS_SERVICIO = [
  { v: "", l: "—" }, { v: "adultos", l: "Adultos" }, { v: "ninos", l: "Niños" },
  { v: "adolescentes", l: "Adolescentes" }, { v: "pareja", l: "Pareja" },
  { v: "familia", l: "Familia" }, { v: "lenguaje", l: "Lenguaje" },
  { v: "evaluacion", l: "Evaluación psicológica" }, { v: "otro", l: "Otro" },
];
const LEAD_SEM = {
  verde: { c: "#2BA35A", l: "Al día" }, amarillo: { c: "#E0A82E", l: "1+ día sin contactar" },
  naranja: { c: "#E07B2E", l: "3+ días sin contactar" }, rojo: { c: "#D85656", l: "5+ días — abandonado" },
};
// Tipos de documento clínico (Atencion.tipo).
const TIPOS_HC = [
  { v: "evolucion", l: "Ficha de evolución" },
  { v: "historia", l: "Historia clínica" },
  { v: "continuidad", l: "Ficha de Transición y Continuidad Terapéutica" },
  { v: "informe_continuidad", l: "Informe de continuidad" },
  { v: "informe", l: "Informe psicológico" },
  { v: "derivacion", l: "Derivación" },
  { v: "evaluacion", l: "Evaluación psicológica" },
  { v: "otro", l: "Otro documento clínico" },
];

// Campos de cada tipo de ficha. Cada uno se guarda en un campo del modelo
// Atencion (k), con la etiqueta (l) propia del tipo. Así "evolución" ≠ "derivación".
const FICHAS = {
  historia: [
    { k: "motivo", l: "Motivo de consulta", ph: "¿Por qué viene el paciente?" },
    { k: "aspectos_historicos", l: "Aspectos históricos relevantes", ph: "Antecedentes relevantes…" },
    { k: "objetivos", l: "Objetivos del proceso de terapia", ph: "Metas del proceso…" },
    { k: "diagnostico", l: "Impresión diagnóstica / problemática a tratar", ph: "Impresión diagnóstica…" },
  ],
  evolucion: [
    { k: "nota", l: "Resumen de la sesión", ph: "¿Qué se trabajó en la sesión?" },
    { k: "puntos_importantes", l: "Puntos importantes a recordar", ph: "Observaciones clave…" },
    { k: "proximos_pasos", l: "Próximos pasos a seguir", ph: "Qué abordar la próxima sesión…" },
    { k: "indicaciones", l: "Tratamiento / tareas asignadas", ph: "Tareas o actividades…" },
  ],
  continuidad: [
    { k: "nota", l: "Estado actual del paciente", ph: "¿Cómo está hoy el paciente?" },
    { k: "puntos_importantes", l: "Avances", ph: "Avances observados…" },
    { k: "proximos_pasos", l: "Plan a seguir", ph: "Plan de continuidad…" },
  ],
  informe_continuidad: [
    { k: "nota", l: "Resumen del proceso", ph: "Resumen del proceso terapéutico…" },
    { k: "puntos_importantes", l: "Avances logrados", ph: "Logros del proceso…" },
    { k: "indicaciones", l: "Recomendaciones para continuar", ph: "Recomendaciones…" },
  ],
  informe: [
    { k: "motivo", l: "Motivo / objetivo del informe", ph: "Motivo del informe…" },
    { k: "aspectos_historicos", l: "Técnicas / instrumentos aplicados", ph: "Pruebas y técnicas usadas…" },
    { k: "puntos_importantes", l: "Resultados", ph: "Resultados obtenidos…" },
    { k: "diagnostico", l: "Conclusiones", ph: "Conclusiones del informe…" },
    { k: "indicaciones", l: "Recomendaciones", ph: "Recomendaciones…" },
  ],
  derivacion: [
    { k: "motivo", l: "Motivo de la derivación", ph: "¿Por qué se deriva?" },
    { k: "proximos_pasos", l: "A quién / dónde se deriva", ph: "Profesional o servicio destino…" },
    { k: "nota", l: "Resumen del caso", ph: "Resumen para quien recibe…" },
    { k: "indicaciones", l: "Recomendaciones", ph: "Recomendaciones…" },
  ],
  evaluacion: [
    { k: "motivo", l: "Motivo de la evaluación", ph: "Motivo de la evaluación…" },
    { k: "aspectos_historicos", l: "Instrumentos aplicados", ph: "Pruebas aplicadas…" },
    { k: "puntos_importantes", l: "Resultados", ph: "Resultados…" },
    { k: "diagnostico", l: "Impresión diagnóstica", ph: "Impresión diagnóstica…" },
    { k: "indicaciones", l: "Recomendaciones", ph: "Recomendaciones…" },
  ],
  otro: [
    { k: "nota", l: "Contenido del documento", ph: "Escribe el documento…" },
  ],
};
// Etiqueta genérica de cada campo del modelo (para mostrar texto que no calce con el tipo).
const CAMPO_LABEL = {
  motivo: "Motivo", diagnostico: "Diagnóstico / impresión", indicaciones: "Indicaciones / recomendaciones",
  nota: "Nota", aspectos_historicos: "Aspectos históricos", objetivos: "Objetivos",
  puntos_importantes: "Puntos importantes", proximos_pasos: "Próximos pasos",
};
const TODOS_CAMPOS_HC = ["motivo", "nota", "aspectos_historicos", "objetivos", "puntos_importantes", "proximos_pasos", "diagnostico", "indicaciones"];

// ---- Helpers de fecha (zona local) ----
const _MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "set", "oct", "nov", "dic"];
const pad2 = (n) => String(n).padStart(2, "0");
const aISO = (d) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
const dDeISO = (iso) => { const [y, m, d] = iso.split("-").map(Number); return new Date(y, m - 1, d); };
const sumarDias = (iso, n) => { const d = dDeISO(iso); d.setDate(d.getDate() + n); return aISO(d); };
const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);

// ---- Reloj sincronizado con el SERVIDOR (no con el reloj del equipo) ----
// "Hoy" no se toma del reloj del PC/celular (que a veces está mal de fecha o zona
// horaria), sino del servidor, que corre en la hora de la clínica. Guardamos el
// desfase servidor↔equipo y medimos el tiempo transcurrido con Date.now() (el
// desfase se cancela en la resta), así la fecha es correcta aunque el equipo tenga
// mal la hora. La fecha local se lee en UTC tras desplazar por el offset del
// servidor → ignora también la zona horaria del equipo.
const _CLK_KEY = "itaca_reloj";
function _leerReloj() {
  try { return JSON.parse(localStorage.getItem(_CLK_KEY) || "null"); } catch { return null; }
}
function _ahoraServidorMs() {
  const c = _leerReloj();
  return c ? c.serverEpoch + (Date.now() - c.deviceEpoch) : Date.now();
}
function hoyISO() {
  const c = _leerReloj();
  if (!c) return aISO(new Date()); // aún sin sincronizar → cae al reloj del equipo
  const d = new Date(_ahoraServidorMs() + c.offsetMin * 60000);
  return `${d.getUTCFullYear()}-${pad2(d.getUTCMonth() + 1)}-${pad2(d.getUTCDate())}`;
}
const _fechaCorta = (iso) => { const [y, m, d] = iso.split("-").map(Number); return `${d} ${_MESES[m - 1]} ${y}`; };

let HOY_ISO = hoyISO();
// fecha_corta del backend ("12 jun 2026"), para resaltar la atención de hoy en la ficha.
let HOY_FECHA = _fechaCorta(HOY_ISO);

// Sincroniza el reloj con el servidor y actualiza HOY_ISO/HOY_FECHA. Devuelve true
// si cambió el día (para que quien llame recargue). Se llama al arrancar (main.jsx)
// y al volver a la pestaña.
export async function sincronizarReloj() {
  try {
    const r = await api.hora(); // { epoch_ms, offset_min }
    localStorage.setItem(_CLK_KEY, JSON.stringify({
      serverEpoch: r.epoch_ms, deviceEpoch: Date.now(), offsetMin: r.offset_min,
    }));
    const nuevo = hoyISO();
    const cambio = nuevo !== HOY_ISO;
    HOY_ISO = nuevo;
    HOY_FECHA = _fechaCorta(nuevo);
    return cambio;
  } catch { return false; }
}

function semanaDe(iso) {
  const d = dDeISO(iso);
  const lunesOffset = (d.getDay() + 6) % 7; // 0 = lunes
  const lunes = sumarDias(iso, -lunesOffset);
  return Array.from({ length: 7 }, (_, i) => sumarDias(lunes, i));
}
const labelLargo = (iso) => cap(dDeISO(iso).toLocaleDateString("es-PE", { weekday: "long", day: "numeric", month: "long" }));
const labelDiaSemana = (iso) => cap(dDeISO(iso).toLocaleDateString("es-PE", { weekday: "short" }).replace(".", ""));
const labelNumMes = (iso) => { const d = dDeISO(iso); return `${d.getDate()} ${_MESES[d.getMonth()]}`; };
const labelMes = (iso) => cap(dDeISO(iso).toLocaleDateString("es-PE", { month: "long", year: "numeric" }));
// Grilla de un mes: filas de 7 días (lunes primero), rellenando semanas parciales.
function mesDe(iso) {
  const d = dDeISO(iso);
  const primero = aISO(new Date(d.getFullYear(), d.getMonth(), 1));
  const inicio = semanaDe(primero)[0]; // lunes de la 1ª semana
  const dias = [];
  for (let i = 0; i < 42; i++) dias.push(sumarDias(inicio, i));
  // Recorta la última fila si queda entera fuera del mes.
  while (dias.length > 35 && dDeISO(dias[dias.length - 7]).getMonth() !== d.getMonth()) dias.splice(-7);
  return dias;
}
const sumarMeses = (iso, n) => { const d = dDeISO(iso); return aISO(new Date(d.getFullYear(), d.getMonth() + n, Math.min(d.getDate(), 28))); };

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

// Exporta a un archivo .xls que abre Excel (sin librerías: tabla HTML con el mime de Excel).
function descargarExcel(nombre, headers, filas) {
  const esc = (v) => String(v ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const th = headers.map((h) => `<th style="background:#EDE7F6;border:1px solid #ccc;padding:4px 8px;text-align:left">${esc(h)}</th>`).join("");
  const tr = filas.map((f) => `<tr>${f.map((c) => `<td style="border:1px solid #ccc;padding:4px 8px">${esc(c)}</td>`).join("")}</tr>`).join("");
  const html = `<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel" xmlns="http://www.w3.org/TR/REC-html40"><head><meta charset="utf-8"></head><body><table><thead><tr>${th}</tr></thead><tbody>${tr}</tbody></table></body></html>`;
  const blob = new Blob(["﻿" + html], { type: "application/vnd.ms-excel;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = nombre; a.click();
  URL.revokeObjectURL(url);
}

// Abre una ventana con la tabla formateada para imprimir o guardar como PDF (igual que la historia clínica).
function descargarPDF(titulo, headers, filas) {
  const w = window.open("", "_blank", "width=1000,height=800");
  if (!w) { alert("Permite las ventanas emergentes para descargar el PDF."); return; }
  const esc = (v) => String(v ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const th = headers.map((h) => `<th>${esc(h)}</th>`).join("");
  const tr = filas.map((f) => `<tr>${f.map((c) => `<td>${esc(c)}</td>`).join("")}</tr>`).join("");
  w.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>${esc(titulo)}</title>
    <style>
      body{font-family:Inter,Arial,sans-serif;color:#32302C;margin:24px}
      .head{display:flex;justify-content:space-between;align-items:baseline;border-bottom:2px solid #4F8A77;padding-bottom:8px;margin-bottom:14px}
      h1{font-size:18px;margin:0} .sub{color:#888;font-size:12px}
      table{border-collapse:collapse;width:100%;font-size:11px}
      th,td{border:1px solid #ddd;padding:5px 7px;text-align:left;vertical-align:top}
      th{background:#EDE7F6;color:#3A2F46} tr:nth-child(even) td{background:#FAF8FD}
      @media print{body{margin:8mm} .noprint{display:none}}
    </style></head><body>
    <div class="head"><h1>${esc(titulo)}</h1><div class="sub">${filas.length} registro(s)</div></div>
    <table><thead><tr>${th}</tr></thead><tbody>${tr || `<tr><td colspan="${headers.length}">Sin datos.</td></tr>`}</tbody></table>
    <button class="noprint" onclick="window.print()" style="margin-top:16px;padding:9px 16px;border:none;border-radius:7px;background:#4F8A77;color:#fff;font-size:14px;cursor:pointer">Imprimir / Guardar PDF</button>
    </body></html>`);
  w.document.close();
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
  const campoLinea = (etq, val) => (val && val.trim() ? `<p><b>${esc(etq)}:</b> ${esc(val).replace(/\n/g, "<br>")}</p>` : "");
  const ats = (p.historial || []).map((h) => {
    const ficha = FICHAS[h.tipo] || FICHAS.evolucion;
    const mostrados = new Set();
    let cuerpo = "";
    ficha.forEach((c) => { if ((h[c.k] || "").trim()) { cuerpo += campoLinea(c.l, h[c.k]); mostrados.add(c.k); } });
    TODOS_CAMPOS_HC.forEach((k) => { if (!mostrados.has(k) && (h[k] || "").trim()) cuerpo += campoLinea(CAMPO_LABEL[k], h[k]); });
    const tipoLabel = (TIPOS_HC.find((t) => t.v === h.tipo) || {}).l || "";
    return `
    <div class="at">
      <div class="meta">${tipoLabel ? "<b>" + esc(tipoLabel) + "</b> · " : ""}${esc(h.fecha)} · ${esc(h.medico || "")}${h.especialidad ? " · " + esc(h.especialidad) : ""}</div>
      ${vit(h) ? `<p><b>Signos vitales:</b> ${esc(vit(h))}</p>` : ""}
      ${cuerpo}
    </div>`;
  }).join("");
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

// Grupo de botones de descarga (CSV / Excel / PDF) reutilizable en cada tabla.
function ExportBtns({ nombre, titulo, headers, filas, disabled }) {
  const off = disabled || !filas || filas.length === 0;
  const base = String(nombre || "datos").replace(/\.(csv|xlsx?|pdf)$/i, "");
  return (
    <div style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
      <button className="ca-btn ghost" disabled={off} title="Descargar CSV"
        onClick={() => descargarCSV(base + ".csv", headers, filas)}>
        <Download size={15} strokeWidth={2} /> CSV
      </button>
      <button className="ca-btn ghost" disabled={off} title="Descargar Excel"
        onClick={() => descargarExcel(base + ".xls", headers, filas)}>
        <Download size={15} strokeWidth={2} /> Excel
      </button>
      <button className="ca-btn ghost" disabled={off} title="Descargar PDF"
        onClick={() => descargarPDF(titulo || base, headers, filas)}>
        <Download size={15} strokeWidth={2} /> PDF
      </button>
    </div>
  );
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
  const [bloqueos, setBloqueos] = useState([]);
  const [mensajes, setMensajes] = useState([]);
  const [servicios, setServicios] = useState([]);
  const [waPaciente, setWaPaciente] = useState(null);
  const [waCita, setWaCita] = useState(null);
  const [usuario, setUsuario] = useState(null);
  const [iniciando, setIniciando] = useState(true);
  const [query, setQuery] = useState("");
  const [filterEsp, setFilterEsp] = useState(null);
  const [filterSede, setFilterSede] = useState(null);
  const [filterProf, setFilterProf] = useState("");
  const [filterFrec, setFilterFrec] = useState("");
  const [soloSinProxima, setSoloSinProxima] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  // Detalle completo del paciente abierto (historial, citas, adjuntos, paquetes…).
  // La LISTA trae solo lo liviano; el detalle se carga al abrir la ficha.
  const [detalle, setDetalle] = useState(null);
  const [adding, setAdding] = useState(false);
  const [atender, setAtender] = useState(null);
  const [recordar, setRecordar] = useState(null);
  const [reagendar, setReagendar] = useState(null);
  const [cancelando, setCancelando] = useState(null);
  const [cobrando, setCobrando] = useState(null);
  const [citaDetalle, setCitaDetalle] = useState(null);
  const [notaCita, setNotaCita] = useState(null);
  const [bloqueando, setBloqueando] = useState(null);
  const [cambiarPass, setCambiarPass] = useState(false);
  const [agendarPara, setAgendarPara] = useState(null);
  const [vendiendoPaquete, setVendiendoPaquete] = useState(null);
  const [agendaFecha, setAgendaFecha] = useState(HOY_ISO);
  const [agendaVista, setAgendaVista] = useState("dia");
  const [editingPaciente, setEditingPaciente] = useState(null);
  const [registrandoSesion, setRegistrandoSesion] = useState(null);
  const [toast, setToast] = useState("");

  async function cargarDatos() {
    const [pac, cit, msg, srv, blo] = await Promise.all([
      api.pacientes(), api.citas(), api.mensajes(), api.servicios(), api.bloqueos().catch(() => []),
    ]);
    setPacientes(pac); setCitas(cit); setMensajes(msg); setServicios(srv); setBloqueos(blo);
  }
  const refrescarBloqueos = async () => setBloqueos(await api.bloqueos().catch(() => []));
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

  // Trae el detalle completo del paciente (para la ficha). Si falla, la ficha se
  // queda con la fila liviana de la lista (nombre y estado ya alcanzan).
  const cargarDetalle = async (id) => {
    if (!id) { setDetalle(null); return; }
    try { setDetalle(await api.paciente(id)); } catch { /* mantiene lo liviano */ }
  };
  const refrescarPacientes = async () => {
    setPacientes(await api.pacientes());
    if (selectedId) cargarDetalle(selectedId); // mantiene la ficha abierta al día
  };
  const guardarRegistroSesion = async (paciente, datos) => {
    try {
      await api.registrarSesion(paciente.id, datos);
      await refrescarPacientes();
      setRegistrandoSesion(null);
      showToast("Sesión de la semana registrada ✓");
    } catch (e) { showToast("Error: " + e.message); }
  };
  const refrescarCitas = async () => setCitas(await api.citas());
  const refrescarMensajes = async () => setMensajes(await api.mensajes());

  // El detalle completo si ya cargó para este paciente; si no, la fila liviana.
  const selected =
    (detalle && detalle.id === selectedId)
      ? detalle
      : (pacientes.find((p) => p.id === selectedId) || null);
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return pacientes.filter((p) =>
      (!q || p.nombre.toLowerCase().includes(q) || (p.tel || "").toLowerCase().includes(q) || (p.numero_documento || "").toLowerCase().includes(q)) &&
      (!filterEsp || p.especialidad === filterEsp) &&
      (!filterSede || p.sede === filterSede) &&
      (!filterProf || p.profesional_nombre === filterProf) &&
      (!filterFrec || p.frecuencia === filterFrec) &&
      (!soloSinProxima || !p.proxima));
  }, [pacientes, query, filterEsp, filterSede, filterProf, filterFrec, soloSinProxima]);

  // Psicólogos presentes en la lista de pacientes (para el filtro).
  // Psicólogos del filtro: solo los que tienen pacientes en la sede elegida.
  const profsEnPacientes = useMemo(
    () => [...new Set(pacientes.filter((p) => !filterSede || p.sede === filterSede).map((p) => p.profesional_nombre).filter(Boolean))].sort(),
    [pacientes, filterSede]
  );

  const nav = [
    { id: "hoy", label: "Hoy", icon: Home },
    // Mentalidad Ítaca: cultura y funciones. La ve todo el equipo.
    { id: "mentalidad", label: "Mentalidad Ítaca", icon: Compass },
    // El panel de Gerencia lo ve solo el dueño/admin.
    ...(usuario?.rol === "admin" ? [{ id: "gerencia", label: "Gerencia", icon: BarChart3 }] : []),
    ...(usuario?.rol === "admin" ? [{ id: "historico", label: "Histórico", icon: Activity }] : []),
    ...(usuario?.rol === "admin" ? [{ id: "reporte", label: "Reporte", icon: FileText }] : []),
    ...(usuario?.rol === "admin" ? [{ id: "ocupacion", label: "Ocupación", icon: Clock }] : []),
    // Clínico (Agenda, Pacientes, Profesionales): gerencia, coordinación y psicólogo (no comercial).
    ...(usuario?.rol !== "comercial" ? [{ id: "agenda", label: "Agenda", icon: Calendar }] : []),
    ...(usuario?.rol !== "comercial" ? [{ id: "pacientes", label: "Pacientes", icon: Users }] : []),
    // Profesionales (directorio): gerencia y coordinación; el psicólogo no lo ve.
    ...((usuario?.rol !== "comercial" && usuario?.rol !== "medico") ? [{ id: "profesionales", label: "Profesionales", icon: HeartPulse }] : []),
    // Herramientas (materiales para pacientes + tips): equipo clínico (no comercial).
    // Para el psicólogo reemplaza el acceso a Profesionales.
    ...(usuario?.rol !== "comercial" ? [{ id: "herramientas", label: "Herramientas", icon: FolderOpen }] : []),
    // Mensajes: gerencia, coordinación y comercial (no psicólogo).
    ...(usuario?.rol !== "medico" ? [{ id: "mensajes", label: "Mensajes", icon: MessageCircle }] : []),
    // Marketing / Leads: gerencia, comercial y coordinación (asistente).
    ...((usuario?.rol === "admin" || usuario?.rol === "comercial" || usuario?.rol === "asistente") ? [{ id: "marketing", label: "Marketing", icon: Megaphone }] : []),
    // Finanzas: solo gerencia.
    ...(usuario?.rol === "admin" ? [{ id: "finanzas", label: "Finanzas", icon: TrendingUp }] : []),
    ...(usuario?.rol === "admin" ? [{ id: "liquidacion", label: "Liquidación", icon: Receipt }] : []),
    // Espacios profesionales (alquiler de consultorios): solo gerencia.
    ...(usuario?.rol === "admin" ? [{ id: "espacios", label: "Espacios", icon: Building2 }] : []),
    ...(usuario?.rol === "admin" ? [{ id: "equipo", label: "Equipo", icon: UserCog }] : []),
    ...(usuario?.rol === "admin" ? [{ id: "legal", label: "Legal", icon: FileText }] : []),
    ...(usuario?.rol === "admin" ? [{ id: "whatsapp", label: "Conexión WhatsApp", icon: MessageCircle }] : []),
    ...(usuario?.rol === "admin" ? [{ id: "hojas", label: "Editar (Excel)", icon: Pencil }] : []),
    // El buzón de sugerencias lo ve todo el equipo (dejar sugerencia); gerencia además ve la bandeja.
    { id: "buzon", label: "Buzón", icon: MessageCircle },
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
  const porConfirmar = citasHoy.filter((c) => c.estado === "agendada" || c.estado === "por_confirmar").length;
  const atendidas = citasHoy.filter((c) => c.estado === "atendida").length;

  function showToast(msg) { setToast(msg); setTimeout(() => setToast(""), 2800); }
  function go(v) { setView(v); setSelectedId(null); }
  function openFicha(id) { if (!id) return; setView("pacientes"); setSelectedId(id); setDetalle(null); cargarDetalle(id); }

  // `HOY_ISO` se fija al cargar la página (con el reloj del SERVIDOR). Si dejan la
  // pestaña abierta varios días, hay que refrescar el día:
  //  - local (cada minuto, sin red): el reloj sincronizado avanza solo con el tiempo
  //    transcurrido, así que a medianoche `hoyISO()` cambia y recargamos.
  //  - al volver a la pestaña: re-sincronizamos con el servidor (por si el equipo
  //    tenía la hora mal o la corrigieron) y recargamos si cambió el día.
  // Solo recarga cuando cambia el día → nunca mientras están escribiendo.
  useEffect(() => {
    const revisarLocal = () => { if (hoyISO() !== HOY_ISO) window.location.reload(); };
    const reSincronizar = async () => { if (await sincronizarReloj()) window.location.reload(); };
    document.addEventListener("visibilitychange", reSincronizar);
    window.addEventListener("focus", reSincronizar);
    const t = setInterval(revisarLocal, 60000);
    return () => {
      document.removeEventListener("visibilitychange", reSincronizar);
      window.removeEventListener("focus", reSincronizar);
      clearInterval(t);
    };
  }, []);

  async function guardarAtencion(cita, datos) {
    try {
      const r = await api.atenderCita(cita.id, datos);
      await Promise.all([refrescarCitas(), refrescarPacientes()]);
      setAtender(null);
      if (r?.paquete) {
        showToast(`Atención guardada ✓ · Paquete: ${r.paquete.usadas}/${r.paquete.total} (quedan ${r.paquete.restantes})`);
      } else {
        showToast("Atención guardada en la historia clínica ✓");
      }
    } catch (e) { showToast("Error: " + e.message); }
  }

  async function venderPaquete(data) {
    try {
      await api.crearPaquete(data);
      await refrescarPacientes();
      setVendiendoPaquete(null);
      showToast("Paquete vendido ✓");
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

  async function enviarMensajePaciente(paciente, texto, tipo, plantillaId, citaId) {
    try {
      const r = await api.enviarMensajePaciente(paciente.id, texto, tipo, plantillaId, citaId);
      setWaPaciente(null); setWaCita(null);
      manejarResultadoEnvio(r, "Mensaje enviado por WhatsApp ✓");
      Promise.all([refrescarMensajes(), refrescarCitas()]).catch(() => {});
    } catch (e) { showToast("Error: " + e.message); }
  }

  async function guardarPaciente(data) {
    const payload = {
      nombre: data.nombre,
      fecha_nacimiento: data.fecha_nacimiento || null,
      especialidad: data.especialidad || "",
      sede: data.sede || "",
      profesional: data.profesional ?? null,
      frecuencia: data.frecuencia || "",
      modalidad: data.modalidad || "",
      alergias: data.alergias || "",
      antecedentes: data.antecedentes || "",
      medicacion_habitual: data.medicacion_habitual || "",
      antecedentes_medicos: data.antecedentes_medicos || "",
      antecedentes_familiares: data.antecedentes_familiares || "",
      antecedentes_otros: data.antecedentes_otros || "",
      // Trabajo clínico (lo edita también el psicólogo): antes se perdía al guardar.
      resumen_clinico: data.resumen_clinico || "",
      objetivo_principal: data.objetivo_principal || "",
      riesgo: data.riesgo || "",
      alertas: data.alertas || "",
      notas_internas: data.notas_internas || "",
      ...(data.sesiones_proceso !== undefined ? { sesiones_proceso: data.sesiones_proceso } : {}),
      // Contacto/identidad: solo se envían si el modal los incluyó. El médico NO
      // los ve, así que no los manda y así NO se sobrescriben al editar.
      ...(data.tel !== undefined ? { tel: data.tel } : {}),
      ...(data.email !== undefined ? { email: data.email } : {}),
      ...(data.tipo_documento !== undefined ? { tipo_documento: data.tipo_documento } : {}),
      ...(data.numero_documento !== undefined ? { numero_documento: data.numero_documento } : {}),
      ...(data.direccion !== undefined ? { direccion: data.direccion } : {}),
      ...(data.genero !== undefined ? { genero: data.genero } : {}),
      ...(data.tutor_nombre !== undefined ? { tutor_nombre: data.tutor_nombre } : {}),
      ...(data.tutor_parentesco !== undefined ? { tutor_parentesco: data.tutor_parentesco } : {}),
      ...(data.tutor_telefono !== undefined ? { tutor_telefono: data.tutor_telefono } : {}),
      ...(data.tutor_documento !== undefined ? { tutor_documento: data.tutor_documento } : {}),
      ...(data.n_sesion !== undefined ? { n_sesion: data.n_sesion } : {}),
      ...(data.proceso !== undefined ? { proceso: data.proceso } : {}),
    };
    try {
      if (data.id) {
        await api.actualizarPaciente(data.id, payload);
        setEditingPaciente(null);
        showToast("Datos actualizados ✓");
        refrescarPacientes().catch(() => {});
      } else {
        const nuevo = await api.crearPaciente(payload);
        setEditingPaciente(null);
        showToast("Paciente agregado ✓");
        await refrescarPacientes();
        setSelectedId(nuevo.id);
        cargarDetalle(nuevo.id);
      }
    } catch (e) { showToast("Error: " + e.message); }
  }

  async function agendarCita(data) {
    try {
      let pacienteId = data.pacienteId;
      if (data.nuevoNombre) {
        const nuevo = await api.crearPaciente({ nombre: data.nuevoNombre, especialidad: data.especialidad, sede: data.sede || "", tel: data.nuevoTel || "" });
        pacienteId = nuevo.id;
      }
      const r = await api.agendarCita({
        pacienteId, fecha: data.fecha, hora: data.hora, especialidad: data.especialidad,
        categoria: data.categoria || "", motivo_consulta: data.motivo_consulta || "",
        medicoId: data.medicoId || null, sede: data.sede || "", modalidad: data.modalidad || "presencial",
        enlace: data.enlace || "", notas: data.notas || "", n_sesion: data.n_sesion || null,
      });
      // Feedback inmediato: cerrar modal + toast ya; la recarga va en segundo plano.
      setAdding(false);
      if (data.fecha) setAgendaFecha(data.fecha); // saltar al día de la cita recién creada
      showToast(r?.aviso ? r.aviso : "Sesión agendada ✓");
      Promise.all([refrescarCitas(), refrescarPacientes()]).catch(() => {});
    } catch (e) { showToast("Error: " + e.message); }
  }

  async function moverCita(cita, fecha, hora) {
    try {
      await api.moverCita(cita.id, fecha, hora);
      setReagendar(null);
      setAgendaFecha(fecha);
      showToast("Sesión reagendada ✓");
      refrescarCitas().catch(() => {});
    } catch (e) { showToast("Error: " + e.message); }
  }

  async function cancelarCita(cita) {
    try {
      await api.cancelarCita(cita.id);
      setCancelando(null);
      showToast("Sesión cancelada");
      refrescarCitas().catch(() => {});
    } catch (e) { showToast("Error: " + e.message); }
  }

  async function eliminarCita(cita) {
    if (!window.confirm(`¿ELIMINAR la cita de ${cita.paciente} del ${cita.fecha} ${cita.hora}?\n\nSe borra de forma permanente y queda registrado para gerencia. (Si solo quieres marcarla cancelada, usa el estado "Cancelada".)`)) return;
    try {
      await api.borrarCita(cita.id);
      showToast("Cita eliminada");
      refrescarCitas().catch(() => {});
    } catch (e) { showToast("Error: " + e.message); }
  }

  async function guardarCobro(data) {
    try {
      await api.crearCobro(data);
      setCobrando(null);
      showToast("Cobro registrado ✓");
      Promise.all([refrescarCitas(), refrescarPacientes()]).catch(() => {});
    } catch (e) { showToast("Error: " + e.message); }
  }

  async function confirmarCita(cita) {
    try {
      await api.confirmarCita(cita.id);
      showToast("Sesión confirmada ✓");
      refrescarCitas().catch(() => {});
    } catch (e) { showToast("Error: " + e.message); }
  }

  async function guardarBloqueo(data) {
    try {
      await api.crearBloqueo(data);
      setBloqueando(null);
      showToast("Horario bloqueado ✓");
      refrescarBloqueos().catch(() => {});
    } catch (e) { showToast("Error: " + e.message); }
  }
  async function borrarBloqueo(b) {
    if (!window.confirm("¿Quitar este bloqueo?")) return;
    try { await api.borrarBloqueo(b.id); showToast("Bloqueo quitado"); refrescarBloqueos().catch(() => {}); }
    catch (e) { showToast("Error: " + e.message); }
  }

  async function setEstadoCita(cita, estado) {
    try {
      await api.setEstadoCita(cita.id, estado);
      const lbl = (ESTADOS_CITA.find((e) => e.v === estado) || {}).l || estado;
      showToast(`Estado: ${lbl} ✓`);
      refrescarCitas().catch(() => {});
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
        .ca-ws-img { height:46px; width:auto; max-width:100%; display:block; object-fit:contain; }
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
        .ca-subnav { display:flex; flex-direction:column; gap:1px; margin:1px 0 6px 15px; padding-left:9px; border-left:1px solid var(--line); }
        .ca-subitem { display:flex; align-items:center; gap:8px; padding:5px 8px; border-radius:6px; background:none; border:none; cursor:pointer; text-align:left; font-size:12.8px; color:var(--muted); font-family:inherit; }
        .ca-subitem:hover { background:var(--hover); color:var(--ink); }
        .ca-subitem::before { content:"•"; color:var(--accent); font-size:14px; line-height:1; }
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
        .ca-charts2 { display:grid; grid-template-columns:repeat(auto-fit, minmax(320px, 1fr)); gap:14px; margin-top:14px; }
        .ca-table { width:100%; border-collapse:collapse; font-size:13.5px; }
        .ca-table th { text-align:left; font-weight:600; color:var(--muted); font-size:12px; padding:7px 10px; border-bottom:1px solid var(--line); white-space:nowrap; }
        .ca-table td { padding:8px 10px; border-bottom:1px solid var(--line); }
        .ca-table tr:last-child td { border-bottom:none; }
        .ca-table .num { text-align:right; font-variant-numeric:tabular-nums; }
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
        .ca-mini.danger { color:#B4564E; }
        .ca-mini.danger:hover { background:#FDE9E7; }
        a.ca-mini { text-decoration:none; }
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
        .ca-mes { margin-top:18px; }
        .ca-mes-hd { display:grid; grid-template-columns:repeat(7,minmax(0,1fr)); gap:6px; margin-bottom:6px; }
        .ca-mes-hd > div { text-align:center; font-size:11.5px; font-weight:600; color:var(--muted); text-transform:uppercase; letter-spacing:.03em; }
        .ca-mes-grid { display:grid; grid-template-columns:repeat(7,minmax(0,1fr)); gap:6px; }
        .ca-mes-cel { background:var(--surface); border:1px solid var(--line); border-radius:9px; padding:5px 5px 6px; min-height:92px; cursor:pointer; transition:background .12s; }
        .ca-mes-cel:hover { background:rgba(0,0,0,.02); }
        .ca-mes-cel.off { background:transparent; border-color:transparent; }
        .ca-mes-cel.off .d { color:var(--line); }
        .ca-mes-cel.hoy { border-color:var(--accent); background:var(--accent-soft); }
        .ca-mes-cel .d { font-size:12.5px; font-weight:600; color:var(--ink); margin-bottom:3px; text-align:right; padding-right:2px; }
        .ca-mes-evt { font-size:10.5px; font-weight:600; border-radius:5px; padding:2px 5px; margin-bottom:3px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .ca-mes-mas { font-size:10.5px; color:var(--muted); font-weight:600; padding-left:3px; }
        @media (max-width:820px){ .ca-mes-grid, .ca-mes-hd { gap:3px; } .ca-mes-cel { min-height:64px; } .ca-mes-evt { font-size:9px; } }
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
        /* Hoja editable tipo Excel */
        .ca-hoja-wrap { overflow:auto; max-height:calc(100vh - 230px); border:1px solid var(--line); border-radius:11px; background:var(--surface); }
        .ca-hoja { border-collapse:separate; border-spacing:0; width:max-content; min-width:100%; font-size:13px; }
        .ca-hoja th { position:sticky; top:0; z-index:2; background:#F3F1EC; text-align:left; font-size:11px; font-weight:600;
          color:var(--ink-soft); text-transform:uppercase; letter-spacing:.03em; padding:8px 10px; border-bottom:1px solid var(--line); border-right:1px solid var(--line); white-space:nowrap; }
        .ca-hoja td { padding:0; border-bottom:1px solid var(--line); border-right:1px solid var(--line); }
        .ca-hoja td.ca-ro { padding:6px 10px; color:var(--muted); background:#FBFAF8; white-space:nowrap; }
        .ca-hoja tr:hover td { background:#FAF7F2; }
        .ca-hoja .ca-cell { width:100%; border:0; background:transparent; padding:6px 10px; font:inherit; color:var(--ink); outline:none; min-width:90px; }
        .ca-hoja .ca-cell:focus { background:#E9F1ED; box-shadow:inset 0 0 0 2px var(--accent); border-radius:3px; }
        .ca-hoja select.ca-cell { cursor:pointer; }
        .ca-hoja td.saving { box-shadow:inset 0 0 0 2px #C9923A; }
        .ca-hoja td.saved { box-shadow:inset 0 0 0 2px #4F8A77; }
        .ca-hoja td.err { box-shadow:inset 0 0 0 2px #B4564E; }
        .ca-hoja .rownum { position:sticky; left:0; z-index:1; background:#F3F1EC; color:var(--muted); text-align:right;
          padding:6px 8px; font-size:11px; white-space:nowrap; }
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
        .ca-toast { position:fixed; top:22px; left:50%; transform:translateX(-50%); background:#fff; color:#343434;
          padding:12px 20px 12px 13px; border-radius:14px; font-size:14.5px; font-weight:600; z-index:9999;
          box-shadow:0 14px 40px rgba(40,38,34,.22); display:flex; align-items:center; gap:11px; min-width:210px;
          border:1px solid #DCEBEF; font-family:'Inter',-apple-system,system-ui,sans-serif;
          animation:caUp .2s cubic-bezier(.2,.85,.25,1); }
        .ca-toast .ca-toast-ic { width:28px; height:28px; border-radius:999px; display:flex; align-items:center;
          justify-content:center; flex-shrink:0; color:#fff; }
        .ca-toast.ok { border-color:#BFE6CE; } .ca-toast.ok .ca-toast-ic { background:#2F8F5B; }
        .ca-toast.err { border-color:#F0C4BF; } .ca-toast.err .ca-toast-ic { background:#C9453B; }
        @keyframes caUp { from { opacity:0; transform:translate(-50%,-14px) scale(.96); } to { opacity:1; transform:translate(-50%,0) scale(1); } }
        @media (prefers-reduced-motion: reduce) { .ca-toast { animation:none; } }
        @media (max-width:720px) {
          .clinica-app { flex-direction:column; height:auto; }
          .ca-side { width:100%; flex-direction:row; overflow-x:auto; border-right:none;
            border-bottom:1px solid var(--line); padding:10px; align-items:center; }
          .ca-ws { padding:4px 8px 4px 4px; }
          .ca-ws-img { height:32px; }
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
          <img src={`${import.meta.env.BASE_URL}itaca-logo-h.png`} alt="Itaca Conversemos" className="ca-ws-img"
            onError={(e) => { e.currentTarget.style.display = "none"; e.currentTarget.nextElementSibling.style.display = "flex"; }} />
          <div className="ca-ws-fallback" style={{ display: "none", alignItems: "center", gap: 9 }}>
            <div className="ca-ws-logo">🩺</div>
            <div>
              <div className="ca-ws-name">{nombreClinica}</div>
              <div className="ca-ws-sub">{ciudadClinica}</div>
            </div>
          </div>
        </div>
        {nav.map((n) => {
          const Icon = n.icon;
          return (
            <React.Fragment key={n.id}>
              <button className={`ca-navitem ${view === n.id ? "active" : ""}`} onClick={() => go(n.id)}>
                <Icon size={17} strokeWidth={1.9} />{n.label}
              </button>
              {n.id === "mentalidad" && view === "mentalidad" && (
                <div className="ca-subnav">
                  {MENT_SUBS.map((s) => (
                    <button key={s.id} className="ca-subitem" onClick={() => {
                      const el = document.getElementById("ment-" + s.id);
                      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
                    }}>{s.label}</button>
                  ))}
                </div>
              )}
            </React.Fragment>
          );
        })}
        {usuario?.rol !== "medico" && <>
          <div className="ca-sectlabel">Pronto</div>
          <div className="ca-navitem soft">
            <Receipt size={17} strokeWidth={1.9} />Facturación<span className="ca-soonbadge">SUNAT</span>
          </div>
        </>}
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
            onRetencion={() => { setSoloSinProxima(true); go("pacientes"); }} cumple={cumpleHoy} esAdmin={usuario?.rol === "admin"} esMedico={usuario?.rol === "medico"} showToast={showToast} />
        )}

        {view === "agenda" && (
          <Agenda
            citas={citas} bloqueos={bloqueos} fecha={agendaFecha} setFecha={setAgendaFecha}
            vista={agendaVista} setVista={setAgendaVista} esAsistente={esAsistente} esMedico={usuario?.rol === "medico"}
            onBloquear={() => setBloqueando({})} onBorrarBloqueo={borrarBloqueo} onVenta={() => setCobrando({})}
            onAgendar={() => setAdding(true)} onAtender={setAtender} onRecordar={setRecordar}
            onReagendar={setReagendar} onCancelar={setCancelando} openFicha={openFicha}
            onConfirmar={confirmarCita} onSetEstado={setEstadoCita} onAbrirCita={setCitaDetalle}
            onMensaje={(c) => { const p = pacientes.find((x) => x.id === c.pacienteId); if (p) { setWaPaciente(p); setWaCita(c); } else showToast("No se encontró el paciente"); }}
            onCobrar={(c) => setCobrando({ pacienteId: c.pacienteId, paciente: c.paciente, citaId: c.id, especialidad: c.especialidad })}
            onEditarNota={setNotaCita}
            onEliminarCita={(usuario?.rol === "asistente" || usuario?.rol === "admin") ? eliminarCita : undefined}
          />
        )}

        {view === "pacientes" && !selected && (
          <>
            <div className="ca-tophead">
              <div>
                <h1 className="ca-h1">Pacientes</h1>
                <div className="ca-sub">{filtered.length === pacientes.length ? `${pacientes.length} en total` : `${filtered.length} de ${pacientes.length}`}</div>
              </div>
              <div style={{ display: "flex", gap: 9, alignItems: "center" }}>
                {usuario?.rol !== "medico" && <ExportBtns nombre="pacientes" titulo="Pacientes" disabled={filtered.length === 0}
                  headers={["Nombre", "Documento", "Numero", "Edad", "Genero", "Telefono", "Direccion", "Especialidad", "Ultima visita", "Proxima sesion", "Pendiente S/"]}
                  filas={filtered.map((p) => [p.nombre, p.tipo_documento_label || "", p.numero_documento || "", p.edad ?? "", p.genero_label || "", p.tel, p.direccion || "", p.especialidad, p.ultima, p.proxima ? `${p.proxima.fecha} ${p.proxima.hora}` : "", p.cuenta?.pendiente || 0])} />}
                {usuario?.rol !== "medico" && (
                  <button className="ca-btn" onClick={() => setEditingPaciente({ new: true })}>
                    <UserPlus size={16} strokeWidth={2.1} /> Nuevo paciente
                  </button>
                )}
              </div>
            </div>
            <div className="ca-search" style={{ marginTop: 22 }}>
              <Search size={16} strokeWidth={2} style={{ color: "var(--muted)" }} />
              <input placeholder="Buscar por nombre o teléfono…" value={query} onChange={(e) => setQuery(e.target.value)} />
            </div>
            <div className="ca-fchips">
              <button className={`ca-fchip ${!filterSede ? "on" : ""}`} onClick={() => { setFilterSede(null); setFilterProf(""); }}>Todas las sedes</button>
              <button className={`ca-fchip ${filterSede === "piura" ? "on" : ""}`} onClick={() => { setFilterSede("piura"); setFilterProf(""); }}>Piura</button>
              <button className={`ca-fchip ${filterSede === "lima" ? "on" : ""}`} onClick={() => { setFilterSede("lima"); setFilterProf(""); }}>Lima</button>
              {profsEnPacientes.length > 0 && (
                <select className="ca-input" style={{ width: "auto", padding: "6px 10px", marginLeft: 6 }} value={filterProf} onChange={(e) => setFilterProf(e.target.value)}>
                  <option value="">Todos los psicólogos</option>
                  {profsEnPacientes.map((n) => <option key={n} value={n}>{n}</option>)}
                </select>
              )}
              <select className="ca-input" style={{ width: "auto", padding: "6px 10px", marginLeft: 6 }} value={filterFrec} onChange={(e) => setFilterFrec(e.target.value)}>
                <option value="">Todos los estados</option>
                <option value="semanal">Semanal</option>
                <option value="quincenal">Quincenal</option>
                <option value="esporadico">Esporádico</option>
                <option value="en_pausa">En pausa</option>
                <option value="alta">Alta</option>
              </select>
              <button className={`ca-fchip ${soloSinProxima ? "on" : ""}`} onClick={() => setSoloSinProxima((v) => !v)}
                style={{ marginLeft: 6, color: soloSinProxima ? undefined : "#B0822F" }}>⏰ Sin próxima sesión</button>
            </div>
            {filtered.length === 0 ? (
              <div className="ca-empty">No encontramos a nadie con ese filtro. Prueba con otro o agrégalo arriba.</div>
            ) : (
              filtered.map((p) => {
                const meta = p.proceso === "consulta"
                  ? "Consulta inicial"
                  : `${p.n_sesion ? `Sesión ${p.n_sesion}` : ""}${p.n_sesion && p.proceso_label ? " · " : ""}${p.proceso_label || ""}`;
                return (
                  <div key={p.id} className="ca-row click" onClick={() => openFicha(p.id)}>
                    <div className="ca-avatar">{iniciales(p.nombre)}</div>
                    <div style={{ flex: 1 }}>
                      <div className="ca-pname">{p.nombre}</div>
                      <div className="ca-pmeta">{p.profesional_nombre ? `${p.profesional_nombre} · ` : ""}{meta || `última visita ${p.ultima}`}</div>
                    </div>
                    {p.cuenta?.pendiente > 0 && <Tag colors={ESTADO_COBRO_COLOR.pendiente}>Debe {money(p.cuenta.pendiente)}</Tag>}
                    {p.frecuencia_label && <Tag colors={p.frecuencia === "alta" ? { bg: "#E7EEF6", fg: "#3D5C82" } : p.frecuencia === "en_pausa" ? { bg: "#FCF3D4", fg: "#8A6D14" } : { bg: "#E4F3E8", fg: "#1E7D45" }}>{p.frecuencia_label}</Tag>}
                    {p.modalidad_label && <Tag colors={{ bg: "#EFEDE8", fg: "#7C7870" }}>{p.modalidad_label}</Tag>}
                    {p.sede_label && <Tag colors={p.sede === "piura" ? { bg: "#D7F4FA", fg: "#0A7D92" } : { bg: "#FBE9D6", fg: "#B5701F" }}>{p.sede_label}</Tag>}
                  </div>
                );
              })
            )}
          </>
        )}

        {view === "pacientes" && selected && (
          <Ficha p={selected} esMedico={usuario?.rol === "medico"} onBack={() => setSelectedId(null)} onEdit={() => setEditingPaciente(selected)}
            onWhatsApp={() => { setWaPaciente(selected); setWaCita(null); }} clinica={nombreClinica} onAgendar={() => setAgendarPara(selected)}
            onRegistrarSesion={() => setRegistrandoSesion(selected)} puedeRegistrar={usuario?.rol === "medico" || usuario?.rol === "admin"}
            onVenderPaquete={() => setVendiendoPaquete(selected)} puedeVenderPaquete={usuario?.rol === "asistente" || usuario?.rol === "admin"}
            onRegistrarPago={() => setCobrando({ pacienteId: selected.id, paciente: selected.nombre, especialidad: selected.especialidad })}
            puedeCobrar={usuario?.rol === "asistente" || usuario?.rol === "admin"}
            onSubirAdjunto={(file) => subirAdjunto(selected, file)}
            onEliminarAdjunto={eliminarAdjunto} puedeEliminar={usuario?.rol === "medico" || usuario?.rol === "admin"} showToast={showToast} onRefrescar={refrescarPacientes} />
        )}

        {view === "gerencia" && <Gerencia showToast={showToast} />}

        {view === "historico" && <Historico showToast={showToast} esAdmin={usuario?.rol === "admin"} />}

        {view === "reporte" && <ReporteSemanal showToast={showToast} esAdmin={usuario?.rol === "admin"} />}

        {view === "ocupacion" && <Ocupacion showToast={showToast} />}

        {view === "equipo" && <Equipo showToast={showToast} miId={usuario?.id} />}

        {view === "legal" && <Legal showToast={showToast} />}

        {view === "buzon" && <Buzon showToast={showToast} esAdmin={usuario?.rol === "admin"} />}

        {view === "whatsapp" && <ConexionWhatsapp showToast={showToast} />}

        {view === "hojas" && <HojasExcel showToast={showToast} onCambio={cargarDatos} />}

        {view === "profesionales" && <Profesionales showToast={showToast} esAdmin={usuario?.rol === "admin"} />}

        {view === "herramientas" && <Recursos showToast={showToast} esAdmin={usuario?.rol === "admin"} esMedico={usuario?.rol === "medico"} />}
        {view === "mentalidad" && <MentalidadItaca rol={usuario?.rol} esAdmin={usuario?.rol === "admin"} showToast={showToast} />}

        {view === "mensajes" && <Mensajes mensajes={mensajes} puedeEditar={usuario?.rol === "admin" || usuario?.rol === "asistente"} showToast={showToast} />}

        {view === "marketing" && <Marketing showToast={showToast} onConvertir={refrescarPacientes} esAdmin={usuario?.rol === "admin"} />}

        {view === "finanzas" && <Finanzas showToast={showToast} esAdmin={usuario?.rol === "admin"} />}

        {view === "liquidacion" && <Liquidacion showToast={showToast} />}

        {view === "espacios" && <EspaciosProfesionales showToast={showToast} />}

        {adding && <AgendarModal pacientes={pacientes} fechaInicial={agendaFecha} onClose={() => setAdding(false)} onSave={agendarCita} />}
        {agendarPara && (
          <AgendarModal pacientes={pacientes} fechaInicial={agendaFecha}
            pacienteFijo={{ id: agendarPara.id, nombre: agendarPara.nombre, especialidad: agendarPara.especialidad, sede: agendarPara.sede, n_sesion: agendarPara.n_sesion }}
            onClose={() => setAgendarPara(null)} onSave={async (d) => { await agendarCita(d); setAgendarPara(null); }} />
        )}
        {vendiendoPaquete && (
          <VenderPaqueteModal paciente={vendiendoPaquete} servicios={servicios}
            onClose={() => setVendiendoPaquete(null)} onSave={venderPaquete} />
        )}
        {atender && <AtenderModal cita={atender} servicios={servicios} esMedico={usuario?.rol === "medico"} onClose={() => setAtender(null)} onSave={(datos) => guardarAtencion(atender, datos)} />}
        {recordar && <RecordarModal cita={recordar} clinica={nombreClinica} onClose={() => setRecordar(null)} onSend={(texto) => enviarRecordatorio(recordar, texto)} />}
        {reagendar && <ReagendarModal cita={reagendar} onClose={() => setReagendar(null)} onSave={moverCita} />}
        {notaCita && (
          <NotaCitaModal cita={notaCita} showToast={showToast} onClose={() => setNotaCita(null)}
            onSaved={() => { setNotaCita(null); refrescarCitas(); }} />
        )}
        {cobrando && <CobroModal prefill={cobrando} pacientes={pacientes} servicios={servicios} onClose={() => setCobrando(null)} onSave={guardarCobro} />}
        {citaDetalle && (
          <CitaDetalleModal cita={citaDetalle} esMedico={usuario?.rol === "medico"} esAsistente={esAsistente}
            onClose={() => setCitaDetalle(null)} onSetEstado={setEstadoCita} openFicha={openFicha}
            onAtender={setAtender} onReagendar={setReagendar} onCancelar={setCancelando}
            onMensaje={(c) => { const p = pacientes.find((x) => x.id === c.pacienteId); if (p) { setWaPaciente(p); setWaCita(c); } else showToast("No se encontró el paciente"); }}
            onCobrar={(c) => setCobrando({ pacienteId: c.pacienteId, paciente: c.paciente, citaId: c.id, especialidad: c.especialidad })} />
        )}
        {bloqueando && <BloqueoModal fechaInicial={agendaFecha} onClose={() => setBloqueando(null)} onSave={guardarBloqueo} />}
        {cancelando && (
          <ConfirmModal
            titulo="Cancelar sesión"
            mensaje={`¿Cancelar la sesión de ${cancelando.paciente} del ${labelLargo(cancelando.fecha)} a las ${cancelando.hora}? Quedará registrada como cancelada.`}
            confirmLabel="Sí, cancelar" peligro
            onConfirm={() => cancelarCita(cancelando)} onClose={() => setCancelando(null)}
          />
        )}
        {waPaciente && <MensajePacienteModal paciente={waPaciente} cita={waCita} onClose={() => { setWaPaciente(null); setWaCita(null); }} onSend={(texto, tipo, plantillaId) => enviarMensajePaciente(waPaciente, texto, tipo, plantillaId, waCita?.id)} />}
        {editingPaciente && (
          <PacienteModal paciente={editingPaciente.new ? null : editingPaciente} esMedico={usuario?.rol === "medico"}
            onClose={() => setEditingPaciente(null)} onSave={guardarPaciente} />
        )}
        {registrandoSesion && (
          <RegistrarSesionModal paciente={registrandoSesion}
            onClose={() => setRegistrandoSesion(null)} onSave={(d) => guardarRegistroSesion(registrandoSesion, d)} />
        )}
      </main>

      {cambiarPass && <CambiarPasswordModal onClose={() => setCambiarPass(false)} onSave={cambiarMiPassword} />}
      {toast && createPortal(
        (() => {
          const esError = /^error\b/i.test(toast);
          return (
            <div className={`ca-toast ${esError ? "err" : "ok"}`}>
              <span className="ca-toast-ic">{esError ? <X size={16} strokeWidth={3} /> : <Check size={16} strokeWidth={3.2} />}</span>
              <span>{toast.replace(/^Error:\s*/i, "").replace(/\s*✓\s*$/, "")}</span>
            </div>
          );
        })(),
        document.body
      )}
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
  const [tCons, setTCons] = useState("");
  const [tPol, setTPol] = useState("");
  const [tMof, setTMof] = useState("");
  const [tPil, setTPil] = useState("");
  const [metaMin, setMetaMin] = useState("");
  const [metaIdeal, setMetaIdeal] = useState("");
  const [metasSede, setMetasSede] = useState({ lima: { min: "", ideal: "" }, piura: { min: "", ideal: "" } });
  const [guardandoTxt, setGuardandoTxt] = useState(false);
  const [editandoGame, setEditandoGame] = useState(false);
  function cargar(c) {
    setCfg(c); setNombre(c.nombre); setCiudad(c.ciudad || "");
    setTCons(c.texto_consentimiento || ""); setTPol(c.texto_politicas || "");
    setTMof(c.mof || ""); setTPil(c.pilares || "");
    setMetaMin(String(c.meta_min_mes ?? "")); setMetaIdeal(String(c.meta_ideal_mes ?? ""));
    const ms = c.metas_sede || {};
    setMetasSede({
      lima: { min: String(ms.lima?.min ?? ""), ideal: String(ms.lima?.ideal ?? "") },
      piura: { min: String(ms.piura?.min ?? ""), ideal: String(ms.piura?.ideal ?? "") },
    });
  }
  useEffect(() => { api.clinicaConfig().then(cargar).catch(() => {}); }, []);
  function metasSedePayload() {
    const out = {};
    for (const s of ["lima", "piura"]) {
      const min = Number(metasSede[s].min) || 0, ideal = Number(metasSede[s].ideal) || 0;
      if (min || ideal) out[s] = { min, ideal };
    }
    return out;
  }
  async function guardar() {
    try {
      const c = await api.actualizarClinica({
        nombre, ciudad,
        meta_min_mes: Number(metaMin) || 0, meta_ideal_mes: Number(metaIdeal) || 0,
        metas_sede: metasSedePayload(),
      });
      cargar(c); showToast("Datos de la clínica actualizados ✓");
    } catch (e) { showToast("Error: " + e.message); }
  }
  const setMS = (sede, k) => (e) => setMetasSede((p) => ({ ...p, [sede]: { ...p[sede], [k]: e.target.value } }));
  async function guardarTextos() {
    setGuardandoTxt(true);
    try {
      const c = await api.actualizarClinica({ texto_consentimiento: tCons, texto_politicas: tPol });
      cargar(c); showToast("Textos legales guardados ✓");
    } catch (e) { showToast("Error: " + e.message); }
    finally { setGuardandoTxt(false); }
  }
  async function guardarInstitucional() {
    try {
      const c = await api.actualizarClinica({ mof: tMof, pilares: tPil });
      cargar(c); showToast("MOF y pilares guardados ✓");
    } catch (e) { showToast("Error: " + e.message); }
  }
  const instCambiado = tMof !== (cfg?.mof || "") || tPil !== (cfg?.pilares || "");
  if (!cfg) return null;
  const cambiado = nombre.trim() && (
    nombre !== cfg.nombre || ciudad !== (cfg.ciudad || "") ||
    Number(metaMin) !== Number(cfg.meta_min_mes ?? 0) ||
    Number(metaIdeal) !== Number(cfg.meta_ideal_mes ?? 0) ||
    JSON.stringify(metasSedePayload()) !== JSON.stringify(cfg.metas_sede || {})
  );
  const txtCambiado = tCons !== (cfg.texto_consentimiento || "") || tPol !== (cfg.texto_politicas || "");
  const areaTxt = { minHeight: 200, resize: "vertical", lineHeight: 1.55, fontSize: 13, fontFamily: "inherit" };
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
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end", marginTop: 14, paddingTop: 14, borderTop: "1px solid var(--line)" }}>
          <div style={{ flex: 1, minWidth: 150 }}>
            <div className="ca-label">Meta mínima del mes (S/)</div>
            <input className="ca-input" type="number" min="0" value={metaMin} onChange={(e) => setMetaMin(e.target.value)} />
          </div>
          <div style={{ flex: 1, minWidth: 150 }}>
            <div className="ca-label">Meta ideal del mes (S/)</div>
            <input className="ca-input" type="number" min="0" value={metaIdeal} onChange={(e) => setMetaIdeal(e.target.value)} />
          </div>
          <div className="ca-pmeta" style={{ flex: 2, minWidth: 220, paddingBottom: 10 }}>
            La gerencia ve el total de la clínica. Cada coordinadora ve la meta de SU sede (abajo); si una sede no tiene meta, usa la general.
          </div>
        </div>
        <div style={{ marginTop: 14, paddingTop: 14, borderTop: "1px solid var(--line)" }}>
          <div className="ca-label" style={{ marginBottom: 8 }}>Metas por sede (opcional)</div>
          {["lima", "piura"].map((s) => (
            <div key={s} style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end", marginBottom: 10 }}>
              <div style={{ width: 70, fontWeight: 600, fontSize: 13.5, paddingBottom: 10, textTransform: "capitalize" }}>{s}</div>
              <div style={{ flex: 1, minWidth: 130 }}>
                <div className="ca-label">Mínima (S/)</div>
                <input className="ca-input" type="number" min="0" value={metasSede[s].min} onChange={setMS(s, "min")} placeholder="usa la general" />
              </div>
              <div style={{ flex: 1, minWidth: 130 }}>
                <div className="ca-label">Ideal (S/)</div>
                <input className="ca-input" type="number" min="0" value={metasSede[s].ideal} onChange={setMS(s, "ideal")} placeholder="usa la general" />
              </div>
            </div>
          ))}
        </div>
      </div>

      <h2 className="ca-secth">Documentos que firma el paciente</h2>
      <div className="ca-card" style={{ marginBottom: 26 }}>
        <div style={{ fontSize: 12.5, color: "var(--muted)", marginBottom: 14, display: "flex", gap: 7, alignItems: "flex-start", lineHeight: 1.5 }}>
          <AlertTriangle size={14} strokeWidth={2} style={{ color: "#B0822F", flexShrink: 0, marginTop: 1 }} />
          <span>Este es el texto EXACTO que el paciente lee y acepta por el enlace. Si lo dejas vacío se usa el
            borrador por defecto del sistema. <strong>Revísalo y adáptalo a las condiciones reales de la clínica</strong> (cargos
            por cancelación, grabaciones, contacto de emergencia) antes de enviarlo a un paciente.</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 16 }}>
          <div>
            <div className="ca-label">Consentimiento informado {!cfg.personalizado_consentimiento && <span style={{ color: "var(--muted)", fontWeight: 400 }}>(borrador del sistema)</span>}</div>
            <textarea className="ca-input" style={areaTxt} value={tCons} onChange={(e) => setTCons(e.target.value)} />
          </div>
          <div>
            <div className="ca-label">Políticas de atención {!cfg.personalizado_politicas && <span style={{ color: "var(--muted)", fontWeight: 400 }}>(borrador del sistema)</span>}</div>
            <textarea className="ca-input" style={areaTxt} value={tPol} onChange={(e) => setTPol(e.target.value)} />
          </div>
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 12 }}>
          <button className="ca-btn" style={{ opacity: txtCambiado ? 1 : 0.5, pointerEvents: txtCambiado ? "auto" : "none" }}
            onClick={guardarTextos} disabled={guardandoTxt}>{guardandoTxt ? "Guardando…" : "Guardar textos"}</button>
        </div>
      </div>

      <h2 className="ca-secth">Funciones del psicólogo (MOF y pilares Itaca)</h2>
      <div className="ca-card" style={{ marginBottom: 26 }}>
        <div style={{ fontSize: 12.5, color: "var(--muted)", marginBottom: 14, lineHeight: 1.5 }}>
          Esto lo ve el psicólogo SIEMPRE en su inicio. Escribe aquí su MOF (funciones) y la mentalidad/pilares de Itaca.
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 16 }}>
          <div>
            <div className="ca-label">Pilares / Mentalidad Itaca</div>
            <textarea className="ca-input" style={areaTxt} value={tPil} onChange={(e) => setTPil(e.target.value)}
              placeholder="Ej: No solo trabajamos con pacientes. Cambiamos vidas…" />
          </div>
          <div>
            <div className="ca-label">MOF · Funciones del psicólogo</div>
            <textarea className="ca-input" style={areaTxt} value={tMof} onChange={(e) => setTMof(e.target.value)}
              placeholder="Funciones y responsabilidades del psicólogo…" />
          </div>
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 12 }}>
          <button className="ca-btn" style={{ opacity: instCambiado ? 1 : 0.5, pointerEvents: instCambiado ? "auto" : "none" }}
            onClick={guardarInstitucional}>Guardar</button>
        </div>
      </div>

      <h2 className="ca-secth">Progreso y medallas del psicólogo 🏅</h2>
      <div className="ca-card" style={{ marginBottom: 26 }}>
        <div className="ca-pmeta" style={{ marginBottom: 12 }}>
          El sistema de niveles y medallas que ven los psicólogos en su inicio. Configura los nombres, íconos, cuántos puntos vale cada logro y los umbrales de cada grado.
        </div>
        <button className="ca-btn ghost" onClick={() => setEditandoGame(true)}><Trophy size={15} strokeWidth={2} /> Editar medallas y niveles</button>
      </div>
      {editandoGame && <GamificacionEditor inicial={cfg.gamificacion} showToast={showToast}
        onClose={() => setEditandoGame(false)} onSaved={(g) => { setCfg((p) => ({ ...p, gamificacion: g })); setEditandoGame(false); }} />}
    </>
  );
}

// Editor del sistema de progreso/medallas (solo gerencia). La métrica de cada
// medalla es fija (calculada por el sistema); se editan nombre, ícono, umbrales y puntos.
const GAME_METRICAS = {
  historias: "Historias clínicas registradas", satisfaccion: "Satisfacción NPS (%)",
  continuidad: "Pacientes que continúan", cierre: "Cierre de consulta (%)", sesiones: "Sesiones atendidas",
};
function GamificacionEditor({ inicial, showToast, onClose, onSaved }) {
  const [f, setF] = useState(JSON.parse(JSON.stringify(inicial || {})));
  const [guardando, setGuardando] = useState(false);
  const meds = f.medallas || [];
  const setMed = (i, k, v) => setF((p) => ({ ...p, medallas: p.medallas.map((m, j) => (j === i ? { ...m, [k]: v } : m)) }));
  async function guardar() {
    setGuardando(true);
    try {
      // Convertir "niveles" (texto "10, 25, 50") a números.
      const g = {
        puntos_por_nivel: Number(f.puntos_por_nivel) || 100,
        rangos: (typeof f.rangos === "string" ? f.rangos.split("\n") : f.rangos || []).map((s) => s.trim()).filter(Boolean),
        medallas: meds.map((m) => ({
          ...m,
          niveles: (typeof m.niveles === "string" ? m.niveles.split(",") : m.niveles || [])
            .map((x) => Number(String(x).trim())).filter((n) => !isNaN(n) && n > 0),
          puntos: Number(m.puntos) || 0,
        })),
      };
      await api.actualizarClinica({ gamificacion: g });
      showToast && showToast("Medallas guardadas ✓");
      onSaved(g);
    } catch (e) { showToast && showToast("Error: " + e.message); }
    finally { setGuardando(false); }
  }
  const L = ({ children }) => <div className="ca-label" style={{ marginTop: 8 }}>{children}</div>;
  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 620, maxHeight: "88vh", overflowY: "auto" }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
          <strong style={{ fontSize: 16 }}>Medallas y niveles del psicólogo</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>
        <div className="ca-pmeta" style={{ marginBottom: 6 }}>Los umbrales son los puntos de cada grado (bronce, plata, oro…), separados por coma. "Puntos" = cuánto XP da cada grado alcanzado.</div>

        <div style={{ display: "flex", gap: 11, marginTop: 8 }}>
          <div style={{ flex: 1 }}><L>Puntos por nivel</L>
            <input className="ca-input" type="number" min="10" value={f.puntos_por_nivel || 100} onChange={(e) => setF((p) => ({ ...p, puntos_por_nivel: e.target.value }))} /></div>
          <div style={{ flex: 2 }}><L>Rangos (uno por línea)</L>
            <textarea className="ca-input" style={{ minHeight: 74, resize: "vertical", fontSize: 12.5, fontFamily: "inherit" }}
              value={Array.isArray(f.rangos) ? f.rangos.join("\n") : (f.rangos || "")}
              onChange={(e) => setF((p) => ({ ...p, rangos: e.target.value }))} /></div>
        </div>

        <div className="ca-secth" style={{ marginTop: 16 }}>Medallas</div>
        {meds.map((m, i) => (
          <div key={m.clave || i} className="ca-card" style={{ marginBottom: 10, background: "var(--bg-soft,#F6F5F2)" }}>
            <div style={{ fontSize: 11.5, color: "var(--muted)", marginBottom: 6 }}>Mide: <strong>{GAME_METRICAS[m.metrica] || m.metrica}</strong></div>
            <div style={{ display: "flex", gap: 9, flexWrap: "wrap" }}>
              <div style={{ width: 54 }}><L>Ícono</L><input className="ca-input" style={{ textAlign: "center" }} value={m.emoji || ""} onChange={(e) => setMed(i, "emoji", e.target.value)} /></div>
              <div style={{ flex: 2, minWidth: 140 }}><L>Nombre</L><input className="ca-input" value={m.label || ""} onChange={(e) => setMed(i, "label", e.target.value)} /></div>
              <div style={{ width: 80 }}><L>Puntos</L><input className="ca-input" type="number" min="0" value={m.puntos ?? 0} onChange={(e) => setMed(i, "puntos", e.target.value)} /></div>
            </div>
            <L>Umbrales de cada grado {m.sufijo === "%" ? "(en %)" : ""}</L>
            <input className="ca-input" value={Array.isArray(m.niveles) ? m.niveles.join(", ") : (m.niveles || "")} onChange={(e) => setMed(i, "niveles", e.target.value)} placeholder="10, 25, 50, 100" />
            <L>Descripción</L>
            <input className="ca-input" value={m.desc || ""} onChange={(e) => setMed(i, "desc", e.target.value)} />
          </div>
        ))}

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 12 }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" onClick={guardar} disabled={guardando}>{guardando ? "Guardando…" : "Guardar"}</button>
        </div>
      </div>
    </div>
  );
}

function Gerencia({ showToast }) {
  const [periodo, setPeriodo] = useState("mes");
  const [sede, setSede] = useState("");
  const [data, setData] = useState(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    let vivo = true;
    setCargando(true);
    api.gerenciaResumen(periodo, sede)
      .then((d) => { if (vivo) setData(d); })
      .catch((e) => showToast("Error: " + e.message))
      .finally(() => { if (vivo) setCargando(false); });
    return () => { vivo = false; };
  }, [periodo, sede]);

  const op = data?.operacion, cap = data?.captacion, pac = data?.pacientes;

  // Indicadores del tablero como pares Indicador/Valor para exportar.
  const indicadores = data ? [
    ["Período", data.periodo.label],
    ["Sede", data.sede ? (data.sede === "lima" ? "Lima" : "Piura") : "Total"],
    ["Sesiones en el período", op.citas],
    ["Atendidas", op.atendidas],
    ["% Asistencia", `${op.asistencia_pct}%`],
    ["% Cancelación", `${op.cancelacion_pct}%`],
    ["Recordatorios enviados", op.recordatorios],
    ["Leads recibidos", cap.recibidos],
    ["% de pauta", `${cap.pauta_pct}%`],
    ["Cierres (iniciaron)", cap.cierres],
    ["Tasa de cierre", `${cap.tasa_cierre}%`],
    ["Mejor fuente", cap.top_fuente],
    ["Mejor campaña", cap.top_campania],
    ["Pacientes totales", pac.total],
    ["Nuevos en el período", pac.nuevos],
    ["Sin próxima sesión", pac.sin_proxima],
    ...(data.retencion && data.retencion.con_sesiones > 0 ? [
      ["Retención · en ritmo (<8d)", data.retencion.verde],
      ["Retención · alerta (8–15d)", data.retencion.amarillo],
      ["Retención · abandono (>15d)", data.retencion.rojo],
      ["Retención · % abandono", `${data.retencion.rojo_pct}%`],
    ] : []),
    ["Ingresos (cobrado)", data.finanzas?.cobrado || 0],
    ...(data.finanzas?.egresos != null ? [["Egresos (gastos)", data.finanzas.egresos]] : []),
    ...(data.finanzas?.utilidad != null ? [["Utilidad (neto)", data.finanzas.utilidad]] : []),
    ["Pendiente por cobrar", data.finanzas?.pendiente || 0],
  ] : [];
  const tituloGer = `Gerencia${data ? " · " + data.periodo.label : ""}${sede ? " · " + (sede === "lima" ? "Lima" : "Piura") : ""}`;

  return (
    <div>
      <div className="ca-tophead">
        <div>
          <h1 className="ca-h1">Gerencia</h1>
          <div className="ca-sub">
            {data ? `${data.periodo.label} · ${labelNumMes(data.periodo.desde)} – ${labelNumMes(data.periodo.hasta)}` : "Cargando…"}
          </div>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <ExportBtns nombre={`gerencia_${periodo}${sede ? "_" + sede : ""}`} titulo={tituloGer}
            headers={["Indicador", "Valor"]} filas={indicadores} disabled={!data} />
          <div className="ca-seg">
            {[["", "Total"], ["lima", "Lima"], ["piura", "Piura"]].map(([v, l]) => (
              <button key={v || "total"} className={sede === v ? "on" : ""} onClick={() => setSede(v)}>{l}</button>
            ))}
          </div>
          <div className="ca-seg">
            {[["hoy", "Hoy"], ["semana", "Semana"], ["mes", "Mes"]].map(([v, l]) => (
              <button key={v} className={periodo === v ? "on" : ""} onClick={() => setPeriodo(v)}>{l}</button>
            ))}
          </div>
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

          {data.retencion && data.retencion.con_sesiones > 0 && (
            <>
              <h2 className="ca-secth" style={{ marginTop: 28 }}>Retención (días desde la última sesión)</h2>
              <div className="ca-stats">
                <StatCard label="En ritmo (<8 días)" valor={data.retencion.verde} color="#4F8A77" />
                <StatCard label="Alerta (8–15 días)" valor={data.retencion.amarillo} color="#C9923A" />
                <StatCard label="Abandono (>15 días)" valor={data.retencion.rojo} sub="para llamar / reactivar" color="#B4564E" />
                <StatCard label="% en abandono" valor={`${data.retencion.rojo_pct}%`} color={data.retencion.rojo_pct >= 50 ? "#B4564E" : "#C9923A"} />
              </div>
              <div style={{ fontSize: 12.5, color: "var(--muted)", marginTop: 6 }}>
                Sobre {data.retencion.con_sesiones} pacientes con al menos una sesión registrada. Regla de la clínica: verde &lt;8 días · amarillo 8–15 · rojo &gt;15.
              </div>
            </>
          )}

          <h2 className="ca-secth" style={{ marginTop: 28 }}>Dinero{data.sede ? ` · ${data.sede === "lima" ? "Lima" : "Piura"}` : ""}</h2>
          <div className="ca-stats">
            <StatCard label="Ingresos (cobrado)" valor={money(data.finanzas?.cobrado || 0)} color="#4F8A77"
              sub={data.anterior ? deltaTxt(data.finanzas?.cobrado || 0, data.anterior.cobrado) : undefined} />
            {data.finanzas?.egresos != null && (
              <StatCard label="Egresos (gastos)" valor={money(data.finanzas.egresos)} color="#B4564E" />
            )}
            {data.finanzas?.utilidad != null && (
              <StatCard label="Utilidad (neto)" valor={money(data.finanzas.utilidad)}
                color={data.finanzas.utilidad >= 0 ? "#3E7A65" : "#B4564E"} />
            )}
            <StatCard label="Pendiente por cobrar" valor={money(data.finanzas?.pendiente || 0)} color={(data.finanzas?.pendiente || 0) > 0 ? "#C9923A" : "#7C7870"} />
          </div>
          {data.sede && (
            <div style={{ fontSize: 12.5, color: "var(--muted)", marginTop: 6 }}>
              Egresos y utilidad solo en la vista <strong>Total</strong> (no se registran por sede).
            </div>
          )}

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 28, gap: 10, flexWrap: "wrap" }}>
            <h2 className="ca-secth" style={{ margin: 0 }}>Productividad por psicólogo</h2>
            <ExportBtns nombre={`productividad_${periodo}${sede ? "_" + sede : ""}`} titulo={`Productividad por psicólogo${data ? " · " + data.periodo.label : ""}`}
              headers={["Psicologo", "Sesiones", "Atenciones", "Leads", "Cierres"]}
              filas={data.productividad.map((m) => [m.medico, m.citas, m.atenciones, m.leads, m.cierres])}
              disabled={data.productividad.length === 0} />
          </div>
          <table className="ca-tbl">
            <thead>
              <tr>
                <th>Psicólogo</th>
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

// --- Editor tipo Excel: grillas editables de los "formatos" del sistema --------
const OPC_SEDE = [{ v: "lima", l: "Lima" }, { v: "piura", l: "Piura" }];
const OPC_DOC = [{ v: "dni", l: "DNI" }, { v: "ce", l: "C. Extranjería" }, { v: "pasaporte", l: "Pasaporte" }, { v: "ruc", l: "RUC" }];
const OPC_GENERO = [{ v: "", l: "—" }, { v: "femenino", l: "Femenino" }, { v: "masculino", l: "Masculino" }, { v: "otro", l: "Otro" }];
const _op = (pares) => pares.map(([v, l]) => ({ v, l }));
const OPC_FUENTE = _op([["instagram", "Instagram"], ["facebook", "Facebook"], ["tiktok", "TikTok"], ["referido", "Referido"], ["whatsapp", "WhatsApp"], ["bot", "Bot"], ["web", "Web"], ["agendapro", "AgendaPro"], ["derivado", "Derivado"], ["linkedin", "LinkedIn"], ["convenio", "Convenio"], ["otro", "Otro"]]);
const OPC_ESTADO_LEAD = _op([["nuevo", "Nuevo"], ["contactado", "Contactado"], ["agendado", "Agendado"], ["agendo_no_pago", "Agendó, no pagó"], ["agendo_espera_pago", "Agendó, esp. pago"], ["no_realizada", "No realizada"], ["evaluando", "Evaluando"], ["pendiente_pago", "Pend. pago"], ["ganado", "Inició proceso"], ["perdido", "Perdido"]]);
const OPC_ESTADO_COBRO = _op([["pagado", "Pagado"], ["pendiente", "Pendiente"], ["anulado", "Anulado"]]);
const OPC_MEDIO = _op([["", "—"], ["efectivo", "Efectivo"], ["yape", "Yape"], ["plin", "Plin"], ["tarjeta", "Tarjeta"], ["transferencia", "Transferencia"], ["mercado_pago", "Mercado Pago"]]);
const OPC_CAT_EGRESO = _op([["insumos", "Insumos"], ["sueldos", "Sueldos"], ["alquiler", "Alquiler"], ["equipos", "Equipos"], ["marketing", "Marketing"], ["otro", "Otro"]]);
const OPC_MODALIDAD = _op([["presencial", "Presencial"], ["virtual", "Virtual"], ["ambas", "Ambas"]]);

const FORMATOS = [
  {
    key: "pacientes", label: "Pacientes", endpoint: "pacientes", puedeAgregar: true,
    nuevo: { nombre: "Nuevo paciente", sede: "lima" },
    cols: [
      { campo: "nombre", label: "Nombre", tipo: "text" },
      { campo: "tel", label: "Teléfono", tipo: "text" },
      { campo: "sede", label: "Sede", tipo: "select", opciones: OPC_SEDE },
      { campo: "profesional", label: "Psicólogo", tipo: "fk", fk: "profesionales", labelCampo: "profesional_nombre" },
      { campo: "proceso", label: "Proceso", tipo: "text" },
      { campo: "n_sesion", label: "N° ses.", tipo: "num" },
      { campo: "tipo_documento", label: "Tipo doc", tipo: "select", opciones: OPC_DOC },
      { campo: "numero_documento", label: "N° doc", tipo: "text" },
      { campo: "genero", label: "Género", tipo: "select", opciones: OPC_GENERO },
      { campo: "fecha_nacimiento", label: "F. nac.", tipo: "fecha" },
      { campo: "direccion", label: "Dirección", tipo: "text" },
      { campo: "especialidad", label: "Especialidad", tipo: "text" },
      { campo: "ultima", label: "Últ. visita", tipo: "ro" },
    ],
  },
  {
    key: "leads", label: "Leads", endpoint: "leads", puedeAgregar: true,
    nuevo: { nombre: "Nuevo lead", sede: "lima", fuente: "whatsapp", estado: "nuevo" },
    cols: [
      { campo: "nombre", label: "Nombre", tipo: "text" },
      { campo: "telefono", label: "Teléfono", tipo: "text" },
      { campo: "sede", label: "Sede", tipo: "select", opciones: OPC_SEDE },
      { campo: "fuente", label: "Fuente", tipo: "select", opciones: OPC_FUENTE },
      { campo: "estado", label: "Estado", tipo: "select", opciones: OPC_ESTADO_LEAD },
      { campo: "medico", label: "Psicólogo", tipo: "fk", fk: "medicos", labelCampo: "medico_nombre" },
      { campo: "fecha_consulta", label: "F. consulta", tipo: "fecha" },
      { campo: "fecha_cierre", label: "F. cierre", tipo: "fecha" },
      { campo: "campania", label: "Campaña", tipo: "text" },
      { campo: "especialidad", label: "Motivo", tipo: "text" },
      { campo: "motivo_perdida", label: "Motivo pérdida", tipo: "text" },
      { campo: "notas", label: "Notas", tipo: "text" },
      { campo: "paciente_nombre", label: "Paciente", tipo: "ro" },
      { campo: "creado", label: "Creado", tipo: "ro" },
    ],
  },
  {
    key: "cobros", label: "Cobros / pagos", endpoint: "cobros", puedeAgregar: false,
    cols: [
      { campo: "paciente_nombre", label: "Paciente", tipo: "ro" },
      { campo: "concepto", label: "Concepto", tipo: "text" },
      { campo: "monto", label: "Monto S/", tipo: "num" },
      { campo: "estado", label: "Estado", tipo: "select", opciones: OPC_ESTADO_COBRO },
      { campo: "medio_pago", label: "Medio", tipo: "select", opciones: OPC_MEDIO },
      { campo: "fecha_label", label: "Fecha", tipo: "ro" },
    ],
  },
  {
    key: "servicios", label: "Servicios (precios)", endpoint: "servicios", puedeAgregar: true,
    nuevo: { nombre: "Nuevo servicio", precio: 0, activo: true },
    cols: [
      { campo: "nombre", label: "Nombre", tipo: "text" },
      { campo: "especialidad", label: "Especialidad", tipo: "text" },
      { campo: "precio", label: "Precio S/", tipo: "num" },
      { campo: "activo", label: "Activo", tipo: "check" },
    ],
  },
  {
    key: "egresos", label: "Egresos (gastos)", endpoint: "egresos", puedeAgregar: true,
    nuevo: { concepto: "Nuevo gasto", monto: 1, categoria: "otro" },
    cols: [
      { campo: "concepto", label: "Concepto", tipo: "text" },
      { campo: "categoria", label: "Categoría", tipo: "select", opciones: OPC_CAT_EGRESO },
      { campo: "monto", label: "Monto S/", tipo: "num" },
      { campo: "medio_pago", label: "Medio", tipo: "select", opciones: OPC_MEDIO },
      { campo: "proveedor", label: "Proveedor", tipo: "text" },
      { campo: "fecha_label", label: "Fecha", tipo: "ro" },
    ],
  },
  {
    key: "profesionales", label: "Profesionales", endpoint: "profesionales", puedeAgregar: true,
    nuevo: { nombre: "Nuevo profesional", sede: "lima", activo: true },
    cols: [
      { campo: "nombre", label: "Nombre", tipo: "text" },
      { campo: "titulo", label: "Título", tipo: "text" },
      { campo: "colegiatura", label: "C.Ps.P.", tipo: "text" },
      { campo: "sede", label: "Sede", tipo: "select", opciones: OPC_SEDE },
      { campo: "modalidad", label: "Modalidad", tipo: "select", opciones: OPC_MODALIDAD },
      { campo: "activo", label: "Activo", tipo: "check" },
    ],
  },
  {
    key: "atenciones", label: "Historias clínicas", endpoint: "atenciones", puedeAgregar: false,
    aviso: "La historia clínica es un registro permanente: aquí se corrige, no se borra. Solo psicólogo/admin. (Las atenciones nuevas se crean al Atender una cita.)",
    cols: [
      { campo: "paciente_nombre", label: "Paciente", tipo: "ro" },
      { campo: "fecha", label: "Fecha", tipo: "ro" },
      { campo: "tipo", label: "Tipo", tipo: "select", opciones: TIPOS_HC },
      { campo: "nota", label: "Resumen de la sesión", tipo: "text" },
      { campo: "puntos_importantes", label: "Puntos importantes", tipo: "text" },
      { campo: "proximos_pasos", label: "Próximos pasos", tipo: "text" },
      { campo: "indicaciones", label: "Tratamiento / tareas", tipo: "text" },
      { campo: "motivo", label: "Motivo (H.C.)", tipo: "text" },
      { campo: "aspectos_historicos", label: "Aspectos históricos (H.C.)", tipo: "text" },
      { campo: "objetivos", label: "Objetivos (H.C.)", tipo: "text" },
      { campo: "diagnostico", label: "Impresión dx (H.C.)", tipo: "text" },
      { campo: "especialidad", label: "Especialidad", tipo: "text" },
      { campo: "medico", label: "Psicólogo", tipo: "ro" },
      { campo: "registrado_por_nombre", label: "Registró", tipo: "ro" },
      { campo: "ultima_edicion", label: "Última edición", tipo: "ro" },
    ],
  },
];

function HojasExcel({ showToast, onCambio }) {
  const [fkey, setFkey] = useState("pacientes");
  const cambios = React.useRef(false);
  // Al salir del editor, si hubo cambios, refresca los datos compartidos del
  // sistema (pacientes, citas, etc.) para que las otras pestañas los reflejen.
  useEffect(() => () => { if (cambios.current && onCambio) onCambio(); }, []);
  const formato = FORMATOS.find((f) => f.key === fkey);
  return (
    <div>
      <div className="ca-tophead">
        <div>
          <h1 className="ca-h1">Editar (Excel)</h1>
          <div className="ca-sub">Edita los datos en una grilla. Cada celda se guarda sola al salir (Enter o clic afuera) y se actualiza en todo el sistema.</div>
        </div>
      </div>
      <div className="ca-seg" style={{ flexWrap: "wrap", marginLeft: 0, marginBottom: 14 }}>
        {FORMATOS.map((f) => (
          <button key={f.key} className={fkey === f.key ? "on" : ""} onClick={() => setFkey(f.key)}>{f.label}</button>
        ))}
      </div>
      {formato.aviso && (
        <div className="ca-alert" style={{ marginBottom: 14 }}>
          <AlertTriangle size={16} /> <span>{formato.aviso}</span>
        </div>
      )}
      <HojaEditable key={fkey} formato={formato} showToast={showToast} onSaved={() => { cambios.current = true; }} />
    </div>
  );
}

function HojaEditable({ formato, showToast, onSaved }) {
  const [rows, setRows] = useState(null);
  const [filtro, setFiltro] = useState("");
  const [fk, setFk] = useState({});
  const [estado, setEstado] = useState({});
  const TOPE = 250;

  useEffect(() => {
    let vivo = true;
    setRows(null); setFiltro("");
    api.hojaListar(formato.endpoint)
      .then((d) => { if (vivo) setRows(Array.isArray(d) ? d : (d.results || [])); })
      .catch((e) => { if (vivo) { setRows([]); showToast("Error: " + e.message); } });
    const fks = [...new Set(formato.cols.filter((c) => c.tipo === "fk").map((c) => c.fk))];
    fks.forEach((name) => {
      const loader = name === "medicos" ? api.medicos : api.profesionales;
      loader().then((d) => { if (vivo) setFk((p) => ({ ...p, [name]: d || [] })); }).catch(() => {});
    });
    return () => { vivo = false; };
  }, [formato.key]);

  const fkOpcs = (name) => (fk[name] || []).map((o) => ({ v: String(o.id), l: o.nombre || ("#" + o.id) }));

  function marcar(id, campo, st) {
    const k = id + ":" + campo;
    setEstado((p) => ({ ...p, [k]: st }));
    if (st === "saved") setTimeout(() => setEstado((p) => { const n = { ...p }; delete n[k]; return n; }), 900);
  }

  async function guardar(row, campo, valor) {
    marcar(row.id, campo, "saving");
    try {
      const upd = await api.hojaActualizar(formato.endpoint, row.id, { [campo]: valor });
      setRows((rs) => rs.map((r) => (r.id === row.id ? { ...r, ...upd } : r)));
      marcar(row.id, campo, "saved");
      if (onSaved) onSaved();
    } catch (e) {
      marcar(row.id, campo, "err");
      showToast("No se guardó: " + e.message);
    }
  }

  async function agregar() {
    try {
      const creado = await api.hojaCrear(formato.endpoint, formato.nuevo);
      setRows((rs) => [creado, ...rs]);
      showToast("Fila agregada arriba. Edítala.");
    } catch (e) { showToast("No se pudo agregar: " + e.message); }
  }

  function normaliza(col, raw) {
    if (col.tipo === "num") return raw === "" ? null : Number(raw);
    if (col.tipo === "check") return !!raw;
    if (col.tipo === "fk") return raw === "" ? null : Number(raw);
    if (col.tipo === "fecha") return raw || null;
    return raw;
  }

  function celda(row, col) {
    const st = estado[row.id + ":" + col.campo] || "";
    if (col.tipo === "ro") return <td className="ca-ro">{(row[col.campo] ?? "") === "" ? "—" : row[col.campo]}</td>;
    if (col.tipo === "select" || col.tipo === "fk") {
      const ops = col.tipo === "fk" ? [{ v: "", l: "—" }, ...fkOpcs(col.fk)] : col.opciones;
      const val = col.tipo === "fk" ? (row[col.campo] == null ? "" : String(row[col.campo])) : (row[col.campo] ?? "");
      return (
        <td className={st}>
          <select className="ca-cell" value={val} onChange={(e) => guardar(row, col.campo, normaliza(col, e.target.value))}>
            {ops.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
          </select>
        </td>
      );
    }
    if (col.tipo === "check") {
      return <td className={st} style={{ textAlign: "center" }}>
        <input type="checkbox" checked={!!row[col.campo]} onChange={(e) => guardar(row, col.campo, e.target.checked)} />
      </td>;
    }
    const tipoInput = col.tipo === "num" ? "number" : col.tipo === "fecha" ? "date" : "text";
    return (
      <td className={st}>
        <input className="ca-cell" type={tipoInput} defaultValue={row[col.campo] ?? ""}
          onKeyDown={(e) => { if (e.key === "Enter") e.target.blur(); }}
          onBlur={(e) => {
            const nuevo = normaliza(col, e.target.value);
            const viejo = row[col.campo] ?? (col.tipo === "num" ? null : "");
            if (String(nuevo ?? "") !== String(viejo ?? "")) guardar(row, col.campo, nuevo);
          }} />
      </td>
    );
  }

  const filtradas = useMemo(() => {
    if (!rows) return [];
    const q = filtro.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((r) => formato.cols.some((c) => String(r[c.campo] ?? r[c.labelCampo] ?? "").toLowerCase().includes(q)));
  }, [rows, filtro, formato]);
  const visibles = filtradas.slice(0, TOPE);

  // Valor legible de cada celda para exportar (resuelve fk/select/check a su etiqueta).
  const valorExport = (row, col) => {
    if (col.tipo === "check") return row[col.campo] ? "Sí" : "No";
    if (col.tipo === "fk") {
      const o = fkOpcs(col.fk).find((x) => x.v === String(row[col.campo] ?? ""));
      return o ? o.l : (row[col.labelCampo] ?? row[col.campo] ?? "");
    }
    if (col.tipo === "select") {
      const o = (col.opciones || []).find((x) => String(x.v) === String(row[col.campo] ?? ""));
      return o ? o.l : (row[col.campo] ?? "");
    }
    return row[col.campo] ?? "";
  };
  const expHeaders = formato.cols.map((c) => c.label);
  const expFilas = filtradas.map((r) => formato.cols.map((c) => valorExport(r, c)));

  if (rows === null) return <div className="ca-empty">Cargando…</div>;

  return (
    <div>
      <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 10, flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 7, flex: "1 1 240px", background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8, padding: "7px 11px" }}>
          <Search size={15} color="var(--muted)" />
          <input placeholder={`Buscar en ${formato.label.toLowerCase()}…`} value={filtro} onChange={(e) => setFiltro(e.target.value)}
            style={{ border: 0, outline: "none", background: "transparent", width: "100%", font: "inherit", color: "var(--ink)" }} />
        </div>
        {formato.puedeAgregar && <button className="ca-btn" onClick={agregar}><Plus size={15} /> Nueva fila</button>}
        <ExportBtns nombre={formato.label} titulo={formato.label} headers={expHeaders} filas={expFilas} disabled={filtradas.length === 0} />
        <span style={{ fontSize: 12.5, color: "var(--muted)" }}>
          {filtradas.length} fila{filtradas.length === 1 ? "" : "s"}{filtradas.length > TOPE ? ` · mostrando ${TOPE}` : ""}
        </span>
      </div>
      <div className="ca-hoja-wrap">
        <table className="ca-hoja">
          <thead>
            <tr><th className="rownum">#</th>{formato.cols.map((c) => <th key={c.campo}>{c.label}</th>)}</tr>
          </thead>
          <tbody>
            {visibles.map((row, i) => (
              <tr key={row.id}>
                <td className="rownum">{i + 1}</td>
                {formato.cols.map((c) => <React.Fragment key={c.campo}>{celda(row, c)}</React.Fragment>)}
              </tr>
            ))}
            {visibles.length === 0 && <tr><td className="ca-ro" colSpan={formato.cols.length + 1}>Sin resultados.</td></tr>}
          </tbody>
        </table>
      </div>
      <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 8 }}>
        Edita una celda y sal con Enter o clic afuera para guardar. Borde verde = guardado, rojo = error.
        {!formato.puedeAgregar && " Los cobros se crean desde Finanzas o al Atender."}
      </div>
    </div>
  );
}

// Cultura de Ítaca: ADN, no negociables, pilares I+M, mentalidad ganadora y mi rol.
// La ve todo el equipo (pedido de Emma/Gaby, con su contenido).
function BloqueLista({ titulo, items }) {
  return (
    <div>
      {titulo && <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 5 }}>{titulo}</div>}
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {items.map((it, i) => (
          <div key={i} style={{ fontSize: 13, color: "var(--ink-soft)", lineHeight: 1.5, display: "flex", gap: 7 }}>
            <Check size={14} strokeWidth={2.5} style={{ color: "var(--accent)", flexShrink: 0, marginTop: 3 }} />
            <span>{it}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// Tarjeta de una sección (número + título en versalitas + ícono, con "Ver más").
function MentCard({ id, n, titulo, Icon, resumen, cta = "Ver más", preview, detalle }) {
  const [ver, setVer] = useState(false);
  return (
    <div className="ca-card" id={id} style={{ display: "flex", flexDirection: "column", gap: 10, scrollMarginTop: 16 }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ width: 30, height: 30, borderRadius: 999, background: "var(--accent)", color: "#fff", display: "inline-flex", alignItems: "center", justifyContent: "center", fontWeight: 800, fontSize: 15, flexShrink: 0 }}>{n}</span>
          <div style={{ fontWeight: 800, fontSize: 13.5, letterSpacing: 0.4, color: "var(--accent)", textTransform: "uppercase" }}>{titulo}</div>
        </div>
        <span style={{ width: 40, height: 40, borderRadius: 999, background: "#E9F5F3", display: "inline-flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}><Icon size={19} strokeWidth={2} style={{ color: "var(--accent)" }} /></span>
      </div>
      {resumen && <div style={{ fontSize: 13, color: "var(--ink-soft)", lineHeight: 1.5 }}>{resumen}</div>}
      {preview}
      {ver && detalle && <div style={{ marginTop: 2, paddingTop: 12, borderTop: "1px solid var(--line)", display: "flex", flexDirection: "column", gap: 12 }}>{detalle}</div>}
      {detalle && <button onClick={() => setVer((v) => !v)} style={{ alignSelf: "flex-start", marginTop: "auto", paddingTop: 4, background: "none", border: "none", color: "var(--accent)", fontWeight: 700, fontSize: 13, cursor: "pointer" }}>{ver ? "Ver menos ↑" : `${cta} →`}</button>}
    </div>
  );
}
function MentCheck({ items }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
      {items.map((it, i) => (
        <div key={i} style={{ fontSize: 13.5, display: "flex", gap: 8, alignItems: "center" }}>
          <Check size={16} strokeWidth={2.5} style={{ color: "var(--accent)", flexShrink: 0 }} /><span>{it}</span>
        </div>
      ))}
    </div>
  );
}
function PilarBadge({ icon, texto, titulo, desc, color, bg }) {
  return (
    <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
      <span style={{ width: 34, height: 34, borderRadius: 9, background: bg, color, display: "inline-flex", alignItems: "center", justifyContent: "center", fontWeight: 800, fontSize: 13, flexShrink: 0 }}>{icon ? React.createElement(icon, { size: 18, strokeWidth: 2.2 }) : texto}</span>
      <div>
        <div style={{ fontWeight: 800, fontSize: 12.5, letterSpacing: 0.3, color, textTransform: "uppercase" }}>{titulo}</div>
        <div style={{ fontSize: 12.8, color: "var(--ink-soft)", lineHeight: 1.4 }}>{desc}</div>
      </div>
    </div>
  );
}
function MentIcono({ Icon, label }) {
  return (
    <div style={{ textAlign: "center", flex: "1 1 78px", minWidth: 72 }}>
      <span style={{ width: 40, height: 40, borderRadius: 999, background: "#E9F5F3", display: "inline-flex", alignItems: "center", justifyContent: "center", marginBottom: 5 }}><Icon size={18} strokeWidth={2} style={{ color: "var(--accent)" }} /></span>
      <div style={{ fontSize: 11.5, color: "var(--ink-soft)", lineHeight: 1.3 }}>{label}</div>
    </div>
  );
}

// Sub-secciones del menú lateral cuando estás en Mentalidad Ítaca (llevan a cada tarjeta).
const MENT_SUBS = [
  { id: "adn", label: "ADN Ítaca" },
  { id: "noNeg", label: "No negociables" },
  { id: "pilares", label: "Pilares Ítaca" },
  { id: "ganadora", label: "Mentalidad ganadora" },
  { id: "miRol", label: "Mi rol en Ítaca" },
];

// Contenido por defecto de Mentalidad Ítaca (la gerencia lo puede editar; se guarda
// en Clinica.mentalidad). En los "cuerpo", una línea que empieza con "# " es un
// subtítulo; las demás líneas son viñetas.
const MENT_DEFAULT = {
  intro: "En Ítaca creemos que el conocimiento te convierte en un buen profesional, pero **la cultura es lo que te convierte en un profesional extraordinario**. Esta sección reúne los principios que guían cada decisión, cada interacción y cada sesión. No son reglas; son la forma en que **elegimos cambiar vidas**.",
  cierre: "La cultura no se demuestra en los grandes momentos, sino en las pequeñas decisiones que tomamos cada día. En Ítaca elegimos escuchar con empatía, actuar con excelencia, aprender constantemente, trabajar en equipo y recordar siempre que detrás de cada agenda, cada historia clínica y cada sesión, hay una vida que puede cambiar. Ese es nuestro compromiso. **Esa es la Mentalidad Ítaca.**",
  adn: {
    resumen: "Nuestro propósito, visión y lo que nos mueve cada día.",
    cuerpo: `# Nuestro propósito: cambiar vidas
Cambiar vidas a través de un acompañamiento psicológico humano, ético y basado en evidencia, acercando la salud mental a cada vez más personas.
Cada paciente que llega a Ítaca deposita en nosotros una parte importante de su historia. No solo brindamos sesiones: acompañamos procesos que pueden transformar una vida.
# Nuestra visión
Ser el centro psicológico referente en el Perú por la calidad de nuestra atención, la excelencia de nuestros profesionales y el impacto positivo en la vida de miles de personas.
# ¿Qué significa trabajar en Ítaca?
Cada conversación importa.
Cada paciente merece una experiencia extraordinaria.
La excelencia no es un objetivo; es el estándar.
Siempre buscamos mejorar.
Trabajamos como un solo equipo.
Nunca olvidamos que detrás de cada historia clínica existe una persona.
# Nuestro compromiso
Cambiar vidas.
Generar bienestar.
Crear experiencias memorables.
Crecer como profesionales.
Construir un equipo del que sintamos orgullo.`,
  },
  noNeg: {
    resumen: "Los estándares mínimos que todos vivimos, sin excepción.",
    cuerpo: `# Excelencia profesional
Mantengo mis historias clínicas completas y actualizadas dentro del tiempo establecido.
Me preparo antes de cada sesión.
Conozco a mis pacientes antes de atenderlos.
Mantengo mi agenda organizada.
# Experiencia del paciente
Cada paciente recibe un trato cálido, respetuoso y profesional.
Resuelvo dudas con claridad.
Cada paciente termina la sesión entendiendo cuál es el siguiente paso de su proceso.
Cuido cada detalle de la experiencia, desde el primer contacto hasta el cierre terapéutico.
# Trabajo en equipo
Mantengo comunicación clara y respetuosa.
Aviso oportunamente cualquier incidencia.
Cumplo los acuerdos del equipo.
Colaboro antes de que me lo pidan.
# Responsabilidad
Soy puntual.
Cumplo los plazos establecidos.
Asumo responsabilidad sobre mis errores.
Si detecto un problema, también propongo una solución.
# Crecimiento
Busco aprender constantemente.
Participo activamente en capacitaciones.
Estoy dispuesto a recibir feedback.
Comparto conocimiento con mi equipo.
# Representación de la marca
Represento la confianza que miles de pacientes depositan en nosotros.
Cada conversación, mensaje, llamada o sesión fortalece o debilita esa confianza.`,
  },
  pilares: {
    resumen: "Los principios que sostienen nuestra cultura y guían cada decisión.",
    badges: ["Damos soluciones, no problemas.", "Cada acción cuenta. Cada +1 genera impacto.", "Somos directos, nos cuidamos y resolvemos en equipo."],
    cuerpo: `# 💡 Itactividad — damos soluciones, no problemas
Actuamos con iniciativa, anticipándonos a los desafíos y buscando siempre soluciones.
No esperamos que las cosas sucedan; las hacemos suceder. No nos quejamos de los problemas, los solucionamos.
# ➕1 Sí importa — enfocados en resultados y calidad
Cada acción cuenta. Cada esfuerzo extra, cada detalle y cada mejora suman para una experiencia extraordinaria.
No nos conformamos; siempre damos la milla extra.
# 🛡️ Muro de confianza — directos y nos cuidamos
Construimos relaciones basadas en la comunicación transparente, el respeto y la confianza.
Hablamos directamente, evitamos las suposiciones y resolvemos en equipo. No suponemos nunca, preguntamos siempre.`,
  },
  ganadora: {
    resumen: "No es competir con otros, es desarrollar nuestra mejor versión para generar mayor impacto.",
    ic: ["Pensamos en resultados", "Guiamos con claridad", "Creemos en la continuidad", "Nos enfocamos en el impacto", "Crecemos juntos"],
    cuerpo: `# Pensamos en resultados
Nuestro objetivo no es acumular sesiones, es que más personas logren cambios significativos en su vida.
# Guiamos con claridad
No presionamos ni persuadimos: guiamos al paciente para que tome decisiones informadas sobre su proceso.
# Creemos en la continuidad terapéutica
Los cambios importantes requieren tiempo. Explicamos el proceso, resolvemos dudas y ayudamos al paciente a comprometerse con su bienestar.
# Nos enfocamos en el impacto
Personas que continúan su proceso.
Pacientes satisfechos.
Altas terapéuticas exitosas.
Vidas transformadas.
# Crecemos juntos
Cuando mejora un colaborador, mejora el equipo; cuando mejora el equipo, mejora la experiencia del paciente; y así cumplimos nuestro propósito.`,
  },
  miRol: {
    resumen: "Todos compartimos una misión: contribuir a cambiar vidas desde nuestro rol.",
    roles: {
      medico: "Como psicólogo/a, tu rol es acompañar procesos que transforman vidas: prepara cada sesión, conoce a tu paciente, mantén tus historias clínicas completas y cuida cada detalle de su experiencia.",
      asistente: "Como coordinadora, eres la primera y última impresión del paciente: cuidas la experiencia desde el primer contacto, ordenas la agenda y sostienes la comunicación del equipo.",
      admin: "Desde gerencia sostienes la cultura y los estándares: haces que el propósito de cambiar vidas sea posible cada día.",
      comercial: "Desde captación acercas la salud mental a más personas: cada conversación acerca o aleja a alguien de la ayuda que necesita.",
    },
    cuerpo: `# Lo que esperamos de ti
Actuar con profesionalismo.
Vivir la cultura Ítaca.
Cumplir los estándares de calidad.
Cuidar la experiencia del paciente.
Trabajar colaborativamente.
Buscar siempre mejorar.`,
  },
};

// "# Subtítulo" inicia un bloque; las demás líneas son viñetas.
function parseCuerpo(txt) {
  const blks = []; let cur = null;
  (txt || "").split("\n").forEach((ln) => {
    const t = ln.trim();
    if (!t) return;
    if (t.startsWith("# ")) { cur = { t: t.slice(2).trim(), items: [] }; blks.push(cur); }
    else { if (!cur) { cur = { t: "", items: [] }; blks.push(cur); } cur.items.push(t); }
  });
  return blks;
}
// Renderiza **negrita teal** en un texto.
function MentRich({ text }) {
  return (text || "").split("**").map((p, i) => (i % 2
    ? <strong key={i} style={{ color: "var(--accent)" }}>{p}</strong>
    : <span key={i}>{p}</span>));
}

function MentalidadItaca({ rol, esAdmin, showToast }) {
  const [cfg, setCfg] = useState(null);
  const [editar, setEditar] = useState(false);
  useEffect(() => { api.clinicaConfig().then(setCfg).catch(() => setCfg({})); }, []);
  const M = (cfg && cfg.mentalidad) || {};
  const D = MENT_DEFAULT;
  const c = {
    intro: M.intro ?? D.intro, cierre: M.cierre ?? D.cierre,
    adn: { ...D.adn, ...M.adn }, noNeg: { ...D.noNeg, ...M.noNeg },
    pilares: { ...D.pilares, ...M.pilares }, ganadora: { ...D.ganadora, ...M.ganadora },
    miRol: { ...D.miRol, ...M.miRol, roles: { ...D.miRol.roles, ...((M.miRol && M.miRol.roles) || {}) } },
  };
  const bAdn = parseCuerpo(c.adn.cuerpo), bNeg = parseCuerpo(c.noNeg.cuerpo);
  const bPil = parseCuerpo(c.pilares.cuerpo), bGan = parseCuerpo(c.ganadora.cuerpo), bRol = parseCuerpo(c.miRol.cuerpo);
  const rolItems = (bRol[0] && bRol[0].items) || [];
  const badge = c.pilares.badges || D.pilares.badges;
  const ic = c.ganadora.ic || D.ganadora.ic;
  const GAN_ICONS = [Target, MessageCircle, Heart, BarChart3, Users];
  const bloques = (blks) => blks.map((b, i) => <BloqueLista key={i} titulo={b.t} items={b.items} />);

  return (
    <div>
      {esAdmin && (
        <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
          <button className="ca-btn ghost" onClick={() => setEditar(true)}><Pencil size={14} strokeWidth={2} /> Editar contenido</button>
        </div>
      )}
      {/* Hero */}
      <div className="ca-card" style={{ background: "linear-gradient(135deg, #E7F4F1, #F6FAFD)", borderColor: "#CDE7E2", marginBottom: 18, display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap" }}>
        <div style={{ width: 76, height: 76, borderRadius: 18, background: "#DCEEEA", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, position: "relative" }}>
          <Users size={34} strokeWidth={1.8} style={{ color: "var(--accent)" }} />
          <Heart size={15} strokeWidth={2.5} style={{ color: "var(--accent)", fill: "#fff", position: "absolute", top: 13, right: 13 }} />
        </div>
        <div style={{ flex: 1, minWidth: 260 }}>
          <h1 className="ca-h1" style={{ margin: "0 0 6px" }}>Mentalidad Ítaca</h1>
          <div style={{ fontSize: 14, color: "var(--ink-soft)", lineHeight: 1.6 }}><MentRich text={c.intro} /></div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(290px, 1fr))", gap: 14, alignItems: "start" }}>
        <MentCard id="ment-adn" n="1" titulo="ADN Ítaca" Icon={Sparkles} resumen={c.adn.resumen}
          preview={<MentCheck items={bAdn.map((b) => b.t).filter(Boolean)} />} detalle={bloques(bAdn)} />

        <MentCard id="ment-noNeg" n="2" titulo="No Negociables Ítaca" Icon={Shield} resumen={c.noNeg.resumen}
          preview={<MentCheck items={bNeg.map((b) => b.t).filter(Boolean)} />} detalle={bloques(bNeg)} />

        <MentCard id="ment-pilares" n="3" titulo="Pilares Ítaca · I + M" Icon={Landmark} resumen={c.pilares.resumen} cta="Conocer más"
          preview={<div style={{ display: "flex", flexDirection: "column", gap: 11 }}>
            <PilarBadge icon={Lightbulb} titulo="Itactividad" desc={badge[0]} color="#B0822F" bg="#FBF1D6" />
            <PilarBadge texto="+1" titulo="+1 Sí importa" desc={badge[1]} color="#6E52A3" bg="#EDE7F7" />
            <PilarBadge icon={Shield} titulo="Muro de confianza" desc={badge[2]} color="#3D6B9E" bg="#E4EDF7" />
          </div>}
          detalle={bloques(bPil)} />

        <MentCard id="ment-ganadora" n="4" titulo="Mentalidad Ganadora" Icon={Trophy} resumen={c.ganadora.resumen}
          preview={<div style={{ display: "flex", gap: 6, flexWrap: "wrap", justifyContent: "space-between" }}>
            {ic.map((label, i) => <MentIcono key={i} Icon={GAN_ICONS[i] || Sparkles} label={label} />)}
          </div>}
          detalle={bloques(bGan)} />

        <MentCard id="ment-miRol" n="5" titulo="Mi Rol en Ítaca" Icon={Award} resumen={c.miRol.resumen} cta="Ver mi rol y funciones"
          preview={<div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ background: "var(--bg-soft, #F6F5F2)", borderRadius: 10, padding: "11px 13px", fontSize: 13, lineHeight: 1.5 }}>
              {c.miRol.roles[rol] || "Cada puesto tiene funciones específicas, pero todos somos responsables de la experiencia que vive el paciente."}
            </div>
            <MentCheck items={rolItems.slice(0, 3).map((s) => s.replace(/\.$/, ""))} />
          </div>}
          detalle={bloques(bRol)} />
      </div>

      {/* Cierre */}
      <div className="ca-card" style={{ marginTop: 18, borderColor: "#CDE7E2", background: "linear-gradient(135deg, #EAF5F2, #F6FAFD)", display: "flex", alignItems: "center", gap: 18, flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 260, display: "flex", gap: 12 }}>
          <span style={{ fontSize: 42, lineHeight: 0.9, color: "var(--accent)", fontFamily: "Georgia, serif", flexShrink: 0 }}>“</span>
          <div style={{ fontSize: 14, color: "var(--ink-soft)", lineHeight: 1.65 }}><MentRich text={c.cierre} /></div>
        </div>
        <img src="/itaca-logo-v.png" alt="Ítaca" style={{ height: 70, opacity: 0.92, flexShrink: 0 }} onError={(e) => { e.currentTarget.style.display = "none"; }} />
      </div>

      {editar && <MentalidadEditor inicial={c} showToast={showToast} onClose={() => setEditar(false)}
        onSaved={(nc) => { setCfg((p) => ({ ...(p || {}), mentalidad: nc })); setEditar(false); }} />}
    </div>
  );
}

// Editor del contenido de Mentalidad Ítaca (solo gerencia). Guarda todo en
// Clinica.mentalidad. Los íconos/colores son fijos; se edita el texto.
function MentalidadEditor({ inicial, showToast, onClose, onSaved }) {
  const [f, setF] = useState(JSON.parse(JSON.stringify(inicial)));
  const [guardando, setGuardando] = useState(false);
  const top = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));
  const sec = (s, k) => (e) => setF((p) => ({ ...p, [s]: { ...p[s], [k]: e.target.value } }));
  const arr = (s, k, i) => (e) => setF((p) => ({ ...p, [s]: { ...p[s], [k]: p[s][k].map((v, j) => (j === i ? e.target.value : v)) } }));
  const rolTxt = (k) => (e) => setF((p) => ({ ...p, miRol: { ...p.miRol, roles: { ...p.miRol.roles, [k]: e.target.value } } }));
  const areaCuerpo = { minHeight: 120, resize: "vertical", lineHeight: 1.5, fontSize: 12.5, fontFamily: "inherit" };
  const L = ({ children }) => <div className="ca-label" style={{ marginTop: 10 }}>{children}</div>;

  async function guardar() {
    setGuardando(true);
    try {
      await api.actualizarClinica({ mentalidad: f });
      showToast && showToast("Mentalidad Ítaca guardada ✓");
      onSaved(f);
    } catch (e) { showToast && showToast("Error: " + e.message); }
    finally { setGuardando(false); }
  }

  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 620, maxHeight: "88vh", overflowY: "auto" }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
          <strong style={{ fontSize: 16 }}>Editar Mentalidad Ítaca</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>
        <div className="ca-pmeta" style={{ marginBottom: 6 }}>En los "contenidos", una línea que empieza con <code># </code> es un subtítulo; las demás son viñetas. Usa <code>**texto**</code> para resaltar en la intro y el cierre.</div>

        <L>Introducción</L>
        <textarea className="ca-input" style={{ ...areaCuerpo, minHeight: 80 }} value={f.intro} onChange={top("intro")} />

        <div className="ca-secth" style={{ marginTop: 16 }}>1 · ADN Ítaca</div>
        <L>Resumen</L><input className="ca-input" value={f.adn.resumen} onChange={sec("adn", "resumen")} />
        <L>Contenido</L><textarea className="ca-input" style={areaCuerpo} value={f.adn.cuerpo} onChange={sec("adn", "cuerpo")} />

        <div className="ca-secth" style={{ marginTop: 16 }}>2 · No Negociables</div>
        <L>Resumen</L><input className="ca-input" value={f.noNeg.resumen} onChange={sec("noNeg", "resumen")} />
        <L>Contenido</L><textarea className="ca-input" style={areaCuerpo} value={f.noNeg.cuerpo} onChange={sec("noNeg", "cuerpo")} />

        <div className="ca-secth" style={{ marginTop: 16 }}>3 · Pilares I + M</div>
        <L>Resumen</L><input className="ca-input" value={f.pilares.resumen} onChange={sec("pilares", "resumen")} />
        <L>Itactividad (descripción corta)</L><input className="ca-input" value={f.pilares.badges[0]} onChange={arr("pilares", "badges", 0)} />
        <L>+1 Sí importa (descripción corta)</L><input className="ca-input" value={f.pilares.badges[1]} onChange={arr("pilares", "badges", 1)} />
        <L>Muro de confianza (descripción corta)</L><input className="ca-input" value={f.pilares.badges[2]} onChange={arr("pilares", "badges", 2)} />
        <L>Contenido (detalle)</L><textarea className="ca-input" style={areaCuerpo} value={f.pilares.cuerpo} onChange={sec("pilares", "cuerpo")} />

        <div className="ca-secth" style={{ marginTop: 16 }}>4 · Mentalidad Ganadora</div>
        <L>Resumen</L><input className="ca-input" value={f.ganadora.resumen} onChange={sec("ganadora", "resumen")} />
        {f.ganadora.ic.map((v, i) => (
          <div key={i}><L>Ícono {i + 1} (etiqueta corta)</L><input className="ca-input" value={v} onChange={arr("ganadora", "ic", i)} /></div>
        ))}
        <L>Contenido (detalle)</L><textarea className="ca-input" style={areaCuerpo} value={f.ganadora.cuerpo} onChange={sec("ganadora", "cuerpo")} />

        <div className="ca-secth" style={{ marginTop: 16 }}>5 · Mi Rol en Ítaca</div>
        <L>Resumen</L><input className="ca-input" value={f.miRol.resumen} onChange={sec("miRol", "resumen")} />
        <L>Texto para el psicólogo</L><textarea className="ca-input" style={{ ...areaCuerpo, minHeight: 60 }} value={f.miRol.roles.medico} onChange={rolTxt("medico")} />
        <L>Texto para coordinación</L><textarea className="ca-input" style={{ ...areaCuerpo, minHeight: 60 }} value={f.miRol.roles.asistente} onChange={rolTxt("asistente")} />
        <L>Texto para gerencia</L><textarea className="ca-input" style={{ ...areaCuerpo, minHeight: 60 }} value={f.miRol.roles.admin} onChange={rolTxt("admin")} />
        <L>Texto para comercial</L><textarea className="ca-input" style={{ ...areaCuerpo, minHeight: 60 }} value={f.miRol.roles.comercial} onChange={rolTxt("comercial")} />
        <L>Contenido (lo que esperamos)</L><textarea className="ca-input" style={areaCuerpo} value={f.miRol.cuerpo} onChange={sec("miRol", "cuerpo")} />

        <div className="ca-secth" style={{ marginTop: 16 }}>Cita de cierre</div>
        <textarea className="ca-input" style={{ ...areaCuerpo, minHeight: 80 }} value={f.cierre} onChange={top("cierre")} />

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16 }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" onClick={guardar} disabled={guardando}>{guardando ? "Guardando…" : "Guardar"}</button>
        </div>
      </div>
    </div>
  );
}

// Inicio del psicólogo: sus indicadores, su horario y el contenido institucional
// (MOF + pilares Itaca) siempre visible. Pedido de Emma.
// Niveles de medalla (bronce → leyenda), por índice de nivel alcanzado.
const TIER = [
  { n: "Bloqueada", c: "#B8B8B8" },
  { n: "Bronce", c: "#B87333" },
  { n: "Plata", c: "#8A96A3" },
  { n: "Oro", c: "#D4A017" },
  { n: "Diamante", c: "#2FA5A5" },
  { n: "Platino", c: "#7A5FA8" },
  { n: "Leyenda", c: "#C0392B" },
];
const tierDe = (nivel) => TIER[Math.min(nivel, TIER.length - 1)];

// Confeti de celebración (canvas, sin librerías). Respeta prefers-reduced-motion.
function lanzarConfeti() {
  if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const canvas = document.createElement("canvas");
  canvas.style.cssText = "position:fixed;inset:0;pointer-events:none;z-index:9999";
  document.body.appendChild(canvas);
  const ctx = canvas.getContext("2d");
  const W = (canvas.width = window.innerWidth), H = (canvas.height = window.innerHeight);
  const cols = ["#0E8271", "#E0A93B", "#3B6EA5", "#8B6FC0", "#2C8A5C", "#D4694A"];
  const parts = Array.from({ length: 130 }, () => ({
    x: W / 2 + (Math.random() - 0.5) * W * 0.35, y: H * 0.28 + (Math.random() - 0.5) * 80,
    vx: (Math.random() - 0.5) * 11, vy: Math.random() * -9 - 3,
    r: Math.random() * 6 + 3, c: cols[(Math.random() * cols.length) | 0],
    rot: Math.random() * Math.PI, vr: (Math.random() - 0.5) * 0.3, a: 1,
  }));
  let t0 = null;
  function frame(t) {
    if (t0 === null) t0 = t;
    const el = t - t0;
    ctx.clearRect(0, 0, W, H);
    for (const p of parts) {
      p.vy += 0.3; p.x += p.vx; p.y += p.vy; p.rot += p.vr;
      if (el > 1400) p.a = Math.max(0, p.a - 0.03);
      ctx.save(); ctx.globalAlpha = p.a; ctx.translate(p.x, p.y); ctx.rotate(p.rot);
      ctx.fillStyle = p.c; ctx.fillRect(-p.r / 2, -p.r / 2, p.r, p.r * 0.6); ctx.restore();
    }
    if (el < 2300) requestAnimationFrame(frame); else canvas.remove();
  }
  requestAnimationFrame(frame);
}

// Anillo de progreso (SVG) con el emoji al centro.
function Anillo({ pct, color, children, size = 56 }) {
  const r = (size - 8) / 2, C = 2 * Math.PI * r, off = C * (1 - Math.min(100, pct || 0) / 100);
  return (
    <div style={{ position: "relative", width: size, height: size, margin: "0 auto" }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--line)" strokeWidth="4" />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth="4" strokeLinecap="round"
          strokeDasharray={C} strokeDashoffset={off} style={{ transition: "stroke-dashoffset .7s" }} />
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>{children}</div>
    </div>
  );
}

// "Mi Progreso Ítaca": nivel + puntos + medallas por grados, con celebración.
function MiProgreso({ pr }) {
  useEffect(() => {
    try {
      const KEY = "itaca_mi_progreso";
      const prev = JSON.parse(localStorage.getItem(KEY) || "null");
      const snap = { nivel: pr.nivel, m: Object.fromEntries((pr.medallas || []).map((m) => [m.clave, m.nivel])) };
      if (prev) {
        const subioNivel = snap.nivel > (prev.nivel ?? 0);
        const nuevaMedalla = (pr.medallas || []).some((m) => m.nivel > (prev.m?.[m.clave] ?? 0));
        if (subioNivel || nuevaMedalla) lanzarConfeti();
      }
      localStorage.setItem(KEY, JSON.stringify(snap));
    } catch { /* localStorage bloqueado: sin celebración */ }
  }, [pr.xp, pr.nivel]);

  const pctNivel = pr.es_max ? 100 : Math.round((pr.xp_en_nivel / (pr.xp_por_nivel || 100)) * 100);
  return (
    <div className="ca-card" style={{ marginTop: 14, borderColor: "#D8E6EF", background: "linear-gradient(135deg,#F3F9FC,#F7FBF9)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 14 }}>
        <div style={{ width: 56, height: 56, borderRadius: 16, background: "var(--accent)", color: "#fff", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", flexShrink: 0, boxShadow: "0 4px 12px rgba(14,130,113,.35)" }}>
          <div style={{ fontSize: 8.5, opacity: 0.85, letterSpacing: 0.5 }}>NIVEL</div>
          <div style={{ fontSize: 22, fontWeight: 800, lineHeight: 1 }}>{pr.nivel}</div>
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 15, fontWeight: 800 }}>{pr.rango} <span style={{ fontWeight: 600, color: "var(--muted)", fontSize: 12.5 }}>· {pr.xp} pts</span></div>
          <div style={{ height: 9, background: "var(--line)", borderRadius: 999, overflow: "hidden", marginTop: 6 }}>
            <div style={{ width: `${pctNivel}%`, height: "100%", background: "linear-gradient(90deg,var(--accent),#35C0AC)", transition: "width .7s" }} />
          </div>
          <div style={{ fontSize: 11.5, color: "var(--muted)", marginTop: 4 }}>
            {pr.es_max ? "¡Nivel máximo! 🏆" : `${(pr.xp_por_nivel || 100) - pr.xp_en_nivel} pts para el siguiente nivel`}
          </div>
        </div>
      </div>

      <div style={{ fontSize: 12.5, fontWeight: 600, color: "var(--ink-soft)", marginBottom: 2 }}>Mis medallas 🏅</div>
      <div style={{ fontSize: 11.5, color: "var(--muted)", marginBottom: 9, lineHeight: 1.45 }}>
        Cada medalla premia una parte de tu trabajo (historias al día, sesiones, satisfacción de tus pacientes…). Sube de grado <b>Bronce → Plata → Oro → Diamante → Platino → Leyenda</b> y suma puntos para tu <b>nivel</b>. «Faltan X» es lo que te falta para el siguiente grado.
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(132px,1fr))", gap: 10 }}>
        {(pr.medallas || []).map((m) => {
          const t = tierDe(m.nivel), desbloq = m.nivel > 0;
          const pctMed = m.siguiente != null ? Math.min(100, Math.round((m.valor / m.siguiente) * 100)) : 100;
          return (
            <div key={m.clave} title={m.desc} style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 12, padding: "12px 10px", textAlign: "center" }}>
              <Anillo pct={pctMed} color={desbloq ? t.c : "#C9C9C9"}>
                <span style={{ fontSize: 22, filter: desbloq ? "none" : "grayscale(1) opacity(.5)" }}>{m.emoji}</span>
              </Anillo>
              <div style={{ fontSize: 12.5, fontWeight: 700, marginTop: 6 }}>{m.label}</div>
              <div style={{ fontSize: 11, fontWeight: 700, color: desbloq ? t.c : "var(--muted)", marginTop: 1 }}>{desbloq ? t.n : "Bloqueada"}</div>
              <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 3 }}>
                {m.valor}{m.sufijo}{m.siguiente != null ? ` · faltan ${Math.max(0, m.siguiente - m.valor)}${m.sufijo}` : " · ¡máx!"}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function PanelPsicologo({ panel }) {
  const [ver, setVer] = useState(false); // desplegar MOF/pilares
  const m = panel.metricas || {};
  const kpis = [
    { l: "Ocupación", v: m.ocupacion, suf: "%", sub: `${m.sesiones_semana} esta semana`, hint: "Marca tu horario para verlo" },
    { l: "Cierre de consulta", v: m.cierre, suf: "%", sub: `${m.cierre_num}/${m.cierre_den} a proceso`, hint: "Aún sin consultas" },
    { l: "Satisfacción", v: m.satisfaccion, suf: "%", sub: `${m.nps_respondieron} de ${m.pacientes} respondieron`, hint: "Aún sin respuestas NPS" },
    { l: "Sesiones promedio", v: m.ltv, suf: "", sub: "por paciente (LTV)", hint: "Aún sin datos" },
  ];
  return (
    <div className="ca-card" style={{ marginTop: 14, borderColor: "#DCE7F0", background: "#F6FAFD" }}>
      <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, display: "flex", alignItems: "center", gap: 7 }}>
        <Activity size={15} strokeWidth={2} style={{ color: "var(--accent)" }} /> Mi tablero
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: 10 }}>
        {kpis.map((k) => (
          <div key={k.l} style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 10, padding: "10px 12px" }}>
            <div style={{ fontSize: 12, color: "var(--muted)", fontWeight: 600 }}>{k.l}</div>
            <div style={{ fontSize: 22, fontWeight: 700, marginTop: 2 }}>
              {k.v == null ? <span style={{ fontSize: 13, fontWeight: 500, color: "var(--muted)" }}>—</span> : <>{k.v}{k.suf}</>}
            </div>
            <div style={{ fontSize: 11.5, color: "var(--muted)", marginTop: 2 }}>{k.v == null ? k.hint : k.sub}</div>
          </div>
        ))}
      </div>

      {panel.progreso && <MiProgreso pr={panel.progreso} />}

      {panel.agendadas && panel.agendadas.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <div style={{ fontSize: 12.5, fontWeight: 600, color: "var(--ink-soft)", marginBottom: 6 }}>Sesiones agendadas por venir</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {panel.agendadas.map((a) => (
              <div key={a.servicio} style={{ fontSize: 12.5, background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8, padding: "5px 10px" }}>
                <strong>{a.n}</strong> {a.servicio}
              </div>
            ))}
          </div>
        </div>
      )}

      {panel.horario && panel.horario.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <div style={{ fontSize: 12.5, fontWeight: 600, color: "var(--ink-soft)", marginBottom: 6 }}>
            Mi horario de atención {panel.modalidad ? `· ${panel.modalidad}` : ""} {panel.cupos_semana ? `· ${panel.cupos_semana} cupos/sem` : ""}
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {panel.horario.map((h) => (
              <div key={h.dia} style={{ fontSize: 12.5, background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8, padding: "5px 9px" }}>
                <strong>{h.dia}</strong> {(h.slots || []).map((s, i) => {
                  const col = { presencial: "#4F8A77", virtual: "#3D6B9E", mixto: "#8A6BB0" }[s.mod];
                  return <span key={i}>{i ? ", " : " "}<span style={{ color: col || "inherit", fontWeight: col ? 600 : 400 }}>{s.hora}{s.mod ? ` (${s.mod[0].toUpperCase()})` : ""}</span></span>;
                })}
              </div>
            ))}
          </div>
        </div>
      )}

      {(panel.mof || panel.pilares) && (
        <div style={{ marginTop: 14, paddingTop: 12, borderTop: "1px solid var(--line)" }}>
          <button className="ca-mini" onClick={() => setVer((v) => !v)}>
            <FileText size={13} strokeWidth={2} /> MOF y pilares Itaca {ver ? "▲" : "▼"}
          </button>
          {ver && (
            <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 12 }}>
              {panel.pilares && <div><div style={{ fontSize: 12.5, fontWeight: 700, marginBottom: 3 }}>Pilares Itaca</div><div style={{ fontSize: 13, color: "var(--ink-soft)", whiteSpace: "pre-wrap", lineHeight: 1.55 }}>{panel.pilares}</div></div>}
              {panel.mof && <div><div style={{ fontSize: 12.5, fontWeight: 700, marginBottom: 3 }}>MOF</div><div style={{ fontSize: 13, color: "var(--ink-soft)", whiteSpace: "pre-wrap", lineHeight: 1.55 }}>{panel.mof}</div></div>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Barra de "Meta comercial del mes". Se muestra una por sede (gerencia) o solo
// la de la sede del coordinador. La barra llega hasta la meta IDEAL.
function MetaComercialBar({ m }) {
  const pos = (v) => `${Math.min(Math.max((v / m.meta_ideal) * 100, 0), 100)}%`;
  const falta = Math.max(m.esperado_hoy - m.generado, 0);
  const sedeLbl = m.sede_label || m.sede || "";
  return (
    <div className="ca-card" style={{ marginTop: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
        <div style={{ fontSize: 14, fontWeight: 600, display: "flex", alignItems: "center", gap: 7 }}>
          <TrendingUp size={15} strokeWidth={2} style={{ color: "var(--accent)" }} /> Meta comercial del mes
          {sedeLbl && <span style={{ marginLeft: 8, fontSize: 11.5, fontWeight: 600, padding: "1px 9px", borderRadius: 999, background: "#EEF2EC", color: "#4B6B4E", textTransform: "capitalize" }}>{sedeLbl}</span>}
        </div>
        <div style={{ fontSize: 12.5, fontWeight: 600, color: m.en_ritmo ? "#2F6B4F" : "#B0822F" }}>
          {m.en_ritmo ? "✓ En ritmo" : `${money(falta)} por debajo del ritmo`}
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap", marginBottom: 10 }}>
        <span style={{ fontSize: 24, fontWeight: 700 }}>{money(m.generado)}</span>
        <span style={{ fontSize: 12.5, color: "var(--muted)" }}>generado · día {m.dia} de {m.dias_mes}</span>
        <span style={{ marginLeft: "auto", fontSize: 13.5, fontWeight: 600, color: m.pct_min >= 100 ? "#2F6B4F" : "var(--ink)" }}>
          {m.pct_min}% de la meta mínima
        </span>
      </div>
      <div style={{ position: "relative", height: 12, borderRadius: 999, background: "var(--line)", overflow: "hidden" }}>
        <div style={{ width: pos(m.generado), height: "100%", background: m.pct_min >= 100 ? "#2F6B4F" : "var(--accent)", transition: "width .3s" }} />
        <div title={`Meta mínima ${money(m.meta_min)}`} style={{ position: "absolute", left: pos(m.meta_min), top: 0, width: 2, height: "100%", background: "#8A8378" }} />
        <div title={`Ritmo esperado a hoy: ${money(m.esperado_hoy)}`} style={{ position: "absolute", left: pos(m.esperado_hoy), top: 0, width: 2, height: "100%", background: "#B0822F", opacity: 0.85 }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11.5, color: "var(--muted)", marginTop: 6 }}>
        <span>Mínima {money(m.meta_min)}</span>
        <span title="Lo que deberías llevar hoy para ir en ritmo">Ritmo hoy {money(m.esperado_hoy)}</span>
        <span>Ideal {money(m.meta_ideal)}</span>
      </div>
    </div>
  );
}

function Hoy({ proximas, citasHoy, porConfirmar, atendidas, onOpen, onGo, onRetencion, cumple, esAdmin, esMedico, showToast }) {
  const [r, setR] = useState(null);
  const [legalRec, setLegalRec] = useState(null);
  const [recordatorios, setRecordatorios] = useState([]);
  const [panel, setPanel] = useState(null); // panel del psicólogo (mi-panel)
  useEffect(() => { api.hoy().then(setR).catch(() => {}); }, []);
  useEffect(() => { api.miPanel().then((p) => setPanel(p?.es_psicologo ? p : null)).catch(() => {}); }, []);
  useEffect(() => { api.recursos("recordatorio").then((rs) => setRecordatorios((rs || []).filter((x) => x.activo))).catch(() => {}); }, []);
  useEffect(() => {
    if (!esAdmin) return;
    api.profesionales().then((ps) => {
      const hoy = new Date(), mes = hoy.getMonth(), anio = hoy.getFullYear();
      const mesDe = (iso) => (iso ? Number(iso.slice(5, 7)) - 1 : null);
      const cumpleN = ps.filter((p) => p.activo && p.fecha_nacimiento && mesDe(p.fecha_nacimiento) === mes).length;
      let aniv = 0;
      ps.forEach((p) => {
        if (!p.activo || !p.fecha_ingreso) return;
        const ini = dLocal(p.fecha_ingreso);
        if (ini.getMonth() === mes && anio > ini.getFullYear()) aniv++;
        const s = new Date(ini); s.setMonth(s.getMonth() + 6);
        if (s.getMonth() === mes && s.getFullYear() === anio) aniv++;
      });
      const vence = ps.filter((p) => p.activo && p.contrato_vencimiento && (dLocal(p.contrato_vencimiento) - hoy) / 86400000 <= 45).length;
      setLegalRec({ cumple: cumpleN, aniv, vence });
    }).catch(() => {});
  }, [esAdmin]);
  const legalTotal = legalRec ? legalRec.cumple + legalRec.aniv + legalRec.vence : 0;
  const revisarElim = (id) => {
    api.marcarEliminacionRevisada(id)
      // Recarga el resumen: si había más avisos que los 12 mostrados, entran los
      // siguientes y el contador total baja de verdad (persistido en el servidor).
      .then(() => api.hoy().then(setR))
      .catch((e) => (showToast || window.alert)("No se pudo marcar como revisado: " + e.message));
  };
  const revisarTodasElim = () => {
    api.marcarTodasEliminacionesRevisadas()
      .then((res) => {
        setR((prev) => (prev ? { ...prev, eliminaciones: [], eliminaciones_total: 0 } : prev));
        showToast && showToast(`${res.revisadas} aviso(s) marcados como revisados ✓`);
      })
      .catch((e) => (showToast || window.alert)("No se pudo marcar todo: " + e.message));
  };
  const _hh = new Date().getHours();
  const saludo = _hh < 12 ? "Buenos días 🌞" : _hh < 19 ? "Buenas tardes ☀️" : "Buenas noches 🌙";
  return (
    <>
      <h1 className="ca-h1">{saludo}</h1>
      <div className="ca-sub">{labelLargo(HOY_ISO)} · Aquí está tu día, sin sorpresas.</div>

      {panel && <PanelPsicologo panel={panel} />}

      {recordatorios.length > 0 && (
        <div className="ca-card" style={{ marginTop: 14, borderColor: "#F0E4C9", background: "#FDFAF1" }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 10, display: "flex", alignItems: "center", gap: 7 }}>
            <Bell size={15} strokeWidth={2} style={{ color: "#B0822F" }} /> Recordatorios del equipo
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {recordatorios.map((rc) => (
              <div key={rc.id} style={{ display: "flex", gap: 9, alignItems: "flex-start" }}>
                <span style={{ fontSize: 15, lineHeight: 1.3 }}>{rc.fijado ? "📌" : "•"}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13.8, fontWeight: 600 }}>{rc.titulo}{rc.categoria ? <span style={{ marginLeft: 8, fontSize: 11.5, fontWeight: 600, padding: "1px 8px", borderRadius: 999, background: "#F1E8CF", color: "#8A6D2E" }}>{rc.categoria}</span> : null}</div>
                  {rc.descripcion && <div style={{ fontSize: 13, color: "var(--ink-soft)", whiteSpace: "pre-wrap", lineHeight: 1.5, marginTop: 2 }}>{rc.descripcion}</div>}
                  {rc.link && <a href={rc.link} target="_blank" rel="noreferrer" style={{ fontSize: 12.5, color: "var(--accent)", fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 4, marginTop: 3 }}><ExternalLink size={12} strokeWidth={2} /> Abrir</a>}
                </div>
              </div>
            ))}
          </div>
          {esAdmin && <button className="ca-mini" style={{ marginTop: 12 }} onClick={() => onGo("herramientas")}><Pencil size={13} strokeWidth={2} /> Gestionar recordatorios</button>}
        </div>
      )}

      {r && r.por_continuidad && r.por_continuidad.length > 0 && (
        <div className="ca-card" style={{ marginTop: 14, borderColor: "#CDE8F0", background: "#F4FBFD" }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 10, display: "flex", alignItems: "center", gap: 7, flexWrap: "wrap" }}>
            <Activity size={15} strokeWidth={2} style={{ color: "var(--accent)" }} /> Evaluar continuidad
            <span style={{ fontWeight: 400, color: "var(--muted)", fontSize: 12.5 }}>· {r.por_continuidad_total} paciente{r.por_continuidad_total !== 1 ? "s" : ""} por terminar proceso (sesión 6, 12…)</span>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {r.por_continuidad.map((p) => (
              <button key={p.id} className="ca-mini" onClick={() => onOpen(p.id)}>
                {p.nombre} <span style={{ color: "var(--muted)" }}>· sesión {p.n_sesion}/{p.meta}</span>
              </button>
            ))}
          </div>
          {r.por_continuidad_total > r.por_continuidad.length && (
            <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 8 }}>y {r.por_continuidad_total - r.por_continuidad.length} más…</div>
          )}
        </div>
      )}

      {esAdmin && r && r.eliminaciones && r.eliminaciones.length > 0 && (
        <div className="ca-card" style={{ marginTop: 14, borderColor: "#F0D6D6", background: "#FDF6F6" }}>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 10, display: "flex", alignItems: "center", gap: 7, flexWrap: "wrap" }}>
            <Trash2 size={15} strokeWidth={2} style={{ color: "#9C4646" }} /> Eliminaciones recientes
            <span style={{ fontWeight: 400, color: "var(--muted)", fontSize: 12.5 }}>
              · citas y pagos borrados en los últimos 7 días
              {(r.eliminaciones_total || 0) > r.eliminaciones.length && ` · mostrando ${r.eliminaciones.length} de ${r.eliminaciones_total}`}
            </span>
            <button className="ca-mini" style={{ marginLeft: "auto", color: "#2F6B4F", borderColor: "#BFE0CC" }}
              onClick={revisarTodasElim} title="Marcar TODOS los avisos pendientes como revisados y conformes">
              <Check size={13} strokeWidth={2.2} /> OK a todo{(r.eliminaciones_total || r.eliminaciones.length) > 1 ? ` (${r.eliminaciones_total || r.eliminaciones.length})` : ""}
            </button>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
            {r.eliminaciones.map((e, i) => (
              <div key={e.id ?? i} style={{ fontSize: 13, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                <span style={{ fontSize: 11, fontWeight: 600, color: "#9C4646", background: "#F7E1E1", padding: "1px 8px", borderRadius: 20 }}>{e.tipo_label}</span>
                <span style={{ flex: 1, minWidth: 120 }}>{e.descripcion}{e.paciente ? ` · ${e.paciente}` : ""}</span>
                <span style={{ color: "var(--muted)", fontSize: 12 }}>{e.usuario} · {e.cuando}</span>
                {e.id != null && (
                  <button className="ca-mini" style={{ color: "#2F6B4F", borderColor: "#BFE0CC" }} onClick={() => revisarElim(e.id)} title="Marcar como revisado y conforme">
                    <Check size={13} strokeWidth={2.2} /> OK
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {esAdmin && legalTotal > 0 && (
        <button onClick={() => onGo("legal")} className="ca-card" style={{ width: "100%", textAlign: "left", cursor: "pointer", marginTop: 14, borderColor: "#EAD9F2", background: "#FBF7FE", display: "flex", alignItems: "center", gap: 10 }}>
          <FileText size={16} strokeWidth={2} style={{ color: "#6B4E96" }} />
          <span style={{ fontSize: 13.5 }}>
            <strong>Legal este mes:</strong> {legalRec.cumple} cumpleaños · {legalRec.aniv} aniversarios · {legalRec.vence} contrato(s) por vencer
          </span>
          <span style={{ marginLeft: "auto", color: "var(--accent)", fontWeight: 600, fontSize: 13 }}>Ver →</span>
        </button>
      )}

      <div className="ca-glance">
        <button className="ca-gcard" onClick={() => onGo("agenda")}>
          <div className="ca-ghead"><Calendar size={14} strokeWidth={2} /> Agenda</div>
          <div className="ca-gmain">{citasHoy} sesiones hoy</div>
          <div className="ca-gsub">{atendidas} atendidas · {citasHoy - atendidas} por venir</div>
        </button>
        {!esMedico && (
          <button className="ca-gcard" onClick={() => onGo("marketing")}>
            <div className="ca-ghead"><Megaphone size={14} strokeWidth={2} /> Captación</div>
            <div className="ca-gmain">{r ? `${r.leads_nuevos} leads` : "…"}</div>
            <div className="ca-gsub">{r ? `nuevos sin contactar · ${r.leads_hoy} hoy` : "cargando…"}</div>
          </button>
        )}
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
        {!esMedico && (
          <button className="ca-gcard" onClick={onRetencion} style={{ borderColor: "#F0DDBF" }}>
            <div className="ca-ghead" style={{ color: "#B0822F" }}><AlertTriangle size={14} strokeWidth={2} /> Retención</div>
            <div className="ca-gmain">{r ? `${r.sin_proxima} pacientes` : "…"}</div>
            <div className="ca-gsub">sin próxima sesión · reactivar</div>
          </button>
        )}
        {r && r.nps && r.nps.n > 0 && (
          <button className="ca-gcard" onClick={() => onGo("pacientes")} style={{ borderColor: "#CDE8F0", cursor: "default" }}>
            <div className="ca-ghead" style={{ color: "var(--accent)" }}><HeartPulse size={14} strokeWidth={2} /> NPS promedio</div>
            <div className="ca-gmain">{r.nps.promedio}</div>
            <div className="ca-gsub">{r.nps.n} respuesta{r.nps.n !== 1 ? "s" : ""} · últimos {r.nps.dias} días · índice {r.nps.indice}</div>
          </button>
        )}
      </div>

      {!esMedico && (() => {
        // Gerencia: una barra por sede (r.metas); coordinación: solo la suya (r.meta).
        const metas = (r?.metas && r.metas.length) ? r.metas : (r?.meta ? [r.meta] : []);
        const vis = metas.filter((m) => m && m.meta_ideal > 0);
        if (!vis.length) return null;
        return <>{vis.map((m, i) => <MetaComercialBar key={m.sede || i} m={m} />)}</>;
      })()}

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

      <div style={{ textAlign: "center", marginTop: 34, marginBottom: 6, fontSize: 13.5, fontWeight: 600, color: "var(--accent)", letterSpacing: "-0.01em" }}>
        Sigamos cambiando vidas juntos 💚
      </div>
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

const ESCALAS_DEF = [
  { v: "phq9", l: "PHQ-9 · Depresión", max: 27 },
  { v: "gad7", l: "GAD-7 · Ansiedad", max: 21 },
  { v: "dass21", l: "DASS-21 · Estrés", max: 42 },
  { v: "isi", l: "ISI · Insomnio", max: 28 },
  { v: "pss10", l: "PSS-10 · Estrés percibido", max: 40 },
  { v: "pcl5", l: "PCL-5 · Estrés postraumático", max: 80 },
  { v: "otra", l: "Otra escala", max: null },
];
const NIVEL_COLOR = { normal: "#2F6B4F", leve: "#9C6B2E", moderado: "#C9923A", severo: "#9C4646" };

function EscalasPaciente({ pacienteId, puede, showToast }) {
  const [lista, setLista] = useState([]);
  const [nueva, setNueva] = useState(false);
  const [cargando, setCargando] = useState(true);
  function cargar() { setCargando(true); api.escalas(pacienteId).then(setLista).catch(() => {}).finally(() => setCargando(false)); }
  useEffect(() => { cargar(); }, [pacienteId]);

  const grupos = useMemo(() => {
    const m = {};
    lista.forEach((e) => {
      const key = e.escala === "otra" ? `otra:${e.nombre_escala}` : e.escala;
      if (!m[key]) m[key] = [];
      m[key].push(e);
    });
    Object.values(m).forEach((arr) => arr.sort((a, b) => a.fecha.localeCompare(b.fecha)));
    return m;
  }, [lista]);

  async function borrar(e) {
    if (!window.confirm(`¿Eliminar ${e.nombre_escala} del ${labelNumMes(e.fecha)} (${e.puntaje})?`)) return;
    try { await api.borrarEscala(e.id); cargar(); showToast && showToast("Escala eliminada"); }
    catch (err) { showToast && showToast("Error: " + err.message); }
  }

  const claves = Object.keys(grupos);
  return (
    <>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <h2 className="ca-secth">Escalas y tests</h2>
        {puede && <button className="ca-mini" onClick={() => setNueva(true)}><Plus size={13} strokeWidth={2.2} /> Registrar escala</button>}
      </div>
      <div className="ca-card" style={{ marginBottom: 26 }}>
        {claves.length === 0 ? (
          <div style={{ color: "var(--muted)", fontSize: 13.5 }}>{cargando ? "Cargando…" : "Sin escalas registradas. Usa «Registrar escala» para llevar PHQ-9, GAD-7, DASS-21 y ver su evolución."}</div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))", gap: 16 }}>
            {claves.map((k) => {
              const arr = grupos[k];
              const ult = arr[arr.length - 1];
              const color = NIVEL_COLOR[ult.nivel] || "var(--muted)";
              const valores = arr.map((e) => e.puntaje);
              const previo = arr.length >= 2 ? arr[arr.length - 2].puntaje : null;
              const delta = previo != null ? ult.puntaje - previo : null;
              return (
                <div key={k} style={{ border: "1px solid var(--line)", borderRadius: 10, padding: 12 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 600, marginBottom: 6 }}>{ult.nombre_escala}</div>
                  <div style={{ display: "flex", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
                    <span style={{ fontSize: 24, fontWeight: 700 }}>{ult.puntaje}</span>
                    {ult.severidad && <span style={{ fontSize: 12.5, fontWeight: 600, color }}>{ult.severidad}</span>}
                    {delta != null && delta !== 0 && <span style={{ fontSize: 11.5, color: delta < 0 ? "#2F6B4F" : "#9C4646" }}>{delta < 0 ? "▼" : "▲"} {Math.abs(delta)}</span>}
                  </div>
                  <div className="ca-pmeta" style={{ marginBottom: valores.length >= 2 ? 8 : 0 }}>{labelNumMes(ult.fecha)}{arr.length > 1 ? ` · ${arr.length} tomas` : ""}</div>
                  {valores.length >= 2 && <Sparkline valores={valores} color={color} ancho={180} alto={34} />}
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
                    {arr.slice(-8).map((e) => (
                      <span key={e.id} title={`${labelNumMes(e.fecha)}: ${e.puntaje}${e.severidad ? ` (${e.severidad})` : ""}${puede ? " · clic para eliminar" : ""}`}
                        onClick={() => puede && borrar(e)}
                        style={{ fontSize: 11, background: "var(--accent-soft)", borderRadius: 6, padding: "2px 7px", cursor: puede ? "pointer" : "default" }}>
                        {e.puntaje}
                      </span>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
      {nueva && <EscalaModal pacienteId={pacienteId} onClose={() => setNueva(false)} onSaved={() => { setNueva(false); cargar(); }} showToast={showToast} />}
    </>
  );
}

function EscalaModal({ pacienteId, onClose, onSaved, showToast }) {
  const [escala, setEscala] = useState("phq9");
  const [escalaOtra, setEscalaOtra] = useState("");
  const [puntaje, setPuntaje] = useState("");
  const [fecha, setFecha] = useState(HOY_ISO);
  const [notas, setNotas] = useState("");
  const def = ESCALAS_DEF.find((x) => x.v === escala);
  async function guardar() {
    if (puntaje === "" || Number(puntaje) < 0) return showToast && showToast("Ingresa el puntaje.");
    if (escala === "otra" && !escalaOtra.trim()) return showToast && showToast("Ponle nombre a la escala.");
    try {
      await api.crearEscala({ paciente: pacienteId, escala, escala_otra: escalaOtra.trim(), puntaje: Number(puntaje), fecha, notas: notas.trim() });
      showToast && showToast("Escala registrada ✓"); onSaved();
    } catch (e) { showToast && showToast("Error: " + e.message); }
  }
  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 400 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <strong style={{ fontSize: 16 }}>Registrar escala</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>
        <div style={{ marginBottom: 13 }}>
          <div className="ca-label">Escala</div>
          <select className="ca-input" value={escala} onChange={(e) => setEscala(e.target.value)}>
            {ESCALAS_DEF.map((x) => <option key={x.v} value={x.v}>{x.l}</option>)}
          </select>
        </div>
        {escala === "otra" && (
          <div style={{ marginBottom: 13 }}>
            <div className="ca-label">Nombre de la escala</div>
            <input className="ca-input" value={escalaOtra} onChange={(e) => setEscalaOtra(e.target.value)} placeholder="Ej: AAQ-II, WHO-5…" />
          </div>
        )}
        <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Puntaje{def && def.max ? ` (0–${def.max})` : ""}</div>
            <input className="ca-input" type="number" min="0" max={def && def.max ? def.max : undefined} value={puntaje} onChange={(e) => setPuntaje(e.target.value)} autoFocus />
          </div>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Fecha</div>
            <input className="ca-input" type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
          </div>
        </div>
        <div style={{ marginBottom: 16 }}>
          <div className="ca-label">Notas <span style={{ color: "var(--muted)", fontWeight: 400 }}>(opcional)</span></div>
          <input className="ca-input" value={notas} onChange={(e) => setNotas(e.target.value)} placeholder="Contexto de la aplicación…" />
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" onClick={guardar}>Registrar</button>
        </div>
      </div>
    </div>
  );
}

const NPS_CAT = {
  promotor: { l: "Promotor", c: "#2F6B4F" },
  pasivo: { l: "Pasivo", c: "#9C6B2E" },
  detractor: { l: "Detractor", c: "#9C4646" },
};

function NpsModal({ pacienteId, onClose, onSaved, showToast }) {
  const [puntaje, setPuntaje] = useState("");
  const [comentario, setComentario] = useState("");
  const [fecha, setFecha] = useState(HOY_ISO);
  async function guardar() {
    const n = Number(puntaje);
    if (puntaje === "" || n < 0 || n > 10) return showToast && showToast("El puntaje va de 0 a 10.");
    try {
      await api.crearNPS({ paciente: pacienteId, puntaje: n, comentario: comentario.trim(), fecha });
      showToast && showToast("NPS registrado ✓"); onSaved();
    } catch (e) { showToast && showToast("Error: " + e.message); }
  }
  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 380 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
          <strong style={{ fontSize: 16 }}>Registrar NPS</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>
        <div className="ca-pmeta" style={{ marginBottom: 13 }}>¿Qué tan probable es que recomiende la clínica? (0 = nada · 10 = muchísimo)</div>
        <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
          <div style={{ flex: 1 }}><div className="ca-label">Puntaje (0-10)</div><input className="ca-input" type="number" min="0" max="10" value={puntaje} onChange={(e) => setPuntaje(e.target.value)} autoFocus /></div>
          <div style={{ flex: 1 }}><div className="ca-label">Fecha</div><input className="ca-input" type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} /></div>
        </div>
        <div style={{ marginBottom: 16 }}>
          <div className="ca-label">Comentario <span style={{ color: "var(--muted)", fontWeight: 400 }}>(opcional)</span></div>
          <input className="ca-input" value={comentario} onChange={(e) => setComentario(e.target.value)} />
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" onClick={guardar}>Registrar</button>
        </div>
      </div>
    </div>
  );
}

function NpsPaciente({ pacienteId, puede, showToast }) {
  const [lista, setLista] = useState([]);
  const [modal, setModal] = useState(false);
  const [enviando, setEnviando] = useState(false);
  function cargar() { api.nps(pacienteId).then(setLista).catch(() => {}); }
  useEffect(() => { cargar(); }, [pacienteId]);
  const ult = lista[lista.length - 1];
  const cat = ult ? (NPS_CAT[ult.categoria] || NPS_CAT.pasivo) : null;

  async function pedir() {
    setEnviando(true);
    try {
      const r = await api.enviarNPS(pacienteId);
      if (r.ok) showToast && showToast("Encuesta enviada ✓ · su respuesta se registrará sola");
      else if (r.wa_url) { window.open(r.wa_url, "_blank"); showToast && showToast("Abrimos WhatsApp para enviarla a mano 📲"); }
      else showToast && showToast("No se pudo enviar: " + (r.detalle || "revisa el teléfono"));
    } catch (e) { showToast && showToast("Error: " + e.message); }
    finally { setEnviando(false); }
  }

  return (
    <FichaCard label="NPS paciente">
      {!ult ? (
        <div style={{ color: "var(--muted)", fontSize: 13.5 }}>Sin respuestas aún.</div>
      ) : (
        <>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
            <span style={{ fontSize: 26, fontWeight: 700, color: cat.c }}>{ult.puntaje}</span>
            <span style={{ fontSize: 12.5, fontWeight: 600, color: cat.c }}>{cat.l}</span>
          </div>
          <div className="ca-pmeta">Última respuesta: {labelNumMes(ult.fecha)}{lista.length > 1 ? ` · ${lista.length} respuestas` : ""}</div>
          {lista.length >= 2 && <div style={{ marginTop: 6 }}><Sparkline valores={lista.map((x) => x.puntaje)} color={cat.c} ancho={150} alto={28} /></div>}
        </>
      )}
      {puede && (
        <div style={{ display: "flex", gap: 12, marginTop: 8, flexWrap: "wrap" }}>
          <button className="ca-link" onClick={() => setModal(true)}>Registrar</button>
          <button className="ca-link" onClick={pedir} disabled={enviando}>{enviando ? "Enviando…" : "Pedir por WhatsApp"}</button>
        </div>
      )}
      {modal && <NpsModal pacienteId={pacienteId} onClose={() => setModal(false)} onSaved={() => { setModal(false); cargar(); }} showToast={showToast} />}
    </FichaCard>
  );
}

function AntesDeIniciar({ p }) {
  const [tareas, setTareas] = useState([]);
  useEffect(() => { api.tareas(p.id).then(setTareas).catch(() => {}); }, [p.id]);
  const pendientes = tareas.filter((t) => t.estado !== "cumplida");
  const ultimaEvo = (p.historial || [])[0];
  const retomar = ultimaEvo ? [ultimaEvo.proximos_pasos, ultimaEvo.puntos_importantes].map((x) => (x || "").trim()).find(Boolean) : "";
  const items = [];
  items.push({ icon: Clock, l: "Última sesión", v: (p.ultima && p.ultima !== "—") ? p.ultima : "primera vez" });
  if (p.proxima) items.push({ icon: Calendar, l: "Próxima", v: `${p.proxima.fecha} · ${p.proxima.hora}` });
  if (retomar) items.push({ icon: FileText, l: "Para retomar", v: retomar });
  if (pendientes.length) items.push({ icon: Check, l: "Tarea pendiente", v: pendientes[0].texto + (pendientes.length > 1 ? ` (+${pendientes.length - 1})` : "") });
  if (p.objetivo_principal) items.push({ icon: Activity, l: "Objetivo", v: p.objetivo_principal });
  if (items.length <= 1 && !p.proxima && !retomar) return null;
  return (
    <div style={{ background: "var(--accent-soft)", border: "1px solid #BEE7EF", borderRadius: 12, padding: "12px 16px", marginBottom: 18 }}>
      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.4, textTransform: "uppercase", color: "var(--accent)", marginBottom: 8 }}>Antes de iniciar la sesión</div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "10px 22px" }}>
        {items.map((it, i) => (
          <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 7, maxWidth: 340 }}>
            <it.icon size={14} strokeWidth={2} style={{ color: "var(--accent)", marginTop: 2, flexShrink: 0 }} />
            <div>
              <div style={{ fontSize: 11, color: "var(--muted)" }}>{it.l}</div>
              <div style={{ fontSize: 13, fontWeight: 500 }}>{it.v}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

const BRUJULA_CAMPOS = [
  { k: "brujula_motivo", l: "Motivo de consulta" },
  { k: "brujula_hipotesis", l: "Hipótesis clínica" },
  { k: "brujula_objetivos", l: "Objetivos" },
  { k: "brujula_fortalezas", l: "Fortalezas" },
  { k: "brujula_factores_protectores", l: "Factores protectores" },
  { k: "brujula_factores_riesgo", l: "Factores de riesgo" },
  { k: "brujula_barreras", l: "Barreras" },
  { k: "brujula_plan", l: "Plan" },
];

function BrujulaClinica({ p, puede, onRefrescar, showToast }) {
  const [edit, setEdit] = useState(false);
  const [form, setForm] = useState({});
  const [guardando, setGuardando] = useState(false);
  const tieneAlgo = BRUJULA_CAMPOS.some((c) => (p[c.k] || "").trim());

  function abrir() {
    const f = {};
    BRUJULA_CAMPOS.forEach((c) => { f[c.k] = p[c.k] || ""; });
    setForm(f); setEdit(true);
  }
  async function guardar() {
    setGuardando(true);
    try {
      await api.actualizarPaciente(p.id, form);
      if (onRefrescar) await onRefrescar();
      setEdit(false);
      showToast && showToast("Brújula guardada ✓");
    } catch (e) { showToast && showToast("Error: " + e.message); }
    finally { setGuardando(false); }
  }

  return (
    <>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <h2 className="ca-secth" style={{ display: "inline-flex", alignItems: "center", gap: 7 }}><Compass size={16} strokeWidth={2} style={{ color: "var(--accent)" }} /> Brújula clínica</h2>
        {puede && !edit && <button className="ca-mini" onClick={abrir}><Pencil size={13} /> {tieneAlgo ? "Editar" : "Completar"}</button>}
      </div>
      <div className="ca-card" style={{ marginBottom: 26 }}>
        {edit ? (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 14 }}>
              {BRUJULA_CAMPOS.map((c) => (
                <div key={c.k}>
                  <div className="ca-label">{c.l}</div>
                  <textarea className="ca-input" style={{ minHeight: 60, resize: "vertical", lineHeight: 1.5 }} value={form[c.k]} onChange={(e) => setForm((o) => ({ ...o, [c.k]: e.target.value }))} />
                </div>
              ))}
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 14 }}>
              <button className="ca-btn ghost" onClick={() => setEdit(false)}>Cancelar</button>
              <button className="ca-btn" onClick={guardar} disabled={guardando}>{guardando ? "Guardando…" : "Guardar brújula"}</button>
            </div>
          </>
        ) : !tieneAlgo ? (
          <div style={{ color: "var(--muted)", fontSize: 13.5 }}>Sin completar. La brújula reúne en una hoja el motivo, la hipótesis, objetivos, fortalezas, factores y el plan del caso — para entrar preparado a la sesión.{puede ? " Usa «Completar»." : ""}</div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 16 }}>
            {BRUJULA_CAMPOS.filter((c) => (p[c.k] || "").trim()).map((c) => (
              <div key={c.k}>
                <div className="ca-antlabel" style={{ marginBottom: 3 }}>{c.l}</div>
                <div style={{ fontSize: 13.5, lineHeight: 1.55, whiteSpace: "pre-wrap" }}>{p[c.k]}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}

function LineaTiempoProceso({ p }) {
  const puntos = useMemo(() => {
    const hist = [...(p.historial || [])].reverse(); // de la más antigua a la más reciente
    return hist.map((h, i) => ({ n: i + 1, fecha: h.fecha }));
  }, [p.historial]);
  const total = p.sesiones_proceso || 0;
  if (puntos.length === 0) return null;
  const proyectada = total > puntos.length;
  return (
    <>
      <h2 className="ca-secth">Línea de tiempo del proceso</h2>
      <div className="ca-card" style={{ marginBottom: 26, overflowX: "auto" }}>
        <div style={{ display: "flex", alignItems: "flex-start", minWidth: "min-content", paddingTop: 2 }}>
          {puntos.map((pt, i) => {
            const actual = i === puntos.length - 1;
            return (
              <div key={i} style={{ display: "flex", alignItems: "flex-start" }}>
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: 88 }}>
                  <div style={{ width: 26, height: 26, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11.5, fontWeight: 700, background: actual ? "var(--accent)" : "#E3F0E8", color: actual ? "#fff" : "#2F6B4F" }}>
                    {actual ? pt.n : <Check size={13} strokeWidth={2.5} />}
                  </div>
                  <div style={{ fontSize: 11.5, fontWeight: 600, marginTop: 6, textAlign: "center" }}>{pt.n === 1 ? "Consulta" : `Sesión ${pt.n}`}</div>
                  <div style={{ fontSize: 11, color: "var(--muted)", textAlign: "center" }}>{pt.fecha}</div>
                </div>
                {(i < puntos.length - 1 || proyectada) && <div style={{ height: 2, width: 30, background: "var(--line)", marginTop: 12 }} />}
              </div>
            );
          })}
          {proyectada && (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: 88 }}>
              <div style={{ width: 26, height: 26, borderRadius: "50%", border: "2px dashed var(--line)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, color: "var(--muted)" }}>{total}</div>
              <div style={{ fontSize: 11.5, fontWeight: 600, marginTop: 6, color: "var(--muted)", textAlign: "center" }}>Sesión {total}</div>
              <div style={{ fontSize: 11, color: "var(--muted)" }}>(estimada)</div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

const RED_TIPOS = [
  { v: "psiquiatra", l: "Psiquiatra" }, { v: "nutricionista", l: "Nutricionista" },
  { v: "neurologo", l: "Neurólogo" }, { v: "medico", l: "Médico" },
  { v: "terapeuta", l: "Terapeuta" }, { v: "abogado", l: "Abogado" }, { v: "otro", l: "Otro" },
];

function RedProfesionalesPaciente({ pacienteId, puede, showToast }) {
  const [lista, setLista] = useState([]);
  const [form, setForm] = useState(null);
  const [cargando, setCargando] = useState(true);
  function cargar() { setCargando(true); api.redProfesionales(pacienteId).then(setLista).catch(() => {}).finally(() => setCargando(false)); }
  useEffect(() => { cargar(); }, [pacienteId]);
  async function agregar() {
    if (!form.nombre.trim()) return showToast && showToast("Escribe el nombre.");
    try { await api.crearRedProfesional({ paciente: pacienteId, ...form }); setForm(null); cargar(); }
    catch (e) { showToast && showToast("Error: " + e.message); }
  }
  async function borrar(c) {
    if (!window.confirm(`¿Quitar a ${c.nombre} de la red?`)) return;
    try { await api.borrarRedProfesional(c.id); cargar(); } catch (e) { showToast && showToast("Error: " + e.message); }
  }
  return (
    <>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <h2 className="ca-secth">Red de profesionales</h2>
        {puede && !form && <button className="ca-mini" onClick={() => setForm({ tipo: "psiquiatra", nombre: "", telefono: "", notas: "", tipo_otro: "" })}><Plus size={13} /> Agregar</button>}
      </div>
      <div className="ca-card" style={{ marginBottom: 26 }}>
        {lista.length === 0 && !form && <div style={{ color: "var(--muted)", fontSize: 13.5 }}>{cargando ? "Cargando…" : "Sin profesionales en la red del paciente (psiquiatra, nutricionista, etc.)."}</div>}
        {lista.map((c) => (
          <div key={c.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "9px 0", borderTop: "1px solid var(--line)" }}>
            <span style={{ fontSize: 11.5, fontWeight: 600, color: "var(--accent)", background: "var(--accent-soft)", padding: "2px 9px", borderRadius: 20, minWidth: 92, textAlign: "center", flexShrink: 0 }}>{c.tipo_display}</span>
            <span style={{ flex: 1, minWidth: 0, fontSize: 14, fontWeight: 500 }}>{c.nombre}{c.notas ? <span className="ca-pmeta"> · {c.notas}</span> : null}</span>
            {c.telefono && <span style={{ fontSize: 13, color: "var(--muted)", display: "inline-flex", alignItems: "center", gap: 5, flexShrink: 0 }}><Phone size={13} /> {c.telefono}</span>}
            {puede && <button onClick={() => borrar(c)} className="ca-iconbtn" title="Quitar" style={{ color: "#9C4646" }}><Trash2 size={14} /></button>}
          </div>
        ))}
        {form && (
          <div style={{ borderTop: lista.length ? "1px solid var(--line)" : "none", paddingTop: lista.length ? 12 : 0, marginTop: lista.length ? 4 : 0 }}>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 8 }}>
              <select className="ca-input" style={{ width: 150 }} value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value })}>
                {RED_TIPOS.map((t) => <option key={t.v} value={t.v}>{t.l}</option>)}
              </select>
              <input className="ca-input" style={{ flex: 2, minWidth: 160 }} value={form.nombre} onChange={(e) => setForm({ ...form, nombre: e.target.value })} placeholder="Nombre (Dr./Dra. …)" />
              <input className="ca-input" style={{ width: 150 }} value={form.telefono} onChange={(e) => setForm({ ...form, telefono: e.target.value })} placeholder="Teléfono" inputMode="tel" />
            </div>
            {form.tipo === "otro" && <input className="ca-input" style={{ marginBottom: 8 }} value={form.tipo_otro} onChange={(e) => setForm({ ...form, tipo_otro: e.target.value })} placeholder="Especialidad" />}
            <div style={{ display: "flex", gap: 8 }}>
              <input className="ca-input" style={{ flex: 1 }} value={form.notas} onChange={(e) => setForm({ ...form, notas: e.target.value })} placeholder="Notas (opcional)" />
              <button className="ca-btn ghost" onClick={() => setForm(null)}>Cancelar</button>
              <button className="ca-btn" onClick={agregar} disabled={!form.nombre.trim()}>Agregar</button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

function ObjetivoRow({ o, puede, onUpd, onDel }) {
  const [val, setVal] = useState(o.progreso);
  useEffect(() => { setVal(o.progreso); }, [o.progreso]);
  const logrado = o.estado === "logrado";
  const color = logrado ? "#2F6B4F" : (val >= 67 ? "#2F6B4F" : val >= 34 ? "#C9923A" : "#9C6B2E");
  return (
    <div style={{ padding: "10px 0", borderTop: "1px solid var(--line)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <button onClick={() => puede && onUpd(logrado ? { estado: "activo" } : { estado: "logrado", progreso: 100 })}
          title={logrado ? "Marcar en curso" : "Marcar logrado"}
          style={{ background: "none", border: "none", cursor: puede ? "pointer" : "default", padding: 0, color: logrado ? "#2F6B4F" : "var(--muted)", flexShrink: 0, display: "inline-flex" }}>
          {logrado ? <Check size={18} /> : <span style={{ display: "inline-block", width: 15, height: 15, borderRadius: "50%", border: "2px solid var(--line)" }} />}
        </button>
        <span style={{ flex: 1, fontSize: 14, fontWeight: 500, textDecoration: logrado ? "line-through" : "none", color: logrado ? "var(--muted)" : "var(--ink)" }}>{o.texto}</span>
        <span style={{ fontSize: 13, fontWeight: 600, color, width: 44, textAlign: "right" }}>{val}%</span>
        {puede && <button onClick={onDel} className="ca-iconbtn" title="Eliminar" style={{ color: "#9C4646" }}><Trash2 size={14} /></button>}
      </div>
      <div style={{ height: 7, borderRadius: 999, background: "var(--line)", overflow: "hidden", marginTop: 6 }}>
        <div style={{ width: `${val}%`, height: "100%", background: color, transition: "width .15s" }} />
      </div>
      {puede && !logrado && (
        <input type="range" min="0" max="100" step="5" value={val} onChange={(e) => setVal(Number(e.target.value))}
          onMouseUp={() => val !== o.progreso && onUpd({ progreso: val })} onTouchEnd={() => val !== o.progreso && onUpd({ progreso: val })}
          style={{ width: "100%", marginTop: 7, accentColor: color }} />
      )}
    </div>
  );
}

function ObjetivosPaciente({ pacienteId, puede, showToast }) {
  const [lista, setLista] = useState([]);
  const [nuevo, setNuevo] = useState("");
  const [cargando, setCargando] = useState(true);
  function cargar() { setCargando(true); api.objetivos(pacienteId).then(setLista).catch(() => {}).finally(() => setCargando(false)); }
  useEffect(() => { cargar(); }, [pacienteId]);
  async function actualizar(o, data) {
    try { const upd = await api.actualizarObjetivo(o.id, data); setLista((L) => L.map((x) => x.id === o.id ? upd : x)); }
    catch (e) { showToast && showToast("Error: " + e.message); cargar(); }
  }
  async function agregar() {
    const t = nuevo.trim(); if (!t) return;
    try { await api.crearObjetivo({ paciente: pacienteId, texto: t }); setNuevo(""); cargar(); }
    catch (e) { showToast && showToast("Error: " + e.message); }
  }
  async function borrar(o) {
    if (!window.confirm("¿Eliminar el objetivo?")) return;
    try { await api.borrarObjetivo(o.id); cargar(); } catch (e) { showToast && showToast("Error: " + e.message); }
  }
  return (
    <>
      <h2 className="ca-secth">Objetivos terapéuticos</h2>
      <div className="ca-card" style={{ marginBottom: 26 }}>
        {lista.length === 0 && <div style={{ color: "var(--muted)", fontSize: 13.5, marginBottom: puede ? 12 : 0 }}>{cargando ? "Cargando…" : "Sin objetivos definidos."}</div>}
        {lista.map((o) => <ObjetivoRow key={o.id} o={o} puede={puede} onUpd={(d) => actualizar(o, d)} onDel={() => borrar(o)} />)}
        {puede && (
          <div style={{ display: "flex", gap: 8, marginTop: lista.length ? 14 : 0 }}>
            <input className="ca-input" value={nuevo} onChange={(e) => setNuevo(e.target.value)} placeholder="Nuevo objetivo: p. ej. Regular ansiedad" onKeyDown={(e) => { if (e.key === "Enter") agregar(); }} />
            <button className="ca-btn" onClick={agregar} disabled={!nuevo.trim()}><Plus size={15} /> Agregar</button>
          </div>
        )}
      </div>
    </>
  );
}

const TAREA_EST = {
  pendiente: { l: "Pendiente", bg: "#EEEBE6", fg: "#8A8378" },
  parcial: { l: "Parcial", bg: "#FFF1DA", fg: "#9C6B2E" },
  cumplida: { l: "Cumplida", bg: "#E3F0E8", fg: "#2F6B4F" },
};
const TAREA_CICLO = { pendiente: "parcial", parcial: "cumplida", cumplida: "pendiente" };

function TareasPaciente({ pacienteId, puede, showToast }) {
  const [lista, setLista] = useState([]);
  const [nuevo, setNuevo] = useState("");
  const [fecha, setFecha] = useState("");
  const [cargando, setCargando] = useState(true);
  function cargar() { setCargando(true); api.tareas(pacienteId).then(setLista).catch(() => {}).finally(() => setCargando(false)); }
  useEffect(() => { cargar(); }, [pacienteId]);
  async function ciclar(t) {
    if (!puede) return;
    try { const u = await api.actualizarTarea(t.id, { estado: TAREA_CICLO[t.estado] || "pendiente" }); setLista((L) => L.map((x) => x.id === t.id ? u : x)); }
    catch (e) { showToast && showToast("Error: " + e.message); }
  }
  async function agregar() {
    const x = nuevo.trim(); if (!x) return;
    try { await api.crearTarea({ paciente: pacienteId, texto: x, fecha: fecha || null }); setNuevo(""); setFecha(""); cargar(); }
    catch (e) { showToast && showToast("Error: " + e.message); }
  }
  async function borrar(t) {
    if (!window.confirm("¿Eliminar la tarea?")) return;
    try { await api.borrarTarea(t.id); cargar(); } catch (e) { showToast && showToast("Error: " + e.message); }
  }
  return (
    <>
      <h2 className="ca-secth">Tareas</h2>
      <div className="ca-card" style={{ marginBottom: 26 }}>
        {lista.length === 0 && <div style={{ color: "var(--muted)", fontSize: 13.5, marginBottom: puede ? 12 : 0 }}>{cargando ? "Cargando…" : "Sin tareas asignadas."}</div>}
        {lista.map((t) => {
          const e = TAREA_EST[t.estado] || TAREA_EST.pendiente;
          return (
            <div key={t.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 0", borderTop: "1px solid var(--line)" }}>
              <button onClick={() => ciclar(t)} title={puede ? "Cambiar estado" : ""} style={{ background: "none", border: "none", cursor: puede ? "pointer" : "default", padding: 0, color: e.fg, flexShrink: 0, display: "inline-flex" }}>
                {t.estado === "cumplida" ? <Check size={18} /> : t.estado === "parcial" ? <Clock size={17} /> : <span style={{ display: "inline-block", width: 15, height: 15, borderRadius: "50%", border: "2px solid var(--line)" }} />}
              </button>
              <span style={{ flex: 1, fontSize: 14, textDecoration: t.estado === "cumplida" ? "line-through" : "none", color: t.estado === "cumplida" ? "var(--muted)" : "var(--ink)" }}>{t.texto}</span>
              {t.fecha && <span className="ca-pmeta">{labelNumMes(t.fecha)}</span>}
              <span style={{ background: e.bg, color: e.fg, fontSize: 11.5, fontWeight: 600, padding: "2px 9px", borderRadius: 20 }}>{e.l}</span>
              {puede && <button onClick={() => borrar(t)} className="ca-iconbtn" title="Eliminar" style={{ color: "#9C4646" }}><Trash2 size={14} /></button>}
            </div>
          );
        })}
        {puede && (
          <div style={{ display: "flex", gap: 8, marginTop: lista.length ? 14 : 0, flexWrap: "wrap" }}>
            <input className="ca-input" style={{ flex: 2, minWidth: 180 }} value={nuevo} onChange={(e) => setNuevo(e.target.value)} placeholder="Nueva tarea: p. ej. Registro de emociones diario" onKeyDown={(e) => { if (e.key === "Enter") agregar(); }} />
            <input className="ca-input" style={{ width: 150 }} type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} title="Fecha objetivo (opcional)" />
            <button className="ca-btn" onClick={agregar} disabled={!nuevo.trim()}><Plus size={15} /> Agregar</button>
          </div>
        )}
      </div>
    </>
  );
}

const LBL_CONSENT = { consentimiento: "Consentimiento informado", politicas: "Políticas de atención" };

function ConsentimientoPaciente({ pacienteId, showToast }) {
  const [docs, setDocs] = useState(null);
  const [marcando, setMarcando] = useState(0);
  function cargar() { api.consentimientos(pacienteId).then(setDocs).catch(() => setDocs([])); }
  useEffect(() => { cargar(); }, [pacienteId]);

  // El paciente dio su OK por WhatsApp: se registra la aceptación (queda quién y cuándo).
  async function marcarAceptado(d) {
    const que = LBL_CONSENT[d.tipo] || d.tipo_label;
    if (!window.confirm(`¿El paciente ya dio su OK de estar de acuerdo? (${que})\n\nQuedará como aceptado, con la fecha de hoy y tu nombre como quien lo registró.`)) return;
    setMarcando(d.id);
    try {
      await api.marcarConsentimientoAceptado(d.id, "whatsapp");
      cargar();
      showToast && showToast("Aceptación registrada ✓");
    } catch (e) { showToast && showToast("Error: " + e.message); }
    finally { setMarcando(0); }
  }

  if (!docs || docs.length === 0) return null;
  // Un solo estado por tipo: si el paciente ya aceptó, ese es el estado (un reenvío
  // posterior no lo vuelve "pendiente de firma").
  const porTipo = [];
  for (const d of docs) {
    const i = porTipo.findIndex((x) => x.tipo === d.tipo);
    if (i < 0) porTipo.push(d);
    else if (d.aceptado && !porTipo[i].aceptado) porTipo[i] = d;
  }
  return (
    <>
      <h2 className="ca-secth">Consentimiento y políticas</h2>
      <div className="ca-card" style={{ marginBottom: 26 }}>
        {porTipo.map((d) => (
          <div key={d.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 0", borderTop: "1px solid var(--line)", fontSize: 13.5, flexWrap: "wrap" }}>
            <span style={{ flex: 1, minWidth: 150 }}>{LBL_CONSENT[d.tipo] || d.tipo_label}</span>
            {d.aceptado ? (
              <span style={{ color: "#2F6B4F", fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 5, flexWrap: "wrap", justifyContent: "flex-end" }}>
                <Check size={14} strokeWidth={2.5} /> Aceptado{d.aceptado_fecha ? ` · ${d.aceptado_fecha}` : ""}{d.firmante_nombre ? ` · ${d.firmante_nombre}` : ""}
                {d.aceptado_via && d.aceptado_via !== "enlace" && (
                  <span style={{ color: "var(--muted)", fontWeight: 400 }}>
                    ({d.aceptado_via_label}{d.registrado_por_nombre ? ` · registró ${d.registrado_por_nombre}` : ""})
                  </span>
                )}
              </span>
            ) : (
              <>
                <span style={{ color: "#9C6B2E", fontWeight: 600 }}>Enviado · pendiente de firma</span>
                <button className="ca-mini" onClick={() => marcarAceptado(d)} disabled={marcando === d.id}
                  title="El paciente respondió que está de acuerdo por WhatsApp">
                  <Check size={13} strokeWidth={2.2} /> {marcando === d.id ? "Registrando…" : "Dio su OK"}
                </button>
              </>
            )}
          </div>
        ))}
      </div>
    </>
  );
}

function FichaCard({ label, children, style }) {
  return (
    <div className="ca-card" style={{ margin: 0, ...style }}>
      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.4, textTransform: "uppercase", color: "var(--muted)", marginBottom: 8 }}>{label}</div>
      {children}
    </div>
  );
}

function Ficha({ p, onBack, onEdit, onWhatsApp, onSubirAdjunto, onEliminarAdjunto, puedeEliminar, clinica, onAgendar, onRegistrarSesion, puedeRegistrar, onVenderPaquete, puedeVenderPaquete, onRegistrarPago, puedeCobrar, esMedico, showToast, onRefrescar }) {
  const alertas = (p.alertas || "").split(",").map((s) => s.trim()).filter(Boolean);
  const ultimaEvo = (p.historial || [])[0];
  return (
    <div>
      <button className="ca-back" onClick={onBack}><ChevronLeft size={16} strokeWidth={2} /> Pacientes</button>

      {/* Encabezado */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 16, marginBottom: 18, flexWrap: "wrap" }}>
        <div className="ca-avatar" style={{ width: 52, height: 52, fontSize: 18, borderRadius: 13 }}>{iniciales(p.nombre)}</div>
        <div style={{ flex: 1, minWidth: 220 }}>
          <h1 className="ca-h1" style={{ fontSize: 22 }}>{p.nombre}</h1>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4, flexWrap: "wrap" }}>
            {p.codigo && <span className="ca-pmeta">ID: {p.codigo}</span>}
            <SpecialtyTag name={p.especialidad} />
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
            <span className="ca-field"><Cake size={14} strokeWidth={1.9} style={{ color: "var(--muted)" }} /> {p.edad != null ? `${p.edad} años` : "Edad —"}{p.genero_label ? ` · ${p.genero_label}` : ""}</span>
            {p.sede_label && <span className="ca-field"><MapPin size={14} strokeWidth={1.9} style={{ color: "var(--muted)" }} /> Sede {p.sede_label}</span>}
            {p.profesional_nombre && <span className="ca-field"><HeartPulse size={14} strokeWidth={1.9} style={{ color: "var(--accent)" }} /> {p.profesional_nombre}</span>}
            {(p.frecuencia_label || p.modalidad_label) && <span className="ca-field"><Clock size={14} strokeWidth={1.9} style={{ color: "var(--muted)" }} /> {[p.frecuencia_label, p.modalidad_label].filter(Boolean).join(" · ")}</span>}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {/* El psicólogo solo edita la ficha/historia: sin registrar sesión, agendar, WhatsApp ni imprimir. */}
          {puedeRegistrar && !esMedico && <button className="ca-mini" onClick={onRegistrarSesion}><Activity size={13} strokeWidth={2} /> Registrar sesión</button>}
          {!esMedico && <button className="ca-mini" onClick={onAgendar}><Calendar size={13} strokeWidth={2} /> Agendar</button>}
          {!esMedico && <button className="ca-mini wa" onClick={onWhatsApp}><MessageCircle size={13} strokeWidth={2} /> WhatsApp</button>}
          {!esMedico && <button className="ca-mini" onClick={() => imprimirHistoria(p, clinica)}><FileText size={13} strokeWidth={2} /> Imprimir</button>}
          <button className="ca-mini" onClick={onEdit}><Pencil size={13} strokeWidth={2} /> Editar</button>
        </div>
      </div>

      <AntesDeIniciar p={p} />

      {/* Tarjetas principales (Centro de trabajo del terapeuta) */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 14, marginBottom: 16 }}>
        <FichaCard label="Estado del proceso">
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 6 }}>
            <span style={{ background: p.frecuencia === "alta" ? "#EEEBE6" : "#E3F0E8", color: p.frecuencia === "alta" ? "#8A8378" : "#2F6B4F", fontSize: 12, fontWeight: 600, padding: "2px 10px", borderRadius: 20 }}>
              {p.frecuencia === "alta" ? "Alta" : p.frecuencia === "en_pausa" ? "En pausa" : "En proceso"}
            </span>
            <span style={{ fontWeight: 600 }}>{p.proceso === "consulta" ? "Consulta inicial" : `Sesión ${p.n_sesion || 0}${p.sesiones_proceso ? ` de ${p.sesiones_proceso}` : ""}`}</span>
          </div>
          <div className="ca-pmeta">{[p.proceso_label && p.proceso !== "consulta" ? p.proceso_label : "", p.frecuencia_label].filter(Boolean).join(" · ") || "Frecuencia —"}</div>
          <div className="ca-pmeta" style={{ marginTop: 4 }}>Última sesión: {p.ultima}</div>
          <div className="ca-pmeta" style={{ color: p.proxima ? "var(--accent)" : "var(--muted)" }}>Próxima: {p.proxima ? `${p.proxima.fecha} · ${p.proxima.hora}` : "sin agendar"}</div>
        </FichaCard>
        <FichaCard label="Objetivo terapéutico principal">
          {p.objetivo_principal ? <div style={{ fontSize: 14.5, fontWeight: 500, lineHeight: 1.4 }}>{p.objetivo_principal}</div>
            : <div style={{ color: "var(--muted)", fontSize: 13.5 }}>Sin definir · edítalo en «Editar».</div>}
        </FichaCard>
        <FichaCard label="Riesgo actual">
          {(() => {
            const R = { bajo: ["#E3F0E8", "#2F6B4F", "Bajo"], moderado: ["#FFF1DA", "#9C6B2E", "Moderado"], alto: ["#F7E1E1", "#9C4646", "Alto"] };
            const r = R[p.riesgo];
            return r ? <span style={{ background: r[0], color: r[1], fontSize: 14, fontWeight: 600, padding: "5px 14px", borderRadius: 20 }}>{r[2]}</span>
              : <span style={{ color: "var(--muted)", fontSize: 13.5 }}>Sin evaluar</span>;
          })()}
        </FichaCard>
        {/* El psicólogo VE el NPS (satisfacción de sus pacientes) pero no lo registra ni lo pide. */}
        <NpsPaciente pacienteId={p.id} puede={!esMedico && (puedeRegistrar || puedeCobrar)} showToast={showToast} />
      </div>

      {/* Alertas clínicas */}
      {alertas.length > 0 && (
        <div className="ca-card" style={{ marginBottom: 16, display: "flex", alignItems: "center", gap: 9, flexWrap: "wrap" }}>
          <span style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.4, color: "#9C6B2E", display: "inline-flex", alignItems: "center", gap: 5 }}><AlertTriangle size={14} strokeWidth={2} /> Alertas clínicas</span>
          {alertas.map((a, i) => <span key={i} style={{ background: "#FFF1DA", color: "#9C6B2E", fontSize: 12.5, fontWeight: 500, padding: "3px 11px", borderRadius: 20 }}>{a}</span>)}
        </div>
      )}

      {/* Resumen clínico + última evolución */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 16, marginBottom: 20 }}>
        <FichaCard label="Resumen clínico">
          {p.resumen_clinico ? <div style={{ fontSize: 13.5, lineHeight: 1.6, whiteSpace: "pre-wrap" }}>{p.resumen_clinico}</div>
            : <div style={{ color: "var(--muted)", fontSize: 13.5 }}>Sin resumen. Escríbelo en «Editar» para ver el caso de un vistazo, sin leer todas las evoluciones.</div>}
        </FichaCard>
        <FichaCard label="Última evolución">
          {!ultimaEvo ? <div style={{ color: "var(--muted)", fontSize: 13.5 }}>Aún no hay evoluciones registradas.</div> : (() => {
            const snip = [ultimaEvo.nota, ultimaEvo.puntos_importantes, ultimaEvo.motivo, ultimaEvo.proximos_pasos, ultimaEvo.diagnostico].map((x) => (x || "").trim()).find(Boolean) || "—";
            return (
              <>
                <div className="ca-pmeta" style={{ marginBottom: 6 }}>{ultimaEvo.fecha}{ultimaEvo.medico ? ` · ${ultimaEvo.medico}` : ""}</div>
                <div style={{ fontSize: 13.5, lineHeight: 1.55, display: "-webkit-box", WebkitLineClamp: 5, WebkitBoxOrient: "vertical", overflow: "hidden" }}>{snip}</div>
                <button className="ca-link" onClick={() => document.getElementById("hc-historia")?.scrollIntoView({ behavior: "smooth", block: "start" })} style={{ marginTop: 8 }}>Ver evolución completa</button>
              </>
            );
          })()}
        </FichaCard>
      </div>

      {(!esMedico && (p.numero_documento || p.tel || p.direccion || p.tutor_nombre)) && (
        <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginBottom: 22 }}>
          {p.numero_documento && <div className="ca-field"><FileText size={15} strokeWidth={1.9} style={{ color: "var(--muted)" }} /> {p.tipo_documento_label} {p.numero_documento}</div>}
          {p.tel && <div className="ca-field"><Phone size={15} strokeWidth={1.9} style={{ color: "var(--muted)" }} /> {p.tel}</div>}
          {p.direccion && <div className="ca-field"><MapPin size={15} strokeWidth={1.9} style={{ color: "var(--muted)" }} /> {p.direccion}</div>}
          {p.tutor_nombre && <div className="ca-field"><Users size={15} strokeWidth={1.9} style={{ color: "var(--muted)" }} /> Tutor: {p.tutor_nombre}{p.tutor_parentesco ? ` (${p.tutor_parentesco})` : ""}{p.tutor_telefono ? ` · ${p.tutor_telefono}` : ""}</div>}
        </div>
      )}

      <BrujulaClinica p={p} puede={puedeRegistrar} onRefrescar={onRefrescar} showToast={showToast} />

      <LineaTiempoProceso p={p} />

      <ObjetivosPaciente pacienteId={p.id} puede={puedeRegistrar} showToast={showToast} />

      <TareasPaciente pacienteId={p.id} puede={puedeRegistrar} showToast={showToast} />

      <EscalasPaciente pacienteId={p.id} puede={puedeRegistrar} showToast={showToast} />

      {p.seguimiento && p.seguimiento.length > 0 && (
        <>
          <h2 className="ca-secth">Evolución de sesiones</h2>
          <div className="ca-card" style={{ marginBottom: 26 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 22, flexWrap: "wrap" }}>
              <div>
                <div className="ca-antlabel"><Activity size={14} strokeWidth={2} style={{ color: "var(--muted)" }} /> Sesión actual</div>
                <div style={{ fontSize: 20, fontWeight: 600, marginTop: 4 }}>
                  {p.proceso === "consulta" ? "Consulta inicial" : `Sesión ${p.n_sesion}`}
                  {p.proceso_label && p.proceso !== "consulta" ? <span style={{ fontSize: 12, color: "var(--muted)", fontWeight: 400 }}> · {p.proceso_label}</span> : null}
                </div>
              </div>
              {p.seguimiento.length >= 2 && <Sparkline valores={p.seguimiento.map((s) => s.n_sesion)} color="var(--accent)" />}
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 14 }}>
              {p.seguimiento.map((s, i) => (
                <div key={i} style={{ background: "var(--accent-soft)", borderRadius: 8, padding: "5px 10px", fontSize: 12.5 }}>
                  <span style={{ color: "var(--muted)" }}>{s.etiqueta}:</span> <b>{s.proceso === "consulta" ? "Consulta" : `Ses. ${s.n_sesion}`}</b>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      <h2 className="ca-secth">Antecedentes relevantes</h2>
      <div className="ca-card" style={{ marginBottom: 26 }}>
        <div className="ca-anteced">
          <AntItem icon={HeartPulse} label="Médicos" valor={p.antecedentes_medicos} />
          <AntItem icon={Activity} label="Psicológicos" valor={p.antecedentes} />
          <AntItem icon={Users} label="Familiares" valor={p.antecedentes_familiares} />
          <AntItem icon={FileText} label="Otros" valor={p.antecedentes_otros} />
          <AntItem icon={AlertTriangle} label="Alergias" valor={p.alergias} alerta />
          <AntItem icon={Pill} label="Medicación habitual" valor={p.medicacion_habitual} />
        </div>
        <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 14 }}>Edita los antecedentes desde «Editar».</div>
      </div>

      <h2 className="ca-secth">Notas internas <span style={{ fontSize: 12.5, fontWeight: 400, color: "var(--muted)" }}>(solo equipo · no es historia clínica)</span></h2>
      <div className="ca-card" style={{ marginBottom: 26 }}>
        {p.notas_internas ? <div style={{ fontSize: 13.5, lineHeight: 1.6, whiteSpace: "pre-wrap" }}>{p.notas_internas}</div>
          : <div style={{ color: "var(--muted)", fontSize: 13.5 }}>Sin notas. Aquí van preferencias del paciente o avisos del equipo (ej: «prefiere recordatorios por WhatsApp»). Se edita en «Editar».</div>}
      </div>

      <RedProfesionalesPaciente pacienteId={p.id} puede={puedeRegistrar} showToast={showToast} />

      <ConsentimientoPaciente pacienteId={p.id} showToast={showToast} />

      {/* Pagos y estado de cuenta: NO para el psicólogo. */}
      {!esMedico && (p.cuenta || puedeCobrar) && (
        <>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <h2 className="ca-secth">Pagos y estado de cuenta</h2>
            {puedeCobrar && (
              <button className="ca-mini" onClick={onRegistrarPago}><Receipt size={13} strokeWidth={2} /> Registrar pago</button>
            )}
          </div>
          <div className="ca-card" style={{ marginBottom: 26 }}>
            <div style={{ display: "flex", gap: 28, flexWrap: "wrap", marginBottom: (p.cuenta && p.cuenta.items.length) ? 12 : 0 }}>
              <div><div style={{ fontSize: 20, fontWeight: 600, color: "#4F8A77" }}>{money(p.cuenta ? p.cuenta.cobrado : 0)}</div><div className="ca-pmeta">Pagado</div></div>
              <div><div style={{ fontSize: 20, fontWeight: 600, color: (p.cuenta && p.cuenta.pendiente > 0) ? "#C9923A" : "var(--muted)" }}>{money(p.cuenta ? p.cuenta.pendiente : 0)}</div><div className="ca-pmeta">Pendiente</div></div>
            </div>
            {(!p.cuenta || p.cuenta.items.length === 0) ? (
              <div style={{ color: "var(--muted)", fontSize: 13.5 }}>Sin pagos registrados todavía.{puedeCobrar ? " Usa «Registrar pago» para agregar uno." : ""}</div>
            ) : p.cuenta.items.map((c) => (
              <div key={c.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 0", borderTop: "1px solid var(--line)", fontSize: 13.5 }}>
                <span style={{ color: "var(--muted)", width: 86, flexShrink: 0 }}>{c.fecha}</span>
                <span style={{ flex: 1, minWidth: 0 }}>{c.concepto}{c.comprobante ? <span style={{ color: "var(--muted)", fontSize: 12 }}> · {c.comprobante}{c.comprobante_numero ? ` ${c.comprobante_numero}` : ""}</span> : null}
                  {puedeCobrar && (
                    <button className="ca-iconbtn" title="Editar la descripción de este pago" style={{ padding: 2, marginLeft: 6, verticalAlign: "middle" }}
                      onClick={async () => {
                        const nuevo = window.prompt("Descripción del pago:", c.concepto);
                        if (nuevo == null || nuevo.trim() === (c.concepto || "")) return;
                        try { await api.actualizarCobro(c.id, { concepto: nuevo.trim() }); onRefrescar && onRefrescar(); showToast && showToast("Descripción actualizada ✓"); }
                        catch (e) { showToast && showToast("Error: " + e.message); }
                      }}><Pencil size={12} strokeWidth={2} /></button>
                  )}
                </span>
                <span style={{ fontVariantNumeric: "tabular-nums", fontWeight: 500 }}>{money(c.monto)}</span>
                <Tag colors={ESTADO_COBRO_COLOR[c.estado]}>{c.estado === "pagado" ? (c.medio || "Pagado") : "Pendiente"}</Tag>
                {puedeCobrar && (
                  <button className="ca-iconbtn" title="Eliminar este pago (se avisa a gerencia)" style={{ padding: 2, color: "#9C4646" }}
                    onClick={async () => {
                      if (!window.confirm(`¿Eliminar el pago "${c.concepto}" de ${money(c.monto)}? Se avisa a gerencia.`)) return;
                      try { await api.borrarCobro(c.id); onRefrescar && onRefrescar(); showToast && showToast("Pago eliminado"); }
                      catch (e) { showToast && showToast("Error: " + e.message); }
                    }}><Trash2 size={13} strokeWidth={2} /></button>
                )}
              </div>
            ))}
          </div>
        </>
      )}

      {(puedeVenderPaquete || (p.paquetes && p.paquetes.length > 0)) && (
        <>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <h2 className="ca-secth">Paquetes de sesiones</h2>
            {puedeVenderPaquete && (
              <button className="ca-mini" onClick={onVenderPaquete}><Plus size={13} strokeWidth={2.2} /> Vender paquete</button>
            )}
          </div>
          <div className="ca-card" style={{ marginBottom: 26 }}>
            {(!p.paquetes || p.paquetes.length === 0) ? (
              <div style={{ color: "var(--muted)", fontSize: 13.5 }}>Sin paquetes. Las sesiones prepagadas se descuentan solas al atender.</div>
            ) : (
              p.paquetes.map((pq) => {
                const pct = pq.total ? Math.round((pq.usadas / pq.total) * 100) : 0;
                const agotado = pq.estado !== "activo";
                return (
                  <div key={pq.id} style={{ padding: "10px 0", borderTop: "1px solid var(--line)" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
                      <span style={{ flex: 1, fontWeight: 500, fontSize: 14, opacity: agotado ? 0.6 : 1 }}>{pq.nombre}</span>
                      <span style={{ fontSize: 13, fontWeight: 600, color: pq.restantes > 0 ? "#4F8A77" : "#B4564E" }}>
                        {pq.usadas}/{pq.total} usadas · quedan {pq.restantes}
                      </span>
                      {pq.estado !== "activo" && <Tag colors={pq.estado === "agotado" ? STATUS.atendida : STATUS.cancelada}>{pq.estado === "agotado" ? "Agotado" : "Anulado"}</Tag>}
                    </div>
                    <div style={{ height: 7, borderRadius: 999, background: "var(--line)", overflow: "hidden" }}>
                      <div style={{ width: `${pct}%`, height: "100%", background: pq.restantes > 0 ? "#4F8A77" : "#C9923A" }} />
                    </div>
                    <div className="ca-pmeta" style={{ marginTop: 5 }}>{pq.fecha} · {money(pq.monto)}</div>
                  </div>
                );
              })
            )}
          </div>
        </>
      )}

      {p.citas && p.citas.length > 0 && (
        <>
          <h2 className="ca-secth">Historial de citas</h2>
          <div className="ca-card" style={{ marginBottom: 26, padding: 0, overflow: "hidden" }}>
            {p.citas.map((c) => (
              <div key={c.id} style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "9px 14px", borderTop: "1px solid var(--line)", fontSize: 13.5 }}>
                <span style={{ color: "var(--muted)", width: 96, flexShrink: 0 }}>{c.fecha}</span>
                <span style={{ width: 44, flexShrink: 0, color: "var(--muted)" }}>{c.hora}</span>
                <span style={{ flex: 1, minWidth: 0 }}>{c.especialidad || "—"}{c.medico ? <span style={{ color: "var(--muted)" }}> · {c.medico}</span> : null}{c.motivo_consulta ? <div className="ca-pmeta" style={{ whiteSpace: "pre-wrap" }}><b>Motivo:</b> {c.motivo_consulta}</div> : null}{c.notas ? <div className="ca-pmeta" style={{ whiteSpace: "pre-wrap" }}>{c.notas}</div> : null}</span>
                <Tag colors={STATUS[c.estado] || { bg: "#EEEBE6", fg: "#7C7870" }}>{c.estado_label}</Tag>
              </div>
            ))}
          </div>
        </>
      )}

      <h2 className="ca-secth" id="hc-historia">Historia clínica</h2>
      <div className="ca-card">
        {p.historial === undefined ? (
          <div style={{ color: "var(--muted)", fontSize: 14 }}>Cargando historia clínica…</div>
        ) : p.historial.length === 0 ? (
          <div style={{ color: "var(--muted)", fontSize: 14 }}>Aún no hay atenciones registradas. Aparecerán aquí después de la primera consulta.</div>
        ) : (
          <div className="ca-hist">
            {p.historial.map((h, i) => {
              const ficha = FICHAS[h.tipo] || FICHAS.evolucion;
              const mostrados = new Set();
              const filas = [];
              ficha.forEach((c) => {
                const val = (h[c.k] || "").trim();
                if (val) { filas.push([c.l, val]); mostrados.add(c.k); }
              });
              // Campos con contenido que no pertenecen al tipo (datos antiguos): se muestran igual.
              TODOS_CAMPOS_HC.forEach((k) => {
                if (!mostrados.has(k) && (h[k] || "").trim()) filas.push([CAMPO_LABEL[k], h[k].trim()]);
              });
              const tipoLabel = (TIPOS_HC.find((t) => t.v === h.tipo) || {}).l || "";
              return (
              <div key={h.id ?? i} className={`ca-histitem ${h.fecha === HOY_FECHA && i === 0 ? "nuevo" : ""}`}>
                <div style={{ fontSize: 12.5, color: "var(--muted)", marginBottom: 6, display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                  {tipoLabel && <span style={{ fontSize: 10.5, background: "var(--accent-soft)", color: "var(--accent)", padding: "1px 8px", borderRadius: 999, fontWeight: 600 }}>{tipoLabel}</span>}
                  <span>{h.fecha} · {h.medico || "—"}{h.especialidad ? ` · ${h.especialidad}` : ""}</span>
                </div>
                {vitalesDe(h).length > 0 && (
                  <div className="ca-vitales">
                    {vitalesDe(h).map(([k, val]) => <span key={k} className="ca-vital"><b>{k}</b> {val}</span>)}
                  </div>
                )}
                {filas.map(([etq, val], idx) => <Campo key={idx} etiqueta={etq}>{val}</Campo>)}
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
              );
            })}
          </div>
        )}
      </div>

      <h2 className="ca-secth" style={{ marginTop: 28 }}>Archivos adjuntos</h2>
      <div className="ca-card">
        <UploaderAdjunto onSubir={onSubirAdjunto} />
        <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 9 }}>Laboratorios, ecografías, PDFs o imágenes. Máx. 25 MB. Descarga protegida (solo personal de la clínica).</div>
        {p.adjuntos === undefined ? (
          <div style={{ color: "var(--muted)", fontSize: 14, marginTop: 14 }}>Cargando archivos…</div>
        ) : p.adjuntos.length === 0 ? (
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
  const [nuevoTel, setNuevoTel] = useState("");
  const [fecha, setFecha] = useState(fechaInicial || HOY_ISO);
  const [hora, setHora] = useState("");
  const [esp, setEsp] = useState(pacienteFijo?.especialidad || "");
  const [categoria, setCategoria] = useState("");
  const [servicios, setServicios] = useState([]);
  const [medicos, setMedicos] = useState([]);
  const [medicoId, setMedicoId] = useState("");
  const [sede, setSede] = useState(pacienteFijo?.sede || "");
  const [modalidad, setModalidad] = useState("presencial");
  const [enlace, setEnlace] = useState("");
  const [notas, setNotas] = useState("");
  const [motivoConsulta, setMotivoConsulta] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [nSesion, setNSesion] = useState(
    pacienteFijo?.n_sesion != null ? String(pacienteFijo.n_sesion + 1) : ""
  );

  useEffect(() => { api.medicos().then(setMedicos).catch(() => {}); }, []);
  useEffect(() => { api.servicios().then((s) => setServicios((s || []).filter((x) => x.activo !== false))).catch(() => {}); }, []);

  // Solo psicólogos de la sede elegida (si hay sede); si no, todos los activos.
  const medicosVisibles = medicos.filter((m) => !sede || !m.sede || m.sede === sede);
  // Servicios del catálogo (Precios). Si la categoría elegida coincide con la
  // "especialidad" de algún servicio, se filtra por ella; si no, se muestran todos.
  const serviciosCat = useMemo(() => {
    if (!categoria) return servicios;
    const f = servicios.filter((s) => (s.especialidad || "").toLowerCase() === categoria.toLowerCase());
    return f.length ? f : servicios;
  }, [servicios, categoria]);

  const matches = useMemo(
    () => (busca.trim() ? pacientes.filter((p) => p.nombre.toLowerCase().includes(busca.toLowerCase())).slice(0, 4) : []),
    [busca, pacientes]
  );

  function elegir(p) {
    setSel(p); setNuevo(false); setEsp(p.especialidad || "");
    if (p.sede) setSede(p.sede);
    if (p.n_sesion != null) setNSesion(String(p.n_sesion + 1));
    setBusca("");
  }
  function elegirNuevo() { setNuevo(true); setSel(null); }
  function limpiar() { setSel(null); setNuevo(false); setBusca(""); }

  async function guardar() {
    if (enviando) return;
    if (!sel && !(nuevo && busca.trim())) {
      setError("Selecciona un paciente: búscalo y haz clic en su nombre, o usa «Crear paciente nuevo».");
      return;
    }
    if (!fecha) { setError("Falta la fecha."); return; }
    if (!hora.trim()) { setError("Falta la hora."); return; }
    setError("");
    const extra = {
      especialidad: esp, categoria, fecha, hora, medicoId: medicoId || null, sede,
      modalidad, enlace: modalidad === "virtual" ? enlace.trim() : "",
      notas: notas.trim(), motivo_consulta: motivoConsulta.trim(), n_sesion: nSesion ? Number(nSesion) : null,
    };
    setEnviando(true);
    try {
      if (sel) await onSave({ pacienteId: sel.id, paciente: sel.nombre, ...extra });
      else if (nuevo) await onSave({ nuevoNombre: busca.trim(), nuevoTel: nuevoTel.trim(), ...extra });
    } finally { setEnviando(false); }
  }

  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 430 }} onClick={(e) => e.stopPropagation()}>
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

        {nuevo && (
          <div style={{ marginBottom: 13 }}>
            <div className="ca-label">Teléfono del paciente nuevo <span style={{ color: "var(--muted)", fontWeight: 400 }}>(opcional)</span></div>
            <input className="ca-input" value={nuevoTel} onChange={(e) => setNuevoTel(e.target.value)} placeholder="987 654 321" inputMode="tel" />
            <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 6 }}>Se crea la ficha con nombre, teléfono, sede y especialidad. Lo demás se completa luego desde Pacientes.</div>
          </div>
        )}

        <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
          <div style={{ flex: 1.3 }}>
            <div className="ca-label">Fecha</div>
            <input className="ca-input" type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
          </div>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Hora</div>
            <input className="ca-input" type="time" step={900} value={hora} onChange={(e) => setHora(e.target.value)} placeholder="14:30" />
          </div>
        </div>
        <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Categoría</div>
            <select className="ca-input" value={categoria} onChange={(e) => setCategoria(e.target.value)}>
              <option value="">— Elegir —</option>
              <option value="general">General</option>
              <option value="adultos">Adultos</option>
              <option value="infantojuvenil">Infantojuvenil</option>
              <option value="parejas">Parejas</option>
              <option value="constancias">Constancias e informes</option>
            </select>
          </div>
          <div style={{ flex: 1.3 }}>
            <div className="ca-label">Servicio <span style={{ color: "var(--muted)", fontWeight: 400 }}>(de Precios)</span></div>
            <select className="ca-input" value={esp} onChange={(e) => setEsp(e.target.value)}>
              <option value="">— Elegir —</option>
              {serviciosCat.map((s) => <option key={s.id} value={s.nombre}>{s.nombre}</option>)}
            </select>
          </div>
        </div>

        <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
          <div style={{ flex: 1.5 }}>
            <div className="ca-label">Psicólogo</div>
            <select className="ca-input" value={medicoId} onChange={(e) => setMedicoId(e.target.value)}>
              <option value="">— Sin asignar —</option>
              {medicosVisibles.map((m) => <option key={m.id} value={m.id}>{m.nombre}</option>)}
            </select>
          </div>
          <div style={{ width: 92 }}>
            <div className="ca-label">N° sesión</div>
            <input className="ca-input" value={nSesion} onChange={(e) => setNSesion(e.target.value.replace(/[^0-9]/g, ""))} inputMode="numeric" placeholder="1" />
          </div>
        </div>

        <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Sede</div>
            <select className="ca-input" value={sede} onChange={(e) => {
              const s = e.target.value; setSede(s);
              // Si el psicólogo elegido no es de la nueva sede, se limpia.
              if (medicoId && !medicos.some((m) => String(m.id) === String(medicoId) && (!s || !m.sede || m.sede === s))) setMedicoId("");
            }}>
              <option value="">— Sin sede —</option>
              <option value="lima">Lima</option>
              <option value="piura">Piura</option>
            </select>
          </div>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Modalidad</div>
            <div style={{ display: "flex", gap: 6 }}>
              {[["presencial", "Presencial"], ["virtual", "Virtual"]].map(([v, l]) => (
                <button key={v} type="button" onClick={() => setModalidad(v)}
                  className="ca-input" style={{
                    flex: 1, cursor: "pointer", fontWeight: modalidad === v ? 600 : 400,
                    color: modalidad === v ? "#fff" : "var(--ink)",
                    background: modalidad === v ? "var(--accent)" : "var(--bg)",
                    borderColor: modalidad === v ? "var(--accent)" : "var(--line)",
                  }}>{l}</button>
              ))}
            </div>
          </div>
        </div>

        {modalidad === "virtual" && (
          <div style={{ marginBottom: 13 }}>
            <div className="ca-label">Enlace de la videollamada</div>
            <input className="ca-input" value={enlace} onChange={(e) => setEnlace(e.target.value)} placeholder="https://meet.google.com/…" />
          </div>
        )}

        <div style={{ marginBottom: 13 }}>
          <div className="ca-label">Motivo indicado por el consultante <span style={{ color: "var(--muted)", fontWeight: 400 }}>(lo que contó al agendar)</span></div>
          <textarea className="ca-input" style={{ minHeight: 52, resize: "vertical", lineHeight: 1.5 }} value={motivoConsulta} onChange={(e) => setMotivoConsulta(e.target.value)} placeholder="Ej: ansiedad, problemas de pareja… — para que el psicólogo llegue sabiendo con qué viene" />
        </div>
        <div style={{ marginBottom: 20 }}>
          <div className="ca-label">Notas internas (opcional)</div>
          <textarea className="ca-input" style={{ minHeight: 52, resize: "vertical", lineHeight: 1.5 }} value={notas} onChange={(e) => setNotas(e.target.value)} placeholder="Indicaciones para la cita, recordatorios…" />
        </div>

        {error && <div style={{ color: "#B4564E", fontSize: 13, marginBottom: 10, background: "#FDECEA", border: "1px solid #F3C9C4", borderRadius: 8, padding: "8px 10px" }}>{error}</div>}
        <div style={{ display: "flex", gap: 9, justifyContent: "flex-end" }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" style={{ opacity: enviando ? 0.7 : 1, pointerEvents: enviando ? "none" : "auto" }} onClick={guardar}>{enviando ? "Agendando…" : "Agendar"}</button>
        </div>
      </div>
    </div>
  );
}

function BloqueoModal({ fechaInicial, onClose, onSave }) {
  const [fecha, setFecha] = useState(fechaInicial || HOY_ISO);
  const [horaInicio, setHoraInicio] = useState("");
  const [horaFin, setHoraFin] = useState("");
  const [medicos, setMedicos] = useState([]);
  const [medicoId, setMedicoId] = useState("");
  const [sede, setSede] = useState("");
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState("");
  useEffect(() => { api.medicos().then(setMedicos).catch(() => {}); }, []);
  const medicosVisibles = medicos.filter((m) => !sede || !m.sede || m.sede === sede);

  function guardar() {
    if (!fecha) { setError("Falta la fecha."); return; }
    if (!horaInicio || !horaFin) { setError("Pon hora de inicio y de fin."); return; }
    if (horaFin <= horaInicio) { setError("La hora de fin debe ser posterior al inicio."); return; }
    setError("");
    onSave({ fecha, hora_inicio: horaInicio, hora_fin: horaFin, medicoId: medicoId || null, sede, motivo: motivo.trim() });
  }

  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 420 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <strong style={{ fontSize: 16 }}>Bloquear horario</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>
        <div style={{ fontSize: 12.5, color: "var(--muted)", marginBottom: 14 }}>Reserva un espacio sin paciente (almuerzo, ausencia, viaje…) para que no se agende.</div>

        <div style={{ marginBottom: 13 }}>
          <div className="ca-label">Fecha</div>
          <input className="ca-input" type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
        </div>
        <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
          <div style={{ flex: 1 }}><div className="ca-label">Desde</div>
            <input className="ca-input" type="time" value={horaInicio} onChange={(e) => setHoraInicio(e.target.value)} /></div>
          <div style={{ flex: 1 }}><div className="ca-label">Hasta</div>
            <input className="ca-input" type="time" value={horaFin} onChange={(e) => setHoraFin(e.target.value)} /></div>
        </div>
        <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Sede</div>
            <select className="ca-input" value={sede} onChange={(e) => { const s = e.target.value; setSede(s); if (medicoId && !medicos.some((m) => String(m.id) === String(medicoId) && (!s || m.sede === s))) setMedicoId(""); }}>
              <option value="">— Todas —</option>
              <option value="lima">Lima</option>
              <option value="piura">Piura</option>
            </select>
          </div>
          <div style={{ flex: 1.5 }}>
            <div className="ca-label">Psicólogo <span style={{ color: "var(--muted)", fontWeight: 400 }}>(opcional)</span></div>
            <select className="ca-input" value={medicoId} onChange={(e) => setMedicoId(e.target.value)}>
              <option value="">— Toda la sede —</option>
              {medicosVisibles.map((m) => <option key={m.id} value={m.id}>{m.nombre}</option>)}
            </select>
          </div>
        </div>
        <div style={{ marginBottom: 18 }}>
          <div className="ca-label">Motivo <span style={{ color: "var(--muted)", fontWeight: 400 }}>(opcional)</span></div>
          <input className="ca-input" value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Almuerzo, reunión, viaje…" />
        </div>

        {error && <div style={{ color: "#B4564E", fontSize: 13, marginBottom: 10, background: "#FDECEA", border: "1px solid #F3C9C4", borderRadius: 8, padding: "8px 10px" }}>{error}</div>}
        <div style={{ display: "flex", gap: 9, justifyContent: "flex-end" }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" onClick={guardar}>Bloquear</button>
        </div>
      </div>
    </div>
  );
}

// Nota administrativa de una cita YA agendada ("el paciente confirmó inicio de
// proceso", "quedó para quincena"…). Se puede escribir DESPUÉS de la sesión.
function NotaCitaModal({ cita, onClose, onSaved, showToast }) {
  const [notas, setNotas] = useState(cita.notas || "");
  const [guardando, setGuardando] = useState(false);
  async function guardar() {
    setGuardando(true);
    try {
      await api.actualizarCita(cita.id, { notas: notas.trim() });
      showToast && showToast("Nota guardada ✓");
      onSaved();
    } catch (e) { showToast && showToast("Error: " + e.message); }
    finally { setGuardando(false); }
  }
  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 440 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
          <strong style={{ fontSize: 16 }}>Nota de la sesión</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>
        <div className="ca-pmeta" style={{ marginBottom: 14 }}>{cita.paciente} · {cita.fecha} {cita.hora}</div>
        <div style={{ marginBottom: 14 }}>
          <div className="ca-label">¿Qué pasó con esta cita?</div>
          <textarea className="ca-input" style={{ minHeight: 110, resize: "vertical", lineHeight: 1.5 }} value={notas} autoFocus
            onChange={(e) => setNotas(e.target.value)}
            placeholder="Ej: el paciente confirmó inicio de proceso · quedó en escribir en quincena · pidió cambiar de horario…" />
          <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 6 }}>Es una nota administrativa del seguimiento, no la historia clínica.</div>
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" onClick={guardar} disabled={guardando}>{guardando ? "Guardando…" : "Guardar nota"}</button>
        </div>
      </div>
    </div>
  );
}

function CitaRow({ c, esAsistente, esMedico, onAtender, onRecordar, onReagendar, onCancelar, onConfirmar, onCobrar, onSetEstado, onMensaje, openFicha, onEditarNota, onEliminarCita }) {
  const activa = c.estado !== "atendida" && c.estado !== "cancelada";
  const col = STATUS[c.estado] || {};
  const cc = colorCita(c);
  return (
    <div className="ca-row" style={{ background: cc.bg, borderLeft: `5px solid ${cc.fg}`, flexWrap: "wrap" }} title={cc.l}>
      <div className="ca-time"><Clock size={13} strokeWidth={2} style={{ color: "var(--muted)" }} />{c.hora}</div>
      <div style={{ flex: 1, minWidth: 150 }}>
        <button className="ca-pnamebtn" onClick={() => openFicha(c.pacienteId)}>{c.paciente}</button>
        {c.agendado_web && <span title="La reservó el paciente desde la web — priorizar contacto para confirmar y cobrar" style={{ marginLeft: 6, fontSize: 10.5, background: "#E3F1F2", color: "#0C5E69", padding: "1px 7px", borderRadius: 999, fontWeight: 700, verticalAlign: "middle" }}>🌐 Web</span>}
        <div className="ca-pmeta">
          {c.medico}{c.n_sesion ? ` · Sesión N° ${c.n_sesion}` : ""}{c.sede_label ? ` · ${c.sede_label}` : ""} · {c.modalidad === "virtual" ? "Virtual" : "Presencial"}
          {c.modalidad === "virtual" && c.enlace && (<> · <a href={c.enlace} target="_blank" rel="noreferrer" style={{ color: "var(--accent)", fontWeight: 600 }}>Unirse</a></>)}
        </div>
      </div>
      <SpecialtyTag name={c.especialidad} />
      {esMedico ? (
        <Tag colors={STATUS[c.estado]}>{c.estado_label}</Tag>
      ) : (
        <select className="ca-input" title="Cambiar estado de la cita"
          style={{ width: "auto", padding: "5px 9px", fontSize: 12.5, fontWeight: 600, borderRadius: 999, cursor: "pointer", background: col.bg || "var(--bg)", color: col.fg || "var(--ink)", borderColor: col.bg || "var(--line)" }}
          value={ESTADOS_CITA.some((e) => e.v === c.estado) ? c.estado : "agendada"}
          onChange={(e) => onSetEstado(c, e.target.value)}>
          {ESTADOS_CITA.map((e) => <option key={e.v} value={e.v} style={{ background: "#fff", color: "var(--ink)" }}>{e.l}</option>)}
        </select>
      )}
      <div className="ca-actions">
        {/* Estado (confirmar/asistió/cancelar…) se maneja con el desplegable de arriba.
            Aquí solo acciones que NO son estado: mensaje, atender, cobrar, mover. */}
        {!esMedico && (
          <button className="ca-mini wa" onClick={() => onMensaje(c)} title="Enviar mensaje (recordatorio y demás plantillas)"><MessageCircle size={13} strokeWidth={2} /> Mensaje{c.recordado ? " ✓" : ""}</button>
        )}
        {activa && !esAsistente && (
          <button className="ca-mini" onClick={() => onAtender(c)}><Stethoscope size={13} strokeWidth={2} /> {esMedico ? "Registrar sesión" : "Atender"}</button>
        )}
        {esMedico && (
          <button className="ca-mini" onClick={() => openFicha(c.pacienteId)} title="Historia clínica"><FileText size={13} strokeWidth={2} /> Historia</button>
        )}
        {!esMedico && c.estado === "atendida" && (c.cobrada ? (
          <span className="ca-mini done"><Check size={13} strokeWidth={2.4} /> Cobrada</span>
        ) : (
          <button className="ca-mini" onClick={() => onCobrar(c)} title="Registrar cobro"><Receipt size={13} strokeWidth={2} /> Cobrar</button>
        ))}
        {onEditarNota && (
          <button className="ca-mini" onClick={() => onEditarNota(c)} title={c.notas ? `Nota: ${c.notas}` : "Agregar una nota de seguimiento a esta cita"}>
            <Pencil size={13} strokeWidth={2} /> Nota{c.notas ? " ✓" : ""}
          </button>
        )}
        {activa && !esMedico && (
          <button className="ca-mini" onClick={() => onReagendar(c)} title="Reagendar (cambiar fecha/hora)"><Calendar size={13} strokeWidth={2} /> Mover</button>
        )}
        {onEliminarCita && (
          <button className="ca-mini" onClick={() => onEliminarCita(c)} title="Eliminar esta cita (queda registrado para gerencia)" style={{ color: "#9C4646" }}><Trash2 size={13} strokeWidth={2} /> Eliminar</button>
        )}
      </div>
      {c.notas && (
        <div style={{ flexBasis: "100%", fontSize: 12.5, color: "var(--muted)", marginTop: 4, display: "flex", gap: 6, alignItems: "flex-start" }}>
          <Pencil size={12} strokeWidth={2} style={{ flexShrink: 0, marginTop: 2 }} />
          <span style={{ whiteSpace: "pre-wrap" }}>{c.notas}</span>
        </div>
      )}
    </div>
  );
}

// Agenda multi-terapeuta (estilo AgendaPro): horas a la izquierda, una columna por
// CADA psicólogo activo (atienda o no ese día). Clic en una cita abre su detalle.
function TerapeutasGrid({ citas, terapeutas, horarios = {}, fecha, onAbrirCita }) {
  // Día de la semana (1=Lun … 7=Dom) de la fecha mostrada, sin líos de zona horaria.
  const wd = (() => { if (!fecha) return null; const [y, m, d] = fecha.split("-").map(Number); const g = new Date(y, m - 1, d).getDay(); return g === 0 ? 7 : g; })();
  const horasSet = new Set();
  citas.forEach((c) => { const h = parseInt(c.hora.slice(0, 2), 10); if (!isNaN(h)) horasSet.add(h); });
  terapeutas.forEach((t) => (horarios[t]?.[String(wd)] || []).forEach((h) => horasSet.add(Number(h))));
  const arr = [...horasSet];
  const hIni = arr.length ? Math.max(6, Math.min(...arr, 8)) : 8;
  const hFin = arr.length ? Math.min(22, Math.max(...arr, 19) + 1) : 20;
  const rows = [];
  for (let h = hIni; h <= hFin; h++) rows.push(h);
  const trabaja = (t, h) => {
    const hor = horarios[t];
    if (!hor || Object.keys(hor).length === 0) return true; // sin horario definido → no se grisea
    return (hor[String(wd)] || []).map(Number).includes(h);
  };

  if (terapeutas.length === 0)
    return <div className="ca-empty" style={{ marginTop: 18 }}>No hay psicólogos activos para mostrar.</div>;

  return (
    <div className="ca-card" style={{ marginTop: 18, overflowX: "auto", padding: 0 }}>
      <table className="ca-table" style={{ minWidth: 80 + terapeutas.length * 160 }}>
        <thead>
          <tr>
            <th style={{ width: 60 }}>Hora</th>
            {terapeutas.map((t) => <th key={t} style={{ textAlign: "center" }}>{t}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((h) => (
            <tr key={h}>
              <td style={{ color: "var(--muted)", fontSize: 12, whiteSpace: "nowrap", verticalAlign: "top" }}>{String(h).padStart(2, "0")}:00</td>
              {terapeutas.map((t) => {
                const evs = citas.filter((c) => c.medico === t && parseInt(c.hora.slice(0, 2), 10) === h && c.estado !== "cancelada");
                const disp = trabaja(t, h);
                return (
                  <td key={t} style={{ verticalAlign: "top", background: evs.length ? undefined : (disp ? "#F3FBF6" : "repeating-linear-gradient(45deg,#F1F0EE,#F1F0EE 6px,#ECEBE8 6px,#ECEBE8 12px)") }}>
                    {evs.length === 0 && (
                      <span style={{ fontSize: 10.5, color: disp ? "#3E7A65" : "var(--muted)", opacity: 0.75 }}>{disp ? "Libre" : "No disp."}</span>
                    )}
                    {evs.map((c) => {
                      const col = colorCita(c);
                      return (
                        <button key={c.id} onClick={() => onAbrirCita(c)}
                          title={`${c.hora} · ${c.paciente} · ${c.especialidad} · ${col.l}${c.agendado_web ? " · 🌐 Reserva web del paciente" : ""}`}
                          style={{ display: "block", width: "100%", textAlign: "left", border: "none",
                                   borderLeft: `3px solid ${col.fg}`, background: col.bg, borderRadius: 6,
                                   padding: "4px 7px", marginBottom: 4, cursor: "pointer" }}>
                          <span style={{ fontSize: 11.5, fontWeight: 600, color: col.fg }}>{c.agendado_web ? "🌐 " : ""}{c.hora}</span>
                          <span style={{ fontSize: 12.5, display: "block" }}>{c.paciente}</span>
                        </button>
                      );
                    })}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Agenda({ citas, bloqueos = [], fecha, setFecha, vista, setVista, esAsistente, esMedico, onAgendar, onBloquear, onBorrarBloqueo, onVenta, onAtender, onRecordar, onReagendar, onCancelar, onConfirmar, onCobrar, onSetEstado, onAbrirCita, onMensaje, openFicha, onEditarNota, onEliminarCita }) {
  const [filtroMedico, setFiltroMedico] = useState("");
  const [filtroSede, setFiltroSede] = useState("");
  const [filtroEstado, setFiltroEstado] = useState("");
  const [verTodosTipos, setVerTodosTipos] = useState(false);
  const [medicosDir, setMedicosDir] = useState([]);
  useEffect(() => { api.medicos().then(setMedicosDir).catch(() => {}); }, []);
  // Sede "de casa" de cada psicólogo, según su ficha del directorio.
  const sedePorNombre = useMemo(
    () => Object.fromEntries(medicosDir.map((m) => [m.nombre, m.sede || ""])),
    [medicosDir]
  );
  // Lista de psicólogos = SOLO los del directorio ACTIVO (api.medicos ya excluye
  // inactivos), filtrados por su sede. Antes se agregaban también los presentes en
  // las citas, y eso colaba psicólogos DESACTIVADOS que aún tenían citas (ej. Mirai).
  const medicos = useMemo(
    () => medicosDir.filter((m) => !filtroSede || m.sede === filtroSede).map((m) => m.nombre).filter(Boolean).sort(),
    [medicosDir, filtroSede]
  );
  const horariosPorNombre = useMemo(() => Object.fromEntries(medicosDir.map((m) => [m.nombre, m.horario || {}])), [medicosDir]);
  const semana = vista === "semana" ? semanaDe(fecha) : null;
  const dias = vista === "mes" ? mesDe(fecha) : null;
  const mesActual = vista === "mes" ? dDeISO(fecha).getMonth() : null;
  const delDia = (iso) => citas
    .filter((c) => c.fecha === iso && (!filtroMedico || c.medico === filtroMedico) && (!filtroSede || c.sede === filtroSede))
    .sort((a, b) => a.hora.localeCompare(b.hora));
  // Filtro por ESTADO al hacer clic en un chip de arriba. NO se aplica a `visibles`
  // (de ahí salen los conteos, que deben seguir mostrando el total), sino solo a
  // lo que se dibuja en cada vista.
  const filtEstado = (arr) => (filtroEstado ? arr.filter((c) => c.estado === filtroEstado) : arr);
  const visibles = vista === "semana"
    ? citas.filter((c) => semana.includes(c.fecha) && (!filtroMedico || c.medico === filtroMedico) && (!filtroSede || c.sede === filtroSede))
    : vista === "mes"
    ? citas.filter((c) => dias.includes(c.fecha) && dDeISO(c.fecha).getMonth() === mesActual && (!filtroMedico || c.medico === filtroMedico) && (!filtroSede || c.sede === filtroSede))
    : delDia(fecha);
  const activas = visibles.filter((c) => c.estado !== "cancelada");
  // Resumen de cuántas citas hay en cada estado (del día/semana mostrado).
  const resumen = ESTADOS_CITA.map((e) => ({ ...e, n: visibles.filter((c) => c.estado === e.v).length })).filter((e) => e.n > 0);
  // Resumen por tipo de servicio (no cuenta canceladas).
  const resumenTipos = Object.entries(
    visibles.filter((c) => c.estado !== "cancelada").reduce((acc, c) => { const k = c.especialidad || "Sin tipo"; acc[k] = (acc[k] || 0) + 1; return acc; }, {})
  ).sort((a, b) => b[1] - a[1]);
  const bloqueosDia = bloqueos.filter((b) => b.fecha === fecha).sort((a, b) => a.hora_inicio.localeCompare(b.hora_inicio));
  const subt = vista === "semana" ? `${labelNumMes(semana[0])} – ${labelNumMes(semana[6])}`
    : vista === "mes" ? labelMes(fecha) : labelLargo(fecha);
  const paso = vista === "semana" ? 7 : 1;
  const irAtras = () => setFecha(vista === "mes" ? sumarMeses(fecha, -1) : sumarDias(fecha, -paso));
  const irAdelante = () => setFecha(vista === "mes" ? sumarMeses(fecha, 1) : sumarDias(fecha, paso));

  return (
    <>
      <div className="ca-tophead">
        <div>
          <h1 className="ca-h1">Agenda</h1>
          <div className="ca-sub">{subt} · {activas.length} {activas.length === 1 ? "sesión" : "sesiones"}</div>
        </div>
        <div style={{ display: "flex", gap: 9, alignItems: "center" }}>
          {!esMedico && <ExportBtns nombre="agenda" titulo="Agenda" disabled={activas.length === 0}
            headers={["Fecha", "Hora", "Paciente", "Psicologo", "Especialidad", "N° sesion", "Sede", "Modalidad", "Estado"]}
            filas={activas.map((c) => [c.fecha, c.hora, c.paciente, c.medico, c.especialidad, c.n_sesion || "", c.sede_label || "", c.modalidad === "virtual" ? "Virtual" : "Presencial", c.estado_label])} />}
          {!esMedico && <button className="ca-btn ghost" onClick={onVenta}><Receipt size={15} strokeWidth={2} /> Venta</button>}
          {!esMedico && <button className="ca-btn ghost" onClick={onBloquear}><Clock size={15} strokeWidth={2} /> Bloquear horario</button>}
          {!esMedico && <button className="ca-btn" onClick={onAgendar}><Plus size={16} strokeWidth={2.2} /> Agendar sesión</button>}
        </div>
      </div>

      <div className="ca-agnav">
        <div className="ca-navgrp">
          <button className="ca-navbtn" onClick={irAtras} aria-label="Anterior"><ChevronLeft size={16} strokeWidth={2.2} /></button>
          <button className={`ca-navbtn ${fecha === HOY_ISO ? "on" : ""}`} onClick={() => setFecha(HOY_ISO)}>Hoy</button>
          <button className="ca-navbtn" onClick={irAdelante} aria-label="Siguiente"><ChevronLeft size={16} strokeWidth={2.2} style={{ transform: "rotate(180deg)" }} /></button>
        </div>
        <input className="ca-datein" type="date" value={fecha} onChange={(e) => e.target.value && setFecha(e.target.value)} />
        {/* El psicólogo solo ve SU agenda: sin filtros de sede/psicólogo ni vista de todos. */}
        {!esMedico && (
          <select className="ca-datein" value={filtroSede} onChange={(e) => { setFiltroSede(e.target.value); setFiltroMedico(""); }}>
            <option value="">Todas las sedes</option>
            <option value="lima">Lima</option>
            <option value="piura">Piura</option>
          </select>
        )}
        {!esMedico && medicos.length > 1 && (
          <select className="ca-datein" value={filtroMedico} onChange={(e) => setFiltroMedico(e.target.value)}>
            <option value="">Todos los psicólogos</option>
            {medicos.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        )}
        <div className="ca-seg">
          <button className={vista === "dia" ? "on" : ""} onClick={() => setVista("dia")}>Día</button>
          {!esMedico && <button className={vista === "terapeutas" ? "on" : ""} onClick={() => setVista("terapeutas")}>Terapeutas</button>}
          <button className={vista === "semana" ? "on" : ""} onClick={() => setVista("semana")}>Semana</button>
          <button className={vista === "mes" ? "on" : ""} onClick={() => setVista("mes")}>Mes</button>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8, background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 12, padding: "10px 13px", margin: "8px 0 14px" }}>
      {resumen.length > 0 && (
        <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
          <span style={{ width: 58, flexShrink: 0, fontSize: 11.5, color: "var(--muted)", fontWeight: 700, paddingTop: 4 }}>Estado</span>
          <div style={{ display: "flex", gap: 7, flexWrap: "wrap", flex: 1, alignItems: "center" }}>
            {resumen.map((e) => {
              const activo = filtroEstado === e.v;
              return (
                <button key={e.v} onClick={() => setFiltroEstado((s) => (s === e.v ? "" : e.v))}
                  title={activo ? "Quitar filtro — ver todas" : `Ver solo: ${e.l}`}
                  style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12.5, fontWeight: 600, cursor: "pointer",
                    padding: "3px 11px", borderRadius: 999, background: (STATUS[e.v] || {}).bg, color: (STATUS[e.v] || {}).fg,
                    border: `2px solid ${activo ? (STATUS[e.v] || {}).fg : "transparent"}`,
                    boxShadow: activo ? "0 1px 5px rgba(0,0,0,.16)" : "none",
                    opacity: filtroEstado && !activo ? 0.45 : 1, transition: "opacity .12s" }}>
                  {e.l} <b style={{ fontWeight: 800 }}>{e.n}</b>
                </button>
              );
            })}
            {filtroEstado && (
              <button onClick={() => setFiltroEstado("")} title="Quitar el filtro de estado"
                style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 12, fontWeight: 700, cursor: "pointer",
                  padding: "3px 10px", borderRadius: 999, background: "transparent", color: "var(--muted)", border: "1px solid var(--line)" }}>
                <X size={12} strokeWidth={2.4} /> Ver todas
              </button>
            )}
          </div>
        </div>
      )}
      {resumenTipos.length > 0 && (
        <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
          <span style={{ width: 58, flexShrink: 0, fontSize: 11.5, color: "var(--muted)", fontWeight: 700, paddingTop: 4 }}>Por tipo</span>
          <div style={{ display: "flex", gap: 7, flexWrap: "wrap", flex: 1 }}>
            {(verTodosTipos ? resumenTipos : resumenTipos.slice(0, 8)).map(([tipo, n]) => (
              <span key={tipo} style={{ display: "inline-flex", alignItems: "center", gap: 7, fontSize: 12.5, fontWeight: 500,
                padding: "2px 11px 2px 3px", borderRadius: 999, background: "#F4F2EE", color: "var(--ink-soft)", border: "1px solid var(--line)" }}>
                <span style={{ minWidth: 21, textAlign: "center", fontWeight: 800, fontSize: 11.5, lineHeight: "18px",
                  padding: "0 6px", borderRadius: 999, background: (SPECIALTY[tipo]?.fg) || "#7C7870", color: "#fff" }}>{n}</span>
                <span>{tipo}</span>
              </span>
            ))}
            {resumenTipos.length > 8 && (
              <button onClick={() => setVerTodosTipos((v) => !v)}
                style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 12, fontWeight: 700, cursor: "pointer",
                  padding: "3px 12px", borderRadius: 999, background: "transparent", color: "var(--accent)", border: "1px dashed var(--accent)" }}>
                {verTodosTipos ? "ver menos" : `＋${resumenTipos.length - 8} más`}
              </button>
            )}
          </div>
        </div>
      )}

      <div style={{ display: "flex", gap: 10, alignItems: "flex-start", borderTop: "1px solid var(--line)", paddingTop: 9 }}>
        <span style={{ width: 58, flexShrink: 0, fontSize: 11.5, color: "var(--muted)", fontWeight: 700, paddingTop: 1 }}>Colores</span>
        <div style={{ display: "flex", gap: 13, flexWrap: "wrap", alignItems: "center", flex: 1, fontSize: 11.5, color: "var(--muted)" }}>
          {COLOR_CITA_LEYENDA.map((x) => (
            <span key={x.l} style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
              <span style={{ width: 10, height: 10, borderRadius: 3, background: x.fg, display: "inline-block" }} />{x.l}
            </span>
          ))}
          <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }} title="La reservó el paciente desde la web — priorizar contacto para confirmar y cobrar">
            🌐 Reservó el paciente por la web
          </span>
        </div>
      </div>
      </div>
      {vista === "dia" ? (
        <div style={{ marginTop: 18 }}>
          {bloqueosDia.map((b) => (
            <div key={`b${b.id}`} style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 12px", marginBottom: 8, borderRadius: 10, background: "#F1F0EE", border: "1px dashed var(--line)", color: "#6B675F" }}>
              <Clock size={14} strokeWidth={2} />
              <span style={{ fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>{b.hora_inicio}–{b.hora_fin}</span>
              <span style={{ flex: 1 }}>🚫 {b.motivo || "No disponible"}{b.medico_nombre ? ` · ${b.medico_nombre}` : b.sede_label ? ` · ${b.sede_label}` : ""}</span>
              {!esMedico && <button className="ca-iconbtn" title="Quitar bloqueo" onClick={() => onBorrarBloqueo(b)}><X size={14} strokeWidth={2} /></button>}
            </div>
          ))}
          {filtEstado(delDia(fecha)).length === 0 ? (
            bloqueosDia.length === 0 && <div className="ca-empty">{filtroEstado ? "No hay citas con ese estado en este día." : "No hay sesiones para este día. Usa «Agendar sesión» para reservar una."}</div>
          ) : (
            filtEstado(delDia(fecha)).map((c) => (
              <CitaRow key={c.id} c={c} esAsistente={esAsistente} esMedico={esMedico}
                onAtender={onAtender} onRecordar={onRecordar} onReagendar={onReagendar}
                onCancelar={onCancelar} onConfirmar={onConfirmar} onCobrar={onCobrar}
                onSetEstado={onSetEstado} onMensaje={onMensaje} openFicha={openFicha} onEditarNota={onEditarNota} onEliminarCita={onEliminarCita} />
            ))
          )}
        </div>
      ) : vista === "terapeutas" ? (
        <TerapeutasGrid citas={filtEstado(delDia(fecha))} terapeutas={filtroMedico ? [filtroMedico] : medicos} horarios={horariosPorNombre} fecha={fecha} onAbrirCita={onAbrirCita} />
      ) : vista === "mes" ? (
        <div className="ca-mes">
          <div className="ca-mes-hd">
            {["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"].map((d) => <div key={d}>{d}</div>)}
          </div>
          <div className="ca-mes-grid">
            {dias.map((iso) => {
              const delMes = dDeISO(iso).getMonth() === mesActual;
              const dc = filtroEstado ? delDia(iso).filter((c) => c.estado === filtroEstado) : delDia(iso).filter((c) => c.estado !== "cancelada");
              return (
                <div key={iso} className={`ca-mes-cel ${delMes ? "" : "off"} ${iso === HOY_ISO ? "hoy" : ""}`}
                  onClick={() => { setFecha(iso); setVista("dia"); }} title={dc.length ? `${dc.length} sesiones` : ""}>
                  <div className="d">{dDeISO(iso).getDate()}</div>
                  {dc.slice(0, 3).map((c) => {
                    const col = colorCita(c);
                    return (
                      <div key={c.id} className="ca-mes-evt" style={{ background: col.bg, color: col.fg }}
                        title={`${c.hora} · ${c.paciente} · ${c.especialidad}${c.agendado_web ? " · 🌐 Reserva web del paciente" : ""}`}>
                        {c.agendado_web ? "🌐 " : ""}{c.hora} {c.paciente}
                      </div>
                    );
                  })}
                  {dc.length > 3 && <div className="ca-mes-mas">+{dc.length - 3} más</div>}
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        <div className="ca-wk">
          {semana.map((iso) => (
            <div key={iso} className={`ca-wkcol ${iso === HOY_ISO ? "hoy" : ""}`}>
              <div className="ca-wkhd" onClick={() => { setFecha(iso); setVista("dia"); }}>
                <div className="d">{labelDiaSemana(iso)}</div>
                <div className="n">{dDeISO(iso).getDate()}</div>
              </div>
              {filtEstado(delDia(iso)).length === 0 ? (
                <div className="ca-wkempty">·</div>
              ) : (
                filtEstado(delDia(iso)).map((c) => {
                  const col = colorCita(c);
                  return (
                    <div key={c.id} className={`ca-evt ${c.estado === "cancelada" ? "cancel" : ""}`}
                      style={{ background: col.bg, borderLeftColor: col.fg }}
                      onClick={() => { setFecha(iso); setVista("dia"); }} title={`${c.hora} · ${c.paciente} · ${c.especialidad}${c.agendado_web ? " · 🌐 Reserva web del paciente" : ""}`}>
                      <div className="h" style={{ color: col.fg }}>{c.agendado_web ? "🌐 " : ""}{c.hora}</div>
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

function CitaDetalleModal({ cita, esMedico, esAsistente, onClose, onSetEstado, openFicha, onAtender, onCobrar, onReagendar, onCancelar, onMensaje }) {
  const [estado, setEstado] = useState(cita.estado);
  const col = STATUS[estado] || {};
  const activa = estado !== "atendida" && estado !== "cancelada";
  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 420 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <strong style={{ fontSize: 16 }}>Cita · {cita.hora}</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>
        <button className="ca-pnamebtn" style={{ fontSize: 17, fontWeight: 600 }} onClick={() => openFicha(cita.pacienteId)}>{cita.paciente}</button>
        {cita.agendado_web && <span title="La reservó el paciente desde la web — priorizar contacto para confirmar y cobrar" style={{ marginLeft: 8, fontSize: 11, background: "#E3F1F2", color: "#0C5E69", padding: "2px 8px", borderRadius: 999, fontWeight: 700, verticalAlign: "middle" }}>🌐 Reserva web</span>}
        <div className="ca-pmeta" style={{ marginTop: 4, lineHeight: 1.6 }}>
          {cita.fecha} · {cita.hora}<br />
          {cita.medico || "Sin psicólogo"}{cita.n_sesion ? ` · Sesión N° ${cita.n_sesion}` : ""}<br />
          {cita.especialidad}{cita.sede_label ? ` · ${cita.sede_label}` : ""} · {cita.modalidad === "virtual" ? "Virtual" : "Presencial"}
          {cita.modalidad === "virtual" && cita.enlace && (<> · <a href={cita.enlace} target="_blank" rel="noreferrer" style={{ color: "var(--accent)", fontWeight: 600 }}>Unirse</a></>)}
          {cita.notas ? <><br /><span style={{ fontStyle: "italic" }}>{cita.notas}</span></> : null}
        </div>

        {!esMedico && (
          <div style={{ margin: "16px 0" }}>
            <div className="ca-label">Estado</div>
            <select className="ca-input" value={ESTADOS_CITA.some((e) => e.v === estado) ? estado : "agendada"}
              style={{ fontWeight: 600, background: col.bg || "var(--bg)", color: col.fg || "var(--ink)" }}
              onChange={(e) => { setEstado(e.target.value); onSetEstado(cita, e.target.value); }}>
              {ESTADOS_CITA.map((e) => <option key={e.v} value={e.v} style={{ background: "#fff", color: "var(--ink)" }}>{e.l}</option>)}
            </select>
          </div>
        )}

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
          <button className="ca-mini" onClick={() => { onClose(); openFicha(cita.pacienteId); }}><FileText size={13} strokeWidth={2} /> Ficha / pagos</button>
          {!esMedico && <button className="ca-mini wa" onClick={() => { onClose(); onMensaje(cita); }}><MessageCircle size={13} strokeWidth={2} /> Mensaje</button>}
          {activa && !esAsistente && <button className="ca-mini" onClick={() => { onClose(); onAtender(cita); }}><Stethoscope size={13} strokeWidth={2} /> {esMedico ? "Registrar sesión" : "Atender"}</button>}
          {!esMedico && <button className="ca-mini" onClick={() => { onClose(); onCobrar(cita); }}><Receipt size={13} strokeWidth={2} /> Cobrar</button>}
          {activa && !esMedico && <button className="ca-mini" onClick={() => { onClose(); onReagendar(cita); }}><Calendar size={13} strokeWidth={2} /> Mover</button>}
          {activa && <button className="ca-mini" style={{ color: "#B4564E" }} onClick={() => { onClose(); onCancelar(cita); }}><X size={13} strokeWidth={2} /> Cancelar</button>}
        </div>
      </div>
    </div>
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
            <input className="ca-input" type="time" step={900} value={hora} onChange={(e) => setHora(e.target.value)} />
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

function AtenderModal({ cita, servicios, onClose, onSave, esMedico }) {
  const [tipo, setTipo] = useState("evolucion");
  // Un campo por cada campo del modelo Atencion; la ficha activa decide cuáles se muestran.
  const [campos, setCampos] = useState(() =>
    Object.fromEntries(TODOS_CAMPOS_HC.map((k) => [k, ""]))
  );
  const setCampo = (k) => (e) => setCampos((p) => ({ ...p, [k]: e.target.value }));

  const [transcribiendo, setTranscribiendo] = useState(false);
  const [dictMsg, setDictMsg] = useState("");
  const [grabando, setGrabando] = useState(false);
  const recRef = React.useRef(null);
  const chunksRef = React.useRef([]);

  const fichaCampos = FICHAS[tipo] || FICHAS.evolucion;
  const canSave = fichaCampos.some((c) => (campos[c.k] || "").trim().length > 0);

  async function toggleGrabar() {
    if (grabando) { recRef.current?.stop(); return; }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setDictMsg("Error: este navegador no permite grabar aquí. Usa 'Subir audio'. (En el celular por red se necesita HTTPS.)");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      chunksRef.current = [];
      mr.ondataavailable = (e) => { if (e.data && e.data.size) chunksRef.current.push(e.data); };
      mr.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        setGrabando(false);
        const tipo = mr.mimeType || "audio/webm";
        const ext = tipo.includes("mp4") ? "mp4" : tipo.includes("ogg") ? "ogg" : "webm";
        const blob = new Blob(chunksRef.current, { type: tipo });
        if (blob.size > 0) dictar(new File([blob], `sesion.${ext}`, { type: tipo }));
        else setDictMsg("No se grabó audio.");
      };
      recRef.current = mr;
      mr.start();
      setGrabando(true);
      setDictMsg("● Grabando… habla y toca Detener al terminar.");
    } catch (err) {
      setDictMsg("Error: no se pudo usar el micrófono (" + (err.message || err.name) + "). En el celular por red hace falta HTTPS.");
    }
  }

  async function dictar(file) {
    if (!file) return;
    setTranscribiendo(true);
    setDictMsg("Transcribiendo el audio…");
    try {
      const r = await api.transcribirAudio(file, tipo);
      const e = r.estructura;
      if (e) {
        setCampos((prev) => {
          const next = { ...prev };
          TODOS_CAMPOS_HC.forEach((k) => { if (e[k] && !next[k].trim()) next[k] = e[k]; });
          return next;
        });
        setDictMsg("Listo: la IA llenó los campos. Revísalos antes de guardar.");
      } else if (r.transcripcion) {
        const primero = fichaCampos[0].k;
        setCampos((prev) => ({ ...prev, [primero]: prev[primero].trim() ? prev[primero] + "\n\n" + r.transcripcion : r.transcripcion }));
        setDictMsg("Transcripción lista. (Para que la IA la ordene en campos, configura OpenAI.)");
      } else {
        setDictMsg("No se detectó voz en el audio.");
      }
    } catch (err) {
      setDictMsg("Error: " + err.message);
    } finally {
      setTranscribiendo(false);
    }
  }

  // Inserta el código DP estandarizado en la nota (campo "próximos pasos" si existe;
  // si no, en el último campo del tipo activo).
  function insertarDP(codigo, label) {
    const target = (fichaCampos.find((c) => c.k === "proximos_pasos") || fichaCampos[fichaCampos.length - 1] || {}).k;
    if (!target) return;
    const texto = `${codigo} | ${label}. `;
    setCampos((p) => {
      const prev = (p[target] || "").replace(/\s*$/, "");
      return { ...p, [target]: prev ? prev + "\n" + texto : texto };
    });
  }

  function guardar() {
    // Solo se guardan los campos del tipo activo (los demás van vacíos: sin mezcla entre tipos).
    const datos = { tipo };
    TODOS_CAMPOS_HC.forEach((k) => { datos[k] = ""; });
    fichaCampos.forEach((c) => { datos[c.k] = (campos[c.k] || "").trim(); });
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

        <div style={{ border: "1px solid var(--accent-soft)", background: "var(--accent-soft)", borderRadius: 10, padding: "10px 12px", marginBottom: 16 }}>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
            <button type="button" onClick={toggleGrabar} disabled={transcribiendo}
              style={{
                display: "inline-flex", alignItems: "center", gap: 7, cursor: transcribiendo ? "wait" : "pointer",
                fontSize: 13.5, fontWeight: 600, border: "none", borderRadius: 8, padding: "8px 12px",
                color: "#fff", background: grabando ? "#B4564E" : "var(--accent)",
              }}>
              <Mic size={15} strokeWidth={2.2} /> {grabando ? "■ Detener y transcribir" : "● Grabar la sesión"}
            </button>
            <label style={{ display: "inline-flex", alignItems: "center", gap: 6, cursor: transcribiendo ? "wait" : "pointer", fontSize: 13, color: "var(--accent)", fontWeight: 500 }}>
              <Paperclip size={13} strokeWidth={2} /> Subir audio
              <input type="file" accept="audio/*" hidden disabled={transcribiendo || grabando}
                onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; dictar(f); }} />
            </label>
          </div>
          <div style={{ fontSize: 12, color: "var(--ink-soft)", marginTop: 6 }}>
            {transcribiendo ? "Transcribiendo con Whisper…" : "Graba (o sube) un audio y la IA llena los campos de la historia clínica. Tú solo revisas."}
          </div>
          {dictMsg && <div style={{ fontSize: 12, marginTop: 6, color: dictMsg.startsWith("Error") ? "#B4564E" : "var(--ink)" }}>{dictMsg}</div>}
        </div>

        {/* Tipo de documento clínico */}
        <div style={{ marginBottom: 14 }}>
          <div className="ca-label">Tipo de documento</div>
          <select className="ca-input" value={tipo} onChange={(e) => setTipo(e.target.value)}>
            {TIPOS_HC.map((t) => <option key={t.v} value={t.v}>{t.l}</option>)}
          </select>
        </div>

        {/* Guía de notas: Decisión del Paciente (DP). Es de coordinación (va en las
            notas de la cita), no de la ficha clínica: no se muestra al psicólogo. */}
        {!esMedico && (
        <div style={{ marginBottom: 14 }}>
          <div className="ca-label" style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <FileText size={13} strokeWidth={2} style={{ color: "var(--accent)" }} /> Decisión del paciente (DP) — insertar en la nota
          </div>
          <select className="ca-input" value="" onChange={(e) => { if (e.target.value) { const [c, l] = e.target.value.split("|::|"); insertarDP(c, l); } }}>
            <option value="">Elige un código para insertarlo…</option>
            {DP_CODES.map((g) => (
              <optgroup key={g.cat} label={g.cat}>
                {g.items.map((it) => <option key={it.c} value={`${it.c}|::|${it.l}`}>{it.c} · {it.l}</option>)}
              </optgroup>
            ))}
          </select>
        </div>
        )}

        {fichaCampos.map((c, i) => (
          <div key={c.k} style={{ marginBottom: 13 }}>
            <div className="ca-label">{c.l}{i === 0 && <span style={{ color: "#B4564E" }}> *</span>}</div>
            <textarea className="ca-input" style={{ minHeight: i === 0 ? 80 : 56, resize: "vertical", lineHeight: 1.5 }}
              value={campos[c.k]} onChange={setCampo(c.k)} placeholder={c.ph} />
          </div>
        ))}
        <div style={{ fontSize: 12.5, color: "var(--muted)", margin: "0 0 16px", display: "flex", gap: 7, alignItems: "flex-start", lineHeight: 1.5 }}>
          <Receipt size={14} strokeWidth={2} style={{ color: "var(--accent)", flexShrink: 0, marginTop: 1 }} />
          <span>Se guarda en la historia clínica con fecha de hoy. El <strong>cobro lo registra Coordinación</strong> aparte, con el botón “Cobrar” de la agenda.</span>
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

function Mensajes({ mensajes, puedeEditar, showToast }) {
  const [plantillas, setPlantillas] = useState(null);
  const [editando, setEditando] = useState(null); // { id, texto }
  const [nueva, setNueva] = useState(null); // { clave, nombre, texto }

  useEffect(() => { api.plantillas().then(setPlantillas).catch(() => setPlantillas([])); }, []);

  // Clave sugerida a partir del nombre (sin tildes ni espacios): la usa el código
  // para buscar la plantilla (plantilla_por_clave).
  const claveDe = (s) => (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 30); // eslint-disable-line

  async function crearPlantilla() {
    const nombre = (nueva.nombre || "").trim();
    const texto = (nueva.texto || "").trim();
    const clave = (nueva.clave || "").trim() || claveDe(nombre);
    if (!nombre || !texto) return showToast && showToast("Ponle nombre y texto a la plantilla.");
    if (!clave) return showToast && showToast("La clave no puede quedar vacía.");
    if ((plantillas || []).some((p) => p.clave === clave)) return showToast && showToast(`Ya existe una plantilla con la clave «${clave}».`);
    try {
      const creada = await api.crearPlantilla({ clave, nombre, texto });
      setPlantillas((ps) => [...(ps || []), creada]);
      setNueva(null);
      showToast && showToast("Plantilla creada ✓");
    } catch (e) { showToast && showToast("Error: " + e.message); }
  }

  async function guardarPlantilla(ed) {
    try {
      const datos = {
        texto: ed.texto,
        wa_template_nombre: (ed.wa_template_nombre || "").trim(),
        wa_template_idioma: (ed.wa_template_idioma || "es").trim(),
        wa_template_vars: (ed.wa_template_vars || "").trim(),
      };
      await api.actualizarPlantilla(ed.id, datos);
      setPlantillas((ps) => ps.map((p) => (p.id === ed.id ? { ...p, ...datos } : p)));
      setEditando(null);
      showToast && showToast("Plantilla guardada ✓");
    } catch (e) { showToast && showToast("Error: " + e.message); }
  }

  return (
    <div>
      <h1 className="ca-h1">Mensajes</h1>
      <div className="ca-sub">Plantillas de WhatsApp y bitácora de envíos</div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 22 }}>
        <h2 className="ca-secth" style={{ margin: 0 }}>Plantillas</h2>
        {puedeEditar && !nueva && (
          <button className="ca-mini" onClick={() => setNueva({ clave: "", nombre: "", texto: "" })}>
            <Plus size={13} strokeWidth={2.2} /> Nueva plantilla
          </button>
        )}
      </div>
      <div className="ca-pmeta" style={{ marginBottom: 10 }}>
        Variables que se reemplazan solas: <code>{"{nombre} {psicologo} {fecha} {hora} {n_sesion} {sede} {clinica}"}</code>
      </div>

      {nueva && (
        <div className="ca-card" style={{ marginBottom: 12, borderColor: "var(--accent)" }}>
          <div style={{ display: "flex", gap: 11, marginBottom: 10, flexWrap: "wrap" }}>
            <div style={{ flex: 2, minWidth: 180 }}>
              <div className="ca-label">Nombre</div>
              <input className="ca-input" value={nueva.nombre} autoFocus placeholder="Ej: Recordatorio de encuesta"
                onChange={(e) => setNueva((n) => ({ ...n, nombre: e.target.value }))} />
            </div>
            <div style={{ flex: 1, minWidth: 140 }}>
              <div className="ca-label">Clave <span style={{ color: "var(--muted)", fontWeight: 400 }}>(opcional)</span></div>
              <input className="ca-input" value={nueva.clave} placeholder={claveDe(nueva.nombre) || "se genera sola"}
                onChange={(e) => setNueva((n) => ({ ...n, clave: e.target.value }))} />
            </div>
          </div>
          <div className="ca-label">Texto del mensaje</div>
          <textarea className="ca-input" style={{ minHeight: 100, resize: "vertical", lineHeight: 1.5 }} value={nueva.texto}
            onChange={(e) => setNueva((n) => ({ ...n, texto: e.target.value }))}
            placeholder="Hola {nombre} 👋 …" />
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 10 }}>
            <button className="ca-btn ghost" onClick={() => setNueva(null)}>Cancelar</button>
            <button className="ca-btn" onClick={crearPlantilla}>Crear plantilla</button>
          </div>
        </div>
      )}
      {!plantillas ? <div className="ca-empty">Cargando…</div> : plantillas.map((p) => (
        <div key={p.id} className="ca-card" style={{ marginBottom: 10 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6, gap: 8 }}>
            <strong style={{ fontSize: 13.5, display: "flex", alignItems: "center", gap: 8 }}>
              {p.nombre}
              {p.wa_template_nombre
                ? <Tag colors={{ bg: "#E4F3E8", fg: "#1E7D45" }}>Aprobada: {p.wa_template_nombre}</Tag>
                : <Tag colors={{ bg: "#FBF0D4", fg: "#8A6D14" }}>Texto (solo 24h)</Tag>}
            </strong>
            {puedeEditar && editando?.id !== p.id && (
              <button className="ca-mini" onClick={() => setEditando({ id: p.id, texto: p.texto, wa_template_nombre: p.wa_template_nombre || "", wa_template_idioma: p.wa_template_idioma || "es", wa_template_vars: p.wa_template_vars || "" })}><Pencil size={13} strokeWidth={2} /> Editar</button>
            )}
          </div>
          {editando?.id === p.id ? (
            <>
              <textarea className="ca-input" style={{ minHeight: 80 }} value={editando.texto}
                onChange={(e) => setEditando({ ...editando, texto: e.target.value })} />
              <div style={{ marginTop: 10, borderTop: "1px dashed var(--line)", paddingTop: 10 }}>
                <div className="ca-pmeta" style={{ marginBottom: 8 }}>
                  <strong>Plantilla aprobada de Meta (opcional)</strong> — para enviar fuera de las 24 h. Crea y aprueba la plantilla en Meta WhatsApp Manager y pega aquí su nombre exacto.
                </div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <div style={{ flex: "2 1 200px" }}>
                    <div className="ca-label">Nombre de la plantilla en Meta</div>
                    <input className="ca-input" value={editando.wa_template_nombre}
                      placeholder="ej. cumpleanos_itaca"
                      onChange={(e) => setEditando({ ...editando, wa_template_nombre: e.target.value })} />
                  </div>
                  <div style={{ width: 90 }}>
                    <div className="ca-label">Idioma</div>
                    <input className="ca-input" value={editando.wa_template_idioma}
                      placeholder="es" onChange={(e) => setEditando({ ...editando, wa_template_idioma: e.target.value })} />
                  </div>
                  <div style={{ flex: "1 1 160px" }}>
                    <div className="ca-label">Variables (en orden)</div>
                    <input className="ca-input" value={editando.wa_template_vars}
                      placeholder="nombre  ó  nombre,clinica"
                      onChange={(e) => setEditando({ ...editando, wa_template_vars: e.target.value })} />
                  </div>
                </div>
                <div className="ca-pmeta" style={{ marginTop: 6 }}>
                  Las variables llenan {"{{1}}, {{2}}…"} de la plantilla, en ese orden. Disponibles: nombre, psicologo, fecha, hora, n_sesion, sede, clinica.
                </div>
              </div>
              <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 10 }}>
                <button className="ca-btn ghost" onClick={() => setEditando(null)}>Cancelar</button>
                <button className="ca-btn" onClick={() => guardarPlantilla(editando)}>Guardar</button>
              </div>
            </>
          ) : (
            <div style={{ fontSize: 13, color: "var(--ink-soft)", whiteSpace: "pre-wrap" }}>{p.texto}</div>
          )}
        </div>
      ))}

      <h2 className="ca-secth" style={{ marginTop: 26 }}>Bitácora de envíos · {mensajes.length}</h2>
      {mensajes.length === 0 ? (
        <div className="ca-empty">Aún no se han enviado mensajes. Los que envíes aparecerán aquí.</div>
      ) : (
        <table className="ca-tbl" style={{ marginTop: 12 }}>
          <thead>
            <tr><th>Fecha</th><th>Paciente</th><th>Tipo</th><th>Estado</th><th>Mensaje</th></tr>
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

function MensajePacienteModal({ paciente, cita, onClose, onSend }) {
  const primer = (paciente.nombre || "").split(" ")[0];
  const inicial = `Hola ${primer} 👋 Desde Itaca Conversemos queremos saber cómo te encuentras. Si lo deseas, podemos agendar tu próxima sesión. Estamos para ayudarte 🌿`;
  const [texto, setTexto] = useState(inicial);
  const [enviando, setEnviando] = useState(false);
  const [plantillas, setPlantillas] = useState([]);
  const [tipoSel, setTipoSel] = useState("seguimiento");
  const [plantillaSel, setPlantillaSel] = useState(null); // { id, hsm }
  const sinTel = !paciente.tel || paciente.tel === "—";
  const canSend = texto.trim().length > 0 && !sinTel && !enviando;

  useEffect(() => {
    if (sinTel) return;
    // Con la cita en contexto, el recordatorio trae fecha/hora ya sustituidas.
    api.plantillas(paciente.id, cita?.id).then((ps) => setPlantillas(ps.filter((p) => p.activo))).catch(() => {});
  }, [paciente.id, sinTel, cita?.id]);

  async function usarPlantilla(p) {
    let txt = p.preview || p.texto;
    // Consentimiento / políticas: genera el enlace de firma y lo agrega al mensaje.
    if (["consentimiento", "politicas"].includes(p.clave)) {
      try {
        const c = await api.crearConsentimiento(paciente.id, p.clave);
        txt += `\n\n📄 Léelo y acéptalo aquí: ${window.location.origin}${c.url}`;
      } catch (e) { /* si falla, se manda el texto sin enlace */ }
    }
    setTexto(txt);
    setPlantillaSel({ id: p.id, hsm: !!p.wa_template_nombre });
    setTipoSel(["recordatorio", "confirmacion"].includes(p.clave) ? p.clave : "manual");
  }

  async function enviar() {
    setEnviando(true);
    try { await onSend(texto.trim(), tipoSel, plantillaSel?.id); } finally { setEnviando(false); }
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
          <>
            {plantillas.length > 0 && (
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
                {plantillas.map((p) => (
                  <button key={p.id} className="ca-mini" onClick={() => usarPlantilla(p)}>{p.nombre}</button>
                ))}
              </div>
            )}
            <textarea className="ca-input ca-textarea" style={{ minHeight: 120 }} value={texto}
              onChange={(e) => { setTexto(e.target.value); setPlantillaSel(null); }} autoFocus />
            {plantillaSel?.hsm && (
              <div className="ca-pmeta" style={{ marginTop: 8, background: "#E4F3E8", color: "#1E7D45", padding: "8px 10px", borderRadius: 8, lineHeight: 1.5 }}>
                ✅ Plantilla aprobada en Meta: se entrega aunque hayan pasado más de 24 h. El contenido lo define la plantilla aprobada (solo se personaliza el nombre).
              </div>
            )}
          </>
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

function ReporteCierreMkt({ showToast }) {
  const [abierto, setAbierto] = useState(false);
  const [data, setData] = useState(null);
  async function cargar() {
    try { setData(await api.reporteCierre()); }
    catch (e) { showToast && showToast("Error: " + e.message); }
  }
  function toggle() { const nv = !abierto; setAbierto(nv); if (nv && !data) cargar(); }

  const Fila = ({ etq, valor, sub }) => (
    <div style={{ display: "flex", alignItems: "baseline", gap: 10, padding: "6px 0", borderTop: "1px solid var(--line)" }}>
      <span style={{ flex: 1, fontSize: 13.5 }}>{etq}</span>
      <span style={{ fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>{valor}</span>
      {sub != null && <span style={{ color: "var(--muted)", fontSize: 12, width: 78, textAlign: "right" }}>{sub}</span>}
    </div>
  );
  const big = { fontSize: 24, fontWeight: 700, color: "#4F8A77" };
  const bigSub = { fontSize: 13, fontWeight: 400, color: "var(--muted)" };

  return (
    <div className="ca-card" style={{ marginTop: 18 }}>
      <button onClick={toggle} style={{ width: "100%", background: "none", border: "none", cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center", padding: 0 }}>
        <span className="ca-secth" style={{ margin: 0 }}>📊 Reporte de cierre (marketing)</span>
        <ChevronDown size={18} style={{ transform: abierto ? "rotate(180deg)" : "none", color: "var(--muted)" }} />
      </button>
      {abierto && (!data ? <div className="ca-empty" style={{ marginTop: 12 }}>Cargando…</div> : (
        <div style={{ marginTop: 14, display: "grid", gap: 24 }}>
          <div>
            <div className="ca-label" style={{ marginBottom: 4 }}>Cierre de leads → consulta</div>
            <div style={big}>{data.leads_consulta.general.pct}% <span style={bigSub}>({data.leads_consulta.general.num}/{data.leads_consulta.general.den})</span></div>
            {data.leads_consulta.por_sede.map((s) => <Fila key={s.sede || "x"} etq={s.sede_label} valor={`${s.pct}%`} sub={`${s.num}/${s.den}`} />)}
          </div>
          <div>
            <div className="ca-label" style={{ marginBottom: 4 }}>Cierre de consultas → proceso</div>
            <div style={big}>{data.consulta_proceso.general.pct}% <span style={bigSub}>({data.consulta_proceso.general.num}/{data.consulta_proceso.general.den})</span></div>
            {data.consulta_proceso.por_sede.map((s) => <Fila key={"s" + (s.sede || "x")} etq={`Sede ${s.sede_label}`} valor={`${s.pct}%`} sub={`${s.num}/${s.den}`} />)}
            {data.consulta_proceso.por_psicologo.map((p) => <Fila key={"p" + p.psicologo} etq={p.psicologo} valor={`${p.pct}%`} sub={`${p.num}/${p.den}`} />)}
          </div>
          <div>
            <div className="ca-label" style={{ marginBottom: 4 }}>Sesiones promedio por paciente (LTV)</div>
            <div style={big}>{data.ltv.general.promedio} <span style={bigSub}>({data.ltv.general.n} pacientes)</span></div>
            {data.ltv.por_sede.map((s) => <Fila key={"ls" + (s.sede || "x")} etq={`Sede ${s.sede_label}`} valor={s.promedio} sub={`${s.n} pac.`} />)}
            {data.ltv.por_psicologo.map((p) => <Fila key={"lp" + p.psicologo} etq={p.psicologo} valor={p.promedio} sub={`${p.n} pac.`} />)}
          </div>
          <div style={{ fontSize: 11.5, color: "var(--muted)", lineHeight: 1.5 }}>
            Consulta = leads en evaluando/pendiente de pago/inició proceso. Proceso = inició proceso (ganado). LTV = N° de sesión promedio de pacientes con sesiones.
          </div>
        </div>
      ))}
    </div>
  );
}

function Marketing({ showToast, onConvertir, esAdmin }) {
  const [leads, setLeads] = useState([]);
  const [rep, setRep] = useState(null);
  const [medicos, setMedicos] = useState([]);
  const [cfg, setCfg] = useState(null);
  const [anuncios, setAnuncios] = useState([]);
  const [copiado, setCopiado] = useState("");
  const [probando, setProbando] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [creando, setCreando] = useState(false);
  const [editandoLead, setEditandoLead] = useState(null);
  const [filtroSedeLead, setFiltroSedeLead] = useState("");
  const [filtroEstadoLead, setFiltroEstadoLead] = useState("");
  const [desdeLead, setDesdeLead] = useState("");
  const [hastaLead, setHastaLead] = useState("");
  const [buscaLead, setBuscaLead] = useState("");
  const leadsFiltrados = leads.filter((l) => {
    if (filtroSedeLead && l.sede !== filtroSedeLead) return false;
    if (filtroEstadoLead && l.estado !== filtroEstadoLead) return false;
    if (desdeLead && (l.creado_iso || "") < desdeLead) return false;
    if (hastaLead && (l.creado_iso || "") > hastaLead) return false;
    const q = buscaLead.trim().toLowerCase();
    if (q) {
      const dig = q.replace(/\D/g, "");
      const enNombre = (l.nombre || "").toLowerCase().includes(q);
      const enTel = dig && (l.telefono || "").replace(/\D/g, "").includes(dig);
      const enCorreo = (l.email || "").toLowerCase().includes(q);
      if (!enNombre && !enTel && !enCorreo) return false;
    }
    return true;
  });
  const [pauta, setPauta] = useState({ sede: "lima", desde: "", hasta: "", data: null, cargando: false });
  const origen = window.location.origin;

  async function cargar() {
    const [l, r, m, c, an] = await Promise.all([
      api.leads(), api.reportesLeads(), api.medicos(), api.captacionConfig(), api.anuncios(),
    ]);
    setLeads(l); setRep(r); setMedicos(m); setCfg(c); setAnuncios(an);
  }

  async function generarPauta() {
    setPauta((p) => ({ ...p, cargando: true }));
    try {
      const d = await api.reportePauta({ sede: pauta.sede, desde: pauta.desde, hasta: pauta.hasta });
      setPauta((p) => ({ ...p, data: d, cargando: false }));
    } catch (err) { showToast("Error: " + err.message); setPauta((p) => ({ ...p, cargando: false })); }
  }
  async function agregarAnuncio(data) {
    try { await api.crearAnuncio(data); await cargar(); showToast("Anuncio agregado ✓"); }
    catch (err) { showToast("Error: " + err.message); }
  }
  async function quitarAnuncio(id) {
    if (!window.confirm("¿Eliminar este anuncio?")) return;
    try { await api.eliminarAnuncio(id); await cargar(); }
    catch (err) { showToast("Error: " + err.message); }
  }
  async function guardarLead(data) {
    try {
      if (data.id) await api.actualizarLead(data.id, data); else await api.crearLead(data);
      await cargar(); setCreando(false); setEditandoLead(null);
      showToast(data.id ? "Lead actualizado ✓" : "Lead captado ✓");
    } catch (err) {
      // Número repetido: no cerramos el modal; dejamos el número en el buscador
      // para que encuentren el lead que ya existe.
      if (err.status === 409) { setBuscaLead((data.telefono || "").trim()); showToast(err.message); }
      else showToast("Error: " + err.message);
    }
  }
  async function borrarLead(lead) {
    if (!window.confirm(`¿Eliminar el lead "${lead.nombre}"? Se usa para quitar duplicados (ej. el mismo que llegó por IG y WhatsApp).`)) return;
    try { await api.eliminarLead(lead.id); await cargar(); showToast("Lead eliminado"); }
    catch (err) { showToast("Error: " + err.message); }
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
    try { await api.actualizarLead(lead.id, { medico: medicoId || null }); await cargar(); showToast("Psicólogo asignado ✓"); }
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
  async function seguimientoLead(lead) {
    const nota = window.prompt(`Seguimiento de ${lead.nombre} — ¿qué pasó? (opcional)`);
    if (nota === null) return; // canceló
    try { await api.leadSeguimiento(lead.id, nota.trim()); await cargar(); showToast("Seguimiento registrado ✓"); }
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
          <div className="ca-sub">Leads, embudo y cierre por psicólogo</div>
        </div>
        <div style={{ display: "flex", gap: 9, alignItems: "center" }}>
          <ExportBtns nombre="leads" titulo="Captación · Leads" disabled={leads.length === 0}
            headers={["Nombre", "Telefono", "Fuente", "Subfuente", "Pauta", "Campaña", "Especialidad", "Psicologo", "Estado", "Creado"]}
            filas={leads.map((l) => [l.nombre, l.telefono, l.fuente_label, l.subfuente || "", l.es_pauta ? "Si" : "No", l.campania, l.especialidad, l.medico_nombre, l.estado_label, l.creado])} />
          <button className="ca-btn" onClick={() => setCreando(true)}>
            <Plus size={16} strokeWidth={2.2} /> Captar lead
          </button>
        </div>
      </div>

      <ReporteCierreMkt showToast={showToast} />

      {/* ---- Generador del reporte de pauta (listo para WhatsApp) ---- */}
      <div className="ca-card" style={{ marginTop: 22 }}>
        <div className="ca-secth" style={{ marginTop: 0 }}>Generar reporte de pauta</div>
        <div style={{ display: "flex", gap: 10, alignItems: "flex-end", flexWrap: "wrap", marginBottom: 12 }}>
          <div>
            <div className="ca-label">Sede</div>
            <select className="ca-input" value={pauta.sede} onChange={(e) => setPauta((p) => ({ ...p, sede: e.target.value }))}>
              <option value="">Todas</option>
              <option value="piura">Piura</option>
              <option value="lima">Lima</option>
            </select>
          </div>
          <div><div className="ca-label">Desde</div><input className="ca-input" type="date" value={pauta.desde} onChange={(e) => setPauta((p) => ({ ...p, desde: e.target.value }))} /></div>
          <div><div className="ca-label">Hasta</div><input className="ca-input" type="date" value={pauta.hasta} onChange={(e) => setPauta((p) => ({ ...p, hasta: e.target.value }))} /></div>
          <button className="ca-btn" onClick={generarPauta} disabled={pauta.cargando}>
            <FileText size={15} strokeWidth={2} /> {pauta.cargando ? "Generando…" : "Generar"}
          </button>
        </div>
        {pauta.data ? (
          <>
            <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 6 }}>
              <button className="ca-mini" onClick={() => copiar(pauta.data.texto, "pauta")}>
                <Copy size={13} strokeWidth={2} /> {copiado === "pauta" ? "¡Copiado!" : "Copiar para WhatsApp"}
              </button>
            </div>
            <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit", fontSize: 13.5, lineHeight: 1.55, background: "var(--accent-soft)", borderRadius: 10, padding: 14, margin: 0 }}>{pauta.data.texto}</pre>
          </>
        ) : (
          <div className="ca-pmeta">Elige sede y fechas; el sistema arma el reporte (leads, consultas por origen, embudo, procesos y publicidad) listo para pegar en WhatsApp.</div>
        )}
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

          <h2 className="ca-secth" style={{ marginTop: 26 }}>Página de auto-agendamiento</h2>
          <div className="ca-card">
            <div style={{ fontSize: 13.5, color: "var(--ink-soft)", lineHeight: 1.55, marginBottom: 14 }}>
              Comparte este enlace en tu <strong>bio de Instagram</strong>, tu <strong>estado de WhatsApp</strong> o tu web.
              El paciente elige psicólogo y un <strong>horario libre</strong> y reserva solo: si es <strong>nuevo</strong>,
              entra como lead + una cita tentativa para que coordinación la confirme; si <strong>ya es paciente</strong>,
              la cita entra directo a la agenda.
            </div>
            <UrlBox label="Enlace para tus pacientes" url={origen + "/agendar/" + cfg.token}
              onCopy={() => copiar(origen + "/agendar/" + cfg.token, "agendar")} copiado={copiado === "agendar"} />
            <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 12, lineHeight: 1.5 }}>
              Los horarios que ve el paciente salen del <strong>horario semanal</strong> de cada psicólogo
              (se configura en Profesionales). Un psicólogo sin horario semanal no aparece en la página.
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

      <h2 className="ca-secth" style={{ marginTop: 30 }}>Cierre por psicólogo</h2>
      <table className="ca-tbl">
        <thead>
          <tr>
            <th>Psicólogo</th>
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
        Cuántos leads llegan por cada psicólogo (de pauta u orgánico) y cuántos cierran.
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

      <h2 className="ca-secth" style={{ marginTop: 30 }}>Anuncios de pauta ({anuncios.length})</h2>
      <div className="ca-card">
        <AnuncioForm onSave={agregarAnuncio} />
        {anuncios.length > 0 && (
          <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 9 }}>
            {anuncios.map((a) => (
              <div key={a.id} style={{ display: "flex", alignItems: "flex-start", gap: 12, padding: "11px 13px", border: "1px solid var(--line)", borderRadius: 11, background: "var(--bg)" }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 13.8, lineHeight: 1.4 }}>{a.nombre}</div>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginTop: 5 }}>
                    <span style={{ fontSize: 11.5, fontWeight: 600, padding: "1px 9px", borderRadius: 999, background: "#EEF2EC", color: "#4B6B4E" }}>{a.plataforma_label}</span>
                    {a.sede_label && <span style={{ fontSize: 11.5, fontWeight: 600, padding: "1px 9px", borderRadius: 999, background: "#EEF2EC", color: "#4B6B4E" }}>{a.sede_label}</span>}
                    <span style={{ fontSize: 11.5, fontWeight: 700, padding: "1px 9px", borderRadius: 999, background: a.n_leads ? "#E1F2E8" : "var(--line)", color: a.n_leads ? "#2E7D52" : "var(--muted)" }}>{a.n_leads} lead{a.n_leads === 1 ? "" : "s"}</span>
                    {a.link && <a href={a.link} target="_blank" rel="noreferrer" style={{ color: "var(--accent)", fontSize: 12.5, fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 3 }}><ExternalLink size={12} strokeWidth={2} /> ver anuncio</a>}
                  </div>
                </div>
                <button className="ca-iconbtn" title="Eliminar anuncio" onClick={() => quitarAnuncio(a.id)}><Trash2 size={14} strokeWidth={2} /></button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginTop: 30 }}>
        <h2 className="ca-secth" style={{ marginTop: 0 }}>Leads ({leadsFiltrados.length})</h2>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <div style={{ position: "relative" }}>
            <Search size={15} strokeWidth={2} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--muted)" }} />
            <input className="ca-input" style={{ width: 190, padding: "6px 10px 6px 32px" }} value={buscaLead} onChange={(e) => setBuscaLead(e.target.value)} placeholder="Buscar por número o nombre" />
          </div>
          <div className="ca-seg">
            {[["", "Todas"], ["lima", "Lima"], ["piura", "Piura"]].map(([v, l]) => (
              <button key={v || "todas"} className={filtroSedeLead === v ? "on" : ""} onClick={() => setFiltroSedeLead(v)}>{l}</button>
            ))}
          </div>
          <select className="ca-input" style={{ width: "auto", padding: "6px 10px" }} value={filtroEstadoLead} onChange={(e) => setFiltroEstadoLead(e.target.value)}>
            <option value="">Todos los estados</option>
            {LEAD_ESTADOS.map((s) => <option key={s.v} value={s.v}>{s.l}</option>)}
          </select>
          <input className="ca-input" type="date" style={{ width: "auto", padding: "6px 8px" }} value={desdeLead} onChange={(e) => setDesdeLead(e.target.value)} title="Desde (fecha de llegada)" />
          <input className="ca-input" type="date" style={{ width: "auto", padding: "6px 8px" }} value={hastaLead} onChange={(e) => setHastaLead(e.target.value)} title="Hasta" />
          {(filtroEstadoLead || desdeLead || hastaLead || buscaLead) && <button className="ca-fchip" onClick={() => { setFiltroEstadoLead(""); setDesdeLead(""); setHastaLead(""); setBuscaLead(""); }}>Limpiar</button>}
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 13, flexWrap: "wrap", fontSize: 11.5, color: "var(--muted)", margin: "2px 0 12px 2px" }}>
        <span style={{ fontWeight: 600, color: "var(--ink-soft)" }}>Punto de color = días sin contactar:</span>
        {["verde", "amarillo", "naranja", "rojo"].map((k) => (
          <span key={k} style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
            <span style={{ width: 9, height: 9, borderRadius: 999, background: LEAD_SEM[k].c, display: "inline-block" }} />{LEAD_SEM[k].l}
          </span>
        ))}
      </div>
      {leadsFiltrados.length === 0 ? (
        <div className="ca-empty">No hay leads con ese filtro.</div>
      ) : (
        leadsFiltrados.map((lead) => {
          const sem = LEAD_SEM[lead.semaforo];
          return (
          <div key={lead.id} className="ca-row" style={(lead.agendo_consulta === false || lead.recontacto_vencido) ? { borderLeft: "3px solid #D85656" } : undefined}>
            {sem ? <span title={`${sem.l} (${lead.dias_sin_contacto}d sin contacto)`} style={{ width: 10, height: 10, borderRadius: 999, background: sem.c, flexShrink: 0, alignSelf: "center" }} /> : <span style={{ width: 10, flexShrink: 0 }} />}
            <div style={{ flex: 1, minWidth: 160 }}>
              <div className="ca-pname">
                {lead.nombre}
                {lead.es_pauta && (
                  <span style={{ marginLeft: 8, fontSize: 10.5, background: "#EDE6F4", color: "#6B4E96", padding: "1px 7px", borderRadius: 999, fontWeight: 600, verticalAlign: "middle" }}>PAUTA</span>
                )}
                {lead.agendo_consulta === false && (
                  <span style={{ marginLeft: 8, fontSize: 10.5, background: "#F7E5E5", color: "#B4564E", padding: "1px 7px", borderRadius: 999, fontWeight: 600, verticalAlign: "middle" }}>SIN AGENDAR</span>
                )}
                {lead.agendo_consulta === true && lead.fecha_consulta && (
                  <span style={{ marginLeft: 8, fontSize: 10.5, background: "#E9F1ED", color: "#3E7A65", padding: "1px 7px", borderRadius: 999, fontWeight: 600, verticalAlign: "middle" }}>📅 {lead.fecha_consulta}{lead.hora_consulta ? ` · ${String(lead.hora_consulta).slice(0, 5)}` : ""}</span>
                )}
                {lead.estado === "seguimiento" && lead.seguimiento_frecuencia_label && (
                  <span style={{ marginLeft: 8, fontSize: 10.5, background: "#E1F2E8", color: "#2E7D52", padding: "1px 7px", borderRadius: 999, fontWeight: 600, verticalAlign: "middle" }}>🔁 Seguimiento {lead.seguimiento_frecuencia_label.toLowerCase()}</span>
                )}
                {lead.estado === "recontacto" && lead.recontacto_fecha && (
                  <span style={{ marginLeft: 8, fontSize: 10.5, background: lead.recontacto_vencido ? "#F7E5E5" : "#EAE6F2", color: lead.recontacto_vencido ? "#B4564E" : "#6B5B9C", padding: "1px 7px", borderRadius: 999, fontWeight: 600, verticalAlign: "middle" }}>⏰ {lead.recontacto_vencido ? "Recontactar hoy" : `Recontactar ${lead.recontacto_fecha}`}</span>
                )}
              </div>
              <div className="ca-pmeta">
                {lead.sede_label ? `${lead.sede_label} · ` : ""}{lead.fuente_label}{lead.subfuente ? ` › ${lead.subfuente}` : ""}{lead.tipo_servicio_label ? ` · ${lead.tipo_servicio_label}` : ""}{lead.anuncio_nombre ? ` · 📣 ${lead.anuncio_nombre.length > 32 ? lead.anuncio_nombre.slice(0, 32).trim() + "…" : lead.anuncio_nombre}` : ""}{lead.medico_nombre ? ` · ${lead.medico_nombre}` : ""}
              </div>
            </div>
            <select className="ca-tplsel" value={lead.estado} onChange={(ev) => moverEstado(lead, ev.target.value)}
              style={{ fontWeight: 600, background: (LEAD_ESTADO_COLOR[lead.estado] || {}).bg, color: (LEAD_ESTADO_COLOR[lead.estado] || {}).fg }}>
              {LEAD_ESTADOS.map((s) => <option key={s.v} value={s.v}>{s.l}</option>)}
            </select>
            {!lead.paciente_nombre && (
              <button className="ca-mini wa" title="Registrar seguimiento" onClick={() => seguimientoLead(lead)}><MessageCircle size={13} strokeWidth={2} /> Seguimiento</button>
            )}
            <button className="ca-iconbtn" title="Editar lead" onClick={() => setEditandoLead(lead)}><Pencil size={14} strokeWidth={2} /></button>
            {lead.paciente_nombre ? (
              <Tag colors={LEAD_ESTADO_COLOR.ganado}>Ya es paciente</Tag>
            ) : (
              <button className="ca-mini" onClick={() => convertir(lead)}>
                <UserPlus size={13} strokeWidth={2} /> Convertir
              </button>
            )}
            {esAdmin && <button className="ca-iconbtn" title="Eliminar lead (solo gerencia)" onClick={() => borrarLead(lead)}><Trash2 size={14} strokeWidth={2} /></button>}
          </div>
          );
        })
      )}

      {(creando || editandoLead) && (
        <CrearLeadModal lead={editandoLead} medicos={medicos} anuncios={anuncios}
          onClose={() => { setCreando(false); setEditandoLead(null); }} onSave={guardarLead} />
      )}
    </div>
  );
}

function AnuncioForm({ onSave }) {
  const [nombre, setNombre] = useState("");
  const [link, setLink] = useState("");
  const [plataforma, setPlataforma] = useState("instagram");
  const [sede, setSede] = useState("ambas");
  const PLATS = [{ v: "instagram", l: "Instagram" }, { v: "facebook", l: "Facebook" }, { v: "tiktok", l: "TikTok" }, { v: "otro", l: "Otro" }];
  const SEDES_A = [{ v: "ambas", l: "Todas las sedes" }, { v: "lima", l: "Lima" }, { v: "piura", l: "Piura" }];
  return (
    <div style={{ display: "flex", gap: 9, alignItems: "flex-end", flexWrap: "wrap" }}>
      <div style={{ flex: 2, minWidth: 160 }}><div className="ca-label">Anuncio / publicación</div><input className="ca-input" value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder='ej. "reaccionas y luego te arrepientes"' /></div>
      <div style={{ flex: 2, minWidth: 160 }}><div className="ca-label">Link (opcional)</div><input className="ca-input" value={link} onChange={(e) => setLink(e.target.value)} placeholder="https://instagram.com/p/…" /></div>
      <div style={{ flex: 1, minWidth: 110 }}><div className="ca-label">Plataforma</div><select className="ca-input" value={plataforma} onChange={(e) => setPlataforma(e.target.value)}>{PLATS.map((p) => <option key={p.v} value={p.v}>{p.l}</option>)}</select></div>
      <div style={{ flex: 1, minWidth: 120 }}><div className="ca-label">Sede</div><select className="ca-input" value={sede} onChange={(e) => setSede(e.target.value)}>{SEDES_A.map((s) => <option key={s.v} value={s.v}>{s.l}</option>)}</select></div>
      <button className="ca-btn" style={{ opacity: nombre.trim() ? 1 : 0.5, pointerEvents: nombre.trim() ? "auto" : "none" }}
        onClick={() => { onSave({ nombre: nombre.trim(), link: link.trim(), plataforma, sede }); setNombre(""); setLink(""); }}>
        <Plus size={15} strokeWidth={2.2} /> Agregar
      </button>
    </div>
  );
}

function CrearLeadModal({ lead, medicos, anuncios, onClose, onSave }) {
  const [f, setF] = useState({
    nombre: lead?.nombre || "",
    telefono: lead?.telefono && lead.telefono !== "—" ? lead.telefono : "",
    email: lead?.email || "",
    fecha_llegada: lead?.creado_iso || HOY_ISO,
    sede: lead?.sede || "lima",
    fuente: lead?.fuente || "tiktok_ads",
    subfuente: lead?.subfuente || "",
    fuente_otro: lead?.fuente_otro || "",
    es_pauta: lead ? lead.es_pauta : true,
    anuncio: lead?.anuncio || "",
    es_pareja: lead?.es_pareja || false,
    estado: lead?.estado || "nuevo",
    agendo_consulta: lead?.agendo_consulta ?? null,
    fecha_consulta: lead?.fecha_consulta || "",
    hora_consulta: lead?.hora_consulta || "",
    fecha_cierre: lead?.fecha_cierre || "",
    seguimiento_frecuencia: lead?.seguimiento_frecuencia || "",
    recontacto_fecha: lead?.recontacto_fecha || "",
    campania: lead?.campania || "",
    especialidad: lead?.especialidad || Object.keys(SPECIALTY)[0],
    medico: lead?.medico || "",
    tipo_servicio: lead?.tipo_servicio || "",
    motivo_consulta: lead?.motivo_consulta || "",
    resumen_conversacion: lead?.resumen_conversacion || "",
    objeciones: lead?.objeciones || "",
    observaciones: lead?.observaciones || "",
  });
  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));
  const setChk = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.checked }));
  // Al cambiar el origen: limpia la subfuente y ajusta «pauta» según el origen.
  const setFuente = (e) => { const v = e.target.value; setF((p) => ({ ...p, fuente: v, subfuente: "", es_pauta: FUENTES_PAUTA.includes(v) })); };
  const subOpciones = SUBFUENTES[f.fuente] || [];
  const esFuentePauta = FUENTES_PAUTA.includes(f.fuente);
  // Si se edita un lead con un origen antiguo (no listado), se agrega para no perderlo.
  const fuentesOpciones = FUENTES.some((x) => x.v === f.fuente)
    ? FUENTES
    : [{ v: f.fuente, l: lead?.fuente_label || f.fuente }, ...FUENTES];
  const canSave = f.nombre.trim().length > 0;
  const anunciosActivos = (anuncios || []).filter((a) => a.activo);

  function guardar() {
    onSave({
      ...(lead?.id ? { id: lead.id } : {}),
      nombre: f.nombre.trim(), telefono: f.telefono.trim(), email: f.email.trim(),
      fecha_llegada: f.fecha_llegada || null, sede: f.sede, fuente: f.fuente,
      subfuente: f.fuente === "referido" ? f.subfuente.trim() : ((SUBFUENTES[f.fuente] || []).includes(f.subfuente) ? f.subfuente : ""),
      fuente_otro: ["otro", "convenio", "alianza"].includes(f.fuente) ? f.fuente_otro.trim() : "",
      es_pauta: esFuentePauta ? f.es_pauta : false,
      anuncio: esFuentePauta && f.es_pauta && f.anuncio ? Number(f.anuncio) : null, es_pareja: f.es_pareja,
      estado: f.estado, agendo_consulta: f.agendo_consulta,
      seguimiento_frecuencia: f.estado === "seguimiento" ? f.seguimiento_frecuencia : "",
      recontacto_fecha: f.estado === "recontacto" ? (f.recontacto_fecha || null) : null,
      fecha_consulta: f.agendo_consulta === false ? null : (f.fecha_consulta || null),
      hora_consulta: f.agendo_consulta === false ? null : (f.hora_consulta || null), fecha_cierre: f.fecha_cierre || null,
      campania: f.campania.trim(), especialidad: f.especialidad, medico: f.medico ? Number(f.medico) : null,
      tipo_servicio: f.tipo_servicio, motivo_consulta: f.motivo_consulta.trim(),
      resumen_conversacion: f.resumen_conversacion.trim(), objeciones: f.objeciones.trim(),
      observaciones: f.observaciones.trim(),
    });
  }

  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 460, maxHeight: "88vh", overflowY: "auto" }} onClick={(ev) => ev.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <strong style={{ fontSize: 16 }}>{lead ? "Editar lead" : "Captar lead"}</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>
        <div style={{ marginBottom: 12 }}>
          <div className="ca-label">Nombre</div>
          <input className="ca-input" value={f.nombre} onChange={set("nombre")} placeholder="Nombre del interesado" autoFocus />
        </div>
        <div style={{ display: "flex", gap: 11, marginBottom: 12 }}>
          <div style={{ flex: 1.4 }}><div className="ca-label">Teléfono</div><input className="ca-input" value={f.telefono} onChange={set("telefono")} placeholder="987 654 321" /></div>
          <div style={{ flex: 1 }}><div className="ca-label">Sede</div><select className="ca-input" value={f.sede} onChange={set("sede")}><option value="">—</option>{SEDES.map((s) => <option key={s.v} value={s.v}>{s.l}</option>)}</select></div>
        </div>
        <div style={{ display: "flex", gap: 11, marginBottom: 12 }}>
          <div style={{ flex: 1.4 }}><div className="ca-label">Correo <span style={{ color: "var(--muted)", fontWeight: 400 }}>(opcional)</span></div><input className="ca-input" value={f.email} onChange={set("email")} placeholder="correo@ejemplo.com" inputMode="email" /></div>
          <div style={{ flex: 1 }}><div className="ca-label">Llegó el</div><input className="ca-input" type="date" value={f.fecha_llegada} onChange={set("fecha_llegada")} title="Fecha en que llegó el lead (para leads antiguos o fuera de horario)" /></div>
        </div>
        <div style={{ display: "flex", gap: 11, marginBottom: 12 }}>
          <div style={{ flex: 1 }}><div className="ca-label">Origen</div><select className="ca-input" value={f.fuente} onChange={setFuente}>{fuentesOpciones.map((x) => <option key={x.v} value={x.v}>{x.l}</option>)}</select></div>
          <div style={{ flex: 1 }}><div className="ca-label">Etapa</div><select className="ca-input" value={f.estado} onChange={set("estado")}>{LEAD_ESTADOS.map((s) => <option key={s.v} value={s.v}>{s.l}</option>)}</select></div>
        </div>
        {f.fuente === "referido" ? (
          <div style={{ marginBottom: 12 }}>
            <div className="ca-label">¿Quién refirió?</div>
            <input className="ca-input" value={f.subfuente} onChange={set("subfuente")} placeholder="Nombre de quien lo refirió" />
          </div>
        ) : subOpciones.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            <div className="ca-label">Canal / subfuente</div>
            <select className="ca-input" value={f.subfuente} onChange={set("subfuente")}>
              <option value="">—</option>
              {subOpciones.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        )}
        {["otro", "convenio", "alianza"].includes(f.fuente) && (
          <div style={{ marginBottom: 12 }}>
            <div className="ca-label">{f.fuente === "convenio" ? "¿Cuál convenio?" : f.fuente === "alianza" ? "¿Cuál alianza?" : "¿Cuál otro origen?"}</div>
            <input className="ca-input" value={f.fuente_otro} onChange={set("fuente_otro")}
              placeholder={f.fuente === "convenio" ? "Nombre del convenio" : f.fuente === "alianza" ? "Nombre de la alianza" : "Especifica de dónde vino el lead"} />
          </div>
        )}
        {f.estado === "seguimiento" && (
          <div style={{ marginBottom: 12 }}>
            <div className="ca-label">Frecuencia del seguimiento</div>
            <select className="ca-input" value={f.seguimiento_frecuencia} onChange={set("seguimiento_frecuencia")}>
              {LEAD_FRECUENCIAS.map((x) => <option key={x.v} value={x.v}>{x.l}</option>)}
            </select>
          </div>
        )}
        {f.estado === "recontacto" && (
          <div style={{ marginBottom: 12 }}>
            <div className="ca-label">Recontactar el</div>
            <input className="ca-input" type="date" value={f.recontacto_fecha || ""} onChange={set("recontacto_fecha")} />
            <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>Ej. el lead quiere agendar en quincena — te aparecerá como recordatorio.</div>
          </div>
        )}
        {esFuentePauta && (
          <div style={{ display: "flex", gap: 16, marginBottom: 12, flexWrap: "wrap" }}>
            <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13.5, color: "var(--ink-soft)", cursor: "pointer" }}>
              <input type="checkbox" checked={f.es_pauta} onChange={setChk("es_pauta")} /> Vino de pauta (anuncio pagado)
            </label>
          </div>
        )}
        {esFuentePauta && f.es_pauta && (
          <div style={{ marginBottom: 12 }}>
            <div className="ca-label">Anuncio que lo atrajo</div>
            <select className="ca-input" value={f.anuncio} onChange={set("anuncio")}>
              <option value="">— (sin especificar)</option>
              {anunciosActivos.map((a) => <option key={a.id} value={a.id}>{a.nombre}</option>)}
            </select>
            {anunciosActivos.length === 0 && <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>Aún no has agregado anuncios. Puedes crearlos abajo, en «Generar reporte de pauta».</div>}
          </div>
        )}
        <div style={{ marginBottom: 12 }}>
          <div className="ca-label">¿Agendó consulta?</div>
          <div style={{ display: "flex", gap: 8 }}>
            {[[true, "Sí"], [false, "No"]].map(([v, l]) => {
              const on = f.agendo_consulta === v;
              return (
                <button key={String(v)} type="button"
                  onClick={() => setF((p) => ({ ...p, agendo_consulta: on ? null : v, ...((!on && v === false) ? { fecha_consulta: "" } : {}) }))}
                  className="ca-input" style={{
                    flex: 1, cursor: "pointer", fontWeight: on ? 600 : 400,
                    color: on ? "#fff" : "var(--ink)",
                    background: on ? (v === true ? "var(--accent)" : "#D85656") : "var(--bg)",
                    borderColor: on ? "transparent" : "var(--line)",
                  }}>{l}</button>
              );
            })}
          </div>
        </div>
        <div style={{ display: "flex", gap: 11, marginBottom: 12 }}>
          {f.agendo_consulta === true && (
            <div style={{ flex: 1.4 }}><div className="ca-label">Fecha de la consulta</div><input className="ca-input" type="date" value={f.fecha_consulta || ""} onChange={set("fecha_consulta")} /></div>
          )}
          {f.agendo_consulta === true && (
            <div style={{ flex: 1 }}><div className="ca-label">Hora</div><input className="ca-input" type="time" step={900} value={f.hora_consulta || ""} onChange={set("hora_consulta")} /></div>
          )}
          {f.agendo_consulta === false && (
            <div style={{ flex: 1, alignSelf: "center", fontSize: 12.5, color: "#B4564E" }}>⚠ Quedará marcado «sin agendar» para hacerle seguimiento.</div>
          )}
          <div style={{ flex: 1 }}><div className="ca-label">Inició proceso (fecha)</div><input className="ca-input" type="date" value={f.fecha_cierre || ""} onChange={set("fecha_cierre")} /></div>
        </div>
        <div style={{ display: "flex", gap: 11, marginBottom: 18 }}>
          <div style={{ flex: 1 }}><div className="ca-label">Campaña (opcional)</div><input className="ca-input" value={f.campania} onChange={set("campania")} placeholder="ej. Pauta junio" /></div>
          <div style={{ flex: 1 }}><div className="ca-label">Psicólogo</div><select className="ca-input" value={f.medico} onChange={set("medico")}><option value="">Sin asignar</option>{medicos.map((m) => <option key={m.id} value={m.id}>{m.nombre}</option>)}</select></div>
        </div>
        <div style={{ marginBottom: 12 }}><div className="ca-label">Tipo de servicio</div><select className="ca-input" value={f.tipo_servicio} onChange={set("tipo_servicio")}>{TIPOS_SERVICIO.map((x) => <option key={x.v} value={x.v}>{x.l}</option>)}</select></div>
        <div className="ca-secth" style={{ marginTop: 4, marginBottom: 8, fontSize: 13 }}>Información comercial</div>
        <div style={{ marginBottom: 10 }}><div className="ca-label">Motivo de consulta</div><textarea className="ca-input" rows={2} value={f.motivo_consulta} onChange={set("motivo_consulta")} /></div>
        <div style={{ marginBottom: 10 }}><div className="ca-label">Resumen de la conversación</div><textarea className="ca-input" rows={2} value={f.resumen_conversacion} onChange={set("resumen_conversacion")} placeholder="Útil: las charlas de WhatsApp luego se borran" /></div>
        <div style={{ display: "flex", gap: 11, marginBottom: 16 }}>
          <div style={{ flex: 1 }}><div className="ca-label">Objeciones</div><textarea className="ca-input" rows={2} value={f.objeciones} onChange={set("objeciones")} /></div>
          <div style={{ flex: 1 }}><div className="ca-label">Observaciones</div><textarea className="ca-input" rows={2} value={f.observaciones} onChange={set("observaciones")} /></div>
        </div>
        <div style={{ display: "flex", gap: 9, justifyContent: "flex-end" }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" style={{ opacity: canSave ? 1 : 0.5, pointerEvents: canSave ? "auto" : "none" }} onClick={guardar}>
            {lead ? "Guardar" : "Captar"}
          </button>
        </div>
      </div>
    </div>
  );
}

const MEDIOS_PAGO = [
  { v: "efectivo", l: "Efectivo" }, { v: "yape", l: "Yape" }, { v: "plin", l: "Plin" },
  { v: "tarjeta", l: "Tarjeta" }, { v: "transferencia", l: "Transferencia" },
  { v: "mercado_pago", l: "Mercado Pago" }, { v: "otro", l: "Otro" },
];
const COMPROBANTES = [
  { v: "", l: "Sin comprobante" }, { v: "boleta", l: "Boleta" }, { v: "factura", l: "Factura" },
  { v: "recibo", l: "Recibo x honorarios" }, { v: "nota_venta", l: "Nota de venta" },
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

function NumeroWaCard({ numero, esNuevo, onSaved, onCancel, showToast }) {
  const [sede, setSede] = useState(numero?.sede || "");
  const [phone, setPhone] = useState(numero?.phone_number_id || "");
  const [waba, setWaba] = useState(numero?.waba_id || "");
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);

  async function guardar() {
    if (!phone.trim()) { showToast("Falta el Phone Number ID"); return; }
    if (esNuevo && !token.trim()) { showToast("Falta el Access Token"); return; }
    setBusy(true);
    try {
      const c = await api.guardarWhatsappConfig({
        id: numero?.id, sede, phone_number_id: phone, access_token: token, waba_id: waba,
      });
      setToken(""); onSaved(c);
      showToast(esNuevo ? "Número agregado ✓" : "Número guardado ✓");
    } catch (e) { showToast("Error: " + e.message); }
    finally { setBusy(false); }
  }
  async function eliminar() {
    if (!window.confirm("¿Eliminar este número de WhatsApp?")) return;
    setBusy(true);
    try { const c = await api.borrarWhatsappNumero(numero.id); onSaved(c); showToast("Número eliminado"); }
    catch (e) { showToast("Error: " + e.message); }
    finally { setBusy(false); }
  }

  const help = { fontSize: 12, color: "var(--muted)", marginTop: 6, lineHeight: 1.5 };
  const titulo = esNuevo
    ? "Nuevo número"
    : (numero.sede_display || "Sin sede") + (phone ? ` · ${phone}` : "");

  return (
    <div className="ca-card" style={{ marginBottom: 14, ...(esNuevo ? { border: "1px dashed var(--line)" } : {}) }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <strong style={{ fontSize: 15 }}>{titulo}</strong>
        {!esNuevo && (
          <button className="ca-iconbtn" title="Eliminar número" onClick={eliminar} disabled={busy}>
            <Trash2 size={15} strokeWidth={2} />
          </button>
        )}
      </div>

      <div style={{ marginBottom: 16 }}>
        <div className="ca-label">Sede</div>
        <select className="ca-input" value={sede} onChange={(e) => setSede(e.target.value)}>
          <option value="">(Sin sede)</option>
          <option value="lima">Lima</option>
          <option value="piura">Piura</option>
          <option value="ambas">Ambas sedes</option>
        </select>
      </div>

      <div style={{ marginBottom: 16 }}>
        <div className="ca-label">Phone Number ID <span style={{ color: "#B4564E" }}>*</span></div>
        <input className="ca-input" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="1055543397650352" />
        <div style={help}>Meta Business Suite › WhatsApp › API Setup.</div>
      </div>

      <div style={{ marginBottom: 16 }}>
        <div className="ca-label">Access Token <span style={{ color: "#B4564E" }}>*</span></div>
        <input className="ca-input" type="password" value={token} onChange={(e) => setToken(e.target.value)}
          placeholder={numero?.token_set ? "•••••••• (guardado · escribe uno nuevo para cambiarlo)" : "Pega el token permanente de este número"} />
      </div>

      <div style={{ marginBottom: 18 }}>
        <div className="ca-label">WABA ID <span style={{ color: "var(--muted)", fontWeight: 400 }}>(opcional)</span></div>
        <input className="ca-input" value={waba} onChange={(e) => setWaba(e.target.value)} placeholder="984894134127366" />
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
        {esNuevo && <button className="ca-btn ghost" onClick={onCancel} disabled={busy}>Cancelar</button>}
        <button className="ca-btn" style={{ opacity: busy ? 0.6 : 1, pointerEvents: busy ? "none" : "auto" }} onClick={guardar}>
          {busy ? "Guardando…" : (esNuevo ? "Agregar número" : "Guardar")}
        </button>
      </div>
    </div>
  );
}

// ─── Legal / Contratos (Gerencia) ───────────────────────────────────
const CONTRATO_ESTADOS = [
  { v: "", l: "— Sin definir —" },
  { v: "preparando", l: "Preparando" },
  { v: "entregado", l: "Entregado" },
  { v: "firmado", l: "Firmado" },
];
const CONTRATO_COLOR = {
  preparando: { bg: "#FFF4DA", fg: "#9A7B1E" },
  entregado: { bg: "#E7EEF6", fg: "#3D5C82" },
  firmado: { bg: "#E1F2E8", fg: "#2E7D52" },
};

function dLocal(iso) { if (!iso) return null; const [y, m, d] = iso.split("-").map(Number); return new Date(y, m - 1, d, 12); }
function fmtFecha(iso) { if (!iso) return "—"; const [y, m, d] = iso.split("-"); return `${d}/${m}/${y}`; }
function antiguedad(iso) {
  if (!iso) return "";
  const ini = dLocal(iso), hoy = new Date();
  let meses = (hoy.getFullYear() - ini.getFullYear()) * 12 + (hoy.getMonth() - ini.getMonth());
  if (hoy.getDate() < ini.getDate()) meses--;
  if (meses < 0) return "";
  const a = Math.floor(meses / 12), m = meses % 12;
  return a ? `${a} año${a > 1 ? "s" : ""}${m ? ` ${m}m` : ""}` : `${m} mes${m !== 1 ? "es" : ""}`;
}

function RecordCard({ titulo, items, vacio, alerta }) {
  return (
    <div className="ca-card" style={alerta ? { borderColor: "#F0DDBF" } : undefined}>
      <div className="ca-secth" style={{ marginTop: 0, marginBottom: 8, fontSize: 13.5 }}>{titulo}</div>
      {items.length === 0
        ? <div style={{ color: "var(--muted)", fontSize: 13 }}>{vacio}</div>
        : items.map((t, i) => <div key={i} style={{ fontSize: 13.5, padding: "3px 0" }}>{t}</div>)}
    </div>
  );
}

const BUZON_DESEA = [
  { v: "", l: "—" },
  { v: "tener_en_cuenta", l: "Que se tenga en cuenta" },
  { v: "revisar_proceso", l: "Que se revise un proceso" },
  { v: "me_contacten", l: "Que alguien me contacte" },
  { v: "solo_observacion", l: "Que solo quede como observación" },
  { v: "conversar", l: "Que se converse con alguien" },
];
const SUGERENCIA_ESTADO_COLOR = {
  nueva: { bg: "#FCF3D4", fg: "#8A6D14" },
  vista: { bg: "#E7EEF6", fg: "#3D5C82" },
  atendida: { bg: "#E4F3E8", fg: "#1E7D45" },
};

// Herramientas para pacientes + Tips para el psicólogo. La gerencia los edita;
// el equipo (incluido el psicólogo) solo los consulta. Reemplaza el acceso a
// Profesionales para el rol psicólogo.
const RECURSO_TABS = [
  { v: "herramienta", l: "Herramientas para el paciente", icon: FolderOpen, hint: "Materiales, guías y enlaces para compartir con los pacientes." },
  { v: "terapeuta", l: "Herramientas para el terapeuta", icon: Stethoscope, hint: "Recursos clínicos para usar durante la sesión: escalas, dinámicas, materiales de intervención." },
  { v: "manual", l: "Manuales y guías", icon: GraduationCap, hint: "Manuales clínicos, protocolos, guías de intervención, procedimientos internos y material de capacitación." },
  { v: "tip", l: "Autocuidado del terapeuta", icon: HeartPulse, hint: "Contenido de bienestar y autocuidado para el equipo terapéutico." },
  { v: "recordatorio", l: "Recordatorios del equipo", icon: Bell, hint: "Avisos de gerencia (capacitación, supervisión, NPS…) que salen en el inicio del equipo.", soloAdmin: true },
];

function Recursos({ showToast, esAdmin, esMedico }) {
  const tabs = RECURSO_TABS.filter((t) => !t.soloAdmin || esAdmin);
  const [tipo, setTipo] = useState("herramienta");
  const [lista, setLista] = useState(null);
  const [editando, setEditando] = useState(null); // objeto recurso o {tipo} nuevo
  const meta = RECURSO_TABS.find((t) => t.v === tipo);

  const [busca, setBusca] = useState("");
  const [catSel, setCatSel] = useState("");
  const [enviarRec, setEnviarRec] = useState(null); // recurso a enviar por WhatsApp

  function cargar() { setLista(null); api.recursos(tipo).then(setLista).catch(() => setLista([])); }
  useEffect(() => { cargar(); }, [tipo]);
  useEffect(() => { setBusca(""); setCatSel(""); }, [tipo]);

  // Categorías presentes (para los chips) y filtrado por texto + categoría.
  const categorias = useMemo(
    () => [...new Set((lista || []).map((r) => (r.categoria || "").trim()).filter(Boolean))].sort(),
    [lista]
  );
  const visibles = useMemo(() => {
    const q = busca.trim().toLowerCase();
    return (lista || []).filter((r) => {
      if (catSel && (r.categoria || "").trim() !== catSel) return false;
      if (!q) return true;
      return [r.titulo, r.descripcion, r.categoria].some((x) => (x || "").toLowerCase().includes(q));
    });
  }, [lista, busca, catSel]);

  async function guardar(data) {
    try {
      if (data.id) await api.actualizarRecurso(data.id, data);
      else await api.crearRecurso({ ...data, tipo });
      setEditando(null); showToast("Guardado ✓"); cargar();
    } catch (e) { showToast("Error: " + e.message); }
  }
  async function borrar(r) {
    if (!window.confirm(`¿Eliminar "${r.titulo}"?`)) return;
    try { await api.borrarRecurso(r.id); setLista((l) => l.filter((x) => x.id !== r.id)); showToast("Eliminado"); }
    catch (e) { showToast("Error: " + e.message); }
  }
  async function toggleActivo(r) {
    try { await api.actualizarRecurso(r.id, { activo: !r.activo }); setLista((l) => l.map((x) => (x.id === r.id ? { ...x, activo: !r.activo } : x))); }
    catch (e) { showToast("Error: " + e.message); }
  }

  return (
    <div>
      <div className="ca-tophead">
        <div><h1 className="ca-h1">Herramientas</h1><div className="ca-sub">{meta.hint}</div></div>
        {esAdmin && <button className="ca-btn" onClick={() => setEditando({ tipo, titulo: "", descripcion: "", link: "", categoria: "", fijado: false, activo: true })}><Plus size={16} strokeWidth={2.2} /> Agregar</button>}
      </div>

      <div className="ca-seg" style={{ marginTop: 4 }}>
        {tabs.map((t) => (
          <button key={t.v} className={tipo === t.v ? "on" : ""} onClick={() => setTipo(t.v)}>{t.l}</button>
        ))}
      </div>

      {lista && lista.length > 0 && (
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", marginTop: 14 }}>
          <div style={{ position: "relative", flex: 1, minWidth: 220, maxWidth: 380 }}>
            <Search size={15} strokeWidth={2} style={{ position: "absolute", left: 11, top: "50%", transform: "translateY(-50%)", color: "var(--muted)" }} />
            <input className="ca-input" style={{ paddingLeft: 34 }} value={busca} onChange={(e) => setBusca(e.target.value)}
              placeholder={`Buscar por nombre o categoría (ej. ansiedad)…`} />
          </div>
          {categorias.length > 0 && (
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              <button className={`ca-mini${catSel === "" ? " done" : ""}`} onClick={() => setCatSel("")}>Todas</button>
              {categorias.map((c) => (
                <button key={c} className={`ca-mini${catSel === c ? " done" : ""}`} onClick={() => setCatSel(catSel === c ? "" : c)}>{c}</button>
              ))}
            </div>
          )}
        </div>
      )}

      {!lista ? <div className="ca-empty" style={{ marginTop: 18 }}>Cargando…</div> :
        lista.length === 0 ? <div className="ca-empty" style={{ marginTop: 18 }}>Aún no hay {meta.l.toLowerCase()}.{esAdmin ? " Usa «Agregar» para publicar el primero." : ""}</div> :
        visibles.length === 0 ? <div className="ca-empty" style={{ marginTop: 18 }}>Nada coincide con la búsqueda.</div> : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(280px,1fr))", gap: 12, marginTop: 18 }}>
            {visibles.map((r) => (
              <div key={r.id} className="ca-card" style={{ opacity: r.activo ? 1 : 0.55, display: "flex", flexDirection: "column", gap: 6 }}>
                <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                  <meta.icon size={17} strokeWidth={2} style={{ color: "var(--accent)", flexShrink: 0, marginTop: 1 }} />
                  <div style={{ fontWeight: 600, fontSize: 14.5, lineHeight: 1.35, flex: 1 }}>{r.titulo}</div>
                  {!r.activo && <span style={{ fontSize: 10.5, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase" }}>Oculto</span>}
                </div>
                {r.categoria && <span style={{ alignSelf: "flex-start", fontSize: 11.5, fontWeight: 600, padding: "2px 9px", borderRadius: 999, background: "#EEF2EC", color: "#4B6B4E" }}>{r.categoria}</span>}
                {r.descripcion && <div style={{ fontSize: 13, color: "var(--ink-soft)", whiteSpace: "pre-wrap", lineHeight: 1.5 }}>{r.descripcion}</div>}
                <div style={{ display: "flex", gap: 8, marginTop: "auto", paddingTop: 6, flexWrap: "wrap" }}>
                  {r.link && <a className="ca-mini" href={r.link} target="_blank" rel="noreferrer"><ExternalLink size={13} strokeWidth={2} /> Abrir</a>}
                  {!esMedico && (tipo === "herramienta" || tipo === "terapeuta") && r.link && <button className="ca-mini" style={{ color: "#1E7E5A" }} onClick={() => setEnviarRec(r)}><Send size={13} strokeWidth={2} /> Enviar por WhatsApp</button>}
                  {esAdmin && <button className="ca-mini" onClick={() => setEditando(r)}><Pencil size={13} strokeWidth={2} /> Editar</button>}
                  {esAdmin && <button className="ca-mini" onClick={() => toggleActivo(r)}>{r.activo ? "Ocultar" : "Mostrar"}</button>}
                  {esAdmin && <button className="ca-mini danger" onClick={() => borrar(r)}><Trash2 size={13} strokeWidth={2} /></button>}
                </div>
              </div>
            ))}
          </div>
        )}

      {editando && <RecursoModal rec={editando} tabLabel={meta.l} onClose={() => setEditando(null)} onGuardar={guardar} />}
      {enviarRec && <EnviarRecursoModal rec={enviarRec} showToast={showToast} onClose={() => setEnviarRec(null)} />}
    </div>
  );
}

// Coordinadoras/psicólogos: mandar el enlace de una herramienta directo al WhatsApp del paciente.
function EnviarRecursoModal({ rec, showToast, onClose }) {
  const [pacs, setPacs] = useState(null);
  const [busca, setBusca] = useState("");
  const [sel, setSel] = useState(null);
  const [enviando, setEnviando] = useState(false);
  useEffect(() => { api.pacientes().then((ps) => setPacs(ps || [])).catch(() => setPacs([])); }, []);

  const texto = `Hola${sel ? ` ${(sel.nombre || "").split(" ")[0]}` : ""} 🌿 Te comparto *${rec.titulo}*${rec.descripcion ? `\n\n${rec.descripcion}` : ""}\n\n${rec.link}`;
  const visibles = useMemo(() => {
    const q = busca.trim().toLowerCase();
    // OJO: el paciente serializado trae el teléfono en `tel` (no `telefono`).
    return (pacs || []).filter((p) => p.tel && (!q || (p.nombre || "").toLowerCase().includes(q) || (p.tel || "").includes(q))).slice(0, 40);
  }, [pacs, busca]);

  async function enviar() {
    if (!sel) return;
    setEnviando(true);
    try {
      await api.enviarMensajePaciente(sel.id, texto, "manual");
      showToast(`Enviado a ${(sel.nombre || "").split(" ")[0]} ✓`);
      onClose();
    } catch (e) { showToast("Error: " + e.message); setEnviando(false); }
  }

  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
          <strong style={{ fontSize: 16 }}>Enviar por WhatsApp</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>
        <div className="ca-sub" style={{ marginBottom: 14 }}>{rec.titulo}</div>
        {!sel ? (
          <>
            <div style={{ position: "relative", marginBottom: 10 }}>
              <Search size={15} strokeWidth={2} style={{ position: "absolute", left: 11, top: "50%", transform: "translateY(-50%)", color: "var(--muted)" }} />
              <input className="ca-input" style={{ paddingLeft: 34 }} value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar paciente por nombre o teléfono…" autoFocus />
            </div>
            <div style={{ maxHeight: 300, overflowY: "auto", display: "flex", flexDirection: "column", gap: 4 }}>
              {pacs === null ? <div className="ca-empty">Cargando pacientes…</div> :
                visibles.length === 0 ? <div className="ca-empty">{busca ? "Nadie coincide." : "No hay pacientes con teléfono."}</div> :
                visibles.map((p) => (
                  <button key={p.id} className="ca-row-btn" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "9px 11px", borderRadius: 9, border: "1px solid var(--line)", background: "var(--card)", cursor: "pointer", textAlign: "left" }} onClick={() => setSel(p)}>
                    <span style={{ fontWeight: 600, fontSize: 13.5 }}>{p.nombre}</span>
                    <span style={{ fontSize: 12, color: "var(--muted)" }}>{p.tel}</span>
                  </button>
                ))}
            </div>
          </>
        ) : (
          <>
            <div className="ca-card" style={{ background: "var(--bg-soft, #F6F5F2)", marginBottom: 12 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6, display: "flex", justifyContent: "space-between" }}>
                <span>Para: {sel.nombre} · {sel.tel}</span>
                <button className="ca-mini" onClick={() => setSel(null)}>Cambiar</button>
              </div>
              <div style={{ fontSize: 13, color: "var(--ink-soft)", whiteSpace: "pre-wrap", lineHeight: 1.5 }}>{texto}</div>
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
              <button className="ca-btn" disabled={enviando} onClick={enviar}><Send size={15} strokeWidth={2} /> {enviando ? "Enviando…" : "Enviar"}</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function RecursoModal({ rec, tabLabel, onClose, onGuardar }) {
  const [f, setF] = useState({ titulo: rec.titulo || "", descripcion: rec.descripcion || "", link: rec.link || "", categoria: rec.categoria || "", fijado: !!rec.fijado, activo: rec.activo !== false });
  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));
  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <strong style={{ fontSize: 16 }}>{rec.id ? "Editar" : "Nuevo"} · {tabLabel}</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>
        <div style={{ marginBottom: 12 }}><div className="ca-label">Título</div>
          <input className="ca-input" value={f.titulo} onChange={set("titulo")} placeholder="Ej: Guía de respiración para la ansiedad" autoFocus /></div>
        <div style={{ marginBottom: 12 }}><div className="ca-label">Descripción (opcional)</div>
          <textarea className="ca-input" style={{ minHeight: 72, resize: "vertical", lineHeight: 1.5 }} value={f.descripcion} onChange={set("descripcion")} placeholder="¿Para qué sirve? ¿Cuándo usarlo?" /></div>
        <div style={{ display: "flex", gap: 11, marginBottom: 14, flexWrap: "wrap" }}>
          <div style={{ flex: 2, minWidth: 200 }}><div className="ca-label">Enlace (Drive, PDF, video…)</div>
            <input className="ca-input" value={f.link} onChange={set("link")} placeholder="https://…" /></div>
          <div style={{ flex: 1, minWidth: 140 }}><div className="ca-label">Categoría (opcional)</div>
            <input className="ca-input" value={f.categoria} onChange={set("categoria")} placeholder={rec.tipo === "recordatorio" ? "Capacitación, NPS…" : "Ansiedad, Pareja…"} /></div>
        </div>
        {rec.tipo === "recordatorio" && (
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13.5, color: "var(--ink-soft)", cursor: "pointer", marginBottom: 14 }}>
            <input type="checkbox" checked={f.fijado} onChange={(e) => setF((p) => ({ ...p, fijado: e.target.checked }))} /> Fijar arriba en el inicio del equipo
          </label>
        )}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" onClick={() => f.titulo.trim() ? onGuardar({ ...rec, ...f }) : null}>Guardar</button>
        </div>
      </div>
    </div>
  );
}

function Buzon({ showToast, esAdmin }) {
  const [tab, setTab] = useState(esAdmin ? "bandeja" : "dejar");
  const [f, setF] = useState({ area: "", mensaje: "", contexto: "", desea: "", contacto: "" });
  const [anon, setAnon] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [lista, setLista] = useState(null);
  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));
  function cargar() { if (esAdmin) api.sugerencias().then(setLista).catch(() => setLista([])); }
  useEffect(() => { cargar(); }, []);

  async function enviar() {
    if (!f.mensaje.trim()) { showToast("Escribe tu sugerencia"); return; }
    setEnviando(true);
    try {
      await api.crearSugerencia({ ...f, anonimo: anon });
      setF({ area: "", mensaje: "", contexto: "", desea: "", contacto: "" }); setAnon(false);
      showToast("¡Gracias! Tu sugerencia fue enviada ✓");
      if (esAdmin) cargar();
    } catch (e) { showToast("Error: " + e.message); }
    finally { setEnviando(false); }
  }
  async function marcar(s, estado) {
    try { await api.actualizarSugerencia(s.id, { estado }); setLista((l) => l.map((x) => (x.id === s.id ? { ...x, estado } : x))); }
    catch (e) { showToast("Error: " + e.message); }
  }

  return (
    <div>
      <div className="ca-tophead">
        <div><h1 className="ca-h1">Buzón de sugerencias</h1><div className="ca-sub">Un espacio seguro para ideas, sugerencias y observaciones</div></div>
        {esAdmin && (
          <div className="ca-seg">
            <button className={tab === "bandeja" ? "on" : ""} onClick={() => setTab("bandeja")}>Bandeja{lista ? ` (${lista.filter((x) => x.estado === "nueva").length})` : ""}</button>
            <button className={tab === "dejar" ? "on" : ""} onClick={() => setTab("dejar")}>Dejar una</button>
          </div>
        )}
      </div>

      {(!esAdmin || tab === "dejar") ? (
        <div className="ca-card" style={{ maxWidth: 640, marginTop: 18 }}>
          <div style={{ fontSize: 13, color: "var(--muted)", marginBottom: 14, lineHeight: 1.5 }}>
            En Ítaca creemos que los equipos sanos se construyen con diálogo, respeto y escucha real. Cuéntanos ideas, sugerencias, observaciones o propuestas de mejora 🤍
          </div>
          <div style={{ marginBottom: 12 }}><div className="ca-label">¿Sobre qué es? (área / tema)</div>
            <input className="ca-input" value={f.area} onChange={set("area")} placeholder="Organización, comunicación, procesos, clima, coordinación…" /></div>
          <div style={{ marginBottom: 12 }}><div className="ca-label">Tu sugerencia u observación</div>
            <textarea className="ca-input" style={{ minHeight: 90, resize: "vertical", lineHeight: 1.5 }} value={f.mensaje} onChange={set("mensaje")} placeholder="¿Qué estás notando? ¿Qué te gustaría que mejore?" /></div>
          <div style={{ marginBottom: 12 }}><div className="ca-label">¿Tiene que ver con una situación o persona específica? (opcional)</div>
            <textarea className="ca-input" style={{ minHeight: 60, resize: "vertical", lineHeight: 1.5 }} value={f.contexto} onChange={set("contexto")} placeholder="No es para acusar, sino para comprender mejor el contexto." /></div>
          <div style={{ display: "flex", gap: 11, marginBottom: 12, flexWrap: "wrap" }}>
            <div style={{ flex: 2, minWidth: 200 }}><div className="ca-label">¿Qué te gustaría que pase?</div>
              <select className="ca-input" value={f.desea} onChange={set("desea")}>{BUZON_DESEA.map((d) => <option key={d.v} value={d.v}>{d.l}</option>)}</select></div>
            <div style={{ flex: 1.5, minWidth: 160 }}><div className="ca-label">Contacto (si deseas que te contacten)</div>
              <input className="ca-input" value={f.contacto} onChange={set("contacto")} placeholder="Correo / WhatsApp (opcional)" /></div>
          </div>
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13.5, color: "var(--ink-soft)", cursor: "pointer", marginBottom: 16 }}>
            <input type="checkbox" checked={anon} onChange={(e) => setAnon(e.target.checked)} /> Enviar de forma anónima
          </label>
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button className="ca-btn" style={{ opacity: enviando ? 0.6 : 1, pointerEvents: enviando ? "none" : "auto" }} onClick={enviar}>{enviando ? "Enviando…" : "Enviar"}</button>
          </div>
        </div>
      ) : (
        !lista ? <div className="ca-empty" style={{ marginTop: 18 }}>Cargando…</div> :
        lista.length === 0 ? <div className="ca-empty" style={{ marginTop: 18 }}>Aún no hay sugerencias.</div> : (
          <div style={{ marginTop: 18 }}>
            {lista.map((s) => (
              <div key={s.id} className="ca-card" style={{ marginBottom: 12 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
                  <Tag colors={SUGERENCIA_ESTADO_COLOR[s.estado]}>{s.estado_label}</Tag>
                  {s.area && <span style={{ fontSize: 12.5, fontWeight: 600 }}>{s.area}</span>}
                  <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--muted)" }}>{s.autor_nombre} · {s.fecha}</span>
                </div>
                <div style={{ fontSize: 14, whiteSpace: "pre-wrap", lineHeight: 1.5 }}>{s.mensaje}</div>
                {s.contexto && <div style={{ fontSize: 13, color: "var(--ink-soft)", marginTop: 6, whiteSpace: "pre-wrap" }}><b>Contexto:</b> {s.contexto}</div>}
                {(s.desea_label || s.contacto) && <div style={{ fontSize: 12.5, color: "var(--muted)", marginTop: 6 }}>{s.desea_label}{s.contacto ? ` · 📞 ${s.contacto}` : ""}</div>}
                <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                  {s.estado !== "vista" && <button className="ca-mini" onClick={() => marcar(s, "vista")}><Check size={13} strokeWidth={2} /> Vista</button>}
                  {s.estado !== "atendida" && <button className="ca-mini" onClick={() => marcar(s, "atendida")}><Check size={13} strokeWidth={2} /> Atendida</button>}
                </div>
              </div>
            ))}
          </div>
        )
      )}
    </div>
  );
}

function Legal({ showToast }) {
  const [profs, setProfs] = useState(null);
  const [editar, setEditar] = useState(null);
  const [fSede, setFSede] = useState("");
  const [fEstado, setFEstado] = useState("activos"); // activos | inactivos | todos
  function cargar() { api.profesionales().then(setProfs).catch((e) => showToast("Error: " + e.message)); }
  useEffect(() => { cargar(); }, []);

  const rec = useMemo(() => {
    if (!profs) return { cumples: [], aniversarios: [], vencimientos: [] };
    const hoy = new Date(), mesAct = hoy.getMonth(), anioAct = hoy.getFullYear();
    const mesDe = (iso) => (iso ? Number(iso.slice(5, 7)) - 1 : null);
    const cumples = profs.filter((p) => p.fecha_nacimiento && p.activo && mesDe(p.fecha_nacimiento) === mesAct)
      .map((p) => ({ ...p, dia: Number(p.fecha_nacimiento.slice(8, 10)) })).sort((a, b) => a.dia - b.dia);
    const aniversarios = [];
    profs.forEach((p) => {
      if (!p.fecha_ingreso || !p.activo) return;
      const ini = dLocal(p.fecha_ingreso);
      if (ini.getMonth() === mesAct && anioAct > ini.getFullYear())
        aniversarios.push({ ...p, hito: `${anioAct - ini.getFullYear()} año${anioAct - ini.getFullYear() > 1 ? "s" : ""}`, dia: ini.getDate() });
      const seis = new Date(ini); seis.setMonth(seis.getMonth() + 6);
      if (seis.getMonth() === mesAct && seis.getFullYear() === anioAct)
        aniversarios.push({ ...p, hito: "6 meses", dia: seis.getDate() });
    });
    aniversarios.sort((a, b) => a.dia - b.dia);
    const vencimientos = profs.filter((p) => {
      if (!p.contrato_vencimiento || !p.activo) return false;
      return (dLocal(p.contrato_vencimiento) - hoy) / 86400000 <= 45;
    }).sort((a, b) => dLocal(a.contrato_vencimiento) - dLocal(b.contrato_vencimiento));
    return { cumples, aniversarios, vencimientos };
  }, [profs]);

  if (!profs) return <div className="ca-empty" style={{ marginTop: 20 }}>Cargando…</div>;

  const profsFiltrados = profs.filter((p) =>
    (!fSede || p.sede === fSede) &&
    (fEstado === "todos" || (fEstado === "activos" ? p.activo : !p.activo)));

  return (
    <div>
      <div className="ca-tophead">
        <div><h1 className="ca-h1">Legal</h1><div className="ca-sub">Contratos, adendas y datos del equipo</div></div>
        <button className="ca-btn" onClick={() => setEditar({ new: true })}><UserPlus size={16} strokeWidth={2.1} /> Agregar</button>
      </div>

      <div className="ca-fchips" style={{ marginTop: 14 }}>
        {[["", "Todas las sedes"], ["piura", "Piura"], ["lima", "Lima"]].map(([v, l]) => (
          <button key={v || "t"} className={`ca-fchip ${fSede === v ? "on" : ""}`} onClick={() => setFSede(v)}>{l}</button>
        ))}
        <span style={{ width: 10 }} />
        {[["activos", "Activos"], ["inactivos", "Inactivos"], ["todos", "Todos"]].map(([v, l]) => (
          <button key={v} className={`ca-fchip ${fEstado === v ? "on" : ""}`} onClick={() => setFEstado(v)}>{l}</button>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(240px,1fr))", gap: 14, marginTop: 18, marginBottom: 24 }}>
        <RecordCard titulo="🎂 Cumpleaños del mes" vacio="Ninguno este mes"
          items={rec.cumples.map((p) => `${p.nombre} · día ${p.dia}`)} />
        <RecordCard titulo="🎉 Aniversarios del mes" vacio="Ninguno este mes"
          items={rec.aniversarios.map((p) => `${p.nombre} · ${p.hito}`)} />
        <RecordCard titulo="📄 Contratos por vencer" vacio="Nada por vencer (45 días)" alerta
          items={rec.vencimientos.map((p) => `${p.nombre} · ${fmtFecha(p.contrato_vencimiento)}${p.contrato_estado_label ? ` (${p.contrato_estado_label})` : ""}`)} />
      </div>

      <table className="ca-tbl">
        <thead><tr><th>Psicólogo ({profsFiltrados.length})</th><th>Sede</th><th>DNI</th><th>Nacimiento</th><th>Antigüedad</th><th>Vence</th><th>Contrato</th><th className="num">Docs</th></tr></thead>
        <tbody>
          {profsFiltrados.map((p) => (
            <tr key={p.id} style={{ cursor: "pointer" }} onClick={() => setEditar(p)}>
              <td style={{ fontWeight: 500 }}>{p.nombre}{!p.activo && <span style={{ color: "var(--muted)", fontWeight: 400 }}> · inactivo</span>}</td>
              <td>{p.sede_label || "—"}</td>
              <td>{p.dni || "—"}</td>
              <td>{fmtFecha(p.fecha_nacimiento)}</td>
              <td>{antiguedad(p.fecha_ingreso) || "—"}</td>
              <td>{fmtFecha(p.contrato_vencimiento)}</td>
              <td>{p.contrato_estado ? <Tag colors={CONTRATO_COLOR[p.contrato_estado]}>{p.contrato_estado_label}</Tag> : "—"}</td>
              <td className="num">{(p.documentos || []).length}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {editar && <LegalModal prof={editar.new ? null : editar} onClose={() => setEditar(null)} onSaved={cargar} showToast={showToast} />}
    </div>
  );
}

function LegalModal({ prof, onClose, onSaved, showToast }) {
  const nuevo = !prof;
  const [nombre, setNombre] = useState(prof?.nombre || "");
  const [sede, setSede] = useState(prof?.sede || "");
  const [dni, setDni] = useState(prof?.dni || "");
  const [nac, setNac] = useState(prof?.fecha_nacimiento || "");
  const [ingreso, setIngreso] = useState(prof?.fecha_ingreso || "");
  const [vence, setVence] = useState(prof?.contrato_vencimiento || "");
  const [firma, setFirma] = useState(prof?.contrato_ultima_firma || "");
  const [estado, setEstado] = useState(prof?.contrato_estado || "");
  const [horas, setHoras] = useState(prof?.horas_disponibles ?? 0);
  const [docs, setDocs] = useState(prof?.documentos || []);
  const [guardando, setGuardando] = useState(false);
  const [upTipo, setUpTipo] = useState("contrato");
  const [upFecha, setUpFecha] = useState("");
  const [upDesc, setUpDesc] = useState("");
  const [upFile, setUpFile] = useState(null);
  const [subiendo, setSubiendo] = useState(false);

  async function guardar() {
    if (!nombre.trim()) { showToast("Falta el nombre"); return; }
    setGuardando(true);
    const data = {
      nombre: nombre.trim(), sede, dni: dni.trim(),
      fecha_nacimiento: nac || null, fecha_ingreso: ingreso || null,
      contrato_vencimiento: vence || null, contrato_ultima_firma: firma || null,
      contrato_estado: estado, horas_disponibles: Number(horas) || 0,
    };
    try {
      if (nuevo) await api.crearProfesional(data);
      else await api.actualizarProfesional(prof.id, data);
      showToast("Guardado ✓"); onSaved(); onClose();
    } catch (e) { showToast("Error: " + e.message); }
    finally { setGuardando(false); }
  }

  async function subir() {
    if (!upFile) { showToast("Elige un archivo (PDF/imagen)"); return; }
    setSubiendo(true);
    try {
      const d = await api.subirDocumentoLegal({ profesional: prof.id, tipo: upTipo, fecha: upFecha, descripcion: upDesc.trim(), archivo: upFile });
      setDocs((ds) => [d, ...ds]); setUpFile(null); setUpDesc(""); setUpFecha("");
      showToast("Documento subido ✓"); onSaved();
    } catch (e) { showToast("Error: " + e.message); }
    finally { setSubiendo(false); }
  }
  async function borrarDoc(id) {
    if (!window.confirm("¿Eliminar este documento?")) return;
    try { await api.borrarDocumentoLegal(id); setDocs((ds) => ds.filter((d) => d.id !== id)); showToast("Eliminado"); onSaved(); }
    catch (e) { showToast("Error: " + e.message); }
  }

  const campo = { marginBottom: 12 };
  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 520 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <strong style={{ fontSize: 16 }}>{nuevo ? "Agregar al equipo" : nombre}</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>

        <div style={campo}><div className="ca-label">Nombre completo</div>
          <input className="ca-input" value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre y apellidos" /></div>
        <div style={{ display: "flex", gap: 11, ...campo }}>
          <div style={{ flex: 1 }}><div className="ca-label">Sede</div>
            <select className="ca-input" value={sede} onChange={(e) => setSede(e.target.value)}>
              <option value="">—</option><option value="lima">Lima</option><option value="piura">Piura</option>
            </select></div>
          <div style={{ flex: 1 }}><div className="ca-label">DNI</div>
            <input className="ca-input" value={dni} onChange={(e) => setDni(e.target.value)} inputMode="numeric" /></div>
          <div style={{ width: 110 }}><div className="ca-label">Horas/sem</div>
            <input className="ca-input" value={horas} onChange={(e) => setHoras(e.target.value.replace(/[^\d]/g, ""))} inputMode="numeric" /></div>
        </div>
        <div style={{ display: "flex", gap: 11, ...campo }}>
          <div style={{ flex: 1 }}><div className="ca-label">Nacimiento</div>
            <input className="ca-input" type="date" value={nac || ""} onChange={(e) => setNac(e.target.value)} /></div>
          <div style={{ flex: 1 }}><div className="ca-label">Ingreso</div>
            <input className="ca-input" type="date" value={ingreso || ""} onChange={(e) => setIngreso(e.target.value)} /></div>
        </div>

        <div className="ca-secth" style={{ margin: "6px 0 10px" }}>Contrato</div>
        <div style={{ display: "flex", gap: 11, ...campo }}>
          <div style={{ flex: 1 }}><div className="ca-label">Vencimiento</div>
            <input className="ca-input" type="date" value={vence || ""} onChange={(e) => setVence(e.target.value)} /></div>
          <div style={{ flex: 1 }}><div className="ca-label">Última firma</div>
            <input className="ca-input" type="date" value={firma || ""} onChange={(e) => setFirma(e.target.value)} /></div>
          <div style={{ flex: 1 }}><div className="ca-label">Estado</div>
            <select className="ca-input" value={estado} onChange={(e) => setEstado(e.target.value)}>
              {CONTRATO_ESTADOS.map((s) => <option key={s.v} value={s.v}>{s.l}</option>)}
            </select></div>
        </div>

        <div style={{ display: "flex", gap: 9, justifyContent: "flex-end", marginTop: 8, marginBottom: nuevo ? 0 : 18 }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" style={{ opacity: guardando ? 0.6 : 1, pointerEvents: guardando ? "none" : "auto" }} onClick={guardar}>{guardando ? "Guardando…" : "Guardar"}</button>
        </div>

        {!nuevo && (
          <>
            <div className="ca-secth" style={{ margin: "4px 0 10px" }}>Documentos (contrato / adendas)</div>
            {docs.length === 0 ? <div style={{ color: "var(--muted)", fontSize: 13, marginBottom: 10 }}>Aún no hay documentos.</div> : (
              <div style={{ marginBottom: 12 }}>
                {docs.map((d) => (
                  <div key={d.id} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 0", borderTop: "1px solid var(--line)", fontSize: 13.5 }}>
                    <span style={{ width: 78, color: "var(--muted)" }}>{d.tipo_label}</span>
                    <span style={{ flex: 1 }}>{d.descripcion || "—"}{d.fecha ? ` · ${fmtFecha(d.fecha)}` : ""}</span>
                    {d.archivo_url && <a className="ca-mini" href={api.urlDocumentoLegal(d.id)} target="_blank" rel="noreferrer"><Download size={13} strokeWidth={2} /> Ver</a>}
                    <button className="ca-iconbtn" title="Eliminar" onClick={() => borrarDoc(d.id)}><Trash2 size={14} strokeWidth={2} /></button>
                  </div>
                ))}
              </div>
            )}
            <div style={{ border: "1px dashed var(--line)", borderRadius: 10, padding: 12 }}>
              <div style={{ display: "flex", gap: 9, marginBottom: 9, flexWrap: "wrap" }}>
                <select className="ca-input" style={{ width: 130 }} value={upTipo} onChange={(e) => setUpTipo(e.target.value)}>
                  <option value="contrato">Contrato</option><option value="adenda">Adenda</option><option value="otro">Otro</option>
                </select>
                <input className="ca-input" type="date" style={{ width: 150 }} value={upFecha} onChange={(e) => setUpFecha(e.target.value)} />
                <input className="ca-input" style={{ flex: 1, minWidth: 120 }} value={upDesc} onChange={(e) => setUpDesc(e.target.value)} placeholder="Descripción (opcional)" />
              </div>
              <div style={{ display: "flex", gap: 9, alignItems: "center" }}>
                <input type="file" accept=".pdf,image/*" onChange={(e) => setUpFile(e.target.files?.[0] || null)} style={{ flex: 1, fontSize: 13 }} />
                <button className="ca-btn" style={{ opacity: subiendo ? 0.6 : 1, pointerEvents: subiendo ? "none" : "auto" }} onClick={subir}><Paperclip size={14} strokeWidth={2} /> {subiendo ? "Subiendo…" : "Subir"}</button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function ConexionWhatsapp({ showToast }) {
  const [cfg, setCfg] = useState(null);
  const [agregando, setAgregando] = useState(false);

  useEffect(() => {
    api.whatsappConfig().then(setCfg).catch((e) => showToast("Error: " + e.message));
  }, []);

  function copiar(texto, que) {
    navigator.clipboard?.writeText(texto)
      .then(() => showToast(`${que} copiado ✓`))
      .catch(() => showToast("No se pudo copiar"));
  }
  function onSaved(c) { setCfg(c); setAgregando(false); }

  if (!cfg) return <div className="ca-empty" style={{ marginTop: 20 }}>Cargando…</div>;

  const mono = {
    flex: 1, minWidth: 0, fontFamily: "ui-monospace, 'Space Mono', monospace", fontSize: 13,
    padding: "10px 12px", background: "var(--surface, #fff)", border: "1px solid var(--line)",
    borderRadius: 8, overflowX: "auto", whiteSpace: "nowrap", color: "var(--ink)",
  };
  const caja = { border: "1px solid var(--line)", borderRadius: 10, padding: "13px 14px" };
  const help = { fontSize: 12, color: "var(--muted)", marginTop: 6, lineHeight: 1.5 };

  return (
    <div>
      <div className="ca-tophead">
        <div>
          <h1 className="ca-h1">Conexión WhatsApp</h1>
          <div className="ca-sub">WhatsApp Cloud API · Meta</div>
        </div>
      </div>

      <div style={{ maxWidth: 740 }}>
        {/* Datos compartidos por todos los números (se pegan una sola vez en Meta) */}
        <div className="ca-card" style={{ marginBottom: 18 }}>
          <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 14 }}>
            Estos dos datos son los mismos para <strong>todos</strong> los números (misma app de Meta): se pegan una sola vez.
          </div>
          <div style={{ ...caja, marginBottom: 14 }}>
            <div className="ca-label" style={{ marginBottom: 8 }}>Webhook URL</div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <code style={mono}>{cfg.webhook_url}</code>
              <button className="ca-btn ghost" onClick={() => copiar(cfg.webhook_url, "URL")}><Copy size={14} strokeWidth={2} /> Copiar</button>
            </div>
            <div style={help}>Meta Developer Console › Webhooks configuration.</div>
          </div>
          <div style={caja}>
            <div className="ca-label" style={{ marginBottom: 8 }}>Verify Token</div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <code style={mono}>{cfg.verify_token}</code>
              <button className="ca-btn ghost" onClick={() => copiar(cfg.verify_token, "Token")}><Copy size={14} strokeWidth={2} /> Copiar</button>
            </div>
            <div style={help}>Meta Developer Console › Webhooks › Verify Token field.</div>
          </div>
        </div>

        {/* Lista de números */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", margin: "4px 2px 12px" }}>
          <strong style={{ fontSize: 15 }}>Números conectados ({cfg.numeros.length})</strong>
          {!agregando && (
            <button className="ca-btn" onClick={() => setAgregando(true)}><Plus size={15} /> Agregar número</button>
          )}
        </div>

        {cfg.numeros.length === 0 && !agregando && (
          <div className="ca-empty" style={{ marginBottom: 14 }}>Aún no hay números conectados.</div>
        )}

        {cfg.numeros.map((n) => (
          <NumeroWaCard key={n.id} numero={n} esNuevo={false} onSaved={onSaved} showToast={showToast} />
        ))}

        {agregando && (
          <NumeroWaCard key="nuevo" numero={null} esNuevo onSaved={onSaved} onCancel={() => setAgregando(false)} showToast={showToast} />
        )}
      </div>
    </div>
  );
}

function ConsolidadoSoto({ showToast }) {
  const [abierto, setAbierto] = useState(false);
  const [data, setData] = useState(null);
  const [mes, setMes] = useState("");
  const [probando, setProbando] = useState(false);

  async function cargar(m) {
    try {
      const r = await api.sotoResumen(m);
      setData(r);
      if (!m && r?.mes) setMes(r.mes);
    } catch (e) { /* silencioso: si no responde, la sección simplemente no aparece */ }
  }
  useEffect(() => { cargar(""); }, []);

  // Mientras no sepamos el estado, o si Soto NO está conectado, no mostramos nada
  // (sin cuadro vacío). La sección aparece sola cuando se configure SOTO_EXEC_URL.
  if (!data || !data.configurado) return null;

  function cambiarMes(m) { setMes(m); cargar(m); }
  async function probar() {
    setProbando(true);
    try {
      const r = await api.sotoPrueba();
      showToast(r.ok ? "Fila de prueba enviada a Soto ✓ (recuerda borrarla de la hoja)" : "Error: " + r.detalle);
    } catch (e) { showToast("Error: " + e.message); }
    finally { setProbando(false); }
  }

  return (
    <div className="ca-card" style={{ marginBottom: 18, padding: 0, overflow: "hidden" }}>
      <button onClick={() => setAbierto(!abierto)} style={{ width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, padding: "13px 16px", background: "none", border: "none", cursor: "pointer", fontFamily: "inherit" }}>
        <span style={{ display: "flex", alignItems: "center", gap: 9, fontWeight: 600, fontSize: 14.5, color: "var(--ink)" }}>
          <TrendingUp size={16} strokeWidth={2} style={{ color: "var(--accent)" }} /> Consolidado financiero (Soto)
        </span>
        <ChevronDown size={18} style={{ transform: abierto ? "rotate(180deg)" : "none", transition: "transform .2s", color: "var(--muted)" }} />
      </button>
      {abierto && (
        <div style={{ padding: "0 16px 16px" }}>
          {!data.ok ? (
            <div style={{ fontSize: 13, color: "#B4564E", lineHeight: 1.5 }}>
              {data.detalle}
              <div style={{ marginTop: 8 }}><button className="ca-mini" onClick={() => cargar(mes)}>Reintentar</button></div>
            </div>
          ) : (
            <>
              <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 12 }}>
                <select className="ca-input" style={{ width: "auto" }} value={mes} onChange={(e) => cambiarMes(e.target.value)}>
                  {(data.meses || []).map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
                {data.push_enabled
                  ? <span className="ca-vital" style={{ background: "#E9F1ED", color: "#3E7A65" }}>Auto-envío a Soto: ON</span>
                  : <span className="ca-vital" style={{ background: "#F7ECDD", color: "#9C6B2E" }}>Auto-envío a Soto: OFF</span>}
                <button className="ca-mini" disabled={probando} onClick={probar}>{probando ? "Enviando…" : "Probar conexión"}</button>
                {data.dashboard_url && <a className="ca-link" href={data.dashboard_url} target="_blank" rel="noreferrer">Ver tablero completo ↗</a>}
              </div>
              <div className="ca-stats">
                <StatCard label="Ingresos" valor={money(data.ingresos)} color="#4F8A77" />
                <StatCard label="Egresos" valor={money(data.egresos)} color="#B4564E" />
                <StatCard label="Regalías (2.5%)" valor={money(data.regalias)} color="#9C6B2E" />
                <StatCard label="Utilidad" valor={money(data.utilidad)} sub={`Margen ${data.margen}%`} color={data.utilidad >= 0 ? "#3E7A65" : "#B4564E"} />
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
                <span className="ca-vital"><b>Piura</b> {money(data.ing_piura)}</span>
                <span className="ca-vital"><b>Lima</b> {money(data.ing_lima)}</span>
                <span className="ca-vital"><b>{data.n_ingresos}</b> ingresos · <b>{data.n_egresos}</b> egresos</span>
              </div>
              {data.ranking && data.ranking.length > 0 && (
                <>
                  <div className="ca-label" style={{ marginTop: 14, marginBottom: 6 }}>Ranking de psicólogos</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    {data.ranking.map((r, i) => (
                      <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13 }}>
                        <span style={{ color: "var(--muted)", width: 18 }}>{i + 1}</span>
                        <span style={{ flex: 1, textTransform: "capitalize" }}>{r.nombre}</span>
                        <span style={{ fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>{money(r.total)}</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
              <div style={{ fontSize: 11.5, color: "var(--muted)", marginTop: 12 }}>Datos del tablero de Soto (Google Sheets). La utilidad descuenta egresos y regalías (2.5%).</div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// Liquidación de honorarios: cuánto pagar a cada psicólogo según el % de lo
// cobrado en sus sesiones, en un rango de fechas. Solo gerencia.
// ============ ESPACIOS PROFESIONALES (alquiler de consultorios) ============

const ESP_H_INI = 6, ESP_H_FIN = 22, ESP_PX_H = 46; // agenda 6:00–22:00
const ESP_SEDES = [{ v: "lima", l: "Lima" }, { v: "piura", l: "Piura" }];
// Estados del CRM de interesados (color pastel estilo Notion).
const ESP_EST_INT = {
  interesado: { l: "Interesado", bg: "#E1F0FB", fg: "#2A6FA6" },
  visita: { l: "Visita", bg: "#FFF1DA", fg: "#9C6B2E" },
  negociacion: { l: "Negociación", bg: "#EDE6F4", fg: "#6B4E96" },
  activo: { l: "Activo", bg: "#E3F0E8", fg: "#2F6B4F" },
  descartado: { l: "Descartado", bg: "#F3E3E3", fg: "#9C4646" },
};
const ESP_EST_CONT = {
  activo: { l: "Activo", bg: "#E3F0E8", fg: "#2F6B4F" },
  pausado: { l: "Pausado", bg: "#FFF1DA", fg: "#9C6B2E" },
  finalizado: { l: "Finalizado", bg: "#EEEBE6", fg: "#8A8378" },
};
// Colores de la agenda: 2 tonos para distinguir quién ocupa (pedido de Gaby).
const ESP_TIPO = {
  externo: { l: "Externo (alquiler)", bg: "#BCE7F1", fg: "#086F82", bd: "#5FC3D6" },
  conversemos: { l: "Conversemos", bg: "#C6E6D3", fg: "#256045", bd: "#86C4A6" },
};
// Planes del dossier comercial (precio de lanzamiento). Auto-rellenan el contrato.
const ESP_PLANES = [
  { id: "", nombre: "— Personalizado —", modalidad: "por_horas", horas: 0, precio: 0 },
  { id: "hora", nombre: "Hora individual (1 h)", modalidad: "por_horas", horas: 1, precio: 25 },
  { id: "flex1", nombre: "Flexible 1 · 5 h/mes", modalidad: "por_horas", horas: 5, precio: 120 },
  { id: "flex2", nombre: "Flexible 2 · 10 h/mes", modalidad: "por_horas", horas: 10, precio: 230 },
  { id: "flex3", nombre: "Flexible 3 · 20 h/mes", modalidad: "por_horas", horas: 20, precio: 420 },
  { id: "inicio", nombre: "Inicio · 4 h/sem", modalidad: "fijo", horas: 4, precio: 360 },
  { id: "crecimiento", nombre: "Crecimiento · 8 h/sem", modalidad: "fijo", horas: 8, precio: 680 },
  { id: "profesional", nombre: "Profesional · 12 h/sem", modalidad: "fijo", horas: 12, precio: 930 },
  { id: "full", nombre: "Full · 20 h/sem", modalidad: "fijo", horas: 20, precio: 1450 },
];
const espHDec = (t) => { if (!t) return 0; const [h, m] = t.split(":").map(Number); return h + (m || 0) / 60; };
const espHm = (t) => (t || "").slice(0, 5);
// Opciones de hora 06:00–22:00 en pasos de 30 min.
const ESP_HORAS_OP = (() => {
  const out = [];
  for (let h = ESP_H_INI; h <= ESP_H_FIN; h++) { out.push(`${pad2(h)}:00`); if (h < ESP_H_FIN) out.push(`${pad2(h)}:30`); }
  return out;
})();

function EspBadge({ est }) {
  if (!est) return null;
  return <span style={{ background: est.bg, color: est.fg, fontSize: 11.5, fontWeight: 600, padding: "2px 9px", borderRadius: 20, whiteSpace: "nowrap" }}>{est.l}</span>;
}

function EspaciosProfesionales({ showToast }) {
  const [tab, setTab] = useState("agenda");
  const [consultorios, setConsultorios] = useState([]);
  const [contratos, setContratos] = useState([]);

  const recargarConsultorios = () => api.espConsultorios().then(setConsultorios).catch(() => {});
  const recargarContratos = () => api.espContratos().then(setContratos).catch(() => {});
  useEffect(() => { recargarConsultorios(); recargarContratos(); }, []);

  const tabs = [
    { id: "agenda", label: "Agenda de ocupación", icon: Calendar },
    { id: "interesados", label: "Interesados", icon: Users },
    { id: "clientes", label: "Clientes activos", icon: DoorOpen },
    { id: "pagos", label: "Pagos", icon: Receipt },
  ];

  return (
    <div>
      <div className="ca-tophead">
        <div>
          <h1 className="ca-h1">Espacios profesionales</h1>
          <div className="ca-sub">Alquiler de consultorios a profesionales externos (y uso interno de Conversemos)</div>
        </div>
      </div>

      <div style={{ background: "var(--accent-soft)", border: "1px solid #BEE7EF", borderRadius: 12, padding: "12px 15px", margin: "4px 0 16px", fontSize: 13.3, lineHeight: 1.55 }}>
        <div style={{ fontWeight: 600, marginBottom: 5 }}>¿Para qué sirve esta sección?</div>
        Aquí gestionas el <b>alquiler de tus consultorios</b>. Cada pestaña:
        <ul style={{ margin: "6px 0 0", paddingLeft: 20 }}>
          <li><b>Agenda de ocupación</b> — calendario de qué consultorio está ocupado, cuándo y por quién (verde = Conversemos, azul = profesional externo).</li>
          <li><b>Interesados</b> — profesionales que quieren alquilar; desde aquí los conviertes en cliente con contrato.</li>
          <li><b>Clientes activos</b> — los contratos de alquiler vigentes (quién, qué consultorio, condiciones).</li>
          <li><b>Pagos</b> — los cobros del alquiler de cada cliente.</li>
        </ul>
      </div>

      <div className="ca-seg" style={{ marginLeft: 0, marginBottom: 16, flexWrap: "wrap" }}>
        {tabs.map((t) => (
          <button key={t.id} className={tab === t.id ? "on" : ""} onClick={() => setTab(t.id)}>
            <t.icon size={14} strokeWidth={2} style={{ marginRight: 5, verticalAlign: "-2px" }} />{t.label}
          </button>
        ))}
      </div>

      {consultorios.length === 0 ? (
        <div className="ca-empty">No hay consultorios registrados. Créalos en la pestaña Agenda de ocupación.</div>
      ) : null}

      {tab === "agenda" && <EspAgenda showToast={showToast} consultorios={consultorios} contratos={contratos} recargarConsultorios={recargarConsultorios} />}
      {tab === "interesados" && <EspInteresados showToast={showToast} onContrato={() => setTab("clientes")} recargarContratos={recargarContratos} />}
      {tab === "clientes" && <EspContratos showToast={showToast} consultorios={consultorios} contratos={contratos} recargarContratos={recargarContratos} />}
      {tab === "pagos" && <EspPagos showToast={showToast} contratos={contratos} />}
    </div>
  );
}

// ---- Agenda de ocupación (día / semana / mes) ----
function EspAgenda({ showToast, consultorios, contratos, recargarConsultorios }) {
  const [sede, setSede] = useState("lima");
  const [vista, setVista] = useState("dia");
  const [fecha, setFecha] = useState(HOY_ISO);
  const [reservas, setReservas] = useState([]);
  const [nueva, setNueva] = useState(null);
  const [nuevoConsul, setNuevoConsul] = useState(false);

  const consSede = useMemo(() => consultorios.filter((c) => c.sede === sede && c.activo), [consultorios, sede]);

  const rango = useMemo(() => {
    if (vista === "dia") return [fecha, fecha];
    if (vista === "semana") { const s = semanaDe(fecha); return [s[0], s[6]]; }
    const m = mesDe(fecha); return [m[0], m[m.length - 1]];
  }, [vista, fecha]);

  function cargar() {
    api.espReservas({ sede, desde: rango[0], hasta: rango[1] }).then(setReservas).catch((e) => showToast("Error: " + e.message));
  }
  useEffect(() => { cargar(); }, [sede, rango[0], rango[1]]);

  const irAtras = () => setFecha(vista === "mes" ? sumarMeses(fecha, -1) : sumarDias(fecha, vista === "semana" ? -7 : -1));
  const irAdelante = () => setFecha(vista === "mes" ? sumarMeses(fecha, 1) : sumarDias(fecha, vista === "semana" ? 7 : 1));
  const subt = vista === "semana" ? `${labelNumMes(rango[0])} – ${labelNumMes(rango[1])}` : vista === "mes" ? labelMes(fecha) : labelLargo(fecha);

  async function borrar(id) {
    if (!window.confirm("¿Quitar esta reserva del calendario?")) return;
    try { await api.espBorrarReserva(id); cargar(); showToast("Reserva eliminada"); }
    catch (e) { showToast("Error: " + e.message); }
  }

  return (
    <div>
      <div className="ca-agnav" style={{ justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button className="ca-btn ghost" onClick={irAtras}><ChevronLeft size={16} /></button>
          <button className="ca-btn ghost" onClick={irAdelante}><ChevronRight size={16} /></button>
          <button className="ca-btn ghost" onClick={() => setFecha(HOY_ISO)}>Hoy</button>
          <strong style={{ fontSize: 15, marginLeft: 6 }}>{subt}</strong>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <div className="ca-seg" style={{ marginLeft: 0 }}>
            {ESP_SEDES.map((s) => <button key={s.v} className={sede === s.v ? "on" : ""} onClick={() => setSede(s.v)}>{s.l}</button>)}
          </div>
          <div className="ca-seg" style={{ marginLeft: 0 }}>
            <button className={vista === "dia" ? "on" : ""} onClick={() => setVista("dia")}>Día</button>
            <button className={vista === "semana" ? "on" : ""} onClick={() => setVista("semana")}>Semana</button>
            <button className={vista === "mes" ? "on" : ""} onClick={() => setVista("mes")}>Mes</button>
          </div>
          <button className="ca-btn" onClick={() => setNueva({ fecha: vista === "dia" ? fecha : HOY_ISO })}><Plus size={15} /> Reservar</button>
        </div>
      </div>

      <div style={{ display: "flex", gap: 16, alignItems: "center", margin: "10px 2px 14px", fontSize: 12.5, color: "var(--muted)", flexWrap: "wrap" }}>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}><span style={{ width: 12, height: 12, borderRadius: 3, background: ESP_TIPO.conversemos.bg, border: `1px solid ${ESP_TIPO.conversemos.bd}` }} /> Conversemos</span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}><span style={{ width: 12, height: 12, borderRadius: 3, background: ESP_TIPO.externo.bg, border: `1px solid ${ESP_TIPO.externo.bd}` }} /> Profesional externo</span>
        <button className="ca-link" onClick={() => setNuevoConsul(true)} style={{ marginLeft: "auto" }}>+ Consultorio</button>
      </div>

      {consSede.length === 0 ? (
        <div className="ca-empty">No hay consultorios activos en {sede === "lima" ? "Lima" : "Piura"}. Agrega uno con “+ Consultorio”.</div>
      ) : vista === "dia" ? (
        <EspGridDia consultorios={consSede} reservas={reservas.filter((r) => r.consultorio_sede === sede)} onBorrar={borrar}
          onNueva={(cid, hora) => setNueva({ fecha, consultorio: cid, hora_inicio: hora })} onAbrir={(r) => setNueva(r)} />
      ) : vista === "semana" ? (
        <EspVistaSemana dias={semanaDe(fecha)} reservas={reservas} consultorios={consSede} onDia={(d) => { setFecha(d); setVista("dia"); }} onBorrar={borrar} />
      ) : (
        <EspVistaMes fecha={fecha} reservas={reservas} onDia={(d) => { setFecha(d); setVista("dia"); }} />
      )}

      {nueva && (
        <EspReservaModal base={nueva} sede={sede} consultorios={consSede} contratos={contratos}
          onClose={() => setNueva(null)} onSaved={() => { setNueva(null); cargar(); }} showToast={showToast} />
      )}
      {nuevoConsul && (
        <EspConsultorioModal sede={sede} onClose={() => setNuevoConsul(false)}
          onSaved={() => { setNuevoConsul(false); recargarConsultorios(); }} showToast={showToast} />
      )}
    </div>
  );
}

// Grilla del día: columnas = consultorios, filas = horas 6–22, bloques por reserva.
function EspGridDia({ consultorios, reservas, onBorrar, onNueva, onAbrir }) {
  const horas = [];
  for (let h = ESP_H_INI; h <= ESP_H_FIN; h++) horas.push(h);
  const alto = (ESP_H_FIN - ESP_H_INI) * ESP_PX_H;
  return (
    <div className="ca-card" style={{ padding: 0, overflow: "auto" }}>
      <div style={{ display: "flex", minWidth: 120 + consultorios.length * 150 }}>
        {/* Columna de horas */}
        <div style={{ width: 56, flexShrink: 0, borderRight: "1px solid var(--line)", paddingTop: 34 }}>
          {horas.slice(0, -1).map((h) => (
            <div key={h} style={{ height: ESP_PX_H, fontSize: 11, color: "var(--muted)", textAlign: "right", paddingRight: 8, transform: "translateY(-7px)" }}>{pad2(h)}:00</div>
          ))}
        </div>
        {/* Una columna por consultorio */}
        {consultorios.map((c) => {
          const rs = reservas.filter((r) => r.consultorio === c.id);
          return (
            <div key={c.id} style={{ flex: 1, minWidth: 150, borderRight: "1px solid var(--line)" }}>
              <div style={{ height: 34, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12.5, fontWeight: 600, borderBottom: "1px solid var(--line)", position: "sticky", top: 0, background: "var(--surface)" }}>
                <DoorOpen size={13} strokeWidth={2} style={{ marginRight: 5, color: "var(--muted)" }} />{c.nombre}
              </div>
              <div style={{ position: "relative", height: alto }}>
                {/* Líneas de hora + click para reservar */}
                {horas.slice(0, -1).map((h, i) => (
                  <div key={h} onClick={() => onNueva(c.id, `${pad2(h)}:00`)}
                    style={{ position: "absolute", top: i * ESP_PX_H, left: 0, right: 0, height: ESP_PX_H, borderBottom: "1px solid #F1EEE9", cursor: "pointer" }} />
                ))}
                {rs.map((r) => {
                  const top = (espHDec(r.hora_inicio) - ESP_H_INI) * ESP_PX_H;
                  const alt = Math.max((espHDec(r.hora_fin) - espHDec(r.hora_inicio)) * ESP_PX_H - 3, 20);
                  const t = ESP_TIPO[r.tipo] || ESP_TIPO.externo;
                  return (
                    <div key={r.id} onClick={() => onAbrir && onAbrir(r)} title="Editar / duplicar" style={{ position: "absolute", top, left: 4, right: 4, height: alt, background: t.bg, border: `1px solid ${t.bd}`, borderLeft: `3px solid ${t.fg}`, borderRadius: 6, padding: "3px 6px", overflow: "hidden", fontSize: 11.5, cursor: "pointer" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", gap: 4 }}>
                        <strong style={{ color: t.fg, fontSize: 11, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{espHm(r.hora_inicio)}–{espHm(r.hora_fin)}</strong>
                        <button onClick={(e) => { e.stopPropagation(); onBorrar(r.id); }} title="Quitar" style={{ background: "none", border: "none", cursor: "pointer", color: t.fg, padding: 0, lineHeight: 1 }}><X size={12} /></button>
                      </div>
                      <div style={{ color: "var(--ink)", fontWeight: 500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{r.ocupante_display}</div>
                      {r.notas ? <div style={{ color: "var(--muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{r.notas}</div> : null}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Vista semana: 7 columnas (días), chips de reservas por día.
function EspVistaSemana({ dias, reservas, consultorios, onDia, onBorrar }) {
  const nombre = (id) => consultorios.find((c) => c.id === id)?.nombre || "";
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 8 }}>
      {dias.map((d) => {
        const rs = reservas.filter((r) => r.fecha === d).sort((a, b) => a.hora_inicio.localeCompare(b.hora_inicio));
        const hoy = d === HOY_ISO;
        return (
          <div key={d} className="ca-card" style={{ padding: 8, minHeight: 120, ...(hoy ? { borderColor: "var(--accent)" } : {}) }}>
            <div onClick={() => onDia(d)} style={{ cursor: "pointer", fontSize: 12, fontWeight: 600, marginBottom: 6, textAlign: "center", color: hoy ? "var(--accent)" : "var(--ink)" }}>
              {cap(labelDiaSemana(d))} {dDeISO(d).getDate()}
            </div>
            {rs.length === 0 ? <div style={{ fontSize: 11, color: "var(--muted)", textAlign: "center" }}>—</div> : rs.map((r) => {
              const t = ESP_TIPO[r.tipo] || ESP_TIPO.externo;
              return (
                <div key={r.id} title={`${nombre(r.consultorio)} · ${r.ocupante_display}`} style={{ background: t.bg, borderLeft: `3px solid ${t.fg}`, borderRadius: 5, padding: "3px 5px", marginBottom: 4, fontSize: 11 }}>
                  <div style={{ fontWeight: 600, color: t.fg }}>{espHm(r.hora_inicio)}–{espHm(r.hora_fin)}</div>
                  <div style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{nombre(r.consultorio)} · {r.ocupante_display}</div>
                </div>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

// Vista mes: grilla con conteo de reservas por día.
function EspVistaMes({ fecha, reservas, onDia }) {
  const dias = mesDe(fecha);
  const mesActual = dDeISO(fecha).getMonth();
  const cont = {};
  reservas.forEach((r) => { cont[r.fecha] = (cont[r.fecha] || 0) + 1; });
  return (
    <div className="ca-card" style={{ padding: 10 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 4, fontSize: 11, color: "var(--muted)", marginBottom: 4, textAlign: "center" }}>
        {["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"].map((d) => <div key={d}>{d}</div>)}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 4 }}>
        {dias.map((d) => {
          const fuera = dDeISO(d).getMonth() !== mesActual;
          const n = cont[d] || 0;
          return (
            <div key={d} onClick={() => onDia(d)} style={{ minHeight: 62, border: "1px solid var(--line)", borderRadius: 6, padding: 5, cursor: "pointer", background: d === HOY_ISO ? "#FBF7FE" : "var(--surface)", opacity: fuera ? 0.4 : 1 }}>
              <div style={{ fontSize: 12, fontWeight: 500 }}>{dDeISO(d).getDate()}</div>
              {n > 0 && <div style={{ marginTop: 4, fontSize: 11, color: "#0A7D92", fontWeight: 600 }}>{n} reserva{n > 1 ? "s" : ""}</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function EspReservaModal({ base, sede, consultorios, contratos, onClose, onSaved, showToast }) {
  const [consultorio, setConsultorio] = useState(base.consultorio || consultorios[0]?.id || "");
  const [fecha, setFecha] = useState(base.fecha || HOY_ISO);
  const [hIni, setHIni] = useState((base.hora_inicio || "09:00").slice(0, 5));
  const [hFin, setHFin] = useState((base.hora_fin || "10:00").slice(0, 5));
  const [tipo, setTipo] = useState(base.tipo || "externo");
  const [contrato, setContrato] = useState(base.contrato || "");
  const [ocupante, setOcupante] = useState(base.ocupante || "");
  const [repetir, setRepetir] = useState(0);
  const [notas, setNotas] = useState(base.notas || "");
  const [guardando, setGuardando] = useState(false);
  const [dup, setDup] = useState(false); // "duplicar" = crear una copia (aunque base tenga id)
  const esEdicion = !!base.id && !dup;
  const activos = contratos.filter((c) => c.estado === "activo" && c.consultorio_sede === sede);

  function elegirContrato(id) {
    setContrato(id);
    const c = contratos.find((x) => String(x.id) === String(id));
    if (c) { setOcupante(c.nombre_display || ""); if (c.consultorio) setConsultorio(c.consultorio); }
  }

  async function guardar() {
    if (!consultorio) return showToast("Elige un consultorio.");
    if (hFin <= hIni) return showToast("La hora de fin debe ser posterior al inicio.");
    setGuardando(true);
    const payload = { consultorio, fecha, hora_inicio: hIni, hora_fin: hFin, tipo, contrato: contrato || null, ocupante, notas };
    try {
      if (esEdicion) {
        await api.espActualizarReserva(base.id, payload);
        showToast("Reserva actualizada ✓");
      } else {
        const r = await api.espCrearReserva({ ...payload, repetir_semanas: Number(repetir) || 0 });
        const n = r.creadas?.length || 0, s = r.saltadas?.length || 0;
        showToast(s ? `${n} reserva(s) creada(s) · ${s} se cruzaban (saltadas)` : "Reserva creada ✓");
      }
      onSaved();
    } catch (e) { showToast("Error: " + e.message); }
    finally { setGuardando(false); }
  }
  async function eliminar() {
    if (!window.confirm("¿Eliminar esta reserva?")) return;
    try { await api.espBorrarReserva(base.id); showToast("Reserva eliminada"); onSaved(); }
    catch (e) { showToast("Error: " + e.message); }
  }

  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 440 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <strong style={{ fontSize: 16 }}>{esEdicion ? "Editar reserva" : dup ? "Duplicar reserva" : "Reservar espacio"}</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>

        <div style={{ marginBottom: 13 }}>
          <div className="ca-label">Consultorio</div>
          <select className="ca-input" value={consultorio} onChange={(e) => setConsultorio(e.target.value)}>
            {consultorios.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </select>
        </div>

        <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
          <div style={{ flex: 1.3 }}>
            <div className="ca-label">Fecha</div>
            <input className="ca-input" type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
          </div>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Desde</div>
            <select className="ca-input" value={hIni} onChange={(e) => setHIni(e.target.value)}>{ESP_HORAS_OP.map((h) => <option key={h}>{h}</option>)}</select>
          </div>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Hasta</div>
            <select className="ca-input" value={hFin} onChange={(e) => setHFin(e.target.value)}>{ESP_HORAS_OP.map((h) => <option key={h}>{h}</option>)}</select>
          </div>
        </div>

        <div style={{ marginBottom: 13 }}>
          <div className="ca-label">¿Quién ocupa?</div>
          <div className="ca-seg" style={{ marginLeft: 0, display: "flex" }}>
            <button className={tipo === "externo" ? "on" : ""} onClick={() => setTipo("externo")} style={{ flex: 1 }}>Externo (alquiler)</button>
            <button className={tipo === "conversemos" ? "on" : ""} onClick={() => setTipo("conversemos")} style={{ flex: 1 }}>Conversemos</button>
          </div>
        </div>

        {tipo === "externo" && activos.length > 0 && (
          <div style={{ marginBottom: 13 }}>
            <div className="ca-label">Cliente de alquiler <span style={{ color: "var(--muted)", fontWeight: 400 }}>(opcional)</span></div>
            <select className="ca-input" value={contrato} onChange={(e) => elegirContrato(e.target.value)}>
              <option value="">— Sin vincular —</option>
              {activos.map((c) => <option key={c.id} value={c.id}>{c.nombre_display}</option>)}
            </select>
          </div>
        )}

        <div style={{ marginBottom: 13 }}>
          <div className="ca-label">Profesional que ocupa</div>
          <input className="ca-input" value={ocupante} onChange={(e) => setOcupante(e.target.value)} placeholder={tipo === "conversemos" ? "Nombre del terapeuta de Conversemos" : "Nombre del profesional"} />
        </div>

        <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
          {!esEdicion && (
            <div style={{ flex: 1 }}>
              <div className="ca-label">Repetir semanas <span style={{ color: "var(--muted)", fontWeight: 400 }}>(horario fijo)</span></div>
              <input className="ca-input" type="number" min="0" max="52" value={repetir} onChange={(e) => setRepetir(e.target.value)} />
            </div>
          )}
          <div style={{ flex: 2 }}>
            <div className="ca-label">Notas</div>
            <input className="ca-input" value={notas} onChange={(e) => setNotas(e.target.value)} placeholder="Opcional" />
          </div>
        </div>
        {!esEdicion && Number(repetir) > 0 && <div style={{ fontSize: 12, color: "var(--muted)", marginTop: -6, marginBottom: 12 }}>Se creará la MISMA reserva (mismo día y hora) en las próximas {repetir} semana{Number(repetir) === 1 ? "" : "s"}. Las que se crucen con otra se saltan.</div>}

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, marginTop: 6 }}>
          <div style={{ display: "flex", gap: 8 }}>
            {base.id && !dup && <button className="ca-btn ghost" style={{ color: "#9C4646" }} onClick={eliminar}><Trash2 size={14} strokeWidth={2} /> Eliminar</button>}
            {base.id && !dup && <button className="ca-btn ghost" onClick={() => setDup(true)}><Copy size={14} strokeWidth={2} /> Duplicar</button>}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
            <button className="ca-btn" onClick={guardar} disabled={guardando}>{guardando ? "Guardando…" : esEdicion ? "Guardar" : "Reservar"}</button>
          </div>
        </div>
      </div>
    </div>
  );
}

function EspConsultorioModal({ sede, onClose, onSaved, showToast }) {
  const [nombre, setNombre] = useState("");
  const [sedeC, setSedeC] = useState(sede);
  const [desc, setDesc] = useState("");
  async function guardar() {
    if (!nombre.trim()) return showToast("Ponle un nombre al consultorio.");
    try { await api.espCrearConsultorio({ nombre: nombre.trim(), sede: sedeC, descripcion: desc }); showToast("Consultorio creado ✓"); onSaved(); }
    catch (e) { showToast("Error: " + e.message); }
  }
  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 360 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <strong style={{ fontSize: 16 }}>Nuevo consultorio</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>
        <div style={{ marginBottom: 13 }}><div className="ca-label">Nombre</div><input className="ca-input" value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Consultorio 4" autoFocus /></div>
        <div style={{ marginBottom: 13 }}><div className="ca-label">Sede</div>
          <select className="ca-input" value={sedeC} onChange={(e) => setSedeC(e.target.value)}>{ESP_SEDES.map((s) => <option key={s.v} value={s.v}>{s.l}</option>)}</select>
        </div>
        <div style={{ marginBottom: 13 }}><div className="ca-label">Descripción <span style={{ color: "var(--muted)", fontWeight: 400 }}>(opcional)</span></div><input className="ca-input" value={desc} onChange={(e) => setDesc(e.target.value)} /></div>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" onClick={guardar}>Crear</button>
        </div>
      </div>
    </div>
  );
}

// ---- CRM de interesados en alquilar ----
function EspInteresados({ showToast, onContrato, recargarContratos }) {
  const [lista, setLista] = useState([]);
  const [fEstado, setFEstado] = useState("");
  const [fSede, setFSede] = useState("");
  const [edit, setEdit] = useState(null);
  const [cargando, setCargando] = useState(true);

  function cargar() {
    setCargando(true);
    api.espInteresados({ estado: fEstado, sede: fSede }).then(setLista).catch((e) => showToast("Error: " + e.message)).finally(() => setCargando(false));
  }
  useEffect(() => { cargar(); }, [fEstado, fSede]);

  async function cambiarEstado(it, estado) {
    try { await api.espActualizarInteresado(it.id, { estado }); cargar(); }
    catch (e) { showToast("Error: " + e.message); }
  }
  async function borrar(it) {
    if (!window.confirm(`¿Eliminar a ${it.nombre}?`)) return;
    try { await api.espBorrarInteresado(it.id); cargar(); showToast("Interesado eliminado"); }
    catch (e) { showToast("Error: " + e.message); }
  }

  return (
    <div>
      <div className="ca-agnav" style={{ justifyContent: "space-between", marginBottom: 12 }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <select className="ca-input" style={{ width: "auto" }} value={fEstado} onChange={(e) => setFEstado(e.target.value)}>
            <option value="">Todos los estados</option>
            {Object.entries(ESP_EST_INT).map(([k, v]) => <option key={k} value={k}>{v.l}</option>)}
          </select>
          <select className="ca-input" style={{ width: "auto" }} value={fSede} onChange={(e) => setFSede(e.target.value)}>
            <option value="">Ambas sedes</option>{ESP_SEDES.map((s) => <option key={s.v} value={s.v}>{s.l}</option>)}
          </select>
        </div>
        <button className="ca-btn" onClick={() => setEdit({ new: true })}><Plus size={15} /> Interesado</button>
      </div>

      {lista.length === 0 ? (
        <div className="ca-empty">{cargando ? "Cargando…" : "Sin interesados registrados."}</div>
      ) : (
        <div className="ca-card" style={{ padding: 0, overflow: "auto" }}>
          <table className="ca-table">
            <thead><tr><th>Nombre</th><th>Profesión</th><th>Contacto</th><th>Sede</th><th>Estado</th><th>Seguimiento</th><th></th></tr></thead>
            <tbody>
              {lista.map((it) => (
                <tr key={it.id}>
                  <td>
                    <div style={{ fontWeight: 500 }}>{it.nombre}</div>
                    {it.observaciones ? <div className="ca-pmeta" style={{ maxWidth: 220, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }} title={it.observaciones}>{it.observaciones}</div> : null}
                  </td>
                  <td>{it.profesion || "—"}</td>
                  <td style={{ fontSize: 12.5 }}>{it.telefono || ""}{it.telefono && it.correo ? <br /> : ""}{it.correo || (!it.telefono ? "—" : "")}</td>
                  <td>{it.sede_label || "—"}</td>
                  <td>
                    <select value={it.estado} onChange={(e) => cambiarEstado(it, e.target.value)} style={{ border: "1px solid var(--line)", borderRadius: 20, padding: "2px 8px", fontSize: 11.5, fontWeight: 600, background: (ESP_EST_INT[it.estado] || {}).bg, color: (ESP_EST_INT[it.estado] || {}).fg, cursor: "pointer" }}>
                      {Object.entries(ESP_EST_INT).map(([k, v]) => <option key={k} value={k} style={{ background: "#fff", color: "var(--ink)" }}>{v.l}</option>)}
                    </select>
                  </td>
                  <td style={{ fontSize: 12.5 }}>{it.proximo_seguimiento ? labelNumMes(it.proximo_seguimiento) : "—"}</td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    {it.estado !== "activo" && <button className="ca-link" onClick={() => setEdit({ ...it, _contrato: true })} title="Convertir en cliente">→ Cliente</button>}
                    <button className="ca-iconbtn" onClick={() => setEdit(it)} title="Editar" style={{ marginLeft: 6 }}><Pencil size={14} /></button>
                    <button className="ca-iconbtn" onClick={() => borrar(it)} title="Eliminar" style={{ marginLeft: 4, color: "#9C4646" }}><Trash2 size={14} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {edit && !edit._contrato && (
        <EspInteresadoModal it={edit.new ? null : edit} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); cargar(); }} showToast={showToast} />
      )}
      {edit && edit._contrato && (
        <EspContratoModal interesado={edit} consultorios={[]} onClose={() => setEdit(null)}
          onSaved={() => { setEdit(null); cargar(); recargarContratos(); onContrato(); }} showToast={showToast} soloDesdeInteresado />
      )}
    </div>
  );
}

function EspInteresadoModal({ it, onClose, onSaved, showToast }) {
  const [f, setF] = useState({
    nombre: it?.nombre || "", telefono: it?.telefono || "", correo: it?.correo || "",
    profesion: it?.profesion || "", sede_interes: it?.sede_interes || "", estado: it?.estado || "interesado",
    observaciones: it?.observaciones || "", proximo_seguimiento: it?.proximo_seguimiento || "",
  });
  const set = (k, v) => setF((o) => ({ ...o, [k]: v }));
  async function guardar() {
    if (!f.nombre.trim()) return showToast("El nombre es obligatorio.");
    const data = { ...f, proximo_seguimiento: f.proximo_seguimiento || null };
    try {
      if (it) await api.espActualizarInteresado(it.id, data);
      else await api.espCrearInteresado(data);
      showToast(it ? "Interesado actualizado ✓" : "Interesado agregado ✓"); onSaved();
    } catch (e) { showToast("Error: " + e.message); }
  }
  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 440 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <strong style={{ fontSize: 16 }}>{it ? "Editar interesado" : "Nuevo interesado"}</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>
        <div style={{ marginBottom: 13 }}><div className="ca-label">Nombre</div><input className="ca-input" value={f.nombre} onChange={(e) => set("nombre", e.target.value)} autoFocus /></div>
        <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
          <div style={{ flex: 1 }}><div className="ca-label">Teléfono</div><input className="ca-input" value={f.telefono} onChange={(e) => set("telefono", e.target.value)} inputMode="tel" /></div>
          <div style={{ flex: 1 }}><div className="ca-label">Correo</div><input className="ca-input" value={f.correo} onChange={(e) => set("correo", e.target.value)} inputMode="email" /></div>
        </div>
        <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
          <div style={{ flex: 1.5 }}><div className="ca-label">Profesión / especialidad</div><input className="ca-input" value={f.profesion} onChange={(e) => set("profesion", e.target.value)} /></div>
          <div style={{ flex: 1 }}><div className="ca-label">Sede de interés</div>
            <select className="ca-input" value={f.sede_interes} onChange={(e) => set("sede_interes", e.target.value)}><option value="">—</option>{ESP_SEDES.map((s) => <option key={s.v} value={s.v}>{s.l}</option>)}</select>
          </div>
        </div>
        <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
          <div style={{ flex: 1 }}><div className="ca-label">Estado</div>
            <select className="ca-input" value={f.estado} onChange={(e) => set("estado", e.target.value)}>{Object.entries(ESP_EST_INT).map(([k, v]) => <option key={k} value={k}>{v.l}</option>)}</select>
          </div>
          <div style={{ flex: 1 }}><div className="ca-label">Próximo seguimiento</div><input className="ca-input" type="date" value={f.proximo_seguimiento || ""} onChange={(e) => set("proximo_seguimiento", e.target.value)} /></div>
        </div>
        <div style={{ marginBottom: 13 }}><div className="ca-label">Observaciones</div><textarea className="ca-input" rows={3} value={f.observaciones} onChange={(e) => set("observaciones", e.target.value)} /></div>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" onClick={guardar}>{it ? "Guardar" : "Agregar"}</button>
        </div>
      </div>
    </div>
  );
}

// ---- Clientes activos (contratos de alquiler) ----
function EspContratos({ showToast, consultorios, contratos, recargarContratos }) {
  const [lista, setLista] = useState([]);
  const [fEstado, setFEstado] = useState("");
  const [fSede, setFSede] = useState("");
  const [nuevo, setNuevo] = useState(false);
  const [cargando, setCargando] = useState(true);

  function cargar() {
    setCargando(true);
    api.espContratos({ estado: fEstado, sede: fSede }).then(setLista).catch((e) => showToast("Error: " + e.message)).finally(() => setCargando(false));
  }
  useEffect(() => { cargar(); }, [fEstado, fSede]);

  async function borrar(c) {
    if (!window.confirm(`¿Eliminar el contrato de ${c.nombre_display}?`)) return;
    try { await api.espBorrarContrato(c.id); cargar(); recargarContratos(); showToast("Contrato eliminado"); }
    catch (e) { showToast("Error: " + e.message); }
  }

  return (
    <div>
      <div className="ca-agnav" style={{ justifyContent: "space-between", marginBottom: 12 }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <select className="ca-input" style={{ width: "auto" }} value={fEstado} onChange={(e) => setFEstado(e.target.value)}>
            <option value="">Todos los estados</option>{Object.entries(ESP_EST_CONT).map(([k, v]) => <option key={k} value={k}>{v.l}</option>)}
          </select>
          <select className="ca-input" style={{ width: "auto" }} value={fSede} onChange={(e) => setFSede(e.target.value)}>
            <option value="">Ambas sedes</option>{ESP_SEDES.map((s) => <option key={s.v} value={s.v}>{s.l}</option>)}
          </select>
        </div>
        <button className="ca-btn" onClick={() => setNuevo(true)}><Plus size={15} /> Cliente</button>
      </div>

      {lista.length === 0 ? (
        <div className="ca-empty">{cargando ? "Cargando…" : "Sin clientes activos."}</div>
      ) : (
        <div className="ca-card" style={{ padding: 0, overflow: "auto" }}>
          <table className="ca-table">
            <thead><tr><th>Cliente</th><th>Consultorio</th><th>Modalidad</th><th>Plan</th><th className="num">Horas</th><th>Horario</th><th className="num">Precio</th><th className="num">Pagado</th><th>Estado</th><th></th></tr></thead>
            <tbody>
              {lista.map((c) => (
                <tr key={c.id}>
                  <td><div style={{ fontWeight: 500 }}>{c.nombre_display}</div>{c.profesion ? <div className="ca-pmeta">{c.profesion}</div> : null}</td>
                  <td>{c.consultorio_nombre} <span style={{ color: "var(--muted)", fontSize: 12 }}>· {c.consultorio_sede === "lima" ? "Lima" : "Piura"}</span></td>
                  <td>{c.modalidad_label}</td>
                  <td>{c.plan || "—"}</td>
                  <td className="num">{Number(c.horas_contratadas)}</td>
                  <td style={{ fontSize: 12.5, maxWidth: 160 }}>{c.horario_semanal || "—"}</td>
                  <td className="num">{money(c.precio)}</td>
                  <td className="num" title="Horas cubiertas por pagos">{Number(c.horas_pagadas)} h</td>
                  <td><EspBadge est={ESP_EST_CONT[c.estado]} /></td>
                  <td style={{ whiteSpace: "nowrap" }}><button className="ca-iconbtn" onClick={() => borrar(c)} title="Eliminar" style={{ color: "#9C4646" }}><Trash2 size={14} /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {nuevo && (
        <EspContratoModal interesado={null} consultorios={consultorios} onClose={() => setNuevo(false)}
          onSaved={() => { setNuevo(false); cargar(); recargarContratos(); }} showToast={showToast} />
      )}
    </div>
  );
}

function EspContratoModal({ interesado, consultorios, onClose, onSaved, showToast, soloDesdeInteresado }) {
  const [cons, setCons] = useState(consultorios);
  const [f, setF] = useState({
    consultorio: consultorios[0]?.id || "", fecha_inicio: HOY_ISO, modalidad: "por_horas",
    plan: "", horas_contratadas: "", horario_semanal: "", precio: "", estado: "activo",
    nombre: interesado?.nombre || "", profesion: interesado?.profesion || "", telefono: interesado?.telefono || "",
  });
  const set = (k, v) => setF((o) => ({ ...o, [k]: v }));

  // Si venimos desde el interesado sin lista de consultorios, la cargamos.
  useEffect(() => {
    if (soloDesdeInteresado && cons.length === 0) {
      api.espConsultorios().then((cs) => { setCons(cs); if (cs[0]) set("consultorio", cs[0].id); }).catch(() => {});
    }
  }, []);

  function aplicarPlan(id) {
    const p = ESP_PLANES.find((x) => x.id === id);
    if (!p) return;
    setF((o) => ({ ...o, plan: p.id ? p.nombre : "", modalidad: p.modalidad, horas_contratadas: p.horas || "", precio: p.precio || "" }));
  }

  async function guardar() {
    if (!f.consultorio) return showToast("Elige un consultorio.");
    const data = {
      interesado: interesado?.id || null,
      consultorio: f.consultorio, fecha_inicio: f.fecha_inicio, modalidad: f.modalidad,
      plan: f.plan, horas_contratadas: f.horas_contratadas || 0, horario_semanal: f.horario_semanal,
      precio: f.precio || 0, estado: f.estado,
      nombre: f.nombre, profesion: f.profesion, telefono: f.telefono,
    };
    try { await api.espCrearContrato(data); showToast("Cliente de alquiler creado ✓"); onSaved(); }
    catch (e) { showToast("Error: " + e.message); }
  }

  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 460 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <strong style={{ fontSize: 16 }}>{interesado ? `Cliente: ${interesado.nombre}` : "Nuevo cliente de alquiler"}</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>

        {!interesado && (
          <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
            <div style={{ flex: 1.5 }}><div className="ca-label">Nombre del profesional</div><input className="ca-input" value={f.nombre} onChange={(e) => set("nombre", e.target.value)} /></div>
            <div style={{ flex: 1 }}><div className="ca-label">Teléfono</div><input className="ca-input" value={f.telefono} onChange={(e) => set("telefono", e.target.value)} inputMode="tel" /></div>
          </div>
        )}

        <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
          <div style={{ flex: 1.4 }}><div className="ca-label">Consultorio</div>
            <select className="ca-input" value={f.consultorio} onChange={(e) => set("consultorio", e.target.value)}>
              <option value="">— Elegir —</option>
              {cons.map((c) => <option key={c.id} value={c.id}>{c.nombre} · {c.sede === "lima" ? "Lima" : "Piura"}</option>)}
            </select>
          </div>
          <div style={{ flex: 1 }}><div className="ca-label">Fecha de inicio</div><input className="ca-input" type="date" value={f.fecha_inicio} onChange={(e) => set("fecha_inicio", e.target.value)} /></div>
        </div>

        <div style={{ marginBottom: 13 }}>
          <div className="ca-label">Plan del dossier <span style={{ color: "var(--muted)", fontWeight: 400 }}>(auto-rellena horas y precio)</span></div>
          <select className="ca-input" onChange={(e) => aplicarPlan(e.target.value)} defaultValue="">
            {ESP_PLANES.map((p) => <option key={p.id || "custom"} value={p.id}>{p.nombre}</option>)}
          </select>
        </div>

        <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
          <div style={{ flex: 1 }}><div className="ca-label">Modalidad</div>
            <select className="ca-input" value={f.modalidad} onChange={(e) => set("modalidad", e.target.value)}>
              <option value="por_horas">Por horas (flexible)</option><option value="fijo">Horario fijo (semanal)</option>
            </select>
          </div>
          <div style={{ flex: 1 }}><div className="ca-label">Horas {f.modalidad === "fijo" ? "/ semana" : "/ mes"}</div><input className="ca-input" type="number" min="0" value={f.horas_contratadas} onChange={(e) => set("horas_contratadas", e.target.value)} /></div>
          <div style={{ flex: 1 }}><div className="ca-label">Precio (S/)</div><input className="ca-input" type="number" min="0" value={f.precio} onChange={(e) => set("precio", e.target.value)} /></div>
        </div>

        {f.modalidad === "fijo" && (
          <div style={{ marginBottom: 13 }}><div className="ca-label">Horario semanal</div><input className="ca-input" value={f.horario_semanal} onChange={(e) => set("horario_semanal", e.target.value)} placeholder="Lun y Mié 10:00–12:00" /></div>
        )}

        <div style={{ marginBottom: 13 }}><div className="ca-label">Estado</div>
          <select className="ca-input" value={f.estado} onChange={(e) => set("estado", e.target.value)}>{Object.entries(ESP_EST_CONT).map(([k, v]) => <option key={k} value={k}>{v.l}</option>)}</select>
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" onClick={guardar}>Guardar</button>
        </div>
      </div>
    </div>
  );
}

// ---- Pagos del alquiler ----
function EspPagos({ showToast, contratos }) {
  const [contrato, setContrato] = useState("");
  const [lista, setLista] = useState([]);
  const [nuevo, setNuevo] = useState(false);
  const [pagando, setPagando] = useState(null);
  const [cargando, setCargando] = useState(true);

  function cargar() {
    setCargando(true);
    api.espPagos({ contrato }).then(setLista).catch((e) => showToast("Error: " + e.message)).finally(() => setCargando(false));
  }
  useEffect(() => { cargar(); }, [contrato]);

  const contSel = contratos.find((c) => String(c.id) === String(contrato));

  async function marcarPagado(p, medio) {
    try { await api.espMarcarPagoPagado(p.id, medio); setPagando(null); cargar(); showToast("Pago marcado como pagado ✓"); }
    catch (e) { showToast("Error: " + e.message); }
  }
  async function borrar(p) {
    if (!window.confirm("¿Eliminar este pago?")) return;
    try { await api.espBorrarPago(p.id); cargar(); showToast("Pago eliminado"); }
    catch (e) { showToast("Error: " + e.message); }
  }

  return (
    <div>
      <div className="ca-agnav" style={{ justifyContent: "space-between", marginBottom: 12 }}>
        <select className="ca-input" style={{ width: "auto", maxWidth: 280 }} value={contrato} onChange={(e) => setContrato(e.target.value)}>
          <option value="">Todos los clientes</option>
          {contratos.map((c) => <option key={c.id} value={c.id}>{c.nombre_display} · {c.consultorio_nombre}</option>)}
        </select>
        <button className="ca-btn" onClick={() => setNuevo(true)} disabled={contratos.length === 0}><Plus size={15} /> Pago</button>
      </div>

      {contSel && (
        <div className="ca-glance" style={{ marginBottom: 14 }}>
          <div className="ca-gcard" style={{ cursor: "default" }}>
            <div className="ca-ghead"><Clock size={14} strokeWidth={2} /> Horas pagadas</div>
            <div className="ca-gmain">{Number(contSel.horas_pagadas)} h</div>
            <div className="ca-gsub">de {Number(contSel.horas_contratadas)} h contratadas ({contSel.modalidad_label})</div>
          </div>
          <div className="ca-gcard" style={{ cursor: "default" }}>
            <div className="ca-ghead"><Receipt size={14} strokeWidth={2} /> Pagado acumulado</div>
            <div className="ca-gmain">{money(lista.filter((p) => p.estado === "pagado").reduce((a, p) => a + Number(p.monto), 0))}</div>
            <div className="ca-gsub">{lista.filter((p) => p.estado === "pendiente").length} pago(s) pendiente(s)</div>
          </div>
        </div>
      )}

      {lista.length === 0 ? (
        <div className="ca-empty">{cargando ? "Cargando…" : "Sin pagos registrados."}</div>
      ) : (
        <div className="ca-card" style={{ padding: 0, overflow: "auto" }}>
          <table className="ca-table">
            <thead><tr><th>Cliente</th><th>Fecha</th><th className="num">Monto</th><th>Método</th><th className="num">Horas</th><th>Estado</th><th></th></tr></thead>
            <tbody>
              {lista.map((p) => (
                <tr key={p.id}>
                  <td>{p.contrato_nombre}</td>
                  <td>{p.fecha ? labelNumMes(p.fecha) : "—"}</td>
                  <td className="num" style={{ fontWeight: 600 }}>{money(p.monto)}</td>
                  <td>{p.medio_label || "—"}</td>
                  <td className="num">{Number(p.horas_cubiertas)} h</td>
                  <td><EspBadge est={p.estado === "pagado" ? { l: "Pagado", bg: "#E3F0E8", fg: "#2F6B4F" } : { l: "Pendiente", bg: "#FFF1DA", fg: "#9C6B2E" }} /></td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    {p.estado === "pendiente" && <button className="ca-link" onClick={() => setPagando(p)}>Marcar pagado</button>}
                    <button className="ca-iconbtn" onClick={() => borrar(p)} title="Eliminar" style={{ marginLeft: 6, color: "#9C4646" }}><Trash2 size={14} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {nuevo && <EspPagoModal contratos={contratos} contratoSel={contrato} onClose={() => setNuevo(false)} onSaved={() => { setNuevo(false); cargar(); }} showToast={showToast} />}
      {pagando && (
        <div className="ca-modal-bg" onClick={() => setPagando(null)}>
          <div className="ca-modal" style={{ maxWidth: 320 }} onClick={(e) => e.stopPropagation()}>
            <strong style={{ fontSize: 15 }}>¿Con qué medio se pagó?</strong>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 14 }}>
              {[["efectivo", "Efectivo"], ["yape", "Yape"], ["plin", "Plin"], ["transferencia", "Transferencia"], ["tarjeta", "Tarjeta"]].map(([v, l]) => (
                <button key={v} className="ca-btn ghost" onClick={() => marcarPagado(pagando, v)}>{l}</button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function EspPagoModal({ contratos, contratoSel, onClose, onSaved, showToast }) {
  const [f, setF] = useState({
    contrato: contratoSel || contratos[0]?.id || "", fecha: HOY_ISO, monto: "", medio_pago: "yape",
    estado: "pagado", horas_cubiertas: "", notas: "",
  });
  const set = (k, v) => setF((o) => ({ ...o, [k]: v }));
  async function guardar() {
    if (!f.contrato) return showToast("Elige el cliente de alquiler.");
    if (!f.monto || Number(f.monto) <= 0) return showToast("El monto debe ser mayor a 0.");
    try {
      await api.espCrearPago({ ...f, horas_cubiertas: f.horas_cubiertas || 0 });
      showToast("Pago registrado ✓"); onSaved();
    } catch (e) { showToast("Error: " + e.message); }
  }
  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 420 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <strong style={{ fontSize: 16 }}>Registrar pago de alquiler</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>
        <div style={{ marginBottom: 13 }}><div className="ca-label">Cliente</div>
          <select className="ca-input" value={f.contrato} onChange={(e) => set("contrato", e.target.value)}>
            <option value="">— Elegir —</option>
            {contratos.map((c) => <option key={c.id} value={c.id}>{c.nombre_display} · {c.consultorio_nombre}</option>)}
          </select>
        </div>
        <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
          <div style={{ flex: 1 }}><div className="ca-label">Fecha</div><input className="ca-input" type="date" value={f.fecha} onChange={(e) => set("fecha", e.target.value)} /></div>
          <div style={{ flex: 1 }}><div className="ca-label">Monto (S/)</div><input className="ca-input" type="number" min="0" value={f.monto} onChange={(e) => set("monto", e.target.value)} autoFocus /></div>
        </div>
        <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
          <div style={{ flex: 1 }}><div className="ca-label">Horas que cubre</div><input className="ca-input" type="number" min="0" value={f.horas_cubiertas} onChange={(e) => set("horas_cubiertas", e.target.value)} placeholder="Ej: 4" /></div>
          <div style={{ flex: 1 }}><div className="ca-label">Estado</div>
            <select className="ca-input" value={f.estado} onChange={(e) => set("estado", e.target.value)}><option value="pagado">Pagado</option><option value="pendiente">Pendiente</option></select>
          </div>
        </div>
        {f.estado === "pagado" && (
          <div style={{ marginBottom: 13 }}><div className="ca-label">Método</div>
            <select className="ca-input" value={f.medio_pago} onChange={(e) => set("medio_pago", e.target.value)}>
              <option value="efectivo">Efectivo</option><option value="yape">Yape</option><option value="plin">Plin</option><option value="transferencia">Transferencia</option><option value="tarjeta">Tarjeta</option>
            </select>
          </div>
        )}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" onClick={guardar}>Registrar</button>
        </div>
      </div>
    </div>
  );
}

function Liquidacion({ showToast }) {
  const primerDia = HOY_ISO.slice(0, 8) + "01";
  const [desde, setDesde] = useState(primerDia);
  const [hasta, setHasta] = useState(HOY_ISO);
  const [data, setData] = useState(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    if (!desde || !hasta) return;
    setCargando(true);
    api.liquidacion(desde, hasta).then(setData).catch((e) => showToast("Error: " + e.message)).finally(() => setCargando(false));
  }, [desde, hasta]);

  const filas = data?.filas || [];
  const sinMonto = data?.sin_monto || [];
  // Una fila por psicólogo y servicio, para el export.
  const filasExport = filas.flatMap((f) => f.detalle.map((d) => [f.nombre, d.servicio, d.sesiones, d.monto, d.subtotal]));

  return (
    <div>
      <div className="ca-tophead">
        <div>
          <h1 className="ca-h1">Liquidación de honorarios</h1>
          <div className="ca-sub">Cuánto pagar a cada psicólogo · sesiones atendidas × pago del servicio</div>
        </div>
        <ExportBtns nombre={`liquidacion_${desde}_a_${hasta}`} titulo={`Liquidación · ${desde} a ${hasta}`} disabled={filas.length === 0}
          headers={["Psicologo", "Servicio", "Sesiones atendidas", "Pago x sesion (S/)", "Subtotal (S/)"]}
          filas={filasExport} />
      </div>

      <div className="ca-agnav" style={{ justifyContent: "flex-end", flexWrap: "wrap", gap: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <input className="ca-input" style={{ width: "auto" }} type="date" value={desde} max={hasta || undefined} onChange={(e) => setDesde(e.target.value)} title="Desde" />
          <span style={{ color: "var(--muted)" }}>–</span>
          <input className="ca-input" style={{ width: "auto" }} type="date" value={hasta} min={desde || undefined} onChange={(e) => setHasta(e.target.value)} title="Hasta" />
        </div>
      </div>

      {sinMonto.length > 0 && (
        <div className="ca-card" style={{ marginBottom: 14, borderColor: "#F0DDBF", background: "#FDFAF1", display: "flex", gap: 9, alignItems: "flex-start" }}>
          <AlertTriangle size={15} strokeWidth={2} style={{ color: "#B0822F", flexShrink: 0, marginTop: 2 }} />
          <div style={{ fontSize: 13, lineHeight: 1.5 }}>
            <strong>Estos servicios se atendieron pero no tienen pago configurado</strong> (se están pagando S/0):{" "}
            {sinMonto.join(" · ")}.<br />
            <span style={{ color: "var(--muted)" }}>Ponles el «Pago terapeuta» en <strong>Finanzas → Precios</strong>.</span>
          </div>
        </div>
      )}

      {!data ? (
        <div className="ca-empty">{cargando ? "Cargando…" : "Sin datos."}</div>
      ) : filas.length === 0 ? (
        <div className="ca-empty">No hay sesiones atendidas en este rango.</div>
      ) : (
        <>
          <div className="ca-glance" style={{ marginBottom: 16 }}>
            <div className="ca-gcard" style={{ cursor: "default" }}>
              <div className="ca-ghead"><Activity size={14} strokeWidth={2} /> Sesiones atendidas</div>
              <div className="ca-gmain">{data.total_sesiones}</div>
              <div className="ca-gsub">en el rango seleccionado</div>
            </div>
            <div className="ca-gcard" style={{ cursor: "default", borderColor: "#EAD9F2", background: "#FBF7FE" }}>
              <div className="ca-ghead" style={{ color: "#6B4E96" }}><Receipt size={14} strokeWidth={2} /> Total a pagar</div>
              <div className="ca-gmain">{money(data.total_a_pagar)}</div>
              <div className="ca-gsub">honorarios de psicólogos</div>
            </div>
          </div>

          <div className="ca-card" style={{ padding: 0, overflow: "hidden" }}>
            <table className="ca-table">
              <thead>
                <tr>
                  <th>Psicólogo</th>
                  <th>Servicio</th>
                  <th className="num">Sesiones</th>
                  <th className="num">Pago x sesión</th>
                  <th className="num">Subtotal</th>
                </tr>
              </thead>
              <tbody>
                {filas.map((f) => (
                  <React.Fragment key={f.medico_id || "sin"}>
                    {f.detalle.map((d, i) => (
                      <tr key={d.servicio}>
                        {i === 0 && <td rowSpan={f.detalle.length} style={{ verticalAlign: "top", fontWeight: 500 }}>{f.nombre}</td>}
                        <td>{d.servicio}{d.monto === 0 ? <span style={{ marginLeft: 7, fontSize: 11.5, color: "#B0822F" }}>· sin pago configurado</span> : null}</td>
                        <td className="num">{d.sesiones}</td>
                        <td className="num" style={{ color: "var(--muted)" }}>{money(d.monto)}</td>
                        <td className="num">{money(d.subtotal)}</td>
                      </tr>
                    ))}
                    <tr style={{ background: "#FBFAF8" }}>
                      <td colSpan={2} style={{ textAlign: "right", fontSize: 12.5, color: "var(--muted)" }}>Total {f.nombre}</td>
                      <td className="num" style={{ fontWeight: 600 }}>{f.sesiones}</td>
                      <td className="num"></td>
                      <td className="num" style={{ fontWeight: 700 }}>{money(f.a_pagar)}</td>
                    </tr>
                  </React.Fragment>
                ))}
              </tbody>
              <tfoot>
                <tr style={{ fontWeight: 600, borderTop: "2px solid var(--line)" }}>
                  <td colSpan={2}>Total general</td>
                  <td className="num">{data.total_sesiones}</td>
                  <td className="num"></td>
                  <td className="num">{money(data.total_a_pagar)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
          <div style={{ fontSize: 12.5, color: "var(--muted)", marginTop: 12, display: "flex", gap: 7, alignItems: "flex-start", lineHeight: 1.5 }}>
            <AlertTriangle size={14} strokeWidth={2} style={{ color: "#B0822F", flexShrink: 0, marginTop: 1 }} />
            <span>Se paga por <strong>sesión atendida</strong> (citas en estado «atendida» de la agenda) × el <strong>pago del servicio</strong>, que configuras en <strong>Finanzas → Precios</strong>. NO se usa un % de lo cobrado: los descuentos al paciente los asume la clínica y no reducen el pago al profesional.</span>
          </div>
        </>
      )}
    </div>
  );
}

function Finanzas({ showToast, esAdmin }) {
  const [periodo, setPeriodo] = useState("mes");
  const [sede, setSede] = useState("");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
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

  const rangoActivo = desde && hasta;
  const filtro = { periodo, sede, desde, hasta };

  async function cargar() {
    const base = [api.resumenFinanzas(filtro), api.cobros(filtro), api.servicios(), api.pacientes()];
    const extra = esAdmin ? [api.cajaFinanzas(filtro), api.egresos(filtro)] : [];
    const [r, c, s, p, cj, eg] = await Promise.all([...base, ...extra]);
    setRes(r); setCobros(c); setServicios(s); setPacientes(p);
    if (esAdmin) { setCaja(cj); setEgresos(eg); }
  }
  useEffect(() => {
    setCargando(true);
    cargar().catch((e) => showToast("Error: " + e.message)).finally(() => setCargando(false));
  }, [periodo, sede, desde, hasta]);

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
          <ExportBtns nombre={`cobros_${rangoActivo ? `${desde}_a_${hasta}` : periodo}${sede ? "_" + sede : ""}`} titulo="Finanzas · Cobros" disabled={cobros.length === 0}
            headers={["Fecha", "Paciente", "Concepto", "Monto", "Estado", "Medio"]}
            filas={cobros.map((c) => [c.fecha_label, c.paciente_nombre, c.concepto, c.monto, c.estado_label, c.medio_label])} />
          {esAdmin && <button className="ca-btn ghost" onClick={() => setPrecios(true)}>Precios</button>}
          <button className="ca-btn" onClick={() => setNuevo({})}><Plus size={16} strokeWidth={2.2} /> Registrar cobro</button>
        </div>
      </div>

      {esAdmin && <ConsolidadoSoto showToast={showToast} />}

      <div className="ca-agnav" style={{ justifyContent: "flex-end", flexWrap: "wrap", gap: 10 }}>
        <select className="ca-input" style={{ width: "auto" }} value={sede} onChange={(e) => setSede(e.target.value)}>
          <option value="">Todas las sedes</option>
          <option value="lima">Lima</option>
          <option value="piura">Piura</option>
        </select>
        <div className="ca-seg" style={{ opacity: rangoActivo ? 0.45 : 1 }}>
          {[["hoy", "Hoy"], ["semana", "Semana"], ["mes", "Mes"]].map(([v, l]) => (
            <button key={v} className={!rangoActivo && periodo === v ? "on" : ""}
              onClick={() => { setDesde(""); setHasta(""); setPeriodo(v); }}>{l}</button>
          ))}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <input className="ca-input" style={{ width: "auto" }} type="date" value={desde} max={hasta || undefined} onChange={(e) => setDesde(e.target.value)} title="Desde" />
          <span style={{ color: "var(--muted)" }}>–</span>
          <input className="ca-input" style={{ width: "auto" }} type="date" value={hasta} min={desde || undefined} onChange={(e) => setHasta(e.target.value)} title="Hasta" />
          {rangoActivo && <button className="ca-mini" onClick={() => { setDesde(""); setHasta(""); }} title="Quitar el rango"><X size={13} strokeWidth={2} /> rango</button>}
        </div>
      </div>

      {!res ? (
        <div className="ca-empty">{cargando ? "Cargando…" : "Sin datos."}</div>
      ) : (
        <div style={{ opacity: cargando ? 0.5 : 1, transition: "opacity .15s" }}>
          {esAdmin && caja && (
            <>
              <h2 className="ca-secth" style={{ marginTop: 16 }}>Caja del período{caja.sede ? ` · ${caja.sede === "lima" ? "Lima" : "Piura"}` : ""}</h2>
              <div className="ca-stats">
                <StatCard label="Ingresos (cobrado)" valor={money(caja.ingresos)} color="#4F8A77" />
                {!caja.egresos_solo_total && <StatCard label="Egresos (gastos)" valor={money(caja.egresos)} sub={`${caja.n_egresos} gastos`} color="#B4564E" />}
                {!caja.egresos_solo_total && <StatCard label="Utilidad (neto)" valor={money(caja.utilidad)} color={caja.utilidad >= 0 ? "#3E7A65" : "#B4564E"} />}
                <StatCard label="Pendiente por cobrar" valor={money(caja.pendiente)} color={caja.pendiente > 0 ? "#C9923A" : "#7C7870"} />
              </div>
              {caja.egresos_solo_total ? (
                <div style={{ fontSize: 12.5, color: "var(--muted)", marginTop: 8 }}>
                  Egresos y utilidad se calculan solo en «Todas las sedes» (los gastos no se registran por sede).
                </div>
              ) : caja.egresos_por_categoria.length > 0 && (
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

          {(() => {
            const m = {};
            cobros.forEach((c) => {
              if (c.estado !== "pagado") return;
              const d = (c.fecha || "").slice(0, 10);
              if (d) { (m[d] = m[d] || { total: 0, n: 0 }).total += Number(c.monto || 0); m[d].n += 1; }
            });
            const dias = Object.entries(m).sort((a, b) => b[0].localeCompare(a[0]));
            if (!dias.length) return null;
            return (
              <>
                <h2 className="ca-secth" style={{ marginTop: 28 }}>Facturación por día</h2>
                <table className="ca-tbl">
                  <thead><tr><th>Día</th><th className="num">Cobros</th><th className="num">Facturado</th></tr></thead>
                  <tbody>
                    {dias.map(([d, v]) => (
                      <tr key={d}>
                        <td style={{ textTransform: "capitalize" }}>{labelLargo(d)}</td>
                        <td className="num">{v.n}</td>
                        <td className="num" style={{ fontWeight: 600, color: "#4F8A77" }}>{money(v.total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            );
          })()}

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

function VenderPaqueteModal({ paciente, servicios, onClose, onSave }) {
  const serviciosActivos = (servicios || []).filter((s) => s.activo);
  const [servicio, setServicio] = useState("");
  const [precioUnit, setPrecioUnit] = useState("");
  const [sesiones, setSesiones] = useState("8");
  const [monto, setMonto] = useState("");
  const [nombre, setNombre] = useState("");
  const [medio, setMedio] = useState("efectivo");
  const [comprobante, setComprobante] = useState("");
  const [compNumero, setCompNumero] = useState("");

  const nSes = Number(sesiones) || 0;
  const nombreFinal = nombre.trim() || (nSes ? `Paquete de ${nSes} sesiones` : "Paquete de sesiones");
  const canSave = nSes > 0 && Number(monto) > 0;

  function elegirServicio(id) {
    setServicio(id);
    const s = serviciosActivos.find((x) => String(x.id) === id);
    if (s) { setPrecioUnit(String(s.precio)); if (nSes) setMonto((Number(s.precio) * nSes).toFixed(2)); }
  }
  function setSes(v) {
    const n = v.replace(/[^0-9]/g, "");
    setSesiones(n);
    if (precioUnit && Number(n)) setMonto((Number(precioUnit) * Number(n)).toFixed(2));
  }

  function guardar() {
    onSave({
      paciente: paciente.id, nombre: nombreFinal, sesiones_total: nSes, monto,
      medio_pago: medio, comprobante_tipo: comprobante, comprobante_numero: compNumero.trim(),
    });
  }

  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 430 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
          <strong style={{ fontSize: 16 }}>Vender paquete</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>
        <div style={{ fontSize: 13, color: "var(--muted)", marginBottom: 10 }}>Para {paciente.nombre} · se cobra ahora y las sesiones se descuentan al atender.</div>
        <div style={{ fontSize: 12, color: "#4B6B4E", background: "#EEF2EC", borderRadius: 8, padding: "8px 10px", marginBottom: 16, lineHeight: 1.45 }}>
          Al psicólogo se le paga <strong>por cada sesión que atienda</strong> (según el precio del servicio en Finanzas → Precios), no por el paquete completo. El pago total de este paquete es ingreso de la clínica.
        </div>

        <div style={{ marginBottom: 12 }}>
          <div className="ca-label">Servicio (opcional, sugiere precio)</div>
          <select className="ca-input" value={servicio} onChange={(e) => elegirServicio(e.target.value)}>
            <option value="">— Personalizado —</option>
            {serviciosActivos.map((s) => <option key={s.id} value={s.id}>{s.nombre} (S/ {s.precio})</option>)}
          </select>
        </div>
        <div style={{ display: "flex", gap: 11, marginBottom: 12 }}>
          <div style={{ flex: 1 }}>
            <div className="ca-label">N° de sesiones</div>
            <input className="ca-input" value={sesiones} onChange={(e) => setSes(e.target.value)} inputMode="numeric" placeholder="8" />
          </div>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Monto total S/.</div>
            <input className="ca-input" value={monto} onChange={(e) => setMonto(e.target.value)} inputMode="decimal" placeholder="640" />
          </div>
        </div>
        {precioUnit && nSes > 0 && (
          <div style={{ fontSize: 12, color: "var(--muted)", marginTop: -4, marginBottom: 12 }}>{nSes} × S/ {precioUnit} = S/ {(Number(precioUnit) * nSes).toFixed(2)} (puedes ajustar el total)</div>
        )}
        <div style={{ marginBottom: 12 }}>
          <div className="ca-label">Nombre del paquete</div>
          <input className="ca-input" value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder={nombreFinal} />
        </div>
        <div style={{ display: "flex", gap: 11, marginBottom: 12 }}>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Medio de pago</div>
            <select className="ca-input" value={medio} onChange={(e) => setMedio(e.target.value)}>
              {MEDIOS_PAGO.map((m) => <option key={m.v} value={m.v}>{m.l}</option>)}
            </select>
          </div>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Comprobante</div>
            <select className="ca-input" value={comprobante} onChange={(e) => setComprobante(e.target.value)}>
              {COMPROBANTES.map((c) => <option key={c.v} value={c.v}>{c.l}</option>)}
            </select>
          </div>
        </div>
        {comprobante && (
          <div style={{ marginBottom: 12 }}>
            <div className="ca-label">N° de comprobante</div>
            <input className="ca-input" value={compNumero} onChange={(e) => setCompNumero(e.target.value)} placeholder="B001-123" />
          </div>
        )}

        <div style={{ display: "flex", gap: 9, justifyContent: "flex-end", marginTop: 18 }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" style={{ opacity: canSave ? 1 : 0.5, pointerEvents: canSave ? "auto" : "none" }} onClick={guardar}>
            Vender por {money(Number(monto) || 0)}
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
  const [medioOtro, setMedioOtro] = useState("");
  const [comprobante, setComprobante] = useState("");
  const [compNumero, setCompNumero] = useState("");
  const [fecha, setFecha] = useState(HOY_ISO);
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
    // "Otro" medio (giftcard, asumido por mkt/hub, etc.): el detalle se anota en el concepto.
    const detalleOtro = (estado === "pagado" && medio === "otro" && medioOtro.trim()) ? medioOtro.trim() : "";
    const conceptoFinal = detalleOtro ? `${concepto.trim() || "Cobro"} · ${detalleOtro}` : (concepto.trim() || undefined);
    onSave({
      paciente: sel.id,
      cita: prefill?.citaId || null,
      servicio: servicio || null,
      concepto: conceptoFinal,
      monto, estado, fecha,
      medio_pago: estado === "pagado" ? medio : "",
      comprobante_tipo: comprobante,
      comprobante_numero: compNumero.trim(),
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

        <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Fecha del pago</div>
            <input className="ca-input" type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} title="Fecha del pago (para cargar pagos antiguos)" />
          </div>
          {estado === "pagado" && (
            <div style={{ flex: 1 }}>
              <div className="ca-label">Medio de pago</div>
              <select className="ca-input" value={medio} onChange={(e) => setMedio(e.target.value)}>
                {MEDIOS_PAGO.map((m) => <option key={m.v} value={m.v}>{m.l}</option>)}
              </select>
            </div>
          )}
        </div>
        {estado === "pagado" && medio === "otro" && (
          <div style={{ marginBottom: 13 }}>
            <div className="ca-label">¿Cuál? <span style={{ color: "var(--muted)", fontWeight: 400, fontSize: 12 }}>(giftcard, asumido por mkt/hub…)</span></div>
            <input className="ca-input" value={medioOtro} onChange={(e) => setMedioOtro(e.target.value)} placeholder="Ej. giftcard / cortesía Hub" autoFocus />
          </div>
        )}

        <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
          <div style={{ flex: 1.3 }}>
            <div className="ca-label">Comprobante</div>
            <select className="ca-input" value={comprobante} onChange={(e) => setComprobante(e.target.value)}>
              {COMPROBANTES.map((c) => <option key={c.v} value={c.v}>{c.l}</option>)}
            </select>
          </div>
          {comprobante && (
            <div style={{ flex: 1 }}>
              <div className="ca-label">N° (opcional)</div>
              <input className="ca-input" value={compNumero} onChange={(e) => setCompNumero(e.target.value)} placeholder="B001-123" />
            </div>
          )}
        </div>

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

const SERVICIOS_SUGERIDOS = [
  { nombre: "Consulta psicológica", especialidad: "Consulta psicológica", precio: 75, monto_terapeuta: 20 },
  { nombre: "Sesión individual", especialidad: "Terapia individual", precio: 100, monto_terapeuta: 38 },
  { nombre: "Terapia de pareja", especialidad: "Terapia de pareja", precio: 130, monto_terapeuta: 0 },
  { nombre: "Terapia familiar", especialidad: "Terapia familiar", precio: 140, monto_terapeuta: 0 },
  { nombre: "Sesión infantil/adolescente", especialidad: "Terapia infantil/adolescente", precio: 100, monto_terapeuta: 0 },
  { nombre: "Evaluación psicológica", especialidad: "Evaluación psicológica", precio: 150, monto_terapeuta: 0 },
  { nombre: "Sesión brújula", especialidad: "", precio: 80, monto_terapeuta: 0 },
];

function PreciosModal({ onClose, showToast }) {
  const [lista, setLista] = useState(null);
  const [nombre, setNombre] = useState("");
  const [esp, setEsp] = useState("");
  const [precio, setPrecio] = useState("");
  const [sembrando, setSembrando] = useState(false);

  async function cargar() { setLista(await api.servicios()); }
  useEffect(() => { cargar().catch((e) => showToast("Error: " + e.message)); }, []);

  async function sembrarSugeridos() {
    const existentes = new Set((lista || []).map((s) => (s.nombre || "").trim().toLowerCase()));
    const faltan = SERVICIOS_SUGERIDOS.filter((s) => !existentes.has(s.nombre.toLowerCase()));
    if (faltan.length === 0) { showToast("Ya están todos los servicios sugeridos."); return; }
    setSembrando(true);
    try {
      for (const s of faltan) await api.crearServicio(s);
      await cargar();
      showToast(`${faltan.length} servicio(s) agregado(s) ✓ · ajusta precios y pago al terapeuta`);
    } catch (e) { showToast("Error: " + e.message); }
    finally { setSembrando(false); }
  }

  async function guardarCampo(s, campo, valor) {
    try { await api.actualizarServicio(s.id, { [campo]: valor }); await cargar(); showToast("Guardado ✓"); }
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
      <div className="ca-modal" style={{ maxWidth: 540 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <strong style={{ fontSize: 16 }}>Catálogo de precios</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>
        {!lista ? <div className="ca-empty">Cargando…</div> : (
          <>
            {lista.length === 0 && (
              <div style={{ background: "var(--accent-soft)", border: "1px solid #BEE7EF", borderRadius: 10, padding: 12, marginBottom: 12, fontSize: 13, lineHeight: 1.5 }}>
                Aún no hay servicios. Sin ellos no puedes elegir servicio al registrar un cobro ni calcular la liquidación.
                <div style={{ marginTop: 8 }}>
                  <button className="ca-btn" onClick={sembrarSugeridos} disabled={sembrando}>{sembrando ? "Agregando…" : "Agregar servicios sugeridos"}</button>
                </div>
              </div>
            )}
            <div style={{ display: "flex", gap: 8, padding: "0 4px 4px", fontSize: 11.5, color: "var(--muted)", fontWeight: 600 }}>
              <div style={{ flex: 1 }}>Servicio</div>
              <div style={{ width: 84, textAlign: "right" }} title="Lo que paga el paciente">Precio</div>
              <div style={{ width: 84, textAlign: "right" }} title="Lo que se le paga al psicólogo por cada sesión atendida de este servicio">Pago terapeuta</div>
              <div style={{ width: 44, textAlign: "center" }} title="¿Se ofrece en la página pública de reservas? (desmarca informes, reprogramación, etc.)">Web</div>
              <div style={{ width: 26 }} />
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: "46vh", overflowY: "auto", marginBottom: 14 }}>
              {lista.map((s) => (
                <div key={s.id} className="ca-adjrow">
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 14, fontWeight: 500 }}>{s.nombre}</div>
                    {s.especialidad && <div className="ca-pmeta">{s.especialidad}</div>}
                  </div>
                  <input className="ca-input" style={{ width: 84, marginTop: 0, textAlign: "right" }} defaultValue={s.precio} title="Precio de lista"
                    onBlur={(e) => { if (e.target.value && String(e.target.value) !== String(s.precio)) guardarCampo(s, "precio", e.target.value); }} inputMode="decimal" />
                  <input className="ca-input" style={{ width: 84, marginTop: 0, textAlign: "right" }} defaultValue={s.monto_terapeuta} title="Pago al terapeuta por cada sesión atendida de este servicio"
                    onBlur={(e) => { if (String(e.target.value) !== String(s.monto_terapeuta)) guardarCampo(s, "monto_terapeuta", e.target.value || 0); }} inputMode="decimal" />
                  <label style={{ width: 44, display: "flex", justifyContent: "center", alignItems: "center", cursor: "pointer" }} title="¿Se ofrece en la web pública de reservas?">
                    <input type="checkbox" checked={s.reservable_web !== false} onChange={(e) => guardarCampo(s, "reservable_web", e.target.checked)} />
                  </label>
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
            <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 12 }}>Edita un valor y haz clic afuera para guardarlo. <strong>Pago terapeuta</strong> es lo que se le paga al psicólogo por cada sesión atendida de ese servicio (la Liquidación es sesiones atendidas × ese monto). {lista.length > 0 && <button className="ca-link" onClick={sembrarSugeridos} disabled={sembrando}>Agregar servicios sugeridos</button>}</div>
          </>
        )}
      </div>
    </div>
  );
}

const ROLES = [
  { v: "medico", l: "Psicólogo/a" },
  { v: "asistente", l: "Asistente (coordinación)" },
  { v: "comercial", l: "Comercial" },
  { v: "admin", l: "Administrador (gerencia)" },
];
const ROL_COLOR = {
  admin: { bg: "#EDE6F4", fg: "#6B4E96" },
  medico: { bg: "#E3F0E8", fg: "#2F6B4F" },
  asistente: { bg: "#E2ECF5", fg: "#2E5C86" },
  comercial: { bg: "#F7ECDD", fg: "#9C6B2E" },
};

const SEDES = [{ v: "piura", l: "Piura" }, { v: "lima", l: "Lima" }];
const PROCESOS = ["", "consulta", "primero", "segundo", "tercero", "cuarto", "quinto", "sexto", "septimo", "octavo", "noveno", "decimo", "quincenal", "mensual"];
const MODALIDADES = [
  { v: "presencial", l: "Presencial" }, { v: "virtual", l: "Virtual" }, { v: "ambas", l: "Presencial y virtual" },
];

function Profesionales({ showToast, esAdmin }) {
  const [lista, setLista] = useState(null);
  const [editar, setEditar] = useState(null);
  const [sede, setSede] = useState(null);
  const [frec, setFrec] = useState(""); // "", semanal, quincenal, esporadico
  const [verPacientes, setVerPacientes] = useState(null);

  async function cargar() { setLista(await api.profesionales()); }
  useEffect(() => { cargar().catch((e) => showToast("Error: " + e.message)); }, []);

  const nActivos = (p) => p.pacientes_stats ? (frec ? (p.pacientes_stats[frec] || 0) : p.pacientes_stats.activos) : 0;

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
        <div style={{ display: "flex", gap: 9, alignItems: "center" }}>
          <ExportBtns nombre="profesionales" titulo="Profesionales" disabled={!filtradas || filtradas.length === 0}
            headers={["Nombre", "Titulo", "Colegiatura", "Sede", "Modalidad", "Enfoque", "Atiende", "Activo"]}
            filas={(filtradas || []).map((p) => [p.nombre, p.titulo, p.colegiatura, p.sede_label, p.modalidad_label, p.enfoque, p.poblaciones, p.activo ? "Sí" : "No"])} />
          {esAdmin && <button className="ca-btn" onClick={() => setEditar({ new: true })}><Plus size={16} strokeWidth={2.2} /> Nuevo profesional</button>}
        </div>
      </div>

      <div className="ca-fchips" style={{ marginTop: 18, display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center" }}>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          <button className={`ca-fchip ${!sede ? "on" : ""}`} onClick={() => setSede(null)}>Todas las sedes</button>
          {SEDES.map((s) => <button key={s.v} className={`ca-fchip ${sede === s.v ? "on" : ""}`} onClick={() => setSede(s.v)}>{s.l}</button>)}
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
          <span className="ca-pmeta">Pacientes activos:</span>
          {[["", "Todos"], ["semanal", "Semanales"], ["quincenal", "Quincenales"], ["esporadico", "Esporádicos"]].map(([v, l]) => (
            <button key={v || "all"} className={`ca-fchip ${frec === v ? "on" : ""}`} onClick={() => setFrec(v)}>{l}</button>
          ))}
        </div>
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
                    {p.horas_disponibles > 0 && <Tag colors={{ bg: "#E7EEF6", fg: "#3D5C82" }}>{p.horas_disponibles} h/sem</Tag>}
                    {!p.activo && <Tag colors={{ bg: "#F7E5E5", fg: "#9C4646" }}>Inactivo</Tag>}
                  </div>
                </div>
              </div>
              {p.enfoque && <div style={{ fontSize: 13, color: "var(--ink-soft)", lineHeight: 1.5, marginBottom: 6 }}>{p.enfoque}</div>}
              {p.poblaciones && <div className="ca-pmeta" style={{ marginBottom: 6 }}><b>Atiende:</b> {p.poblaciones}</div>}
              {p.frase && <div style={{ fontSize: 12.5, fontStyle: "italic", color: "var(--muted)", marginTop: 4 }}>“{p.frase}”</div>}
              {p.pacientes_stats && (
                <div style={{ display: "flex", alignItems: "baseline", gap: 8, flexWrap: "wrap", marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--line)" }}>
                  <span style={{ fontSize: 20, fontWeight: 700, color: "var(--accent)" }}>{nActivos(p)}</span>
                  <span className="ca-pmeta">{frec ? `activos ${frec === "semanal" ? "semanales" : frec === "quincenal" ? "quincenales" : "esporádicos"}` : "pacientes activos"}</span>
                  {!frec && (
                    <span style={{ display: "flex", gap: 6, marginLeft: "auto", flexWrap: "wrap" }}>
                      <Tag colors={{ bg: "#E7EEF6", fg: "#3D5C82" }}>{p.pacientes_stats.semanal} sem</Tag>
                      <Tag colors={{ bg: "#EDE6F4", fg: "#6B4E96" }}>{p.pacientes_stats.quincenal} quinc</Tag>
                      {p.pacientes_stats.esporadico > 0 && <Tag colors={{ bg: "#EFEDE8", fg: "#7C7870" }}>{p.pacientes_stats.esporadico} espor</Tag>}
                      {p.pacientes_stats.sin_frecuencia > 0 && <Tag colors={{ bg: "#FBF1DD", fg: "#8A6D2E" }} >{p.pacientes_stats.sin_frecuencia} sin frec.</Tag>}
                    </span>
                  )}
                </div>
              )}
              <div style={{ display: "flex", gap: 8, marginTop: 12, alignItems: "center", flexWrap: "wrap" }}>
                <button className="ca-mini" onClick={() => setVerPacientes(p)}>
                  <Users size={13} strokeWidth={2} /> {p.n_pacientes} en total
                </button>
                {esAdmin && <button className="ca-mini" onClick={() => setEditar(p)}><Pencil size={13} strokeWidth={2} /> Editar ficha</button>}
                {esAdmin && <button className="ca-iconbtn" title="Eliminar" onClick={() => eliminar(p)}><Trash2 size={14} strokeWidth={2} /></button>}
              </div>
            </div>
          ))}
        </div>
      )}

      {editar && <ProfesionalModal prof={editar.new ? null : editar} onClose={() => setEditar(null)} onSave={guardar} />}
      {verPacientes && <PacientesDeProfesionalModal prof={verPacientes} onClose={() => setVerPacientes(null)} showToast={showToast} />}
    </div>
  );
}

function PacientesDeProfesionalModal({ prof, onClose, showToast }) {
  const [pacs, setPacs] = useState(null);
  useEffect(() => {
    api.pacientesDeProfesional(prof.id)
      .then(setPacs)
      .catch((e) => { showToast("Error: " + e.message); setPacs([]); });
  }, [prof.id]);

  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 480, maxHeight: "85vh", overflowY: "auto" }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
          <strong style={{ fontSize: 16 }}>Pacientes de {prof.nombre}</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>
        <div className="ca-pmeta" style={{ marginBottom: 14 }}>{prof.sede_label} · {pacs ? `${pacs.length} en proceso` : "…"}</div>
        {!pacs ? <div className="ca-empty">Cargando…</div> : pacs.length === 0 ? (
          <div className="ca-empty">Sin pacientes asignados.</div>
        ) : (
          pacs.map((p) => {
            const meta = p.proceso === "consulta"
              ? "Consulta inicial"
              : `${p.n_sesion ? `Sesión ${p.n_sesion}` : ""}${p.n_sesion && p.proceso_label ? " · " : ""}${p.proceso_label || ""}`;
            return (
              <div key={p.id} className="ca-row" style={{ cursor: "default" }}>
                <div className="ca-avatar" style={{ width: 36, height: 36, fontSize: 13 }}>{iniciales(p.nombre)}</div>
                <div style={{ flex: 1 }}>
                  <div className="ca-pname" style={{ fontSize: 14 }}>{p.nombre}</div>
                  <div className="ca-pmeta">{meta || "—"}</div>
                </div>
              </div>
            );
          })
        )}
      </div>
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
    horas_disponibles: prof?.horas_disponibles ?? 0,
    porcentaje_liquidacion: prof?.porcentaje_liquidacion ?? 0,
    horario_semanal: prof?.horario_semanal || {},
    horario_modalidad: prof?.horario_modalidad || {},
  });
  const [foto, setFoto] = useState(null);
  const set = (k) => (e) => setF((prev) => ({ ...prev, [k]: e.target.value }));
  const canSave = f.nombre.trim().length > 0;
  const ta = { minHeight: 70, resize: "vertical", lineHeight: 1.5 };
  // Cada clic cicla: apagada → presencial → virtual → mixto → apagada.
  // Estado de una celda: "" apagada · "activo" (hora ya marcada, sin modalidad, p.ej.
  // horarios cargados antes) · presencial/virtual/mixto. El clic cicla:
  // apagada/activo → presencial → virtual → mixto → apagada.
  const MOD_CICLO = { "": "presencial", activo: "presencial", presencial: "virtual", virtual: "mixto", mixto: "" };
  const MOD_COLOR = { presencial: "#4F8A77", virtual: "#3D6B9E", mixto: "#8A6BB0" };
  function estadoDe(dia, hora) {
    const mod = ((f.horario_modalidad || {})[dia] || {})[hora];
    if (mod) return mod;
    // sin modalidad pero la hora ya está en el horario → "activo" (no invisible)
    return ((f.horario_semanal || {})[dia] || []).map(Number).includes(hora) ? "activo" : "";
  }
  function toggleHora(dia, hora) {
    setF((prev) => {
      const mod = ((prev.horario_modalidad || {})[dia] || {})[hora];
      const activa = ((prev.horario_semanal || {})[dia] || []).map(Number).includes(hora);
      const actual = mod || (activa ? "activo" : "");
      const nueva = MOD_CICLO[actual];
      // horas (capacidad/landing): presente si queda en cualquier modalidad ON
      const h = { ...(prev.horario_semanal || {}) };
      const list = new Set((h[dia] || []).map(Number));
      if (nueva) list.add(hora); else list.delete(hora);
      const arr = [...list].sort((a, b) => a - b);
      if (arr.length) h[dia] = arr; else delete h[dia];
      // modalidad por hora
      const m = { ...(prev.horario_modalidad || {}) };
      const md = { ...(m[dia] || {}) };
      if (nueva) md[hora] = nueva; else delete md[hora];
      if (Object.keys(md).length) m[dia] = md; else delete m[dia];
      return { ...prev, horario_semanal: h, horario_modalidad: m };
    });
  }

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
          <div style={{ width: 90 }}><div className="ca-label">Horas/sem</div><input className="ca-input" value={f.horas_disponibles} onChange={(e) => setF((prev) => ({ ...prev, horas_disponibles: e.target.value.replace(/[^\d]/g, "") }))} inputMode="numeric" /></div>
          <div style={{ width: 100 }}><div className="ca-label" title="Porcentaje de lo cobrado que se le paga">% honorarios</div><input className="ca-input" value={f.porcentaje_liquidacion} onChange={(e) => setF((prev) => ({ ...prev, porcentaje_liquidacion: e.target.value.replace(/[^\d.]/g, "") }))} inputMode="decimal" placeholder="40" /></div>
        </div>
        <div style={{ marginBottom: 12 }}><div className="ca-label">Enfoque</div><textarea className="ca-input" style={ta} value={f.enfoque} onChange={set("enfoque")} placeholder="Psicoterapeuta clínica con enfoque…" /></div>
        <div style={{ marginBottom: 12 }}><div className="ca-label">Poblaciones que atiende</div><input className="ca-input" value={f.poblaciones} onChange={set("poblaciones")} placeholder="Niños, adolescentes, adultos, parejas" /></div>
        <div style={{ marginBottom: 12 }}><div className="ca-label">Problemáticas que acompaña</div><textarea className="ca-input" style={ta} value={f.problematicas} onChange={set("problematicas")} /></div>
        <div style={{ marginBottom: 12 }}><div className="ca-label">Formación / especialidades</div><textarea className="ca-input" style={ta} value={f.formacion} onChange={set("formacion")} /></div>
        <div style={{ marginBottom: 12 }}><div className="ca-label">Trayectoria</div><textarea className="ca-input" style={ta} value={f.trayectoria} onChange={set("trayectoria")} /></div>
        <div style={{ marginBottom: 12 }}><div className="ca-label">Frase / lema</div><input className="ca-input" value={f.frase} onChange={set("frase")} /></div>

        <div className="ca-secth" style={{ margin: "4px 0 8px" }}>Horario de atención <span style={{ color: "var(--muted)", fontWeight: 400, fontSize: 12 }}>(clic para ciclar: presencial → virtual → mixto → libre)</span></div>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 8, fontSize: 12 }}>
          {[["Presencial", "#4F8A77"], ["Virtual", "#3D6B9E"], ["Mixto", "#8A6BB0"], ["Sin especificar", "#9AA0A6"]].map(([l, col]) => (
            <span key={l} style={{ display: "inline-flex", alignItems: "center", gap: 5 }}><span style={{ width: 12, height: 12, borderRadius: 3, background: col, display: "inline-block" }} /> {l}</span>
          ))}
        </div>
        <div style={{ overflowX: "auto", marginBottom: 16 }}>
          <table style={{ borderCollapse: "collapse", fontSize: 11 }}>
            <thead><tr><th></th>{[["1", "Lun"], ["2", "Mar"], ["3", "Mié"], ["4", "Jue"], ["5", "Vie"], ["6", "Sáb"]].map(([d, l]) => <th key={d} style={{ padding: "2px 5px", color: "var(--muted)", fontWeight: 600 }}>{l}</th>)}</tr></thead>
            <tbody>
              {Array.from({ length: 15 }, (_, i) => 7 + i).map((h) => (
                <tr key={h}>
                  <td style={{ color: "var(--muted)", paddingRight: 6, textAlign: "right", whiteSpace: "nowrap" }}>{h}:00</td>
                  {["1", "2", "3", "4", "5", "6"].map((d) => {
                    const est = estadoDe(d, h);
                    const bg = est === "activo" ? "#9AA0A6" : (MOD_COLOR[est] || "var(--bg)");
                    return (
                      <td key={d} style={{ padding: 2 }}>
                        <button type="button" title={`${["", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"][d]} ${h}:00${est && est !== "activo" ? ` · ${est}` : est === "activo" ? " · sin modalidad" : ""}`} onClick={() => toggleHora(d, h)}
                          style={{ width: 36, height: 20, borderRadius: 4, cursor: "pointer", border: "1px solid var(--line)", background: bg }} />
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

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
            onClick={() => onSave({ ...(prof?.id ? { id: prof.id } : {}), ...f, nombre: f.nombre.trim(), horas_disponibles: Number(f.horas_disponibles) || 0, porcentaje_liquidacion: Number(f.porcentaje_liquidacion) || 0 }, foto)}>Guardar</button>
        </div>
      </div>
    </div>
  );
}

const MES_ABBR = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
const MESES_FULL = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
const COL_PIURA = "#0A7D92";
const COL_LIMA = "#E08D3C";

function Historico({ showToast, esAdmin }) {
  const [rows, setRows] = useState(null);
  const [anio, setAnio] = useState(null);
  const [editar, setEditar] = useState(null);

  async function cargar() {
    const r = await api.metricas();
    setRows(r);
    setAnio((a) => a || (r.length ? Math.max(...r.map((x) => x.anio)) : null));
  }
  useEffect(() => { cargar().catch((e) => showToast("Error: " + e.message)); }, []);

  async function guardar(data) {
    try {
      if (data.id) await api.actualizarMetrica(data.id, data);
      else await api.crearMetrica(data);
      await cargar();
      setEditar(null);
      showToast(data.id ? "Mes actualizado ✓" : "Mes agregado ✓");
    } catch (e) { showToast("Error: " + e.message); }
  }
  async function eliminar(r) {
    if (!window.confirm(`¿Eliminar ${r.sede_label} · ${r.mes_label} ${r.anio}?`)) return;
    try { await api.eliminarMetrica(r.id); await cargar(); showToast("Mes eliminado"); }
    catch (e) { showToast("Error: " + e.message); }
  }

  if (!rows) return <div className="ca-empty">Cargando…</div>;

  const anios = [...new Set(rows.map((r) => r.anio))].sort((a, b) => b - a);
  const delAnio = rows.filter((r) => r.anio === anio);
  const piura = {}, lima = {};
  delAnio.forEach((r) => { (r.sede === "piura" ? piura : lima)[r.mes] = r; });
  const meses = [...new Set(delAnio.map((r) => r.mes))].sort((a, b) => a - b);
  const serie = meses.map((m) => ({ abbr: MES_ABBR[m], p: piura[m], l: lima[m] }));

  const tot = (map) => {
    const arr = Object.values(map);
    const inv = arr.reduce((s, r) => s + Number(r.invertido), 0);
    const cit = arr.reduce((s, r) => s + r.citas_nuevas, 0);
    const pac = arr.reduce((s, r) => s + r.pacientes, 0);
    const led = arr.reduce((s, r) => s + (r.leads || 0), 0);
    return { inv, cit, pac, led, cac: pac ? inv / pac : 0, cpl: led ? inv / led : 0, conv: led ? pac / led : 0 };
  };
  const tp = tot(piura), tl = tot(lima);
  const filas = [...delAnio].sort((a, b) => a.mes - b.mes || (a.sede < b.sede ? -1 : 1));
  const ent = (v) => String(Math.round(v));

  return (
    <div>
      <div className="ca-tophead">
        <div>
          <h1 className="ca-h1">Histórico de marketing</h1>
          <div className="ca-sub">Inversión, captación y CAC por sede · {anio}</div>
        </div>
        <div style={{ display: "flex", gap: 9, alignItems: "center" }}>
          <ExportBtns nombre={`historico_marketing_${anio}`} titulo={`Histórico de marketing · ${anio}`} disabled={filas.length === 0}
            headers={["Año", "Mes", "Sede", "Invertido", "Mensajes", "Leads", "Citas nuevas", "Pacientes", "CAC", "Costo/lead", "Conversion %"]}
            filas={filas.map((r) => [r.anio, r.mes_label, r.sede_label, Number(r.invertido), r.mensajes, r.leads, r.citas_nuevas, r.pacientes, Math.round(r.cac), Math.round(r.costo_lead), Math.round((r.conversion || 0) * 100)])} />
          {esAdmin && <button className="ca-btn" onClick={() => setEditar({ new: true, anio })}><Plus size={16} strokeWidth={2.2} /> Agregar mes</button>}
        </div>
      </div>

      <div className="ca-fchips" style={{ marginTop: 18 }}>
        {anios.map((a) => (
          <button key={a} className={`ca-fchip ${anio === a ? "on" : ""}`} onClick={() => setAnio(a)}>{a}</button>
        ))}
      </div>

      {/* Resumen del año por sede */}
      <div className="ca-stats" style={{ marginTop: 18, marginBottom: 6 }}>
        {[["Piura", tp, COL_PIURA], ["Lima", tl, COL_LIMA]].map(([nombre, t, color]) => (
          <div key={nombre} className="ca-card" style={{ flex: 1, minWidth: 240, borderTop: `3px solid ${color}` }}>
            <div style={{ fontWeight: 600, marginBottom: 10 }}>{nombre} · {anio}</div>
            <div style={{ display: "flex", gap: 18, flexWrap: "wrap" }}>
              <div><div className="ca-pmeta">Invertido</div><div style={{ fontWeight: 600 }}>{money(t.inv)}</div></div>
              <div><div className="ca-pmeta">Leads</div><div style={{ fontWeight: 600 }}>{t.led}</div></div>
              <div><div className="ca-pmeta">Citas nuevas</div><div style={{ fontWeight: 600 }}>{t.cit}</div></div>
              <div><div className="ca-pmeta">Pacientes</div><div style={{ fontWeight: 600 }}>{t.pac}</div></div>
              <div><div className="ca-pmeta">Costo/lead</div><div style={{ fontWeight: 600 }}>{money(t.cpl)}</div></div>
              <div><div className="ca-pmeta">CAC (costo/pac.)</div><div style={{ fontWeight: 600 }}>{money(t.cac)}</div></div>
              <div><div className="ca-pmeta">Conversión</div><div style={{ fontWeight: 600 }}>{Math.round(t.conv * 100)}%</div></div>
            </div>
          </div>
        ))}
      </div>

      {serie.length === 0 ? <div className="ca-empty">No hay datos para {anio}.</div> : (
        <div className="ca-charts2">
          <div className="ca-card">
            <div className="ca-secth" style={{ marginTop: 0 }}>Inversión mensual (S/)</div>
            <MiniBarsDuo data={serie} a={(d) => (d.p ? Number(d.p.invertido) : 0)} b={(d) => (d.l ? Number(d.l.invertido) : 0)}
              etiqueta={(d) => d.abbr} labelA="Piura" labelB="Lima" colorA={COL_PIURA} colorB={COL_LIMA} fmt={money} />
          </div>
          <div className="ca-card">
            <div className="ca-secth" style={{ marginTop: 0 }}>CAC — costo por paciente (S/)</div>
            <MiniBarsDuo data={serie} a={(d) => (d.p ? d.p.cac : 0)} b={(d) => (d.l ? d.l.cac : 0)}
              etiqueta={(d) => d.abbr} labelA="Piura" labelB="Lima" colorA={COL_PIURA} colorB={COL_LIMA} fmt={money} />
          </div>
          <div className="ca-card">
            <div className="ca-secth" style={{ marginTop: 0 }}>Citas nuevas</div>
            <MiniBarsDuo data={serie} a={(d) => (d.p ? d.p.citas_nuevas : 0)} b={(d) => (d.l ? d.l.citas_nuevas : 0)}
              etiqueta={(d) => d.abbr} labelA="Piura" labelB="Lima" colorA={COL_PIURA} colorB={COL_LIMA} fmt={ent} />
          </div>
          <div className="ca-card">
            <div className="ca-secth" style={{ marginTop: 0 }}>Pacientes nuevos</div>
            <MiniBarsDuo data={serie} a={(d) => (d.p ? d.p.pacientes : 0)} b={(d) => (d.l ? d.l.pacientes : 0)}
              etiqueta={(d) => d.abbr} labelA="Piura" labelB="Lima" colorA={COL_PIURA} colorB={COL_LIMA} fmt={ent} />
          </div>
        </div>
      )}

      {/* Tabla detalle */}
      <div className="ca-card" style={{ marginTop: 16, overflowX: "auto" }}>
        <table className="ca-table">
          <thead>
            <tr>
              <th>Mes</th><th>Sede</th><th style={{ textAlign: "right" }}>Invertido</th>
              <th style={{ textAlign: "right" }}>Msjs</th><th style={{ textAlign: "right" }}>Leads</th><th style={{ textAlign: "right" }}>Citas</th>
              <th style={{ textAlign: "right" }}>Pac.</th><th style={{ textAlign: "right" }}>CAC</th>
              <th style={{ textAlign: "right" }}>C/lead</th><th style={{ textAlign: "right" }}>Conv.</th>
              {esAdmin && <th></th>}
            </tr>
          </thead>
          <tbody>
            {filas.map((r) => (
              <tr key={r.id}>
                <td>{r.mes_label}</td>
                <td><span style={{ color: r.sede === "piura" ? COL_PIURA : COL_LIMA, fontWeight: 600 }}>{r.sede_label}</span></td>
                <td style={{ textAlign: "right" }}>{money(Number(r.invertido))}</td>
                <td style={{ textAlign: "right" }}>{r.mensajes}</td>
                <td style={{ textAlign: "right" }}>{r.leads}</td>
                <td style={{ textAlign: "right" }}>{r.citas_nuevas}</td>
                <td style={{ textAlign: "right" }}>{r.pacientes}</td>
                <td style={{ textAlign: "right" }}>{money(r.cac)}</td>
                <td style={{ textAlign: "right" }}>{money(r.costo_lead)}</td>
                <td style={{ textAlign: "right" }}>{Math.round((r.conversion || 0) * 100)}%</td>
                {esAdmin && (
                  <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                    <button className="ca-iconbtn" title="Editar" onClick={() => setEditar(r)}><Pencil size={13} strokeWidth={2} /></button>
                    <button className="ca-iconbtn" title="Eliminar" onClick={() => eliminar(r)}><Trash2 size={13} strokeWidth={2} /></button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {editar && <MetricaModal metrica={editar.new ? null : editar} anioDefault={editar.anio || anio} onClose={() => setEditar(null)} onSave={guardar} />}
    </div>
  );
}

function MetricaModal({ metrica, anioDefault, onClose, onSave }) {
  const [f, setF] = useState({
    sede: metrica?.sede || "piura",
    anio: metrica?.anio || anioDefault || 2026,
    mes: metrica?.mes || 1,
    invertido: metrica?.invertido ?? "",
    mensajes: metrica?.mensajes ?? "",
    leads: metrica?.leads ?? "",
    citas_nuevas: metrica?.citas_nuevas ?? "",
    pacientes: metrica?.pacientes ?? "",
    nota: metrica?.nota || "",
  });
  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));
  const num = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value.replace(/[^\d.]/g, "") }));

  function guardar() {
    onSave({
      ...(metrica?.id ? { id: metrica.id } : {}),
      sede: f.sede, anio: Number(f.anio), mes: Number(f.mes),
      invertido: Number(f.invertido || 0), mensajes: Number(f.mensajes || 0),
      leads: Number(f.leads || 0),
      citas_nuevas: Number(f.citas_nuevas || 0), pacientes: Number(f.pacientes || 0),
      nota: f.nota,
    });
  }

  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 440 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <strong style={{ fontSize: 16 }}>{metrica ? "Editar mes" : "Agregar mes"}</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>
        <div style={{ display: "flex", gap: 11, marginBottom: 12 }}>
          <div style={{ flex: 1 }}><div className="ca-label">Sede</div><select className="ca-input" value={f.sede} onChange={set("sede")}>{SEDES.map((s) => <option key={s.v} value={s.v}>{s.l}</option>)}</select></div>
          <div style={{ flex: 1 }}><div className="ca-label">Mes</div><select className="ca-input" value={f.mes} onChange={set("mes")}>{MESES_FULL.slice(1).map((m, i) => <option key={i + 1} value={i + 1}>{m}</option>)}</select></div>
          <div style={{ width: 90 }}><div className="ca-label">Año</div><input className="ca-input" value={f.anio} onChange={num("anio")} /></div>
        </div>
        <div style={{ display: "flex", gap: 11, marginBottom: 12 }}>
          <div style={{ flex: 1 }}><div className="ca-label">Invertido S/</div><input className="ca-input" value={f.invertido} onChange={num("invertido")} placeholder="1453.25" /></div>
          <div style={{ flex: 1 }}><div className="ca-label">Mensajes</div><input className="ca-input" value={f.mensajes} onChange={num("mensajes")} /></div>
          <div style={{ flex: 1 }}><div className="ca-label">Leads</div><input className="ca-input" value={f.leads} onChange={num("leads")} /></div>
        </div>
        <div style={{ display: "flex", gap: 11, marginBottom: 12 }}>
          <div style={{ flex: 1 }}><div className="ca-label">Citas nuevas</div><input className="ca-input" value={f.citas_nuevas} onChange={num("citas_nuevas")} /></div>
          <div style={{ flex: 1 }}><div className="ca-label">Pacientes nuevos</div><input className="ca-input" value={f.pacientes} onChange={num("pacientes")} /></div>
        </div>
        <div style={{ marginBottom: 18 }}><div className="ca-label">Nota (opcional)</div><input className="ca-input" value={f.nota} onChange={set("nota")} /></div>
        <div style={{ display: "flex", gap: 9, justifyContent: "flex-end" }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" onClick={guardar}>Guardar</button>
        </div>
      </div>
    </div>
  );
}

const SEM = {
  verde: { bg: "#E4F3E8", fg: "#1E7D45", dot: "#2BA35A", l: "Verde" },
  amarillo: { bg: "#FBF0D4", fg: "#8A6D14", dot: "#E0A82E", l: "Amarillo" },
  rojo: { bg: "#FAE2E2", fg: "#B23B3B", dot: "#D85656", l: "Rojo" },
};

function RepCard({ label, valor, sub }) {
  return (
    <div className="ca-card" style={{ flex: 1, minWidth: 170 }}>
      <div className="ca-pmeta">{label}</div>
      <div style={{ fontSize: 22, fontWeight: 600, margin: "4px 0 2px" }}>{valor}</div>
      <div className="ca-pmeta">{sub}</div>
    </div>
  );
}

function ReporteSemanal({ showToast, esAdmin }) {
  const [lista, setLista] = useState(null);
  const [selId, setSelId] = useState(null);
  const [editar, setEditar] = useState(null);

  async function cargar() {
    const r = await api.reportesSemanales();
    setLista(r);
    setSelId((id) => id || (r[0]?.id ?? null));
  }
  useEffect(() => { cargar().catch((e) => showToast("Error: " + e.message)); }, []);

  async function guardar(data) {
    try {
      const r = data.id ? await api.actualizarReporte(data.id, data) : await api.crearReporte(data);
      await cargar(); setEditar(null); setSelId(r.id);
      showToast(data.id ? "Reporte actualizado ✓" : "Reporte creado ✓");
    } catch (e) { showToast("Error: " + e.message); }
  }
  async function eliminar(r) {
    if (!window.confirm(`¿Eliminar ${r.periodo_label}?`)) return;
    try { await api.eliminarReporte(r.id); setSelId(null); await cargar(); showToast("Reporte eliminado"); }
    catch (e) { showToast("Error: " + e.message); }
  }

  if (!lista) return <div className="ca-empty">Cargando…</div>;
  const rep = lista.find((r) => r.id === selId) || lista[0];

  return (
    <div>
      <div className="ca-tophead">
        <div>
          <h1 className="ca-h1">Reporte semanal</h1>
          <div className="ca-sub">Tablero ejecutivo para el directorio</div>
        </div>
        <div style={{ display: "flex", gap: 9, alignItems: "center" }}>
          <ExportBtns nombre={`reporte_${rep?.periodo_label || ""}`} titulo={`Reporte semanal${rep?.periodo_label ? " · " + rep.periodo_label : ""}`}
            disabled={!rep || !rep.semaforo || rep.semaforo.length === 0}
            headers={["Indicador", "Valor", "Meta", "Estado"]}
            filas={(rep?.semaforo || []).map((s) => [s.area, s.valor, s.meta, (SEM[s.estado] || SEM.rojo).l])} />
          {esAdmin && <button className="ca-btn" onClick={() => setEditar({ new: true })}><Plus size={16} strokeWidth={2.2} /> Nuevo reporte</button>}
        </div>
      </div>

      {lista.length === 0 ? (
        <div className="ca-empty">Aún no hay reportes.{esAdmin ? " Crea el primero arriba." : ""}</div>
      ) : (
        <>
          <div className="ca-fchips" style={{ marginTop: 18 }}>
            {lista.map((r) => (
              <button key={r.id} className={`ca-fchip ${rep.id === r.id ? "on" : ""}`} onClick={() => setSelId(r.id)}>{r.periodo_label}</button>
            ))}
          </div>

          <div className="ca-card" style={{ marginTop: 14, display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10 }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: 16 }}>{rep.periodo_label}</div>
              <div className="ca-pmeta">Del {rep.fecha_inicio} al {rep.fecha_fin}</div>
            </div>
            {esAdmin && (
              <div style={{ display: "flex", gap: 8 }}>
                <button className="ca-mini" onClick={() => setEditar(rep)}><Pencil size={13} strokeWidth={2} /> Editar</button>
                <button className="ca-iconbtn" title="Eliminar" onClick={() => eliminar(rep)}><Trash2 size={14} strokeWidth={2} /></button>
              </div>
            )}
          </div>

          <div className="ca-stats" style={{ marginTop: 14 }}>
            <RepCard label="Facturación del mes" valor={money(rep.fact_total)} sub={`Meta ${money(Number(rep.meta_min_sede) * 2)}`} />
            <RepCard label="Leads de la semana" valor={rep.leads_total} sub={`${rep.conv_consulta}% pasó a consulta`} />
            <RepCard label="Pacientes activos" valor={rep.pac_activos_lima + rep.pac_activos_piura} sub={`${rep.pac_activos_piura} Piura · ${rep.pac_activos_lima} Lima`} />
            <RepCard label="Proyección de cierre" valor={money(rep.proy_total)} sub={`Sin próxima sesión: ${rep.sin_proxima}`} />
          </div>

          <div className="ca-secth" style={{ marginTop: 22 }}>Semáforo para el directorio</div>
          <div className="ca-card" style={{ overflowX: "auto" }}>
            <table className="ca-table">
              <thead><tr><th>Indicador</th><th>Valor</th><th>Meta</th><th>Estado</th></tr></thead>
              <tbody>
                {rep.semaforo.map((s, i) => {
                  const c = SEM[s.estado] || SEM.rojo;
                  return (
                    <tr key={i}>
                      <td>{s.area}</td>
                      <td style={{ fontWeight: 600 }}>{s.valor}</td>
                      <td style={{ color: "var(--muted)" }}>{s.meta}</td>
                      <td><span style={{ display: "inline-flex", alignItems: "center", gap: 6, background: c.bg, color: c.fg, padding: "2px 10px", borderRadius: 20, fontSize: 12, fontWeight: 600 }}><span style={{ width: 8, height: 8, borderRadius: "50%", background: c.dot }} /> {c.l}</span></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {rep.novedades && (<><div className="ca-secth" style={{ marginTop: 22 }}>Novedades de la semana</div><div className="ca-card" style={{ whiteSpace: "pre-wrap", lineHeight: 1.6 }}>{rep.novedades}</div></>)}
          {rep.decisiones && (<><div className="ca-secth" style={{ marginTop: 22 }}>Decisiones requeridas</div><div className="ca-card" style={{ whiteSpace: "pre-wrap", lineHeight: 1.6 }}>{rep.decisiones}</div></>)}
        </>
      )}

      {editar && <ReporteModal reporte={editar.new ? null : editar} onClose={() => setEditar(null)} onSave={guardar} showToast={showToast} />}
    </div>
  );
}

function ReporteModal({ reporte, onClose, onSave, showToast }) {
  const r = reporte || {};
  const [f, setF] = useState({
    semana: r.semana ?? 1, mes: r.mes ?? 6, anio: r.anio ?? 2026,
    fecha_inicio: r.fecha_inicio || "", fecha_fin: r.fecha_fin || "", novedades: r.novedades || "",
    fact_lima: r.fact_lima ?? 0, fact_piura: r.fact_piura ?? 0,
    meta_min_sede: r.meta_min_sede ?? 20000, meta_ideal_sede: r.meta_ideal_sede ?? 30000,
    proy_lima: r.proy_lima ?? 0, proy_piura: r.proy_piura ?? 0,
    leads_lima: r.leads_lima ?? 0, leads_piura: r.leads_piura ?? 0,
    consultas_agendadas: r.consultas_agendadas ?? 0, pacientes_iniciaron: r.pacientes_iniciaron ?? 0,
    videos_publicados: r.videos_publicados ?? 0, videos_planificados: r.videos_planificados ?? 0,
    invertido_lima: r.invertido_lima ?? 0, invertido_piura: r.invertido_piura ?? 0,
    pac_activos_lima: r.pac_activos_lima ?? 0, pac_activos_piura: r.pac_activos_piura ?? 0,
    retencion_lima: r.retencion_lima ?? 0, retencion_piura: r.retencion_piura ?? 0,
    sin_proxima: r.sin_proxima ?? 0, ocupacion_lima: r.ocupacion_lima ?? 0, ocupacion_piura: r.ocupacion_piura ?? 0,
    decisiones: r.decisiones || "", compromisos: r.compromisos || "",
  });
  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));

  // Campo numérico compacto
  const N = (k, label, w) => (
    <div style={{ flex: w || 1, minWidth: 80 }}>
      <div className="ca-label">{label}</div>
      <input className="ca-input" value={f[k]} onChange={(e) => setF((p) => ({ ...p, [k]: e.target.value.replace(/[^\d.]/g, "") }))} inputMode="decimal" />
    </div>
  );

  async function traerReales() {
    if (!f.fecha_inicio || !f.fecha_fin) { showToast && showToast("Primero pon las fechas de inicio y fin."); return; }
    try {
      const d = await api.sugerirReporte({ desde: f.fecha_inicio, hasta: f.fecha_fin, anio: f.anio, mes: f.mes, semana: f.semana });
      setF((p) => ({ ...p, ...d }));
      showToast && showToast("Datos reales traídos ✓ (revisa y completa el resto)");
    } catch (e) { showToast && showToast("Error: " + e.message); }
  }

  function guardar() {
    const numK = ["semana", "mes", "anio", "fact_lima", "fact_piura", "meta_min_sede", "meta_ideal_sede",
      "proy_lima", "proy_piura", "leads_lima", "leads_piura", "consultas_agendadas", "pacientes_iniciaron",
      "videos_publicados", "videos_planificados", "invertido_lima", "invertido_piura", "pac_activos_lima",
      "pac_activos_piura", "retencion_lima", "retencion_piura", "sin_proxima", "ocupacion_lima", "ocupacion_piura"];
    const out = { ...(reporte?.id ? { id: reporte.id } : {}) };
    numK.forEach((k) => { out[k] = Number(f[k]) || 0; });
    ["fecha_inicio", "fecha_fin", "novedades", "decisiones", "compromisos"].forEach((k) => { out[k] = f[k]; });
    onSave(out);
  }
  const sec = { margin: "14px 0 10px" };

  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 580, maxHeight: "88vh", overflowY: "auto" }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
          <strong style={{ fontSize: 16 }}>{reporte ? "Editar reporte" : "Nuevo reporte semanal"}</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>

        <div className="ca-secth" style={sec}>Período</div>
        <div style={{ display: "flex", gap: 10, marginBottom: 10 }}>
          {N("semana", "Semana", 0.7)}{N("mes", "Mes (1-12)", 0.8)}{N("anio", "Año", 1)}
        </div>
        <div style={{ display: "flex", gap: 10, marginBottom: 8 }}>
          <div style={{ flex: 1 }}><div className="ca-label">Inicio</div><input className="ca-input" type="date" value={f.fecha_inicio} onChange={set("fecha_inicio")} /></div>
          <div style={{ flex: 1 }}><div className="ca-label">Fin</div><input className="ca-input" type="date" value={f.fecha_fin} onChange={set("fecha_fin")} /></div>
        </div>
        <button className="ca-mini" onClick={traerReales}><Download size={13} strokeWidth={2} /> Traer datos reales del período</button>
        <div className="ca-pmeta" style={{ marginTop: 5 }}>Rellena leads, consultas, procesos, pacientes activos, facturación (cobros del mes, por sede), ocupación y retención S3+ desde el sistema. Solo videos y metas se completan a mano.</div>

        <div className="ca-secth" style={sec}>Facturación del mes (S/)</div>
        <div style={{ display: "flex", gap: 10, marginBottom: 8 }}>{N("fact_lima", "Lima")}{N("fact_piura", "Piura")}{N("meta_min_sede", "Meta x sede")}</div>
        <div style={{ display: "flex", gap: 10, marginBottom: 6 }}>{N("proy_lima", "Proy. Lima")}{N("proy_piura", "Proy. Piura")}</div>

        <div className="ca-secth" style={sec}>Captación</div>
        <div style={{ display: "flex", gap: 10, marginBottom: 6 }}>{N("leads_lima", "Leads Lima")}{N("leads_piura", "Leads Piura")}{N("consultas_agendadas", "Consultas")}{N("pacientes_iniciaron", "Iniciaron")}</div>

        <div className="ca-secth" style={sec}>Marketing / pauta</div>
        <div style={{ display: "flex", gap: 10, marginBottom: 6 }}>{N("videos_publicados", "Videos pub.")}{N("videos_planificados", "Planificados")}{N("invertido_lima", "Pauta Lima")}{N("invertido_piura", "Pauta Piura")}</div>

        <div className="ca-secth" style={sec}>Clínica y retención</div>
        <div style={{ display: "flex", gap: 10, marginBottom: 8 }}>{N("pac_activos_lima", "Activos Lima")}{N("pac_activos_piura", "Activos Piura")}{N("sin_proxima", "Sin próxima")}</div>
        <div style={{ display: "flex", gap: 10, marginBottom: 8 }}>{N("retencion_lima", "Retenc. Lima %")}{N("retencion_piura", "Retenc. Piura %")}</div>
        <div style={{ display: "flex", gap: 10, marginBottom: 6 }}>{N("ocupacion_lima", "Ocup. Lima %")}{N("ocupacion_piura", "Ocup. Piura %")}</div>

        <div className="ca-secth" style={sec}>Novedades y decisiones</div>
        <div style={{ marginBottom: 10 }}><div className="ca-label">Novedades de la semana</div><textarea className="ca-input" style={{ minHeight: 56, resize: "vertical", lineHeight: 1.5 }} value={f.novedades} onChange={set("novedades")} /></div>
        <div style={{ marginBottom: 18 }}><div className="ca-label">Decisiones requeridas</div><textarea className="ca-input" style={{ minHeight: 70, resize: "vertical", lineHeight: 1.5 }} value={f.decisiones} onChange={set("decisiones")} /></div>

        <div style={{ display: "flex", gap: 9, justifyContent: "flex-end" }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" onClick={guardar}>Guardar</button>
        </div>
      </div>
    </div>
  );
}

function Ocupacion({ showToast }) {
  const [data, setData] = useState(null);
  const [sel, setSel] = useState(null); // null hasta que carga la semana en curso
  const primera = React.useRef(true);

  async function cargar(params) {
    try {
      const d = await api.ocupacion(params || {});
      setData(d);
      if (!params) setSel({ anio: d.anio, mes: d.mes, semana: d.semana });
    } catch (e) { showToast("Error: " + e.message); }
  }
  useEffect(() => { cargar(); }, []);
  // Al cambiar semana/mes/año recarga sola: ya no hace falta apretar "Ver".
  useEffect(() => {
    if (!sel) return;
    if (primera.current) { primera.current = false; return; }
    cargar(sel);
  }, [sel]);

  if (!data || !sel) return <div className="ca-empty">Cargando…</div>;

  const anioBase = dDeISO(HOY_ISO).getFullYear();
  const anios = [...new Set([anioBase - 2, anioBase - 1, anioBase, anioBase + 1, Number(data.anio)])].sort((a, b) => a - b);
  const set = (k) => (e) => setSel((s) => ({ ...s, [k]: Number(e.target.value) }));

  const badge = (estado, txt) => {
    const c = SEM[estado] || SEM.rojo;
    return <span style={{ display: "inline-flex", alignItems: "center", gap: 6, background: c.bg, color: c.fg, padding: "2px 10px", borderRadius: 20, fontSize: 12.5, fontWeight: 600 }}><span style={{ width: 8, height: 8, borderRadius: "50%", background: c.dot }} /> {txt}</span>;
  };

  return (
    <div>
      <div className="ca-tophead">
        <div>
          <h1 className="ca-h1">Ocupación de agenda</h1>
          <div className="ca-sub">Horas disponibles vs. sesiones realizadas, por psicólogo</div>
        </div>
        <ExportBtns nombre={`ocupacion_${data.anio}_${data.mes}_s${data.semana}`}
          titulo={`Ocupación de agenda · Sem ${data.semana} · ${MESES_FULL[data.mes] || ""} ${data.anio}`}
          disabled={data.sedes.length === 0}
          headers={["Sede", "Psicologo", "Horas/sem", "Sesiones", "Libres", "% Ocupacion", "Consultas", "1er proceso", "% Cierre", "Recompra"]}
          filas={data.sedes.flatMap((g) => g.psicologos.map((p) => [g.sede_label, p.nombre, p.horas_disponibles, p.sesiones, Math.max(0, p.horas_disponibles - p.sesiones), `${p.ocupacion}%`, p.consultas, p.primer_proceso, `${p.consultas ? Math.round((p.primer_proceso / p.consultas) * 100) : 0}%`, p.recompra]))} />
      </div>

      <div className="ca-fchips" style={{ marginTop: 18, alignItems: "flex-end" }}>
        <div style={{ width: 108 }}><div className="ca-label">Semana</div>
          <select className="ca-input" value={sel.semana} onChange={set("semana")}>
            {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>Semana {n}</option>)}
          </select>
        </div>
        <div style={{ width: 130 }}><div className="ca-label">Mes</div>
          <select className="ca-input" value={sel.mes} onChange={set("mes")}>
            {MESES_FULL.slice(1).map((m, i) => <option key={i + 1} value={i + 1}>{m}</option>)}
          </select>
        </div>
        <div style={{ width: 100 }}><div className="ca-label">Año</div>
          <select className="ca-input" value={sel.anio} onChange={set("anio")}>
            {anios.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>
        {data.desde && (
          <div className="ca-pmeta" style={{ paddingBottom: 10 }}>
            {labelNumMes(data.desde)} – {labelNumMes(data.hasta)}
          </div>
        )}
      </div>

      {data.sedes.length === 0 ? (
        <div className="ca-empty">No hay sesiones registradas en esa semana.</div>
      ) : data.sedes.map((g) => (
        <div key={g.sede} style={{ marginTop: 24 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
            <h2 className="ca-secth" style={{ margin: 0 }}>{g.sede_label}</h2>
            {badge(g.estado, `${g.ocupacion}% ocupación`)}
          </div>
          <div className="ca-card" style={{ overflowX: "auto" }}>
            <table className="ca-table">
              <thead>
                <tr>
                  <th>Psicólogo</th>
                  <th style={{ textAlign: "right" }}>Horas/sem</th>
                  <th style={{ textAlign: "right" }}>Sesiones</th>
                  <th style={{ textAlign: "right" }}>Libres</th>
                  <th style={{ textAlign: "right" }}>% Ocup.</th>
                  <th style={{ textAlign: "right" }}>Consultas</th>
                  <th style={{ textAlign: "right" }}>1er proc.</th>
                  <th style={{ textAlign: "right" }}>% Cierre</th>
                  <th style={{ textAlign: "right" }}>Recompra</th>
                </tr>
              </thead>
              <tbody>
                {g.psicologos.map((p) => {
                  const pc = SEM[p.estado] || SEM.rojo;
                  return (
                    <tr key={p.id}>
                      <td>{p.nombre}</td>
                      <td style={{ textAlign: "right" }}>{p.horas_disponibles}</td>
                      <td style={{ textAlign: "right" }}>{p.sesiones}</td>
                      <td style={{ textAlign: "right", color: "#3D5C82", fontWeight: 600 }}>{Math.max(0, p.horas_disponibles - p.sesiones)}</td>
                      <td style={{ textAlign: "right" }}><span style={{ color: pc.fg, fontWeight: 600 }}>{p.ocupacion}%</span></td>
                      <td style={{ textAlign: "right" }}>{p.consultas}</td>
                      <td style={{ textAlign: "right" }}>{p.primer_proceso}</td>
                      <td style={{ textAlign: "right", fontWeight: 600 }}>{p.consultas ? Math.round((p.primer_proceso / p.consultas) * 100) : 0}%</td>
                      <td style={{ textAlign: "right" }}>{p.recompra}</td>
                    </tr>
                  );
                })}
                <tr style={{ fontWeight: 700 }}>
                  <td>TOTAL {g.sede_label}</td>
                  <td style={{ textAlign: "right" }}>{g.total_horas}</td>
                  <td style={{ textAlign: "right" }}>{g.total_sesiones}</td>
                  <td style={{ textAlign: "right" }}>{g.ocupacion}%</td>
                  <td colSpan={3}></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}

function RegistrarSesionModal({ paciente, onClose, onSave }) {
  const ult = paciente.seguimiento && paciente.seguimiento.length ? paciente.seguimiento[paciente.seguimiento.length - 1] : null;
  const [f, setF] = useState({
    anio: ult?.anio || 2026,
    mes: ult?.mes || 6,
    semana: ult ? Math.min(5, ult.semana + 1) : 1,
    n_sesion: ult ? (ult.proceso === "consulta" ? 1 : ult.n_sesion + 1) : (paciente.n_sesion || 1),
    proceso: ult && ult.proceso !== "consulta" ? ult.proceso : (paciente.proceso && paciente.proceso !== "consulta" ? paciente.proceso : "primero"),
  });
  const setN = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value.replace(/[^\d]/g, "") }));
  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));

  return (
    <div className="ca-modal-bg" onClick={onClose}>
      <div className="ca-modal" style={{ maxWidth: 440 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
          <strong style={{ fontSize: 16 }}>Registrar sesión</strong>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>
        <div className="ca-pmeta" style={{ marginBottom: 16 }}>{paciente.nombre} · se actualiza su sesión actual.</div>
        <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
          <div style={{ flex: 0.8 }}><div className="ca-label">Semana</div><input className="ca-input" value={f.semana} onChange={setN("semana")} inputMode="numeric" /></div>
          <div style={{ flex: 1.3 }}><div className="ca-label">Mes</div><select className="ca-input" value={f.mes} onChange={set("mes")}>{MESES_FULL.slice(1).map((m, i) => <option key={i + 1} value={i + 1}>{m}</option>)}</select></div>
          <div style={{ width: 84 }}><div className="ca-label">Año</div><input className="ca-input" value={f.anio} onChange={setN("anio")} inputMode="numeric" /></div>
        </div>
        <div style={{ display: "flex", gap: 11, marginBottom: 20 }}>
          <div style={{ width: 110 }}><div className="ca-label">N° de sesión</div><input className="ca-input" value={f.n_sesion} onChange={setN("n_sesion")} inputMode="numeric" /></div>
          <div style={{ flex: 1 }}><div className="ca-label">Proceso</div><select className="ca-input" value={f.proceso} onChange={set("proceso")}>{PROCESOS.map((p) => <option key={p || "none"} value={p}>{p ? p.charAt(0).toUpperCase() + p.slice(1) : "—"}</option>)}</select></div>
        </div>
        <div style={{ display: "flex", gap: 9, justifyContent: "flex-end" }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" onClick={() => onSave({ anio: Number(f.anio), mes: Number(f.mes), semana: Number(f.semana), n_sesion: Number(f.n_sesion) || 0, proceso: f.proceso })}>Guardar</button>
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
  { v: null, l: "Todos" }, { v: "medico", l: "Psicólogos" },
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
          <div className="ca-sub">Psicólogos, asistentes y administradores de la clínica</div>
        </div>
        <button className="ca-btn" onClick={() => setEditar({ new: true })}><UserPlus size={16} strokeWidth={2.1} /> Nuevo usuario</button>
      </div>

      <ConfigClinica showToast={showToast} />

      <div className="ca-card" style={{ marginTop: 22 }}>
        <div className="ca-secth" style={{ margin: "0 0 10px" }}>¿Qué puede hacer cada rol?</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 9, fontSize: 13.5, color: "var(--ink-soft)", lineHeight: 1.5 }}>
          <div><Tag colors={ROL_COLOR.admin}>Administrador (gerencia)</Tag> <span style={{ marginLeft: 4 }}>Ve todo: gerencia, finanzas, marketing, equipo y configuración.</span></div>
          <div><Tag colors={ROL_COLOR.medico}>Psicólogo/a</Tag> <span style={{ marginLeft: 4 }}>Solo lo clínico: su agenda, sus pacientes asignados, historia clínica y sesiones. No ve finanzas ni comercial.</span></div>
          <div><Tag colors={ROL_COLOR.asistente}>Asistente (coordinación)</Tag> <span style={{ marginLeft: 4 }}>Agenda, pacientes y seguimiento clínico + mensajes. No ve marketing ni finanzas.</span></div>
          <div><Tag colors={ROL_COLOR.comercial}>Comercial</Tag> <span style={{ marginLeft: 4 }}>Leads, seguimientos, marketing y conversión + mensajes. No ve datos clínicos ni finanzas.</span></div>
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
  const [sede, setSede] = useState(usuario?.sede || ""); // "" = todas / sin asignar (no forzar piura)
  const [telefono, setTelefono] = useState(usuario?.telefono || "");
  const [password, setPassword] = useState("");
  const esNuevo = !usuario;
  const canSave = nombre.trim() && (esNuevo ? (email.trim() && password.length >= 6) : true);

  function guardar() {
    const data = {
      ...(usuario?.id ? { id: usuario.id } : {}),
      nombre: nombre.trim(), rol, telefono: telefono.trim(), sede,
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
          <div style={{ flex: 1 }}>
            <div className="ca-label">Sede</div>
            <select className="ca-input" value={sede} onChange={(e) => setSede(e.target.value)}>
              <option value="">— Todas / sin asignar —</option>
              <option value="lima">Lima</option>
              <option value="piura">Piura</option>
            </select>
          </div>
        </div>
        <div style={{ fontSize: 12, color: "var(--muted)", marginTop: -4, marginBottom: 13 }}>
          La sede define de qué local ve la información (meta comercial, etc.). «Todas» = ve la clínica completa (gerencia).
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

function PacienteModal({ paciente, onClose, onSave, esMedico }) {
  const [nombre, setNombre] = useState(paciente?.nombre || "");
  const [fechaNac, setFechaNac] = useState(paciente?.fecha_nacimiento || "");
  const [tel, setTel] = useState(paciente?.tel && paciente.tel !== "—" ? paciente.tel : "");
  const [email, setEmail] = useState(paciente?.email || "");
  const [esp, setEsp] = useState(paciente?.especialidad || "Terapia individual");
  const [tipoDoc, setTipoDoc] = useState(paciente?.tipo_documento || "dni");
  const [numDoc, setNumDoc] = useState(paciente?.numero_documento || "");
  const [direccion, setDireccion] = useState(paciente?.direccion || "");
  const [genero, setGenero] = useState(paciente?.genero || "");
  const [alergias, setAlergias] = useState(paciente?.alergias || "");
  const [antecedentes, setAntecedentes] = useState(paciente?.antecedentes || "");
  const [medicacion, setMedicacion] = useState(paciente?.medicacion_habitual || "");
  const [tutorNombre, setTutorNombre] = useState(paciente?.tutor_nombre || "");
  const [tutorParentesco, setTutorParentesco] = useState(paciente?.tutor_parentesco || "");
  const [tutorTel, setTutorTel] = useState(paciente?.tutor_telefono || "");
  const [tutorDoc, setTutorDoc] = useState(paciente?.tutor_documento || "");
  const [sede, setSede] = useState(paciente?.sede || "");
  const [profId, setProfId] = useState(paciente?.profesional || "");
  const [frecuencia, setFrecuencia] = useState(paciente?.frecuencia || "");
  const [modalidadP, setModalidadP] = useState(paciente?.modalidad || "");
  const [nSesion, setNSesion] = useState(paciente?.n_sesion ?? 0);
  const [proceso, setProceso] = useState(paciente?.proceso || "");
  const [sesionesProceso, setSesionesProceso] = useState(paciente?.sesiones_proceso ?? 0);
  const [resumenClinico, setResumenClinico] = useState(paciente?.resumen_clinico || "");
  const [objetivoPrincipal, setObjetivoPrincipal] = useState(paciente?.objetivo_principal || "");
  const [riesgo, setRiesgo] = useState(paciente?.riesgo || "");
  const [alertas, setAlertas] = useState(paciente?.alertas || "");
  const [notasInternas, setNotasInternas] = useState(paciente?.notas_internas || "");
  const [antMedicos, setAntMedicos] = useState(paciente?.antecedentes_medicos || "");
  const [antFamiliares, setAntFamiliares] = useState(paciente?.antecedentes_familiares || "");
  const [antOtros, setAntOtros] = useState(paciente?.antecedentes_otros || "");
  const [profs, setProfs] = useState([]);
  useEffect(() => { api.profesionales().then(setProfs).catch(() => {}); }, []);
  const canSave = nombre.trim().length > 0;
  const esNuevo = !paciente;
  // Psicólogos activos de la sede elegida (más el ya asignado, aunque esté inactivo).
  // Incluye a los psicólogos INACTIVOS (marcados): al migrar de AgendaPro hay que
  // poder asignar pacientes a psicólogos que ya no están activos en el directorio.
  const profsVisibles = profs.filter((pr) => !sede || pr.sede === sede);

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
          {!esMedico && (
            <div style={{ flex: 1 }}>
              <div className="ca-label">Teléfono</div>
              <input className="ca-input" value={tel} onChange={(e) => setTel(e.target.value)} placeholder="987 654 321" />
            </div>
          )}
        </div>
        {!esMedico && (
          <div style={{ marginBottom: 13 }}>
            <div className="ca-label">Correo electrónico</div>
            <input className="ca-input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="correo@ejemplo.com" inputMode="email" />
          </div>
        )}
        <div style={{ display: "flex", gap: 11, marginBottom: 16 }}>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Frecuencia</div>
            <select className="ca-input" value={frecuencia} onChange={(e) => setFrecuencia(e.target.value)}>
              <option value="">—</option><option value="semanal">Semanal</option><option value="quincenal">Quincenal</option><option value="esporadico">Esporádico</option><option value="en_pausa">En pausa</option><option value="alta">Alta</option>
            </select>
          </div>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Modalidad</div>
            <select className="ca-input" value={modalidadP} onChange={(e) => setModalidadP(e.target.value)}>
              <option value="">—</option><option value="presencial">Presencial</option><option value="virtual">Virtual</option><option value="hibrido">Híbrido</option>
            </select>
          </div>
        </div>
        <div style={{ marginBottom: 16 }}>
          <div className="ca-label">Especialidad habitual</div>
          <select className="ca-input" value={esp} onChange={(e) => setEsp(e.target.value)}>
            {Object.keys(SPECIALTY).map((s) => <option key={s}>{s}</option>)}
          </select>
        </div>

        <div className="ca-secth" style={{ margin: "4px 0 12px" }}>Sede y psicólogo</div>
        <div style={{ display: "flex", gap: 11, marginBottom: esNuevo ? 16 : 13 }}>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Sede</div>
            <select className="ca-input" value={sede} onChange={(e) => {
              const s = e.target.value; setSede(s);
              // Si el psicólogo elegido no es de la nueva sede, se limpia.
              if (profId && !profs.some((pr) => String(pr.id) === String(profId) && (!s || pr.sede === s))) setProfId("");
            }}>
              <option value="">—</option>
              {SEDES.map((s) => <option key={s.v} value={s.v}>{s.l}</option>)}
            </select>
          </div>
          <div style={{ flex: 1.6 }}>
            <div className="ca-label">Psicólogo</div>
            <select className="ca-input" value={profId} onChange={(e) => setProfId(e.target.value)}>
              <option value="">Sin asignar</option>
              {profsVisibles.map((pr) => <option key={pr.id} value={pr.id}>{pr.nombre} ({pr.sede_label}){pr.activo ? "" : " · inactivo"}</option>)}
            </select>
          </div>
        </div>
        {/* N° de sesión y proceso solo al EDITAR; en un paciente nuevo no se piden
            (arrancan en 0 y se actualizan solos con las sesiones). */}
        {!esNuevo && (
          <div style={{ display: "flex", gap: 11, marginBottom: 16 }}>
            <div style={{ width: 92 }}>
              <div className="ca-label">N° de sesión</div>
              <input className="ca-input" value={nSesion} onChange={(e) => setNSesion(e.target.value.replace(/[^\d]/g, ""))} inputMode="numeric" />
            </div>
            <div style={{ width: 92 }}>
              <div className="ca-label">de (total)</div>
              <input className="ca-input" value={sesionesProceso} onChange={(e) => setSesionesProceso(e.target.value.replace(/[^\d]/g, ""))} inputMode="numeric" placeholder="12" />
            </div>
            <div style={{ flex: 1 }}>
              <div className="ca-label">Proceso</div>
              <select className="ca-input" value={proceso} onChange={(e) => setProceso(e.target.value)}>
                {PROCESOS.map((p) => <option key={p || "none"} value={p}>{p ? p.charAt(0).toUpperCase() + p.slice(1) : "—"}</option>)}
              </select>
            </div>
          </div>
        )}

        <div className="ca-secth" style={{ margin: "4px 0 12px" }}>Trabajo clínico</div>
        <div style={{ marginBottom: 13 }}>
          <div className="ca-label">Objetivo terapéutico principal</div>
          <input className="ca-input" value={objetivoPrincipal} onChange={(e) => setObjetivoPrincipal(e.target.value)} placeholder="Ej: Regulación emocional y dependencia emocional" />
        </div>
        <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Riesgo actual</div>
            <select className="ca-input" value={riesgo} onChange={(e) => setRiesgo(e.target.value)}>
              <option value="">Sin evaluar</option><option value="bajo">Bajo</option><option value="moderado">Moderado</option><option value="alto">Alto</option>
            </select>
          </div>
          <div style={{ flex: 2 }}>
            <div className="ca-label">Alertas clínicas <span style={{ color: "var(--muted)", fontWeight: 400, fontSize: 12 }}>(separadas por coma)</span></div>
            <input className="ca-input" value={alertas} onChange={(e) => setAlertas(e.target.value)} placeholder="Antecedente de ansiedad, Duelo no elaborado…" />
          </div>
        </div>
        <div style={{ marginBottom: 20 }}>
          <div className="ca-label">Resumen clínico</div>
          <textarea className="ca-input" style={{ minHeight: 70, resize: "vertical", lineHeight: 1.5 }} value={resumenClinico}
            onChange={(e) => setResumenClinico(e.target.value)} placeholder="Por qué consulta, esquemas predominantes, adherencia, riesgo. Para ver el caso de un vistazo." />
        </div>

        {!esMedico && <div className="ca-secth" style={{ margin: "4px 0 12px" }}>Identificación</div>}
        {!esMedico && (
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
        )}
        <div style={{ display: "flex", gap: 11, marginBottom: 20 }}>
          {!esMedico && (
            <div style={{ flex: 2 }}>
              <div className="ca-label">Dirección</div>
              <input className="ca-input" value={direccion} onChange={(e) => setDireccion(e.target.value)} placeholder="Calle, urbanización, distrito…" />
            </div>
          )}
          <div style={{ flex: 1 }}>
            <div className="ca-label">Género</div>
            <select className="ca-input" value={genero} onChange={(e) => setGenero(e.target.value)}>
              {GENEROS.map((g) => <option key={g.v} value={g.v}>{g.l}</option>)}
            </select>
          </div>
        </div>

        <div className="ca-secth" style={{ margin: "4px 0 12px" }}>Padre/madre/tutor o apoyo <span style={{ color: "var(--muted)", fontWeight: 400, fontSize: 12.5 }}>(menores, o quien paga/acompaña · opcional)</span></div>
        <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
          <div style={{ flex: 1.6 }}>
            <div className="ca-label">Nombre del tutor</div>
            <input className="ca-input" value={tutorNombre} onChange={(e) => setTutorNombre(e.target.value)} placeholder="Nombre y apellidos" />
          </div>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Parentesco</div>
            <input className="ca-input" value={tutorParentesco} onChange={(e) => setTutorParentesco(e.target.value)} placeholder="Madre, padre, tutor…" />
          </div>
        </div>
        {!esMedico && (
        <div style={{ display: "flex", gap: 11, marginBottom: 20 }}>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Teléfono del tutor</div>
            <input className="ca-input" value={tutorTel} onChange={(e) => setTutorTel(e.target.value)} placeholder="987 654 321" inputMode="tel" />
          </div>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Documento del tutor</div>
            <input className="ca-input" value={tutorDoc} onChange={(e) => setTutorDoc(e.target.value)} placeholder="DNI" inputMode="numeric" />
          </div>
        </div>
        )}

        <div className="ca-secth" style={{ margin: "4px 0 12px" }}>Antecedentes relevantes</div>
        <div style={{ marginBottom: 13 }}>
          <div className="ca-label">Psicológicos</div>
          <textarea className="ca-input" style={{ minHeight: 52, resize: "vertical", lineHeight: 1.5 }} value={antecedentes}
            onChange={(e) => setAntecedentes(e.target.value)} placeholder="Historia emocional: ansiedad, duelos, procesos previos…" />
        </div>
        <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Médicos</div>
            <textarea className="ca-input" style={{ minHeight: 52, resize: "vertical", lineHeight: 1.5 }} value={antMedicos}
              onChange={(e) => setAntMedicos(e.target.value)} placeholder="Enfermedades, cirugías, hospitalizaciones…" />
          </div>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Familiares</div>
            <textarea className="ca-input" style={{ minHeight: 52, resize: "vertical", lineHeight: 1.5 }} value={antFamiliares}
              onChange={(e) => setAntFamiliares(e.target.value)} placeholder="Antecedentes familiares relevantes…" />
          </div>
        </div>
        <div style={{ display: "flex", gap: 11, marginBottom: 13 }}>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Otros</div>
            <textarea className="ca-input" style={{ minHeight: 52, resize: "vertical", lineHeight: 1.5 }} value={antOtros}
              onChange={(e) => setAntOtros(e.target.value)} placeholder="Consumo de sustancias u otros…" />
          </div>
          <div style={{ flex: 1 }}>
            <div className="ca-label">Alergias</div>
            <textarea className="ca-input" style={{ minHeight: 52, resize: "vertical", lineHeight: 1.5 }} value={alergias}
              onChange={(e) => setAlergias(e.target.value)} placeholder="Penicilina, mariscos…" />
          </div>
        </div>
        <div style={{ marginBottom: 13 }}>
          <div className="ca-label">Medicación habitual</div>
          <textarea className="ca-input" style={{ minHeight: 52, resize: "vertical", lineHeight: 1.5 }} value={medicacion}
            onChange={(e) => setMedicacion(e.target.value)} placeholder="Medicamentos que toma de forma habitual…" />
        </div>
        <div style={{ marginBottom: 20 }}>
          <div className="ca-label">Notas internas <span style={{ color: "var(--muted)", fontWeight: 400, fontSize: 12 }}>(solo equipo)</span></div>
          <textarea className="ca-input" style={{ minHeight: 52, resize: "vertical", lineHeight: 1.5 }} value={notasInternas}
            onChange={(e) => setNotasInternas(e.target.value)} placeholder="Preferencias/avisos: p. ej. «prefiere recordatorios por WhatsApp»." />
        </div>

        <div style={{ display: "flex", gap: 9, justifyContent: "flex-end" }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" style={{ opacity: canSave ? 1 : 0.5, pointerEvents: canSave ? "auto" : "none" }}
            onClick={() => onSave({ ...(paciente?.id ? { id: paciente.id } : {}), nombre: nombre.trim(), fecha_nacimiento: fechaNac || null, especialidad: esp, sede, profesional: profId ? Number(profId) : null, frecuencia, modalidad: modalidadP, n_sesion: Number(nSesion) || 0, proceso, alergias: alergias.trim(), antecedentes: antecedentes.trim(), medicacion_habitual: medicacion.trim(), sesiones_proceso: Number(sesionesProceso) || 0, resumen_clinico: resumenClinico.trim(), objetivo_principal: objetivoPrincipal.trim(), riesgo, alertas: alertas.trim(), notas_internas: notasInternas.trim(), antecedentes_medicos: antMedicos.trim(), antecedentes_familiares: antFamiliares.trim(), antecedentes_otros: antOtros.trim(), ...(!esMedico ? { tel: tel.trim(), email: email.trim(), tipo_documento: tipoDoc, numero_documento: numDoc.trim(), direccion: direccion.trim(), genero, tutor_nombre: tutorNombre.trim(), tutor_parentesco: tutorParentesco.trim(), tutor_telefono: tutorTel.trim(), tutor_documento: tutorDoc.trim() } : {}) })}>
            Guardar
          </button>
        </div>
      </div>
    </div>
  );
}

// Página PÚBLICA del consentimiento (sin login). El paciente la abre por su enlace,
// lee el documento y lo acepta con su nombre (sello de fecha/hora e IP en el backend).
// Copia imprimible (o "guardar como PDF") del documento que el paciente aceptó,
// con el sello de aceptación: quién firmó, su documento y la fecha/hora.
function imprimirConsentimiento(doc, firma) {
  const w = window.open("", "_blank", "width=840,height=920");
  if (!w) return;
  const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  w.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>${esc(doc.tipo_label)} · ${esc(doc.paciente_nombre)}</title>
    <style>
      body{font-family:'Inter',system-ui,sans-serif;color:#2A2722;max-width:720px;margin:0 auto;padding:36px 28px;line-height:1.6}
      .cab{text-align:center;margin-bottom:22px}
      .cl{font-size:13px;color:#9B968D}
      h1{font-size:20px;margin:6px 0}
      .para{font-size:13px;color:#6B675F}
      .doc{white-space:pre-wrap;font-size:13.5px;border:1px solid #ECE8E1;background:#FBFAF8;border-radius:10px;padding:18px}
      .sello{margin-top:22px;border:1px solid #CFE3D8;background:#E9F1ED;border-radius:10px;padding:16px;font-size:13px;color:#2F6B4F}
      .sello b{color:#245741}
      .pie{margin-top:18px;font-size:11px;color:#9B968D;text-align:center}
      @media print{body{padding:0}}
    </style></head><body>
    <div class="cab">
      <div class="cl">${esc(doc.clinica)}</div>
      <h1>${esc(doc.tipo_label)}</h1>
      <div class="para">Para: <b>${esc(doc.paciente_nombre)}</b></div>
    </div>
    <div class="doc">${esc(doc.texto)}</div>
    <div class="sello">
      <div>✅ <b>Documento aceptado</b>${firma.fecha ? ` el ${esc(firma.fecha)}` : ""}.</div>
      ${firma.nombre ? `<div>Firmado electrónicamente por <b>${esc(firma.nombre)}</b>${firma.documento ? ` · DNI ${esc(firma.documento)}` : ""}.</div>` : ""}
    </div>
    <div class="pie">Copia generada desde ${esc(doc.clinica)}. Conserva este documento.</div>
    </body></html>`);
  w.document.close();
  w.focus();
  setTimeout(() => w.print(), 350);
}

export function ConsentimientoPublico({ token }) {
  const [doc, setDoc] = useState(null);
  const [err, setErr] = useState("");
  const [nombre, setNombre] = useState("");
  const [documento, setDocumento] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [hecho, setHecho] = useState(null);

  useEffect(() => { api.consentimientoPublico(token).then(setDoc).catch((e) => setErr(e.message)); }, [token]);

  async function aceptar() {
    if (nombre.trim().length < 3) return;
    setEnviando(true); setErr("");
    try { setHecho(await api.aceptarConsentimiento(token, { nombre: nombre.trim(), documento: documento.trim() })); }
    catch (e) { setErr(e.message); } finally { setEnviando(false); }
  }

  const wrap = { maxWidth: 640, margin: "0 auto", padding: "32px 20px", fontFamily: "'Inter',system-ui,sans-serif", color: "#2A2722", minHeight: "100vh", background: "#fff" };
  const inp = { width: "100%", padding: "10px 12px", borderRadius: 8, border: "1px solid #DDD8CF", fontSize: 15, marginBottom: 10, boxSizing: "border-box" };

  if (err && !doc) return <div style={wrap}><h2>Documento no disponible</h2><p style={{ color: "#9C4646" }}>{err}</p></div>;
  if (!doc) return <div style={wrap}>Cargando…</div>;

  const yaFirmado = doc.aceptado || hecho;
  return (
    <div style={wrap}>
      <div style={{ textAlign: "center", marginBottom: 18 }}>
        <div style={{ fontSize: 13, color: "#9B968D" }}>{doc.clinica}</div>
        <h1 style={{ fontSize: 21, margin: "6px 0" }}>{doc.tipo_label}</h1>
        <div style={{ fontSize: 13, color: "#6B675F" }}>Para: <strong>{doc.paciente_nombre}</strong></div>
      </div>
      <div style={{ background: "#FBFAF8", border: "1px solid #ECE8E1", borderRadius: 12, padding: 18, whiteSpace: "pre-wrap", lineHeight: 1.55, fontSize: 14.5 }}>{doc.texto}</div>
      {yaFirmado ? (
        <div style={{ marginTop: 20, background: "#E9F1ED", border: "1px solid #CFE3D8", borderRadius: 12, padding: 16, textAlign: "center", color: "#2F6B4F" }}>
          ✅ Documento aceptado{(hecho?.aceptado_en || doc.aceptado_en) ? ` el ${hecho?.aceptado_en || doc.aceptado_en}` : ""}.
          {(hecho?.firmante_nombre || doc.firmante_nombre || nombre) ? <div style={{ fontSize: 13, marginTop: 4 }}>Firmado por {doc.firmante_nombre || nombre}.</div> : null}
          <button onClick={() => imprimirConsentimiento(doc, {
            nombre: doc.firmante_nombre || nombre,
            documento: doc.firmante_documento || documento,
            fecha: hecho?.aceptado_en || doc.aceptado_en,
          })}
            style={{ marginTop: 12, padding: "11px 18px", borderRadius: 10, border: "1px solid #3E7A65", background: "#fff", color: "#2F6B4F", fontSize: 14, fontWeight: 600, cursor: "pointer" }}>
            ⬇︎ Descargar mi copia
          </button>
          <div style={{ fontSize: 12.5, marginTop: 10, color: "#6B675F" }}>
            Guarda o imprime tu copia. Ya puedes cerrar esta página. ¡Gracias! 🌿
          </div>
        </div>
      ) : (
        <div style={{ marginTop: 20 }}>
          <div style={{ fontSize: 13, marginBottom: 6 }}>Para aceptar, escribe tu <strong>nombre completo</strong>:</div>
          <input style={inp} value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre y apellidos" />
          <input style={inp} value={documento} onChange={(e) => setDocumento(e.target.value)} placeholder="DNI (opcional)" />
          {err ? <div style={{ color: "#9C4646", fontSize: 13, marginBottom: 10 }}>{err}</div> : null}
          <button onClick={aceptar} disabled={enviando || nombre.trim().length < 3}
            style={{ width: "100%", padding: "13px", borderRadius: 10, border: "none", background: "#3E7A65", color: "#fff", fontSize: 15, fontWeight: 600, cursor: "pointer", opacity: (enviando || nombre.trim().length < 3) ? 0.5 : 1 }}>
            {enviando ? "Guardando…" : "Acepto"}
          </button>
          <div style={{ fontSize: 11.5, color: "#9B968D", marginTop: 10, textAlign: "center" }}>
            Al hacer clic en "Acepto" registramos tu aceptación con fecha y hora.
          </div>
        </div>
      )}
    </div>
  );
}

// Página PÚBLICA de auto-agendamiento (sin login): /agendar/<token>. El paciente
// elige psicólogo y un horario libre y reserva. Nuevo → lead + cita tentativa;
// existente (match por teléfono/DNI) → cita directa en la agenda.
// Sedes de Ítaca Conversemos (dirección + teléfono para el mensaje de pre-reserva).
const AGENDA_SEDES = {
  lima: { label: "Lima", direccion: "Av. Arequipa 4130, Of. 205 — Miraflores, Lima", telefono: "+51 980 453 832" },
  piura: { label: "Piura", direccion: "Av. Bolognesi 582, Of. 201 — Piura", telefono: "+51 983 292 173" },
};
// Categorías para la rama "necesito ayuda" → se cruzan con Profesional.poblaciones.
const AGENDA_CATS = [
  { v: "adultos", emoji: "🧑", label: "Atención a adultos", match: ["adult"] },
  { v: "ninos", emoji: "🧒", label: "Atención a niños", match: ["niñ", "nin", "infant"] },
  { v: "adolescentes", emoji: "🧑‍🎓", label: "Atención a adolescentes", match: ["adolescen"] },
  { v: "parejas", emoji: "💞", label: "Atención a parejas", match: ["pareja"] },
];

// Categoría implícita de un servicio (por su nombre) y si el psicólogo la atiende
// (según su campo `poblaciones`). Evita ofrecer en la web servicios que ese
// profesional no da (ej. lenguaje, pareja). Lenient: si falta info, se muestra.
function _servCategoria(nombre) {
  const n = (nombre || "").toLowerCase();
  if (n.includes("pareja")) return "pareja";
  if (n.includes("lenguaje")) return "lenguaje";
  if (n.includes("infantojuvenil") || n.includes("niñ") || n.includes("nin") || n.includes("adolescent") || n.includes("infantil")) return "infantojuvenil";
  if (n.includes("adulto")) return "adulto";
  return "";
}
function _profSirveServicio(prof, nombreServicio) {
  const cat = _servCategoria(nombreServicio);
  if (!cat) return true; // servicio general (consulta inicial, brújula…) -> siempre
  const pob = (prof?.poblaciones || "").toLowerCase();
  if (!pob) return true; // sin público declarado -> no filtramos
  const kw = { pareja: ["pareja"], lenguaje: ["lenguaje"], infantojuvenil: ["niñ", "nin", "adolescent", "infant"], adulto: ["adulto"] }[cat] || [];
  return kw.some((k) => pob.includes(k));
}

export function AgendarPublico({ token }) {
  const [info, setInfo] = useState(null);
  const [err, setErr] = useState("");
  const [sede, setSede] = useState(null);          // "lima" | "piura"
  const [via, setVia] = useState(null);            // "elegir" | "ayuda"
  const [categoria, setCategoria] = useState(null);// solo rama "ayuda"
  const [prof, setProf] = useState(null);
  const [perfil, setPerfil] = useState(null);      // psicólogo en el modal "Ver perfil"
  const [slotsData, setSlotsData] = useState(null);
  const [slot, setSlot] = useState(null);          // {inicio, hora, diaLabel}
  const [form, setForm] = useState({ nombre: "", telefono: "", documento: "", email: "", servicio: "", modalidad: "presencial", mensaje: "" });
  const [enviando, setEnviando] = useState(false);
  const [hecho, setHecho] = useState(null);
  const setF = (k) => (e) => setForm((p) => ({ ...p, [k]: e.target.value }));

  useEffect(() => { api.agendaInfo(token).then(setInfo).catch((e) => setErr(e.message)); }, [token]);

  useEffect(() => {
    if (!prof) return;
    setSlotsData(null); setSlot(null);
    setForm((p) => ({
      ...p,
      servicio: (((info?.servicios || []).filter((s) => _profSirveServicio(prof, s.nombre))[0] || (info?.servicios || [])[0] || {}).nombre) || "",
      modalidad: prof.modalidad === "virtual" ? "virtual" : "presencial",
    }));
    api.agendaSlots(token, prof.id, 21).then(setSlotsData).catch(() => setSlotsData({ dias: [] }));
  }, [prof]); // eslint-disable-line

  const diaLabel = (iso) => {
    const s = new Date(iso + "T12:00:00").toLocaleDateString("es-PE", { weekday: "long", day: "numeric", month: "long" });
    return s.charAt(0).toUpperCase() + s.slice(1);
  };

  async function reservar() {
    if (form.nombre.trim().length < 3 || form.telefono.replace(/\D/g, "").length < 6) {
      setErr("Escribe tu nombre y un teléfono válido."); return;
    }
    setEnviando(true); setErr("");
    try {
      const r = await api.agendaReservar(token, {
        profesional_id: prof.id, inicio: slot.inicio,
        nombre: form.nombre.trim(), telefono: form.telefono.trim(),
        documento: form.documento.trim(), email: form.email.trim(),
        servicio: form.servicio, modalidad: form.modalidad, mensaje: form.mensaje.trim(),
        categoria: via === "ayuda" ? categoria : "", ayuda: via === "ayuda",
      });
      setHecho({ ...r, sede });
    } catch (e) {
      // 409 = el horario se tomó mientras llenaba el formulario: refrescar slots.
      if (e.status === 409) { setSlot(null); api.agendaSlots(token, prof.id, 21).then(setSlotsData).catch(() => {}); }
      setErr(e.message);
    } finally { setEnviando(false); }
  }

  // --- Paleta y estilos (marca Conversemos, tono teal) ---
  const A = "#127C8A", AD = "#0C5E69";
  const wrap = { maxWidth: 620, margin: "0 auto", padding: "22px 16px 64px", fontFamily: "'Inter',system-ui,sans-serif", color: "#22303A", minHeight: "100vh", background: "#F7FAFB" };
  const inp = { width: "100%", padding: "11px 12px", borderRadius: 9, border: "1px solid #D6DFE1", fontSize: 15, marginBottom: 11, boxSizing: "border-box", fontFamily: "inherit", background: "#fff" };
  const cardClick = { border: "1px solid #E1E8EA", borderRadius: 14, padding: 15, marginBottom: 11, cursor: "pointer", background: "#fff", textAlign: "left", width: "100%", display: "block", boxShadow: "0 1px 2px rgba(12,94,105,.04)" };
  const cardStatic = { border: "1px solid #E1E8EA", borderRadius: 14, padding: 15, marginBottom: 11, background: "#fff", boxShadow: "0 1px 2px rgba(12,94,105,.04)" };
  const btnPrimary = { padding: "10px 16px", borderRadius: 9, border: "none", background: A, color: "#fff", fontSize: 14, fontWeight: 700, cursor: "pointer" };
  const btnGhost = { padding: "10px 16px", borderRadius: 9, border: `1px solid ${A}`, background: "#fff", color: A, fontSize: 14, fontWeight: 600, cursor: "pointer" };
  const avatar = (p, size = 54) => (p.foto
    ? <img src={p.foto} alt="" style={{ width: size, height: size, borderRadius: "50%", objectFit: "cover", flexShrink: 0 }} />
    : <div style={{ width: size, height: size, borderRadius: "50%", background: "#E3F1F2", color: A, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: size * 0.37, flexShrink: 0 }}>{(p.nombre || "?").replace(/^lic\.?\s*/i, "").trim().charAt(0)}</div>);

  if (err && !info) return <div style={wrap}><h2>Enlace no disponible</h2><p style={{ color: "#9C4646" }}>{err}</p></div>;
  if (!info) return <div style={wrap}>Cargando…</div>;

  // Pantalla final: mensaje de PRE-RESERVA (con medios de pago/políticas y contactos).
  if (hecho) {
    const s = AGENDA_SEDES[hecho.sede] || null;
    return (
      <div style={wrap}>
        <div style={{ ...cardStatic, padding: 22, marginTop: 8 }}>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 44 }}>💙</div>
            <h1 style={{ fontSize: 21, margin: "8px 0 2px", color: AD }}>¡Gracias por agendar!</h1>
            <div style={{ fontSize: 13.5, color: "#5B6B72" }}>a través de nuestra página web</div>
          </div>
          <div style={{ fontSize: 14.5, lineHeight: 1.6, color: "#33434B", marginTop: 16 }}>
            <p style={{ margin: "0 0 12px" }}>
              Reservaste con <strong>{hecho.profesional}</strong> para el <strong>{hecho.inicio_label}</strong>.
            </p>
            <p style={{ margin: "0 0 12px" }}>
              Queremos comentarte que esta es una <strong>pre-reserva ✨</strong>. En breve nos comunicaremos al número que registraste para confirmar tus datos, el horario, sede, modalidad y psicólogo/a seleccionado/a, para asegurarnos de que recibas la atención que buscas.
            </p>
            <p style={{ margin: "0 0 6px", fontWeight: 600 }}>Una vez confirmados los datos, te enviaremos:</p>
            <div style={{ margin: "0 0 12px", lineHeight: 1.8 }}>
              ✅ Los medios de pago.<br />✅ Nuestras políticas de atención.<br />✅ La confirmación oficial de tu cita.
            </div>
            <div style={{ background: "#FFF7EC", border: "1px solid #F1E2C4", borderRadius: 10, padding: "10px 12px", fontSize: 13.5, color: "#8A6D2E" }}>
              Recuerda que <strong>solo con el pago realizado</strong> la cita queda confirmada y programada para su desarrollo.
            </div>
          </div>
          <div style={{ marginTop: 16, borderTop: "1px solid #EBF0F1", paddingTop: 14, fontSize: 13.5, color: "#33434B" }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>¿Dudas o consultas? Escríbenos:</div>
            {(s ? [hecho.sede] : ["piura", "lima"]).map((k) => {
              const se = AGENDA_SEDES[k];
              return (
                <div key={k} style={{ marginBottom: 8, lineHeight: 1.5 }}>
                  📍 <strong>{se.label}:</strong> {se.direccion}<br />
                  <span style={{ marginLeft: 20 }}>📞 {se.telefono}</span>
                </div>
              );
            })}
          </div>
          <div style={{ textAlign: "center", fontSize: 13.5, color: AD, marginTop: 12, fontWeight: 600 }}>
            Nos sentimos honrados de acompañarte en este primer paso hacia tu bienestar. 💙
          </div>
        </div>
      </div>
    );
  }

  // --- Derivados de estado ---
  const profsSede = info.profesionales.filter((p) => p.sede === sede);
  const catDef = AGENDA_CATS.find((c) => c.v === categoria);
  const matchCat = (p) => {
    if (!catDef) return true;
    const pob = (p.poblaciones || "").toLowerCase();
    if (!pob) return true; // sin público declarado: se muestra igual y el coordinador verifica
    return catDef.match.some((m) => pob.includes(m));
  };
  const profsAyuda = profsSede.filter(matchCat);
  const profsMostrar = via === "ayuda" ? (profsAyuda.length ? profsAyuda : profsSede) : profsSede;

  const showSede = !sede;
  const showVia = sede && !via;
  const showCat = sede && via === "ayuda" && !categoria;
  const needProf = sede && via && (via === "elegir" || categoria) && !prof;
  const showSlots = prof && !slot;
  const showDatos = prof && slot;
  const stepIdx = !sede ? 0 : !via ? 1 : (showCat || needProf) ? 2 : !slot ? 3 : 4;
  const PASOS = ["Sede", "Con quién", "Profesional", "Horario", "Tus datos"];

  const volver = () => {
    setErr("");
    if (slot) return setSlot(null);
    if (prof) return setProf(null);
    if (via === "ayuda" && categoria) return setCategoria(null);
    if (via) return setVia(null);
    if (sede) return setSede(null);
  };

  const ProfCard = (p) => (
    <div key={p.id} style={cardStatic}>
      <div style={{ display: "flex", gap: 13, alignItems: "center" }}>
        {avatar(p)}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 15.5 }}>{p.nombre}</div>
          <div style={{ fontSize: 12.5, color: "#5B6B72" }}>{p.titulo}{p.sede_label ? ` · ${p.sede_label}` : ""}{p.modalidad_label ? ` · ${p.modalidad_label}` : ""}</div>
          {p.enfoque ? <div style={{ fontSize: 12.5, color: "#7B8A90", marginTop: 3, lineHeight: 1.45 }}>{p.enfoque.length > 110 ? p.enfoque.slice(0, 110) + "…" : p.enfoque}</div> : null}
        </div>
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <button style={btnGhost} onClick={() => setPerfil(p)}>Ver perfil</button>
        <button style={{ ...btnPrimary, flex: 1 }} onClick={() => setProf(p)}>Elegir</button>
      </div>
    </div>
  );

  return (
    <div style={wrap}>
      {/* Portada / logo de marca */}
      {showSede ? (
        <div style={{ borderRadius: 18, overflow: "hidden", marginBottom: 18, boxShadow: "0 8px 26px rgba(12,94,105,.16)" }}>
          <div style={{ background: `linear-gradient(135deg, ${AD} 0%, ${A} 58%, #18A6B4 100%)`, padding: "32px 22px 28px", color: "#fff", textAlign: "center" }}>
            <div style={{ fontSize: 12, letterSpacing: 3, textTransform: "uppercase", opacity: 0.85, fontWeight: 600 }}>{info.clinica}</div>
            <div style={{ fontSize: 25, fontWeight: 800, lineHeight: 1.18, marginTop: 10 }}>Todos necesitamos de un<br />sincero <span style={{ borderBottom: "3px solid rgba(255,255,255,.55)", paddingBottom: 1 }}>conversemos</span></div>
            <div style={{ fontSize: 13.5, opacity: 0.92, marginTop: 10 }}>Agenda tu cita en línea</div>
          </div>
        </div>
      ) : (
        <div style={{ textAlign: "center", marginBottom: 14 }}>
          <div style={{ fontSize: 12, letterSpacing: 2.5, textTransform: "uppercase", color: A, fontWeight: 700 }}>{info.clinica}</div>
          <div style={{ fontSize: 13, color: "#7B8A90", marginTop: 2 }}>Agenda tu cita en línea</div>
        </div>
      )}

      {/* Bienvenida (solo en la portada) */}
      {showSede && (
        <div style={{ ...cardStatic, padding: 18, fontSize: 14, lineHeight: 1.6, color: "#33434B" }}>
          <p style={{ margin: "0 0 10px" }}><strong>Gracias por estar aquí y confiar en nosotros para acompañarte.</strong></p>
          <p style={{ margin: "0 0 10px" }}>En {info.clinica} creemos que <em>todos, en algún momento, necesitamos un espacio seguro para conversar</em>, comprender lo que sentimos y encontrar nuevas herramientas para seguir adelante.</p>
          <p style={{ margin: "0 0 10px" }}>Nuestro propósito es <em>cambiar vidas</em> a través de un acompañamiento psicológico humano, profesional y libre de juicios.</p>
          <p style={{ margin: 0 }}>Nos alegra que estés aquí. Comencemos juntos este camino.</p>
        </div>
      )}

      {/* Barra de progreso */}
      <div style={{ margin: "4px 0 18px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10.5, marginBottom: 6 }}>
          {PASOS.map((l, i) => (
            <span key={l} style={{ color: i <= stepIdx ? A : "#B4C1C4", fontWeight: i === stepIdx ? 700 : 500 }}>{l}</span>
          ))}
        </div>
        <div style={{ height: 6, background: "#E1E8EA", borderRadius: 999, overflow: "hidden" }}>
          <div style={{ width: `${(stepIdx / (PASOS.length - 1)) * 100}%`, height: "100%", background: A, transition: "width .3s" }} />
        </div>
      </div>

      {/* Volver */}
      {sede && (
        <button onClick={volver} style={{ background: "none", border: "none", color: A, fontWeight: 600, cursor: "pointer", fontSize: 13.5, padding: "2px 0", marginBottom: 12 }}>← Volver</button>
      )}

      {!info.hay_agenda && (
        <div style={{ background: "#FDF6F6", border: "1px solid #F0D6D6", borderRadius: 12, padding: 16, color: "#9C4646", fontSize: 14 }}>
          Por ahora no hay horarios disponibles en línea. Escríbenos por WhatsApp y te ayudamos a agendar. 🙏
        </div>
      )}

      {/* Paso 1: elegir sede */}
      {info.hay_agenda && showSede && (
        <div>
          <h2 style={{ fontSize: 17, margin: "0 0 4px", color: AD }}>📍 ¿Dónde te gustaría atenderte?</h2>
          <div style={{ fontSize: 13, color: "#7B8A90", marginBottom: 14 }}>Para atención virtual, elige igualmente la sede más cercana a ti.</div>
          {["lima", "piura"].map((k) => {
            const se = AGENDA_SEDES[k];
            return (
              <button key={k} style={cardClick} onClick={() => setSede(k)}>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <div style={{ fontSize: 26 }}>📍</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 700, fontSize: 16 }}>{se.label}</div>
                    <div style={{ fontSize: 12.5, color: "#7B8A90" }}>{se.direccion}</div>
                  </div>
                  <ChevronRight size={18} style={{ color: "#B4C1C4" }} />
                </div>
              </button>
            );
          })}
        </div>
      )}

      {/* Paso 2: ¿ya sabes con quién? */}
      {showVia && (
        <div>
          <h2 style={{ fontSize: 17, margin: "0 0 12px", color: AD }}>👩‍⚕️ ¿Ya sabes con quién deseas atenderte?</h2>
          {[
            { v: "elegir", emoji: "🔎", label: "Quiero elegir un profesional", desc: "Verás los psicólogos disponibles y escoges tú." },
            { v: "ayuda", emoji: "🤝", label: "Necesito ayuda para encontrar al indicado", desc: "Nos cuentas a quién va dirigido y te ayudamos a elegir." },
          ].map((o) => (
            <button key={o.v} style={cardClick} onClick={() => setVia(o.v)}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div style={{ fontSize: 24 }}>{o.emoji}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 700, fontSize: 15 }}>{o.label}</div>
                  <div style={{ fontSize: 12.5, color: "#7B8A90" }}>{o.desc}</div>
                </div>
                <ChevronRight size={18} style={{ color: "#B4C1C4" }} />
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Rama "necesito ayuda": elegir categoría */}
      {showCat && (
        <div>
          <h2 style={{ fontSize: 17, margin: "0 0 4px", color: AD }}>Escoge una categoría</h2>
          <div style={{ fontSize: 13, color: "#7B8A90", marginBottom: 14 }}>Te mostraremos los horarios de los psicólogos disponibles y un coordinador te contactará para confirmar que sea el ideal para ti.</div>
          {AGENDA_CATS.map((c) => (
            <button key={c.v} style={cardClick} onClick={() => setCategoria(c.v)}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div style={{ fontSize: 24 }}>{c.emoji}</div>
                <div style={{ flex: 1, fontWeight: 700, fontSize: 15 }}>{c.label}</div>
                <ChevronRight size={18} style={{ color: "#B4C1C4" }} />
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Paso 3: elegir profesional */}
      {needProf && (
        <div>
          <h2 style={{ fontSize: 17, margin: "0 0 4px", color: AD }}>Selecciona a tu profesional</h2>
          {via === "ayuda" && (
            <div style={{ background: "#EAF5F6", border: "1px solid #CFE6E9", borderRadius: 10, padding: "10px 12px", fontSize: 13, color: "#0C5E69", marginBottom: 14 }}>
              Según lo que elegiste, estos son los psicólogos con horarios disponibles. Un coordinador se comunicará contigo para ayudarte a verificar que sea el ideal.
            </div>
          )}
          {profsMostrar.length === 0 ? (
            <div style={{ background: "#FDFAF1", border: "1px solid #F0E4C9", borderRadius: 12, padding: 16, fontSize: 14, color: "#8A6D2E" }}>
              No hay psicólogos con horario en línea en {AGENDA_SEDES[sede]?.label} por ahora. Escríbenos por WhatsApp y te ayudamos a agendar. 🙏
            </div>
          ) : profsMostrar.map((p) => ProfCard(p))}
        </div>
      )}

      {/* Paso 4: elegir horario */}
      {showSlots && (
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 11, background: "#EAF5F6", borderRadius: 12, padding: "10px 14px", marginBottom: 14 }}>
            {avatar(prof, 38)}
            <div style={{ fontSize: 14 }}>Reservando con <strong>{prof.nombre}</strong></div>
          </div>
          {!slotsData ? <div style={{ color: "#7B8A90" }}>Buscando horarios libres…</div> :
            slotsData.dias.length === 0 ? (
              <div style={{ background: "#FDFAF1", border: "1px solid #F0E4C9", borderRadius: 12, padding: 16, fontSize: 14, color: "#8A6D2E" }}>
                {prof.nombre} no tiene horarios libres en las próximas semanas. Vuelve y prueba con otro/a psicólogo/a o escríbenos por WhatsApp.
              </div>
            ) : slotsData.dias.map((d) => (
              <div key={d.fecha} style={{ marginBottom: 15 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: AD, marginBottom: 8 }}>{diaLabel(d.fecha)}</div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {d.slots.map((s) => (
                    <button key={s.inicio} onClick={() => { setSlot({ ...s, diaLabel: diaLabel(d.fecha) }); setErr(""); }}
                      style={{ padding: "9px 14px", borderRadius: 999, border: `1px solid ${A}`, background: "#fff", color: A, fontSize: 14, fontWeight: 600, cursor: "pointer" }}>
                      {s.hora}
                    </button>
                  ))}
                </div>
              </div>
            ))}
        </div>
      )}

      {/* Paso 5: datos + confirmar */}
      {showDatos && (
        <div>
          <div style={{ background: "#E7F3F1", border: "1px solid #CBE6E1", borderRadius: 12, padding: "12px 14px", marginBottom: 16, fontSize: 14, color: "#0C5E69" }}>
            <strong>{prof.nombre}</strong> · {slot.diaLabel} a las <strong>{slot.hora}</strong>
            <button onClick={() => setSlot(null)} style={{ marginLeft: 10, background: "none", border: "none", color: A, fontWeight: 600, cursor: "pointer", fontSize: 13 }}>cambiar</button>
          </div>
          <input style={inp} value={form.nombre} onChange={setF("nombre")} placeholder="Nombre y apellidos *" autoFocus />
          <input style={inp} value={form.telefono} onChange={setF("telefono")} placeholder="Teléfono / WhatsApp *" inputMode="tel" />
          <div style={{ display: "flex", gap: 10 }}>
            <input style={inp} value={form.documento} onChange={setF("documento")} placeholder="DNI (opcional)" inputMode="numeric" />
            <input style={inp} value={form.email} onChange={setF("email")} placeholder="Correo (opcional)" inputMode="email" />
          </div>
          {(() => {
            const servs = (info.servicios || []).filter((s) => _profSirveServicio(prof, s.nombre));
            const lista = servs.length ? servs : (info.servicios || []);
            if (!lista.length) return null;
            const val = lista.some((s) => s.nombre === form.servicio) ? form.servicio : (lista[0]?.nombre || "");
            return (
              <select style={{ ...inp, appearance: "auto" }} value={val} onChange={setF("servicio")}>
                {lista.map((s) => <option key={s.nombre} value={s.nombre}>{s.nombre}{s.precio && Number(s.precio) > 0 ? ` — S/${Number(s.precio).toFixed(0)}` : ""}</option>)}
              </select>
            );
          })()}
          {prof.modalidad === "ambas" && (
            <select style={{ ...inp, appearance: "auto" }} value={form.modalidad} onChange={setF("modalidad")}>
              <option value="presencial">Presencial</option>
              <option value="virtual">Virtual</option>
            </select>
          )}
          <textarea style={{ ...inp, minHeight: 74, resize: "vertical", lineHeight: 1.5 }} value={form.mensaje} onChange={setF("mensaje")} placeholder="¿Qué te gustaría trabajar? (opcional)" />
          {err ? <div style={{ color: "#9C4646", fontSize: 13, marginBottom: 10 }}>{err}</div> : null}
          <button onClick={reservar} disabled={enviando}
            style={{ width: "100%", padding: "14px", borderRadius: 11, border: "none", background: A, color: "#fff", fontSize: 15.5, fontWeight: 700, cursor: "pointer", opacity: enviando ? 0.5 : 1 }}>
            {enviando ? "Reservando…" : "Confirmar mi pre-reserva"}
          </button>
          <div style={{ fontSize: 11.5, color: "#7B8A90", marginTop: 10, textAlign: "center" }}>
            Es una pre-reserva: nuestro equipo te contactará para confirmar y enviarte los medios de pago.
          </div>
        </div>
      )}

      {/* Modal "Ver perfil" */}
      {perfil && (
        <div onClick={() => setPerfil(null)} style={{ position: "fixed", inset: 0, background: "rgba(18,28,32,.5)", display: "flex", alignItems: "center", justifyContent: "center", padding: 16, zIndex: 60 }}>
          <div onClick={(e) => e.stopPropagation()} style={{ background: "#fff", borderRadius: 16, maxWidth: 460, width: "100%", maxHeight: "90vh", overflow: "auto", padding: 22, fontFamily: "inherit" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 13 }}>
              {avatar(perfil, 58)}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 800, fontSize: 17 }}>{perfil.nombre}</div>
                <div style={{ fontSize: 12.5, color: "#5B6B72" }}>{perfil.titulo}{perfil.sede_label ? ` · ${perfil.sede_label}` : ""}{perfil.modalidad_label ? ` · ${perfil.modalidad_label}` : ""}</div>
              </div>
              <button onClick={() => setPerfil(null)} style={{ background: "none", border: "none", cursor: "pointer", color: "#8A959A" }}><X size={20} /></button>
            </div>
            {perfil.frase ? <div style={{ fontStyle: "italic", color: AD, fontSize: 14, lineHeight: 1.5, margin: "14px 0 6px", borderLeft: `3px solid ${A}`, paddingLeft: 12 }}>“{perfil.frase}”</div> : null}
            <div style={{ marginTop: 14 }}>
              {[
                { l: "Especialidades y enfoque", v: [perfil.enfoque, perfil.problematicas].filter(Boolean).join("\n\n") },
                { l: "Formación y experiencia", v: [perfil.formacion, perfil.trayectoria].filter(Boolean).join("\n\n") },
                { l: "Público que atiende", v: perfil.poblaciones },
              ].filter((sc) => sc.v && sc.v.trim()).map((sc) => (
                <div key={sc.l} style={{ marginBottom: 14 }}>
                  <div style={{ fontSize: 11.5, fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.5, color: A, marginBottom: 4 }}>{sc.l}</div>
                  <div style={{ fontSize: 13.5, color: "#3D474D", lineHeight: 1.55, whiteSpace: "pre-wrap" }}>{sc.v}</div>
                </div>
              ))}
            </div>
            <button style={{ ...btnPrimary, width: "100%", padding: "13px", fontSize: 15 }} onClick={() => { setProf(perfil); setPerfil(null); }}>
              Elegir a {perfil.nombre.replace(/^lic\.?\s*/i, "").trim().split(" ")[0]}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
