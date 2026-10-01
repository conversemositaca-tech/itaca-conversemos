// Dirección Clínica → continuidad y abandono inferido de los procesos.
//
// Solo lectura. Todo sale de /api/direccion-clinica/ (core/direccion_clinica.py),
// que reconstruye los procesos con la misma regla del Centro de Continuidad.
// Definiciones y límites: docs/direccion-clinica.md.
//
// Tres cosas que esta pantalla NO hace, a propósito:
// - No llama "abandono" a lo que no lo es: hoy no existe un estado formal de
//   abandono y casi ningún cierre tiene su código DP. Se dice "abandono
//   inferido" en todos lados, con su definición a la vista.
// - No ordena a los psicólogos por desempeño. La tabla va en orden alfabético
//   y sin colores de bueno/malo: sirve para ver patrones, no para calificar.
// - No muestra un porcentaje sin su base: cada tasa va con numerador,
//   denominador (los evaluables) y cuántos siguen «aún en curso».
//
// Los filtros viven en la URL (/gestion?vista=direccion&sede=piura…): recargar,
// compartir el enlace o volver atrás conserva lo que se estaba mirando.
import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Printer, RotateCcw } from "lucide-react";
import { api } from "./api";

const SEDES = [["", "Todas"], ["lima", "Lima"], ["piura", "Piura"]];
const ROJO = "#B4564E", AMBAR = "#C9923A", VERDE = "#4F8A77";

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
// está abierta (body:has(.dc-pagina)), así que no cambian cómo se imprime
// ninguna otra parte del sistema.
const ESTILOS = `
.dc-solo-impresion { display:none; }
.dc-pagina .ca-stats { margin-bottom:0; }
.dc-filtros { display:flex; gap:10px; flex-wrap:wrap; align-items:center; margin-top:14px; }
.dc-filtros .ca-seg { margin-left:0; max-width:100%; overflow-x:auto; }
.dc-filtros .ca-seg button { white-space:nowrap; flex-shrink:0; }
.dc-filtros select.ca-input { width:auto; max-width:100%; padding:6px 10px; }
.dc-rango { display:flex; gap:8px; flex-wrap:wrap; align-items:center; font-size:13px; color:var(--ink-soft); }
.dc-rango input { width:auto; padding:6px 8px; }
.dc-error { color:${ROJO}; font-size:12.5px; }
.dc-activos { font-size:12.5px; color:var(--muted); margin-top:10px; line-height:1.5; }
.dc-kpi-sub { font-size:12px; color:var(--muted); margin-top:2px; line-height:1.4; }
.dc-muestra { display:inline-block; font-size:10.5px; color:var(--ink-soft); background:var(--hover);
  border-radius:5px; padding:0 5px; margin-left:4px; white-space:nowrap; font-weight:500; }
.dc-celda-sub { display:block; font-size:11px; color:var(--muted); white-space:nowrap; }
.dc-dist { display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:14px; }
.dc-barra-fila { display:grid; grid-template-columns:84px 1fr 64px; gap:8px; align-items:center; font-size:12.5px; margin-top:6px; }
.dc-barra { height:10px; background:var(--hover); border-radius:5px; overflow:hidden; display:flex; }
.dc-barra span { display:block; height:100%; }
.dc-leyenda { display:flex; gap:12px; font-size:11.5px; color:var(--muted); margin-top:8px; flex-wrap:wrap; }
.dc-leyenda i { display:inline-block; width:9px; height:9px; border-radius:2px; margin-right:4px; vertical-align:-1px; }
@media (max-width:640px) {
  .dc-pagina .ca-tophead { flex-wrap:wrap; }
  .dc-pagina .ca-stat { min-width:140px; }
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
  .dc-pagina .ca-card { overflow:visible !important; box-shadow:none !important; break-inside:avoid; }
  .dc-pagina .ca-stat { box-shadow:none !important; break-inside:avoid; }
  .dc-pagina .ca-secth { break-after:avoid; margin-top:18px !important; }
  .dc-pagina .ca-stats { gap:8px !important; }
  .dc-pagina .ca-stat-n { font-size:22px !important; }
  .dc-pagina table { width:100%; font-size:10.5px; }
  .dc-pagina th, .dc-pagina td { padding:5px 6px !important; }
  .dc-pagina tr { break-inside:avoid; }
  .dc-tabla-larga { break-inside:auto !important; }
}`;

const pct = (v) => (v === null || v === undefined ? "—" : `${v}%`);
const num = (v) => (v === null || v === undefined ? "—" : v);
const fechaCorta = (iso) => (iso ? iso.split("-").reverse().join("/") : "—");

