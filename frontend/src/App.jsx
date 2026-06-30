import React, { useState, useMemo, useEffect } from "react";
import {
  Home, Calendar, Users, Receipt, Search, Plus, Clock, ChevronLeft, ChevronDown,
  Phone, Cake, X, Stethoscope, MessageCircle, Check, Pencil, UserPlus, FileText,
  TrendingUp, Download, AlertTriangle, Megaphone, LogOut,
  Paperclip, Trash2, Activity, Pill, HeartPulse, Copy, BarChart3, UserCog, KeyRound, MapPin,
  Mic,
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
  { v: "agendado", l: "Consulta agendada" },
  { v: "no_realizada", l: "Consulta no realizada" },
  { v: "evaluando", l: "Evaluando inicio" },
  { v: "pendiente_pago", l: "Pendiente de pago" },
  { v: "ganado", l: "Inició proceso" },
  { v: "perdido", l: "Perdido" },
];
const LEAD_ESTADO_COLOR = {
  nuevo: { bg: "#EFEDE8", fg: "#7C7870" },
  contactado: { bg: "#E2ECF5", fg: "#2E5C86" },
  agendado: { bg: "#F7ECDD", fg: "#9C6B2E" },
  no_realizada: { bg: "#F0E7E7", fg: "#8A5A5A" },
  evaluando: { bg: "#E6EEF5", fg: "#2E5C86" },
  pendiente_pago: { bg: "#F7ECDD", fg: "#9C6B2E" },
  ganado: { bg: "#E9F1ED", fg: "#3E7A65" },
  perdido: { bg: "#F7E5E5", fg: "#9C4646" },
};
const FUENTES = [
  { v: "meta_ads", l: "Meta Ads" }, { v: "google", l: "Google" },
  { v: "instagram", l: "Instagram" }, { v: "facebook", l: "Facebook" },
  { v: "tiktok", l: "TikTok" }, { v: "referido_paciente", l: "Referido por paciente" },
  { v: "referido_psicologo", l: "Referido por psicólogo" }, { v: "referido", l: "Referido" },
  { v: "convenio", l: "Convenio" }, { v: "organico", l: "Orgánico" },
  { v: "web", l: "Página web" }, { v: "whatsapp", l: "WhatsApp directo" },
  { v: "bot", l: "Bot / Chatbot" }, { v: "agendapro", l: "AgendaPro web" },
  { v: "derivado", l: "Derivado de otra sede" }, { v: "linkedin", l: "LinkedIn" },
  { v: "otro", l: "Otro" },
];
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
  { v: "continuidad", l: "Ficha de continuidad" },
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
  const [mensajes, setMensajes] = useState([]);
  const [servicios, setServicios] = useState([]);
  const [waPaciente, setWaPaciente] = useState(null);
  const [usuario, setUsuario] = useState(null);
  const [iniciando, setIniciando] = useState(true);
  const [query, setQuery] = useState("");
  const [filterEsp, setFilterEsp] = useState(null);
  const [filterSede, setFilterSede] = useState(null);
  const [filterProf, setFilterProf] = useState("");
  const [soloSinProxima, setSoloSinProxima] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [adding, setAdding] = useState(false);
  const [atender, setAtender] = useState(null);
  const [recordar, setRecordar] = useState(null);
  const [reagendar, setReagendar] = useState(null);
  const [cancelando, setCancelando] = useState(null);
  const [cobrando, setCobrando] = useState(null);
  const [citaDetalle, setCitaDetalle] = useState(null);
  const [cambiarPass, setCambiarPass] = useState(false);
  const [agendarPara, setAgendarPara] = useState(null);
  const [vendiendoPaquete, setVendiendoPaquete] = useState(null);
  const [agendaFecha, setAgendaFecha] = useState(HOY_ISO);
  const [agendaVista, setAgendaVista] = useState("dia");
  const [editingPaciente, setEditingPaciente] = useState(null);
  const [registrandoSesion, setRegistrandoSesion] = useState(null);
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

  const selected = pacientes.find((p) => p.id === selectedId) || null;
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return pacientes.filter((p) =>
      (!q || p.nombre.toLowerCase().includes(q) || (p.tel || "").toLowerCase().includes(q) || (p.numero_documento || "").toLowerCase().includes(q)) &&
      (!filterEsp || p.especialidad === filterEsp) &&
      (!filterSede || p.sede === filterSede) &&
      (!filterProf || p.profesional_nombre === filterProf) &&
      (!soloSinProxima || !p.proxima));
  }, [pacientes, query, filterEsp, filterSede, filterProf, soloSinProxima]);

  // Psicólogos presentes en la lista de pacientes (para el filtro).
  // Psicólogos del filtro: solo los que tienen pacientes en la sede elegida.
  const profsEnPacientes = useMemo(
    () => [...new Set(pacientes.filter((p) => !filterSede || p.sede === filterSede).map((p) => p.profesional_nombre).filter(Boolean))].sort(),
    [pacientes, filterSede]
  );

  const nav = [
    { id: "hoy", label: "Hoy", icon: Home },
    // El panel de Gerencia lo ve solo el dueño/admin.
    ...(usuario?.rol === "admin" ? [{ id: "gerencia", label: "Gerencia", icon: BarChart3 }] : []),
    ...(usuario?.rol === "admin" ? [{ id: "historico", label: "Histórico", icon: Activity }] : []),
    ...(usuario?.rol === "admin" ? [{ id: "reporte", label: "Reporte", icon: FileText }] : []),
    ...(usuario?.rol === "admin" ? [{ id: "ocupacion", label: "Ocupación", icon: Clock }] : []),
    // Clínico (Agenda, Pacientes, Profesionales): gerencia, coordinación y psicólogo (no comercial).
    ...(usuario?.rol !== "comercial" ? [{ id: "agenda", label: "Agenda", icon: Calendar }] : []),
    ...(usuario?.rol !== "comercial" ? [{ id: "pacientes", label: "Pacientes", icon: Users }] : []),
    ...(usuario?.rol !== "comercial" ? [{ id: "profesionales", label: "Profesionales", icon: HeartPulse }] : []),
    // Mensajes: gerencia, coordinación y comercial (no psicólogo).
    ...(usuario?.rol !== "medico" ? [{ id: "mensajes", label: "Mensajes", icon: MessageCircle }] : []),
    // Marketing / Leads: gerencia y comercial.
    ...((usuario?.rol === "admin" || usuario?.rol === "comercial") ? [{ id: "marketing", label: "Marketing", icon: Megaphone }] : []),
    // Finanzas: solo gerencia.
    ...(usuario?.rol === "admin" ? [{ id: "finanzas", label: "Finanzas", icon: TrendingUp }] : []),
    ...(usuario?.rol === "admin" ? [{ id: "equipo", label: "Equipo", icon: UserCog }] : []),
    ...(usuario?.rol === "admin" ? [{ id: "whatsapp", label: "Conexión WhatsApp", icon: MessageCircle }] : []),
    ...(usuario?.rol === "admin" ? [{ id: "hojas", label: "Editar (Excel)", icon: Pencil }] : []),
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
  function openFicha(id) { if (!id) return; setView("pacientes"); setSelectedId(id); }

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

  async function enviarMensajePaciente(paciente, texto, tipo, plantillaId) {
    try {
      const r = await api.enviarMensajePaciente(paciente.id, texto, tipo, plantillaId);
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
        const nuevo = await api.crearPaciente({ nombre: data.nuevoNombre, especialidad: data.especialidad, sede: data.sede || "" });
        pacienteId = nuevo.id;
      }
      const r = await api.agendarCita({
        pacienteId, fecha: data.fecha, hora: data.hora, especialidad: data.especialidad,
        medicoId: data.medicoId || null, sede: data.sede || "", modalidad: data.modalidad || "presencial",
        enlace: data.enlace || "", notas: data.notas || "", n_sesion: data.n_sesion || null,
      });
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
      await Promise.all([refrescarCitas(), refrescarPacientes()]);
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

  async function setEstadoCita(cita, estado) {
    try {
      await api.setEstadoCita(cita.id, estado);
      await refrescarCitas();
      const lbl = (ESTADOS_CITA.find((e) => e.v === estado) || {}).l || estado;
      showToast(`Estado: ${lbl} ✓`);
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
            vista={agendaVista} setVista={setAgendaVista} esAsistente={esAsistente} esMedico={usuario?.rol === "medico"}
            onAgendar={() => setAdding(true)} onAtender={setAtender} onRecordar={setRecordar}
            onReagendar={setReagendar} onCancelar={setCancelando} openFicha={openFicha}
            onConfirmar={confirmarCita} onSetEstado={setEstadoCita} onAbrirCita={setCitaDetalle}
            onCobrar={(c) => setCobrando({ pacienteId: c.pacienteId, paciente: c.paciente, citaId: c.id, especialidad: c.especialidad })}
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
                <ExportBtns nombre="pacientes" titulo="Pacientes" disabled={filtered.length === 0}
                  headers={["Nombre", "Documento", "Numero", "Edad", "Genero", "Telefono", "Direccion", "Especialidad", "Ultima visita", "Proxima sesion", "Pendiente S/"]}
                  filas={filtered.map((p) => [p.nombre, p.tipo_documento_label || "", p.numero_documento || "", p.edad ?? "", p.genero_label || "", p.tel, p.direccion || "", p.especialidad, p.ultima, p.proxima ? `${p.proxima.fecha} ${p.proxima.hora}` : "", p.cuenta?.pendiente || 0])} />
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
              <button className={`ca-fchip ${!filterSede ? "on" : ""}`} onClick={() => { setFilterSede(null); setFilterProf(""); }}>Todas las sedes</button>
              <button className={`ca-fchip ${filterSede === "piura" ? "on" : ""}`} onClick={() => { setFilterSede("piura"); setFilterProf(""); }}>Piura</button>
              <button className={`ca-fchip ${filterSede === "lima" ? "on" : ""}`} onClick={() => { setFilterSede("lima"); setFilterProf(""); }}>Lima</button>
              {profsEnPacientes.length > 0 && (
                <select className="ca-input" style={{ width: "auto", padding: "6px 10px", marginLeft: 6 }} value={filterProf} onChange={(e) => setFilterProf(e.target.value)}>
                  <option value="">Todos los psicólogos</option>
                  {profsEnPacientes.map((n) => <option key={n} value={n}>{n}</option>)}
                </select>
              )}
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
                  <div key={p.id} className="ca-row click" onClick={() => setSelectedId(p.id)}>
                    <div className="ca-avatar">{iniciales(p.nombre)}</div>
                    <div style={{ flex: 1 }}>
                      <div className="ca-pname">{p.nombre}</div>
                      <div className="ca-pmeta">{p.profesional_nombre ? `${p.profesional_nombre} · ` : ""}{meta || `última visita ${p.ultima}`}</div>
                    </div>
                    {p.cuenta?.pendiente > 0 && <Tag colors={ESTADO_COBRO_COLOR.pendiente}>Debe {money(p.cuenta.pendiente)}</Tag>}
                    {p.sede_label && <Tag colors={p.sede === "piura" ? { bg: "#D7F4FA", fg: "#0A7D92" } : { bg: "#FBE9D6", fg: "#B5701F" }}>{p.sede_label}</Tag>}
                  </div>
                );
              })
            )}
          </>
        )}

        {view === "pacientes" && selected && (
          <Ficha p={selected} onBack={() => setSelectedId(null)} onEdit={() => setEditingPaciente(selected)}
            onWhatsApp={() => setWaPaciente(selected)} clinica={nombreClinica} onAgendar={() => setAgendarPara(selected)}
            onRegistrarSesion={() => setRegistrandoSesion(selected)} puedeRegistrar={usuario?.rol === "medico" || usuario?.rol === "admin"}
            onVenderPaquete={() => setVendiendoPaquete(selected)} puedeVenderPaquete={usuario?.rol === "asistente" || usuario?.rol === "admin"}
            onRegistrarPago={() => setCobrando({ pacienteId: selected.id, paciente: selected.nombre, especialidad: selected.especialidad })}
            puedeCobrar={usuario?.rol === "asistente" || usuario?.rol === "admin"}
            onSubirAdjunto={(file) => subirAdjunto(selected, file)}
            onEliminarAdjunto={eliminarAdjunto} puedeEliminar={usuario?.rol === "medico" || usuario?.rol === "admin"} />
        )}

        {view === "gerencia" && <Gerencia showToast={showToast} />}

        {view === "historico" && <Historico showToast={showToast} esAdmin={usuario?.rol === "admin"} />}

        {view === "reporte" && <ReporteSemanal showToast={showToast} esAdmin={usuario?.rol === "admin"} />}

        {view === "ocupacion" && <Ocupacion showToast={showToast} />}

        {view === "equipo" && <Equipo showToast={showToast} miId={usuario?.id} />}

        {view === "whatsapp" && <ConexionWhatsapp showToast={showToast} />}

        {view === "hojas" && <HojasExcel showToast={showToast} onCambio={cargarDatos} />}

        {view === "profesionales" && <Profesionales showToast={showToast} esAdmin={usuario?.rol === "admin"} />}

        {view === "mensajes" && <Mensajes mensajes={mensajes} esAdmin={usuario?.rol === "admin"} showToast={showToast} />}

        {view === "marketing" && <Marketing showToast={showToast} onConvertir={refrescarPacientes} esAdmin={usuario?.rol === "admin"} />}

        {view === "finanzas" && <Finanzas showToast={showToast} esAdmin={usuario?.rol === "admin"} />}

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
        {atender && <AtenderModal cita={atender} servicios={servicios} onClose={() => setAtender(null)} onSave={(datos) => guardarAtencion(atender, datos)} />}
        {recordar && <RecordarModal cita={recordar} clinica={nombreClinica} onClose={() => setRecordar(null)} onSend={(texto) => enviarRecordatorio(recordar, texto)} />}
        {reagendar && <ReagendarModal cita={reagendar} onClose={() => setReagendar(null)} onSave={moverCita} />}
        {cobrando && <CobroModal prefill={cobrando} pacientes={pacientes} servicios={servicios} onClose={() => setCobrando(null)} onSave={guardarCobro} />}
        {citaDetalle && (
          <CitaDetalleModal cita={citaDetalle} esMedico={usuario?.rol === "medico"} esAsistente={esAsistente}
            onClose={() => setCitaDetalle(null)} onSetEstado={setEstadoCita} openFicha={openFicha}
            onAtender={setAtender} onReagendar={setReagendar} onCancelar={setCancelando}
            onCobrar={(c) => setCobrando({ pacienteId: c.pacienteId, paciente: c.paciente, citaId: c.id, especialidad: c.especialidad })} />
        )}
        {cancelando && (
          <ConfirmModal
            titulo="Cancelar sesión"
            mensaje={`¿Cancelar la sesión de ${cancelando.paciente} del ${labelLargo(cancelando.fecha)} a las ${cancelando.hora}? Quedará registrada como cancelada.`}
            confirmLabel="Sí, cancelar" peligro
            onConfirm={() => cancelarCita(cancelando)} onClose={() => setCancelando(null)}
          />
        )}
        {waPaciente && <MensajePacienteModal paciente={waPaciente} onClose={() => setWaPaciente(null)} onSend={(texto, tipo, plantillaId) => enviarMensajePaciente(waPaciente, texto, tipo, plantillaId)} />}
        {editingPaciente && (
          <PacienteModal paciente={editingPaciente.new ? null : editingPaciente}
            onClose={() => setEditingPaciente(null)} onSave={guardarPaciente} />
        )}
        {registrandoSesion && (
          <RegistrarSesionModal paciente={registrandoSesion}
            onClose={() => setRegistrandoSesion(null)} onSave={(d) => guardarRegistroSesion(registrandoSesion, d)} />
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
const OPC_ESTADO_LEAD = _op([["nuevo", "Nuevo"], ["contactado", "Contactado"], ["agendado", "Agendado"], ["no_realizada", "No realizada"], ["evaluando", "Evaluando"], ["pendiente_pago", "Pend. pago"], ["ganado", "Inició proceso"], ["perdido", "Perdido"]]);
const OPC_ESTADO_COBRO = _op([["pagado", "Pagado"], ["pendiente", "Pendiente"], ["anulado", "Anulado"]]);
const OPC_MEDIO = _op([["", "—"], ["efectivo", "Efectivo"], ["yape", "Yape"], ["plin", "Plin"], ["tarjeta", "Tarjeta"], ["transferencia", "Transferencia"]]);
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

function Ficha({ p, onBack, onEdit, onWhatsApp, onSubirAdjunto, onEliminarAdjunto, puedeEliminar, clinica, onAgendar, onRegistrarSesion, puedeRegistrar, onVenderPaquete, puedeVenderPaquete, onRegistrarPago, puedeCobrar }) {
  return (
    <div>
      <button className="ca-back" onClick={onBack}><ChevronLeft size={16} strokeWidth={2} /> Pacientes</button>
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 22 }}>
        <div className="ca-avatar" style={{ width: 52, height: 52, fontSize: 18, borderRadius: 13 }}>{iniciales(p.nombre)}</div>
        <div style={{ flex: 1 }}>
          <h1 className="ca-h1" style={{ fontSize: 22 }}>{p.nombre}</h1>
          <div style={{ marginTop: 7 }}><SpecialtyTag name={p.especialidad} /></div>
        </div>
        {puedeRegistrar && <button className="ca-mini" onClick={onRegistrarSesion}><Activity size={13} strokeWidth={2} /> Registrar sesión</button>}
        <button className="ca-mini" onClick={onAgendar}><Calendar size={13} strokeWidth={2} /> Agendar</button>
        <button className="ca-mini wa" onClick={onWhatsApp}><MessageCircle size={13} strokeWidth={2} /> WhatsApp</button>
        <button className="ca-mini" onClick={() => imprimirHistoria(p, clinica)}><FileText size={13} strokeWidth={2} /> Imprimir</button>
        <button className="ca-mini" onClick={onEdit}><Pencil size={13} strokeWidth={2} /> Editar</button>
      </div>

      <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginBottom: 26 }}>
        {p.profesional_nombre && <div className="ca-field"><HeartPulse size={15} strokeWidth={1.9} style={{ color: "var(--accent)" }} /> {p.profesional_nombre}</div>}
        {p.sede_label && <div className="ca-field"><MapPin size={15} strokeWidth={1.9} style={{ color: "var(--muted)" }} /> Sede {p.sede_label}</div>}
        {(p.n_sesion > 0 || p.proceso_label) && <div className="ca-field"><Activity size={15} strokeWidth={1.9} style={{ color: "var(--muted)" }} /> {p.proceso === "consulta" ? "Consulta inicial" : `Sesión ${p.n_sesion}${p.proceso_label ? ` · ${p.proceso_label}` : ""}`}</div>}
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

      <h2 className="ca-secth">Antecedentes</h2>
      <div className="ca-card" style={{ marginBottom: 26 }}>
        <div className="ca-anteced">
          <AntItem icon={AlertTriangle} label="Alergias" valor={p.alergias} alerta />
          <AntItem icon={HeartPulse} label="Antecedentes / condiciones" valor={p.antecedentes} />
          <AntItem icon={Pill} label="Medicación habitual" valor={p.medicacion_habitual} />
        </div>
        <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 14 }}>Edita los antecedentes desde el botón «Editar» del paciente.</div>
      </div>

      {(p.cuenta || puedeCobrar) && (
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
                <span style={{ flex: 1, minWidth: 0 }}>{c.concepto}{c.comprobante ? <span style={{ color: "var(--muted)", fontSize: 12 }}> · {c.comprobante}{c.comprobante_numero ? ` ${c.comprobante_numero}` : ""}</span> : null}</span>
                <span style={{ fontVariantNumeric: "tabular-nums", fontWeight: 500 }}>{money(c.monto)}</span>
                <Tag colors={ESTADO_COBRO_COLOR[c.estado]}>{c.estado === "pagado" ? (c.medio || "Pagado") : "Pendiente"}</Tag>
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

      <h2 className="ca-secth">Historia clínica</h2>
      <div className="ca-card">
        {p.historial.length === 0 ? (
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
  const [medicos, setMedicos] = useState([]);
  const [medicoId, setMedicoId] = useState("");
  const [sede, setSede] = useState(pacienteFijo?.sede || "");
  const [modalidad, setModalidad] = useState("presencial");
  const [enlace, setEnlace] = useState("");
  const [notas, setNotas] = useState("");
  const [error, setError] = useState("");
  const [nSesion, setNSesion] = useState(
    pacienteFijo?.n_sesion != null ? String(pacienteFijo.n_sesion + 1) : ""
  );

  useEffect(() => { api.medicos().then(setMedicos).catch(() => {}); }, []);

  // Solo psicólogos de la sede elegida (si hay sede); si no, todos los activos.
  const medicosVisibles = medicos.filter((m) => !sede || !m.sede || m.sede === sede);

  const matches = useMemo(
    () => (busca.trim() ? pacientes.filter((p) => p.nombre.toLowerCase().includes(busca.toLowerCase())).slice(0, 4) : []),
    [busca, pacientes]
  );

  function elegir(p) {
    setSel(p); setNuevo(false); setEsp(p.especialidad || "Terapia individual");
    if (p.sede) setSede(p.sede);
    if (p.n_sesion != null) setNSesion(String(p.n_sesion + 1));
    setBusca("");
  }
  function elegirNuevo() { setNuevo(true); setSel(null); }
  function limpiar() { setSel(null); setNuevo(false); setBusca(""); }

  function guardar() {
    if (!sel && !(nuevo && busca.trim())) {
      setError("Selecciona un paciente: búscalo y haz clic en su nombre, o usa «Crear paciente nuevo».");
      return;
    }
    if (!fecha) { setError("Falta la fecha."); return; }
    if (!hora.trim()) { setError("Falta la hora."); return; }
    setError("");
    const extra = {
      especialidad: esp, fecha, hora, medicoId: medicoId || null, sede,
      modalidad, enlace: modalidad === "virtual" ? enlace.trim() : "",
      notas: notas.trim(), n_sesion: nSesion ? Number(nSesion) : null,
    };
    if (sel) onSave({ pacienteId: sel.id, paciente: sel.nombre, ...extra });
    else if (nuevo) onSave({ nuevoNombre: busca.trim(), ...extra });
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
        <div style={{ marginBottom: 13 }}>
          <div className="ca-label">Especialidad</div>
          <select className="ca-input" value={esp} onChange={(e) => setEsp(e.target.value)}>
            {Object.keys(SPECIALTY).map((s) => <option key={s}>{s}</option>)}
          </select>
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

        <div style={{ marginBottom: 20 }}>
          <div className="ca-label">Notas (opcional)</div>
          <textarea className="ca-input" style={{ minHeight: 52, resize: "vertical", lineHeight: 1.5 }} value={notas} onChange={(e) => setNotas(e.target.value)} placeholder="Indicaciones para la cita, recordatorios…" />
        </div>

        {error && <div style={{ color: "#B4564E", fontSize: 13, marginBottom: 10, background: "#FDECEA", border: "1px solid #F3C9C4", borderRadius: 8, padding: "8px 10px" }}>{error}</div>}
        <div style={{ display: "flex", gap: 9, justifyContent: "flex-end" }}>
          <button className="ca-btn ghost" onClick={onClose}>Cancelar</button>
          <button className="ca-btn" onClick={guardar}>Agendar</button>
        </div>
      </div>
    </div>
  );
}

function CitaRow({ c, esAsistente, esMedico, onAtender, onRecordar, onReagendar, onCancelar, onConfirmar, onCobrar, onSetEstado, openFicha }) {
  const activa = c.estado !== "atendida" && c.estado !== "cancelada";
  const pendiente = c.estado === "agendada" || c.estado === "por_confirmar" || c.estado === "reprogramada";
  const col = STATUS[c.estado] || {};
  return (
    <div className="ca-row">
      <div className="ca-time"><Clock size={13} strokeWidth={2} style={{ color: "var(--muted)" }} />{c.hora}</div>
      <div style={{ flex: 1, minWidth: 150 }}>
        <button className="ca-pnamebtn" onClick={() => openFicha(c.pacienteId)}>{c.paciente}</button>
        <div className="ca-pmeta">
          {c.medico}{c.n_sesion ? ` · Sesión N° ${c.n_sesion}` : ""}{c.sede_label ? ` · ${c.sede_label}` : ""} · {c.modalidad === "virtual" ? "Virtual" : "Presencial"}
          {c.modalidad === "virtual" && c.enlace && (<> · <a href={c.enlace} target="_blank" rel="noreferrer" style={{ color: "var(--accent)", fontWeight: 600 }}>Unirse</a></>)}
        </div>
        {c.notas && <div className="ca-pmeta" style={{ fontStyle: "italic" }}>{c.notas}</div>}
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
        {/* El psicólogo no ve acciones comerciales (confirmar, recordar, cobrar). */}
        {!esMedico && pendiente && (
          <button className="ca-mini" onClick={() => onConfirmar(c)} title="Marcar confirmada"><Check size={13} strokeWidth={2.2} /> Confirmar</button>
        )}
        {!esMedico && pendiente && (c.recordado ? (
          <span className="ca-mini done"><Check size={13} strokeWidth={2.4} /> Recordado</span>
        ) : (
          <button className="ca-mini wa" onClick={() => onRecordar(c)}><MessageCircle size={13} strokeWidth={2} /> Recordar</button>
        ))}
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

// Agenda multi-terapeuta (estilo AgendaPro): horas a la izquierda, una columna por
// CADA psicólogo activo (atienda o no ese día). Clic en una cita abre su detalle.
function TerapeutasGrid({ citas, terapeutas, onAbrirCita }) {
  const horas = citas.map((c) => parseInt(c.hora.slice(0, 2), 10)).filter((h) => !isNaN(h));
  const hIni = horas.length ? Math.max(6, Math.min(...horas, 8)) : 8;
  const hFin = horas.length ? Math.min(22, Math.max(...horas, 19) + 1) : 20;
  const rows = [];
  for (let h = hIni; h <= hFin; h++) rows.push(h);

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
                return (
                  <td key={t} style={{ verticalAlign: "top" }}>
                    {evs.map((c) => {
                      const col = STATUS[c.estado] || STATUS.agendada;
                      return (
                        <button key={c.id} onClick={() => onAbrirCita(c)}
                          title={`${c.hora} · ${c.paciente} · ${c.especialidad} · ${c.estado_label}`}
                          style={{ display: "block", width: "100%", textAlign: "left", border: "none",
                                   borderLeft: `3px solid ${col.fg}`, background: col.bg, borderRadius: 6,
                                   padding: "4px 7px", marginBottom: 4, cursor: "pointer" }}>
                          <span style={{ fontSize: 11.5, fontWeight: 600, color: col.fg }}>{c.hora}</span>
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

function Agenda({ citas, fecha, setFecha, vista, setVista, esAsistente, esMedico, onAgendar, onAtender, onRecordar, onReagendar, onCancelar, onConfirmar, onCobrar, onSetEstado, onAbrirCita, openFicha }) {
  const [filtroMedico, setFiltroMedico] = useState("");
  const [medicosDir, setMedicosDir] = useState([]);
  useEffect(() => { api.medicos().then(setMedicosDir).catch(() => {}); }, []);
  // Lista de psicólogos activos del directorio + cualquiera presente en las citas,
  // para que aparezcan todos (no solo los que ya tienen sesiones).
  const medicos = useMemo(() => {
    const nombres = new Set(medicosDir.map((m) => m.nombre).filter(Boolean));
    citas.forEach((c) => { if (c.medico) nombres.add(c.medico); });
    return [...nombres].sort();
  }, [medicosDir, citas]);
  const semana = vista === "semana" ? semanaDe(fecha) : null;
  const delDia = (iso) => citas
    .filter((c) => c.fecha === iso && (!filtroMedico || c.medico === filtroMedico))
    .sort((a, b) => a.hora.localeCompare(b.hora));
  const visibles = vista === "semana" ? citas.filter((c) => semana.includes(c.fecha)) : delDia(fecha);
  const activas = visibles.filter((c) => c.estado !== "cancelada");
  // Resumen de cuántas citas hay en cada estado (del día/semana mostrado).
  const resumen = ESTADOS_CITA.map((e) => ({ ...e, n: visibles.filter((c) => c.estado === e.v).length })).filter((e) => e.n > 0);
  const subt = vista === "semana" ? `${labelNumMes(semana[0])} – ${labelNumMes(semana[6])}` : labelLargo(fecha);
  const paso = vista === "semana" ? 7 : 1;

  return (
    <>
      <div className="ca-tophead">
        <div>
          <h1 className="ca-h1">Agenda</h1>
          <div className="ca-sub">{subt} · {activas.length} {activas.length === 1 ? "sesión" : "sesiones"}</div>
        </div>
        <div style={{ display: "flex", gap: 9, alignItems: "center" }}>
          <ExportBtns nombre="agenda" titulo="Agenda" disabled={activas.length === 0}
            headers={["Fecha", "Hora", "Paciente", "Psicologo", "Especialidad", "N° sesion", "Sede", "Modalidad", "Estado"]}
            filas={activas.map((c) => [c.fecha, c.hora, c.paciente, c.medico, c.especialidad, c.n_sesion || "", c.sede_label || "", c.modalidad === "virtual" ? "Virtual" : "Presencial", c.estado_label])} />
          <button className="ca-btn" onClick={onAgendar}><Plus size={16} strokeWidth={2.2} /> Agendar sesión</button>
        </div>
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
            <option value="">Todos los psicólogos</option>
            {medicos.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        )}
        <div className="ca-seg">
          <button className={vista === "dia" ? "on" : ""} onClick={() => setVista("dia")}>Día</button>
          <button className={vista === "terapeutas" ? "on" : ""} onClick={() => setVista("terapeutas")}>Terapeutas</button>
          <button className={vista === "semana" ? "on" : ""} onClick={() => setVista("semana")}>Semana</button>
        </div>
      </div>

      {resumen.length > 0 && (
        <div style={{ display: "flex", gap: 7, flexWrap: "wrap", margin: "2px 0 4px" }}>
          {resumen.map((e) => (
            <span key={e.v} style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 12.5, fontWeight: 600,
              padding: "3px 10px", borderRadius: 999, background: (STATUS[e.v] || {}).bg, color: (STATUS[e.v] || {}).fg }}>
              {e.l}: {e.n}
            </span>
          ))}
        </div>
      )}

      {vista === "dia" ? (
        <div style={{ marginTop: 18 }}>
          {delDia(fecha).length === 0 ? (
            <div className="ca-empty">No hay sesiones para este día. Usa «Agendar sesión» para reservar una.</div>
          ) : (
            delDia(fecha).map((c) => (
              <CitaRow key={c.id} c={c} esAsistente={esAsistente} esMedico={esMedico}
                onAtender={onAtender} onRecordar={onRecordar} onReagendar={onReagendar}
                onCancelar={onCancelar} onConfirmar={onConfirmar} onCobrar={onCobrar}
                onSetEstado={onSetEstado} openFicha={openFicha} />
            ))
          )}
        </div>
      ) : vista === "terapeutas" ? (
        <TerapeutasGrid citas={delDia(fecha)} terapeutas={filtroMedico ? [filtroMedico] : medicos} onAbrirCita={onAbrirCita} />
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

function CitaDetalleModal({ cita, esMedico, esAsistente, onClose, onSetEstado, openFicha, onAtender, onCobrar, onReagendar, onCancelar }) {
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
          {activa && !esAsistente && <button className="ca-mini" onClick={() => { onClose(); onAtender(cita); }}><Stethoscope size={13} strokeWidth={2} /> {esMedico ? "Registrar sesión" : "Atender"}</button>}
          {!esMedico && <button className="ca-mini" onClick={() => { onClose(); onCobrar(cita); }}><Receipt size={13} strokeWidth={2} /> Cobrar</button>}
          {activa && <button className="ca-mini" onClick={() => { onClose(); onReagendar(cita); }}><Calendar size={13} strokeWidth={2} /> Mover</button>}
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

function Mensajes({ mensajes, esAdmin, showToast }) {
  const [plantillas, setPlantillas] = useState(null);
  const [editando, setEditando] = useState(null); // { id, texto }

  useEffect(() => { api.plantillas().then(setPlantillas).catch(() => setPlantillas([])); }, []);

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

      <h2 className="ca-secth" style={{ marginTop: 22 }}>Plantillas</h2>
      <div className="ca-pmeta" style={{ marginBottom: 10 }}>
        Variables que se reemplazan solas: <code>{"{nombre} {psicologo} {fecha} {hora} {n_sesion} {sede} {clinica}"}</code>
      </div>
      {!plantillas ? <div className="ca-empty">Cargando…</div> : plantillas.map((p) => (
        <div key={p.id} className="ca-card" style={{ marginBottom: 10 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6, gap: 8 }}>
            <strong style={{ fontSize: 13.5, display: "flex", alignItems: "center", gap: 8 }}>
              {p.nombre}
              {p.wa_template_nombre
                ? <Tag colors={{ bg: "#E4F3E8", fg: "#1E7D45" }}>Aprobada: {p.wa_template_nombre}</Tag>
                : <Tag colors={{ bg: "#FBF0D4", fg: "#8A6D14" }}>Texto (solo 24h)</Tag>}
            </strong>
            {esAdmin && editando?.id !== p.id && (
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

function MensajePacienteModal({ paciente, onClose, onSend }) {
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
    api.plantillas(paciente.id).then((ps) => setPlantillas(ps.filter((p) => p.activo))).catch(() => {});
  }, [paciente.id, sinTel]);

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
    } catch (err) { showToast("Error: " + err.message); }
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
            headers={["Nombre", "Telefono", "Fuente", "Pauta", "Campaña", "Especialidad", "Psicologo", "Estado", "Creado"]}
            filas={leads.map((l) => [l.nombre, l.telefono, l.fuente_label, l.es_pauta ? "Si" : "No", l.campania, l.especialidad, l.medico_nombre, l.estado_label, l.creado])} />
          <button className="ca-btn" onClick={() => setCreando(true)}>
            <Plus size={16} strokeWidth={2.2} /> Captar lead
          </button>
        </div>
      </div>

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
          <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 7 }}>
            {anuncios.map((a) => (
              <div key={a.id} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13.5 }}>
                <span style={{ fontWeight: 600 }}>{a.nombre}</span>
                <span className="ca-pmeta">{a.plataforma_label} · {a.n_leads} lead{a.n_leads === 1 ? "" : "s"}</span>
                {a.link && <a href={a.link} target="_blank" rel="noreferrer" style={{ color: "var(--accent)", fontSize: 12.5 }}>ver</a>}
                <button className="ca-iconbtn" style={{ marginLeft: "auto" }} title="Eliminar" onClick={() => quitarAnuncio(a.id)}><Trash2 size={13} strokeWidth={2} /></button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginTop: 30 }}>
        <h2 className="ca-secth" style={{ marginTop: 0 }}>Leads ({leads.filter((l) => !filtroSedeLead || l.sede === filtroSedeLead).length})</h2>
        <div className="ca-seg">
          {[["", "Todas"], ["lima", "Lima"], ["piura", "Piura"]].map(([v, l]) => (
            <button key={v || "todas"} className={filtroSedeLead === v ? "on" : ""} onClick={() => setFiltroSedeLead(v)}>{l}</button>
          ))}
        </div>
      </div>
      {leads.filter((l) => !filtroSedeLead || l.sede === filtroSedeLead).length === 0 ? (
        <div className="ca-empty">No hay leads{filtroSedeLead ? " en esta sede" : ". Capta el primero con el botón de arriba."}.</div>
      ) : (
        leads.filter((l) => !filtroSedeLead || l.sede === filtroSedeLead).map((lead) => {
          const sem = LEAD_SEM[lead.semaforo];
          return (
          <div key={lead.id} className="ca-row" style={lead.agendo_consulta === false ? { borderLeft: "3px solid #D85656" } : undefined}>
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
                  <span style={{ marginLeft: 8, fontSize: 10.5, background: "#E9F1ED", color: "#3E7A65", padding: "1px 7px", borderRadius: 999, fontWeight: 600, verticalAlign: "middle" }}>📅 {lead.fecha_consulta}</span>
                )}
              </div>
              <div className="ca-pmeta">
                {lead.sede_label ? `${lead.sede_label} · ` : ""}{lead.fuente_label}{lead.tipo_servicio_label ? ` · ${lead.tipo_servicio_label}` : ""}{lead.anuncio_nombre ? ` · 📣 ${lead.anuncio_nombre}` : ""}{lead.medico_nombre ? ` · ${lead.medico_nombre}` : ""}
              </div>
            </div>
            <select className="ca-tplsel" value={lead.estado} onChange={(ev) => moverEstado(lead, ev.target.value)}>
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
  const PLATS = [{ v: "instagram", l: "Instagram" }, { v: "facebook", l: "Facebook" }, { v: "tiktok", l: "TikTok" }, { v: "otro", l: "Otro" }];
  return (
    <div style={{ display: "flex", gap: 9, alignItems: "flex-end", flexWrap: "wrap" }}>
      <div style={{ flex: 2, minWidth: 160 }}><div className="ca-label">Anuncio / publicación</div><input className="ca-input" value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder='ej. "reaccionas y luego te arrepientes"' /></div>
      <div style={{ flex: 2, minWidth: 160 }}><div className="ca-label">Link (opcional)</div><input className="ca-input" value={link} onChange={(e) => setLink(e.target.value)} placeholder="https://instagram.com/p/…" /></div>
      <div style={{ flex: 1, minWidth: 110 }}><div className="ca-label">Plataforma</div><select className="ca-input" value={plataforma} onChange={(e) => setPlataforma(e.target.value)}>{PLATS.map((p) => <option key={p.v} value={p.v}>{p.l}</option>)}</select></div>
      <button className="ca-btn" style={{ opacity: nombre.trim() ? 1 : 0.5, pointerEvents: nombre.trim() ? "auto" : "none" }}
        onClick={() => { onSave({ nombre: nombre.trim(), link: link.trim(), plataforma }); setNombre(""); setLink(""); }}>
        <Plus size={15} strokeWidth={2.2} /> Agregar
      </button>
    </div>
  );
}

function CrearLeadModal({ lead, medicos, anuncios, onClose, onSave }) {
  const [f, setF] = useState({
    nombre: lead?.nombre || "",
    telefono: lead?.telefono && lead.telefono !== "—" ? lead.telefono : "",
    sede: lead?.sede || "lima",
    fuente: lead?.fuente || "instagram",
    fuente_otro: lead?.fuente_otro || "",
    es_pauta: lead ? lead.es_pauta : true,
    anuncio: lead?.anuncio || "",
    es_pareja: lead?.es_pareja || false,
    estado: lead?.estado || "nuevo",
    agendo_consulta: lead?.agendo_consulta ?? null,
    fecha_consulta: lead?.fecha_consulta || "",
    fecha_cierre: lead?.fecha_cierre || "",
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
  const canSave = f.nombre.trim().length > 0;
  const anunciosActivos = (anuncios || []).filter((a) => a.activo);

  function guardar() {
    onSave({
      ...(lead?.id ? { id: lead.id } : {}),
      nombre: f.nombre.trim(), telefono: f.telefono.trim(), sede: f.sede, fuente: f.fuente,
      fuente_otro: f.fuente === "otro" ? f.fuente_otro.trim() : "",
      es_pauta: f.es_pauta, anuncio: f.anuncio ? Number(f.anuncio) : null, es_pareja: f.es_pareja,
      estado: f.estado, agendo_consulta: f.agendo_consulta,
      fecha_consulta: f.agendo_consulta === false ? null : (f.fecha_consulta || null), fecha_cierre: f.fecha_cierre || null,
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
          <div style={{ flex: 1 }}><div className="ca-label">Origen</div><select className="ca-input" value={f.fuente} onChange={set("fuente")}>{FUENTES.map((x) => <option key={x.v} value={x.v}>{x.l}</option>)}</select></div>
          <div style={{ flex: 1 }}><div className="ca-label">Etapa</div><select className="ca-input" value={f.estado} onChange={set("estado")}>{LEAD_ESTADOS.map((s) => <option key={s.v} value={s.v}>{s.l}</option>)}</select></div>
        </div>
        {f.fuente === "otro" && (
          <div style={{ marginBottom: 12 }}>
            <div className="ca-label">¿Cuál otro origen?</div>
            <input className="ca-input" value={f.fuente_otro} onChange={set("fuente_otro")} placeholder="Especifica de dónde vino el lead" />
          </div>
        )}
        <div style={{ display: "flex", gap: 16, marginBottom: 12, flexWrap: "wrap" }}>
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13.5, color: "var(--ink-soft)", cursor: "pointer" }}>
            <input type="checkbox" checked={f.es_pauta} onChange={setChk("es_pauta")} /> Vino de pauta (pagado)
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13.5, color: "var(--ink-soft)", cursor: "pointer" }}>
            <input type="checkbox" checked={f.es_pareja} onChange={setChk("es_pareja")} /> Consulta de pareja
          </label>
        </div>
        {f.es_pauta && (
          <div style={{ marginBottom: 12 }}>
            <div className="ca-label">Anuncio que lo atrajo</div>
            <select className="ca-input" value={f.anuncio} onChange={set("anuncio")}>
              <option value="">— (sin especificar)</option>
              {anunciosActivos.map((a) => <option key={a.id} value={a.id}>{a.nombre}</option>)}
            </select>
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
            <div style={{ flex: 1 }}><div className="ca-label">Fecha de la consulta</div><input className="ca-input" type="date" value={f.fecha_consulta || ""} onChange={set("fecha_consulta")} /></div>
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
        <div style={{ fontSize: 13, color: "var(--muted)", marginBottom: 16 }}>Para {paciente.nombre} · se cobra ahora y las sesiones se descuentan al atender.</div>

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
  const [comprobante, setComprobante] = useState("");
  const [compNumero, setCompNumero] = useState("");
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

        {estado === "pagado" && (
          <div style={{ marginBottom: 13 }}>
            <div className="ca-label">Medio de pago</div>
            <select className="ca-input" value={medio} onChange={(e) => setMedio(e.target.value)}>
              {MEDIOS_PAGO.map((m) => <option key={m.v} value={m.v}>{m.l}</option>)}
            </select>
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
  const [verPacientes, setVerPacientes] = useState(null);

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
        <div style={{ display: "flex", gap: 9, alignItems: "center" }}>
          <ExportBtns nombre="profesionales" titulo="Profesionales" disabled={!filtradas || filtradas.length === 0}
            headers={["Nombre", "Titulo", "Colegiatura", "Sede", "Modalidad", "Enfoque", "Atiende", "Activo"]}
            filas={(filtradas || []).map((p) => [p.nombre, p.titulo, p.colegiatura, p.sede_label, p.modalidad_label, p.enfoque, p.poblaciones, p.activo ? "Sí" : "No"])} />
          {esAdmin && <button className="ca-btn" onClick={() => setEditar({ new: true })}><Plus size={16} strokeWidth={2.2} /> Nuevo profesional</button>}
        </div>
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
              <div style={{ display: "flex", gap: 8, marginTop: 12, alignItems: "center", flexWrap: "wrap" }}>
                <button className="ca-mini" onClick={() => setVerPacientes(p)}>
                  <Users size={13} strokeWidth={2} /> {p.n_pacientes} paciente{p.n_pacientes === 1 ? "" : "s"}
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
          <div style={{ width: 90 }}><div className="ca-label">Horas/sem</div><input className="ca-input" value={f.horas_disponibles} onChange={(e) => setF((prev) => ({ ...prev, horas_disponibles: e.target.value.replace(/[^\d]/g, "") }))} inputMode="numeric" /></div>
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
            onClick={() => onSave({ ...(prof?.id ? { id: prof.id } : {}), ...f, nombre: f.nombre.trim(), horas_disponibles: Number(f.horas_disponibles) || 0 }, foto)}>Guardar</button>
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
  const [sel, setSel] = useState({ anio: "", mes: "", semana: "" });

  async function cargar(params) {
    try {
      const d = await api.ocupacion(params || {});
      setData(d);
      setSel({ anio: d.anio, mes: d.mes, semana: d.semana });
    } catch (e) { showToast("Error: " + e.message); }
  }
  useEffect(() => { cargar(); }, []);
  if (!data) return <div className="ca-empty">Cargando…</div>;

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
          headers={["Sede", "Psicologo", "Horas", "Sesiones", "% Ocupacion", "Consultas", "1er proceso", "Recompra"]}
          filas={data.sedes.flatMap((g) => g.psicologos.map((p) => [g.sede_label, p.nombre, p.horas_disponibles, p.sesiones, `${p.ocupacion}%`, p.consultas, p.primer_proceso, p.recompra]))} />
      </div>

      <div className="ca-fchips" style={{ marginTop: 18, alignItems: "flex-end" }}>
        <div style={{ width: 78 }}><div className="ca-label">Semana</div><input className="ca-input" value={sel.semana} onChange={(e) => setSel((s) => ({ ...s, semana: e.target.value.replace(/[^\d]/g, "") }))} inputMode="numeric" /></div>
        <div style={{ width: 130 }}><div className="ca-label">Mes</div><select className="ca-input" value={sel.mes} onChange={(e) => setSel((s) => ({ ...s, mes: Number(e.target.value) }))}>{MESES_FULL.slice(1).map((m, i) => <option key={i + 1} value={i + 1}>{m}</option>)}</select></div>
        <div style={{ width: 88 }}><div className="ca-label">Año</div><input className="ca-input" value={sel.anio} onChange={(e) => setSel((s) => ({ ...s, anio: e.target.value.replace(/[^\d]/g, "") }))} inputMode="numeric" /></div>
        <button className="ca-btn" onClick={() => cargar(sel)}>Ver</button>
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
                  <th style={{ textAlign: "right" }}>Horas</th>
                  <th style={{ textAlign: "right" }}>Sesiones</th>
                  <th style={{ textAlign: "right" }}>% Ocup.</th>
                  <th style={{ textAlign: "right" }}>Consultas</th>
                  <th style={{ textAlign: "right" }}>1er proc.</th>
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
                      <td style={{ textAlign: "right" }}><span style={{ color: pc.fg, fontWeight: 600 }}>{p.ocupacion}%</span></td>
                      <td style={{ textAlign: "right" }}>{p.consultas}</td>
                      <td style={{ textAlign: "right" }}>{p.primer_proceso}</td>
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
  const [sede, setSede] = useState(paciente?.sede || "");
  const [profId, setProfId] = useState(paciente?.profesional || "");
  const [nSesion, setNSesion] = useState(paciente?.n_sesion ?? 0);
  const [proceso, setProceso] = useState(paciente?.proceso || "");
  const [profs, setProfs] = useState([]);
  useEffect(() => { api.profesionales().then(setProfs).catch(() => {}); }, []);
  const canSave = nombre.trim().length > 0;
  const esNuevo = !paciente;
  // Psicólogos activos de la sede elegida (más el ya asignado, aunque esté inactivo).
  const profsVisibles = profs.filter((pr) => (pr.activo || String(pr.id) === String(profId)) && (!sede || pr.sede === sede));

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
              {profsVisibles.map((pr) => <option key={pr.id} value={pr.id}>{pr.nombre} ({pr.sede_label})</option>)}
            </select>
          </div>
        </div>
        {/* N° de sesión y proceso solo al EDITAR; en un paciente nuevo no se piden
            (arrancan en 0 y se actualizan solos con las sesiones). */}
        {!esNuevo && (
          <div style={{ display: "flex", gap: 11, marginBottom: 16 }}>
            <div style={{ width: 120 }}>
              <div className="ca-label">N° de sesión</div>
              <input className="ca-input" value={nSesion} onChange={(e) => setNSesion(e.target.value.replace(/[^\d]/g, ""))} inputMode="numeric" />
            </div>
            <div style={{ flex: 1 }}>
              <div className="ca-label">Proceso</div>
              <select className="ca-input" value={proceso} onChange={(e) => setProceso(e.target.value)}>
                {PROCESOS.map((p) => <option key={p || "none"} value={p}>{p ? p.charAt(0).toUpperCase() + p.slice(1) : "—"}</option>)}
              </select>
            </div>
          </div>
        )}

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
            onClick={() => onSave({ ...(paciente?.id ? { id: paciente.id } : {}), nombre: nombre.trim(), fecha_nacimiento: fechaNac || null, tel: tel.trim(), especialidad: esp, sede, profesional: profId ? Number(profId) : null, n_sesion: Number(nSesion) || 0, proceso, tipo_documento: tipoDoc, numero_documento: numDoc.trim(), direccion: direccion.trim(), genero, alergias: alergias.trim(), antecedentes: antecedentes.trim(), medicacion_habitual: medicacion.trim() })}>
            Guardar
          </button>
        </div>
      </div>
    </div>
  );
}

// Página PÚBLICA del consentimiento (sin login). El paciente la abre por su enlace,
// lee el documento y lo acepta con su nombre (sello de fecha/hora e IP en el backend).
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
          {doc.firmante_nombre ? <div style={{ fontSize: 13, marginTop: 4 }}>Firmado por {doc.firmante_nombre}.</div> : null}
          <div style={{ fontSize: 13, marginTop: 6 }}>Ya puedes cerrar esta página. ¡Gracias! 🌿</div>
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
