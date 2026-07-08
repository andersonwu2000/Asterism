# Asterism setup orchestrator — installs every dependency, driven by the
# decisions the web page collected, streaming progress the server tails.
# This is the PowerShell home of the install knowledge that used to live
# in Tooling/serve/setup.py + installer/install.ps1. Steps no-op when
# already satisfied, and truth is taken from the WORLD (re-detection),
# never an installer's exit code. PS 5.1, ASCII only.

param([string]$DecisionsFile)

$ErrorActionPreference = 'Continue'
# Capture child-process output as UTF-8. winget (the Git step), git, pip
# and elan all emit UTF-8; PS 5.1 would otherwise decode their stdout with
# the OEM code page and mangle every Unicode glyph (progress bars, box
# drawing) - which the ASCII progress log then flattened to a flood of '?'.
# The progress page is UTF-8 end to end, so decode + log to match.
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$Root = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'setup-lib.ps1')

$ProgressLog = Join-Path $PSScriptRoot 'setup-progress.log'
$DoneMarker  = Join-Path $PSScriptRoot 'setup-done.marker'
$PyVer = '3.12.10'

# ---- progress log (tags the web page renders) -----------------------
function Emit($s) { try { Add-Content -Path $ProgressLog -Value $s -Encoding UTF8 } catch {} }
function Step($msg) { Emit ("[STEP] " + $msg) }
function Ok($msg)   { Emit ("[OK] " + $msg) }
function Note($msg) { Emit ("[NOTE] " + $msg) }
function Warn($msg) { Emit ("[WARN] " + $msg) }
function Tick($msg) { Emit ("[TICK] " + $msg) }
function Human($msg){ Emit ("[HUMAN] " + $msg) }   # a move only the user can make

function Run-Stream($file, $arguments, $cwd, [switch]$AsTick) {
    # run a command, feeding each output line to the progress log. stderr
    # merged in (native, no OEM mojibake as Python had). ErrorAction
    # Continue so a non-zero exit / stderr line never throws past us.
    # -AsTick: emit each line as a single UPDATING tick instead of piling
    # up thousands of rows (mathlib cache-get, the Lean toolchain pull).
    $prev = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    $oldloc = Get-Location
    try {
        if ($cwd) { Set-Location $cwd }
        & $file @arguments 2>&1 | ForEach-Object {
            $line = "$_".TrimEnd()
            if ($line -ne '') { if ($AsTick) { Tick $line } else { Note ("  " + $line) } }
        }
        return $LASTEXITCODE
    } catch {
        Note ("  " + $_.Exception.Message); return 1
    } finally {
        Set-Location $oldloc; $ErrorActionPreference = $prev
    }
}

# ---- Python (minimal, direct — see installer/install.ps1 rationale) --
function Install-Python {
    Get-Process ('python-' + $PyVer + '-amd64') -ErrorAction SilentlyContinue |
        ForEach-Object { try { Stop-Process -Id $_.Id -Force } catch {} }
    $url = 'https://www.python.org/ftp/python/' + $PyVer + '/python-' + $PyVer + '-amd64.exe'
    $exe = Join-Path $env:TEMP ('python-' + $PyVer + '-amd64.exe')
    if (-not (Test-Path $exe) -or (Get-Item $exe).Length -lt 20MB) {
        Note 'downloading Python...'
        $ProgressPreference = 'SilentlyContinue'
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        try { Invoke-WebRequest -Uri $url -OutFile $exe } catch { Warn ('download failed: ' + $_.Exception.Message); return $false }
    }
    Note 'installing Python (core + pip, no extras)...'
    $proc = Start-Process -FilePath $exe -PassThru -ArgumentList @(
        '/quiet', 'InstallAllUsers=0', 'PrependPath=1', 'Include_launcher=1',
        'Include_pip=1', 'Include_tcltk=0', 'Include_doc=0', 'Include_test=0', 'Include_dev=0')
    $started = Get-Date
    while (-not $proc.HasExited) {
        Start-Sleep -Seconds 5
        $el = [int]((Get-Date) - $started).TotalSeconds
        if ($el -ge 900) { Warn 'Python installer over 900s - checking what landed'; break }
        Tick ('installing Python (' + $el + 's)')
    }
    if ($proc -and -not $proc.HasExited) { try { Stop-Process -Id $proc.Id -Force } catch {} }
    $py = Get-PyVersion
    if (-not $py) { return $false }
    # complete pip if the installer left it out
    if (-not (& (Resolve-Py) -3.12 -m pip --version 2>$null)) {
        Note 'adding pip (ensurepip)...'
        & (Resolve-Py) -3.12 -m ensurepip --upgrade 2>$null | Out-Null
    }
    return [bool](Get-PyVersion)
}

