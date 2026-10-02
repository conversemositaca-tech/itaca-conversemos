---
name: qa-browser
description: Validación funcional de pantallas en navegador para proyectos de la Ítaca Software Factory. Úsala después de cambiar una pantalla y antes de abrir el PR. Levanta el proyecto contra una base demo aislada, recorre el flujo por cada rol afectado en 1366 px y 390 px, y reporta consola, red, estados y factores humanos. Si no hay navegador automatizable, hace la revisión estática y lo dice.
---

# QA en navegador

## Entorno (siempre aislado)
1. Base demo propia: `DATABASE_URL=sqlite:///<scratchpad>/qa.sqlite3`, `python manage.py migrate`, `python manage.py crear_demo --password <generada>` (o el seed del proyecto). **Nunca** contra una base real ni con el `.env` de producción.
2. Backend en un puerto libre (p. ej. 8765) y Vite con `VITE_API_TARGET=http://127.0.0.1:8765`.
3. Anota los PID para detenerlos al final.

## Recorrido
Para cada rol afectado (según la matriz de la feature), en 1366 px y en 390 px:
- Flujo feliz completo de la feature.
- Estados: vacío, cargando (red lenta), error (forzar 500/400), mucho dato.
- Acciones destructivas: ¿piden `confirmar()` con la consecuencia escrita?
- Modales de formulario: ¿se cierran por clic fuera o Escape con datos? (no deben).
- Doble clic en guardar: ¿una sola petición?
- Avisos: errores con tipo `error`, no con check verde.
- Teclado: Tab llega a todo, Enter envía formularios, Escape cierra lo descartable.
- Consola del navegador limpia; ninguna petición 4xx/5xx inesperada.

## Herramienta
- Playwright si está disponible (no lo instales en el repo del cliente sin permiso; usa uno global o del scratchpad).
- Si no hay navegador automatizable: revisión estática del JSX contra la lista anterior + `npm run build` + tests de `node --test`. **Dilo explícitamente en el reporte**: "QA en navegador no ejecutado".

## Salida
`qa/<fecha>-<slug>.md` fuera del repo (o adjunto al PR): tabla rol × paso × resultado, capturas, errores de consola, fricciones con severidad. Detén los procesos que levantaste.
