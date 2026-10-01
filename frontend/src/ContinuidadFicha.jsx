// Continuidad del proceso en la ficha del paciente (fase 2).
//
// Muestra el estado FORMAL (lo que alguien registró) separado de lo que se
// INFIERE de la agenda, la frecuencia esperada y la historia del proceso. Las
// acciones salen del servidor (qué se puede registrar en ese estado y con ese
// rol): aquí no se decide ninguna regla. No hay datos clínicos: los motivos
// son operativos y el detalle es un texto breve, también operativo.
//
// Backend: continuidad/api.py · reglas: continuidad/servicios.py ·
// docs/continuidad-estados.md.
import { useEffect, useMemo, useState } from "react";
import { ChevronDown, History, X } from "lucide-react";
import { api } from "./api";

const COLOR_ESTADO = {
  activo: { bg: "#E9F1ED", fg: "#3F7362" },
  pausa: { bg: "#F4EEDF", fg: "#8A6A2E" },
  alta: { bg: "#E6EEF5", fg: "#3D6485" },
  abandono: { bg: "#F3E7E5", fg: "#8E4A43" },
  cerrado: { bg: "#EEEBE6", fg: "#6B6760" },
  sin_registro: { bg: "#F3F1EC", fg: "#7C7870" },
};

// Qué registra cada acción, en una frase, antes de confirmar.
const AYUDA = {
  continuacion_confirmada: "Confirma que este proceso (anterior al registro formal) sigue activo.",
  pausa_iniciada: "El proceso queda en pausa acordada. No hace falta fecha de fin; puedes dejar una fecha tentativa para revisarlo.",
  reactivacion: "El proceso vuelve a estar activo. La pausa o el cierre anterior se conservan en la historia.",
  alta: "Registra el alta del proceso. Sale del seguimiento de inactividad y no cuenta como abandono.",
  abandono_confirmado: "Registra que el proceso se interrumpió sin alta, pausa ni cambio de profesional. Úsalo solo cuando consta (no por días sin venir).",
  cierre: "Cierra el proceso por otra decisión acordada (por ejemplo, una derivación externa).",
  cambio_profesional: "Cambia el profesional asignado. El proceso sigue activo en Conversemos: no es un abandono.",
  cambio_frecuencia: "Fija cada cuánto se esperan las sesiones. Sirve para ver atrasos, no para calificar.",
  correccion_motivo: "Corrige el motivo de un registro anterior sin borrarlo: queda un registro nuevo que lo reemplaza.",
};
const CON_MOTIVO = {
  pausa_iniciada: true, abandono_confirmado: true, cierre: true, alta: false, cambio_profesional: false,
};
const DETALLE_MAX = 280;

const hoyISO = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
const fecha = (iso) => (iso ? iso.split("-").reverse().join("/") : "—");
const nuevaClave = () => (window.crypto?.randomUUID ? window.crypto.randomUUID() : `${Date.now()}-${Math.random()}`);

function Estado({ codigo, label }) {
  const c = COLOR_ESTADO[codigo] || COLOR_ESTADO.sin_registro;
  return <span style={{ background: c.bg, color: c.fg, borderRadius: 7, padding: "2px 8px", fontSize: 12.5, fontWeight: 600 }}>{label}</span>;
}

function Dato({ label, children }) {
  return (
    <div style={{ minWidth: 0 }}>
      <div className="ca-label" style={{ fontSize: 11.5 }}>{label}</div>
      <div style={{ fontSize: 13.5, marginTop: 2 }}>{children}</div>
    </div>
  );
}

