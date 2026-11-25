"""向 sources.json 追加「AI 技能 / 工具」与「GitHub 开源」两类源（幂等）。"""

import json
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "sources.json"

NEW = [
    # AI 技能 / 工具 / Agent 生态
    {"id": "openai-news", "name": "OpenAI News", "domain": "skills", "lang": "en",
     "url": "https://openai.com/news/rss.xml", "tier": 1},
    {"id": "the-decoder", "name": "The Decoder", "domain": "skills", "lang": "en",
     "url": "https://the-decoder.com/feed/", "tier": 2},
    {"id": "product-hunt", "name": "Product Hunt", "domain": "skills", "lang": "en",
     "url": "https://www.producthunt.com/feed", "tier": 3},
    {"id": "latent-space", "name": "Latent Space", "domain": "skills", "lang": "en",
     "url": "https://www.latent.space/feed", "tier": 3},
    {"id": "infoq-cn", "name": "InfoQ 中文", "domain": "skills", "lang": "zh",
     "url": "https://www.infoq.cn/feed", "tier": 3},
    # GitHub 开源趋势 / 平台更新
    {"id": "gh-trending", "name": "GitHub Trending", "domain": "oss", "lang": "en",
     "url": "https://mshibanami.github.io/GitHubTrendingRSS/daily/all.xml", "tier": 1},
    {"id": "gh-changelog", "name": "GitHub Changelog", "domain": "oss", "lang": "en",
     "url": "https://github.blog/changelog/feed/", "tier": 2},
]

payload = json.loads(PATH.read_text(encoding="utf-8"))
existing = {row["id"] for row in payload["sources"]}
added = []
for row in NEW:
    if row["id"] not in existing:
        payload["sources"].append(row)
        added.append(row["id"])

payload["note"] = (
    "31 源：ai/geopol 24 源（2026-11-24 实测）+ skills/oss 7 源（2026-11-25 实测，"
    "GitHub Trending 走社区 RSS，Anthropic/MCP/n8n 当前不可达未纳入）"
)
PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print("新增:", ", ".join(added) if added else "（无，已存在）")
print("总源数:", len(payload["sources"]))
from collections import Counter
print("域分布:", dict(Counter(row["domain"] for row in payload["sources"])))
