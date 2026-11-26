"""接入 zaelix.tech 的 5 个分类 RSS。

不接的两个：
    全站文章 /feed/   10 条混合主题（超微距摄影等），会污染 AI 分类
    全站评论 /comments/ 0 条，且评论不是情报
站点在 Cloudflare 后面，无法从 IP 判断归属，按中文内容标 approx + Hong Kong。
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SOURCES = ROOT / "pip_app" / "sources.json"
GLOBE = ROOT / "pip_app" / "tools" / "build_globe_data.py"

NEW = [
    ("zaelix-ai-coding", "Zaelix · AI 编程", "ai", "zh",
     "https://zaelix.tech/category/ai-coding/feed/", 3),
    ("zaelix-ai-news", "Zaelix · AI 动态", "ai", "zh",
     "https://zaelix.tech/category/ai-news/feed/", 3),
    ("zaelix-codex", "Zaelix · Codex", "ai", "zh",
     "https://zaelix.tech/category/codex/feed/", 3),
    ("zaelix-claude-code", "Zaelix · Claude Code", "ai", "zh",
     "https://zaelix.tech/category/claude-code/feed/", 3),
    ("zaelix-resources", "Zaelix · 资源", "skills", "zh",
     "https://zaelix.tech/category/resources/feed/", 3),
]


def patch_sources() -> None:
    payload = json.loads(SOURCES.read_text(encoding="utf-8"))
    existing = {s["id"] for s in payload["sources"]}
    added = 0
    for sid, name, domain, lang, url, tier in NEW:
        if sid in existing:
            continue
        payload["sources"].append({
            "id": sid, "name": name, "domain": domain, "lang": lang,
            "url": url, "tier": tier,
        })
        added += 1
    SOURCES.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"sources.json: {len(payload['sources'])} 源（新增 {added}）")


def patch_globe() -> None:
    text = GLOBE.read_text(encoding="utf-8")
    if "zaelix-ai-coding" in text:
        print("build_globe_data: 已存在，跳过")
        return

    anchor = '    "timesofisrael": ("Jerusalem", "hq"),\n'
    assert anchor in text, "SOURCE_PLACE 锚点未找到"
    lines = "".join(
        f'    "{sid}": ("Hong Kong", "approx"),   # Cloudflare 后端，位置近似\n'
        for sid, *_ in NEW
    )
    text = text.replace(anchor, anchor + lines, 1)
    GLOBE.write_text(text, encoding="utf-8")
    print(f"build_globe_data: 新增 {len(NEW)} 个源点位（Hong Kong / approx）")


if __name__ == "__main__":
    patch_sources()
    patch_globe()
