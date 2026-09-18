// Calidad de datos → Posibles duplicados.
//
// La misma persona con dos fichas parte su historia en dos: sus sesiones, su
// próxima cita y su continuidad viven en Paciente.id distintos, y el Centro de
// Continuidad evalúa cada id por separado. Esta pantalla propone candidatos;
// consolidar es SIEMPRE una decisión humana, de a un caso por vez, y la ejecuta
// gerencia. No hay ningún "fusionar todo" a propósito.
import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowRight, Check, Search, Users, X } from "lucide-react";
import { api } from "./api";

const PESTANAS = [
  { key: "alta", label: "Alta confianza", ayuda: "Mismo documento, o mismo nombre y teléfono con la sede compatible." },
  { key: "media", label: "Revisar", ayuda: "Coincide lo suficiente para mirarlo, pero falta un identificador fuerte." },
  { key: "baja", label: "Descartados", ayuda: "Solo se parece el nombre. Casi siempre son homónimos." },
];

const SENAL = {
  documento_igual: "mismo documento",
  nombre_igual: "mismo nombre",
  nombre_similar: "nombre parecido",
  telefono_igual: "mismo teléfono",
  telefono_tutor_igual: "el teléfono del tutor coincide",
  nacimiento_igual: "misma fecha de nacimiento",
  email_igual: "mismo correo",
  mismo_psicologo: "mismo psicólogo",
};

const SEDE = { lima: "Lima", piura: "Piura" };

function Senal({ clave }) {
  return <span className="dup-senal">{SENAL[clave] || clave}</span>;
}

function Dato({ etiqueta, valor, resaltar }) {
  return (
    <div className="dup-dato">
      <span className="dup-dato-k">{etiqueta}</span>
      <span className="dup-dato-v" style={resaltar ? { fontWeight: 600 } : undefined}>
        {valor === null || valor === undefined || valor === "" ? "—" : valor}
      </span>
    </div>
  );
}

// --- Tarjeta de un grupo en la lista ----------------------------------------

function TarjetaGrupo({ grupo, onComparar }) {
  const { impacto } = grupo;
  const avisos = [
    impacto.proxima_en_una_sola && "la próxima cita está en una sola ficha",
    impacto.sesiones_repartidas && "las sesiones están repartidas",
    impacto.decisiones_repartidas && "la decisión (DP) está en una ficha y las sesiones en otra",
  ].filter(Boolean);

  return (
    <div className="ca-card dup-grupo">
      <div className="dup-grupo-top">
        <div>
          <div className="dup-nombre">{grupo.nombre}</div>
          <div className="dup-ids">
            {grupo.ids.map((id) => `#${id}`).join(" · ")}
            {grupo.ids.length > 2 && <span className="dup-tres"> · {grupo.ids.length} fichas</span>}
          </div>
        </div>
        <div className="dup-senales">
          {grupo.senales.map((s) => <Senal key={s} clave={s} />)}
        </div>
      </div>

      <div className="dup-fichas">
        {grupo.fichas.map((f) => (
          <div key={f.id} className="dup-ficha">
            <div className="dup-ficha-head">
              <strong>#{f.id}</strong>
              <span className="dup-sede">{SEDE[f.sede] || "sin sede"}</span>
              {f.provisional && <span className="dup-prov">provisional</span>}
            </div>
            <Dato etiqueta="Psicólogo" valor={f.profesional} />
            <Dato etiqueta="Documento" valor={f.documento} />
            <Dato etiqueta="Teléfono" valor={f.telefono} />
            <Dato etiqueta="Citas" valor={`${f.citas} (${f.sesiones} asistidas)`} />
            <Dato etiqueta="Proceso" valor={f.proceso ? `P${f.proceso} · S${f.sesion}` : "sin sesiones"} />
            <Dato etiqueta="Próxima cita" valor={f.proxima_cita} resaltar={!!f.proxima_cita} />
            <Dato etiqueta="Decisiones" valor={f.decisiones.join(", ")} />
            <Dato etiqueta="Creada" valor={f.creado_en} />
          </div>
        ))}
      </div>

      {avisos.length > 0 && (
        <div className="dup-impacto">
          <AlertTriangle size={14} />
          <span>Afecta a Continuidad: {avisos.join("; ")}.</span>
        </div>
      )}

      <div className="dup-acciones">
        <button className="ca-btn" onClick={() => onComparar(grupo)}>
          Comparar fichas <ArrowRight size={15} />
        </button>
      </div>
    </div>
  );
}

