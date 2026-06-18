# Levanta el backend (Django) y el frontend (Vite) en ventanas separadas.
# Uso:  ./dev.ps1
$raiz = $PSScriptRoot

Write-Host "Iniciando backend (Django) en http://127.0.0.1:8000 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command",
  "Set-Location '$raiz'; & '.\.venv\Scripts\python.exe' manage.py runserver"

Write-Host "Iniciando frontend (Vite) en http://localhost:5173 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command",
  "Set-Location '$raiz\frontend'; npm run dev"

Write-Host ""
Write-Host "Listo. Abre http://localhost:5173 en el navegador." -ForegroundColor Cyan
Write-Host "Cierra las dos ventanas de PowerShell para detener los servidores."
