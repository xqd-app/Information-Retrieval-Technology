"""§6.4 立场知识层（Stance Memory）：可积累、可自我校准的来源画像。

为什么不用 Insight-News 的做法：
  它的 ground truth 是「来源标签」，而模型输入里没有来源字段——准确率度量的
  其实是「标签的再现率」，属于循环论证。本模块改用可证伪的路子：
  用历史观测估计来源的表述倾向，再去预测它在新事件上的表述方向，
  预测错了就写进 calibration，准确率随样本量增长可被独立检验。

三层：
  L0 observation  原始观测（append-only，不可改写）
  L1 profile      来源画像（贝叶斯收缩 + 样本量置信度）
  L2 prediction   对未观测事件的倾向预测 + 不确定性
"""

from __future__ import annotations

import hashlib
import math
import random
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Sequence

DEFAULT_PRIOR_WEIGHT = 5.0
NEUTRAL_EPS = 0.05
DEFAULT_DOMAIN = "default"
ROLLBACK_MARGIN = 0.05

SCHEMA = """
CREATE TABLE IF NOT EXISTS source_profile (
  source    TEXT NOT NULL,
  domain    TEXT NOT NULL,
  sum_value REAL NOT NULL DEFAULT 0,
  n_obs     INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (source, domain)
);
CREATE TABLE IF NOT EXISTS stance_observation (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  source        TEXT NOT NULL,
  domain        TEXT NOT NULL,
  event_id      TEXT NOT NULL,
  dimension     TEXT NOT NULL,
  value         REAL NOT NULL,
  evidence_hash TEXT NOT NULL DEFAULT '',
  observed_at   TEXT NOT NULL,
  conflict      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_obs_source ON stance_observation(source, event_id, dimension);
"""


@dataclass(frozen=True)
class SourceProfile:
    source: str
    domain: str
    lean: float
    n_obs: int

    @property
    def ready(self) -> bool:
        return self.n_obs > 0


@dataclass(frozen=True)
class Observation:
    source: str
    event_id: str
    value: float
    conflict: bool
    n_obs: int
    lean: float


@dataclass(frozen=True)
class Prediction:
    source: str
    direction: int      # +1 / -1 / 0（中立）
    lean: float
    confidence: float
    uncertainty: float

    @property
    def label(self) -> str:
        return {1: "leans_positive", -1: "leans_negative", 0: "neutral"}[self.direction]


@dataclass(frozen=True)
class CalibrationResult:
    accuracy: float
    ece: float
    n: int


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


