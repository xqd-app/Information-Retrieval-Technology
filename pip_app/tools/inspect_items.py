"""采集数据质量体检（只读）。"""

import collections
import json
import sys
from pathlib import Path

path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("pip_app/data/items/2026-11-24.jsonl")
rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

print("总数", len(rows))
print("时间可信度", dict(collections.Counter(r["time_confidence"] for r in rows)))
print("时间来源", dict(collections.Counter(r["time_source"] for r in rows)))
print("语言", dict(collections.Counter(r["lang"] for r in rows)))
print("域", dict(collections.Counter(r["domain"] for r in rows)))
print("源数", len({r["source_id"] for r in rows}))

pub = [r["published_at"] for r in rows if r["published_at"]]
print("有发布时间", len(pub), "最早", min(pub)[:16], "最新", max(pub)[:16])
print()

for row in rows[:8]:
    print(f"[{row['time_confidence']}/{row['time_source']}] {row['source_id']}: {row['title'][:78]}")
    print("    ", (row["summary"] or "")[:96])

print()
bad = [r["title"] for r in rows if "&" in r["title"] or "<" in r["title"]]
print("标题含实体/标签:", len(bad), bad[:3])
hashes = collections.Counter(r["content_hash"] for r in rows)
print("内容哈希重复组:", sum(1 for v in hashes.values() if v > 1))
empty_summary = sum(1 for r in rows if not r["summary"])
print("空摘要:", empty_summary)
