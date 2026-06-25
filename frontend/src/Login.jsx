import React, { useState } from "react";

const C = {
  bg: "#F4FBFD", surface: "#FFFFFF", ink: "#343434", inkSoft: "#555555",
  muted: "#6E6E6E", line: "#DCEBEF", accent: "#0A7D92", accentSoft: "#D7F4FA",
};

export default function Login({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);

  async function enviar(e) {
    e.preventDefault();
    setError("");
    setCargando(true);
    try {
      await onLogin(email.trim(), password);
    } catch (err) {
      setError(err.message || "No se pudo iniciar sesión.");
    } finally {
      setCargando(false);
    }
  }

  const input = {
    width: "100%", border: `1px solid ${C.line}`, borderRadius: 9, padding: "11px 13px",
    fontSize: 14.5, fontFamily: "inherit", color: C.ink, outline: "none", marginTop: 6,
    background: C.surface,
  };
  const label = { fontSize: 12.5, fontWeight: 500, color: C.inkSoft };

  return (
    <div style={{
      fontFamily: "'Inter',-apple-system,system-ui,sans-serif", letterSpacing: "-0.01em",
      minHeight: "88vh", display: "flex", alignItems: "center", justifyContent: "center",
      background: C.bg, border: `1px solid ${C.line}`, borderRadius: 14, color: C.ink,
      WebkitFontSmoothing: "antialiased",
    }}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;450;500;600;700&display=swap');`}</style>
      <form onSubmit={enviar} style={{
        width: "100%", maxWidth: 380, background: C.surface, border: `1px solid ${C.line}`,
        borderRadius: 16, padding: "30px 28px", boxShadow: "0 12px 40px rgba(40,38,34,.06)",
      }}>
        <img src={`${import.meta.env.BASE_URL}itaca-logo-v.png`} alt="Itaca Conversemos"
          style={{ display: "block", width: 190, maxWidth: "72%", height: "auto", margin: "0 auto 8px" }}
          onError={(e) => { e.currentTarget.style.display = "none"; }} />
        <p style={{ fontSize: 13.5, color: C.inkSoft, textAlign: "center", margin: "4px 0 22px" }}>
          Ingresa para gestionar tu consultorio.
        </p>

        <div style={{ marginBottom: 14 }}>
          <div style={label}>Correo</div>
          <input style={input} type="email" value={email} autoFocus autoComplete="username"
            onChange={(e) => setEmail(e.target.value)} placeholder="tucorreo@clinica.pe" />
        </div>
        <div style={{ marginBottom: 18 }}>
          <div style={label}>Contraseña</div>
          <input style={input} type="password" value={password} autoComplete="current-password"
            onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
        </div>

        {error && (
          <div style={{
            background: "#F7E5E5", color: "#9C4646", borderRadius: 9, padding: "9px 12px",
            fontSize: 13, marginBottom: 14,
          }}>{error}</div>
        )}

        <button type="submit" disabled={cargando || !email.trim() || !password}
          style={{
            width: "100%", background: C.accent, color: "#fff", border: "none", padding: "11px 14px",
            borderRadius: 9, fontSize: 14.5, fontWeight: 500, cursor: "pointer", fontFamily: "inherit",
            opacity: cargando || !email.trim() || !password ? 0.6 : 1,
          }}>
          {cargando ? "Ingresando…" : "Ingresar"}
        </button>
      </form>
    </div>
  );
}
