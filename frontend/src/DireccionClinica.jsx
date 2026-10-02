// Dirección Clínica → continuidad y seguimiento de los procesos.
//
// Solo lectura. Todo sale de /api/direccion-clinica/ (core/direccion_clinica.py),
// que reconstruye los procesos con la misma regla del Centro de Continuidad.
// Definiciones y límites: docs/direccion-clinica.md y docs/continuidad-*.md.
//
// Jerarquía de la pantalla (de lo que se mira cada vez a lo que se consulta):
//   1. cuatro indicadores · 2. Atención hoy · 3. lectura rápida (continuidad,
//   ritmo, estado registrado) · 4. desglose en pestañas · 5. calidad del dato y
//   metodología, plegadas. Ninguna cifra se eliminó: lo que no está a la vista
//   está en un detalle plegable, una pestaña o un ⓘ, y al imprimir se despliega.
//
// Lo que esta pantalla NO hace, a propósito:
// - No llama "abandono" a lo que no lo es: el inferido (cálculo) y el
//   confirmado (registrado) van siempre por separado.
// - No ordena a los psicólogos por desempeño: orden alfabético, sin colores de
//   bueno/malo.
// - No muestra un porcentaje sin su base: numerador, evaluables y «aún en curso».
//
// Los filtros viven en la URL (/gestion?vista=direccion&sede=piura…): recargar,
// compartir el enlace o volver atrás conserva lo que se estaba mirando.
import { useEffect, useRef, useState } from "react";
import { Activity, ArrowRight, CalendarX, ClipboardList, Info, Printer, RotateCcw } from "lucide-react";
import { api } from "./api";

const SEDES = [["", "Todas"], ["lima", "Lima"], ["piura", "Piura"]];
// Colores de CALIDAD del dato y de atención. El acento de marca sale de
// var(--accent); el rojo queda reservado para un dato de calidad realmente bajo.
const ROJO = "#B4564E", AMBAR = "#B07A1E", VERDE = "#3F7F5F";

// La vista se reconoce en la URL por ?vista=direccion (ver App.jsx).
const VISTA_URL = "direccion";
const DEFECTO = {
  periodo: "365d", desde: "", hasta: "", sede: "", psicologo: "", categoria: "",
  modalidad: "", etapa: "", dias_abandono: 45,
};
const PERIODOS_CORTOS = { "30d": "30 días", "90d": "3 meses", "180d": "6 meses", "365d": "12 meses", todo: "Todo" };

// Filtros ⇄ URL. Solo se escribe lo que difiere del valor por defecto.
function filtrosDeUrl() {
  const q = new URLSearchParams(window.location.search);
  const f = { ...DEFECTO };
  for (const k of Object.keys(DEFECTO)) {
    if (q.has(k)) f[k] = q.get(k) || "";
  }
  const dias = parseInt(f.dias_abandono, 10);
  f.dias_abandono = Number.isFinite(dias) ? dias : DEFECTO.dias_abandono;
  if (f.desde || f.hasta) f.periodo = "rango";
  else if (f.periodo === "rango" || !PERIODOS_CORTOS[f.periodo]) f.periodo = DEFECTO.periodo;
  return f;
}

function urlDeFiltros(f) {
  const q = new URLSearchParams({ vista: VISTA_URL });
  for (const [k, v] of Object.entries(f)) {
    if (k === "periodo" && v === "rango") continue;
    if (v !== "" && v !== null && v !== undefined && String(v) !== String(DEFECTO[k])) q.set(k, v);
  }
  return `${window.location.pathname}?${q.toString()}`;
}

// Lo que se manda a la API (el período "rango" se expresa con desde/hasta).
function paraApi(f) {
  const { periodo, ...resto } = f;
  return periodo === "rango" ? resto : { ...resto, periodo, desde: "", hasta: "" };
}

const esDefecto = (f) => Object.keys(DEFECTO).every((k) => String(f[k]) === String(DEFECTO[k]));

