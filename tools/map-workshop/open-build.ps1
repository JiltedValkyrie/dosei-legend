param([switch]$TestOnly)
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[Windows.Forms.Application]::EnableVisualStyles()
. (Join-Path $PSScriptRoot '../launcher/build-dialog.ps1')
$mapProject = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$mapOwner = New-Object Windows.Forms.Form
try { $null = Show-BuildDialog -Owner $mapOwner -Project $mapProject -Preselect 'clean' -TestOnly:$TestOnly }
finally { $mapOwner.Dispose() }