function Install-Engine($py) {
    Note 'installing the Asterism engine...'
    Run-Stream $py @('-3.12', '-m', 'pip', 'install', '-e', $Root, '--quiet', '--disable-pip-version-check') $null | Out-Null
    return (Test-Engine $py)
}

# ---- Claude Code (official installer, npm fallback, PATH repair) -----
function Repair-ClaudePath {
    $c = Resolve-Claude
    if ($c -and -not (Get-Command claude -ErrorAction SilentlyContinue)) {
        Prepend-UserPath (Split-Path -Parent $c)
    }
}
function Install-Claude {
    Note 'installing Claude Code (official installer)...'
    Run-Stream 'powershell' @('-NoProfile', '-Command', 'irm https://claude.ai/install.ps1 | iex') $null | Out-Null
    if ((Get-ClaudeStatus).installed) { Repair-ClaudePath; return $true }
    if (Get-Command npm -ErrorAction SilentlyContinue) {
        Note 'native installer unavailable - trying npm...'
        Run-Stream 'npm' @('install', '-g', '@anthropic-ai/claude-code') $null | Out-Null
        if ((Get-ClaudeStatus).installed) { Repair-ClaudePath; return $true }
    }
    Warn 'could not install Claude Code automatically - see docs.claude.com'
    return $false
}
function Spawn-ClaudeLogin {
    # hand off to Claude Code's own browser OAuth (claude auth login)
    $c = Resolve-Claude
    if (-not $c) { return }
    try {
        if ($c.ToLower().EndsWith('.cmd')) {
            Start-Process 'cmd.exe' -ArgumentList @('/c', $c, 'auth', 'login', '--claudeai') -WindowStyle Hidden
        } else {
            Start-Process $c -ArgumentList @('auth', 'login', '--claudeai') -WindowStyle Hidden
        }
        Human 'A browser tab opened for the Claude login - click Authorize. The rest keeps installing meanwhile.'
    } catch {
        Human 'Run `claude auth login` in a terminal to sign in - the rest keeps installing.'
    }
}

# ---- Git (winget) ----------------------------------------------------
function Install-Git {
    Note 'installing Git (winget)...'
    Run-Stream 'cmd' @('/c', 'winget', 'install', '-e', '--id', 'Git.Git', '--source', 'winget',
        '--silent', '--disable-interactivity', '--accept-package-agreements', '--accept-source-agreements') $null | Out-Null
    foreach ($cand in @('C:\Program Files\Git\cmd', 'C:\Program Files (x86)\Git\cmd')) {
        if ((Test-Path $cand) -and -not (Get-Command git -ErrorAction SilentlyContinue)) { Prepend-UserPath $cand }
    }
    return (Test-Git)
}

