# PIP v1.1 设计补丁与实施计划

> 定位：本文是 PIP 项目报告的**增量修订稿**，不是新方案。它承接「六项目吸收审计」的结论，把 3 处实质缺口、1 处自我矛盾、2 处需明示的取舍，落成可直接并入原报告的章节正文、数据结构与验收标准。
> 读取方式：每一节 = 原章节的替换/追加内容；编号沿用审计文本引用的章节（§5.1、§5.2、§11.1–11.3、M1–M6），若你的原稿编号不同，按标题内容定位。
> 一句话结论：v1.1 补的是「**可验证性**」——不只声明做了鉴权、降级、去重，而是给出可被机器检查的判定条件。

---

## 0. 变更摘要（v1.0 → v1.1）

| 编号 | 类型 | 目标位置 | 吸收来源 | 解决的问题 | 验收方式 |
|:--:|:--|:--|:--|:--|:--|
| C1 | 新增 | §5.3 采集并发与刷新闸门 | ZipNews（同步阻塞、`?refresh=1` 无冷却） | PIP 未定义采集是同步/异步、无刷新限流 | 并发参数表 + 闸门伪代码 + 压测记录 |
| C2 | 新增 | §5.4 时间可信度校验 | ai-news（`lastBuildDate` 冒充发布时间） | `published_at` 有字段、无校验规则 | `time_confidence` 三值 + 三条判定规则 + 单测 |
| C3 | 新增 | §5.6 文章级分析缓存 | Insight-News（content hash 幂等） | 边界日重复摘要、token 白烧 | `analysis_cache` 表 + 命中率指标 |
| C4 | 新增 | §5.7 跨语言与术语一致性 | ai-news（翻译缓存） | 外文源（arXiv/HN/官方博客）无翻译设计 | 术语表 + 译文缓存 + 术语命中率 |
| C5 | 修改 | §6 分析层 | Insight-News（中间指标落库） | 只存稳定性等级，不存判断依据 | `stability_evidence` 表 + 可解释字段 |
| C6 | 决策 | §6.4 多源立场对比 | Insight-News（事件聚类/偏见） | 政经领域最该做却未做 | 做/不做的显式声明 + 若做的最小设计 |
| C7 | 新增 | §10.3 Agent 接入层 | world-model（llms.txt + prompt patch） | 只有双格式，Agent 接入弱 | `llms.txt` + `prompt_patch.md` 产物 |
| C8 | 修改 | §11.2 预算与可观测 | world-model（35 天 fallback 无人发现） | 有 `degraded` 标记、无连续告警 | 连续降级状态机 + 阻断规则 |
| C9 | 新增 | §11.4 文档-实现一致性检查 | 六项目共性（README 漂移） | 「报告声明不漂移」只是承诺 | CI 断言脚本 + 漂移清单 |
| C10 | 新增 | §12 测试策略 | 六项目共性（测试不足）**——本次审计认定的自我矛盾** | M1–M6 无一行测试 | 测试矩阵 + CI 门禁 + 覆盖率阈值 |
| C11 | 修改 | M1–M6 里程碑 | 审计建议 1–5 | 补丁无归属、无 gate | 每阶段交付物与退出条件 |

**修订后 PIP 的一句话定位**（可直接替换报告开头的定位句）：

> PIP 是一套面向 AI 与政经领域的**可审计情报流水线**：以「规则优先、LLM 润色、证据落库」为分析原则，把每日全球信息压缩成一份带降级标记、可回溯证据、可被 Agent 直接消费的白话日报；它的第一版不追求展现与跨语言体验，但要求每一次失败都能被看见、每一笔 token 都能被归因。

---

## 1. §5.3 采集并发与刷新闸门（新增）

### 1.1 问题

审计指出：PIP 未说明采集是同步还是异步，也没有刷新限流。ZipNews 的教训是——一次请求内同步等完 45 路源（最坏 40s），`?refresh=1` 无冷却，任何匿名 GET 都能触发全量重抓，同时 `/api/health` 不做 I/O 从而掩盖真实可用性。

### 1.2 设计

**模式：异步采集 + 单飞（single-flight）刷新 + 显式冷却期。** 采集永远不在 HTTP 请求路径内执行；请求只读最近一次产物。

