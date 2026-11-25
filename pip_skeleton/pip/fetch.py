"""§5.3 采集并发 / 单飞 / 冷却 / 预算。

设计要点：
- 采集不在 HTTP 请求路径内执行（此处只提供可复用的调度原语）
- 单飞：用原子 mkdir 作跨进程锁（Windows/Linux 通用，无需第三方库）
- 冷却：同 domain 手动刷新需 >= cooldown 秒
- 单源失败只影响自己：fetch_one 吞异常并返回结构化 status
"""

from __future__ import annotations

import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

WORKERS = 8
CONNECT_TIMEOUT = 5.0
READ_TIMEOUT = 10.0
GLOBAL_BUDGET = 180.0
DEFAULT_COOLDOWN = 600
RETRIES = 2

OK = "ok"
FAILED = "failed"
ZERO_RESULT = "zero_result"
TIMEOUT = "timeout"
BUSY = "busy"
THROTTLED = "throttled"
PARTIAL = "partial"


@dataclass
class SourceResult:
    name: str
    status: str
    items: int = 0
    error: str = ""
    duration_ms: int = 0


@dataclass
class CollectResult:
    status: str
    sources: list[SourceResult] = field(default_factory=list)
    retry_after: int = 0

    @property
    def failed(self) -> list[SourceResult]:
        return [s for s in self.sources if s.status in (FAILED, TIMEOUT, ZERO_RESULT)]


class SingleFlight:
    """原子 mkdir 锁：拿到锁返回 True，拿不到返回 False（不阻塞）。"""

    def __init__(self, lock_dir: str | os.PathLike[str]) -> None:
        self.path = Path(lock_dir)

    def __enter__(self) -> bool:
        try:
            self.path.mkdir(parents=True, exist_ok=False)
            (self.path / "owner").write_text(str(os.getpid()), encoding="utf-8")
            self.acquired = True
        except FileExistsError:
            self.acquired = False
        return self.acquired

    def __exit__(self, *exc: object) -> None:
        if getattr(self, "acquired", False):
            shutil.rmtree(self.path, ignore_errors=True)


def throttle_remaining(last_refresh: float | None, now: float, cooldown: int = DEFAULT_COOLDOWN) -> int:
    if last_refresh is None:
        return 0
    elapsed = now - last_refresh
    if elapsed >= cooldown:
        return 0
    return int(round(cooldown - elapsed))


def classify(count: int, error: str) -> str:
    if error:
        return TIMEOUT if "timeout" in error.lower() else FAILED
    if count == 0:
        return ZERO_RESULT
    return OK


def collect(
    sources: list[str],
    fetch_one: Callable[[str], tuple[int, str]],
    *,
    workers: int = WORKERS,
    budget: float = GLOBAL_BUDGET,
    clock: Callable[[], float] = time.monotonic,
) -> CollectResult:
    """fetch_one(name) -> (item_count, error)。任何异常都必须由调用方转换为 error 字符串。"""
    deadline = clock() + budget
    results: list[SourceResult] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_timed, name, fetch_one): name for name in sources}
        try:
            for future in as_completed(futures, timeout=budget):
                if clock() > deadline:
                    break
                results.append(future.result())
        except Exception:
            pass  # 预算耗尽：未完成的源在下面统一标记
    done = {r.name for r in results}
    for name in (n for n in futures.values() if n not in done):
        results.append(SourceResult(name=name, status=TIMEOUT, error="global budget exceeded"))
    status = PARTIAL if any(r.status in (FAILED, TIMEOUT, ZERO_RESULT) for r in results) else OK
    return CollectResult(status=status, sources=sorted(results, key=lambda r: r.name))


def _timed(name: str, fetch_one: Callable[[str], tuple[int, str]]) -> SourceResult:
    started = time.perf_counter()
    try:
        count, error = fetch_one(name)
    except Exception as exc:  # 单源异常绝不外溢
        count, error = 0, type(exc).__name__
    return SourceResult(
        name=name,
        status=classify(count, error),
        items=count,
        error=error,
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
