// Páginas públicas del sitio de Ítaca Conversemos: inicio, quiénes somos,
// psicólogos, terapias online y preguntas frecuentes.
//
// Viven dentro de la misma app que el agendamiento y reusan su marco (cabecera,
// pie, WhatsApp) y su sistema visual, para que reservar no sea un salto a otro
// lugar sino el paso siguiente de la misma página.
//
// El equipo y los precios NO están escritos aquí: salen de `GET /api/sitio/`,
// o sea de la base del sistema. Si entra o sale un psicólogo, la web cambia sola.
import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight, Check, ChevronDown, Clock, Compass, GraduationCap, Heart, HeartHandshake, MapPin,
  MessageCircle, MessagesSquare, Shield, Sprout, User, Users,
} from "lucide-react";

// Iconos lineales de los servicios y los principios, en un solo lugar para que
// el trazo sea el mismo en toda la página.
const ICONOS_SERVICIO = {
  individual: User, grupal: Users, pareja: HeartHandshake, vocacional: Compass,
  desarrollo: Sprout, talleres: MessagesSquare, objetivo: Check, comunidad: Users, aprendizaje: Heart,
};

import {
  AGENDA_CSS, AGENDA_SEDES, AgendaDuda, AgendaPie, AgendaTop, AgendaWa, agendaFaq,
  agendaWhatsapp,
} from "./App.jsx";
import datosDePaginas from "./paginas.json";
import { PASOS as PASOS_EMBUDO, registrar } from "./embudo";
import { SITE_ROUTES, alCambiarRuta, propsEnlace, rutaCanonica } from "./rutas";
import { INICIO, PASOS, PREGUNTAS, PSICOLOGOS, QUIENES_SOMOS, TERAPIAS, TESTIMONIOS } from "./sitio-textos";

