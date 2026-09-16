# Loaded after WinForms and project-config.ps1. No changes until Save is clicked.
function Show-ConfigDialog($Owner, [switch]$TestOnly) {
    $dialog = New-Object Windows.Forms.Form
    $dialog.Text = 'Dosei Legend - local paths'
    $dialog.ClientSize = New-Object Drawing.Size(900, 510)
    $dialog.StartPosition = 'CenterParent'
    $dialog.FormBorderStyle = 'FixedDialog'
    $dialog.MaximizeBox = $false
    $dialog.Font = New-Object Drawing.Font('Segoe UI', 10)
    $fields = @{}
    $values = Get-ProjectPaths
    $specs = @(
        @('jo_engine', 'Jo Engine SDK root', 'folder'),
        @('msys2', 'MSYS2 root', 'folder'),
        @('python', 'Python executable', 'file'),
        @('kronos', 'Kronos executable', 'file'),
        @('kronos_dlls', 'Kronos DLLs (optional)', 'folder'),
        @('saturn_bios', 'Saturn BIOS file', 'file'),
        @('oot_decomp', 'zeldaret/oot checkout', 'folder'),
        @('oot_roms', 'US 1.2 ROM directory', 'folder'))
    $row = 0
    foreach ($spec in $specs) {
        $label = New-Object Windows.Forms.Label
        $label.Text = $spec[1]
        $label.SetBounds(12, (18 + $row * 40), 180, 25)
        $dialog.Controls.Add($label)
        $field = New-Object Windows.Forms.TextBox
        $field.Text = $values[$spec[0]]
        $field.SetBounds(195, (14 + $row * 40), 600, 28)
        $fields[$spec[0]] = $field
        $dialog.Controls.Add($field)
        $button = New-Object Windows.Forms.Button
        $button.Text = 'Browse'
        $button.SetBounds(802, (12 + $row * 40), 85, 30)
        $button.Tag = @($field, $spec[2])
        $button.Add_Click({
            $target = $this.Tag[0]
            if ($this.Tag[1] -eq 'folder') {
                $picker = New-Object Windows.Forms.FolderBrowserDialog
                if (Test-Path -LiteralPath $target.Text -PathType Container) { $picker.SelectedPath = $target.Text }
                if ($picker.ShowDialog() -eq 'OK') { $target.Text = $picker.SelectedPath }
            } else {
                $picker = New-Object Windows.Forms.OpenFileDialog
                $picker.CheckFileExists = $true
                if ($picker.ShowDialog() -eq 'OK') { $target.Text = $picker.FileName }
            }
            $picker.Dispose()
        })
        $dialog.Controls.Add($button)
        $row++
    }
    $note = New-Object Windows.Forms.Label
    $note.Text = "Original US NTSC 1.2 big-endian .z64; MD5 57a9719ad547c516342e1a15d5c28c3d.`r`nPlace baserom.z64 in <oot>/baseroms/ntsc-1.2, or choose a separate ROM folder.`r`nBlank ROM directory uses the checkout's baseroms/ntsc-1.2. No ROM or BIOS is supplied."
    $note.SetBounds(12, 340, 876, 70)
    $dialog.Controls.Add($note)
    foreach ($link in @(@('Open decomp', 'oot_decomp'), @('Open ROM folder', 'oot_roms'))) {
        $button = New-Object Windows.Forms.Button
        $button.Text = $link[0]
        $button.Tag = $link[1]
        $x = if ($link[1] -eq 'oot_decomp') { 12 } else { 168 }
        $button.SetBounds($x, 412, 150, 32)
        $button.Add_Click({
            try {
                $raw = @{}
                foreach ($key in $ConfigKeys) { $raw[$key] = $fields[$key].Text }
                $resolved = Resolve-ProjectPaths $raw
                $folder = $resolved[$this.Tag]
                if (!$folder -or !(Test-Path -LiteralPath $folder -PathType Container)) { throw "Folder does not exist: $folder" }
                Start-Process explorer.exe -ArgumentList ('"' + $folder + '"')
            } catch { [Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Local paths') | Out-Null }
        })
        $dialog.Controls.Add($button)
    }
    $guide = New-Object Windows.Forms.Button
    $guide.Text = 'Setup instructions'
    $guide.SetBounds(330, 412, 160, 32)
    $guide.Add_Click({ Start-Process (Join-Path $ProjectRoot 'tools/launcher/SETUP.md') })
    $dialog.Controls.Add($guide)
    $validate = New-Object Windows.Forms.Button
    $validate.Text = 'Validate paths / ROM'
    $validate.SetBounds(510, 412, 200, 32)
    $validate.Add_Click({
        $dialog.UseWaitCursor = $true
        try {
            $raw = @{}
            foreach ($key in $ConfigKeys) { $raw[$key] = $fields[$key].Text }
            $resolved = Resolve-ProjectPaths $raw
            $issues = @(Get-PathProblems $resolved -Build)
            if (Test-Path -LiteralPath $resolved.oot_roms -PathType Container) {
                $roms = @(Get-ChildItem -LiteralPath $resolved.oot_roms -Filter '*.z64' -File | Where-Object {
                    (Get-FileHash -LiteralPath $_.FullName -Algorithm MD5).Hash -eq '57a9719ad547c516342e1a15d5c28c3d'
                })
                if ($roms.Count -ne 1) { $issues += 'Expected exactly one original US 1.2 .z64 with the documented MD5.' }
            }
            if (Test-Path -LiteralPath $resolved.python -PathType Leaf) {
                & $resolved.python -c 'import PIL' 2>$null
                if ($LASTEXITCODE -ne 0) { $issues += 'Python needs Pillow: run the configured Python with -m pip install Pillow.' }
            }
            $message = if ($issues.Count) { $issues -join "`r`n" } else { 'Paths, ROM checksum and Pillow passed. SDK compatibility is checked during build.' }
            [Windows.Forms.MessageBox]::Show($message, 'Configuration validation') | Out-Null
        } catch { [Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Configuration validation') | Out-Null }
        finally { $dialog.UseWaitCursor = $false }
    })
    $dialog.Controls.Add($validate)
    $save = New-Object Windows.Forms.Button
    $save.Text = 'Save'
    $save.SetBounds(680, 466, 100, 32)
    $save.Add_Click({
        try {
            $raw = @{}
            foreach ($key in $ConfigKeys) { $raw[$key] = $fields[$key].Text }
            Save-ProjectPaths $raw
            $dialog.DialogResult = 'OK'
        } catch { [Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Save configuration') | Out-Null }
    })
    $dialog.Controls.Add($save)
    $cancel = New-Object Windows.Forms.Button
    $cancel.Text = 'Cancel'
    $cancel.SetBounds(790, 466, 100, 32)
    $cancel.DialogResult = 'Cancel'
    $dialog.Controls.Add($cancel)
    $dialog.CancelButton = $cancel
    if ($TestOnly) {
        $null = $dialog.Handle
        if ($fields.Count -ne 8 -or !$fields.oot_decomp.Text) { throw 'Config fields incomplete' }
        Write-Output 'Config dialog constructed; no settings changed.'
    } else { [void]$dialog.ShowDialog($Owner) }
    $dialog.Dispose()
}
