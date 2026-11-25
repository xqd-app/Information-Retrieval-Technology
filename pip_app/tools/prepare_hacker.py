"""把兜帽贴图转成透明 PNG（去白底/棋盘格），用于页面左上角。

做法：从四边做 flood fill，只清除「与边缘连通的浅色区域」，
这样被兜帽围住的浅灰色笔记本（不与边缘连通）不会被误删。
"""

from __future__ import annotations

import base64
import io
from collections import deque
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "date" / "images.jpg"
OUT = ROOT / "pip_app" / "web" / "assets" / "hacker.png"
B64 = ROOT / "pip_app" / "web" / "assets" / "hacker.b64.txt"

# 背景判定：够亮且灰（棋盘格的白与浅灰都落在区间内）
LUM_MIN = 205
SAT_MAX = 26


def is_background(px: tuple[int, int, int]) -> bool:
    r, g, b = px[:3]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    sat = max(r, g, b) - min(r, g, b)
    return lum >= LUM_MIN and sat <= SAT_MAX


def strip_background(img: Image.Image) -> Image.Image:
    img = img.convert("RGBA")
    w, h = img.size
    px = img.load()

    seen = bytearray(w * h)
    queue: deque[tuple[int, int]] = deque()

    for x in range(w):
        queue.append((x, 0))
        queue.append((x, h - 1))
    for y in range(h):
        queue.append((0, y))
        queue.append((w - 1, y))

    while queue:
        x, y = queue.popleft()
        if x < 0 or y < 0 or x >= w or y >= h:
            continue
        idx = y * w + x
        if seen[idx]:
            continue
        seen[idx] = 1
        if not is_background(px[x, y]):
            continue
        r, g, b, _ = px[x, y]
        px[x, y] = (r, g, b, 0)
        queue.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

    return img


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"缺少素材：{SRC}")
    img = strip_background(Image.open(SRC))

    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)

    # 统一到 320px 高，保持比例（贴图会再靠 CSS 缩放）
    if img.height > 320:
        ratio = 320 / img.height
        img = img.resize((max(1, round(img.width * ratio)), 320), Image.LANCZOS)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "PNG", optimize=True)

    raw = OUT.read_bytes()
    B64.write_text(base64.b64encode(raw).decode("ascii"), encoding="utf-8")
    print(f"{OUT.name}: {img.width}x{img.height}  {len(raw)/1024:.1f} KB")
    print(f"base64: {len(raw)*4/3/1024:.1f} KB → {B64}")


if __name__ == "__main__":
    main()
