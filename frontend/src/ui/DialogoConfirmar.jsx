import { useEffect, useRef } from "react";

// Diálogo que usa confirmar() (ui/confirmar.js). No se monta a mano.
export default function DialogoConfirmar({ titulo, mensaje, confirmarTexto, cancelarTexto, peligro, onRespuesta }) {
  const volver = useRef(null);
  const aceptar = useRef(null);

  useEffect(() => {
    (peligro ? volver : aceptar).current?.focus();
    const tecla = (e) => { if (e.key === "Escape") onRespuesta(false); };
    document.addEventListener("keydown", tecla);
    return () => document.removeEventListener("keydown", tecla);
  }, [peligro, onRespuesta]);

  return (
    <div className="ca-modal-bg" style={{ zIndex: 10000 }}>
      <div className="ca-modal" role="alertdialog" aria-modal="true" aria-labelledby="confirmar-titulo"
        aria-describedby="confirmar-mensaje" style={{ maxWidth: 420 }}>
        <strong id="confirmar-titulo" style={{ fontSize: 16, display: "block", marginBottom: 8 }}>{titulo}</strong>
        <p id="confirmar-mensaje" style={{ margin: "0 0 18px", fontSize: 14, lineHeight: 1.5, color: "var(--ink)" }}>{mensaje}</p>
        <div style={{ display: "flex", gap: 9, justifyContent: "flex-end" }}>
          <button ref={volver} type="button" className="ca-btn ghost" onClick={() => onRespuesta(false)}>{cancelarTexto}</button>
          <button ref={aceptar} type="button" className="ca-btn"
            style={peligro ? { background: "#B23A3A", borderColor: "#B23A3A" } : undefined}
            onClick={() => onRespuesta(true)}>{confirmarTexto}</button>
        </div>
      </div>
    </div>
  );
}
