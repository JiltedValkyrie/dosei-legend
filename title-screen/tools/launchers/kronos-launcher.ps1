param(
    [ValidateSet('normal', 'perf', 'early', 'notex', 'wire', 'nocol', 'nomus', 'staged', 'debug')]
    [string]$Variant,
    [switch]$Check,
    [switch]$SmokeTest
)

$ErrorActionPreference = 'Stop'
$project = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$workspace = Split-Path (Split-Path $project -Parent) -Parent
$kronosDir = Join-Path $workspace 'Kronos/build_kronos/src/port/qt'
$bios = Join-Path $workspace 'bios/Sega Saturn BIOS (E) (1.00)/Sega Saturn BIOS (E) (1.00).bin'
$variants = @(
    [pscustomobject]@{ Id='normal'; Name='Normal play'; Image='title-screen.cue'; Note='Normal game: controls, textures and music enabled.' },
    [pscustomobject]@{ Id='perf'; Name='Performance baseline'; Image='build-perf/title-screen.cue'; Note='Fixed-pose benchmark. Staging off; no ablations.' },
    [pscustomobject]@{ Id='early'; Name='Early face culling'; Image='build-perf-early/title-screen.cue'; Note='EXPERIMENT: conservative sphere rejection before the vertex loop. Full textures, no ablations.' },
    [pscustomobject]@{ Id='notex'; Name='No texture resampling'; Image='build-perf-notex/title-screen.cue'; Note='EXPERIMENT ONLY: clipped texture UVs are deliberately incorrect.' },
    [pscustomobject]@{ Id='wire'; Name='Wireframe (no fill)'; Image='build-perf-wire/title-screen.cue'; Note='EXPERIMENT ONLY: polyline outlines, no fill and no textures. Isolates VDP1 fill cost.' },
    [pscustomobject]@{ Id='nocol'; Name='No collision response'; Image='build-perf-nocol/title-screen.cue'; Note='EXPERIMENT ONLY: camera passes through geometry. PERF_BENCH holds a fixed pose, so per-frame collision is already absent there.' },
    [pscustomobject]@{ Id='nomus'; Name='No score advancement'; Image='build-perf-nomus/title-screen.cue'; Note='EXPERIMENT ONLY: music score advancement is disabled.' },
    [pscustomobject]@{ Id='staged'; Name='Texture staging comparison'; Image='build-perf-staged/title-screen.cue'; Note='Optional benchmark with source-tile staging enabled. Requires its own build.' },
    [pscustomobject]@{ Id='debug'; Name='Debug interpreter'; Image='title-screen.cue'; Note='Normal image with isolated debug-core settings. Slower; not a performance baseline.' }
)

function Get-ImagePath($entry) { Join-Path $project $entry.Image }

function Test-Image($entry) {
    $cue = Get-ImagePath $entry
    if (!(Test-Path -LiteralPath $cue -PathType Leaf)) { return 'Missing image' }
    $files = @(Select-String -LiteralPath $cue -Pattern '^\s*FILE\s+"([^"]+)"' | ForEach-Object { $_.Matches[0].Groups[1].Value })
    if (!$files.Count) { return 'No disc data in CUE' }
    foreach ($file in $files) {
        if (!(Test-Path -LiteralPath (Join-Path (Split-Path $cue -Parent) $file) -PathType Leaf)) { return "Missing disc data: $file" }
    }
    return 'Ready'
}

