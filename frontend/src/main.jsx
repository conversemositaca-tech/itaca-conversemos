import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App, { ConsentimientoPublico, AgendarPublico, sincronizarReloj } from './App.jsx'
import { SitioPublico } from './Sitio.jsx'
import { esRutaSitio } from './rutas'

// Páginas públicas (sin login), enrutadas por el path:
//  /consentimiento/<token>  → firma del consentimiento
//  /agendar/<token>         → auto-agendamiento de cita
//  /, /quienes-somos, /psicologos, /terapias-online, /preguntas → sitio público
// Cualquier otra ruta es el panel interno (que pide login).
const cons = window.location.pathname.match(/^\/consentimiento\/([^/]+)/)
const agen = window.location.pathname.match(/^\/agendar\/([^/]+)/)
const sitio = !cons && !agen && esRutaSitio(window.location.pathname)

function arrancar() {
  createRoot(document.getElementById('root')).render(
    <StrictMode>
      {cons ? <ConsentimientoPublico token={cons[1]} />
        : agen ? <AgendarPublico token={agen[1]} />
          : sitio ? <SitioPublico />
            : <App />}
    </StrictMode>,
  )
}

// Sincroniza "hoy" con el reloj del servidor ANTES de pintar, para que la fecha sea
// correcta aunque el reloj del equipo esté mal. Tope de 1.5s: si la red tarda o
// falla, arranca igual con el reloj del equipo (y se corrige al volver a la pestaña).
Promise.race([sincronizarReloj(), new Promise((r) => setTimeout(r, 1500))]).finally(arrancar)
