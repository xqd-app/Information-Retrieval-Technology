#!/usr/bin/env python3
"""容器/面板入口（Pterodactyl、Pelican 等要求 PY_FILE 指向一个 .py 文件）。

面板会执行 `python app.py`，并通过环境变量注入端口（SERVER_PORT）。
这里把它翻译成 PIP 自己的配置，然后启动生产服务。

环境变量（面板里可在 Startup 页配）：
    SERVER_PORT      面板注入的端口（优先）
    PIP_PORT         手动指定端口（没注入时用）
    PIP_HOST         默认 0.0.0.0（面板必须对外监听）
    PIP_AUTO_COLLECT 1 = 后台定时采集
    PIP_AUTO_DB      1 = 启动时建库并同步 JSONL（默认开）
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for extra in (ROOT, ROOT / "packetvoyage-master" / "src"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))


def bootstrap_db() -> None:
    """首次启动建库并把仓库里的 JSONL 同步进去（幂等，失败不阻塞启动）。"""
    if os.environ.get("PIP_AUTO_DB", "1") != "1":
        return
    try:
        from pip_app import db, ingest

        conn = db.init()
        conn.commit()
        conn.close()
        result = ingest.sync(days=3)
        ingest.sync_health()
        print(f"[bootstrap] db ready: +{result['inserted']} new / "
              f"{result['updated']} updated / {result['total']} total", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[bootstrap] db skipped: {type(exc).__name__}: {exc}", flush=True)


def main() -> None:
    # 兼容各平台的端口变量：Render/Heroku/Fly 用 PORT，Pterodactyl 用 SERVER_PORT
    port = (
        os.environ.get("PORT")
        or os.environ.get("SERVER_PORT")
        or os.environ.get("PIP_PORT")
        or "8080"
    )
    os.environ.setdefault("PIP_HOST", "0.0.0.0")
    os.environ["PIP_PORT"] = str(port)
    os.environ.setdefault("PIP_LOG_LEVEL", "INFO")

    print(f"[boot] PIP starting on 0.0.0.0:{port}  (cwd={os.getcwd()})", flush=True)
    bootstrap_db()

    from pip_app.server import main as serve

    serve([])


if __name__ == "__main__":
    main()