function Historial({ eventos }) {
  if (!eventos.length) {
    return <div style={{ fontSize: 13, color: "var(--muted)" }}>Sin registros formales: el proceso empezó antes del registro formal o nadie registró su estado todavía.</div>;
  }
  return (
    <ol style={{ listStyle: "none", margin: 0, padding: 0 }}>
      {[...eventos].reverse().map((e) => (
        <li key={e.uuid} style={{ padding: "8px 0", borderTop: "1px solid var(--line)", fontSize: 13 }}>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "baseline" }}>
            <strong>{e.tipo_label}</strong>
            <span style={{ color: "var(--muted)" }}>{fecha(e.fecha_efectiva)}</span>
            {e.estado_anterior !== e.estado_nuevo && <span style={{ color: "var(--muted)" }}>→ {e.estado_nuevo_label}</span>}
          </div>
          <div style={{ color: "var(--ink-soft)", marginTop: 2, lineHeight: 1.45 }}>
            {e.motivo && <>Motivo: {e.motivo.nombre} <span style={{ color: "var(--muted)" }}>({e.motivo.categoria}{e.motivo_corregido ? ", corregido" : ""})</span>. </>}
            {e.profesional_nuevo && <>De {e.profesional_anterior || "sin asignar"} a {e.profesional_nuevo}. </>}
            {e.frecuencia_nueva && <>Frecuencia: {e.frecuencia_anterior || "—"} → {e.frecuencia_nueva}{e.intervalo_nuevo_dias ? ` (cada ${e.intervalo_nuevo_dias} días)` : ""}. </>}
            {e.fecha_revision && <>Revisar el {fecha(e.fecha_revision)}. </>}
            {e.detalle_operativo && <span style={{ fontStyle: "italic" }}>«{e.detalle_operativo}» </span>}
          </div>
          <div style={{ color: "var(--muted)", fontSize: 11.5, marginTop: 2 }}>{e.registrado_por} · {e.origen}</div>
        </li>
      ))}
    </ol>
  );
}

