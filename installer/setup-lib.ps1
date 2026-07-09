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

# The two setup lanes both persist user-env changes (PATH, ELAN_HOME); a
# named mutex serializes those read-modify-writes so a concurrent PATH
# edit can't lost-update the other lane's (SetEnvironmentVariable is a
# plain HKCU write with no locking of its own).
$script:EnvMutex = New-Object System.Threading.Mutex($false, 'AsterismSetupEnv')

function Persist-UserEnv($name, $value) {
    # SetEnvironmentVariable, NOT setx — setx truncates PATH at 1024
    try { [void]$script:EnvMutex.WaitOne() } catch {}
    try { [Environment]::SetEnvironmentVariable($name, $value, 'User') } catch {}
    finally { try { $script:EnvMutex.ReleaseMutex() } catch {} }
}

function Prepend-UserPath($directory) {
    # add a dir to the persistent user PATH (idempotent) AND to this
    # process, so both this run and future sessions see the tool. The
    # persistent read-modify-write is held under the mutex (re-reading
    # PATH inside it) so two lanes can't clobber each other's edit.
    try { [void]$script:EnvMutex.WaitOne() } catch {}
    try {
        $cur = [Environment]::GetEnvironmentVariable('Path', 'User')
        if (-not $cur) { $cur = '' }
        $parts = $cur -split ';' | Where-Object { $_ -ne '' }
        if ($parts -notcontains $directory) {
            [Environment]::SetEnvironmentVariable('Path', (($directory + ';' + $cur).TrimEnd(';')), 'User')
        }
    } catch {} finally { try { $script:EnvMutex.ReleaseMutex() } catch {} }
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

function Get-PyTag {
    # the engine needs >=3.12 (pyproject), not ==3.12: a user who
    # pre-installed 3.13 was told "no Python" and the wizard installed
    # a second one next to it (seen live in a sandbox). Prefer 3.12
    # (the tested floor), accept newer.
    Refresh-Path
    $p = Resolve-Py
    if (-not $p) { return $null }
    foreach ($tag in @('-3.12', '-3.13', '-3.14')) {
        try { $v = & $p $tag -V 2>$null; if ($v) { return $tag } } catch {}
    }
    return $null
}

function Get-PyVersion {
    $p = Resolve-Py
    if (-not $p) { return $null }
    $tag = Get-PyTag
    if (-not $tag) { return $null }
    try { $v = & $p $tag -V 2>$null; if ($v) { return "$v".Trim() } } catch {}
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
    $tag = Get-PyTag
    if (-not $tag) { return $false }
    $prev = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { $null = & $py $tag -P -c 'import Tooling, fastapi, uvicorn' 2>$null; return ($LASTEXITCODE -eq 0) }
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

function Get-FreeGB($path) {
    # free space on the drive a path lives on (the math library lands
    # next to the repo, so the user should see that number up front)
    try {
        $root = [System.IO.Path]::GetPathRoot([System.IO.Path]::GetFullPath($path))
        $d = New-Object System.IO.DriveInfo($root)
        return [math]::Round($d.AvailableFreeSpace / 1GB, 1)
    } catch { return $null }
}

function Get-SetupStatus($workspace) {
    $py = Get-PyVersion
    $lake = Get-LakeStatus
    $claude = Get-ClaudeStatus
    return @{
        repo        = $workspace
        repo_free_gb = (Get-FreeGB $workspace)
        python      = @{ found = [bool]$py; version = $py }
        engine      = @{ present = (Test-Engine (Resolve-Py)) }
        git         = @{ found = (Test-Git) }
        lean        = @{ found = $lake.found; path = $lake.path; version = $lake.version }
        mathlib     = Get-MathlibStatus $workspace
        claude      = @{ installed = $claude.installed; logged_in = $claude.logged_in }
        elan_home   = $(if ($env:ELAN_HOME) { $env:ELAN_HOME } else { Join-Path $env:USERPROFILE '.elan' })
    }
}

function Test-Preflight($decisions, $workspace) {
    # the check round BEFORE anything installs (owner: a bad answer
    # must surface at the button, not half an hour into an unattended
    # run). Returns a list of blocking problems; empty = go.
    $errors = @()
    $lakeStatus = Get-LakeStatus
    if (-not $lakeStatus.found) {
        if ($decisions.lean_mode -eq 'existing') {
            $p = $decisions.lake_path
            if (-not $p) {
                $errors += 'point at your lake.exe (or its folder) first'
            } else {
                $exe = if ($p.ToLower().EndsWith('lake.exe')) { $p } else { Join-Path $p 'lake.exe' }
                if (-not (Test-Path $exe)) {
                    $errors += ('no lake at ' + $exe)
                } else {
                    # validate by RUNNING it (a Job so a hung lake cannot
                    # hang the check; a healthy one answers instantly)
                    $job = Start-Job -ScriptBlock { param($e) & $e --version 2>$null } -ArgumentList $exe
                    $done = Wait-Job $job -Timeout 15
                    $out = if ($done) { Receive-Job $job } else { $null }
                    Remove-Job $job -Force -ErrorAction SilentlyContinue
                    if (-not $out) { $errors += ($exe + ' exists but `lake --version` failed') }
                }
            }
        } else {
            # NOT $home - that is a read-only PowerShell automatic var
            $eh = if ($decisions.elan_home) { $decisions.elan_home } else { Join-Path $env:USERPROFILE '.elan' }
            try {
                $full = [System.IO.Path]::GetFullPath($eh)
                $root = [System.IO.Path]::GetPathRoot($full)
                if (-not (Test-Path $root)) { $errors += ('drive ' + $root + ' does not exist') }
                else {
                    $gb = Get-FreeGB $full
                    if ($gb -ne $null -and $gb -lt 2) { $errors += ('only ' + $gb + ' GB free on ' + $root + ' - the Lean toolchain needs ~1 GB') }
                }
            } catch { $errors += ('not a usable folder path: ' + $eh) }
        }
    }
    if (-not (Get-MathlibStatus $workspace).present) {
        $gb = Get-FreeGB $workspace
        if ($gb -ne $null -and $gb -lt 8) {
            $errors += ('only ' + $gb + ' GB free where Asterism lives - the math library needs ~5 GB; free some space first')
        }
    }
    return $errors
}
