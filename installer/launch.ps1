# Asterism launcher - start the engine console (if it isn't already
# running) and open the browser. Invoked hidden via launch.vbs; safe
# to run twice (an existing serve is reused, not duplicated).
# -NoBrowser: the bootstrap's welcome page is already polling - just
# bring the engine up.
param([switch]$NoBrowser)
$ErrorActionPreference = 'SilentlyContinue'
$Root = Split-Path -Parent $PSScriptRoot

$up = Get-NetTCPConnection -LocalPort 8642 -State Listen -ErrorAction SilentlyContinue
if (-not $up) {
    # console entry point without relying on the pip Scripts dir being
    # on PATH. `-m Tooling.core.cli serve` (the codebase's canonical
    # invocation), NOT inline `-c` code — Start-Process word-splits the
    # quoted code (python saw `-c import` -> SyntaxError; same fix as
    # setup-orchestrator's Start-Serve).
    # resolve the py launcher: a shortcut-spawned session may not have
    # it on PATH yet (per-user install PATH edits land on next logon)
    $py = 'py'
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        foreach ($p in @((Join-Path $env:LOCALAPPDATA 'Programs\Python\Launcher\py.exe'),
                         'C:\Windows\py.exe')) {
            if (Test-Path $p) { $py = $p; break }
        }
    }
    # engine needs >=3.12, not ==3.12 (a pre-installed 3.13 counts)
    $tag = '-3.12'
    foreach ($t in @('-3.12', '-3.13', '-3.14')) {
        try { if (& $py $t -V 2>$null) { $tag = $t; break } } catch {}
    }
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
    # the console cannot come up (setup never ran, or something broke)
    # - Asterism.exe is the universal door, so open the SETUP page
    # instead of a dead tab; it detects what is missing and offers the
    # one button
    Start-Process -FilePath 'powershell' -WindowStyle Hidden -ArgumentList `
        ('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' +
         (Join-Path $PSScriptRoot 'setup-server.ps1') + '" 8641')
    if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:8641/' }
    return
}
if (-not $NoBrowser) {
    Start-Process 'http://127.0.0.1:8642'
}
