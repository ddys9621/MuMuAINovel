@echo off
chcp 65001 >nul
title MuMuAI启动

echo MuMuAI小说创作工具
echo ==================

powershell -ExecutionPolicy Bypass -File "简单启动.ps1"

if %errorlevel% neq 0 (
    echo 启动失败
    pause
)