| 参数 | 值 | 理由 |
|:--|:--|:--|
| 采集触发 | cron（每日 2 次）+ 手动 `/fetch` | 手动路径必须带 `X-API-Key` |
| 单源并发 | `ThreadPoolExecutor(max_workers=8)` | 与 ZipNews 的 10 相近，留出重试余量 |
| 单源超时 | connect 5s / read 10s | 分离连接与读取，避免慢响应拖死整批 |
| 单源重试 | 2 次，指数退避 1s/4s | 仅对 5xx 与超时重试；4xx 立即放弃 |
| 全局预算 | 单次采集 wall-clock ≤ 180s，超时即中止并标 `partial` | 防 cron 重叠 |
| 刷新冷却 | 同一 `domain` 手动刷新 ≥ 10 min 才生效，否则返回 `429 + retry_after` | 直接对应 ZipNews 缺口 |
| 单飞锁 | 以 `date+domain` 为键的进程内锁 + 状态文件锁 | Actions 无长驻进程，用文件锁兜底 |

```python
# fetch.py 核心骨架（示意）
def collect(domain: str, force: bool = False) -> CollectResult:
    lock = acquire_lock(f"fetch:{domain}")          # 文件锁，阻塞 0s，拿不到即返回 busy
    if lock is None:
        return CollectResult(status="busy", retry_after=60)
    state = load_state(domain)                       # 上次成功时间、上次 refresh 时间
    if not force and now() - state.last_refresh < COOLDOWN[domain]:
        return CollectResult(status="throttled", retry_after=COOLDOWN[domain] - elapsed)
    deadline = now() + GLOBAL_BUDGET
    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(fetch_one, s, deadline): s for s in sources(domain)}
        for fut in as_completed(futs, timeout=GLOBAL_BUDGET):
            results.append(fut.result())             # fetch_one 内部已吞异常并返回 status
    write_health(domain, results)                    # 追加 source_health.jsonl，逐源一行
    return CollectResult(status="partial" if any_failed else "ok", items=merge(results))
```

### 1.3 验收标准

- 单源超时不影响其余源，`source_health.jsonl` 中该源为 `{"status":"failed","error":"timeout"}`。
- 冷却期内第二次手动刷新返回 429 且 `retry_after` 正确；冷却期外正常执行。
- 采集总耗时在 180s 内中止，产物标记 `partial: true`，日报生成时显式带降级说明。
- 同一 cron 重叠触发时，第二次拿到 `busy` 而不是并行抓两遍（用状态文件的 mtime 断言）。

---

## 2. §5.4 时间可信度校验（新增）

### 2.1 问题

`published_at` 与 `fetched_at` 已分离，但没有「如何校验源时间可信度」的规则。ai-news 的实证是：整源共用 `lastBuildDate` 当成发布时间，导致 24h 窗口失真，且这种失真在数据里看不出来。

### 2.2 设计

**字段**：
```json
{
  "published_at": "2026-11-24T02:10:00Z",
  "fetched_at": "2026-11-24T03:00:00Z",
  "time_confidence": "high | medium | low",
  "time_source": "item_pubDate | feed_updated | http_last_modified | unknown"
}
```

**三条判定规则**（按顺序短路）：

1. `item_pubDate` 解析成功且落在 `[fetched_at - 30d, fetched_at + 6h]` → `high`。
2. 仅 `feed_updated` / `channel.lastBuildDate` 可得 → `medium`，且**强制标记来源级**：同源当轮所有条目共享同一时间戳时，自动降为 `low`（这正是 ai-news 的坑）。
3. 时间缺失、解析失败、或超出窗口 → `low`，`published_at` 置为 `null`，仅保留 `fetched_at`。

**窗口归属规则**：日报窗口只接受 `time_confidence != "low"` 的条目；`low` 条目进入「待核验池」并计入日报末尾的 `uncertain_items` 计数（不静默丢弃，也不污染主列表）。

### 2.3 验收标准

- 单测覆盖：正常 pubDate、只有 lastBuildDate、同源时间戳全相同、未来时间、缺失时间、非法格式（6 个用例）。
- 对历史数据回放：给定 ai-news 式 feed，`low` 占比应 > 0 且日报主列表不含这些条目。
- 日报 JSON 中 `uncertain_items` 可被下游读取，且在 Markdown 版以「另有 N 条时间存疑」一行呈现。

---

## 3. §5.6 文章级分析缓存（新增）

### 3.1 问题

`content_hash` 只用于去重，不用于「同一文章再次进入日报窗口时复用已生成的摘要与稳定性评级」。后果：UTC 边界日（同一篇文章在两次窗口中都满足条件）、增量重跑、失败重试三种场景都会重复付费。

### 3.2 设计

缓存放 **SQLite**（与 ChromaDB 并置，不放进向量库——这是元数据不是向量）：

