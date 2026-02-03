#!/usr/bin/env pwsh
# ============================================
# PostgreSQL 数据库自动设置脚本
# ============================================

$ErrorActionPreference = "Stop"

Write-Host "🗄️  PostgreSQL 数据库设置" -ForegroundColor Cyan
Write-Host "================================`n" -ForegroundColor Cyan

# 设置密码
$env:PGPASSWORD = "962106"

# 步骤 1: 创建数据库
Write-Host "📝 步骤 1: 创建数据库..." -ForegroundColor Yellow
try {
    psql -U postgres -c "DROP DATABASE IF EXISTS mumuai_novel;" 2>$null
    psql -U postgres -c "CREATE DATABASE mumuai_novel;"
    Write-Host "  ✓ 数据库 mumuai_novel 创建成功" -ForegroundColor Green
} catch {
    Write-Host "  ⚠️  数据库可能已存在，继续..." -ForegroundColor Yellow
}

# 步骤 2: 创建用户（可选）
Write-Host "`n📝 步骤 2: 创建数据库用户..." -ForegroundColor Yellow
try {
    psql -U postgres -c "DROP USER IF EXISTS mumuai;" 2>$null
    psql -U postgres -c "CREATE USER mumuai WITH PASSWORD '962106';"
    psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE mumuai_novel TO mumuai;"
    Write-Host "  ✓ 用户 mumuai 创建成功" -ForegroundColor Green
} catch {
    Write-Host "  ⚠️  用户可能已存在，继续..." -ForegroundColor Yellow
}

# 步骤 3: 初始化表结构
Write-Host "`n📝 步骤 3: 初始化数据库表结构..." -ForegroundColor Yellow
try {
    psql -U postgres -d mumuai_novel -f backend/scripts/init_new_database.sql
    Write-Host "  ✓ 数据库表结构初始化成功" -ForegroundColor Green
} catch {
    Write-Host "  ❌ 表结构初始化失败: $_" -ForegroundColor Red
    exit 1
}

# 步骤 4: 验证数据库
Write-Host "`n📝 步骤 4: 验证数据库..." -ForegroundColor Yellow
$tableCount = psql -U postgres -d mumuai_novel -t -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public';"
Write-Host "  ✓ 数据库表数量: $($tableCount.Trim())" -ForegroundColor Green

# 步骤 5: 配置 .env 文件
Write-Host "`n📝 步骤 5: 配置环境变量..." -ForegroundColor Yellow
$envFile = "backend/.env"
if (-not (Test-Path $envFile)) {
    Copy-Item "backend/.env.example" $envFile
    Write-Host "  ✓ 已创建 .env 文件" -ForegroundColor Green
}

# 更新数据库 URL
$envContent = Get-Content $envFile -Raw
if ($envContent -match "DATABASE_URL=") {
    $envContent = $envContent -replace "DATABASE_URL=.*", "DATABASE_URL=postgresql+asyncpg://postgres:962106@localhost:5432/mumuai_novel"
    $envContent | Set-Content $envFile -NoNewline
    Write-Host "  ✓ 已更新 DATABASE_URL" -ForegroundColor Green
} else {
    Add-Content $envFile "`nDATABASE_URL=postgresql+asyncpg://postgres:962106@localhost:5432/mumuai_novel"
    Write-Host "  ✓ 已添加 DATABASE_URL" -ForegroundColor Green
}

# 完成
Write-Host "`n================================" -ForegroundColor Cyan
Write-Host "🎉 数据库设置完成！" -ForegroundColor Green
Write-Host "`n下一步:" -ForegroundColor Cyan
Write-Host "  1. 启动后端服务:" -ForegroundColor White
Write-Host "     cd backend" -ForegroundColor Gray
Write-Host "     .venv\Scripts\Activate.ps1" -ForegroundColor Gray
Write-Host "     uvicorn app.main:app --reload --port 8000" -ForegroundColor Gray
Write-Host "`n  2. 访问 API 文档:" -ForegroundColor White
Write-Host "     http://localhost:8000/docs" -ForegroundColor Gray
Write-Host "`n  3. 查看数据库:" -ForegroundColor White
Write-Host "     psql -U postgres -d mumuai_novel" -ForegroundColor Gray
Write-Host ""