// Impresión / "Guardar como PDF". El sistema vive dentro de un contenedor con
// scroll propio (.clinica-app / .ca-main): impreso tal cual, salía UNA hoja con
// el menú y el resto cortado. Estas reglas solo aplican cuando esta pantalla
// está abierta (body:has(.dc-pagina)). Al imprimir se despliegan los detalles
// (ver `useImpresionCompleta`) y se muestran todas las pestañas del desglose.
const ESTILOS = `
.dc-solo-impresion { display:none; }
.dc-pagina { --dc-gap:16px; }
.dc-filtros { display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin-top:12px; }
.dc-filtros .ca-seg { margin-left:0; max-width:100%; overflow-x:auto; }
.dc-filtros .ca-seg button { white-space:nowrap; flex-shrink:0; padding:6px 10px; }
.dc-filtros select.ca-input { width:auto; max-width:100%; padding:6px 10px; font-size:13px; }
.dc-dias { font-size:12.5px; color:var(--ink-soft); display:flex; align-items:center; gap:6px; }
.dc-dias input { width:62px; padding:5px 8px; }
.dc-rango { display:flex; gap:8px; flex-wrap:wrap; align-items:center; font-size:13px; color:var(--ink-soft); margin-top:10px; }
.dc-rango input { width:auto; padding:6px 8px; }
.dc-error { color:${ROJO}; font-size:12.5px; }
.dc-activos { font-size:12px; color:var(--muted); margin-top:8px; line-height:1.5; }
.dc-sub { font-size:12px; color:var(--muted); line-height:1.4; }
.dc-muestra { display:inline-block; font-size:10.5px; color:var(--ink-soft); background:var(--hover);
  border-radius:5px; padding:0 6px; white-space:nowrap; font-weight:500; vertical-align:1px; }
.dc-info { display:inline-flex; vertical-align:-2px; margin-left:4px; color:var(--muted); cursor:help; border-radius:4px; }
.dc-info:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
.dc-seccion { margin-top:28px; }
.dc-titulo { display:flex; align-items:baseline; justify-content:space-between; gap:10px; flex-wrap:wrap; margin-bottom:10px; }
.dc-titulo h2 { margin:0; }
/* --- Indicadores principales --- */
.dc-kpis { display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); gap:var(--dc-gap); margin-top:20px; }
.dc-kpi { background:var(--surface); border:1px solid var(--line); border-radius:12px; padding:18px 18px 16px; min-width:0; }
.dc-kpi-cab { display:flex; align-items:center; gap:8px; color:var(--ink-soft); font-size:13px; font-weight:500; }
.dc-kpi-cab svg { color:var(--accent); flex-shrink:0; }
.dc-kpi-n { font-size:34px; font-weight:600; letter-spacing:-0.02em; line-height:1.1; margin-top:10px; font-variant-numeric:tabular-nums; color:var(--ink); }
.dc-kpi.atencion { border-color:#EBD9B5; background:#FFFBF2; }
.dc-kpi.atencion .dc-kpi-cab svg { color:${AMBAR}; }
.dc-kpi.atencion .dc-kpi-n { color:#8A5A10; }
.dc-kpi .dc-sub { margin-top:4px; }
/* --- Atención hoy --- */
.dc-atencion { background:var(--surface); border:1px solid var(--line); border-radius:12px; padding:18px; }
.dc-razones { display:grid; grid-template-columns:repeat(auto-fill, minmax(230px, 1fr)); gap:10px; margin-top:12px; }
.dc-razon { display:flex; align-items:baseline; gap:10px; padding:10px 12px; border-radius:10px; background:#FFF8EA; border:1px solid #F0E1C2; }
.dc-razon b { font-size:22px; font-weight:600; font-variant-numeric:tabular-nums; color:#7A4E0C; min-width:2ch; }
.dc-razon span { font-size:13.5px; color:var(--ink); line-height:1.35; }
.dc-ceros { margin-top:12px; font-size:12.5px; color:var(--muted); line-height:1.6; }
.dc-ceros .dc-nowrap { white-space:nowrap; }
.dc-acciones { display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-top:14px; }
/* --- Lectura rápida --- */
.dc-lectura { display:grid; grid-template-columns:minmax(0,1.35fr) minmax(0,1fr); gap:var(--dc-gap); }
.dc-panel { background:var(--surface); border:1px solid var(--line); border-radius:12px; padding:18px; min-width:0; }
.dc-panel h3 { font-size:15px; font-weight:600; margin:0; display:flex; align-items:center; gap:4px; }
.dc-panel-ancho { grid-column:1 / -1; }
.dc-flujo { display:flex; align-items:stretch; gap:6px; margin-top:14px; overflow-x:auto; padding-bottom:4px; }
.dc-etapa { flex:1 0 64px; text-align:center; padding:10px 6px; border-radius:10px; background:var(--accent-soft); }
.dc-etapa small { display:block; font-size:12px; color:var(--ink-soft); font-weight:600; }
.dc-etapa b { display:block; font-size:22px; font-weight:600; font-variant-numeric:tabular-nums; color:var(--ink); }
.dc-paso { flex:1 0 74px; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; }
.dc-paso svg { color:var(--muted); }
.dc-paso strong { font-size:15px; font-variant-numeric:tabular-nums; }
.dc-paso .dc-sub { font-size:11px; }
.dc-paso.sin { color:var(--muted); }
.dc-chips { display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }
.dc-chip { font-size:12.5px; border:1px solid var(--line); border-radius:8px; padding:5px 10px; background:var(--surface); color:var(--ink); }
.dc-chip b { font-variant-numeric:tabular-nums; }
.dc-chip.cero { color:var(--muted); background:transparent; }
.dc-grande { font-size:28px; font-weight:600; letter-spacing:-0.02em; margin-top:8px; font-variant-numeric:tabular-nums; }
.dc-barra-fila { display:grid; grid-template-columns:96px 1fr 56px; gap:8px; align-items:center; font-size:12.5px; margin-top:7px; }
.dc-barra-fila.cero { color:var(--muted); }
.dc-barra { height:9px; background:var(--hover); border-radius:5px; overflow:hidden; display:flex; }
.dc-barra span { display:block; height:100%; background:var(--accent); }
.dc-motivos .dc-barra-fila { grid-template-columns:minmax(120px, 170px) 1fr 84px; }
.dc-leyenda { display:flex; gap:12px; font-size:11.5px; color:var(--muted); margin-top:8px; flex-wrap:wrap; }
.dc-leyenda i { display:inline-block; width:9px; height:9px; border-radius:2px; margin-right:4px; vertical-align:-1px; }
.dc-mini-stats { display:grid; grid-template-columns:repeat(auto-fit, minmax(170px, 1fr)); gap:10px; margin-top:10px; }
.dc-mini { border:1px solid var(--line); border-radius:10px; padding:10px 12px; }
.dc-mini b { display:block; font-size:18px; font-weight:600; font-variant-numeric:tabular-nums; }
.dc-mini span { display:block; font-size:12.5px; color:var(--ink-soft); }
/* --- Detalles plegables --- */
.dc-det { margin-top:12px; border-top:1px solid var(--line); padding-top:10px; }
.dc-det > summary { cursor:pointer; font-size:13px; color:var(--accent); font-weight:500; list-style:none; display:inline-flex; align-items:center; gap:6px; }
.dc-det > summary::-webkit-details-marker { display:none; }
.dc-det > summary::before { content:"▸"; font-size:11px; transition:transform .15s; }
.dc-det[open] > summary::before { transform:rotate(90deg); }
.dc-det > summary:focus-visible { outline:2px solid var(--accent); outline-offset:2px; border-radius:4px; }
.dc-det-cuerpo { margin-top:10px; }
.dc-nota { font-size:12.5px; color:var(--muted); margin-top:8px; line-height:1.55; }
/* --- Desglose --- */
.dc-tabs { display:flex; gap:4px; border-bottom:1px solid var(--line); overflow-x:auto; }
.dc-tabs button { background:none; border:none; border-bottom:2px solid transparent; padding:9px 14px; font-size:13.5px;
  color:var(--ink-soft); cursor:pointer; white-space:nowrap; font-weight:500; margin-bottom:-1px; }
.dc-tabs button[aria-selected="true"] { color:var(--accent); border-bottom-color:var(--accent); }
.dc-tabs button:focus-visible { outline:2px solid var(--accent); outline-offset:-2px; }
.dc-panel-tab[hidden] { display:none; }
.dc-tabla { overflow-x:auto; }
.dc-tabla .ca-table td.num, .dc-tabla .ca-table th.num { text-align:right; font-variant-numeric:tabular-nums; }
.dc-celda-sub { display:block; font-size:11px; color:var(--muted); white-space:nowrap; }
.dc-tabla-cab { display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap; margin:12px 0 4px; }
.dc-check { font-size:12.5px; color:var(--ink-soft); display:flex; align-items:center; gap:6px; cursor:pointer; }
/* --- Calidad del dato --- */
.dc-calidad-barra { display:flex; align-items:center; gap:14px; flex-wrap:wrap; font-size:13px; }
.dc-calidad-barra strong { font-weight:600; }
.dc-calidad-barra .dc-pct { font-variant-numeric:tabular-nums; font-weight:600; }
.dc-stats-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(200px, 1fr)); gap:10px; margin-top:12px; }
@media (max-width:1100px) { .dc-kpis { grid-template-columns:repeat(2, minmax(0,1fr)); } .dc-lectura { grid-template-columns:1fr; } }
@media (max-width:640px) {
  .dc-pagina .ca-tophead { flex-wrap:wrap; }
  .dc-kpis { grid-template-columns:1fr 1fr; gap:10px; }
  .dc-kpi { padding:14px; }
  .dc-kpi-n { font-size:28px; }
  .dc-filtros .ca-seg { flex-wrap:wrap; overflow-x:visible; }
}
@media print {
  @page { size: A4; margin: 12mm; }
  html, body, #root { height:auto !important; overflow:visible !important; background:#fff !important; }
  body:has(.dc-pagina) .ca-side { display:none !important; }
  body:has(.dc-pagina) .clinica-app { display:block !important; height:auto !important; min-height:0 !important;
    overflow:visible !important; border:none !important; border-radius:0 !important; background:#fff !important; }
  body:has(.dc-pagina) .ca-main { overflow:visible !important; padding:0 !important; }
  .dc-noprint { display:none !important; }
  .dc-solo-impresion { display:block !important; }
  .dc-pagina { -webkit-print-color-adjust:exact; print-color-adjust:exact; font-size:12px; }
  .dc-kpis { grid-template-columns:repeat(4, 1fr) !important; gap:8px !important; }
  .dc-lectura { grid-template-columns:1fr !important; }
  .dc-kpi, .dc-panel, .dc-atencion, .ca-card { box-shadow:none !important; break-inside:avoid; }
  .dc-kpi-n { font-size:22px !important; }
  .dc-panel-tab[hidden] { display:block !important; }
  .dc-tabs { display:none !important; }
  .dc-solo-impresion-titulo { display:block !important; font-weight:600; margin:12px 0 4px; }
  .dc-flujo { overflow:visible !important; }
  .dc-pagina table { width:100%; font-size:10.5px; }
  .dc-pagina th, .dc-pagina td { padding:5px 6px !important; }
  .dc-pagina tr { break-inside:avoid; }
}
.dc-solo-impresion-titulo { display:none; }`;

// --- Formato -----------------------------------------------------------------

const fechaCorta = (iso) => (iso ? iso.split("-").reverse().join("/") : "Sin datos");
const num = (v) => (v === null || v === undefined ? "Sin datos" : v);
// Un % sin dato puede ser "no evaluable" (nadie llegó al hito todavía) o
// simplemente "sin datos". Se dice cuál, en vez de un guion.
const pctTexto = (k) => {
  if (k?.pct !== null && k?.pct !== undefined) return `${k.pct}%`;
  return k && k.denominador === 0 ? "No evaluable" : "Sin datos";
};
const pctCelda = (v) => (v === null || v === undefined ? "—" : `${v}%`);

// Una tasa con su base: «43 de 56 evaluables · 2 aún en curso».
function baseDe(k, enCurso = "aún en curso") {
  if (!k) return "";
  if (!k.denominador) return k.no_evaluables ? `0 evaluables · ${k.no_evaluables} ${enCurso}` : "0 evaluables";
  const partes = [`${k.numerador} de ${k.denominador} evaluables`];
  if (k.no_evaluables) partes.push(`${k.no_evaluables} ${enCurso}`);
  return partes.join(" · ");
}

