param(
    [ValidateSet("all", "app", "web", "dev")]
    [string]$Mode = "all"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$DataHome = Join-Path $ProjectRoot "runtime"
$DataDir = Join-Path $DataHome ".jiuwenswarm"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "项目虚拟环境不存在：$Python"
}
if (-not (Test-Path -LiteralPath (Join-Path $DataDir "config\config.yaml"))) {
    throw "JiuwenSwarm 尚未初始化。请先运行 scripts\setup.ps1。"
}

$env:JIUWENSWARM_HOME = $DataHome
$env:JIUWENSWARM_DATA_DIR = $DataDir
$env:SUYITONG_LITE_MODE = "true"

Write-Host "JiuwenSwarm data: $DataDir"
Write-Host "JiuwenSwarm mode: $Mode"
& $Python -m jiuwenswarm.start_services $Mode
exit $LASTEXITCODE

