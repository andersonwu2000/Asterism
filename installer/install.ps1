# Asterism installer (Windows) - run via install.bat (double-click).
#
# Audience: someone who has never opened a terminal. Every step is
# idempotent (re-running skips what's already done), progress is
# narrated in plain words, and the long step (the Lean math library
# download) announces itself honestly. When it finishes there is an
# "Asterism" shortcut on the Desktop: double-click = engine console
# in the browser.
#
# PowerShell 5.1 compatible (no &&, no ternary).

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot   # repo root (this file lives in installer\)
$Total = 7

function Step($n, $msg) {
    Write-Host ''
    Write-Host ("[$n/$Total] " + $msg) -ForegroundColor Cyan
}
function Ok($msg)   { Write-Host ('   OK   ' + $msg) -ForegroundColor Green }
function Note($msg) { Write-Host ('        ' + $msg) -ForegroundColor DarkGray }
function Warn($msg) { Write-Host ('   !!   ' + $msg) -ForegroundColor Yellow }

function Refresh-Path {
    # a tool installed a second ago isn't on THIS session's PATH yet
    $m = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $u = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = $m + ';' + $u
    # elan installs to ~\.elan\bin without always touching PATH broadly
    $elan = Join-Path $env:USERPROFILE '.elan\bin'
    if (Test-Path $elan) { $env:Path = $env:Path + ';' + $elan }
}

Write-Host ''
Write-Host '  Asterism installer' -ForegroundColor White
Write-Host ("  installing into: " + $Root) -ForegroundColor DarkGray
Write-Host '  Safe to re-run at any time - finished steps are skipped.' -ForegroundColor DarkGray

# ---------------------------------------------------------------- 1/7
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

# ---------------------------------------------------------------- 2/7
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

# ---------------------------------------------------------------- 3/7
Step 3 'The Asterism engine (Python packages)...'
& py -3.12 -m pip install -e $Root --quiet --disable-pip-version-check
Ok 'engine installed'

# ---------------------------------------------------------------- 4/7
Step 4 'The web interface...'
$dist = Join-Path $Root 'web\dist\index.html'
if (Test-Path $dist) {
    Ok 'a built interface is already present'
} else {
    $haveNode = Get-Command node -ErrorAction SilentlyContinue
    if (-not $haveNode) {
        Note 'Installing Node.js (needed once, to build the interface)...'
        winget install -e --id OpenJS.NodeJS.LTS --silent --accept-package-agreements --accept-source-agreements
        Refresh-Path
    }
    Note 'Building the interface (a minute or two)...'
    Push-Location (Join-Path $Root 'web')
    try {
        & npm ci --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw 'npm ci failed' }
        & npm run build
        if ($LASTEXITCODE -ne 0) { throw 'npm run build failed' }
    } finally { Pop-Location }
    Ok 'interface built'
}

# ---------------------------------------------------------------- 5/7
Step 5 'The Lean theorem prover...'
Refresh-Path
$haveLake = Get-Command lake -ErrorAction SilentlyContinue
if ($haveLake) {
    Ok 'Lean toolchain already installed'
} else {
    Note 'Installing elan (the Lean toolchain manager)...'
    $tmp = Join-Path $env:TEMP 'elan-init.ps1'
    Invoke-WebRequest -UseBasicParsing 'https://elan.lean-lang.org/elan-init.ps1' -OutFile $tmp
    try {
        & powershell -NoProfile -ExecutionPolicy Bypass -File $tmp -y
    } catch {
        # older elan-init has no -y; run interactive as fallback
        & powershell -NoProfile -ExecutionPolicy Bypass -File $tmp
    }
    Refresh-Path
    Ok 'Lean toolchain installed'
}
Note 'Fetching the prebuilt math library (Mathlib). FIRST TIME THIS IS'
Note 'SEVERAL GIGABYTES and can take a while - leave the window open.'
Note '(Re-runs are quick: it only downloads what is missing.)'
Push-Location $Root
try {
    & lake exe cache get
    if ($LASTEXITCODE -ne 0) { throw 'lake exe cache get failed' }
} finally { Pop-Location }
Ok 'math library ready'

# ---------------------------------------------------------------- 6/7
Step 6 'Claude Code (the AI that writes the proofs)...'
Refresh-Path
$haveClaude = Get-Command claude -ErrorAction SilentlyContinue
if (-not $haveClaude) {
    $haveNpm = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $haveNpm) {
        # step 4 skips Node when a built interface ships with the folder
        Note 'Installing Node.js (needed for Claude Code)...'
        winget install -e --id OpenJS.NodeJS.LTS --silent --accept-package-agreements --accept-source-agreements
        Refresh-Path
    }
    Note 'Installing Claude Code...'
    & npm install -g '@anthropic-ai/claude-code'
    if ($LASTEXITCODE -ne 0) { throw 'npm install -g @anthropic-ai/claude-code failed' }
    Refresh-Path
}
$creds = Join-Path $env:USERPROFILE '.claude\.credentials.json'
if (Test-Path $creds) {
    Ok 'Claude Code is installed and logged in'
} else {
    Warn 'Claude Code needs a one-time login with your Claude subscription.'
    Note 'A new window will open. Follow the login prompts there'
    Note '(it opens your browser). When it says you are logged in,'
    Note 'close that window and come back here.'
    Read-Host '        Press Enter to open the login window'
    Start-Process -FilePath 'cmd' -ArgumentList '/k', 'claude'
    Read-Host '        Press Enter here AFTER you finished logging in'
    if (Test-Path $creds) {
        Ok 'logged in'
    } else {
        Warn 'still not logged in - you can finish this later; runs will fail until then'
    }
}

# ---------------------------------------------------------------- 7/7
Step 7 'Desktop shortcut...'
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
Write-Host '  All set. Launching Asterism...' -ForegroundColor White
Write-Host '  (Next time: just double-click the Asterism shortcut on your Desktop.)' -ForegroundColor DarkGray
& wscript.exe (Join-Path $Root 'installer\launch.vbs')