const TXT = {
  evaluables: "Evaluables: los procesos cuyo paso ya está resuelto (lo alcanzaron o ya terminaron). Los activos que todavía no llegan quedan fuera («aún en curso»).",
  muestra: "Menos de 10 evaluables: un caso más o menos mueve mucho la cifra. Es una regla técnica, no un juicio.",
  inferido: "Abandono inferido: última sesión hace más de N días, sin próxima cita y sin alta ni cierre registrado. Es un cálculo, no un abandono confirmado.",
  formal: "Estado registrado: lo que alguien registró en el proceso (pausa, alta, abandono confirmado, cierre). Los procesos anteriores al registro formal quedan «sin estado formal».",
  frecuencia: "Frecuencia esperada: cada cuánto se esperan las sesiones del proceso. Si el proceso no la tiene, se usa la anotada en la ficha (dato anterior).",
  revision: "Procesos con al menos una razón para revisarlos. Es información para coordinación: no envía mensajes ni cambia estados.",
};

// --- Piezas pequeñas ------------------------------------------------------------

function InfoTip({ texto }) {
  return (
    <span className="dc-info" tabIndex={0} role="img" aria-label={texto} title={texto}>
      <Info size={13} aria-hidden="true" />
    </span>
  );
}

function Muestra({ k }) {
  return k?.muestra_pequena ? <span className="dc-muestra" title={TXT.muestra}>muestra pequeña</span> : null;
}

function Nota({ children }) {
  return <div className="dc-nota">{children}</div>;
}

function Detalle({ resumen, children, id }) {
  return (
    <details className="dc-det" id={id}>
      <summary>{resumen}</summary>
      <div className="dc-det-cuerpo">{children}</div>
    </details>
  );
}