// --- Comparación lado a lado + dry-run + confirmación ------------------------

function Comparador({ grupo, puedeFusionar, showToast, onCerrar, onHecho }) {
  const [par, setPar] = useState(() => grupo.ids.slice(0, 2));
  const [principal, setPrincipal] = useState(null);
  const [analisis, setAnalisis] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [aceptarSede, setAceptarSede] = useState(false);
  const [confirmando, setConfirmando] = useState(false);
  const [motivo, setMotivo] = useState("");

  const fichas = useMemo(
    () => par.map((id) => grupo.fichas.find((f) => f.id === id)).filter(Boolean),
    [par, grupo],
  );
  const [a, b] = fichas;
  const secundario = principal && par.find((id) => id !== principal);

  async function correrDryRun(idPrincipal) {
    setCargando(true);
    setAnalisis(null);
    try {
      const otro = par.find((id) => id !== idPrincipal);
      const r = await api.analizarFusion(idPrincipal, otro, { aceptar_sede_distinta: aceptarSede });
      setPrincipal(idPrincipal);
      setAnalisis(r);
    } catch (e) {
      showToast(e.message || "No se pudo preparar la consolidación.");
    } finally {
      setCargando(false);
    }
  }

  async function descartar() {
    try {
      await api.descartarDuplicado(par[0], par[1], "Revisado: no son la misma persona.");
      showToast("Anotado: no son la misma persona. No se volverá a proponer.");
      onHecho();
    } catch (e) {
      showToast(e.message || "No se pudo guardar la decisión.");
    }
  }

  async function consolidar() {
    setCargando(true);
    try {
      const r = await api.fusionarPacientes(principal, secundario, {
        motivo, aceptar_sede_distinta: aceptarSede,
      });
      showToast(`Consolidado en la ficha #${r.paciente_id}. Se eliminó la #${r.eliminado_id}.`);
      onHecho();
    } catch (e) {
      showToast(e.message || "No se pudo consolidar.");
      setConfirmando(false);
    } finally {
      setCargando(false);
    }
  }

  if (!a || !b) return null;

  return (
    <div className="ca-modal-bg" onClick={onCerrar}>
      <div className="ca-modal dup-modal" onClick={(e) => e.stopPropagation()}>
        <div className="dup-modal-head">
          <div>
            <h2 className="ca-h1" style={{ fontSize: 20 }}>{grupo.nombre}</h2>
            <div className="ca-sub">¿Son la misma persona? Compara antes de decidir.</div>
          </div>
          <button className="ca-btn ghost" onClick={onCerrar}><X size={16} /></button>
        </div>

        {grupo.ids.length > 2 && (
          <div className="dup-selector">
            <span className="ca-sub">Hay {grupo.ids.length} fichas. Compara de a dos:</span>
            <div className="ca-seg" style={{ marginLeft: 0 }}>
              {grupo.ids.map((id) => (
                <button
                  key={id}
                  className={par.includes(id) ? "on" : ""}
                  onClick={() => {
                    setAnalisis(null);
                    setPrincipal(null);
                    setPar((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id].slice(-2)));
                  }}
                >#{id}</button>
              ))}
            </div>
          </div>
        )}

        <div className="dup-lado-a-lado">
          {[a, b].map((f) => (
            <div key={f.id} className={`dup-col ${principal === f.id ? "elegida" : ""}`}>
              <div className="dup-col-head">
                <strong>Ficha #{f.id}</strong>
                {principal === f.id && <span className="dup-badge">se conserva</span>}
              </div>
              <Dato etiqueta="Nombre" valor={f.nombre} />
              <Dato etiqueta="Sede" valor={SEDE[f.sede] || "—"} />
              <Dato etiqueta="Documento" valor={f.documento} />
              <Dato etiqueta="Teléfono" valor={f.telefono} />
              <Dato etiqueta="Tel. del tutor" valor={f.tutor_telefono} />
              <Dato etiqueta="Nacimiento" valor={f.fecha_nacimiento} />
              <Dato etiqueta="Psicólogo" valor={f.profesional} />
              <Dato etiqueta="Provisional" valor={f.provisional ? "sí" : "no"} />
              <Dato etiqueta="Citas" valor={f.citas} />
              <Dato etiqueta="Sesiones asistidas" valor={f.sesiones} />
              <Dato etiqueta="Proceso" valor={f.proceso ? `P${f.proceso} · S${f.sesion}` : "sin sesiones"} />
              <Dato etiqueta="Próxima cita" valor={f.proxima_cita} />
              <Dato etiqueta="Decisiones" valor={f.decisiones.join(", ")} />
              <Dato etiqueta="Creada" valor={f.creado_en} />
            </div>
          ))}
        </div>

        {!analisis && (
          <div className="dup-botonera">
            <button className="ca-btn ghost" onClick={descartar}>No son la misma persona</button>
            <button className="ca-btn ghost" onClick={onCerrar}>Revisar después</button>
            <div className="dup-preparar">
              <span className="ca-sub">Preparar consolidación conservando:</span>
              <button className="ca-btn" disabled={cargando} onClick={() => correrDryRun(a.id)}>Ficha #{a.id}</button>
              <button className="ca-btn" disabled={cargando} onClick={() => correrDryRun(b.id)}>Ficha #{b.id}</button>
            </div>
          </div>
        )}

        {analisis && <Analisis
          analisis={analisis}
          puedeFusionar={puedeFusionar}
          cargando={cargando}
          aceptarSede={aceptarSede}
          setAceptarSede={(v) => { setAceptarSede(v); setAnalisis(null); setPrincipal(null); }}
          motivo={motivo}
          setMotivo={setMotivo}
          confirmando={confirmando}
          setConfirmando={setConfirmando}
          onVolver={() => { setAnalisis(null); setPrincipal(null); setConfirmando(false); }}
          onConsolidar={consolidar}
        />}
      </div>
    </div>
  );
}

