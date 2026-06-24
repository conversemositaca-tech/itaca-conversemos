import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App, { ConsentimientoPublico } from './App.jsx'

// Página pública del consentimiento (sin login): /consentimiento/<token>
const m = window.location.pathname.match(/^\/consentimiento\/([^/]+)/)

createRoot(document.getElementById('root')).render(
  <StrictMode>
    {m ? <ConsentimientoPublico token={m[1]} /> : <App />}
  </StrictMode>,
)
