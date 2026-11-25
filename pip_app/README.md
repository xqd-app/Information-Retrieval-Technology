# pip_app — W1 真实采集链路

按 PIP v1.2 的 M1 交付物落地：24 源真实抓取、时间可信度判定、跨源去重、源健康趋势。
依赖 `../pip_skeleton` 里的可判定内核（去重 / 时间可信度），不重复实现。

## 用法

```bash
cd "E:\Information Retrieval Technology"

# 起本地服务（页面 + JSON API），默认 8765
python -m pip_app.serve
python -m pip_app.serve --port 8765 --refresh   # 启动前先抓一次

# 抓全部 24 源（约 25 秒）
python -m pip_app.cli collect

# 只抓某个域
python -m pip_app.cli collect --domain ai
python -m pip_app.cli collect --domain geopol

# 7 天源健康报告（红色 = 成功率 <50% 或连续失败 ≥3）
python -m pip_app.cli health

# 看当日最近 N 条
python -m pip_app.cli tail -n 20

# 重建静态仪表盘（数据内联，可 file:// 直接打开）
python pip_app/tools/build_web.py

# 数据体检
python pip_app/tools/inspect_items.py
```

## 视觉来源

### v1.0：全息情报中心（当前）

按参考图整层重做，**数据链路与交互一条没动**，只换表现层。

| 层 | 实现 |
|:--|:--|
| 背景 | 三层叠加：Canvas 矩阵雨（数字流，11fps 节流）+ 透视地面网格 + 暗角，再压一道扫描线 |
| 面板 | 双层切角（外框青色描边 + 内层深色，`clip-path` 八角）+ 135° 斜纹 + 顶部横向扫描光 + 右上斜纹装饰条 |
| 剪影 | 兜帽人贴图（`date/images.jpg` → 去背景 → `web/assets/hacker.png` → base64 内联）；放在面板**外层**，否则会被 `clip-path` 裁掉 |

去背景用 `pip_app/tools/prepare_hacker.py`：从四边 flood fill，只清「与边缘连通的浅色像素」，所以被兜帽围住的浅灰笔记本不会被误删。换图时重跑它再 `build_web` 即可。
| 标题 | 40px 800 字重 + 青色斜块 + 双重发光；副标题换 Orbitron 排 `2026-11-25 · DAILY INTELLIGENCE REPORT` |
| 统计卡 | 八角切角 + 顶部 mono 小标签（SRC/GEO/INTEL/ZH）+ 32px Orbitron 数字 |
| 按钮 | 切角 + 青色描边 + 内发光 + 循环扫光 + 刷新图标 |
| 地球 | **点阵大陆**（6,744 点，`fillRect` 分三档 z 深度着色）+ 3 条倾斜轨道环 + 扫描弧 + 球体昼夜渐变 + 强边缘辉光 |
| 平台 | 4 层椭圆环 + 径向光晕，托住球体 |
| 节点 | 城市点带呼吸光晕，旧金山用琥珀色突出；标签只保留 top1，避免密集区叠字 |
| 底部 | 六边形胶囊状态条（`12 城 · 524 条 · 拖拽旋转`） |
| 顶栏 | 右上角 `SYSTEM ONLINE` 胶囊（绿点呼吸） |

**点阵大陆怎么来的**：`pip_app/tools/build_dots.py` 在 1.7° 网格上对 116 块陆地多边形做点在多边形内判断，采样出 6,744 点（84.8 KB）写进 `data/land_dots.json`。浏览器端只做投影 + `fillRect`，不需要每帧算几何。

```bash
python -m pip_app.tools.build_dots     # 点阵（改 STEP_DEG 可调密度）
python -m pip_app.tools.build_web
```

### v0.15：采集端自动定位

「采集端」现在自动检测，按优先级解析并**把来源印在页面上**：

| 优先级 | 方式 | 页面角标 |
|:--:|:--|:--|
| 1 | `PIP_ORIGIN_LATLON="25.04,102.72"` | 采集端：手动指定 |
| 2 | `PIP_ORIGIN_CITY="Kunming"`（查 `CITY_COORDS`） | 采集端：手动指定 |
| 3 | 自动检测（`ip-api.com` → `ipwho.is` → `ipinfo.io`） | 采集端：自动检测出口 IP（<ip>） |
| 4 | 默认 Kunming | 采集端：默认回落 |

**一个必须知道的事实**：自动检测拿到的是**公网出口 IP 的位置**，走代理/VPN 时会指向代理节点。本机实测：

