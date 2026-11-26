# PIP 部署指南

三种部署方式，按运维条件选一种。

| 方式 | 适用 | 启动成本 |
|:--|:--|:--|
| 直接跑（标准库） | 有 Python 3.10+ 的机器 | 1 条命令 |
| Docker Compose | 有 Docker 的服务器 | 2 条命令 |
| systemd | 长期驻留的 Linux 主机 | 5 分钟配一次 |

---

## 0. 环境要求

- Python **3.10+**（用了 `X | None` 类型语法）
- 网络：能访问 RSS 源（境外源可能需要代理）
- 磁盘：约 200 MB（代码 + 数据 + 页面）

服务**零第三方依赖**，只用标准库：`http.server` / `urllib` / `xml.etree` / `sqlite3` / `gzip`。

---

## 1. 直接运行

```bash
git clone https://github.com/xqd-app/Information-Retrieval-Technology.git
cd Information-Retrieval-Technology

# 首次：采一次数据并生成页面
python -m pip_app.cli collect
python -m pip_app.cli health
python -m pip_app.tools.build_globe_data
python -m pip_app.tools.build_web

# 起服务（生产模式：0.0.0.0:8080）
PIP_HOST=0.0.0.0 PIP_PORT=8080 python -m pip_app.server
```

验证：

```bash
curl -s localhost:8080/healthz
# {"status":"ok","items":524,"date":"2026-11-25","sources":23,"uptime_s":5}
```

> `pip_app.serve` 是本地调试用的最小服务（只监听 127.0.0.1，无指标）。
> `pip_app.server` 是生产版，**部署请用它**。

---

## 2. Docker Compose

```bash
docker compose up -d --build
docker compose logs -f
```

- 访问 `http://<服务器IP>:8080/`
- 数据挂在 `./pip_app/data`，容器重建不丢
- 默认开启自动采集（每 6 小时）

首次启动若 `data/items/` 为空，`/healthz` 会返回 **503 degraded**，这是预期行为——先采一次：

```bash
docker compose exec pip python -m pip_app.cli collect
docker compose exec pip python -m pip_app.tools.build_globe_data
docker compose exec pip python -m pip_app.tools.build_web
```

---

## 3. systemd（推荐长期使用）

```bash
sudo useradd -r -s /bin/false pip
sudo mkdir -p /opt/pip && sudo chown pip:pip /opt/pip
sudo -u pip git clone https://github.com/xqd-app/Information-Retrieval-Technology.git /opt/pip
cd /opt/pip && python3 -m venv .venv

sudo cp deploy/pip.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pip
sudo systemctl status pip
```

改端口或采集端：编辑 `/etc/systemd/system/pip.service` 的 `Environment=`，然后 `sudo systemctl daemon-reload && sudo systemctl restart pip`。

---

## 4. 环境变量

