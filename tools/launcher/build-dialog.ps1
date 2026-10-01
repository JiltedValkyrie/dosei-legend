# Rebuild dialog for the launcher: choose which images to build, watch the
# output, see whether each one passed.
#
# The build is run as a CHILD PROCESS with its output redirected to files, and
# a timer tails those files. Running it inline would block the UI thread and
# the window would show "not responding" for the whole build, which for three
# images is a long time to look broken.
#
# Each variant is built by tools/launcher/build-game.ps1, the same path
# game/build.bat uses, so a build started here is identical to one started from
# a terminal -- including the $env:OS the SDK makefile needs to pick its
# SH-2 compiler.

# Which log lines survive the dialog's filter.
#
# Top level so it can be exercised against a real captured build log rather
# than only by eye. The build prints one ~1200-character compiler invocation
# per source file; everything a person actually reads is a summary line, a
# warning, an error, one of the two boundary checks, or the final image path.
#
# It never hides a warning or an error. The only noise it drops on purpose is
# the SDK makefile's own recipe-override chatter, which is expected and says
# nothing about the build, and Pillow's deprecation warnings from the asset
# tools.
function Test-BuildLogLine {
    param([string]$line)
    if ($null -eq $line -or $line.Trim() -eq '') { return $false }
    if ($line -match '^(=====|---|Building:)') { return $true }
    if ($line -match 'overriding recipe|ignoring old recipe') { return $false }
    if ($line -match '(?i)deprecationwarning|get_flattened_data|\.getdata\(\)') { return $false }
    if ($line -match '(?i)error|failed|cannot|warning|refus|exceed|overflow|missing') { return $true }
    if ($line -match '^\S.*?\s*:\s') { return $true }   # "scenes  : ...", "built: ..."
    if ($line -match '^\s{2,}\S') { return $true }        # indented tool detail lines
    return $false
}