// Estilos propios de las páginas de contenido. Se apoyan en los tokens del
// agendamiento (papel crema, tinta cálida, acento turquesa legible): aquí solo
// va lo que el formulario no necesitaba —rejillas, secciones anchas, citas—.
// ── Sistema visual nuevo, por ahora solo en "Quiénes somos" ──────────────
// Vive en clases `sw-*` para no alterar las páginas que todavía no se
// rediseñan. Ritmo: blanco → celeste → blanco → petróleo → celeste, en vez de
// una sucesión de tarjetas sobre el mismo fondo.
const SW_CSS = `
/* El contenedor .ag es flex en fila (lo hereda del panel): apilamos en columna
   para que cabecera, contenido y pie ocupen todo el ancho. No se toca .ag, que
   es también el marco del agendamiento ya publicado. */
.sw-sitio { display:flex; flex-direction:column; align-items:stretch; }
.sw-tema { background:var(--clinico); color:var(--txt); }
.sw-wrap { width:100%; max-width:1200px; margin:0 auto; padding-inline:clamp(20px,4vw,40px); }
.sw-sec { padding-block:clamp(56px,7.5vw,104px); }
.sw-blanco { background:var(--blanco); }
.sw-celeste { background:var(--t-suave); }
.sw-celeste .sw-eyebrow, .sw-celeste .sw-enlace { color:var(--t-sobre-suave); }
.sw-celeste .sw-btn-linea { color:var(--t-sobre-suave); border-color:rgba(8,94,113,.4); }
.sw-hondo { background:var(--t-profundo); color:#fff; }

.sw-eyebrow {
  font-size:12px; font-weight:600; letter-spacing:.18em; text-transform:uppercase;
  color:var(--t-profundo); margin:0 0 18px;
}
.sw-h1 {
  font-family:var(--serif); font-optical-sizing:auto; font-weight:400;
  font-size:clamp(34px,4.6vw,56px); line-height:1.08; letter-spacing:-0.015em;
  color:var(--txt); margin:0 0 22px; max-width:15ch; text-wrap:balance;
}
.sw-h2 {
  font-family:var(--serif); font-optical-sizing:auto; font-weight:400;
  font-size:clamp(27px,3.2vw,40px); line-height:1.15; letter-spacing:-0.012em;
  color:var(--txt); margin:0 0 14px; max-width:20ch; text-wrap:balance;
}
.sw-h2-c { max-width:24ch; margin-inline:auto; text-align:center; }
.sw-lee p { font-size:clamp(17px,1.15vw,18.5px); line-height:1.72; color:var(--txt-2); margin:0 0 18px; max-width:63ch; }
.sw-lee p:last-child { margin-bottom:0; }
.sw-intro { font-size:17px; line-height:1.7; color:var(--txt-2); margin:0 0 40px; max-width:60ch; }
.sw-intro-c { text-align:center; margin-inline:auto; }

/* Botones */
.sw-acciones { display:flex; flex-wrap:wrap; align-items:center; gap:14px 22px; margin-top:34px; }
.sw-btn {
  display:inline-flex; align-items:center; gap:9px; text-decoration:none; cursor:pointer;
  font-family:inherit; font-size:16px; font-weight:600; border:none;
  padding:16px 28px; border-radius:999px; background:var(--t-profundo); color:#fff;
  transition:background .16s, transform .16s var(--curva), box-shadow .16s var(--curva);
}
.sw-btn:hover { background:#0B6A7C; transform:translateY(-1px); box-shadow:0 8px 20px rgba(10,125,146,.24); }
.sw-btn svg { transition:transform .16s var(--curva); }
.sw-btn:hover svg { transform:translateX(3px); }
.sw-btn-claro { background:#fff; color:var(--t-hondo); }
.sw-btn-claro:hover { background:#fff; box-shadow:0 8px 20px rgba(0,0,0,.16); }
.sw-btn-linea {
  background:transparent; color:var(--t-profundo); border:1.5px solid rgba(10,125,146,.35);
  padding:14.5px 26px;
}
.sw-btn-linea:hover { background:rgba(10,125,146,.06); border-color:var(--t-profundo); box-shadow:none; }
.sw-enlace {
  display:inline-flex; align-items:center; gap:7px; font-size:16px; font-weight:600;
  color:var(--t-profundo); text-decoration:none; border-bottom:1.5px solid rgba(10,125,146,.28);
  padding-bottom:2px; transition:border-color .16s, gap .16s;
}
.sw-enlace:hover { border-color:var(--t-profundo); gap:11px; }

/* 1 · Hero 52/48 con la foto real del equipo */
.sw-hero { padding-block:clamp(48px,6.5vw,92px); overflow-x:clip; }
.sw-hero-in { display:grid; gap:clamp(32px,5vw,64px); align-items:center; grid-template-columns:minmax(0,1fr); }
@media (min-width:940px) { .sw-hero-in { grid-template-columns:52fr 48fr; } }
.sw-hero-in > * { min-width:0; }
.sw-foto { position:relative; }
/* Halo celeste: acompaña a la foto, no la disfraza. */
.sw-foto::before {
  content:''; position:absolute; inset:auto -4% -6% -8%; height:72%;
  background:var(--t-suave); border-radius:48% 52% 46% 54% / 60% 46% 54% 40%; z-index:0;
}
.sw-foto img {
  position:relative; z-index:1; display:block; width:100%; height:auto;
  border-radius:28px; background:var(--blanco);
}

/* 2 · Qué hacemos — rejilla 3×2, iconos lineales */
.sw-serv { display:grid; gap:clamp(18px,2.4vw,30px); grid-template-columns:repeat(auto-fit,minmax(min(260px,100%),1fr)); }
@media (min-width:900px) { .sw-serv { grid-template-columns:repeat(3,1fr); } }
.sw-serv li { list-style:none; }
.sw-serv-ico {
  width:46px; height:46px; border-radius:14px; display:flex; align-items:center; justify-content:center;
  background:var(--blanco); color:var(--t-profundo); margin-bottom:14px;
}
.sw-serv h3 { font-size:17.5px; font-weight:600; letter-spacing:-0.015em; color:var(--txt); margin:0 0 5px; }
.sw-serv p { font-size:15px; line-height:1.6; color:var(--txt-2); margin:0; max-width:34ch; }

/* 3 · Áreas — tres pilares numerados, no otra lista con checks */
.sw-pilares { display:grid; gap:0; margin:0; padding:0; list-style:none; counter-reset:pilar; }
@media (min-width:880px) { .sw-pilares { grid-template-columns:repeat(3,1fr); } }
.sw-pilar { position:relative; padding:30px 30px 30px 0; border-top:2px solid var(--t-suave); }
@media (min-width:880px) {
  .sw-pilar { padding:34px 34px 10px 0; }
  .sw-pilar + .sw-pilar { padding-left:34px; }
}
.sw-pilar-n {
  display:block; font-family:var(--serif); font-size:34px; font-weight:400; line-height:1;
  color:var(--t-profundo); margin-bottom:14px;
}
.sw-pilar h3 { font-size:18px; font-weight:600; letter-spacing:-0.015em; color:var(--txt); margin:0 0 7px; max-width:22ch; }
.sw-pilar p { font-size:15px; line-height:1.6; color:var(--txt-2); margin:0; max-width:32ch; }

/* 4 · Modelo integrativo — composición dividida */
.sw-modelo { display:grid; gap:clamp(32px,5vw,64px); align-items:center; grid-template-columns:minmax(0,1fr); }
@media (min-width:940px) { .sw-modelo { grid-template-columns:47fr 53fr; } }
.sw-modelo > * { min-width:0; }
.sw-modelo img { display:block; width:100%; height:auto; border-radius:26px; }
.sw-cita {
  font-family:var(--serif); font-size:clamp(20px,2.1vw,25px); line-height:1.4; font-weight:400;
  color:var(--t-profundo); margin:0 0 26px; padding-left:20px; border-left:3px solid var(--t-vivo);
  max-width:26ch;
}
.sw-dims { display:flex; flex-wrap:wrap; gap:9px; margin:26px 0 0; padding:0; list-style:none; }
.sw-dims li {
  font-size:14.5px; font-weight:500; color:var(--t-sobre-suave); background:var(--t-suave);
  border-radius:999px; padding:9px 17px;
}

/* 5 · En lo que creemos — franja petróleo */
.sw-creencias { display:grid; gap:0; margin:0; padding:0; list-style:none; }
@media (min-width:880px) { .sw-creencias { grid-template-columns:repeat(3,1fr); } }
.sw-creencia { padding:28px 0; border-top:1px solid rgba(255,255,255,.22); }
@media (min-width:880px) {
  .sw-creencia { padding:0 34px; border-top:none; border-left:1px solid rgba(255,255,255,.22); }
  .sw-creencia:first-child { padding-left:0; border-left:none; }
  .sw-creencia:last-child { padding-right:0; }
}
.sw-creencia svg { color:rgba(255,255,255,.85); margin-bottom:16px; }
.sw-creencia p { font-size:17px; line-height:1.6; color:#fff; margin:0; max-width:28ch; }
.sw-hondo .sw-h2, .sw-hondo .sw-eyebrow { color:#fff; }
.sw-lee-claro p { color:rgba(255,255,255,.86); }
.sw-hondo .sw-eyebrow { color:rgba(255,255,255,.7); }

/* 6 · Cierre */
.sw-cierre { text-align:center; }
.sw-cierre .sw-acciones { justify-content:center; margin-top:30px; }
.sw-sedes { display:grid; gap:20px; grid-template-columns:repeat(auto-fit,minmax(min(260px,100%),1fr));
  max-width:720px; margin:44px auto 0; padding-top:26px; border-top:1px solid rgba(10,125,146,.18); }
.sw-sede { display:flex; gap:11px; text-align:left; justify-content:center; }
.sw-sede svg { color:var(--t-profundo); flex-shrink:0; margin-top:3px; }
.sw-sede strong { display:block; font-size:15px; color:var(--txt); letter-spacing:-0.01em; }
.sw-sede span { display:block; font-size:14px; color:var(--txt-2); line-height:1.5; }
.sw-sede a { display:inline-block; margin-top:3px; font-size:14px; font-weight:600; color:var(--t-profundo); text-decoration:none; }
.sw-sede a:hover { text-decoration:underline; }

/* ── Psicólogos ──────────────────────────────────────────────────────── */
.sw-equipo { display:grid; gap:clamp(18px,2.2vw,26px); grid-template-columns:repeat(auto-fill,minmax(min(320px,100%),1fr)); }
.sw-prof {
  background:var(--blanco); border-radius:24px; padding:26px; display:flex; flex-direction:column;
  box-shadow:0 1px 2px rgba(8,94,113,.05), 0 10px 30px rgba(8,94,113,.06);
}
.sw-prof-top { display:flex; align-items:center; gap:16px; }
.sw-prof-foto { width:76px; height:76px; border-radius:50%; object-fit:cover; flex-shrink:0; background:var(--t-suave); }
.sw-prof-ini { display:flex; align-items:center; justify-content:center; font-weight:600; font-size:27px; color:var(--t-sobre-suave); }
.sw-prof-nombre { font-size:19px; font-weight:600; letter-spacing:-0.02em; color:var(--txt); margin:0; }
.sw-prof-meta { font-size:13px; line-height:1.5; color:var(--txt-2); margin:4px 0 0; }
.sw-prof-cps { font-weight:600; color:var(--t-sobre-suave); }
.sw-prof-frase {
  font-family:var(--serif); font-size:16.5px; line-height:1.45; color:var(--t-sobre-suave);
  margin:20px 0 0; padding-left:16px; border-left:2px solid var(--t-suave);
}
.sw-prof-campos { margin:20px 0 0; display:grid; gap:12px; }
.sw-campo strong {
  display:block; font-size:10.5px; font-weight:600; letter-spacing:.1em; text-transform:uppercase;
  color:var(--txt-2); margin-bottom:3px;
}
.sw-campo span { font-size:14.5px; line-height:1.55; color:var(--txt-2); }
.sw-corta { display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; }
.sw-prof-pie { margin-top:auto; padding-top:22px; display:flex; flex-wrap:wrap; gap:10px 16px; align-items:center; }
.sw-prof-pie .sw-btn { padding:12px 20px; font-size:14.5px; }
.sw-mas { margin-top:18px; border-top:1px solid var(--linea-cl); padding-top:14px; }
.sw-mas summary {
  display:flex; align-items:center; justify-content:space-between; gap:8px; cursor:pointer;
  list-style:none; font-size:14px; font-weight:600; color:var(--t-sobre-suave); padding:2px 0;
}
.sw-mas summary::-webkit-details-marker { display:none; }
.sw-mas summary svg { transition:transform .18s var(--curva); }
.sw-mas[open] summary svg { transform:rotate(180deg); }
.sw-filtros { display:flex; flex-wrap:wrap; gap:10px; margin:0 0 34px; }
.sw-filtro {
  font-family:inherit; font-size:15px; font-weight:500; cursor:pointer; color:var(--txt-2);
  background:var(--blanco); border:1px solid var(--linea-cl); border-radius:999px; padding:11px 22px;
  transition:border-color .15s, color .15s, background .15s;
}
.sw-filtro:hover { border-color:var(--t-profundo); color:var(--t-profundo); }
.sw-filtro[aria-pressed="true"] { background:var(--t-profundo); border-color:var(--t-profundo); color:#fff; }
.sw-cargando { font-size:16px; color:var(--txt-2); padding:10px 0; }
.sw-aviso {
  background:var(--t-suave); border-radius:20px; padding:24px 26px;
  font-size:16px; line-height:1.6; color:var(--t-sobre-suave); max-width:62ch;
}

/* ── Preguntas ───────────────────────────────────────────────────────── */
.sw-faq { max-width:820px; }
.sw-tema .ag-dudas { margin-top:0; }
.sw-tema .ag-duda { border-top:1px solid var(--linea-cl); }
.sw-tema .ag-duda:last-of-type { border-bottom:1px solid var(--linea-cl); }
.sw-tema .ag-duda summary { font-size:17px; font-weight:500; color:var(--txt); padding:22px 0; gap:20px; }
.sw-tema .ag-duda summary:hover { color:var(--t-sobre-suave); }
.sw-tema .ag-duda[open] summary { color:var(--t-sobre-suave); font-weight:600; }
.sw-tema .ag-duda summary svg { color:var(--t-profundo); }
.sw-tema .ag-duda-txt { font-size:16.5px; line-height:1.72; color:var(--txt-2); max-width:68ch; }
.sw-tema .ag-rotulo { color:var(--txt-2); }

/* ── Terapias online ─────────────────────────────────────────────────── */
.sw-chips { display:flex; flex-wrap:wrap; gap:10px; margin:0; padding:0; list-style:none; }
.sw-chips li {
  font-size:15px; font-weight:500; color:var(--txt-2); background:var(--blanco);
  border:1px solid var(--linea-cl); border-radius:999px; padding:10px 18px;
}
.sw-celeste .sw-chips li { background:rgba(255,255,255,.75); border-color:transparent; color:var(--t-sobre-suave); }
.sw-precios { display:grid; gap:16px; grid-template-columns:repeat(auto-fit,minmax(min(250px,100%),1fr)); }
.sw-precio {
  background:var(--blanco); border-radius:20px; padding:24px;
  box-shadow:0 1px 2px rgba(8,94,113,.05), 0 8px 24px rgba(8,94,113,.05);
  display:flex; flex-direction:column; gap:10px;
}
.sw-precio h3 { font-size:16px; font-weight:600; color:var(--txt); margin:0; letter-spacing:-0.01em; }
.sw-precio b { font-family:var(--serif); font-size:30px; font-weight:400; color:var(--t-profundo); line-height:1; margin-top:auto; }
.sw-circulos { display:grid; gap:clamp(18px,2.4vw,26px); grid-template-columns:repeat(auto-fit,minmax(min(300px,100%),1fr)); }
.sw-circulo { background:var(--blanco); border-radius:24px; padding:28px; }
.sw-circulo h3 { font-family:var(--serif); font-size:22px; font-weight:400; color:var(--txt); margin:0 0 12px; }
.sw-circulo .preg { font-size:15px; line-height:1.62; color:var(--t-sobre-suave); margin:0 0 14px; }
.sw-circulo p { font-size:15.5px; line-height:1.65; color:var(--txt-2); margin:0; }

/* ── Inicio ──────────────────────────────────────────────────────────── */
.sw-senas { display:flex; flex-wrap:wrap; gap:10px 26px; margin:30px 0 0; padding:0; list-style:none; }
.sw-senas li { display:flex; align-items:center; gap:9px; font-size:14.5px; font-weight:500; color:var(--txt-2); }
.sw-senas svg { color:var(--t-profundo); flex-shrink:0; }
.sw-pasos { display:grid; gap:clamp(16px,2vw,22px); grid-template-columns:repeat(auto-fit,minmax(min(240px,100%),1fr)); margin:0; padding:0; list-style:none; counter-reset:paso; }
.sw-paso { counter-increment:paso; }
.sw-paso::before {
  content:counter(paso,decimal-leading-zero); display:block; font-family:var(--serif);
  font-size:26px; font-weight:400; color:var(--t-profundo); margin-bottom:10px;
}
.sw-paso h3 { font-size:17px; font-weight:600; color:var(--txt); margin:0 0 6px; letter-spacing:-0.015em; }
.sw-paso p { font-size:15px; line-height:1.6; color:var(--txt-2); margin:0; }
.sw-caras { display:flex; flex-wrap:wrap; gap:12px; margin:0 0 28px; padding:0; list-style:none; }
.sw-caras img, .sw-caras .sw-cara-ini {
  width:64px; height:64px; border-radius:50%; object-fit:cover; display:block; background:var(--t-suave);
}
.sw-cara-ini { display:flex; align-items:center; justify-content:center; font-weight:600; color:var(--t-sobre-suave); }
.sw-testis { display:grid; gap:clamp(18px,2.2vw,26px); grid-template-columns:repeat(auto-fit,minmax(min(420px,100%),1fr)); }
.sw-testi { background:var(--blanco); border-radius:24px; padding:30px; margin:0; display:flex; flex-direction:column; }
.sw-testi blockquote { margin:0; }
.sw-testi p { font-size:16px; line-height:1.72; color:var(--txt-2); margin:0 0 20px; }
.sw-testi figcaption { margin-top:auto; display:flex; align-items:center; gap:12px; }
.sw-testi-ini {
  width:42px; height:42px; border-radius:50%; display:flex; align-items:center; justify-content:center;
  background:var(--t-suave); color:var(--t-sobre-suave); font-weight:600; font-size:15px; flex-shrink:0;
}
.sw-testi-quien { display:block; font-size:15.5px; font-weight:600; color:var(--txt); letter-spacing:-0.01em; }
.sw-testi-rol { display:block; font-size:13.5px; color:var(--txt-2); margin-top:1px; }
.sw-mosaico { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin:0; padding:0; list-style:none; }
.sw-mosaico img, .sw-mosaico .sw-cara-ini {
  width:100%; height:auto; aspect-ratio:1; border-radius:18px; object-fit:cover; font-size:26px;
}
.sw-mosaico-pie { font-size:14px; line-height:1.55; color:var(--txt-2); margin:14px 0 0; }

/* Fotografías del consultorio (material propio de la clínica) */
.sw-foto-sec { display:block; width:100%; height:auto; border-radius:26px; object-fit:cover; }
.sw-foto-ancha {
  display:block; width:100%; height:auto; max-height:380px; object-fit:cover;
  border-radius:26px; margin:0 0 clamp(28px,3.5vw,42px);
}
.sw-foto-cierre {
  display:block; width:100%; max-width:560px; height:auto; aspect-ratio:16/10; object-fit:cover;
  border-radius:24px; margin:0 auto clamp(26px,3vw,36px);
}

@media (max-width:600px) {
  .sw-foto::before { inset:auto -6% -5% -6%; height:60%; }
  .sw-circulo, .sw-testi { padding:22px; }
  .sw-serv-ico { width:42px; height:42px; }
  .sw-prof { padding:22px; }
  .sw-prof-foto { width:64px; height:64px; }
  .sw-prof-pie { flex-direction:column; align-items:stretch; }
  .sw-prof-pie .sw-btn { justify-content:center; }
}
`;

