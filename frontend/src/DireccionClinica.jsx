// Dirección Clínica → continuidad y abandono inferido de los procesos.
//
// Solo lectura. Todo sale de /api/direccion-clinica/ (core/direccion_clinica.py),
// que reconstruye los procesos con la misma regla del Centro de Continuidad.
//
// Dos cosas que esta pantalla NO hace, a propósito:
// - No llama "abandono" a lo que no lo es: hoy no existe un estado formal de
//   abandono y casi ningún cierre tiene su código DP. Se dice "abandono
//   inferido" en todos lados, con su definición a la vista.
// - No ordena a los psicólogos por desempeño. La tabla va en orden alfabético
//   y sin colores de bueno/malo: sirve para ver patrones, no para calificar.
import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Printer } from "lucide-react";
import { api } from "./api";

const SEDES = [["", "Todas"], ["lima", "Lima"], ["piura", "Piura"]];
const ROJO = "#B4564E", AMBAR = "#C9923A", VERDE = "#4F8A77";

// Impresión / "Guardar como PDF". El sistema vive dentro de un contenedor con
// scroll propio (.clinica-app / .ca-main): impreso tal cual, salía UNA hoja con
// el menú y el resto cortado. Estas reglas solo aplican cuando esta pantalla
// está abierta (body:has(.dc-pagina)), así que no cambian cómo se imprime
// ninguna otra parte del sistema.
const ESTILOS = `
.dc-solo-impresion { display:none; }
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
      {sub && <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>{sub}</div>}
    </div>
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
            <th className="num">S1→S2</th>
            <th className="num">S1→S3</th>
            <th className="num">Prom. sesiones</th>
            <th className="num">Abandono inferido</th>
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
              <td className="num" title={`Base: ${f.s1_s2_base} procesos con el paso resuelto`}>{pct(f.s1_s2)}</td>
              <td className="num" title={`Base: ${f.s1_s3_base} procesos con el paso resuelto`}>{pct(f.s1_s3)}</td>
              <td className="num">{num(f.promedio_sesiones)}</td>
              <td className="num">{f.abandono_inferido} <span style={{ color: "var(--muted)" }}>({pct(f.tasa_abandono_inferido)})</span></td>
              <td className="num">{f.altas + f.cierres_registrados}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function DireccionClinica({ showToast }) {
  const [f, setF] = useState({ periodo: "365d", sede: "", psicologo: "", categoria: "", etapa: "", dias_abandono: 45 });
  const [dias, setDias] = useState("45");
  const [data, setData] = useState(null);
  // Para qué filtros es lo que está en pantalla: "cargando" es que no coincidan.
  const [listoPara, setListoPara] = useState(null);
  const clave = JSON.stringify(f);
  const cargando = listoPara !== clave;
  const avisar = useRef(showToast);
  useEffect(() => { avisar.current = showToast; });

  useEffect(() => {
    let vivo = true;
    api.direccionClinica(JSON.parse(clave))
      .then((d) => { if (vivo) setData(d); })
      .catch((e) => avisar.current?.("Error: " + e.message))
      .finally(() => { if (vivo) setListoPara(clave); });
    return () => { vivo = false; };
  }, [clave]);

  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const aplicarDias = () => {
    const n = parseInt(dias, 10);
    if (Number.isFinite(n) && n !== f.dias_abandono) set("dias_abandono", n);
  };

  const op = data?.filtros?.opciones;
  const r = data?.resumen, cal = data?.calidad, uni = data?.universo;
  const N = data?.filtros?.dias_abandono ?? f.dias_abandono;

  // Qué filtros tiene aplicado lo impreso: una hoja sin esto no se puede leer.
  const etiquetaDe = (lista, clave, todos) => (clave ? (lista || []).find((x) => x.clave === clave)?.label || clave : todos);
  const filtrosTexto = data ? [
    `Período: ${data.periodo.label}${data.periodo.desde ? ` (${fechaCorta(data.periodo.desde)} – ${fechaCorta(data.periodo.hasta)})` : ""}`,
    `Sede: ${SEDES.find(([v]) => v === f.sede)?.[1] || "Todas"}`,
    `Psicólogo: ${etiquetaDe(op?.psicologos, f.psicologo, "Todos")}`,
    `Categoría: ${etiquetaDe(op?.categorias, f.categoria, "Todas")}`,
    `Etapa: ${f.etapa ? `va en S${f.etapa}` : "Todas"}`,
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
          <button className="ca-btn" onClick={() => window.print()} disabled={!data}
            title="Imprimir o guardar como PDF (en el cuadro de impresión, elige «Guardar como PDF»)">
            <Printer size={15} /> Imprimir / PDF
          </button>
          <div className="ca-seg">
            {SEDES.map(([v, l]) => (
              <button key={v || "todas"} className={f.sede === v ? "on" : ""} onClick={() => set("sede", v)}>{l}</button>
            ))}
          </div>
          <div className="ca-seg">
            {(op?.periodos || [{ clave: "365d", label: "Últimos 12 meses" }]).map((p) => (
              <button key={p.clave} className={f.periodo === p.clave ? "on" : ""} onClick={() => set("periodo", p.clave)}>
                {p.label.replace("Últimos ", "").replace("Todo el histórico", "Todo")}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="dc-noprint" style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center", marginTop: 14 }}>
        <select className="ca-input" style={{ width: "auto", padding: "6px 10px" }} value={f.psicologo} onChange={(e) => set("psicologo", e.target.value)}>
          <option value="">Todos los psicólogos</option>
          {(op?.psicologos || []).map((p) => <option key={p.clave} value={p.clave}>{p.label}</option>)}
        </select>
        <select className="ca-input" style={{ width: "auto", padding: "6px 10px" }} value={f.categoria} onChange={(e) => set("categoria", e.target.value)}>
          <option value="">Todas las categorías</option>
          {(op?.categorias || []).map((c) => <option key={c.clave} value={c.clave}>{c.label}</option>)}
        </select>
        <select className="ca-input" style={{ width: "auto", padding: "6px 10px" }} value={f.etapa} onChange={(e) => set("etapa", e.target.value)}>
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

      {!data ? (
        <div className="ca-empty">{cargando ? "Cargando…" : "Sin datos."}</div>
      ) : (
        <div style={{ opacity: cargando ? 0.5 : 1, transition: "opacity .15s" }}>
          {/* --- Calidad del dato: arriba de todo, antes de cualquier cifra --- */}
          <div className="ca-card" style={{ marginTop: 18, borderLeft: `4px solid ${AMBAR}` }}>
            <div style={{ display: "flex", gap: 8, alignItems: "center", fontWeight: 600 }}>
              <AlertTriangle size={17} color={AMBAR} /> Calidad del dato · léela antes de decidir
            </div>
            <div className="ca-stats" style={{ marginTop: 12 }}>
              <Stat label="Sesiones con psicólogo identificado" valor={pct(cal.pct_con_psicologo)}
                sub={`${cal.sesiones_sin_psicologo} de ${cal.sesiones_periodo} sin psicólogo`} color={colorCalidad(cal.pct_con_psicologo)} />
              <Stat label="Sesiones con N° de sesión" valor={pct(cal.pct_con_numero)} color={colorCalidad(cal.pct_con_numero)} />
              <Stat label="Cierres de bloque con DP" valor={pct(cal.pct_cierres_con_dp)}
                sub={`${cal.cierres_con_dp} de ${cal.cierres_bloque} (S6, S12…)`} color={colorCalidad(cal.pct_cierres_con_dp)} />
              <Stat label="Procesos terminados solo por inferencia" valor={cal.terminados_solo_inferidos}
                sub={`de ${cal.procesos_terminados} terminados · ${cal.terminados_con_registro} con alta o cierre registrado`} />
              <Stat label="Sesiones históricas sin psicólogo" valor={cal.historicas_sin_psicologo}
                sub={`de ${cal.historicas_sesiones} anteriores al ${fechaCorta(uni.inicio_sistema_propio)}`} />
            </div>
            <Nota>
              Las sesiones del período se miden sobre la sede elegida. El psicólogo de un proceso es quien atendió la S1;
              si la cita no lo dice se usa el asignado en la ficha ({cal.procesos_psicologo_por_ficha} procesos) y,
              si tampoco, queda en «Sin asignar» ({cal.procesos_sin_psicologo} procesos).
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

          {/* --- Resumen --- */}
          <h2 className="ca-secth" style={{ marginTop: 28 }}>Resumen</h2>
          <div className="ca-stats">
            <Stat label="Pacientes nuevos" valor={r.pacientes_nuevos} sub="primer proceso iniciado en el período" />
            <Stat label="Procesos iniciados" valor={r.procesos_iniciados} sub={`${r.reingresos} son reingresos`} />
            <Stat label="Procesos activos hoy" valor={r.procesos_activos_hoy} sub="empezaran cuando empezaran" />
            <Stat label="Abandono inferido" valor={r.abandono_inferido} sub={`${pct(r.tasa_abandono_inferido)} de los iniciados`} />
            <Stat label="Altas registradas" valor={r.altas_registradas} sub={`${r.cierres_registrados} otros cierres registrados`} />
          </div>
          <div className="ca-stats" style={{ marginTop: 12 }}>
            <Stat label="Promedio de sesiones por proceso" valor={num(r.promedio_sesiones)}
              sub={`${num(r.promedio_sesiones_terminados)} en los ya terminados`} />
            <Stat label="Días promedio entre sesiones" valor={num(r.promedio_dias_entre_sesiones)}
              sub={`mediana ${num(r.mediana_dias_entre_sesiones)}`} />
            <Stat label="Días de S1 a abandono inferido" valor={num(r.promedio_dias_s1_a_abandono)}
              sub={`mediana ${num(r.mediana_dias_s1_a_abandono)} · hasta su última sesión`} />
          </div>

          {/* --- Embudo --- */}
          <h2 className="ca-secth" style={{ marginTop: 28 }}>Embudo de continuidad</h2>
          <div className="ca-card dc-tabla-larga" style={{ overflowX: "auto", padding: 0 }}>
            <table className="ca-table">
              <thead>
                <tr>
                  <th>Etapa</th>
                  <th className="num">Llegaron</th>
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
                        <td className="num">{e.evaluables}</td>
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
            S1, S2… es el <strong>orden</strong> de la sesión dentro del proceso (no el número escrito en la cita) y la
            consulta inicial no cuenta. Los porcentajes se calculan sobre los <strong>evaluables</strong>: los que ya
            pasaron a la siguiente sesión o ya terminaron. Los procesos activos que todavía no llegan a la siguiente
            quedan fuera («aún en curso»): no tuvieron tiempo, contarlos como caída inflaría el abandono.
          </Nota>

          {/* --- Por psicólogo --- */}
          <h2 className="ca-secth" style={{ marginTop: 28 }}>Por psicólogo</h2>
          <TablaGrupo filas={data.por_psicologo} primera="Psicólogo"
            extra={[{ k: "sesiones_realizadas", t: "Sesiones en el período" }, { k: "carga_activos_hoy", t: "Carga activa hoy" }]} />
          <Nota>
            En orden alfabético, sin ranking: es para detectar patrones (dónde se cortan los procesos, qué carga
            tiene cada agenda), no para calificar a nadie. Una diferencia entre psicólogos puede venir de la
            población que atiende, la sede o la categoría, y de qué tan completo está su registro.
            «Procesos» y las tasas son de los procesos iniciados en el período (psicólogo de la S1); «Sesiones en el
            período» se atribuye a quien atendió cada sesión ({data.sesiones_sin_psicologo_periodo} sesiones sin psicólogo).
          </Nota>

          {/* --- Por sede y categoría --- */}
          {/* Una debajo de la otra: lado a lado, la de categoría no entraba y se cortaba. */}
          <h2 className="ca-secth" style={{ marginTop: 28 }}>Por sede</h2>
          <TablaGrupo filas={data.por_sede} primera="Sede" />
          <h2 className="ca-secth" style={{ marginTop: 28 }}>Por categoría</h2>
          <TablaGrupo filas={data.por_categoria} primera="Categoría" />
          <Nota>La categoría es la de la cita de la S1. Muchas citas importadas no la traen («Sin categoría»).</Nota>

          {/* --- Universo y fuente --- */}
          <h2 className="ca-secth" style={{ marginTop: 28 }}>De dónde salen estos datos</h2>
          <div className="ca-card" style={{ fontSize: 13.5, lineHeight: 1.6 }}>
            <div><strong>Fuente:</strong> {uni.fuente}</div>
            <div><strong>Primera sesión con cita en la base:</strong> {fechaCorta(uni.desde)} · {uni.procesos_totales} procesos en total.</div>
            <div>
              <strong>Procesos de este período:</strong> {uni.cohorte_agendapro} empezaron antes del {fechaCorta(uni.inicio_sistema_propio)}
              {" "}(vienen de AgendaPro) y {uni.cohorte_sistema_propio} en el sistema propio.
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
