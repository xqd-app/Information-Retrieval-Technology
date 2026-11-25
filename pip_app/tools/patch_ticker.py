"""补丁：顶部 ticker 改为按实际域动态生成（原逻辑 rows.length-ai 把两域假设写死了）。"""

from pathlib import Path

PATH = Path(__file__).resolve().parent / "build_web.py"
text = PATH.read_text(encoding="utf-8")

old = """  const tick = [
    ["条目", rows.length, ""],
    ["高可信", high, "var(--green)"],
    ["低可信", rows.length - high, "var(--gold)"],
    ["AI", ai, "var(--ai)"],
    ["政经", rows.length - ai, "var(--geo)"],
    ["中文", zh, "var(--blue)"]
  ];"""

new = """  const domainTicks = [...new Set(rows.map(r => r.domain))].map(d =>
    [DOMAIN_META[d] || d, rows.filter(r => r.domain === d).length, DOMAIN_COLOR[d] || "var(--muted)"]);
  const tick = [
    ["条目", rows.length, ""],
    ["高可信", high, "var(--green)"],
    ["低可信", rows.length - high, "var(--gold)"],
    ...domainTicks,
    ["中文", zh, "var(--blue)"]
  ];"""

if old not in text:
    raise SystemExit("ticker 片段未找到")
text = text.replace(old, new)

# ai 变量已不再用于 ticker，但 renderBrief 里也没用了；保留避免未定义引用报错
PATH.write_text(text, encoding="utf-8")
print("patched ticker")
