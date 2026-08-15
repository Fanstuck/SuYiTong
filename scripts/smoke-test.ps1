param(
    [string]$PlatformUrl = "http://127.0.0.1:8000",
    [string]$JiuwenSwarmUrl = "http://127.0.0.1:5173"
)

$ErrorActionPreference = "Stop"

$platform = Invoke-WebRequest -Uri "$PlatformUrl/health" -UseBasicParsing -TimeoutSec 10
$swarm = Invoke-WebRequest -Uri $JiuwenSwarmUrl -UseBasicParsing -TimeoutSec 10

Write-Host "速易通 API: HTTP $($platform.StatusCode)"
Write-Host "JiuwenSwarm Web: HTTP $($swarm.StatusCode)"

