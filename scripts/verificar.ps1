<#
.SYNOPSIS
  Punto único de verificación de Ítaca Conversemos.

.DESCRIPTION
  FAST      ciclo de edición: check, migraciones, tests de las apps tocadas +
            regresión de seguridad, ESLint de los archivos cambiados.
  STANDARD  para declarar una feature terminada: lo de FAST + suite completa,
            build del frontend y ESLint del proyecto contra la línea base.
  FULL      integración / release: STANDARD desde cero (sin reusar la base de
            prueba) + `check --deploy` con configuración de producción.

  Las pruebas corren SIEMPRE contra una base SQLite temporal: aunque exista un
  .env con DATABASE_URL de producción, este script no la usa.

  Códigos de salida: 0 = todo bien (puede haber avisos), 1 = algún paso falló,
  2 = el entorno no permite verificar (falta Python, Node, etc.).

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verificar.ps1 -Modo FAST
#>
param(
    [ValidateSet("FAST", "STANDARD", "FULL")]
    [string]$Modo = "STANDARD",
    [switch]$Silencioso
)

# "Continue" a propósito: en PowerShell 5.1 cualquier línea de git en stderr
# (p. ej. el aviso de finales de línea) con "Stop" aborta el script.
$ErrorActionPreference = "Continue"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz

# Una carpeta por worktree: dos sesiones en paralelo no comparten la base de prueba.
$huellaRaiz = [BitConverter]::ToString([Security.Cryptography.MD5]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($raiz.ToLower()))).Replace("-", "").Substring(0, 10)
$trabajo = Join-Path $env:TEMP "itaca-verificar\$huellaRaiz"
New-Item -ItemType Directory -Force -Path $trabajo | Out-Null
$sello = Get-Date -Format "yyyyMMdd-HHmmss"
$logs = Join-Path $trabajo "logs-$sello"
New-Item -ItemType Directory -Force -Path $logs | Out-Null

$resultados = New-Object System.Collections.ArrayList
$inicioTotal = Get-Date

function Escribir([string]$texto) {
    if (-not $Silencioso) { Write-Host $texto }
}

function Registrar([string]$paso, [string]$estado, [double]$segundos, [string]$detalle) {
    [void]$resultados.Add([pscustomobject]@{ Paso = $paso; Estado = $estado; Segundos = [math]::Round($segundos, 1); Detalle = $detalle })
    $marca = @{ "OK" = "[ok]  "; "AVISO" = "[aviso]"; "FALLA" = "[FALLA]"; "OMITIDO" = "[--]  " }[$estado]
    Escribir ("{0} {1,-34} {2,6}s  {3}" -f $marca, $paso, [math]::Round($segundos, 1), $detalle)
}

