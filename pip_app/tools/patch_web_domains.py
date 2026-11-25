"""补丁：页面支持动态域（ai/geopol/skills/oss）+ 自动取最新数据文件。"""

from pathlib import Path

PATH = Path(__file__).resolve().parent / "build_web.py"
text = PATH.read_text(encoding="utf-8")

repl = [
    # 1) 数据文件自动取最新
    (
        'DATA_FILE = ROOT / "data" / "items" / "2026-11-24.jsonl"',
        'ITEMS_DIR = ROOT / "data" / "items"\n\n\ndef latest_items_path() -> Path:\n'
        '    files = sorted(ITEMS_DIR.glob("*.jsonl"))\n'
        '    return files[-1] if files else ITEMS_DIR / "2026-11-24.jsonl"\n',
    ),
    # 2) 域颜色
    (
        "  --ai:#7b56d9; --geo:#0f9f8f; --radius:8px;",
        "  --ai:#7b56d9; --geo:#0f9f8f; --skills:#2f6fed; --oss:#d69b16; --radius:8px;",
    ),
    # 3) chip 与卡片/标签的域色
    (
        ".chip.on.geo{background:#e7f6f3;border-color:var(--teal);color:#0b6f64}\n"
        ".chip.on.ai{background:#f1ecfd;border-color:var(--violet);color:#5533b0}",
        ".chip.on.geo,.chip.on.geopol{background:#e7f6f3;border-color:var(--teal);color:#0b6f64}\n"
        ".chip.on.ai{background:#f1ecfd;border-color:var(--violet);color:#5533b0}\n"
        ".chip.on.skills{background:#eaf1ff;border-color:var(--blue);color:#1b46c2}\n"
        ".chip.on.oss{background:#fdf3e0;border-color:var(--gold);color:#8a5a06}",
    ),
    (
        ".item.ai{border-left-color:var(--ai)}\n.item.geopol{border-left-color:var(--geo)}",
        ".item.ai{border-left-color:var(--ai)}\n.item.geopol{border-left-color:var(--geo)}\n"
        ".item.skills{border-left-color:var(--skills)}\n.item.oss{border-left-color:var(--oss)}",
    ),
    (
        ".tag.dom-ai{background:#f1ecfd;color:#5533b0}\n.tag.dom-geo{background:#e7f6f3;color:#0b6f64}",
        ".tag.dom-ai{background:#f1ecfd;color:#5533b0}\n.tag.dom-geopol{background:#e7f6f3;color:#0b6f64}\n"
        ".tag.dom-skills{background:#eaf1ff;color:#1b46c2}\n.tag.dom-oss{background:#fdf3e0;color:#8a5a06}",
    ),
    # 4) 域元信息 + 动态 chips
    (
        'const state = {domain:"all", conf:"all", src:"all", q:""};',
        'const DOMAIN_META = {ai:"AI", geopol:"政经", skills:"AI 技能", oss:"GitHub"};\n'
        'const DOMAIN_COLOR = {ai:"var(--ai)", geopol:"var(--geo)", skills:"var(--skills)", oss:"var(--oss)"};\n'
        'const state = {domain:"all", conf:"all", src:"all", q:""};',
    ),
    (
        '  const domains = [["all","全部", rows.length], ["ai","AI", rows.filter(r=>r.domain==="ai").length],\n'
        '                   ["geopol","政经", rows.filter(r=>r.domain==="geopol").length]];\n'
        '  $("ch-domains").innerHTML = domains.map(([v,label,n]) =>\n'
        '    `<span class="chip${state.domain===v?" on":""}${v==="ai"?" ai":v==="geopol"?" geo":""}" data-domain="${v}">${label} ${n}</span>`).join("");',
        '  const present = [...new Set(rows.map(r => r.domain))];\n'
        '  const domains = [["all", "全部", rows.length], ...present.map(d =>\n'
        '    [d, DOMAIN_META[d] || d, rows.filter(r => r.domain === d).length])];\n'
        '  $("ch-domains").innerHTML = domains.map(([v, label, n]) =>\n'
        '    `<span class="chip${state.domain === v ? " on" : ""} ${v}" data-domain="${v}">${label} ${n}</span>`).join("");',
    ),
    # 5) 卡片标签用统一映射
    (
        '        <span class="tag dom-${r.domain==="ai"?"ai":"geo"}">${r.domain==="ai"?"AI":"政经"}</span>',
        '        <span class="tag dom-${r.domain}">${DOMAIN_META[r.domain] || r.domain}</span>',
    ),
    # 6) BRIEFING 动态域分布
    (
        '  $("brief").innerHTML =\n'
        '    bar("AI", ai, "var(--ai)") +\n'
        '    bar("政经", geo, "var(--geo)") +\n'
        '    bar("高可信", high, "var(--green)") +\n'
        '    bar("低可信", rows.length-high, "var(--gold)") +\n'
        '    bar("中文", zh, "var(--blue)");',
        '  const domainBars = [...new Set(rows.map(r => r.domain))]\n'
        '    .map(d => bar(DOMAIN_META[d] || d, rows.filter(r => r.domain === d).length, DOMAIN_COLOR[d] || "var(--muted)"))\n'
        '    .join("");\n'
        '  $("brief").innerHTML = domainBars +\n'
        '    bar("高可信", high, "var(--green)") +\n'
        '    bar("低可信", rows.length - high, "var(--gold)") +\n'
        '    bar("中文", zh, "var(--blue)");',
    ),
    # 7) build() 默认取最新
    (
        "def build(items_path: Path = DATA_FILE, health_path: Path = HEALTH_FILE, out: Path = OUT_FILE) -> Path:\n"
        "    items = load_items(items_path)",
        "def build(items_path: Path | None = None, health_path: Path = HEALTH_FILE, out: Path = OUT_FILE) -> Path:\n"
        "    items_path = items_path or latest_items_path()\n"
        "    items = load_items(items_path)",
    ),
]

for old, new in repl:
    if old not in text:
        raise SystemExit(f"未找到片段: {old[:60]!r}")
    text = text.replace(old, new)

PATH.write_text(text, encoding="utf-8")
print("patched build_web.py")
