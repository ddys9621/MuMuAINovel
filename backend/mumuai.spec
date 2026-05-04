# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from pathlib import Path

# 获取项目根目录
backend_dir = Path.cwd()
project_root = backend_dir.parent

# 查找 webview 库路径
import webview
webview_path = Path(webview.__file__).parent

# 数据文件列表
datas = [
    # 静态文件（前端）
    (str(backend_dir / 'static'), 'static'),
    # Embedding 模型
    (str(backend_dir / 'embedding'), 'embedding'),
    # 配置文件模板
    (str(project_root / 'config.ini.template'), '.'),
    # 配置加载器
    (str(backend_dir / 'config_loader.py'), '.'),
    # pywebview 的 lib 目录（包含 DLL 和 runtimes）
    (str(webview_path / 'lib'), 'webview/lib'),
]

# 隐藏导入（PyInstaller 可能检测不到的模块）
hiddenimports = [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'aiosqlite',
    'sqlalchemy.ext.asyncio',
    'anthropic',
    'openai',
    'chromadb',
    'chromadb.api',
    'chromadb.api.rust',
    'chromadb.api.client',
    'chromadb.api.shared_system_client',
    'chromadb.telemetry',
    'chromadb.telemetry.product',
    'chromadb.telemetry.product.posthog',
    'chromadb.config',
    'chromadb.db',
    'chromadb.db.impl',
    'chromadb.db.impl.sqlite',
    'sentence_transformers',
    'transformers',
    'torch',
    'app.api',
    'app.models',
    'app.services',
    'app.middleware',
    'app.mcp',
    # pywebview 桌面窗口相关
    'webview',
    'webview.platforms',
    'webview.platforms.edgechromium',  # Windows Edge WebView2
    'webview.platforms.winforms',       # Windows 备用
    'webview.platforms.cef',            # CEF 引擎
    'clr',                               # pythonnet (Windows)
    'clr_loader',
    'pythonnet',
]

# 排除的模块（减小体积）
excludes = [
    'matplotlib',
    # 'PIL',  # sentence-transformers 的 CLIPModel 需要 PIL，不能排除
    'tkinter',
    'test',
    # 'unittest',  # PyTorch 需要 unittest，不能排除
]

a = Analysis(
    ['start_app.py'],  # 使用 start_app.py 作为入口点（包含数据库检查和自动打开浏览器）
    pathex=[str(backend_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MuMuAINovel',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 隐藏控制台窗口（使用 pywebview 桌面窗口）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可以添加图标文件路径
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MuMuAINovel',
)

