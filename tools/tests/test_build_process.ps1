$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '../launcher/build-dialog.ps1')
$testFolder = Join-Path ([IO.Path]::GetTempPath()) ('dosei build test ' + [guid]::NewGuid())
[void][IO.Directory]::CreateDirectory($testFolder)
try {
    $script = Join-Path $testFolder 'child process.ps1'
    # Exercise real child-process completion, including paths with spaces.
    Set-Content -LiteralPath $script -Value 'param($Variant); Write-Output "built: test"; Start-Sleep -Milliseconds 100; exit ([int]$Variant)'
    foreach ($expected in @(0, 7)) {
        $output = Join-Path $testFolder 'stdout.txt'
        $errors = Join-Path $testFolder 'stderr.txt'
        $process = Start-BuildProcess -Script $script -Variant "$expected" -OutputPath $output -ErrorPath $errors
        try {
            $deadline = [DateTime]::UtcNow.AddSeconds(15)
            while (!$process.HasExited) {
                if ([DateTime]::UtcNow -gt $deadline) { throw 'Child process timed out' }
                Start-Sleep -Milliseconds 100
            }
            $process.WaitForExit()
            if ($null -eq $process.ExitCode -or $process.ExitCode -ne $expected) {
                throw "Expected exit $expected, got '$($process.ExitCode)'"
            }
            if ((Get-Content -Raw -LiteralPath $output) -notmatch 'built: test') { throw 'Output missing' }
            Write-Output "PASS: exit $expected retained after asynchronous completion"
        } finally { $process.Dispose() }
    }
} finally {
    # Only delete the explicit files created by this test.
    Remove-Item -LiteralPath (Join-Path $testFolder 'child process.ps1'), (Join-Path $testFolder 'stdout.txt'), (Join-Path $testFolder 'stderr.txt') -ErrorAction SilentlyContinue
    [IO.Directory]::Delete($testFolder)
}
