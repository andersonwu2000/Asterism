# Asterism setup orchestrator — installs every dependency, driven by the
# decisions the web page collected, streaming progress the server tails.
# This is the PowerShell home of the install knowledge (it grew out of
# Tooling/serve/setup.py). Steps no-op when already satisfied, and truth
# is taken from the WORLD (re-detection), never an installer's exit code.
#
# TWO DOWNLOAD LANES run concurrently: lane A = Lean + Mathlib (the
# multi-GB long pole), lane B = Python + engine + Claude Code + Git. Main
# spawns both, waits, then JOINS on the console step (which needs the
# engine from B and Mathlib from A). Every progress line is tagged with
# its step, so the page attributes interleaved output to the right row
# and can show two rows running at once. PS 5.1, ASCII only.

param([string]$DecisionsFile, [string]$Lane = 'main')

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

# ---- progress log — ONE file, several writers (two lanes + main). A
#      named mutex serializes the appends; every line carries its step
#      ([TAG|Step]) so the page attributes interleaved lanes correctly. -
$script:LogMutex = New-Object System.Threading.Mutex($false, 'AsterismSetupProgress')
$script:CurStep = ''
function Emit($s) {
    try { [void]$script:LogMutex.WaitOne() } catch {}
    try { Add-Content -Path $ProgressLog -Value $s -Encoding UTF8 } catch {}
    finally { try { $script:LogMutex.ReleaseMutex() } catch {} }
}
function Step($name) { $script:CurStep = $name; Emit ("[STEP|" + $name + "] ") }
function Ok($msg)   { Emit ("[OK|" + $script:CurStep + "] " + $msg) }
function Note($msg) { Emit ("[NOTE|" + $script:CurStep + "] " + $msg) }
function Warn($msg) { Emit ("[WARN|" + $script:CurStep + "] " + $msg) }
function Tick($msg) { Emit ("[TICK|" + $script:CurStep + "] " + $msg) }
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

# ---- Python (minimal, direct: core + pip only; python.org's full MSI
#      bundle drags in tcl/tk/docs/tests and its servicing is slow) -----
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
    $tag = Get-PyTag
    if ($tag -and -not (& (Resolve-Py) $tag -m pip --version 2>$null)) {
        Note 'adding pip (ensurepip)...'
        & (Resolve-Py) $tag -m ensurepip --upgrade 2>$null | Out-Null
    }
    return [bool](Get-PyVersion)
}

