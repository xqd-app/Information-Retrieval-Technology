"""把当日采集结果渲染成单文件 HTML（v0.7：以 Packet Voyage /report 版式为主）。

版式（对照 packets.simplyzee.dev/report）：
- 首屏 hero：左上米黄纸卡（标题 / 内部导航 / 一句话摘要 / 主按钮）+ 右侧大幅地球
- 地球光柱长度 = 该国条目量，琥珀色为条目最多的国家
- 左下胶囊切换：条目 / 分布 / 健康（对应 PV 的 Speed / Your data / Route）
- hero 下方是内容面板：横排筛选条 + 列表 / 分布 / 健康
数据内联，file:// 直接打开可用。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))

from pip_app.health_report import load_rows, summarize  # noqa: E402

ITEMS_DIR = ROOT / "data" / "items"
HEALTH_FILE = ROOT / "data" / "source_health.jsonl"
SOURCES_FILE = ROOT / "sources.json"
OUT_FILE = ROOT / "web" / "index.html"


def latest_items_path() -> Path:
    files = sorted(ITEMS_DIR.glob("*.jsonl"))
    return files[-1] if files else ITEMS_DIR / "2026-11-24.jsonl"


TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>PIP 情报日报 · __DATE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Young+Serif&family=Hanken+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{
  --abyss:#071526; --deep:#0f2740; --paper:#f3ebda; --paper-edge:#dccfb4;
  --ink:#1f2a37; --ink-soft:#5b6573; --amber:#e09a2b; --amber-glow:#f6c06a;
  --sea:#2f8c9c; --sea-bright:#5cc8d6; --fog:#8a9aae;
  --serif:"Young Serif", Georgia, "Songti SC", "SimSun", serif;
  --sans:"Hanken Grotesk", Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  --rule:rgba(31,42,55,.16);
  --ai:#7b56d9; --geo:#0f9f8f; --skills:#2f6fed; --oss:#c9891a;
  font-family:var(--sans);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0;min-height:100%;color:var(--paper);font-size:14px;line-height:1.6;
  background:
    radial-gradient(1200px 700px at 78% 6%, #143556 0%, rgba(20,53,86,0) 58%),
    radial-gradient(900px 600px at 4% 100%, #0d2b46 0%, rgba(13,43,70,0) 62%),
    var(--abyss);
  background-attachment:fixed;
}
a{color:inherit;text-decoration:none}
::selection{background:rgba(224,154,43,.35)}

/* ============ HERO ============ */
.hero{position:relative;min-height:min(94vh,860px);display:grid;grid-template-columns:minmax(360px,470px) minmax(0,1fr);
  gap:24px;align-items:center;padding:44px 26px 90px;max-width:1560px;margin:0 auto}
.paper{background:linear-gradient(180deg,#f8f1e2 0%,#f3ebda 44%,#eee4cf 100%);
  color:var(--ink);border:1px solid var(--paper-edge);border-radius:20px;
  padding:28px 30px 24px;position:relative;align-self:center;
  box-shadow:0 30px 70px rgba(0,0,0,.45), inset 0 1px 0 rgba(255,255,255,.55)}
.meta-row{display:flex;align-items:baseline;justify-content:space-between;gap:12px;
  font-size:9.5px;letter-spacing:1.6px;text-transform:uppercase;color:#93876f}
.paper h1{margin:11px 0 15px;font-family:var(--serif);font-size:40px;line-height:1.06;
  font-weight:700;letter-spacing:-.6px;color:#16202b}
.nav{display:flex;flex-wrap:wrap;gap:8px 17px;margin:0 0 19px;padding:0 0 17px;
  border-bottom:1px solid rgba(31,42,55,.14)}
.nav a{font-size:12.5px;color:#2f7f8c;position:relative;letter-spacing:.1px}
.nav a:hover{color:#1b5f6a}
.nav a:hover::after{content:"";position:absolute;left:0;right:0;bottom:-3px;height:1px;background:#1b5f6a}
.lede{margin:0 0 21px;font-size:15.5px;line-height:1.72;color:#303b49}
.lede b{font-weight:600;color:#16202b}
.stats{display:grid;grid-template-columns:repeat(4,1fr);margin:0 0 21px;
  border-top:1px solid rgba(31,42,55,.12);border-bottom:1px solid rgba(31,42,55,.12)}
.stat{padding:12px 12px 11px;border-left:1px solid rgba(31,42,55,.10)}
.stat:first-child{border-left:none;padding-left:0}
.stat b{display:block;font-family:var(--serif);font-size:27px;line-height:1.05;color:#16202b;
  font-variant-numeric:tabular-nums;letter-spacing:-.3px}
.stat span{display:block;margin-top:4px;font-size:9px;letter-spacing:1.2px;
  text-transform:uppercase;color:#93876f}
.actions{display:flex;align-items:center;gap:20px;flex-wrap:wrap}
.btn{border:1px solid #16324f;background:var(--deep);color:var(--paper);border-radius:999px;
  padding:12px 24px;font-size:13px;font-weight:600;letter-spacing:.3px;cursor:pointer;
  font-family:var(--sans);box-shadow:0 8px 18px rgba(15,39,64,.28);transition:.15s}
.btn:hover{background:#16324f;border-color:var(--sea);transform:translateY(-1px)}
.link{font-size:13px;color:#2f7f8c;cursor:pointer;display:inline-flex;align-items:center;gap:6px}
.link:hover{color:#1b5f6a}
.updated{margin-top:18px;padding-top:14px;border-top:1px solid rgba(31,42,55,.10);
  font-size:10.5px;letter-spacing:.3px;color:#93876f;display:flex;align-items:center;gap:7px}
.updated::before{content:"";width:5px;height:5px;border-radius:50%;background:#c9891a;flex:0 0 auto}

/* 地球 */
.globe-stage{position:relative;display:flex;align-items:center;justify-content:center;min-height:420px}
.globe-stage canvas{width:min(100%,740px);height:auto;display:block;cursor:grab;touch-action:none}
.globe-stage canvas:active{cursor:grabbing}
.globe-hint{position:absolute;right:10px;bottom:6px;font-size:10.5px;color:var(--fog);letter-spacing:.5px;text-align:right;line-height:1.5}

/* 胶囊切换 */
.tabs{position:absolute;left:26px;bottom:26px;display:inline-flex;background:#f7f2e6;border-radius:999px;
  padding:4px;box-shadow:0 12px 30px rgba(0,0,0,.35);border:1px solid rgba(220,207,180,.8)}
.tab{border:0;background:transparent;color:#5b6573;font-family:var(--sans);font-size:13px;font-weight:600;
  padding:9px 20px;border-radius:999px;cursor:pointer;letter-spacing:.2px}
.tab.on{background:var(--deep);color:var(--paper);box-shadow:0 4px 12px rgba(15,39,64,.4)}

/* ============ PANEL ============ */
.panel{max-width:1560px;margin:0 auto;padding:0 26px 70px}
.panel-head{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap;
  padding:6px 2px 14px;border-bottom:1px solid rgba(220,207,180,.2)}
.panel-head h2{margin:0;font-family:var(--serif);font-size:26px;font-weight:700;color:var(--paper)}
.panel-head span{font-size:12px;color:var(--fog);letter-spacing:.4px}
.filters{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:14px 0 16px}
.fchip{cursor:pointer;border:1px solid rgba(220,207,180,.32);background:rgba(243,235,218,.06);
  color:#cfd8e3;border-radius:7px;padding:5px 11px;font-size:12.5px;transition:.12s;font-family:var(--sans)}
.fchip:hover{border-color:rgba(220,207,180,.6);color:var(--paper)}
.fchip.on{background:var(--paper);border-color:var(--paper);color:var(--ink);font-weight:600}
.filters select,.filters input{border:1px solid rgba(220,207,180,.32);background:rgba(243,235,218,.08);
  color:var(--paper);border-radius:7px;padding:6px 10px;font-size:12.5px;font-family:var(--sans);outline:none}
.filters input{min-width:220px}
.filters input::placeholder{color:rgba(207,216,227,.55)}
.filters select:focus,.filters input:focus{border-color:var(--sea);box-shadow:0 0 0 3px rgba(47,140,156,.18)}
.filters select option{background:var(--deep);color:var(--paper)}
.spacer{flex:1}

/* 列表：纸卡堆叠 */
.list{display:flex;flex-direction:column;gap:11px}
.item{background:var(--paper);border:1px solid var(--paper-edge);border-left:4px solid var(--paper-edge);
  border-radius:12px;padding:15px 18px;box-shadow:0 12px 30px rgba(0,0,0,.26);transition:.14s;color:var(--ink)}
.item:hover{transform:translateY(-2px);box-shadow:0 18px 40px rgba(0,0,0,.36)}
.item.ai{border-left-color:var(--ai)}
.item.geopol{border-left-color:var(--geo)}
.item.skills{border-left-color:var(--skills)}
.item.oss{border-left-color:var(--oss)}
.item h3{margin:0;font-family:var(--serif);font-size:17px;font-weight:700;line-height:1.4;color:var(--ink)}
.item h3 a:hover{color:#8a5a06;text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:3px}
.meta{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:8px 0 9px;color:var(--ink-soft);font-size:11.5px}
.tag{display:inline-flex;align-items:center;gap:5px;border-radius:999px;padding:2px 9px;font-size:10.5px;
  font-weight:600;letter-spacing:.3px;border:1px solid transparent}
.tag.dom-ai{background:#efe8fb;color:#5533b0;border-color:#dccdf5}
.tag.dom-geopol{background:#e3f3f0;color:#0b6f64;border-color:#c6e5df}
.tag.dom-skills{background:#e7eefc;color:#1b46c2;border-color:#cbd9f7}
.tag.dom-oss{background:#fbf0d8;color:#8a5a06;border-color:#ecd8ab}
.tag.high{background:#e4f4ea;color:#0f6f47;border-color:#c6e5d2}
.tag.low{background:#fbefd9;color:#8a5a06;border-color:#ecd8ab}
.tag.zh{background:#e7eefc;color:#1b46c2;border-color:#cbd9f7}
.src{font-weight:600;color:var(--ink)}
.sum{color:#33404f;font-size:13.5px;line-height:1.62;display:-webkit-box;-webkit-line-clamp:2;
  -webkit-box-orient:vertical;overflow:hidden;cursor:pointer}
.sum.open{-webkit-line-clamp:unset;display:block}

/* 分布视图 */
.dist-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.dcard{background:var(--paper);color:var(--ink);border:1px solid var(--paper-edge);border-radius:14px;
  padding:16px 18px 18px;box-shadow:0 14px 34px rgba(0,0,0,.28)}
.dcard h3{margin:0 0 14px;font-family:var(--serif);font-size:17px;font-weight:700}
.bars{display:flex;align-items:flex-end;gap:10px;height:170px}
.bar{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;gap:5px;min-width:0}
.bar .v{font-family:var(--serif);font-size:12px;color:var(--ink);font-variant-numeric:tabular-nums}
.bar .col{width:100%;max-width:34px;border-radius:5px 5px 0 0;
  background:linear-gradient(180deg,var(--sea-bright),var(--sea));min-height:4px}
.bar.lead .col{background:linear-gradient(180deg,var(--amber-glow),var(--amber))}
.bar .cc{font-size:10px;color:var(--ink-soft);letter-spacing:.4px}
.rows .row{display:flex;align-items:center;gap:10px;margin-bottom:10px}
.rows .row:last-child{margin-bottom:0}
.rows .lbl{flex:0 0 68px;font-size:12px;color:var(--ink-soft)}
.rows .track{flex:1;height:9px;border-radius:5px;background:rgba(31,42,55,.1);overflow:hidden}
.rows .track i{display:block;height:100%}
.rows .val{flex:0 0 42px;text-align:right;font-family:var(--serif);font-size:12.5px;font-variant-numeric:tabular-nums}

/* 健康视图 */
.hgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px}
.hcard{background:var(--paper);color:var(--ink);border:1px solid var(--paper-edge);border-radius:11px;
  padding:11px 13px;display:flex;align-items:center;gap:10px;box-shadow:0 8px 22px rgba(0,0,0,.22)}
.hcard .dot{width:8px;height:8px;border-radius:50%;flex:0 0 auto}
.dot.ok{background:#178457} .dot.warn{background:#c9891a} .dot.bad{background:#c0472f}
.hcard .nm{flex:1;font-size:12.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hcard .pc{font-family:var(--serif);font-size:13px;font-variant-numeric:tabular-nums}
.hcard .sm{font-size:10px;color:var(--ink-soft);margin-left:2px}

.foot{padding:8px 26px 40px;text-align:center;color:var(--fog);font-size:11.5px;letter-spacing:.3px}
.kbd{border:1px solid rgba(220,207,180,.4);border-radius:4px;padding:0 5px;font-size:10.5px;color:var(--paper)}
.hidden{display:none}

@media (max-width:1080px){
  .hero{grid-template-columns:1fr;min-height:auto;padding:28px 18px 80px;gap:12px}
  .globe-stage{order:2;min-height:320px}
  .paper{order:1}
  .tabs{left:18px;bottom:18px}
  .dist-grid{grid-template-columns:1fr}
  .panel{padding:0 18px 60px}
}
@media (max-width:560px){
  .paper h1{font-size:27px}
  .stats{grid-template-columns:repeat(2,1fr)}
  .globe-stage{min-height:260px}
  .nav{gap:6px 10px}
}
</style>
</head>
<body>

<section class="hero">
  <div class="paper">
    <div class="meta-row"><span>Daily Intelligence Report</span><span>__DATE__</span></div>
    <h1>PIP 情报日报</h1>
    <nav class="nav">
      <a href="#panel" data-view="feed">今日条目</a>
      <a href="#panel" data-view="dist">分布</a>
      <a href="#panel" data-view="health">源健康</a>
      <a href="#panel" data-view="feed">全部 __TOTAL__ 条</a>
    </nav>
    <p class="lede">
      <b>__TOTAL__ 条</b>情报，来自 <b>__SOURCES__ 个源</b>、<b id="lede-countries">__COUNTRIES__ 个国家</b>；
      其中 <b>__HIGH__ 条</b>时间可信度达标，可直接进入日报。
    </p>
    <div class="stats" id="hero-stats"></div>
    <div class="actions">
      <button class="btn" onclick="location.reload()">刷新数据</button>
      <span class="link" id="to-feed">查看全部条目 →</span>
    </div>
    <p class="updated" id="hero-updated"></p>
  </div>

  <div class="globe-stage">
    <canvas id="globe" width="620" height="620" aria-label="来源城市到采集端的地球投影"></canvas>
    <div class="globe-hint">光束长度 = 该国条目量<br>实测采集 · RSS</div>
  </div>

  <div class="tabs" id="tabs">
    <button class="tab on" data-view="feed">条目</button>
    <button class="tab" data-view="dist">分布</button>
    <button class="tab" data-view="health">健康</button>
  </div>
</section>

<section class="panel" id="panel">
  <div class="panel-head">
    <h2 id="panel-title">今日条目</h2>
    <span id="panel-sub"></span>
  </div>
  <div class="filters" id="filters">
    <span class="fchip on" data-domain="all">全部</span>
    <div id="domain-chips" style="display:flex;gap:8px;flex-wrap:wrap"></div>
    <span class="fchip on" data-conf="all" data-conf-chip>全部可信度</span>
    <span class="fchip" data-conf="high">高可信</span>
    <span class="fchip" data-conf="low">低（不进日报）</span>
    <select id="src" style="max-width:190px"><option value="all">全部来源</option></select>
    <input id="q" placeholder="搜索标题 / 摘要…  按 / 聚焦"/>
    <span class="spacer"></span>
    <span id="count" style="font-size:12px;color:var(--fog)"></span>
  </div>

  <div id="view-feed" class="list"></div>
  <div id="view-dist" class="dist-grid hidden"></div>
  <div id="view-health" class="hgrid hidden"></div>
</section>

<div class="foot">PIP v0.7 · 版式取自 Packet Voyage /report · 采集 __SOURCES__ 源 · 按 <span class="kbd">/</span> 搜索</div>

<script>
const DATA = __DATA__;
const HEALTH = __HEALTH__;
const GLOBE = __GLOBE__;
const DOMAIN_META = {ai:"AI", geopol:"政经", skills:"AI 技能", oss:"GitHub"};
const DOMAIN_COLOR = {ai:"#7b56d9", geopol:"#0f9f8f", skills:"#2f6fed", oss:"#c9891a"};
const SOURCE_COUNTRY = {
  "techcrunch-ai":"US","ars-technica":"US","theverge":"US","mit-tech-review":"US",
  "google-ai-blog":"US","deepmind":"GB","huggingface-blog":"US","hn-frontpage":"US",
  "simonwillison":"US","github-blog":"US","google-news-ai":"US","openai-news":"US",
  "the-decoder":"DE","product-hunt":"US","latent-space":"US","gh-trending":"US","gh-changelog":"US",
  "aljazeera":"QA","cnbc-world":"US","guardian-world":"GB","politico":"US","thehill":"US",
  "npr-world":"US","france24":"FR","euronews":"FR","scmp":"HK","financial-times":"GB",
  "wsj-markets":"US","ithome":"CN","qbitai":"CN","infoq-cn":"CN"
};
const COUNTRY_META = {
  US:{n:"美国",x:0.24,y:0.36}, GB:{n:"英国",x:0.48,y:0.30}, CN:{n:"中国",x:0.66,y:0.40},
  QA:{n:"卡塔尔",x:0.60,y:0.47}, FR:{n:"法国",x:0.48,y:0.38}, HK:{n:"香港",x:0.68,y:0.46},
  DE:{n:"德国",x:0.51,y:0.34}, SG:{n:"新加坡",x:0.70,y:0.54}, JP:{n:"日本",x:0.74,y:0.36}
};
const countryOf = (r) => SOURCE_COUNTRY[r.source_id] || "US";
const state = {domain:"all", conf:"all", src:"all", q:"", view:"feed"};
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const hhmm = (iso) => iso ? iso.slice(11,16) : "--:--";

function rel(iso){
  if(!iso) return "无时间";
  const d = new Date(iso), diff = (Date.now() - d.getTime())/1000;
  if(diff < 3600) return Math.max(1, Math.round(diff/60)) + " 分钟前";
  if(diff < 86400) return Math.round(diff/3600) + " 小时前";
  return Math.round(diff/86400) + " 天前";
}
function countryCounts(rows){
  const map = new Map();
  rows.forEach(r => { const c = countryOf(r); map.set(c, (map.get(c) || 0) + 1); });
  return [...map.entries()].sort((a, b) => b[1] - a[1]);
}

/* 地球：packetvoyage 数据 + 正交投影 + 可拖拽 */
function renderGlobe(){
  const cv = $("globe");
  if(!cv || !cv.getContext) return;
  const ctx = cv.getContext("2d");
  const SIZE = 740, dpr = Math.min(window.devicePixelRatio || 1, 2);
  cv.width = SIZE * dpr; cv.height = SIZE * dpr;
  cv.style.width = SIZE + "px"; cv.style.height = SIZE + "px";
  ctx.scale(dpr, dpr);

  const cx = SIZE / 2, cy = SIZE / 2, R = SIZE * 0.305, RAD = Math.PI / 180;
  const G = GLOBE || {cities: [], terminator: [], origin: null, solar: {lat: 0, lon: 0}};
  const cities = G.cities || [];
  const originCity = (G.origin && G.origin.city) || "";
  const maxCount = Math.max(1, ...cities.map(c => c.count));
  const total = cities.reduce((s, c) => s + c.count, 0) || 1;

  let lat0 = 20, lon0 = -170, spin = 0.06, dragging = false, lastX = 0, lastY = 0;

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
    sphere.addColorStop(0, "#24547e");
    sphere.addColorStop(0.5, "#123350");
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

    // 城市点（标签做碰撞避让：挤不下就只留点）
    const placed = [];
    cities.forEach(c => {
      if(c.city === originCity) return;  // 采集端由脉冲标记单独绘制
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
        ctx.textAlign = "center";
        ctx.fillText("采集端 " + o.city, ox, oy - pulse - 7);
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
function renderHeroStats(rows){
  const high = rows.filter(r => r.time_confidence === "high").length;
  const zh = rows.filter(r => r.lang === "zh").length;
  const countries = countryCounts(rows).length;
  const ledeCountries = $("lede-countries");
  if(ledeCountries) ledeCountries.textContent = `${countries} 个国家`;
  const stats = [
    ["源", new Set(rows.map(r => r.source_id)).size],
    ["国家", countryCounts(rows).length],
    ["条目", rows.length],
    ["中文", zh]
  ];
  $("hero-stats").innerHTML = stats.map(([k, v]) =>
    `<div class="stat"><b>${v}</b><span>${k}</span></div>`).join("");
  const last = rows.length ? rows[0].published_at : null;
  $("hero-updated").textContent = last ? `最新一条 · ${rel(last)}（${hhmm(last)} UTC）` : "";
  const sub = $("panel-sub");
  if(sub) sub.textContent = `${high} 高可信 · ${rows.length - high} 低可信 · ${new Set(rows.map(r=>r.lang)).size} 种语言`;
}

/* 分布视图 */
function renderDist(rows){
  const counts = countryCounts(rows);
  const maxC = Math.max(1, ...counts.map(([, n]) => n));
  const total = rows.length || 1;
  const bars = counts.map(([code, n], i) => `
    <div class="bar${i===0?" lead":""}">
      <span class="v">${n}</span>
      <span class="col" style="height:${Math.max(4, Math.round(n/maxC*140))}px"></span>
      <span class="cc">${(COUNTRY_META[code]||{n:code}).n}</span>
    </div>`).join("");

  const domainRows = [...new Set(rows.map(r => r.domain))].map(d => {
    const n = rows.filter(r => r.domain === d).length;
    return `<div class="row"><span class="lbl">${DOMAIN_META[d]||d}</span>
      <span class="track"><i style="width:${(n/total*100).toFixed(1)}%;background:${DOMAIN_COLOR[d]||"#5b6573"}"></i></span>
      <span class="val">${n}</span></div>`;
  }).join("");

  const high = rows.filter(r => r.time_confidence === "high").length;
  const qualityRows = `
    <div class="row"><span class="lbl">高可信</span>
      <span class="track"><i style="width:${(high/total*100).toFixed(1)}%;background:#0f6f47"></i></span>
      <span class="val">${high}</span></div>
    <div class="row"><span class="lbl">低可信</span>
      <span class="track"><i style="width:${((rows.length-high)/total*100).toFixed(1)}%;background:#c9891a"></i></span>
      <span class="val">${rows.length - high}</span></div>
    <div class="row"><span class="lbl">中文</span>
      <span class="track"><i style="width:${(rows.filter(r=>r.lang==="zh").length/total*100).toFixed(1)}%;background:#2f8c9c"></i></span>
      <span class="val">${rows.filter(r=>r.lang==="zh").length}</span></div>`;

  $("view-dist").innerHTML = `
    <div class="dcard"><h3>来源国家</h3><div class="bars">${bars}</div></div>
    <div class="dcard"><h3>频道与可信度</h3><div class="rows">${domainRows}${qualityRows}</div></div>`;
}

/* 健康视图 */
function renderHealthCards(){
  const rows = HEALTH.rows || [];
  $("view-health").innerHTML = rows.map(h => {
    const cls = h.flag === "GREEN" ? "ok" : h.flag === "YELLOW" ? "warn" : "bad";
    return `<div class="hcard"><span class="dot ${cls}"></span>
      <span class="nm">${esc(h.source_name)}</span>
      <span class="pc">${Math.round(h.success_rate*100)}%</span>
      <span class="sm">${h.ok}/${h.ok + h.zero + h.failed}</span></div>`;
  }).join("");
}

function renderFilters(rows){
  const present = [...new Set(rows.map(r => r.domain))];
  $("domain-chips").innerHTML = present.map(d => {
    const n = rows.filter(r => r.domain === d).length;
    return `<span class="fchip${state.domain===d?" on":""}" data-domain="${d}">${DOMAIN_META[d]||d} ${n}</span>`;
  }).join("");
  const sel = $("src");
  if(sel.options.length === 1){
    [...new Set(rows.map(r => r.source_id))].sort().forEach(id => {
      const o = document.createElement("option"); o.value = id; o.textContent = id; sel.appendChild(o);
    });
  }
}

function renderList(rows){
  const q = state.q.trim().toLowerCase();
  const filtered = rows.filter(r => {
    if(state.domain !== "all" && r.domain !== state.domain) return false;
    if(state.conf !== "all" && r.time_confidence !== state.conf) return false;
    if(state.src !== "all" && r.source_id !== state.src) return false;
    if(q && !(`${r.title||""} ${r.summary||""} ${r.source_name||""}`.toLowerCase().includes(q))) return false;
    return true;
  });
  $("count").textContent = `${filtered.length} / ${rows.length} 条`;
  if(!filtered.length){ $("view-feed").innerHTML = `<div class="item"><h3>没有匹配的条目</h3></div>`; return; }
  $("view-feed").innerHTML = filtered.map((r, i) => `
    <article class="item ${r.domain}">
      <h3><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.title)}</a></h3>
      <div class="meta">
        <span class="tag dom-${r.domain}">${DOMAIN_META[r.domain]||r.domain}</span>
        <span class="src">${esc(r.source_name)}</span>
        <span>${hhmm(r.published_at)} · ${rel(r.published_at)}</span>
        <span class="tag ${r.time_confidence}">${r.time_confidence}</span>
        ${r.lang==="zh"?'<span class="tag zh">中文</span>':""}
      </div>
      <div class="sum" data-i="${i}">${esc(r.summary || "（该源未提供摘要，W2 接正文抽取）")}</div>
    </article>`).join("");
  document.querySelectorAll(".sum").forEach(el => el.onclick = () => el.classList.toggle("open"));
}

function setView(view, rows){
  state.view = view;
  document.querySelectorAll(".tab").forEach(t => t.classList.toggle("on", t.dataset.view === view));
  $("view-feed").classList.toggle("hidden", view !== "feed");
  $("view-dist").classList.toggle("hidden", view !== "dist");
  $("view-health").classList.toggle("hidden", view !== "health");
  $("filters").classList.toggle("hidden", view === "health");
  const titles = {feed:"今日条目", dist:"数据分布", health:"源健康"};
  $("panel-title").textContent = titles[view] || "";
  if(view === "dist") renderDist(rows);
  if(view === "health") renderHealthCards();
  if(view === "feed") renderList(rows);
}

function bind(rows){
  document.querySelectorAll(".tab").forEach(t => t.onclick = () => setView(t.dataset.view, rows));
  document.querySelectorAll(".nav a").forEach(a => a.onclick = (e) => {
    e.preventDefault(); setView(a.dataset.view, rows); $("panel").scrollIntoView({behavior:"smooth"});
  });
  $("to-feed").onclick = () => { setView("feed", rows); $("panel").scrollIntoView({behavior:"smooth"}); };
  document.querySelectorAll("[data-domain]").forEach(el => el.onclick = () => {
    state.domain = el.dataset.domain;
    document.querySelectorAll("[data-domain]").forEach(x => x.classList.toggle("on", x === el));
    renderList(rows);
  });
  document.querySelectorAll("[data-conf]").forEach(el => el.onclick = () => {
    state.conf = el.dataset.conf;
    document.querySelectorAll("[data-conf]").forEach(x => x.classList.toggle("on", x === el));
    renderList(rows);
  });
  $("src").onchange = (e) => { state.src = e.target.value; renderList(rows); };
  $("q").oninput = (e) => { state.q = e.target.value; renderList(rows); };
  document.addEventListener("keydown", (e) => {
    if(e.key === "/" && document.activeElement !== $("q")){ e.preventDefault(); $("q").focus(); $("panel").scrollIntoView({behavior:"smooth"}); }
  });
}

const rows = DATA.items || [];
renderGlobe(); renderHeroStats(rows); renderFilters(rows); renderList(rows); renderDist(rows); renderHealthCards(); bind(rows);
</script>
</body>
</html>
"""


