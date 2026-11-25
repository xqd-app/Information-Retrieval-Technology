"""W1 采集配置（参数集中，不散落硬编码）。"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "pip_app" / "data"
ITEMS_DIR = DATA_DIR / "items"
HEALTH_FILE = DATA_DIR / "source_health.jsonl"
SOURCES_FILE = ROOT / "pip_app" / "sources.json"

# 采集端：跑 collect 的那台机器所在城市（决定地球上的汇聚点与全部 RTT 距离）
# 可用环境变量覆盖：PIP_ORIGIN_CITY=Chongqing python -m pip_app.tools.build_globe_data
ORIGIN_CITY = os.environ.get("PIP_ORIGIN_CITY", "Kunming")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
ACCEPT = "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8"

TIMEOUT_SECONDS = 15
RETRY_TIMEOUT_SECONDS = 8       # 重试用更短超时，避免一个坏源吃掉整轮预算
MAX_BYTES = 2_500_000
WORKERS = 6                     # 31 源时 8 并发会触发站点限流/超时
LIMIT_PER_SOURCE = 40
GLOBAL_BUDGET_SECONDS = 240
MANUAL_COOLDOWN_SECONDS = 600
HEALTH_WINDOW_DAYS = 7
RETRY_ATTEMPTS = 2              # 网络层故障最多再重试 2 次（共 3 次）
RETRY_BACKOFF_SECONDS = 1.5     # 指数退避：1.5s / 3s
REQUEST_JITTER_SECONDS = 0.25   # 并发前的抖动，缓解同批握手集中被重置
