"""桥段填充后台任务（进程内）。

为什么要有它：填充一次十几分钟，之前任务寿命 = 一条 SSE 连接，关弹窗 / 刷新 / 切路由就断。
现在填充在独立 asyncio Task + 独立 DB 会话里跑；事件带序号写进任务日志，SSE 端点可从任意
序号回放再续尾；partial / thinking 只保留最新快照（回放时不重播几百条打字机中间态）。

约束：状态只在内存（桌面版单进程）；桥段表 status 仍是唯一持久状态，任务中断 = 当前子批
保持 draft，下次点填充即续跑。同一项目同时只允许一个 running 任务。

事件发布是同步的（publish / finish 不 await）：Python 3.11+ 任务被 cancel 后再 await 会立刻
再次抛 CancelledError，取消路径上必须能无 await 地写下"已停止"事件。
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Optional

from sqlalchemy import select

from app.models.plot_bridge import PlotBridge
from app.services.bridge_planning_service import BridgePlanningService
from app.services.bridge_slot_planner import BridgePlanningConflictError

logger = logging.getLogger(__name__)

# partial / thinking 不进日志，只留最新快照
LIVE_EVENT_TYPES = ("partial", "thinking")
TERMINAL_STATUSES = ("done", "error", "cancelled")
CANCELLED_MESSAGE = "已停止填充；已完成的桥段已保存，再次点击填充可续跑"


@dataclass
class BridgeFillJob:
    id: str
    project_id: str
    user_id: str
    model: Optional[str]
    beat_index: Optional[int]
    status: str = "running"
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    error: Optional[str] = None
    seq: int = 0
    log: list[dict[str, Any]] = field(default_factory=list)
    live: dict[str, dict[str, Any]] = field(default_factory=dict)
    task: Optional[asyncio.Task] = None
    # 每次变更 set 后换一个新 Event：等待方先取引用再 wait，不会漏事件
    _changed: asyncio.Event = field(default_factory=asyncio.Event, repr=False)

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    def snapshot(self) -> dict[str, Any]:
        """给 GET fill-jobs/current：页面挂载时判断是否有任务在跑并恢复横幅。"""
        last_progress = next((e for e in reversed(self.log) if e["type"] == "progress"), None)
        return {
            "id": self.id,
            "project_id": self.project_id,
            "status": self.status,
            "model": self.model,
            "beat_index": self.beat_index,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "elapsed": round((self.finished_at or time.time()) - self.started_at, 1),
            "seq": self.seq,
            "error": self.error,
            "last_progress": last_progress,
            "live": dict(self.live),
        }

    def _notify(self) -> None:
        waiter, self._changed = self._changed, asyncio.Event()
        waiter.set()

    def publish(self, event: dict[str, Any]) -> None:
        self.seq += 1
        event = {**event, "seq": self.seq}
        if event["type"] in LIVE_EVENT_TYPES:
            self.live[event["type"]] = event
        else:
            self.log.append(event)
        self._notify()

    def finish(self, status: str, error: Optional[str] = None) -> None:
        self.status = status
        self.error = error
        self.finished_at = time.time()
        self._notify()


class BridgeFillJobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, BridgeFillJob] = {}

    # ---------------- 查询 ----------------

    def get(self, job_id: str) -> Optional[BridgeFillJob]:
        return self._jobs.get(job_id)

    def current(self, project_id: str) -> Optional[BridgeFillJob]:
        """该项目正在运行的任务（终态不算）。"""
        for job in self._jobs.values():
            if job.project_id == project_id and not job.is_terminal:
                return job
        return None

    # ---------------- 启动 / 取消 ----------------

    async def start(
        self,
        *,
        project_id: str,
        user_id: str,
        ai_service: Any,
        model: Optional[str],
        beat_index: Optional[int],
        session_factory: Callable[[], Any],
        service_factory: Optional[Callable[[Any], Any]] = None,
    ) -> BridgeFillJob:
        """启动任务。session_factory() 须返回可 `async with … as db` 的会话上下文。"""
        if self.current(project_id) is not None:
            raise BridgePlanningConflictError("该项目已有填充任务在运行，请等待完成或先停止")
        job = BridgeFillJob(
            id=str(uuid.uuid4()), project_id=project_id, user_id=user_id, model=model, beat_index=beat_index,
        )
        self._jobs[job.id] = job
        make_service = service_factory or (lambda ai: BridgePlanningService(ai_service=ai))
        job.task = asyncio.create_task(
            self._run(job, ai_service, session_factory, make_service), name=f"bridge-fill:{project_id[:8]}"
        )
        return job

    async def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job is None or job.is_terminal or job.task is None:
            return False
        job.task.cancel()
        try:
            await job.task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001 - 取消路径上的异常已在 _run 内记录
            pass
        if not job.is_terminal:
            # 任务在跑出第一步之前就被取消：_run 的 except 分支没机会执行，这里补终态
            job.publish({"type": "error", "error": CANCELLED_MESSAGE, "code": 499})
            job.finish("cancelled")
        return True

    async def shutdown(self) -> None:
        """应用退出：取消所有运行中的任务（桥段保持 draft，下次续跑）。"""
        for job in list(self._jobs.values()):
            if not job.is_terminal:
                await self.cancel(job.id)

    # ---------------- 事件回放 + 续尾 ----------------

    async def events(self, job_id: str, since: int = 0) -> AsyncIterator[dict[str, Any]]:
        job = self._jobs.get(job_id)
        if job is None:
            yield {"type": "error", "error": "填充任务不存在或已过期", "code": 404, "seq": 0}
            return
        last = since
        while True:
            waiter = job._changed
            pending = [e for e in job.log if e["seq"] > last]
            pending += [e for e in job.live.values() if e["seq"] > last]
            pending.sort(key=lambda e: e["seq"])
            terminal = job.is_terminal
            if not pending:
                if terminal:
                    return
                await waiter.wait()
                continue
            for e in pending:
                yield e
                last = e["seq"]

    # ---------------- runner ----------------

    async def _run(
        self,
        job: BridgeFillJob,
        ai_service: Any,
        session_factory: Callable[[], Any],
        make_service: Callable[[Any], Any],
    ) -> None:
        try:
            async with session_factory() as db:
                total = len((await db.execute(
                    select(PlotBridge.id).where(PlotBridge.project_id == job.project_id, PlotBridge.status == "draft")
                )).scalars().all())
                done_count = 0

                def pct() -> int:
                    return int(done_count / total * 100) if total else 100

                job.publish({"type": "progress", "message": "开始填充桥段内容...", "progress": 1, "status": "processing"})
                service = make_service(ai_service)
                async for evt in service.fill_bridges(db, job.project_id, job.model, job.beat_index):
                    kind = evt["type"]
                    if kind == "beat_start":
                        nums = evt["bridge_numbers"]
                        job.publish({
                            "type": "progress", "status": "processing", "progress": pct(),
                            "message": f"节点 {evt['beat_index']}：生成桥段 {nums[0]}-{nums[-1]}",
                        })
                    elif kind in LIVE_EVENT_TYPES:
                        job.publish(evt)
                    elif kind == "batch_done":
                        done_count += len(evt["bridges"])
                        nums = evt["bridge_numbers"]
                        job.publish({"type": "meta", "beat_index": evt["beat_index"], "bridge_numbers": nums,
                                     "provenance": evt["provenance"]})
                        job.publish({"type": "bridges", "beat_index": evt["beat_index"], "bridges": evt["bridges"]})
                        job.publish({
                            "type": "progress", "status": "processing", "progress": pct(),
                            "message": f"节点 {evt['beat_index']}：桥段 {nums[0]}-{nums[-1]} 已填充（累计 {done_count}/{total}）",
                        })
                    elif kind == "beat_done":
                        job.publish({
                            "type": "progress", "status": "processing", "progress": pct(),
                            "message": f"节点 {evt['beat_index']} 完成（累计 {done_count}/{total}）",
                        })
                    elif kind == "done":
                        job.publish({"type": "result", "data": evt})
                job.publish({"type": "progress", "message": "完成!", "progress": 100, "status": "success"})
                job.publish({"type": "done"})
                job.finish("done")
        except asyncio.CancelledError:
            logger.info("[BridgeFillJob] %s 已取消（当前子批保持 draft）", job.id)
            job.publish({"type": "error", "error": CANCELLED_MESSAGE, "code": 499})
            job.finish("cancelled")
            raise
        except Exception as exc:  # noqa: BLE001 - 统一转 error 事件
            logger.error("[BridgeFillJob] %s 失败: %s", job.id, exc, exc_info=True)
            job.publish({"type": "error", "error": f"桥段填充失败: {exc}", "code": 500})
            job.finish("error", str(exc))


bridge_fill_jobs = BridgeFillJobManager()
