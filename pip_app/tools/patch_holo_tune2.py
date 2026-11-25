"""调优 2：初始视角改为大西洋（能看到北美+南美+欧洲+非洲）、面板上移、兜帽轮廓加宽。"""

from pathlib import Path

PATH = Path(__file__).resolve().parent / "build_web.py"
text = PATH.read_text(encoding="utf-8")

edits = [
    # 1) 视角：太平洋 → 大西洋（陆地更完整，接近参考图）
    ("let lat0 = 18, lon0 = -170, spin = 0.05, dragging = false, lastX = 0, lastY = 0;",
     "let lat0 = 24, lon0 = -55, spin = 0.045, dragging = false, lastX = 0, lastY = 0;"),
    # 2) hero 高度略降，面板上移
    ("min-height:clamp(560px,90vh,900px);max-width:1780px;margin:0 auto;",
     "min-height:clamp(540px,78vh,820px);max-width:1780px;margin:0 auto;"),
    # 3) 兜帽：加宽披风轮廓
    ('<path d="M60 10c-20 0-32 14-34 30-1 9-1 17 2 24-6 6-8 14-7 22l6 20c2 7 9 12 16 12h34c7 0 14-5 16-12l6-20c1-8-1-16-7-22 3-7 3-15 2-24C92 24 80 10 60 10z"\n                fill="#061426" stroke="#1d5d7a" stroke-width="1.5"/>',
     '<path d="M60 8c-19 0-31 13-33 29-1 9 0 17 3 24-10 7-17 20-20 36-2 10-3 20-3 27h106c0-7-1-17-3-27-3-16-10-29-20-36 3-7 4-15 3-24C91 21 79 8 60 8z"\n                fill="#051222" stroke="#1d5d7a" stroke-width="1.6"/>'),
    # 4) 矩阵雨再亮一档
    ("#matrix{position:fixed;inset:0;z-index:0;opacity:.55;pointer-events:none}",
     "#matrix{position:fixed;inset:0;z-index:0;opacity:.7;pointer-events:none}"),
]

for old, new in edits:
    if old not in text:
        raise SystemExit(f"未找到片段: {old[:70]!r}")
    text = text.replace(old, new, 1)

PATH.write_text(text, encoding="utf-8")
print("patched v1.0 tuning 2")
