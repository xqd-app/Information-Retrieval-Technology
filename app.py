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
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = os.environ.get(
    "PIP_REPO",
    "https://github.com/xqd-app/Information-Retrieval-Technology.git",
)
BRANCH = os.environ.get("PIP_BRANCH", "main")


def code_present() -> bool:
    return (ROOT / "pip_app" / "server.py").exists()


def _net_check() -> bool:
    """clone 前先确认容器能访问 GitHub，避免 30 秒超时后一头雾水。"""
    import urllib.request

    url = REPO.replace(".git", "").rstrip("/")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "pip-bootstrap"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            print(f"[net] GitHub 可达（HTTP {resp.status}）", flush=True)
            return True
    except Exception as exc:  # noqa: BLE001
        print(f"[net] GitHub 不可达：{type(exc).__name__}: {exc}", flush=True)
        print("[net] 容器可能被限制出网，或需要配置代理；clone 仍会尝试一次", flush=True)
        return False


# 只取运行所需的目录：仓库里还有 6 个参考项目共 48 MB，全拉下来会撑爆容器磁盘。
# 注意 cone 模式只接受**目录**，根目录下的文件（app.py / requirements.txt）会自动包含。
SPARSE_DIRS = ("pip_app", "pip_skeleton", "packetvoyage-master")
BOOTSTRAP_DIR = ROOT / ".bootstrap-tmp"
MIN_FREE_MB = 120


def _disk_free_mb(path: Path) -> int:
    try:
        return shutil.disk_usage(path).free // (1024 * 1024)
    except OSError:
        return -1


def _run_git(args: list[str], *, timeout: int = 300) -> tuple[bool, str]:
    env = dict(os.environ)
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    env.setdefault("GIT_HTTP_LOW_SPEED_LIMIT", "1000")
    env.setdefault("GIT_HTTP_LOW_SPEED_TIME", "30")
    print(f"[bootstrap] $ git {' '.join(args[:7])}{' …' if len(args) > 7 else ''}", flush=True)
    try:
        result = subprocess.run(["git", *args], capture_output=True, text=True,
                                timeout=timeout, env=env)
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"
    if result.returncode != 0:
        lines = (result.stderr or result.stdout or "").strip().splitlines()
        return False, (" / ".join(lines[-2:])[:400] if lines else f"exit {result.returncode}")
    return True, ""


def _rmtree(path: Path) -> None:
    """删干净（Windows 上偶发文件锁，删两次）。"""
    for _ in range(2):
        if not path.exists():
            return
        shutil.rmtree(path, ignore_errors=True)


def _clone(attempt: int) -> Path | None:
    """clone 到工作目录，而不是 /tmp。

    为什么：Pterodactyl 容器的 /tmp 常是 tmpfs（内存盘，容量很小）。
    仓库 48 MB，正常 clone 会直接 No space left on device。
    所以先尝试「部分克隆 + 稀疏检出」，只下运行需要的约 6 MB。
    """
    dest = BOOTSTRAP_DIR / f"r{attempt}"
    _rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    free = _disk_free_mb(BOOTSTRAP_DIR)
    print(f"[bootstrap] 可用磁盘 {free} MB @ {dest.parent}", flush=True)
    if 0 <= free < MIN_FREE_MB:
        print(f"[bootstrap] 磁盘不足（<{MIN_FREE_MB} MB），放弃 clone", flush=True)
        return None

    ok, err = _run_git(["clone", "--depth", "1", "--branch", BRANCH,
                        "--filter=blob:none", "--sparse", REPO, str(dest)])
    if ok:
        # cone 模式只接受目录；根目录文件会自动包含在检出里
        ok2, err2 = _run_git(["-C", str(dest), "sparse-checkout", "set", *SPARSE_DIRS])
        if ok2 and (dest / "pip_app" / "server.py").exists():
            print("[bootstrap] 稀疏检出完成（仅运行所需目录）", flush=True)
            return dest
        print(f"[bootstrap] sparse-checkout 未成功：{err2 or '缺少 pip_app/server.py'}", flush=True)
        _rmtree(dest)

    print(f"[bootstrap] 回退普通浅克隆（上次：{err[:100]}）", flush=True)
    fallback = BOOTSTRAP_DIR / f"r{attempt}b"
    _rmtree(fallback)
    ok, err = _run_git(["clone", "--depth", "1", "--branch", BRANCH, REPO, str(fallback)])
    if not ok:
        print(f"[bootstrap] clone 失败：{err}", flush=True)
        _rmtree(fallback)
        return None
    return fallback


