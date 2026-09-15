$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$workspace = Split-Path -Parent (Split-Path -Parent $project)
$original = Join-Path $workspace 'Kronos/build_kronos/src/port/qt'
$profile = Join-Path $project 'build/kronos-debug-core'
New-Item -ItemType Directory -Force -Path $profile | Out-Null
Copy-Item -LiteralPath (Join-Path $original 'kronos.exe') -Destination (Join-Path $profile 'kronos.exe')
$settings = Get-Content -LiteralPath (Join-Path $original 'kronos.ini') -Raw
if ($settings -notmatch '(?m)^Advanced\\SH2Interpreter=') { throw 'SH2 interpreter setting not found' }
# This build exposes cores 8 and 9. Core 9 fetches/decodes instructions directly
# in its debug execution loop, providing a comparison to core 8's opcode cache.
$settings = $settings -replace '(?m)^Advanced\\SH2Interpreter=.*$', 'Advanced\SH2Interpreter=9'
$localPath = $profile.Replace('\', '/')
$settings = $settings -replace '(?m)^Memory\\Path=.*$', "Memory\Path=$localPath/bkram.bin"
$settings = $settings -replace '(?m)^General\\SaveStates=.*$', "General\SaveStates=$localPath"
$settings | Set-Content -LiteralPath (Join-Path $profile 'kronos.ini') -Encoding UTF8
Write-Output "Prepared isolated debug-interpreter profile: $profile"
