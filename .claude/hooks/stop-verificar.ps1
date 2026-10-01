<#
  Stop hook de Claude Code: no se da por terminada una tarea con código sin
  verificar.

  - Si el árbol (HEAD + cambios + archivos nuevos) ya pasó la verificación,
    o si solo cambiaron documentos, sale en silencio.
  - Si no, corre scripts/verificar.ps1 STANDARD en silencio. Si falla, devuelve
    código 2: Claude Code bloquea el cierre y le muestra a Claude qué falló.
  - Tras 3 bloqueos sobre el mismo árbol deja terminar, pero con un aviso
    visible para la persona (evita bucles infinitos).

  FULL nunca corre aquí: es manual, antes de integrar o publicar.
#>
$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$raiz = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $raiz

$entrada = $null
try { $entrada = [Console]::In.ReadToEnd() | ConvertFrom-Json } catch { }

function Huella([string]$texto) {
    $sha = [Security.Cryptography.SHA256]::Create()
    return [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($texto))).Replace("-", "")
}

$cabeza = (git rev-parse HEAD 2>$null)
$diff = (git diff HEAD 2>$null) -join "`n"
$nuevos = (git ls-files --others --exclude-standard 2>$null)
$contenidoNuevos = ($nuevos | ForEach-Object { "$_ " + (git hash-object -- $_ 2>$null) }) -join "`n"
$arbol = Huella "$cabeza`n$diff`n$contenidoNuevos"

$estado = Join-Path $env:TEMP ("itaca-verificar\stop-" + (Huella $raiz.ToLower()).Substring(0, 10))
New-Item -ItemType Directory -Force -Path $estado | Out-Null
$okArchivo = Join-Path $estado "ultimo-ok.txt"
$intentosArchivo = Join-Path $estado "intentos-$($arbol.Substring(0, 16)).txt"

if ((Test-Path $okArchivo) -and ((Get-Content $okArchivo -Raw).Trim() -eq $arbol)) { exit 0 }

# ¿Hay algo que verificar? Solo documentación = no.
$base = (git merge-base HEAD origin/main 2>$null)
if (-not $base) { $base = "HEAD" }
$cambiados = @()
$cambiados += (git diff --name-only $base 2>$null)
$cambiados += $nuevos
$codigo = $cambiados | Where-Object { $_ -and ($_ -notmatch "\.md$") -and ($_ -notlike "docs/*") }
if (-not $codigo) {
    Set-Content -Path $okArchivo -Value $arbol -Encoding ASCII
    exit 0
}

$ErrorActionPreference = "Continue"
$salida = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $raiz "scripts\verificar.ps1") -Modo STANDARD -Silencioso 2>&1
$rc = $LASTEXITCODE

if ($rc -eq 0) {
    Set-Content -Path $okArchivo -Value $arbol -Encoding ASCII
    Remove-Item -Force -ErrorAction SilentlyContinue $intentosArchivo
    exit 0
}

$intentos = 0
if (Test-Path $intentosArchivo) { $intentos = [int](Get-Content $intentosArchivo -Raw) }
$intentos += 1
Set-Content -Path $intentosArchivo -Value $intentos -Encoding ASCII

$detalle = ($salida | Out-String).Trim()
if ($intentos -ge 3) {
    $aviso = "La verificación STANDARD sigue fallando tras $intentos intentos. Revisa antes de dar la tarea por terminada.`n$detalle"
    @{ systemMessage = $aviso } | ConvertTo-Json -Compress
    exit 0
}

[Console]::Error.WriteLine("No des la tarea por terminada: scripts/verificar.ps1 STANDARD falló (intento $intentos de 3).")
[Console]::Error.WriteLine($detalle)
[Console]::Error.WriteLine("Arregla lo que falla o, si no corresponde a esta tarea, explícalo a la persona en tu respuesta.")
exit 2
