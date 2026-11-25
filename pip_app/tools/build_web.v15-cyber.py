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
<link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet">
<style>
:root{
  --bg0:#03080f; --bg1:#05101d;
  --panel:rgba(7,24,39,.72); --panel-solid:#082033;
  --line:rgba(34,211,238,.20); --line-hi:rgba(34,211,238,.55);
  --cyan:#22d3ee; --cyan-b:#67e8f9; --blue:#38bdf8;
  --amber:#f59e0b; --amber-glow:#fbbf24;
  --text:#d9eefb; --muted:#7ea6c0; --dim:#4d7188;
  --ai:#a78bfa; --geo:#22d3ee; --skills:#38bdf8; --oss:#f59e0b;
  --mono:ui-monospace,"JetBrains Mono","Cascadia Mono",Menlo,monospace;
  --sans:"Rajdhani","Segoe UI",system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
  font-family:var(--sans);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0;min-height:100%;color:var(--text);font-size:14px;line-height:1.6;
  background:
    radial-gradient(1200px 640px at 74% -10%, rgba(34,211,238,.13), transparent 62%),
    radial-gradient(900px 520px at 6% 104%, rgba(56,189,248,.10), transparent 64%),
    var(--bg0);
  background-attachment:fixed;
}
/* 电子网格 */
body::before{
  content:"";position:fixed;inset:0;z-index:0;pointer-events:none;
  background-image:
    linear-gradient(rgba(34,211,238,.055) 1px, transparent 1px),
    linear-gradient(90deg, rgba(34,211,238,.055) 1px, transparent 1px),
    radial-gradient(rgba(34,211,238,.10) 1px, transparent 1px);
  background-size:48px 48px, 48px 48px, 12px 12px;
  -webkit-mask-image:radial-gradient(circle at 52% 42%, #000 24%, transparent 80%);
  mask-image:radial-gradient(circle at 52% 42%, #000 24%, transparent 80%);
}
/* 扫描线 */
body::after{
  content:"";position:fixed;inset:0;z-index:1;pointer-events:none;
  background:repeating-linear-gradient(0deg, rgba(2,10,18,.5) 0 1px, transparent 1px 3px);
  opacity:.30;
}
a{color:inherit;text-decoration:none}
::selection{background:rgba(34,211,238,.3)}

/* ============ HERO ============ */
.hero{position:relative;z-index:3;min-height:clamp(540px,74vh,800px);display:grid;
  grid-template-columns:minmax(380px,500px) minmax(0,1fr);gap:26px;align-items:center;
  padding:44px 30px 96px;max-width:1600px;margin:0 auto;z-index:2}

/* 全息面板 */
.paper{position:relative;padding:26px 28px 22px;color:var(--text);
  background:linear-gradient(158deg, rgba(11,34,54,.94) 0%, rgba(6,20,34,.96) 52%, rgba(4,14,25,.97) 100%);
  border:1px solid var(--line);border-radius:2px;
  box-shadow:0 0 0 1px rgba(34,211,238,.05), 0 26px 64px rgba(0,0,0,.6),
             inset 0 0 46px rgba(34,211,238,.055);
  -webkit-backdrop-filter:blur(7px);backdrop-filter:blur(7px)}
.paper::before{content:"";position:absolute;inset:-1px;pointer-events:none;
  background:
    linear-gradient(var(--cyan),var(--cyan)) left top/20px 2px no-repeat,
    linear-gradient(var(--cyan),var(--cyan)) left top/2px 20px no-repeat,
    linear-gradient(var(--cyan),var(--cyan)) right bottom/20px 2px no-repeat,
    linear-gradient(var(--cyan),var(--cyan)) right bottom/2px 20px no-repeat;
  opacity:.8}
.paper::after{content:"";position:absolute;left:0;right:0;top:0;height:1px;
  background:linear-gradient(90deg,transparent,var(--cyan-b),transparent);opacity:.6;
  animation:scanX 5.5s linear infinite}
@keyframes scanX{0%{transform:translateX(-60%);opacity:0}18%{opacity:.7}100%{transform:translateX(110%);opacity:0}}

.meta-row{display:flex;align-items:center;gap:10px;font-family:var(--mono);
  font-size:9.5px;letter-spacing:1.8px;text-transform:uppercase;color:var(--dim)}
.meta-row .date{margin-left:auto;color:var(--muted)}
.live{display:inline-flex;align-items:center;gap:6px;color:#34d399;letter-spacing:1.4px}
.live i{width:6px;height:6px;border-radius:50%;background:#34d399;box-shadow:0 0 8px #34d399;
  animation:blink 2.2s ease-in-out infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.28}}
.paper h1{margin:10px 0 14px;font-size:38px;font-weight:800;letter-spacing:1.6px;line-height:1.08;
  color:#eaf9ff;text-shadow:0 0 22px rgba(34,211,238,.42), 0 0 2px rgba(255,255,255,.4)}
.paper h1 em{font-style:normal;color:var(--cyan);text-shadow:0 0 26px rgba(34,211,238,.75)}

.nav{display:flex;flex-wrap:wrap;gap:6px 18px;margin:0 0 18px;padding:0 0 15px;
  border-bottom:1px solid rgba(34,211,238,.16)}
.nav a{position:relative;display:inline-flex;align-items:center;gap:6px;
  font-size:12.5px;letter-spacing:.6px;color:var(--muted);padding-bottom:3px;transition:.15s}
.nav a svg{width:13px;height:13px;opacity:.85}
.nav a:hover{color:var(--cyan-b)}
.nav a.on{color:var(--cyan-b);text-shadow:0 0 12px rgba(34,211,238,.6)}
.nav a.on::after{content:"";position:absolute;left:0;right:0;bottom:-1px;height:1px;
  background:linear-gradient(90deg,transparent,var(--cyan),transparent);
  box-shadow:0 0 10px rgba(34,211,238,.8)}

.lede{margin:0 0 20px;font-size:14.5px;line-height:1.72;color:#a9c8db}
.lede b{font-family:var(--mono);font-weight:600;color:var(--cyan-b);letter-spacing:.3px}

/* HUD 统计卡（切角） */
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:9px;margin:0 0 20px}
.stat{position:relative;padding:11px 12px 10px;background:linear-gradient(180deg, rgba(13,40,63,.9), rgba(6,20,34,.92));
  border:1px solid var(--line);
  -webkit-clip-path:polygon(9px 0,100% 0,100% calc(100% - 9px),calc(100% - 9px) 100%,0 100%,0 9px);
  clip-path:polygon(9px 0,100% 0,100% calc(100% - 9px),calc(100% - 9px) 100%,0 100%,0 9px);
  transition:.18s}
.stat:hover{border-color:var(--line-hi);box-shadow:0 0 18px rgba(34,211,238,.18) inset}
.stat .ico{font-family:var(--mono);font-size:10px;color:var(--cyan);opacity:.8;letter-spacing:1px}
.stat b{display:block;margin-top:3px;font-family:var(--mono);font-size:25px;font-weight:700;
  line-height:1.05;color:#eaf9ff;letter-spacing:-.5px;font-variant-numeric:tabular-nums;
  text-shadow:0 0 16px rgba(34,211,238,.35)}
.stat span{display:block;margin-top:3px;font-size:9.5px;letter-spacing:1.6px;
  text-transform:uppercase;color:var(--dim)}

.actions{display:flex;align-items:center;gap:18px;flex-wrap:wrap}
.btn{position:relative;overflow:hidden;border:1px solid var(--line-hi);
  background:linear-gradient(180deg, rgba(16,58,86,.95), rgba(8,32,52,.98));
  color:var(--cyan-b);border-radius:2px;padding:11px 24px;font-family:var(--sans);
  font-size:13px;font-weight:700;letter-spacing:1.2px;cursor:pointer;
  -webkit-clip-path:polygon(10px 0,100% 0,100% calc(100% - 10px),calc(100% - 10px) 100%,0 100%,0 10px);
  clip-path:polygon(10px 0,100% 0,100% calc(100% - 10px),calc(100% - 10px) 100%,0 100%,0 10px);
  box-shadow:0 0 20px rgba(34,211,238,.22), inset 0 0 14px rgba(34,211,238,.12);transition:.18s}
.btn::after{content:"";position:absolute;top:0;bottom:0;width:40%;
  background:linear-gradient(90deg,transparent,rgba(103,232,249,.42),transparent);
  transform:translateX(-140%);animation:btnSweep 3.4s ease-in-out infinite}
@keyframes btnSweep{0%,72%{transform:translateX(-140%)}100%{transform:translateX(320%)}}
.btn:hover{border-color:var(--cyan);color:#fff;box-shadow:0 0 30px rgba(34,211,238,.45), inset 0 0 18px rgba(34,211,238,.2)}
.link{font-size:12.5px;letter-spacing:.6px;color:var(--cyan);cursor:pointer;border-bottom:1px dashed rgba(34,211,238,.4);padding-bottom:1px}
.link:hover{color:var(--cyan-b);border-bottom-color:var(--cyan-b)}
.updated{margin-top:16px;padding-top:13px;border-top:1px solid rgba(34,211,238,.12);
  font-family:var(--mono);font-size:10px;letter-spacing:.8px;color:var(--dim);
  display:flex;align-items:center;gap:8px}
.updated::before{content:"";width:6px;height:6px;border-radius:50%;background:#34d399;
  box-shadow:0 0 9px #34d399;flex:0 0 auto;animation:blink 2.6s ease-in-out infinite}

/* 地球舞台 */
.globe-stage{position:relative;display:flex;align-items:center;justify-content:center;min-height:460px}
.globe-stage canvas{width:min(100%,780px);height:auto;display:block;cursor:grab;touch-action:none;
  filter:drop-shadow(0 0 42px rgba(34,211,238,.20))}
.globe-stage canvas:active{cursor:grabbing}
.globe-hint{position:absolute;right:6px;bottom:2px;font-family:var(--mono);font-size:9.5px;
  letter-spacing:1.2px;color:var(--dim);text-align:right;line-height:1.7;text-transform:uppercase}

/* HUD 胶囊切换 */
.tabs{position:absolute;left:30px;bottom:26px;z-index:6;display:inline-flex;gap:2px;padding:5px;
  background:rgba(6,20,34,.86);border:1px solid var(--line);border-radius:2px;
  -webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);
  box-shadow:0 10px 30px rgba(0,0,0,.5), inset 0 0 20px rgba(34,211,238,.06)}
.tab{border:0;background:transparent;color:var(--muted);font-family:var(--sans);
  font-size:12.5px;font-weight:600;letter-spacing:1px;padding:8px 20px;cursor:pointer;
  border-radius:1px;transition:.16s}
.tab:hover{color:var(--cyan-b)}
.tab.on{background:linear-gradient(180deg, rgba(34,211,238,.20), rgba(34,211,238,.08));
  color:#eaf9ff;box-shadow:inset 0 0 0 1px rgba(34,211,238,.5), 0 0 16px rgba(34,211,238,.28)}

/* ============ PANEL ============ */
.panel{position:relative;z-index:2;max-width:1600px;margin:0 auto;padding:0 30px 72px}
.panel-head{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap;
  padding:8px 2px 14px;border-bottom:1px solid rgba(34,211,238,.16)}
.panel-head h2{margin:0;font-size:24px;font-weight:800;letter-spacing:1.4px;color:#eaf9ff;
  text-shadow:0 0 18px rgba(34,211,238,.35)}
.panel-head span{font-family:var(--mono);font-size:10.5px;letter-spacing:.8px;color:var(--dim)}
.filters{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:14px 0 16px}
.fchip{cursor:pointer;border:1px solid var(--line);background:rgba(9,30,48,.66);
  color:var(--muted);border-radius:2px;padding:5px 11px;font-size:12px;letter-spacing:.4px;
  font-family:var(--sans);transition:.15s}
.fchip:hover{border-color:var(--line-hi);color:var(--cyan-b)}
.fchip.on{background:rgba(34,211,238,.16);border-color:var(--cyan);color:#eaf9ff;
  box-shadow:0 0 14px rgba(34,211,238,.25)}
.filters select,.filters input{border:1px solid var(--line);background:rgba(9,30,48,.72);
  color:var(--text);border-radius:2px;padding:6px 10px;font-size:12px;font-family:var(--mono);
  outline:none}
.filters input{min-width:220px}
.filters input::placeholder{color:var(--dim)}
.filters select:focus,.filters input:focus{border-color:var(--cyan);box-shadow:0 0 0 3px rgba(34,211,238,.14)}
.filters select option{background:#061524;color:var(--text)}
.spacer{flex:1}

/* 情报卡片 */
.list{display:flex;flex-direction:column;gap:10px}
.item{position:relative;padding:14px 18px;color:var(--text);
  background:linear-gradient(150deg, rgba(9,30,48,.82), rgba(5,17,29,.9));
  border:1px solid var(--line);border-left:2px solid var(--dim);border-radius:2px;
  -webkit-backdrop-filter:blur(4px);backdrop-filter:blur(4px);transition:.16s}
.item::after{content:"";position:absolute;left:0;top:0;bottom:0;width:2px;
  background:var(--cyan);opacity:0;transition:.16s}
.item:hover{border-color:var(--line-hi);box-shadow:0 0 26px rgba(34,211,238,.14), inset 0 0 24px rgba(34,211,238,.04);
  transform:translateX(2px)}
.item:hover::after{opacity:.9}
.item.ai{border-left-color:var(--ai)}
.item.geopol{border-left-color:var(--geo)}
.item.skills{border-left-color:var(--skills)}
.item.oss{border-left-color:var(--oss)}
.item h3{margin:0;font-size:16.5px;font-weight:700;line-height:1.45;letter-spacing:.2px;color:#e8f6ff}
.item h3 a:hover{color:var(--cyan-b);text-shadow:0 0 14px rgba(34,211,238,.45)}
.meta{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:7px 0 8px;
  font-family:var(--mono);font-size:10.5px;letter-spacing:.4px;color:var(--dim)}
.tag{display:inline-flex;align-items:center;gap:5px;border-radius:2px;padding:1px 7px;
  font-family:var(--mono);font-size:9.5px;letter-spacing:.8px;text-transform:uppercase;
  border:1px solid transparent}
.tag.dom-ai{background:rgba(167,139,250,.16);color:#c4b5fd;border-color:rgba(167,139,250,.4)}
.tag.dom-geopol{background:rgba(34,211,238,.14);color:var(--cyan-b);border-color:rgba(34,211,238,.4)}
.tag.dom-skills{background:rgba(56,189,248,.14);color:#7dd3fc;border-color:rgba(56,189,248,.4)}
.tag.dom-oss{background:rgba(245,158,11,.14);color:var(--amber-glow);border-color:rgba(245,158,11,.4)}
.tag.high{background:rgba(52,211,153,.14);color:#6ee7b7;border-color:rgba(52,211,153,.4)}
.tag.low{background:rgba(245,158,11,.14);color:var(--amber-glow);border-color:rgba(245,158,11,.4)}
.tag.zh{background:rgba(56,189,248,.14);color:#7dd3fc;border-color:rgba(56,189,248,.4)}
.src{font-weight:600;color:#a9c8db}
.sum{color:#8fb3c9;font-size:12.5px;line-height:1.62;display:-webkit-box;-webkit-line-clamp:2;
  -webkit-box-orient:vertical;overflow:hidden;cursor:pointer}
.sum.open{-webkit-line-clamp:unset;display:block}

/* 分布视图 */
.dist-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.dcard{position:relative;padding:16px 18px 18px;color:var(--text);
  background:linear-gradient(160deg, rgba(10,32,52,.88), rgba(5,17,29,.92));
  border:1px solid var(--line);border-radius:2px;
  box-shadow:inset 0 0 30px rgba(34,211,238,.05)}
.dcard::before{content:"";position:absolute;left:-1px;top:-1px;width:16px;height:16px;
  border-left:1px solid var(--cyan);border-top:1px solid var(--cyan)}
.dcard h3{margin:0 0 14px;font-size:14px;font-weight:700;letter-spacing:1.2px;color:#cfe9f7;
  text-transform:uppercase}
.bars{display:flex;align-items:flex-end;gap:10px;height:172px}
.bar{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;gap:5px;min-width:0}
.bar .v{font-family:var(--mono);font-size:11px;color:var(--cyan-b);font-variant-numeric:tabular-nums}
.bar .col{width:100%;max-width:34px;min-height:4px;
  background:linear-gradient(180deg, rgba(103,232,249,.85), rgba(34,211,238,.25));
  box-shadow:0 0 16px rgba(34,211,238,.35);border-radius:1px 1px 0 0}
.bar.lead .col{background:linear-gradient(180deg, var(--amber-glow), rgba(245,158,11,.3));
  box-shadow:0 0 18px rgba(245,158,11,.45)}
.bar .cc{font-family:var(--mono);font-size:9.5px;letter-spacing:.8px;color:var(--dim);text-transform:uppercase}
.rows .row{display:flex;align-items:center;gap:10px;margin-bottom:10px}
.rows .row:last-child{margin-bottom:0}
.rows .lbl{flex:0 0 70px;font-family:var(--mono);font-size:10.5px;letter-spacing:.6px;color:var(--muted);
  text-transform:uppercase}
.rows .track{flex:1;height:7px;background:rgba(34,211,238,.10);border-radius:1px;overflow:hidden}
.rows .track i{display:block;height:100%;box-shadow:0 0 12px rgba(34,211,238,.4)}
.rows .val{flex:0 0 44px;text-align:right;font-family:var(--mono);font-size:11.5px;
  color:var(--cyan-b);font-variant-numeric:tabular-nums}

/* 健康视图 */
.hgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px}
.hcard{display:flex;align-items:center;gap:10px;padding:10px 13px;color:var(--text);
  background:linear-gradient(150deg, rgba(9,30,48,.8), rgba(5,17,29,.9));
  border:1px solid var(--line);border-radius:2px;transition:.15s}
.hcard:hover{border-color:var(--line-hi);box-shadow:0 0 18px rgba(34,211,238,.14)}
.hcard .dot{width:7px;height:7px;border-radius:50%;flex:0 0 auto}
.dot.ok{background:#34d399;box-shadow:0 0 8px #34d399}
.dot.warn{background:var(--amber);box-shadow:0 0 8px var(--amber)}
.dot.bad{background:#f87171;box-shadow:0 0 8px #f87171}
.hcard .nm{flex:1;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hcard .pc{font-family:var(--mono);font-size:12px;color:var(--cyan-b);font-variant-numeric:tabular-nums}
.hcard .sm{font-family:var(--mono);font-size:9.5px;color:var(--dim)}

.foot{padding:8px 30px 40px;text-align:center;font-family:var(--mono);font-size:10px;
  letter-spacing:1.2px;color:var(--dim);text-transform:uppercase}
.kbd{border:1px solid var(--line);border-radius:2px;padding:0 5px;font-size:10px;color:var(--cyan-b)}
.hidden{display:none}

@media (max-width:1280px){
  .paper h1{font-size:32px}
  .globe-stage canvas{width:min(100%,640px)}
}
@media (max-width:1080px){
  .hero{grid-template-columns:1fr;min-height:auto;padding:26px 18px 84px;gap:10px}
  .globe-stage{order:2;min-height:360px}
  .paper{order:1}
  .tabs{left:16px;bottom:18px}
  .dist-grid{grid-template-columns:1fr}
  .panel{padding:0 18px 60px}
  .stats{grid-template-columns:repeat(4,1fr)}
}
@media (max-width:760px){
  .paper h1{font-size:26px}
  .stats{grid-template-columns:repeat(2,1fr)}
  .globe-stage{min-height:280px}
  .nav{gap:6px 12px}
}
</style>
</head>
<body>

<section class="hero">
  <div class="paper">
    <div class="meta-row">
      <span class="live"><i></i>LIVE</span>
      <span>Daily Intelligence Report</span>
      <span class="date">__DATE__</span>
    </div>
    <h1>PIP <em>情报日报</em></h1>
    <nav class="nav">
      <a href="#panel" data-view="feed" class="on">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M2 4h12M2 8h12M2 12h8"/></svg>今日条目
      </a>
      <a href="#panel" data-view="dist">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M3 13V7M8 13V3M13 13V9"/></svg>分布
      </a>
      <a href="#panel" data-view="health">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><circle cx="8" cy="8" r="6"/><path d="M2 8h12M8 2v12"/></svg>源健康
      </a>
      <a href="#panel" data-view="feed">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M8 2l6 3-6 3-6-3 6-3zM2 8l6 3 6-3M2 11l6 3 6-3"/></svg>全部 __TOTAL__ 条
      </a>
    </nav>
    <p class="lede">
      <b>__TOTAL__</b> 条情报，来自 <b>__SOURCES__</b> 个源、<b id="lede-countries">__COUNTRIES__</b> 个国家；
      其中 <b>__HIGH__</b> 条时间可信度达标，可直接进入日报。
    </p>
    <div class="stats" id="hero-stats"></div>
    <div class="actions">
      <button class="btn" onclick="location.reload()">刷新数据</button>
      <span class="link" id="to-feed">查看全部条目 ›</span>
    </div>
    <p class="updated" id="hero-updated"></p>
  </div>

  <div class="globe-stage">
    <canvas id="globe" width="740" height="740" aria-label="来源城市到采集端的地球投影"></canvas>
    <div class="globe-hint" id="globe-hint">轨迹：来源 → 采集端 · 光纤最低 RTT</div>
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
const LAND = __LAND__;
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

/* 地球：packetvoyage 数据 + 正交投影 + 旋转/缩放 + HUD 外环与全息平台 */
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

  const FALLBACK_LAND = [
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
  const CONTINENTS = (typeof LAND !== "undefined" && LAND && LAND.length) ? LAND : FALLBACK_LAND;

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
    sweep(0, "rgba(103,232,249,.42)", 1.6);
    sweep(Math.PI * 0.9, "rgba(34,211,238,.22)", 1);
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
      ctx.fillStyle = "rgba(22,62,94,.62)";
      ctx.lineWidth = 1;
      ctx.fill(); ctx.stroke();
    });

    ctx.strokeStyle = "rgba(34,211,238,.16)";
    ctx.lineWidth = 0.8;
    for(let lon = -180; lon < 180; lon += 20){
      let started = false;
      ctx.beginPath();
      for(let lat = -90; lat <= 90; lat += 3){
        const [x, y, z] = proj(lat, lon, R);
        if(z > 0){ started ? ctx.lineTo(x, y) : (ctx.moveTo(x, y), started = true); }
        else { started = false; }
      }
      ctx.stroke();
    }
    for(let lat = -80; lat <= 80; lat += 20){
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
    // 来源节点（每个源一点；hq=官网核实，city/approx 半透明）
    (G.sources || []).forEach(n => {
      const [nx, ny, nz] = proj(n.lat, n.lon, R);
      if(nz <= 0.02) return;
      const solid = n.precision === "hq";
      ctx.beginPath();
      ctx.arc(nx, ny, solid ? 2.1 : 1.7, 0, Math.PI * 2);
      ctx.fillStyle = solid ? "rgba(165,243,252,.95)" : "rgba(103,232,249,.55)";
      ctx.fill();
    });

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
        ctx.textAlign = "right";
        ctx.fillText("采集端 " + o.city, ox - pulse - 8, oy + 4);
      }
    }

    /* 球缘 + 状态行 */
    ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.strokeStyle = "rgba(103,232,249,.45)"; ctx.lineWidth = 1.2; ctx.stroke();

    ctx.fillStyle = "#4d7188";
    ctx.font = "10.5px 'JetBrains Mono', ui-monospace, monospace";
    ctx.textAlign = "center";
    const nodeCount = (G.sources || []).length;
    ctx.fillText(`${cities.length} CITIES · ${nodeCount} NODES · ${total} INTEL · DRAG / SCROLL`, cx, cy + R + 58);
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
function renderHeroStats(rows){
  const high = rows.filter(r => r.time_confidence === "high").length;
  const zh = rows.filter(r => r.lang === "zh").length;
  const countries = countryCounts(rows).length;
  const ledeCountries = $("lede-countries");
  if(ledeCountries) ledeCountries.textContent = String(countries);
  const stats = [
    ["源", new Set(rows.map(r => r.source_id)).size],
    ["国家", countryCounts(rows).length],
    ["条目", rows.length],
    ["中文", zh]
  ];
  const icons = ["FEED", "GEO", "INTEL", "ZH"];
  $("hero-stats").innerHTML = stats.map(([k, v], i) =>
    `<div class="stat"><span class="ico">${icons[i] || "DATA"}</span><b>${v}</b><span>${k}</span></div>`).join("");
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
    land_file = ROOT / "data" / "land.json"
    land_json = land_file.read_text(encoding="utf-8") if land_file.exists() else "null"
    high = sum(1 for i in items if i.get("time_confidence") == "high")
    countries = len({i["source_id"] for i in items})

    html = (
        TEMPLATE.replace("__DATA__", data_json)
        .replace("__HEALTH__", health_json)
        .replace("__GLOBE__", globe_json)
        .replace("__LAND__", land_json)
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