```json
{"city": "Tokyo", "lat": 35.6289, "lon": 139.7915,
 "ip": "94.177.131.216", "source": "ip-api.com"}
```

即出口在日本（G-Core Labs），不是云南。要还原真实位置就用方式 1 或 2 手动指定。

实现细节：结果缓存到 `data/geo_self.json`（TTL 24h，避免每次构建都打接口）；接口全挂时回落，不会让构建失败。测试 12 例覆盖三种响应格式、降级链、缓存命中与过期、以及「必须回传 ip 与 source」这条诚实性要求。

### v0.14：采集端可配置

地球上的「采集端」＝**跑 collect 的那台机器**，不再是我硬编码的北京。默认云南昆明，可用环境变量覆盖：

```bash
python -m pip_app.tools.build_globe_data                          # 昆明（默认）
PIP_ORIGIN_CITY=Beijing python -m pip_app.tools.build_globe_data  # 北京
PIP_ORIGIN_CITY=Shanghai python -m pip_app.tools.build_globe_data # 上海
```

支持的城市写在 `build_globe_data.py` 的 `CITY_COORDS` 里（含 Kunming 25.0389/102.7183）。**所有距离与光纤 RTT 都以采集端为起点重算**——换城市后：

| 线路 | 北京出发 | **昆明出发** |
|:--|:--|:--|
| → 旧金山 | 9,503 km / 95.0 ms | **11,590 km / 115.9 ms** |
| → 北京 | — | 2,088 km / 20.9 ms |
| → 青岛 | 551 km / 5.5 ms | **2,083 km / 20.8 ms** |
| → 伦敦 | 8,141 km / 81.4 ms | **8,686 km / 86.9 ms** |

测试：4 例专门守这件事（默认值、坐标在昆明附近、`origin` 与配置一致、昆明离北京比离旧金山近）。

### v0.13：坐标真实化

地球上的点位从「按国家估算」改成「按编辑部实际所在城市」，每条目一个来源节点。

**精度三档**（写进 `globe.json` 的 `precision` 字段，页面上实心=核实、半透明=近似）：

| 精度 | 含义 | 例子 |
|:--|:--|:--|
| `hq` | 官网 contact / imprint 页可核实 | The Decoder → **Hannover**（Karl-Wiechert-Allee 10, 30625）；CNBC → Englewood Cliffs；Politico → Arlington；MIT TR → Cambridge |
| `city` | 只知道城市，用城市中心 | IT之家 → **青岛**；量子位 / InfoQ 中文 → 北京 |
| `approx` | 只确定区域，取代表城市 | Latent Space / Simon Willison → 旧金山 |

**修正掉的错标**（之前按印象写成大都市）：

| 来源 | 之前 | 现在 |
|:--|:--|:--|
| The Decoder | Berlin | **Hannover**（官网地址） |
| Ars Technica / The Verge / Hugging Face / WSJ | San Francisco | **New York** |
| Google AI Blog / Google News | San Francisco | **Mountain View**（Googleplex） |
| CNBC | New York | **Englewood Cliffs, NJ** |
| Politico | Washington | **Arlington, VA** |
| IT之家 | Beijing | **Qingdao** |

**结构**：`globe.json` 现在同时给两级——`cities`（12 个城市聚合，用于标签与航迹）与 `sources`（23 个来源点位，同城做约 6–10 km 环形偏移避免重叠）。距离与光纤 RTT 按城市重算，例如青岛→北京 551 km / RTT ≥ 5.5 ms。

页面上：实心点 = `hq`，半透明 = `city` / `approx`；状态行显示 `12 CITIES · 23 NODES · 524 INTEL`。

### v0.11：真实海岸线（已切到 50m）

地球的陆地轮廓不再是手绘的 10 块示意多边形，而是 **Natural Earth**（公共领域）抽稀而来。默认使用 **50m** 精度：

| 项 | 110m | **50m（当前）** |
|:--|:--|:--|
| 数据源 | `ne_110m_land.geojson` | `ne_50m_land.geojson`（原始 1.56 MB，已缓存） |
| 抽稀容差 | 0.35° | **0.22°**（≈24 km） |
| 过滤 | — | 面积 < 0.035 度²（≈430 km²）的小岛丢弃 |
| 结果 | 116 块 / 2,130 点 / 30.9 KB | **408 块 / 6,032 点 / 88 KB** |
| 页面体积 | 483.6 KB | **540.9 KB** |
| 肉眼差别 | 大陆轮廓可辨，海峡与群岛糊在一起 | 日本列岛、英吉利海峡、印尼群岛、北美东岸细节清晰 |

