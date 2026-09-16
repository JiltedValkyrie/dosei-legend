param([int]$Seconds = 95)
$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$workspace = Split-Path -Parent (Split-Path -Parent $project)
$testDir = Join-Path $project 'build/emulator-audio-test'
New-Item -ItemType Directory -Force -Path $testDir | Out-Null
$emulator = Join-Path $workspace 'Kronos/build_kronos/src/port/qt/kronos.exe'
Copy-Item -LiteralPath $emulator -Destination (Join-Path $testDir 'kronos.exe')
$localPath = $testDir.Replace('\', '/')
$config = Get-Content -LiteralPath (Join-Path (Split-Path -Parent $emulator) 'kronos.ini') -Raw
$config = $config -replace '(?m)^Memory\\Path=.*$', "Memory\Path=$localPath/bkram.bin"
$config = $config -replace '(?m)^General\\SaveStates=.*$', "General\SaveStates=$localPath"
$config | Set-Content -LiteralPath (Join-Path $testDir 'kronos.ini') -Encoding ASCII
@"
drivers=wave
frequency=44100
channels=stereo
sample-type=int16
[wave]
file=$localPath/capture.wav
"@ | Set-Content -LiteralPath (Join-Path $testDir 'alsoft.ini') -Encoding ASCII
$env:ALSOFT_CONF = Join-Path $testDir 'alsoft.ini'
$env:ALSOFT_DRIVERS = 'wave'
$env:ALSOFT_LOGLEVEL = '3'
$env:ALSOFT_LOGFILE = Join-Path $testDir 'openal.log'
$env:PATH = 'C:\msys64\mingw64\bin;' + $env:PATH
$bios = Join-Path $workspace 'bios/Sega Saturn BIOS (E) (1.00)/Sega Saturn BIOS (E) (1.00).bin'
$disc = Join-Path $project 'title-screen.cue'
$arguments = '-b "' + $bios + '" -i "' + $disc + '" -a'
$process = Start-Process -FilePath (Join-Path $testDir 'kronos.exe') -ArgumentList $arguments -WorkingDirectory $testDir -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $testDir 'stdout.log') -RedirectStandardError (Join-Path $testDir 'stderr.log')
Write-Output "Capture process: $($process.Id)"
try {
    for ($elapsed = 0; $elapsed -lt $Seconds; $elapsed += 5) {
        Start-Sleep -Seconds 5
        if ($process.HasExited) { throw "Kronos exited with code $($process.ExitCode)" }
    }
} finally {
    if (!$process.HasExited) {
        $null = $process.CloseMainWindow()
        if (!$process.WaitForExit(5000)) { Stop-Process -Id $process.Id }
    }
}
Get-Item -LiteralPath (Join-Path $testDir 'capture.wav') | Select-Object FullName, Length
