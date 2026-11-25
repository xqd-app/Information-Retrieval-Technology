"""探测补盲候选源：是否可达、是否是有效 feed、能解析出多少条。"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
for candidate in (ROOT,):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from pip_app.collect import _request_once  # noqa: E402
from pip_app.feedparse import NotAFeed, parse_feed  # noqa: E402

CANDIDATES = [
    # 拉美（第一轮 Folha/Infobae 403，换源）
    ("g1-world", "G1 Globo", "https://g1.globo.com/rss/g1/", "BR"),
    ("uol-noticias", "UOL Notícias", "https://rss.uol.com.br/feed/noticias.xml", "BR"),
    ("lanacion", "La Nación", "https://www.lanacion.com.ar/arc/outboundfeeds/rss/?outputType=xml", "AR"),
    ("clarin", "Clarín", "https://www.clarin.com/rss/lo-ultimo/", "AR"),
    ("eluniversal-mx", "El Universal", "https://www.eluniversal.com.mx/rss.xml", "MX"),
    ("emol", "Emol", "https://www.emol.com/rss/", "CL"),
    # 非洲
    ("africanews", "Africanews", "https://www.africanews.com/feed/rss", "KE"),
    ("iol-news", "IOL News", "https://www.iol.co.za/cmlink/1.640", "ZA"),
    ("eastafrican", "The EastAfrican", "https://www.theeastafrican.co.ke/tea/rss", "KE"),
    ("standard-ke", "The Standard Kenya", "https://www.standardmedia.co.ke/rss/headlines.php", "KE"),
    # 大洋洲
    ("nzherald", "NZ Herald", "https://www.nzherald.co.nz/arc/outboundfeeds/rss/", "NZ"),
    ("sbs-news", "SBS News", "https://www.sbs.com.au/news/feed", "AU"),
    ("abc-au", "ABC News Australia", "https://www.abc.net.au/news/feed/45910/rss.xml", "AU"),
    # 东南亚
    ("bangkokpost", "Bangkok Post", "https://www.bangkokpost.com/rss/data/topstories.xml", "TH"),
    ("vnexpress", "VnExpress", "https://vnexpress.net/rss/tin-moi-nhat.rss", "VN"),
    ("rappler", "Rappler", "https://www.rappler.com/feed/", "PH"),
    ("jakartaglobe", "Jakarta Globe", "https://jakartaglobe.id/feed", "ID"),
    # 东欧与俄
    ("kyivpost", "Kyiv Post", "https://www.kyivpost.com/feed", "UA"),
    ("rferl", "RFE/RL", "https://www.rferl.org/api/zrqiteuuir", "CZ"),
    ("balkaninsight", "Balkan Insight", "https://balkaninsight.com/feed/", "RS"),
]

def probe(row: tuple[str, str, str, str]) -> dict:
    sid, name, url, country = row
    try:
        body = _request_once(url, timeout=12)
    except Exception as exc:  # noqa: BLE001
        return {"id": sid, "name": name, "country": country, "status": f"fetch-fail: {type(exc).__name__}"}
    try:
        items, _updated = parse_feed(body)
    except NotAFeed as exc:
        return {"id": sid, "name": name, "country": country, "status": f"not-a-feed: {exc}"}
    except Exception as exc:  # noqa: BLE001
        return {"id": sid, "name": name, "country": country, "status": f"parse-fail: {type(exc).__name__}"}
    return {
        "id": sid, "name": name, "country": country, "status": "ok",
        "items": len(items), "title": "",
        "sample": (items[0].get("title", "")[:70] if items else ""),
    }


def main() -> None:
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(probe, CANDIDATES))
    ok = [r for r in results if r["status"] == "ok"]
    for r in results:
        flag = "OK  " if r["status"] == "ok" else "FAIL"
        extra = f"{r.get('items', 0):>3} 条  {r.get('sample', '')}" if r["status"] == "ok" else r["status"]
        print(f"{flag} {r['country']:<3} {r['id']:<20} {extra}")
    print(f"\n可用 {len(ok)} / {len(results)}")
    print(json.dumps([{"id": r["id"], "country": r["country"], "items": r.get("items")} for r in ok],
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