```sql
CREATE TABLE analysis_cache (
  content_hash   TEXT PRIMARY KEY,      -- sha256(title + normalized_body)
  domain         TEXT NOT NULL,
  lang           TEXT NOT NULL,
  summary_zh     TEXT NOT NULL,
  stability      TEXT NOT NULL,          -- stable | developing | contested
  evidence_json  TEXT NOT NULL,          -- 见 §5.5，稳定性依据
  model          TEXT NOT NULL,
  prompt_version TEXT NOT NULL,          -- 提示词改版即失效
  tokens_in      INTEGER,
  tokens_out     INTEGER,
  created_at     TEXT NOT NULL,
  last_hit_at    TEXT
);
CREATE INDEX idx_cache_domain_created ON analysis_cache(domain, created_at);
```

**命中规则**：
- 命中条件 = `content_hash` 相同 **且** `prompt_version` 相同 **且** `model` 相同。
- 命中即复用 `summary_zh / stability / evidence_json`，只更新 `last_hit_at`，不重算。
- 正文变化（`content_hash` 变）→ 视为新文章。
- 提示词改版（`prompt_version` 变）→ 旧缓存不删，仅不再命中；提供 `--invalidate-cache` 显式重建。

**指标**：每次日报生成输出 `cache_hit_rate`，写入当日 metadata。目标：稳定运行一周后 `cache_hit_rate ≥ 15%`（边界日与重跑占主导）。

### 3.3 验收标准

- 同一篇文章连续两次进入生成流程，第二次 LLM 调用次数为 0（用 mock LLM 计数断言）。
- 修改 `prompt_version` 后，同文重新计算（断言调用次数 +1）。
- 日报 metadata 中 `cache_hit_rate` 字段存在且可聚合。

---

## 4. §5.7 跨语言与术语一致性（新增）

### 4.1 问题

AI 前沿的主力源是外文（arXiv、HN、官方博客），白话日报必然跨语言，但原设计只有 `language` 字段。审计判定这是「弱于 ai-news」的实质缺口。

### 4.2 设计（最小可用版）

1. **翻译缓存表**（同库 SQLite）：
   ```sql
   CREATE TABLE translation_cache (
     src_hash TEXT PRIMARY KEY,      -- sha256(lang + text)
     src_lang TEXT, dst_lang TEXT,
     translated TEXT, engine TEXT, created_at TEXT
   );
   ```
2. **术语表**（`glossary.yaml`，人工维护 200 条起步）：
   ```yaml
   - src: "world model"
     zh: "世界模型"
     forbid: ["全球模型", "世界建模"]
   - src: "inference-time compute"
     zh: "推理期算力"
   ```
3. **注入方式**：翻译请求的 system prompt 附术语表命中项（只传命中，不传全表，控制 token）；译后做术语回检，命中 `forbid` 即重译一次，仍失败则标 `glossary_violation` 并降级为原文直引。
4. **双语落库**：摘要保留 `summary_zh` + `key_terms_en`，便于后续做英文版。

### 4.3 验收标准

- 术语回检：给定 20 条含术语的英文句，`glossary_violation` 率 < 5%。
- 翻译缓存命中时零 API 调用（mock 计数断言）。
- 日报中每条外文来源都带 `src_lang`，且中文摘要不出现 `forbid` 列表中的译法。

### 4.4 若第一版不做（可替代的取舍声明）

> 第一版仅处理英文源，中文摘要由 LLM 直译生成，术语一致性不做强制校验；`src_lang` 字段保留以便 M4 接入 `glossary.yaml`。此取舍的代价是：专业术语可能出现「世界模型/全球模型」不一致，评阅时应按「可用但不精校」标准判断。

---

## 5. §6 分析层修订：中间指标持久化与可解释性

### 5.1 问题

PIP 吸收了「规则优先 + LLM 润色」，但没有吸收 Insight-News 最关键的一半——**把中间判断依据落库**。只存最终 `stability` 等级，等于把可解释性丢在生成现场。

### 5.2 设计：稳定性三元组 → 稳定性证据包

把原来的「三元组」（`stability / confidence / rationale`）扩展为**可审计的证据包**：

```json
{
  "stability": "developing",
  "confidence": 0.68,
  "rule_signals": {
    "source_count": 4,
    "source_agreement": 0.75,
    "has_primary_source": true,
    "contradiction_terms": ["however", "denied"],
    "time_span_hours": 19
  },
  "llm_signals": {
    "model": "deepseek-chat",
    "prompt_version": "stability-v3",
    "rationale": "两家通讯社给出不同伤亡数字，官方通报未更新"
  },
  "final_rule": "source_agreement<0.8 AND contradiction_terms>0 → developing"
}
```

