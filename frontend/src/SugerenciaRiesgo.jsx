import { useEffect, useState } from "react";
import { api } from "./api";

const NIVELES = [
  { v: "bajo", l: "Bajo" },
  { v: "moderado", l: "Moderado" },
  { v: "alto", l: "Alto" },
];

// Riesgo que propuso la IA al estructurar una nota. No es el valor oficial:
// solo el psicólogo del paciente o un admin lo confirma, lo cambia o lo descarta.
export default function SugerenciaRiesgo({ pacienteId, puedeResolver, showToast, onResuelta }) {
  const [sugerencia, setSugerencia] = useState(null);
  const [valor, setValor] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    let vivo = true;
    api.sugerenciasRiesgo(pacienteId)
      .then((lista) => { if (vivo) setSugerencia(Array.isArray(lista) && lista.length ? lista[0] : null); })
      .catch(() => { if (vivo) setSugerencia(null); });
    return () => { vivo = false; };
  }, [pacienteId]);

  if (!sugerencia) return null;

  async function resolver(decision) {
    if (decision === "modificar" && !valor) {
      showToast?.("Error: elige el nivel de riesgo antes de guardar.");
      return;
    }
    setEnviando(true);
    try {
      await api.resolverSugerenciaRiesgo(sugerencia.id, decision, valor || undefined);
      setSugerencia(null);
      showToast?.(decision === "rechazar" ? "Sugerencia descartada. El riesgo no cambió." : "Riesgo actualizado.");
      onResuelta?.();
    } catch (e) {
      showToast?.("Error: " + (e?.message || "no se pudo guardar la revisión."));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div role="status" style={{ marginTop: 10, padding: "8px 10px", borderRadius: 8, background: "#FFF6E5", color: "#6B4A1F", fontSize: 12.5, lineHeight: 1.45 }}>
      <div>
        <strong>Sugerencia de la IA: {sugerencia.valor_sugerido_label}</strong>. Pendiente de revisión clínica; no es el riesgo oficial.
      </div>
      {puedeResolver && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center", marginTop: 6 }}>
          <button type="button" className="ca-btn" disabled={enviando} onClick={() => resolver("confirmar")}>Confirmar</button>
          <label htmlFor={`riesgo-mod-${sugerencia.id}`} style={{ position: "absolute", left: -9999 }}>Otro nivel de riesgo</label>
          <select id={`riesgo-mod-${sugerencia.id}`} className="ca-input" value={valor} disabled={enviando}
            onChange={(e) => setValor(e.target.value)} style={{ width: "auto" }}>
            <option value="">Otro nivel…</option>
            {NIVELES.map((n) => <option key={n.v} value={n.v}>{n.l}</option>)}
          </select>
          <button type="button" className="ca-btn" disabled={enviando || !valor} onClick={() => resolver("modificar")}>Guardar nivel</button>
          <button type="button" className="ca-btn" disabled={enviando} onClick={() => resolver("rechazar")}>Descartar</button>
        </div>
      )}
    </div>
  );
}
