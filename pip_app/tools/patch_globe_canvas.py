"""补丁：把假球换成 packetvoyage 数据驱动的真投影 Canvas 地球。

- 数据来自 data/globe.json（build_globe_data.py 用 packetvoyage.geo 生成）
- 正交投影 + 可拖拽旋转 + 缓慢自转
- 大陆用经纬度多边形，弧线用真实大圆航迹（跨太平洋不断线）
- 昼夜按太阳直射点做径向渐变
"""

import re
from pathlib import Path

PATH = Path(__file__).resolve().parent / "build_web.py"
text = PATH.read_text(encoding="utf-8")

# 1) HTML：svg -> canvas
old_svg = '<svg id="globe" viewBox="0 0 620 620" width="620" height="620" aria-label="来源国家分布"></svg>'
new_svg = '<canvas id="globe" width="620" height="620" aria-label="来源城市到采集端的地球投影"></canvas>'
assert old_svg in text
text = text.replace(old_svg, new_svg)

# 2) CSS
old_css = '.globe-stage svg{width:min(100%,760px);height:auto;overflow:visible}'
new_css = ('.globe-stage canvas{width:min(100%,660px);height:auto;display:block;cursor:grab;'
           'touch-action:none}\n.globe-stage canvas:active{cursor:grabbing}')
assert old_css in text
text = text.replace(old_css, new_css)

# 3) 注入 GLOBE 常量
old_data = 'const DATA = __DATA__;\nconst HEALTH = __HEALTH__;'
new_data = 'const DATA = __DATA__;\nconst HEALTH = __HEALTH__;\nconst GLOBE = __GLOBE__;'
assert old_data in text
text = text.replace(old_data, new_data)

