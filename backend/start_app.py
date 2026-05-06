"""应用启动脚本 - pywebview 启动面板 + 主应用窗口"""
import sys
import os
import time
import threading
import asyncio
import json
import logging
import traceback
from pathlib import Path
from collections import deque

if getattr(sys, 'frozen', False):
    _exe_dir = Path(sys.executable).parent
    _internal_dir = _exe_dir / '_internal'
    if _internal_dir.exists():
        sys.path.insert(0, str(_internal_dir))

# Windows 编码修复：防止 emoji/Unicode 字符导致 GBK 编码错误
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

# pythonw.exe 没有 stdout/stderr，需要创建 devnull 替代
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w', encoding='utf-8')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w', encoding='utf-8')

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

_server_thread = None
_server_started = threading.Event()
_server_error = None

# 日志缓冲区（供启动面板显示）
_log_buffer: deque = deque(maxlen=500)
_log_seq = 0


def write_startup_error(exc):
    """Persist fatal startup errors because pythonw has no visible stderr."""
    try:
        log_dir = Path(__file__).resolve().parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "startup_error.log"
        with log_file.open("a", encoding="utf-8") as f:
            f.write("\n" + "=" * 80 + "\n")
            f.write(time.strftime("%Y-%m-%d %H:%M:%S") + "\n")
            f.write(f"{type(exc).__name__}: {exc}\n")
            f.write(traceback.format_exc())
            f.write("\n")
    except Exception:
        pass


class PanelLogHandler(logging.Handler):
    """捕获日志到内存缓冲区"""
    def emit(self, record):
        global _log_seq
        try:
            _log_seq += 1
            _log_buffer.append({
                "seq": _log_seq,
                "ts": record.created,
                "level": record.levelname,
                "name": record.name,
                "msg": record.getMessage(),
            })
        except Exception:
            pass


def ensure_sqlite_database_dir(database_url):
    """Create the parent directory for file-based SQLite databases."""
    from sqlalchemy.engine import make_url

    url = make_url(database_url)
    if not url.drivername.startswith("sqlite"):
        return

    database_path = url.database
    if not database_path or database_path == ":memory:":
        return

    db_file = Path(database_path)
    if not db_file.is_absolute():
        db_file = Path.cwd() / db_file

    db_file.parent.mkdir(parents=True, exist_ok=True)


def check_database_connection():
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            return False, "环境变量 DATABASE_URL 未配置"

        ensure_sqlite_database_dir(database_url)

        async def test():
            engine = create_async_engine(database_url, echo=False)
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            await engine.dispose()
        asyncio.run(test())
        return True, None
    except Exception as e:
        return False, f"数据库连接失败：{e}"


def run_server(host, port):
    global _server_error
    try:
        import uvicorn
        from app.main import app

        # setup_logging() 会 clear 所有 handler，所以在 app 导入后重新挂载
        panel_handler = PanelLogHandler()
        panel_handler.setLevel(logging.DEBUG)
        logging.getLogger().addHandler(panel_handler)

        config = uvicorn.Config(app, host=host, port=port, log_level="info", access_log=False)
        server = uvicorn.Server(config)
        _server_started.set()
        server.run()
    except Exception as e:
        _server_error = str(e)
        _server_started.set()


def start_server_thread(host='127.0.0.1', port=8000):
    global _server_thread
    _server_thread = threading.Thread(target=run_server, args=(host, port), daemon=True)
    _server_thread.start()
    _server_started.wait(timeout=30)
    if _server_error:
        return False, _server_error
    time.sleep(1)
    return True, None


class PanelAPI:
    """pywebview JavaScript 可调用的 API"""

    def get_logs(self, after_seq=0):
        entries = [e for e in _log_buffer if e["seq"] > after_seq]
        return json.dumps(entries[-100:], ensure_ascii=False)

    def open_app(self):
        import webbrowser
        port = int(os.getenv('APP_PORT', '8000'))
        webbrowser.open(f"http://127.0.0.1:{port}")

    def get_status(self):
        return json.dumps({
            "started": _server_started.is_set(),
            "error": _server_error,
            "log_count": len(_log_buffer),
        }, ensure_ascii=False)


