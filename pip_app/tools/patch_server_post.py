"""补 do_POST：登录需要 POST，之前只有 GET/HEAD。"""

from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "server.py"
text = PATH.read_text(encoding="utf-8")

old = '''    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_GET(self) -> None:  # noqa: N802
        started = time.perf_counter()
        status = 500
        try:
            status = self._route()
        except Exception as exc:  # noqa: BLE001
            LOG.exception("request failed: %s", exc)
            METRICS.inc("errors_total")
            try:
                self._error(500, "internal error")
            except OSError:
                pass
            status = 500
        finally:
            elapsed = time.perf_counter() - started
            METRICS.inc("requests_total")
            METRICS.observe(elapsed)
            LOG.info(json.dumps({
                "method": self.command, "path": self.path.split("?")[0],
                "status": status, "ms": round(elapsed * 1000, 1),
            }, ensure_ascii=False))'''

new = '''    def do_HEAD(self) -> None:  # noqa: N802
        self._dispatch()

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch()

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch()

    def _dispatch(self) -> None:
        started = time.perf_counter()
        status = 500
        try:
            status = self._route()
        except Exception as exc:  # noqa: BLE001
            LOG.exception("request failed: %s", exc)
            METRICS.inc("errors_total")
            try:
                self._error(500, "internal error")
            except OSError:
                pass
            status = 500
        finally:
            elapsed = time.perf_counter() - started
            METRICS.inc("requests_total")
            METRICS.observe(elapsed)
            LOG.info(json.dumps({
                "method": self.command, "path": self.path.split("?")[0],
                "status": status, "ms": round(elapsed * 1000, 1),
            }, ensure_ascii=False))'''

assert old in text, "do_GET 段未找到"
text = text.replace(old, new, 1)
PATH.write_text(text, encoding="utf-8")
print("patched do_POST")