const iniciales = (n) => (n || "?").replace(/^lic\.?\s*/i, "").trim().charAt(0).toUpperCase();

/** Enlace de reserva: el mismo para todos los CTA del sitio, sin depender de
 *  que la API haya respondido. Sale de SITE_ROUTES. */
function hrefReserva() {
  return SITE_ROUTES.agendar;
}

/** Cierre común: la misma invitación al final de cada página. */
function Cierre({ titulo = "¿Damos el primer paso?", texto }) {
  const hrefCita = hrefReserva();
  return (
    <section className="sw-sec sw-celeste">
      <div className="sw-wrap sw-cierre">
        <img className="sw-foto-cierre" src={`${import.meta.env.BASE_URL}sitio/bienvenida.jpg`}
          width="1600" height="1066" loading="lazy"
          alt="Psicóloga de Ítaca Conversemos recibiendo a un paciente en la sede" />
        <h2 className="sw-h2 sw-h2-c">{titulo}</h2>
        <p className="sw-intro sw-intro-c">
          {texto || "Elige sede, psicólogo y horario. Coordinación confirma contigo antes de la sesión y no pagas nada al reservar."}
        </p>
        <div className="sw-acciones">
          <a className="sw-btn" href={hrefCita}>
            Pide tu cita <ArrowRight size={18} strokeWidth={2.2} aria-hidden="true" />
          </a>
          {/* Uno por sede: quien escribe llega a la ciudad que lo atiende, no a
              un número que después tiene que derivar la consulta a mano. */}
          {Object.keys(AGENDA_SEDES).map((sede) => (
            <a key={sede} className="sw-btn sw-btn-linea" href={agendaWhatsapp(sede)}
              target="_blank" rel="noopener noreferrer">
              WhatsApp {AGENDA_SEDES[sede].label} <MessageCircle size={17} strokeWidth={2} aria-hidden="true" />
            </a>
          ))}
        </div>
        <div className="sw-sedes">
          {Object.entries(AGENDA_SEDES).map(([k, se]) => (
            <div key={k} className="sw-sede">
              <MapPin size={17} strokeWidth={1.9} aria-hidden="true" />
              <div>
                <strong>{se.label}</strong>
                <span>{se.direccion}</span>
                <a href={`tel:${se.telefono.replace(/\s/g, "")}`}>{se.telefono}</a>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── Página: inicio ────────────────────────────────────────────────────────
function PaginaInicio({ datos, faq }) {
  const equipo = datos?.equipo || [];
  const conFoto = equipo.filter((x) => x.foto);
  const mosaico = conFoto.slice(0, Math.min(9, Math.floor(conFoto.length / 3) * 3));
  const hrefCita = hrefReserva();
  return (
    <>
      <section className="sw-sec sw-hero">
        <div className="sw-wrap">
          <div className="sw-hero-in">
            <div>
              <p className="sw-eyebrow">{INICIO.rotulo}</p>
              <h1 className="sw-h1">Este espacio <em>es para ti</em>.</h1>
              <div className="sw-lee"><p>{INICIO.entrada}</p></div>
              <div className="sw-acciones">
                <a className="sw-btn" href={hrefCita}>
                  Pide tu cita <ArrowRight size={18} strokeWidth={2.2} aria-hidden="true" />
                </a>
                <a className="sw-enlace" {...propsEnlace(SITE_ROUTES.quienesSomos)}>
                  Conócenos <ArrowRight size={16} strokeWidth={2.2} aria-hidden="true" />
                </a>
              </div>
              <ul className="sw-senas">
                <li><GraduationCap size={17} strokeWidth={1.8} aria-hidden="true" /> Psicólogos colegiados</li>
                <li><Shield size={17} strokeWidth={1.8} aria-hidden="true" /> Confidencial por secreto profesional</li>
                <li><Clock size={17} strokeWidth={1.8} aria-hidden="true" /> Primera consulta de 30 a 45 min</li>
              </ul>
            </div>
            {mosaico.length >= 6 && (
              <div>
                <ul className="sw-mosaico">
                  {mosaico.map((m) => (
                    <li key={m.id}><img src={m.foto} alt="" loading="lazy" /></li>
                  ))}
                </ul>
                <p className="sw-mosaico-pie">
                  {equipo.length} psicólogos colegiados atendiendo en Lima, Piura y en línea.
                </p>
              </div>
            )}
          </div>
        </div>
      </section>

      <section className="sw-sec sw-blanco">
        <div className="sw-wrap">
          <h2 className="sw-h2">{INICIO.procesoTitulo}</h2>
          <p className="sw-intro">{INICIO.procesoRotulo}</p>
          <img className="sw-foto-ancha" src={`${import.meta.env.BASE_URL}sitio/acompanamiento.jpg`}
            width="1600" height="1066" loading="lazy"
            alt="Psicóloga de Ítaca Conversemos acompañando a una paciente" />
          <ol className="sw-pasos">
            {PASOS.map((p) => (
              <li key={p.t} className="sw-paso">
                <h3>{p.t}</h3>
                <p>{p.d}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="sw-sec sw-celeste">
        <div className="sw-wrap">
          <h2 className="sw-h2">{INICIO.equipoTitulo}</h2>
          <p className="sw-intro">{INICIO.equipoRotulo}</p>
          {conFoto.length > 0 && (
            <ul className="sw-caras">
              {conFoto.slice(0, 10).map((p) => <li key={p.id}><img src={p.foto} alt="" loading="lazy" /></li>)}
            </ul>
          )}
          <div className="sw-acciones" style={{ marginTop: 0 }}>
            <a className="sw-btn sw-btn-linea" {...propsEnlace(SITE_ROUTES.psicologos)}>
              Conócelos aquí <ArrowRight size={16} strokeWidth={2.2} aria-hidden="true" />
            </a>
          </div>
        </div>
      </section>

      <section className="sw-sec">
        <div className="sw-wrap">
          <h2 className="sw-h2">{INICIO.testimoniosTitulo}</h2>
          <p className="sw-intro">{INICIO.testimoniosRotulo}</p>
          <div className="sw-testis">
            {TESTIMONIOS.map((t) => (
              <figure key={t.nombre} className="sw-testi">
                <blockquote><p>{t.texto}</p></blockquote>
                <figcaption>
                  <span className="sw-testi-ini" aria-hidden="true">{iniciales(t.nombre)}</span>
                  <span>
                    <span className="sw-testi-quien">{t.nombre}</span>
                    <span className="sw-testi-rol">Paciente</span>
                  </span>
                </figcaption>
              </figure>
            ))}
          </div>
        </div>
      </section>

      <section className="sw-sec sw-blanco">
        <div className="sw-wrap">
          <h2 className="sw-h2">Antes de decidirte</h2>
          <p className="sw-intro">Las que más nos preguntan.</p>
          <div className="ag-dudas sw-faq">
            {["costo", "online", "confidencial", "elegir"].map((id) => {
              const item = faq.find((f) => f.id === id);
              return item ? <AgendaDuda key={id} item={item} /> : null;
            })}
          </div>
          <p style={{ marginTop: 26 }}>
            <a className="sw-enlace" {...propsEnlace(SITE_ROUTES.preguntas)}>
              Ver todas las preguntas <ArrowRight size={16} strokeWidth={2.2} aria-hidden="true" />
            </a>
          </p>
        </div>
      </section>

      <Cierre titulo={INICIO.procesoFrase} />
    </>
  );
}

// ── Página: quiénes somos (sistema visual nuevo) ──────────────────────────
function PaginaQuienes() {
  const q = QUIENES_SOMOS;
  const hrefCita = hrefReserva();
  return (
    <>
      {/* 1 · Hero humano */}
      <section className="sw-sec sw-hero">
        <div className="sw-wrap">
          <div className="sw-hero-in">
            <div>
              <p className="sw-eyebrow">{q.eyebrow}</p>
              <h1 className="sw-h1">{q.titulo}</h1>
              <div className="sw-lee">{q.entrada.map((p, i) => <p key={i}>{p}</p>)}</div>
              <div className="sw-acciones">
                <a className="sw-btn" href={hrefCita}>
                  Pide tu cita <ArrowRight size={18} strokeWidth={2.2} aria-hidden="true" />
                </a>
                <a className="sw-enlace" {...propsEnlace(SITE_ROUTES.psicologos)}>
                  Conoce a nuestros psicólogos <ArrowRight size={16} strokeWidth={2.2} aria-hidden="true" />
                </a>
              </div>
            </div>
            <div className="sw-foto">
              <img src={`${import.meta.env.BASE_URL}sitio/equipo.jpg`} width="1600" height="1108"
                alt="Psicóloga de Ítaca Conversemos conversando con una paciente en consulta" />
            </div>
          </div>
        </div>
      </section>

      {/* 2 · Qué hacemos */}
      <section className="sw-sec sw-celeste">
        <div className="sw-wrap">
          <h2 className="sw-h2">{q.queHacemosTitulo}</h2>
          <p className="sw-intro">{q.queHacemosEntrada}</p>
          <ul className="sw-serv">
            {q.queHacemos.map((sv) => {
              const Icono = ICONOS_SERVICIO[sv.icono] || Users;
              return (
                <li key={sv.nombre}>
                  <span className="sw-serv-ico"><Icono size={22} strokeWidth={1.6} aria-hidden="true" /></span>
                  <h3>{sv.nombre}</h3>
                  <p>{sv.detalle}</p>
                </li>
              );
            })}
          </ul>
        </div>
      </section>

      {/* 3 · Áreas de trabajo */}
      <section className="sw-sec sw-blanco">
        <div className="sw-wrap">
          <h2 className="sw-h2">{q.areasTitulo}</h2>
          <p className="sw-intro">{q.areasEntrada}</p>
          <ol className="sw-pilares">
            {q.areas.map((a, i) => (
              <li key={a.titulo} className="sw-pilar">
                <span className="sw-pilar-n">{String(i + 1).padStart(2, "0")}</span>
                <h3>{a.titulo}</h3>
                <p>{a.detalle}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* 4 · Modelo integrativo */}
      <section className="sw-sec">
        <div className="sw-wrap">
          <div className="sw-modelo">
            <img src={`${import.meta.env.BASE_URL}sitio/consulta.jpg`} width="1600" height="1066"
              alt="Sesión de terapia en el consultorio de Ítaca Conversemos" loading="lazy" />
            <div>
              <p className="sw-eyebrow">{q.modeloEyebrow}</p>
              <h2 className="sw-h2">{q.modeloTitulo}</h2>
              <p className="sw-cita">{q.modeloCita}</p>
              <div className="sw-lee">{q.modelo.map((p, i) => <p key={i}>{p}</p>)}</div>
              <ul className="sw-dims">{q.dimensiones.map((d) => <li key={d}>{d}</li>)}</ul>
            </div>
          </div>
        </div>
      </section>

      {/* 5 · En lo que creemos */}
      <section className="sw-sec sw-hondo">
        <div className="sw-wrap">
          <p className="sw-eyebrow">{q.creenciasEyebrow}</p>
          <h2 className="sw-h2">{q.creenciasTitulo}</h2>
          <ul className="sw-creencias" style={{ marginTop: 36 }}>
            {q.creencias.map((c) => {
              const Icono = ICONOS_SERVICIO[c.icono] || Heart;
              return (
                <li key={c.texto} className="sw-creencia">
                  <Icono size={26} strokeWidth={1.5} aria-hidden="true" />
                  <p>{c.texto}</p>
                </li>
              );
            })}
          </ul>
        </div>
      </section>

      {/* 6 · Cierre */}
      <section className="sw-sec sw-celeste">
        <div className="sw-wrap sw-cierre">
          <h2 className="sw-h2 sw-h2-c">{q.cierreTitulo}</h2>
          <p className="sw-intro sw-intro-c">{q.cierreTexto}</p>
          <div className="sw-acciones">
            <a className="sw-btn" href={hrefCita}>
              Pide tu cita <ArrowRight size={18} strokeWidth={2.2} aria-hidden="true" />
            </a>
            {Object.keys(AGENDA_SEDES).map((sede) => (
              <a key={sede} className="sw-btn sw-btn-linea" href={agendaWhatsapp(sede)}
                target="_blank" rel="noopener noreferrer">
                WhatsApp {AGENDA_SEDES[sede].label} <MessageCircle size={17} strokeWidth={2} aria-hidden="true" />
              </a>
            ))}
          </div>
          <div className="sw-sedes">
            {Object.entries(AGENDA_SEDES).map(([k, se]) => (
              <div key={k} className="sw-sede">
                <MapPin size={17} strokeWidth={1.9} aria-hidden="true" />
                <div>
                  <strong>{se.label}</strong>
                  <span>{se.direccion}</span>
                  <a href={`tel:${se.telefono.replace(/\s/g, "")}`}>{se.telefono}</a>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}

// ── Página: psicólogos (la lista sale de la base) ─────────────────────────
function TarjetaProfesional({ p }) {
  const hrefCita = hrefReserva();
  const extra = [p.problematicas, p.formacion, p.trayectoria].some(Boolean);
  return (
    <article className="sw-prof">
      <div className="sw-prof-top">
        {p.foto
          ? <img className="sw-prof-foto" src={p.foto} alt="" loading="lazy" />
          : <div className="sw-prof-foto sw-prof-ini" aria-hidden="true">{iniciales(p.nombre)}</div>}
        <div style={{ minWidth: 0 }}>
          <h3 className="sw-prof-nombre">{p.nombre}</h3>
          <p className="sw-prof-meta">
            {p.titulo}
            {p.colegiatura ? <> · <span className="sw-prof-cps">C.Ps.P. N° {p.colegiatura}</span></> : null}
            <br />{[p.sede_label, p.modalidad_label].filter(Boolean).join(" · ")}
          </p>
        </div>
      </div>
      {p.frase ? <p className="sw-prof-frase">{p.frase}</p> : null}
      <div className="sw-prof-campos">
        {p.enfoque ? <p className="sw-campo"><strong>Enfoque</strong><span className="sw-corta">{p.enfoque}</span></p> : null}
        {p.poblaciones ? <p className="sw-campo"><strong>Atiende a</strong><span>{p.poblaciones}</span></p> : null}
      </div>
      {extra && (
        <details className="sw-mas">
          <summary>Ver perfil completo <ChevronDown size={16} strokeWidth={2} aria-hidden="true" /></summary>
          <div className="sw-prof-campos">
            {p.problematicas ? <p className="sw-campo"><strong>Qué trabaja</strong><span>{p.problematicas}</span></p> : null}
            {p.formacion ? <p className="sw-campo"><strong>Formación</strong><span>{p.formacion}</span></p> : null}
            {p.trayectoria ? <p className="sw-campo"><strong>Trayectoria</strong><span>{p.trayectoria}</span></p> : null}
          </div>
        </details>
      )}
      <div className="sw-prof-pie">
        {p.agendable
          ? (
            <a className="sw-btn" href={hrefCita}>
              Ver sus horarios <ArrowRight size={16} strokeWidth={2.2} aria-hidden="true" />
            </a>
          )
          : (
            /* Aquí sí se sabe la sede: la del psicólogo por el que preguntan. */
            <a className="sw-btn sw-btn-linea"
              href={agendaWhatsapp(p.sede || (p.sede_label || "").toLowerCase())}
              target="_blank" rel="noopener noreferrer">
              Consultar por WhatsApp <MessageCircle size={16} strokeWidth={2} aria-hidden="true" />
            </a>
          )}
      </div>
    </article>
  );
}

function PaginaPsicologos({ datos, cargando }) {
  const [sede, setSede] = useState("");
  const equipo = useMemo(() => datos?.equipo || [], [datos]);
  const mostrados = sede ? equipo.filter((p) => p.sede === sede) : equipo;
  const sedes = useMemo(() => [...new Set(equipo.map((p) => p.sede))].filter(Boolean), [equipo]);
  return (
    <>
      <section className="sw-sec sw-hero" style={{ paddingBottom: 0 }}>
        <div className="sw-wrap">
          <div className="sw-hero-in">
            <div>
              <p className="sw-eyebrow">{PSICOLOGOS.rotulo}</p>
              <h1 className="sw-h1" style={{ maxWidth: "18ch" }}>{PSICOLOGOS.titulo}</h1>
              <p className="sw-intro" style={{ marginBottom: 0 }}>{PSICOLOGOS.entrada}</p>
            </div>
            <img className="sw-foto-sec" src={`${import.meta.env.BASE_URL}sitio/sesion.jpg`}
              width="1600" height="1066"
              alt="Psicóloga de Ítaca Conversemos en sesión con un paciente" />
          </div>
        </div>
      </section>

      <section className="sw-sec">
        <div className="sw-wrap">
          {sedes.length > 1 && (
            <div className="sw-filtros" role="group" aria-label="Filtrar por sede">
              <button type="button" className="sw-filtro" aria-pressed={sede === ""} onClick={() => setSede("")}>
                Todos ({equipo.length})
              </button>
              {sedes.map((x) => (
                <button key={x} type="button" className="sw-filtro" aria-pressed={sede === x} onClick={() => setSede(x)}>
                  {AGENDA_SEDES[x]?.label || x} ({equipo.filter((p) => p.sede === x).length})
                </button>
              ))}
            </div>
          )}
          {cargando ? <p className="sw-cargando">Cargando el equipo…</p>
            : mostrados.length === 0 ? (
              <div className="sw-aviso">
                No pudimos cargar el equipo en este momento. Escríbenos por WhatsApp y te contamos quién puede atenderte.
              </div>
            ) : (
              <div className="sw-equipo">
                {mostrados.map((p) => <TarjetaProfesional key={p.id} p={p} />)}
              </div>
            )}
        </div>
      </section>

      <Cierre titulo="¿Ya sabes con quién quieres atenderte?"
        texto="Elige su horario y reserva. Si prefieres que te ayudemos a elegir, cuéntanos qué necesitas y coordinación te acompaña." />
    </>
  );
}

// ── Página: terapias online ───────────────────────────────────────────────
function PaginaTerapias({ datos }) {
  const t = TERAPIAS;
  const servicios = datos?.servicios || [];
  const hrefCita = hrefReserva();
  return (
    <>
      <section className="sw-sec sw-hero">
        <div className="sw-wrap">
          <p className="sw-eyebrow">{t.rotulo}</p>
          <h1 className="sw-h1">{t.titulo}</h1>
          <p className="sw-intro" style={{ marginBottom: 0 }}>{t.entradaRotulo}.</p>
          <div className="sw-acciones">
            <a className="sw-btn" href={hrefCita}>
              Pide tu terapia <ArrowRight size={18} strokeWidth={2.2} aria-hidden="true" />
            </a>
          </div>
        </div>
      </section>

      <section className="sw-sec sw-blanco">
        <div className="sw-wrap">
          <div className="sw-modelo">
            <div>
              <div className="sw-lee">
                <h2 className="sw-h2">{t.entradaTitulo}</h2>
                <p style={{ marginTop: 16 }}>{t.cuerpo}</p>
              </div>
              <h3 className="sw-h3" style={{ margin: "28px 0 14px" }}>{t.paraTitulo}</h3>
              <ul className="sw-chips">{t.para.map((x) => <li key={x}>{x}</li>)}</ul>
            </div>
            <img className="sw-foto-sec" src={`${import.meta.env.BASE_URL}sitio/pareja.jpg`}
              width="1600" height="1066" loading="lazy"
              alt="Sesión de terapia de pareja en Ítaca Conversemos" />
          </div>
        </div>
      </section>

      <section className="sw-sec sw-celeste">
        <div className="sw-wrap">
          <h2 className="sw-h2">{t.temasTitulo}</h2>
          <p className="sw-intro">Nuestro equipo tiene experiencia en una amplia variedad de problemáticas.</p>
          <ul className="sw-chips">{t.temas.map((x) => <li key={x}>{x}</li>)}</ul>
        </div>
      </section>

      {servicios.length > 0 && (
        <section className="sw-sec">
          <div className="sw-wrap">
            <h2 className="sw-h2">Nuestros paquetes</h2>
            <p className="sw-intro">
              Precios vigentes del catálogo de la clínica. La primera consulta sirve para conocer a tu psicólogo y
              definir tu plan; después, tu asesor te ayuda a elegir el paquete y las facilidades de pago.
            </p>
            <div className="sw-precios">
              {servicios.map((sv) => (
                <div key={sv.nombre} className="sw-precio">
                  <h3>{sv.nombre}</h3>
                  <b>S/ {Number(sv.precio).toFixed(0)}</b>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      <section className="sw-sec sw-celeste">
        <div className="sw-wrap">
          <p className="sw-eyebrow">{t.circuloRotulo}</p>
          <h2 className="sw-h2">{t.circuloTitulo}</h2>
          <p className="sw-intro">{t.circuloEntrada}</p>
          <div className="sw-circulos">
            {t.circulos.map((c) => (
              <div key={c.nombre} className="sw-circulo">
                <h3>{c.nombre}</h3>
                <p className="preg">{c.preguntas}</p>
                <p>{c.texto}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="sw-sec sw-hondo">
        <div className="sw-wrap">
          <p className="sw-eyebrow">{t.cierreRotulo}</p>
          <h2 className="sw-h2">{t.cierreTitulo}</h2>
          <div className="sw-lee sw-lee-claro" style={{ marginTop: 18 }}>
            {t.cierre.map((p, i) => <p key={i}>{p}</p>)}
          </div>
        </div>
      </section>

      <Cierre titulo="Estás a solo un paso"
        texto="Empecemos el viaje. Elige sede, psicólogo y horario; nosotros confirmamos contigo antes de tu sesión." />
    </>
  );
}

// ── Página: preguntas frecuentes ──────────────────────────────────────────
function PaginaPreguntas({ faq }) {
  return (
    <>
      <section className="sw-sec sw-hero" style={{ paddingBottom: 0 }}>
        <div className="sw-wrap">
          <p className="sw-eyebrow">{PREGUNTAS.rotulo}</p>
          <h1 className="sw-h1">{PREGUNTAS.titulo}</h1>
          <p className="sw-intro" style={{ marginBottom: 0 }}>{PREGUNTAS.entrada}</p>
        </div>
      </section>

      <section className="sw-sec">
        <div className="sw-wrap">
          <div className="ag-dudas sw-faq">
            {faq.map((item) => <AgendaDuda key={item.id} item={item} />)}
          </div>
        </div>
      </section>

      <Cierre titulo="¿Te quedó alguna duda?"
        texto="Escríbenos por WhatsApp y te respondemos. Si ya lo tienes claro, puedes reservar tu primera consulta ahora." />
    </>
  );
}

// ── Raíz del sitio: ruta, datos y marco ───────────────────────────────────
// El título y la descripción de cada página salen del MISMO archivo que usa el
// servidor para escribirlos en el HTML (`core/seo.py`). Al navegar sin recargar
// no hay ida al servidor, así que hay que actualizarlos aquí —pero leyendo de
// una sola fuente: en dos sitios distintos acabarían diciendo dos cosas.
const PAGINAS = datosDePaginas.paginas;
const PAGINA_POR_DEFECTO = PAGINAS[SITE_ROUTES.inicio] || {
  titulo: "Ítaca Conversemos",
  descripcion: "",
};

export function SitioPublico() {
  const [ruta, setRuta] = useState(() => rutaCanonica(window.location.pathname));
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => alCambiarRuta(() => setRuta(rutaCanonica(window.location.pathname))), []);

  useEffect(() => {
    let vivo = true;
    fetch("/api/sitio/", { headers: { Accept: "application/json" } })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("sin datos"))))
      .then((d) => { if (vivo) setDatos(d); })
      .catch(() => { /* las páginas de texto se ven igual; el CTA cae a WhatsApp */ })
      .finally(() => { if (vivo) setCargando(false); });
    return () => { vivo = false; };
  }, []);

  useEffect(() => {
    const pagina = PAGINAS[ruta] || PAGINA_POR_DEFECTO;
    document.title = pagina.titulo;
    // Al navegar sin recargar, la descripción del HTML sigue siendo la de la
    // página por la que se entró; se actualiza para que no quede descolgada.
    const meta = document.querySelector('meta[name="description"]');
    if (meta && pagina.descripcion) meta.setAttribute("content", pagina.descripcion);
    // Alguien vio esta página. Va en el mismo efecto que el título porque se
    // dispara igual al entrar y al navegar sin recargar.
    registrar(PASOS_EMBUDO.VISITA, ruta);
    document.documentElement.lang = "es";
    // Si se entró por un alias (o con barra final), la barra de direcciones se
    // queda con la forma canónica, sin añadir una entrada al historial.
    if (window.location.pathname !== ruta) {
      window.history.replaceState({}, "", ruta + window.location.search + window.location.hash);
    }
  }, [ruta]);

  // El precio de la primera consulta sale del catálogo real; si no está
  // publicado, el que dice el sitio. Mismo criterio que en el agendamiento.
  const faq = useMemo(() => {
    const s = (datos?.servicios || []).find((x) => /consulta|inicial|primera/i.test(x.nombre) && Number(x.precio) > 0);
    return agendaFaq(s ? `S/ ${Number(s.precio).toFixed(0)}` : "S/ 50");
  }, [datos]);

  const pagina =
    ruta === SITE_ROUTES.quienesSomos ? <PaginaQuienes />
      : ruta === SITE_ROUTES.psicologos ? <PaginaPsicologos datos={datos} cargando={cargando} />
        : ruta === SITE_ROUTES.terapias ? <PaginaTerapias datos={datos} />
          : ruta === SITE_ROUTES.preguntas ? <PaginaPreguntas faq={faq} />
            : <PaginaInicio datos={datos} faq={faq} />;

  return (
    <div className="ag sw-sitio sw-tema">
      <style>{AGENDA_CSS}{SW_CSS}</style>
      <AgendaTop ruta={ruta} />
      <main>{pagina}</main>
      <AgendaPie />
      <AgendaWa />
    </div>
  );
}
