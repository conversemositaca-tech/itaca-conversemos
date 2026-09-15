import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App, { ConsentimientoPublico, AgendarPublico, sincronizarReloj } from './App.jsx'
import { SitioPublico } from './Sitio.jsx'
import { esRutaSitio } from './rutas'

// Qué se monta según el path, EN ESTE ORDEN:
//  /consentimiento/<token>  → firma del consentimiento (público)
//  /agendar/<token>         → auto-agendamiento de cita (público)
//  /gestion[/...]           → sistema interno de gestión (pide login)
//  /, /quienes-somos, /psicologos, /terapias-online, /preguntas → sitio público
//  cualquier otra           → el sistema interno, como siempre
// Las rutas /api/, /admin/, /static/ y /media/ las resuelve Django y nunca
// llegan hasta aquí (ver el catch-all de config/urls.py).
const RUTA = window.location.pathname
const cons = RUTA.match(/^\/consentimiento\/([^/]+)/)
const agen = RUTA.match(/^\/agendar\/([^/]+)/)
const gestion = /^\/gestion(\/|$)/.test(RUTA)
const sitio = !cons && !agen && !gestion && esRutaSitio(RUTA)

function arrancar() {
  createRoot(document.getElementById('root')).render(
    <StrictMode>
      {cons ? <ConsentimientoPublico token={cons[1]} />
        : agen ? <AgendarPublico token={agen[1]} />
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
