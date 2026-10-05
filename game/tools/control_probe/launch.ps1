# Launch the real configured GUI on the human's desktop. In Codex, invoke this
# outside the restricted execution desktop (require_escalated).
$ErrorActionPreference = 'Stop'
$astraRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$astraRun = Join-Path $astraRoot 'game/build/astra-control'
$astraCue = Join-Path $astraRun 'oot-sat/game/build/game.cue'
. (Join-Path $astraRoot 'tools/launcher/project-config.ps1')
$astraPaths = Get-ProjectPaths
if (Get-Process -Name kronos -ErrorAction SilentlyContinue) {
    throw 'Kronos already running. Preserve that session; close the controlled session before relaunching.'
}
foreach ($astraLine in Get-Content -LiteralPath $astraCue) {
    if ($astraLine -match '^FILE "([^"]+)"') {
        if (!(Test-Path -LiteralPath (Join-Path (Split-Path $astraCue) $Matches[1]))) {
            throw "Missing CUE payload: $($Matches[1])"
        }
    }
}
$astraOldPath = $env:PATH
try {
    $env:PATH = $astraPaths.kronos_dlls + ';' + $env:PATH
    $astraProcess = Start-Process -FilePath $astraPaths.kronos -WorkingDirectory (Split-Path $astraPaths.kronos) -WindowStyle Normal -ArgumentList @('-b', ('"' + $astraPaths.saturn_bios + '"'), '-i', ('"' + $astraCue + '"'), '-a') -PassThru
} finally { $env:PATH = $astraOldPath }
@{
    pid = $astraProcess.Id
    exe = $astraPaths.kronos
    exe_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $astraPaths.kronos).Hash.ToLower()
    cue = $astraCue
    iso_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath ([IO.Path]::ChangeExtension($astraCue, '.iso'))).Hash.ToLower()
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $astraRun 'session.json') -Encoding UTF8
$astraProcess | Select-Object Id,ProcessName
