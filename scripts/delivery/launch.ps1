param([int]$Port = 8765, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$deliveryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$selectedPython = $null
function Test-Python([string]$Executable, [string[]]$Prefix) {
    & $Executable @Prefix -S -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 2)" 2>$null
    return $LASTEXITCODE -eq 0
}
try {
    $bundledPython = Join-Path $deliveryRoot 'runtime/python/python.exe'
    if (Test-Path -LiteralPath $bundledPython -PathType Leaf) {
        if (-not (Test-Python $bundledPython @())) { throw 'Bundled Python is unavailable or older than 3.11. Re-extract the complete delivery.' }
        $selectedPython = $bundledPython
        $pythonPrefix = @()
    }
    if (-not $selectedPython) {
        $launcher = Get-Command py.exe -CommandType Application -ErrorAction SilentlyContinue
        if ($launcher -and $launcher.Source -notmatch '\\Microsoft\\WindowsApps\\' -and (Test-Python $launcher.Source @('-3.12'))) {
            $selectedPython = $launcher.Source
            $pythonPrefix = @('-3.12')
        }
    }
    if (-not $selectedPython) {
        foreach ($candidate in @(Get-Command python.exe -CommandType Application -All -ErrorAction SilentlyContinue)) {
            if ($candidate.Source -match '\\Microsoft\\WindowsApps\\') { continue }
            if (Test-Python $candidate.Source @()) {
                $selectedPython = $candidate.Source
                $pythonPrefix = @()
                break
            }
        }
    }
    if (-not $selectedPython) { throw 'No usable Python found. Re-extract runtime/python from the delivery or install Python 3.11+ from python.org. Microsoft Store aliases are not executed.' }
    Set-Location -LiteralPath $deliveryRoot
    $arguments = @('-S','-m','agent_pilot.launch','--workspace',$deliveryRoot,'--demo','--mode','view','--auto-port','--port',"$Port")
    if (-not $NoBrowser) { $arguments += '--open-browser' }
    & $selectedPython @pythonPrefix @arguments
    exit $LASTEXITCODE
} catch {
    Write-Host "CredProof startup failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'Keep this window open. Check runtime/python, extracted files and TEMP write permission.'
    exit 2
}
