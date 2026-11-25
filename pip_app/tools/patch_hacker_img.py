"""把左上角手绘 SVG 换成透明贴图（base64 内联，保持单文件）。"""

import re
from pathlib import Path

PATH = Path(__file__).resolve().parent / "build_web.py"
text = PATH.read_text(encoding="utf-8")

# 1) 用 <img> 替换整块 SVG
pattern = re.compile(r'  <div class="hacker-out">\s*<svg.*?</svg>\s*</div>', re.S)
if not pattern.search(text):
    raise SystemExit("未找到 hacker-out 块")
text = pattern.sub(
    lambda _: '  <img class="hacker-out" src="data:image/png;base64,__HACKER__" alt=""/>',
    text,
    count=1,
)

# 2) CSS 适配 img
old_css = ('.hacker-out{position:absolute;left:34px;top:56px;width:150px;height:164px;z-index:6;pointer-events:none;\n'
           '  filter:drop-shadow(0 0 22px rgba(34,211,238,.55))}\n'
           '.hacker-out svg{width:100%;height:100%}')
new_css = ('.hacker-out{position:absolute;left:26px;top:26px;width:158px;height:200px;z-index:6;pointer-events:none;\n'
           '  object-fit:contain;object-position:top left;\n'
           '  filter:drop-shadow(0 0 24px rgba(34,211,238,.5)) drop-shadow(0 0 60px rgba(34,211,238,.22))}')
if old_css in text:
    text = text.replace(old_css, new_css, 1)
else:
    # 兜底：直接改选择器属性
    text = text.replace('width:150px;height:164px;z-index:6', 'width:158px;height:200px;z-index:6', 1)
    text = text.replace('.hacker-out svg{width:100%;height:100%}', '.hacker-out{object-fit:contain}', 1)

# 3) build() 注入 base64
old_build = '    dots_json = _read_json(ROOT / "data" / "land_dots.json", "[]")'
new_build = ('    dots_json = _read_json(ROOT / "data" / "land_dots.json", "[]")\n'
             '    hacker_b64 = _read_json(ROOT / "web" / "assets" / "hacker.b64.txt", "")')
assert old_build in text
text = text.replace(old_build, new_build, 1)

old_replace = '        .replace("__LAND_DOTS__", dots_json)'
new_replace = '        .replace("__LAND_DOTS__", dots_json)\n        .replace("__HACKER__", hacker_b64)'
assert old_replace in text
text = text.replace(old_replace, new_replace, 1)

# 4) 响应式尺寸
text = text.replace('.hacker-out{width:120px;height:132px;left:22px;top:44px}',
                    '.hacker-out{width:120px;height:152px;left:14px;top:18px}')

PATH.write_text(text, encoding="utf-8")
print("patched hacker image")