切换精度（生成物会覆盖 `data/land.json`）：

```bash
python -m pip_app.tools.build_land_data --scale 110m              # 低精度、省体积
python -m pip_app.tools.build_land_data --scale 50m               # 默认，高精度
python -m pip_app.tools.build_land_data --scale 50m --eps 0.16    # 更细（~8,000 点 / 117 KB）
python -m pip_app.tools.build_web
```

经纬网同步加密到 20°。若 `data/land.json` 缺失，前端自动回落到手绘轮廓——不会白屏。

### v0.10：Cyber Intelligence Dashboard

整站改为网络情报指挥中心风格，**布局、数据绑定、交互一律不变**，只换视觉层：

| 层 | 做法 |
|:--|:--|
| 背景 | 深海军蓝 `#03080f` + 两处径向冷光 + 电子网格（48px 主线 / 12px 点阵，径向遮罩）+ 全屏扫描线 |
| 面板 | 半透明玻璃（`rgba(7,24,39,.72)`）+ 1px 青色描边 + 四角 L 形角标 + 顶部横向扫描光 |
| 标题 | 38px 加粗 + 青色外发光；`情报日报` 单独强调 |
| 导航 | 每项带 13px 线性图标，选中态青色 + 底部长条发光 |
| 统计卡 | HUD 切角（`clip-path` 八角）+ mono 小标签（FEED / GEO / INTEL / ZH）+ 25px 等宽数字 |
| 按钮 | 切角 + 青色描边 + 内发光 + 循环扫光；hover 提亮 |
| 地球 | 72 格刻度环 + 双扫描弧 + 呼吸节点 + 流动粒子 + 球下三层全息平台 + 缩放（滚轮 0.72–1.45） |
| 列表 | 暗色玻璃卡 + 左侧域色竖条 + hover 位移与青色辉光；标签全部 mono 大写 |
| 底部切换 | 固定在视口左下（`position:fixed`），滚动时始终可达 |

字体换成 `Rajdhani`（标题）+ `JetBrains Mono`（数字与标签），中文回落系统黑体。

**没有引入 Three.js**：地球仍用 Canvas 2D 正交投影（packetvoyage 已把经纬度、大圆弧算好），零额外依赖、离线可用、滚动/缩放/拖拽都在 60fps。视觉上的"3D 感"来自球面渐变、边缘辉光、外环与平台，而不是引擎。

### v0.8：接入 packetvoyage 的真实地理与物理

地球不再是我画的示意球，而是由 `packetvoyage-master`（MIT）的 `geo.py` 生成数据，前端只做正交投影：

| packetvoyage 能力 | PIP 用法 |
|:--|:--|
| `great_circle_arc()` | 每个来源城市 → 采集端（北京）的大圆航迹；跨太平洋经度连续，不断线 |
| `haversine_km()` + `min_rtt_ms()` | 每段航迹标注距离与光纤理论最低 RTT（北京–旧金山 9,503 km / 95.0 ms） |
| `terminator_points()` + 太阳直射点 | 球体按太阳方向做径向渐变，自然呈现昼夜 |
| 城市坐标表 | 8 个编辑部城市（旧金山/纽约/波士顿/华盛顿/伦敦/巴黎/柏林/北京/多哈/香港） |

渲染换成 Canvas 2D：正交投影 + 可拖拽旋转 + 缓慢自转 + 虚线流动；城市标签做碰撞避让。**packetvoyage 只贡献数据与算法，不引入它的 MCP/CLI 运行时。**

重新生成地球数据（采集后跑一次）：

```bash
python -m pip_app.tools.build_globe_data    # 输出 pip_app/data/globe.json
python -m pip_app.tools.build_web           # 内联进 index.html
```

### v0.7：以 Packet Voyage `/report` 为主版式

首屏直接照 `packets.simplyzee.dev/report` 的结构重做，数据面板下移：

| PV /report 元素 | PIP 对应 |
|:--|:--|
| 左上米黄纸卡（标题 + 内部导航 + 一句话摘要 + 主按钮） | 同日历 + 8 项统计 + 「刷新数据」「查看全部条目」 |
| 右侧大幅暗色地球 + 光柱 | 经纬网球 + 简化大陆 + 光柱（长度 = 该国条目量，琥珀 = 最多那国） |
| 左下胶囊切换 Speed / Your data / Route | **条目 / 分布 / 健康** |
| 正文极简（3 行内说清是什么） | 「524 条情报，来自 23 个源、5 个国家；其中 456 条时间可信度达标」 |

