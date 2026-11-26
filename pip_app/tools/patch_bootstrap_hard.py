"""加固自举：网络自检、clone 重试、失败时明确退出而不是崩在 import。"""

from pathlib import Path

PATH = Path(__file__).resolve().parent.parent.parent / "app.py"
text = PATH.read_text(encoding="utf-8")

OLD_ENSURE = '''def ensure_code() -> None:
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
                # 连 .git 一起复制：否则目录不是 git 仓库，
                # 面板的 `if [[ -d .git ]]; then git pull` 永远不会执行，
                # AUTO_UPDATE=1 就成了摆设。
                target = ROOT / item.name
                try:
                    if item.is_dir():
                        shutil.copytree(item, target, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, target)
                except Exception as exc:  # noqa: BLE001
                    print(f"[bootstrap] 复制 {item.name} 失败：{exc}", flush=True)
            if (ROOT / ".git").exists():
                print("[bootstrap] 已复制 .git，后续可用 git pull 更新", flush=True)
        shutil.rmtree(tmp, ignore_errors=True)
'''

NEW_ENSURE = '''def code_present() -> bool:
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


def _clone(attempt: int) -> Path | None:
    tmp = Path(tempfile.mkdtemp(prefix="pip-clone-"))
    dest = tmp / "r"
    env = dict(os.environ)
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    env.setdefault("GIT_HTTP_LOW_SPEED_LIMIT", "1000")
    env.setdefault("GIT_HTTP_LOW_SPEED_TIME", "30")
    cmd = ["git", "clone", "--depth", "1", "--branch", BRANCH, REPO, str(dest)]
    print(f"[bootstrap] clone 第 {attempt} 次：{' '.join(cmd)}", flush=True)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=240, env=env)
    except Exception as exc:  # noqa: BLE001
        print(f"[bootstrap] clone 异常：{type(exc).__name__}: {exc}", flush=True)
        return None
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        tail = " / ".join(detail[-2:]) if detail else f"exit {result.returncode}"
        print(f"[bootstrap] clone 失败：{tail[:400]}", flush=True)
        return None
    if not dest.exists():
        print("[bootstrap] clone 返回成功但目录不存在", flush=True)
        return None
    return dest


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
        # 连 .git 一起复制：否则目录不是 git 仓库，
        # 面板的 `if [[ -d .git ]]; then git pull` 永远不会执行。
        try:
            if item.is_dir():
                shutil.copytree(item, ROOT / item.name, dirs_exist_ok=True)
            else:
                shutil.copy2(item, ROOT / item.name)
        except Exception as exc:  # noqa: BLE001
            print(f"[bootstrap] 复制 {item.name} 失败：{exc}", flush=True)
    shutil.rmtree(src.parent, ignore_errors=True)

    ok = code_present()
    if ok:
        print(f"[bootstrap] 代码就绪{'，已复制 .git' if (ROOT / '.git').exists() else ''}", flush=True)
    return ok
'''

assert OLD_ENSURE in text, "ensure_code 段未找到"
text = text.replace(OLD_ENSURE, NEW_ENSURE, 1)

# 主流程：代码不可用就明确退出
old_main = '''def main() -> None:
    ensure_code()
'''
new_main = '''def main() -> None:
    if not ensure_code():
        print("", flush=True)
        print("=" * 68, flush=True)
        print("[fatal] 代码不可用，服务无法启动。", flush=True)
        print("  1. 确认容器能访问 GitHub（上面 [net] 那行的结论）", flush=True)
        print("  2. 或改用上传部署：解压 pip-deploy.tar.gz 到 /home/container", flush=True)
        print("  3. 或设置 PIP_REPO 指向可访问的镜像仓库", flush=True)
        print("=" * 68, flush=True)
        sys.exit(3)
'''
assert old_main in text
text = text.replace(old_main, new_main, 1)

# 需要 time / sys
if "import time" not in text.split("ROOT =")[0]:
    text = text.replace("import tempfile", "import tempfile\nimport time", 1)

PATH.write_text(text, encoding="utf-8")
print("patched app.py bootstrap hardening")
