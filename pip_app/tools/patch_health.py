"""一次性补丁：健康报告区分「网络层失败」与「源失败」。"""

import io
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ---------- health_report.py ----------
hp = ROOT / "health_report.py"
text = hp.read_text(encoding="utf-8")

repl = [
    (
        "    avg_ms: int\n    last_error: str\n    retired: bool = False",
        "    avg_ms: int\n    last_error: str\n    unreachable: int = 0\n    retired: bool = False",
    ),
    (
        '    @property\n    def success_rate(self) -> float:\n        return self.ok / self.runs if self.runs else 0.0',
        "    @property\n    def reachable_runs(self) -> int:\n        return max(self.runs - self.unreachable, 0)\n\n"
        "    @property\n    def success_rate(self) -> float:\n"
        "        return self.ok / self.reachable_runs if self.reachable_runs else 0.0",
    ),
    (
        '        if self.runs == 0:\n            return IDLE',
        '        if self.runs == 0 or self.reachable_runs == 0:\n            return IDLE',
    ),
    (
        '        failed = sum(1 for r in group if r["status"] in {"failed", "timeout"})',
        '        failed = sum(1 for r in group if r["status"] in {"failed", "timeout"})\n'
        '        unreachable = sum(1 for r in group if r["status"] == "unreachable")',
    ),
    (
        "                failed=failed,\n                avg_ms=",
        "                failed=failed,\n                unreachable=unreachable,\n                avg_ms=",
    ),
    (
        '        f"{row.avg_ms:>7}ms  {row.last_error[:40]}"',
        '        f"{row.avg_ms:>7}ms{row.unreachable:>6}  {row.last_error[:40]}"',
    ),
    (
        '    lines.append(f"{\'状态\':<8}{\'源\':<26}{\'域\':<8}{\'成功率\':>7}{\'ok/zero/fail\':>15}{\'均耗时\':>8}  最近错误")',
        '    lines.append(\n'
        '        f"{\'状态\':<8}{\'源\':<26}{\'域\':<8}{\'成功率\':>7}{\'ok/zero/fail\':>15}"\n'
        '        f"{\'均耗时\':>8}{\'离线\':>6}  最近错误"\n'
        '    )',
    ),
]

for old, new in repl:
    if old not in text:
        raise SystemExit(f"health_report: 未找到片段 -> {old[:50]!r}")
    text = text.replace(old, new)
hp.write_text(text, encoding="utf-8")

# ---------- cli.py ----------
cp = ROOT / "cli.py"
ctext = cp.read_text(encoding="utf-8")
old_mark = '        mark = "OK  " if run.status == "ok" else run.status.upper()[:4].ljust(4)'
new_mark = (
    '        labels = {"ok": "OK  ", "failed": "FAIL", "timeout": "TIME",\n'
    '                  "zero_result": "ZERO", "unreachable": "NET "}\n'
    '        mark = labels.get(run.status, run.status.upper()[:4].ljust(4))'
)
if old_mark not in ctext:
    raise SystemExit("cli.py: 未找到 mark 行")
cp.write_text(ctext.replace(old_mark, new_mark), encoding="utf-8")

print("patched health_report.py + cli.py")
