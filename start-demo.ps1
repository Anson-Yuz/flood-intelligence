[CmdletBinding()]
param(
    [switch]$Docker,
    [switch]$Install,
    [switch]$NoBrowser,
    [int]$FrontendPort = 0,
    [int]$BackendPort = 0
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$StateDir = Join-Path $Root ".demo"
$StateFile = Join-Path $StateDir "processes.json"
$LogDir = Join-Path $StateDir "logs"

function Import-DotEnv {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return }
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) { continue }
        $parts = $trimmed.Split(@("="), 2, [System.StringSplitOptions]::None)
        $name = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")
        if ($name -match '^[A-Za-z_][A-Za-z0-9_]*$') {
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

function Wait-Http {
    param([string]$Url, [int]$TimeoutSeconds = 90)
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) { return }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "Timed out waiting for $Url"
}

function Assert-PortAvailable {
    param([int]$Port, [string]$Name)
    $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    if ($listener) {
        throw "$Name port $Port is already in use. Stop the existing service or choose another port."
    }
}

function Open-DemoBrowser {
    param([string]$Url)
    if (-not $NoBrowser) {
        Start-Process -FilePath $Url
    }
}

Set-Location -LiteralPath $Root
Import-DotEnv -Path (Join-Path $Root ".env")

if ($FrontendPort -le 0) {
    $FrontendPort = if ($env:FRONTEND_PORT) { [int]$env:FRONTEND_PORT } else { 5173 }
}
if ($BackendPort -le 0) {
    $BackendPort = if ($env:BACKEND_PORT) { [int]$env:BACKEND_PORT } else { 8000 }
}
$frontendUrl = "http://127.0.0.1:$FrontendPort"
$backendHealthUrl = "http://127.0.0.1:$BackendPort/api/v1/health"
$env:FRONTEND_PORT = "$FrontendPort"
$env:BACKEND_PORT = "$BackendPort"

if ($Docker) {
    if (Test-Path -LiteralPath $StateFile) {
        Write-Host "Stopping the previously tracked local demo before Docker startup..." -ForegroundColor Yellow
        & (Join-Path $Root "stop-demo.ps1") -Quiet
    }
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker was not found. Install Docker Desktop or run without -Docker."
    }
    Write-Host "Starting PostgreSQL, FastAPI and Vite with Docker Compose..." -ForegroundColor Cyan
    & docker compose up -d
    if ($LASTEXITCODE -ne 0) { throw "docker compose up failed" }
    Wait-Http -Url $backendHealthUrl -TimeoutSeconds 180
    Wait-Http -Url $frontendUrl -TimeoutSeconds 180
    Write-Host "Demo ready: $frontendUrl" -ForegroundColor Green
    Write-Host "API docs: http://127.0.0.1:$BackendPort/docs"
    Open-DemoBrowser -Url $frontendUrl
    exit 0
}

if (Test-Path -LiteralPath $StateFile) {
    Write-Host "Stopping the previously tracked local demo..." -ForegroundColor Yellow
    & (Join-Path $Root "stop-demo.ps1") -Quiet
}

Assert-PortAvailable -Port $FrontendPort -Name "Frontend"
Assert-PortAvailable -Port $BackendPort -Name "Backend"

$npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npmCommand) { $npmCommand = Get-Command npm -ErrorAction SilentlyContinue }
if (-not $npmCommand) { throw "npm was not found. Install Node.js 20 or newer." }
$nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
if (-not $nodeCommand) { $nodeCommand = Get-Command node -ErrorAction SilentlyContinue }
if (-not $nodeCommand) { throw "node was not found. Install Node.js 20 or newer." }

$pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
if (-not $pythonCommand) { $pythonCommand = Get-Command python -ErrorAction SilentlyContinue }
if (-not $pythonCommand) { throw "Python was not found. Install Python 3.10 or newer." }

$serverDir = Join-Path $Root "server"
$venvDir = Join-Path $serverDir ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "Creating backend virtual environment..." -ForegroundColor Cyan
    & $pythonCommand.Source -m venv $venvDir
    if ($LASTEXITCODE -ne 0) { throw "Failed to create the Python virtual environment." }
}

$needsPythonInstall = $Install
if (-not $needsPythonInstall) {
    & $venvPython -c "import fastapi, uvicorn, sqlalchemy, pydantic_settings, psycopg" 2>$null
    $needsPythonInstall = $LASTEXITCODE -ne 0
}
if ($needsPythonInstall) {
    Write-Host "Installing backend dependencies..." -ForegroundColor Cyan
    & $venvPython -m pip install --disable-pip-version-check -r (Join-Path $serverDir "requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "Backend dependency installation failed." }
}

$viteCommand = Join-Path $Root "node_modules\.bin\vite.cmd"
if ($Install -or -not (Test-Path -LiteralPath $viteCommand)) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
    & $npmCommand.Source ci
    if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed." }
}

$viteEntry = Join-Path $Root "node_modules\vite\bin\vite.js"
if (-not (Test-Path -LiteralPath $viteEntry)) { throw "Vite entrypoint was not found after npm install." }

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$backendOut = Join-Path $LogDir "backend.out.log"
$backendErr = Join-Path $LogDir "backend.err.log"
$frontendOut = Join-Path $LogDir "frontend.out.log"
$frontendErr = Join-Path $LogDir "frontend.err.log"
Remove-Item -LiteralPath $backendOut, $backendErr, $frontendOut, $frontendErr -Force -ErrorAction SilentlyContinue

$env:VITE_API_BASE_URL = "http://127.0.0.1:$BackendPort/api/v1"
$backend = $null
$frontend = $null
try {
    $backend = Start-Process -FilePath $venvPython `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$BackendPort") `
        -WorkingDirectory $serverDir -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr

    $frontend = Start-Process -FilePath $nodeCommand.Source `
        -ArgumentList @($viteEntry, "--host", "127.0.0.1", "--port", "$FrontendPort") `
        -WorkingDirectory $Root -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr

    $state = [ordered]@{
        mode = "local"
        createdAtUtc = [DateTime]::UtcNow.ToString("o")
        backend = [ordered]@{ pid = $backend.Id; startTimeUtc = $backend.StartTime.ToUniversalTime().ToString("o") }
        frontend = [ordered]@{ pid = $frontend.Id; startTimeUtc = $frontend.StartTime.ToUniversalTime().ToString("o") }
        urls = [ordered]@{ frontend = $frontendUrl; backendHealth = $backendHealthUrl }
    }
    $state | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $StateFile -Encoding UTF8

    Wait-Http -Url $backendHealthUrl -TimeoutSeconds 120
    Wait-Http -Url $frontendUrl -TimeoutSeconds 120
} catch {
    Write-Host "Startup failed. Logs are in $LogDir" -ForegroundColor Red
    if (Test-Path -LiteralPath $StateFile) {
        & (Join-Path $Root "stop-demo.ps1") -Quiet
    } else {
        if ($backend -and -not $backend.HasExited) { Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue }
        if ($frontend -and -not $frontend.HasExited) { Stop-Process -Id $frontend.Id -Force -ErrorAction SilentlyContinue }
    }
    throw
}

Write-Host "预鉴平台已启动" -ForegroundColor Green
Write-Host "Frontend : $frontendUrl"
Write-Host "Backend  : http://127.0.0.1:$BackendPort"
Write-Host "API docs : http://127.0.0.1:$BackendPort/docs"
Write-Host "Logs     : $LogDir"
Write-Host "Stop     : .\stop-demo.ps1"
Open-DemoBrowser -Url $frontendUrl
