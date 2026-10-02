import { useEffect, useId, useRef } from "react";
import { X } from "lucide-react";
import { confirmar } from "./confirmar";

// Modal base. Cuatro tipos, porque no todos se cierran igual:
//   informativo  — se cierra con clic fuera, Escape o la X.
//   descartable  — igual, no guarda nada.
//   formulario   — si hay cambios sin guardar (`sucio`), cerrar pide confirmación;
//                  el clic fuera nunca cierra (era la causa de notas perdidas).
//   destructivo  — no se cierra con clic fuera; la acción va en el pie.
// Mientras `ocupado` (guardando), no se cierra de ninguna forma.
export default function Modal({
  titulo, tipo = "descartable", sucio = false, ocupado = false, ancho = 480, onCerrar, pie, children,
}) {
  const idTitulo = useId();
  const caja = useRef(null);

  async function intentarCerrar() {
    if (ocupado) return;
    if (tipo === "formulario" && sucio) {
      const descartar = await confirmar({
        titulo: "¿Descartar lo que escribiste?",
        mensaje: "Tienes cambios sin guardar. Si cierras ahora, se pierden.",
        confirmarTexto: "Descartar", cancelarTexto: "Seguir editando", peligro: true,
      });
      if (!descartar) return;
    }
    onCerrar?.();
  }

  const cerrarRef = useRef(intentarCerrar);
  useEffect(() => { cerrarRef.current = intentarCerrar; });

  useEffect(() => {
    const tecla = (e) => { if (e.key === "Escape") cerrarRef.current(); };
    document.addEventListener("keydown", tecla);
    const enfocable = caja.current?.querySelector("input, select, textarea, button:not([data-cerrar])");
    enfocable?.focus();
    return () => document.removeEventListener("keydown", tecla);
  }, []);

  const cierraConClicFuera = tipo === "informativo" || tipo === "descartable";

  return (
    <div className="ca-modal-bg" onClick={cierraConClicFuera ? () => cerrarRef.current() : undefined}>
      <div ref={caja} className="ca-modal" role="dialog" aria-modal="true" aria-labelledby={idTitulo}
        aria-busy={ocupado || undefined} style={{ maxWidth: ancho }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <strong id={idTitulo} style={{ fontSize: 16 }}>{titulo}</strong>
          <button type="button" data-cerrar aria-label="Cerrar" disabled={ocupado} onClick={() => cerrarRef.current()}
            style={{ background: "none", border: "none", cursor: ocupado ? "default" : "pointer", color: "var(--muted)" }}>
            <X size={18} />
          </button>
        </div>
        {children}
        {pie && <div style={{ display: "flex", gap: 9, justifyContent: "flex-end", marginTop: 4 }}>{pie}</div>}
      </div>
    </div>
  );
}

// Botón de guardar que no deja enviar dos veces: deshabilitado de verdad
// (no solo transparente) mientras guarda o si falta algo.
export function BotonGuardar({ ocupado, listo = true, onClick, children, textoOcupado = "Guardando…" }) {
  return (
    <button type="button" className="ca-btn" disabled={ocupado || !listo} aria-busy={ocupado || undefined}
      style={{ opacity: ocupado || !listo ? 0.55 : 1, cursor: ocupado || !listo ? "not-allowed" : "pointer" }}
      onClick={onClick}>
      {ocupado ? textoOcupado : children}
    </button>
  );
}
