# Asterism first-run setup server — a tiny, engine-free local web app
# that detects what's installed, takes the user's few decisions, and
# orchestrates every dependency (Python, engine, Git, Lean, Claude Code,
# Mathlib) with live progress. The engine is just one install target, so
# setup no longer waits on it. Raw TcpListener (no admin, no URL-ACL);
# a single self-contained page + three JSON routes. PS 5.1, ASCII only.
#
#   GET  /          -> setup.html (the wizard UI)
#   GET  /status    -> JSON: what is installed
#   POST /install   -> begin (body = the decisions); spawns the orchestrator
#   GET  /progress  -> JSON: { state, log[] } of the running install

param([int]$Port = 8641)
$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $PSScriptRoot           # repo root
. (Join-Path $PSScriptRoot 'setup-lib.ps1')

$ProgressLog = Join-Path $PSScriptRoot 'setup-progress.log'
$DoneMarker  = Join-Path $PSScriptRoot 'setup-done.marker'
$HtmlPath    = Join-Path $PSScriptRoot 'setup.html'
$script:OrchPid = 0
$OrchPidFile = Join-Path $PSScriptRoot 'setup-orchestrator.pid'

function Orchestrator-Alive {
    # in-memory pid first; else the pid FILE the orchestrator writes -
    # this server may have restarted (2h idle exit with the page
    # closed) while the install is still running, and forgetting that
    # meant a false "failed" + a second orchestrator on retry
    $pid2 = $script:OrchPid
    if (-not $pid2 -and (Test-Path $OrchPidFile)) {
        try { $pid2 = [int](Get-Content $OrchPidFile -Raw).Trim() } catch { $pid2 = 0 }
    }
    if (-not $pid2) { return $false }
    $p = Get-Process -Id $pid2 -ErrorAction SilentlyContinue
    return [bool]($p -and $p.ProcessName -match 'powershell')
}

function Engine-Up {
    $c = New-Object System.Net.Sockets.TcpClient
    try { $c.Connect('127.0.0.1', 8642); return $c.Connected } catch { return $false } finally { $c.Close() }
}

function Read-Request($stream) {
    # read headers up to the blank line, then Content-Length body bytes
    $stream.ReadTimeout = 4000
    $ms = New-Object System.IO.MemoryStream
    $buf = New-Object byte[] 1
    $prev = 0
    $count = 0
    while ($count -lt 65536) {
        $n = 0
        try { $n = $stream.Read($buf, 0, 1) } catch { break }
        if ($n -le 0) { break }
        $ms.WriteByte($buf[0]); $count++
        # stop at the CRLFCRLF that ends the headers
        $arr = $ms.ToArray()
        if ($arr.Length -ge 4 -and $arr[-4] -eq 13 -and $arr[-3] -eq 10 -and $arr[-2] -eq 13 -and $arr[-1] -eq 10) { break }
    }
    $head = [System.Text.Encoding]::ASCII.GetString($ms.ToArray())
    $lines = $head -split "`r`n"
    $reqLine = if ($lines.Count -gt 0) { $lines[0] } else { '' }
    $parts = $reqLine -split ' '
    $method = if ($parts.Count -gt 0) { $parts[0] } else { '' }
    $path = if ($parts.Count -gt 1) { $parts[1] } else { '/' }
    $len = 0
    foreach ($l in $lines) { if ($l -match '^(?i)content-length:\s*(\d+)') { $len = [int]$matches[1] } }
    $body = ''
    if ($len -gt 0) {
        $bb = New-Object byte[] $len
        $got = 0
        while ($got -lt $len) {
            $r = 0
            try { $r = $stream.Read($bb, $got, $len - $got) } catch { break }
            if ($r -le 0) { break }
            $got += $r
        }
        $body = [System.Text.Encoding]::UTF8.GetString($bb, 0, $got)
    }
    return @{ method = $method; path = $path; body = $body }
}

function Send-Response($stream, $status, $contentType, [byte[]]$bytes) {
    $head = "HTTP/1.0 $status`r`n" +
            "Content-Type: $contentType`r`n" +
            "Content-Length: $($bytes.Length)`r`n" +
            "Cache-Control: no-store`r`n" +
            "Connection: close`r`n`r`n"
    $hb = [System.Text.Encoding]::ASCII.GetBytes($head)
    $stream.Write($hb, 0, $hb.Length)
    if ($bytes.Length -gt 0) { $stream.Write($bytes, 0, $bytes.Length) }
    $stream.Flush()
}
function Send-Text($stream, $status, $ct, $text) {
    Send-Response $stream $status $ct ([System.Text.Encoding]::UTF8.GetBytes($text))
}

$listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $Port)
try { $listener.Start() } catch { exit 0 }