hero 下方才是内容面板：横排筛选条（频道 / 可信度 / 来源 / 搜索）+ 纸卡列表；切到「分布」是柱形图 + 条形图，切到「健康」是源卡片网格。v0.6 的纸质皮肤（米黄纸卡、衬线标题、深 navy 底）全部保留。

### v0.6：整站纸质皮肤（Packet Voyage 全量）

整站改用 `packets.simplyzee.dev` 的设计语言，不再只是顶栏：


| 元素 | Packet Voyage 做法 | PIP 落实 |
|:--|:--|:--|
| 底色 | `--abyss #071526` + 地球光晕 | 深navy + 两处径向光晕（右上冷光、左下海水） |
| 卡面 | `--paper #f3ebda`、描边 `--paper-edge #dccfb4`、大圆角 | 所有卡片 / 条目 / 票据统一纸卡，圆角 12–14px |
| 标题 | `Young Serif` 衬线、粗、字距略松 | 品牌、卡片标题、条目标题、所有数字 |
| 正文 | `Hanken Grotesk` 无衬线 | meta、摘要、表单（Google Fonts 加载失败时回落 Georgia / 系统字体） |
| 强调 | `--amber #e09a2b`、`--sea #2f8c9c` | 高可信热卡、图表条、链接 hover |
| 按钮 | 深色胶囊 | Refresh（`--deep` 胶囊）、Clear（描边小按钮） |
| 分隔 | 细墨线 `rgba(31,42,55,.16)` | 卡片头、字段、健康行 |

条目标题现在用衬线排，中文回落到宋体——这是有意的：让「日报」读起来像一份印刷刊物，而不是后台表格。

### v0.3：顶栏票据（Packet Voyage）

顶栏数据条改为 **Packet Voyage**（`packets.simplyzee.dev`）的票据风格，token 取自其 CSS 变量：

| Token | 原值 | PIP 用法 |
|:--|:--|:--|
| `--abyss` | `#071526` | 顶栏深底 |
| `--deep` | `#0f2740` | 顶栏边线、按钮底 |
| `--paper` | `#f3ebda` | 数据票据卡背景 |
| `--paper-edge` | `#dccfb4` | 票据描边 |
| `--pv-ink` / `--pv-soft` | `#1f2a37` / `#5b6573` | 票据上的数字与标签 |
| `--amber` / `--amber-glow` | `#e09a2b` / `#f6c06a` | 「高可信」热卡、低可信条 |
| `--sea` / `--sea-bright` | `#2f8c9c` / `#5cc8d6` | 图表条、地球图标高光 |
| `--serif` | `Young Serif, Georgia, serif` | 品牌名、所有数据数字 |

**布局同时调整**：左栏 = 控制台 → Briefing → Source Health（原右栏内容下移），右侧单列放条目列表（阅读宽度从 ~700px 增加到 ~1150px）。

### v0.2：卡面基线（ZipNews）

页面主体的浅色卡片、细线、域色标签仍沿用 ZipNews / World Signal 的 `static/styles.css`：

| Token | ZipNews 原值 | PIP 用法 |
|:--|:--|:--|
| 主文字 | `#10131a` | 标题 |
| 次要文字 | `#637083` | meta、字段名 |
| 卡片 | `#ffffff` / `rgba(255,255,255,.94)` | 卡片面 |
| 分隔线 | `rgba(18,24,38,.14)` | 1px 细边框 |
| 阴影 | `0 18px 45px rgba(13,23,38,.18)` | 卡片悬浮 |
| 圆角 | `8px`（卡片 10px） | 统一 |
| 强调色 | blue / teal / violet / gold / green | 域标签、可信度、分布条 |
| 底色 | `#e8edf2` | 内容区背景 |

两套 token 并存：**深色票据顶栏负责“数据”，浅色卡面负责“读内容”**。

## HTTP 端点

| 端点 | 说明 |
|:--|:--|
| `GET /` | 仪表盘（内联数据，离线可用） |
| `GET /api/meta` | 总量、域分布、可信度分布、语言、源健康计数、`daily_candidates` |
| `GET /api/items?domain=ai&conf=high&q=nvidia&limit=20` | 条目查询（三重筛选 + 上限） |
| `GET /api/health` | 当前 24 源健康（含 `red` 列表） |
| `GET /screens/*` | 截图静态资源 |