# ---- Lean (elan) -----------------------------------------------------
function Install-Lean($elanHome) {
    Note 'downloading elan-init...'
    $tmp = Join-Path $env:TEMP 'elan-init.ps1'
    $ProgressPreference = 'SilentlyContinue'
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    try { Invoke-WebRequest -Uri 'https://elan.lean-lang.org/elan-init.ps1' -OutFile $tmp } catch { Warn 'could not download elan-init'; return $false }
    $env:ELAN_HOME = $elanHome
    Note ('installing the Lean toolchain into ' + $elanHome + ' ...')
    # the official script's flag is -NoPrompt (bool) - pass a real $true
    Run-Stream 'powershell' @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command',
        ("& '" + $tmp + "' -NoPrompt `$true")) $null | Out-Null
    $bin = Join-Path $elanHome 'bin'
    $lake = Join-Path $bin 'lake.exe'
    if (-not (Test-Path $lake)) { Warn 'elan-init finished but no lake landed - see lines above'; return $false }
    Persist-UserEnv 'ELAN_HOME' $elanHome
    Prepend-UserPath $bin
    # elan -NoPrompt only RECORDS the default; the first lake in the repo
    # surprise-downloads the PINNED toolchain (hundreds of MB) - pull it
    # here so later probes meet a ready lake
    Note 'fetching the pinned Lean toolchain (first run only)...'
    Run-Stream $lake @('--version') $Root -AsTick | Out-Null
    return (Get-LakeStatus).found
}

# ---- Mathlib (lake) --------------------------------------------------
function Fetch-Mathlib {
    Note 'fetching the prebuilt math library (several GB on first run)...'
    Run-Stream 'lake' @('exe', 'cache', 'get') $Root -AsTick | Out-Null
    Note "building the engine's Lean server (a few minutes)..."
    Run-Stream 'lake' @('build', 'lean-asterism-server') $Root | Out-Null
    return (Get-MathlibStatus $Root).present
}

