// Páginas públicas del sitio de Ítaca Conversemos: inicio, quiénes somos,
// psicólogos, terapias online y preguntas frecuentes.
//
// Viven dentro de la misma app que el agendamiento y reusan su marco (cabecera,
// pie, WhatsApp) y su sistema visual, para que reservar no sea un salto a otro
// lugar sino el paso siguiente de la misma página.
//
// El equipo y los precios NO están escritos aquí: salen de `GET /api/sitio/`,
// o sea de la base del sistema. Si entra o sale un psicólogo, la web cambia sola.
import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowRight, Check, ChevronDown, Clock, Compass, GraduationCap, Heart, HeartHandshake, MapPin,
  MessageCircle, MessagesSquare, Play, Shield, Sprout, User, Users,
} from "lucide-react";

// Iconos lineales de los servicios y los principios, en un solo lugar para que
// el trazo sea el mismo en toda la página.
const ICONOS_SERVICIO = {
  individual: User, grupal: Users, pareja: HeartHandshake, vocacional: Compass,
  desarrollo: Sprout, talleres: MessagesSquare, objetivo: Check, comunidad: Users, aprendizaje: Heart,
};

import {
  AGENDA_CSS, AGENDA_SEDES, AGENDA_SITIO, AgendaDuda, AgendaPie, AgendaTop, AgendaWa, agendaFaq,
  agendaWhatsapp,
} from "./App.jsx";
import datosDePaginas from "./paginas.json";
import { PASOS as PASOS_EMBUDO, registrar } from "./embudo";
import { SITE_ROUTES, alCambiarRuta, propsEnlace, rutaCanonica } from "./rutas";
import { api } from "./api";
import { FARO, INICIO, PASOS, PREGUNTAS, PSICOLOGOS, QUIENES_SOMOS, TERAPIAS, TESTIMONIOS } from "./sitio-textos";

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
/* Faro. Reutiliza los campos de formulario del agendamiento (AGENDA_CSS ya
   está cargado en esta misma página), así que aquí solo van las piezas que no
   existían: las dos tarjetas de plan y el bloque de lo que el colegio no
   recibe, que tiene que leerse distinto del resto para que nadie lo pase. */
/* ═══ Faro ═══════════════════════════════════════════════════════════════
   Dirección elegida por Mirai: Apple Health · Vercel · Linear. Blanco, vidrio,
   radio 24, sombra suave, mucho aire y jerarquía editorial.

   Dos decisiones técnicas que sostienen eso sin tocar el stack:
   · El vidrio necesita algo detrás que desenfocar. Sobre blanco puro no se ve
     nada, así que la página lleva dos lavados radiales muy tenues del celeste
     de la marca. Un solo tono, no degradado de dos colores.
   · El reveal y los números animados van con IntersectionObserver y CSS. No
     hace falta traer una librería de animación para siete secciones. */
.fa { --v:rgba(255,255,255,.72); --b:rgba(11,22,32,.09); --t:#0B1620; --t2:#55606B;
  --m:#00788C; --m-luz:#00B8D8; --r:24px;
  --s:0 1px 2px rgba(11,22,32,.04), 0 14px 38px -14px rgba(11,22,32,.16);
  --curva:cubic-bezier(.22,1,.36,1);
  position:relative; background:#fff; color:var(--t); isolation:isolate;
}
.fa::before {
  content:""; position:absolute; inset:0; z-index:-1; pointer-events:none;
  background:
    radial-gradient(900px 620px at 78% -8%, rgba(0,184,216,.13), transparent 62%),
    radial-gradient(760px 520px at 8% 34%, rgba(0,120,140,.08), transparent 60%);
}
.fa-wrap { max-width:1080px; margin:0 auto; padding:0 clamp(20px,5vw,40px); }
.fa-sec { padding:clamp(72px,11vw,140px) 0; }

/* Jerarquía editorial: saltos grandes, no seis tamaños pegados. */
.fa-display { font-size:clamp(40px,7.2vw,72px); line-height:1.04; letter-spacing:-0.035em;
  font-weight:600; margin:0; text-wrap:balance; }
.fa-h2 { font-size:clamp(28px,4.2vw,44px); line-height:1.1; letter-spacing:-0.03em;
  font-weight:600; margin:0 0 20px; text-wrap:balance; }
.fa-lead { font-size:clamp(17px,2vw,21px); line-height:1.6; color:var(--t2);
  margin:22px 0 0; max-width:54ch; }
.fa-p { font-size:17px; line-height:1.72; color:var(--t2); margin:0 0 16px; max-width:64ch; }
.fa-kicker { font-size:13px; font-weight:600; letter-spacing:.02em; color:var(--m);
  margin:0 0 18px; }

/* Vidrio */
.fa-card {
  background:var(--v); backdrop-filter:blur(22px) saturate(160%);
  -webkit-backdrop-filter:blur(22px) saturate(160%);
  border:1px solid var(--b); border-radius:var(--r); box-shadow:var(--s);
  padding:clamp(24px,3.4vw,34px);
}

/* Reveal al entrar en pantalla */
.fa-rev { opacity:0; transform:translateY(22px); transition:opacity .7s var(--curva), transform .7s var(--curva); }
.fa-rev.dentro { opacity:1; transform:none; }
.fa-rev[data-r="1"] { transition-delay:.08s } .fa-rev[data-r="2"] { transition-delay:.16s }
.fa-rev[data-r="3"] { transition-delay:.24s } .fa-rev[data-r="4"] { transition-delay:.32s }

/* Hero: el título aparece por líneas */
.fa-hero { padding:clamp(88px,13vw,168px) 0 clamp(56px,8vw,96px); }
.fa-linea { display:block; overflow:hidden; }
.fa-linea > span { display:block; transform:translateY(105%); opacity:0;
  animation:fa-sube .95s var(--curva) forwards; }
