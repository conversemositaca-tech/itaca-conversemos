// Centro de exportación del panel de Gerencia.
//
// Un solo "modelo de reporte" (modeloReporte) se arma a partir de la MISMA
// respuesta de /api/gerencia/resumen/ que pinta la pantalla, y los cuatro
// formatos (Excel, PDF ejecutivo, Word, PowerPoint) salen de ese modelo. Así
// los archivos dicen exactamente lo que dice la pantalla y no se desfasan
// entre sí. Las librerías pesadas se cargan solo al exportar (import dinámico).
//
// Identidad visual: sigue el Manual de Identidad Corporativa de Itaca
// Conversemos (Agencia Deb) — paleta de 4 colores + blanco en gama
// monocromática del celeste, tipografía Montserrat, y el logotipo oficial
// (versión principal y horizontal, en frontend/public). No se agregan colores
// fuera de la paleta: los "tintes" son mezclas del celeste con blanco.
//
// Este archivo no usa JSX ni React a propósito: se puede ejecutar en Node para
// probar los archivos generados sin levantar el navegador.

export const MARCA = {
  celeste: "#00B8D8",       // CELESTE 1 · primario (títulos, barras, acentos)
  celesteClaro: "#D7F4FA",  // CELESTE 2 · cabeceras de tabla, tarjetas
  gris: "#6E6E6E",          // GRIS · texto secundario (el wordmark "ITACA" es de este gris)
  negro: "#343434",         // NEGRO · texto principal
  blanco: "#FFFFFF",
  // Tintes del celeste (misma gama; no son colores nuevos de paleta):
  celesteMedio: "#66D4E8",  // segunda serie en gráficos
  celesteFondo: "#F1FBFD",  // fondo muy suave de tarjetas
  linea: "#DCEFF4",         // líneas y pistas de gráfico
  fuente: "Montserrat",
  fuenteFallback: '"Century Gothic", "Segoe UI", Arial, sans-serif',
  tagline: "Te cambia la vida",
  logo: { v: { archivo: "itaca-logo-v.png", w: 539, h: 417 }, h: { archivo: "itaca-logo-h.png", w: 620, h: 224 } },
};
const hex = (c) => c.replace("#", "");
const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "set", "oct", "nov", "dic"];

