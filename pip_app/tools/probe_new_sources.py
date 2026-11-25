"""探测新增候选源：AI 技能/工具类 + GitHub 趋势类。"""

import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

CANDIDATES = [
    # AI 技能 / 工具 / Agent 生态
    ("anthropic-news", "https://www.anthropic.com/rss.xml"),
    ("anthropic-eng", "https://www.anthropic.com/engineering/rss.xml"),
    ("openai-news", "https://openai.com/news/rss.xml"),
    ("langchain-blog", "https://blog.langchain.dev/rss/"),
    ("product-hunt", "https://www.producthunt.com/feed"),
    ("the-decoder", "https://the-decoder.com/feed/"),
    ("latent-space", "https://www.latent.space/feed"),
    ("infoq-cn", "https://www.infoq.cn/feed"),
    ("mcp-blog", "https://blog.modelcontextprotocol.io/feed.xml"),
    ("n8n-blog", "https://blog.n8n.io/rss/"),
    ("dify-blog", "https://dify.ai/blog/rss.xml"),
    ("vercel-ai", "https://vercel.com/atom"),
    # GitHub 趋势 / 更新
    ("gh-trending-rss", "https://mshibanami.github.io/GitHubTrendingRSS/daily/all.xml"),
    ("gh-changelog", "https://github.blog/changelog/feed/"),
    ("gh-trending-html", "https://github.com/trending?since=daily"),
    ("gh-search-ai", "https://github.com/search?q=topic%3Aai+stars%3A%3E500&type=repositories"),
    ("gh-blog", "https://github.blog/feed/"),
]


def probe(name: str, url: str) -> tuple[str, str, int, str, str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/html, */*"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read(120_000)
            ctype = (resp.headers.get("Content-Type") or "")[:32]
            head = body[:70].decode("utf-8", "replace").replace("\n", " ").replace("\r", " ")
            return name, str(resp.status), len(body), ctype, head
    except Exception as exc:  # noqa: BLE001
        return name, "ERR", 0, type(exc).__name__, str(exc)[:60]


results = []
with ThreadPoolExecutor(max_workers=8) as pool:
    for fut in as_completed([pool.submit(probe, n, u) for n, u in CANDIDATES]):
        results.append(fut.result())

for name, status, size, ctype, head in sorted(results):
    flag = "OK  " if status == "200" and size > 500 else "FAIL"
    print(f"{flag} {name:<18} {status:<4} {size:>7}B  {ctype:<30} {head[:60]}")
