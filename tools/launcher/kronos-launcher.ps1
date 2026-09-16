param(
    [ValidateSet('normal', 'hires')]
    [string]$Variant,
    [switch]$Check,
    [switch]$SmokeTest
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'project-config.ps1')
$project = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$variants = @(
    [pscustomobject]@{ Id='normal'; Name='Dosei Legend - standard (320x240)'; Image='game/build/game.cue'; Batch='game/run-kronos.bat'; Note='Jo Engine game: Link, forest, controls and music.' },
    [pscustomobject]@{ Id='hires'; Name='Dosei Legend - hi-res (320x480i)'; Image='game/build/game-hires.cue'; Batch='game/run-kronos-hires.bat'; Note='Same Jo game, native interlaced vertical-resolution experiment.' }
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
    $paths = Get-ProjectPaths
    $problems = @(Get-PathProblems $paths)
    if ($problems.Count) { throw ($problems -join "`r`n") }
    # Do not silently run two competing performance experiments.
    if (Get-Process -Name kronos -ErrorAction SilentlyContinue) {
        throw 'Kronos is already running. Close it before starting another variant.'
    }
    $oldPath = $env:PATH
    try {
        if ($paths.kronos_dlls) { $env:PATH = $paths.kronos_dlls + ';' + $env:PATH }
        Start-Process -FilePath $paths.kronos -WorkingDirectory (Split-Path $paths.kronos -Parent) -WindowStyle Normal -ArgumentList @('-b', ('"' + $paths.saturn_bios + '"'), '-i', ('"' + (Get-ImagePath $entry) + '"'), '-a') | Out-Null
    } finally { $env:PATH = $oldPath }
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
. (Join-Path $PSScriptRoot 'config-dialog.ps1')
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
$menu = New-Object Windows.Forms.MenuStrip
$configMenu = New-Object Windows.Forms.ToolStripMenuItem('Config')
$pathsItem = $configMenu.DropDownItems.Add('Paths...')
$pathsItem.Add_Click({ Show-ConfigDialog $form })
$guideItem = $configMenu.DropDownItems.Add('Developer setup guide')
$guideItem.Add_Click({ Start-Process (Join-Path $project 'tools/launcher/SETUP.md') })
[void]$menu.Items.Add($configMenu)
$form.MainMenuStrip = $menu
$form.Controls.Add($menu)

$list = New-Object Windows.Forms.ListView
$list.Location = New-Object Drawing.Point(16, 32)
$list.Size = New-Object Drawing.Size(788, 204)
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
    $selected = 'normal'
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
    if ($details.Text -notlike '*game-hires*') { throw 'Selection details missing' }
    Write-Output 'GUI controls and hi-res selection passed; no emulator launched.'
    Show-ConfigDialog $form -TestOnly
    $form.Dispose()
    exit 0
}
[void]$form.ShowDialog()