PANEL_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: "Microsoft YaHei", system-ui, sans-serif; background:#1a1a2e; color:#e0e0e0; height:100vh; display:flex; flex-direction:column; }
.header { background:linear-gradient(135deg,#16213e,#0f3460); padding:16px 20px; display:flex; align-items:center; justify-content:space-between; flex-shrink:0; }
.header h1 { font-size:16px; font-weight:600; color:#e94560; }
.header .info { font-size:12px; color:#888; }
.toolbar { display:flex; align-items:center; gap:8px; padding:8px 16px; background:#16213e; border-bottom:1px solid #333; flex-shrink:0; }
.toolbar input { background:#0f3460; border:1px solid #333; color:#ccc; font-size:11px; padding:4px 8px; border-radius:4px; width:180px; outline:none; }
.toolbar input:focus { border-color:#e94560; }
.toolbar select { background:#0f3460; border:1px solid #333; color:#ccc; font-size:11px; padding:4px 6px; border-radius:4px; outline:none; }
.toolbar .count { font-size:11px; color:#666; margin-left:auto; }
.btn { padding:6px 16px; border:none; border-radius:4px; font-size:12px; cursor:pointer; transition:all .15s; }
.btn-primary { background:#e94560; color:#fff; }
.btn-primary:hover { background:#c23050; }
.btn-outline { background:transparent; border:1px solid #444; color:#aaa; }
.btn-outline:hover { border-color:#e94560; color:#e94560; }
#logs { flex:1; overflow-y:auto; font-family:"Cascadia Code","JetBrains Mono","Consolas",monospace; font-size:11.5px; line-height:1.7; padding:8px 12px; }
.log-line { display:flex; gap:8px; padding:1px 4px; border-radius:2px; }
.log-line:hover { background:rgba(255,255,255,.03); }
.ts { color:#555; flex-shrink:0; user-select:none; }
.lv { flex-shrink:0; width:56px; text-align:right; user-select:none; }
.lv-DEBUG { color:#888; } .lv-INFO { color:#4ade80; } .lv-WARNING { color:#fbbf24; } .lv-ERROR { color:#f87171; } .lv-CRITICAL { color:#c084fc; }
.mod { color:rgba(96,165,250,.6); flex-shrink:0; max-width:180px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; user-select:none; }
.msg { color:#d1d5db; word-break:break-all; }
.empty { text-align:center; color:#555; padding:60px 0; }
.status-bar { background:#16213e; border-top:1px solid #333; padding:6px 16px; display:flex; align-items:center; gap:12px; flex-shrink:0; font-size:11px; color:#666; }
.dot { width:8px; height:8px; border-radius:50%; display:inline-block; }
.dot-ok { background:#4ade80; } .dot-err { background:#f87171; } .dot-loading { background:#fbbf24; animation:blink 1s infinite; }
@keyframes blink { 50%{opacity:.3;} }
</style>
</head>
<body>
<div class="header">
  <h1>HH小说创作 启动控制台</h1>
  <div style="display:flex;gap:8px;align-items:center;">
    <button class="btn btn-primary" onclick="openApp()">进入应用</button>
  </div>
</div>
<div class="toolbar">
  <input id="search" placeholder="筛选运行日志…" oninput="render()">
  <select id="levelFilter" onchange="render()">
    <option value="">全部日志级别</option>
    <option value="DEBUG">DEBUG</option>
    <option value="INFO">INFO</option>
    <option value="WARNING">WARNING</option>
    <option value="ERROR">ERROR</option>
  </select>
  <button class="btn btn-outline" onclick="togglePause()" id="pauseBtn">暂停刷新</button>
  <button class="btn btn-outline" onclick="allLogs=[];render()">清空列表</button>
  <span class="count" id="logCount">0 条</span>
</div>
<div id="logs"><div class="empty">正在初始化，请稍候…</div></div>
<div class="status-bar">
  <span class="dot dot-loading" id="statusDot"></span>
  <span id="statusText">正在启动服务…</span>
</div>
<script>
let allLogs = [], lastSeq = 0, paused = false, autoScroll = true;
const logsEl = document.getElementById('logs');

function formatTime(ts) {
  const d = new Date(ts * 1000);
  return d.toTimeString().slice(0,8) + '.' + String(d.getMilliseconds()).padStart(3,'0');
}

function render() {
  const q = document.getElementById('search').value.toLowerCase();
  const lv = document.getElementById('levelFilter').value;
  const filtered = allLogs.filter(e => {
    if (lv && e.level !== lv) return false;
    if (q && !e.msg.toLowerCase().includes(q) && !e.name.toLowerCase().includes(q)) return false;
    return true;
  });
  document.getElementById('logCount').textContent = filtered.length + ' / ' + allLogs.length + ' 条';
  if (filtered.length === 0) {
    logsEl.innerHTML = '<div class="empty">' + (allLogs.length === 0 ? '等待日志输出…' : '没有匹配的日志记录') + '</div>';
    return;
  }
  const html = filtered.slice(-500).map(e =>
    '<div class="log-line">' +
    '<span class="ts">' + formatTime(e.ts) + '</span>' +
    '<span class="lv lv-' + e.level + '">' + e.level + '</span>' +
    '<span class="mod">' + e.name + '</span>' +
    '<span class="msg">' + e.msg.replace(/</g,'&lt;') + '</span>' +
    '</div>'
  ).join('');
  logsEl.innerHTML = html;
  if (autoScroll) logsEl.scrollTop = logsEl.scrollHeight;
}

logsEl.addEventListener('scroll', () => {
  autoScroll = logsEl.scrollHeight - logsEl.scrollTop - logsEl.clientHeight < 40;
});

function togglePause() {
  paused = !paused;
  document.getElementById('pauseBtn').textContent = paused ? '继续刷新' : '暂停刷新';
}

async function poll() {
  if (paused) return;
  try {
    const raw = await pywebview.api.get_logs(lastSeq);
    const entries = JSON.parse(raw);
    if (entries.length > 0) {
      lastSeq = entries[entries.length - 1].seq;
      allLogs.push(...entries);
      if (allLogs.length > 2000) allLogs = allLogs.slice(-2000);
      render();
    }
  } catch(e) {}

  try {
    const raw = await pywebview.api.get_status();
    const st = JSON.parse(raw);
    const dot = document.getElementById('statusDot');
    const txt = document.getElementById('statusText');
    if (st.error) {
      dot.className = 'dot dot-err';
      txt.textContent = '服务启动失败：' + st.error;
    } else if (st.started) {
      dot.className = 'dot dot-ok';
      txt.textContent = '服务运行中';
    }
  } catch(e) {}
}

async function openApp() {
  try { await pywebview.api.open_app(); } catch(e) {}
}

setInterval(poll, 1000);
setTimeout(poll, 500);
</script>
</body>
</html>"""


def main():
    import webview

    try:
        from config_loader import init_config
        init_config()
    except Exception as e:
        print(f"[WARN] 配置加载失败: {e}")

    # 安装日志捕获器（启动阶段用，app 导入后会在 run_server 中重新挂载）
    early_handler = PanelLogHandler()
    early_handler.setLevel(logging.DEBUG)
    logging.getLogger().addHandler(early_handler)

    # 检查数据库
    db_ok, db_error = check_database_connection()
    if not db_ok:
        _log_buffer.append({"seq": 1, "ts": time.time(), "level": "ERROR", "name": "launcher", "msg": db_error})

    port = int(os.getenv('APP_PORT', '8000'))
    host = '127.0.0.1'

    # 创建控制面板窗口
    api = PanelAPI()
    panel = webview.create_window(
        title='HH小说创作 - 启动控制台',
        html=PANEL_HTML,
        width=900,
        height=550,
        min_size=(700, 400),
        resizable=True,
        js_api=api,
    )

    def on_loaded():
        if not db_ok:
            return
        ok, err = start_server_thread(host, port)
        if ok:
            global _log_seq
            _log_seq += 1
            _log_buffer.append({
                "seq": _log_seq, "ts": time.time(), "level": "INFO",
                "name": "launcher", "msg": f"✅ 服务器已启动: http://{host}:{port}"
            })

    panel.events.loaded += on_loaded

    webview.start(debug=False, private_mode=False)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        write_startup_error(e)
        raise
