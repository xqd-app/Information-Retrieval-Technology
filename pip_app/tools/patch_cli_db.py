"""给 CLI 加数据库子命令，并让 collect 结束后自动入库。"""

from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "cli.py"
text = PATH.read_text(encoding="utf-8")

# ---------- 1) 新命令实现 ----------
anchor = "def build_parser() -> argparse.ArgumentParser:"
assert anchor in text
NEW_CMDS = '''def cmd_db(args: argparse.Namespace) -> int:
    """db init | db sync | db stats"""
    from . import db as database
    from . import ingest as ingest_mod
    from . import repo

    action = getattr(args, "db_action", "sync")
    if action == "init":
        conn = database.init()
        print(f"数据库已初始化：{database.DEFAULT_DB}  version={database.version(conn)}")
        conn.close()
        return 0

    if action == "sync":
        result = ingest_mod.sync(days=args.days)
        runs = ingest_mod.sync_health()
        print(json.dumps({**result, "runs_imported": runs}, ensure_ascii=False, indent=2))
        return 0

    if action == "stats":
        with database.session() as conn:
            data = repo.stats(conn)
            sources = repo.sources_with_counts(conn)
        print(f"条目 {data['total']} · 源 {data['sources']} · 域 {data['domains']}")
        print(f"语言 {data['languages']}")
        print(f"可信度 {data['confidence']}")
        print(f"时间范围 {data['oldest']} → {data['newest']}")
        print(f"最活跃源：{sources[0]['name']}（{sources[0]['items']} 条）" if sources else "无源")
        return 0

    print(f"未知动作 {action}")
    return 1


def cmd_search(args: argparse.Namespace) -> int:
    """命令行全文检索（走 FTS5）。"""
    from . import db as database
    from . import repo

    with database.session() as conn:
        out = repo.query_items(conn, q=args.q, size=args.n, page=1)
    for item in out["items"]:
        print(f"[{item['time_confidence'] or '?'}] {item['source_name'] or item['source_id']:<16} "
              f"{(item['published_at'] or '')[:16]}  {item['title'][:70]}")
    print(f"\\n匹配 {out['total']} 条，显示 {len(out['items'])} 条")
    return 0


'''
text = text.replace(anchor, NEW_CMDS + anchor, 1)

# ---------- 2) collect 后自动入库 ----------
old_collect_tail = '    return 0 if outcome.status == "ok" else 1'
new_collect_tail = '''    # 采集完成后自动入库（幂等；库不可用不影响采集结果）
    try:
        from . import ingest as ingest_mod

        result = ingest_mod.sync(days=1)
        ingest_mod.sync_health()
        print(f"入库：新增 {result['inserted']} · 更新 {result['updated']} · 库内共 {result['total']} 条")
    except Exception as exc:  # noqa: BLE001
        print(f"入库失败（采集结果仍在 JSONL 中）：{exc}")

    return 0 if outcome.status == "ok" else 1'''
assert old_collect_tail in text
text = text.replace(old_collect_tail, new_collect_tail, 1)

# ---------- 3) 注册子命令 ----------
old_reg = '    p_tail.set_defaults(func=cmd_tail)\n    return parser'
new_reg = '''    p_tail.set_defaults(func=cmd_tail)

    p_db = sub.add_parser("db", help="数据库：init / sync / stats")
    p_db.add_argument("db_action", nargs="?", default="sync", choices=["init", "sync", "stats"])
    p_db.add_argument("--days", type=int, default=7)
    p_db.set_defaults(func=cmd_db)

    p_search = sub.add_parser("search", help="全文检索（FTS5）")
    p_search.add_argument("q")
    p_search.add_argument("-n", type=int, default=10)
    p_search.set_defaults(func=cmd_search)

    return parser'''
assert old_reg in text
text = text.replace(old_reg, new_reg, 1)

PATH.write_text(text, encoding="utf-8")
print("patched cli with db commands")