落库到 `stability_evidence(content_hash, signals_json, rule_trace, created_at)`。**规则先算、LLM 后判、规则可覆盖 LLM**：当 `source_agreement < 0.8` 且出现矛盾词时，无论 LLM 说什么，最终等级不得为 `stable`（硬约束写入代码，不写在提示词里）。

### 5.3 验收标准

- 每条日报条目的 instability 判级都能追到 `rule_trace` 中的一行具体规则。
- 构造「4 源报道、2 源数字冲突」的样本，最终等级必须是 `developing` 或 `contested`，不得为 `stable`。
- LLM 不可用时，仅凭 `rule_signals` 仍能给出等级与理由（降级路径可跑）。

---

## 6. §6.4 多源立场对比：显式取舍（决策项）

审计指出这是政经领域最实质的缺口，且必须**明说**，否则读者会误以为 PIP 在对标 Insight-News 的分析深度。

### 6.1 建议：做“最小可用版”，不做“完整偏见评分”

**理由**：完整偏见评分需要来源基线表 + 政治口径定义 + 人工标注验证集，成本远高于收益，且 Insight-News 的评测本身存在循环论证（ground truth 用来源标签，模型却看不到来源）。而「同一事件多源表述差异」只需要事件聚类 + 差异抽取，收益直接对应「打破信息壁垒」的产品目标。

**最小设计（M3 范围，约 3 人日）**：

1. **事件聚类**：对当日条目按标题/实体 Jaccard（阈值 0.45）+ 时间窗 48h 聚类，复用 AI-Search 的三段去重思路，但目的从「删重复」改为「聚多视角」。产出 `event_cluster(event_id, article_ids[], source_diversity)`。
2. **差异抽取**：对簇内 ≥3 源的条目，让 LLM 只回答三个问题（不给政治标签）：①各源在**事实**上有何不同（数字、时间、地点、当事方）；②各源**引用了谁**（官方/匿名/专家/社交媒体）；③哪些关键要素**只有一方提到**。
3. **展示**：日报中该事件下方以「多源差异」小节呈现，标注来源数量与来源名，不做左右标签。

**明确不做**：`political_lean` 评分、来源偏见基线、立场百分比。理由写进报告：单源标签无法验证，且与「白话」定位冲突。

### 6.2 若第一版不做

> 第一版不做多源立场对比，只做单源摘要与稳定性判级。这意味着 PIP 在「同一事件的多视角呈现」上弱于 Insight-News；该能力的缺失已在 §6.4 登记为 M3 可选项，触发条件为：政经领域条目中「同事件 ≥3 源」的占比连续两周 > 20%。

---

## 7. §10.3 Agent 接入层：llms.txt + prompt patch（新增）

### 7.1 问题

PIP 有 Markdown + JSON 双格式，但没有 `llms.txt` 与 prompt patch。world-model 最有价值的设计恰在此处：**把「知识截止已过期」这件事本身变成可粘贴的补丁**。

### 7.2 设计

每日产物增加两个文件（与日报同目录）：

```
output/2026-11-24/
├── briefing.md          # 人读
├── briefing.json        # 机读（含 metadata / synthesis / items / degraded）
├── llms.txt             # Agent 入口索引
└── prompt_patch.md      # 可直接粘贴的系统指令补丁
```

`llms.txt` 内容模板：
```
# PIP — Daily World Patch
> 数据时间：2026-11-24T02:00Z（UTC）｜覆盖：AI / 政经｜条目：37

## 端点
- 当日摘要（人读）: ./briefing.md
- 当日数据（机读）: ./briefing.json
- 系统指令补丁: ./prompt_patch.md
- 归档模板: ../{YYYY-MM-DD}/briefing.json

## 使用约束
- 本文件的所有结论标注了 stability 与来源数，未标注者视为未经核验
- degraded=true 时，当日结论不可作为事实引用
```

`prompt_patch.md` 结构（≤ 15 行，控制在 400 token 内）：
```
[World State Patch — 2026-11-24]
你的知识截止时间已过期。以下是截至 2026-11-24T02:00Z 的世界状态增量。
- 数据新鲜度：2 小时前｜来源数：24｜降级：false
- 今日三条主线：<synthesis 三句>
- 未决/矛盾项：<contested 条目列表，含来源数>
使用规则：只把本补丁当作「可能的更新」，冲突时以用户提供的一手信息为准。
```

### 7.3 验收标准

