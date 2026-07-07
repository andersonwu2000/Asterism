# Asterism bootstrap (Windows) - run via install.bat (double-click).
#
# Deliberately MINIMAL (owner: browser wizard over a terminal
# narrative). This script only gets the engine console on screen:
# Python, the engine package, a Desktop shortcut, the browser. The
# long steps - the Lean toolchain, the multi-GB math library, Claude
# Code and its login - run inside the browser at #/setup, with
# progress bars, drive pickers and retries.
#
# Idempotent: safe to re-run at any time.
# PowerShell 5.1 compatible; ASCII only (a BOM-less .ps1 is read in
# the system ANSI codepage, where multibyte punctuation can swallow
# the following quote - learned the hard way on zh-TW cp950).

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot   # repo root (this file lives in installer\)
$Total = 4

function Step($n, $msg) {
    Write-Host ''
    Write-Host ("[$n/$Total] " + $msg) -ForegroundColor Cyan
}
function Ok($msg)   { Write-Host ('   OK   ' + $msg) -ForegroundColor Green }
function Note($msg) { Write-Host ('        ' + $msg) -ForegroundColor DarkGray }
function Warn($msg) { Write-Host ('   !!   ' + $msg) -ForegroundColor Yellow }

function Refresh-Path {
    $m = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $u = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = $m + ';' + $u
}

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
    Warn 'winget is missing. It ships with Windows 10/11 via the "App Installer".'
    Note 'Opening the Microsoft Store page - install "App Installer", then re-run install.bat.'
    Start-Process 'ms-windows-store://pdp/?ProductId=9NBLGGH4NNS1'
    exit 1
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
Ok 'engine installed'
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
        Warn 'no built interface and no Node.js - the console cannot render.'
        Note 'Use a release zip (ships prebuilt), or install Node.js LTS and re-run.'
        exit 1
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

Write-Host ''
Write-Host '  Opening Asterism - finish the setup in your browser.' -ForegroundColor White
Write-Host '  (The page will offer to install Lean, fetch the math library,' -ForegroundColor DarkGray
Write-Host '   and set up Claude Code - each with a progress bar.)' -ForegroundColor DarkGray
& wscript.exe (Join-Path $Root 'installer\launch.vbs')