export const soles = (n) => "S/ " + Math.round(Number(n || 0)).toLocaleString("es-PE");
const fDia = (iso) => { const [, m, d] = iso.split("-").map(Number); return `${d} ${MESES[m - 1]}`; };
// Fecha real para Excel (ordenable y filtrable). En UTC para que exceljs no la corra un día.
const fechaExcel = (iso) => { const [y, m, d] = iso.split("-").map(Number); return new Date(Date.UTC(y, m - 1, d)); };
const fRango = (a, b) => {
  const [y1, m1, d1] = a.split("-").map(Number);
  const [y2, m2, d2] = b.split("-").map(Number);
  if (a === b) return `${d1} ${MESES[m1 - 1]} ${y1}`;
  return `${d1} ${MESES[m1 - 1]} – ${d2} ${MESES[m2 - 1]} ${y2}`;
};
const ahora = () => new Date().toLocaleString("es-PE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
const deltaTxt = (cur, prev) => {
  if (prev == null || cur == null) return "";
  if (!prev && !cur) return "sin cambios";
  if (!prev) return "▲ nuevo";
  const d = Math.round(((cur - prev) / prev) * 100);
  if (d === 0) return "= igual al anterior";
  return `${d > 0 ? "▲" : "▼"} ${Math.abs(d)}% vs anterior`;
};
const fmtValor = (v, fmt) => (fmt === "soles" ? soles(v) : Number(v || 0).toLocaleString("es-PE"));
const pctDe = (v, total) => (total ? Math.round((v / total) * 100) : 0);

// ---------------------------------------------------------------------------
// Logotipo oficial (frontend/public). En el navegador se trae por fetch una
// sola vez; en Node (pruebas) se pasa por opts.logos. Cada logo: {b64, bytes, w, h}.
// ---------------------------------------------------------------------------
let _logos = null;
export async function cargarLogos(opts = {}) {
  if (opts.logos) return opts.logos;
  if (_logos) return _logos;
  if (typeof fetch === "undefined" || typeof document === "undefined") return null;
  const base = (typeof import.meta !== "undefined" && import.meta.env && import.meta.env.BASE_URL) || "/";
  const leer = async (k) => {
    const meta = MARCA.logo[k];
    try {
      const r = await fetch(base + meta.archivo);
      if (!r.ok) return null;
      const bytes = new Uint8Array(await r.arrayBuffer());
      let s = "";
      for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
      return { b64: btoa(s), bytes, w: meta.w, h: meta.h };
    } catch { return null; }
  };
  _logos = { v: await leer("v"), h: await leer("h") };
  return _logos;
}

// ---------------------------------------------------------------------------
// Modelo de reporte
// ---------------------------------------------------------------------------
export function modeloReporte(data, opts = {}) {
  const op = data.operacion || {}, cap = data.captacion || {}, pac = data.pacientes || {};
  const fin = data.finanzas || {}, dg = data.diagnostico, ret = data.retencion;
  const ant = data.anterior || {}, demo = data.demografia;
  const sedeLbl = data.sede === "lima" ? "Lima" : data.sede === "piura" ? "Piura" : "Todas las sedes";
  const clinica = opts.clinica || "Itaca Conversemos";
  const pctS = (n) => `${Math.round(n ?? 0)}%`;
  const kpi = (label, valor, extra = {}) => ({ label, valor, ...extra });
  const serieDia = (id, titulo, arr, key, color, fmt) =>
    arr && arr.length > 1
      ? [{ id, titulo, tipo: "columnas", datos: arr.map((x) => ({ label: fDia(x.fecha), valor: x[key] })), color, fmt }]
      : [];

  const secciones = [];
  secciones.push({
    id: "operacion", titulo: "Operación",
    kpis: [
      kpi("Sesiones en el período", op.citas ?? 0, { num: op.citas ?? 0, sub: deltaTxt(op.citas, ant.citas) }),
      kpi("Atendidas", op.atendidas ?? 0, { num: op.atendidas ?? 0 }),
      kpi("% Asistencia", pctS(op.asistencia_pct), { num: (op.asistencia_pct ?? 0) / 100, fmt: "pct", sub: `${op.cancelacion_pct ?? 0}% canceladas` }),
      kpi("Recordatorios enviados", op.recordatorios ?? 0, { num: op.recordatorios ?? 0 }),
    ],
    series: serieDia("sesiones_dia", "Sesiones por día", op.por_dia, "citas", MARCA.celeste),
    tablas: [], notas: [],
  });
  secciones.push({
    id: "captacion", titulo: "Captación",
    kpis: [
      kpi("Leads recibidos", cap.recibidos ?? 0, { num: cap.recibidos ?? 0, sub: `${cap.pauta_pct ?? 0}% de pauta` }),
      kpi("Cierres (iniciaron)", cap.cierres ?? 0, { num: cap.cierres ?? 0 }),
      kpi("Tasa de cierre", pctS(cap.tasa_cierre), { num: (cap.tasa_cierre ?? 0) / 100, fmt: "pct" }),
      kpi("Mejor fuente", cap.top_fuente || "—"),
    ],
    series: serieDia("leads_dia", "Leads por día", cap.por_dia, "leads", MARCA.celesteMedio),
    tablas: [], notas: [`Mejor campaña del período: ${cap.top_campania || "—"}.`],
  });
  const pacSec = {
    id: "pacientes", titulo: "Pacientes",
    kpis: [
      kpi("Pacientes totales", pac.total ?? 0, { num: pac.total ?? 0 }),
      kpi("Nuevos en el período", pac.nuevos ?? 0, { num: pac.nuevos ?? 0 }),
      kpi("Sin próxima sesión", pac.sin_proxima ?? 0, { num: pac.sin_proxima ?? 0, sub: "para reactivar" }),
    ],
    series: [], tablas: [], notas: [],
  };
  if (demo) {
    pacSec.series.push(
      { id: "genero", titulo: "Pacientes por género", tipo: "barras", datos: (demo.genero || []).filter((x) => x.valor > 0), color: MARCA.celeste },
      { id: "edad", titulo: "Pacientes por edad", tipo: "barras", datos: demo.edad || [], color: MARCA.celesteMedio },
    );
  }
  secciones.push(pacSec);
  if (ret && ret.con_sesiones > 0) {
    secciones.push({
      id: "retencion", titulo: "Retención (días desde la última sesión)",
      kpis: [
        kpi("En ritmo (<8 días)", ret.verde, { num: ret.verde }),
        kpi("Alerta (8–15 días)", ret.amarillo, { num: ret.amarillo }),
        kpi("Abandono (>15 días)", ret.rojo, { num: ret.rojo, sub: "para llamar / reactivar" }),
        kpi("% en abandono", pctS(ret.rojo_pct), { num: (ret.rojo_pct ?? 0) / 100, fmt: "pct" }),
      ],
      series: [], tablas: [],
      notas: [`Sobre ${ret.con_sesiones} pacientes con al menos una sesión registrada. Regla: verde <8 días · amarillo 8–15 · rojo >15.`],
    });
  }
  const dinero = {
    id: "dinero", titulo: `Dinero${data.sede ? " · " + sedeLbl : ""}`,
    kpis: [kpi("Ingresos (cobrado)", soles(fin.cobrado), { num: fin.cobrado ?? 0, fmt: "soles", sub: deltaTxt(fin.cobrado, ant.cobrado) })],
    series: serieDia("cobros_dia", "Cobros por día", fin.por_dia, "monto", MARCA.celeste, "soles"),
    tablas: [], notas: [],
  };
  if (fin.egresos != null) dinero.kpis.push(kpi("Egresos (gastos)", soles(fin.egresos), { num: fin.egresos, fmt: "soles" }));
  if (fin.utilidad != null) dinero.kpis.push(kpi("Utilidad (neto)", soles(fin.utilidad), { num: fin.utilidad, fmt: "soles" }));
  dinero.kpis.push(kpi("Pendiente por cobrar", soles(fin.pendiente), { num: fin.pendiente ?? 0, fmt: "soles" }));
  if (data.sede) dinero.notas.push("Egresos y utilidad solo en la vista Total (no se registran por sede).");
  secciones.push(dinero);
  if (dg) {
    const e = dg.embudo, c = dg.continuidad, dc = dg.decision, mp = dg.medio_pago;
    secciones.push({
      id: "diagnostico", titulo: "Diagnóstico",
      kpis: [
        kpi("Leads resueltos", pctS(e.resueltos_pct), { num: (e.resueltos_pct ?? 0) / 100, fmt: "pct", sub: `${e.resueltos} de ${e.total}` }),
        kpi("Ganados (iniciaron)", e.ganados, { num: e.ganados }),
        kpi("Marcados perdidos", e.perdidos, { num: e.perdidos, sub: e.perdidos === 0 && e.total > 0 ? "nadie cierra los que no compran" : "" }),
        kpi("En curso (sin cerrar)", e.en_curso, { num: e.en_curso }),
        kpi("Sesiones con motivo de cierre", pctS(dc.pct), { num: (dc.pct ?? 0) / 100, fmt: "pct", sub: `${dc.con_motivo} de ${dc.citas_terminadas} terminadas` }),
      ],
      series: [
        { id: "continuidad", titulo: "Continuidad · sesiones por paciente", tipo: "barras", datos: c.por_sesiones || [], color: MARCA.celeste },
        { id: "medio_pago", titulo: "Ingresos por medio de pago", tipo: "barras", datos: mp.por_medio || [], color: MARCA.celesteMedio, fmt: "soles" },
      ],
      tablas: [],
      notas: [
        `Sobre ${c.con_historia} pacientes con historia clínica: ${c.abandono_1_2_pct}% no pasa de la sesión 2.`,
        mp.total > 0 ? `${mp.sin_medio_pct}% de lo cobrado no tiene medio de pago registrado.` : "Sin cobros en el período.",
      ],
    });
  }
  const prod = data.productividad || [];
  secciones.push({
    id: "productividad", titulo: "Productividad por psicólogo",
    kpis: [], series: [],
    tablas: [{
      id: "productividad", titulo: "",
      columnas: ["Psicólogo", "Sesiones", "Atenciones", "Leads", "Cierres"],
      numericas: [1, 2, 3, 4],
      filas: prod.map((m) => [m.medico, m.citas, m.atenciones, m.leads, m.cierres]),
    }],
    notas: prod.length ? [] : ["Sin actividad en el período."],
  });

  return {
    titulo: `Gerencia · ${data.periodo.label}`,
    subtitulo: `${clinica} · ${sedeLbl} · ${fRango(data.periodo.desde, data.periodo.hasta)}`,
    clinica, sedeLbl, periodo: data.periodo, sede: data.sede, generadoEn: ahora(),
    secciones, raw: data,
  };
}

// ---------------------------------------------------------------------------
// Descarga (solo navegador)
// ---------------------------------------------------------------------------
function descargarBlob(nombre, blob) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = nombre;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}
const nombreArchivo = (modelo, base, ext) => {
  const sede = modelo.sede ? "_" + modelo.sede : "";
  return `${base || "gerencia"}_${modelo.periodo.clave}${sede}_${modelo.periodo.hasta}.${ext}`;
};

// ---------------------------------------------------------------------------
// CSV (datos crudos)
// ---------------------------------------------------------------------------
export function construirCSV(modelo) {
  const filas = [["Sección", "Indicador", "Valor"]];
  modelo.secciones.forEach((s) => s.kpis.forEach((k) => filas.push([s.titulo, k.label, k.num != null ? k.num : k.valor])));
  const esc = (c) => `"${String(c ?? "").replace(/"/g, '""')}"`;
  return "﻿" + filas.map((r) => r.map(esc).join(",")).join("\r\n");
}
export function exportarCSV(modelo, base) {
  descargarBlob(nombreArchivo(modelo, base, "csv"), new Blob([construirCSV(modelo)], { type: "text/csv;charset=utf-8;" }));
}

// ---------------------------------------------------------------------------
// Excel (.xlsx) real: una hoja por sección, con fórmulas para los porcentajes
// y totales (si alguien corrige un número, el % se recalcula solo).
// ---------------------------------------------------------------------------
const FMT = { pct: "0%", soles: '"S/ "#,##0', int: "#,##0" };

