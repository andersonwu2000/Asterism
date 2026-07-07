# Rebuild "Setup Asterism.exe" (repo root) from SetupAsterism.cs using
# the C# compiler that ships with every Windows (.NET Framework 4.x) -
# no SDK, no packages. Run whenever the stub source changes; the built
# exe is committed so users never build anything.
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$root = Split-Path -Parent $here
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path $csc)) {
    $csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe'
}
if (-not (Test-Path $csc)) { throw 'csc.exe not found (.NET Framework 4.x missing?)' }
$out = Join-Path $root 'Setup Asterism.exe'
& $csc /nologo /target:winexe /out:"$out" /r:System.Windows.Forms.dll (Join-Path $here 'SetupAsterism.cs')
if ($LASTEXITCODE -ne 0) { throw 'csc failed' }
Write-Host ("built: " + $out)
