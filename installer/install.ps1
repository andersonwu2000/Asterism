# Asterism bootstrap (Windows).
#
# Two front doors, one script:
#   "Setup Asterism.exe" (repo root)  -> runs this HIDDEN (-FromStub):
#       progress goes to installer\bootstrap.log, failures pop a
#       message box, and the browser welcome page carries the user
#   fallback (AV blocks the exe): right-click this file and choose
#       "Run with PowerShell" - same steps, visible console
#
# Deliberately MINIMAL (owner: browser wizard over a terminal
# narrative): Python, the engine package, a Desktop shortcut, serve.
# The long steps - Lean toolchain, multi-GB math library, Claude Code
# and its login - run in the browser at #/setup with progress bars.
#
# Idempotent: safe to re-run at any time.
# PowerShell 5.1 compatible; ASCII only (a BOM-less .ps1 is read in
# the system ANSI codepage, where multibyte punctuation can swallow
# the following quote - learned the hard way on zh-TW cp950).

param([switch]$FromStub)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot   # repo root (this file lives in installer\)
$Total = 4

# The browser welcome page tails this clean, tagged log through a tiny
# localhost JSONP server (setup-logserver.ps1) so a hidden install
# still shows progress live - a novice watching a silent spinner for
# three minutes assumes it hung.
$ProgressLog = Join-Path $PSScriptRoot 'setup-progress.log'
try { Set-Content -Path $ProgressLog -Value '' -Encoding ASCII } catch {}
function Progress-Line($s) {
    try { Add-Content -Path $ProgressLog -Value $s -Encoding ASCII } catch {}
}

if ($FromStub) {
    # hidden run: the log is the console
    try { Start-Transcript -Path (Join-Path $PSScriptRoot 'bootstrap.log') -Force | Out-Null } catch {}
    # stand up the log tap BEFORE the slow steps so the welcome page
    # has something to show from the first second
    try {
        Start-Process -FilePath 'powershell' -WindowStyle Hidden -ArgumentList @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
            (Join-Path $PSScriptRoot 'setup-logserver.ps1'),
            $ProgressLog, '8641', '8642') | Out-Null
    } catch {}
}

function Step($n, $msg) {
    Write-Host ''
    Write-Host ("[$n/$Total] " + $msg) -ForegroundColor Cyan
    Progress-Line ("[STEP] [$n/$Total] " + $msg)
}
function Ok($msg)   { Write-Host ('   OK   ' + $msg) -ForegroundColor Green; Progress-Line ('[OK] ' + $msg) }
function Note($msg) { Write-Host ('        ' + $msg) -ForegroundColor DarkGray; Progress-Line ('[NOTE] ' + $msg) }
function Warn($msg) { Write-Host ('   !!   ' + $msg) -ForegroundColor Yellow; Progress-Line ('[WARN] ' + $msg) }

function Fail-Visible($msg) {
    # a hidden installer must never fail silently
    Warn $msg
    if ($FromStub) {
        $sh = New-Object -ComObject WScript.Shell
        [void]$sh.Popup(($msg + "`n`nDetails: installer\bootstrap.log" +
            "`nFallback: right-click installer\install.ps1 -> Run with PowerShell"), 0,
            'Asterism setup', 48)
    }
    try { Stop-Transcript | Out-Null } catch {}
    exit 1
}

function Refresh-Path {
    $m = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $u = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = $m + ';' + $u
}