function Stat({ label, valor, sub, color }) {
  return (
    <div className="ca-stat">
      <div className="ca-stat-n" style={color ? { color } : undefined}>{valor}</div>
      <div className="ca-stat-l">{label}</div>
      {sub && <div className="dc-kpi-sub">{sub}</div>}
    </div>
  );
}

function Muestra({ k }) {
  return k?.muestra_pequena
    ? <span className="dc-muestra" title="Menos de 10 evaluables: un caso más o menos mueve mucho la cifra.">muestra pequeña</span>
    : null;
}

// Una tasa con su base: «43 de 56 evaluables · 2 aún en curso».
function baseDe(k, enCurso = "aún en curso") {
  if (!k) return "";
  if (!k.denominador) return k.no_evaluables ? `sin evaluables · ${k.no_evaluables} ${enCurso}` : "sin evaluables";
  const partes = [`${k.numerador} de ${k.denominador} evaluables`];
  if (k.no_evaluables) partes.push(`${k.no_evaluables} ${enCurso}`);
  return partes.join(" · ");
}

function StatKpi({ label, k, enCurso, color }) {
  return (
    <Stat label={<>{label}<Muestra k={k} /></>} valor={pct(k?.pct)} sub={baseDe(k, enCurso)} color={color} />
  );
}

function StatMediana({ label, e, unidad = "" }) {
  return (
    <Stat label={label} valor={num(e?.mediana)}
      sub={e?.n ? `mediana${unidad} · media ${num(e.media)} · N ${e.n}` : "sin datos"} />
  );
}

// Celda de tabla para una tasa: % arriba, «num/den» abajo.
function KpiCelda({ k }) {
  return (
    <td className="num" title={k ? baseDe(k) : ""}>
      {pct(k?.pct)}
      <span className="dc-celda-sub">{k ? `${k.numerador}/${k.denominador}` : ""}{k?.muestra_pequena ? " · m. pequeña" : ""}</span>
    </td>
  );
}

// Color de un indicador de CALIDAD del dato (no de desempeño clínico).
const colorCalidad = (v) => (v === null || v === undefined ? undefined : v >= 80 ? VERDE : v >= 50 ? AMBAR : ROJO);

function Nota({ children }) {
  return <div style={{ fontSize: 12.5, color: "var(--muted)", marginTop: 6, lineHeight: 1.5 }}>{children}</div>;
}

