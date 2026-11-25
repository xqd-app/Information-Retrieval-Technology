"""补丁：重排首屏纸卡（标题层级 / 导航 / 摘要 / 统计 / 行动区）。"""

import re
from pathlib import Path

PATH = Path(__file__).resolve().parent / "build_web.py"
text = PATH.read_text(encoding="utf-8")

# ---------- CSS ----------
css_pattern = re.compile(r"\.paper\{.*?\.updated\{[^}]*\}", re.S)
NEW_CSS = """--paper:{display:none}
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
.updated::before{content:"";width:5px;height:5px;border-radius:50%;background:#c9891a;flex:0 0 auto}"""
if not css_pattern.search(text):
    raise SystemExit("未找到纸卡 CSS 段")
text = css_pattern.sub(NEW_CSS, text, count=1)

# ---------- HTML ----------
html_pattern = re.compile(r'  <div class="paper">.*?\n  </div>\n', re.S)
NEW_HTML = """  <div class="paper">
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
"""
if not html_pattern.search(text):
    raise SystemExit("未找到纸卡 HTML 段")
text = html_pattern.sub(NEW_HTML, text, count=1)

PATH.write_text(text, encoding="utf-8")
print("patched hero paper card")