export async function construirExcel(modelo, opts = {}) {
  const m = await import("exceljs");
  const ExcelJS = m.default || m;
  const logos = await cargarLogos(opts);
  const wb = new ExcelJS.Workbook();
  wb.creator = modelo.clinica;
  wb.created = new Date();
  wb.calcProperties.fullCalcOnLoad = true;
  const d = modelo.raw;
  const op = d.operacion || {}, cap = d.captacion || {}, pac = d.pacientes || {}, fin = d.finanzas || {};
  const dg = d.diagnostico, ret = d.retencion, demo = d.demografia;

  const argb = (h) => "FF" + hex(h).toUpperCase();
  const F = MARCA.fuente;
  function hoja(nombre, titulo) {
    const ws = wb.addWorksheet(nombre, { views: [{ showGridLines: false, state: "frozen", ySplit: 4 }] });
    ws.properties.tabColor = { argb: argb(nombre === "Resumen" ? MARCA.celeste : MARCA.celesteClaro) };
    // Pie de impresión como el del manual: texto gris a la izquierda, número en celeste negrita a la derecha.
    ws.headerFooter = { oddFooter: `&L&"${F}"&8&K${hex(MARCA.gris)}${modelo.clinica} · ${modelo.titulo}&R&"${F},Bold"&10&K${hex(MARCA.celeste)}&P` };
    ws.columns = [{ width: 36 }, { width: 16 }, { width: 14 }, { width: 14 }, { width: 14 }, { width: 14 }];
    ws.getCell("A1").value = titulo;
    ws.getCell("A1").font = { name: F, bold: true, size: 15, color: { argb: argb(MARCA.celeste) } };
    ws.getCell("A2").value = `${modelo.subtitulo} · generado ${modelo.generadoEn}`;
    ws.getCell("A2").font = { name: F, size: 9, color: { argb: argb(MARCA.gris) } };
    ws.getRow(1).height = 24;
    return ws;
  }
  function cabecera(ws, r, cols) {
    cols.forEach((t, i) => {
      const c = ws.getRow(r).getCell(i + 1);
      // Cabecera como en los formatos impresos de la clínica: celeste sólido, texto blanco en mayúsculas.
      c.value = String(t).toUpperCase();
      c.font = { name: F, bold: true, size: 9.5, color: { argb: argb(MARCA.blanco) } };
      c.fill = { type: "pattern", pattern: "solid", fgColor: { argb: argb(MARCA.celeste) } };
      c.alignment = { horizontal: i === 0 ? "left" : "right", vertical: "middle" };
    });
    ws.getRow(r).height = 21;
    return r + 1;
  }
  // Escribe una fila. Cada celda: número, texto, o {f:"fórmula", v:resultado, fmt}.
  function fila(ws, r, celdas, o = {}) {
    celdas.forEach((v, i) => {
      const c = ws.getRow(r).getCell(i + 1);
      if (v && typeof v === "object" && "f" in v) {
        c.value = { formula: v.f, result: v.v };
        if (v.fmt) c.numFmt = FMT[v.fmt] || v.fmt;
      } else {
        c.value = v;
        if (typeof v === "number") c.numFmt = (o.fmts && o.fmts[i] && FMT[o.fmts[i]]) || FMT.int;
        if (v instanceof Date) c.numFmt = "dd/mm/yyyy";
      }
      c.font = { name: F, size: 10, bold: !!o.bold, color: { argb: argb(i === 0 && !o.bold ? MARCA.gris : MARCA.negro) } };
      c.alignment = { horizontal: i > 0 && !(v instanceof Date) ? "right" : "left" };
      c.border = { bottom: { style: "hair", color: { argb: argb(MARCA.linea) } } };
      if (o.linea) c.border = { top: { style: "thin", color: { argb: argb(MARCA.celeste) } } };
    });
    return r + 1;
  }
  const pctF = (num, den, v) => ({ f: `IF(${den}=0,0,${num}/${den})`, v: v ?? 0, fmt: "pct" });
  const sumF = (col, a, b, v) => ({ f: `SUM(${col}${a}:${col}${b})`, v: v ?? 0 });

  // --- Resumen ---
  {
    const ws = hoja("Resumen", modelo.titulo);
    ws.columns = [{ width: 22 }, { width: 58 }, { width: 14 }, { width: 22 }];
    if (logos && logos.h) {
      const id = wb.addImage({ base64: logos.h.b64, extension: "png" });
      ws.addImage(id, { tl: { col: 3, row: 0 }, ext: { width: 120, height: 43 } });
    }
    let r = cabecera(ws, 4, ["Sección", "Indicador", "Valor"]);
    modelo.secciones.forEach((s) => s.kpis.forEach((k) => {
      const c1 = ws.getRow(r).getCell(1), c2 = ws.getRow(r).getCell(2), c3 = ws.getRow(r).getCell(3);
      c1.value = s.titulo.replace(/\s*\(.*\)$/, ""); c1.font = { name: F, size: 10, color: { argb: argb(MARCA.gris) } };
      c2.value = k.label + (k.sub ? ` (${k.sub})` : ""); c2.font = { name: F, size: 10, color: { argb: argb(MARCA.negro) } };
      c3.value = k.num != null ? k.num : k.valor;
      if (k.num != null) c3.numFmt = FMT[k.fmt] || FMT.int;
      c3.font = { name: F, size: 10, bold: true, color: { argb: argb(MARCA.negro) } };
      c3.alignment = { horizontal: "right" };
      [c1, c2, c3].forEach((c) => { c.border = { bottom: { style: "hair", color: { argb: argb(MARCA.linea) } } }; });
      r += 1;
    }));
    // El logo (columna D) entra en la impresión y la hoja cabe a lo ancho en una página.
    ws.pageSetup = { printArea: `A1:D${r}`, orientation: "portrait", fitToPage: true, fitToWidth: 1, fitToHeight: 0 };
  }
  // --- Operación ---
  {
    const ws = hoja("Operación", "Operación");
    let r = cabecera(ws, 4, ["Concepto", "Cantidad"]);
    r = fila(ws, r, ["Sesiones en el período", op.citas ?? 0]);
    const rA = r; r = fila(ws, r, ["Atendidas", op.atendidas ?? 0]);
    const rC = r; r = fila(ws, r, ["Canceladas", op.canceladas ?? 0]);
    r = fila(ws, r, ["Confirmadas", op.confirmadas ?? 0]);
    r = fila(ws, r, ["Por confirmar", op.por_confirmar ?? 0]);
    r = fila(ws, r, ["% Asistencia", pctF(`B${rA}`, `(B${rA}+B${rC})`, (op.asistencia_pct ?? 0) / 100)]);
    r = fila(ws, r, ["% Cancelación", pctF(`B${rC}`, `(B${rA}+B${rC})`, (op.cancelacion_pct ?? 0) / 100)]);
    r = fila(ws, r, ["Recordatorios enviados", op.recordatorios ?? 0]);
    if (op.por_dia && op.por_dia.length) {
      r += 1; r = cabecera(ws, r, ["Sesiones por día", "Sesiones"]);
      const ini = r;
      op.por_dia.forEach((x) => { r = fila(ws, r, [fechaExcel(x.fecha), x.citas]); });
      r = fila(ws, r, ["Total", sumF("B", ini, r - 1, op.citas)], { bold: true, linea: true });
    }
  }
  // --- Captación ---
  {
    const ws = hoja("Captación", "Captación");
    let r = cabecera(ws, 4, ["Concepto", "Cantidad"]);
    const rL = r; r = fila(ws, r, ["Leads recibidos", cap.recibidos ?? 0]);
    const rP = r; r = fila(ws, r, ["De pauta", cap.pauta ?? 0]);
    const rG = r; r = fila(ws, r, ["Cierres (iniciaron)", cap.cierres ?? 0]);
    r = fila(ws, r, ["% de pauta", pctF(`B${rP}`, `B${rL}`, (cap.pauta_pct ?? 0) / 100)]);
    r = fila(ws, r, ["Tasa de cierre", pctF(`B${rG}`, `B${rL}`, (cap.tasa_cierre ?? 0) / 100)]);
    r = fila(ws, r, ["Mejor fuente", cap.top_fuente || "—"]);
    r = fila(ws, r, ["Mejor campaña", cap.top_campania || "—"]);
    if (cap.por_dia && cap.por_dia.length) {
      r += 1; r = cabecera(ws, r, ["Leads por día", "Leads"]);
      const ini = r;
      cap.por_dia.forEach((x) => { r = fila(ws, r, [fechaExcel(x.fecha), x.leads]); });
      r = fila(ws, r, ["Total", sumF("B", ini, r - 1, cap.recibidos)], { bold: true, linea: true });
    }
    if (dg && dg.embudo.por_estado && dg.embudo.por_estado.length) {
      r += 1; r = cabecera(ws, r, ["Embudo por estado", "Leads", "%"]);
      const ini = r; const fin_ = ini + dg.embudo.por_estado.length - 1;
      dg.embudo.por_estado.forEach((x) => {
        r = fila(ws, r, [x.label, x.valor, pctF(`B${r}`, `SUM($B$${ini}:$B$${fin_})`, pctDe(x.valor, dg.embudo.total) / 100)]);
      });
      r = fila(ws, r, ["Total", sumF("B", ini, fin_, dg.embudo.total)], { bold: true, linea: true });
    }
  }
  // --- Pacientes ---
  {
    const ws = hoja("Pacientes", "Pacientes");
    let r = cabecera(ws, 4, ["Concepto", "Cantidad"]);
    const rT = r; r = fila(ws, r, ["Pacientes totales", pac.total ?? 0]);
    r = fila(ws, r, ["Nuevos en el período", pac.nuevos ?? 0]);
    const rS = r; r = fila(ws, r, ["Sin próxima sesión", pac.sin_proxima ?? 0]);
    r = fila(ws, r, ["% sin próxima sesión", pctF(`B${rS}`, `B${rT}`, pctDe(pac.sin_proxima ?? 0, pac.total ?? 0) / 100)]);
    const bloque = (titulo, datos) => {
      if (!datos || !datos.length) return;
      r += 1; r = cabecera(ws, r, [titulo, "Pacientes", "%"]);
      const ini = r, fin_ = ini + datos.length - 1;
      const total = datos.reduce((s, x) => s + (x.valor || 0), 0);
      datos.forEach((x) => { r = fila(ws, r, [x.label, x.valor, pctF(`B${r}`, `SUM($B$${ini}:$B$${fin_})`, pctDe(x.valor, total) / 100)]); });
      r = fila(ws, r, ["Total", sumF("B", ini, fin_, total)], { bold: true, linea: true });
    };
    if (demo) { bloque("Por género", demo.genero); bloque("Por edad", demo.edad); }
    if (ret && ret.con_sesiones > 0) {
      r += 1; r = cabecera(ws, r, ["Retención (días desde la última sesión)", "Pacientes", "%"]);
      const ini = r;
      r = fila(ws, r, ["En ritmo (<8 días)", ret.verde, pctF(`B${r}`, `SUM($B$${ini}:$B$${ini + 2})`, pctDe(ret.verde, ret.con_sesiones) / 100)]);
      r = fila(ws, r, ["Alerta (8–15 días)", ret.amarillo, pctF(`B${r}`, `SUM($B$${ini}:$B$${ini + 2})`, pctDe(ret.amarillo, ret.con_sesiones) / 100)]);
      r = fila(ws, r, ["Abandono (>15 días)", ret.rojo, pctF(`B${r}`, `SUM($B$${ini}:$B$${ini + 2})`, (ret.rojo_pct ?? 0) / 100)]);
      r = fila(ws, r, ["Total con sesiones", sumF("B", ini, ini + 2, ret.con_sesiones)], { bold: true, linea: true });
    }
  }
  // --- Dinero ---
  {
    const ws = hoja("Dinero", modelo.secciones.find((s) => s.id === "dinero").titulo);
    let r = cabecera(ws, 4, ["Concepto", "Monto"]);
    const rI = r; r = fila(ws, r, ["Ingresos (cobrado)", fin.cobrado ?? 0], { fmts: [null, "soles"] });
    if (fin.egresos != null) {
      const rE = r; r = fila(ws, r, ["Egresos (gastos)", fin.egresos], { fmts: [null, "soles"] });
      r = fila(ws, r, ["Utilidad (neto)", { f: `B${rI}-B${rE}`, v: fin.utilidad ?? 0, fmt: "soles" }], { bold: true });
    } else {
      r = fila(ws, r, ["Egresos (gastos)", "Solo en la vista Total"]);
      r = fila(ws, r, ["Utilidad (neto)", "Solo en la vista Total"]);
    }
    r = fila(ws, r, ["Pendiente por cobrar", fin.pendiente ?? 0], { fmts: [null, "soles"] });
    if (fin.por_dia && fin.por_dia.length) {
      r += 1; r = cabecera(ws, r, ["Cobros por día", "Monto"]);
      const ini = r;
      fin.por_dia.forEach((x) => { r = fila(ws, r, [fechaExcel(x.fecha), x.monto], { fmts: [null, "soles"] }); });
      r = fila(ws, r, ["Total", { ...sumF("B", ini, r - 1, fin.cobrado), fmt: "soles" }], { bold: true, linea: true });
    }
  }
  // --- Diagnóstico ---
  if (dg) {
    const ws = hoja("Diagnóstico", "Diagnóstico");
    const e = dg.embudo, c = dg.continuidad, dc = dg.decision, mp = dg.medio_pago;
    let r = cabecera(ws, 4, ["Leads del período", "Cantidad"]);
    const rT = r; r = fila(ws, r, ["Leads recibidos", e.total]);
    const rG = r; r = fila(ws, r, ["Ganados (iniciaron)", e.ganados]);
    const rP = r; r = fila(ws, r, ["Marcados perdidos", e.perdidos]);
    const rR = r; r = fila(ws, r, ["Resueltos (ganado o perdido)", { f: `B${rG}+B${rP}`, v: e.resueltos }]);
    r = fila(ws, r, ["En curso (sin cerrar)", { f: `B${rT}-B${rR}`, v: e.en_curso }]);
    r = fila(ws, r, ["% resueltos", pctF(`B${rR}`, `B${rT}`, (e.resueltos_pct ?? 0) / 100)]);
    r += 1; r = cabecera(ws, r, ["Continuidad · sesiones por paciente", "Pacientes", "%"]);
    {
      const ini = r, datos = c.por_sesiones || [], fin_ = ini + datos.length - 1;
      datos.forEach((x) => { r = fila(ws, r, [`${x.label} ${x.label === "1" ? "sesión" : "sesiones"}`, x.valor, pctF(`B${r}`, `SUM($B$${ini}:$B$${fin_})`, pctDe(x.valor, c.con_historia) / 100)]); });
      r = fila(ws, r, ["Total con historia", sumF("B", ini, fin_, c.con_historia)], { bold: true, linea: true });
      r = fila(ws, r, ["% que no pasa de la sesión 2", pctF(`(B${ini}+B${ini + 1})`, `B${r - 1}`, (c.abandono_1_2_pct ?? 0) / 100)]);
    }
    r += 1; r = cabecera(ws, r, ["Motivo de cierre registrado", "Sesiones"]);
    const rTe = r; r = fila(ws, r, ["Sesiones terminadas", dc.citas_terminadas]);
    const rCm = r; r = fila(ws, r, ["Con motivo registrado", dc.con_motivo]);
    r = fila(ws, r, ["% con motivo", pctF(`B${rCm}`, `B${rTe}`, (dc.pct ?? 0) / 100)]);
    r += 1; r = cabecera(ws, r, ["Ingresos por medio de pago", "Monto", "%"]);
    {
      const ini = r, datos = mp.por_medio || [], fin_ = ini + Math.max(datos.length - 1, 0);
      datos.forEach((x) => { r = fila(ws, r, [x.label, x.valor, pctF(`B${r}`, `SUM($B$${ini}:$B$${fin_})`, pctDe(x.valor, mp.total) / 100)], { fmts: [null, "soles"] }); });
      if (datos.length) r = fila(ws, r, ["Total cobrado", { ...sumF("B", ini, fin_, mp.total), fmt: "soles" }], { bold: true, linea: true });
    }
  }
  // --- Productividad ---
  {
    const ws = hoja("Productividad", "Productividad por psicólogo");
    ws.columns = [{ width: 32 }, { width: 12 }, { width: 12 }, { width: 12 }, { width: 12 }, { width: 14 }];
    let r = cabecera(ws, 4, ["Psicólogo", "Sesiones", "Atenciones", "Leads", "Cierres", "Tasa de cierre"]);
    const ini = r, prod = d.productividad || [];
    prod.forEach((p) => { r = fila(ws, r, [p.medico, p.citas, p.atenciones, p.leads, p.cierres, pctF(`E${r}`, `D${r}`, pctDe(p.cierres, p.leads) / 100)]); });
    if (prod.length) {
      const fin_ = r - 1;
      const tot = (k) => prod.reduce((s, p) => s + (p[k] || 0), 0);
      r = fila(ws, r, ["Total", sumF("B", ini, fin_, tot("citas")), sumF("C", ini, fin_, tot("atenciones")), sumF("D", ini, fin_, tot("leads")), sumF("E", ini, fin_, tot("cierres")), pctF(`E${r}`, `D${r}`, pctDe(tot("cierres"), tot("leads")) / 100)], { bold: true, linea: true });
    } else {
      fila(ws, r, ["Sin actividad en el período."]);
    }
  }
  return await wb.xlsx.writeBuffer();
}
export async function exportarExcel(modelo, base) {
  const buf = await construirExcel(modelo);
  descargarBlob(nombreArchivo(modelo, base, "xlsx"), new Blob([buf], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }));
}