.fa-linea:nth-child(2) > span { animation-delay:.1s }
.fa-linea:nth-child(3) > span { animation-delay:.2s }
@keyframes fa-sube { to { transform:none; opacity:1 } }

.fa-cta { display:inline-flex; align-items:center; gap:10px; margin-top:38px;
  padding:16px 30px; border-radius:100px; background:var(--t); color:#fff;
  font-size:16px; font-weight:600; text-decoration:none;
  transition:transform .25s var(--curva), box-shadow .25s var(--curva);
  box-shadow:0 10px 26px -12px rgba(11,22,32,.6); }
.fa-cta:hover { transform:translateY(-2px); box-shadow:0 16px 34px -12px rgba(11,22,32,.55); }

/* Pasos 01–05 */
.fa-pasos { display:grid; gap:14px; margin-top:44px;
  grid-template-columns:repeat(auto-fit,minmax(min(230px,100%),1fr)); }
.fa-paso .n { font-size:13px; font-weight:600; color:var(--m); letter-spacing:.06em;
  font-variant-numeric:tabular-nums; display:block; margin-bottom:14px; }
.fa-paso h3 { font-size:18px; font-weight:600; letter-spacing:-0.02em; margin:0 0 8px; }
.fa-paso p { font-size:15px; line-height:1.6; color:var(--t2); margin:0; }

/* Áreas */
.fa-areas { display:grid; gap:16px; margin-top:44px;
  grid-template-columns:repeat(auto-fit,minmax(min(250px,100%),1fr)); }
.fa-area h3 { font-size:19px; font-weight:600; letter-spacing:-0.02em; margin:0 0 10px; }
.fa-area p { font-size:15px; line-height:1.62; color:var(--t2); margin:0; }
.fa-area .ico { width:42px; height:42px; border-radius:13px; display:flex;
  align-items:center; justify-content:center; background:rgba(0,184,216,.12);
  color:var(--m); margin-bottom:18px; }

/* Cifras */
.fa-cifras { display:grid; gap:16px; margin-top:8px;
  grid-template-columns:repeat(auto-fit,minmax(min(200px,100%),1fr)); }
.fa-cifra .v { font-size:clamp(38px,5.6vw,56px); font-weight:600; letter-spacing:-0.04em;
  line-height:1; font-variant-numeric:tabular-nums; display:block; }
.fa-cifra .r { font-size:14.5px; color:var(--t2); margin:12px 0 0; }

/* Línea de tiempo */
.fa-linea-t { margin-top:44px; display:grid; gap:0; }
.fa-hito { display:grid; grid-template-columns:auto 1fr; gap:22px; }
.fa-hito .eje { display:flex; flex-direction:column; align-items:center; }
.fa-hito .bolita { width:11px; height:11px; border-radius:50%; background:var(--m); margin-top:7px; flex-shrink:0; }
.fa-hito .tallo { width:1px; flex:1; background:var(--b); margin:8px 0 0; }
.fa-hito:last-child .tallo { display:none; }
.fa-hito .cuerpo { padding-bottom:34px; }
.fa-hito h3 { font-size:17.5px; font-weight:600; letter-spacing:-0.02em; margin:0 0 6px; }
.fa-hito p { font-size:15px; line-height:1.6; color:var(--t2); margin:0; }

/* Lo que no hace */
.fa-limites { list-style:none; margin:22px 0 0; padding:0; display:grid; gap:12px; }
.fa-limites li { display:flex; gap:12px; align-items:flex-start; font-size:16px;
  line-height:1.6; color:var(--t2); }
.fa-limites li b { color:var(--t); font-weight:600; }

