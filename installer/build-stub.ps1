# Rebuild the two repo-root stubs - "Setup Asterism.exe" (first run)
# and "Asterism.exe" (the everyday door) - from their .cs sources,
# using the C# compiler that ships with every Windows (.NET Framework
# 4.x): no SDK, no packages. Both carry installer\asterism.ico (the
# favicon's three-star plate), which the Desktop shortcut inherits.
# Run whenever a stub source or the icon changes; the built exes are
# committed so users never build anything.
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$root = Split-Path -Parent $here
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path $csc)) {
    $csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe'
}
if (-not (Test-Path $csc)) { throw 'csc.exe not found (.NET Framework 4.x missing?)' }
$icon = Join-Path $here 'asterism.ico'
$iconArg = if (Test-Path $icon) { "/win32icon:$icon" } else { '/nologo' }
foreach ($stub in @(
    @{ src = 'SetupAsterism.cs';   out = 'Setup Asterism.exe' },
    @{ src = 'AsterismLauncher.cs'; out = 'Asterism.exe' }
)) {
    $out = Join-Path $root $stub.out
    & $csc /nologo /target:winexe $iconArg /out:"$out" /r:System.Windows.Forms.dll (Join-Path $here $stub.src)
    if ($LASTEXITCODE -ne 0) { throw ('csc failed for ' + $stub.src) }
    Write-Host ("built: " + $out)
}