# ---- start the app's engine ------------------------------------------
function Start-Serve($py) {
    if (Get-NetTCPConnection -LocalPort 8642 -State Listen -ErrorAction SilentlyContinue) { return $true }
    Note 'starting the Asterism console...'
    # -m, not -c: passing the launch as inline code through Start-Process
    # got split on spaces (python saw `-c import` -> SyntaxError). `-m
    # Tooling.core.cli serve` is the codebase's own canonical invocation.
    # cwd = repo root - serve needs lakefile.lean, Problems/, Library/ and
    # Tooling/prompts/ at runtime.
    Start-Process -FilePath $py -ArgumentList @('-3.12', '-m', 'Tooling.core.cli', 'serve') `
        -WorkingDirectory $Root -WindowStyle Hidden
    # wait for the port to bind so "everything is ready" never fires while
    # the console is still unreachable (the page hands off on engine_up)
    for ($i = 1; $i -le 90; $i++) {
        Start-Sleep -Seconds 1
        if (Get-NetTCPConnection -LocalPort 8642 -State Listen -ErrorAction SilentlyContinue) { return $true }
        if ($i % 3 -eq 0) { Tick ('starting the console (' + $i + 's)') }
    }
    return $false
}

# =====================================================================
try {
    $dec = @{}
    if ($DecisionsFile -and (Test-Path $DecisionsFile)) {
        try { $dec = Get-Content $DecisionsFile -Raw | ConvertFrom-Json } catch {}
    }
    $leanMode = if ($dec.lean_mode) { $dec.lean_mode } else { 'install' }
    $elanHome = if ($dec.elan_home) { $dec.elan_home } elseif ($env:ELAN_HOME) { $env:ELAN_HOME } else { Join-Path $env:USERPROFILE '.elan' }
    $lakePath = $dec.lake_path
    $failures = @()

    # the checklist the page draws up front - names MUST match the
    # Step '...' calls below (the page fills each row's status in as its
    # step runs, so the user sees the whole roadmap and what is left)
    Emit ('[PLAN] ' + (@('Python', 'Asterism engine', 'Claude Code', 'Git',
        'Lean theorem prover', 'Math library (Mathlib)', 'Asterism console') -join '|'))

    # 1. Python
    Step 'Python'
    if (Get-PyVersion) { Ok ('already installed  (' + (Get-PyVersion) + ')') }
    elseif (Install-Python) { Ok ('Python installed  (' + (Get-PyVersion) + ')') }
    else { Warn 'Python did not install'; $failures += 'Python' }
    $py = Resolve-Py

    # 2. Engine
    if ($py) {
        Step 'Asterism engine'
        if (Test-Engine $py) { Ok 'already installed' }
        elseif (Install-Engine $py) { Ok 'engine installed' }
        else { Warn 'the engine did not install'; $failures += 'engine' }
    }

    # 3. Claude Code FIRST among the tools (its login needs the human,
    #    who is still at the keyboard) - then fire the browser login
    Step 'Claude Code'
    if ((Get-ClaudeStatus).installed) { Ok 'already installed' }
    elseif (Install-Claude) { Ok 'Claude Code installed' }
    else { $failures += 'Claude Code' }
    Repair-ClaudePath
    $cs = Get-ClaudeStatus
    if ($cs.installed -and -not $cs.logged_in) { Spawn-ClaudeLogin }

    # 4. Git
    Step 'Git'
    if (Test-Git) { Ok 'already installed' }
    elseif (Install-Git) { Ok 'Git installed' }
    else { Warn 'Git did not install'; $failures += 'Git' }

    # 5. Lean
    Step 'Lean theorem prover'
    if ((Get-LakeStatus).found) {
        Ok ('already installed  (' + (Get-LakeStatus).version + ')')
    } elseif ($leanMode -eq 'existing') {
        if ($lakePath) {
            $dir = if ($lakePath.ToLower().EndsWith('lake.exe')) { Split-Path -Parent $lakePath } else { $lakePath }
            Prepend-UserPath $dir
        }
        if ((Get-LakeStatus).found) { Ok 'using your existing Lean' } else { Warn 'lake not found at the path given'; $failures += 'Lean' }
    } elseif (Install-Lean $elanHome) {
        Ok 'Lean toolchain installed'
    } else { $failures += 'Lean' }

    # 6. Mathlib
    if ((Get-LakeStatus).found) {
        Step 'Math library (Mathlib)'
        if ((Get-MathlibStatus $Root).present) { Ok 'already present' }
        elseif (Fetch-Mathlib) { Ok 'Math library ready' }
        else { Warn 'the math library did not finish'; $failures += 'Mathlib' }
    }

    # 7. bring the console up (and wait for it, so done == reachable)
    $engineUp = $false
    if ($py -and (Test-Engine $py)) {
        Step 'Asterism console'
        if (Start-Serve $py) { $engineUp = $true; Ok 'the console is up' }
        else { Warn 'the console did not come up on port 8642 - see the lines above' }
    }

    # end-to-end truth check (installers can exit 0 after a child dies)
    $missing = @()
    if (-not (Get-PyVersion)) { $missing += 'Python' }
    if (-not (Test-Engine (Resolve-Py))) { $missing += 'engine' }
    if (-not (Get-ClaudeStatus).installed) { $missing += 'Claude Code' }
    if (-not (Test-Git)) { $missing += 'Git' }
    if (-not (Get-LakeStatus).found) { $missing += 'Lean' } elseif (-not (Get-MathlibStatus $Root).present) { $missing += 'Mathlib' }
    if (-not $engineUp) { $missing += 'console' }
    foreach ($m in $missing) { if ($failures -notcontains $m) { $failures += $m } }

    if ($failures.Count -gt 0) {
        Warn ('setup finished with problems: ' + ($failures -join ', ') + ' - press the button again to retry just those')
        Set-Content $DoneMarker 'failed' -Encoding ASCII
    } else {
        Ok 'everything is ready'
        Set-Content $DoneMarker 'done' -Encoding ASCII
    }
} catch {
    Warn ('setup hit an error: ' + $_.Exception.Message)
    Set-Content $DoneMarker 'failed' -Encoding ASCII
}
