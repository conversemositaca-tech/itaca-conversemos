// Página PÚBLICA de preferencias de correo (Email 1.0): /preferencias/correo/<token>/
//
// Sin login: el token es un UUID aleatorio que solo tiene quien recibió el
// correo. No muestra nada de la persona salvo su correo enmascarado.
//
// Con ?baja=1 (el enlace "Cancelar suscripción" del pie) da de baja al abrirse.
// Lo hace con JavaScript a propósito: los antivirus de correo "visitan" los
// enlaces sin ejecutar scripts, así que no pueden dar de baja a nadie por error.
import { useEffect, useRef, useState } from "react";
import { api } from "./api";

const C = { celeste: "#00B8D8", celesteClaro: "#D7F4FA", gris: "#6E6E6E", negro: "#343434", blanco: "#FFFFFF" };
const FUENTE = "Montserrat, Arial, Helvetica, sans-serif";

export default function PreferenciasCorreo({ token }) {
  const [d, setD] = useState(null);
  const [marcada, setMarcada] = useState(false);
  const [err, setErr] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [aviso, setAviso] = useState("");
  const bajaHecha = useRef(false);

  useEffect(() => {
    const prev = document.title;
    document.title = "Preferencias de correo · Ítaca Conversemos";
    const quiereBaja = new URLSearchParams(window.location.search).get("baja") === "1";
    const cargar = () => api.correoPreferencias(token).then((r) => { setD(r); setMarcada(!!r.marketing); });
    (async () => {
      try {
        if (quiereBaja && !bajaHecha.current) {
          bajaHecha.current = true;
          await api.correoBaja(token);
          setAviso("Listo. Ya no recibirás correos con contenidos ni novedades. Los correos sobre tus reservas seguirán llegando.");
        }
        await cargar();
      } catch (e) { setErr(e.message || "Este enlace no es válido."); }
    })();
    return () => { document.title = prev; };
  }, [token]);

  async function guardar() {
    setGuardando(true); setErr(""); setAviso("");
    try {
      const r = await api.correoGuardarPreferencias(token, { marketing: marcada === true });
      setD(r); setMarcada(!!r.marketing);
      setAviso("Guardamos tus preferencias.");
    } catch (e) { setErr(e.message || "No pudimos guardar. Inténtalo de nuevo."); }
    finally { setGuardando(false); }
  }

  return (
    <div style={{ minHeight: "100vh", background: C.blanco, fontFamily: FUENTE, color: C.negro, padding: "40px 16px" }}>
      <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;600&display=swap" rel="stylesheet" />
      <main style={{ maxWidth: 520, margin: "0 auto", border: `1px solid ${C.celesteClaro}`, borderRadius: 12, padding: "32px 28px" }}>
        <img src="/itaca-logo-h.png" alt="Ítaca Conversemos" width="200" style={{ display: "block", width: 200, height: "auto", marginBottom: 20 }} />
        <div style={{ height: 3, width: 48, background: C.celeste, marginBottom: 24 }} />
        <h1 style={{ fontSize: 22, fontWeight: 600, margin: "0 0 18px" }}>Preferencias de correo</h1>

        {aviso ? (
          <p role="status" style={{ background: C.celesteClaro, borderRadius: 8, padding: "12px 14px", fontSize: 14.5, lineHeight: 1.55, margin: "0 0 18px" }}>{aviso}</p>
        ) : null}
        {err ? <p role="alert" style={{ color: "#9C4646", fontSize: 14.5, margin: "0 0 18px" }}>{err}</p> : null}

        {d ? (
          <>
            <label style={{ display: "flex", gap: 12, alignItems: "flex-start", cursor: "pointer", fontSize: 15, lineHeight: 1.55, marginBottom: 14 }}>
              <input type="checkbox" checked={marcada} onChange={(e) => setMarcada(e.target.checked)}
                style={{ marginTop: 4, width: 18, height: 18, accentColor: C.celeste, flexShrink: 0 }} />
              <span>{d.texto}</span>
            </label>
            <p style={{ color: C.gris, fontSize: 14, margin: "0 0 22px 30px" }}>{d.correo}</p>
            <button onClick={guardar} disabled={guardando}
              style={{ background: C.celeste, color: C.blanco, border: "none", borderRadius: 8, padding: "12px 22px", fontFamily: FUENTE, fontSize: 15, fontWeight: 600, cursor: "pointer", opacity: guardando ? 0.6 : 1 }}>
              {guardando ? "Guardando…" : "Guardar preferencias"}
            </button>
          </>
        ) : !err ? <p style={{ color: C.gris }}>Cargando…</p> : null}

        <p style={{ color: C.gris, fontSize: 12.5, fontWeight: 300, lineHeight: 1.6, marginTop: 28 }}>
          Los correos sobre una reserva o una cita que pediste no dependen de esta casilla.
        </p>
      </main>
    </div>
  );
}
