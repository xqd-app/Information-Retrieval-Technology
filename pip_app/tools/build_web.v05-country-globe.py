"""把当日采集结果渲染成单文件 HTML 仪表盘。

v0.4 布局（按需求重排）：
- 顶栏：品牌 + Packet Voyage 风格地球（光柱长度 = 该国条目数）+ Refresh
- 左栏：控制台 → 数据分布（国家柱形图 + 域分布条）→ Source Health → 票据数据卡（原顶栏 ticker，移到底部）
- 右侧：条目列表
数据内联进 HTML，file:// 直接打开可用。
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
<style>
:root{
  --ink:#10131a; --muted:#637083; --panel:#ffffff;
  --line:rgba(18,24,38,.14); --line-soft:rgba(18,24,38,.07);
  --shadow:0 18px 45px rgba(13,23,38,.14); --shadow-sm:0 6px 18px rgba(13,23,38,.08);
  --abyss:#071526; --deep:#0f2740; --paper:#f3ebda; --paper-edge:#dccfb4;
  --pv-ink:#1f2a37; --pv-soft:#5b6573; --amber:#e09a2b; --amber-glow:#f6c06a;
  --sea:#2f8c9c; --sea-bright:#5cc8d6; --fog:#8a9aae;
  --serif:"Young Serif", Georgia, "Songti SC", "SimSun", serif;
  --ai:#7b56d9; --geo:#0f9f8f; --skills:#2f6fed; --oss:#d69b16;
  font-family:"Hanken Grotesk", Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
}
*{box-sizing:border-box}
html,body{margin:0;height:100%}
body{color:var(--ink);background:#e8edf2;font-size:13px;line-height:1.55}
a{color:inherit;text-decoration:none}

/* ---------- 顶栏 + 地球 ---------- */
.topbar{background:var(--abyss);border-bottom:1px solid var(--deep);padding:10px 22px;
  position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:22px}
.brand{display:flex;flex-direction:column;gap:3px;min-width:230px}
.brand h1{margin:0;font-family:var(--serif);font-size:20px;font-weight:700;color:var(--paper);letter-spacing:.2px}
.brand p{margin:0;font-size:11px;color:var(--fog);letter-spacing:.2px}
.brand .rule{height:1px;background:linear-gradient(90deg,var(--sea) 0%,transparent 70%);margin-top:5px}
.globe-wrap{flex:1;display:flex;align-items:center;justify-content:center;position:relative;min-height:152px}
.globe-wrap svg{display:block;overflow:visible}
.globe-caption{position:absolute;right:8px;bottom:6px;font-size:9.5px;color:var(--fog);letter-spacing:.6px}
.btn{border:1px solid #24405f;background:var(--deep);color:var(--paper);border-radius:999px;
  padding:9px 18px;font-size:12px;font-weight:600;cursor:pointer;letter-spacing:.3px}
.btn:hover{background:#16324f;border-color:var(--sea)}
.btn-sm{border:1px solid var(--line);background:#fff;color:var(--muted);border-radius:6px;
  padding:3px 9px;font-size:11px;cursor:pointer}
.btn-sm:hover{color:var(--ink);border-color:rgba(18,24,38,.28)}

/* ---------- 两栏 ---------- */
.layout{display:grid;grid-template-columns:312px minmax(0,1fr);gap:14px;padding:14px 22px 40px;
  align-items:start;max-width:1560px;margin:0 auto}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;box-shadow:var(--shadow-sm)}
.card-head{display:flex;align-items:center;justify-content:space-between;padding:11px 13px;
  border-bottom:1px solid var(--line-soft);font-size:10px;letter-spacing:.9px;color:var(--muted);text-transform:uppercase}
.col-left{display:flex;flex-direction:column;gap:12px;position:sticky;top:126px}
.field{padding:11px 13px;border-bottom:1px solid var(--line-soft)}
.field:last-child{border-bottom:none}
.field label{display:flex;justify-content:space-between;font-size:10px;letter-spacing:.8px;color:var(--muted);
  text-transform:uppercase;margin-bottom:7px}
.field label b{color:var(--ink);font-size:11px;letter-spacing:0}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{cursor:pointer;border:1px solid var(--line);background:#fff;color:var(--muted);border-radius:6px;
  padding:4px 9px;font-size:11.5px;transition:.12s}
.chip:hover{border-color:rgba(18,24,38,.3);color:var(--ink)}
.chip.on{background:#eef2ff;border-color:#2f6fed;color:#1b46c2;font-weight:600}
.chip.on.ai{background:#f1ecfd;border-color:var(--ai);color:#5533b0}
.chip.on.geopol{background:#e7f6f3;border-color:var(--geo);color:#0b6f64}
.chip.on.skills{background:#eaf1ff;border-color:var(--skills);color:#1b46c2}
.chip.on.oss{background:#fdf3e0;border-color:var(--oss);color:#8a5a06}
select,input{width:100%;border:1px solid var(--line);border-radius:6px;padding:7px 9px;font-size:12px;
  background:#fff;color:var(--ink);outline:none;font-family:inherit}
select:focus,input:focus{border-color:var(--sea);box-shadow:0 0 0 3px rgba(47,140,156,.15)}

/* 国家柱形图 */
.chart{padding:12px 13px 8px}
.bars{display:flex;align-items:flex-end;gap:6px;height:104px}
.bar{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;gap:4px;min-width:0}
.bar .v{font-family:var(--serif);font-size:11px;color:var(--pv-ink);font-variant-numeric:tabular-nums}
.bar .col{width:100%;max-width:22px;border-radius:4px 4px 0 0;background:linear-gradient(180deg,var(--sea-bright),var(--sea));
  min-height:3px;transition:height .3s}
.bar.lead .col{background:linear-gradient(180deg,var(--amber-glow),var(--amber))}
.bar .cc{font-size:9.5px;color:var(--muted);letter-spacing:.4px;text-align:center;line-height:1.2}
.chart-foot{display:flex;justify-content:space-between;padding:6px 2px 0;font-size:10px;color:var(--muted)}

/* 域分布条 */
.brief{padding:10px 13px 12px}
.brief-row{display:flex;align-items:center;gap:9px;margin-bottom:8px}
.brief-row:last-child{margin-bottom:0}
.brief-label{flex:0 0 62px;font-size:11px;color:var(--muted)}
.brief-bar{flex:1;height:7px;border-radius:4px;background:#eef1f5;overflow:hidden;display:flex}
.brief-bar i{display:block;height:100%}
.brief-val{flex:0 0 38px;text-align:right;font-size:11.5px;font-variant-numeric:tabular-nums;color:#3c4757}

/* 票据数据卡（原顶栏 ticker） */
.ticker{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:11px 13px}
.tick{background:var(--paper);border:1px solid var(--paper-edge);border-radius:9px;padding:8px 10px;
  box-shadow:0 2px 0 rgba(20,24,32,.14)}
.tick b{display:block;font-family:var(--serif);font-size:18px;font-weight:700;line-height:1.1;
  color:var(--pv-ink);font-variant-numeric:tabular-nums}
.tick span{display:block;margin-top:2px;font-size:9px;letter-spacing:.7px;text-transform:uppercase;color:var(--pv-soft)}
.tick.hot{background:linear-gradient(180deg,#f9e3bb,#f3ebda);border-color:#e8cf9d}
.tick.hot b{color:#8a5a06}

/* Source Health */
.health{max-height:26vh;overflow:auto}
.hrow{display:flex;align-items:center;gap:8px;padding:6px 13px;border-bottom:1px solid var(--line-soft);font-size:11.5px}
.hrow:last-child{border-bottom:none}
.dot{width:7px;height:7px;border-radius:50%;flex:0 0 auto}
.dot.ok{background:#178457} .dot.warn{background:var(--amber)} .dot.bad{background:#d05a3b}
.hname{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#3c4757}
.hnum{color:var(--muted);font-variant-numeric:tabular-nums;font-size:11px}

/* 列表 */
.col-main{min-width:0}
.mid-head{display:flex;align-items:center;justify-content:space-between;padding:0 4px 8px;
  font-size:11px;color:var(--muted);letter-spacing:.3px}
.list{display:flex;flex-direction:column;gap:9px}
.item{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--line);
  border-radius:10px;padding:13px 16px;box-shadow:var(--shadow-sm);transition:.13s}
.item:hover{transform:translateY(-1px);box-shadow:var(--shadow)}
.item.ai{border-left-color:var(--ai)}
.item.geopol{border-left-color:var(--geo)}
.item.skills{border-left-color:var(--skills)}
.item.oss{border-left-color:var(--oss)}
.item h3{margin:0;font-size:15px;font-weight:650;letter-spacing:-.15px;line-height:1.35}
.item h3 a:hover{color:var(--sea)}
.meta{display:flex;flex-wrap:wrap;gap:7px;align-items:center;margin:6px 0 7px;color:var(--muted);font-size:11px}
.tag{display:inline-flex;align-items:center;gap:5px;border-radius:999px;padding:2px 8px;font-size:10.5px;
  font-weight:600;letter-spacing:.2px}
.tag.high{background:#e7f6ee;color:#0f6f47}
.tag.low{background:#fdf3e0;color:#8a5a06}
.tag.zh{background:#eaf1ff;color:#1b46c2}
.tag.dom-ai{background:#f1ecfd;color:#5533b0}
.tag.dom-geopol{background:#e7f6f3;color:#0b6f64}
.tag.dom-skills{background:#eaf1ff;color:#1b46c2}
.tag.dom-oss{background:#fdf3e0;color:#8a5a06}
.tag.cc{background:#f3f6f9;color:#4a5566;font-weight:500}
.src{font-weight:600;color:#3c4757}
.sum{color:#4a5566;font-size:12.5px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;
  overflow:hidden;cursor:pointer}
.sum.open{-webkit-line-clamp:unset;display:block}
.empty{padding:44px;text-align:center;color:var(--muted);background:var(--panel);border:1px dashed var(--line);
  border-radius:10px;font-size:12.5px}
.foot{padding:6px 22px 26px;text-align:center;color:var(--muted);font-size:11px}
.kbd{border:1px solid var(--line);border-radius:4px;padding:0 5px;font-size:10.5px;background:#fff}

@media (max-width:1024px){
  .layout{grid-template-columns:1fr}
  .col-left{position:static;order:2}
  .col-main{order:1}
  .health{max-height:none}
  .globe-wrap{min-height:80px}
}
@media (max-width:760px){
  .topbar{flex-wrap:wrap;gap:10px;padding:10px 12px}
  .globe-wrap{order:3;width:100%;min-height:110px}
  .layout{padding:12px}
}
</style>
</head>
<body>
<div class="topbar">
  <div class="brand">
    <h1>PIP 情报日报</h1>
    <p>__DATE__ · __SOURCES__ 源 · RSS 原文，无 LLM 改写</p>
    <div class="rule"></div>
  </div>
  <div class="globe-wrap">
    <svg id="globe" width="0" height="0" viewBox="0 0 420 116" aria-label="来源国家分布地球"></svg>
    <span class="globe-caption">光束长度 = 该国条目量 · 实测采集</span>
  </div>
  <button class="btn" onclick="location.reload()">Refresh</button>
</div>

<div class="layout">
  <aside class="col-left">
    <section class="card">
      <div class="card-head"><span>控制台</span><button class="btn-sm" id="clear">Clear</button></div>
      <div class="field">
        <label>频道 <b id="n-domain"></b></label>
        <div class="chips" id="ch-domains"></div>
      </div>
      <div class="field">
        <label>可信度 <b id="n-conf"></b></label>
        <div class="chips" id="ch-conf"></div>
      </div>
      <div class="field">
        <label>来源</label>
        <select id="src"><option value="all">全部来源</option></select>
      </div>
      <div class="field">
        <label>搜索</label>
        <input id="q" placeholder="标题 / 摘要 / 来源…  按 / 聚焦"/>
      </div>
    </section>

    <section class="card">
      <div class="card-head"><span>数据分布</span><span id="country-count" class="hnum"></span></div>
      <div class="chart">
        <div class="bars" id="bars"></div>
        <div class="chart-foot"><span id="chart-left"></span><span id="chart-right"></span></div>
      </div>
      <div class="brief" id="brief"></div>
    </section>

    <section class="card">
      <div class="card-head"><span>Source Health</span><span id="health-sum" class="hnum"></span></div>
      <div class="health" id="health"></div>
    </section>

    <section class="card">
      <div class="card-head"><span>总量</span><span class="tag high" id="daily-badge"></span></div>
      <div class="ticker" id="ticker"></div>
    </section>
  </aside>

  <main class="col-main">
    <div class="mid-head"><span id="count"></span><span id="freshness"></span></div>
    <div class="list" id="list"></div>
  </main>
</div>

<div class="foot">PIP v0.4 · 地球与票据风格取自 Packet Voyage · 采集 31 源 · 按 <span class="kbd">/</span> 搜索</div>

<script>
const DATA = __DATA__;
const HEALTH = __HEALTH__;
const DOMAIN_META = {ai:"AI", geopol:"政经", skills:"AI 技能", oss:"GitHub"};
const DOMAIN_COLOR = {ai:"var(--ai)", geopol:"var(--geo)", skills:"var(--skills)", oss:"var(--oss)"};

/* 源 → 国家（按媒体总部 / 主要编辑部所在地） */
const SOURCE_COUNTRY = {
  "techcrunch-ai":"US", "ars-technica":"US", "theverge":"US", "mit-tech-review":"US",
  "google-ai-blog":"US", "deepmind":"GB", "huggingface-blog":"US", "hn-frontpage":"US",
  "simonwillison":"US", "github-blog":"US", "google-news-ai":"US", "openai-news":"US",
  "the-decoder":"DE", "product-hunt":"US", "latent-space":"US",
  "gh-trending":"US", "gh-changelog":"US",
  "aljazeera":"QA", "cnbc-world":"US", "guardian-world":"GB", "politico":"US",
  "thehill":"US", "npr-world":"US", "france24":"FR", "euronews":"FR",
  "scmp":"HK", "financial-times":"GB", "wsj-markets":"US",
  "ithome":"CN", "qbitai":"CN", "infoq-cn":"CN"
};
const COUNTRY_META = {
  US:{name:"美国", flag:"🇺🇸"}, GB:{name:"英国", flag:"🇬🇧"}, CN:{name:"中国", flag:"🇨🇳"},
  QA:{name:"卡塔尔", flag:"🇶🇦"}, FR:{name:"法国", flag:"🇫🇷"}, HK:{name:"香港", flag:"🇭🇰"},
  DE:{name:"德国", flag:"🇩🇪"}, SG:{name:"新加坡", flag:"🇸🇬"}, JP:{name:"日本", flag:"🇯🇵"}
};
const countryOf = (r) => SOURCE_COUNTRY[r.source_id] || "US";

const state = {domain:"all", conf:"all", src:"all", q:""};
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

function rel(iso){
  if(!iso) return "无时间";
  const d = new Date(iso), diff = (Date.now() - d.getTime())/1000;
  if(diff < 3600) return Math.max(1, Math.round(diff/60)) + " 分钟前";
  if(diff < 86400) return Math.round(diff/3600) + " 小时前";
  return Math.round(diff/86400) + " 天前";
}
const hhmm = (iso) => iso ? iso.slice(11,16) : "--:--";

function countryCounts(rows){
  const map = new Map();
  rows.forEach(r => { const c = countryOf(r); map.set(c, (map.get(c) || 0) + 1); });
  return [...map.entries()].sort((a, b) => b[1] - a[1]);
}

/* ---------- 地球（Packet Voyage 风格，光柱 = 国家条目量） ---------- */
function renderGlobe(rows){
  const counts = countryCounts(rows);
  const max = Math.max(1, ...counts.map(([, n]) => n));
  const W = 460, H = 150, cx = W / 2, cy = 74, r = 46;
  const total = rows.length || 1;

  // 光柱：按国家数均分角度，两侧对称分布
  const beams = counts.map(([code, n], i) => {
    const side = i % 2 === 0 ? 1 : -1;
    const idx = Math.floor(i / 2);
    const angle = (-62 + idx * (124 / Math.max(1, Math.ceil(counts.length / 2)))) * Math.PI / 180;
    const len = 26 + (n / max) * 62;
    const x1 = cx + Math.cos(angle) * (r - 4) * side * 0.9;
    const y1 = cy + Math.sin(angle) * (r - 4);
    const x2 = cx + Math.cos(angle) * (r + len) * side * 0.9;
    const y2 = cy + Math.sin(angle) * (r + len);
    const hot = n >= max * 0.66;
    return `<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}"
      stroke="${hot ? "#f6c06a" : "#5cc8d6"}" stroke-width="${hot ? 3.2 : 2.2}" stroke-linecap="round" opacity=".95"/>
      <circle cx="${x2.toFixed(1)}" cy="${y2.toFixed(1)}" r="${hot ? 2.6 : 1.8}"
        fill="${hot ? "#f6c06a" : "#5cc8d6"}" opacity=".9"/>`;
  }).join("");

  // 弧线（Packet Voyage 的琥珀弧）
  const arcs = counts.slice(0, 3).map(([code, n], i) => {
    const rr = r + 16 + i * 9;
    return `<circle cx="${cx}" cy="${cy}" r="${rr}" fill="none" stroke="#e09a2b"
      stroke-width="1" stroke-dasharray="26 40" opacity=".45"/>`;
  }).join("");

  const ticks = counts.map(([code, n]) => {
    const meta = COUNTRY_META[code] || {name: code, flag: ""};
    return `<title>${esc(meta.name)}：${n} 条</title>`;
  }).join("");

  const svg = `
    <defs>
      <radialGradient id="sphere" cx="34%" cy="30%">
        <stop offset="0%" stop-color="#1d3a5c"/>
        <stop offset="55%" stop-color="#0f2740"/>
        <stop offset="100%" stop-color="#071526"/>
      </radialGradient>
      <radialGradient id="halo" cx="50%" cy="50%">
        <stop offset="58%" stop-color="rgba(92,200,214,.22)"/>
        <stop offset="100%" stop-color="rgba(92,200,214,0)"/>
      </radialGradient>
    </defs>
    <circle cx="${cx}" cy="${cy}" r="${r + 26}" fill="url(#halo)"/>
    <g>${beams}${ticks}</g>
    <circle cx="${cx}" cy="${cy}" r="${r}" fill="url(#sphere)" stroke="#24405f" stroke-width="1"/>
    <ellipse cx="${cx}" cy="${cy}" rx="${r * 0.42}" ry="${r}" fill="none" stroke="#2f8c9c" stroke-width=".8" opacity=".5"/>
    <ellipse cx="${cx}" cy="${cy}" rx="${r * 0.78}" ry="${r}" fill="none" stroke="#2f8c9c" stroke-width=".8" opacity=".35"/>
    <ellipse cx="${cx}" cy="${cy}" rx="${r}" ry="${r * 0.34}" fill="none" stroke="#2f8c9c" stroke-width=".8" opacity=".45"/>
    <ellipse cx="${cx}" cy="${cy}" rx="${r}" ry="${r * 0.68}" fill="none" stroke="#2f8c9c" stroke-width=".8" opacity=".25"/>
    ${arcs}
    <text x="${cx}" y="${cy + r + 16}" text-anchor="middle" fill="#8a9aae"
      style="font-size:10.5px;letter-spacing:.6px">${counts.length} 国 · ${total} 条</text>`;

  const svgEl = $("globe");
  svgEl.setAttribute("width", String(W));
  svgEl.setAttribute("height", String(H));
  svgEl.innerHTML = svg;
}

/* ---------- 国家柱形图 ---------- */
function renderCountryChart(rows){
  const counts = countryCounts(rows);
  const max = Math.max(1, ...counts.map(([, n]) => n));
  $("bars").innerHTML = counts.map(([code, n], i) => {
    const meta = COUNTRY_META[code] || {name: code, flag: ""};
    const h = Math.max(3, Math.round((n / max) * 78));
    return `<div class="bar${i === 0 ? " lead" : ""}" title="${esc(meta.name)} · ${n} 条">
      <span class="v">${n}</span>
      <span class="col" style="height:${h}px"></span>
      <span class="cc">${esc(code)}</span>
    </div>`;
  }).join("");
  $("country-count").textContent = `${counts.length} 国`;
  const top = counts[0];
  $("chart-left").textContent = top ? `最多：${(COUNTRY_META[top[0]] || {}).name || top[0]} ${top[1]} 条` : "";
  const cn = counts.find(([c]) => c === "CN");
  $("chart-right").textContent = cn ? `中国 ${cn[1]} 条` : "";
}

function renderBrief(rows){
  const total = rows.length || 1;
  const high = rows.filter(r => r.time_confidence === "high").length;
  const zh = rows.filter(r => r.lang === "zh").length;
  const bar = (label, value, color) => `
    <div class="brief-row">
      <span class="brief-label">${label}</span>
      <span class="brief-bar"><i style="width:${(value/total*100).toFixed(1)}%;background:${color}"></i></span>
      <span class="brief-val">${value}</span>
    </div>`;
  const domainBars = [...new Set(rows.map(r => r.domain))]
    .map(d => bar(DOMAIN_META[d] || d, rows.filter(r => r.domain === d).length, DOMAIN_COLOR[d] || "var(--muted)"))
    .join("");
  $("brief").innerHTML = domainBars +
    bar("高可信", high, "#178457") +
    bar("低可信", rows.length - high, "var(--amber)") +
    bar("中文", zh, "var(--sea)");
  $("daily-badge").textContent = `日报候选 ${high}`;
}

function renderTicker(rows){
  const high = rows.filter(r => r.time_confidence === "high").length;
  const zh = rows.filter(r => r.lang === "zh").length;
  const domainTicks = [...new Set(rows.map(r => r.domain))].map(d =>
    [DOMAIN_META[d] || d, rows.filter(r => r.domain === d).length, false]);
  const tick = [
    ["条目", rows.length, false],
    ["高可信", high, true],
    ["低可信", rows.length - high, false],
    ...domainTicks,
    ["中文", zh, false]
  ];
  $("ticker").innerHTML = tick.map(([k, v, hot]) =>
    `<div class="tick${hot ? " hot" : ""}"><b>${v}</b><span>${k}</span></div>`).join("");
}

function renderControls(rows){
  const present = [...new Set(rows.map(r => r.domain))];
  const domains = [["all", "全部", rows.length], ...present.map(d =>
    [d, DOMAIN_META[d] || d, rows.filter(r => r.domain === d).length])];
  $("ch-domains").innerHTML = domains.map(([v, label, n]) =>
    `<span class="chip${state.domain === v ? " on" : ""} ${v}" data-domain="${v}">${label} ${n}</span>`).join("");

  const confs = [["all","全部", rows.length], ["high","高可信", rows.filter(r=>r.time_confidence==="high").length],
                 ["low","低（不进日报）", rows.filter(r=>r.time_confidence==="low").length]];
  $("ch-conf").innerHTML = confs.map(([v,label,n]) =>
    `<span class="chip${state.conf===v?" on":""}" data-conf="${v}">${label} ${n}</span>`).join("");

  $("n-domain").textContent = rows.length;
  $("n-conf").textContent = rows.filter(r=>r.time_confidence==="high").length + " 可用";
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
  const last = rows.length ? rows[0].published_at : null;
  $("freshness").textContent = last ? `最新一条 ${rel(last)}` : "";
  if(!filtered.length){ $("list").innerHTML = `<div class="empty">没有匹配的条目</div>`; return; }
  $("list").innerHTML = filtered.map((r,i) => {
    const cc = countryOf(r);
    const meta = COUNTRY_META[cc] || {name: cc, flag: ""};
    return `
    <article class="item ${r.domain}">
      <h3><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.title)}</a></h3>
      <div class="meta">
        <span class="tag dom-${r.domain}">${DOMAIN_META[r.domain] || r.domain}</span>
        <span class="src">${esc(r.source_name)}</span>
        <span class="tag cc" title="采集来源国">${meta.flag} ${esc(meta.name)}</span>
        <span>${hhmm(r.published_at)} · ${rel(r.published_at)}</span>
        <span class="tag ${r.time_confidence}">${r.time_confidence}</span>
        ${r.lang==="zh"?'<span class="tag zh">中文</span>':""}
      </div>
      <div class="sum" data-i="${i}">${esc(r.summary || "（该源未提供摘要，W2 接正文抽取）")}</div>
    </article>`;
  }).join("");
  document.querySelectorAll(".sum").forEach(el => el.onclick = () => el.classList.toggle("open"));
}

function renderHealth(){
  const rows = HEALTH.rows || [];
  const ok = rows.filter(h => h.flag === "GREEN").length;
  $("health-sum").textContent = `${ok}/${rows.length} 正常`;
  $("health").innerHTML = rows.map(h => {
    const cls = h.flag === "GREEN" ? "ok" : h.flag === "YELLOW" ? "warn" : "bad";
    return `<div class="hrow"><span class="dot ${cls}"></span>
      <span class="hname">${esc(h.source_name)}</span>
      <span class="hnum" title="ok ${h.ok} / zero ${h.zero} / fail ${h.failed}">${Math.round(h.success_rate*100)}%</span></div>`;
  }).join("");
}

function bind(rows){
  const sel = $("src");
  [...new Set(rows.map(r=>r.source_id))].sort().forEach(id => {
    const o = document.createElement("option");
    o.value = id; o.textContent = id; sel.appendChild(o);
  });
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
  sel.onchange = () => { state.src = sel.value; renderList(rows); };
  $("q").oninput = (e) => { state.q = e.target.value; renderList(rows); };
  $("clear").onclick = () => {
    state.domain = "all"; state.conf = "all"; state.src = "all"; state.q = "";
    sel.value = "all"; $("q").value = "";
    renderControls(rows); renderList(rows);
  };
  document.addEventListener("keydown", (e) => {
    if(e.key === "/" && document.activeElement !== $("q")){ e.preventDefault(); $("q").focus(); }
  });
}

const rows = DATA.items || [];
const brandSub = document.querySelector(".brand p");
if(brandSub){
  const srcCount = new Set(rows.map(r => r.source_id)).size;
  brandSub.textContent = `${DATA.date} · ${srcCount} 源 · ${countryCounts(rows).length} 个国家 · RSS 原文，无 LLM 改写`;
}
renderGlobe(rows); renderCountryChart(rows); renderBrief(rows); renderTicker(rows);
renderControls(rows); renderList(rows); renderHealth(); bind(rows);
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
    countries = len({i["source_id"] for i in items})

    html = (
        TEMPLATE.replace("__DATA__", data_json)
        .replace("__HEALTH__", health_json)
        .replace("__DATE__", items_path.stem)
        .replace("__SOURCES__", str(len({i["source_id"] for i in items})))
        .replace("__COUNTRIES__", str(countries))
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


if __name__ == "__main__":
    path = build()
    print(f"生成 {path}  ({path.stat().st_size/1024:.1f} KB)")
