[CmdletBinding()]
param(
    [switch]$Docker,
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$StateFile = Join-Path $Root ".demo\processes.json"

if ($Docker) {
    Set-Location -LiteralPath $Root
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker was not found."
    }
    & docker compose down
    if ($LASTEXITCODE -ne 0) { throw "docker compose down failed" }
    if (-not $Quiet) { Write-Host "Docker demo stopped." -ForegroundColor Green }
    exit 0
}

if (-not (Test-Path -LiteralPath $StateFile)) {
    if (-not $Quiet) { Write-Host "No locally tracked demo processes were found." -ForegroundColor Yellow }
    exit 0
}

$state = Get-Content -LiteralPath $StateFile -Raw -Encoding UTF8 | ConvertFrom-Json

function Stop-TrackedProcess {
    param([object]$Entry, [string]$Name)
    if (-not $Entry -or -not $Entry.pid -or -not $Entry.startTimeUtc) { return }
    $process = Get-Process -Id ([int]$Entry.pid) -ErrorAction SilentlyContinue
    if (-not $process) {
        if (-not $Quiet) { Write-Host "$Name is already stopped." }
        return
    }
    $expected = [DateTime]::Parse([string]$Entry.startTimeUtc).ToUniversalTime()
    $actual = $process.StartTime.ToUniversalTime()
    if ([Math]::Abs(($actual - $expected).TotalSeconds) -gt 2) {
        Write-Warning "Refusing to stop PID $($Entry.pid): it has been reused by another process."
        return
    }
    Stop-Process -Id $process.Id -ErrorAction SilentlyContinue
    try { Wait-Process -Id $process.Id -Timeout 5 -ErrorAction Stop } catch {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
    if (-not $Quiet) { Write-Host "$Name stopped." }
}

Stop-TrackedProcess -Entry $state.frontend -Name "Frontend"
Stop-TrackedProcess -Entry $state.backend -Name "Backend"
Remove-Item -LiteralPath $StateFile -Force

if (-not $Quiet) {
    Write-Host "预鉴本地演示已停止。日志保留在 .demo\logs。" -ForegroundColor Green
}
