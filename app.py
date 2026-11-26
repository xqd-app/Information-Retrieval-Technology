#!/usr/bin/env python3
"""容器/面板入口（Pterodactyl、Pelican 等要求 PY_FILE 指向一个 .py 文件）。

两种部署形态都能跑：
    1. 面板 install script 已经把仓库 clone 到 /home/container → 直接启动
    2. 面板没有 install script（目录里只有这个文件）→ 自己从 GitHub clone，再启动

第二种情况下，你只需要上传这**一个文件**，剩下的代码由 git 拉取；
配合面板的 AUTO_UPDATE=1，以后每次重启都会自动更新。

环境变量：
    SERVER_PORT / PORT   面板注入的端口（优先）
    PIP_PORT             手动指定（没注入时用）
    PIP_HOST             默认 0.0.0.0
    PIP_REPO             覆盖仓库地址
    PIP_AUTO_COLLECT     1 = 后台定时采集
    PIP_AUTO_DB          1 = 启动时建库并同步 JSONL（默认开）
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = os.environ.get(
    "PIP_REPO",
    "https://github.com/xqd-app/Information-Retrieval-Technology.git",
)
BRANCH = os.environ.get("PIP_BRANCH", "main")


def ensure_code() -> None:
    """代码缺失时从 GitHub 拉取（幂等；已有代码则直接返回）。"""
    if (ROOT / "pip_app" / "server.py").exists():
        return

    print(f"[bootstrap] 代码缺失，从 {REPO} 拉取 …", flush=True)

    if shutil.which("git"):
        tmp = Path(tempfile.mkdtemp(prefix="pip-clone-"))
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", "--branch", BRANCH, REPO, str(tmp / "r")],
                check=True,
                timeout=180,
            )
            src = tmp / "r"
        except Exception as exc:  # noqa: BLE001
            print(f"[bootstrap] git clone 失败：{type(exc).__name__}: {exc}", flush=True)
            src = None
        if src and src.exists():
            for item in src.iterdir():
                if item.name == ".git":
                    continue  # 不复制 git 元数据，交给面板的 AUTO_UPDATE 处理
                target = ROOT / item.name
                try:
                    if item.is_dir():
                        shutil.copytree(item, target, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, target)
                except Exception as exc:  # noqa: BLE001
                    print(f"[bootstrap] 复制 {item.name} 失败：{exc}", flush=True)
        shutil.rmtree(tmp, ignore_errors=True)

    if not (ROOT / "pip_app" / "server.py").exists():
        print("[bootstrap] 仍无代码，可能网络不通；请检查容器能否访问 GitHub", flush=True)


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
        print(
            f"[bootstrap] db ready: +{result['inserted']} new / "
            f"{result['updated']} updated / {result['total']} total",
            flush=True,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[bootstrap] db skipped: {type(exc).__name__}: {exc}", flush=True)


def sync_origin() -> None:
    """让「采集端」跟随当前机器的出口位置。

    为什么需要：
        globe.json 与 index.html 都是构建产物，origin 会被一起固化。
        把项目部署到德国服务器后，页面上仍显示构建机的位置（比如 Tokyo），
        与实际执行采集的机器不符。这里在启动时重新检测出口 IP，
        位置变了就按新位置重算地球与页面。
    """
    if os.environ.get("PIP_AUTO_ORIGIN", "1") != "1":
        return
    try:
        from pip_app.tools import detect_location

        previous = detect_location.load_cache(ttl=10 ** 9)  # 忽略 TTL，只读旧值做比较
        info = detect_location.detect(force=True)           # 强制重新测当前出口
        if not info:
            print("[origin] 检测失败，沿用现有位置", flush=True)
            return
        print(
            f"[origin] 本机出口：{info.get('city')} ({info.get('lat')}, {info.get('lon')}) "
            f"via {info.get('source')} ip={info.get('ip')}",
            flush=True,
        )
        same = (
            previous
            and previous.get("city") == info.get("city")
            and round(float(previous.get("lat", 0)), 3) == round(float(info["lat"]), 3)
        )
        if same:
            print("[origin] 位置未变，跳过重建", flush=True)
            return

        from pip_app.tools import build_globe_data, build_web

        build_globe_data.main()
        build_web.build()
        print("[origin] 已按当前机器位置重建地球与页面", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[origin] 同步失败（沿用现有数据）：{type(exc).__name__}: {exc}", flush=True)


def main() -> None:
    ensure_code()

    for extra in (ROOT, ROOT / "packetvoyage-master" / "src"):
        if str(extra) not in sys.path:
            sys.path.insert(0, str(extra))

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
    sync_origin()

    from pip_app.server import main as serve

    serve([])


if __name__ == "__main__":
    main()