function Start-Variant($entry) {
    $state = Test-Image $entry
    if ($state -ne 'Ready') { throw $state }
    $exe = Join-Path $kronosDir 'kronos.exe'
    foreach ($path in @($exe, $bios)) {
        if (!(Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing dependency: $path" }
    }
    # Do not silently run two competing performance experiments.
    if (Get-Process -Name kronos -ErrorAction SilentlyContinue) {
        throw 'Kronos is already running. Close it before starting another variant.'
    }
    if ($entry.Id -eq 'debug') {
        & (Join-Path $project 'tools/prepare_kronos_debug.ps1') | Out-Null
        $exe = Join-Path $project 'build/kronos-debug-core/kronos.exe'
    }
    $oldPath = $env:PATH
    $oldPlugins = $env:QT_PLUGIN_PATH
    try {
        $env:PATH = "C:\msys64\mingw64\bin;$oldPath"
        if ($entry.Id -eq 'debug') { $env:QT_PLUGIN_PATH = 'C:\msys64\mingw64\share\qt5\plugins' }
        $cue = Get-ImagePath $entry
        # Kronos is the visible interactive application requested by the user.
        Start-Process -FilePath $exe -WorkingDirectory $kronosDir -ArgumentList "-b `"$bios`" -i `"$cue`" -a" | Out-Null
    } finally {
        $env:PATH = $oldPath
        $env:QT_PLUGIN_PATH = $oldPlugins
    }
}

if ($Check) {
    $variants | ForEach-Object {
        [pscustomobject]@{ Variant=$_.Id; State=(Test-Image $_); Image=(Get-ImagePath $_) }
    } | Format-Table -AutoSize | Out-Host
    exit 0
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[Windows.Forms.Application]::EnableVisualStyles()
if ($Variant) {
    try { Start-Variant ($variants | Where-Object Id -eq $Variant) }
    catch { [Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Kronos launcher') | Out-Null; exit 1 }
    exit 0
}

$form = New-Object Windows.Forms.Form
$form.Text = 'Dosei Legend - Kronos variants'
$form.ClientSize = New-Object Drawing.Size(820, 410)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.Font = New-Object Drawing.Font('Segoe UI', 10)

$list = New-Object Windows.Forms.ListView
$list.Location = New-Object Drawing.Point(16, 16)
$list.Size = New-Object Drawing.Size(788, 220)
$list.View = 'Details'
$list.FullRowSelect = $true
$list.MultiSelect = $false
$list.HideSelection = $false
foreach ($column in @(@('Variant', 275), @('Status', 190), @('Image built (local)', 285))) {
    [void]$list.Columns.Add($column[0], $column[1])
}
$form.Controls.Add($list)
$details = New-Object Windows.Forms.Label
$details.Location = New-Object Drawing.Point(16, 248)
$details.Size = New-Object Drawing.Size(788, 90)
$form.Controls.Add($details)
$status = New-Object Windows.Forms.Label
$status.Location = New-Object Drawing.Point(16, 350)
$status.Size = New-Object Drawing.Size(490, 48)
$status.Text = 'Runs existing images only. Close Kronos between comparisons.'
$form.Controls.Add($status)
$refresh = New-Object Windows.Forms.Button
$refresh.Text = 'Refresh'
$refresh.Location = New-Object Drawing.Point(520, 350)
$refresh.Size = New-Object Drawing.Size(110, 36)
$form.Controls.Add($refresh)
$launch = New-Object Windows.Forms.Button
$launch.Text = 'Run selected'
$launch.Location = New-Object Drawing.Point(646, 350)
$launch.Size = New-Object Drawing.Size(158, 36)
$form.Controls.Add($launch)

function Update-Selection {
    $launch.Enabled = $false
    if (!$list.SelectedItems.Count) { return }
    $entry = $list.SelectedItems[0].Tag
    $details.Text = $entry.Note + "`r`n`r`n" + (Get-ImagePath $entry)
    $launch.Enabled = (Test-Image $entry) -eq 'Ready'
}
function Update-List {
    $selected = 'perf'
    if ($list.SelectedItems.Count) { $selected = $list.SelectedItems[0].Tag.Id }
    $list.Items.Clear()
    foreach ($entry in $variants) {
        $item = New-Object Windows.Forms.ListViewItem($entry.Name)
        $item.Tag = $entry
        [void]$item.SubItems.Add((Test-Image $entry))
        $stamp = '-'
        $cue = Get-ImagePath $entry
        if (Test-Path -LiteralPath $cue) { $stamp = (Get-Item -LiteralPath $cue).LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss') }
        [void]$item.SubItems.Add($stamp)
        [void]$list.Items.Add($item)
        if ($entry.Id -eq $selected) { $item.Selected = $true }
    }
    Update-Selection
}
$list.Add_SelectedIndexChanged({ Update-Selection })
$refresh.Add_Click({ Update-List })
$runAction = {
    if (!$list.SelectedItems.Count) { return }
    try {
        $entry = $list.SelectedItems[0].Tag
        Start-Variant $entry
        $status.Text = 'Started: ' + $entry.Name + '. Close Kronos before the next run.'
    } catch { [Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Kronos launcher') | Out-Null }
}
$launch.Add_Click($runAction)
$list.Add_DoubleClick($runAction)
$form.AcceptButton = $launch
$form.Add_Shown({ Update-Selection })
Update-List
if ($SmokeTest) {
    # Construct real controls without showing a window or starting Kronos.
    $null = $form.Handle
    $null = $list.Handle
    $list.Items[1].Selected = $true
    Update-Selection
    if ($list.Items.Count -ne $variants.Count) { throw 'Variant list incomplete' }
    if ($details.Text -notlike '*build-perf*') { throw 'Selection details missing' }
    Write-Output 'GUI controls and baseline selection passed; no emulator launched.'
    $form.Dispose()
    exit 0
}
[void]$form.ShowDialog()
