"""接入补盲源：sources.json + build_globe_data（城市/国家）+ world_scan（区域表）。"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SOURCES = ROOT / "pip_app" / "sources.json"
GLOBE = ROOT / "pip_app" / "tools" / "build_globe_data.py"
WORLD = ROOT / "pip_app" / "world_scan.py"

# (id, name, domain, lang, url, tier, city, precision)
NEW = [
    # 南亚
    ("hindu-world", "The Hindu · World", "geopol", "en", "https://www.thehindu.com/news/international/feeder/default.rss", 2, "Chennai", "hq"),
    ("toi-world", "Times of India · World", "geopol", "en", "https://timesofindia.indiatimes.com/rssfeeds/296589292.cms", 2, "Mumbai", "hq"),
    ("dawn-world", "Dawn · World", "geopol", "en", "https://www.dawn.com/feeds/home", 2, "Karachi", "hq"),
    # 拉美
    ("g1-world", "G1 Globo", "geopol", "pt", "https://g1.globo.com/rss/g1/", 2, "São Paulo", "hq"),
    ("lanacion", "La Nación", "geopol", "es", "https://www.lanacion.com.ar/arc/outboundfeeds/rss/?outputType=xml", 2, "Buenos Aires", "hq"),
    ("clarin", "Clarín", "geopol", "es", "https://www.clarin.com/rss/lo-ultimo/", 3, "Buenos Aires", "hq"),
    # 非洲
    ("premium-times", "Premium Times", "geopol", "en", "https://www.premiumtimesng.com/feed", 2, "Abuja", "hq"),
    ("africanews", "Africanews", "geopol", "en", "https://www.africanews.com/feed/rss", 2, "Brazzaville", "city"),
    ("standard-ke", "The Standard Kenya", "geopol", "en", "https://www.standardmedia.co.ke/rss/headlines.php", 3, "Nairobi", "hq"),
    # 大洋洲
    ("guardian-au", "The Guardian Australia", "geopol", "en", "https://www.theguardian.com/au/rss", 2, "Sydney", "hq"),
    ("rnz-world", "RNZ · World", "geopol", "en", "https://www.rnz.co.nz/rss/world.xml", 3, "Wellington", "hq"),
    ("sbs-news", "SBS News", "geopol", "en", "https://www.sbs.com.au/news/feed", 3, "Sydney", "hq"),
    # 东南亚
    ("straitstimes-world", "The Straits Times · World", "geopol", "en", "https://www.straitstimes.com/news/world/rss.xml", 2, "Singapore", "hq"),
    ("cna-asia", "CNA · Asia", "geopol", "en", "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml", 2, "Singapore", "hq"),
    ("bangkokpost", "Bangkok Post", "geopol", "en", "https://www.bangkokpost.com/rss/data/topstories.xml", 3, "Bangkok", "hq"),
    ("vnexpress", "VnExpress", "geopol", "vi", "https://vnexpress.net/rss/tin-moi-nhat.rss", 3, "Hanoi", "hq"),
    ("rappler", "Rappler", "geopol", "en", "https://www.rappler.com/feed/", 3, "Manila", "hq"),
    # 东欧与俄
    ("notesfrompoland", "Notes from Poland", "geopol", "en", "https://notesfrompoland.com/feed/", 3, "Warsaw", "hq"),
    ("kyivpost", "Kyiv Post", "geopol", "en", "https://www.kyivpost.com/feed", 2, "Kyiv", "hq"),
    ("balkaninsight", "Balkan Insight", "geopol", "en", "https://balkaninsight.com/feed/", 3, "Belgrade", "hq"),
    # 西欧（美洲版，编辑部在马德里）
    ("elpais-america", "El País América", "geopol", "es", "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/america/portada", 2, "Madrid", "hq"),
]

CITY_COORDS = {
    "Chennai": (13.0827, 80.2707),
    "Karachi": (24.8607, 67.0011),
    "São Paulo": (-23.5505, -46.6333),
    "Buenos Aires": (-34.6037, -58.3816),
    "Abuja": (9.0765, 7.3986),
    "Brazzaville": (-4.2634, 15.2429),
    "Nairobi": (-1.2921, 36.8219),
    "Wellington": (-41.2865, 174.7762),
    "Bangkok": (13.7563, 100.5018),
    "Hanoi": (21.0278, 105.8342),
    "Manila": (14.5995, 120.9842),
    "Warsaw": (52.2297, 21.0122),
    "Kyiv": (50.4501, 30.5234),
    "Belgrade": (44.7866, 20.4489),
    "Madrid": (40.4168, -3.7038),
}


def patch_sources() -> None:
    payload = json.loads(SOURCES.read_text(encoding="utf-8"))
    existing = {s["id"] for s in payload["sources"]}
    for sid, name, domain, lang, url, tier, _city, _prec in NEW:
        if sid in existing:
            continue
        payload["sources"].append({
            "id": sid, "name": name, "domain": domain, "lang": lang,
            "url": url, "tier": tier,
        })
    SOURCES.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"sources.json: {len(payload['sources'])} 源（+{len(payload['sources']) - len(existing)}）")


def patch_globe() -> None:
    text = GLOBE.read_text(encoding="utf-8")

    # 1) CITY_COORDS
    lines = "".join(f'    "{c}": ({lat}, {lon}),\n' for c, (lat, lon) in CITY_COORDS.items())
    anchor = '    "Dubai": (25.2048, 55.2708),\n'
    assert anchor in text, "CITY_COORDS 锚点未找到"
    text = text.replace(anchor, anchor + lines, 1)

    # 2) SOURCE_PLACE
    place = "".join(f'    "{sid}": ("{city}", "{prec}"),\n' for sid, _n, _d, _l, _u, _t, city, prec in NEW)
    anchor2 = '    "infoq-cn": ("Beijing", "city"),\n'
    assert anchor2 in text, "SOURCE_PLACE 锚点未找到"
    text = text.replace(anchor2, anchor2 + place, 1)

    # 3) COUNTRY_OF_CITY
    country = {
        "Chennai": "IN", "Karachi": "PK", "São Paulo": "BR", "Buenos Aires": "AR",
        "Abuja": "NG", "Brazzaville": "CG", "Nairobi": "KE", "Wellington": "NZ",
        "Bangkok": "TH", "Hanoi": "VN", "Manila": "PH", "Warsaw": "PL",
        "Kyiv": "UA", "Belgrade": "RS", "Madrid": "ES",
    }
    pairs = "".join(f'"{c}": "{k}", ' for c, k in country.items())
    anchor3 = '    "Kunming": "CN", "Tokyo": "JP", "Singapore": "SG", "Frankfurt": "DE",\n'
    assert anchor3 in text, "COUNTRY_OF_CITY 锚点未找到"
    text = text.replace(anchor3, anchor3 + f'    {pairs}\n', 1)

    GLOBE.write_text(text, encoding="utf-8")
    print(f"build_globe_data: 城市 +{len(CITY_COORDS)} 源 +{len(NEW)}")


def patch_world() -> None:
    text = WORLD.read_text(encoding="utf-8")

    text = text.replace(
        '"非洲": ["ZA", "NG", "KE", "EG", "MA"],',
        '"非洲": ["ZA", "NG", "KE", "EG", "MA", "CG"],',
    )
    text = text.replace(
        '"东欧与俄": ["RU", "PL", "CZ", "UA", "HU", "RO"],',
        '"东欧与俄": ["RU", "PL", "CZ", "UA", "HU", "RO", "RS"],',
    )
    text = text.replace(
        '"RU": "俄罗斯", "PL": "波兰", "CZ": "捷克", "UA": "乌克兰", "HU": "匈牙利", "RO": "罗马尼亚",',
        '"RU": "俄罗斯", "PL": "波兰", "CZ": "捷克", "UA": "乌克兰", "HU": "匈牙利", "RO": "罗马尼亚",\n'
        '    "RS": "塞尔维亚", "CG": "刚果（布）", "ES": "西班牙", "PT": "葡萄牙",',
    )
    WORLD.write_text(text, encoding="utf-8")
    print("world_scan: 区域表已扩展（+CG +RS）")


if __name__ == "__main__":
    patch_sources()
    patch_globe()
    patch_world()