/* Formulario: editorial, no formulario. Campos sin caja, separados por línea. */
.fa-form { margin-top:8px; display:grid; gap:0; }
.fa-campo { border-bottom:1px solid var(--b); padding:20px 2px 14px; display:grid; gap:7px; }
.fa-campo:first-child { border-top:1px solid var(--b); }
.fa-campo label { font-size:13px; font-weight:600; color:var(--t2); letter-spacing:.01em; }
.fa-campo .opt { font-weight:400; color:#8A939C; }
.fa-campo input, .fa-campo select, .fa-campo textarea {
  border:0; background:none; padding:0; font:inherit; font-size:18px; color:var(--t);
  width:100%; outline:none; letter-spacing:-0.01em;
}
.fa-campo textarea { resize:vertical; min-height:74px; line-height:1.6; }
.fa-campo input::placeholder, .fa-campo textarea::placeholder { color:#9BA4AD; }
.fa-campo:focus-within { border-bottom-color:var(--m); }
.fa-campo:focus-within label { color:var(--m); }
.fa-enviar { margin-top:30px; display:inline-flex; align-items:center; gap:10px;
  padding:17px 34px; border:0; border-radius:100px; background:var(--t); color:#fff;
  font:600 16px inherit; cursor:pointer;
  transition:transform .25s var(--curva), box-shadow .25s var(--curva);
  box-shadow:0 10px 26px -12px rgba(11,22,32,.6); }
.fa-enviar:hover:not(:disabled) { transform:translateY(-2px); }
.fa-enviar:disabled { background:#C3CAD1; cursor:default; box-shadow:none; }
.fa-error { color:#B3261E; font-size:15px; margin:18px 0 0; }

@media (prefers-reduced-motion:reduce) {
  .fa-rev, .fa-linea > span, .fa-cta, .fa-enviar { transition:none; animation:none;
    opacity:1; transform:none; }
}

/* ── Cuestionario del estudiante ──────────────────────────────────────────
   Se responde en un salón, con el tutor caminando entre las filas y un
   compañero al lado, y se pregunta si ha deseado estar muerto. La pantalla
   tiene que ser aburrida a tres metros y clara a treinta centímetros: si desde
   atrás se lee de qué va la pregunta, el chico miente.

   Por eso la barra dice "12 de 38" y NUNCA el nombre de la sección, y por eso
   las cuatro opciones son idénticas entre sí. Pintarlas por gravedad —verde,
   ámbar, rojo— le enseñaría cuál es la respuesta "mala" antes de contestar,
   que es sesgo inducido por la interfaz. */
.fa-q-barra {
  position:sticky; top:0; z-index:5; padding:13px 20px 11px;
  background:rgba(255,255,255,.8); backdrop-filter:blur(18px) saturate(160%);
  -webkit-backdrop-filter:blur(18px) saturate(160%); border-bottom:1px solid var(--b);
}
.fa-q-barra-in { max-width:620px; margin:0 auto; }
.fa-q-fila { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.fa-q-paso { font-size:13px; color:var(--t2); font-variant-numeric:tabular-nums; }
.fa-q-riel { height:3px; background:rgba(11,22,32,.07); border-radius:2px; margin-top:11px; overflow:hidden; }
.fa-q-riel span { display:block; height:100%; background:var(--m); border-radius:2px; transition:width .45s var(--curva); }

.fa-q-wrap { max-width:620px; margin:0 auto; padding:clamp(26px,5vw,48px) 20px 150px; }
.fa-q-marco { font-size:17px; line-height:1.55; color:var(--t2); margin:0 0 14px; }
.fa-q-texto { font-size:clamp(23px,4.6vw,28px); font-weight:600; line-height:1.32;
  letter-spacing:-0.025em; margin:0 0 32px; text-wrap:balance; }

.fa-q-ops { display:grid; gap:10px; }
.fa-q-op {
  display:flex; align-items:center; gap:15px; width:100%; text-align:left;
  background:var(--v); backdrop-filter:blur(20px) saturate(160%);
  -webkit-backdrop-filter:blur(20px) saturate(160%);
  border:1px solid var(--b); border-radius:var(--r); box-shadow:var(--s);
  padding:19px 20px; cursor:pointer; font:inherit; font-size:17px; color:var(--t);
  min-height:66px; transition:border-color .18s var(--curva), transform .18s var(--curva);
}
.fa-q-op:hover { transform:translateY(-1px); }
.fa-q-punto { width:21px; height:21px; border-radius:50%; border:1.5px solid #B4BBC2;
  flex-shrink:0; position:relative; }
.fa-q-op[aria-checked="true"] { border-color:var(--m); }
.fa-q-op[aria-checked="true"] .fa-q-punto { border-color:var(--m); }
.fa-q-op[aria-checked="true"] .fa-q-punto::after {
  content:""; position:absolute; inset:4px; border-radius:50%; background:var(--m); }

.fa-q-pie {
  position:fixed; left:0; right:0; bottom:0; z-index:5;
  background:rgba(255,255,255,.84); backdrop-filter:blur(18px) saturate(160%);
  -webkit-backdrop-filter:blur(18px) saturate(160%); border-top:1px solid var(--b);
  padding:13px 20px calc(13px + env(safe-area-inset-bottom));
}
.fa-q-pie-in { max-width:620px; margin:0 auto; display:grid; gap:10px; }
.fa-q-botones { display:flex; gap:11px; align-items:center; }
.fa-q-atras { padding:15px 22px; border:1px solid var(--b); border-radius:100px;
  background:transparent; color:var(--t2); font:600 17px inherit; cursor:pointer; }
.fa-q-seguir { flex:1; padding:16px; border:0; border-radius:100px; background:var(--t);
  color:#fff; font:600 17px inherit; cursor:pointer;
  box-shadow:0 10px 26px -12px rgba(11,22,32,.6); }
.fa-q-seguir:disabled { background:transparent; border:1px solid var(--b); color:var(--t3);
  cursor:default; box-shadow:none; }
.fa-q-ayuda { font-size:13px; color:var(--t2); text-align:center; margin:0; }

/* ── Panel del colegio ────────────────────────────────────────────────────
   Herramienta de trabajo, no pieza de venta: quien la abre es un director
   entre dos cosas. Lo que busca —en qué va el proceso y cuántos faltan— va
   arriba y grande. Mismo lenguaje visual que la landing para que se sienta de
   una pieza, pero con densidad: aquí el aire generoso estorba. */
.fa-panel-top { padding:clamp(40px,6vw,72px) 0 clamp(24px,3vw,34px); }
.fa-estado {
  display:inline-flex; align-items:center; gap:8px; padding:7px 15px;
  border-radius:100px; background:rgba(0,184,216,.12); color:var(--m);
  font-size:13px; font-weight:600; margin-bottom:20px;
}
.fa-inst { font-size:clamp(28px,4.4vw,44px); font-weight:600; letter-spacing:-0.03em;
  line-height:1.08; margin:0; text-wrap:balance; }
.fa-sede { font-size:16px; color:var(--t2); margin:10px 0 0; }

.fa-metricas { display:grid; gap:14px; margin-top:34px;
  grid-template-columns:repeat(auto-fit,minmax(min(200px,100%),1fr)); }
.fa-metrica .v { font-size:clamp(32px,4.4vw,44px); font-weight:600; letter-spacing:-0.04em;
  line-height:1; font-variant-numeric:tabular-nums; display:block; }
.fa-metrica .r { font-size:14px; color:var(--t2); margin:12px 0 0; }
.fa-metrica .nota { font-size:13px; color:#8A939C; margin:6px 0 0; }

/* El estado vacío enseña: dice qué falta y a quién escribirle, no "sin datos". */
.fa-vacio { margin-top:30px; }
.fa-vacio h2 { font-size:22px; font-weight:600; letter-spacing:-0.02em; margin:0 0 12px; }
.fa-vacio p { font-size:16px; line-height:1.68; color:var(--t2); margin:0 0 14px; max-width:60ch; }
.fa-vacio ol { margin:18px 0 0; padding-left:20px; }
.fa-vacio li { font-size:15.5px; line-height:1.66; color:var(--t2); margin-bottom:9px; }
.fa-vacio li b { color:var(--t); font-weight:600; }

.fa-aviso {
  margin-top:26px; padding:20px 22px; border-radius:16px;
  background:rgba(0,120,140,.06); border:1px solid var(--b);
}
.fa-aviso p { margin:0; font-size:14.5px; line-height:1.65; color:var(--t2); }
.fa-aviso b { color:var(--t); }

.sw-video-btn {
  display:inline-flex; align-items:center; justify-content:center; gap:9px; width:100%;
  margin:18px 0 0; padding:12px 18px; border-radius:12px; cursor:pointer;
  border:1px solid var(--t-suave); background:var(--t-suave); color:var(--txt);
  font-size:14.5px; font-weight:600; font-family:inherit; transition:filter .15s, transform .15s;
}
.sw-video-btn:hover { filter:brightness(.96); transform:translateY(-1px); }
.sw-video-btn svg { color:var(--t-sobre-suave); flex-shrink:0; }
/* El archivo solo se pide cuando le dan play: si no, cada visita a la página
   se traería varios megas por psicólogo sin que nadie los mire. */
/* Sin proporcion fija: los videos del equipo son verticales y forzar 16:9 los
   dejaba diminutos entre franjas negras. */
.sw-video { max-width:300px; margin:18px auto 0; }
.sw-video video {
  display:block; width:100%; height:auto; border:0;
  border-radius:12px; background:#000;
}
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
  const [verVideo, setVerVideo] = useState(false);
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
      {p.video ? (
        verVideo ? (
          <div className="sw-video">
            <video src={p.video} controls autoPlay playsInline
              aria-label={`Presentación de ${p.nombre}`} />
          </div>
        ) : (
          <button type="button" className="sw-video-btn" onClick={() => setVerVideo(true)}>
            <Play size={17} strokeWidth={2} aria-hidden="true" /> Ver su presentación
          </button>
        )
      ) : null}
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


// ── Página: Faro, el tamizaje escolar ────────────────────────────────────────
// Landing B2B. Quien la lee decide por una institución, no por sí mismo: por eso
// no hay ningún botón de reservar, y por eso "lo que Faro no hace" está arriba y
// no escondido al final. Un director que se entera después de que no recibirá
// los nombres de sus estudiantes se siente engañado, y con razón.
//
// Dirección visual: Apple Health · Vercel · Linear. Blanco, vidrio, radio 24,
// jerarquía editorial. El reveal y las cifras van con IntersectionObserver;
// no se trae una librería de animación para siete secciones.
function PaginaFaro() {
  const t = FARO;
  const [f, setF] = useState({
    institucion: "", responsable: "", cargo: "", estudiantes: "", ciudad: "",
    nivel: "secundaria", interes: "tamizaje", whatsapp: "", correo: "", mensaje: "",
  });
  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));
  const [enviando, setEnviando] = useState(false);
  const [err, setErr] = useState("");
  const [hecho, setHecho] = useState(false);

  useEffect(() => {
    const suave = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const obs = new IntersectionObserver((filas) => {
      filas.forEach((fila) => {
        if (!fila.isIntersecting) return;
        const el = fila.target;
        obs.unobserve(el);
        el.classList.add("dentro");
        // Las cifras cuentan hasta su valor real. Son datos del servicio
        // (duración, áreas, preguntas), no métricas de relleno.
        const n = el.querySelector?.("[data-hasta]");
        if (!n) return;
        const hasta = Number(n.dataset.hasta) || 0;
        if (!suave) { n.textContent = hasta + (n.dataset.suf || ""); return; }
        const t0 = performance.now(), dur = 900;
        const paso = (ahora) => {
          const p = Math.min((ahora - t0) / dur, 1);
          const e = 1 - Math.pow(1 - p, 3);
          n.textContent = Math.round(hasta * e) + (n.dataset.suf || "");
          if (p < 1) requestAnimationFrame(paso);
        };
        requestAnimationFrame(paso);
      });
    }, { threshold: 0.2, rootMargin: "0px 0px -8% 0px" });
    document.querySelectorAll(".fa-rev").forEach((el) => obs.observe(el));
    return () => obs.disconnect();
  }, [hecho]);

  async function enviar() {
    if (!f.institucion.trim() || !f.responsable.trim()) {
      setErr("Necesitamos el nombre de la institución y de la persona de contacto."); return;
    }
    if (!f.whatsapp.trim() && !f.correo.trim()) {
      setErr("Déjenos un WhatsApp o un correo para responderle."); return;
    }
    setEnviando(true); setErr("");
    try {
      await api.solicitarFaro(f);
      setHecho(true);
      // No se registra en el embudo: ese mide visitas que terminan en reserva de
      // terapia. Un colegio que pide información no es un paciente.
    } catch (e) {
      setErr(e.message || "No pudimos enviar su solicitud. Intente de nuevo.");
    } finally { setEnviando(false); }
  }

  const campo = (k, etiqueta, extra = {}) => (
    <label className="fa-campo">
      <span>{etiqueta}{extra.opcional ? <span className="opt"> · opcional</span> : null}</span>
      {extra.opciones
        ? <select value={f[k]} onChange={set(k)}>{extra.opciones.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
        : extra.largo
          ? <textarea value={f[k]} onChange={set(k)} placeholder={extra.ph} />
          : <input value={f[k]} onChange={set(k)} placeholder={extra.ph} inputMode={extra.modo} autoComplete={extra.auto} />}
    </label>
  );

  return (
    <div className="fa">
      {/* Hero */}
      <section className="fa-sec fa-hero">
        <div className="fa-wrap">
          <p className="fa-kicker">Para instituciones educativas</p>
          <h1 className="fa-display">
            {t.hero.map((l) => <span className="fa-linea" key={l}><span>{l}</span></span>)}
          </h1>
          <p className="fa-lead">{t.bajada}</p>
          <a className="fa-cta" href="#solicitar">
            {t.cta} <ArrowRight size={17} strokeWidth={2.2} aria-hidden="true" />
          </a>
        </div>
      </section>

      {/* Qué es */}
      <section className="fa-sec">
        <div className="fa-wrap">
          <div className="fa-rev">
            <h2 className="fa-h2">{t.queEsTitulo}</h2>
            {t.queEs.map((p, i) => <p className="fa-p" key={i}>{p}</p>)}
          </div>
          <div className="fa-card fa-rev" data-r="1" style={{ marginTop: 34 }}>
            <p className="fa-kicker" style={{ marginBottom: 4 }}>Lo que Faro no hace</p>
            <ul className="fa-limites">
              {t.noEs.map(([b, d]) => <li key={b}><b>{b}</b> {d}</li>)}
            </ul>
          </div>
        </div>
      </section>

      {/* Cómo funciona */}
      <section className="fa-sec">
        <div className="fa-wrap">
          <h2 className="fa-h2 fa-rev">{t.pasosTitulo}</h2>
          <div className="fa-pasos">
            {t.pasos.map((p, i) => (
              <div className="fa-card fa-paso fa-rev" data-r={String((i % 4) + 1)} key={p.n}>
                <span className="n">{p.n}</span>
                <h3>{p.t}</h3>
                <p>{p.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Áreas */}
      <section className="fa-sec">
        <div className="fa-wrap">
          <h2 className="fa-h2 fa-rev">{t.areasTitulo}</h2>
          <div className="fa-areas">
            {t.areas.map((a, i) => (
              <div className="fa-card fa-area fa-rev" data-r={String((i % 4) + 1)} key={a.t}>
                <span className="ico"><Sprout size={20} strokeWidth={1.8} aria-hidden="true" /></span>
                <h3>{a.t}</h3>
                <p>{a.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Cifras */}
      <section className="fa-sec">
        <div className="fa-wrap">
          <div className="fa-cifras">
            {t.cifras.map((c, i) => (
              <div className="fa-card fa-cifra fa-rev" data-r={String((i % 4) + 1)} key={c.r}>
                <span className="v" data-hasta={c.v} data-suf={c.suf}>0{c.suf}</span>
                <p className="r">{c.r}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Proceso */}
      <section className="fa-sec">
        <div className="fa-wrap">
          <h2 className="fa-h2 fa-rev">{t.procesoTitulo}</h2>
          <div className="fa-linea-t">
            {t.proceso.map((h, i) => (
              <div className="fa-hito fa-rev" data-r={String((i % 4) + 1)} key={h.t}>
                <div className="eje"><span className="bolita" /><span className="tallo" /></div>
                <div className="cuerpo">
                  <h3>{h.t}</h3>
                  <p>{h.d}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Privacidad */}
      <section className="fa-sec">
        <div className="fa-wrap">
          <div className="fa-rev">
            <h2 className="fa-h2">{t.seguridadTitulo}</h2>
            <p className="fa-lead" style={{ marginTop: 0 }}>{t.seguridadLead}</p>
          </div>
          <div className="fa-areas" style={{ marginTop: 38 }}>
            {t.seguridad.map((x, i) => (
              <div className="fa-card fa-area fa-rev" data-r={String((i % 4) + 1)} key={x.t}>
                <span className="ico"><Shield size={20} strokeWidth={1.8} aria-hidden="true" /></span>
                <h3>{x.t}</h3>
                <p>{x.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Solicitud */}
      <section className="fa-sec" id="solicitar">
        <div className="fa-wrap" style={{ maxWidth: 720 }}>
          {hecho ? (
            <div className="fa-card">
              <h2 className="fa-h2" style={{ marginBottom: 14 }}>Recibimos su solicitud</h2>
              <p className="fa-p" style={{ margin: 0 }}>{t.gracias}</p>
            </div>
          ) : (
            <>
              <h2 className="fa-h2 fa-rev">{t.formTitulo}</h2>
              <p className="fa-lead fa-rev" data-r="1" style={{ marginTop: 0, marginBottom: 34 }}>{t.formBajada}</p>
              <div className="fa-form">
                {campo("institucion", "Institución educativa", { auto: "organization" })}
                {campo("responsable", "Persona de contacto", { auto: "name" })}
                {campo("cargo", "Cargo", { opcional: true, ph: "Dirección, psicología, coordinación…" })}
                {campo("ciudad", "Ciudad", { ph: "Lima, Piura…" })}
                {campo("nivel", "Nivel", { opciones: [
                  ["secundaria", "Secundaria"], ["primaria", "Primaria"],
                  ["ambos", "Primaria y secundaria"], ["otro", "Otro"]] })}
                {campo("estudiantes", "Estudiantes aproximados", { opcional: true, modo: "numeric", ph: "No hace falta el número exacto" })}
                {campo("interes", "¿Qué están buscando?", { opciones: [
                  ["tamizaje", "Tamizaje preventivo de estudiantes"],
                  ["evaluacion", "Evaluación de casos puntuales"],
                  ["talleres", "Talleres y capacitación"],
                  ["programa", "Un programa de bienestar escolar"],
                  ["no_sabe", "Aún no lo tenemos claro"]] })}
                {campo("whatsapp", "WhatsApp", { modo: "tel", auto: "tel" })}
                {campo("correo", "Correo", { modo: "email", auto: "email" })}
                {campo("mensaje", "Cuéntenos brevemente", { opcional: true, largo: true, ph: "Qué los trae, qué han observado, en qué plazo lo están pensando…" })}
              </div>
              {err ? <p className="fa-error" role="alert">{err}</p> : null}
              <button className="fa-enviar" onClick={enviar} disabled={enviando}>
                {enviando ? "Enviando…" : "Solicitar propuesta"}
                {enviando ? null : <ArrowRight size={17} strokeWidth={2.2} aria-hidden="true" />}
              </button>
            </>
          )}
        </div>
      </section>
    </div>
  );
}

// ── Cuestionario del estudiante ─────────────────────────────────────────────
// Entra por el enlace del AULA, distinto del de la dirección. Al terminar NO se
// le dice en qué nivel quedó: enterarse por una pantalla de que uno "salió en
// rojo", solo y en un salón, es exactamente lo que el protocolo evita. Eso se
// conversa en persona y el mismo día.
export function TamizajeFaro({ token }) {
  const [info, setInfo] = useState(null);
  const [err, setErr] = useState("");
  const [paso, setPaso] = useState(-3);            // -3..-1 presentación · 0..n-1 ítems · n final
  const [datos, setDatos] = useState({ nombre: "", grado: "", seccion: "" });
  const [resp, setResp] = useState({});
  const [enviando, setEnviando] = useState(false);
  // Avance automático al elegir. Se guarda el temporizador para poder cancelarlo:
  // dos toques seguidos dejarían dos avances encolados y se saltaría una pregunta.
  const avance = useRef(null);
  const cancelarAvance = () => { clearTimeout(avance.current); avance.current = null; };
  useEffect(() => cancelarAvance, []);

  useEffect(() => {
    api.faroCuestionario(token).then(setInfo).catch((e) => setErr(e.message));
    const prev = document.title;
    document.title = "Faro";
    return () => { document.title = prev; };
  }, [token]);
  useEffect(() => { window.scrollTo(0, 0); }, [paso]);

  const marco = (hijos) => (
    <div className="ag sw-sitio sw-tema">
      <style>{AGENDA_CSS}{SW_CSS}</style>
      <div className="fa">{hijos}</div>
    </div>
  );

  if (err) return marco(
    <div className="fa-q-wrap">
      <h1 className="fa-h2">Este enlace no está disponible</h1>
      <p className="fa-p">Avísale a tu tutor para que te pase el correcto.</p>
    </div>
  );
  if (!info) return marco(<div className="fa-q-wrap"><p className="fa-p">Cargando…</p></div>);
  if (!info.abierto) return marco(
    <div className="fa-q-wrap">
      <h1 className="fa-h2">Este tamizaje ya cerró</h1>
      <p className="fa-p">Avísale a tu tutor si necesitabas responderlo.</p>
    </div>
  );

  const items = info.items || [];
  const enItems = paso >= 0 && paso < items.length;
  const it = enItems ? items[paso] : null;

  async function enviar() {
    setEnviando(true); setErr("");
    try {
      await api.faroResponder(token, { ...datos, respuestas: resp });
      setPaso(items.length);
    } catch (e) {
      setErr(e.message || "No pudimos guardar tus respuestas. Avísale a tu tutor.");
    } finally { setEnviando(false); }
  }

  // Elegir una opción pasa sola a la siguiente: son 38 preguntas y obligar a un
  // segundo toque en cada una es medio centenar de toques de más en un celular.
  //
  // Dos excepciones deliberadas:
  //   · La ÚLTIMA no avanza sola, porque avanzar ahí es ENVIAR. Un toque de más
  //     no puede cerrar el cuestionario sin que el estudiante quiera.
  //   · Hay una pausa corta antes de pasar. Sin ella la pantalla cambia antes de
  //     que se vea la opción marcada y parece que el toque no se registró.
  function elegir(k) {
    cancelarAvance();
    setResp((p) => ({ ...p, [it.id]: k }));
    if (paso < items.length - 1) {
      avance.current = setTimeout(() => setPaso((p) => p + 1), 260);
    }
  }

  // ── Presentación y datos ──
  // El texto es el que aprobó el equipo, palabra por palabra. Acá está solo
  // maquetado: partido en tres pantallas por donde el propio texto se corta, y
  // con los títulos que ya venían marcados como tales. Es texto de
  // consentimiento —es lo que se le promete al estudiante—, así que no se
  // cambia una palabra sin que lo revise el equipo de psicólogos.

  if (paso === -3) return marco(
    <div className="fa-q-wrap">
      <h1 className="fa-h2" style={{ marginBottom: 10 }}>Queremos Escucharte</h1>
      <p className="fa-lead" style={{ marginTop: 0, marginBottom: 34 }}>
        Un espacio para conocer cómo estás.
      </p>

      <p className="fa-p">Hola.</p>
      <p className="fa-p">En el colegio vivimos distintas experiencias.</p>
      <p className="fa-p">
        Hay cosas que son fáciles de contar y otras que pueden ser difíciles de
        expresar. A veces necesitamos ayuda y no sabemos cómo pedirla. Otras veces
        vemos que alguien está pasando por una situación difícil y no sabemos qué
        hacer.
      </p>
      <p className="fa-p">
        En Ítaca Conversemos, junto con tu colegio, queremos conocer cómo estás,
        cómo te sientes en tu entorno y qué podemos hacer para que los estudiantes
        se sientan más seguros y acompañados.
      </p>
      <p className="fa-p">
        Te haremos algunas preguntas. No hay respuestas correctas o incorrectas, y
        no tienes que responder lo que crees que los demás esperan de ti. Queremos
        conocer tu experiencia.
      </p>

      <p className="fa-p" style={{ color: "var(--t)", fontWeight: 600, margin: "26px 0" }}>
        Tu bienestar importa. Tu voz también.
      </p>

      <p className="fa-p">
        Antes de comenzar, te explicaremos cómo se utilizará la información y qué
        sucederá si identificamos que tú o alguien más necesita ayuda.
      </p>

      <button className="fa-enviar" onClick={() => setPaso(-2)}>
        Continuar <ArrowRight size={17} strokeWidth={2.2} aria-hidden="true" />
      </button>
    </div>
  );

  if (paso === -2) return marco(
    <div className="fa-q-wrap">
      <h1 className="fa-h2" style={{ marginBottom: 10 }}>Lo que necesitas saber:</h1>
      <p className="fa-lead" style={{ marginTop: 0 }}>
        Queremos que respondas con confianza
      </p>

      <ul className="fa-limites" style={{ marginTop: 34 }}>
        <li>
          <span>
            <b>No hay respuestas correctas o incorrectas.</b><br />
            Queremos conocer tu experiencia, no evaluarte ni calificarte.
          </span>
        </li>
        <li>
          <span>
            <b>Esto no es un examen.</b><br />
            Tu participación no tiene nota y no afecta tus calificaciones.
          </span>
        </li>
        <li>
          <span>
            <b>Tómate tu tiempo.</b><br />
            Puedes detenerte si necesitas una pausa, de acuerdo con las condiciones
            de participación.
          </span>
        </li>
        <li>
          <span>
            <b>Tu información será tratada con cuidado.</b><br />
            Te explicaremos quién puede acceder a tus respuestas y cómo se utilizarán.
          </span>
        </li>
      </ul>

      <div className="fa-q-botones" style={{ marginTop: 34 }}>
        <button className="fa-q-atras" onClick={() => setPaso(-3)}>Atrás</button>
        <button className="fa-enviar" style={{ marginTop: 0 }} onClick={() => setPaso(-1)}>
          Continuar <ArrowRight size={17} strokeWidth={2.2} aria-hidden="true" />
        </button>
      </div>
    </div>
  );

  if (paso === -1) return marco(
    <div className="fa-q-wrap">
      <h1 className="fa-h2">Si algo te está haciendo daño, queremos ayudarte:</h1>

      <div className="fa-card">
        <p className="fa-p" style={{ margin: 0 }}>
          Queremos ser honestos contigo: la información que compartas será tratada
          con cuidado, pero si identificamos una situación que requiere ayuda o
          protección, un psicólogo conversará contigo en privado para comprender
          mejor lo que sucede y ayudarte.
        </p>
      </div>

      <p className="fa-p" style={{ marginTop: 26 }}>
        No tendrás que afrontar una situación difícil sin apoyo. Estamos aquí para
        ti, eres importante. Queremos escucharte.
      </p>

      <div className="fa-form" style={{ marginTop: 34 }}>
        <label className="fa-campo">
          <span>Tu nombre completo</span>
          <input value={datos.nombre} onChange={(e) => setDatos((p) => ({ ...p, nombre: e.target.value }))}
            autoComplete="name" />
        </label>
        <label className="fa-campo">
          <span>Grado</span>
          <input value={datos.grado} onChange={(e) => setDatos((p) => ({ ...p, grado: e.target.value }))}
            placeholder="3.° secundaria" />
        </label>
        <label className="fa-campo">
          <span>Sección</span>
          <input value={datos.seccion} onChange={(e) => setDatos((p) => ({ ...p, seccion: e.target.value }))}
            placeholder="B" />
        </label>
      </div>

      <div className="fa-q-botones" style={{ marginTop: 30 }}>
        <button className="fa-q-atras" onClick={() => setPaso(-2)}>Atrás</button>
        <button className="fa-enviar" style={{ marginTop: 0 }} onClick={() => setPaso(0)}
          disabled={datos.nombre.trim().length < 3}>
          Empezar <ArrowRight size={17} strokeWidth={2.2} aria-hidden="true" />
        </button>
      </div>
    </div>
  );

  // ── Cierre ──
  if (paso >= items.length) return marco(
    <div className="fa-q-wrap">
      <h1 className="fa-h2">Listo, gracias por contestar</h1>
      <p className="fa-p">
        Tus respuestas las va a revisar un psicólogo del equipo. Si algo de lo que
        contestaste hace falta conversarlo, te vamos a buscar.
      </p>
      <p className="fa-p">
        Si en algún momento quieres hablar con alguien y no sabes con quién, puedes llamar
        gratis a la <b>Línea 113, opción 5</b>, de salud mental del Ministerio de Salud.
        Atienden todos los días.
      </p>
    </div>
  );

  // ── Una pregunta ──
  const elegido = resp[it.id];
  return marco(
    <>
      <div className="fa-q-barra">
        <div className="fa-q-barra-in">
          <div className="fa-q-fila">
            {/* Nunca el nombre de la sección: eso le cuenta al de al lado de qué
                va la pregunta. */}
            <span className="fa-q-paso">Pregunta {paso + 1} de {items.length}</span>
          </div>
          <div className="fa-q-riel">
            <span style={{ width: `${((paso + 1) / items.length) * 100}%` }} />
          </div>
        </div>
      </div>

      <div className="fa-q-wrap">
        <p className="fa-q-marco">{it.marco}</p>
        <h1 className="fa-q-texto">{it.texto}</h1>
        <div className="fa-q-ops" role="radiogroup" aria-label="Respuesta">
          {it.escala.map((etiqueta, k) => (
            <button key={etiqueta} className="fa-q-op" role="radio"
              aria-checked={elegido === k}
              onClick={() => elegir(k)}>
              <span className="fa-q-punto" />{etiqueta}
            </button>
          ))}
        </div>
        {err ? <p className="fa-error" role="alert">{err}</p> : null}
      </div>

      <div className="fa-q-pie">
        <div className="fa-q-pie-in">
          <div className="fa-q-botones">
            <button className="fa-q-atras"
              onClick={() => { cancelarAvance(); setPaso((p) => p - 1); }}>Atrás</button>
            <button className="fa-q-seguir" disabled={elegido === undefined || enviando}
              onClick={() => {
                cancelarAvance();
                if (paso === items.length - 1) enviar(); else setPaso((p) => p + 1);
              }}>
              {enviando ? "Guardando…" : paso === items.length - 1 ? "Terminar" : "Siguiente"}
            </button>
          </div>
          <p className="fa-q-ayuda">Si necesitas hablar con alguien, avísale al psicólogo que está en tu salón.</p>
        </div>
      </div>
    </>
  );
}

// ── Panel del colegio ────────────────────────────────────────────────────────
// Entra por enlace permanente con token, sin cuenta. Lo que se muestra es
// SIEMPRE agregado: ni un estudiante identificado, ni un dato que permita
// deducir quién es quién. Esa regla está firmada en el consentimiento de los
// apoderados y en el convenio de la institución.
export function PanelFaro({ token }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.faroPanel(token).then(setD).catch((e) => setErr(e.message));
    const prev = document.title;
    document.title = "Faro · Panel de la institución";
    return () => { document.title = prev; };
  }, [token]);

  const marco = (hijos) => (
    <div className="ag sw-sitio sw-tema">
      <style>{AGENDA_CSS}{SW_CSS}</style>
      <AgendaTop />
      <main><div className="fa">{hijos}</div></main>
      <AgendaPie />
    </div>
  );

  if (err) return marco(
    <section className="fa-sec fa-panel-top"><div className="fa-wrap">
      <h1 className="fa-inst">Este enlace no está disponible</h1>
      <p className="fa-sede">{err}</p>
      <p className="fa-sede">Escríbanos a {AGENDA_SITIO.correo} y le enviamos uno nuevo.</p>
    </div></section>
  );
  if (!d) return marco(
    <section className="fa-sec fa-panel-top"><div className="fa-wrap">
      <p className="fa-sede">Cargando…</p>
    </div></section>
  );

  return marco(
    <>
      <section className="fa-panel-top">
        <div className="fa-wrap">
          <span className="fa-estado"><Shield size={15} strokeWidth={2} aria-hidden="true" /> {d.estado_label}</span>
          <h1 className="fa-inst">{d.institucion}</h1>
          <p className="fa-sede">
            {[d.ciudad, d.contacto].filter(Boolean).join(" · ") || "Programa Faro · Ítaca Conversemos"}
          </p>

          {d.hay_datos ? (
            <div className="fa-metricas">
              <div className="fa-card fa-metrica">
                <span className="v">{d.evaluados}</span>
                <p className="r">Estudiantes evaluados</p>
              </div>
              <div className="fa-card fa-metrica">
                <span className="v">{d.autorizados}</span>
                <p className="r">Con autorización firmada</p>
                {d.matriculados ? <p className="nota">de {d.matriculados} matriculados en secundaria</p> : null}
              </div>
              <div className="fa-card fa-metrica">
                <span className="v">{d.participacion === null ? "—" : `${d.participacion}%`}</span>
                <p className="r">Participación</p>
                <p className="nota">Sobre los autorizados, no sobre el total</p>
              </div>
            </div>
          ) : null}
        </div>
      </section>

      <section className="fa-sec" style={{ paddingTop: 0 }}>
        <div className="fa-wrap">
          {d.hay_datos ? (
            <div className="fa-card fa-vacio">
              <h2>Panorama por grado</h2>
              <p>
                El detalle por grado y sección se publica aquí junto con el informe institucional.
                {d.fecha_informe ? ` Entregado el ${d.fecha_informe}.` : " Está en preparación."}
              </p>
              <div className="fa-aviso">
                <p>
                  <b>Este panel no muestra estudiantes.</b> Los casos que requieren atención se
                  comunican con la familia y con el psicólogo del colegio, según el protocolo
                  firmado. La institución recibe el panorama, nunca nombres junto a resultados.
                </p>
              </div>
            </div>
          ) : (
            <div className="fa-card fa-vacio">
              <h2>Todavía no hay resultados</h2>
              <p>
                El tamizaje aún no se ha aplicado en su institución. Cuando se aplique, este panel
                mostrará el panorama por grado y sección.
              </p>
              <ol>
                <li><b>Convenio y protocolo firmados.</b> El protocolo define quién responde ante una alerta y en cuánto tiempo. Sin él no se aplica nada.</li>
                <li><b>Autorizaciones recogidas.</b> Le entregamos los formatos de consentimiento y asentimiento listos para repartir.</li>
                <li><b>Aplicación por aulas</b>, en horario de tutoría, con el tutor presente.</li>
                <li><b>Informe y reunión de devolución</b> dentro de los quince días hábiles.</li>
              </ol>
              <div className="fa-aviso">
                <p>
                  ¿Dudas o quiere mover una fecha? Escríbanos a <b>{AGENDA_SITIO.correo}</b> y
                  coordinamos.
                </p>
              </div>
            </div>
          )}
        </div>
      </section>
    </>
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

      {/* La Brújula va antes del Círculo de Aliados porque es una puerta de
          entrada, no un servicio más del catálogo. La duda que más le llega al
          equipo por WhatsApp es en qué se diferencia de la primera consulta, así
          que se responde aquí mismo y no en una pregunta frecuente. */}
      <section className="sw-sec">
        <div className="sw-wrap">
          <p className="sw-eyebrow">{t.brujulaRotulo}</p>
          <h2 className="sw-h2">{t.brujulaTitulo}</h2>
          <p className="sw-intro">{t.brujulaEntrada}</p>
          <ol className="sw-pasos" style={{ marginTop: 30 }}>
            {t.brujulaIncluye.map((p) => (
              <li key={p.t} className="sw-paso">
                <h3>{p.t}</h3>
                <p>{p.d}</p>
              </li>
            ))}
          </ol>
          <p className="sw-intro" style={{ marginTop: 30 }}>{t.brujulaPara}</p>
          <p className="sw-cita">{t.brujulaDiferencia}</p>
        </div>
      </section>

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
            : ruta === SITE_ROUTES.faro ? <PaginaFaro />
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
