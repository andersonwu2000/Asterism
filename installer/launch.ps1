# Asterism launcher — start the engine console (if it isn't already
# running) and open the browser. Invoked hidden via launch.vbs; safe
# to run twice (an existing serve is reused, not duplicated).
$ErrorActionPreference = 'SilentlyContinue'
$Root = Split-Path -Parent $PSScriptRoot

$up = Get-NetTCPConnection -LocalPort 8642 -State Listen -ErrorAction SilentlyContinue
if (-not $up) {
    # console entry point without relying on the pip Scripts dir being
    # on PATH: import the CLI directly under the py launcher.
    # Start-Process does NOT quote args itself (PS 5.1) — wrap the code
    # or py receives it word-split.
    $code = "import sys; sys.argv=['asterism','serve']; from Tooling.core.cli import main; raise SystemExit(main())"
    Start-Process -FilePath 'py' -ArgumentList @('-3.12', '-c', ('"' + $code + '"')) `
        -WorkingDirectory $Root -WindowStyle Hidden
    # wait for the port (fresh start takes a few seconds)
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Milliseconds 500
        $up = Get-NetTCPConnection -LocalPort 8642 -State Listen -ErrorAction SilentlyContinue
        if ($up) { break }
    }
}
Start-Process 'http://127.0.0.1:8642'