# Corre un comando nativo vía cmd para capturar stdout+stderr sin las rarezas de
# PowerShell 5.1 con stderr. Devuelve el código de salida.
function Correr([string]$nombreLog, [string]$linea, [string]$dir = $raiz) {
    $log = Join-Path $logs "$nombreLog.log"
    Push-Location $dir
    try {
        cmd /c "$linea > `"$log`" 2>&1"
        return $LASTEXITCODE
    } finally { Pop-Location }
}

function Ultimas([string]$nombreLog, [int]$n = 15) {
    $log = Join-Path $logs "$nombreLog.log"
    if (Test-Path $log) { return (Get-Content $log -Tail $n) -join "`n" }
    return ""
}

# --- Entorno -----------------------------------------------------------------
function Buscar-Python {
    if ($env:ITACA_PYTHON -and (Test-Path $env:ITACA_PYTHON)) { return $env:ITACA_PYTHON }
    $local = Join-Path $raiz ".venv\Scripts\python.exe"
    if (Test-Path $local) { return $local }
    # En un worktree el .venv vive en la carpeta principal del repo.
    $comun = (git rev-parse --git-common-dir 2>$null)
    if ($comun) {
        $principal = Split-Path -Parent (Resolve-Path $comun)
        $compartido = Join-Path $principal ".venv\Scripts\python.exe"
        if (Test-Path $compartido) { return $compartido }
    }
    $sistema = Get-Command python -ErrorAction SilentlyContinue
    if ($sistema) { return $sistema.Source }
    return $null
}

$py = Buscar-Python
if (-not $py) { Write-Host "No encontré Python (.venv ni ITACA_PYTHON)."; exit 2 }
$hayNode = [bool](Get-Command npx -ErrorAction SilentlyContinue)
$hayModulos = Test-Path (Join-Path $raiz "frontend\node_modules")

$env:DATABASE_URL = "sqlite:///" + (Join-Path $trabajo "verificar.sqlite3").Replace("\", "/")
$env:DJANGO_DB_SSL = "False"
$env:PYTHONIOENCODING = "utf-8"
# La base de prueba va EN MEMORIA (lo que hace Django por defecto con SQLite).
# Probado: con --keepdb en archivo la suite pasó de ~100 s a ~50 min en
# Windows (cada test escribe a disco). Crearla cuesta ~35 s y vale la pena.

# --- Qué cambió ------------------------------------------------------------------
# FAST mira lo que aún no está en un commit (el ciclo de edición). STANDARD y
# FULL miran toda la rama respecto de origin/main.
$base = (git merge-base HEAD origin/main 2>$null)
if (-not $base) { $base = "HEAD" }
if ($Modo -eq "FAST") { $base = "HEAD" }
$cambiados = @()
$cambiados += (git diff --name-only $base 2>$null)
$cambiados += (git ls-files --others --exclude-standard 2>$null)
$cambiados = $cambiados | Where-Object { $_ } | ForEach-Object { $_.Replace("\", "/") } | Sort-Object -Unique

$apps = Get-ChildItem -Directory $raiz | Where-Object { Test-Path (Join-Path $_.FullName "apps.py") } | ForEach-Object { $_.Name }
$appsTocadas = $cambiados | ForEach-Object { ($_ -split "/")[0] } | Where-Object { $apps -contains $_ } | Sort-Object -Unique
$tocaConfig = [bool]($cambiados | Where-Object { $_ -like "config/*" })
$frontCambiado = $cambiados | Where-Object { $_ -like "frontend/*" -and $_ -match "\.(js|jsx)$" -and (Test-Path $_) }

Escribir "verificar.ps1 · modo $Modo · base $($base.Substring(0, [math]::Min(7, $base.Length)))"

# --- 1. Django check -------------------------------------------------------------
$t = Get-Date
$rc = Correr "check" "`"$py`" manage.py check"
if ($rc -eq 0) { Registrar "django check" "OK" ((Get-Date) - $t).TotalSeconds "" }
else { Registrar "django check" "FALLA" ((Get-Date) - $t).TotalSeconds (Ultimas "check" 8) }

# --- 2. Migraciones al día ---------------------------------------------------------
$t = Get-Date
$rc = Correr "migraciones" "`"$py`" manage.py makemigrations --check --dry-run"
if ($rc -eq 0) { Registrar "migraciones al día" "OK" ((Get-Date) - $t).TotalSeconds "" }
else { Registrar "migraciones al día" "FALLA" ((Get-Date) - $t).TotalSeconds "falta generar una migración: $(Ultimas 'migraciones' 6)" }

# --- 3. Tests backend ----------------------------------------------------------------
$t = Get-Date
$etiquetas = @()
if ($Modo -eq "FAST") {
    $etiquetas += $appsTocadas
    if ($tocaConfig -and -not ($etiquetas -contains "core")) { $etiquetas += "core" }
    # La regresión de seguridad y la matriz de permisos corren siempre.
    if (-not ($etiquetas -contains "core")) {
        $etiquetas += "core.tests_seguridad_p0", "core.tests_matriz_permisos"
    }
}
$nombre = "tests"
$descripcion = "suite completa"
if ($Modo -eq "FAST") { $descripcion = "apps: " + (($etiquetas | ForEach-Object { ($_ -split "\.")[0] } | Sort-Object -Unique) -join ", ") }
$rc = Correr $nombre "`"$py`" manage.py test $($etiquetas -join ' ') --noinput"
$seg = ((Get-Date) - $t).TotalSeconds
$resumenTests = (Select-String -Path (Join-Path $logs "$nombre.log") -Pattern "^Ran \d+ tests?" -ErrorAction SilentlyContinue | Select-Object -Last 1).Line
if ($rc -eq 0) { Registrar "tests backend" "OK" $seg "$resumenTests · $descripcion" }
else {
    $fallos = (Select-String -Path (Join-Path $logs "$nombre.log") -Pattern "^(FAIL|ERROR):" -ErrorAction SilentlyContinue | Select-Object -First 8 | ForEach-Object { $_.Line }) -join "`n"
    if (-not $fallos) { $fallos = Ultimas $nombre 12 }
    Registrar "tests backend" "FALLA" $seg "$resumenTests`n$fallos"
}

# --- 4. ESLint: ninguna deuda nueva ------------------------------------------------
$t = Get-Date
if (-not ($hayNode -and $hayModulos)) {
    Registrar "eslint (sin deuda nueva)" "AVISO" 0 "no hay Node o frontend/node_modules: no se pudo revisar"
} else {
    $objetivo = "."
    if ($Modo -eq "FAST") {
        $objetivo = ($frontCambiado | ForEach-Object { '"' + ($_ -replace "^frontend/", "") + '"' }) -join " "
    }
    if ($Modo -eq "FAST" -and -not $objetivo) {
        Registrar "eslint (sin deuda nueva)" "OMITIDO" 0 "no cambió JS/JSX"
    } else {
        $json = Join-Path $logs "eslint.json"
        [void](Correr "eslint" "npx eslint $objetivo --cache --cache-location `"$trabajo\.eslintcache`" -f json -o `"$json`"" (Join-Path $raiz "frontend"))
        if (-not (Test-Path $json)) {
            Registrar "eslint (sin deuda nueva)" "FALLA" ((Get-Date) - $t).TotalSeconds (Ultimas "eslint" 10)
        } else {
            # La regla vive en scripts/eslint-sin-deuda.mjs: la misma que usa el CI.
            $rc = Correr "eslint-sin-deuda" "node scripts\eslint-sin-deuda.mjs `"$json`""
            $seg = ((Get-Date) - $t).TotalSeconds
            $texto = Get-Content (Join-Path $logs "eslint-sin-deuda.log") -Encoding UTF8
            $resumen = ($texto | Select-Object -First 1) -replace "^ESLint: ", ""
            $fallas = ($texto | Where-Object { $_ -like "FALLA*" }) -join "; "
            $avisosE = ($texto | Where-Object { $_ -like "AVISO*" }) -join "; "
            if ($rc -ne 0) { Registrar "eslint (sin deuda nueva)" "FALLA" $seg ("errores nuevos: " + $fallas) }
            elseif ($avisosE) { Registrar "eslint (sin deuda nueva)" "AVISO" $seg ("avisos nuevos: " + $avisosE) }
            else { Registrar "eslint (sin deuda nueva)" "OK" $seg $resumen }
        }
    }
}

# --- 5. Tests y build del frontend -----------------------------------------------------
if ($Modo -ne "FAST" -and $hayNode) {
    $t = Get-Date
    $rc = Correr "tests-frontend" "node --test" (Join-Path $raiz "frontend")
    $resumenFront = (Select-String -Path (Join-Path $logs "tests-frontend.log") -Pattern "^. tests \d+" -ErrorAction SilentlyContinue | Select-Object -Last 1).Line
    if ($rc -eq 0) { Registrar "tests frontend" "OK" ((Get-Date) - $t).TotalSeconds "$resumenFront" }
    else { Registrar "tests frontend" "FALLA" ((Get-Date) - $t).TotalSeconds (Ultimas "tests-frontend" 12) }
}
if ($Modo -ne "FAST") {
    $t = Get-Date
    if (-not ($hayNode -and $hayModulos)) {
        Registrar "build frontend" "AVISO" 0 "no hay Node o frontend/node_modules"
    } else {
        $rc = Correr "build" "npm run build" (Join-Path $raiz "frontend")
        if ($rc -eq 0) { Registrar "build frontend" "OK" ((Get-Date) - $t).TotalSeconds "" }
        else { Registrar "build frontend" "FALLA" ((Get-Date) - $t).TotalSeconds (Ultimas "build" 12) }
    }
}

# --- 6. Configuración de producción (solo FULL) ---------------------------------------
if ($Modo -eq "FULL") {
    $t = Get-Date
    $prevDebug = $env:DJANGO_DEBUG; $prevKey = $env:DJANGO_SECRET_KEY
    $env:DJANGO_DEBUG = "False"
    $env:DJANGO_SECRET_KEY = "verificar-" + [guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")
    $rc = Correr "check-deploy" "`"$py`" manage.py check --deploy --fail-level ERROR"
    $env:DJANGO_DEBUG = $prevDebug; $env:DJANGO_SECRET_KEY = $prevKey
    $avisos = ([regex]::Matches((Get-Content (Join-Path $logs "check-deploy.log") -Raw), "security\.W\d+") | ForEach-Object { $_.Value } | Sort-Object -Unique) -join ", "
    if ($rc -ne 0) { Registrar "check --deploy" "FALLA" ((Get-Date) - $t).TotalSeconds (Ultimas "check-deploy" 10) }
    elseif ($avisos) { Registrar "check --deploy" "AVISO" ((Get-Date) - $t).TotalSeconds $avisos }
    else { Registrar "check --deploy" "OK" ((Get-Date) - $t).TotalSeconds "" }
}

# --- Resumen ---------------------------------------------------------------------------
$total = [math]::Round(((Get-Date) - $inicioTotal).TotalSeconds, 1)
$fallas = @($resultados | Where-Object { $_.Estado -eq "FALLA" })
$avisosTot = @($resultados | Where-Object { $_.Estado -eq "AVISO" })
if ($fallas.Count) {
    if ($Silencioso) {
        foreach ($r in $fallas) { Write-Host "[FALLA] $($r.Paso): $($r.Detalle)" }
    }
    Write-Host "verificar $($Modo): FALLA ($($fallas.Count) paso(s)) en $total s · logs: $logs"
    exit 1
}
Escribir "verificar $($Modo): OK en $total s ($($avisosTot.Count) aviso(s)) · logs: $logs"
exit 0
