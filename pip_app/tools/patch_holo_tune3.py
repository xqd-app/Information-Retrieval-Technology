"""调优 3：城市标签只保留前 6（避免欧洲挤成一团）、边缘可见阈值提高、地球左移放大。"""

from pathlib import Path

PATH = Path(__file__).resolve().parent / "build_web.py"
text = PATH.read_text(encoding="utf-8")

edits = [
    # 1) 地球更靠左更大
    ("grid-template-columns:minmax(430px,600px) minmax(0,1fr);\n  align-items:center;gap:10px;",
     "grid-template-columns:minmax(430px,560px) minmax(0,1fr);\n  align-items:center;gap:2px;"),
    # 2) 城市标签：只给前 6 名（其余只画点），避让间距加大
    ("""    const placed = [];
    cities.forEach(c => {
      if(c.city === originCity) return;
      const q = proj(c.lat, c.lon, R);
      if(q[2] <= 0.02) return;""",
     """    const placed = [];
    const labelled = cities.slice(0, 6).map(c => c.city);
    cities.forEach(c => {
      if(c.city === originCity) return;
      const q = proj(c.lat, c.lon, R);
      if(q[2] <= 0.14) return;"""),
    # 3) 非前 6 名只画点不画标签
    ("""      const label = c.city + " " + c.count;
      ctx.font = "11.5px 'Orbitron', ui-monospace, monospace";""",
     """      if(labelled.indexOf(c.city) < 0) return;
      const label = c.city + " " + c.count;
      ctx.font = "11.5px 'Orbitron', ui-monospace, monospace";"""),
    # 4) 避让间距 16 → 22
    ("const clash = placed.some(p => lx < p.x + p.w + 4 && lx + w + 4 > p.x && Math.abs(p.y - ly) < 16);",
     "const clash = placed.some(p => lx < p.x + p.w + 6 && lx + w + 6 > p.x && Math.abs(p.y - ly) < 22);"),
    # 5) 采集端可见阈值
    ("""      const q = proj(o.lat, o.lon, R);
      if(q[2] > 0.02){""",
     """      const q = proj(o.lat, o.lon, R);
      if(q[2] > 0.16){"""),
]

for old, new in edits:
    if old not in text:
        raise SystemExit(f"未找到片段: {old[:70]!r}")
    text = text.replace(old, new, 1)

PATH.write_text(text, encoding="utf-8")
print("patched v1.0 tuning 3")
