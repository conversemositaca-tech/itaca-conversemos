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
import { ArrowRight, Check, ChevronDown, Clock, GraduationCap, MapPin, MessageCircle, Shield, Users } from "lucide-react";

import {
  AGENDA_CSS, AGENDA_SEDES, AGENDA_SITIO, AgendaDuda, AgendaPie, AgendaTop, AgendaWa, agendaFaq,
} from "./App.jsx";
import { alCambiarRuta, normalizarRuta, propsEnlace, rutaAgendar } from "./rutas";
import { INICIO, PASOS, PREGUNTAS, PSICOLOGOS, QUIENES_SOMOS, TERAPIAS, TESTIMONIOS } from "./sitio-textos";

// Estilos propios de las páginas de contenido. Se apoyan en los tokens del
// agendamiento (papel crema, tinta cálida, acento turquesa legible): aquí solo
// va lo que el formulario no necesitaba —rejillas, secciones anchas, citas—.
const SITIO_CSS = `
/* El contenedor .ag es flex en fila (lo hereda del panel): en el agendamiento da
   igual porque su columna es fija, pero aquí dejaba el <main> al ancho de su
   contenido —la página de preguntas salía angosta y descentrada respecto al pie—.
   Apilamos en columna, sin tocar .ag para no alterar el agendamiento ya en vivo. */
.st-sitio { display:flex; flex-direction:column; align-items:stretch; }
/* width:100% es imprescindible: dentro de un flex, un elemento con margin auto
   y sin ancho definido se encoge a su contenido en vez de ocupar la página. */
.st-wrap { width:100%; max-width:1080px; margin:0 auto; padding-left:clamp(18px,4vw,36px); padding-right:clamp(18px,4vw,36px); overflow-x:clip; }
.st-wrap * { min-width:0; }
.st-sec { padding-block:clamp(40px,6.5vw,72px); }
.st-sec + .st-sec { border-top:1px solid var(--linea); }
.st-sec-clara { background:var(--superficie); }
.st-lee { max-width:68ch; }
.st-lee p { font-size:16px; line-height:1.72; color:var(--tinta-2); margin:0 0 16px; }
.st-lee p:last-child { margin-bottom:0; }
.st-rotulo { font-size:11.5px; font-weight:600; letter-spacing:.16em; text-transform:uppercase; color:var(--acento); margin:0 0 10px; }
.st-h1 { font-size:clamp(32px,6.4vw,52px); line-height:1.05; font-weight:600; letter-spacing:-0.035em; margin:0 0 18px; text-wrap:balance; }
.st-h2 { font-size:clamp(22px,3.6vw,30px); line-height:1.2; font-weight:600; letter-spacing:-0.028em; margin:0 0 8px; text-wrap:balance; }
.st-h3 { font-size:17.5px; font-weight:600; letter-spacing:-0.02em; margin:0 0 6px; }
.st-sub { font-size:16px; line-height:1.6; color:var(--tinta-2); margin:0 0 26px; max-width:60ch; }

/* Portada: el texto manda; las únicas caras del sitio son las del equipo real. */
.st-hero { padding-block:clamp(44px,8vw,92px) clamp(36px,5vw,60px); }
.st-hero-in { display:grid; gap:clamp(30px,5vw,56px); align-items:center; grid-template-columns:minmax(0,1fr); }
.st-hero-in > * { min-width:0; }
@media (min-width:940px) { .st-hero-in { grid-template-columns:minmax(0,1fr) 340px; } }
.st-mosaico { display:grid; grid-template-columns:repeat(3,1fr); gap:9px; margin:0; padding:0; list-style:none; }
.st-mosaico img, .st-mosaico .st-foto-ini {
  width:100%; height:auto; aspect-ratio:1; border-radius:14px; object-fit:cover; font-size:24px;
}
.st-mosaico-pie { font-size:13px; line-height:1.5; color:var(--tinta-3); margin:12px 0 0; }
.st-hero .st-h1 em { font-style:normal; color:var(--acento); }
.st-hero-lead { font-size:clamp(16.5px,2vw,18.5px); line-height:1.6; color:var(--tinta-2); margin:0 0 28px; max-width:52ch; }
.st-acciones { display:flex; flex-wrap:wrap; align-items:center; gap:12px 16px; }
.st-btn {
  display:inline-flex; align-items:center; gap:7px; text-decoration:none; cursor:pointer;
  font-family:inherit; font-size:15.5px; font-weight:600; border:none;
  padding:14px 24px; border-radius:12px; background:var(--acento); color:#fff;
  box-shadow:0 1px 2px rgba(0,120,140,.2); transition:background .15s, transform .15s var(--curva), box-shadow .15s var(--curva);
}
.st-btn:hover { background:#00647A; transform:translateY(-1px); box-shadow:0 6px 18px rgba(0,120,140,.26); }
.st-btn svg { transition:transform .16s var(--curva); }
.st-btn:hover svg { transform:translateX(3px); }
.st-btn-2 {
  background:var(--superficie); color:var(--acento); box-shadow:var(--sombra);
  border:1px solid var(--linea);
}
.st-btn-2:hover { background:var(--arena); color:var(--acento); }

/* Rejillas */
.st-rej { display:grid; gap:16px; grid-template-columns:repeat(auto-fit,minmax(min(248px,100%),1fr)); }
.st-rej-2 { display:grid; gap:clamp(22px,4vw,48px); grid-template-columns:repeat(auto-fit,minmax(min(300px,100%),1fr)); align-items:start; }
.st-card { background:var(--superficie); border-radius:16px; padding:22px; box-shadow:var(--sombra); }
.st-card p { font-size:14.5px; line-height:1.62; color:var(--tinta-2); margin:0; }

/* Pasos del proceso: numerados, sin iconos de adorno. */
.st-pasos { list-style:none; counter-reset:paso; margin:0; padding:0; display:grid; gap:14px; grid-template-columns:repeat(auto-fit,minmax(min(230px,100%),1fr)); }
.st-pasos li { counter-increment:paso; background:var(--superficie); border-radius:16px; padding:20px; box-shadow:var(--sombra); }
.st-pasos li::before {
  content:counter(paso); display:flex; align-items:center; justify-content:center;
  width:27px; height:27px; margin-bottom:12px; border-radius:50%;
  background:var(--acento-suave); color:var(--acento); font-size:13.5px; font-weight:700;
}

/* Listas de temas y servicios: pastillas, no viñetas. */
.st-chips { display:flex; flex-wrap:wrap; gap:9px; margin:0; padding:0; list-style:none; }
.st-chips li {
  font-size:14px; font-weight:500; color:var(--tinta-2); background:var(--superficie);
  border:1px solid var(--linea); border-radius:999px; padding:8px 15px;
}
.st-lista { margin:0; padding:0; list-style:none; display:grid; gap:11px; }
.st-lista li { display:flex; gap:10px; align-items:flex-start; font-size:15.5px; line-height:1.55; color:var(--tinta-2); }
.st-lista svg { color:var(--acento); flex-shrink:0; margin-top:3px; }

/* Equipo */
.st-equipo { display:grid; gap:16px; grid-template-columns:repeat(auto-fill,minmax(min(272px,100%),1fr)); }
.st-prof { background:var(--superficie); border-radius:18px; padding:22px; box-shadow:var(--sombra); display:flex; flex-direction:column; }
.st-prof-top { display:flex; align-items:center; gap:14px; }
.st-prof-nombre { font-size:16.5px; font-weight:600; letter-spacing:-0.02em; margin:0; }
.st-prof-meta { font-size:12.5px; color:var(--tinta-3); margin:3px 0 0; line-height:1.45; }
.st-prof-frase {
  margin:16px 0 0; padding-left:13px; border-left:2px solid var(--acento-suave);
  font-size:14px; line-height:1.55; color:var(--tinta-2); font-style:italic;
}
.st-prof-datos { margin:16px 0 0; display:grid; gap:9px; }
.st-dato { font-size:13.5px; line-height:1.5; color:var(--tinta-2); }
.st-dato strong { display:block; font-size:10.5px; font-weight:600; letter-spacing:.09em; text-transform:uppercase; color:var(--tinta-3); margin-bottom:2px; }
.st-corta { display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; }
.st-perfil { margin-top:14px; border-top:1px solid var(--linea); padding-top:12px; }
.st-perfil summary {
  display:flex; align-items:center; justify-content:space-between; gap:8px; cursor:pointer;
  list-style:none; font-size:13.5px; font-weight:600; color:var(--acento); padding:2px 0;
}
.st-perfil summary::-webkit-details-marker { display:none; }
.st-perfil summary svg { transition:transform .18s var(--curva); flex-shrink:0; }
.st-perfil[open] summary svg { transform:rotate(180deg); }
.st-perfil .st-prof-datos { margin-top:12px; }
.st-prof-pie { margin-top:auto; padding-top:18px; display:flex; align-items:center; gap:12px; }
.st-prof-pie .st-btn { padding:10px 17px; font-size:14px; }
.st-foto { border-radius:50%; object-fit:cover; flex-shrink:0; width:60px; height:60px; }
.st-foto-ini { display:flex; align-items:center; justify-content:center; font-weight:600; font-size:22px; background:var(--acento-vivo); color:var(--tinta); }
.st-tira { display:flex; flex-wrap:wrap; gap:10px; margin:0 0 22px; padding:0; list-style:none; }
.st-tira img, .st-tira .st-foto-ini { width:54px; height:54px; font-size:19px; }

/* Filtro por sede: pestañas de verdad, no un select escondido. */
.st-filtros { display:flex; flex-wrap:wrap; gap:9px; margin:0 0 24px; }
.st-filtro {
  font-family:inherit; font-size:14.5px; font-weight:500; cursor:pointer; color:var(--tinta-2);
  background:var(--superficie); border:1px solid var(--linea); border-radius:999px; padding:9px 18px;
  transition:border-color .15s, color .15s, background .15s;
}
.st-filtro:hover { border-color:var(--acento); color:var(--acento); }
.st-filtro[aria-pressed="true"] { background:var(--acento); border-color:var(--acento); color:#fff; }

/* Testimonios: palabras de pacientes, con su nombre. Sin estrellas ni adornos. */
.st-testis { display:grid; gap:16px; grid-template-columns:repeat(auto-fit,minmax(min(420px,100%),1fr)); }
.st-testi { background:var(--superficie); border-radius:18px; padding:24px; box-shadow:var(--sombra); display:flex; flex-direction:column; }
.st-testi { margin:0; }
.st-testi blockquote { margin:0; }
.st-testi p { font-size:14.5px; line-height:1.68; color:var(--tinta-2); margin:0 0 16px; }
.st-testi figcaption { margin-top:auto; display:flex; align-items:center; gap:11px; }
.st-testi-ini {
  width:38px; height:38px; border-radius:50%; display:flex; align-items:center; justify-content:center;
  background:var(--arena); color:var(--acento); font-weight:600; font-size:14px; flex-shrink:0;
}
.st-testi-quien { display:block; font-size:14.5px; font-weight:600; letter-spacing:-0.01em; }
.st-testi-rol { display:block; font-size:12.5px; color:var(--tinta-3); margin-top:1px; }

/* Cierre: la invitación a reservar, siempre igual en todas las páginas. */
.st-cierre { background:var(--arena); border-radius:20px; padding:clamp(26px,4vw,40px); text-align:center; }
.st-cierre .st-h2 { margin-bottom:10px; }
.st-cierre p { font-size:15.5px; line-height:1.6; color:var(--tinta-2); margin:0 auto 22px; max-width:48ch; }
.st-cierre .st-acciones { justify-content:center; }

/* Sedes en el cierre y en contacto */
.st-sedes { display:grid; gap:14px; grid-template-columns:repeat(auto-fit,minmax(min(250px,100%),1fr)); margin-top:22px; }
.st-sede { display:flex; gap:11px; text-align:left; }
.st-sede svg { color:var(--acento); flex-shrink:0; margin-top:2px; }
.st-sede strong { display:block; font-size:15px; letter-spacing:-0.01em; }
.st-sede span { display:block; font-size:13.5px; color:var(--tinta-2); line-height:1.45; }
.st-sede a { display:inline-block; margin-top:3px; font-size:13.5px; font-weight:600; color:var(--acento); text-decoration:none; }
.st-sede a:hover { text-decoration:underline; }

.st-nota { font-size:13.5px; line-height:1.6; color:var(--tinta-3); margin:18px 0 0; }
.st-cargando { color:var(--tinta-3); font-size:15px; padding:10px 0; }
.st-aviso { background:var(--acento-suave); border-radius:14px; padding:16px 18px; font-size:14.5px; line-height:1.55; color:var(--tinta); }

@media (max-width:560px) {
  .st-card, .st-prof, .st-testi { padding:18px; }
  .st-prof-pie { flex-direction:column; align-items:stretch; gap:9px; }
  .st-prof-pie .st-btn { justify-content:center; }
}
`;