- `llms.txt` 中的相对路径在产物目录内全部可解析（脚本断言 4 条路径存在）。
- `prompt_patch.md` 行数 ≤ 15、字符数 ≤ 1200，且包含 `degraded` 与「以一手信息为准」两条约束。
- 将 patch 粘贴进任一 LLM 会话后，模型能正确复述当日数据时间与降级状态（人工抽检 3 次）。

---

## 8. §11.2 修订：预算、计量与连续降级告警

### 8.1 已有部分（保留）

token 计量日志、日预算上限、`degraded: true` 标记、来源许可与付费墙处理、prompt 前基础清洗。

### 8.2 新增：降级状态机与连续告警

**状态机**（每日生成后计算，落 `pipeline_state`）：

```
normal ──(当日 degraded=true)──▶ degraded_1
degraded_1 ──(次日仍 degraded)──▶ degraded_2
degraded_2 ──(第三日仍 degraded)──▶ degraded_3  ⚠️ 告警 + 阻断周报
degraded_n ──(任一正常日)──▶ normal（并记录恢复事件）
```

**硬规则**（写成代码常量，不写进文档备忘）：

| 条件 | 动作 | 通知渠道 |
|:--|:--|:--|
| 连续 3 天 `degraded=true` | 发告警 + 当周周报**拒绝生成**（返回 `blocked_by_degraded`） | 邮件/Telegram 至少一条 |
| 连续 7 天某 `domain` 的 `success_rate < 0.5` | 该领域标 `unreliable`，日报中该领域内容降级为「仅列标题」 | 同上 |
| 单日 token 消耗 > 日预算 80% | 警告；> 100% 则截断当日 LLM 任务并标 `budget_exceeded` | 同上 |
| 连续 3 天 `cache_hit_rate = 0` 且条目数 > 0 | 视为缓存层失效，告警 | 同上 |

**为什么必须有「阻断」而不只是「告警」**：world-model 的 35 天 fallback 说明，只标记不阻断时，人会习惯性地忽略标记。阻断周报是唯一能强制人回看的机制。

### 8.3 验收标准

- 人为把 `LLM_API_KEY` 置空连跑 3 天（模拟），第 3 天产生告警且周报生成返回 `blocked_by_degraded`。
- 恢复后第 1 天状态回到 `normal`，且告警历史保留在 `pipeline_state` 中可查。
- 日预算 80%/100% 两条阈值各有单测（mock token 计数）。

---

## 9. §11.4 文档与实现一致性检查（新增）

### 9.1 问题

六项目审计里「README 与实现漂移」出现 4 次（world-model 的「完整一天」、ZipNews 的「可朗读」、Daily Bot 的「四类源/Pinned 依赖」、ai-news 的「14 平台」）。PIP 原稿只写了「报告声明不漂移」——这是承诺，不是机制。

### 9.2 设计：把声明变成可执行断言

在 `tests/test_docs_contract.py` 中，把报告里的硬声明逐条写成断言：

| 报告中的声明 | 断言 |
|:--|:--|
| 「采集 24 个源」 | `len(load_sources()) == 24` 且 `README` 与 `sources.yaml` 计数一致 |
| 「三阶段去重，阈值 0.85」 | `DEDUP_THRESHOLD == 0.85`，且阶段数为 3 |
| 「全链路 UTC」 | 全仓 grep 不到 `datetime.now()`（无 tz 版本） |
| 「写接口需 X-API-Key」 | 遍历所有 POST/PUT 路由，断言都挂了鉴权装饰器 |
| 「降级连续 3 天阻断周报」 | 常量 `DEGRADED_BLOCK_DAYS == 3` 且周报入口有该分支 |
| 「日报字段含 time_confidence」 | JSON schema 校验 sample 产物包含该字段 |

CI 里加一步 `pytest tests/test_docs_contract.py`，失败即阻断合并。

### 9.3 验收标准

- 任一断言被故意破坏（如把阈值改成 0.8）时 CI 变红。
- 报告新增硬声明时，必须同时新增断言（在 PR 模板中列为必填项）。

---

## 10. §12 测试策略（新增，回应“自我打脸”）

### 10.1 为什么这是最高优先级

六项目审计把「测试覆盖不足」列为共性风险，而 PIP 的 M1–M6 里一行测试都没有，只有盲评与引用覆盖率两个验证实验。盲评验证「报告好不好看」，**不验证「抓取器改版后会不会静默零结果」**——而这正是六个项目里最贵的失败模式（ai-news 的 `aihubtoday` 当轮 failed、world-model 的 35 天 fallback、ZipNews 的词典误配）。

### 10.2 测试矩阵（按风险倒序，共 6 组 24 例）

