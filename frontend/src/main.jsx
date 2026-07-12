import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App, { ConsentimientoPublico, AgendarPublico } from './App.jsx'

// Páginas públicas (sin login), enrutadas por el path:
//  /consentimiento/<token>  → firma del consentimiento
//  /agendar/<token>         → auto-agendamiento de cita
const cons = window.location.pathname.match(/^\/consentimiento\/([^/]+)/)
const agen = window.location.pathname.match(/^\/agendar\/([^/]+)/)

createRoot(document.getElementById('root')).render(
  <StrictMode>
    {cons ? <ConsentimientoPublico token={cons[1]} />
      : agen ? <AgendarPublico token={agen[1]} />
      : <App />}
  </StrictMode>,
)