function TablaGrupo({ filas, primera, extra = [] }) {
  if (!filas.length) return <div className="ca-empty">Sin procesos con estos filtros.</div>;
  return (
    <div className="ca-card dc-tabla-larga" style={{ overflowX: "auto", padding: 0 }}>
      <table className="ca-table">
        <thead>
          <tr>
            <th>{primera}</th>
            {extra.map((c) => <th key={c.k} className="num">{c.t}</th>)}
            <th className="num">Procesos</th>
            <th className="num">Activos</th>
            <th className="num" title="Sobre los procesos con el paso resuelto (pasaron o ya terminaron)">S1→S2</th>
            <th className="num" title="Sobre los procesos con el paso resuelto (pasaron o ya terminaron)">S1→S3</th>
            <th className="num" title="Mediana de sesiones de los procesos iniciados (media entre paréntesis)">Mediana sesiones</th>
            <th className="num" title="Sobre los procesos ya terminados">Abandono inferido</th>
            <th className="num">Altas / cierres reg.</th>
          </tr>
        </thead>
        <tbody>
          {filas.map((f) => (
            <tr key={f.clave}>
              <td>{f.label || f.psicologo}</td>
              {extra.map((c) => <td key={c.k} className="num">{num(f[c.k])}</td>)}
              <td className="num">{f.procesos}</td>
              <td className="num">{f.activos}</td>
              <KpiCelda k={f.kpis?.s1_s2} />
              <KpiCelda k={f.kpis?.s1_s3} />
              <td className="num">
                {num(f.mediana_sesiones)}
                <span className="dc-celda-sub">media {num(f.promedio_sesiones)}</span>
              </td>
              <KpiCelda k={f.kpis?.abandono_inferido} />
              <td className="num">{f.altas_o_cierres ?? f.altas + f.cierres_registrados}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Barras horizontales simples, sin librerías. Solo conteos.
function Distribucion({ titulo, filas, series, nota }) {
  const max = Math.max(1, ...filas.map((f) => series.reduce((s, x) => s + (f[x.k] || 0), 0)));
  const total = filas.reduce((s, f) => s + series.reduce((a, x) => a + (f[x.k] || 0), 0), 0);
  return (
    <div className="ca-card">
      <div style={{ fontWeight: 600, fontSize: 14 }}>{titulo} <span style={{ color: "var(--muted)", fontWeight: 400 }}>· N {total}</span></div>
      {filas.map((f) => {
        const n = series.reduce((s, x) => s + (f[x.k] || 0), 0);
        return (
          <div key={f.label} className="dc-barra-fila">
            <span>{f.label}</span>
            <div className="dc-barra" aria-hidden="true">
              {series.map((x) => <span key={x.k} style={{ width: `${((f[x.k] || 0) / max) * 100}%`, background: x.color }} />)}
            </div>
            <span className="num" style={{ textAlign: "right" }}>{n}</span>
          </div>
        );
      })}
      {series.length > 1 && (
        <div className="dc-leyenda">{series.map((x) => <span key={x.k}><i style={{ background: x.color }} />{x.t}</span>)}</div>
      )}
      {nota && <Nota>{nota}</Nota>}
    </div>
  );
}

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

  const op = data?.filtros?.opciones;
  const r = data?.resumen, cal = data?.calidad, uni = data?.universo;
  const kp = r?.kpis, est = r?.estadisticas, kc = cal?.kpis;
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
      <div className="ca-tophead">
        <div>
          <h1 className="ca-h1">Dirección Clínica</h1>
          <div className="ca-sub">
            Continuidad y abandono inferido de los procesos
            {data ? ` · ${data.periodo.label}` : ""}
          </div>
        </div>
        <div className="dc-noprint" style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          {!esDefecto(f) && (
            <button className="ca-btn" onClick={limpiar} title="Volver a los filtros por defecto">
              <RotateCcw size={15} /> Limpiar filtros
            </button>
          )}
          <button className="ca-btn" onClick={() => window.print()} disabled={!data}
            title="Imprimir o guardar como PDF (en el cuadro de impresión, elige «Guardar como PDF»)">
            <Printer size={15} /> Imprimir / PDF
          </button>
        </div>
      </div>

      <div className="dc-noprint">
        <div className="dc-filtros">
          <div className="ca-seg" role="group" aria-label="Período">
            {[...Object.entries(PERIODOS_CORTOS), ["rango", "Rango…"]].map(([v, l]) => (
              <button key={v} className={f.periodo === v ? "on" : ""} onClick={() => elegirPeriodo(v)}>{l}</button>
            ))}
          </div>
          <div className="ca-seg" role="group" aria-label="Sede">
            {SEDES.map(([v, l]) => (
              <button key={v || "todas"} className={f.sede === v ? "on" : ""} onClick={() => set("sede", v)}>{l}</button>
            ))}
          </div>
        </div>
        {f.periodo === "rango" && (
          <div className="dc-rango" style={{ marginTop: 10 }}>
            <label>Desde <input className="ca-input" type="date" value={rango.desde}
              onChange={(e) => setRango((x) => ({ ...x, desde: e.target.value }))} /></label>
            <label>Hasta <input className="ca-input" type="date" value={rango.hasta}
              onChange={(e) => setRango((x) => ({ ...x, hasta: e.target.value }))} /></label>
            <button className="ca-btn" onClick={aplicarRango}>Aplicar rango</button>
            {errorRango && <span className="dc-error" role="alert">{errorRango}</span>}
            {rangoPendiente && !errorRango && <span>Elige las fechas y aplica.</span>}
          </div>
        )}
        <div className="dc-filtros">
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
          <label style={{ fontSize: 13, color: "var(--ink-soft)", display: "flex", alignItems: "center", gap: 6 }}>
            Abandono inferido tras
            <input className="ca-input" type="number" min={15} max={365} value={dias}
              onChange={(e) => setDias(e.target.value)} onBlur={aplicarDias}
              onKeyDown={(e) => e.key === "Enter" && aplicarDias()}
              style={{ width: 70, padding: "6px 8px" }} />
            días
          </label>
        </div>
        {data && <div className="dc-activos">{filtrosTexto}</div>}
      </div>

      {!data ? (
        <div className="ca-empty">{cargando ? "Cargando…" : errorApi || "Sin datos."}</div>
      ) : (
        <div style={{ opacity: cargando ? 0.5 : 1, transition: "opacity .15s" }}>
          {errorApi && !cargando && (
            <div className="ca-card dc-error" style={{ marginTop: 14 }} role="alert">
              No se pudo aplicar el filtro: {errorApi}. Se muestran los datos anteriores.
            </div>
          )}

          {/* --- Calidad del dato: arriba de todo, antes de cualquier cifra --- */}
          <div className="ca-card" style={{ marginTop: 18, borderLeft: `4px solid ${AMBAR}` }}>
            <div style={{ display: "flex", gap: 8, alignItems: "center", fontWeight: 600 }}>
              <AlertTriangle size={17} color={AMBAR} /> Calidad del dato · léela antes de decidir
            </div>
            <div className="ca-stats" style={{ marginTop: 12 }}>
              <Stat label="Sesiones con psicólogo identificado" valor={pct(kc.sesiones_con_psicologo.pct)}
                sub={`${cal.sesiones_sin_psicologo} de ${cal.sesiones_periodo} sesiones sin psicólogo`}
                color={colorCalidad(kc.sesiones_con_psicologo.pct)} />
              <Stat label="Sesiones con N° de sesión" valor={pct(kc.sesiones_con_numero.pct)}
                sub={`${cal.sesiones_sin_numero} de ${cal.sesiones_periodo} sin número`}
                color={colorCalidad(kc.sesiones_con_numero.pct)} />
              <Stat label="Cierres de bloque con DP" valor={pct(kc.cierres_con_dp.pct)}
                sub={`${cal.cierres_sin_dp} de ${cal.cierres_bloque} sin DP (S6, S12…)`}
                color={colorCalidad(kc.cierres_con_dp.pct)} />
              <Stat label="Terminados solo por inferencia" valor={pct(kc.terminados_solo_inferidos.pct)}
                sub={`${cal.terminados_solo_inferidos} de ${cal.procesos_terminados} terminados · ${cal.terminados_con_registro} con alta o cierre · ${cal.terminados_por_reinicio} por reinicio`} />
            </div>
            <div className="ca-stats" style={{ marginTop: 10 }}>
              <Stat label="Procesos sin categoría" valor={cal.procesos_sin_categoria}
                sub={`de ${r.procesos_iniciados} iniciados (categoría de la S1)`} />
              <Stat label="Numeración inconsistente" valor={cal.procesos_numeracion_inconsistente}
                sub={`de ${r.procesos_iniciados} procesos: el N° escrito bajó sin respaldo`} />
              <Stat label="Sesiones sin modalidad" valor={cal.sesiones_sin_modalidad}
                sub={`de ${cal.sesiones_periodo} · ${cal.procesos_sin_modalidad} procesos sin dato`} />
              <Stat label="Sesiones importadas de AgendaPro" valor={cal.sesiones_importadas_agendapro}
                sub={`${cal.sesiones_sistema_propio} registradas en el sistema propio`} />
              <Stat label="Sesiones históricas sin psicólogo" valor={cal.historicas_sin_psicologo}
                sub={`de ${cal.historicas_sesiones} anteriores al ${fechaCorta(uni.inicio_sistema_propio)} · solo filtra por sede`} />
            </div>
            <Nota>
              Todo se mide sobre los filtros elegidos (las sesiones históricas, solo por sede). El psicólogo de un proceso es quien atendió la S1; si la cita no
              lo dice se usa el asignado en la ficha ({cal.procesos_psicologo_por_ficha} procesos) y, si tampoco, queda
              en «Sin asignar» ({cal.procesos_sin_psicologo} procesos). La modalidad «presencial» es el valor por
              defecto de la cita: una cita que nadie marcó también dice presencial, así que «sin modalidad» subestima
              el faltante real. «Importada de AgendaPro» se reconoce por la marca que dejó el importador en las notas.
            </Nota>
          </div>

          {/* --- Definición del abandono inferido --- */}
          <div className="ca-card" style={{ marginTop: 14, fontSize: 13.5, lineHeight: 1.55 }}>
            <strong>Abandono inferido no es abandono confirmado.</strong> Un proceso entra aquí cuando su última sesión
            fue hace más de <strong>{N} días</strong>, no tiene próxima cita y no tiene alta ni cierre registrado
            (DP-10, otro DP de cierre, o la ficha en «alta» / «en pausa»). Hoy no existe un estado formal de abandono y
            la mayoría de los cierres no lleva su código DP, así que este número incluye altas que nadie registró.
            Úsalo para ver <em>dónde</em> se cortan los procesos, no para afirmar <em>por qué</em>.
          </div>

          {data.vacio ? (
            <div className="ca-card" style={{ marginTop: 18, textAlign: "center", padding: "28px 18px" }}>
              <div style={{ fontWeight: 600 }}>No hay procesos que empiecen en este período con estos filtros.</div>
              <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 6 }}>
                Prueba un período más amplio o quita algún filtro. Procesos activos hoy con estos filtros
                (empezaran cuando empezaran): {r.procesos_activos_hoy}.
              </div>
              {!esDefecto(f) && (
                <button className="ca-btn dc-noprint" style={{ marginTop: 14 }} onClick={limpiar}>
                  <RotateCcw size={15} /> Limpiar filtros
                </button>
              )}
            </div>
          ) : (
            <>
              {/* --- Resumen --- */}
              <h2 className="ca-secth" style={{ marginTop: 28 }}>Resumen</h2>
              <div className="ca-stats">
                <Stat label="Procesos iniciados" valor={r.procesos_iniciados}
                  sub={`${r.pacientes_nuevos} pacientes nuevos · ${r.reingresos} reingresos`} />
                <Stat label="De esos, aún activos" valor={r.activos_de_la_cohorte}
                  sub={`${r.terminados_de_la_cohorte} ya terminaron`} />
                <Stat label="Procesos activos hoy" valor={r.procesos_activos_hoy} sub="empezaran cuando empezaran" />
                <Stat label="Altas registradas" valor={r.altas_registradas}
                  sub={`${r.cierres_registrados} otros cierres · ${r.reinicios} reinicios`} />
              </div>
              <div className="ca-stats" style={{ marginTop: 12 }}>
                <StatKpi label="Pasan de S1 a S2" k={kp.s1_s2} />
                <StatKpi label="Pasan de S1 a S3" k={kp.s1_s3} />
                <StatKpi label="Llegan a S6" k={kp.s1_s6} />
                <StatKpi label="Abandono inferido" k={kp.abandono_inferido} enCurso="aún activos" />
              </div>
              <div className="ca-stats" style={{ marginTop: 12 }}>
                <StatMediana label="Sesiones por proceso terminado" e={est.sesiones_por_proceso_terminados} />
                <StatMediana label="Sesiones por proceso (todos)" e={est.sesiones_por_proceso} />
                <StatMediana label="Días entre sesiones" e={est.dias_entre_sesiones} />
                <StatMediana label="Días de S1 a abandono inferido" e={est.dias_s1_a_abandono} />
              </div>
              <Nota>
                Cada tasa se calcula sobre los <strong>evaluables</strong>: los procesos cuyo hito ya está resuelto
                (lo alcanzaron o ya terminaron). Los activos que todavía no llegan van aparte como «aún en curso»: no
                tuvieron tiempo y contarlos como caída inflaría el abandono. El abandono inferido se mide sobre los
                procesos ya terminados. La <strong>mediana</strong> es la cifra de referencia (un proceso muy largo
                mueve la media, no la mediana); en «todos» los activos siguen sumando sesiones, por eso se muestra
                aparte la de los terminados. «Días de S1 a abandono inferido» llega hasta su última sesión.
              </Nota>

              {/* --- Distribuciones --- */}
              <div className="dc-dist" style={{ marginTop: 16 }}>
                <Distribucion titulo="Sesiones por proceso" filas={data.distribuciones.sesiones_por_proceso}
                  series={[{ k: "terminados", t: "Terminados", color: VERDE }, { k: "activos", t: "Aún activos", color: "#B9CFC6" }]} />
                <Distribucion titulo="Días entre sesiones consecutivas" filas={data.distribuciones.dias_entre_sesiones}
                  series={[{ k: "n", t: "Intervalos", color: VERDE }]}
                  nota="Cada barra cuenta intervalos entre dos sesiones seguidas del mismo proceso. Solo conteos." />
              </div>

              {/* --- Embudo --- */}
              <h2 className="ca-secth" style={{ marginTop: 28 }}>Embudo de continuidad</h2>
              <div className="ca-card dc-tabla-larga" style={{ overflowX: "auto", padding: 0 }}>
                <table className="ca-table">
                  <thead>
                    <tr>
                      <th>Etapa</th>
                      <th className="num" title="N: procesos que llegaron a esta sesión">Llegaron (N)</th>
                      <th className="num">Aún en curso</th>
                      <th className="num">Evaluables</th>
                      <th className="num">Pasaron</th>
                      <th className="num">Abandono inferido</th>
                      <th className="num">Alta / cierre / reinicio</th>
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
                            <td className="num">{e.evaluables}<Muestra k={e.kpi} /></td>
                            <td className="num">{e.pasaron} <span style={{ color: "var(--muted)" }}>({pct(e.pct_paso)})</span></td>
                            <td className="num">{e.cayeron} <span style={{ color: "var(--muted)" }}>({pct(e.pct_caida)})</span></td>
                            <td className="num">{e.otros_cierres} <span style={{ color: "var(--muted)" }}>({pct(e.pct_otros_cierres)})</span></td>
                          </>
                        ) : <td colSpan={5} />}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Nota>
                S1, S2… es el <strong>orden</strong> de la sesión dentro del proceso (no el número escrito en la cita) y
                la consulta inicial no cuenta. Los porcentajes de cada fila son sobre sus <strong>evaluables</strong>
                (pasaron + terminaron en esa etapa); «aún en curso» queda fuera del denominador.
              </Nota>

              {/* --- Por psicólogo --- */}
              <h2 className="ca-secth" style={{ marginTop: 28 }}>Por psicólogo</h2>
              <TablaGrupo filas={data.por_psicologo} primera="Psicólogo"
                extra={[{ k: "sesiones_realizadas", t: "Sesiones en el período" }, { k: "carga_activos_hoy", t: "Carga activa hoy" }]} />
              <Nota>
                En orden alfabético, sin ranking: es para detectar patrones (dónde se cortan los procesos, qué carga
                tiene cada agenda), no para calificar a nadie. Una diferencia entre psicólogos puede venir de la
                población que atiende, la sede o la categoría, y de qué tan completo está su registro. Debajo de cada
                tasa va «numerador/denominador»; con menos de {data.filtros.muestra_pequena} evaluables se marca
                «m. pequeña» (regla técnica, no un juicio). «Procesos» y las tasas son de los procesos iniciados en el
                período (psicólogo de la S1); «Sesiones en el período» se atribuye a quien atendió cada sesión
                ({data.sesiones_sin_psicologo_periodo} sesiones sin psicólogo).
              </Nota>

              {/* --- Por sede, categoría y modalidad --- */}
              {/* Una debajo de la otra: lado a lado, la de categoría no entraba y se cortaba. */}
              <h2 className="ca-secth" style={{ marginTop: 28 }}>Por sede</h2>
              <TablaGrupo filas={data.por_sede} primera="Sede" />
              <Nota>Sedes en orden fijo. Una diferencia entre sedes no dice cuál es «mejor»: cambian la población, el equipo y el registro.</Nota>
              <h2 className="ca-secth" style={{ marginTop: 28 }}>Por categoría</h2>
              <TablaGrupo filas={data.por_categoria} primera="Categoría" />
              <Nota>La categoría es la de la cita de la S1. Muchas citas importadas no la traen («Sin categoría»).</Nota>
              <h2 className="ca-secth" style={{ marginTop: 28 }}>Por modalidad</h2>
              <TablaGrupo filas={data.por_modalidad} primera="Modalidad" />
              <Nota>
                Modalidad del proceso según sus sesiones: si todas dicen lo mismo, esa; si hay presenciales y virtuales,
                «Mixta». Recuerda que «presencial» también es el valor por defecto de una cita que nadie marcó.
              </Nota>
            </>
          )}

          {/* --- Universo y fuente --- */}
          <h2 className="ca-secth" style={{ marginTop: 28 }}>De dónde salen estos datos</h2>
          <div className="ca-card" style={{ fontSize: 13.5, lineHeight: 1.6 }}>
            <div><strong>Fuente:</strong> {uni.fuente}</div>
            <div><strong>Primera sesión con cita en la base:</strong> {fechaCorta(uni.desde)} · {uni.procesos_totales} procesos en total ({uni.procesos_filtrados} con estos filtros, de cualquier fecha).</div>
            <div>
              <strong>Procesos de este período:</strong> {uni.cohorte_agendapro} empezaron antes del {fechaCorta(uni.inicio_sistema_propio)}
              {" "}(época AgendaPro) y {uni.cohorte_sistema_propio} en el sistema propio; {uni.cohorte_s1_importada} tienen
              su S1 marcada como importada.
            </div>
            <div style={{ marginTop: 6, color: "var(--ink-soft)" }}>
              <strong>{uni.fichas_sin_cita}</strong> fichas clínicas no tienen cita asociada —en su mayoría las sesiones
              del Excel de 2024 a febrero de 2026— y <strong>no entran</strong> en estos cálculos: sin cita no hay
              estado de asistencia ni orden confiable dentro del proceso.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
