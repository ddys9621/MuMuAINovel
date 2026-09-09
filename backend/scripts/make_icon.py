"""从 frontend/public/logo.svg 生成品牌图标。

产物：
- backend/assets/app.ico        Windows 应用图标（exe / 启动控制台窗口 / 安装包），16~256 多尺寸
- frontend/public/favicon.ico   网页 favicon 兜底（index.html 首选 logo.svg）

用法（backend 目录下）：
    .venv\\Scripts\\python.exe scripts\\make_icon.py

不引入新依赖：借 pywebview（Edge WebView2）把 SVG 按各尺寸原生栅格化到 canvas 导出 PNG，
再用 Pillow 合成 ICO。改了 logo.svg 后重跑一次即可。
"""
import base64
import json
import sys
import time
from io import BytesIO
from pathlib import Path

import webview
from PIL import Image

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
SVG_PATH = PROJECT_ROOT / 'frontend' / 'public' / 'logo.svg'
APP_ICO = BACKEND_DIR / 'assets' / 'app.ico'
FAVICON_ICO = PROJECT_ROOT / 'frontend' / 'public' / 'favicon.ico'

APP_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
WEB_SIZES = (16, 32, 48)

RENDER_JS = """
(function () {
  window.__icons = null;
  var sizes = %s;
  var img = new Image();
  img.onload = function () {
    var out = {};
    sizes.forEach(function (s) {
      var c = document.createElement('canvas');
      c.width = s; c.height = s;
      var ctx = c.getContext('2d');
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = 'high';
      ctx.drawImage(img, 0, 0, s, s);
      out[s] = c.toDataURL('image/png').split(',')[1];
    });
    window.__icons = out;
  };
  img.onerror = function () { window.__icons = { error: 'svg load failed' }; };
  img.src = 'data:image/svg+xml;base64,%s';
})();
"""


def _render(window):
    svg_b64 = base64.b64encode(SVG_PATH.read_bytes()).decode('ascii')
    window.evaluate_js(RENDER_JS % (json.dumps(sorted(set(APP_SIZES + WEB_SIZES))), svg_b64))

    deadline = time.time() + 20
    result = None
    while time.time() < deadline:
        raw = window.evaluate_js('JSON.stringify(window.__icons)')
        if raw and raw != 'null':
            result = json.loads(raw)
            break
        time.sleep(0.1)

    try:
        if result is None:
            raise RuntimeError('渲染超时：WebView 未返回图标数据')
        if 'error' in result:
            raise RuntimeError(result['error'])

        frames = {int(k): Image.open(BytesIO(base64.b64decode(v))).convert('RGBA') for k, v in result.items()}
        _save_ico(frames, APP_SIZES, APP_ICO)
        _save_ico(frames, WEB_SIZES, FAVICON_ICO)
    except Exception as e:
        print(f'[ERROR] {e}', file=sys.stderr)
        window._make_icon_failed = True
    finally:
        window.destroy()


def _save_ico(frames, sizes, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = [frames[s] for s in sorted(sizes, reverse=True)]
    ordered[0].save(path, format='ICO', sizes=[(s, s) for s in sizes], append_images=ordered[1:])
    print(f'[OK] {path.relative_to(PROJECT_ROOT)}  sizes={list(sizes)}  {path.stat().st_size / 1024:.1f} KB')


def main():
    if not SVG_PATH.exists():
        sys.exit(f'找不到 {SVG_PATH}')
    window = webview.create_window(
        '生成图标…',
        html='<body style="margin:0;font:13px system-ui;display:flex;align-items:center;justify-content:center;height:100vh;color:#5f7090">正在从 logo.svg 生成图标…</body>',
        width=320, height=120, resizable=False,
    )
    webview.start(_render, window)
    if getattr(window, '_make_icon_failed', False):
        sys.exit(1)


if __name__ == '__main__':
    main()