| 组 | 用例 | 类型 | 断言要点 |
|:--|:--|:--|:--|
| **A 抓取健壮性（最高优先）** | A1 正常 RSS | 集成 | 解析出 ≥1 条，字段齐全 |
| | A2 源返回 403 | 集成 | `status=failed`，不抛异常，不进主列表 |
| | A3 源返回 200 但 0 条 | 集成 | `status=zero_result`，**不得**标 success |
| | A4 HTML 改版（选择器失效） | 集成 | `status=failed` + `error=selector_miss`，并触发告警 |
| | A5 超时 | 集成 | 单源超时不影响其余源，总耗时受预算约束 |
| | A6 同名源重复配置 | 单测 | 配置加载期报错 |
| **B 时间与窗口** | B1 pubDate 正常 | 单测 | `high`，归入当日窗口 |
| | B2 仅 lastBuildDate | 单测 | `medium`，同源同戳降 `low` |
| | B3 UTC 边界 23:59/00:01 | 单测 | 归属正确，不重复不遗漏 |
| | B4 未来时间/时区偏移 | 单测 | 超窗置 `low`，不污染主列表 |
| **C 去重** | C1 URL 归一（utm/trailing slash） | 单测 | 判为同一篇 |
| | C2 标题完全相同 | 单测 | 合并保留最新 |
| | C3 Jaccard=0.85 边界 | 单测 | 0.85 合并、0.84 不合并 |
| | C4 同一事件不同标题 | 单测 | **不合并**（宁可重复，不可误并） |
| **D 分析层** | D1 规则先于 LLM | 单测 | LLM 说 stable 但规则判 developing → 最终 developing |
| | D2 LLM 返回非法 JSON | 单测 | 走兜底解析，失败则 `degraded` |
| | D3 缓存命中零调用 | 单测 | mock 计数为 0 |
| | D4 prompt_version 变更 | 单测 | 缓存失效，调用 +1 |
| **E 状态机与告警** | E1 连续 3 天 degraded | 集成 | 告警触发 + 周报 blocked |
| | E2 恢复日 | 集成 | 状态回 normal，历史保留 |
| | E3 预算 80%/100% | 单测 | 两阈值行为不同 |
| **F 交付契约** | F1 briefing.json schema | 契约 | 必填字段齐全 |
| | F2 llms.txt 路径可解析 | 契约 | 4 条路径存在 |
| | F3 写接口鉴权 | 集成 | 无 key 返回 401 |

### 10.3 CI 门禁

```yaml
# .github/workflows/ci.yml 关键片段
- run: ruff check . && mypy --ignore-missing-imports src/
- run: pytest -q --cov=src --cov-fail-under=60
- run: pytest tests/test_docs_contract.py -q      # §11.4 的文档断言
- run: python scripts/replay_fixtures.py          # 用固定 RSS 快照回放，不依赖外网
```

**覆盖率口径**：`src/` 行覆盖 ≥ 60% 起步，其中 `fetch.py`、`dedupe.py`、`stability.py`、`state_machine.py` 四个文件单文件覆盖率 ≥ 75%。**不追求总覆盖率数字，追求高风险文件的覆盖率。**

**离线回放**：所有抓取测试用 `tests/fixtures/*.xml` 固定快照，不联网——这样 CI 稳定、便宜、可在断网环境跑。

### 10.4 验收标准

- 24 例测试全部存在且通过；其中 A3、A4、B3、D1、E1 五例是**必须**有的（直接对应六个项目的真实事故）。
- 删掉 `test_docs_contract.py` 中任一断言，CI 变红。
- 覆盖率门槛达标，且四个高风险文件单独达标。

### 10.5 随附参考骨架

本补丁附带 `pip_skeleton/`：把 §5.2 / §5.3 / §5.4 / §5.6 / §6 / §11.2 六个可判定模块实现为纯标准库 Python，并配 **43 例离线测试**（`python -m unittest discover -s tests -t . `，当前全绿）。它的作用不是替代实现，而是让报告里每一条硬规则——0.85 阈值、0.8 一致度地板、3 天阻断、600s 冷却——都能被一行命令证伪。

| 骨架模块 | 对应章节 | 已被测试固定住的规则 |
|:--|:--|:--|
| `pip/time_confidence.py` | §5.4 | 超窗置 `low`；同源同戳降 `low`；UTC 边界不偏移 |
| `pip/dedupe.py` | §5.2 | 0.85 合并、0.84 不合并；跨语言不合并；短标题不启用模糊 |
| `pip/analysis_cache.py` | §5.6 | prompt/model 变更即失效；命中率可计算 |
| `pip/stability.py` | §6 | 规则可覆盖 LLM；LLM 缺失时 `degraded=true` |
| `pip/state_machine.py` | §11.2 | 连续 3 天阻断；恢复即归零；预算 80%/100% 两档 |
| `pip/fetch.py` | §5.3 | 零结果 ≠ 成功；单源异常不外溢；冷却与单飞可测 |