def active_source_ids() -> set[str]:
    if not SOURCES_FILE.exists():
        return set()
    payload = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
    return {row["id"] for row in payload["sources"]}


def load_items(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_health(path: Path) -> list[dict]:
    rows = load_rows(path)
    health = summarize(rows, active_ids=active_source_ids())
    return [
        {
            "source_id": h.source_id, "source_name": h.source_name, "domain": h.domain,
            "flag": h.flag, "success_rate": round(h.success_rate, 2),
            "ok": h.ok, "zero": h.zero, "failed": h.failed,
            "unreachable": h.unreachable, "avg_ms": h.avg_ms, "error": h.last_error,
        }
        for h in health if not h.retired
    ]


def build(items_path: Path | None = None, health_path: Path = HEALTH_FILE, out: Path = OUT_FILE) -> Path:
    items_path = items_path or latest_items_path()
    items = load_items(items_path)
    health = load_health(health_path)
    payload = {
        "date": items_path.stem,
        "run_at": max(i["fetched_at"] for i in items) if items else "",
        "items": items,
    }
    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    health_json = json.dumps({"rows": health}, ensure_ascii=False).replace("</", "<\\/")
    globe_file = ROOT / "data" / "globe.json"
    globe_json = globe_file.read_text(encoding="utf-8") if globe_file.exists() else "null"
    high = sum(1 for i in items if i.get("time_confidence") == "high")
    countries = len({i["source_id"] for i in items})

    html = (
        TEMPLATE.replace("__DATA__", data_json)
        .replace("__HEALTH__", health_json)
        .replace("__GLOBE__", globe_json)
        .replace("__DATE__", items_path.stem)
        .replace("__TOTAL__", str(len(items)))
        .replace("__SOURCES__", str(len({i["source_id"] for i in items})))
        .replace("__COUNTRIES__", str(countries))
        .replace("__HIGH__", str(high))
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


if __name__ == "__main__":
    path = build()
    print(f"生成 {path}  ({path.stat().st_size/1024:.1f} KB)")
