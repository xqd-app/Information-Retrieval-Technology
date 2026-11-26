"""测试适配鉴权：注入固定密码、登录拿 cookie、新增鉴权用例。"""

import re
from pathlib import Path

TESTS = Path(__file__).resolve().parent.parent / "tests"


def patch_test_server() -> None:
    path = TESTS / "test_server.py"
    text = path.read_text(encoding="utf-8")

    # 1) 固定密码（必须在 import server 之前）
    old_import = "from pip_app.server import Metrics, make_server  # noqa: E402"
    new_import = (
        'os.environ["PIP_USER"] = "admin"\n'
        'os.environ["PIP_PASSWORD"] = "test-secret-123"\n'
        "from pip_app.server import Metrics, make_server  # noqa: E402"
    )
    assert old_import in text
    text = text.replace(old_import, new_import, 1)
    if "import os" not in text:
        text = text.replace("import json", "import json\nimport os", 1)

    # 2) 登录并给所有请求带上 cookie
    old_setup = '''    @classmethod
    def setUpClass(cls):
        cls.server, cls.port = make_server(host="127.0.0.1", port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.port}"'''
    new_setup = '''    @classmethod
    def setUpClass(cls):
        cls.server, cls.port = make_server(host="127.0.0.1", port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.cookie = cls.login()

    @classmethod
    def login(cls, username="admin", password="test-secret-123"):
        payload = json.dumps({"username": username, "password": password}).encode()
        req = urllib.request.Request(
            cls.base + "/api/login", data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.headers.get("Set-Cookie") or ""
            return raw.split(";")[0]'''
    assert old_setup in text
    text = text.replace(old_setup, new_setup, 1)

    old_get = '''    def get(self, path, **headers):
        req = urllib.request.Request(self.base + path, headers=headers)'''
    new_get = '''    def get(self, path, **headers):
        headers.setdefault("Cookie", self.cookie)
        req = urllib.request.Request(self.base + path, headers=headers)'''
    assert old_get in text
    text = text.replace(old_get, new_get, 1)

    # 3) 追加鉴权用例
    anchor = "class MetricsTest(unittest.TestCase):"
    assert anchor in text
    AUTH_TESTS = '''class AuthTest(ServerCase):
    """未登录必须被挡住；登录后才能拿到数据。"""

    def post_login(self, username, password):
        payload = json.dumps({"username": username, "password": password}).encode()
        req = urllib.request.Request(
            self.base + "/api/login", data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers), exc.read()

    def test_login_page_is_public(self):
        status, headers, body = self.get("/login")
        self.assertEqual(status, 200)
        self.assertIn("PIP", body.decode("utf-8"))

    def test_root_redirects_when_anonymous(self):
        req = urllib.request.Request(self.base + "/")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(ctx.exception.code, 302)
        self.assertEqual(ctx.exception.headers["Location"], "/login")

    def test_api_returns_401_when_anonymous(self):
        req = urllib.request.Request(self.base + "/api/v1/items")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(ctx.exception.code, 401)

    def test_login_success_sets_cookie(self):
        status, headers, body = self.post_login("admin", "test-secret-123")
        self.assertEqual(status, 200)
        self.assertIn("pip_session=", headers.get("Set-Cookie", ""))
        self.assertTrue(json.loads(body)["ok"])

    def test_login_wrong_password(self):
        status, _, body = self.post_login("admin", "nope")
        self.assertEqual(status, 401)
        self.assertFalse(json.loads(body)["ok"])

    def test_logout_redirects_and_clears(self):
        req = urllib.request.Request(self.base + "/logout", headers={"Cookie": self.cookie})
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(ctx.exception.code, 302)
        self.assertIn("Max-Age=0", ctx.exception.headers.get("Set-Cookie", ""))

    def test_healthz_stays_public(self):
        req = urllib.request.Request(self.base + "/healthz")
        with urllib.request.urlopen(req, timeout=10) as resp:
            self.assertEqual(resp.status, 200)

    def test_forged_cookie_rejected(self):
        req = urllib.request.Request(self.base + "/api/v1/items",
                                     headers={"Cookie": "pip_session=forged-token"})
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(ctx.exception.code, 401)


class MetricsTest(unittest.TestCase):'''
    text = text.replace(anchor, AUTH_TESTS, 1)
    path.write_text(text, encoding="utf-8")
    print("patched test_server")


def patch_test_api_v1() -> None:
    path = TESTS / "test_api_v1.py"
    text = path.read_text(encoding="utf-8")

    old = "from pip_app.server import make_server  # noqa: E402"
    new = (
        'os.environ["PIP_USER"] = "admin"\n'
        'os.environ["PIP_PASSWORD"] = "test-secret-123"\n'
        "from pip_app.server import make_server  # noqa: E402"
    )
    assert old in text
    text = text.replace(old, new, 1)
    if "import os" not in text:
        text = text.replace("import json", "import json\nimport os", 1)

    old_setup = '''        cls.base = f"http://127.0.0.1:{cls.port}"'''
    new_setup = '''        cls.base = f"http://127.0.0.1:{cls.port}"
        payload = json.dumps({"username": "admin", "password": "test-secret-123"}).encode()
        req = urllib.request.Request(
            cls.base + "/api/login", data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            cls.cookie = (resp.headers.get("Set-Cookie") or "").split(";")[0]'''
    assert old_setup in text
    text = text.replace(old_setup, new_setup, 1)

    old_get = '''    def get(self, path):
        try:
            with urllib.request.urlopen(self.base + path, timeout=10) as resp:'''
    new_get = '''    def get(self, path):
        req = urllib.request.Request(self.base + path, headers={"Cookie": self.cookie})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:'''
    assert old_get in text
    text = text.replace(old_get, new_get, 1)
    path.write_text(text, encoding="utf-8")
    print("patched test_api_v1")


if __name__ == "__main__":
    patch_test_server()
    patch_test_api_v1()
