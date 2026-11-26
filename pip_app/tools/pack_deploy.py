"""打包部署产物（排除截图、node_modules、数据库等可重建内容）。

用法：python -m pip_app.tools.pack_deploy
产物：dist/pip-deploy.tar.gz
"""

from __future__ import annotations

import shutil
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DIST = ROOT / "dist"
TARGET = DIST / "pip-deploy.tar.gz"

INCLUDE = [
    "pip_app/__init__.py", "pip_app/config.py", "pip_app/cli.py", "pip_app/collect.py",
    "pip_app/feedparse.py", "pip_app/health_report.py", "pip_app/serve.py", "pip_app/server.py",
    "pip_app/db.py", "pip_app/repo.py", "pip_app/ingest.py", "pip_app/world_scan.py", "pip_app/auth.py", "pip_app/origin.py",
    "pip_app/sources.json", "pip_app/README.md",
    "pip_app/tools/build_globe_data.py", "pip_app/tools/build_dots.py", "pip_app/tools/build_land_data.py",
    "pip_app/tools/build_web.py", "pip_app/tools/detect_location.py", "pip_app/tools/prepare_hacker.py",
    "pip_skeleton",
    "packetvoyage-master/src",
    "deploy",
    "Dockerfile", "docker-compose.yml", "DEPLOY.md",
    "app.py", "requirements.txt",
]

# 数据里只带「重建页面必需」的，历史和截图都不传
INCLUDE_GLOBS = [
    "pip_app/data/items/*.jsonl",
    "pip_app/data/globe.json",
    "pip_app/data/land.json",
    "pip_app/data/land_dots.json",
    "pip_app/data/source_health.jsonl",
    "pip_app/data/geo_self.json",
]

EXCLUDE_PARTS = {
    "__pycache__", "node_modules", ".git", "screens", "_archive", "dist",
    "pip.db", "pip.db-wal", "pip.db-shm", "land_raw_50m.geojson", "land_raw_110m.geojson",
}
EXCLUDE_SUFFIX = {".pyc", ".pyo", ".png", ".jpg", ".docx"}


def _keep(path: Path) -> bool:
    if any(part in EXCLUDE_PARTS for part in path.parts):
        return False
    if path.suffix.lower() in EXCLUDE_SUFFIX:
        return False
    return True


def collect_files() -> list[Path]:
    files: list[Path] = []
    for entry in INCLUDE:
        target = ROOT / entry
        if target.is_file():
            files.append(target)
        elif target.is_dir():
            files.extend(p for p in target.rglob("*") if p.is_file() and _keep(p))
    for pattern in INCLUDE_GLOBS:
        files.extend(p for p in ROOT.glob(pattern) if p.is_file() and _keep(p))
    # web/ 只带 index.html 与贴图
    web = ROOT / "pip_app" / "web"
    for name in ("index.html", "login.html", "assets/hacker.png"):
        p = web / name
        if p.is_file():
            files.append(p)
    return sorted(set(files))


def build() -> Path:
    DIST.mkdir(exist_ok=True)
    files = collect_files()
    with tarfile.open(TARGET, "w:gz") as tar:
        for path in files:
            tar.add(path, arcname=str(path.relative_to(ROOT)))
    size = TARGET.stat().st_size / 1024 / 1024
    print(f"打包 {len(files)} 个文件 → {TARGET}  ({size:.2f} MB)")
    missing = [e for e in INCLUDE if not (ROOT / e).exists()]
    if missing:
        print(f"  ⚠ 缺失：{missing}")
    return TARGET


if __name__ == "__main__":
    build()