function ModalAccion({ accion, proceso, catalogo, onClose, onGuardar }) {
  const tipo = accion.tipo;
  const [motivo, setMotivo] = useState("");
  const [fechaEf, setFechaEf] = useState(hoyISO());
  const [revision, setRevision] = useState("");
  const [prof, setProf] = useState("");
  const [frec, setFrec] = useState("semanal");
  const [intervalo, setIntervalo] = useState("");
  const [corrige, setCorrige] = useState("");
  const [detalle, setDetalle] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  // Una clave por formulario abierto: un doble clic o un reintento no
  // duplican el registro (el servidor devuelve el mismo).
  const [clave] = useState(nuevaClave);

  const tipoMotivo = tipo === "correccion_motivo"
    ? proceso.eventos.find((e) => e.uuid === corrige)?.tipo : tipo;
  const motivos = (catalogo?.motivos || []).filter((m) => m.aplica.includes(tipoMotivo));
  const pideMotivo = tipo === "correccion_motivo" || tipo in CON_MOTIVO;
  const corregibles = proceso.eventos.filter((e) => e.tipo in CON_MOTIVO);

  const faltante = (() => {
    if (tipo === "correccion_motivo" && !corrige) return "Elige el registro a corregir.";
    if ((CON_MOTIVO[tipo] || tipo === "correccion_motivo") && !motivo) return "Elige un motivo (si no se sabe, «Sin información»).";
    if (tipo === "cambio_profesional" && !prof) return "Elige el profesional nuevo.";
    if (tipo === "cambio_frecuencia" && frec === "personalizada" && !(Number(intervalo) >= 1 && Number(intervalo) <= 180)) return "El intervalo va de 1 a 180 días.";
    return "";
  })();

  const guardar = async () => {
    if (faltante || enviando) return;
    setEnviando(true);
    setError("");
    try {
      await onGuardar({
        proceso: proceso.uuid, ancla: proceso.ancla, evento: tipo, estado_esperado: proceso.estado_formal,
        clave_idempotencia: clave, fecha_efectiva: fechaEf, detalle_operativo: detalle.trim(),
        ...(motivo ? { motivo } : {}),
        ...(tipo === "pausa_iniciada" && revision ? { fecha_revision: revision } : {}),
        ...(tipo === "cambio_profesional" ? { profesional_nuevo: Number(prof) } : {}),
        ...(tipo === "cambio_frecuencia" ? { frecuencia: frec, ...(frec === "personalizada" ? { intervalo_dias: Number(intervalo) } : {}) } : {}),
        ...(tipo === "correccion_motivo" ? { corrige } : {}),
      });
    } catch (e) {
      setError(e.message);
      setEnviando(false);
    }
  };

  return (
    <div className="ca-modal-bg" onClick={enviando ? undefined : onClose}>
      <div className="ca-modal" style={{ maxWidth: 440 }} onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-labelledby="cf-titulo">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
          <strong id="cf-titulo" style={{ fontSize: 16 }}>{accion.label}</strong>
          <button onClick={onClose} aria-label="Cerrar" style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}><X size={18} /></button>
        </div>
        <div style={{ fontSize: 13, color: "var(--ink-soft)", lineHeight: 1.5, marginBottom: 14 }}>{AYUDA[tipo]}</div>

        {tipo === "correccion_motivo" && (
          <label style={{ display: "block", marginBottom: 12 }}>
            <div className="ca-label">Registro a corregir</div>
            <select className="ca-input" value={corrige} onChange={(e) => { setCorrige(e.target.value); setMotivo(""); }}>
              <option value="">Elige…</option>
              {corregibles.map((e) => <option key={e.uuid} value={e.uuid}>{e.tipo_label} · {fecha(e.fecha_efectiva)}{e.motivo ? ` · ${e.motivo.nombre}` : ""}</option>)}
            </select>
          </label>
        )}
        {pideMotivo && (
          <label style={{ display: "block", marginBottom: 12 }}>
            <div className="ca-label">Motivo {CON_MOTIVO[tipo] === false ? "(opcional)" : ""}</div>
            <select className="ca-input" value={motivo} onChange={(e) => setMotivo(e.target.value)}>
              <option value="">{CON_MOTIVO[tipo] === false ? "Sin indicar" : "Elige…"}</option>
              {[...new Set(motivos.map((m) => m.categoria_label))].map((cat) => (
                <optgroup key={cat} label={cat}>
                  {motivos.filter((m) => m.categoria_label === cat).map((m) => <option key={m.codigo} value={m.codigo}>{m.nombre}</option>)}
                </optgroup>
              ))}
            </select>
          </label>
        )}
        {tipo === "cambio_profesional" && (
          <label style={{ display: "block", marginBottom: 12 }}>
            <div className="ca-label">Profesional nuevo</div>
            <select className="ca-input" value={prof} onChange={(e) => setProf(e.target.value)}>
              <option value="">Elige…</option>
              {(catalogo?.profesionales || []).map((x) => <option key={x.id} value={x.id}>{x.nombre}</option>)}
            </select>
          </label>
        )}
        {tipo === "cambio_frecuencia" && (
          <div style={{ display: "flex", gap: 10, marginBottom: 12, flexWrap: "wrap" }}>
            <label style={{ flex: "1 1 180px" }}>
              <div className="ca-label">Frecuencia esperada</div>
              <select className="ca-input" value={frec} onChange={(e) => setFrec(e.target.value)}>
                {(catalogo?.frecuencias || []).map((x) => <option key={x.clave} value={x.clave}>{x.label}</option>)}
              </select>
            </label>
            {frec === "personalizada" && (
              <label style={{ flex: "0 1 120px" }}>
                <div className="ca-label">Cada (días)</div>
                <input className="ca-input" type="number" min={1} max={180} value={intervalo} onChange={(e) => setIntervalo(e.target.value)} />
              </label>
            )}
          </div>
        )}
        {tipo !== "correccion_motivo" && (
          <div style={{ display: "flex", gap: 10, marginBottom: 12, flexWrap: "wrap" }}>
            <label style={{ flex: "1 1 160px" }}>
              <div className="ca-label">Fecha</div>
              <input className="ca-input" type="date" value={fechaEf} max={hoyISO()} min={proceso.inicio} onChange={(e) => setFechaEf(e.target.value)} />
            </label>
            {tipo === "pausa_iniciada" && (
              <label style={{ flex: "1 1 160px" }}>
                <div className="ca-label">Revisar el (opcional)</div>
                <input className="ca-input" type="date" value={revision} min={fechaEf} onChange={(e) => setRevision(e.target.value)} />
              </label>
            )}
          </div>
        )}
        <label style={{ display: "block", marginBottom: 12 }}>
          <div className="ca-label">Detalle operativo (opcional · no es una nota clínica)</div>
          <textarea className="ca-input" rows={2} maxLength={DETALLE_MAX} value={detalle} onChange={(e) => setDetalle(e.target.value)}
            placeholder="Ej.: prefiere retomar después de su viaje" style={{ resize: "vertical" }} />
          <div style={{ fontSize: 11.5, color: "var(--muted)", textAlign: "right" }}>{detalle.length}/{DETALLE_MAX}</div>
        </label>

        {(error || faltante) && <div role="alert" style={{ fontSize: 13, color: error ? "#B4564E" : "var(--muted)", marginBottom: 12 }}>{error || faltante}</div>}
        <div style={{ display: "flex", gap: 9, justifyContent: "flex-end" }}>
          <button className="ca-btn ghost" onClick={onClose} disabled={enviando}>Cancelar</button>
          <button className="ca-btn" onClick={guardar} disabled={!!faltante || enviando}
            style={{ opacity: faltante || enviando ? 0.5 : 1 }}>
            {enviando ? "Guardando…" : "Confirmar registro"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Proceso({ p, puede, catalogo, onAccion }) {
  const dev = p.desviacion;
  return (
    <div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <Estado codigo={p.estado_formal} label={p.estado_formal_label} />
        {p.fecha_estado && <span style={{ fontSize: 12.5, color: "var(--muted)" }}>desde el {fecha(p.fecha_estado)}</span>}
        {p.actual && p.estado_operativo !== "no_aplica" && (
          <span style={{ fontSize: 12.5, color: "var(--ink-soft)" }}>· {p.estado_operativo_label}</span>
        )}
      </div>
      {p.requiere_revision && (
        <div style={{ fontSize: 12.5, color: "#8A6A2E", marginTop: 8 }}>Revisar la identidad de este proceso: {p.requiere_revision}.</div>
      )}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12, marginTop: 12 }}>
        <Dato label="Inicio (S1)">{fecha(p.inicio)} · {p.sesiones} {p.sesiones === 1 ? "sesión" : "sesiones"}</Dato>
        <Dato label="Última sesión">{fecha(p.ultima_sesion)} <span style={{ color: "var(--muted)" }}>(hace {p.dias_sin_sesion} días)</span></Dato>
        <Dato label="Próxima cita">{p.proxima_cita ? fecha(p.proxima_cita) : (p.actual ? "Sin próxima cita" : "—")}</Dato>
        <Dato label="Frecuencia esperada">
          {p.frecuencia.label}{p.frecuencia.intervalo_dias ? ` · cada ${p.frecuencia.intervalo_dias} días` : ""}
          {p.frecuencia.fuente === "ficha_legacy" && <span style={{ color: "var(--muted)" }}> (de la ficha)</span>}
        </Dato>
        {dev && (
          <Dato label="Ritmo">
            {dev.excede ? `${dev.atraso_dias} días más que el intervalo esperado` : "Dentro del intervalo esperado"}
          </Dato>
        )}
      </div>
      <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 8 }}>
        Clasificación en reportes: {p.clasificacion_fuente.toLowerCase()}.
      </div>
      {puede && p.acciones.length > 0 && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
          {p.acciones.map((a) => (
            <button key={a.tipo} className="ca-mini" onClick={() => onAccion(a, p)} disabled={!catalogo}>{a.label}</button>
          ))}
          {p.eventos.some((e) => e.tipo in CON_MOTIVO) && (
            <button className="ca-mini" onClick={() => onAccion({ tipo: "correccion_motivo", label: "Corregir un motivo" }, p)} disabled={!catalogo}>
              Corregir un motivo
            </button>
          )}
        </div>
      )}
      <details style={{ marginTop: 12 }}>
        <summary style={{ cursor: "pointer", fontSize: 13, color: "var(--ink-soft)", display: "flex", alignItems: "center", gap: 6 }}>
          <History size={14} /> Historia del proceso ({p.eventos.length})
        </summary>
        <div style={{ marginTop: 8 }}><Historial eventos={p.eventos} /></div>
      </details>
    </div>
  );
}