// --- El dry-run en pantalla --------------------------------------------------

function FotoContinuidad({ titulo, foto }) {
  return (
    <div className="dup-foto">
      <div className="dup-foto-t">{titulo}</div>
      <Dato etiqueta="Proceso / sesión" valor={foto.sesion ? `P${foto.proceso} · S${foto.sesion}` : "sin sesiones"} />
      <Dato etiqueta="Sesiones asistidas" valor={foto.sesiones_asistidas} />
      <Dato etiqueta="Próxima cita" valor={foto.proxima_cita} />
      <Dato etiqueta="Procesos anteriores sin cierre" valor={foto.anteriores_sin_cierre} />
      <Dato
        etiqueta="Alertas"
        valor={foto.alertas.length ? foto.alertas.map((x) => `${x.estado}${x.meta ? ` (meta ${x.meta})` : ""}`).join(", ") : "ninguna"}
      />
    </div>
  );
}

function Analisis({ analisis, puedeFusionar, cargando, aceptarSede, setAceptarSede,
                    motivo, setMotivo, confirmando, setConfirmando, onVolver, onConsolidar }) {
  const c = analisis.continuidad;
  const sedeEnConflicto = analisis.conflictos.some((x) => x.includes("sedes distintas"));

  return (
    <div className="dup-analisis">
      <div className="dup-analisis-head">
        <strong>Vista previa — todavía no se ha tocado nada</strong>
        <button className="ca-btn ghost" onClick={onVolver}>Cambiar</button>
      </div>

      <div className="dup-resultado">
        Sobrevive la ficha <strong>#{analisis.id_que_sobrevive}</strong> y se elimina
        la <strong>#{analisis.id_que_desaparece}</strong>.
        {analisis.recomendado_id !== analisis.id_que_sobrevive && (
          <span className="dup-ojo"> El sistema recomendaba conservar la #{analisis.recomendado_id} ({analisis.recomendado_porque.join(", ")}).</span>
        )}
      </div>

      {analisis.conflictos.length > 0 && (
        <div className="ca-alert dup-conflictos">
          <AlertTriangle size={16} />
          <div>
            <strong>No se puede consolidar todavía</strong>
            <ul>{analisis.conflictos.map((x, i) => <li key={i}>{x}</li>)}</ul>
            {sedeEnConflicto && (
              <label className="dup-check">
                <input type="checkbox" checked={aceptarSede} onChange={(e) => setAceptarSede(e.target.checked)} />
                Revisé las dos fichas y confirmo que es la misma persona pese a la sede distinta.
              </label>
            )}
          </div>
        </div>
      )}

      <div className="dup-bloques">
        <div>
          <div className="dup-bloque-t">Campos de la ficha</div>
          {analisis.campos.length === 0 && <div className="ca-sub">No cambia ningún campo.</div>}
          {analisis.campos.map((x, i) => (
            <div key={i} className="dup-campo">
              <span className="dup-campo-k">{x.campo}</span>
              <span className={`dup-campo-a dup-${x.accion.replace(/ /g, "-")}`}>{x.accion}</span>
              {x.resumen && <span className="dup-campo-v">{x.resumen}</span>}
              {x.descartado && <span className="dup-descartado">se mantiene el del principal (el otro decía {x.descartado})</span>}
            </div>
          ))}
        </div>

        <div>
          <div className="dup-bloque-t">Se trasladan {analisis.total_relaciones} registro(s)</div>
          {analisis.relaciones.filter((r) => r.filas > 0).map((r) => (
            <div key={`${r.label}.${r.campo}`} className="dup-campo">
              <span className="dup-campo-k">{r.label.split(".")[1]}</span>
              <span className="dup-campo-v">{r.filas}</span>
              {r.especial && <span className="dup-senal">con manejo propio</span>}
            </div>
          ))}
          {analisis.total_relaciones === 0 && <div className="ca-sub">La ficha secundaria no tiene nada colgando.</div>}
        </div>
      </div>

      <div className="dup-bloque-t">Continuidad</div>
      <div className="dup-continuidad">
        <FotoContinuidad titulo={`Antes · #${analisis.principal.id}`} foto={c.principal} />
        <FotoContinuidad titulo={`Antes · #${analisis.secundario.id}`} foto={c.secundario} />
        <FotoContinuidad titulo="Después (consolidada)" foto={c.despues} />
      </div>

      {puedeFusionar && analisis.puede_fusionar && !confirmando && (
        <div className="dup-botonera">
          <input
            className="dup-motivo"
            placeholder="Motivo (opcional): por qué son la misma persona"
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
          />
          <button className="ca-btn" onClick={() => setConfirmando(true)}>Consolidar…</button>
        </div>
      )}

      {puedeFusionar && analisis.puede_fusionar && confirmando && (
        <div className="ca-alert dup-confirmar">
          <AlertTriangle size={16} />
          <div>
            <strong>Esta acción consolidará ambas fichas en un solo paciente y eliminará la ficha secundaria.</strong>
            <div className="ca-sub">
              Sobrevive la ficha <strong>#{analisis.id_que_sobrevive}</strong>. Desaparece
              la <strong>#{analisis.id_que_desaparece}</strong>. No se puede deshacer.
            </div>
            <div className="dup-botonera">
              <button className="ca-btn ghost" onClick={() => setConfirmando(false)}>Cancelar</button>
              <button className="ca-btn" disabled={cargando} onClick={onConsolidar}>
                <Check size={15} /> Confirmar consolidación
              </button>
            </div>
          </div>
        </div>
      )}

      {!puedeFusionar && analisis.puede_fusionar && (
        <div className="ca-sub dup-nota">
          Todo listo para consolidar. La consolidación la ejecuta gerencia.
        </div>
      )}
    </div>
  );
}

