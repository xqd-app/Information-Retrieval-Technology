"""微调：hero 高度自适应（1366 也能看到 tabs 与面板入口）+ 弱化扫描弧。"""

from pathlib import Path

PATH = Path(__file__).resolve().parent / "build_web.py"
text = PATH.read_text(encoding="utf-8")

edits = [
    (
        ".hero{position:relative;min-height:min(94vh,880px);display:grid;",
        ".hero{position:relative;min-height:clamp(540px,74vh,800px);display:grid;",
    ),
    (
        '    sweep(0, "rgba(103,232,249,.65)", 2);\n    sweep(Math.PI * 0.9, "rgba(34,211,238,.35)", 1.2);',
        '    sweep(0, "rgba(103,232,249,.42)", 1.6);\n    sweep(Math.PI * 0.9, "rgba(34,211,238,.22)", 1);',
    ),
]

for old, new in edits:
    if old not in text:
        raise SystemExit(f"未找到片段: {old[:48]!r}")
    text = text.replace(old, new, 1)

PATH.write_text(text, encoding="utf-8")
print("patched hero height + sweep")