| 变量 | 默认 | 说明 |
|:--|:--|:--|
| `PIP_HOST` | `127.0.0.1` | 监听地址，对外服务用 `0.0.0.0` |
| `PIP_PORT` | `8765` | 端口 |
| `PIP_LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `PIP_DATA_DIR` | `pip_app/data` | 数据目录（items / health / 地理） |
| `PIP_WEB_DIR` | `pip_app/web` | 页面目录 |
| `PIP_AUTO_COLLECT` | `0` | `1` 开启后台定时采集 |
| `PIP_COLLECT_INTERVAL` | `21600` | 采集间隔（秒），默认 6 小时 |
| `PIP_ORIGIN_CITY` | 自动检测 | 采集端城市（如 `Kunming`） |
| `PIP_ORIGIN_LATLON` | — | 直接给坐标 `"25.0389,102.7183"`，优先于城市名 |

---

## 5. 接口

| 路径 | 用途 | 缓存 |
|:--|:--|:--|
| `/` | 情报仪表盘（单文件 HTML） | `no-cache` |
| `/healthz` | 存活探针，数据为空返回 503 | `no-store` |
| `/metrics` | Prometheus 文本指标 | `no-store` |
| `/api/items?domain=&conf=&q=&limit=` | 条目查询 | `no-store` |
| `/api/meta` | 总量 / 域 / 可信度 / 语言 | `no-store` |
| `/api/health` | 源健康（7 日成功率） | `no-store` |
| `/api/world` | **全球覆盖扫描**（区域 / 盲区 / 覆盖率） | `no-store` |
| `/screens/*.png` | 迭代截图 | `max-age=86400` |

全站支持 gzip（响应 > 1 KB 且 `Accept-Encoding: gzip`）。

### 指标示例

```
pip_requests_total 128
pip_items 524
pip_regions_covered 4
pip_request_seconds_count 128
pip_request_seconds_avg 0.0031
```

---

## 6. 反向代理（Nginx）

```nginx
server {
    listen 80;
    server_name pip.example.com;

    location / {
        proxy_pass         http://127.0.0.1:8080;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 30s;
    }

    # 指标只给内网
    location = /metrics {
        allow 10.0.0.0/8;
        deny  all;
        proxy_pass http://127.0.0.1:8080;
    }
}
```

HTTPS 用 `certbot --nginx` 一条命令即可。

---

## 7. 运维

**日志**：stdout 输出，每行 JSON（含 `path` / `status` / `ms`）。

```bash
journalctl -u pip -f | jq -c 'select(.status>=500)'
```

**备份**：只需备份数据目录（页面可重建）。

```bash
tar czf pip-backup-$(date +%F).tar.gz pip_app/data/items pip_app/data/source_health.jsonl pip_app/data/globe.json
```

**手动刷新**：

```bash
python -m pip_app.cli collect && python -m pip_app.cli health
python -m pip_app.tools.build_globe_data && python -m pip_app.tools.build_web
```

**常见问题**

| 现象 | 原因 | 处理 |
|:--|:--|:--|
| `/healthz` 503 | `data/items/` 为空 | 跑一次 `collect` |
| 页面 503 | 未生成 `web/index.html` | 跑 `build_web` |
| 大量源 `unreachable` | 服务器在墙内、源在墙外 | 配代理，或在 `sources.json` 换可达源 |
| 采集端显示 Tokyo | 出口 IP 走代理 | `PIP_ORIGIN_CITY=Kunming` |
| 内存持续上涨 | 请求量极大时的 obs 缓冲 | 已限 5000 条样本，正常不会 |

---

## 8. 安全说明

- 静态文件只从 `web/screens/` 出，做了 `..` 与 realpath 双重校验
- 响应带 `X-Content-Type-Options: nosniff`
- 无写接口、无登录、无数据库连接——只读服务
- systemd unit 启用 `ProtectSystem=strict` / `NoNewPrivileges` / `PrivateTmp`

---

## 9. 数据库

服务使用 SQLite（`pip_app/data/pip.db`），无需额外装数据库服务。

```bash
# 首次
python -m pip_app.cli db init
python -m pip_app.cli db sync --days 7

# 采集后会自动 sync，无需手动
python -m pip_app.cli collect
```

| 环境变量 | 默认 | 说明 |
|:--|:--|:--|
| `PIP_DB` | `pip_app/data/pip.db` | 数据库路径 |

**备份**：WAL 模式下要一起备三个文件。

```bash
sqlite3 pip_app/data/pip.db ".backup '/backup/pip-$(date +%F).db'"
```

**Docker**：`pip.db` 落在挂载目录 `./pip_app/data`，容器重建不丢。

**库不存在时**：`/api/v1/*` 自动回落 JSONL，页面与旧接口不受影响——所以可以先跑服务再补库。

---

## 10. 登录鉴权

服务默认**不是**开放的：未登录访问 `/` 会 302 到 `/login`，`/api/*` 返回 401。

| 路径 | 鉴权 |
|:--|:--|
| `/`、`/screens/*`、`/api/v1/*`、`/api/world` | 需要登录 |
| `/login`、`/api/login` | 公开 |
| `/healthz`、`/metrics` | 公开（给监控用） |

### 设置密码

```bash
# 方式一：环境变量（推荐）
PIP_USER=admin PIP_PASSWORD=你的密码 python -m pip_app.server

# 方式二：不设密码，服务自动生成并打印在日志里
#   [auth] 已生成初始密码：xxxxxxxx（可改环境变量 PIP_PASSWORD 覆盖）
#   同时写入 data/.admin_password（权限 600）
```

| 变量 | 默认 | 说明 |
|:--|:--|:--|
| `PIP_USER` | `admin` | 用户名（比较时忽略大小写） |
| `PIP_PASSWORD` | 自动生成 | 密码 |
| `PIP_SESSION_TTL` | `86400` | 会话有效期（秒） |

### 安全实现

- 密码用 **PBKDF2-HMAC-SHA256（12 万轮 + 盐）** 派生后比较，不存明文
- 比较用 `hmac.compare_digest`，防时序侧信道
- 会话 token 为 `secrets.token_urlsafe(32)`，存在内存，服务重启即失效
- Cookie 带 `HttpOnly` + `SameSite=Lax`
- 同一 IP 连续失败 **5 次锁 5 分钟**（返回 429）
- 退出：访问 `/logout`

### 登录后如何调用 API

```bash
TOKEN=$(curl -s -c - -X POST localhost:8080/api/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"你的密码"}' | grep pip_session | awk '{print $7}')

curl -H "Cookie: pip_session=$TOKEN" "localhost:8080/api/v1/items?q=AI&size=3"
```
