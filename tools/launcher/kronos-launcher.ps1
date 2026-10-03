param(
    [ValidateSet('normal', 'hires', 'clean')]
    [string]$Variant,
    [switch]$Check,
    [switch]$SmokeTest
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'project-config.ps1')
$project = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$variants = @(
    [pscustomobject]@{ Id='clean'; Name='Play Dosei Legend (Standard)'; Image='game/build/game-clean.cue'; Batch='game/run-kronos-clean.bat'; Note='Play at 320x240 without the in-game debug overlay.' },
    [pscustomobject]@{ Id='hires'; Name='Play Dosei Legend (320x480i)'; Image='game/build/game-hires.cue'; Batch='game/run-kronos-hires.bat'; Note='Play at 320x480i interlaced resolution.' },
    [pscustomobject]@{ Id='normal'; Name='Debug Mode'; Image='game/build/game.cue'; Batch='game/run-kronos.bat'; Note='320x240 development build with diagnostic overlay.' }
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

# The game requires the 4 MB (32 Mbit) RAM expansion cart and refuses to boot
# without it, so the emulator has to be told to fit one. Kronos keeps this in its
# own ini under the [1.0] group as a flattened "Cartridge\Type" key;
# CART_DRAM32MBIT is 7 (Kronos/yabause/src/sys/memory/include/cs0.h).
# Only that one key is touched. Start-Variant already refuses to run while
# Kronos is open, so there is no live session to clobber the file on exit.
function Set-KronosCartridge {
    $ini = Join-Path $env:LOCALAPPDATA 'kronos/kronos.ini'
    if (!(Test-Path -LiteralPath $ini -PathType Leaf)) {
        Write-Warning "Kronos ini not found at $ini. Set Cartridge/Type to the 32 Mbit DRAM cart by hand, or the game will refuse to boot."
        return
    }
    $lines = @(Get-Content -LiteralPath $ini)
    if ($lines -contains 'Cartridge\Type=7') { return }
    $out = New-Object System.Collections.Generic.List[string]
    $written = $false
    foreach ($line in $lines) {
        if ($line -match '^Cartridge\\Type=') {
            if (!$written) { $out.Add('Cartridge\Type=7'); $written = $true }
            continue
        }
        $out.Add($line)
        # Append to the versioned group the rest of the settings live in.
        if (!$written -and $line -match '^\[1\.0\]\s*$') {
            $out.Add('Cartridge\Type=7'); $written = $true
        }
    }
    if (!$written) { $out.Add('Cartridge\Type=7') }
    Set-Content -LiteralPath $ini -Value $out -Encoding utf8
    Write-Host 'Kronos cartridge set to the 4 MB (32 Mbit) DRAM expansion.'
}

function Start-Variant($entry) {
    $state = Test-Image $entry
    if ($state -ne 'Ready') { throw $state }
    $paths = Get-ProjectPaths
    $problems = @(Get-PathProblems $paths)
    if ($problems.Count) { throw ($problems -join "`r`n") }
    $emu = Get-EmulatorSettings
    if ($emu.emulator -eq 'mednafen') {
        if (Get-Process -Name mednafen -ErrorAction SilentlyContinue) {
            throw 'Mednafen is already running. Close it before starting another variant.'
        }
        # Mednafen has no GUI: the CUE is the last argument. Command-line
        # settings override mednafen.cfg for this run only.
        $medArgs = @('-ss.cart', $emu.cart, '-video.fs', $emu.fullscreen)
        if ($emu.extra_args) { $medArgs += $emu.extra_args }
        $medArgs += ('"' + (Get-ImagePath $entry) + '"')
        Start-Process -FilePath $paths.mednafen -WorkingDirectory (Split-Path $paths.mednafen -Parent) -WindowStyle Normal -ArgumentList $medArgs | Out-Null
        return
    }
    # Do not silently run two competing performance experiments.
    if (Get-Process -Name kronos -ErrorAction SilentlyContinue) {
        throw 'Kronos is already running. Close it before starting another variant.'
    }
    Set-KronosCartridge
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
. (Join-Path $PSScriptRoot 'build-dialog.ps1')
if ($Variant) {
    try { Start-Variant ($variants | Where-Object Id -eq $Variant) }
    catch { [Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Kronos launcher') | Out-Null; exit 1 }
    exit 0
}

$form = New-Object Windows.Forms.Form
$form.Text = 'Dosei Legend - launcher'
$form.ClientSize = New-Object Drawing.Size(980, 410)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.Font = New-Object Drawing.Font('Segoe UI', 10)
$menu = New-Object Windows.Forms.MenuStrip
$configMenu = New-Object Windows.Forms.ToolStripMenuItem('Config')
$pathsItem = $configMenu.DropDownItems.Add('Paths and emulator...')
$pathsItem.Add_Click({ Show-ConfigDialog $form; Update-EmulatorStatus })
$guideItem = $configMenu.DropDownItems.Add('Developer setup guide')
$guideItem.Add_Click({ Start-Process (Join-Path $project 'tools/launcher/SETUP.md') })
[void]$menu.Items.Add($configMenu)
$form.MainMenuStrip = $menu
$form.Controls.Add($menu)

$list = New-Object Windows.Forms.ListView
$list.Location = New-Object Drawing.Point(16, 32)
$list.Size = New-Object Drawing.Size(948, 204)
$list.View = 'Details'
$list.FullRowSelect = $true
$list.MultiSelect = $false
$list.HideSelection = $false
foreach ($column in @(@('Variant', 340), @('Status', 190), @('Image built (local)', 285))) {
    [void]$list.Columns.Add($column[0], $column[1])
}
$form.Controls.Add($list)
$details = New-Object Windows.Forms.Label
$details.Location = New-Object Drawing.Point(16, 248)
$details.Size = New-Object Drawing.Size(948, 90)
$form.Controls.Add($details)
$status = New-Object Windows.Forms.Label
$status.Location = New-Object Drawing.Point(16, 350)
$status.Size = New-Object Drawing.Size(490, 48)
function Update-EmulatorStatus {
    $name = if ((Get-EmulatorSettings).emulator -eq 'mednafen') { 'Mednafen' } else { 'Kronos' }
    $status.Text = "Emulator: $name (Config to change). Rebuild builds the images; Run starts $name."
}
Update-EmulatorStatus
$form.Controls.Add($status)
$refresh = New-Object Windows.Forms.Button
$refresh.Text = 'Refresh'
$refresh.Location = New-Object Drawing.Point(520, 350)
$refresh.Size = New-Object Drawing.Size(110, 36)
$form.Controls.Add($refresh)
$launch = New-Object Windows.Forms.Button
$launch.Text = 'Run selected'
$launch.Location = New-Object Drawing.Point(812, 350)
$launch.Size = New-Object Drawing.Size(158, 36)
$form.Controls.Add($launch)
$rebuild = New-Object Windows.Forms.Button
$rebuild.Text = 'Rebuild...'
$rebuild.Location = New-Object Drawing.Point(646, 350)
$rebuild.Size = New-Object Drawing.Size(158, 36)
$form.Controls.Add($rebuild)

function Update-Selection {
    $launch.Enabled = $false
    if (!$list.SelectedItems.Count) { return }
    $entry = $list.SelectedItems[0].Tag
    $details.Text = $entry.Note + "`r`n`r`n" + (Get-ImagePath $entry)
    $launch.Enabled = (Test-Image $entry) -eq 'Ready'
}
function Update-List {
    $selected = 'clean'
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
        $status.Text = 'Started: ' + $entry.Name + '. Close the emulator before the next run.'
    } catch { [Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Kronos launcher') | Out-Null }
}
$launch.Add_Click($runAction)
$list.Add_DoubleClick($runAction)
$rebuild.Add_Click({
    $preselect = 'clean'
    if ($list.SelectedItems.Count) { $preselect = $list.SelectedItems[0].Tag.Id }
    try {
        $outcome = Show-BuildDialog -Owner $form -Project $project -Preselect $preselect
        # Timestamps and Ready/Missing state change with every build.
        Update-List
        if ($outcome.Failed.Count) {
            $status.Text = 'Build FAILED: ' + ($outcome.Failed -join ', ')
        } elseif ($outcome.Built.Count) {
            $status.Text = 'Built: ' + ($outcome.Built -join ', ') + '. Run one to test it.'
        }
    } catch { [Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Rebuild') | Out-Null }
})
$form.AcceptButton = $launch
$form.Add_Shown({ Update-Selection })
Update-List
if ($SmokeTest) {
    # Construct real controls without showing a window or starting Kronos.
    $null = $form.Handle
    $null = $list.Handle
    $list.Items[0].Selected = $false
    $list.Items[1].Selected = $true
    Update-Selection
    if ($list.Items.Count -ne $variants.Count) { throw 'Variant list incomplete' }
    if ($details.Text -notlike '*game-hires*') { throw 'Selection details missing' }
    $list.Items[1].Selected = $false
    $list.Items[0].Selected = $true
    Update-Selection
    if ($details.Text -notlike '*game-clean.cue*') { throw 'Clean selection details missing' }
    Write-Output 'GUI controls, hi-res and clean selection passed; no emulator launched.'
    Show-ConfigDialog $form -TestOnly
    $null = $rebuild.Handle
    if (!$rebuild.Enabled) { throw 'Rebuild button disabled' }
    $null = Show-BuildDialog -Owner $form -Project $project -Preselect 'clean' -TestOnly
    Write-Output 'Rebuild dialog constructed; no compiler started.'
    $form.Dispose()
    exit 0
}
[void]$form.ShowDialog()
