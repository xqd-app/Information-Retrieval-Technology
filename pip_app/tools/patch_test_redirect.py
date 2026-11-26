"""测试里禁用重定向跟随，才能断言 302。"""

from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "tests" / "test_server.py"
text = PATH.read_text(encoding="utf-8")

# 1) 加不跟随重定向的 opener
anchor = "class ServerCase(unittest.TestCase):"
assert anchor in text
helper = '''class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


NO_REDIRECT = urllib.request.build_opener(_NoRedirect)


class ServerCase(unittest.TestCase):'''
text = text.replace(anchor, helper, 1)

# 2) root 重定向用例改用 NO_REDIRECT
old_root = '''        req = urllib.request.Request(self.base + "/")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(ctx.exception.code, 302)'''
new_root = '''        req = urllib.request.Request(self.base + "/")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            NO_REDIRECT.open(req, timeout=10)
        self.assertEqual(ctx.exception.code, 302)'''
assert old_root in text
text = text.replace(old_root, new_root, 1)

# 3) logout 用例同样
old_logout = '''        req = urllib.request.Request(self.base + "/logout", headers={"Cookie": self.cookie})
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(ctx.exception.code, 302)'''
new_logout = '''        req = urllib.request.Request(self.base + "/logout", headers={"Cookie": self.cookie})
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            NO_REDIRECT.open(req, timeout=10)
        self.assertEqual(ctx.exception.code, 302)'''
assert old_logout in text
text = text.replace(old_logout, new_logout, 1)

PATH.write_text(text, encoding="utf-8")
print("patched test redirect handling")