# 4) 替换 renderGlobe 整段
NEW_JS = r'''
/* 地球：packetvoyage 数据 + 正交投影 + 可拖拽 */
function renderGlobe(){
  const cv = $("globe");
  if(!cv || !cv.getContext) return;
  const ctx = cv.getContext("2d");
  const SIZE = 620, dpr = Math.min(window.devicePixelRatio || 1, 2);
  cv.width = SIZE * dpr; cv.height = SIZE * dpr;
  cv.style.width = SIZE + "px"; cv.style.height = SIZE + "px";
  ctx.scale(dpr, dpr);

  const cx = SIZE / 2, cy = SIZE / 2, R = SIZE * 0.265, RAD = Math.PI / 180;
  const G = GLOBE || {cities: [], terminator: [], origin: null, solar: {lat: 0, lon: 0}};
  const cities = G.cities || [];
  const maxCount = Math.max(1, ...cities.map(c => c.count));
  const total = cities.reduce((s, c) => s + c.count, 0) || 1;

  let lat0 = 24, lon0 = -20, spin = 0.05, dragging = false, lastX = 0, lastY = 0;

  /* 简化大陆（经纬度多边形，够看出形状即可） */
  const CONTINENTS = [
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

  const proj = (lat, lon) => {
    const p = lat * RAD, l = (lon - lon0) * RAD, p0 = lat0 * RAD;
    const cp = Math.cos(p);
    const x = cp * Math.sin(l);
    const y = Math.cos(p0) * Math.sin(p) - Math.sin(p0) * cp * Math.cos(l);
    const z = Math.sin(p0) * Math.sin(p) + Math.cos(p0) * cp * Math.cos(l);
    return [cx + x * R, cy - y * R, z];
  };

  const solar = G.solar || {lat: 0, lon: 0};
  const [sx, sy, sz] = proj(solar.lat, solar.lon);
  const gx = sz > 0 ? sx : cx + (sx - cx) * -1;
  const gy = sz > 0 ? sy : cy + (sy - cy) * -1;

  let dash = 0, raf = null;
  function draw(){
    ctx.clearRect(0, 0, SIZE, SIZE);

    // 光晕
    const halo = ctx.createRadialGradient(cx, cy, R * 0.9, cx, cy, R * 1.9);
    halo.addColorStop(0, "rgba(92,200,214,.20)");
    halo.addColorStop(1, "rgba(92,200,214,0)");
    ctx.fillStyle = halo;
    ctx.beginPath(); ctx.arc(cx, cy, R * 1.9, 0, Math.PI * 2); ctx.fill();

    // 球体（太阳方向高光，自然形成昼夜）
    const sphere = ctx.createRadialGradient(gx, gy, R * 0.05, cx, cy, R * 1.02);
    sphere.addColorStop(0, "#1b3e60");
    sphere.addColorStop(0.45, "#0d2b46");
    sphere.addColorStop(1, "#040c16");
    ctx.fillStyle = sphere;
    ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.fill();

    // 大陆
    ctx.save();
    ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.clip();
    ctx.lineWidth = 1;
    CONTINENTS.forEach(poly => {
      let started = false;
      ctx.beginPath();
      poly.forEach(([lat, lon]) => {
        const [x, y, z] = proj(lat, lon);
        if(z > 0.02){ started ? ctx.lineTo(x, y) : (ctx.moveTo(x, y), started = true); }
        else { started = false; }
      });
      ctx.strokeStyle = "rgba(56,120,168,.85)";
      ctx.fillStyle = "rgba(18,50,76,.85)";
      ctx.fill(); ctx.stroke();
    });

    // 经纬网
    ctx.strokeStyle = "rgba(47,140,156,.28)";
    ctx.lineWidth = 0.8;
    for(let lon = -180; lon < 180; lon += 30){
      let started = false;
      ctx.beginPath();
      for(let lat = -90; lat <= 90; lat += 3){
        const [x, y, z] = proj(lat, lon);
        if(z > 0){ started ? ctx.lineTo(x, y) : (ctx.moveTo(x, y), started = true); }
        else { started = false; }
      }
      ctx.stroke();
    }
    for(let lat = -60; lat <= 60; lat += 30){
      let started = false;
      ctx.beginPath();
      for(let lon = -180; lon <= 180; lon += 4){
        const [x, y, z] = proj(lat, lon);
        if(z > 0){ started ? ctx.lineTo(x, y) : (ctx.moveTo(x, y), started = true); }
        else { started = false; }
      }
      ctx.stroke();
    }
    ctx.restore();

    // 航迹（大圆）
    cities.forEach(c => {
      const hot = c.count >= maxCount * 0.6;
      ctx.lineWidth = hot ? 2.2 : 1.5;
      ctx.strokeStyle = hot ? "rgba(246,192,106,.95)" : "rgba(92,200,214,.8)";
      ctx.setLineDash([5, 7]);
      ctx.lineDashOffset = -dash;
      let started = false;
      ctx.beginPath();
      (c.arc || []).forEach(([lat, lon]) => {
        const [x, y, z] = proj(lat, lon);
        if(z > 0.02){ started ? ctx.lineTo(x, y) : (ctx.moveTo(x, y), started = true); }
        else { started = false; }
      });
      ctx.stroke();
      ctx.setLineDash([]);
    });

    // 城市点
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
    });

    // 采集端脉冲
    const o = G.origin;
    if(o){
      const [ox, oy, oz] = proj(o.lat, o.lon);
      if(oz > 0.02){
        const pulse = 6 + (Math.sin(dash / 8) + 1) * 5;
        ctx.beginPath(); ctx.arc(ox, oy, pulse, 0, Math.PI * 2);
        ctx.strokeStyle = "rgba(240,240,235,.55)"; ctx.lineWidth = 1.2; ctx.stroke();
        ctx.beginPath(); ctx.arc(ox, oy, 3.4, 0, Math.PI * 2);
        ctx.fillStyle = "#f3ebda"; ctx.fill();
        ctx.fillStyle = "#cfd8e3";
        ctx.font = "11px 'Hanken Grotesk', system-ui, sans-serif";
        ctx.textAlign = "left";
        ctx.fillText("采集端 " + o.city, ox + 9, oy + 4);
      }
    }

    // 球缘 + 统计
    ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.strokeStyle = "rgba(92,200,214,.30)"; ctx.lineWidth = 1; ctx.stroke();

    ctx.fillStyle = "#8a9aae";
    ctx.font = "12px 'Hanken Grotesk', system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(`${cities.length} 城 · ${total} 条 · 拖拽旋转`, cx, cy + R + 30);
  }

  function frame(){
    if(!dragging) lon0 += spin;
    if(lon0 > 180) lon0 -= 360;
    dash += 0.35;
    draw();
    raf = requestAnimationFrame(frame);
  }

  cv.addEventListener("pointerdown", e => { dragging = true; lastX = e.clientX; lastY = e.clientY; cv.setPointerCapture(e.pointerId); });
  cv.addEventListener("pointermove", e => {
    if(!dragging) return;
    lon0 -= (e.clientX - lastX) * 0.35;
    lat0 = Math.max(-70, Math.min(70, lat0 + (e.clientY - lastY) * 0.25));
    lastX = e.clientX; lastY = e.clientY;
  });
  cv.addEventListener("pointerup", () => { dragging = false; });
  cv.addEventListener("pointerleave", () => { dragging = false; });

  if(raf) cancelAnimationFrame(raf);
  raf = requestAnimationFrame(frame);
}
'''

pattern = re.compile(r"/\* 地球：经纬网 \+ 简化大陆 \+ 光柱（长度 = 条目量） \*/.*?(?=\nfunction renderHeroStats)", re.S)
if not pattern.search(text):
    raise SystemExit("未找到 renderGlobe 段")
text = pattern.sub(NEW_JS.strip(), text)

# 5) 调用点改为无参
text = text.replace("renderGlobe(rows); renderHeroStats(rows);", "renderGlobe(); renderHeroStats(rows);")

# 6) build() 注入 GLOBE
old_build = '    health_json = json.dumps({"rows": health}, ensure_ascii=False).replace("</", "<\\\\/")'
new_build = ('    health_json = json.dumps({"rows": health}, ensure_ascii=False).replace("</", "<\\\\/")\n'
             '    globe_file = ROOT / "data" / "globe.json"\n'
             '    globe_json = globe_file.read_text(encoding="utf-8") if globe_file.exists() else "null"')
if old_build not in text:
    raise SystemExit("未找到 health_json 行")
text = text.replace(old_build, new_build)

text = text.replace('        .replace("__HEALTH__", health_json)',
                    '        .replace("__HEALTH__", health_json)\n        .replace("__GLOBE__", globe_json)')

PATH.write_text(text, encoding="utf-8")
print("patched build_web.py -> canvas globe")
