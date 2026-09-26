import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App, { ConsentimientoPublico, AgendarPublico, sincronizarReloj } from './App.jsx'
import { AutorizacionFaro, PanelFaro, SitioPublico, TamizajeFaro } from './Sitio.jsx'
import { esRutaSitio } from './rutas'
import { recordarOrigen } from './origen'
import { PASOS, registrar } from './embudo'

// Qué se monta según el path, EN ESTE ORDEN:
//  /consentimiento/<token>  → firma del consentimiento (público)
//  /agendar/<token>         → auto-agendamiento de cita (público)
//  /faro/t/<token>          → cuestionario del estudiante (público)
//  /faro/a/<token>          → autorización de la familia (público)
//  /faro/<token>            → panel del colegio (público, sin cuenta)
//  /gestion[/...]           → sistema interno de gestión (pide login)
//  /, /quienes-somos, /psicologos, /terapias-online, /preguntas → sitio público
//  cualquier otra           → el sistema interno, como siempre
// Las rutas /api/, /admin/, /static/ y /media/ las resuelve Django y nunca
// llegan hasta aquí (ver el catch-all de config/urls.py).
const RUTA = window.location.pathname
const cons = RUTA.match(/^\/consentimiento\/([^/]+)/)
const agen = RUTA.match(/^\/agendar\/([^/]+)/)
// El del aula va PRIMERO: con el otro patrón, /faro/t/xxx leeria "t" como
// el token del colegio y le abriria el panel a un alumno.
const faroT = RUTA.match(/^\/faro\/t\/([^/]+)/)
const faroA = !faroT && RUTA.match(/^\/faro\/a\/([^/]+)/)
const faro = !faroT && !faroA && RUTA.match(/^\/faro\/([^/]+)/)
const gestion = /^\/gestion(\/|$)/.test(RUTA)
const sitio = !cons && !agen && !faro && !faroT && !faroA && !gestion && esRutaSitio(RUTA)

// De dónde llegó la visita (campaña, anuncio, sitio que refirió). Se guarda al
// entrar porque la reserva ocurre después, cuando la URL ya no lleva nada.
recordarOrigen()

// Llegó al formulario de reserva. Es el paso donde más se abandona —ya decidió
// pedir cita y algo lo detiene— y hasta ahora era invisible: solo se veía a
// quien terminaba. Se cuenta aquí, y no dentro del agendamiento, para no tocar
// App.jsx por una medición.
if (agen) registrar(PASOS.ABRE_AGENDA, '/agendar')

function arrancar() {
  createRoot(document.getElementById('root')).render(
    <StrictMode>
      {cons ? <ConsentimientoPublico token={cons[1]} />
        : agen ? <AgendarPublico token={agen[1]} />
          : faroT ? <TamizajeFaro token={faroT[1]} />
          : faroA ? <AutorizacionFaro token={faroA[1]} />
            : faro ? <PanelFaro token={faro[1]} />
            : gestion ? <App />
              : sitio ? <SitioPublico />
                : <App />}
    </StrictMode>,
  )
}

// Sincroniza "hoy" con el reloj del servidor ANTES de pintar, para que la fecha sea
// correcta aunque el reloj del equipo esté mal. Tope de 1.5s: si la red tarda o
// falla, arranca igual con el reloj del equipo (y se corrige al volver a la pestaña).
Promise.race([sincronizarReloj(), new Promise((r) => setTimeout(r, 1500))]).finally(arrancar)
