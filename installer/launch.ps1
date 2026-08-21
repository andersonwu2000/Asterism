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

# First run after an unzip: the shipped yaml is a TEMPLATE
# (Asterism.yaml.default) so an update never clobbers the user's own
# settings; materialize it once, only when no real file exists yet.
$yamlDefault = Join-Path $Root 'Asterism.yaml.default'
$yamlReal = Join-Path $Root 'Asterism.yaml'
if ((Test-Path $yamlDefault) -and -not (Test-Path $yamlReal)) {
    Copy-Item $yamlDefault $yamlReal
}

function Open-Setup {
    # idempotent: setup-server exits at bind time if 8641 is taken
    Start-Process -FilePath 'powershell' -WindowStyle Hidden -ArgumentList `
        ('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' +
         (Join-Path $PSScriptRoot 'setup-server.ps1') + '" 8641')
    if (-not $NoBrowser) { Open-Url 'http://127.0.0.1:8641/' }
}

$up = Get-NetTCPConnection -LocalPort 8642 -State Listen -ErrorAction SilentlyContinue

# Update recycle: a console that predates the files on disk must be
# replaced, not reused - web\dist is read from disk per request, so a
# stale serve under a fresh unzip serves NEW pages against OLD
# endpoints. The engine is untouched (it reloads code by its own skew
# handoff) and the gateway keeps its warm toolchain. If anything here
# fails, fall through and open the console - its own banner names the
# mismatch and the way out.
if ($up) {
    $disk = Get-AsterismVersion $Root
    if ($disk) {
        try {
            $meta = Invoke-RestMethod -Uri 'http://127.0.0.1:8642/api/meta' -TimeoutSec 5
            if ($meta.version -ne $disk) {
                try {
                    Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8642/api/shutdown' `
                        -Body '{"console_only": true}' -ContentType 'application/json' `
                        -TimeoutSec 10 | Out-Null
                } catch {}
                for ($i = 0; $i -lt 20; $i++) {
                    Start-Sleep -Milliseconds 500
                    $up = Get-NetTCPConnection -LocalPort 8642 -State Listen -ErrorAction SilentlyContinue
                    if (-not $up) { break }
                }
            }
        } catch {}
    }
}

if (-not $up) {
    # FAST readiness check before any waiting: on a machine where the
    # engine was never installed, the old flow stalled 30s on a port
    # that could never bind before pivoting to setup
    $c = Get-PyCmd
    if (-not $c -or -not (Test-Engine) -or
        -not (Test-Path (Join-Path $Root 'web\dist\index.html'))) {
        Open-Setup
        return
    }
    # `-m Tooling.core.cli serve` (the canonical invocation), NOT
    # inline `-c` code - Start-Process word-splits the quoted code
    Start-Process -FilePath $c.exe -ArgumentList (Py-Args $c @('-m', 'Tooling.core.cli', 'serve')) `
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
    Open-Url 'http://127.0.0.1:8642'
}
