"""调优 v1.0：点阵密度/亮度、球体提亮、矩阵雨可见度、兜帽剪影移出裁切区。"""

from pathlib import Path

PATH = Path(__file__).resolve().parent / "build_web.py"
text = PATH.read_text(encoding="utf-8")

edits = [
    # 1) 点阵：更亮、更大
    ('const alphas = [0.95, 0.6, 0.28], sizes = [1.9, 1.6, 1.3];',
     'const alphas = [1, 0.78, 0.5], sizes = [2.1, 1.8, 1.5];'),
    # 2) 球体提亮，别把点吃掉
    ('sphere.addColorStop(0, "rgba(46,130,180,.95)");\n    sphere.addColorStop(.45, "rgba(8,34,56,.97)");\n    sphere.addColorStop(1, "rgba(2,8,16,1)");',
     'sphere.addColorStop(0, "rgba(58,152,205,.95)");\n    sphere.addColorStop(.45, "rgba(12,48,78,.97)");\n    sphere.addColorStop(1, "rgba(4,16,28,1)");'),
    # 3) 矩阵雨更可见
    ('#matrix{position:fixed;inset:0;z-index:0;opacity:.30;pointer-events:none}',
     '#matrix{position:fixed;inset:0;z-index:0;opacity:.55;pointer-events:none}'),
    ('let w, h, cols, drops, size = 14;', 'let w, h, cols, drops, size = 16;'),
    ('ctx.fillStyle = Math.random() > 0.94 ? "rgba(190,255,255,.85)" : "rgba(34,211,238,.45)";',
     'ctx.fillStyle = Math.random() > 0.93 ? "rgba(210,255,255,.95)" : "rgba(34,211,238,.62)";'),
    # 4) 兜帽剪影移出 panel（clip-path 会裁掉溢出），放大
    ("""      <div class="hacker">
        <svg viewBox="0 0 120 132" fill="none">""",
     """      <div class="hacker-out">
        <svg viewBox="0 0 120 132" fill="none">"""),
    # 5) legend 挪到地球左下，避免与 SYSTEM ONLINE 冲突
    ('.globe-legend{position:absolute;right:4px;top:8px;text-align:right;',
     '.globe-legend{position:absolute;left:6px;top:6px;text-align:left;'),
]

for old, new in edits:
    if old not in text:
        raise SystemExit(f"未找到片段: {old[:60]!r}")
    text = text.replace(old, new, 1)

# 把 hacker-out 块整体移到 hero 里、panel 之前
import re
m = re.search(r'\n      <div class="hacker-out">.*?\n      </div>\n', text, re.S)
if not m:
    raise SystemExit("未找到 hacker-out 块")
block = m.group(0)
text = text.replace(block, "\n", 1)

hero_open = '<section class="hero">\n'
assert hero_open in text
text = text.replace(hero_open, hero_open + block.strip("\n").replace("      <div", "  <div", 1) + "\n", 1)

# 对应 CSS
old_hacker_css = ('.hacker{position:absolute;left:-6px;top:-34px;width:120px;height:132px;z-index:2;pointer-events:none;\n'
                  '  filter:drop-shadow(0 0 16px rgba(34,211,238,.45))}\n'
                  '.hacker svg{width:100%;height:100%}')
new_hacker_css = ('.hacker-out{position:absolute;left:34px;top:56px;width:150px;height:164px;z-index:6;pointer-events:none;\n'
                  '  filter:drop-shadow(0 0 22px rgba(34,211,238,.55))}\n'
                  '.hacker-out svg{width:100%;height:100%}')
if old_hacker_css in text:
    text = text.replace(old_hacker_css, new_hacker_css, 1)

# 其余响应式里的 .hacker 一并改名
text = text.replace('.hacker{width:96px;height:108px}', '.hacker-out{width:120px;height:132px;left:22px;top:44px}')
text = text.replace('.hacker{display:none}', '.hacker-out{display:none}')

PATH.write_text(text, encoding="utf-8")
print("patched v1.0 tuning")
