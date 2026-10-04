# Shared by the selector, direct BAT launchers, and the Windows build entry.
$ProjectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$ConfigFile = Join-Path $ProjectRoot 'config.ini'
$ConfigKeys = @('jo_engine','msys2','python','kronos','kronos_dlls','saturn_bios','oot_decomp','oot_roms','mednafen')
$EmulatorKeys = @('emulator','cart','fullscreen','extra_args')
$EmulatorDefaults = @{ emulator='kronos'; cart='extram4'; fullscreen='0'; extra_args='' }

function Read-IniPaths([string]$Path, [string]$Want = 'Paths') {
    $values = @{}
    $section = ''
    foreach ($line in [IO.File]::ReadAllLines($Path)) {
        $text = $line.Trim()
        if (!$text -or $text.StartsWith(';') -or $text.StartsWith('#')) { continue }
        if ($text -match '^\[(.+)\]$') { $section = $Matches[1]; continue }
        if ($section -eq $Want -and $text -match '^([^=]+)=(.*)$') {
            $key = $Matches[1].Trim().ToLowerInvariant()
            if ($values.ContainsKey($key)) { throw "Duplicate config key: $key" }
            $values[$key] = $Matches[2].Trim()
        }
    }
    return $values
}

function Get-ProjectPaths {
    $values = Read-IniPaths (Join-Path $ProjectRoot 'config.example.ini')
    # Convenience for the original workstation; never required on another PC.
    $oldCheckout = Join-Path (Split-Path (Split-Path $ProjectRoot -Parent) -Parent) 'game-decomps/n64/oot'
    if (Test-Path -LiteralPath $oldCheckout -PathType Container) { $values.oot_decomp = $oldCheckout }
    if (Test-Path -LiteralPath $ConfigFile -PathType Leaf) {
        $saved = Read-IniPaths $ConfigFile
        foreach ($key in $ConfigKeys) { if ($saved.ContainsKey($key)) { $values[$key] = $saved[$key] } }
    }
    return Resolve-ProjectPaths $values
}

function Resolve-ProjectPaths($values) {
    foreach ($key in $ConfigKeys) {
        $value = $values[$key]
        if ($value -match '[\r\n"]') { throw "Invalid path for $key (do not add quotes)." }
        if (!$value) { continue }
        if ($key -eq 'python' -and $value -notmatch '[/\\:]') {
            $command = Get-Command $value -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($command) { $values[$key] = $command.Source }
        } elseif (![IO.Path]::IsPathRooted($value)) {
            $values[$key] = [IO.Path]::GetFullPath((Join-Path $ProjectRoot $value))
        }
    }
    if ($values.mednafen -eq $null) { $values.mednafen = '' }
    if (!$values.oot_roms -and $values.oot_decomp) { $values.oot_roms = Join-Path $values.oot_decomp 'baseroms/ntsc-1.2' }
    return $values
}

# Emulator choice and Mednafen options live in [Emulator], beside [Paths].
function Get-EmulatorSettings {
    $values = $EmulatorDefaults.Clone()
    if (Test-Path -LiteralPath $ConfigFile -PathType Leaf) {
        $saved = Read-IniPaths $ConfigFile 'Emulator'
        foreach ($key in $EmulatorKeys) { if ($saved.ContainsKey($key)) { $values[$key] = $saved[$key] } }
    }
    if ($values.emulator -notin @('kronos','mednafen')) { $values.emulator = 'kronos' }
    return $values
}

function Save-ProjectPaths($Values, $Emulator = $null) {
    if (!$Emulator) { $Emulator = Get-EmulatorSettings }
    $lines = @('; Local workstation paths. Not committed to git.', '[Paths]')
    foreach ($key in $ConfigKeys) {
        $value = ([string]$Values[$key]).Trim()
        if ($value -match '[\r\n"]') { throw "Invalid path for $key (do not add quotes)." }
        $lines += "$key = $value"
    }
    $lines += '', '[Emulator]'
    foreach ($key in $EmulatorKeys) {
        $value = ([string]$Emulator[$key]).Trim()
        if ($value -match '[\r\n]') { throw "Invalid value for $key." }
        $lines += "$key = $value"
    }
    [IO.File]::WriteAllLines($ConfigFile, $lines, (New-Object Text.UTF8Encoding($false)))
}

function Get-PathProblems($Values, [switch]$Build) {
    foreach ($key in @('jo_engine','msys2','oot_decomp')) {
        if ($Build -and !$Values[$key]) { "Required setting is blank: $key"; return }
    }
    $checks = New-Object System.Collections.ArrayList
    if ((Get-EmulatorSettings).emulator -eq 'mednafen') { [void]$checks.Add(@('Mednafen',$Values.mednafen)) }
    else { [void]$checks.Add(@('Kronos',$Values.kronos)); [void]$checks.Add(@('Saturn BIOS',$Values.saturn_bios)) }
    if ($Build) {
        [void]$checks.AddRange(@(
            @('Jo compiler',(Join-Path $Values.jo_engine 'Compiler/WINDOWS/bin/sh-elf-gcc.exe')),
            @('Jo makefile',(Join-Path $Values.jo_engine 'Compiler/COMMON/jo_engine_makefile')),
            @('SGL work area',(Join-Path $Values.jo_engine 'Compiler/COMMON/SGL_302j/LIB_ELF/SGLAREA.O')),
            @('MSYS2 bash',(Join-Path $Values.msys2 'usr/bin/bash.exe')),
            @('MSYS2 make',(Join-Path $Values.msys2 'usr/bin/make.exe')),
            @('Python',$Values.python),
            @('OoT config',(Join-Path $Values.oot_decomp 'baseroms/ntsc-1.2/config.yml')),
            @('OoT segment table',(Join-Path $Values.oot_decomp 'baseroms/ntsc-1.2/segments.csv'))))
    }
    foreach ($check in $checks) {
        if (!$check[1] -or !(Test-Path -LiteralPath $check[1] -PathType Leaf)) { "$($check[0]): missing $($check[1])" }
    }
    if ($Values.kronos_dlls -and !(Test-Path -LiteralPath $Values.kronos_dlls -PathType Container)) { 'Kronos DLL directory does not exist (leave blank for a self-contained release).' }
    if ($Build -and (!$Values.oot_roms -or !(Test-Path -LiteralPath $Values.oot_roms -PathType Container))) { "ROM directory missing: $($Values.oot_roms)" }
}
