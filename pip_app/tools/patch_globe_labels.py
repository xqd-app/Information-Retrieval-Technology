"""补丁：城市标签做碰撞避让，避免欧洲几个首都挤成一团。"""

from pathlib import Path

PATH = Path(__file__).resolve().parent / "build_web.py"
text = PATH.read_text(encoding="utf-8")

old = """    // 城市点
    cities.forEach(c => {
      const [x, y, z] = proj(c.lat, c.lon);
      if(z <= 0.02) return;
      const hot = c.count >= maxCount * 0.6;
      const r = 2.4 + Math.sqrt(c.count / maxCount) * 4.2;
      ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fillStyle = hot ? "#f6c06a" : "#5cc8d6";
      ctx.fill();
      ctx.strokeStyle = "rgba(7,21,38,.85)"; ctx.lineWidth = 1; ctx.stroke();

      const anchorRight = x < cx;
      ctx.fillStyle = hot ? "#f6c06a" : "#9fb0c2";
      ctx.font = "11.5px 'Hanken Grotesk', system-ui, sans-serif";
      ctx.textAlign = anchorRight ? "left" : "right";
      ctx.fillText(`${c.city} ${c.count}`, anchorRight ? x + r + 6 : x - r - 6, y + 4);
    });"""

new = """    // 城市点（标签做碰撞避让：挤不下就只留点）
    const placed = [];
    cities.forEach(c => {
      const [x, y, z] = proj(c.lat, c.lon);
      if(z <= 0.02) return;
      const hot = c.count >= maxCount * 0.6;
      const r = 2.4 + Math.sqrt(c.count / maxCount) * 4.2;
      ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fillStyle = hot ? "#f6c06a" : "#5cc8d6";
      ctx.fill();
      ctx.strokeStyle = "rgba(7,21,38,.85)"; ctx.lineWidth = 1; ctx.stroke();

      const label = `${c.city} ${c.count}`;
      ctx.font = "11.5px 'Hanken Grotesk', system-ui, sans-serif";
      const w = ctx.measureText(label).width;
      const anchorRight = x < cx;
      const lx = anchorRight ? x + r + 6 : x - r - 6 - w;
      const ly = y - 7;
      const clash = placed.some(p => lx < p.x + p.w + 4 && lx + w + 4 > p.x && Math.abs(p.y - ly) < 13);
      if(clash) return;
      placed.push({x: lx, y: ly, w});
      ctx.fillStyle = hot ? "#f6c06a" : "#9fb0c2";
      ctx.textAlign = "left";
      ctx.fillText(label, lx, y + 4);
    });"""

if old not in text:
    raise SystemExit("未找到城市点段")
PATH.write_text(text.replace(old, new), encoding="utf-8")
print("patched label collision avoidance")
