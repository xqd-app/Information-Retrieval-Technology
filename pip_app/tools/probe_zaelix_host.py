"""解析 zaelix.tech 的服务器 IP 与归属地（决定采集端城市怎么标）。"""

import json
import socket
import urllib.request


def main() -> None:
    try:
        host, aliases, ips = socket.gethostbyname_ex("zaelix.tech")
    except socket.gaierror as exc:
        print("DNS 解析失败:", exc)
        return
    print("DNS:", ips)

    for ip in ips[:2]:
        try:
            url = (f"http://ip-api.com/json/{ip}"
                   "?fields=status,country,regionName,city,isp,org,as,lat,lon")
            req = urllib.request.Request(url, headers={"User-Agent": "pip-probe"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                info = json.loads(resp.read().decode("utf-8", "replace"))
            print(json.dumps(info, ensure_ascii=False, indent=1))
        except Exception as exc:  # noqa: BLE001
            print(f"{ip} 查询失败: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
