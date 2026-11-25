"""补丁：把全球覆盖扫描接进页面（新增「世界」视图 + /api/world 同源数据）。"""

from pathlib import Path

PATH = Path(__file__).resolve().parent / "build_web.py"
text = PATH.read_text(encoding="utf-8")

# ---------- 1) build() 注入 WORLD ----------
old = '    hacker_b64 = _read_json(ROOT / "web" / "assets" / "hacker.b64.txt", "")'
new = old + """
    world_json = "null"
    try:
        from pip_app.world_scan import load_items as _load_items, load_sources as _load_sources, scan as _scan

        world_json = json.dumps(
            _scan(_load_sources(SOURCES_FILE), _load_items(items_path)), ensure_ascii=False
        ).replace("</", "<\\\\/")
    except Exception:  # noqa: BLE001 - 扫描失败不影响页面生成
        pass"""
assert old in text
text = text.replace(old, new, 1)

old_replace = '        .replace("__HACKER__", hacker_b64)'
new_replace = old_replace + '\n        .replace("__WORLD__", world_json)'
assert old_replace in text
text = text.replace(old_replace, new_replace, 1)

# 常量
old_const = "const LAND_DOTS = __LAND_DOTS__;"
new_const = old_const + "\nconst WORLD = __WORLD__;"
assert old_const in text
text = text.replace(old_const, new_const, 1)

# ---------- 2) 导航 + tabs + 视图容器 ----------
old_nav = """        <a href="#panel" data-view="health">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="8" r="6"/><path d="M2 8h12M8 2c2 2 2 10 0 12M8 2c-2 2-2 10 0 12"/></svg>源健康
        </a>"""
new_nav = old_nav + """
        <a href="#panel" data-view="world">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="8" r="6"/><path d="M2 8h12"/><path d="M8 2c2.5 2 2.5 10 0 12"/></svg>全球扫描
        </a>"""
assert old_nav in text
text = text.replace(old_nav, new_nav, 1)

old_tabs = """    <button class="tab" data-view="health">健康</button>"""
new_tabs = old_tabs + """
    <button class="tab" data-view="world">世界</button>"""
assert old_tabs in text
text = text.replace(old_tabs, new_tabs, 1)

old_views = '  <div id="view-health" class="hgrid hidden"></div>'
new_views = old_views + '\n  <div id="view-world" class="wgrid hidden"></div>'
assert old_views in text
text = text.replace(old_views, new_views, 1)

# ---------- 3) setView 支持 world ----------
old_set = """  $("view-health").classList.toggle("hidden", view !== "health");
  $("filters").classList.toggle("hidden", view === "health");
  const titles = {feed: "今日条目", dist: "数据分布", health: "源健康"};"""
new_set = """  $("view-health").classList.toggle("hidden", view !== "health");
  $("view-world").classList.toggle("hidden", view !== "world");
  $("filters").classList.toggle("hidden", view === "health" || view === "world");
  const titles = {feed: "今日条目", dist: "数据分布", health: "源健康", world: "全球覆盖扫描"};"""
assert old_set in text
text = text.replace(old_set, new_set, 1)

old_calls = """  if(view === "dist") renderDist(rows);
  if(view === "health") renderHealthCards();"""
new_calls = """  if(view === "dist") renderDist(rows);
  if(view === "health") renderHealthCards();
  if(view === "world") renderWorld();"""
assert old_calls in text
text = text.replace(old_calls, new_calls, 1)

# ---------- 4) renderWorld 实现 ----------
anchor = "/* ================= 列表 ================= */"
assert anchor in text
WORLD_JS = r"""/* ================= 全球覆盖 ================= */
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

"""
text = text.replace(anchor, WORLD_JS + anchor, 1)

# 启动时先渲染一次（与 dist/health 一致）
old_init = "renderDist(rows);\nrenderHealthCards();"
new_init = "renderDist(rows);\nrenderHealthCards();\nrenderWorld();"
assert old_init in text
text = text.replace(old_init, new_init, 1)

# ---------- 5) CSS ----------
css_anchor = ".hgrid{display:grid;"
idx = text.index(css_anchor)
WORLD_CSS = """.wgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px}
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
"""
text = text[:idx] + WORLD_CSS + text[idx:]

PATH.write_text(text, encoding="utf-8")
print("patched world view")
