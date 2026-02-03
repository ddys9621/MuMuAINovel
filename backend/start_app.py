"""应用启动脚本 - 使用 pywebview 桌面窗口"""
import sys
import os
import time
import threading
import asyncio
from pathlib import Path

# 确保打包后能找到 config_loader
if getattr(sys, 'frozen', False):
    # 打包后的 exe 环境
    _exe_dir = Path(sys.executable).parent
    _internal_dir = _exe_dir / '_internal'
    if _internal_dir.exists():
        sys.path.insert(0, str(_internal_dir))

# 全局变量
_server_thread = None
_server_started = threading.Event()
_server_error = None


def check_database_connection():
    """检查数据库连接，返回 (成功, 错误信息)"""
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        # 从环境变量获取数据库 URL
        database_url = os.getenv('DATABASE_URL', 'postgresql+asyncpg://aaaa:962106@localhost:5432/6666')

        async def test_connection():
            engine = create_async_engine(database_url, echo=False)
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            await engine.dispose()

        asyncio.run(test_connection())
        return True, None

    except Exception as e:
        error_msg = f"""数据库连接失败！

错误信息：{str(e)}

请检查：
1. PostgreSQL 数据库是否已安装并运行
2. config.ini 中的数据库配置是否正确
3. 数据库用户名和密码是否正确
4. 数据库是否已创建（数据库名：mumuai_novel）"""
        return False, error_msg


def run_server(host, port):
    """在后台线程运行 uvicorn 服务器"""
    global _server_error
    try:
        import uvicorn
        from app.main import app

        # 配置 uvicorn，禁用信号处理（因为不在主线程）
        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level="warning",
            access_log=False,
        )
        server = uvicorn.Server(config)

        # 标记服务器已启动
        _server_started.set()

        # 运行服务器
        server.run()

    except Exception as e:
        _server_error = str(e)
        _server_started.set()


def start_server_thread(host='127.0.0.1', port=8000):
    """启动服务器线程"""
    global _server_thread

    _server_thread = threading.Thread(
        target=run_server,
        args=(host, port),
        daemon=True
    )
    _server_thread.start()

    # 等待服务器启动
    _server_started.wait(timeout=30)

    if _server_error:
        return False, _server_error

    # 额外等待一下确保服务完全就绪
    time.sleep(1)
    return True, None


def show_error_dialog(title, message):
    """显示错误对话框"""
    try:
        import webview
        # 创建一个简单的错误窗口
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: "Microsoft YaHei", Arial, sans-serif;
                    padding: 20px;
                    background: #fff;
                    color: #333;
                }}
                h2 {{ color: #e74c3c; margin-bottom: 20px; }}
                pre {{
                    background: #f5f5f5;
                    padding: 15px;
                    border-radius: 5px;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                    font-size: 13px;
                }}
                button {{
                    margin-top: 20px;
                    padding: 10px 30px;
                    font-size: 14px;
                    cursor: pointer;
                    background: #3498db;
                    color: white;
                    border: none;
                    border-radius: 5px;
                }}
                button:hover {{ background: #2980b9; }}
            </style>
        </head>
        <body>
            <h2>❌ {title}</h2>
            <pre>{message}</pre>
            <button onclick="window.close()">关闭</button>
        </body>
        </html>
        """
        window = webview.create_window(
            title='MuMuAINovel - 错误',
            html=error_html,
            width=600,
            height=400,
            resizable=False
        )
        webview.start()
    except Exception:
        # 如果 pywebview 也失败，回退到控制台
        print(f"\n{title}\n{message}")
        input("\n按回车键退出...")


def main():
    """主函数"""
    import webview

    # 加载配置文件
    try:
        from config_loader import init_config
        init_config()
    except Exception as e:
        # 配置加载失败，显示警告但继续运行
        print(f"[WARN] 配置文件加载失败: {e}")

    # 检查数据库连接
    db_ok, db_error = check_database_connection()
    if not db_ok:
        show_error_dialog("数据库连接失败", db_error)
        return

    # 获取端口配置
    port = int(os.getenv('APP_PORT', '8000'))
    host = '127.0.0.1'  # 桌面应用只需要本地访问

    # 启动后台服务器
    server_ok, server_error = start_server_thread(host, port)
    if not server_ok:
        show_error_dialog("服务器启动失败", server_error)
        return

    # 创建桌面窗口
    window = webview.create_window(
        title='MuMuAINovel - AI 小说创作助手',
        url=f'http://{host}:{port}',
        width=1400,
        height=900,
        min_size=(1024, 768),
        resizable=True,
        fullscreen=False,
        frameless=False,
        easy_drag=False,
        text_select=True,
    )

    # 启动 GUI（阻塞直到窗口关闭）
    webview.start(
        debug=False,  # 生产环境关闭调试模式
        private_mode=False,  # 允许保存登录状态等
    )


if __name__ == '__main__':
    main()