---

## 11. 里程碑重排（M1–M6）

| 阶段 | 交付物 | 新增补丁 | 退出条件（Gate） |
|:--|:--|:--|:--|
| **M1 采集地基** | `sources.yaml`、`fetch.py`、`source_health.jsonl`、`health_report.py` | C1、C2 | 24 源可跑；A1–A6 六例测试通过；冷却与单飞生效 |
| **M2 规范化与缓存** | 三阶段去重、`published_at` 校验、`analysis_cache`、`translation_cache` | C3、C4（最小版） | C 组 4 例 + B 组 4 例 + D3/D4 通过；`cache_hit_rate` 有产出 |
| **M3 分析层** | 稳定性证据包、规则硬约束、事件聚类（可选） | C5、C6 | D1/D2 通过；「4 源冲突」样本判级正确；§6.4 取舍声明定稿 |
| **M4 交付层** | `briefing.md/json`、`llms.txt`、`prompt_patch.md` | C7 | F1/F2 通过；patch ≤ 15 行；Agent 抽检 3 次正确 |
| **M5 治理与告警** | 鉴权、幂等键、预算计量、降级状态机、文档断言 | C8、C9 | E1–E3 通过；F3 通过；`test_docs_contract.py` 进 CI |
| **M6 评测与收口** | 盲评（≥20 人）、引用覆盖率、失败复盘报告 | C10 收尾 | 覆盖率门槛达标；24 例全绿；输出「已知缺陷清单」而非「零缺陷」声明 |

**关键调整**：把「测试」从 M6 的验证实验，前移为**每个阶段的退出条件**。原 M1–M6 的测试真空由此消除。M6 保留盲评（体验验证），但不再承担「质量验证」的全部职责。

---

## 12. 风险登记（含本次审计的自我矛盾闭环）

| 风险 | 触发条件 | 影响 | 缓解 | 责任人/阶段 |
|:--|:--|:--|:--|:--|
| 静默零结果（最高频） | 源改版/反爬 | 日报变薄但不报错 | A3/A4 用例 + `zero_result` 独立状态 + 连续低成功率告警 | M1 |
| 连续降级无人发现 | LLM key 失效/额度耗尽 | 37 天占位产出（world-model 原样复刻） | 状态机 + 3 天阻断周报 | M5 |
| 边界日重复计费 | UTC 跨日、重跑 | 成本翻倍 | `analysis_cache` + 命中率指标 | M2 |
| 时间戳失真 | 源用 lastBuildDate | 窗口错位、日报重复 | `time_confidence` 三级 + 待核验池 | M1 |
| 测试真空 | 赶里程碑 | 上述风险全部无预警 | 每阶段 Gate 含测试；高风险文件 75% | M1–M6 |
| 文档漂移 | 实现先改、文档后忘 | 交接成本转移 | `test_docs_contract.py` | M5 |
| 跨语言术语不一致 | 外文源占比高 | 可读性下降、专业性受损 | 术语表 + 回检（或显式取舍声明） | M2 |
| 分析深度被误读为对标 Insight-News | 报告措辞含混 | 预期管理失败 | §6.4 显式写「不做偏见评分」及理由 | M3 |

**闭环说明**：原稿「测试不足是共性风险」与「M1–M6 无测试」的矛盾，由 C10 + 里程碑重排直接消除；「文档不漂移」的承诺，由 C9 的断言机制替代。这两处不再依赖读者信任，而依赖 CI 红灯。

---

## 13. 交付前自检清单

- [ ] 报告里每一处「做了 X」都能对应一段代码或一条断言，不留纯承诺句
- [ ] `degraded` 出现时，日报、JSON、llms.txt 三处口径一致
- [ ] 所有写接口（含手动 `/fetch`）都有 `X-API-Key` 与幂等键
- [ ] 冷却期、超时、重试、预算四个参数都在配置文件中，不散落硬编码
- [ ] 时间一律 UTC 存储，展示层才本地化；全仓无裸 `datetime.now()`
- [ ] 高风险四文件覆盖率 ≥ 75%，24 例测试全绿
- [ ] `llms.txt` 路径可解析，`prompt_patch.md` ≤ 15 行
- [ ] §6.4 的取舍（做或不做多源立场对比）已明确写出，不含糊
- [ ] 首次部署后 72 小时内检查一次 `pipeline_state`，确认无连续 degraded
- [ ] 报告结尾写明「已知缺陷清单」，而非「已完美吸收六项目优点」