function Install-Engine($py) {
    Note 'installing the Asterism engine...'
    $tag = Get-PyTag
    if (-not $tag) { return $false }
    Run-Stream $py @($tag, '-m', 'pip', 'install', '-e', $Root, '--quiet', '--disable-pip-version-check') $null | Out-Null
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
        # Minimized, NOT Hidden: the console is the safety net for
        # Claude Code's paste-a-code fallback (browser can't reach the
        # localhost callback) - hidden, that fallback is unreachable
        # and the "a browser tab opened" line becomes a lie
        if ($c.ToLower().EndsWith('.cmd')) {
            Start-Process 'cmd.exe' -ArgumentList @('/c', $c, 'auth', 'login', '--claudeai') -WindowStyle Minimized
        } else {
            Start-Process $c -ArgumentList @('auth', 'login', '--claudeai') -WindowStyle Minimized
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
    $tag = Get-PyTag
    if (-not $tag) { return $false }
    Start-Process -FilePath $py -ArgumentList @($tag, '-m', 'Tooling.core.cli', 'serve') `
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

function Install-Shortcut {
    # the reopen story: after setup the DAILY entry point is this
    # Desktop shortcut (launch.vbs -> launch.ps1 reuses or starts the
    # console) - the exe is only the first-run door. This step vanished
    # when install.ps1 retired; without it there is no way back in
    # after a reboot short of re-running setup.
    try {
        $sh = New-Object -ComObject WScript.Shell
        $desktop = $sh.SpecialFolders.Item('Desktop')
        $lnk = $sh.CreateShortcut((Join-Path $desktop 'Asterism.lnk'))
        $lnk.TargetPath = 'wscript.exe'
        $lnk.Arguments = '"' + (Join-Path $Root 'installer\launch.vbs') + '"'
        $lnk.WorkingDirectory = $Root
        $lnk.Description = 'Asterism - open the proving console'
        $lnk.Save()
        Note 'Desktop shortcut created (the everyday way back in)'
    } catch { Warn ('could not create the Desktop shortcut: ' + $_.Exception.Message) }
}

function Read-Decisions {
    $f = if ($DecisionsFile) { $DecisionsFile } else { Join-Path $PSScriptRoot 'setup-decisions.json' }
    $dec = @{}
    if (Test-Path $f) { try { $dec = Get-Content $f -Raw | ConvertFrom-Json } catch {} }
    return $dec
}

# ---- lane B: Python -> engine -> Claude Code (+login) ---------------
function Lane-B {
    Step 'Python'
    if (Get-PyVersion) { Ok ('already installed  (' + (Get-PyVersion) + ')') }
    elseif (Install-Python) { Ok ('Python installed  (' + (Get-PyVersion) + ')') }
    else { Warn 'Python did not install' }
    $py = Resolve-Py

    if ($py) {
        Step 'Asterism engine'
        if (Test-Engine $py) { Ok 'already installed' }
        elseif (Install-Engine $py) { Ok 'engine installed' }
        else { Warn 'the engine did not install' }
    }

    # Claude last in this lane so its browser login (the one human step)
    # surfaces while the long Mathlib download runs in lane A
    Step 'Claude Code'
    if ((Get-ClaudeStatus).installed) { Ok 'already installed' }
    elseif (Install-Claude) { Ok 'Claude Code installed' }
    else { Warn 'could not install automatically' }
    Repair-ClaudePath
    $cs = Get-ClaudeStatus
    if ($cs.installed -and -not $cs.logged_in) { Spawn-ClaudeLogin }
}

# ---- lane A: Git -> Lean -> Mathlib (the multi-GB long pole) ---------
function Lane-A {
    $dec = Read-Decisions
    $leanMode = if ($dec.lean_mode) { $dec.lean_mode } else { 'install' }
    $elanHome = if ($dec.elan_home) { $dec.elan_home } elseif ($env:ELAN_HOME) { $env:ELAN_HOME } else { Join-Path $env:USERPROFILE '.elan' }
    $lakePath = $dec.lake_path

    # Git FIRST in this lane: `lake exe cache get` clones Mathlib over
    # git, so the math library step fails ("failed to execute 'git'")
    # without it. Only lake needs git, so it rides the Lean lane, not B.
    Step 'Git'
    if (Test-Git) { Ok 'already installed' }
    elseif (Install-Git) { Ok 'Git installed' }
    else { Warn 'Git did not install' }

    Step 'Lean theorem prover'
    if ((Get-LakeStatus).found) {
        Ok ('already installed  (' + (Get-LakeStatus).version + ')')
    } elseif ($leanMode -eq 'existing') {
        if ($lakePath) {
            $dir = if ($lakePath.ToLower().EndsWith('lake.exe')) { Split-Path -Parent $lakePath } else { $lakePath }
            Prepend-UserPath $dir
        }
        if ((Get-LakeStatus).found) { Ok 'using your existing Lean' } else { Warn 'lake not found at the path given' }
    } elseif (Install-Lean $elanHome) {
        Ok 'Lean toolchain installed'
    } else { Warn 'Lean did not install' }

    if ((Get-LakeStatus).found) {
        Step 'Math library (Mathlib)'
        if ((Get-MathlibStatus $Root).present) { Ok 'already present' }
        elseif (Fetch-Mathlib) { Ok 'Math library ready' }
        else { Warn 'the math library did not finish' }
    }
}

# =====================================================================
if ($Lane -eq 'A') { try { Lane-A } catch { Warn ('lane error: ' + $_.Exception.Message) }; return }
if ($Lane -eq 'B') { try { Lane-B } catch { Warn ('lane error: ' + $_.Exception.Message) }; return }

# ---- main: clear, plan, run BOTH lanes concurrently, join on console -
try {
    if (Test-Path $ProgressLog) { Clear-Content $ProgressLog -ErrorAction SilentlyContinue }
    if (Test-Path $DoneMarker) { Remove-Item $DoneMarker -Force -ErrorAction SilentlyContinue }

    # the checklist the page draws up front - names MUST match the Step
    # '...' calls in the lanes (two of these rows run at once)
    Emit ('[PLAN] ' + (@('Python', 'Asterism engine', 'Claude Code', 'Git',
        'Lean theorem prover', 'Math library (Mathlib)', 'Asterism console') -join '|'))

    # spawn the two lanes as hidden children of this script. ArgumentList
    # as ONE string (not an array) so the quoted path survives spaces -
    # array quoting through Start-Process is the trap that broke -c once.
    $common = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    $pB = Start-Process powershell -PassThru -WindowStyle Hidden -ArgumentList "$common -Lane B"
    $pA = Start-Process powershell -PassThru -WindowStyle Hidden -ArgumentList "$common -Lane A"
    if ($pB) { $pB.WaitForExit() }
    if ($pA) { $pA.WaitForExit() }

    # join: the console needs the engine (lane B) AND Mathlib (lane A)
    $py = Resolve-Py
    $engineUp = $false
    if ($py -and (Test-Engine $py)) {
        Step 'Asterism console'
        Install-Shortcut
        if (Start-Serve $py) { $engineUp = $true; Ok 'the console is up' }
        else { Warn 'the console did not come up on port 8642 - see the lines above' }
    }

    # end-to-end truth check (installers can exit 0 after a child dies);
    # each row re-derived from the WORLD, a miss flags its checklist row
    $checks = @(
        @{ row = 'Python';                 ok = [bool](Get-PyVersion) }
        @{ row = 'Asterism engine';        ok = (Test-Engine (Resolve-Py)) }
        @{ row = 'Claude Code';            ok = (Get-ClaudeStatus).installed }
        @{ row = 'Git';                    ok = (Test-Git) }
        @{ row = 'Lean theorem prover';    ok = (Get-LakeStatus).found }
        @{ row = 'Math library (Mathlib)'; ok = ((Get-LakeStatus).found -and (Get-MathlibStatus $Root).present) }
        @{ row = 'Asterism console';       ok = $engineUp }
    )
    $failed = @()
    foreach ($c in $checks) {
        if (-not $c.ok) { $failed += $c.row; $script:CurStep = $c.row; Warn 'not ready - press Set up Asterism again to retry' }
    }

    if ($failed.Count -gt 0) { Set-Content $DoneMarker 'failed' -Encoding ASCII }
    else {
        # success: the downloaded installers have served their purpose
        # (owner: clean up the packages once everything is in) - a
        # retry after failure keeps them for the resume instead
        Remove-Item (Join-Path $env:TEMP ('python-' + $PyVer + '-amd64.exe')) -Force -ErrorAction SilentlyContinue
        Remove-Item (Join-Path $env:TEMP 'elan-init.ps1') -Force -ErrorAction SilentlyContinue
        Set-Content $DoneMarker 'done' -Encoding ASCII
    }
} catch {
    Human ('setup hit an error: ' + $_.Exception.Message)
    Set-Content $DoneMarker 'failed' -Encoding ASCII
}
