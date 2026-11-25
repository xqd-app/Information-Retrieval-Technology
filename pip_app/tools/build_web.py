"""按参考图整层重做（v1.0 · 全息情报中心）：点阵地球 / 轨道环 / 全息平台 / 矩阵雨 / 双层切角面板。

数据链路不变：
  data/items/*.jsonl      ← collect（真实采集）
  data/globe.json         ← build_globe_data（packetvoyage.geo：坐标/大圆/RTT/昼夜）
  data/land_dots.json     ← build_dots（点阵大陆）
  data/land.json          ← build_land_data（海岸线，兜底用）
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
    return files[-1] if files else ROOT / "data" / "items" / "2026-11-25.jsonl"


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>PIP 情报日报 · __DATE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600;700;900&family=Rajdhani:wght@500;600;700&display=swap" rel="stylesheet">
<style>
:root{
  --void:#02060d; --deep:#04101f; --ink:#06182b;
  --cy:#22d3ee; --cy-b:#7ff3ff; --cy-d:#0e7f96;
  --amber:#ff9a1f; --amber-b:#ffc45c;
  --text:#dfefff; --muted:#7fa8c4; --dim:#446a85;
  --line:rgba(34,211,238,.35); --line-2:rgba(34,211,238,.14);
  --num:"Orbitron","JetBrains Mono",ui-monospace,monospace;
  --sans:"Rajdhani","Segoe UI",system-ui,"PingFang SC","Microsoft YaHei",sans-serif;
  --cut:18px;
}
*{box-sizing:border-box}
a{color:inherit;text-decoration:none}
html{scroll-behavior:smooth}
body{margin:0;min-height:100%;color:var(--text);font-family:var(--sans);font-size:14px;line-height:1.6;
  background:radial-gradient(1200px 700px at 70% 0%, rgba(34,211,238,.10), transparent 60%),
             radial-gradient(900px 600px at 10% 100%, rgba(20,120,160,.14), transparent 62%),
             var(--void);overflow-x:hidden}

#matrix{position:fixed;inset:0;z-index:0;opacity:.7;pointer-events:none}
.vignette{position:fixed;inset:0;z-index:1;pointer-events:none;
  background:radial-gradient(circle at 50% 45%, transparent 30%, rgba(2,6,13,.72) 100%)}
.grid-floor{position:fixed;left:-20%;right:-20%;bottom:-6vh;height:46vh;z-index:1;pointer-events:none;
  background-image:
    linear-gradient(rgba(34,211,238,.20) 1px, transparent 1px),
    linear-gradient(90deg, rgba(34,211,238,.16) 1px, transparent 1px);
  background-size:64px 34px, 64px 34px;
  transform:perspective(340px) rotateX(64deg);
  transform-origin:50% 100%;
  -webkit-mask-image:linear-gradient(to top, #000 6%, transparent 82%);
  mask-image:linear-gradient(to top, #000 6%, transparent 82%);
  opacity:.55}
.scan{position:fixed;inset:0;z-index:2;pointer-events:none;
  background:repeating-linear-gradient(0deg, rgba(0,0,0,.32) 0 1px, transparent 1px 3px);opacity:.45}

.hud-system{position:fixed;top:18px;right:24px;z-index:30;display:inline-flex;align-items:center;gap:9px;
  padding:7px 16px;font-family:var(--num);font-size:10.5px;letter-spacing:2.2px;color:#bdf7c9;
  background:linear-gradient(180deg, rgba(6,26,20,.9), rgba(4,18,14,.92));
  border:1px solid rgba(74,222,128,.45);
  clip-path:polygon(10px 0,100% 0,100% calc(100% - 10px),calc(100% - 10px) 100%,0 100%,0 10px);
  box-shadow:0 0 22px rgba(74,222,128,.25)}
.hud-system i{width:7px;height:7px;border-radius:50%;background:#4ade80;box-shadow:0 0 10px #4ade80;
  animation:blink 2s ease-in-out infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.25}}

.hero{position:relative;z-index:5;display:grid;grid-template-columns:minmax(430px,560px) minmax(0,1fr);
  align-items:center;gap:2px;min-height:clamp(540px,78vh,820px);max-width:1780px;margin:0 auto;
  padding:34px 26px 96px}

.panel{position:relative;padding:2px;
  background:linear-gradient(145deg, var(--cy), rgba(34,211,238,.15) 42%, rgba(14,127,150,.5));
  clip-path:polygon(var(--cut) 0,100% 0,100% calc(100% - var(--cut)),calc(100% - var(--cut)) 100%,0 100%,0 var(--cut));
  filter:drop-shadow(0 0 26px rgba(34,211,238,.32)) drop-shadow(0 22px 60px rgba(0,0,0,.7))}
.panel-inner{position:relative;padding:22px 26px 18px;
  background:linear-gradient(160deg, rgba(6,24,41,.97) 0%, rgba(4,14,26,.98) 55%, rgba(3,10,19,.99) 100%);
  clip-path:polygon(var(--cut) 0,100% 0,100% calc(100% - var(--cut)),calc(100% - var(--cut)) 100%,0 100%,0 var(--cut))}
.panel-inner::before{content:"";position:absolute;inset:0;pointer-events:none;opacity:.5;
  background:repeating-linear-gradient(135deg, rgba(34,211,238,.10) 0 2px, transparent 2px 9px);
  -webkit-mask-image:linear-gradient(115deg, #000 0 22%, transparent 34%);
  mask-image:linear-gradient(115deg, #000 0 22%, transparent 34%)}
.panel-inner::after{content:"";position:absolute;left:0;right:0;top:0;height:1px;
  background:linear-gradient(90deg,transparent,var(--cy-b),transparent);opacity:.85;
  animation:sweep 4.6s linear infinite}
@keyframes sweep{0%{transform:translateX(-70%);opacity:0}20%{opacity:.9}100%{transform:translateX(115%);opacity:0}}
.stripes{position:absolute;top:10px;right:16px;width:96px;height:10px;opacity:.75;
  background:repeating-linear-gradient(115deg, var(--cy) 0 3px, transparent 3px 10px);
  clip-path:polygon(0 0,100% 0,88% 100%,0 100%)}

.hacker-out{position:absolute;left:26px;top:26px;width:158px;height:200px;z-index:6;pointer-events:none;
  object-fit:contain;object-position:top left;
  filter:drop-shadow(0 0 24px rgba(34,211,238,.5)) drop-shadow(0 0 60px rgba(34,211,238,.22))}

.brand{display:flex;align-items:flex-end;gap:12px;margin:6px 0 2px;padding-left:118px;min-height:64px}
.brand h1{margin:0;font-size:40px;font-weight:800;letter-spacing:3px;line-height:1;
  color:#f2fbff;text-shadow:0 0 26px rgba(34,211,238,.65),0 0 3px rgba(255,255,255,.9)}
.brand h1 em{font-style:normal;color:var(--cy-b);text-shadow:0 0 30px rgba(34,211,238,.9)}
.brand .spark{width:10px;height:26px;background:var(--cy);box-shadow:0 0 18px var(--cy);transform:skewX(-18deg)}
.sub{margin:2px 0 18px;padding-left:118px;font-family:var(--num);font-size:10.5px;letter-spacing:2.4px;color:var(--dim)}

.nav{display:flex;gap:6px;margin:0 0 16px;padding:0 0 14px;border-bottom:1px solid var(--line-2);flex-wrap:wrap}
.nav a{position:relative;display:inline-flex;align-items:center;gap:8px;padding:6px 12px;
  font-size:13.5px;font-weight:600;letter-spacing:.6px;color:var(--muted);transition:.16s}
.nav a svg{width:15px;height:15px;opacity:.9}
.nav a:hover{color:var(--cy-b)}
.nav a.on{color:#eafcff;text-shadow:0 0 14px rgba(34,211,238,.8)}
.nav a.on::after{content:"";position:absolute;left:10px;right:10px;bottom:-1px;height:2px;
  background:linear-gradient(90deg,transparent,var(--cy),transparent);box-shadow:0 0 14px var(--cy)}

.lede{position:relative;margin:0 0 18px;padding-left:14px;font-size:14.5px;line-height:1.75;color:#b9d5e8}
.lede::before{content:"";position:absolute;left:0;top:3px;bottom:3px;width:2px;
  background:linear-gradient(180deg,var(--cy),rgba(34,211,238,0));box-shadow:0 0 12px rgba(34,211,238,.8)}
.lede b{font-family:var(--num);font-weight:700;color:var(--cy-b);font-size:14px;text-shadow:0 0 14px rgba(34,211,238,.5)}

.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:0 0 18px}
.stat{position:relative;padding:12px 12px 10px;text-align:center;
  background:linear-gradient(180deg, rgba(10,40,64,.92), rgba(4,16,28,.95));
  border:1px solid var(--line);
  clip-path:polygon(14px 0,calc(100% - 14px) 0,100% 14px,100% calc(100% - 14px),calc(100% - 14px) 100%,14px 100%,0 calc(100% - 14px),0 14px);
  box-shadow:inset 0 0 26px rgba(34,211,238,.10);transition:.18s}
.stat:hover{box-shadow:inset 0 0 34px rgba(34,211,238,.22), 0 0 22px rgba(34,211,238,.18)}
.stat .ico{font-family:var(--num);font-size:9px;letter-spacing:1.4px;color:var(--cy);opacity:.9;display:block;margin-bottom:4px}
.stat b{display:block;font-family:var(--num);font-size:32px;font-weight:700;line-height:1.05;color:#f2fbff;
  letter-spacing:-1px;text-shadow:0 0 20px rgba(34,211,238,.55)}
.stat span{display:block;margin-top:2px;font-size:10px;letter-spacing:2px;color:var(--dim)}

.actions{display:flex;align-items:center;gap:22px;flex-wrap:wrap}
.btn{position:relative;display:inline-flex;align-items:center;gap:9px;overflow:hidden;cursor:pointer;
  padding:11px 26px 11px 20px;font-family:var(--sans);font-size:14px;font-weight:700;letter-spacing:1.4px;
  color:#d8feff;background:linear-gradient(180deg, rgba(12,54,78,.95), rgba(6,26,42,.98));
  border:1px solid var(--cy);
  clip-path:polygon(12px 0,100% 0,100% calc(100% - 12px),calc(100% - 12px) 100%,0 100%,0 12px);
  box-shadow:0 0 24px rgba(34,211,238,.35), inset 0 0 18px rgba(34,211,238,.18);transition:.18s}
.btn svg{width:16px;height:16px}
.btn::after{content:"";position:absolute;top:0;bottom:0;width:36%;
  background:linear-gradient(90deg,transparent,rgba(127,243,255,.5),transparent);
  transform:translateX(-150%);animation:btnSweep 3.6s ease-in-out infinite}
@keyframes btnSweep{0%,70%{transform:translateX(-150%)}100%{transform:translateX(330%)}}
.btn:hover{background:linear-gradient(180deg, rgba(20,78,108,.98), rgba(8,34,54,.99));
  box-shadow:0 0 34px rgba(34,211,238,.6), inset 0 0 22px rgba(34,211,238,.28)}
.link{font-family:var(--num);font-size:11.5px;letter-spacing:1.2px;color:var(--cy);cursor:pointer;
  border-bottom:1px dashed rgba(34,211,238,.45);padding-bottom:2px}
.link:hover{color:var(--cy-b);border-bottom-color:var(--cy-b)}
.updated{margin:16px 0 0;padding-top:13px;border-top:1px solid var(--line-2);
  display:flex;align-items:center;gap:9px;font-family:var(--num);font-size:10.5px;letter-spacing:1px;color:var(--dim)}
.updated::before{content:"";width:7px;height:7px;border-radius:50%;background:#4ade80;
  box-shadow:0 0 10px #4ade80;animation:blink 2.4s ease-in-out infinite}

.globe-stage{position:relative;display:flex;align-items:center;justify-content:center;min-height:520px}
.globe-stage canvas{width:min(100%,860px);height:auto;display:block;cursor:grab;touch-action:none}
.globe-stage canvas:active{cursor:grabbing}
.globe-caption{position:absolute;left:50%;bottom:11%;transform:translateX(-50%);
  display:inline-flex;align-items:center;gap:14px;padding:7px 22px;
  font-family:var(--num);font-size:11px;letter-spacing:2px;color:#cdefff;
  background:linear-gradient(180deg, rgba(6,26,42,.94), rgba(3,12,22,.96));
  border:1px solid var(--line);
  clip-path:polygon(12px 0,calc(100% - 12px) 0,100% 50%,calc(100% - 12px) 100%,12px 100%,0 50%);
  box-shadow:0 0 22px rgba(34,211,238,.28)}
.globe-caption i{font-style:normal;color:var(--cy);letter-spacing:-1px}
.globe-legend{position:absolute;left:6px;top:6px;text-align:left;font-family:var(--num);
  font-size:9px;letter-spacing:1.2px;color:var(--dim);line-height:1.9}

.tabs{position:absolute;left:26px;bottom:22px;z-index:8;display:inline-flex;gap:2px;padding:4px;
  background:rgba(4,16,28,.9);border:1px solid var(--line);
  clip-path:polygon(10px 0,100% 0,100% calc(100% - 10px),calc(100% - 10px) 100%,0 100%,0 10px)}
.tab{border:0;background:transparent;color:var(--dim);font-family:var(--sans);font-size:12.5px;
  font-weight:700;letter-spacing:1.4px;padding:7px 18px;cursor:pointer;transition:.16s}
.tab:hover{color:var(--cy-b)}
.tab.on{color:#02121c;background:linear-gradient(180deg,var(--cy-b),var(--cy));
  box-shadow:0 0 20px rgba(34,211,238,.6)}

.panel-list{position:relative;z-index:5;max-width:1780px;margin:0 auto;padding:0 26px 74px}
.list-head{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap;
  padding:6px 2px 12px;border-bottom:1px solid var(--line)}
.list-head h2{margin:0;font-family:var(--num);font-size:22px;font-weight:700;letter-spacing:2.4px;color:#eafcff;
  text-shadow:0 0 20px rgba(34,211,238,.5)}
.list-head span{font-family:var(--num);font-size:10px;letter-spacing:1.4px;color:var(--dim)}
.filters{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:14px 0}
.fchip{cursor:pointer;border:1px solid var(--line-2);background:rgba(6,24,40,.7);color:var(--muted);
  padding:5px 12px;font-family:var(--sans);font-size:12px;font-weight:600;letter-spacing:.6px;transition:.15s;
  clip-path:polygon(7px 0,100% 0,100% calc(100% - 7px),calc(100% - 7px) 100%,0 100%,0 7px)}
.fchip:hover{border-color:var(--line);color:var(--cy-b)}
.fchip.on{border-color:var(--cy);color:#eafcff;background:rgba(34,211,238,.18);
  box-shadow:0 0 16px rgba(34,211,238,.28)}
.filters select,.filters input{border:1px solid var(--line-2);background:rgba(6,24,40,.8);color:var(--text);
  padding:6px 10px;font-family:var(--num);font-size:11px;letter-spacing:.6px;outline:none}
.filters input{min-width:220px}
.filters select:focus,.filters input:focus{border-color:var(--cy);box-shadow:0 0 0 3px rgba(34,211,238,.14)}
.filters select option{background:#04101f}
.spacer{flex:1}

.list{display:flex;flex-direction:column;gap:8px}
.item{position:relative;padding:13px 18px;color:var(--text);
  background:linear-gradient(150deg, rgba(7,26,44,.86), rgba(3,12,22,.92));
  border:1px solid var(--line-2);border-left:2px solid var(--dim);transition:.15s}
.item::before{content:"";position:absolute;left:-1px;top:-1px;width:10px;height:10px;
  border-left:1px solid var(--cy);border-top:1px solid var(--cy);opacity:0;transition:.15s}
.item:hover{border-color:var(--line);box-shadow:0 0 26px rgba(34,211,238,.16);transform:translateX(2px)}
.item:hover::before{opacity:1}
.item.ai{border-left-color:#a78bfa}
.item.geopol{border-left-color:var(--cy)}
.item.skills{border-left-color:#38bdf8}
.item.oss{border-left-color:var(--amber)}
.item h3{margin:0;font-size:16.5px;font-weight:700;letter-spacing:.2px;line-height:1.45;color:#eaf6ff}
.item h3 a:hover{color:var(--cy-b);text-shadow:0 0 14px rgba(34,211,238,.5)}
.meta{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:7px 0 7px;
  font-family:var(--num);font-size:9.5px;letter-spacing:.9px;color:var(--dim)}
.tag{display:inline-flex;align-items:center;padding:1px 7px;font-family:var(--num);font-size:9px;
  letter-spacing:1px;border:1px solid transparent}
.tag.dom-ai{background:rgba(167,139,250,.16);color:#c4b5fd;border-color:rgba(167,139,250,.45)}
.tag.dom-geopol{background:rgba(34,211,238,.14);color:var(--cy-b);border-color:rgba(34,211,238,.45)}
.tag.dom-skills{background:rgba(56,189,248,.14);color:#7dd3fc;border-color:rgba(56,189,248,.45)}
.tag.dom-oss{background:rgba(255,154,31,.14);color:var(--amber-b);border-color:rgba(255,154,31,.45)}
.tag.high{background:rgba(52,211,153,.14);color:#6ee7b7;border-color:rgba(52,211,153,.45)}
.tag.low{background:rgba(255,154,31,.14);color:var(--amber-b);border-color:rgba(255,154,31,.45)}
.tag.zh{background:rgba(56,189,248,.14);color:#7dd3fc;border-color:rgba(56,189,248,.45)}
.src{font-weight:700;color:#b9d5e8;letter-spacing:.4px;font-family:var(--sans);font-size:11px}
.sum{color:#93b8d0;font-size:12.5px;line-height:1.62;display:-webkit-box;-webkit-line-clamp:2;
  -webkit-box-orient:vertical;overflow:hidden;cursor:pointer}
.sum.open{-webkit-line-clamp:unset;display:block}

.dist-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.dcard{position:relative;padding:16px 18px 18px;background:linear-gradient(160deg, rgba(8,30,50,.9), rgba(3,12,22,.94));
  border:1px solid var(--line-2);
  clip-path:polygon(14px 0,100% 0,100% calc(100% - 14px),calc(100% - 14px) 100%,0 100%,0 14px)}
.dcard h3{margin:0 0 14px;font-family:var(--num);font-size:12px;font-weight:700;letter-spacing:2px;color:#cdefff}
.bars{display:flex;align-items:flex-end;gap:10px;height:176px}
.bar{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;gap:5px;min-width:0}
.bar .v{font-family:var(--num);font-size:10.5px;color:var(--cy-b)}
.bar .col{width:100%;max-width:32px;min-height:4px;
  background:linear-gradient(180deg, var(--cy-b), rgba(34,211,238,.2));
  box-shadow:0 0 16px rgba(34,211,238,.45)}
.bar.lead .col{background:linear-gradient(180deg, var(--amber-b), rgba(255,154,31,.25));
  box-shadow:0 0 18px rgba(255,154,31,.5)}
.bar .cc{font-family:var(--num);font-size:8.5px;letter-spacing:1px;color:var(--dim)}
.rows .row{display:flex;align-items:center;gap:10px;margin-bottom:10px}
.rows .lbl{flex:0 0 72px;font-family:var(--num);font-size:9.5px;letter-spacing:1px;color:var(--muted)}
.rows .track{flex:1;height:6px;background:rgba(34,211,238,.10);overflow:hidden}
.rows .track i{display:block;height:100%;box-shadow:0 0 12px rgba(34,211,238,.5)}
.rows .val{flex:0 0 44px;text-align:right;font-family:var(--num);font-size:10.5px;color:var(--cy-b)}
.wgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px}
.wcard{position:relative;padding:14px 16px;background:linear-gradient(155deg, rgba(8,30,50,.9), rgba(3,12,22,.94));
  border:1px solid var(--line-2);
  clip-path:polygon(12px 0,100% 0,100% calc(100% - 12px),calc(100% - 12px) 100%,0 100%,0 12px);transition:.16s}
.wcard:hover{border-color:var(--line);box-shadow:0 0 22px rgba(34,211,238,.18)}
.wcard.wide{grid-column:1/-1}
.wcard.blind{opacity:.62;border-style:dashed}
.wcard.thin{border-color:rgba(255,154,31,.45)}
.wcard.covered{border-color:rgba(34,211,238,.4)}
.wcard h4{margin:0;font-family:var(--num);font-size:12px;letter-spacing:1.8px;color:#cdefff}
.wtop{display:flex;align-items:center;gap:8px;margin-bottom:10px}
.wdot{width:7px;height:7px;border-radius:50%;flex:0 0 auto}
.covered .wdot{background:#22d3ee;box-shadow:0 0 10px #22d3ee}
.thin .wdot{background:#ff9a1f;box-shadow:0 0 10px #ff9a1f}
.blind .wdot{background:#446a85}
.wtg{margin-left:auto;font-family:var(--num);font-size:8.5px;letter-spacing:1.2px;color:var(--dim)}
.wnum{display:flex;align-items:baseline;gap:5px;margin-bottom:6px}
.wnum b{font-family:var(--num);font-size:20px;font-weight:700;color:#eafcff;text-shadow:0 0 14px rgba(34,211,238,.4)}
.wnum span{font-size:9.5px;color:var(--dim);margin-right:8px}
.wct{margin:0;font-size:10.5px;line-height:1.6;color:var(--muted);font-family:var(--num);letter-spacing:.4px}
.wcover{display:flex;align-items:center;gap:26px;flex-wrap:wrap;margin:6px 0 10px}
.wring{position:relative;width:96px;height:96px;border-radius:50%;flex:0 0 auto;
  background:conic-gradient(var(--cy) calc(var(--pct) * 1%), rgba(34,211,238,.10) 0);
  display:flex;align-items:center;justify-content:center;
  box-shadow:0 0 26px rgba(34,211,238,.28), inset 0 0 22px rgba(2,10,18,.9)}
.wring::after{content:"";position:absolute;inset:7px;border-radius:50%;background:#04101d}
.wring span{position:relative;z-index:1;font-family:var(--num);font-size:24px;font-weight:700;color:#eafcff;
  text-shadow:0 0 16px rgba(34,211,238,.6)}
.wring span i{font-style:normal;font-size:11px;color:var(--cy);margin-left:1px}
.wstats{display:grid;grid-template-columns:repeat(2,minmax(82px,1fr));gap:8px 20px}
.wstats div{display:flex;flex-direction:column}
.wstats b{font-family:var(--num);font-size:17px;color:#dff6ff}
.wstats span{font-size:9.5px;letter-spacing:1.2px;color:var(--dim)}
.wblind{margin:0;font-family:var(--num);font-size:10px;letter-spacing:.8px;color:var(--muted)}
.hgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:9px}
.hcard{display:flex;align-items:center;gap:10px;padding:10px 13px;
  background:linear-gradient(150deg, rgba(7,26,44,.86), rgba(3,12,22,.92));
  border:1px solid var(--line-2);transition:.15s}
.hcard:hover{border-color:var(--line);box-shadow:0 0 18px rgba(34,211,238,.18)}
.hcard .dot{width:7px;height:7px;border-radius:50%;flex:0 0 auto}
.dot.ok{background:#4ade80;box-shadow:0 0 9px #4ade80}
.dot.warn{background:var(--amber);box-shadow:0 0 9px var(--amber)}
.dot.bad{background:#f87171;box-shadow:0 0 9px #f87171}
.hcard .nm{flex:1;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#cde3f2}
.hcard .pc{font-family:var(--num);font-size:11px;color:var(--cy-b)}
.hcard .sm{font-family:var(--num);font-size:9px;color:var(--dim)}
.hidden{display:none}
.foot{padding:10px 26px 44px;text-align:center;font-family:var(--num);font-size:9.5px;
  letter-spacing:2px;color:var(--dim)}
.kbd{border:1px solid var(--line-2);padding:0 5px;font-size:9px;color:var(--cy-b)}

@media (max-width:1280px){
  .hero{grid-template-columns:minmax(400px,520px) minmax(0,1fr)}
  .brand h1{font-size:34px}
  .globe-stage canvas{width:min(100%,700px)}
}
@media (max-width:1080px){
  .hero{grid-template-columns:1fr;min-height:auto;padding:64px 16px 90px;gap:16px}
  .panel{order:1}
  .globe-stage{order:2;min-height:400px}
  .brand,.sub{padding-left:96px}
  .hacker-out{width:120px;height:152px;left:14px;top:18px}
  .tabs{position:static;margin-top:6px}
  .dist-grid{grid-template-columns:1fr}
  .panel-list{padding:0 16px 60px}
  .hud-system{display:none}
}
@media (max-width:760px){
  .brand h1{font-size:26px;letter-spacing:2px}
  .brand,.sub{padding-left:0}
  .hacker-out{display:none}
  .stats{grid-template-columns:repeat(2,1fr)}
  .stat b{font-size:26px}
  .globe-stage{min-height:300px}
}
</style>
</head>
<body>
<canvas id="matrix" aria-hidden="true"></canvas>
<div class="vignette"></div>
<div class="grid-floor"></div>
<div class="scan"></div>

<div class="hud-system"><i></i>SYSTEM ONLINE</div>

<section class="hero">
  <img class="hacker-out" src="data:image/png;base64,__HACKER__" alt=""/>
  <div class="panel">
    <div class="panel-inner">
      <div class="stripes"></div>

      <div class="brand"><span class="spark"></span><h1>PIP <em>情报日报</em></h1></div>
      <p class="sub">__DATE__ · DAILY INTELLIGENCE REPORT</p>

      <nav class="nav">
        <a href="#panel" data-view="feed" class="on">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="3" width="12" height="11" rx="1"/><path d="M2 6h12"/></svg>今日条目
        </a>
        <a href="#panel" data-view="dist">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 13V8M8 13V3M13 13V10"/></svg>分布
        </a>
        <a href="#panel" data-view="health">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="8" r="6"/><path d="M2 8h12M8 2c2 2 2 10 0 12M8 2c-2 2-2 10 0 12"/></svg>源健康
        </a>
        <a href="#panel" data-view="world">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="8" r="6"/><path d="M2 8h12"/><path d="M8 2c2.5 2 2.5 10 0 12"/></svg>全球扫描
        </a>
        <a href="#panel" data-view="feed">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M8 2l6 3-6 3-6-3 6-3zM2 8l6 3 6-3M2 11.5l6 3 6-3"/></svg>全部 __TOTAL__ 条
        </a>
      </nav>

      <p class="lede">
        <b>__TOTAL__</b> 条情报，来自 <b>__SOURCES__</b> 个源、<b id="lede-countries">__COUNTRIES__</b> 个国家；
        其中 <b>__HIGH__</b> 条时间可信度达标，可直接进入日报。
      </p>

      <div class="stats" id="hero-stats"></div>

      <div class="actions">
        <button class="btn" onclick="location.reload()">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6">
            <path d="M13 8a5 5 0 1 1-1.6-3.7"/><path d="M13 2v3.2H9.8"/></svg>
          刷新数据
        </button>
        <span class="link" id="to-feed">查看全部条目 ›</span>
      </div>

      <p class="updated" id="hero-updated"></p>
    </div>
  </div>

  <div class="globe-stage">
    <canvas id="globe" width="880" height="880" aria-label="情报来源与采集端的三维投影"></canvas>
    <div class="globe-legend" id="globe-legend"></div>
    <div class="globe-caption"><i>&#8249;&#8249;&#8249;</i><span id="globe-caption-text">LOADING</span><i>&#8250;&#8250;&#8250;</i></div>
  </div>

  <div class="tabs" id="tabs">
    <button class="tab on" data-view="feed">条目</button>
    <button class="tab" data-view="dist">分布</button>
    <button class="tab" data-view="health">健康</button>
    <button class="tab" data-view="world">世界</button>
  </div>
</section>

<section class="panel-list" id="panel">
  <div class="list-head">
    <h2 id="panel-title">今日条目</h2>
    <span id="panel-sub"></span>
  </div>
  <div class="filters" id="filters">
    <span class="fchip on" data-domain="all">全部</span>
    <div id="domain-chips" style="display:flex;gap:8px;flex-wrap:wrap"></div>
    <span class="fchip on" data-conf="all">全部可信度</span>
    <span class="fchip" data-conf="high">高可信</span>
    <span class="fchip" data-conf="low">低（不进日报）</span>
    <select id="src" style="max-width:190px"><option value="all">全部来源</option></select>
    <input id="q" placeholder="搜索标题 / 摘要…  按 / 聚焦"/>
    <span class="spacer"></span>
    <span id="count" style="font-family:var(--num);font-size:10px;letter-spacing:1px;color:var(--dim)"></span>
  </div>

  <div id="view-feed" class="list"></div>
  <div id="view-dist" class="dist-grid hidden"></div>
  <div id="view-health" class="hgrid hidden"></div>
  <div id="view-world" class="wgrid hidden"></div>
</section>

<div class="foot">PIP v1.0 · INTELLIGENCE COMMAND CENTER · __SOURCES__ SOURCES · PRESS <span class="kbd">/</span> TO SEARCH</div>

<script>
const DATA = __DATA__;
const HEALTH = __HEALTH__;
const GLOBE = __GLOBE__;
const LAND = __LAND__;
const LAND_DOTS = __LAND_DOTS__;
const WORLD = __WORLD__;

const DOMAIN_META = {ai:"AI", geopol:"政经", skills:"AI 技能", oss:"GitHub"};
const DOMAIN_COLOR = {ai:"#a78bfa", geopol:"#22d3ee", skills:"#38bdf8", oss:"#ff9a1f"};
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

/* ================= 矩阵雨 ================= */
function initMatrix(){
  const cv = $("matrix");
  if(!cv) return;
  const ctx = cv.getContext("2d");
  const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
  let w, h, cols, drops, size = 16;
  const glyphs = "01ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉ0123456789ABCDEF".split("");

  function resize(){
    w = cv.width = Math.floor(window.innerWidth * dpr);
    h = cv.height = Math.floor(window.innerHeight * dpr);
    cv.style.width = window.innerWidth + "px";
    cv.style.height = window.innerHeight + "px";
    ctx.font = (size * dpr) + "px monospace";
    cols = Math.ceil(w / (size * dpr));
    drops = Array(cols).fill(0).map(() => Math.random() * -40);
  }
  resize();
  window.addEventListener("resize", resize);

  function frame(){
    ctx.fillStyle = "rgba(2,6,13,.14)";
    ctx.fillRect(0, 0, w, h);
    for(let i = 0; i < cols; i++){
      const ch = glyphs[(Math.random() * glyphs.length) | 0];
      const x = i * size * dpr, y = drops[i] * size * dpr;
      ctx.fillStyle = Math.random() > 0.93 ? "rgba(210,255,255,.95)" : "rgba(34,211,238,.62)";
      ctx.fillText(ch, x, y);
      if(y > h && Math.random() > 0.975) drops[i] = 0;
      drops[i] += 1;
    }
    setTimeout(() => requestAnimationFrame(frame), 90);
  }
  frame();
}

/* ================= 地球 ================= */
function renderGlobe(){
  const cv = $("globe");
  if(!cv || !cv.getContext) return;
  const ctx = cv.getContext("2d");
  const SIZE = 880, dpr = Math.min(window.devicePixelRatio || 1, 2);
  cv.width = SIZE * dpr; cv.height = SIZE * dpr;
  cv.style.width = SIZE + "px"; cv.style.height = SIZE + "px";
  ctx.scale(dpr, dpr);

  const cx = SIZE / 2, cy = SIZE / 2 - 10, RAD = Math.PI / 180;
  let zoom = 1;
  const R0 = SIZE * 0.235;

  const G = GLOBE || {cities: [], sources: [], origin: null, solar: {lat: 0, lon: 0}};
  const cities = G.cities || [];
  const dots = (typeof LAND_DOTS !== "undefined" && LAND_DOTS) ? LAND_DOTS : [];
  const maxCount = Math.max(1, ...cities.map(c => c.count));
  const total = cities.reduce((s, c) => s + c.count, 0) || 1;
  const originCity = (G.origin && G.origin.city) || "";
  let lat0 = 24, lon0 = -55, spin = 0.045, dragging = false, lastX = 0, lastY = 0;

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

    ctx.save();
    ctx.translate(cx, cy);
    for(let i = 0; i < 3; i++){
      const rr = R * (1.18 + i * 0.13);
      const rot = t * 0.0035 + i * 0.7;
      ctx.beginPath();
      ctx.ellipse(0, 0, rr, rr * (0.30 + i * 0.06), rot, 0, Math.PI * 2);
      ctx.strokeStyle = i === 0 ? "rgba(127,243,255,.55)" : i === 1 ? "rgba(34,211,238,.35)" : "rgba(34,211,238,.20)";
      ctx.lineWidth = i === 0 ? 1.6 : 1;
      ctx.stroke();
    }
    ctx.beginPath();
    ctx.arc(0, 0, R * 1.14, t * 0.014, t * 0.014 + 0.9);
    ctx.strokeStyle = "rgba(127,243,255,.55)"; ctx.lineWidth = 2; ctx.stroke();
    ctx.restore();

    const py = cy + R * 0.96;
    for(let i = 0; i < 4; i++){
      ctx.beginPath();
      ctx.ellipse(cx, py + i * 10, R * (1.22 - i * 0.10), R * (0.24 - i * 0.035), 0, 0, Math.PI * 2);
      ctx.strokeStyle = i === 0 ? "rgba(127,243,255,.6)" : "rgba(34,211,238,.22)";
      ctx.lineWidth = i === 0 ? 1.8 : 1;
      ctx.stroke();
    }
    const plat = ctx.createRadialGradient(cx, py, 6, cx, py, R * 1.3);
    plat.addColorStop(0, "rgba(34,211,238,.35)");
    plat.addColorStop(.5, "rgba(34,211,238,.12)");
    plat.addColorStop(1, "rgba(34,211,238,0)");
    ctx.fillStyle = plat;
    ctx.beginPath(); ctx.ellipse(cx, py, R * 1.3, R * 0.3, 0, 0, Math.PI * 2); ctx.fill();

    const halo = ctx.createRadialGradient(cx, cy, R * 0.9, cx, cy, R * 1.55);
    halo.addColorStop(0, "rgba(34,211,238,.28)");
    halo.addColorStop(1, "rgba(34,211,238,0)");
    ctx.fillStyle = halo;
    ctx.beginPath(); ctx.arc(cx, cy, R * 1.55, 0, Math.PI * 2); ctx.fill();

    const solar = G.solar || {lat: 0, lon: 0};
    const [sx, sy, sz] = proj(solar.lat, solar.lon, R);
    const gx = sz > 0 ? sx : cx + (sx - cx) * -1;
    const gy = sz > 0 ? sy : cy + (sy - cy) * -1;
    const sphere = ctx.createRadialGradient(gx, gy, R * 0.05, cx, cy, R * 1.03);
    sphere.addColorStop(0, "rgba(58,152,205,.95)");
    sphere.addColorStop(.45, "rgba(12,48,78,.97)");
    sphere.addColorStop(1, "rgba(4,16,28,1)");
    ctx.fillStyle = sphere;
    ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.fill();

    ctx.save();
    ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.clip();
    const buckets = [[], [], []];
    for(let i = 0; i < dots.length; i++){
      const d = dots[i];
      const [x, y, z] = proj(d[0], d[1], R);
      if(z <= 0.02) continue;
      buckets[z > 0.62 ? 0 : z > 0.3 ? 1 : 2].push(x, y);
    }
    const alphas = [1, 0.78, 0.5], sizes = [2.1, 1.8, 1.5];
    buckets.forEach((arr, bi) => {
      ctx.fillStyle = "rgba(140,232,255," + alphas[bi] + ")";
      for(let i = 0; i < arr.length; i += 2) ctx.fillRect(arr[i], arr[i + 1], sizes[bi], sizes[bi]);
    });

    ctx.strokeStyle = "rgba(34,211,238,.13)";
    ctx.lineWidth = 0.7;
    for(let lon = -180; lon < 180; lon += 20){
      let started = false;
      ctx.beginPath();
      for(let lat = -90; lat <= 90; lat += 4){
        const p = proj(lat, lon, R);
        if(p[2] > 0){ started ? ctx.lineTo(p[0], p[1]) : (ctx.moveTo(p[0], p[1]), started = true); }
        else started = false;
      }
      ctx.stroke();
    }
    for(let lat = -80; lat <= 80; lat += 20){
      let started = false;
      ctx.beginPath();
      for(let lon = -180; lon <= 180; lon += 4){
        const p = proj(lat, lon, R);
        if(p[2] > 0){ started ? ctx.lineTo(p[0], p[1]) : (ctx.moveTo(p[0], p[1]), started = true); }
        else started = false;
      }
      ctx.stroke();
    }
    ctx.restore();

    cities.forEach(c => {
      const hot = c.count >= maxCount * 0.6;
      ctx.lineWidth = hot ? 2.6 : 1.8;
      ctx.strokeStyle = hot ? "rgba(255,154,31,.95)" : "rgba(127,243,255,.7)";
      ctx.setLineDash([7, 10]);
      ctx.lineDashOffset = -t * 2.2;
      let started = false;
      ctx.beginPath();
      (c.arc || []).forEach(pt => {
        const q = proj(pt[0], pt[1], R);
        if(q[2] > 0.02){ started ? ctx.lineTo(q[0], q[1]) : (ctx.moveTo(q[0], q[1]), started = true); }
        else started = false;
      });
      ctx.stroke();
      ctx.setLineDash([]);
    });

    const placed = [];
    const labelled = cities.slice(0, 1).map(c => c.city);
    cities.forEach(c => {
      if(c.city === originCity) return;
      const q = proj(c.lat, c.lon, R);
      if(q[2] <= 0.14) return;
      const x = q[0], y = q[1];
      const hot = c.count >= maxCount * 0.6;
      const breathe = 1 + Math.sin(t * 0.14 + c.count) * 0.16;
      const r = (3 + Math.sqrt(c.count / maxCount) * 3.4) * breathe;

      ctx.beginPath(); ctx.arc(x, y, r * 3.2, 0, Math.PI * 2);
      ctx.fillStyle = hot ? "rgba(255,154,31,.16)" : "rgba(127,243,255,.12)";
      ctx.fill();
      ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fillStyle = hot ? "#ff9a1f" : "#eafcff";
      ctx.shadowColor = hot ? "#ff9a1f" : "#7ff3ff";
      ctx.shadowBlur = 14;
      ctx.fill();
      ctx.shadowBlur = 0;

      if(labelled.indexOf(c.city) < 0) return;
      const label = c.city + " " + c.count;
      ctx.font = "11.5px 'Orbitron', ui-monospace, monospace";
      const w = ctx.measureText(label).width + 14;
      const right = x < cx;
      const lx = right ? x + r + 8 : x - r - 8 - w;
      const ly = y - 11;
      const clash = placed.some(p => lx < p.x + p.w + 6 && lx + w + 6 > p.x && Math.abs(p.y - ly) < 26);
      if(clash) return;
      placed.push({x: lx, y: ly, w: w});

      ctx.fillStyle = hot ? "rgba(255,154,31,.16)" : "rgba(6,24,40,.72)";
      ctx.fillRect(lx - 3, ly, w, 17);
      ctx.strokeStyle = hot ? "rgba(255,154,31,.6)" : "rgba(34,211,238,.45)";
      ctx.lineWidth = 1;
      ctx.strokeRect(lx - 3, ly, w, 17);
      ctx.fillStyle = hot ? "#ffc45c" : "#d6f6ff";
      ctx.textAlign = "left";
      ctx.fillText(label, lx + 4, ly + 13);
    });

    const o = G.origin;
    if(o){
      const q = proj(o.lat, o.lon, R);
      if(q[2] > 0.16){
        const ox = q[0], oy = q[1];
        const pulse = 8 + (Math.sin(t * 0.10) + 1) * 7;
        ctx.beginPath(); ctx.arc(ox, oy, pulse, 0, Math.PI * 2);
        ctx.strokeStyle = "rgba(74,222,128,.55)"; ctx.lineWidth = 1.4; ctx.stroke();
        ctx.beginPath(); ctx.arc(ox, oy, 4, 0, Math.PI * 2);
        ctx.fillStyle = "#4ade80"; ctx.shadowColor = "#4ade80"; ctx.shadowBlur = 16; ctx.fill(); ctx.shadowBlur = 0;

        const label = "采集端 " + o.city;
        ctx.font = "11px 'Orbitron', ui-monospace, monospace";
        const w = ctx.measureText(label).width + 14;
        const lx = ox - pulse - w - 4, ly = oy + 12;
        ctx.fillStyle = "rgba(6,24,40,.86)";
        ctx.fillRect(lx, ly, w, 18);
        ctx.strokeStyle = "rgba(74,222,128,.55)"; ctx.lineWidth = 1; ctx.strokeRect(lx, ly, w, 18);
        ctx.fillStyle = "#b9f7cb"; ctx.textAlign = "left";
        ctx.fillText(label, lx + 5, ly + 13);
      }
    }

    ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.strokeStyle = "rgba(127,243,255,.55)"; ctx.lineWidth = 1.3; ctx.stroke();
    ctx.beginPath(); ctx.arc(cx, cy, R + 3, 0, Math.PI * 2);
    ctx.strokeStyle = "rgba(34,211,238,.18)"; ctx.lineWidth = 1; ctx.stroke();
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
    zoom = Math.max(0.72, Math.min(1.42, zoom - e.deltaY * 0.0012));
  }, {passive: false});

  if(raf) cancelAnimationFrame(raf);
  raf = requestAnimationFrame(frame);
}

/* ================= hero 统计 ================= */
function renderHeroStats(rows){
  const high = rows.filter(r => r.time_confidence === "high").length;
  const zh = rows.filter(r => r.lang === "zh").length;
  const srcCount = new Set(rows.map(r => r.source_id)).size;
  const countries = new Set(((GLOBE && GLOBE.cities) || []).map(c => c.country)).size;
  const lc = $("lede-countries");
  if(lc) lc.textContent = String(countries);

  const stats = [["SRC", srcCount, "源"], ["GEO", countries, "国家"], ["INTEL", rows.length, "条目"], ["ZH", zh, "中文"]];
  $("hero-stats").innerHTML = stats.map(s =>
    `<div class="stat"><span class="ico">${s[0]}</span><b>${s[1]}</b><span>${s[2]}</span></div>`).join("");

  const last = rows.length ? rows[0].published_at : null;
  $("hero-updated").textContent = last ? "最新一条：" + rel(last) + "（" + hhmm(last) + " UTC）" : "";

  const sub = $("panel-sub");
  if(sub) sub.textContent = high + " 高可信 · " + (rows.length - high) + " 低可信 · " + new Set(rows.map(r => r.lang)).size + " 种语言";

  const cap = $("globe-caption-text");
  if(cap) cap.textContent = ((GLOBE && GLOBE.cities) || []).length + " 城 · " + rows.length + " 条 · 拖拽旋转";

  const legend = $("globe-legend");
  if(legend){
    const o = (GLOBE && GLOBE.origin) || {};
    const src = String(o.source || "");
    const tag = src.indexOf("ip-detected") === 0 ? "AUTO IP" : (src === "env-city" || src === "env-latlon") ? "MANUAL" : "DEFAULT";
    legend.innerHTML = "NODE " + tag + "<br>" + ((GLOBE && GLOBE.sources) || []).length + " SOURCE NODES";
  }
}

/* ================= 分布 / 健康 ================= */
function renderDist(rows){
  const byCity = ((GLOBE && GLOBE.cities) || []).slice().sort((a, b) => b.count - a.count);
  const maxC = Math.max(1, ...byCity.map(c => c.count));
  const total = rows.length || 1;
  const bars = byCity.map((c, i) =>
    '<div class="bar' + (i === 0 ? " lead" : "") + '"><span class="v">' + c.count + '</span>' +
    '<span class="col" style="height:' + Math.max(4, Math.round(c.count / maxC * 140)) + 'px"></span>' +
    '<span class="cc">' + esc(String(c.city).slice(0, 9)) + '</span></div>').join("");

  const domainRows = [...new Set(rows.map(r => r.domain))].map(d => {
    const n = rows.filter(r => r.domain === d).length;
    return '<div class="row"><span class="lbl">' + (DOMAIN_META[d] || d) + '</span>' +
      '<span class="track"><i style="width:' + (n / total * 100).toFixed(1) + '%;background:' + DOMAIN_COLOR[d] + '"></i></span>' +
      '<span class="val">' + n + '</span></div>';
  }).join("");
  const high = rows.filter(r => r.time_confidence === "high").length;
  const quality =
    '<div class="row"><span class="lbl">高可信</span><span class="track"><i style="width:' + (high / total * 100).toFixed(1) + '%;background:#4ade80"></i></span><span class="val">' + high + '</span></div>' +
    '<div class="row"><span class="lbl">低可信</span><span class="track"><i style="width:' + ((rows.length - high) / total * 100).toFixed(1) + '%;background:#ff9a1f"></i></span><span class="val">' + (rows.length - high) + '</span></div>' +
    '<div class="row"><span class="lbl">中文</span><span class="track"><i style="width:' + (rows.filter(r => r.lang === "zh").length / total * 100).toFixed(1) + '%;background:#38bdf8"></i></span><span class="val">' + rows.filter(r => r.lang === "zh").length + '</span></div>';

  $("view-dist").innerHTML =
    '<div class="dcard"><h3>SOURCE CITIES</h3><div class="bars">' + bars + '</div></div>' +
    '<div class="dcard"><h3>CHANNEL / CONFIDENCE</h3><div class="rows">' + domainRows + quality + '</div></div>';
}

function renderHealthCards(){
  const rows = HEALTH.rows || [];
  $("view-health").innerHTML = rows.map(h => {
    const cls = h.flag === "GREEN" ? "ok" : h.flag === "YELLOW" ? "warn" : "bad";
    return '<div class="hcard"><span class="dot ' + cls + '"></span>' +
      '<span class="nm">' + esc(h.source_name) + '</span>' +
      '<span class="pc">' + Math.round(h.success_rate * 100) + '%</span>' +
      '<span class="sm">' + h.ok + '/' + (h.ok + h.zero + h.failed) + '</span></div>';
  }).join("");
}

/* ================= 全球覆盖 ================= */
const REGION_STATUS = {covered: "已覆盖", thin: "薄弱", blind: "盲区"};

function renderWorld(){
  const w = WORLD || {};
  const cov = w.coverage || {};
  const regions = (w.regions || []).slice().sort((a, b) => b.source_count - a.source_count);
  const blind = w.blind_spots || [];
  const pct = cov.pct || 0;

  const head = `
    <div class="wcard wide">
      <h4>GLOBAL COVERAGE</h4>
      <div class="wcover">
        <div class="wring" style="--pct:${pct}">
          <span>${pct}<i>%</i></span>
        </div>
        <div class="wstats">
          <div><b>${cov.regions_covered || 0}/${cov.regions_total || 0}</b><span>区域有源</span></div>
          <div><b>${cov.countries_covered || 0}</b><span>国家</span></div>
          <div><b>${cov.sources_total || 0}</b><span>信息源</span></div>
          <div><b>${cov.items_total || 0}</b><span>今日条目</span></div>
        </div>
      </div>
      <p class="wblind">盲区 ${blind.length} 个：${blind.map(b => b.region).join(" · ") || "无"}</p>
    </div>`;

  const cards = regions.map(r => {
    const st = r.status || "blind";
    const countries = (r.countries || []).map(c => `${c.name} ${c.sources}`).join(" · ") || "—";
    return `<div class="wcard ${st}">
      <div class="wtop"><span class="wdot"></span><h4>${esc(r.region)}</h4>
        <span class="wtg">${REGION_STATUS[st] || st}</span></div>
      <div class="wnum"><b>${r.source_count}</b><span>源</span><b>${r.item_count}</b><span>条</span></div>
      <p class="wct">${esc(countries)}</p>
    </div>`;
  }).join("");

  $("view-world").innerHTML = head + cards;
}

/* ================= 列表 ================= */
function renderFilters(rows){
  const present = [...new Set(rows.map(r => r.domain))];
  $("domain-chips").innerHTML = present.map(d => {
    const n = rows.filter(r => r.domain === d).length;
    return '<span class="fchip' + (state.domain === d ? " on" : "") + '" data-domain="' + d + '">' + (DOMAIN_META[d] || d) + ' ' + n + '</span>';
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
    if(q && !((r.title || "") + " " + (r.summary || "") + " " + (r.source_name || "")).toLowerCase().includes(q)) return false;
    return true;
  });
  $("count").textContent = filtered.length + " / " + rows.length + " 条";
  if(!filtered.length){ $("view-feed").innerHTML = '<div class="item"><h3>没有匹配的条目</h3></div>'; return; }
  $("view-feed").innerHTML = filtered.map((r, i) =>
    '<article class="item ' + r.domain + '">' +
      '<h3><a href="' + esc(r.url) + '" target="_blank" rel="noopener">' + esc(r.title) + '</a></h3>' +
      '<div class="meta">' +
        '<span class="tag dom-' + r.domain + '">' + (DOMAIN_META[r.domain] || r.domain) + '</span>' +
        '<span class="src">' + esc(r.source_name) + '</span>' +
        '<span>' + hhmm(r.published_at) + ' · ' + rel(r.published_at) + '</span>' +
        '<span class="tag ' + r.time_confidence + '">' + r.time_confidence + '</span>' +
        (r.lang === "zh" ? '<span class="tag zh">中文</span>' : "") +
      '</div>' +
      '<div class="sum" data-i="' + i + '">' + esc(r.summary || "（该源未提供摘要，W2 接正文抽取）") + '</div>' +
    '</article>').join("");
  document.querySelectorAll(".sum").forEach(el => el.onclick = () => el.classList.toggle("open"));
}

/* ================= 视图切换 ================= */
function setView(view, rows){
  state.view = view;
  document.querySelectorAll(".tab").forEach(t => t.classList.toggle("on", t.dataset.view === view));
  document.querySelectorAll(".nav a").forEach(a => a.classList.toggle("on", a.dataset.view === view));
  $("view-feed").classList.toggle("hidden", view !== "feed");
  $("view-dist").classList.toggle("hidden", view !== "dist");
  $("view-health").classList.toggle("hidden", view !== "health");
  $("view-world").classList.toggle("hidden", view !== "world");
  $("filters").classList.toggle("hidden", view === "health" || view === "world");
  const titles = {feed: "今日条目", dist: "数据分布", health: "源健康", world: "全球覆盖扫描"};
  $("panel-title").textContent = titles[view] || "";
  if(view === "dist") renderDist(rows);
  if(view === "health") renderHealthCards();
  if(view === "world") renderWorld();
  if(view === "feed") renderList(rows);
}

function bind(rows){
  document.querySelectorAll(".tab").forEach(t => t.onclick = () => setView(t.dataset.view, rows));
  document.querySelectorAll(".nav a").forEach(a => a.onclick = (e) => {
    e.preventDefault(); setView(a.dataset.view, rows); $("panel").scrollIntoView({behavior: "smooth"});
  });
  $("to-feed").onclick = () => { setView("feed", rows); $("panel").scrollIntoView({behavior: "smooth"}); };
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
    if(e.key === "/" && document.activeElement !== $("q")){ e.preventDefault(); $("q").focus(); $("panel").scrollIntoView({behavior: "smooth"}); }
  });
}

const rows = DATA.items || [];
initMatrix();
renderGlobe();
renderHeroStats(rows);
renderFilters(rows);
renderList(rows);
renderDist(rows);
renderHealthCards();
renderWorld();
bind(rows);

/* 支持 #world / #dist 直达视图，方便分享与截图 */
(function initialView(){
  const view = (location.hash || "").replace("#", "");
  if(["feed", "dist", "health", "world"].indexOf(view) >= 0) setView(view, rows);
})();
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


def _read_json(path: Path, fallback: str = "null") -> str:
    return path.read_text(encoding="utf-8") if path.exists() else fallback


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
    globe_json = _read_json(ROOT / "data" / "globe.json")
    land_json = _read_json(ROOT / "data" / "land.json")
    dots_json = _read_json(ROOT / "data" / "land_dots.json", "[]")
    hacker_b64 = _read_json(ROOT / "web" / "assets" / "hacker.b64.txt", "")
    world_json = "null"
    try:
        from pip_app.world_scan import load_items as _load_items, load_sources as _load_sources, scan as _scan

        world_json = json.dumps(
            _scan(_load_sources(SOURCES_FILE), _load_items(items_path)), ensure_ascii=False
        ).replace("</", "<\\/")
    except Exception:  # noqa: BLE001 - 扫描失败不影响页面生成
        pass
    high = sum(1 for i in items if i.get("time_confidence") == "high")
    countries = len({i["source_id"] for i in items})

    html = (
        TEMPLATE.replace("__DATA__", data_json)
        .replace("__HEALTH__", health_json)
        .replace("__GLOBE__", globe_json)
        .replace("__LAND__", land_json)
        .replace("__LAND_DOTS__", dots_json)
        .replace("__HACKER__", hacker_b64)
        .replace("__WORLD__", world_json)
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
