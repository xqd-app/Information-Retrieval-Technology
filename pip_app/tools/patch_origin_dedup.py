"""补丁：采集端（北京）不再重复画城市标签，避免与「采集端 Beijing」叠字。"""

from pathlib import Path

PATH = Path(__file__).resolve().parent / "build_web.py"
text = PATH.read_text(encoding="utf-8")

# 1) 取采集端城市名
old = "  const cities = G.cities || [];"
new = '  const cities = G.cities || [];\n  const originCity = (G.origin && G.origin.city) || "";'
if old not in text:
    raise SystemExit("未找到 cities 定义")
text = text.replace(old, new, 1)

# 2) 城市标签循环跳过采集端
old2 = """    const placed = [];
    cities.forEach(c => {
      const [x, y, z] = proj(c.lat, c.lon);"""
new2 = """    const placed = [];
    cities.forEach(c => {
      if(c.city === originCity) return;  // 采集端由脉冲标记单独绘制
      const [x, y, z] = proj(c.lat, c.lon);"""
if old2 not in text:
    raise SystemExit("未找到城市点循环")
text = text.replace(old2, new2, 1)

PATH.write_text(text, encoding="utf-8")
print("patched origin label dedup")
