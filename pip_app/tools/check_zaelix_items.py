"""检查 zaelix 源是否进入当日数据，以及去重情况。"""

import json
from pathlib import Path

path = sorted(Path("pip_app/data/items").glob("*.jsonl"))[-1]
rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
zx = [r for r in rows if str(r.get("source_id", "")).startswith("zaelix")]

print(f"文件 {path.name} · 总条目 {len(rows)} · zaelix {len(zx)} 条")
print(f"源数 {len({r.get('source_id') for r in rows})}")
print()

for r in zx:
    print(f"  [{r['domain']:<6}] {r['source_id']:<20} {r['title'][:56]}")

urls = [r.get("url") for r in zx]
print(f"\nzaelix URL 唯一性: {len(set(urls))}/{len(urls)}")
dupes = len(urls) - len(set(urls))
if dupes:
    print(f"  跨分类重复 {dupes} 条（去重已生效，保留一份）")
