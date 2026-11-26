"""给服务加上登录鉴权：/login 页面、POST /api/login、/logout、页面与 API 保护。

保护范围：
    /                 需要登录，未登录 302 到 /login
    /api/v1/*         需要登录，未登录 401
    /screens/*        需要登录
    /healthz /metrics /login /api/login  不鉴权（监控与登录本身）
"""

from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "server.py"
text = PATH.read_text(encoding="utf-8")

# ---------- 1) 导入 ----------
old = "from . import db as database"
new = "from . import auth\nfrom . import db as database"
assert old in text
text = text.replace(old, new, 1)

# ---------- 2) 会话辅助 ----------
anchor = "def db_path() -> Path:"
assert anchor in text
HELPERS = '''PUBLIC_PATHS = {"/login", "/api/login", "/healthz", "/metrics", "/favicon.ico"}


def session_token(handler) -> str | None:
    raw = handler.headers.get("Cookie") or ""
    for part in raw.split(";"):
        name, _, value = part.strip().partition("=")
        if name == "pip_session":
            return value or None
    return None


def is_authenticated(handler) -> bool:
    return auth.SESSIONS.valid(session_token(handler))


def client_key(handler) -> str:
    fwd = handler.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return handler.client_address[0] if handler.client_address else "unknown"


def db_path() -> Path:'''
text = text.replace(anchor, HELPERS, 1)

# ---------- 3) 路由：登录相关 + 鉴权闸门 ----------
old_route = '''        if path in ("/", "/index.html"):
            return self._serve_html()'''
new_route = '''        if path == "/login":
            return self._serve_login()
        if path == "/api/login":
            return self._handle_login()
        if path == "/logout":
            return self._handle_logout()

        if path not in PUBLIC_PATHS and not is_authenticated(self):
            if path.startswith("/api/"):
                self._json(401, {"ok": False, "message": "未登录或会话已过期"})
                return 401
            self.send_response(302)
            self.send_header("Location", "/login")
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return 302

        if path in ("/", "/index.html"):
            return self._serve_html()'''
assert old_route in text
text = text.replace(old_route, new_route, 1)

# ---------- 4) 处理函数 ----------
anchor2 = "    def _serve_html(self) -> int:"
assert anchor2 in text
HANDLERS = '''    def _serve_login(self) -> int:
        page = web_dir() / "login.html"
        if not page.exists():
            self._error(503, "login page missing")
            return 503
        self._send(200, page.read_bytes(), "text/html; charset=utf-8", cache="no-cache")
        return 200

    def _handle_login(self) -> int:
        if (self.command or "GET").upper() != "POST":
            self._error(405, "method not allowed")
            return 405

        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > 8192:
            self._json(400, {"ok": False, "message": "请求格式错误"})
            return 400
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8", "replace"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._json(400, {"ok": False, "message": "请求格式错误"})
            return 400

        key = client_key(self)
        locked = auth.ATTEMPTS.locked(key)
        if locked:
            self._json(429, {"ok": False, "message": f"尝试次数过多，请 {int(locked)} 秒后再试"})
            METRICS.inc("login_locked_total")
            return 429

        user = str(payload.get("username") or "")
        password = str(payload.get("password") or "")
        if auth.verify(user, password):
            auth.ATTEMPTS.success(key)
            token = auth.SESSIONS.create(user)
            body = json.dumps({"ok": True, "user": auth.username()}).encode()
            self._send(200, body, "application/json; charset=utf-8",
                       cache="no-store", extra={"Set-Cookie": auth.cookie_header(token)})
            METRICS.inc("login_success_total")
            LOG.info(json.dumps({"event": "login_ok", "user": auth.username(), "ip": key}, ensure_ascii=False))
            return 200

        count = auth.ATTEMPTS.fail(key)
        METRICS.inc("login_failed_total")
        LOG.warning(json.dumps({"event": "login_fail", "ip": key, "attempt": count}, ensure_ascii=False))
        message = "账号或密码错误"
        if count >= auth.MAX_FAILURES:
            message = f"尝试次数过多，请 {auth.LOCK_SECONDS // 60} 分钟后重试"
        self._json(401, {"ok": False, "message": message, "attempts": count})
        return 401

    def _handle_logout(self) -> int:
        token = session_token(self)
        auth.SESSIONS.revoke(token)
        if self.path.split("?")[0].startswith("/api/"):
            self._json(200, {"ok": True})
            return 200
        self.send_response(302)
        self.send_header("Location", "/login")
        self.send_header("Set-Cookie", auth.clear_cookie_header())
        self.send_header("Content-Length", "0")
        self.end_headers()
        return 302

    def _serve_html(self) -> int:'''
text = text.replace(anchor2, HANDLERS, 1)

# ---------- 5) 启动时打印初始密码提示 ----------
old_boot = '    LOG.info("PIP listening on http://%s:%s/ (metrics at /metrics)", args.host, port)'
new_boot = '''    notice = auth.generated_password_notice()
    if notice:
        LOG.warning(notice)

    LOG.info("PIP listening on http://%s:%s/ (metrics at /metrics)", args.host, port)'''
assert old_boot in text
text = text.replace(old_boot, new_boot, 1)

PATH.write_text(text, encoding="utf-8")
print("patched server with auth")