// ---------------------------------------------------------------------------
// Word (.docx): tablas de cada sección + espacio para redactar el análisis.
// Estilos de Word propios (Título, Título 1, Título 2) con la marca, para que
// al editar el documento se mantenga la identidad.
// ---------------------------------------------------------------------------
export async function construirWord(modelo, opts = {}) {
  const { node = false } = opts;
  const m = await import("docx");
  const D = m.default && m.default.Document ? m.default : m;
  const { Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, AlignmentType, BorderStyle, ShadingType, PageNumber, Footer, Header, ImageRun } = D;
  const logos = await cargarLogos(opts);
  const F = MARCA.fuente;

  const borde = { style: BorderStyle.SINGLE, size: 4, color: hex(MARCA.linea) };
  const bordes = { top: borde, bottom: borde, left: borde, right: borde };
  // Cabecera celeste sólido con texto blanco (como los formatos impresos de la
  // clínica); filas alternas con un tinte muy suave del celeste.
  const celda = (texto, { bold = false, ancho, cabecera = false, derecha = false, zebra = false } = {}) => new TableCell({
    borders: bordes,
    width: ancho ? { size: ancho, type: WidthType.PERCENTAGE } : undefined,
    shading: cabecera
      ? { type: ShadingType.CLEAR, fill: hex(MARCA.celeste), color: "auto" }
      : (zebra ? { type: ShadingType.CLEAR, fill: hex(MARCA.celesteFondo), color: "auto" } : undefined),
    margins: { top: 70, bottom: 70, left: 110, right: 110 },
    children: [new Paragraph({
      alignment: derecha ? AlignmentType.RIGHT : AlignmentType.LEFT,
      children: [new TextRun({ text: cabecera ? String(texto ?? "").toUpperCase() : String(texto ?? ""), bold: bold || cabecera, font: F, color: hex(cabecera ? MARCA.blanco : MARCA.negro), size: cabecera ? 17 : 19 })],
    })],
  });
  const tabla = (columnas, filas, anchos, numericas = []) => new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    rows: [
      new TableRow({ tableHeader: true, children: columnas.map((c, i) => celda(c, { cabecera: true, ancho: anchos[i], derecha: numericas.includes(i) })) }),
      ...filas.map((f, idx) => new TableRow({ children: f.map((v, i) => celda(v, { ancho: anchos[i], derecha: numericas.includes(i), zebra: idx % 2 === 1 })) })),
    ],
  });
  const p = (texto, { size = 21, color = hex(MARCA.negro), italics = false, bold = false, after = 120, align } = {}) =>
    new Paragraph({ spacing: { after }, alignment: align, children: [new TextRun({ text: texto, size, color, italics, bold, font: F })] });
  const h1 = (texto, saltar) => new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: saltar, children: [new TextRun({ text: texto, font: F })] });
  const h2 = (texto) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text: texto, font: F })] });

  const hijos = [];
  if (logos && logos.v) {
    hijos.push(new Paragraph({ alignment: AlignmentType.LEFT, spacing: { after: 200 }, children: [
      new ImageRun({ type: "png", data: logos.v.bytes, transformation: { width: 120, height: Math.round(120 * logos.v.h / logos.v.w) } }),
    ] }));
  }
  hijos.push(
    new Paragraph({ heading: HeadingLevel.TITLE, children: [new TextRun({ text: modelo.titulo, font: F })] }),
    p(modelo.subtitulo, { size: 21, color: hex(MARCA.gris) }),
    p(`Generado el ${modelo.generadoEn}. Todos los números son reales del período seleccionado.`, { size: 17, color: hex(MARCA.gris), after: 280 }),
  );
  modelo.secciones.forEach((s, i) => {
    hijos.push(h1(s.titulo, i > 0));
    if (s.kpis.length) {
      hijos.push(tabla(["Indicador", "Valor", "Detalle"], s.kpis.map((k) => [k.label, typeof k.valor === "number" ? k.valor.toLocaleString("es-PE") : k.valor, k.sub || ""]), [46, 22, 32], [1]));
    }
    s.series.forEach((se) => {
      const total = se.datos.reduce((a, x) => a + (x.valor || 0), 0);
      hijos.push(h2(se.titulo));
      hijos.push(tabla([se.tipo === "columnas" ? "Día" : "Categoría", se.fmt === "soles" ? "Monto" : "Cantidad", "%"],
        se.datos.map((x) => [x.label, fmtValor(x.valor, se.fmt), `${pctDe(x.valor, total)}%`]), [50, 28, 22], [1, 2]));
    });
    s.tablas.forEach((t) => {
      if (t.titulo) hijos.push(h2(t.titulo));
      const anchos = t.columnas.map((_, j) => (j === 0 ? 40 : Math.floor(60 / (t.columnas.length - 1))));
      hijos.push(tabla(t.columnas, t.filas.length ? t.filas.map((f) => f.map((v) => (typeof v === "number" ? v.toLocaleString("es-PE") : v))) : [["Sin actividad en el período.", ...t.columnas.slice(1).map(() => "")]], anchos, t.numericas));
    });
    s.notas.forEach((n) => hijos.push(p(n, { size: 18, color: hex(MARCA.gris) })));
    hijos.push(h2("Análisis y conclusiones"));
    hijos.push(p("Escribe aquí el análisis de esta sección: qué está pasando, por qué, y qué se decide.", { italics: true, color: hex(MARCA.gris) }));
    hijos.push(p(""), p(""), p(""));
  });

  const encabezado = logos && logos.h
    ? new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [
        new ImageRun({ type: "png", data: logos.h.bytes, transformation: { width: 96, height: Math.round(96 * logos.h.h / logos.h.w) } }),
      ] })] })
    : new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: modelo.clinica, size: 16, color: hex(MARCA.gris), font: F })] })] });

  const doc = new Document({
    creator: modelo.clinica, title: modelo.titulo,
    styles: {
      default: { document: { run: { font: F, size: 21, color: hex(MARCA.negro) } } },
      paragraphStyles: [
        { id: "Title", name: "Title", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: F, size: 48, bold: true, color: hex(MARCA.celeste) }, paragraph: { spacing: { after: 80 } } },
        // Barra vertical celeste a la izquierda del título de sección (acento del manual).
        { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: F, size: 30, bold: true, color: hex(MARCA.celeste) },
          paragraph: { spacing: { before: 240, after: 140 }, border: { left: { style: BorderStyle.SINGLE, size: 18, color: hex(MARCA.celeste), space: 8 } }, indent: { left: 140 } } },
        { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: F, size: 22, bold: true, color: hex(MARCA.gris) }, paragraph: { spacing: { before: 220, after: 100 } } },
      ],
    },
    sections: [{
      // La portada lleva el logo principal grande; el logo horizontal va en el
      // encabezado de las páginas siguientes (no los dos en la misma página).
      properties: { titlePage: true, page: { margin: { top: 1100, bottom: 1000, left: 1100, right: 1100 } } },
      headers: { default: encabezado, first: new Header({ children: [new Paragraph({ children: [] })] }) },
      footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [
        new TextRun({ text: `${modelo.clinica} · ${modelo.titulo}   `, size: 15, color: hex(MARCA.gris), font: F }),
        new TextRun({ children: [PageNumber.CURRENT], size: 20, bold: true, color: hex(MARCA.celeste), font: F }),
      ] })] }) },
      children: hijos,
    }],
  });
  return node ? await Packer.toBuffer(doc) : await Packer.toBlob(doc);
}
export async function exportarWord(modelo, base) {
  const blob = await construirWord(modelo);
  descargarBlob(nombreArchivo(modelo, base, "docx"), blob);
}

