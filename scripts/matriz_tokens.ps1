# Matriz de aislamiento de tokens de integración (producción). NO destructiva.
#
# Pide los secretos sin mostrarlos en pantalla y solo imprime códigos HTTP.
# Cada alcance se prueba con una llamada inofensiva:
#   Eli      GET  /api/integraciones/psicologo/?telefono=000000000   (no existe → {"ok": false})
#   Tareas   POST /api/integraciones/recordatorios/  {"dry": true, "fecha": "2000-01-01"}  (simulación, sin envíos)
#   Respaldo GET  /api/integraciones/respaldo/?resumen=1             (solo conteos, sin el volcado)
#
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\matriz_tokens.ps1
# Esperado: 200 solo en la diagonal (E-Eli, T-Tareas, B-Respaldo); 403 (o 429) en el resto.
# Con -ConCompartido prueba también el token viejo ITACA_INTEGRACION_TOKEN:
# una vez puestos los tres propios, debe dar 403 en las tres columnas.

param(
    [string]$Base = "https://itaca-conversemos-production.up.railway.app",
    [switch]$ConCompartido
)

function Leer-Secreto($nombre) {
    $s = Read-Host "Pega el token $nombre (no se muestra)" -AsSecureString
    $p = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($p).Trim() }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($p) }
}

function Codigo($metodo, $url, $token, $cuerpo) {
    try {
        $p = @{ Uri = $url; Method = $metodo; UseBasicParsing = $true; TimeoutSec = 60
                   Headers = @{ "X-Integracion-Token" = $token } }
        if ($cuerpo) { $p.Body = $cuerpo; $p.ContentType = "application/json" }
        return [int](Invoke-WebRequest @p).StatusCode
    } catch {
        if ($_.Exception.Response) { return [int]$_.Exception.Response.StatusCode }
        return "ERR"
    }
}

$tokens = [ordered]@{
    "E (Eli)"      = Leer-Secreto "E (ITACA_TOKEN_ELI)"
    "T (Tareas)"   = Leer-Secreto "T (ITACA_TOKEN_TAREAS)"
    "B (Respaldo)" = Leer-Secreto "B (ITACA_TOKEN_RESPALDO)"
}
if ($ConCompartido) { $tokens["Compartido"] = Leer-Secreto "compartido (ITACA_INTEGRACION_TOKEN)" }
$tokens["falso"] = "falso-" + [guid]::NewGuid()

$esperado = @{ "E (Eli)" = "Eli"; "T (Tareas)" = "Tareas"; "B (Respaldo)" = "Respaldo" }
$fallos = 0
"{0,-14} {1,8} {2,8} {3,9}" -f "Token", "Eli", "Tareas", "Respaldo"
foreach ($nombre in $tokens.Keys) {
    $t = $tokens[$nombre]
    $r = [ordered]@{
        "Eli"      = Codigo GET  "$Base/api/integraciones/psicologo/?telefono=000000000" $t $null
        "Tareas"   = Codigo POST "$Base/api/integraciones/recordatorios/" $t '{"dry": true, "fecha": "2000-01-01"}'
        "Respaldo" = Codigo GET  "$Base/api/integraciones/respaldo/?resumen=1" $t $null
    }
    foreach ($col in $r.Keys) {
        $debe = if ($esperado[$nombre] -eq $col) { 200 } else { "403/429" }
        $ok = if ($debe -eq 200) { $r[$col] -eq 200 } else { $r[$col] -in 401, 403, 429 }
        if (-not $ok) { $fallos++ }
    }
    "{0,-14} {1,8} {2,8} {3,9}" -f $nombre, $r["Eli"], $r["Tareas"], $r["Respaldo"]
}
$tokens.Clear()
if ($fallos) { "MATRIZ: FALLA ($fallos celda(s) fuera de lo esperado)"; exit 1 }
"MATRIZ: OK (aislamiento completo)"