function Start-BuildProcess {
    param([string]$Script, [string]$Variant, [string]$OutputPath, [string]$ErrorPath)
    $process = Start-Process -FilePath 'powershell.exe' -PassThru `
        -WindowStyle Hidden `
        -RedirectStandardOutput $OutputPath -RedirectStandardError $ErrorPath `
        -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass',
                        '-File', ('"' + $Script + '"'), '-Variant', $Variant)
    # Windows PowerShell's Start-Process returns a Process without a retained
    # handle. Open it while the child is alive, so ExitCode remains available
    # after Windows removes the process from its active process table.
    $null = $process.Handle
    return $process
}

function Show-BuildDialog {
    param(
        [Parameter(Mandatory = $true)] $Owner,
        [Parameter(Mandatory = $true)] $Project,
        [string]$Preselect = 'clean',
        [switch]$TestOnly
    )

    $order = @(
        [pscustomobject]@{ Id = 'clean'; Label = 'Play Dosei Legend (Standard)' }
        [pscustomobject]@{ Id = 'hires'; Label = 'Play Dosei Legend (320x480i)' }
        [pscustomobject]@{ Id = 'normal'; Label = 'Debug Mode' }
    )

    $dialog = New-Object Windows.Forms.Form
    $dialog.Text = 'Rebuild images'
    $dialog.ClientSize = New-Object Drawing.Size(760, 520)
    $dialog.StartPosition = 'CenterParent'
    $dialog.FormBorderStyle = 'FixedDialog'
    $dialog.MinimizeBox = $false
    $dialog.MaximizeBox = $false
    $dialog.Font = New-Object Drawing.Font('Segoe UI', 10)

    $prompt = New-Object Windows.Forms.Label
    $prompt.Text = 'Which images to build:'
    $prompt.Location = New-Object Drawing.Point(16, 12)
    $prompt.Size = New-Object Drawing.Size(400, 22)
    $dialog.Controls.Add($prompt)

    # Build the selected variant by default; additional variants are explicit.
    $boxes = @{}
    $y = 38
    foreach ($entry in $order) {
        $box = New-Object Windows.Forms.CheckBox
        $box.Text = $entry.Label
        $box.Location = New-Object Drawing.Point(24, $y)
        $box.Size = New-Object Drawing.Size(420, 24)
        $box.Checked = ($entry.Id -eq $Preselect)
        $dialog.Controls.Add($box)
        $boxes[$entry.Id] = $box
        $y += 26
    }

    $all = New-Object Windows.Forms.Button
    $all.Text = 'All three'
    $all.Location = New-Object Drawing.Point(470, 38)
    $all.Size = New-Object Drawing.Size(120, 30)
    $all.Add_Click({ foreach ($b in $boxes.Values) { $b.Checked = $true } })
    $dialog.Controls.Add($all)

    $none = New-Object Windows.Forms.Button
    $none.Text = 'None'
    $none.Location = New-Object Drawing.Point(600, 38)
    $none.Size = New-Object Drawing.Size(120, 30)
    $none.Add_Click({ foreach ($b in $boxes.Values) { $b.Checked = $false } })
    $dialog.Controls.Add($none)

    $log = New-Object Windows.Forms.TextBox
    $log.Location = New-Object Drawing.Point(16, 124)
    $log.Size = New-Object Drawing.Size(728, 330)
    $log.Multiline = $true
    $log.ReadOnly = $true
    # Both bars: the compiler command lines are hundreds of characters wide, so
    # without a horizontal bar the interesting end of a line is unreachable.
    $log.ScrollBars = 'Both'
    $log.WordWrap = $false
    $log.Font = New-Object Drawing.Font('Consolas', 9)
    $log.Text = 'Pick images, then Build.'
    $dialog.Controls.Add($log)

    # The build prints one ~1200-character compiler invocation per source file,
    # which buries the parts anyone reads. Filtered is the default; the raw log
    # is kept in full and re-rendered when this is ticked, so nothing is lost.
    $verbose = New-Object Windows.Forms.CheckBox
    $verbose.Text = 'Show full log (every compiler command)'
    $verbose.Location = New-Object Drawing.Point(16, 96)
    $verbose.Size = New-Object Drawing.Size(400, 24)
    $dialog.Controls.Add($verbose)

    $state = New-Object Windows.Forms.Label
    $state.Location = New-Object Drawing.Point(16, 462)
    $state.Size = New-Object Drawing.Size(500, 44)
    $dialog.Controls.Add($state)

    $build = New-Object Windows.Forms.Button
    $build.Text = 'Build'
    $build.Location = New-Object Drawing.Point(520, 468)
    $build.Size = New-Object Drawing.Size(110, 34)
    $dialog.Controls.Add($build)

    $close = New-Object Windows.Forms.Button
    $close.Text = 'Close'
    $close.Location = New-Object Drawing.Point(640, 468)
    $close.Size = New-Object Drawing.Size(104, 34)
    $close.DialogResult = 'Cancel'
    $dialog.Controls.Add($close)
    $dialog.CancelButton = $close

    # Mutable state the timer and the click handler share. A hashtable because
    # a closure assigning to a plain variable would create its own copy.
    $run = @{
        Queue = @(); At = 0; Process = $null; Out = $null; Err = $null
        OutAt = 0; ErrAt = 0; Failed = @(); Built = @(); Busy = $false
        Raw = New-Object Text.StringBuilder
        Partial = ''
    }

    $keep = { param($line) Test-BuildLogLine $line }

    $render = {
        $text = $run.Raw.ToString()
        if ($verbose.Checked) {
            $log.Text = $text
        } else {
            $lines = $text -split "`r?`n"
            $log.Text = (($lines | Where-Object { & $keep $_ }) -join "`r`n")
        }
        $log.SelectionStart = $log.TextLength
        $log.ScrollToCaret()
    }

    # Raw text arrives in arbitrary chunks, so a line can straddle two reads.
    # Whole lines are rendered; the tail is held back until its newline shows up.
    $append = {
        param($text)
        if (!$text) { return }
        [void]$run.Raw.Append($text)
        $pending = $run.Partial + $text
        $lines = $pending -split "`r?`n"
        $run.Partial = $lines[-1]
        $complete = $lines[0..($lines.Count - 2)]
        if (!$complete) { return }
        if ($verbose.Checked) {
            $log.AppendText(($complete -join "`r`n") + "`r`n")
        } else {
            $shown = @($complete | Where-Object { & $keep $_ })
            if ($shown.Count) { $log.AppendText(($shown -join "`r`n") + "`r`n") }
        }
        $log.SelectionStart = $log.TextLength
        $log.ScrollToCaret()
    }

    $verbose.Add_CheckedChanged({ & $render })

    $tail = {
        param($path, [ref]$offset)
        if (!$path -or !(Test-Path -LiteralPath $path)) { return '' }
        try {
            $stream = [IO.File]::Open($path, 'Open', 'Read', 'ReadWrite')
        } catch { return '' }
        try {
            if ($stream.Length -le $offset.Value) { return '' }
            $stream.Position = $offset.Value
            $buffer = New-Object byte[] ($stream.Length - $offset.Value)
            $read = $stream.Read($buffer, 0, $buffer.Length)
            $offset.Value += $read
            return [Text.Encoding]::UTF8.GetString($buffer, 0, $read)
        } finally { $stream.Dispose() }
    }

    $timer = New-Object Windows.Forms.Timer
    $timer.Interval = 400

    $startNext = {
        if ($run.At -ge $run.Queue.Count) {
            $timer.Stop()
            $run.Busy = $false
            $build.Enabled = $true
            $close.Enabled = $true
            foreach ($box in $boxes.Values) { $box.Enabled = $true }
            $all.Enabled = $true
            $none.Enabled = $true
            if ($run.Failed.Count) {
                $state.Text = 'FAILED: ' + ($run.Failed -join ', ') +
                              '. Read the log above for the first error.'
            } else {
                $state.Text = 'Built: ' + ($run.Built -join ', ') + '.'
            }
            return
        }
        $variant = $run.Queue[$run.At]
        $state.Text = "Building $variant ... ($($run.At + 1) of $($run.Queue.Count))"
        & $append "`r`n===== $variant =====`r`n"
        $run.Out = [IO.Path]::GetTempFileName()
        $run.Err = [IO.Path]::GetTempFileName()
        $run.OutAt = 0
        $run.ErrAt = 0
        $script = Join-Path $PSScriptRoot 'build-game.ps1'
        $run.Process = Start-BuildProcess -Script $script -Variant $variant `
            -OutputPath $run.Out -ErrorPath $run.Err
        $timer.Start()
    }

    $timer.Add_Tick({
        $offset = 0
        $offset = $run.OutAt
        $text = & $tail $run.Out ([ref]$offset); $run.OutAt = $offset
        & $append $text
        $offset = $run.ErrAt
        $text = & $tail $run.Err ([ref]$offset); $run.ErrAt = $offset
        & $append $text
        if ($run.Process -and $run.Process.HasExited) {
            $timer.Stop()
            # Drain whatever landed between the last tick and the exit.
            $offset = $run.OutAt
            & $append (& $tail $run.Out ([ref]$offset)); $run.OutAt = $offset
            $offset = $run.ErrAt
            & $append (& $tail $run.Err ([ref]$offset)); $run.ErrAt = $offset
            $variant = $run.Queue[$run.At]
            # The handle was retained at launch. Wait before reading status;
            # do not discard cached process information with Refresh().
            $code = $null
            try {
                $run.Process.WaitForExit()
                $code = $run.Process.ExitCode
            } catch { $code = $null }
            if ($code -eq 0) {
                $run.Built += $variant
                & $append "`r`n--- $variant OK ---`r`n"
            } elseif ($null -eq $code) {
                # Never seen in practice, but do not guess either way: say the
                # exit status was unreadable and let the log settle it.
                $run.Failed += $variant
                & $append "`r`n--- $variant : exit status unreadable, check the log ---`r`n"
            } else {
                $run.Failed += $variant
                & $append "`r`n--- $variant FAILED (exit $code) ---`r`n"
            }
            Remove-Item -LiteralPath $run.Out, $run.Err -ErrorAction SilentlyContinue
            $run.Process.Dispose()
            $run.Process = $null
            $run.At++
            & $startNext
        }
    })

    $build.Add_Click({
        if ($run.Busy) { return }
        $chosen = @($order | Where-Object { $boxes[$_.Id].Checked } |
                    ForEach-Object { $_.Id })
        if (!$chosen.Count) {
            $state.Text = 'Nothing selected.'
            return
        }
        $run.Queue = $chosen
        $run.At = 0
        $run.Failed = @()
        $run.Built = @()
        $run.Busy = $true
        $build.Enabled = $false
        # Closing mid-build would orphan the compiler and leave a half-written
        # image, so the button is disabled until the queue drains.
        $close.Enabled = $false
        foreach ($box in $boxes.Values) { $box.Enabled = $false }
        $all.Enabled = $false
        $none.Enabled = $false
        $log.Clear()
        $run.Raw = New-Object Text.StringBuilder
        $run.Partial = ''
        & $append ('Building: ' + ($chosen -join ', ') + "`r`n")
        & $startNext
    })

    if ($TestOnly) {
        # Construct the real controls without running a compiler.
        $null = $dialog.Handle
        $null = $log.Handle
        if ($boxes.Count -ne 3) { throw 'Build dialog is missing a variant' }
        if (!$boxes[$Preselect].Checked) { throw 'Preselected variant not ticked' }
        # Only the preselected one starts ticked, so the other two are how we
        # know a build here would not quietly rebuild something unasked.
        $ticked = @($boxes.Values | Where-Object Checked)
        if ($ticked.Count -ne 1) { throw 'Expected exactly one variant ticked' }
        foreach ($box in $boxes.Values) { $box.Checked = $true }
        if (@($boxes.Values | Where-Object Checked).Count -ne 3) {
            throw 'Could not tick all three variants'
        }
        # The filter must keep everything anyone reads and drop only noise.
        # Sampled from a real build log rather than invented.
        $mustKeep = @(
            'boundary: .bss ends 0x060aeb10, 15152 bytes below the work area',
            'built: /d/.../game-clean.iso  (cue: build/game-clean.cue)',
            'dialogue: 14 speakers, 45 rules, 35 conditions, 79 pages, 191 lines',
            '  MIDO       fresh-file text 0x102F',
            '  VRAM    440488 of  445432 B (98.9%), 4944 B spare',
            '  note: spot04 exitIndex 5 leads to SCENE_KOKIRI_SHOP',
            'boundary check failed: removing the image so it cannot be run',
            'src/demo.c:12:5: error: something is wrong',
            'src/demo.c:12:5: warning: unused variable')
        $mustDrop = @(
            'build/dependencies/sdk/Compiler/WINDOWS/bin/sh-elf-gcc.exe src/main.c  -DJO_FRAMERATE=1 -o build/obj/main.o',
            "makefile:142: warning: overriding recipe for target 'build/game.elf'",
            'jo_engine_makefile:321: warning: ignoring old recipe for target ''build/game.elf''',
            'D:\path\build_demo_assets.py:130: DeprecationWarning: Image.Image.getdata is deprecated',
            '')
        foreach ($line in $mustKeep) {
            if (!(Test-BuildLogLine $line)) { throw "Filter hid a needed line: $line" }
        }
        foreach ($line in $mustDrop) {
            if (Test-BuildLogLine $line) { throw "Filter kept noise: $line" }
        }
        $dialog.Dispose()
        return @{ Built = @(); Failed = @() }
    }

    [void]$dialog.ShowDialog($Owner)
    $result = @{ Built = $run.Built; Failed = $run.Failed }
    $dialog.Dispose()
    return $result
}
