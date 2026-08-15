param(
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VendorRoot = Join-Path $ProjectRoot "vendor\jiuwenswarm"
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$UvCache = Join-Path $ProjectRoot ".cache\uv"
$RuntimeHome = Join-Path $ProjectRoot "runtime"
$RuntimeData = Join-Path $RuntimeHome ".jiuwenswarm"
$ExpectedCommit = "d7c2ab2f299cd2c73201afb41ebb8b9c00cc7015"
$SafeVendorRoot = $VendorRoot.Replace("\", "/")

if (-not (Test-Path -LiteralPath (Join-Path $VendorRoot ".git"))) {
    New-Item -ItemType Directory -Path (Split-Path -Parent $VendorRoot) -Force | Out-Null
    & git clone --depth 1 --branch JiuwenSwarm0.2.2 `
        https://atomgit.com/openJiuwen/jiuwenswarm.git $VendorRoot
    if ($LASTEXITCODE -ne 0) { throw "JiuwenSwarm 克隆失败" }
}

$head = (& git -c "safe.directory=$SafeVendorRoot" -C $VendorRoot rev-parse HEAD).Trim()
$gatewayFile = Join-Path $VendorRoot "jiuwenswarm\gateway\app_gateway.py"
$liteApplied = Select-String -LiteralPath $gatewayFile -Pattern "SUYITONG_LITE_MODE" -Quiet
if (-not $liteApplied) {
    if ($head -ne $ExpectedCommit) {
        throw "上游提交不是锁定的 JiuwenSwarm0.2.2：$head"
    }
    & git -c "safe.directory=$SafeVendorRoot" -C $VendorRoot apply `
        (Join-Path $ProjectRoot "patches\jiuwenswarm-0.2.2-lite.patch")
    if ($LASTEXITCODE -ne 0) { throw "速易通轻量补丁应用失败" }
}

$env:UV_CACHE_DIR = $UvCache
if (-not (Test-Path -LiteralPath $Python)) {
    & uv venv (Join-Path $ProjectRoot ".venv") --python 3.11
    if ($LASTEXITCODE -ne 0) { throw "Python 虚拟环境创建失败" }
}

Push-Location $VendorRoot
try {
    & uv lock
    if ($LASTEXITCODE -ne 0) { throw "JiuwenSwarm 轻量依赖锁定失败" }
}
finally {
    Pop-Location
}

& uv pip install --python $Python -e $VendorRoot
if ($LASTEXITCODE -ne 0) { throw "JiuwenSwarm Python 依赖安装失败" }
& uv pip install --python $Python -e "$ProjectRoot[test]"
if ($LASTEXITCODE -ne 0) { throw "速易通 Python 依赖安装失败" }

if (-not $SkipFrontend) {
    $Frontend = Join-Path $VendorRoot "jiuwenswarm\channels\web\frontend"
    $env:npm_config_cache = Join-Path $ProjectRoot ".cache\npm"
    Push-Location $Frontend
    try {
        & npm ci
        if ($LASTEXITCODE -ne 0) { throw "前端依赖安装失败" }
        & npm run build
        if ($LASTEXITCODE -ne 0) { throw "前端构建失败" }
    }
    finally {
        Pop-Location
    }
}

$env:JIUWENSWARM_HOME = $RuntimeHome
$env:JIUWENSWARM_DATA_DIR = $RuntimeData
$env:SUYITONG_LITE_MODE = "true"
$runtimeConfig = Join-Path $RuntimeData "config\config.yaml"
if (-not (Test-Path -LiteralPath $runtimeConfig)) {
    & $Python -m jiuwenswarm.init_workspace
    if ($LASTEXITCODE -ne 0) { throw "JiuwenSwarm 工作区初始化失败" }
}
else {
    Write-Host "保留已有 JiuwenSwarm 工作区：$RuntimeData"
}

if (-not $SkipFrontend) {
    $DistSource = Join-Path $VendorRoot "jiuwenswarm\channels\web\frontend\dist"
    $DistTarget = Join-Path $RuntimeData "channels\web\frontend\dist"
    New-Item -ItemType Directory -Path $DistTarget -Force | Out-Null
    Copy-Item -Path "$DistSource\*" -Destination $DistTarget -Recurse -Force
}

$runtimeEnv = Join-Path $RuntimeData "config\.env"
$envContent = Get-Content -LiteralPath $runtimeEnv -Raw -Encoding UTF8
$envContent = $envContent -replace '(?m)^API_BASE="?https://example\.com/compatible-mode/v1"?$', "API_BASE="
$envContent = $envContent -replace '(?m)^API_KEY="?sk-xxxxxxxxx"?$', "API_KEY="
$envContent = $envContent -replace '(?m)^MODEL_NAME="?your-model-name"?$', "MODEL_NAME="
if ($envContent -match "(?m)^SUYITONG_LITE_MODE=") {
    $envContent = $envContent -replace "(?m)^SUYITONG_LITE_MODE=.*$", "SUYITONG_LITE_MODE=true"
}
else {
    $envContent = $envContent.TrimEnd() + "`r`nSUYITONG_LITE_MODE=true`r`n"
}
Set-Content -LiteralPath $runtimeEnv -Value $envContent -Encoding UTF8

Write-Host "部署完成。"
Write-Host "1. 在 runtime\.jiuwenswarm\config\.env 配置第三方模型 API。"
Write-Host "2. 运行 scripts\start-jiuwenswarm.ps1。"
Write-Host "3. 另开终端运行 scripts\start-api.ps1。"
