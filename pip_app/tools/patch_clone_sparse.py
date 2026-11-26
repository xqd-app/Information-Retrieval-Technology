"""修 /tmp 空间不足：clone 改到工作目录 + sparse checkout 只拉必需文件。"""

from pathlib import Path

PATH = Path(__file__).resolve().parent.parent.parent / "app.py"
text = PATH.read_text(encoding="utf-8")

OLD = '''def _clone(attempt: int) -> Path | None:
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
        print(f"[bootstrap] clone 返回成功但目录不存在", flush=True)
        return None
    return dest
'''

NEW = '''# 只取运行所需的路径：仓库里还有 6 个参考项目共 48 MB，全都拉下来会撑爆容器磁盘
SPARSE_PATHS = ("pip_app", "pip_skeleton", "packetvoyage-master",
                "app.py", "requirements.txt", "DEPLOY.md", "render.yaml")
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
    print(f"[bootstrap] $ git {' '.join(args[:6])}{' …' if len(args) > 6 else ''}", flush=True)
    try:
        result = subprocess.run(["git", *args], capture_output=True, text=True,
                                timeout=timeout, env=env)
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"
    if result.returncode != 0:
        lines = (result.stderr or result.stdout or "").strip().splitlines()
        return False, " / ".join(lines[-2:])[:400] if lines else f"exit {result.returncode}"
    return True, ""


def _clone(attempt: int) -> Path | None:
    """clone 到工作目录（不是 /tmp —— 那是 tmpfs，常被 48MB 撑爆）。"""
    dest = BOOTSTRAP_DIR / f"r{attempt}"
    shutil.rmtree(dest, ignore_errors=True)
    dest.parent.mkdir(parents=True, exist_ok=True)

    free = _disk_free_mb(BOOTSTRAP_DIR)
    print(f"[bootstrap] 可用磁盘 {free} MB（目录 {dest.parent}）", flush=True)
    if 0 <= free < MIN_FREE_MB:
        print(f"[bootstrap] 磁盘空间不足（<{MIN_FREE_MB} MB），停止尝试", flush=True)
        return None

    # 首选：部分克隆 + 稀疏检出（只下所需文件，约 6 MB）
    ok, err = _run_git(["clone", "--depth", "1", "--branch", BRANCH,
                        "--filter=blob:none", "--sparse", REPO, str(dest)])
    if ok:
        ok2, err2 = _run_git(["-C", str(dest), "sparse-checkout", "set", *SPARSE_PATHS])
        if ok2:
            print("[bootstrap] 稀疏检出完成（只取运行所需文件）", flush=True)
            return dest
        print(f"[bootstrap] sparse-checkout 失败：{err2}", flush=True)
        shutil.rmtree(dest, ignore_errors=True)

    # 回退：普通浅克隆
    print(f"[bootstrap] 改用普通浅克隆（上次失败：{err[:120]}）", flush=True)
    shutil.rmtree(dest, ignore_errors=True)
    ok, err = _run_git(["clone", "--depth", "1", "--branch", BRANCH, REPO, str(dest)])
    if not ok:
        print(f"[bootstrap] clone 失败：{err}", flush=True)
        return None
    return dest
'''

assert OLD in text, "_clone 段未找到"
text = text.replace(OLD, NEW, 1)

# 复制时排除自举临时目录
old_copy = '''    for item in src.iterdir():
        # 连 .git 一起复制：否则目录不是 git 仓库，
        # 面板的 `if [[ -d .git ]]; then git pull` 永远不会执行。
        try:'''
new_copy = '''    for item in src.iterdir():
        if item.name == ".bootstrap-tmp":
            continue
        # 连 .git 一起复制：否则目录不是 git 仓库，
        # 面板的 `if [[ -d .git ]]; then git pull` 永远不会执行。
        try:'''
assert old_copy in text
text = text.replace(old_copy, new_copy, 1)

# 复制完清理自举目录
old_clean = '    shutil.rmtree(src.parent, ignore_errors=True)'
new_clean = '    shutil.rmtree(BOOTSTRAP_DIR, ignore_errors=True)   # 清掉 48MB 的临时克隆'
assert old_clean in text
text = text.replace(old_clean, new_clean, 1)

# 不再需要 tempfile
if "tempfile" in text and "tempfile.mkdtemp" not in text.replace("import tempfile", ""):
    text = text.replace("import tempfile\n", "", 1)

PATH.write_text(text, encoding="utf-8")
print("patched app.py: clone 到工作目录 + sparse checkout")