class StanceMemory:
    def __init__(self, path: str = ":memory:", *, prior_weight: float = DEFAULT_PRIOR_WEIGHT) -> None:
        self.conn = sqlite3.connect(path)
        self.conn.executescript(SCHEMA)
        self.prior_weight = prior_weight

    def close(self) -> None:
        self.conn.close()

    # ---------- L0: 观测 ----------
    def observe(
        self,
        source: str,
        *,
        event: str,
        dimension: str,
        value: float,
        evidence_hash: str = "",
        domain: str = DEFAULT_DOMAIN,
        observed_at: str | None = None,
    ) -> Observation:
        conflict = self._is_conflict(source, event, dimension, value, domain)
        self.conn.execute(
            "INSERT INTO stance_observation"
            "(source, domain, event_id, dimension, value, evidence_hash, observed_at, conflict) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (source, domain, event, dimension, float(value), evidence_hash,
             observed_at or _now(), int(conflict)),
        )
        self.conn.execute(
            "INSERT INTO source_profile(source, domain, sum_value, n_obs, updated_at) VALUES(?,?,?,1,?) "
            "ON CONFLICT(source, domain) DO UPDATE SET "
            "sum_value = sum_value + excluded.sum_value, n_obs = n_obs + 1, updated_at = excluded.updated_at",
            (source, domain, float(value), _now()),
        )
        self.conn.commit()
        profile = self.profile(source, domain)
        return Observation(source, event, float(value), conflict, profile.n_obs, profile.lean)

    def _is_conflict(self, source: str, event: str, dimension: str, value: float, domain: str) -> bool:
        rows = self.conn.execute(
            "SELECT value FROM stance_observation WHERE source=? AND domain=? AND event_id=? AND dimension=?",
            (source, domain, event, dimension),
        ).fetchall()
        new_sign = _sign(value)
        return any(new_sign != 0 and _sign(row[0]) == -new_sign for row in rows)

    # ---------- L1: 画像 ----------
    def profile(self, source: str, domain: str = DEFAULT_DOMAIN) -> SourceProfile:
        row = self.conn.execute(
            "SELECT sum_value, n_obs FROM source_profile WHERE source=? AND domain=?", (source, domain)
        ).fetchone()
        if row is None:
            return SourceProfile(source, domain, 0.0, 0)
        total, n_obs = row
        lean = total / (n_obs + self.prior_weight)
        return SourceProfile(source, domain, lean, n_obs)

    def confidence(self, n_obs: int) -> float:
        return n_obs / (n_obs + self.prior_weight)

    # ---------- L2: 预测 ----------
    def predict(self, source: str, domain: str = DEFAULT_DOMAIN) -> Prediction:
        profile = self.profile(source, domain)
        direction = 0 if abs(profile.lean) < NEUTRAL_EPS else _sign(profile.lean)
        return Prediction(
            source=source,
            direction=direction,
            lean=profile.lean,
            confidence=self.confidence(profile.n_obs),
            uncertainty=1.0 / math.sqrt(profile.n_obs + self.prior_weight),
        )

    # ---------- 审计 ----------
    def observation_count(self, source: str) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) FROM stance_observation WHERE source=?", (source,)
        ).fetchone()
        return int(row[0])

    def conflicts(self) -> list[tuple]:
        return self.conn.execute(
            "SELECT source, event_id, dimension, observed_at FROM stance_observation "
            "WHERE conflict=1 ORDER BY id"
        ).fetchall()


def exploration_sample(
    sources: Sequence[str],
    memory: StanceMemory,
    *,
    ratio: float = 0.15,
    rng: random.Random | None = None,
) -> list[str]:
    """防回声室：每轮强制抽取最不确定的来源，避免系统只看自己熟悉的那批。"""
    if not sources:
        return []
    quota = max(1, math.ceil(ratio * len(sources)))
    ranked = sorted(sources, key=lambda s: (memory.profile(s).n_obs, s))
    picked = ranked[:quota]
    if rng is not None:
        rng.shuffle(picked)
    return picked


def calibration(pairs: Iterable[tuple[float, bool]], bins: int = 10) -> CalibrationResult:
    """pairs = [(置信度, 是否正确)]。返回准确率与期望校准误差（ECE）。"""
    data = [(float(conf), bool(ok)) for conf, ok in pairs]
    n = len(data)
    if n == 0:
        return CalibrationResult(0.0, 0.0, 0)
    accuracy = sum(1 for _, ok in data if ok) / n

    buckets: list[list[tuple[float, bool]]] = [[] for _ in range(bins)]
    for conf, ok in data:
        idx = min(int(conf * bins), bins - 1)
        buckets[idx].append((conf, ok))

    ece = 0.0
    for bucket in buckets:
        if not bucket:
            continue
        bucket_acc = sum(1 for _, ok in bucket if ok) / len(bucket)
        bucket_conf = sum(conf for conf, _ in bucket) / len(bucket)
        ece += (len(bucket) / n) * abs(bucket_acc - bucket_conf)
    return CalibrationResult(accuracy, ece, n)


def decide_rollback(accuracy: float, *, baseline: float, margin: float = ROLLBACK_MARGIN) -> bool:
    """准确率跌破基线即回滚为「只展示差异、不下倾向判断」，不允许带病上线。"""
    return accuracy < baseline - margin
