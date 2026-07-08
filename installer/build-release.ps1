# Build the release zip - the MINIMAL CLOSURE someone needs to run
# Asterism: unzip, double-click "Setup Asterism.exe", done. Everything
# heavy (Python, Git, Lean, Mathlib, Claude Code) is fetched by the
# bootstrap + browser wizard, so this zip stays a few MB.
#
# What ships: the engine (Tooling/), the built web console (web/dist,
# build it first: cd web; npm run build), the installer, the Lean
# package skeleton (lakefile + Asterism/ server source + toolchain
# pins), pyproject, README.
# What does NOT ship: dev workspace content - Problems/, Library/,
# tests/, docs/, Benchmarks/, demo/, _spike/, .github/. A fresh
# machine grows its own; every consumer of these dirs mkdirs on
# demand (Library glob is declared harmless-when-empty in
# lakefile.lean; regress.py mkdirs Benchmarks).
#
# Output: .asterism\releases\Asterism.zip (+ a -<sha> copy for the
# archive shelf). ASCII only, PowerShell 5.1 compatible.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

$dist = Join-Path $root 'web\dist\index.html'
if (-not (Test-Path $dist)) {
    throw 'web\dist is missing - build the console first: cd web; npm run build'
}

$sha = (& git -C $root rev-parse --short=12 HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'git rev-parse failed' }

$stage = Join-Path $env:TEMP ('asterism-release-' + $sha)
if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
New-Item -ItemType Directory -Force -Path $stage | Out-Null

Write-Host ('[1/4] Exporting tracked files @ ' + $sha + '...')
$archive = Join-Path $env:TEMP ('asterism-archive-' + $sha + '.zip')
& git -C $root archive --format=zip -o $archive HEAD
if ($LASTEXITCODE -ne 0) { throw 'git archive failed' }
Expand-Archive -Path $archive -DestinationPath $stage -Force
Remove-Item $archive

Write-Host '[2/4] Dropping dev-workspace content...'
$exclude = @('Problems', 'Library', 'tests', 'docs', 'Benchmarks',
             'demo', '_spike', '.github')
foreach ($d in $exclude) {
    $p = Join-Path $stage $d
    if (Test-Path $p) { Remove-Item -Recurse -Force $p }
}

Write-Host '[3/4] Adding the built web console...'
Copy-Item -Recurse (Join-Path $root 'web\dist') (Join-Path $stage 'web\dist')

Write-Host '[4/4] Compressing...'
$outDir = Join-Path $root '.asterism\releases'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$out = Join-Path $outDir 'Asterism.zip'
if (Test-Path $out) { Remove-Item $out }
Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $out
Copy-Item $out (Join-Path $outDir ('Asterism-' + $sha + '.zip')) -Force
Remove-Item -Recurse -Force $stage

$mb = [math]::Round((Get-Item $out).Length / 1MB, 2)
Write-Host ''
Write-Host ('built: ' + $out + '  (' + $mb + ' MB, @' + $sha + ')') -ForegroundColor Green
Write-Host 'send this one file; the receiver unzips and double-clicks "Setup Asterism.exe"'
