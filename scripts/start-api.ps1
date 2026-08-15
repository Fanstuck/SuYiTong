param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "项目虚拟环境不存在：$Python"
}

$env:SUYITONG_PROJECT_ROOT = $ProjectRoot
& $Python -m uvicorn syt_platform.api.main:app --host $HostAddress --port $Port
exit $LASTEXITCODE
