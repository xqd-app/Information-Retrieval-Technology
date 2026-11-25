"""补丁：来源节点 + 状态行 + 角标（按实际文本精确匹配）。"""

from pathlib import Path

PATH = Path(__file__).resolve().parent / "build_web.py"
text = PATH.read_text(encoding="utf-8")

# 1) 城市标签循环之前插入来源节点
anchor = "    const placed = [];"
if "G.sources || []" not in text:
    block = """    // 来源节点（每个源一点；hq=官网核实，city/approx 半透明）
    (G.sources || []).forEach(n => {
      const [nx, ny, nz] = proj(n.lat, n.lon, R);
      if(nz <= 0.02) return;
      const solid = n.precision === "hq";
      ctx.beginPath();
      ctx.arc(nx, ny, solid ? 2.1 : 1.7, 0, Math.PI * 2);
      ctx.fillStyle = solid ? "rgba(165,243,252,.95)" : "rgba(103,232,249,.55)";
      ctx.fill();
    });

"""
    assert anchor in text, "找不到城市标签循环锚点"
    text = text.replace(anchor, block + anchor, 1)

# 2) 状态行
old_status = "ctx.fillText(`${cities.length} NODES · ${total} INTEL · DRAG / SCROLL`, cx, cy + R + 58);"
new_status = (
    "const nodeCount = (G.sources || []).length;\n"
    "    ctx.fillText(`${cities.length} CITIES · ${nodeCount} NODES · ${total} INTEL · DRAG / SCROLL`, cx, cy + R + 58);"
)
assert old_status in text, "状态行未找到"
text = text.replace(old_status, new_status, 1)

# 3) 角标
old_hint = '<div class="globe-hint">轨迹：来源城市 → 采集端<br>实时光纤最低 RTT · RSS</div>'
new_hint = ('<div class="globe-hint">坐标：编辑部所在城市（官网核实优先）<br>'
            '轨迹：来源 → 采集端 · 光纤最低 RTT</div>')
assert old_hint in text, "角标未找到"
text = text.replace(old_hint, new_hint, 1)

PATH.write_text(text, encoding="utf-8")
print("patched source nodes + status + hint")