function Mini({ valor, label, sub, extra }) {
  return (
    <div className="dc-mini">
      <b>{valor}{extra}</b>
      <span>{label}</span>
      {sub && <div className="dc-sub" style={{ marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function MiniKpi({ label, k, enCurso }) {
  return <Mini valor={pctTexto(k)} label={label} sub={baseDe(k, enCurso)} extra={k?.muestra_pequena ? <> <Muestra k={k} /></> : null} />;
}

function MiniMediana({ label, e }) {
  return <Mini valor={e?.n ? num(e.mediana) : "Sin datos"} label={label} sub={e?.n ? `mediana · media ${num(e.media)} · N ${e.n}` : null} />;
}

// Color de un indicador de CALIDAD del dato (no de desempeño clínico).
const colorCalidad = (v) => (v === null || v === undefined ? undefined : v >= 80 ? VERDE : v >= 50 ? AMBAR : ROJO);

// Barras horizontales simples, sin librerías. Solo conteos. Las filas en cero
// van atenuadas: no compiten con las que tienen datos.
function Barras({ filas, series = [{ k: "n", t: "", color: "var(--accent)" }], valor }) {
  const total = (f) => series.reduce((s, x) => s + (f[x.k] || 0), 0);
  const max = Math.max(1, ...filas.map(total));
  return (
    <>
      {filas.map((f) => {
        const n = total(f);
        return (
          <div key={f.label} className={`dc-barra-fila${n ? "" : " cero"}`}>
            <span>{f.label}</span>
            <div className="dc-barra" aria-hidden="true">
              {series.map((x) => <span key={x.k} style={{ width: `${((f[x.k] || 0) / max) * 100}%`, background: x.color }} />)}
            </div>
            <span style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{valor ? valor(f, n) : n}</span>
          </div>
        );
      })}
      {series.length > 1 && (
        <div className="dc-leyenda">{series.map((x) => <span key={x.k}><i style={{ background: x.color }} />{x.t}</span>)}</div>
      )}
    </>
  );
}

// --- 1. Indicadores principales -------------------------------------------------

function KpiCard({ icono: Icono, titulo, valor, sub, tono, info }) {
  return (
    <div className={`dc-kpi${tono === "atencion" ? " atencion" : ""}`}>
      <div className="dc-kpi-cab"><Icono size={16} aria-hidden="true" /> {titulo}{info && <InfoTip texto={info} />}</div>
      <div className="dc-kpi-n">{valor}</div>
      {sub && <div className="dc-sub">{sub}</div>}
    </div>
  );
}

function Indicadores({ r, formal }) {
  const s12 = r.kpis.s1_s2;
  const sinProxima = formal?.kpis?.activos_sin_proxima_cita;
  const revision = formal?.revision?.total ?? 0;
  return (
    <div className="dc-kpis">
      <KpiCard icono={Activity} titulo="Procesos activos" valor={r.procesos_activos_hoy}
        sub={`hoy · ${r.procesos_iniciados} iniciados en el período`} />
      <KpiCard icono={ArrowRight} titulo="Continuidad S1 → S2" valor={pctTexto(s12)} info={TXT.evaluables}
        sub={<>{baseDe(s12)} {s12?.muestra_pequena && <Muestra k={s12} />}</>} />
      <KpiCard icono={CalendarX} titulo="Sin próxima cita" valor={sinProxima ? sinProxima.numerador : "Sin datos"}
        tono={sinProxima?.numerador ? "atencion" : undefined}
        sub={sinProxima ? `de ${sinProxima.denominador} activos hoy` : null} />
      {/* Neutral a propósito: el detalle con tono de atención es «Atención hoy», justo debajo. */}
      <KpiCard icono={ClipboardList} titulo="Para revisión" valor={revision} info={TXT.revision}
        sub="procesos con al menos una razón · detalle abajo" />
    </div>
  );
}

// --- 2. Atención hoy ------------------------------------------------------------

const RAZONES_VISIBLES = 6;

function AtencionHoy({ resumen, sede, showToast }) {
  const [lista, setLista] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [todas, setTodas] = useState(false);
  const conCasos = resumen.por_razon.filter((x) => x.n > 0).sort((a, b) => b.n - a.n);
  const sinCasos = resumen.por_razon.filter((x) => !x.n);
  const visibles = todas ? conCasos : conCasos.slice(0, RAZONES_VISIBLES);
  const verCasos = () => {
    if (lista) { setLista(null); return; }
    setCargando(true);
    api.continuidadRevision(sede)
      .then(setLista)
      .catch((e) => showToast?.("Error: " + e.message))
      .finally(() => setCargando(false));
  };
  return (
    <section className="dc-seccion" aria-labelledby="dc-atencion-t">
      <div className="dc-atencion">
        <div className="dc-titulo">
          <div>
            <h2 className="ca-secth" id="dc-atencion-t" style={{ margin: 0 }}>Atención hoy</h2>
            <div className="dc-sub" style={{ marginTop: 4 }}>Casos que requieren revisión o acción.</div>
          </div>
        </div>
        {conCasos.length === 0 ? (
          <div style={{ fontSize: 14, marginTop: 12 }}>No hay casos para revisar con estos filtros.</div>
        ) : (
          <div className="dc-razones">
            {visibles.map((x) => (
              <div key={x.clave} className="dc-razon"><b>{x.n}</b><span>{x.label}</span></div>
            ))}
          </div>
        )}
        {conCasos.length > RAZONES_VISIBLES && (
          <button className="ca-btn ghost dc-noprint" style={{ marginTop: 10 }} onClick={() => setTodas((v) => !v)}>
            {todas ? "Ver menos" : `Ver todos (${conCasos.length})`}
          </button>
        )}
        {sinCasos.length > 0 && (
          <div className="dc-ceros">
            Sin casos: {sinCasos.map((x, i) => (
              <span key={x.clave}><span className="dc-nowrap">{x.label}</span>{i < sinCasos.length - 1 ? " · " : ""}</span>
            ))}
          </div>
        )}
        <div className="dc-acciones dc-noprint">
          <button className="ca-btn" onClick={verCasos} disabled={cargando || !resumen.total} aria-expanded={!!lista}>
            {cargando ? "Cargando…" : lista ? "Ocultar casos" : `Ver casos (${resumen.total})`}
          </button>
          <span className="dc-sub">
            La lista solo filtra por sede. El abandono inferido sin registro entra si su última sesión es de los últimos 180 días.
          </span>
        </div>
        {lista && (
          <div className="dc-tabla" style={{ marginTop: 12 }}>
            <table className="ca-table">
              <thead><tr><th>Paciente</th><th>Psicólogo (S1)</th><th>Estado registrado</th><th className="num">Días sin sesión</th><th>Razones</th></tr></thead>
              <tbody>
                {lista.items.map((i) => (
                  <tr key={`${i.paciente_id}-${i.proceso || ""}-${i.dias_sin_sesion}`}>
                    <td>{i.paciente}</td>
                    <td>{i.psicologo}</td>
                    <td>{i.estado_formal}</td>
                    <td className="num">{i.dias_sin_sesion}</td>
                    <td style={{ fontSize: 12.5 }}>{i.razones.map((x) => x.label).join(" · ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {lista.mostrados < lista.resumen.total && <Nota>Se muestran {lista.mostrados} de {lista.resumen.total}.</Nota>}
          </div>
        )}
      </div>
    </section>
  );
}

// --- 3a. Continuidad del proceso --------------------------------------------------

function ContinuidadFlujo({ data, N }) {
  const r = data.resumen, kp = r.kpis;
  return (
    <div className="dc-panel dc-panel-ancho">
      <h3>Continuidad del proceso <InfoTip texto={TXT.evaluables} /></h3>
      <div className="dc-sub" style={{ marginTop: 4 }}>
        {r.procesos_iniciados} procesos iniciados en el período · {r.pacientes_nuevos} pacientes nuevos · {r.reingresos} reingresos
        {" "}· {r.activos_de_la_cohorte} aún activos · {r.terminados_de_la_cohorte} terminados
      </div>
      <div className="dc-flujo" role="list" aria-label="Procesos que llegan a cada sesión">
        {data.embudo.map((e) => (
          <FragmentoEtapa key={e.etapa} e={e} />
        ))}
      </div>
      <div className="dc-chips">
        <span className="dc-chip" title={baseDe(kp.s1_s3)}>S1 → S3 <b>{pctTexto(kp.s1_s3)}</b> <Muestra k={kp.s1_s3} /></span>
        <span className="dc-chip" title={baseDe(kp.s1_s6)}>Llegan a S6 <b>{pctTexto(kp.s1_s6)}</b> <Muestra k={kp.s1_s6} /></span>
        <span className="dc-chip" title={`${baseDe(kp.abandono_inferido, "aún activos")} · sobre procesos terminados`}>
          Abandono inferido <b>{pctTexto(kp.abandono_inferido)}</b> <InfoTip texto={TXT.inferido.replace("N días", `${N} días`)} />
        </span>
        {kp.abandono_confirmado && (
          <span className={`dc-chip${kp.abandono_confirmado.numerador ? "" : " cero"}`} title={`${baseDe(kp.abandono_confirmado, "aún activos")} · sobre procesos terminados`}>
            Abandono confirmado <b>{pctTexto(kp.abandono_confirmado)}</b>
          </span>
        )}
      </div>
      <Detalle resumen="Ver tabla completa del embudo">
        <div className="dc-tabla">
          <table className="ca-table">
            <thead>
              <tr>
                <th>Etapa</th>
                <th className="num" title="N: procesos que llegaron a esta sesión">Llegaron (N)</th>
                <th className="num">Aún en curso</th>
                <th className="num">Evaluables</th>
                <th className="num">Pasaron</th>
                <th className="num">Abandono inferido</th>
                <th className="num">Abandono confirmado</th>
                <th className="num">Alta / pausa / cierre / reinicio</th>
              </tr>
            </thead>
            <tbody>
              {data.embudo.map((e) => (
                <tr key={e.etapa}>
                  <td><strong>{e.etapa}</strong>{e.siguiente ? ` → ${e.siguiente}` : ""}</td>
                  <td className="num">{e.llegaron}</td>
                  {e.siguiente ? (
                    <>
                      <td className="num" style={{ color: "var(--muted)" }}>{e.en_curso}</td>
                      <td className="num">{e.evaluables} <Muestra k={e.kpi} /></td>
                      <td className="num">{e.pasaron} <span style={{ color: "var(--muted)" }}>({pctCelda(e.pct_paso)})</span></td>
                      <td className="num">{e.cayeron} <span style={{ color: "var(--muted)" }}>({pctCelda(e.pct_caida)})</span></td>
                      <td className="num">{e.cayeron_confirmado ?? 0} <span style={{ color: "var(--muted)" }}>({pctCelda(e.pct_caida_confirmado)})</span></td>
                      <td className="num">{e.otros_cierres} <span style={{ color: "var(--muted)" }}>({pctCelda(e.pct_otros_cierres)})</span></td>
                    </>
                  ) : <td colSpan={6} />}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Nota>
          S1, S2… es el orden de la sesión dentro del proceso (no el número escrito en la cita) y la consulta inicial no
          cuenta. Cada porcentaje es sobre sus evaluables (pasaron + terminaron en esa etapa); «aún en curso» queda fuera
          del denominador. El abandono inferido y el confirmado se miden sobre los procesos ya terminados.
        </Nota>
      </Detalle>
    </div>
  );
}

// Una etapa (S1…) y, a su derecha, el paso a la siguiente con su base.
function FragmentoEtapa({ e }) {
  const k = e.kpi;
  return (
    <>
      <div className="dc-etapa" role="listitem" aria-label={`${e.etapa}: ${e.llegaron} procesos`}>
        <small>{e.etapa}</small><b>{e.llegaron}</b>
      </div>
      {e.siguiente && (
        <div className={`dc-paso${k?.pct === null || k?.pct === undefined ? " sin" : ""}`}
          title={`${e.etapa} → ${e.siguiente}: ${baseDe(k)}`} aria-label={`Pasan de ${e.etapa} a ${e.siguiente}: ${pctTexto(k)}, ${baseDe(k)}`}>
          <ArrowRight size={14} aria-hidden="true" />
          <strong>{pctTexto(k)}</strong>
          <span className="dc-sub">{k?.denominador ? `${k.numerador} de ${k.denominador}` : "0 evaluables"}</span>
          {e.en_curso > 0 && <span className="dc-sub">{e.en_curso} en curso</span>}
          <Muestra k={k} />
        </div>
      )}
    </>
  );
}

// --- 3b. Ritmo entre sesiones -----------------------------------------------------

function RitmoSesiones({ data }) {
  const est = data.resumen.estadisticas;
  const g = est.dias_entre_sesiones;
  return (
    <div className="dc-panel">
      <h3>Ritmo entre sesiones</h3>
      <div className="dc-grande">{g?.n ? `Mediana: ${g.mediana} días` : "Sin datos"}</div>
      {g?.n > 0 && <div className="dc-sub">media {g.media} días · {g.n} intervalos entre sesiones seguidas</div>}
      <div style={{ marginTop: 10 }}>
        <Barras filas={data.distribuciones.dias_entre_sesiones} />
      </div>
      <Detalle resumen="Ver duración de los procesos">
        <div className="dc-mini-stats">
          <MiniMediana label="Sesiones por proceso terminado" e={est.sesiones_por_proceso_terminados} />
          <MiniMediana label="Sesiones por proceso (todos)" e={est.sesiones_por_proceso} />
          <MiniMediana label="Días de S1 a abandono inferido" e={est.dias_s1_a_abandono} />
        </div>
        <div style={{ marginTop: 12, fontWeight: 600, fontSize: 13 }}>Sesiones por proceso</div>
        <Barras filas={data.distribuciones.sesiones_por_proceso}
          series={[{ k: "terminados", t: "Terminados", color: "var(--accent)" }, { k: "activos", t: "Aún activos", color: "#9FD3DE" }]} />
        <Nota>
          La mediana es la cifra de referencia: un proceso muy largo mueve la media, no la mediana. En «todos» los activos
          siguen sumando sesiones; por eso se muestra aparte la de los terminados. «Días de S1 a abandono inferido» llega
          hasta su última sesión. Solo conteos, sin lectura clínica.
        </Nota>
      </Detalle>
    </div>
  );
}

// --- 3c. Estado registrado ------------------------------------------------------

function EstadoRegistrado({ data }) {
  const f = data.formal, r = data.resumen;
  if (!f) return null;
  const k = f.kpis, mot = f.motivos, rd = f.reactivaciones_desde;
  const con = k.con_estado_formal;
  const estados = [["Activo", k.activo], ["En pausa", k.pausa], ["Alta", k.alta],
    ["Abandono confirmado", k.abandono_confirmado], ["Cerrado por otra decisión", k.cerrado]];
  const pctDesconocidos = mot.total ? Math.round((mot.desconocidos / mot.total) * 1000) / 10 : null;
  return (
    <div className="dc-panel">
      <h3>Estado registrado <InfoTip texto={TXT.formal} /></h3>
      <div className="dc-grande">{con.numerador} de {con.denominador}</div>
      <div className="dc-sub">procesos del período tienen estado registrado · {con.denominador - con.numerador} sin estado formal</div>
      <div className="dc-chips">
        {estados.map(([label, x]) => (
          <span key={label} className={`dc-chip${x.numerador ? "" : " cero"}`}>{label} <b>{x.numerador}</b></span>
        ))}
      </div>
      <div className="dc-sub" style={{ marginTop: 10 }}>
        Desenlaces del período (registro o evidencia anterior): {r.altas_registradas} altas · {r.pausas ?? 0} pausas ·
        {" "}{r.cierres_registrados} otros cierres · {r.reinicios} reinicios
      </div>
      <Detalle resumen="Ver detalle: motivos, reactivaciones y frecuencia">
        <div className="dc-mini-stats">
          {estados.slice(1).map(([label, x]) => <MiniKpi key={label} label={label} k={x} enCurso="sin estado registrado" />)}
          <MiniKpi label="Reactivados tras una salida" k={k.reactivacion} />
          <Mini valor={rd.pausa + rd.abandono + rd.alta_o_cierre} label="Reactivaciones por origen"
            sub={`${rd.pausa} desde pausa · ${rd.abandono} desde abandono · ${rd.alta_o_cierre} desde alta o cierre`} />
          <MiniKpi label="Con cambio de profesional" k={k.cambio_profesional} />
          <MiniKpi label="Siguen en el centro tras el cambio" k={f.continuidad_centro_post_cambio.kpi} enCurso="aún sin sesión" />
          <MiniKpi label="Dentro de su frecuencia esperada" k={k.frecuencia_cumplida} enCurso="sin frecuencia definida" />
          <MiniKpi label="Registros con motivo conocido" k={k.motivos_conocidos} />
          <MiniKpi label="Sin continuidad registrada" k={k.sin_continuidad_registrada} enCurso="aún activos" />
        </div>
        <Nota>
          Los porcentajes de estado son sobre los procesos del período que tienen un estado registrado; los demás («sin
          estado registrado») van aparte, no como abandono. «Sin continuidad registrada» junta el abandono confirmado y el
          inferido solo para dimensionar lo que no tiene un desenlace registrado: no es una tasa de abandono. Un cambio de
          profesional no es abandono del primero: se mide si la persona siguió en el centro
          ({f.continuidad_centro_post_cambio.con_profesional_nuevo} con el profesional nuevo).
        </Nota>
        <div className="dc-motivos" style={{ marginTop: 14 }}>
          <div style={{ fontWeight: 600, fontSize: 13 }}>Motivos registrados · N {mot.total}</div>
          {!mot.total ? <div className="dc-sub" style={{ marginTop: 6 }}>Sin información: no hay registros con motivo en el período.</div> : (
            <>
              <Barras filas={[...mot.por_categoria.filter((c) => c.n).map((c) => ({ label: c.label, n: c.n, p: c.pct_sobre_conocidos })),
                { label: "Sin información", n: mot.desconocidos, p: pctDesconocidos }]}
                valor={(fila) => `${fila.n} · ${pctCelda(fila.p)}`} />
              <Nota>Porcentajes por categoría sobre los {mot.conocidos} motivos conocidos; «Sin información» sobre el total.</Nota>
              {mot.por_motivo.length > 0 && (
                <table className="ca-table" style={{ marginTop: 6 }}>
                  <tbody>
                    {mot.por_motivo.map((m) => (
                      <tr key={m.codigo}><td>{m.nombre}</td><td className="num">{m.n}</td><td className="num">{pctCelda(m.pct_sobre_conocidos)}</td></tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}
        </div>
        <div style={{ marginTop: 14 }}>
          <div style={{ fontWeight: 600, fontSize: 13 }}>Frecuencia esperada · activos hoy <InfoTip texto={TXT.frecuencia} /></div>
          <Barras filas={f.por_frecuencia} />
          <Nota>
            Ninguna frecuencia es mejor que otra. {f.por_frecuencia.reduce((a, x) => a + x.desde_ficha, 0)} vienen de la
            frecuencia anotada en la ficha (dato anterior), a falta de una registrada en el proceso.
          </Nota>
        </div>
      </Detalle>
    </div>
  );
}

// --- 4. Desglose -----------------------------------------------------------------

const PESTANAS = [
  { id: "psicologo", label: "Psicólogo", campo: "por_psicologo", primera: "Psicólogo",
    extra: [{ k: "sesiones_realizadas", t: "Sesiones en el período" }, { k: "carga_activos_hoy", t: "Carga activa hoy" }] },
  { id: "sede", label: "Sede", campo: "por_sede", primera: "Sede", extra: [] },
  { id: "categoria", label: "Categoría", campo: "por_categoria", primera: "Categoría", extra: [] },
  { id: "modalidad", label: "Modalidad", campo: "por_modalidad", primera: "Modalidad", extra: [] },
];

function notaDe(id, data) {
  if (id === "psicologo") {
    return `En orden alfabético, sin ranking: sirve para ver patrones, no para calificar a nadie. Una diferencia entre psicólogos puede venir de la población que atiende, la sede, la categoría o de qué tan completo está su registro. «Procesos» y las tasas son de los procesos iniciados en el período (psicólogo de la S1); «Sesiones en el período» se atribuye a quien atendió cada sesión (${data.sesiones_sin_psicologo_periodo} sesiones sin psicólogo). Con menos de ${data.filtros.muestra_pequena} evaluables se marca «muestra pequeña».`;
  }
  if (id === "sede") return "Sedes en orden fijo. Una diferencia entre sedes no dice cuál es «mejor»: cambian la población, el equipo y el registro.";
  if (id === "categoria") return "La categoría es la de la cita de la S1. Muchas citas importadas no la traen («Sin categoría»).";
  return "Modalidad del proceso según sus sesiones: si todas dicen lo mismo, esa; si hay presenciales y virtuales, «Mixta». «Presencial» también es el valor por defecto de una cita que nadie marcó, así que el faltante real puede ser mayor.";
}

function KpiCelda({ k }) {
  return (
    <td className="num" title={k ? baseDe(k) : ""}>
      {pctCelda(k?.pct)}
      <span className="dc-celda-sub">{k ? `${k.numerador}/${k.denominador}` : ""}{k?.muestra_pequena ? " · m. pequeña" : ""}</span>
    </td>
  );
}

function TablaGrupo({ filas, primera, extra, completa }) {
  if (!filas.length) return <div className="dc-sub" style={{ padding: "14px 0" }}>Sin procesos con estos filtros.</div>;
  return (
    <div className="dc-tabla">
      <table className="ca-table">
        <thead>
          <tr>
            <th>{primera}</th>
            <th className="num">Procesos</th>
            <th className="num">Activos</th>
            <th className="num" title={TXT.evaluables}>Continuidad S1→S2</th>
            <th className="num" title={TXT.evaluables}>S1→S3</th>
            <th className="num" title="Mediana de sesiones de los procesos iniciados (media debajo)">Mediana sesiones</th>
            {extra.map((c) => <th key={c.k} className="num">{c.t}</th>)}
            {completa && (
              <>
                <th className="num" title="Sobre los procesos ya terminados">Abandono inferido</th>
                <th className="num">Altas / cierres reg.</th>
                <th className="num" title="Pausa registrada (formal o ficha anterior)">Pausas</th>
                <th className="num" title="Registrado por una persona. No incluye el inferido.">Abandono confirmado</th>
                <th className="num" title="Procesos con al menos un cambio de profesional. No es abandono.">Cambios de prof.</th>
                <th className="num">Reactivados</th>
              </>
            )}
          </tr>
        </thead>
        <tbody>
          {filas.map((f) => (
            <tr key={f.clave}>
              <td>{f.label || f.psicologo}</td>
              <td className="num">{f.procesos}</td>
              <td className="num">{f.activos}</td>
              <KpiCelda k={f.kpis?.s1_s2} />
              <KpiCelda k={f.kpis?.s1_s3} />
              <td className="num">
                {f.mediana_sesiones ?? "—"}
                <span className="dc-celda-sub">media {f.promedio_sesiones ?? "—"}</span>
              </td>
              {extra.map((c) => <td key={c.k} className="num">{f[c.k] ?? "—"}</td>)}
              {completa && (
                <>
                  <KpiCelda k={f.kpis?.abandono_inferido} />
                  <td className="num">{f.altas_o_cierres ?? f.altas + f.cierres_registrados}</td>
                  <td className="num">{f.pausas ?? 0}</td>
                  <td className="num">{f.abandono_confirmado ?? 0}</td>
                  <td className="num">{f.cambios_profesional ?? 0}</td>
                  <td className="num">{f.reactivados ?? 0}</td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Desglose({ data }) {
  const [tab, setTab] = useState("psicologo");
  const [completa, setCompleta] = useState(false);
  const mover = (e) => {
    const i = PESTANAS.findIndex((p) => p.id === tab);
    const j = e.key === "ArrowRight" ? (i + 1) % PESTANAS.length : e.key === "ArrowLeft" ? (i + PESTANAS.length - 1) % PESTANAS.length : -1;
    if (j < 0) return;
    e.preventDefault();
    setTab(PESTANAS[j].id);
    document.getElementById(`dc-tab-${PESTANAS[j].id}`)?.focus();
  };
  return (
    <section className="dc-seccion" aria-labelledby="dc-desglose-t">
      <div className="dc-panel">
        <h2 className="ca-secth" id="dc-desglose-t" style={{ margin: "0 0 10px" }}>Desglose</h2>
        <div className="dc-tabs" role="tablist" aria-label="Desglose por dimensión" onKeyDown={mover}>
          {PESTANAS.map((p) => (
            <button key={p.id} id={`dc-tab-${p.id}`} role="tab" aria-selected={tab === p.id} aria-controls={`dc-panel-${p.id}`}
              tabIndex={tab === p.id ? 0 : -1} onClick={() => setTab(p.id)}>{p.label}</button>
          ))}
        </div>
        <div className="dc-tabla-cab dc-noprint">
          <span className="dc-sub">Orden alfabético o fijo, sin ranking.</span>
          <label className="dc-check">
            <input type="checkbox" checked={completa} onChange={(e) => setCompleta(e.target.checked)} />
            Mostrar todas las columnas
          </label>
        </div>
        {PESTANAS.map((p) => (
          <div key={p.id} id={`dc-panel-${p.id}`} role="tabpanel" aria-labelledby={`dc-tab-${p.id}`}
            className="dc-panel-tab" hidden={tab !== p.id}>
            <div className="dc-solo-impresion-titulo">Por {p.label.toLowerCase()}</div>
            <TablaGrupo filas={data[p.campo]} primera={p.primera} extra={p.extra} completa={completa} />
            <Nota>{notaDe(p.id, data)}</Nota>
          </div>
        ))}
      </div>
    </section>
  );
}

// --- 5. Calidad del dato y metodología -------------------------------------------

function CalidadDato({ data }) {
  const cal = data.calidad, kc = cal.kpis, r = data.resumen, uni = data.universo;
  const cf = data.formal?.calidad;
  const indicadores = [
    ["Psicólogo identificado", kc.sesiones_con_psicologo],
    ["N° de sesión", kc.sesiones_con_numero],
    ["Cierres con DP", kc.cierres_con_dp],
  ];
  return (
    <section className="dc-seccion" aria-label="Calidad del dato">
      <div className="dc-panel">
        <div className="dc-calidad-barra">
          <strong>Calidad del dato</strong>
          {indicadores.map(([label, k]) => (
            <span key={label} title={baseDe(k)}>
              {label}: <span className="dc-pct" style={{ color: colorCalidad(k.pct) }}>{pctTexto(k)}</span>
            </span>
          ))}
        </div>
        <Detalle resumen="Ver detalle de calidad del dato" id="dc-calidad">
          <div className="dc-stats-grid">
            <Mini valor={pctTexto(kc.sesiones_con_psicologo)} label="Sesiones con psicólogo identificado"
              sub={`${cal.sesiones_sin_psicologo} de ${cal.sesiones_periodo} sesiones sin psicólogo`} />
            <Mini valor={pctTexto(kc.sesiones_con_numero)} label="Sesiones con N° de sesión"
              sub={`${cal.sesiones_sin_numero} de ${cal.sesiones_periodo} sin número`} />
            <Mini valor={pctTexto(kc.cierres_con_dp)} label="Cierres de bloque con DP"
              sub={`${cal.cierres_sin_dp} de ${cal.cierres_bloque} sin DP (S6, S12…)`} />
            <Mini valor={pctTexto(kc.terminados_solo_inferidos)} label="Terminados solo por inferencia"
              sub={`${cal.terminados_solo_inferidos} de ${cal.procesos_terminados} terminados · ${cal.terminados_con_registro} con alta o cierre · ${cal.terminados_por_reinicio} por reinicio`} />
            <Mini valor={cal.procesos_sin_categoria} label="Procesos sin categoría" sub={`de ${r.procesos_iniciados} iniciados (categoría de la S1)`} />
            <Mini valor={cal.procesos_numeracion_inconsistente} label="Numeración inconsistente"
              sub={`de ${r.procesos_iniciados} procesos: el N° escrito bajó sin respaldo`} />
            <Mini valor={cal.sesiones_sin_modalidad} label="Sesiones sin modalidad"
              sub={`de ${cal.sesiones_periodo} · ${cal.procesos_sin_modalidad} procesos sin dato`} />
            <Mini valor={cal.sesiones_importadas_agendapro} label="Sesiones importadas de AgendaPro"
              sub={`${cal.sesiones_sistema_propio} registradas en el sistema propio`} />
            <Mini valor={cal.historicas_sin_psicologo} label="Sesiones históricas sin psicólogo"
              sub={`de ${cal.historicas_sesiones} anteriores al ${fechaCorta(uni.inicio_sistema_propio)} · solo filtra por sede`} />
          </div>
          <Nota>
            Todo se mide sobre los filtros elegidos (las sesiones históricas, solo por sede). El psicólogo de un proceso es
            quien atendió la S1; si la cita no lo dice se usa el asignado en la ficha ({cal.procesos_psicologo_por_ficha}{" "}
            procesos) y, si tampoco, queda en «Sin asignar» ({cal.procesos_sin_psicologo} procesos). La modalidad
            «presencial» es el valor por defecto de la cita, así que «sin modalidad» subestima el faltante real. «Importada
            de AgendaPro» se reconoce por la marca que dejó el importador en las notas.
          </Nota>
          {cf && (
            <>
              <div style={{ fontWeight: 600, fontSize: 13, marginTop: 16 }}>Calidad del registro formal</div>
              <div className="dc-stats-grid">
                <Mini valor={pctTexto(cf.procesos_sin_estado_formal)} label="Procesos sin estado registrado" sub={baseDe(cf.procesos_sin_estado_formal).replace(" evaluables", "")} />
                <Mini valor={cf.procesos_solo_inferencia} label="Solo con inferencia" sub="sin estado y con abandono inferido" />
                <Mini valor={cf.procesos_estado_legacy} label="Con estado de evidencia anterior" sub="DP o ficha, sin registro formal" />
                <Mini valor={cf.procesos_estado_importado} label="Estados de la carga histórica" sub="registrados por la importación" />
                <Mini valor={pctTexto(cf.vigentes_sin_frecuencia)} label="Activos sin frecuencia esperada" sub={baseDe(cf.vigentes_sin_frecuencia).replace(" evaluables", "")} />
                <Mini valor={cf.motivos_desconocidos} label="Motivos «Sin información»" sub="en el período" />
                <Mini valor={cf.cambios_sin_sesion_posterior} label="Cambios de profesional sin sesión posterior" sub="más de 14 días" />
                <Mini valor={cf.requieren_revision} label="Procesos para revisar su identidad" sub="la reconciliación no los pudo ubicar" />
              </div>
            </>
          )}
          <div style={{ fontWeight: 600, fontSize: 13, marginTop: 16 }}>De dónde salen estos datos</div>
          <div style={{ fontSize: 13, lineHeight: 1.6, marginTop: 6 }}>
            <div><strong>Fuente:</strong> {uni.fuente}</div>
            <div><strong>Primera sesión con cita en la base:</strong> {fechaCorta(uni.desde)} · {uni.procesos_totales} procesos en total ({uni.procesos_filtrados} con estos filtros, de cualquier fecha).</div>
            <div>
              <strong>Procesos de este período:</strong> {uni.cohorte_agendapro} empezaron antes del {fechaCorta(uni.inicio_sistema_propio)}
              {" "}(época AgendaPro) y {uni.cohorte_sistema_propio} en el sistema propio; {uni.cohorte_s1_importada} tienen su S1 marcada como importada.
            </div>
            <div style={{ marginTop: 6, color: "var(--ink-soft)" }}>
              {uni.fichas_sin_cita} fichas clínicas no tienen cita asociada —en su mayoría las sesiones del Excel de 2024 a
              febrero de 2026— y no entran en estos cálculos: sin cita no hay estado de asistencia ni orden confiable.
            </div>
          </div>
        </Detalle>
      </div>
    </section>
  );
}

function Metodologia({ N, muestra }) {
  return (
    <details className="dc-det dc-panel" id="dc-metodologia" style={{ marginTop: 16, borderTop: "1px solid var(--line)" }}>
      <summary>Metodología y criterios</summary>
      <div className="dc-det-cuerpo" style={{ fontSize: 13.5, lineHeight: 1.6 }}>
        <p><strong>Proceso.</strong> Un tramo de sesiones realizadas (citas asistidas o atendidas, sin la consulta inicial)
          de un paciente, según la misma regla del Centro de Continuidad. S1, S2… es el orden de la sesión dentro del proceso.</p>
        <p><strong>Abandono inferido no es abandono confirmado.</strong> Un proceso entra en el inferido cuando su última
          sesión fue hace más de {N} días, no tiene próxima cita y no tiene alta ni cierre registrado (registro formal, DP-10,
          otro DP de cierre o la ficha en «alta» / «en pausa»). Puede incluir altas que nadie registró: sirve para ver
          <em> dónde</em> se cortan los procesos, no para afirmar <em>por qué</em>. El abandono confirmado es el que una
          persona registró en el proceso. Nunca se suman como «abandono».</p>
        <p><strong>Evaluables y «aún en curso».</strong> Cada tasa se calcula sobre los procesos cuyo hito ya está resuelto
          (lo alcanzaron o ya terminaron). Los activos que todavía no llegan quedan fuera: contarlos como caída inflaría el
          abandono. Un proceso terminado es uno con abandono (inferido o confirmado), alta, pausa, cierre o reinicio.</p>
        <p><strong>Muestra pequeña.</strong> Con menos de {muestra} evaluables se marca «muestra pequeña»: es una regla técnica,
          no un juicio.</p>
        <p><strong>Estado registrado.</strong> Lo que alguien registró en el proceso (app de continuidad). Los procesos
          anteriores al registro formal quedan «sin estado formal»; la evidencia anterior (DP o ficha) se muestra como tal.</p>
        <p><strong>Psicólogo.</strong> El de la S1; si la cita no lo dice, el asignado en la ficha; si tampoco, «Sin asignar».
          Las sesiones del período se atribuyen a quien atendió cada una.</p>
        <p><strong>Modalidad.</strong> La del proceso según sus sesiones («Mixta» si hay de las dos). «Presencial» es el valor
          por defecto de la cita, así que el faltante real puede ser mayor.</p>
        <p style={{ marginBottom: 0 }}><strong>Mediana.</strong> Es la cifra de referencia; la media y el N van al lado.
          Detalle completo en docs/direccion-clinica.md y docs/continuidad-metricas.md.</p>
      </div>
    </details>
  );
}

// Al imprimir se despliegan todos los detalles (y se vuelven a plegar los que
// estaban plegados): una hoja sin el detalle no se puede leer. La marca va en
// el propio elemento, porque el navegador puede avisar "antes de imprimir" más
// de una vez y una lista en memoria se perdería en el segundo aviso.
function useImpresionCompleta() {
  useEffect(() => {
    const antes = () => {
      document.querySelectorAll(".dc-pagina details:not([open])").forEach((d) => {
        d.dataset.dcImpresion = "1";
        d.open = true;
      });
    };
    const despues = () => {
      document.querySelectorAll(".dc-pagina details[data-dc-impresion]").forEach((d) => {
        d.open = false;
        delete d.dataset.dcImpresion;
      });
    };
    window.addEventListener("beforeprint", antes);
    window.addEventListener("afterprint", despues);
    return () => {
      window.removeEventListener("beforeprint", antes);
      window.removeEventListener("afterprint", despues);
    };
  }, []);
}

// --- Pantalla ---------------------------------------------------------------------

export default function DireccionClinica({ showToast }) {
  const [f, setF] = useState(filtrosDeUrl);
  const [dias, setDias] = useState(String(f.dias_abandono));
  const [rango, setRango] = useState({ desde: f.desde, hasta: f.hasta });
  const [errorRango, setErrorRango] = useState("");
  const [data, setData] = useState(null);
  const [errorApi, setErrorApi] = useState("");
  // Para qué filtros es lo que está en pantalla: "cargando" es que no coincidan.
  const [listoPara, setListoPara] = useState(null);
  // El período "rango" sin fechas todavía no consulta: se sigue viendo lo anterior.
  const rangoPendiente = f.periodo === "rango" && !f.desde && !f.hasta;
  const clave = rangoPendiente ? null : JSON.stringify(paraApi(f));
  const cargando = clave !== null && listoPara !== clave;
  const avisar = useRef(showToast);
  useEffect(() => { avisar.current = showToast; });
  useImpresionCompleta();

  // La URL refleja los filtros (al entrar se normaliza sin sumar historial).
  useEffect(() => {
    window.history.replaceState(window.history.state, "", urlDeFiltros(f));
    const atras = () => {
      const g = filtrosDeUrl();
      setF(g);
      setDias(String(g.dias_abandono));
      setRango({ desde: g.desde, hasta: g.hasta });
      setErrorRango("");
    };
    window.addEventListener("popstate", atras);
    return () => window.removeEventListener("popstate", atras);
    // Solo al montar: después, cada cambio de filtro empuja su propia entrada.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (clave === null) return undefined;
    let vivo = true;
    api.direccionClinica(JSON.parse(clave))
      .then((d) => { if (vivo) { setData(d); setErrorApi(""); } })
      .catch((e) => {
        if (!vivo) return;
        setErrorApi(e.message);
        avisar.current?.("Error: " + e.message);
      })
      .finally(() => { if (vivo) setListoPara(clave); });
    return () => { vivo = false; };
  }, [clave]);

  const aplicar = (g) => {
    if (JSON.stringify(g) === JSON.stringify(f)) return;
    setF(g);
    window.history.pushState(window.history.state, "", urlDeFiltros(g));
  };
  const set = (k, v) => aplicar({ ...f, [k]: v });
  const elegirPeriodo = (p) => {
    setErrorRango("");
    if (p === "rango") {
      // Abre el selector; no consulta hasta que haya fechas válidas.
      setF((x) => ({ ...x, periodo: "rango" }));
      return;
    }
    aplicar({ ...f, periodo: p, desde: "", hasta: "" });
  };
  const aplicarRango = () => {
    const { desde, hasta } = rango;
    if (!desde && !hasta) return setErrorRango("Elige al menos una fecha.");
    if (desde && hasta && desde > hasta) return setErrorRango("«Desde» no puede ser posterior a «hasta».");
    setErrorRango("");
    aplicar({ ...f, periodo: "rango", desde, hasta });
  };
  const aplicarDias = () => {
    const n = parseInt(dias, 10);
    if (Number.isFinite(n) && n !== f.dias_abandono) set("dias_abandono", n);
  };
  const limpiar = () => {
    setDias(String(DEFECTO.dias_abandono));
    setRango({ desde: "", hasta: "" });
    setErrorRango("");
    aplicar({ ...DEFECTO });
  };
  const abrirMetodologia = () => {
    const d = document.getElementById("dc-metodologia");
    if (!d) return;
    d.open = true;
    d.scrollIntoView({ behavior: "smooth", block: "start" });
    d.querySelector("summary")?.focus();
  };

  const op = data?.filtros?.opciones;
  const r = data?.resumen;
  const N = data?.filtros?.dias_abandono ?? f.dias_abandono;

  // Qué filtros tiene aplicado lo mostrado (y lo impreso: una hoja sin esto no se puede leer).
  const etiquetaDe = (lista, c, todos) => (c ? (lista || []).find((x) => x.clave === c)?.label || c : todos);
  const filtrosTexto = data ? [
    `Período: ${data.periodo.label}${data.periodo.desde ? ` (${fechaCorta(data.periodo.desde)} – ${fechaCorta(data.periodo.hasta)})` : ""}`,
    `Sede: ${SEDES.find(([v]) => v === data.filtros.sede)?.[1] || "Todas"}`,
    `Psicólogo: ${etiquetaDe(op?.psicologos, data.filtros.psicologo, "Todos")}`,
    `Categoría: ${etiquetaDe(op?.categorias, data.filtros.categoria, "Todas")}`,
    `Modalidad: ${etiquetaDe(op?.modalidades, data.filtros.modalidad, "Todas")}`,
    `Etapa: ${data.filtros.etapa ? `va en S${data.filtros.etapa}` : "Todas"}`,
    `Abandono inferido tras ${N} días`,
  ].join(" · ") : "";

  return (
    <div className="dc-pagina">
      <style>{ESTILOS}</style>
      <div className="dc-solo-impresion" style={{ marginBottom: 14, paddingBottom: 10, borderBottom: "1px solid var(--line)" }}>
        <div style={{ fontSize: 11, color: "var(--muted)" }}>
          Ítaca Conversemos · Documento interno · Generado el {new Date().toLocaleDateString("es-PE")} a las{" "}
          {new Date().toLocaleTimeString("es-PE", { hour: "2-digit", minute: "2-digit" })}
        </div>
        <div style={{ fontSize: 12, marginTop: 4 }}>{filtrosTexto}</div>
      </div>

      {/* --- Cabecera --- */}
      <div className="ca-tophead">
        <div>
          <h1 className="ca-h1">Dirección Clínica</h1>
          <div className="ca-sub">
            Continuidad y seguimiento de procesos
            {data ? <span style={{ color: "var(--muted)" }}> · {data.periodo.label}</span> : null}
          </div>
        </div>
        <div className="dc-noprint" style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <button className="ca-btn ghost" onClick={abrirMetodologia} disabled={!data}>
            <Info size={15} aria-hidden="true" /> Metodología
          </button>
          {!esDefecto(f) && (
            <button className="ca-btn ghost" onClick={limpiar} title="Volver a los filtros por defecto">
              <RotateCcw size={15} aria-hidden="true" /> Limpiar filtros
            </button>
          )}
          <button className="ca-btn" onClick={() => window.print()} disabled={!data}
            title="Imprimir o guardar como PDF (en el cuadro de impresión, elige «Guardar como PDF»)">
            <Printer size={15} aria-hidden="true" /> Imprimir / PDF
          </button>
        </div>
      </div>

      {/* --- Filtros --- */}
      <div className="dc-noprint">
        <div className="dc-filtros">
          <div className="ca-seg" role="group" aria-label="Período">
            {[...Object.entries(PERIODOS_CORTOS), ["rango", "Rango…"]].map(([v, l]) => (
              <button key={v} className={f.periodo === v ? "on" : ""} aria-pressed={f.periodo === v} onClick={() => elegirPeriodo(v)}>{l}</button>
            ))}
          </div>
          <div className="ca-seg" role="group" aria-label="Sede">
            {SEDES.map(([v, l]) => (
              <button key={v || "todas"} className={f.sede === v ? "on" : ""} aria-pressed={f.sede === v} onClick={() => set("sede", v)}>{l}</button>
            ))}
          </div>
          <select className="ca-input" aria-label="Psicólogo" value={f.psicologo} onChange={(e) => set("psicologo", e.target.value)}>
            <option value="">Todos los psicólogos</option>
            {(op?.psicologos || []).map((p) => <option key={p.clave} value={p.clave}>{p.label}</option>)}
          </select>
          <select className="ca-input" aria-label="Categoría" value={f.categoria} onChange={(e) => set("categoria", e.target.value)}>
            <option value="">Todas las categorías</option>
            {(op?.categorias || []).map((c) => <option key={c.clave} value={c.clave}>{c.label}</option>)}
          </select>
          <select className="ca-input" aria-label="Modalidad" value={f.modalidad} onChange={(e) => set("modalidad", e.target.value)}>
            <option value="">Todas las modalidades</option>
            {(op?.modalidades || []).map((m) => <option key={m.clave} value={m.clave}>{m.label}</option>)}
          </select>
          <select className="ca-input" aria-label="Etapa" value={f.etapa} onChange={(e) => set("etapa", e.target.value)}>
            <option value="">Todas las etapas</option>
            {(op?.etapas || []).map((x) => <option key={x.clave} value={x.clave}>Va en {x.label}</option>)}
          </select>
          <label className="dc-dias" title={TXT.inferido.replace("N días", "estos días")}>
            Abandono inferido tras
            <input className="ca-input" type="number" min={15} max={365} value={dias} aria-label="Días para abandono inferido"
              onChange={(e) => setDias(e.target.value)} onBlur={aplicarDias}
              onKeyDown={(e) => e.key === "Enter" && aplicarDias()} />
            días
          </label>
        </div>
        {f.periodo === "rango" && (
          <div className="dc-rango">
            <label>Desde <input className="ca-input" type="date" value={rango.desde}
              onChange={(e) => setRango((x) => ({ ...x, desde: e.target.value }))} /></label>
            <label>Hasta <input className="ca-input" type="date" value={rango.hasta}
              onChange={(e) => setRango((x) => ({ ...x, hasta: e.target.value }))} /></label>
            <button className="ca-btn" onClick={aplicarRango}>Aplicar rango</button>
            {errorRango && <span className="dc-error" role="alert">{errorRango}</span>}
            {rangoPendiente && !errorRango && <span>Elige las fechas y aplica.</span>}
          </div>
        )}
        {data && <div className="dc-activos">{filtrosTexto}</div>}
      </div>

      {!data ? (
        <div className="ca-empty" style={{ marginTop: 20 }}>{cargando ? "Cargando…" : errorApi || "Sin datos."}</div>
      ) : (
        <div style={{ opacity: cargando ? 0.55 : 1, transition: "opacity .15s" }} aria-busy={cargando}>
          {errorApi && !cargando && (
            <div className="ca-card dc-error" style={{ marginTop: 14 }} role="alert">
              No se pudo aplicar el filtro: {errorApi}. Se muestran los datos anteriores.
            </div>
          )}

          {/* 1. Cuatro indicadores */}
          <Indicadores r={r} formal={data.formal} />

          {/* 2. Atención hoy */}
          {data.formal && <AtencionHoy resumen={data.formal.revision} sede={data.filtros.sede} showToast={showToast} />}

          {/* 3. Lectura rápida */}
          {data.vacio ? (
            <div className="dc-panel dc-seccion" style={{ textAlign: "center", padding: "28px 18px" }}>
              <div style={{ fontWeight: 600 }}>No hay procesos que empiecen en este período con estos filtros.</div>
              <div className="dc-sub" style={{ marginTop: 6 }}>
                Prueba un período más amplio o quita algún filtro. Procesos activos hoy con estos filtros
                (empezaran cuando empezaran): {r.procesos_activos_hoy}.
              </div>
              {!esDefecto(f) && (
                <button className="ca-btn dc-noprint" style={{ marginTop: 14 }} onClick={limpiar}>
                  <RotateCcw size={15} aria-hidden="true" /> Limpiar filtros
                </button>
              )}
            </div>
          ) : (
            <>
              <section className="dc-seccion" aria-label="Lectura rápida">
                <div className="dc-lectura">
                  <ContinuidadFlujo data={data} N={N} />
                  <RitmoSesiones data={data} />
                  <EstadoRegistrado data={data} />
                </div>
              </section>

              {/* 4. Desglose */}
              <Desglose data={data} />
            </>
          )}

          {/* 5. Calidad del dato y metodología */}
          <CalidadDato data={data} />
          <Metodologia N={N} muestra={data.filtros.muestra_pequena} />
        </div>
      )}
    </div>
  );
}
