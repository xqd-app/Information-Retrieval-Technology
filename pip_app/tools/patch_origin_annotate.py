"""补丁：角标显示采集端的来源（自动检测 / 手动 / 默认）。"""

from pathlib import Path

PATH = Path(__file__).resolve().parent / "build_web.py"
text = PATH.read_text(encoding="utf-8")

old_hint = ('<div class="globe-hint">坐标：编辑部所在城市（官网核实优先）<br>'
            '轨迹：来源 → 采集端 · 光纤最低 RTT</div>')
new_hint = '<div class="globe-hint" id="globe-hint">轨迹：来源 → 采集端 · 光纤最低 RTT</div>'
assert old_hint in text, "角标未找到"
text = text.replace(old_hint, new_hint, 1)

anchor = "const rows = DATA.items || [];"
assert anchor in text
snippet = """const rows = DATA.items || [];

/* 采集端来源标注：自动检测 / 手动指定 / 默认 */
(function annotateOrigin(){
  const hint = $("globe-hint");
  if(!hint) return;
  const o = (GLOBE && GLOBE.origin) || {};
  const src = String(o.source || "");
  let label;
  if(src.indexOf("ip-detected") === 0){
    label = "采集端：自动检测出口 IP" + (o.ip ? "（" + o.ip + "）" : "");
  } else if(src === "env-city" || src === "env-latlon"){
    label = "采集端：手动指定";
  } else {
    label = "采集端：默认回落";
  }
  hint.innerHTML = label + "<br>实心点 = 官网核实 · 半透明 = 城市级/近似";
})();
"""
text = text.replace(anchor, snippet, 1)

PATH.write_text(text, encoding="utf-8")
print("patched origin annotation")