// --- Pantalla ----------------------------------------------------------------

export default function Duplicados({ showToast, puedeFusionar }) {
  const [pestana, setPestana] = useState("alta");
  const [data, setData] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [busca, setBusca] = useState("");
  const [abierto, setAbierto] = useState(null);
  // Se incrementa tras consolidar o descartar: la lista se vuelve a pedir
  // porque el caso que se acaba de resolver ya no debe aparecer.
  const [recarga, setRecarga] = useState(0);
  // Piura y Lima se reparten el trabajo, pero ninguna pierde el acceso a
  // la otra sede: esto es un filtro, no un permiso.
  const [sede, setSede] = useState("");

  useEffect(() => {
    let vivo = true;
    (async () => {
      setCargando(true);
      try {
        const r = await api.duplicados(pestana, sede);
        if (vivo) setData(r);
      } catch (e) {
        if (!vivo) return;
        showToast(e.message || "No se pudieron cargar los posibles duplicados.");
        setData({ grupos: [], total: 0 });
      } finally {
        if (vivo) setCargando(false);
      }
    })();
    return () => { vivo = false; };
  }, [pestana, sede, recarga, showToast]);

  const grupos = useMemo(() => {
    const t = busca.trim().toLowerCase();
    const todos = data?.grupos || [];
    if (!t) return todos;
    return todos.filter((g) => g.nombre.toLowerCase().includes(t)
      || g.ids.some((id) => String(id).includes(t)));
  }, [data, busca]);

  const info = PESTANAS.find((p) => p.key === pestana);

  return (
    <div>
      <div className="ca-tophead">
        <div>
          <h1 className="ca-h1">Posibles duplicados</h1>
          <div className="ca-sub">
            Fichas que podrían ser la misma persona. El sistema propone; consolidar lo decide una persona, caso por caso.
          </div>
        </div>
      </div>

      <div className="ca-seg" style={{ flexWrap: "wrap", marginLeft: 0, marginBottom: 10 }}>
        {PESTANAS.map((p) => (
          <button key={p.key} className={pestana === p.key ? "on" : ""} onClick={() => setPestana(p.key)}>
            {p.label}
          </button>
        ))}
      </div>
      <div className="ca-sub" style={{ marginBottom: 14 }}>{info.ayuda}</div>

      <div className="dup-barra">
        <div className="dup-busca">
          <Search size={15} />
          <input placeholder="Buscar por nombre o id…" value={busca} onChange={(e) => setBusca(e.target.value)} />
        </div>
        {/* Reparto del trabajo entre Piura y Lima. Es un filtro: ninguna pierde
            el acceso a la otra sede, y un par con una ficha en cada una sale en
            los dos filtros porque es el caso que más necesita mirarse. */}
        <select className="ca-input" style={{ width: "auto", padding: "6px 10px" }}
          value={sede} onChange={(e) => setSede(e.target.value)}
          title="Filtra por sede para repartirse la revisión">
          <option value="">Las dos sedes</option>
          <option value="piura">Piura</option>
          <option value="lima">Lima</option>
        </select>
        <span className="ca-sub">
          {cargando ? "Buscando…" : `${grupos.length} caso(s)`}
        </span>
      </div>

      {!cargando && grupos.length === 0 && (
        <div className="ca-card dup-vacio">
          <Users size={22} />
          <div>
            <strong>No hay casos en esta pestaña.</strong>
            <div className="ca-sub">
              {busca ? "Prueba con otra búsqueda." : "Nada que revisar por ahora."}
            </div>
          </div>
        </div>
      )}

      {grupos.map((g) => (
        <TarjetaGrupo key={g.ids.join("-")} grupo={g} onComparar={setAbierto} />
      ))}

      {abierto && (
        <Comparador
          grupo={abierto}
          puedeFusionar={puedeFusionar}
          showToast={showToast}
          onCerrar={() => setAbierto(null)}
          onHecho={() => { setAbierto(null); setRecarga((n) => n + 1); }}
        />
      )}

      <style>{`
        .dup-grupo { margin-bottom: 14px; }
        .dup-grupo-top { display:flex; justify-content:space-between; gap:14px; flex-wrap:wrap; align-items:flex-start; }
        .dup-nombre { font-size:16px; font-weight:600; letter-spacing:-0.01em; }
        .dup-ids { color:var(--muted); font-size:13px; margin-top:2px; }
        .dup-tres { color:var(--accent); font-weight:600; }
        .dup-senales { display:flex; gap:6px; flex-wrap:wrap; }
        .dup-senal { background:var(--accent-soft); color:var(--accent); font-size:12px;
          padding:3px 9px; border-radius:999px; white-space:nowrap; }
        .dup-fichas { display:grid; grid-template-columns:repeat(auto-fit, minmax(230px, 1fr));
          gap:12px; margin-top:14px; }
        .dup-ficha { border:1px solid var(--line); border-radius:12px; padding:12px 14px; }
        .dup-ficha-head { display:flex; align-items:center; gap:8px; margin-bottom:8px; }
        .dup-sede { font-size:12px; color:var(--ink-soft); }
        .dup-prov { font-size:11px; background:#FFF1DA; color:#9C6B2E; padding:2px 7px; border-radius:999px; }
        .dup-dato { display:flex; justify-content:space-between; gap:10px; font-size:13px; padding:2px 0; }
        .dup-dato-k { color:var(--muted); }
        .dup-dato-v { color:var(--ink); text-align:right; }
        .dup-impacto { display:flex; align-items:center; gap:8px; margin-top:12px;
          font-size:13px; color:#9C6B2E; background:#FBF1E3; border-radius:10px; padding:8px 12px; }
        .dup-acciones { display:flex; justify-content:flex-end; margin-top:14px; }

        .dup-modal { max-width:900px; max-height:88vh; overflow-y:auto; }
        .dup-modal-head { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; margin-bottom:14px; }
        .dup-selector { display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:12px; }
        .dup-lado-a-lado { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
        .dup-col { border:1px solid var(--line); border-radius:12px; padding:14px; }
        .dup-col.elegida { border-color:var(--accent); background:var(--accent-soft); }
        .dup-col-head { display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; }
        .dup-badge { font-size:11px; background:var(--accent); color:#fff; padding:2px 8px; border-radius:999px; }
        .dup-botonera { display:flex; gap:10px; flex-wrap:wrap; align-items:center; margin-top:16px; }
        .dup-preparar { display:flex; gap:8px; align-items:center; margin-left:auto; flex-wrap:wrap; }
        .dup-motivo { flex:1; min-width:200px; border:1px solid var(--line); border-radius:8px;
          padding:8px 11px; font-size:13px; font-family:inherit; }

        .dup-analisis { margin-top:18px; border-top:1px solid var(--line); padding-top:16px; }
        .dup-analisis-head { display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; }
        .dup-resultado { font-size:14px; background:var(--hover); border-radius:10px; padding:10px 14px; }
        .dup-ojo { color:#9C6B2E; }
        .dup-conflictos ul { margin:6px 0 0; padding-left:18px; font-size:13px; }
        .dup-check { display:flex; gap:8px; align-items:flex-start; margin-top:10px; font-size:13px; }
        .dup-bloques { display:grid; grid-template-columns:1fr 1fr; gap:18px; margin-top:16px; }
        .dup-bloque-t { font-size:13px; font-weight:600; color:var(--ink-soft); margin:16px 0 8px;
          text-transform:uppercase; letter-spacing:0.04em; }
        .dup-bloques .dup-bloque-t { margin-top:0; }
        .dup-campo { display:flex; gap:8px; align-items:center; flex-wrap:wrap; font-size:13px; padding:3px 0; }
        .dup-campo-k { font-weight:500; min-width:120px; }
        .dup-campo-v { color:var(--ink-soft); }
        .dup-campo-a { font-size:11px; padding:2px 7px; border-radius:999px; background:var(--hover); color:var(--ink-soft); }
        .dup-hereda, .dup-une, .dup-toma-el-mayor, .dup-toma-el-más-completo { background:var(--accent-soft); color:var(--accent); }
        .dup-descartado { font-size:12px; color:var(--muted); }
        .dup-continuidad { display:grid; grid-template-columns:repeat(auto-fit, minmax(210px, 1fr)); gap:12px; }
        .dup-foto { border:1px solid var(--line); border-radius:12px; padding:12px 14px; }
        .dup-foto:last-child { border-color:var(--accent); background:var(--accent-soft); }
        .dup-foto-t { font-size:12px; font-weight:600; color:var(--ink-soft); margin-bottom:6px; }
        .dup-confirmar { margin-top:16px; }
        .dup-nota { margin-top:14px; }

        .dup-barra { display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:14px; }
        .dup-busca { display:flex; align-items:center; gap:8px; border:1px solid var(--line);
          border-radius:9px; padding:7px 12px; background:var(--surface); flex:1; max-width:340px; }
        .dup-busca input { border:none; outline:none; font-size:14px; font-family:inherit; width:100%; background:transparent; }
        .dup-vacio { display:flex; gap:14px; align-items:center; color:var(--ink-soft); }

        @media (max-width: 760px) {
          .dup-lado-a-lado, .dup-bloques { grid-template-columns:1fr; }
          .dup-preparar { margin-left:0; }
        }
      `}</style>
    </div>
  );
}