---

## 14. 审计缺口闭环对照（v1.1 后各条状态）

| 审计发现 | 原状态 | v1.1 处理 | 新状态 | 位置 |
|:--|:--:|:--|:--:|:--|
| 未定义采集同步/异步、无刷新限流 | ✗ 遗漏 | 异步采集 + 单飞锁 + 冷却期 + 全局预算 | ✓ | §5.3 |
| `published_at` 有字段、无校验规则 | ◐ 部分 | `time_confidence` 三级 + 三条判定 + 待核验池 | ✓ | §5.4 |
| `content_hash` 只去重、不复用分析 | ✗ 遗漏 | `analysis_cache` 表 + 命中规则 + 命中率指标 | ✓ | §5.6 |
| 中间指标不落库、只存最终等级 | ◐ 部分 | 稳定性证据包 + `rule_trace` + 规则可覆盖 LLM | ✓ | §6 |
| 事件聚类语义差异（删重复 vs 聚多视角） | ◐ 部分 | 明确目的改为「聚多视角」，给出最小设计 | ✓（可选） | §6.4 |
| 缺多源立场对比（政经最实质缺口） | ✗ 遗漏 | 决策：做「多源差异」不做「偏见评分」，理由与触发条件写清 | ◐ 显式取舍 | §6.4 |
| 缺 llms.txt / prompt patch | ◐ 部分 | 新增 Agent 接入层两个产物 + 行数与约束 | ✓ | §10.3 |
| 有 `degraded` 标记、无连续告警 | ✗ 遗漏 | 降级状态机 + 3 天阻断周报 + 四条硬规则 | ✓ | §11.2 |
| 无文档-实现一致性机制（只是承诺） | ✗ 遗漏 | `test_docs_contract.py` 六条断言进 CI | ✓ | §11.4 |
| **M1–M6 无任何测试（自我打脸）** | **✗ 矛盾** | 24 例测试矩阵 + 每阶段 Gate + 高风险文件 75% 覆盖 | **✓ 已闭环** | §12 + §11 |
| 跨语言/翻译缓存未设计 | ✗ 遗漏 | 术语表 + 翻译缓存 + 回检；或显式取舍声明 | ✓（最小版） | §5.7 |
| 前端与双语延后 | ○ 合理 | 保留延后，并在报告中承认弱于 AI-Search/ai-news | ○ 已声明 | §5.7.4 |

**结论**：原审计的 3 处实质缺口全部转为 ✓；2 处取舍中，1 处转为「显式取舍」（可验证的决策而非沉默），1 处保留延后并写明代价；唯一被我判定为「自我矛盾」的测试缺位，由 §12 + 里程碑重排闭环。**修订后可以主张：PIP 在工程治理上不弱于六项目中的任何一个，在分析可解释性上强于其中五个，在展现与跨语言上明确弱于 AI-Search 与 ai-news，且这一弱点已被写进报告而非隐藏。**

---

## 附：与六项目的对应关系（一页速查）

| PIP v1.1 组件 | 直接吸收自 | 改进了什么 |
|:--|:--|:--|
| `fetch.py` 并发 + 单飞 + 冷却 | AI-Search 的 allSettled + ZipNews 的反面教训 | 补上 ZipNews 缺失的刷新限流 |
| `source_health.jsonl` + `health_report.py` | AI-Search 死源告警 + ai-news 三态 status + ZipNews 逐源红点 | 三态语义 + 7 天成功率趋势 |
| 三阶段去重（0.85） | AI-Search URL→标题→Jaccard | 阈值显式化 + 「宁重复不误并」原则 |
| `time_confidence` | ai-news 的 lastBuildDate 事故 | 把隐性失真变成显式字段 |
| `analysis_cache` | Insight-News content hash 幂等 | 从「去重」扩展到「分析复用」 |
| 稳定性证据包 | Insight-News 三路融合 + 中间量落库 | 规则可覆盖 LLM，且留 rule_trace |
| 事件聚类（可选） | Insight-News 事件簇 | 目的从「删重复」改为「聚多视角」 |
| `llms.txt` + `prompt_patch.md` | world-model 的核心创意 | 补上 degraded 声明与使用约束 |
| 降级状态机 + 阻断 | world-model 35 天 fallback 事故 | 从「标记」升级为「阻断」 |
| 测试矩阵 + 文档断言 | 六项目共性缺陷 | 从「承诺」升级为「CI 红灯」 |
