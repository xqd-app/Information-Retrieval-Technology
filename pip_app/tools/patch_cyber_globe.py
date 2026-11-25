"""补丁 B：地球赛博化（外环 / 全息平台 / 呼吸节点 / 流动粒子 / 缩放）+ 修文案重复。"""

import re
from pathlib import Path

PATH = Path(__file__).resolve().parent / "build_web.py"
text = PATH.read_text(encoding="utf-8")

# ---------- 1) 修「5 个国家 个国家」重复 ----------
old_lede = 'if(ledeCountries) ledeCountries.textContent = `${countries} 个国家`;'
new_lede = 'if(ledeCountries) ledeCountries.textContent = String(countries);'
if old_lede not in text:
    raise SystemExit("未找到 lede 文案")
text = text.replace(old_lede, new_lede)

# ---------- 2) 替换 renderGlobe ----------
NEW_GLOBE = r'''/* 地球：packetvoyage 数据 + 正交投影 + 旋转/缩放 + HUD 外环与全息平台 */
function renderGlobe(){
  const cv = $("globe");
  if(!cv || !cv.getContext) return;
  const ctx = cv.getContext("2d");
  const SIZE = 740, dpr = Math.min(window.devicePixelRatio || 1, 2);
  cv.width = SIZE * dpr; cv.height = SIZE * dpr;
  cv.style.width = SIZE + "px"; cv.style.height = SIZE + "px";
  ctx.scale(dpr, dpr);

  const cx = SIZE / 2, cy = SIZE / 2 - 6, RAD = Math.PI / 180;
  let zoom = 1;
  const R0 = SIZE * 0.255;

  const G = GLOBE || {cities: [], terminator: [], origin: null, solar: {lat: 0, lon: 0}};
  const cities = G.cities || [];
  const maxCount = Math.max(1, ...cities.map(c => c.count));
  const total = cities.reduce((s, c) => s + c.count, 0) || 1;
  const originCity = (G.origin && G.origin.city) || "";

  let lat0 = 20, lon0 = -170, spin = 0.055, dragging = false, lastX = 0, lastY = 0;

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

  const proj = (lat, lon, R) => {
    const p = lat * RAD, l = (lon - lon0) * RAD, p0 = lat0 * RAD;
    const cp = Math.cos(p);
    const x = cp * Math.sin(l);
    const y = Math.cos(p0) * Math.sin(p) - Math.sin(p0) * cp * Math.cos(l);
    const z = Math.sin(p0) * Math.sin(p) + Math.cos(p0) * cp * Math.cos(l);
    return [cx + x * R, cy - y * R, z];
  };

  let t = 0;
  function draw(){
    const R = R0 * zoom;
    ctx.clearRect(0, 0, SIZE, SIZE);

    /* 外圈 HUD：刻度 + 双扫描弧 */
    const outer = R + 26;
    ctx.save();
    ctx.translate(cx, cy);
    ctx.strokeStyle = "rgba(34,211,238,.22)";
    ctx.lineWidth = 1;
    for(let i = 0; i < 72; i++){
      const a = (i / 72) * Math.PI * 2 + t * 0.004;
      const long = i % 6 === 0;
      const r1 = outer + 6, r2 = outer + (long ? 15 : 10);
      ctx.beginPath();
      ctx.moveTo(Math.cos(a) * r1, Math.sin(a) * r1);
      ctx.lineTo(Math.cos(a) * r2, Math.sin(a) * r2);
      ctx.stroke();
    }
    const sweep = (offset, color, width) => {
      ctx.beginPath();
      ctx.arc(0, 0, outer + 2, t * 0.012 + offset, t * 0.012 + offset + 1.15);
      ctx.strokeStyle = color; ctx.lineWidth = width; ctx.stroke();
    };
    sweep(0, "rgba(103,232,249,.65)", 2);
    sweep(Math.PI * 0.9, "rgba(34,211,238,.35)", 1.2);
    ctx.restore();

    /* 全息平台（球下方） */
    const py = cy + R * 0.92, rx = R * 1.18, ry = R * 0.22;
    for(let i = 0; i < 3; i++){
      ctx.beginPath();
      ctx.ellipse(cx, py + i * 9, rx - i * 12, ry - i * 3, 0, 0, Math.PI * 2);
      ctx.strokeStyle = i === 0 ? "rgba(34,211,238,.42)" : "rgba(34,211,238,.16)";
      ctx.lineWidth = i === 0 ? 1.4 : 1;
      ctx.stroke();
    }
    const plat = ctx.createRadialGradient(cx, py, 4, cx, py, rx);
    plat.addColorStop(0, "rgba(34,211,238,.20)");
    plat.addColorStop(1, "rgba(34,211,238,0)");
    ctx.fillStyle = plat;
    ctx.beginPath(); ctx.ellipse(cx, py, rx, ry, 0, 0, Math.PI * 2); ctx.fill();

    /* 球体 */
    const halo = ctx.createRadialGradient(cx, cy, R * 0.92, cx, cy, R * 1.6);
    halo.addColorStop(0, "rgba(34,211,238,.16)");
    halo.addColorStop(1, "rgba(34,211,238,0)");
    ctx.fillStyle = halo;
    ctx.beginPath(); ctx.arc(cx, cy, R * 1.6, 0, Math.PI * 2); ctx.fill();

    const solar = G.solar || {lat: 0, lon: 0};
    const [sx, sy, sz] = proj(solar.lat, solar.lon, R);
    const gx = sz > 0 ? sx : cx + (sx - cx) * -1;
    const gy = sz > 0 ? sy : cy + (sy - cy) * -1;

    const sphere = ctx.createRadialGradient(gx, gy, R * 0.04, cx, cy, R * 1.04);
    sphere.addColorStop(0, "rgba(41,110,160,.92)");
    sphere.addColorStop(0.5, "rgba(10,38,60,.96)");
    sphere.addColorStop(1, "rgba(3,10,18,1)");
    ctx.fillStyle = sphere;
    ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.fill();

    /* 大陆 + 网格 */
    ctx.save();
    ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.clip();
    CONTINENTS.forEach(poly => {
      let started = false;
      ctx.beginPath();
      poly.forEach(([lat, lon]) => {
        const [x, y, z] = proj(lat, lon, R);
        if(z > 0.02){ started ? ctx.lineTo(x, y) : (ctx.moveTo(x, y), started = true); }
        else { started = false; }
      });
      ctx.strokeStyle = "rgba(56,140,190,.75)";
      ctx.fillStyle = "rgba(14,48,74,.55)";
      ctx.lineWidth = 1;
      ctx.fill(); ctx.stroke();
    });

    ctx.strokeStyle = "rgba(34,211,238,.16)";
    ctx.lineWidth = 0.8;
    for(let lon = -180; lon < 180; lon += 30){
      let started = false;
      ctx.beginPath();
      for(let lat = -90; lat <= 90; lat += 3){
        const [x, y, z] = proj(lat, lon, R);
        if(z > 0){ started ? ctx.lineTo(x, y) : (ctx.moveTo(x, y), started = true); }
        else { started = false; }
      }
      ctx.stroke();
    }
    for(let lat = -60; lat <= 60; lat += 30){
      let started = false;
      ctx.beginPath();
      for(let lon = -180; lon <= 180; lon += 4){
        const [x, y, z] = proj(lat, lon, R);
        if(z > 0){ started ? ctx.lineTo(x, y) : (ctx.moveTo(x, y), started = true); }
        else { started = false; }
      }
      ctx.stroke();
    }
    ctx.restore();

    /* 航迹 + 流动粒子 */
    cities.forEach((c, ci) => {
      const hot = c.count >= maxCount * 0.6;
      ctx.lineWidth = hot ? 2 : 1.4;
      ctx.strokeStyle = hot ? "rgba(251,191,36,.9)" : "rgba(103,232,249,.65)";
      ctx.setLineDash([4, 8]);
      ctx.lineDashOffset = -t * 1.6;
      const pts = [];
      let started = false;
      ctx.beginPath();
      (c.arc || []).forEach(([lat, lon]) => {
        const [x, y, z] = proj(lat, lon, R);
        if(z > 0.02){ started ? ctx.lineTo(x, y) : (ctx.moveTo(x, y), started = true); }
        else { started = false; }
        if(z > 0.02) pts.push([x, y]);
      });
      ctx.stroke();
      ctx.setLineDash([]);

      /* 沿轨迹流动的高亮点 */
      if(pts.length > 4){
        const k = ((t * 0.9 + ci * 13) % 40) / 40;
        const idx = Math.floor(k * (pts.length - 1));
        const [px, py] = pts[idx];
        const glow = ctx.createRadialGradient(px, py, 0, px, py, hot ? 9 : 6);
        glow.addColorStop(0, hot ? "rgba(253,224,71,1)" : "rgba(165,243,252,1)");
        glow.addColorStop(1, "rgba(34,211,238,0)");
        ctx.fillStyle = glow;
        ctx.beginPath(); ctx.arc(px, py, hot ? 9 : 6, 0, Math.PI * 2); ctx.fill();
      }
    });

    /* 城市节点（呼吸） */
    const placed = [];
    cities.forEach(c => {
      if(c.city === originCity) return;
      const [x, y, z] = proj(c.lat, c.lon, R);
      if(z <= 0.02) return;
      const hot = c.count >= maxCount * 0.6;
      const breathe = 1 + Math.sin(t * 0.16 + c.count) * 0.18;
      const r = (2.2 + Math.sqrt(c.count / maxCount) * 3.8) * breathe;

      ctx.beginPath(); ctx.arc(x, y, r * 2.6, 0, Math.PI * 2);
      ctx.fillStyle = hot ? "rgba(251,191,36,.12)" : "rgba(34,211,238,.10)";
      ctx.fill();
      ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fillStyle = hot ? "#fbbf24" : "#67e8f9";
      ctx.fill();
      ctx.strokeStyle = "rgba(3,10,18,.9)"; ctx.lineWidth = 1; ctx.stroke();

      const label = `${c.city} ${c.count}`;
      ctx.font = "11px 'JetBrains Mono', ui-monospace, monospace";
      const w = ctx.measureText(label).width;
      const anchorRight = x < cx;
      const lx = anchorRight ? x + r + 6 : x - r - 6 - w;
      const ly = y - 7;
      const clash = placed.some(p => lx < p.x + p.w + 4 && lx + w + 4 > p.x && Math.abs(p.y - ly) < 13);
      if(clash) return;
      placed.push({x: lx, y: ly, w});
      ctx.fillStyle = hot ? "#fcd34d" : "#a5f3fc";
      ctx.textAlign = "left";
      ctx.fillText(label, lx, y + 4);
    });

    /* 采集端 */
    const o = G.origin;
    if(o){
      const [ox, oy, oz] = proj(o.lat, o.lon, R);
      if(oz > 0.02){
        const pulse = 6 + (Math.sin(t * 0.12) + 1) * 5;
        ctx.beginPath(); ctx.arc(ox, oy, pulse, 0, Math.PI * 2);
        ctx.strokeStyle = "rgba(52,211,153,.6)"; ctx.lineWidth = 1.3; ctx.stroke();
        ctx.beginPath(); ctx.arc(ox, oy, 3.4, 0, Math.PI * 2);
        ctx.fillStyle = "#34d399"; ctx.fill();
        ctx.fillStyle = "#a7f3d0";
        ctx.font = "10.5px 'JetBrains Mono', ui-monospace, monospace";
        ctx.textAlign = "center";
        ctx.fillText("采集端 " + o.city, ox, oy - pulse - 7);
      }
    }

    /* 球缘 + 状态行 */
    ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.strokeStyle = "rgba(103,232,249,.45)"; ctx.lineWidth = 1.2; ctx.stroke();

    ctx.fillStyle = "#4d7188";
    ctx.font = "10.5px 'JetBrains Mono', ui-monospace, monospace";
    ctx.textAlign = "center";
    ctx.fillText(`${cities.length} NODES · ${total} INTEL · DRAG / SCROLL`, cx, cy + R + 58);
  }

  let raf = null;
  function frame(){
    if(!dragging) lon0 += spin;
    if(lon0 > 180) lon0 -= 360;
    t += 1;
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
  cv.addEventListener("wheel", e => {
    e.preventDefault();
    zoom = Math.max(0.72, Math.min(1.45, zoom - e.deltaY * 0.0012));
  }, {passive: false});

  if(raf) cancelAnimationFrame(raf);
  raf = requestAnimationFrame(frame);
}
'''

pattern = re.compile(r"/\* 地球：packetvoyage 数据 \+ 正交投影 \+ 可拖拽 \*/.*?(?=\nfunction renderHeroStats)", re.S)
if not pattern.search(text):
    raise SystemExit("未找到 renderGlobe 段")
text = pattern.sub(lambda _: NEW_GLOBE.strip(), text, count=1)

# ---------- 3) hero-stats 加图标 ----------
old_stats = '''  $("hero-stats").innerHTML = stats.map(([k, v]) =>
    `<div class="stat"><b>${v}</b><span>${k}</span></div>`).join("");'''
new_stats = '''  const icons = ["FEED", "GEO", "INTEL", "ZH"];
  $("hero-stats").innerHTML = stats.map(([k, v], i) =>
    `<div class="stat"><span class="ico">${icons[i] || "DATA"}</span><b>${v}</b><span>${k}</span></div>`).join("");'''
if old_stats not in text:
    raise SystemExit("未找到 hero-stats 渲染")
text = text.replace(old_stats, new_stats)

PATH.write_text(text, encoding="utf-8")
print("patched cyber globe + stats")
