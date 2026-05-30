param(
  [switch]$NoBuild
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Write-Step($msg) {
  Write-Host "[MuMuAINovel] $msg" -ForegroundColor Cyan
}

function Write-Err($msg) {
  Write-Host "[MuMuAINovel] ❌ $msg" -ForegroundColor Red
}

function Test-CommandAvailable($name, $checkArgs = '--version') {
  try {
    & $name $checkArgs *> $null
  } catch {
    throw "Command not found: $name. Please install it and add to PATH."
  }
}

function Get-EnvValue($name, $defaultValue) {
  $line = Get-Content '.env' | Where-Object { $_ -match "^$name=" } | Select-Object -Last 1
  if (-not $line) {
    return $defaultValue
  }

  $value = $line.Substring($name.Length + 1).Trim().Trim('"').Trim("'")
  if ([string]::IsNullOrWhiteSpace($value)) {
    return $defaultValue
  }

  return $value
}

# 读取密码文件：剥离 UTF-8 BOM + 所有空白字符（兼容 Notepad 编辑遗留）
function Read-SecretFile($path) {
  $bytes = [System.IO.File]::ReadAllBytes($path)
  if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
    $bytes = $bytes[3..($bytes.Length - 1)]
  }
  $text = [System.Text.Encoding]::UTF8.GetString($bytes)
  return ($text -replace '\s', '')
}

Write-Step "Checking Docker environment"
Test-CommandAvailable docker

docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
  throw "docker compose plugin not found. Please update Docker Desktop."
}

# embedding 模型预检（必须在 build 之前）
$embeddingDir = 'backend/embedding/models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2'
if (-not (Test-Path $embeddingDir)) {
  Write-Host ""
  Write-Host "================================================================" -ForegroundColor Red
  Write-Host "  缺少 AI 向量模型，无法构建镜像" -ForegroundColor Red
  Write-Host "================================================================" -ForegroundColor Red
  Write-Host ""
  Write-Host "未找到必需的 embedding 模型目录：" -ForegroundColor Yellow
  Write-Host "  $embeddingDir" -ForegroundColor Yellow
  Write-Host ""
  Write-Host "获取方式（约 500MB，免费）：" -ForegroundColor Yellow
  Write-Host ""
  Write-Host "  1. 加入 QQ 交流群：893474348" -ForegroundColor White
  Write-Host "  2. 在群文件中下载 AI 向量模型压缩包" -ForegroundColor White
  Write-Host "  3. 解压到 backend/embedding/ 目录，最终结构应为：" -ForegroundColor White
  Write-Host ""
  Write-Host "       backend/embedding/" -ForegroundColor Gray
  Write-Host "       └── models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2/" -ForegroundColor Gray
  Write-Host "           └── (模型权重和配置文件)" -ForegroundColor Gray
  Write-Host ""
  Write-Host "  4. 重新执行 ./deploy.ps1" -ForegroundColor White
  Write-Host ""
  Write-Host "模型文件被 .gitignore 排除，必须手动下载后再构建镜像。" -ForegroundColor Yellow
  Write-Host "================================================================" -ForegroundColor Red
  Write-Host ""
  exit 1
}

if (-not (Test-Path '.env')) {
  if (-not (Test-Path '.env.example')) {
    throw "Missing .env.example, cannot initialize .env"
  }
  Copy-Item '.env.example' '.env'
  Write-Step "已从 .env.example 生成 .env，请按需修改后重新执行"
}

if (-not (Test-Path 'secrets')) {
  New-Item -ItemType Directory -Path 'secrets' | Out-Null
}

if (-not (Test-Path 'secrets/local_auth_password.txt')) {
  Set-Content -Path 'secrets/local_auth_password.txt' -Value 'CHANGE_ME_LOCAL_AUTH_PASSWORD' -NoNewline -Encoding UTF8
  Write-Err "已生成占位密码文件 secrets/local_auth_password.txt，请编辑为强密码后重新执行"
  exit 1
}

$localPwd = Read-SecretFile 'secrets/local_auth_password.txt'
if ([string]::IsNullOrEmpty($localPwd)) {
  Write-Err "secrets/local_auth_password.txt 内容为空，请填入强密码"
  exit 1
}
if ($localPwd -like 'CHANGE_ME*') {
  Write-Err "检测到默认占位密码，请修改 secrets/local_auth_password.txt 后再部署"
  exit 1
}

$appPort = Get-EnvValue 'APP_PORT' '8000'
$healthUrl = "http://localhost:$appPort/health/ready"

$composeArgs = @('-f', 'docker-compose.yml', '-f', 'docker-compose.prod.yml', 'up', '-d')
if (-not $NoBuild) {
  $composeArgs += '--build'
}

Write-Step "Starting containers (首次构建可能需要 5-10 分钟)"
docker compose @composeArgs

Write-Step "Waiting for readiness endpoint (最多 60 秒)"
$maxRetry = 30
for ($i = 1; $i -le $maxRetry; $i++) {
  try {
    $resp = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 3
    if ($resp.StatusCode -eq 200) {
      Write-Host "✅ 部署成功，访问地址: http://localhost:$appPort" -ForegroundColor Green
      exit 0
    }
  } catch {
    Start-Sleep -Seconds 2
  }
}

Write-Err "服务未在预期时间内就绪"
Write-Host "请执行以下命令排查：" -ForegroundColor Yellow
Write-Host "  docker compose logs -f mumuainovel" -ForegroundColor Yellow
exit 1
