@echo off
chcp 65001 >nul
title HH Launcher
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0launcher.ps1"
if %errorlevel% neq 0 (
    echo Launch failed. Check the error above.
    pause
)
