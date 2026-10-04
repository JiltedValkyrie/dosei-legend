# Mednafen's default %M first tries an unhashed file, then the disc hash.
# Keep one unhashed backup per game variant so rebuilds retain adventure saves.
# No emulator process, config changes, deletions, or overwrites here.
function Initialize-MednafenSaves([string]$Executable, [string]$Image) {
    $base = Split-Path $Executable -Parent
    $config = Join-Path $base 'mednafen.cfg'
    $savePath = 'sav'
    $format = '%f.%M%x'
    if (Test-Path -LiteralPath $config -PathType Leaf) {
        foreach ($line in [IO.File]::ReadAllLines($config)) {
            if ($line -match '^filesys.path_sav\s+(.+)$') { $savePath = $Matches[1] }
            if ($line -match '^filesys.fname_sav\s+(.+)$') { $format = $Matches[1] }
        }
    }
    # Respect custom naming. Only repair the verified default lookup scheme.
    if ($format -ne '%f.%M%x') { return }
    if (![IO.Path]::IsPathRooted($savePath)) { $savePath = Join-Path $base $savePath }
    if (!(Test-Path -LiteralPath $savePath -PathType Container)) { return }
    $name = [IO.Path]::GetFileNameWithoutExtension($Image)
    $target = Join-Path $savePath ($name + '.bkr')
    if (Test-Path -LiteralPath $target) { return }
    $pattern = '^' + [regex]::Escape($name) + '\.[0-9a-fA-F]{32}\.bkr$'
    $candidates = @(Get-ChildItem -LiteralPath $savePath -File | Where-Object {
        $_.Name -match $pattern -and $_.Length -eq 32768
    } | Sort-Object LastWriteTimeUtc -Descending)
    $chosen = $null
    $fallback = $null
    foreach ($file in $candidates) {
        $bytes = [IO.File]::ReadAllBytes($file.FullName)
        if ([Text.Encoding]::ASCII.GetString($bytes, 0, 16) -ne 'BackUpRam Format') { continue }
        if (!$fallback) { $fallback = $file }
        # Internal BUP uses 64-byte blocks. Active first blocks start 0x80,
        # with their 11-byte filename at +4. Ignore deleted stale names.
        for ($at = 128; $at -lt $bytes.Length; $at += 64) {
            if ($bytes[$at] -eq 128 -and
                [Text.Encoding]::ASCII.GetString($bytes, $at + 4, 7) -match '^DOSEI[012]\x00$') {
                $chosen = $file
                break
            }
        }
        if ($chosen) { break }
    }
    if (!$chosen) { $chosen = $fallback }
    if (!$chosen) { return }
    [IO.File]::Copy($chosen.FullName, $target, $false)
    # RTC is optional; preserve the same session when it exists.
    $rtc = [IO.Path]::ChangeExtension($chosen.FullName, 'smpc')
    $rtcTarget = [IO.Path]::ChangeExtension($target, 'smpc')
    if ((Test-Path -LiteralPath $rtc -PathType Leaf) -and !(Test-Path -LiteralPath $rtcTarget)) {
        [IO.File]::Copy($rtc, $rtcTarget, $false)
    }
    Write-Host "Mednafen save preserved: $($chosen.Name) -> $target"
}
