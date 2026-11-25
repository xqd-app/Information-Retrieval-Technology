"""命令行入口：python -m pip_app.cli collect|health|tail。"""

from __future__ import annotations

import argparse
import json
import sys

from . import config
from .collect import collect, load_sources, write_outputs
from .health_report import load_rows, render, summarize


def cmd_collect(args: argparse.Namespace) -> int:
    sources = load_sources()
    if args.domain != "all":
        sources = [s for s in sources if s.domain == args.domain]
    if not sources:
        print(f"没有匹配 domain={args.domain} 的源", file=sys.stderr)
        return 2

    outcome = collect(sources)
    paths = write_outputs(outcome)
    print(f"运行时间 {outcome.run_at}  状态 {outcome.status}")
    print(f"源 {len(outcome.sources)}  抓取条数 {sum(r.fetched for r in outcome.sources)}  "
          f"去重后 {len(outcome.items)}（合并掉 {outcome.duplicates_removed}）")
    print(f"写入 {paths['items']}")
    for run in outcome.sources:
        labels = {"ok": "OK  ", "failed": "FAIL", "timeout": "TIME",
                  "zero_result": "ZERO", "unreachable": "NET "}
        mark = labels.get(run.status, run.status.upper()[:4].ljust(4))
        print(f"  {mark} {run.source.id:<18} {run.fetched:>3} 条 {run.duration_ms:>6}ms {run.error[:50]}")
    return 0 if outcome.status == "ok" else 1


def cmd_health(args: argparse.Namespace) -> int:
    active_ids = {s.id for s in load_sources()}
    report = render(summarize(load_rows(days=args.days), active_ids=active_ids))
    print(report)
    return 0


def cmd_tail(args: argparse.Namespace) -> int:
    items_dir = config.ITEMS_DIR
    files = sorted(items_dir.glob("*.jsonl"))
    if not files:
        print("还没有采集结果")
        return 1
    rows = [json.loads(line) for line in files[-1].read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows[: args.n]:
        print(f"[{row['time_confidence']:<6}] {row['source_id']:<16} {row['published_at']}  {row['title'][:70]}")
    print(f"\n共 {len(rows)} 条，来自 {files[-1].name}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pip_app", description="PIP W1 采集链路")
    sub = parser.add_subparsers(dest="command", required=True)

    p_collect = sub.add_parser("collect", help="抓取全部/指定域的源")
    p_collect.add_argument("--domain", default="all", choices=["all", "ai", "geopol"])
    p_collect.set_defaults(func=cmd_collect)

    p_health = sub.add_parser("health", help="输出源健康报告")
    p_health.add_argument("--days", type=int, default=config.HEALTH_WINDOW_DAYS)
    p_health.set_defaults(func=cmd_health)

    p_tail = sub.add_parser("tail", help="查看最近一次采集的前 N 条")
    p_tail.add_argument("-n", type=int, default=15)
    p_tail.set_defaults(func=cmd_tail)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