`daily_candidates` 是 W2 日报的输入量：只统计 `time_confidence=high` 的条目。

## 目录

```
pip_app/
├── sources.json            24 源（2026-11-24 实测，含 tier）
├── config.py               全部参数集中：超时 15s、并发 8、单源上限 40、预算 180s
├── feedparse.py            RSS2 + Atom 解析（stdlib，无第三方依赖）
├── collect.py              抓取 → 解析 → 时间判定 → 去重 → 落盘 → 健康记录
├── health_report.py        按源聚合成功率，RED/YELLOW/GREEN/RETIRED
├── cli.py                  collect / health / tail
├── tools/probe_sources.py  40 个候选源批量探测（换源时用）
├── tools/inspect_items.py  当日数据体检（可信度分布、空摘要、重复）
├── data/items/YYYY-MM-DD.jsonl      当日条目（按 URL 合并，保留最新）
└── data/source_health.jsonl         每次运行每源一行（append-only）
```

## items.jsonl 字段

| 字段 | 说明 |
|:--|:--|
| `id` | `content_hash(title,url)[:16]`，稳定标识 |
| `domain` / `source_id` / `source_name` / `lang` | 来源元信息 |
| `title` / `url` / `summary` | 标题、链接、去标签摘要（≤400 字） |
| `published_at` | UTC；`time_confidence=low` 时为 `null` |
| `fetched_at` | 采集时刻（UTC），与 `published_at` 严格分离 |
| `time_confidence` | `high` 窗口内 pubDate / `medium` feed 时间 / `low` 超窗或同戳 |
| `time_source` | `item_pubDate` / `feed_updated` / `unknown` |
| `content_hash` | `sha256(title + summary)`，供 §5.6 分析缓存复用 |

## 与 PIP v1.2 的对应

| 设计条目 | 落点 |
|:--|:--|
| §5.3 并发 / 全局预算 | `config.WORKERS=8`、`GLOBAL_BUDGET_SECONDS=180` |
| §5.4 时间可信度 | `normalize()` 调 `pip.time_confidence.resolve`；同戳与全空两种情形都降 `low` |
| §5.2 三阶段去重 | `collect()` 调 `pip.dedupe.dedupe`，跨源合并、按 URL 保留最新 |
| §11.2 可观测 | `source_health.jsonl` 逐源记录 status/fetched/error/duration |
| 源健康趋势 | `health_report` 7 天窗口 + `RETIRED`（换源后旧 id 不再计入红色） |

## 数据源（31 个 / 4 个域）

| 域 | 数量 | 源 |
|:--|:--:|:--|
| `ai` | 13 | TechCrunch AI、Ars Technica、The Verge、MIT Tech Review、Google AI Blog、DeepMind、Hugging Face、Hacker News、Simon Willison、GitHub Blog、机器之心→IT之家、量子位、Google News · AI |
| `geopol` | 11 | Al Jazeera、CNBC World、Guardian World、Politico、The Hill、NPR World、France 24、Euronews、SCMP、Financial Times、WSJ Markets |
| `skills`（AI 技能 / 工具） | 5 | OpenAI News、The Decoder、Product Hunt、Latent Space、InfoQ 中文 |
| `oss`（GitHub 开源） | 2 | GitHub Trending（社区 RSS）、GitHub Changelog |

新增于 2026-11-25。Anthropic / MCP / n8n / Dify 的 RSS 当时返回 404 或证书错误，未纳入。

## 失败语义（重要）

| status | 含义 | 是否计入源质量 |
|:--|:--|:--|
| `ok` | 正常返回条目 | ✓ |
| `zero_result` | 200 但 0 条（不等于成功） | ✓（算不健康） |
| `failed` | HTTP 4xx/5xx、坏 XML、非 feed | ✓ |
| `unreachable` | 网络层失败：DNS / TLS / 连接重置 / 超时 | **✗ 不计入** |

`success_rate = ok / (runs - unreachable)`。这条是踩出来的：2026-11-25 凌晨有 7 个域名在本机整体不可达（单线程也超时），若把它们算成「源坏了」，健康表会把好源全标红。

## 已知问题（W2 处理）