// ---------------------------------------------------------------------------
// PowerPoint (.pptx): portada + una diapositiva por sección + cierre, con
// tarjetas de KPI y gráficos NATIVOS de PowerPoint (editables, no imágenes).
// Sigue el patrón del deck real de la clínica: fondo blanco, títulos en
// celeste negrita, logo principal en la portada y horizontal en cada lámina.
// ---------------------------------------------------------------------------
export async function construirPowerPoint(modelo, opts = {}) {
  const { node = false } = opts;
  const m = await import("pptxgenjs");
  const PptxGenJS = m.default || m;
  const logos = await cargarLogos(opts);
  const pptx = new PptxGenJS();
  pptx.layout = "LAYOUT_16x9"; // 10 x 5.625 pulgadas
  pptx.author = modelo.clinica; pptx.title = modelo.titulo;
  const F = MARCA.fuente;
  const C = { celeste: hex(MARCA.celeste), claro: hex(MARCA.celesteClaro), gris: hex(MARCA.gris), negro: hex(MARCA.negro), linea: hex(MARCA.linea), fondo: hex(MARCA.celesteFondo) };
  const logoData = (k) => (logos && logos[k] ? `image/png;base64,${logos[k].b64}` : null);

  const objetosBase = [
    { text: { text: `${modelo.clinica} · ${modelo.titulo} · ${modelo.sedeLbl}`, options: { x: 0.4, y: 5.22, w: 7, h: 0.28, fontSize: 8.5, color: C.gris, fontFace: F } } },
  ];
  if (logoData("h")) objetosBase.unshift({ image: { data: logoData("h"), x: 0.4, y: 0.28, w: 1.55, h: 1.55 * MARCA.logo.h.h / MARCA.logo.h.w } });
  else objetosBase.unshift({ text: { text: modelo.clinica, options: { x: 0.4, y: 0.28, w: 3, h: 0.4, fontSize: 11, bold: true, color: C.gris, fontFace: F } } });
  pptx.defineSlideMaster({
    title: "BASE", background: { color: "FFFFFF" }, objects: objetosBase,
    slideNumber: { x: 9.1, y: 5.2, w: 0.6, h: 0.3, fontSize: 10, bold: true, color: C.celeste, fontFace: F, align: "right" },
  });

  // Portada (como la del deck: logo principal centrado, título celeste, subtítulo gris)
  {
    const s = pptx.addSlide();
    s.background = { color: "FFFFFF" };
    if (logoData("v")) s.addImage({ data: logoData("v"), x: 3.95, y: 0.7, w: 2.1, h: 2.1 * MARCA.logo.v.h / MARCA.logo.v.w });
    s.addText(modelo.titulo, { x: 0.6, y: 2.55, w: 8.8, h: 0.9, fontSize: 32, bold: true, color: C.celeste, fontFace: F, align: "center", valign: "middle" });
    s.addText(modelo.subtitulo.replace(`${modelo.clinica} · `, ""), { x: 0.6, y: 3.45, w: 8.8, h: 0.5, fontSize: 15, color: C.gris, fontFace: F, align: "center" });
    s.addText(`Generado el ${modelo.generadoEn} · datos reales del período`, { x: 0.6, y: 4.75, w: 8.8, h: 0.35, fontSize: 9.5, color: C.gris, fontFace: F, align: "center" });
  }

  // Título de lámina con la barra vertical celeste del manual a su izquierda.
  const titulo = (s, texto) => {
    s.addShape(pptx.ShapeType.rect, { x: 0.4, y: 1.03, w: 0.06, h: 0.4, fill: { color: C.celeste }, line: { color: C.celeste, width: 0 } });
    s.addText(texto, { x: 0.56, y: 0.95, w: 9.0, h: 0.55, fontSize: 22, bold: true, color: C.celeste, fontFace: F, valign: "middle" });
  };
  const kpis = (s, lista, y) => {
    const n = lista.length; if (!n) return y;
    const gap = 0.14, w = (9.2 - gap * (n - 1)) / n, h = 0.95;
    lista.forEach((k, i) => {
      const x = 0.4 + i * (w + gap);
      s.addShape(pptx.ShapeType.roundRect, { x, y, w, h, fill: { color: C.claro }, line: { color: C.claro, width: 0 }, rectRadius: 0.07 });
      s.addText(String(k.valor), { x: x + 0.12, y: y + 0.07, w: w - 0.24, h: 0.46, fontSize: n > 4 ? 17 : 21, bold: true, color: C.negro, fontFace: F, valign: "middle" });
      s.addText(k.label + (k.sub ? `\n${k.sub}` : ""), { x: x + 0.12, y: y + 0.5, w: w - 0.24, h: 0.42, fontSize: n > 4 ? 7.5 : 8.5, color: C.gris, fontFace: F, valign: "top" });
    });
    return y + h + 0.18;
  };
  const grafico = (s, se, x, y, w, h) => {
    if (!se.datos.length) { s.addText(`${se.titulo}: sin datos.`, { x, y, w, h: 0.4, fontSize: 10, color: C.gris, fontFace: F }); return; }
    s.addChart(pptx.ChartType.bar, [{ name: se.titulo, labels: se.datos.map((d) => String(d.label)), values: se.datos.map((d) => Number(d.valor || 0)) }], {
      x, y, w, h,
      barDir: se.tipo === "columnas" ? "col" : "bar",
      chartColors: [hex(se.color || MARCA.celeste)],
      showTitle: true, title: se.titulo, titleFontSize: 10.5, titleColor: C.gris, titleFontFace: F,
      showLegend: false, showValue: true,
      dataLabelFontSize: 8, dataLabelColor: C.negro, dataLabelFontFace: F, dataLabelFormatCode: se.fmt === "soles" ? '"S/ "#,##0' : "#,##0",
      catAxisLabelFontSize: 8, catAxisLabelColor: C.gris, catAxisLabelFontFace: F,
      valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" },
      barGapWidthPct: se.tipo === "columnas" ? 60 : 40,
    });
  };
  const notas = (s, lista, y) => { if (lista.length) s.addText(lista.join("  ·  "), { x: 0.4, y, w: 9.2, h: 0.3, fontSize: 8.5, color: C.gris, fontFace: F, italic: true }); };

  modelo.secciones.forEach((sec) => {
    if (sec.kpis.length || sec.series.length) {
      const s = pptx.addSlide({ masterName: "BASE" });
      titulo(s, sec.titulo);
      let y = kpis(s, sec.kpis, 1.6);
      const alto = Math.max(4.85 - y, 1.5);
      if (sec.series.length === 1) grafico(s, sec.series[0], 0.4, y, 9.2, alto);
      else if (sec.series.length >= 2) { grafico(s, sec.series[0], 0.4, y, 4.5, alto); grafico(s, sec.series[1], 5.1, y, 4.5, alto); }
      notas(s, sec.notas, 4.9);
    }
    sec.tablas.forEach((t) => {
      const filas = t.filas.length ? t.filas : [["Sin actividad en el período.", ...t.columnas.slice(1).map(() => "")]];
      const porPagina = 11;
      for (let i = 0; i < filas.length; i += porPagina) {
        const s = pptx.addSlide({ masterName: "BASE" });
        titulo(s, sec.titulo + (filas.length > porPagina ? ` (${Math.floor(i / porPagina) + 1}/${Math.ceil(filas.length / porPagina)})` : ""));
        const head = t.columnas.map((c, j) => ({ text: c.toUpperCase(), options: { bold: true, fill: { color: C.celeste }, color: "FFFFFF", align: t.numericas.includes(j) ? "right" : "left", fontFace: F, fontSize: 9 } }));
        const body = filas.slice(i, i + porPagina).map((f) => f.map((v, j) => ({ text: typeof v === "number" ? v.toLocaleString("es-PE") : String(v ?? ""), options: { align: t.numericas.includes(j) ? "right" : "left", color: C.negro, fontFace: F } })));
        const colW = t.columnas.map((_, j) => (j === 0 ? 3.6 : (9.2 - 3.6) / (t.columnas.length - 1)));
        s.addTable([head, ...body], { x: 0.4, y: 1.6, w: 9.2, colW, fontSize: 10, fontFace: F, border: { type: "solid", pt: 0.5, color: C.linea }, rowH: 0.3, autoPage: false });
        if (!sec.kpis.length && !sec.series.length) notas(s, sec.notas, 4.9);
      }
    });
  });

  // Cierre (como el deck: logo principal centrado y la frase de marca)
  {
    const s = pptx.addSlide();
    s.background = { color: "FFFFFF" };
    if (logoData("v")) s.addImage({ data: logoData("v"), x: 3.7, y: 1.35, w: 2.6, h: 2.6 * MARCA.logo.v.h / MARCA.logo.v.w });
    s.addText(MARCA.tagline.toUpperCase(), { x: 0.6, y: 3.6, w: 8.8, h: 0.5, fontSize: 14, bold: true, charSpacing: 6, color: C.gris, fontFace: F, align: "center" });
  }
  return await pptx.write({ outputType: node ? "nodebuffer" : "blob" });
}
export async function exportarPowerPoint(modelo, base) {
  const blob = await construirPowerPoint(modelo);
  descargarBlob(nombreArchivo(modelo, base, "pptx"), blob);
}

