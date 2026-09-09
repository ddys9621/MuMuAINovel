"""Embedding 模型首启引导（桌面版启动器调用）

背景：打包 exe 不再内置 470MB 的 embedding 模型（体积减半）。
首次启动时由 start_app.py 调用本模块：
1. 检查本地 embedding 目录是否已有模型
2. 缺失则经 hf-mirror（可用 HF_ENDPOINT 覆盖）自动下载
3. 下载失败 → 返回 False，应用以「无向量记忆」降级模式继续运行
   （memory_service 已支持降级；用户也可手动放置模型后重启）

注意：必须在 import sentence_transformers / memory_service 之前调用，
否则 HF_HUB_OFFLINE 常量固化后无法联网下载。
"""
from __future__ import annotations

import glob
import os
from typing import Callable

MODEL_REPO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_HF_MIRROR = "https://hf-mirror.com"

# 与 memory_service 保持一致的目录计算：app/services → backend（或 exe 的 _internal）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
EMBEDDING_PATH = os.path.join(BASE_DIR, "embedding")

_WEIGHT_PATTERNS = ("model.safetensors", "pytorch_model.bin")


def model_present() -> bool:
    """检查本地是否已有可用模型权重（HF cache 结构 snapshots/<hash>/ 下）。"""
    repo_dir = os.path.join(
        EMBEDDING_PATH, "models--" + MODEL_REPO.replace("/", "--"), "snapshots"
    )
    for name in _WEIGHT_PATTERNS:
        if glob.glob(os.path.join(repo_dir, "*", name)):
            return True
    return False


def ensure_embedding_model(log: Callable[[str, str], None]) -> bool:
    """确保 embedding 模型就绪；缺失则按镜像列表依次尝试下载。

    镜像顺序：HF_ENDPOINT 环境变量（若设）→ hf-mirror → 官方 huggingface.co。
    单个源失败（如镜像超时）自动切换下一个，避免在一个坏源上重试到天荒地老。

    Args:
        log: 日志回调 (level, message)，由启动面板提供

    Returns:
        True = 模型可用；False = 所有源均失败（应用将降级运行）
    """
    if model_present():
        log("INFO", "✅ Embedding 模型已就绪")
        return True

    # 下载阶段必须允许联网；memory_service 稍后 import 时才会强制 OFFLINE。
    # 收紧 HEAD 探测超时（默认 10s×5 重试，坏源上等待过久）
    os.environ.pop("HF_HUB_OFFLINE", None)
    os.environ.pop("TRANSFORMERS_OFFLINE", None)
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "15")

    endpoints: list[str] = []
    for ep in (os.environ.get("HF_ENDPOINT"), DEFAULT_HF_MIRROR, "https://huggingface.co"):
        if ep and ep not in endpoints:
            endpoints.append(ep)

    log("WARNING", "📥 首次运行：本地缺少 AI 记忆模型（约 470MB）")

    from huggingface_hub import snapshot_download

    os.makedirs(EMBEDDING_PATH, exist_ok=True)
    for i, ep in enumerate(endpoints, 1):
        log("INFO", f"⏬ [{i}/{len(endpoints)}] 从 {ep} 下载（视网络约 2-10 分钟）…")
        try:
            # 用 endpoint 参数而非环境变量：hub 的 ENDPOINT 常量在 import 时已固化，
            # 循环中改环境变量不会生效
            snapshot_download(
                MODEL_REPO,
                cache_dir=EMBEDDING_PATH,
                endpoint=ep,
                ignore_patterns=[
                    "*.onnx", "*openvino*", "*.h5", "*.tflite", "*tf_model*", "*.msgpack",
                ],
            )
        except Exception as e:
            log("WARNING", f"⚠️ 该源失败（{type(e).__name__}: {str(e)[:160]}），尝试下一个…")
            continue
        if model_present():
            log("INFO", "✅ Embedding 模型下载完成")
            return True

    log("ERROR", "❌ 所有下载源均失败")
    log("WARNING", "⚠️ 可改选「导入本地模型包」或「跳过」（跳过后语义检索/伏笔追踪不可用，其余功能正常）")
    log("INFO", f"💡 手动修复：把模型文件夹放入 {EMBEDDING_PATH} 后重启；目录结构为 "
                f"models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2/snapshots/<hash>/")
    return False


def import_model_zip(zip_path: str, log: Callable[[str, str], None]) -> bool:
    """从本地 zip 导入模型（离线分发场景：模型包随群文件/网盘单独提供）。

    支持两种压缩包结构：
    1. 顶层为 embedding/models--…（官方离线包结构）→ 解压到 backend 根
    2. 顶层直接是 models--sentence-transformers--…      → 解压到 embedding/

    Returns:
        True = 导入成功且校验通过
    """
    import zipfile

    if not zip_path or not os.path.isfile(zip_path):
        log("ERROR", f"❌ 文件不存在：{zip_path}")
        return False

    log("INFO", f"📦 正在导入模型包：{os.path.basename(zip_path)} …")
    try:
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            # zip-slip 防护：拒绝绝对路径与路径穿越
            for n in names:
                if n.startswith(("/", "\\")) or ".." in n.replace("\\", "/").split("/"):
                    log("ERROR", f"❌ 压缩包含非法路径，已拒绝导入：{n}")
                    return False

            model_prefix = "models--" + MODEL_REPO.replace("/", "--")
            if any(n.replace("\\", "/").startswith("embedding/") for n in names):
                dest = BASE_DIR          # 结构1：包内自带 embedding/ 层
            elif any(n.replace("\\", "/").startswith(model_prefix) for n in names):
                dest = EMBEDDING_PATH    # 结构2：包内直接是 models--… 层
            else:
                log("ERROR", "❌ 压缩包结构不符：应包含 embedding/ 或 "
                             f"{model_prefix}/ 目录")
                return False

            os.makedirs(dest, exist_ok=True)
            zf.extractall(dest)
    except Exception as e:
        log("ERROR", f"❌ 解压失败：{e}")
        return False

    if model_present():
        log("INFO", "✅ 模型导入完成")
        return True
    log("ERROR", "❌ 解压完成但未通过校验（缺少模型权重文件）")
    return False