function Resolve-Py {
    # the py launcher may not be on PATH yet in this very session even
    # after a successful install - probe its two canonical homes
    $c = Get-Command py -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    foreach ($p in @((Join-Path $env:LOCALAPPDATA 'Programs\Python\Launcher\py.exe'),
                     'C:\Windows\py.exe')) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

function PyWorks {
    # $null unless `py -3.12 -V` runs; returns the launcher path so the
    # caller can use it. Refreshes PATH first (a just-installed launcher
    # lands there only for new sessions).
    Refresh-Path
    $p = Resolve-Py
    if (-not $p) { return $null }
    try { if (& $p -3.12 -V 2>$null) { return $p } } catch {}
    return $null
}

$PyVer = '3.12.10'

function Install-Python {
    # NOT via winget: winget installs the FULL Python (7+ sub-MSIs), and
    # in a constrained MSI environment (Windows Sandbox, some locked-down
    # machines) each sub-MSI crawls - tcltk alone took 2 min in testing,
    # so the whole thing looks hung for 10+ minutes. Instead, download
    # the official installer and install a MINIMAL Python DIRECTLY: core
    # + pip + launcher, NO Tcl/Tk / docs / tests / headers (Asterism
    # needs none of them). Per-user so a non-elevated double-click needs
    # no UAC. Faster and more predictable on real machines too; winget
    # stays for the browser wizard's Git step.
    $url = 'https://www.python.org/ftp/python/' + $PyVer + '/python-' + $PyVer + '-amd64.exe'
    $exe = Join-Path $env:TEMP ('python-' + $PyVer + '-amd64.exe')

    # reap a stuck installer from a prior attempt FIRST: a half-finished
    # slow install holds the Windows Installer, so a re-run would hit
    # "another installation is in progress" (the close-and-retry trap)
    Get-Process ('python-' + $PyVer + '-amd64') -ErrorAction SilentlyContinue |
        ForEach-Object { try { Stop-Process -Id $_.Id -Force } catch {} }

    if (-not (Test-Path $exe) -or (Get-Item $exe).Length -lt 20MB) {
        Note '  downloading Python...'
        $ProgressPreference = 'SilentlyContinue'
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        try {
            Invoke-WebRequest -Uri $url -OutFile $exe
        } catch {
            Fail-Visible ('Could not download Python from python.org (' +
                $_.Exception.Message + '). Check the internet connection' +
                ' and run the setup again.')
        }
    }

    Note '  installing Python (core + pip, no extras)...'
    $installArgs = @('/quiet', 'InstallAllUsers=0', 'PrependPath=1',
        'Include_launcher=1', 'Include_pip=1',
        'Include_tcltk=0', 'Include_doc=0', 'Include_test=0', 'Include_dev=0')
    $proc = Start-Process -FilePath $exe -ArgumentList $installArgs -PassThru
    $started = Get-Date
    # a real machine finishes in well under a minute; the generous cap is
    # only for pathologically slow virtualized MSI (sandbox ~20x slower)
    $timeoutSec = 900
    while ($true) {
        Start-Sleep -Seconds 5
        $elapsed = [int]((Get-Date) - $started).TotalSeconds
        # the launcher lands before the last sub-MSI - once py works we
        # are done, no need to wait for the process to exit
        if (PyWorks) { Note ('  Python is ready (' + $elapsed + 's)'); return $true }
        if ($proc.HasExited) { break }
        if ($elapsed -ge $timeoutSec) {
            Warn ('  Python installer still running after ' + $timeoutSec +
                's - checking what landed')
            break
        }
        Note ('  installing Python... (' + $elapsed + 's)')
    }
    if ($proc -and -not $proc.HasExited) { try { Stop-Process -Id $proc.Id -Force } catch {} }
    return [bool](PyWorks)
}

try {

Write-Host ''
Write-Host '  Asterism bootstrap' -ForegroundColor White
Write-Host ("  location: " + $Root) -ForegroundColor DarkGray
Write-Host '  Safe to re-run. The rest of the setup continues in your browser.' -ForegroundColor DarkGray

# ---------------------------------------------------------------- 1/4
Step 1 'Checking the Windows package manager (winget)...'
$winget = Get-Command winget -ErrorAction SilentlyContinue
if ($winget) {
    Ok 'winget is available'
} else {
    Start-Process 'ms-windows-store://pdp/?ProductId=9NBLGGH4NNS1'
    Fail-Visible ('winget is missing. Install "App Installer" from the' +
        ' Microsoft Store page that just opened, then run the setup again.')
}

# ---------------------------------------------------------------- 2/4
Step 2 'Python 3.12...'
$Py = Resolve-Py
$havePy = $false
if ($Py) {
    try {
        $v = & $Py -3.12 -V 2>$null
        if ($v) { $havePy = $true }
    } catch {}
}
if ($havePy) {
    Ok ("already installed  (" + $v + ")")
} else {
    Note 'Installing Python 3.12 (this can take a minute or two)...'
    [void](Install-Python)
    $Py = PyWorks
    if (-not $Py) {
        Fail-Visible ('Python did not install - see the log above.' +
            ' Close this window and run the setup again.')
    }
    Ok ('Python 3.12 installed  (' + (& $Py -3.12 -V 2>$null) + ')')
}

# A zombie installer (above) can leave Python WITHOUT pip - the exact
# stall we hit. pip is a stdlib bootstrap away, so complete it here
# rather than failing the engine step for a missing module.
if (-not (& $Py -3.12 -m pip --version 2>$null)) {
    Note 'Completing Python (adding pip)...'
    & $Py -3.12 -m ensurepip --upgrade 2>$null | Out-Null
    if (-not (& $Py -3.12 -m pip --version 2>$null)) {
        Fail-Visible ('Python is present but has no pip and ensurepip' +
            ' could not add it - run the setup again.')
    }
    Ok 'pip ready'
}

# ---------------------------------------------------------------- 3/4
Step 3 'The Asterism engine...'
& $Py -3.12 -m pip install -e $Root --quiet --disable-pip-version-check
if ($LASTEXITCODE -ne 0) {
    # a RUNNING console locks its own asterism.exe (WinError 32) - a
    # re-run over a live install is fine as long as the engine imports
    & $Py -3.12 -c "import Tooling" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Ok 'engine already installed (the running console keeps its file locked)'
    } else {
        Fail-Visible 'pip could not install the engine - see the log above.'
    }
} else {
    Ok 'engine installed'
}
$dist = Join-Path $Root 'web\dist\index.html'
if (-not (Test-Path $dist)) {
    # release zips ship a built interface; a bare dev checkout may not
    $haveNpm = Get-Command npm -ErrorAction SilentlyContinue
    if ($haveNpm) {
        Note 'No built interface found - building it (a minute or two)...'
        Push-Location (Join-Path $Root 'web')
        try {
            & npm ci --no-audit --no-fund
            if ($LASTEXITCODE -ne 0) { throw 'npm ci failed' }
            & npm run build
            if ($LASTEXITCODE -ne 0) { throw 'npm run build failed' }
        } finally { Pop-Location }
        Ok 'interface built'
    } else {
        Fail-Visible ('No built interface and no Node.js - the console' +
            ' cannot render. Use a release zip (ships prebuilt), or' +
            ' install Node.js LTS and run the setup again.')
    }
} else {
    Ok 'interface present'
}

# ---------------------------------------------------------------- 4/4
Step 4 'Desktop shortcut + launch...'
$shell = New-Object -ComObject WScript.Shell
$desktop = $shell.SpecialFolders.Item('Desktop')
$lnk = $shell.CreateShortcut((Join-Path $desktop 'Asterism.lnk'))
$lnk.TargetPath = 'wscript.exe'
$lnk.Arguments = '"' + (Join-Path $Root 'installer\launch.vbs') + '"'
$lnk.WorkingDirectory = $Root
$lnk.Description = 'Asterism - open the proving console'
$lnk.Save()
Ok 'created: Desktop\Asterism'

if ($FromStub) {
    # the welcome page is already open and polling - start the engine
    # console, do NOT open a second tab
    & (Join-Path $PSScriptRoot 'launch.ps1') -NoBrowser
    Ok 'engine console started - the browser page takes it from here'
} else {
    Write-Host ''
    Write-Host '  Opening Asterism - finish the setup in your browser.' -ForegroundColor White
    Write-Host '  (The page will offer to install Lean, fetch the math library,' -ForegroundColor DarkGray
    Write-Host '   and set up Claude Code - each with a progress bar.)' -ForegroundColor DarkGray
    & wscript.exe (Join-Path $Root 'installer\launch.vbs')
}

} catch {
    Fail-Visible ('Setup hit an error: ' + $_.Exception.Message)
}

try { Stop-Transcript | Out-Null } catch {}
