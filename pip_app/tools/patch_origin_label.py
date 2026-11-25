"""补丁：采集端标签移到脉冲圈上方并居中。"""

from pathlib import Path

PATH = Path(__file__).resolve().parent / "build_web.py"
text = PATH.read_text(encoding="utf-8")

old_align = '        ctx.textAlign = "left";\n        ctx.fillText("采集端 " + o.city, ox + 9, oy + 4);'
new_align = '        ctx.textAlign = "center";\n        ctx.fillText("采集端 " + o.city, ox, oy - pulse - 7);'

if old_align not in text:
    raise SystemExit("未找到采集端标签段")

PATH.write_text(text.replace(old_align, new_align), encoding="utf-8")
print("patched origin label")
