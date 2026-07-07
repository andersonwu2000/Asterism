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

if ($FromStub) {
    # hidden run: the log is the console
    try { Start-Transcript -Path (Join-Path $PSScriptRoot 'bootstrap.log') -Force | Out-Null } catch {}
}

function Step($n, $msg) {
    Write-Host ''
    Write-Host ("[$n/$Total] " + $msg) -ForegroundColor Cyan
}
function Ok($msg)   { Write-Host ('   OK   ' + $msg) -ForegroundColor Green }
function Note($msg) { Write-Host ('        ' + $msg) -ForegroundColor DarkGray }
function Warn($msg) { Write-Host ('   !!   ' + $msg) -ForegroundColor Yellow }

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
$havePy = $false
try {
    $v = & py -3.12 -V 2>$null
    if ($v) { $havePy = $true }
} catch {}
if ($havePy) {
    Ok ("already installed  (" + $v + ")")
} else {
    Note 'Installing Python 3.12 (silent)...'
    winget install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    Refresh-Path
    Ok 'Python 3.12 installed'
}

# ---------------------------------------------------------------- 3/4
Step 3 'The Asterism engine...'
& py -3.12 -m pip install -e $Root --quiet --disable-pip-version-check
if ($LASTEXITCODE -ne 0) {
    # a RUNNING console locks its own asterism.exe (WinError 32) - a
    # re-run over a live install is fine as long as the engine imports
    & py -3.12 -c "import Tooling" 2>$null
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