1. **3 个源已改版为 HTML 页面**：`36kr.com/feed`、`caixin.com/rss/all.xml`、`jiqizhixin.com/rss` 均返回 HTML，已替换为 `ithome` 与 `financial-times`，旧 id 在健康报告中单列为 `RETIRED`。
2. **空摘要**：HN、Google News 等源 `description` 为空，W2 接正文抽取时补。
3. **`low` 条目**：深层源（deepmind、wsj-markets、huggingface）RSS 内含超 30 天旧文，按设计降级，不污染日报主列表。
4. **网络可达性波动**：部分域名在特定时段整体不可达（DNS/TLS 层），已用 `unreachable` 与源故障区分；不做自动换源，避免掩盖本地网络问题。

## 测试

```bash
python -m unittest discover -s pip_app/tests -t . -p 'test_*.py'   # 56 例
cd pip_skeleton && python -m unittest discover -s tests -t .        # 70 例
```

合计 **126 例**，全部离线（fixture 回放，不联网、不调 LLM）。

---

## 部署（生产）

`pip_app.server` 是生产入口（`pip_app.serve` 仅供本地调试）：

```bash
PIP_HOST=0.0.0.0 PIP_PORT=8080 PIP_AUTO_COLLECT=1 python -m pip_app.server
```

| 能力 | 说明 |
|:--|:--|
| `/healthz` | 探针，数据为空返回 503 |
| `/metrics` | Prometheus 文本（请求数 / 耗时 / 条目数 / 覆盖区域） |
| `/api/world` | 全球覆盖扫描 |
| gzip | >1 KB 且客户端支持时自动压缩 |
| 缓存 | HTML/API `no-store`，截图 `max-age=86400` |
| 日志 | 每行 JSON，含 path / status / ms |
| 优雅关闭 | SIGTERM / SIGINT |
| 定时采集 | `PIP_AUTO_COLLECT=1`，间隔 `PIP_COLLECT_INTERVAL` |

镜像与编排：`Dockerfile`、`docker-compose.yml`、`deploy/pip.service`。完整步骤见 **[DEPLOY.md](../DEPLOY.md)**。

## 全球覆盖扫描

`pip_app/world_scan.py` 把 31 个源按大洲聚合，回答「情报覆盖是不是真的全球化」：

| 区域 | 源 | 今日条目 | 状态 |
|:--|--:|--:|:--|
| 北美 | 20 | 376 | 已覆盖 |
| 西欧 | 6 | 73 | 已覆盖 |
| 东亚 | 4 | 75 | 已覆盖 |
| 中东 | 1 | 0 | 薄弱 |
| 南亚 / 东南亚 / 大洋洲 / 拉美 / 非洲 / 东欧与俄 | 0 | 0 | **盲区** |

**全球覆盖率 40%**（4/10 区域，7 国）。这个数字比「31 个源」诚实得多——说明当前情报网本质是北美 + 西欧 + 东亚视角。

页面上是「世界」标签（或 `#world` 直达），API 是 `/api/world`。国家归属取编辑部所在城市（`build_globe_data.SOURCE_PLACE`）。

### 补盲：40% → 100%

第一版覆盖率 40%（4/10 区域），6 个盲区一个源都没有。逐个探测候选源（两轮共 39 个 URL，只留能解析出条目的），补入 **22 个**：

| 区域 | 新增来源 | 结果 |
|:--|:--|:--|
| 南亚 | The Hindu、Times of India、Dawn | 3 源 / 88 条 |
| 拉美 | G1 Globo、La Nación、Clarín | 3 源 / 87 条 |
| 非洲 | Premium Times、Africanews、The Standard Kenya | 3 源 / 85 条 |
| 大洋洲 | The Guardian Australia、RNZ、SBS News | 3 源 / 66 条 |
| 东南亚 | Straits Times、CNA、Bangkok Post、VnExpress、Rappler | 5 源 / 117 条 |
| 东欧与俄 | Kyiv Post、Balkan Insight、Notes from Poland | 3 源 / 91 条 |
| 中东 | The Times of Israel（原有 Al Jazeera） | 2 源 / 40 条（仍薄弱） |
| 西欧 | El País América（编辑部马德里） | 7 源 / 189 条 |

**当前：10/10 区域、25 国、53 源、1,413 条，盲区 0。**

探测中被淘汰的典型：Folha/Infobae/Arab News/Jordan Times 返回 403，Bangkok 以外的 `gulfnews`/`khaleejtimes` 404，`rferl` 能解析但 0 条，`tehrantimes` 标题字段错位。规则是**能解析出条目才算接**，不为了凑数硬加。

中东仍标 `thin`（2 源）——`gulfnews`/`khaleejtimes`/`arabnews` 都拒绝访问，本地源普遍反爬，这一块没能做实，页面如实显示琥珀色而不是伪装成已覆盖。