# sliding idle deadline: the page polls every second while open, so
# the server lives as long as anyone is watching (a fixed 2h cutoff
# died UNDER a slow Mathlib download and stranded the page mid-install)
$deadline = (Get-Date).AddHours(2)
try {
    while ((Get-Date) -lt $deadline) {
        if (-not $listener.Pending()) { Start-Sleep -Milliseconds 150; continue }
        $deadline = (Get-Date).AddHours(2)
        $client = $listener.AcceptTcpClient()
        try {
            $stream = $client.GetStream()
            $req = Read-Request $stream
            $path = ($req.path -split '\?')[0]

            if ($req.method -eq 'GET' -and $path -eq '/') {
                if (Test-Path $HtmlPath) {
                    Send-Response $stream '200 OK' 'text/html; charset=utf-8' ([System.IO.File]::ReadAllBytes($HtmlPath))
                } else {
                    Send-Text $stream '500 Error' 'text/plain' 'setup.html missing'
                }
            }
            elseif ($req.method -eq 'GET' -and $path -eq '/status') {
                $st = Get-SetupStatus $Root
                $st['engine_up'] = (Engine-Up)
                Send-Text $stream '200 OK' 'application/json' (ConvertTo-Json -Compress -Depth 5 $st)
            }
            elseif ($req.method -eq 'GET' -and $path -eq '/progress') {
                $log = @()
                if (Test-Path $ProgressLog) {
                    try {
                        $fs = New-Object System.IO.FileStream($ProgressLog, 'Open', 'Read', 'ReadWrite')
                        $sr = New-Object System.IO.StreamReader($fs)
                        $txt = $sr.ReadToEnd(); $sr.Close(); $fs.Close()
                        $log = @($txt -split "`n" | ForEach-Object { $_.TrimEnd("`r") } | Where-Object { $_ -ne '' })
                    } catch {}
                }
                $state = if (Test-Path $DoneMarker) { (Get-Content $DoneMarker -Raw).Trim() } else { 'running' }
                # a 'running' state with a DEAD orchestrator (crash, kill,
                # server restarted over a stale log) must not spin the
                # page forever - report it as failed so retry surfaces
                if ($state -eq 'running' -and -not (Orchestrator-Alive)) { $state = 'failed' }
                Send-Text $stream '200 OK' 'application/json' (ConvertTo-Json -Compress @{ state = $state; log = $log })
            }
            elseif ($req.method -eq 'POST' -and $path -eq '/cancel') {
                # explicit intent, not inferred from a closed window: kill
                # the orchestrator TREE, and take the droppings with us -
                # a user who cancels and never returns must not find our
                # leftovers years later (owner). TEMP installers re-download
                # in seconds on resume; a half-pulled toolchain (no lake
                # yet) is garbage; the partial math library stays INSIDE
                # the Asterism folder, where deleting the folder removes it.
                $pid3 = $script:OrchPid
                if (-not $pid3 -and (Test-Path $OrchPidFile)) {
                    try { $pid3 = [int](Get-Content $OrchPidFile -Raw).Trim() } catch { $pid3 = 0 }
                }
                if ($pid3) { try { & taskkill /PID $pid3 /T /F 2>$null | Out-Null } catch {} }
                $script:OrchPid = 0
                Remove-Item $OrchPidFile -Force -ErrorAction SilentlyContinue
                Get-ChildItem (Join-Path $env:TEMP 'python-*-amd64.exe') -ErrorAction SilentlyContinue |
                    Remove-Item -Force -ErrorAction SilentlyContinue
                Remove-Item (Join-Path $env:TEMP 'elan-init.ps1') -Force -ErrorAction SilentlyContinue
                $elan = Join-Path $env:USERPROFILE '.elan'
                if ((Test-Path $elan) -and -not (Test-Path (Join-Path $elan 'bin\lake.exe'))) {
                    Remove-Item $elan -Recurse -Force -ErrorAction SilentlyContinue
                }
                Set-Content $DoneMarker 'cancelled' -Encoding ASCII
                Send-Text $stream '200 OK' 'application/json' '{"cancelled":true}'
            }
            elseif ($req.method -eq 'POST' -and $path -eq '/install') {
                # body = JSON of decisions { lean_mode, elan_home, lake_path }
                if (Orchestrator-Alive) {
                    # a second tab / an impatient retry must not spawn a
                    # SECOND orchestrator over a live one (two concurrent
                    # installers of the same component = the documented
                    # package-in-use collision) - just watch the one running
                    Send-Text $stream '200 OK' 'application/json' '{"started":false,"reason":"already running"}'
                } else {
                    $dec = @{}
                    try { $dec = $req.body | ConvertFrom-Json } catch {}
                    # the check round: a bad answer stops HERE, at the
                    # button, never half an hour into an unattended run
                    $pf = @(Test-Preflight $dec $Root)
                    if ($pf.Count -gt 0) {
                        Send-Text $stream '200 OK' 'application/json' (ConvertTo-Json -Compress @{ started = $false; errors = $pf })
                    } else {
                        Remove-Item $ProgressLog, $DoneMarker -ErrorAction SilentlyContinue
                        $decFile = Join-Path $PSScriptRoot 'setup-decisions.json'
                        Set-Content -Path $decFile -Value $req.body -Encoding UTF8
                        $p = Start-Process -FilePath 'powershell' -PassThru -WindowStyle Hidden -ArgumentList @(
                            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                            (Join-Path $PSScriptRoot 'setup-orchestrator.ps1'), '-DecisionsFile', $decFile)
                        if ($p) { $script:OrchPid = $p.Id }
                        Send-Text $stream '200 OK' 'application/json' '{"started":true}'
                    }
                }
            }
            else {
                Send-Text $stream '404 Not Found' 'text/plain' 'not found'
            }
        } catch {}
        finally { $client.Close() }
    }
} finally {
    try { $listener.Stop() } catch {}
}
