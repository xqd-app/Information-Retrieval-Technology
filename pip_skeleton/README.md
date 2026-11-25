# PIP v1.2 参考骨架（pip_skeleton）

这不是完整实现，而是把 PIP v1.2 设计里**能被机器验证的部分**先落地，用来证明设计可行、并把「测试」从承诺变成红灯。

```
pip_skeleton/
├── pip/
│   ├── time_confidence.py   §5.4  时间可信度三级判定（high/medium/low）
│   ├── dedupe.py            §5.2  URL 归一 → 标题精确 → Jaccard 0.85 三阶段
│   ├── analysis_cache.py    §5.6  文章级分析缓存（SQLite，命中率可统计）
│   ├── stability.py         §6    规则优先的稳定性判级 + rule_trace
│   ├── state_machine.py     §11.2 连续降级阻断周报 + 预算阈值
│   ├── fetch.py             §5.3  并发、单飞文件锁、冷却、全局预算
│   ├── stance_memory.py     §6.4  立场知识层：三层记忆 + 收缩 + 校准 + 回滚门
│   └── bilingual.py         §5.7  双语交付：术语/数字/完整性三道门 + 翻译缓存
└── tests/                   70 例，全部离线（无网络、无 LLM）
```

## 运行

```bash
cd pip_skeleton
python -m unittest discover -s tests -t . -v
```

当前状态：`Ran 70 tests ... OK`（Python 3.11+，仅标准库，约 0.5s）。

## 两个 v1.2 新增能力怎么被证明

### 立场层「越跑越准」（§6.4）

`tests/test_stance_memory.py::SelfEvolutionTest` 用 40 个模拟来源跑 12 轮：前 2 轮预测准确率约 0.72，12 轮后约 0.90。

**反事实证明**：把「累加观测」改成「只保留最近一次」，同一测试的准确率降到 0.70，断言（≥0.80 且比第 2 轮高 5pp）必然失败。这说明测试锁住的是「积累」这一行为，不是走过场。

### 双语三质量门（§5.7）

`tests/test_bilingual.py` 固定住：`world model` 译成「全球模型」即违规；`350 亿美元` 与 `35 billion` 判一致（量级归一）；`94%` vs `49%` 判不一致；P0 缺任一语言直接 `MissingBilingualError`；翻译缓存命中时翻译函数零调用。

## 测试与真实事故的对应

| 测试文件 | 覆盖 | 对应的真实事故 |
|:--|:--|:--|
| `test_fetch.py` | A1–A5 | ai-news 的 403 记 `ok:true`、ZipNews 的同步阻塞 |
| `test_time_confidence.py` | B1–B4 | ai-news 的 `lastBuildDate` 冒充发布时间 |
| `test_dedupe.py` | C1–C4 | AI-Search 的 Jaccard 误并风险 |
| `test_analysis_cache.py` | D3–D4 + 规则覆盖 | Insight-News 的无限重试烧钱 |
| `test_state_machine.py` | E1–E3 | world-model 连续 35 天 fallback 无人发现 |
| `test_stance_memory.py` | G1–G5 | Insight-News 的循环论证评测 |
| `test_bilingual.py` | H1–H5 | ai-news 的术语误译（`LLM=True`→「法学硕士」） |

## 尚未实现（有意留空）

- RSS 解析与真实 HTTP（`fetch_one` 由调用方注入，便于替换 transport）
- LLM 调用与摘要（`stability.judge` 接受 `llm_stability`，`stance_memory` 只记账不推理）
- 事件聚类与三问抽取（L0 观测的采集侧）
- `llms.txt` / `prompt_patch.md` 生成器（§10.3）
- 文档契约测试（§11.4，需要真实报告文本才能断言）

## 接入顺序建议

1. `fetch.py` 的 `fetch_one` 接上 RSS 适配器，跑通 A 组。
2. 用真实历史数据回放 `time_confidence`，统计 `low` 占比（>15% 说明源质量需干预）。
3. `analysis_cache` 先跑一周只读统计，确认边界日确实重复，再开写。
4. 立场层先只写 L0 观测、不对外展示；攒够 4 周再开 L2 预测与回滚门。

## 设计约束（写进代码的，不写在文档里的）

- `DEDUP_THRESHOLD = 0.85`、`MIN_TOKENS_FOR_FUZZY = 6`：宁可重复，不可误并。
- `AGREEMENT_FLOOR = 0.8`：规则可覆盖 LLM 的 `stable` 判断。
- `DEGRADED_BLOCK_DAYS = 3`：连续降级必须阻断周报，不只是告警。
- `throttle_remaining()` 默认 600s：手动刷新必须有冷却。
- `DEFAULT_PRIOR_WEIGHT = 5.0`：一条观测不能给一家来源定性。
- `ROLLBACK_MARGIN = 0.05`：准确率跌破基线 5pp 即降级展示。
