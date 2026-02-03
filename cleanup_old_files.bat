@echo off
REM ============================================
REM 自动清理旧文件脚本 (Windows)
REM 用途：删除重构后不再需要的旧文件
REM ============================================

setlocal enabledelayedexpansion

echo 🧹 开始清理旧文件...
echo ================================

REM 切换到脚本所在目录
cd /d "%~dp0"

REM 创建备份目录
set TIMESTAMP=%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%
set BACKUP_DIR=backup\old_files_%TIMESTAMP%
mkdir "%BACKUP_DIR%" 2>nul
echo 📦 备份目录: %BACKUP_DIR%

REM ============================================
REM 1. 备份并删除旧迁移脚本
REM ============================================
echo.
echo 📝 步骤 1: 清理旧迁移脚本...

set "SCRIPTS[0]=backend\scripts\add_chapter_outline_id_to_plot_cards.sql"
set "SCRIPTS[1]=backend\scripts\add_plot_tables.sql"
set "SCRIPTS[2]=backend\scripts\migration_phase1_create_tables.sql"
set "SCRIPTS[3]=backend\scripts\migration_phase2_migrate_data.py"
set "SCRIPTS[4]=backend\scripts\migration_phase3_cleanup.sql"

for /L %%i in (0,1,4) do (
    set "script=!SCRIPTS[%%i]!"
    if exist "!script!" (
        echo   ✓ 备份: !script!
        copy "!script!" "%BACKUP_DIR%\" >nul
        del "!script!"
        echo   ✓ 删除: !script!
    ) else (
        echo   ⊘ 不存在: !script!
    )
)

REM ============================================
REM 2. 检查 Outline 相关文件的引用
REM ============================================
echo.
echo 🔍 步骤 2: 检查 Outline 相关文件引用...

set "OUTLINE_FILES[0]=backend\app\models\outline.py"
set "OUTLINE_FILES[1]=backend\app\api\outlines.py"
set "OUTLINE_FILES[2]=backend\app\schemas\outline.py"

echo   搜索 Outline 引用...
findstr /s /i /c:"from app.models.outline import" backend\app\*.py >nul 2>&1
set OUTLINE_REFS=%ERRORLEVEL%

findstr /s /i /c:"from app.api import.*outlines" backend\app\*.py >nul 2>&1
set OUTLINE_API_REFS=%ERRORLEVEL%

findstr /s /i /c:"outlines.router" backend\app\*.py >nul 2>&1
set OUTLINE_ROUTER_REFS=%ERRORLEVEL%

if %OUTLINE_REFS% NEQ 0 if %OUTLINE_API_REFS% NEQ 0 if %OUTLINE_ROUTER_REFS% NEQ 0 (
    echo   ✓ 未发现 Outline 引用，可以安全删除
    
    REM 备份并删除 Outline 相关文件
    for /L %%i in (0,1,2) do (
        set "file=!OUTLINE_FILES[%%i]!"
        if exist "!file!" (
            echo   ✓ 备份: !file!
            for %%f in ("!file!") do (
                mkdir "%BACKUP_DIR%\%%~dpf" 2>nul
                copy "!file!" "%BACKUP_DIR%\!file!" >nul
            )
            del "!file!"
            echo   ✓ 删除: !file!
        ) else (
            echo   ⊘ 不存在: !file!
        )
    )
) else (
    echo   ⚠️  发现 Outline 引用，跳过删除
    echo   请手动检查引用
    
    REM 仅备份，不删除
    for /L %%i in (0,1,2) do (
        set "file=!OUTLINE_FILES[%%i]!"
        if exist "!file!" (
            echo   ✓ 仅备份: !file!
            for %%f in ("!file!") do (
                mkdir "%BACKUP_DIR%\%%~dpf" 2>nul
                copy "!file!" "%BACKUP_DIR%\!file!" >nul
            )
        )
    )
)

REM ============================================
REM 3. 清理 Python 缓存
REM ============================================
echo.
echo 🗑️  步骤 3: 清理 Python 缓存...

for /d /r backend %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
del /s /q backend\*.pyc 2>nul
del /s /q backend\*.pyo 2>nul

echo   ✓ Python 缓存已清理

REM ============================================
REM 4. 生成清理报告
REM ============================================
echo.
echo 📊 步骤 4: 生成清理报告...

set REPORT_FILE=%BACKUP_DIR%\cleanup_report.txt

echo 清理报告 > "%REPORT_FILE%"
echo ======================================== >> "%REPORT_FILE%"
echo 清理时间: %date% %time% >> "%REPORT_FILE%"
echo 备份目录: %BACKUP_DIR% >> "%REPORT_FILE%"
echo. >> "%REPORT_FILE%"
echo 已删除的文件: >> "%REPORT_FILE%"

for /L %%i in (0,1,4) do (
    set "script=!SCRIPTS[%%i]!"
    if not exist "!script!" (
        echo   ✓ !script! >> "%REPORT_FILE%"
    )
)

if %OUTLINE_REFS% NEQ 0 if %OUTLINE_API_REFS% NEQ 0 if %OUTLINE_ROUTER_REFS% NEQ 0 (
    for /L %%i in (0,1,2) do (
        set "file=!OUTLINE_FILES[%%i]!"
        if not exist "!file!" (
            echo   ✓ !file! >> "%REPORT_FILE%"
        )
    )
) else (
    echo. >> "%REPORT_FILE%"
    echo 未删除的文件（发现引用）: >> "%REPORT_FILE%"
    for /L %%i in (0,1,2) do (
        set "file=!OUTLINE_FILES[%%i]!"
        if exist "!file!" (
            echo   ⚠️  !file! >> "%REPORT_FILE%"
        )
    )
)

echo. >> "%REPORT_FILE%"
echo 备份文件列表: >> "%REPORT_FILE%"
dir /b "%BACKUP_DIR%" >> "%REPORT_FILE%"

echo   ✓ 报告已生成: %REPORT_FILE%

REM ============================================
REM 5. 验证清理结果
REM ============================================
echo.
echo ✅ 步骤 5: 验证清理结果...

echo   检查 Python 语法...
where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    python -m py_compile backend\app\models\__init__.py >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo   ✓ models\__init__.py 语法正确
    ) else (
        echo   ⚠️  models\__init__.py 语法错误
    )
    
    python -m py_compile backend\app\main.py >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo   ✓ main.py 语法正确
    ) else (
        echo   ⚠️  main.py 语法错误
    )
) else (
    echo   ⊘ Python 未安装，跳过语法检查
)

REM ============================================
REM 完成
REM ============================================
echo.
echo ================================
echo 🎉 清理完成！
echo.
echo 📦 备份位置: %BACKUP_DIR%
echo 📊 清理报告: %REPORT_FILE%
echo.
echo 下一步:
echo   1. 查看清理报告: type %REPORT_FILE%
echo   2. 启动服务测试: cd backend ^&^& uvicorn app.main:app --reload
echo   3. 如果一切正常，可以删除备份: rmdir /s /q %BACKUP_DIR%
echo.

pause
