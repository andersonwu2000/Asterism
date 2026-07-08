# Shared setup library — detection + environment helpers, dot-sourced by
# both the setup server (for /status) and the orchestrator (to skip what
# is already installed). This is the PowerShell port of the knowledge in
# Tooling/serve/setup.py; the engine is now just one install target, not
# the thing that hosts setup. ASCII only, PowerShell 5.1 compatible.

# ---- environment plumbing -------------------------------------------

function Refresh-Path {
    # a just-installed tool's PATH edit only reaches NEW sessions; pull
    # the machine+user PATH into THIS process so the next step finds it
    $m = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $u = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = $m + ';' + $u
}

function Persist-UserEnv($name, $value) {
    # SetEnvironmentVariable, NOT setx — setx truncates PATH at 1024
    try { [Environment]::SetEnvironmentVariable($name, $value, 'User') } catch {}
}

function Prepend-UserPath($directory) {
    # add a dir to the persistent user PATH (idempotent) AND to this
    # process, so both this run and future sessions see the tool
    $cur = [Environment]::GetEnvironmentVariable('Path', 'User')
    if (-not $cur) { $cur = '' }
    $parts = $cur -split ';' | Where-Object { $_ -ne '' }
    if ($parts -notcontains $directory) {
        Persist-UserEnv 'Path' (($directory + ';' + $cur).TrimEnd(';'))
    }
    if (($env:Path -split ';') -notcontains $directory) {
        $env:Path = $directory + ';' + $env:Path
    }
}

# ---- Python + engine -------------------------------------------------

function Resolve-Py {
    $c = Get-Command py -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    foreach ($p in @((Join-Path $env:LOCALAPPDATA 'Programs\Python\Launcher\py.exe'),
                     'C:\Windows\py.exe')) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

function Get-PyVersion {
    Refresh-Path
    $p = Resolve-Py
    if (-not $p) { return $null }
    try { $v = & $p -3.12 -V 2>$null; if ($v) { return "$v".Trim() } } catch {}
    return $null
}

function Test-Engine($py) {
    # engine "ready" = the package imports AND its web deps are present.
    # Critical: -P (Python 3.11+) stops Python prepending the cwd/script
    # dir to sys.path, so this detects a real *install* - not the Tooling/
    # source directory the setup happens to run from. Plain `import
    # Tooling` was true from the very first second (before pip ran),
    # which made the engine step self-skip and serve start with no deps.
    if (-not $py) { return $false }
    $prev = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { $null = & $py -3.12 -P -c 'import Tooling, fastapi, uvicorn' 2>$null; return ($LASTEXITCODE -eq 0) }
    catch { return $false } finally { $ErrorActionPreference = $prev }
}

# ---- Lean toolchain --------------------------------------------------

function Resolve-Lake {
    Refresh-Path
    $c = Get-Command lake -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    $elan = if ($env:ELAN_HOME) { $env:ELAN_HOME } else { Join-Path $env:USERPROFILE '.elan' }
    $p = Join-Path $elan 'bin\lake.exe'
    if (Test-Path $p) { return $p }
    return $null
}

function Get-LakeStatus {
    $lake = Resolve-Lake
    if (-not $lake) { return @{ found = $false; path = $null; version = $null } }
    $v = $null
    $prev = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { $v = (& $lake --version 2>$null | Select-Object -First 1) } catch {}
    $ErrorActionPreference = $prev
    return @{ found = [bool]$v; path = $lake; version = ("$v".Trim()) }
}

function Get-MathlibStatus($workspace) {
    # present = an olean cache actually landed AND the engine's own Lean
    # server binary is built (the contract suite refuses to start
    # without it; a fresh checkout has the package dir but empty build)
    $buildLib = Join-Path $workspace '.lake\packages\mathlib\.lake\build\lib'
    $olean = $false
    if (Test-Path $buildLib) {
        $olean = [bool](Get-ChildItem $buildLib -Recurse -Filter *.olean -ErrorAction SilentlyContinue | Select-Object -First 1)
    }
    $server = Join-Path $workspace '.lake\build\bin\lean-asterism-server.exe'
    return @{ present = ($olean -and (Test-Path $server)) }
}

# ---- Claude Code -----------------------------------------------------

function Resolve-Claude {
    Refresh-Path
    $c = Get-Command claude -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    $cands = @(Join-Path $env:USERPROFILE '.local\bin\claude.exe')
    if ($env:APPDATA) { $cands += (Join-Path $env:APPDATA 'npm\claude.cmd') }
    foreach ($p in $cands) { if (Test-Path $p) { return $p } }
    return $null
}

function Get-ClaudeStatus {
    $exe = Resolve-Claude
    $creds = Join-Path $env:USERPROFILE '.claude\.credentials.json'
    return @{ installed = [bool]$exe; logged_in = (Test-Path $creds); exe = $exe }
}

# ---- Git -------------------------------------------------------------

function Test-Git {
    Refresh-Path
    return [bool](Get-Command git -ErrorAction SilentlyContinue)
}

# ---- the whole picture ----------------------------------------------

function Get-SetupStatus($workspace) {
    $py = Get-PyVersion
    $lake = Get-LakeStatus
    $claude = Get-ClaudeStatus
    return @{
        repo        = $workspace
        python      = @{ found = [bool]$py; version = $py }
        engine      = @{ present = (Test-Engine (Resolve-Py)) }
        git         = @{ found = (Test-Git) }
        lean        = @{ found = $lake.found; path = $lake.path; version = $lake.version }
        mathlib     = Get-MathlibStatus $workspace
        claude      = @{ installed = $claude.installed; logged_in = $claude.logged_in }
        elan_home   = $(if ($env:ELAN_HOME) { $env:ELAN_HOME } else { Join-Path $env:USERPROFILE '.elan' })
    }
}
