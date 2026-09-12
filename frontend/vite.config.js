import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// En desarrollo, las llamadas a /api se reenvían a Django (puerto 8000).
// Así el navegador habla solo con Vite (5173) y no hay problemas de CORS.
export default defineConfig(({ command }) => ({
  // En producción la app la sirve Django bajo /static/; en desarrollo, Vite en la raíz.
  base: command === 'build' ? '/static/' : '/',
  plugins: [react()],
  server: {
    port: 5174,
    // Permite abrir la app a través del túnel temporal (cloudflared) para demos.
    allowedHosts: ['.trycloudflare.com'],
    proxy: {
      // El destino se puede cambiar con VITE_API_TARGET para levantar una
      // segunda instancia (revision, demo) sin tocar la que ya corre.
      '/api': { target: process.env.VITE_API_TARGET || 'http://127.0.0.1:8001', changeOrigin: true },
    },
  },
}))
