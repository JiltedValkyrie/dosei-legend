param([ValidateSet('normal','hires','clean')][string]$Variant='normal')
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/project-config.ps1"
$paths = Get-ProjectPaths
$bash = Join-Path $paths.msys2 'usr/bin/bash.exe'
if (!(Test-Path -LiteralPath $bash)) { throw 'Configure MSYS2 in the launcher Config menu first.' }
if (!(Test-Path -LiteralPath $paths.python)) { throw 'Configure a Python executable in the launcher Config menu first.' }
$env:DOSEI_PYTHON = $paths.python
$env:PATH = (Join-Path $paths.msys2 'usr/bin') + ';' + (Split-Path $paths.python -Parent) + ';' + $env:PATH
Set-Location (Join-Path $ProjectRoot 'game')
$arguments = @('./build.sh')
if ($Variant -eq 'hires') { $arguments += '--hires' }
if ($Variant -eq 'clean') { $arguments += '--clean' }
& $bash @arguments
exit $LASTEXITCODE