const iniciales = (n) => (n || "?").replace(/^lic\.?\s*/i, "").trim().charAt(0).toUpperCase();

/** Enlace de reserva. Sin token todavía (o si la API falló), ofrece WhatsApp:
 *  una salida que sí funciona, en vez de un botón muerto. */
function hrefReserva(token) {
  return rutaAgendar(token) || AGENDA_SITIO.whatsapp;
}

function BotonReservar({ token, children = "Pide tu cita", clase = "st-btn" }) {
  const href = hrefReserva(token);
  const externo = !href.startsWith("/");
  return (
    <a className={clase} href={href} {...(externo ? { target: "_blank", rel: "noopener" } : {})}>
      {children} <ArrowRight size={17} strokeWidth={2.2} aria-hidden="true" />
    </a>
  );
}

/** Cierre común: la misma invitación al final de cada página. */
function Cierre({ token, titulo = "¿Damos el primer paso?", texto }) {
  return (
    <section className="st-sec">
      <div className="st-cierre">
        <h2 className="st-h2">{titulo}</h2>
        <p>{texto || "Elige sede, psicólogo y horario. Coordinación confirma contigo antes de la sesión y no pagas nada al reservar."}</p>
        <div className="st-acciones">
          <BotonReservar token={token} />
          <a className="st-btn st-btn-2" href={AGENDA_SITIO.whatsapp} target="_blank" rel="noopener">
            Escríbenos por WhatsApp <MessageCircle size={16} strokeWidth={2} aria-hidden="true" />
          </a>
        </div>
        <div className="st-sedes">
          {Object.entries(AGENDA_SEDES).map(([k, se]) => (
            <div key={k} className="st-sede">
              <MapPin size={16} strokeWidth={1.9} aria-hidden="true" />
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

function Foto({ p, size = 60 }) {
  return p.foto
    ? <img className="st-foto" src={p.foto} alt="" style={{ width: size, height: size }} loading="lazy" />
    : <div className="st-foto st-foto-ini" style={{ width: size, height: size, fontSize: size * 0.36 }} aria-hidden="true">{iniciales(p.nombre)}</div>;
}

// ── Página: inicio ────────────────────────────────────────────────────────
function PaginaInicio({ datos, token, faq }) {
  const equipo = (datos?.equipo || []).slice(0, 8);
  // Mosaico de la portada: solo caras reales, y en múltiplos de tres para que
  // la rejilla no quede coja.
  const conFoto = (datos?.equipo || []).filter((x) => x.foto);
  const mosaico = conFoto.slice(0, Math.min(9, Math.floor(conFoto.length / 3) * 3));
  const totalEquipo = (datos?.equipo || []).length;
  return (
    <>
      <section className="st-hero">
        <div className="st-hero-in">
          <div>
            <p className="st-rotulo">{INICIO.rotulo}</p>
            <h1 className="st-h1">Este espacio <em>es para ti</em>.</h1>
            <p className="st-hero-lead">{INICIO.entrada}</p>
            <div className="st-acciones">
              <BotonReservar token={token} />
              <a className="st-btn st-btn-2" {...propsEnlace("/quienes-somos")}>Conócenos</a>
            </div>
            <ul className="ag-senas">
              <li><GraduationCap size={16} strokeWidth={1.9} aria-hidden="true" /> Psicólogos colegiados</li>
              <li><Shield size={16} strokeWidth={1.9} aria-hidden="true" /> Confidencial por secreto profesional</li>
              <li><Clock size={16} strokeWidth={1.9} aria-hidden="true" /> Primera consulta de 30 a 45 min</li>
              <li><Users size={16} strokeWidth={1.9} aria-hidden="true" /> Presencial en Lima y Piura, u online</li>
            </ul>
          </div>
          {mosaico.length >= 6 && (
            <div>
              <ul className="st-mosaico">
                {mosaico.map((m) => <li key={m.id}><Foto p={m} size={104} /></li>)}
              </ul>
              <p className="st-mosaico-pie">
                {totalEquipo} psicólogos colegiados atendiendo en Lima, Piura y en línea.
              </p>
            </div>
          )}
        </div>
      </section>

      <section className="st-sec st-sec-clara">
        <h2 className="st-h2">{INICIO.procesoTitulo}</h2>
        <p className="st-sub">{INICIO.procesoRotulo}</p>
        <ol className="st-pasos">
          {PASOS.map((p) => (
            <li key={p.t}>
              <h3 className="st-h3">{p.t}</h3>
              <p style={{ fontSize: 14.5, lineHeight: 1.6, color: "var(--tinta-2)", margin: 0 }}>{p.d}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="st-sec">
        <h2 className="st-h2">{INICIO.equipoTitulo}</h2>
        <p className="st-sub">{INICIO.equipoRotulo}</p>
        {equipo.length > 0 && (
          <ul className="st-tira">
            {equipo.map((p) => <li key={p.id}><Foto p={p} size={54} /></li>)}
          </ul>
        )}
        <div className="st-acciones">
          <a className="st-btn st-btn-2" {...propsEnlace("/psicologos")}>
            Conócelos aquí <ArrowRight size={16} strokeWidth={2.2} aria-hidden="true" />
          </a>
        </div>
      </section>

      <section className="st-sec st-sec-clara">
        <h2 className="st-h2">{INICIO.testimoniosTitulo}</h2>
        <p className="st-sub">{INICIO.testimoniosRotulo}</p>
        <div className="st-testis">
          {TESTIMONIOS.map((t) => (
            <figure key={t.nombre} className="st-testi">
              <blockquote><p>{t.texto}</p></blockquote>
              <figcaption>
                <span className="st-testi-ini" aria-hidden="true">{iniciales(t.nombre)}</span>
                <span>
                  <span className="st-testi-quien">{t.nombre}</span>
                  <span className="st-testi-rol">Paciente</span>
                </span>
              </figcaption>
            </figure>
          ))}
        </div>
      </section>

      <section className="st-sec">
        <h2 className="st-h2">Antes de decidirte</h2>
        <p className="st-sub">Las que más nos preguntan.</p>
        <div className="ag-dudas" style={{ marginTop: 0 }}>
          {["costo", "online", "confidencial", "elegir"].map((id) => {
            const item = faq.find((f) => f.id === id);
            return item ? <AgendaDuda key={id} item={item} /> : null;
          })}
        </div>
        <p className="st-nota">
          <a {...propsEnlace("/preguntas")} style={{ color: "var(--acento)", fontWeight: 600 }}>Ver todas las preguntas</a>
        </p>
      </section>

      <Cierre token={token} titulo={INICIO.procesoFrase} />
    </>
  );
}

// ── Página: quiénes somos ─────────────────────────────────────────────────
function PaginaQuienes({ token }) {
  const q = QUIENES_SOMOS;
  return (
    <>
      <section className="st-hero">
        <p className="st-rotulo">{q.rotulo}</p>
        <h1 className="st-h1">{q.titulo}</h1>
        <div className="st-lee">{q.parrafos.map((p, i) => <p key={i}>{p}</p>)}</div>
      </section>

      <section className="st-sec st-sec-clara">
        <div className="st-rej-2">
          <div>
            <h2 className="st-h2">{q.queHacemosTitulo}</h2>
            <p className="st-sub">{q.queHacemosEntrada}</p>
            <ul className="st-lista">
              {q.queHacemos.map((x) => (
                <li key={x}><Check size={17} strokeWidth={2.2} aria-hidden="true" />{x}</li>
              ))}
            </ul>
          </div>
          <div>
            <h2 className="st-h2">{q.areasTitulo}</h2>
            <p className="st-sub">Tres frentes, en este orden.</p>
            <ul className="st-lista">
              {q.areas.map((x) => (
                <li key={x}><Check size={17} strokeWidth={2.2} aria-hidden="true" />{x}</li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <section className="st-sec">
        <h2 className="st-h2">{q.modeloTitulo}</h2>
        <div className="st-lee" style={{ marginTop: 14 }}>{q.modelo.map((p, i) => <p key={i}>{p}</p>)}</div>
      </section>

      <section className="st-sec st-sec-clara">
        <h2 className="st-h2">{q.creenciasTitulo}</h2>
        <p className="st-sub">Lo que nos repetimos en el equipo.</p>
        <div className="st-rej">
          {q.creencias.map((c) => (
            <div key={c} className="st-card"><p>{c}</p></div>
          ))}
        </div>
      </section>

      <Cierre token={token} />
    </>
  );
}

// ── Página: psicólogos (la lista sale de la base) ─────────────────────────
function TarjetaProfesional({ p, token }) {
  const meta = [p.titulo, p.colegiatura ? `C.Ps.P. N° ${p.colegiatura}` : "", p.sede_label, p.modalidad_label]
    .filter(Boolean).join(" · ");
  return (
    <article className="st-prof">
      <div className="st-prof-top">
        <Foto p={p} />
        <div style={{ minWidth: 0 }}>
          <h3 className="st-prof-nombre">{p.nombre}</h3>
          <p className="st-prof-meta">{meta}</p>
        </div>
      </div>
      {p.frase ? <p className="st-prof-frase">{p.frase}</p> : null}
      <div className="st-prof-datos">
        {p.enfoque ? <p className="st-dato"><strong>Enfoque</strong><span className="st-corta">{p.enfoque}</span></p> : null}
        {p.poblaciones ? <p className="st-dato"><strong>Atiende a</strong>{p.poblaciones}</p> : null}
      </div>
      {(p.problematicas || p.formacion || p.trayectoria) && (
        <details className="st-perfil">
          <summary>Ver perfil completo <ChevronDown size={16} strokeWidth={2} aria-hidden="true" /></summary>
          <div className="st-prof-datos">
            {p.problematicas ? <p className="st-dato"><strong>Qué trabaja</strong>{p.problematicas}</p> : null}
            {p.formacion ? <p className="st-dato"><strong>Formación</strong>{p.formacion}</p> : null}
            {p.trayectoria ? <p className="st-dato"><strong>Trayectoria</strong>{p.trayectoria}</p> : null}
          </div>
        </details>
      )}
      <div className="st-prof-pie">
        {p.agendable
          ? <BotonReservar token={token}>Ver sus horarios</BotonReservar>
          : (
            <a className="st-btn st-btn-2" href={AGENDA_SITIO.whatsapp} target="_blank" rel="noopener">
              Consultar por WhatsApp <MessageCircle size={16} strokeWidth={2} aria-hidden="true" />
            </a>
          )}
      </div>
    </article>
  );
}

function PaginaPsicologos({ datos, token, cargando }) {
  const [sede, setSede] = useState("");
  const equipo = useMemo(() => datos?.equipo || [], [datos]);
  const mostrados = sede ? equipo.filter((p) => p.sede === sede) : equipo;
  const sedes = useMemo(() => [...new Set(equipo.map((p) => p.sede))].filter(Boolean), [equipo]);
  return (
    <>
      <section className="st-hero" style={{ paddingBottom: 0 }}>
        <p className="st-rotulo">{PSICOLOGOS.rotulo}</p>
        <h1 className="st-h1">{PSICOLOGOS.titulo}</h1>
        <p className="st-hero-lead">{PSICOLOGOS.entrada}</p>
      </section>

      <section className="st-sec">
        {sedes.length > 1 && (
          <div className="st-filtros" role="group" aria-label="Filtrar por sede">
            <button type="button" className="st-filtro" aria-pressed={sede === ""} onClick={() => setSede("")}>
              Todos ({equipo.length})
            </button>
            {sedes.map((s) => (
              <button key={s} type="button" className="st-filtro" aria-pressed={sede === s} onClick={() => setSede(s)}>
                {AGENDA_SEDES[s]?.label || s} ({equipo.filter((p) => p.sede === s).length})
              </button>
            ))}
          </div>
        )}
        {cargando ? <p className="st-cargando">Cargando el equipo…</p>
          : mostrados.length === 0 ? (
            <div className="st-aviso">
              No pudimos cargar el equipo en este momento. Escríbenos por WhatsApp y te contamos quién puede atenderte.
            </div>
          ) : (
            <div className="st-equipo">
              {mostrados.map((p) => <TarjetaProfesional key={p.id} p={p} token={token} />)}
            </div>
          )}
      </section>

      <Cierre token={token} titulo="¿Ya sabes con quién quieres atenderte?"
        texto="Elige su horario y reserva. Si prefieres que te ayudemos a elegir, cuéntanos qué necesitas y coordinación te acompaña." />
    </>
  );
}

// ── Página: terapias online ───────────────────────────────────────────────
function PaginaTerapias({ datos, token }) {
  const t = TERAPIAS;
  const servicios = datos?.servicios || [];
  return (
    <>
      <section className="st-hero">
        <p className="st-rotulo">{t.rotulo}</p>
        <h1 className="st-h1">{t.titulo}</h1>
        <p className="st-hero-lead">{t.entradaRotulo}.</p>
        <div className="st-acciones"><BotonReservar token={token}>Pide tu terapia</BotonReservar></div>
      </section>

      <section className="st-sec st-sec-clara">
        <div className="st-rej-2">
          <div className="st-lee">
            <h2 className="st-h2">{t.entradaTitulo}</h2>
            <p style={{ marginTop: 14 }}>{t.cuerpo}</p>
          </div>
          <div>
            <h3 className="st-h3" style={{ marginBottom: 12 }}>{t.paraTitulo}</h3>
            <ul className="st-chips">{t.para.map((x) => <li key={x}>{x}</li>)}</ul>
          </div>
        </div>
      </section>

      <section className="st-sec">
        <h2 className="st-h2">{t.temasTitulo}</h2>
        <p className="st-sub">Nuestro equipo tiene experiencia en una amplia variedad de problemáticas.</p>
        <ul className="st-chips">{t.temas.map((x) => <li key={x}>{x}</li>)}</ul>
      </section>

      {servicios.length > 0 && (
        <section className="st-sec st-sec-clara">
          <h2 className="st-h2">Nuestros paquetes</h2>
          <p className="st-sub">
            Precios vigentes del catálogo de la clínica. La primera consulta sirve para conocer a tu psicólogo y
            definir tu plan; después, tu asesor te ayuda a elegir el paquete y las facilidades de pago.
          </p>
          <div className="st-rej">
            {servicios.map((s) => (
              <div key={s.nombre} className="st-card">
                <h3 className="st-h3">{s.nombre}</h3>
                <p style={{ fontSize: 19, fontWeight: 600, color: "var(--acento)", letterSpacing: "-0.02em" }}>
                  S/ {Number(s.precio).toFixed(0)}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="st-sec">
        <p className="st-rotulo">{t.circuloRotulo}</p>
        <h2 className="st-h2">{t.circuloTitulo}</h2>
        <p className="st-sub">{t.circuloEntrada}</p>
        <div className="st-rej">
          {t.circulos.map((c) => (
            <div key={c.nombre} className="st-card">
              <h3 className="st-h3">{c.nombre}</h3>
              <p style={{ marginBottom: 10, color: "var(--tinta-3)" }}>{c.preguntas}</p>
              <p>{c.texto}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="st-sec st-sec-clara">
        <p className="st-rotulo">{t.cierreRotulo}</p>
        <h2 className="st-h2">{t.cierreTitulo}</h2>
        <div className="st-lee" style={{ marginTop: 14 }}>{t.cierre.map((p, i) => <p key={i}>{p}</p>)}</div>
      </section>

      <Cierre token={token} titulo="Estás a solo un paso"
        texto="Empecemos el viaje. Elige sede, psicólogo y horario; nosotros confirmamos contigo antes de tu sesión." />
    </>
  );
}

// ── Página: preguntas frecuentes ──────────────────────────────────────────
function PaginaPreguntas({ token, faq }) {
  return (
    <>
      <section className="st-hero" style={{ paddingBottom: 0 }}>
        <p className="st-rotulo">{PREGUNTAS.rotulo}</p>
        <h1 className="st-h1">{PREGUNTAS.titulo}</h1>
        <p className="st-hero-lead">{PREGUNTAS.entrada}</p>
      </section>

      <section className="st-sec">
        <div className="ag-dudas" style={{ marginTop: 0 }}>
          {faq.map((item) => <AgendaDuda key={item.id} item={item} />)}
        </div>
      </section>

      <Cierre token={token} titulo="¿Te quedó alguna duda?"
        texto="Escríbenos por WhatsApp y te respondemos. Si ya lo tienes claro, puedes reservar tu primera consulta ahora." />
    </>
  );
}

// ── Raíz del sitio: ruta, datos y marco ───────────────────────────────────
const TITULOS = {
  "/": "Ítaca Conversemos · Terapia psicológica en Lima y Piura",
  "/quienes-somos": "Quiénes somos · Ítaca Conversemos",
  "/psicologos": "Nuestros psicólogos · Ítaca Conversemos",
  "/terapias-online": "Terapias online · Ítaca Conversemos",
  "/preguntas": "Preguntas frecuentes · Ítaca Conversemos",
};

export function SitioPublico() {
  const [ruta, setRuta] = useState(() => normalizarRuta(window.location.pathname));
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => alCambiarRuta(() => setRuta(normalizarRuta(window.location.pathname))), []);

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
    document.title = TITULOS[ruta] || TITULOS["/"];
    document.documentElement.lang = "es";
  }, [ruta]);

  const token = datos?.token_agenda || "";
  // El precio de la primera consulta sale del catálogo real; si no está
  // publicado, el que dice el sitio. Mismo criterio que en el agendamiento.
  const faq = useMemo(() => {
    const s = (datos?.servicios || []).find((x) => /consulta|inicial|primera/i.test(x.nombre) && Number(x.precio) > 0);
    return agendaFaq(s ? `S/ ${Number(s.precio).toFixed(0)}` : "S/ 50");
  }, [datos]);

  const pagina =
    ruta === "/quienes-somos" ? <PaginaQuienes token={token} />
      : ruta === "/psicologos" ? <PaginaPsicologos datos={datos} token={token} cargando={cargando} />
        : ruta === "/terapias-online" ? <PaginaTerapias datos={datos} token={token} />
          : ruta === "/preguntas" ? <PaginaPreguntas token={token} faq={faq} />
            : <PaginaInicio datos={datos} token={token} faq={faq} />;

  return (
    <div className="ag st-sitio">
      <style>{AGENDA_CSS}{SITIO_CSS}</style>
      <AgendaTop ruta={ruta} token={token} />
      <main className="st-wrap">{pagina}</main>
      <AgendaPie />
      <AgendaWa />
    </div>
  );
}
