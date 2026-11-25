"""补丁 A：赛博朋克情报中心视觉层（CSS + hero 结构）。

保留：布局、类名、数据绑定、面板与列表结构。
只替换 <style> 与 hero 的展示型 HTML。
"""

import re
from pathlib import Path

PATH = Path(__file__).resolve().parent / "build_web.py"
text = PATH.read_text(encoding="utf-8")

NEW_CSS = r"""<style>
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
.hero{position:relative;min-height:min(94vh,880px);display:grid;
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
.tabs{position:absolute;left:30px;bottom:28px;display:inline-flex;gap:2px;padding:5px;
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
  .tabs{left:18px;bottom:20px}
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
</style>"""

css_pattern = re.compile(r"<style>.*?</style>", re.S)
if not css_pattern.search(text):
    raise SystemExit("未找到 <style> 块")
text = css_pattern.sub(lambda _: NEW_CSS, text, count=1)

NEW_HERO = r"""<section class="hero">
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
    <div class="globe-hint">轨迹：来源城市 → 采集端<br>实时光纤最低 RTT · RSS</div>
  </div>

  <div class="tabs" id="tabs">
    <button class="tab on" data-view="feed">条目</button>
    <button class="tab" data-view="dist">分布</button>
    <button class="tab" data-view="health">健康</button>
  </div>
</section>"""

hero_pattern = re.compile(r"<section class=\"hero\">.*?</section>", re.S)
if not hero_pattern.search(text):
    raise SystemExit("未找到 hero 段")
text = hero_pattern.sub(lambda _: NEW_HERO, text, count=1)

# 字体：换成长体科技字体
old_font = '<link href="https://fonts.googleapis.com/css2?family=Young+Serif&family=Hanken+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">'
new_font = '<link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet">'
text = text.replace(old_font, new_font)

PATH.write_text(text, encoding="utf-8")
print("patched cyber CSS + hero")
