import React, { useState } from "react";
import { Eye, EyeOff } from "lucide-react";

/**
 * Campo de contraseña con el ojito para ver lo que se escribió.
 *
 * Acepta lo mismo que un <input> (style, className, value, onChange…) y
 * sirve tanto en el login (estilos en línea) como dentro del sistema
 * (`className="ca-input"`). Los márgenes verticales del `style` pasan al
 * contenedor para que el ojito quede centrado respecto a la caja del campo.
 */
export default function InputClave({ style = {}, className, ...props }) {
  const [ver, setVer] = useState(false);
  const { marginTop, marginBottom, ...estiloInput } = style;
  const texto = ver ? "Ocultar contraseña" : "Mostrar contraseña";
  return (
    <div style={{ position: "relative", marginTop, marginBottom }}>
      <input
        {...props}
        type={ver ? "text" : "password"}
        className={className}
        style={{ ...estiloInput, paddingRight: 42, boxSizing: "border-box" }}
      />
      <button
        type="button"
        onClick={() => setVer((v) => !v)}
        aria-label={texto}
        aria-pressed={ver}
        title={texto}
        style={{
          position: "absolute", top: 0, bottom: 0, right: 0, width: 40,
          display: "flex", alignItems: "center", justifyContent: "center",
          background: "none", border: "none", padding: 0, cursor: "pointer",
          color: "var(--muted, #6E6E6E)",
        }}
      >
        {ver ? <EyeOff size={18} /> : <Eye size={18} />}
      </button>
    </div>
  );
}
