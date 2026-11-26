"""给 test_server 补一个 code 字段的用例。"""

from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "tests" / "test_server.py"
text = PATH.read_text(encoding="utf-8")

SNIPPET = '''    def test_healthz_reports_code_provenance(self):
        """healthz 要能回答「线上代码是不是 git 管的」。"""
        status, _, body = self.get("/healthz")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertIn("code", payload)
        self.assertIn("git", payload["code"])
        self.assertIn("files", payload["code"])
        self.assertIn("pip_app/web/login.html", payload["code"]["files"])

'''

if "test_healthz_reports_code_provenance" not in text:
    anchor = "    def test_root_serves_html(self):"
    assert anchor in text, "锚点未找到"
    text = text.replace(anchor, SNIPPET + anchor, 1)
    PATH.write_text(text, encoding="utf-8")
    print("已加用例")
else:
    print("用例已存在")