// ---------------------------------------------------------------------------
// PDF ejecutivo: una vista de reporte (tarjetas, gráficos y tablas como en
// pantalla) preparada para A4, sin cortes raros, que se guarda como PDF desde
// el diálogo de impresión del navegador.
// ---------------------------------------------------------------------------
export function htmlReporte(modelo, { autoImprimir = true, logos = null } = {}) {
  const esc = (v) => String(v ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const M = MARCA;
  const logoH = logos && logos.h ? `<img class="logo" src="data:image/png;base64,${logos.h.b64}" alt="${esc(modelo.clinica)}">` : `<div class="k">${esc(modelo.clinica)}</div>`;
  const kpiHtml = (k) => `<div class="kpi"><div class="n">${esc(k.valor)}</div><div class="l">${esc(k.label)}</div>${k.sub ? `<div class="s">${esc(k.sub)}</div>` : ""}</div>`;
  const serieHtml = (se) => {
    if (!se.datos.length) return `<div class="chart"><div class="t">${esc(se.titulo)}</div><div class="note">Sin datos.</div></div>`;
    const max = Math.max(1, ...se.datos.map((d) => d.valor || 0));
    const total = se.datos.reduce((a, d) => a + (d.valor || 0), 0) || 1;
    if (se.tipo === "columnas") {
      return `<div class="chart"><div class="t">${esc(se.titulo)}</div><div class="cols">${se.datos.map((d) => `
        <div class="col"><div class="v">${esc(se.fmt === "soles" ? soles(d.valor) : d.valor)}</div><div class="b" style="height:${Math.max(2, Math.round(((d.valor || 0) / max) * 80))}px;background:${se.color}"></div><div class="x">${esc(d.label)}</div></div>`).join("")}</div></div>`;
    }
    return `<div class="chart"><div class="t">${esc(se.titulo)}</div>${se.datos.map((d) => `
      <div class="hbar"><div class="lb">${esc(d.label)}</div><div class="tr"><div class="f" style="width:${Math.round(((d.valor || 0) / max) * 100)}%;background:${se.color}"></div></div><div class="v">${esc(fmtValor(d.valor, se.fmt))} <span>${pctDe(d.valor, total)}%</span></div></div>`).join("")}</div>`;
  };
  const tablaHtml = (t) => `<table><thead><tr>${t.columnas.map((c, i) => `<th class="${t.numericas.includes(i) ? "num" : ""}">${esc(c)}</th>`).join("")}</tr></thead><tbody>${
    t.filas.length ? t.filas.map((f) => `<tr>${f.map((v, i) => `<td class="${t.numericas.includes(i) ? "num" : ""}">${esc(typeof v === "number" ? v.toLocaleString("es-PE") : v)}</td>`).join("")}</tr>`).join("")
      : `<tr><td colspan="${t.columnas.length}" class="note">Sin actividad en el período.</td></tr>`}</tbody></table>`;
  const secHtml = (s) => `<section class="sec">
    <h2>${esc(s.titulo)}</h2>
    ${s.kpis.length ? `<div class="kpis n${Math.min(s.kpis.length, 5)}">${s.kpis.map(kpiHtml).join("")}</div>` : ""}
    ${s.series.length ? `<div class="charts ${s.series.length === 1 ? "uno" : ""}">${s.series.map(serieHtml).join("")}</div>` : ""}
    ${s.tablas.map(tablaHtml).join("")}
    ${s.notas.map((n) => `<div class="note">${esc(n)}</div>`).join("")}
  </section>`;

  return `<!doctype html><html lang="es"><head><meta charset="utf-8"><title>${esc(modelo.titulo)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
  @page { size: A4; margin: 13mm 12mm 18mm;
    @bottom-right { content: counter(page); font-family: ${M.fuente}, ${M.fuenteFallback}; font-size: 10px; font-weight: 700; color: ${M.celeste}; } }
  html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  body { font-family: ${M.fuente}, ${M.fuenteFallback}; color: ${M.negro}; margin: 0; background: #fff; padding: 24px; }
  .cover { border-bottom: 3px solid ${M.celeste}; padding-bottom: 12px; margin-bottom: 18px; display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; }
  .cover .logo { height: 44px; width: auto; display: block; margin-bottom: 10px; }
  .cover .k { font-size: 10px; letter-spacing: .12em; text-transform: uppercase; color: ${M.gris}; margin-bottom: 6px; }
  h1 { font-size: 22px; margin: 0; color: ${M.celeste}; font-weight: 700; } .sub { color: ${M.gris}; font-size: 12px; margin-top: 4px; }
  .gen { font-size: 10px; color: ${M.gris}; text-align: right; line-height: 1.5; }
  .sec { break-inside: avoid; page-break-inside: avoid; margin: 0 0 18px; }
  h2 { font-size: 11px; letter-spacing: .1em; text-transform: uppercase; color: ${M.celeste}; font-weight: 700; margin: 0 0 8px; border-left: 3px solid ${M.celeste}; padding-left: 8px; line-height: 1.2; }
  .kpis { display: grid; gap: 8px; margin-bottom: 10px; } .kpis.n1, .kpis.n2, .kpis.n3 { grid-template-columns: repeat(3, 1fr); } .kpis.n4 { grid-template-columns: repeat(4, 1fr); } .kpis.n5 { grid-template-columns: repeat(5, 1fr); }
  .kpi { border-radius: 10px; padding: 10px 12px; background: ${M.celesteClaro}; }
  .kpi .n { font-size: 20px; font-weight: 700; color: ${M.negro}; } .kpi .l { font-size: 10.5px; color: ${M.gris}; margin-top: 2px; } .kpi .s { font-size: 9.5px; color: ${M.gris}; margin-top: 1px; }
  .charts { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; } .charts.uno { grid-template-columns: 1fr; }
  .chart { border: 1px solid ${M.linea}; border-radius: 10px; padding: 10px 12px; break-inside: avoid; }
  .chart .t { font-size: 11px; color: ${M.gris}; margin-bottom: 8px; font-weight: 600; }
  .hbar { display: flex; align-items: center; gap: 8px; margin: 5px 0; font-size: 11px; } .hbar .lb { width: 92px; color: ${M.gris}; flex-shrink: 0; }
  .hbar .tr { flex: 1; height: 10px; background: ${M.linea}; border-radius: 99px; overflow: hidden; } .hbar .f { height: 100%; border-radius: 99px; }
  .hbar .v { width: 92px; text-align: right; font-variant-numeric: tabular-nums; flex-shrink: 0; } .hbar .v span { color: ${M.gris}; font-size: 10px; }
  .cols { display: flex; align-items: flex-end; gap: 4px; height: 118px; } .col { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; gap: 3px; min-width: 0; height: 100%; }
  .col .b { width: 100%; max-width: 26px; border-radius: 3px 3px 0 0; } .col .x, .col .v { font-size: 8px; color: ${M.gris}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
  table { width: 100%; border-collapse: collapse; font-size: 11px; }
  th { text-align: left; font-size: 9.5px; text-transform: uppercase; letter-spacing: .05em; color: #fff; background: ${M.celeste}; padding: 7px 8px; }
  td { padding: 6px 8px; border-bottom: 1px solid ${M.linea}; } td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
  tbody tr:nth-child(even) td { background: ${M.celesteFondo}; }
  .note { font-size: 10.5px; color: ${M.gris}; margin-top: 6px; }
  .foot { display: none; }
  .noprint { position: sticky; top: 0; background: #fff; padding: 8px 0 12px; margin-bottom: 8px; border-bottom: 1px solid ${M.linea}; display: flex; gap: 10px; align-items: center; z-index: 5; }
  .noprint button { padding: 9px 16px; border: none; border-radius: 8px; background: ${M.celeste}; color: #fff; font-size: 14px; cursor: pointer; font-family: inherit; font-weight: 600; }
  .noprint span { font-size: 12px; color: ${M.gris}; }
  @media print {
    body { padding: 0; } .noprint { display: none; }
    .foot { display: flex; position: fixed; bottom: 0; left: 0; right: 0; justify-content: space-between; font-size: 9px; color: ${M.gris}; border-top: 0.5pt solid ${M.gris}; padding-top: 4px; }
  }
</style></head><body>
<div class="noprint"><button onclick="window.print()">Guardar como PDF</button><span>Se abre el diálogo de impresión: elige "Guardar como PDF". Los colores y gráficos se conservan.</span></div>
<div class="cover"><div>${logoH}<h1>${esc(modelo.titulo)}</h1><div class="sub">${esc(modelo.subtitulo)}</div></div><div class="gen">Generado el ${esc(modelo.generadoEn)}<br>Datos reales del período</div></div>
${modelo.secciones.map(secHtml).join("\n")}
<div class="foot"><span>${esc(modelo.clinica)} · ${esc(modelo.titulo)} · ${esc(modelo.sedeLbl)}</span><span>${esc(M.tagline)} · generado el ${esc(modelo.generadoEn)}</span></div>
${autoImprimir ? `<script>window.addEventListener("load",function(){setTimeout(function(){window.print()},700)});</script>` : ""}
</body></html>`;
}
export async function exportarPDF(modelo) {
  // La ventana se abre ANTES de cualquier await: si no, el bloqueador de
  // ventanas emergentes la frena porque ya no cuenta como clic del usuario.
  const w = window.open("", "_blank", "width=1000,height=900");
  if (!w) throw new Error("Permite las ventanas emergentes para generar el PDF.");
  const logos = await cargarLogos();
  w.document.write(htmlReporte(modelo, { logos }));
  w.document.close();
}
