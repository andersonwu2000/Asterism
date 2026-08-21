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

function Get-PyCmd {
    # a COMMAND, not just a path: @{ exe; tag; ver }. The engine needs
    # ANY Python >=3.12 (pyproject) - the py launcher's, a direct
    # python.exe (PATH, python.org per-user, miniconda/anaconda - a
    # tester's conda Python was invisible to the launcher-only probe),
    # or the folder-local embedded one the wizard drops when no MSI
    # will land on the machine. tag is $null for direct interpreters.
    Refresh-Path
    $l = Resolve-Py
    if ($l) {
        foreach ($tag in @('-3.12', '-3.13', '-3.14')) {
            try { $v = & $l $tag -V 2>$null; if ($v) { return @{ exe = $l; tag = $tag; ver = "$v".Trim() } } } catch {}
        }
    }
    $repo = Split-Path -Parent $PSScriptRoot
    $cands = @((Join-Path $repo '.tools\python\python.exe'))
    $c = Get-Command python -ErrorAction SilentlyContinue
    if ($c) { $cands += $c.Source }
    $cands += (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe')
    $cands += (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe')
    $cands += (Join-Path $env:USERPROFILE 'miniconda3\python.exe')
    $cands += (Join-Path $env:USERPROFILE 'anaconda3\python.exe')
    foreach ($p in $cands) {
        if (-not $p -or -not (Test-Path $p)) { continue }
        try {
            # the Store's WindowsApps python.exe alias prints nothing -
            # the version gate skips it safely
            $v = & $p -V 2>$null
            if ("$v" -match 'Python 3\.(\d+)' -and [int]$matches[1] -ge 12) {
                return @{ exe = $p; tag = $null; ver = "$v".Trim() }
            }
        } catch {}
    }
    return $null
}

function Py-Args([hashtable]$cmd, [string[]]$rest) {
    if ($cmd.tag) { return @($cmd.tag) + $rest }
    return $rest
}

function Get-PyTag {
    $c = Get-PyCmd
    if ($c) { return $c.tag }
    return $null
}

function Get-PyVersion {
    $c = Get-PyCmd
    if ($c) { return $c.ver }
    return $null
}

function Test-Engine($py = $null) {
    # engine "ready" = the package imports AND its web deps are present.
    # Critical: -P (Python 3.11+) stops Python prepending the cwd/script
    # dir to sys.path, so this detects a real *install* - not the Tooling/
    # source directory the setup happens to run from. Plain `import
    # Tooling` was true from the very first second (before pip ran),
    # which made the engine step self-skip and serve start with no deps.
    # ($py param kept for old call sites; resolution is Get-PyCmd's.)
    $c = Get-PyCmd
    if (-not $c) { return $false }
    $prev = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try {
        $args2 = Py-Args $c @('-P', '-c', 'import Tooling, fastapi, uvicorn')
        $null = & $c.exe @args2 2>$null
        return ($LASTEXITCODE -eq 0)
    }
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

# ---- the chosen LLM provider ----------------------------------------
#
# The installer knows NOTHING about any provider: how to install one,
# how it authenticates, and whether that can even be checked are
# declared by the provider itself (Tooling/llm/capabilities.py) and read
# through installer/provider-info.py. A `if $provider -eq 'antigravity'`
# here would be the branch-per-backend that module exists to stop, and
# the place the next one (codex/GPT) gets forgotten — an undeclared
# provider comes back all-'undeclared' and renders as "you set this one
# up yourself" with no code change.
#
# Readable only once Python + the engine land; lane B installs them
# first, and before that the page shows the CHOICE, which is copy.

$script:ProvInfoMemo = @{}

function Get-ProviderInfo($provider, [switch]$Check) {
    # Memoized 5s, not because the answer is stable but because /status
    # is polled every couple of seconds through a whole install and this
    # spawns a Python process. Short enough that the row still moves
    # while the user watches, and the OBSERVATION is never stored beyond
    # it - "installed and authenticated" is measured, never cached, which
    # is the line capabilities.py draws.
    $py = Resolve-Py
    $script = Join-Path $PSScriptRoot 'provider-info.py'
    if (-not $py -or -not (Test-Path $script)) { return $null }
    $key = "$provider/$Check"
    $hit = $script:ProvInfoMemo[$key]
    if ($hit -and ((Get-Date) - $hit.at).TotalSeconds -lt 5) { return $hit.value }
    $args = @($script, $provider)
    if ($Check) { $args += '--check' }
    try {
        $out = & $py @args 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $out) { return $null }
        $val = ($out | ConvertFrom-Json)
        $script:ProvInfoMemo[$key] = @{ at = (Get-Date); value = $val }
        return $val
    } catch { return $null }
}

function Get-ChosenProvider($decisions) {
    if ($decisions -and $decisions.provider) { return $decisions.provider }
    return 'claude'
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

function Get-SetupStatus($workspace, $decisions) {
    $py = Get-PyVersion
    $lake = Get-LakeStatus
    $claude = Get-ClaudeStatus
    # The account half of readiness follows the CHOICE, and every
    # provider is asked the SAME way - giving the default one a private
    # path is how it stops being one option among several.
    $prov = Get-ChosenProvider $decisions
    $pinfo = Get-ProviderInfo $prov -Check
    return @{
        repo        = $workspace
        repo_free_gb = (Get-FreeGB $workspace)
        python      = @{ found = [bool]$py; version = $py }
        engine      = @{ present = (Test-Engine (Resolve-Py)) }
        git         = @{ found = (Test-Git) }
        lean        = @{ found = $lake.found; path = $lake.path; version = $lake.version }
        mathlib     = Get-MathlibStatus $workspace
        claude      = @{ installed = $claude.installed; logged_in = $claude.logged_in }
        provider    = @{
            name      = $prov
            installed = $(if ($pinfo) { [bool]$pinfo.installed } else { $claude.installed })
            # tri-state on purpose: $null = "this provider does not let
            # anyone check", which is NOT the same as "not ready"
            ready     = $(if ($pinfo) { $pinfo.ready } else { $claude.logged_in })
            detail    = $(if ($pinfo) { $pinfo.detail } else { '' })
            identity  = $(if ($pinfo) { $pinfo.identity } else { $null })
            auth_flow = $(if ($pinfo) { $pinfo.auth_flow } else { 'own_oauth' })
        }
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

# ---- opening a URL without assuming an http handler ------------------
# A fresh Windows profile (Windows Sandbox's WDAGUtilityAccount; some
# locked-down machines) has NO app registered for the http protocol:
# shell-executing a URL there pops "you need a new app to open this
# http link" and opens nothing. The association is a registry fact, so
# read it first; when it is absent, drive a browser BINARY directly -
# a plain exe launch needs no protocol registration, and Edge ships
# with every supported Windows. Shell-execute stays the first choice
# because it is the only route that respects the user's own default
# browser.
function Open-Url($url) {
    # Trust the association only when the ProgId actually RESOLVES.
    # Windows Sandbox stamps UserChoice=MSEdgeHTM into the image while
    # shipping no HKCR\MSEdgeHTM class at all (measured 2026-08-22,
    # browser-probe) - a ProgId-is-present check walks straight into
    # the "you need a new app" dialog it was written to avoid.
    $choice = Get-ItemProperty -ErrorAction SilentlyContinue -Path `
        'HKCU:\Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice'
    if ($choice -and $choice.ProgId) {
        $open = (Get-ItemProperty -ErrorAction SilentlyContinue -Path `
            ('Registry::HKEY_CLASSES_ROOT\' + $choice.ProgId + '\shell\open\command')).'(default)'
        if ($open) {
            Start-Process $url
            return
        }
    }
    # interpolated strings, NOT Join-Path: an absent root (there is no
    # ProgramFiles(x86) on 32-bit Windows) must merely fail the
    # Test-Path below, not throw while the list is being built
    $browsers = @(
        "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
        "$env:ProgramFiles\Mozilla Firefox\firefox.exe"
    )
    foreach ($b in $browsers) {
        if ($b -and (Test-Path $b)) {
            Start-Process -FilePath $b -ArgumentList $url
            return
        }
    }
    # nothing found: let Windows say so (its dialog names the problem
    # better than silence would)
    Start-Process $url
}
