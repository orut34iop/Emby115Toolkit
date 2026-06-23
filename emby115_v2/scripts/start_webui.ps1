param(
    [int]$Port = 8765,
    [string]$BindAddress = "127.0.0.1",
    [switch]$NoOpen,
    [switch]$Restart
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$OpenHost = if ($BindAddress -eq "0.0.0.0" -or $BindAddress -eq "::") { "127.0.0.1" } else { $BindAddress }
$BaseUrl = "http://$OpenHost`:$Port"

function Test-WebUiHealth {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -Uri "$Url/health" -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

function Open-WebUi {
    param([string]$Url)
    if (-not $NoOpen) {
        Start-Process $Url | Out-Null
    }
}

if (Test-WebUiHealth -Url $BaseUrl) {
    Write-Host "Emby115Toolkit V2 WebUI is already running: $BaseUrl"
    Open-WebUi -Url $BaseUrl
    exit 0
}

$listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
if ($listeners.Count -gt 0) {
    if (-not $Restart) {
        $pids = ($listeners | Select-Object -ExpandProperty OwningProcess -Unique) -join ", "
        Write-Host "Port $Port is already in use by process id(s): $pids"
        Write-Host "Run with -Restart to stop the existing listener and start WebUI again."
        exit 1
    }

    foreach ($listener in $listeners) {
        Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 500
}

Write-Host "Starting Emby115Toolkit V2 WebUI backend..."
$arguments = @("main.py", "--serve-web", "--host", $BindAddress, "--port", "$Port")
$process = Start-Process -FilePath "python" -ArgumentList $arguments -WorkingDirectory $ProjectRoot -WindowStyle Minimized -PassThru

for ($attempt = 1; $attempt -le 60; $attempt++) {
    Start-Sleep -Milliseconds 500
    if ($process.HasExited) {
        Write-Host "WebUI backend exited early with code $($process.ExitCode)."
        exit 1
    }
    if (Test-WebUiHealth -Url $BaseUrl) {
        Write-Host "Emby115Toolkit V2 WebUI is ready: $BaseUrl"
        Open-WebUi -Url $BaseUrl
        exit 0
    }
}

Write-Host "Timed out waiting for WebUI health check: $BaseUrl/health"
exit 1
