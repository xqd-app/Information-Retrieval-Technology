"""采集端位置的运行期同步。

为什么单独成模块：
    位置的检测与「重建地球/页面」原来只写在 app.py 的启动流程里，
    但真正需要它的是**采集之后**——采集由服务器执行，出口位置可能变
    （换机房、代理切节点、多线 BGP）。所以：
        server 的定时采集任务 → sync(rebuild=True)
        前端轮询 /api/origin → current()（读缓存，不重复打接口）
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config

CACHE = config.DATA_DIR / "geo_self.json"
GLBOE = config.DATA_DIR / "globe.json"
EARTH = config.DATA_DIR / "globe.json"

# 位置变化判定阈值（度）：小于它认为没动，避免每次重建
SAME_EPS = 0.05


def _geo_json() -> dict:
    path = config.DATA_DIR / "globe.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def current() -> dict[str, Any]:
    """当前页面上用的采集端（来自已生成的 globe.json），并标注新鲜度。"""
    payload = _geo_json()
    origin = payload.get("origin") or {}
    detected_at = origin.get("detected_at") or ""
    age = None
    if detected_at:
        try:
            when = datetime.strptime(detected_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            age = int((datetime.now(timezone.utc) - when).total_seconds())
        except ValueError:
            age = None
    return {
        "city": origin.get("city", ""),
        "lat": origin.get("lat"),
        "lon": origin.get("lon"),
        "source": origin.get("source", ""),
        "ip": origin.get("ip", ""),
        "detected_at": detected_at,
        "age_seconds": age,
        "globe_generated_at": payload.get("generated_at", ""),
    }


def detect(*, force: bool = True) -> dict | None:
    """检测本机出口位置（force=True 时忽略缓存）。"""
    try:
        from .tools.detect_location import detect as detect_location

        return detect_location(force=force)
    except Exception:  # noqa: BLE001
        return None


def _same(a: dict | None, b: dict | None) -> bool:
    if not a or not b:
        return False
    if (a.get("city") or "") != (b.get("city") or ""):
        return False
    try:
        return (
            abs(float(a.get("lat", 0)) - float(b.get("lat", 0))) < SAME_EPS
            and abs(float(a.get("lon", 0)) - float(b.get("lon", 0))) < SAME_EPS
        )
    except (TypeError, ValueError):
        return False


def sync(*, rebuild: bool = True, force: bool = True) -> dict[str, Any]:
    """检测当前位置；与页面上的不一致就重建地球与页面。

    返回 {"changed": bool, "before": {...}, "after": {...}}
    """
    before = current()
    info = detect(force=force)
    if not info:
        return {"changed": False, "before": before, "after": before, "reason": "detect-failed"}

    after_probe = {
        "city": info.get("city", ""),
        "lat": info.get("lat"),
        "lon": info.get("lon"),
        "source": f"ip-detected:{info.get('source', '?')}",
        "ip": info.get("ip", ""),
        "detected_at": info.get("detected_at", ""),
    }
    if _same(before, after_probe):
        return {"changed": False, "before": before, "after": before, "reason": "unchanged"}

    if not rebuild:
        return {"changed": True, "before": before, "after": after_probe, "reason": "changed-no-rebuild"}

    try:
        from .tools import build_globe_data, build_web

        build_globe_data.main()
        build_web.build()
    except Exception as exc:  # noqa: BLE001
        return {"changed": True, "before": before, "after": after_probe,
                "reason": f"rebuild-failed: {type(exc).__name__}: {exc}"}

    return {"changed": True, "before": before, "after": current(), "reason": "rebuilt"}


def auto_enabled() -> bool:
    return os.environ.get("PIP_AUTO_ORIGIN", "1") == "1"
