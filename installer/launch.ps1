# Asterism launcher - THE door (Asterism.exe runs this hidden). One
# routing decision, fast:
#   console already up            -> open it
#   engine installed and healthy  -> start the console, open it
#   anything missing              -> open the SETUP page (it detects
#                                    what's needed and offers the one
#                                    button; when done it hands back
#                                    to the console)
# Safe to run twice - an existing serve is reused, not duplicated.
# -NoBrowser: a page is already polling; just bring things up.
param([switch]$NoBrowser)
$ErrorActionPreference = 'SilentlyContinue'
$Root = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'setup-lib.ps1')

function Open-Setup {
    # idempotent: setup-server exits at bind time if 8641 is taken
    Start-Process -FilePath 'powershell' -WindowStyle Hidden -ArgumentList `
        ('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' +
         (Join-Path $PSScriptRoot 'setup-server.ps1') + '" 8641')
    if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:8641/' }
}

$up = Get-NetTCPConnection -LocalPort 8642 -State Listen -ErrorAction SilentlyContinue
if (-not $up) {
    # FAST readiness check before any waiting: on a machine where the
    # engine was never installed, the old flow stalled 30s on a port
    # that could never bind before pivoting to setup
    $py = Resolve-Py
    if (-not $py -or -not (Test-Engine $py) -or
        -not (Test-Path (Join-Path $Root 'web\dist\index.html'))) {
        Open-Setup
        return
    }
    # `-m Tooling.core.cli serve` (the canonical invocation), NOT
    # inline `-c` code - Start-Process word-splits the quoted code
    $tag = Get-PyTag
    if (-not $tag) { Open-Setup; return }
    Start-Process -FilePath $py -ArgumentList @($tag, '-m', 'Tooling.core.cli', 'serve') `
        -WorkingDirectory $Root -WindowStyle Hidden
    # wait for the port (fresh start takes a few seconds)
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Milliseconds 500
        $up = Get-NetTCPConnection -LocalPort 8642 -State Listen -ErrorAction SilentlyContinue
        if ($up) { break }
    }
}
if (-not $up) {
    # the engine looked healthy but the console still failed - the
    # setup page is the diagnosis-and-repair surface either way
    Open-Setup
    return
}
if (-not $NoBrowser) {
    Start-Process 'http://127.0.0.1:8642'
}
