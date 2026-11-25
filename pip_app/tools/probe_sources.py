"""批量探测候选 RSS 源可用性（只读，不落盘）。"""

import ssl
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

CANDIDATES = [
    # AI / 技术
    ("techcrunch-ai", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("ars-technica", "https://feeds.arstechnica.com/arstechnica/technology-lab"),
    ("venturebeat-ai", "https://venturebeat.com/category/ai/feed/"),
    ("theverge", "https://www.theverge.com/rss/index.xml"),
    ("mit-tech-review", "https://www.technologyreview.com/feed/"),
    ("google-ai-blog", "https://blog.google/technology/ai/rss/"),
    ("deepmind", "https://deepmind.google/blog/rss.xml"),
    ("huggingface-blog", "https://huggingface.co/blog/feed.xml"),
    ("arxiv-cs-ai", "http://export.arxiv.org/rss/cs.AI"),
    ("hn-frontpage", "https://news.ycombinator.com/rss"),
    ("simonwillison", "https://simonwillison.net/atom/everything/"),
    ("latent-space", "https://www.latent.space/feed"),
    ("import-ai", "https://importai.substack.com/feed"),
    ("github-blog", "https://github.blog/feed/"),
    ("jiqizhixin", "https://www.jiqizhixin.com/rss"),
    ("qbitai", "https://www.qbitai.com/feed"),
    ("36kr", "https://36kr.com/feed"),
    ("ithome", "https://www.ithome.com/rss/"),
    ("sspai", "https://sspai.com/feed"),
    ("infoq-cn", "https://www.infoq.cn/feed"),
    # 政经 / 世界
    ("cnbc-world", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100727362"),
    ("wsj-markets", "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
    ("aljazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("dw-world", "https://rss.dw.com/rdf/rss-en-world"),
    ("france24", "https://www.france24.com/en/rss"),
    ("euronews", "https://feeds.feedburner.com/euronews/en/news/"),
    ("politico", "https://rss.politico.com/politics-news.xml"),
    ("thehill", "https://thehill.com/feed/"),
    ("npr-world", "https://feeds.npr.org/1004/rss.xml"),
    ("guardian-world", "https://www.theguardian.com/world/rss"),
    ("ap-topnews", "https://rsshub.app/apnews/topics/apf-topnews"),
    ("scmp", "https://www.scmp.com/rss/91/feed"),
    ("straits-times", "https://www.straitstimes.com/news/world/rss.xml"),
    ("caixin", "https://www.caixin.com/rss/all.xml"),
    ("yicai", "https://www.yicai.com/api/rss"),
    ("zaobao", "https://www.zaobao.com.sg/rss/realtime/world"),
    ("google-news-ai", "https://news.google.com/rss/search?q=artificial+intelligence&hl=en-US&gl=US&ceid=US:en"),
    ("google-news-china", "https://news.google.com/rss/search?q=%E4%BA%BA%E5%B7%A5%E6%99%BA%E8%83%BD&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("reuters-tech", "https://www.reutersagency.com/feed/?best-topics=tech&post_type=best"),
    ("financial-times", "https://www.ft.com/rss/home"),
]


def probe(name: str, url: str) -> tuple[str, str, int, float, str]:
    started = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read(400_000)
            return name, str(resp.status), len(body), time.time() - started, ""
    except Exception as exc:  # noqa: BLE001 - 探测脚本
        return name, "ERR", 0, time.time() - started, f"{type(exc).__name__}: {str(exc)[:50]}"


def main() -> None:
    results = []
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = [pool.submit(probe, n, u) for n, u in CANDIDATES]
        for fut in as_completed(futures):
            results.append(fut.result())
    ok = [r for r in results if r[1] == "200" and r[2] > 500]
    bad = [r for r in results if r not in ok]
    print(f"可用 {len(ok)} / 共 {len(CANDIDATES)}\n")
    for name, status, size, secs, err in sorted(ok, key=lambda r: r[0]):
        print(f"  OK   {name:<18} {size:>7}B {secs:4.1f}s")
    print("\n不可用：")
    for name, status, size, secs, err in sorted(bad, key=lambda r: r[0]):
        print(f"  FAIL {name:<18} {status:<4} {err}")


if __name__ == "__main__":
    main()
