"""PIP v1.1 skeleton — 只实现设计文档里可被机器验证的部分。

模块边界对应 PIP 报告：
- time_confidence : §5.4 时间可信度三级判定
- dedupe          : §5.2 三阶段去重（宁重复不误并）
- analysis_cache  : §5.6 文章级分析缓存
- state_machine   : §11.2 降级状态机与阻断规则
- fetch           : §5.3 并发 / 单飞 / 冷却 / 预算
"""

__version__ = "1.1.0"