export default function ContinuidadFicha({ pacienteId, showToast }) {
  // Lo cargado va con el id del paciente: al cambiar de ficha no se muestra
  // la continuidad de la anterior mientras llega la nueva.
  const [cargado, setCargado] = useState({ id: null, data: null });
  const data = cargado.id === pacienteId ? cargado.data : null;
  const [oculto, setOculto] = useState(false);
  const [catalogo, setCatalogo] = useState(null);
  const [modal, setModal] = useState(null);

  useEffect(() => {
    let vivo = true;
    api.continuidadProcesos(pacienteId)
      .then((d) => { if (vivo) setCargado({ id: pacienteId, data: d }); })
      .catch((e) => {
        if (!vivo) return;
        if (e.status === 403) setOculto(true);
        else setCargado({ id: pacienteId, data: { error: e.message } });
      });
    return () => { vivo = false; };
  }, [pacienteId]);

  useEffect(() => {
    if (!data?.puede_registrar || catalogo) return;
    api.continuidadMotivos().then(setCatalogo).catch(() => {});
  }, [data?.puede_registrar, catalogo]);

  const [actual, anteriores] = useMemo(() => {
    const ps = data?.procesos || [];
    return [ps[0], ps.slice(1)];
  }, [data]);

  if (oculto) return null;

  const guardar = async (payload) => {
    const r = await api.continuidadTransicion(pacienteId, payload);
    setCargado((c) => ({ ...c, data: { ...c.data, procesos: r.procesos } }));
    setModal(null);
    showToast?.(r.repetido ? "Ese registro ya estaba guardado." : "Registro guardado en la historia del proceso.");
  };

  return (
    <>
      <h2 className="ca-secth" id="hc-continuidad">Continuidad</h2>
      <div className="ca-card" style={{ marginBottom: 26 }}>
        {!data ? <div style={{ fontSize: 13, color: "var(--muted)" }}>Cargando…</div>
          : data.error ? <div style={{ fontSize: 13, color: "#B4564E" }}>No se pudo cargar la continuidad: {data.error}</div>
            : !actual ? <div style={{ fontSize: 13, color: "var(--muted)" }}>Todavía no hay un proceso: aparece con la primera sesión realizada (la consulta inicial no cuenta).</div>
              : (
                <>
                  <Proceso p={actual} puede={data.puede_registrar} catalogo={catalogo} onAccion={(a, p) => setModal({ accion: a, proceso: p })} />
                  {anteriores.length > 0 && (
                    <details style={{ marginTop: 16, borderTop: "1px solid var(--line)", paddingTop: 12 }}>
                      <summary style={{ cursor: "pointer", fontSize: 13, color: "var(--ink-soft)", display: "flex", alignItems: "center", gap: 6 }}>
                        <ChevronDown size={14} /> Procesos anteriores ({anteriores.length})
                      </summary>
                      {anteriores.map((p) => (
                        <div key={p.uuid || p.ancla} style={{ marginTop: 14 }}>
                          <div style={{ fontSize: 12.5, fontWeight: 600, color: "var(--ink-soft)", marginBottom: 6 }}>Proceso {p.numero}</div>
                          <Proceso p={p} puede={data.puede_registrar} catalogo={catalogo} onAccion={(a, x) => setModal({ accion: a, proceso: x })} />
                        </div>
                      ))}
                    </details>
                  )}
                  <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 14, lineHeight: 1.5 }}>
                    «Abandono inferido» es un cálculo de la agenda (días sin venir y sin próxima cita): no cambia el estado registrado.
                    Pausa, alta y cambio de profesional no son abandono.
                  </div>
                </>
              )}
      </div>
      {modal && <ModalAccion accion={modal.accion} proceso={modal.proceso} catalogo={catalogo}
        onClose={() => setModal(null)} onGuardar={guardar} />}
    </>
  );
}
