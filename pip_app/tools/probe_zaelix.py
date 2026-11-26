"""探测 zaelix.tech 的 RSS feed：可达性、条目数、语言、是否重复。"""

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from pip_app.collect import _request_once  # noqa: E402
from pip_app.feedparse import NotAFeed, parse_feed  # noqa: E402

FEEDS = [
    ("zaelix-all", "全站文章", "https://zaelix.tech/feed/"),
    ("zaelix-comments", "全站评论", "https://zaelix.tech/comments/feed/"),
    ("zaelix-ai-coding", "AI 编程", "https://zaelix.tech/category/ai-coding/feed/"),
    ("zaelix-ai-news", "AI 动态", "https://zaelix.tech/category/ai-news/feed/"),
    ("zaelix-codex", "Codex", "https://zaelix.tech/category/codex/feed/"),
    ("zaelix-claude-code", "Claude Code", "https://zaelix.tech/category/claude-code/feed/"),
    ("zaelix-resources", "资源", "https://zaelix.tech/category/resources/feed/"),
]


def probe(row):
    sid, label, url = row
    try:
        body = _request_once(url, timeout=15)
    except Exception as exc:  # noqa: BLE001
        return {"id": sid, "label": label, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
    try:
        items, _updated = parse_feed(body)
    except NotAFeed as exc:
        return {"id": sid, "label": label, "ok": False, "error": f"not-a-feed: {exc}"}
    except Exception as exc:  # noqa: BLE001
        return {"id": sid, "label": label, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
    first = items[0].get("title") or "" if items else ""
    return {
        "id": sid, "label": label, "ok": True, "count": len(items),
        "urls": [it.get("url") for it in items[:60]],
        "sample": first[:60],
        "lang_guess": "zh" if any("\u4e00" <= ch <= "\u9fff" for ch in first) else "en",
    }


def main() -> None:
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(probe, FEEDS))

    for r in results:
        if r["ok"]:
            print(f"OK   {r['id']:<22} {r['count']:>3} 条  [{r['lang_guess']}]  {r['sample']}")
        else:
            print(f"FAIL {r['id']:<22} {r['error'][:90]}")

    # 重叠分析：全站 feed 与各分类 feed 的 URL 交集
    all_row = next((r for r in results if r["id"] == "zaelix-all" and r["ok"]), None)
    if all_row:
        all_urls = set(all_row["urls"])
        print("\n与「全站文章」的重叠：")
        for r in results:
            if r["ok"] and r["id"] != "zaelix-all":
                overlap = len(all_urls & set(r["urls"]))
                print(f"  {r['label']:<12} {overlap}/{len(r['urls'])} 条已在全站里")


if __name__ == "__main__":
    main()
