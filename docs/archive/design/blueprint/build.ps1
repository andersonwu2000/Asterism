# Build the Asterism Library blueprint. Everything stays under blueprint/.
#
#   powershell -File blueprint/build.ps1          # build the web (HTML + dep graph)
#   powershell -File blueprint/build.ps1 -Serve   # build, then serve at http://localhost:8000
#
# Two Windows-specific fixes are applied (see blueprint/README.md for why):
#   1. PYTHONUTF8=1  — plastex reads the UTF-8 .sty/.tex on a cp950 (zh-TW) locale.
#   2. real graphviz bin ahead of the scoop shim on PATH — the shim breaks the
#      piped stdin/stdout that pygraphviz uses to call dot/tred.
param([switch]$Serve)

# 'Continue' (not 'Stop'): plastex writes normal progress to stderr, which would
# otherwise abort the script. We check the real exit code explicitly below.
$ErrorActionPreference = 'Continue'
$root = $PSScriptRoot                       # ...\blueprint
$src  = Join-Path $root 'src'
$venv = Join-Path $root '.venv\Scripts'

$env:PYTHONUTF8 = '1'

$gvReal = Join-Path $env:USERPROFILE 'scoop\apps\graphviz\current\bin'
if (Test-Path $gvReal) {
    $env:PATH = "$gvReal;$env:PATH"
} elseif (-not (Get-Command dot -ErrorAction SilentlyContinue)) {
    Write-Warning "graphviz 'dot' not found; the dependency-graph step will fail. Try: scoop install graphviz"
}

Push-Location $src
try {
    & (Join-Path $venv 'plastex.exe') -c plastex.cfg web.tex
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($code -ne 0) { Write-Error "plastex failed (exit $code)"; exit $code }
Write-Host "`nBuilt: blueprint/web/index.html  and  blueprint/web/dep_graph_document.html" -ForegroundColor Green

if ($Serve) {
    Push-Location (Join-Path $root 'web')
    try {
        Write-Host "Serving http://localhost:8000/  (Ctrl-C to stop)" -ForegroundColor Cyan
        & (Join-Path $venv 'python.exe') -m http.server 8000
    } finally {
        Pop-Location
    }
}