def ensure_code() -> bool:
    """确保代码就绪。返回 True 表示可以启动。"""
    if code_present():
        return True

    print(f"[bootstrap] 代码缺失，从 {REPO} 拉取（分支 {BRANCH}）…", flush=True)

    if not shutil.which("git"):
        print("[bootstrap] 容器内没有 git 命令，无法自举", flush=True)
        return False

    _net_check()

    src = None
    for attempt in (1, 2):
        src = _clone(attempt)
        if src:
            break
        if attempt == 1:
            print("[bootstrap] 8 秒后重试一次 …", flush=True)
            time.sleep(8)

    if not src:
        print("[bootstrap] clone 两次都失败，代码不可用", flush=True)
        return False

    for item in src.iterdir():
        if item.name == ".bootstrap-tmp":
            continue
        # 连 .git 一起复制：否则目录不是 git 仓库，
        # 面板的 `if [[ -d .git ]]; then git pull` 永远不会执行。
        try:
            if item.is_dir():
                shutil.copytree(item, ROOT / item.name, dirs_exist_ok=True)
            else:
                shutil.copy2(item, ROOT / item.name)
        except Exception as exc:  # noqa: BLE001
            print(f"[bootstrap] 复制 {item.name} 失败：{exc}", flush=True)
    _rmtree(BOOTSTRAP_DIR)   # 清掉临时克隆，省出 30MB

    ok = code_present()
    if ok:
        print(f"[bootstrap] 代码就绪{'，已复制 .git' if (ROOT / '.git').exists() else ''}", flush=True)
    return ok

    if not (ROOT / "pip_app" / "server.py").exists():
        print("[bootstrap] 仍无代码，可能网络不通；请检查容器能否访问 GitHub", flush=True)


def _git(*args: str, timeout: int = 20) -> subprocess.CompletedProcess | None:
    env = dict(os.environ)
    env.setdefault("GIT_TERMINAL_PROMPT", "0")     # 绝不弹交互式认证
    env.setdefault("GIT_HTTP_LOW_SPEED_LIMIT", "1000")  # <1KB/s 持续 10s 即中断
    env.setdefault("GIT_HTTP_LOW_SPEED_TIME", "10")
    env.setdefault("GIT_ASKPASS", "echo")
    try:
        return subprocess.run(
            ["git", "-C", str(ROOT), *args],
            capture_output=True, text=True, timeout=timeout, env=env,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _git_rev() -> str:
    result = _git("rev-parse", "--short", "HEAD", timeout=10)
    return result.stdout.strip() if result and result.returncode == 0 else ""


# 这些是被 git 跟踪的「生成物 / 运行期数据」：
# 每次启动 sync_origin / 采集都会改写它们，导致 git pull 因本地改动而失败。
# 拉取前先丢弃这些改动（都能重新生成，不算数据损失）。
GENERATED_TRACKED = (
    "pip_app/data/globe.json",
    "pip_app/data/source_health.jsonl",
    "pip_app/web/index.html",
)


def sync_code() -> None:
    """每次启动先拉最新代码（仅当目录是 git 仓库时）。

    真正的「自动更新」在这里，而不是面板的 AUTO_UPDATE
    —— 面板那条只在有 .git 时触发，且我们这套自举方式拿不到 .git。
    """
    if os.environ.get("PIP_AUTO_UPDATE", "1") != "1":
        print("[sync] PIP_AUTO_UPDATE=0，跳过代码更新", flush=True)
        return
    if not (ROOT / ".git").exists():
        print("[sync] 非 git 目录（上传部署），跳过代码更新", flush=True)
        return
    if not shutil.which("git"):
        print("[sync] 未找到 git 命令，跳过", flush=True)
        return

    before = _git_rev()
    # 丢弃生成物的本地改动，避免 pull 被挡住
    _git("checkout", "--", *GENERATED_TRACKED, timeout=30)

    result = _git("pull", "--ff-only", timeout=25)
    if result is None:
        print("[sync] git pull 超时或无法执行，继续用现有代码", flush=True)
        return
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        print(f"[sync] git pull 未成功（继续用现有代码）：{detail[-1] if detail else 'unknown'}",
              flush=True)
        return

    after = _git_rev()
    if before and after and before != after:
        print(f"[sync] 代码已更新 {before} → {after}", flush=True)
    else:
        print(f"[sync] 已是最新 ({after or before or 'unknown'})", flush=True)


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
    if not ensure_code():
        print("", flush=True)
        print("=" * 68, flush=True)
        print("[fatal] 代码不可用，服务无法启动。", flush=True)
        print("  1. 确认容器能访问 GitHub（上面 [net] 那行的结论）", flush=True)
        print("  2. 或改用上传部署：解压 pip-deploy.tar.gz 到 /home/container", flush=True)
        print("  3. 或设置 PIP_REPO 指向可访问的镜像仓库", flush=True)
        print("=" * 68, flush=True)
        sys.exit(3)

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
    sync_code()
    bootstrap_db()
    sync_origin()

    from pip_app.server import main as serve

    serve([])


if __name__ == "__main__":
    main()
