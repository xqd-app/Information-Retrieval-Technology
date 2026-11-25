"""补丁：用 Natural Earth 真实海岸线替换手绘大陆轮廓。"""

import re
from pathlib import Path

PATH = Path(__file__).resolve().parent / "build_web.py"
text = PATH.read_text(encoding="utf-8")

# 1) 注入 LAND 常量
old = "const GLOBE = __GLOBE__;"
new = "const GLOBE = __GLOBE__;\nconst LAND = __LAND__;"
assert old in text
text = text.replace(old, new, 1)

# 2) build() 读取 land.json
old_build = '    globe_json = globe_file.read_text(encoding="utf-8") if globe_file.exists() else "null"'
new_build = ('    globe_json = globe_file.read_text(encoding="utf-8") if globe_file.exists() else "null"\n'
             '    land_file = ROOT / "data" / "land.json"\n'
             '    land_json = land_file.read_text(encoding="utf-8") if land_file.exists() else "null"')
assert old_build in text
text = text.replace(old_build, new_build, 1)

old_replace = '        .replace("__GLOBE__", globe_json)'
new_replace = '        .replace("__GLOBE__", globe_json)\n        .replace("__LAND__", land_json)'
assert old_replace in text
text = text.replace(old_replace, new_replace, 1)

# 3) 用 LAND 替换 CONTINENTS 数组（保留一份 fallback）
pattern = re.compile(r"  const CONTINENTS = \[\n(?:.*?\n)*?  \];", re.S)
FALLBACK = r"""  const FALLBACK_LAND = [
    [[70,-160],[72,-120],[68,-90],[60,-64],[47,-52],[36,-75],[25,-80],[15,-95],[20,-110],[30,-125],[50,-132],[60,-145]],
    [[12,-75],[6,-52],[-8,-35],[-24,-47],[-52,-70],[-38,-74],[-18,-77],[-2,-80]],
    [[70,10],[70,40],[58,45],[45,45],[40,28],[36,-6],[43,-9],[56,5],[64,5]],
    [[35,-6],[37,10],[30,33],[11,43],[-5,40],[-25,35],[-35,20],[-26,14],[-10,12],[5,-8],[20,-17],[30,-10]],
    [[76,60],[76,140],[62,162],[45,145],[33,126],[20,120],[9,105],[8,78],[25,68],[40,50],[45,40],[60,40]],
    [[30,70],[22,76],[8,78],[8,72],[20,68],[25,62]],
    [[20,95],[0,105],[-10,120],[-8,136],[5,120],[16,100]],
    [[-10,115],[-12,135],[-25,152],[-38,145],[-34,118],[-28,114]],
    [[60,-45],[80,-45],[83,-30],[60,-20]],
    [[-68,-180],[-68,180],[-88,180],[-88,-180]]
  ];
  const CONTINENTS = (typeof LAND !== "undefined" && LAND && LAND.length) ? LAND : FALLBACK_LAND;"""
if not pattern.search(text):
    raise SystemExit("未找到 CONTINENTS 数组")
text = pattern.sub(lambda _: FALLBACK, text, count=1)

# 4) 经纬网加密：经线 30°→20°，纬线 30°→20°
text = text.replace("for(let lon = -180; lon < 180; lon += 30){", "for(let lon = -180; lon < 180; lon += 20){", 1)
text = text.replace("for(let lat = -60; lat <= 60; lat += 30){", "for(let lat = -80; lat <= 80; lat += 20){", 1)

PATH.write_text(text, encoding="utf-8")
print("patched real coastlines")