// --- Aviso al crear un paciente que quizá ya existe --------------------------
//
// Lo dispara el 409 de POST /api/pacientes/. No bloquea a nadie: muestra la
// ficha parecida al lado de lo que se está registrando y deja elegir. Los
// homónimos existen y dar de alta a una persona real nunca puede depender de
// que el sistema se convenza.

export function AvisoDuplicado({ aviso, onUsarExistente, onCrearIgual, onCerrar }) {
  const { payload, candidatos } = aviso;
  return (
    <div className="ca-modal-bg" onClick={onCerrar}>
      <div className="ca-modal dup-modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 760 }}>
        <div className="dup-modal-head">
          <div>
            <h2 className="ca-h1" style={{ fontSize: 19 }}>Encontramos una posible ficha existente</h2>
            <div className="ca-sub">Mira si es la misma persona antes de abrir una ficha nueva.</div>
          </div>
          <button className="ca-btn ghost" onClick={onCerrar}><X size={16} /></button>
        </div>

        <div className="dup-lado-a-lado">
          <div className="dup-col">
            <div className="dup-col-head"><strong>Nuevo registro</strong></div>
            <Dato etiqueta="Nombre" valor={payload.nombre} />
            <Dato etiqueta="Sede" valor={SEDE[payload.sede] || "—"} />
            <Dato etiqueta="Documento" valor={payload.numero_documento} />
            <Dato etiqueta="Teléfono" valor={payload.telefono} />
            <Dato etiqueta="Nacimiento" valor={payload.fecha_nacimiento} />
          </div>
          <div className="dup-col elegida">
            <div className="dup-col-head">
              <strong>Ya existe</strong>
              <span className="dup-badge">#{candidatos[0].id}</span>
            </div>
            <Dato etiqueta="Nombre" valor={candidatos[0].nombre} />
            <Dato etiqueta="Sede" valor={SEDE[candidatos[0].sede] || "—"} />
            <Dato etiqueta="Documento" valor={candidatos[0].documento} />
            <Dato etiqueta="Teléfono" valor={candidatos[0].telefono} />
            <Dato etiqueta="Nacimiento" valor={candidatos[0].fecha_nacimiento} />
            <Dato etiqueta="Psicólogo" valor={candidatos[0].profesional} />
            <div className="dup-senales" style={{ marginTop: 8 }}>
              {candidatos[0].senales.map((s) => <Senal key={s} clave={s} />)}
            </div>
          </div>
        </div>

        {candidatos.length > 1 && (
          <div style={{ marginTop: 12 }}>
            <div className="dup-bloque-t">Otras fichas parecidas</div>
            {candidatos.slice(1).map((c) => (
              <div key={c.id} className="dup-campo">
                <span className="dup-campo-k">#{c.id} {c.nombre}</span>
                <span className="dup-campo-v">{SEDE[c.sede] || "sin sede"} · tel {c.telefono || "—"}</span>
                <button className="ca-btn ghost" onClick={() => onUsarExistente(c.id)}>Usar esta</button>
              </div>
            ))}
          </div>
        )}

        <div className="dup-botonera">
          <button className="ca-btn" onClick={() => onUsarExistente(candidatos[0].id)}>
            Usar ficha existente
          </button>
          <button className="ca-btn ghost" onClick={onCrearIgual}>
            Es otra persona — crear ficha nueva
          </button>
        </div>
      </div>
    </div>
  );
}
