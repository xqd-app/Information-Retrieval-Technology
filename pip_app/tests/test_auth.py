"""认证层契约：密码校验、会话生命周期、暴力破解限速、cookie 属性。"""

import importlib
import os
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))


class AuthModuleTest(unittest.TestCase):
    """用固定密码导入一次，避免读到随机生成的初始密码。"""

    @classmethod
    def setUpClass(cls):
        os.environ["PIP_USER"] = "admin"
        os.environ["PIP_PASSWORD"] = "test-secret-123"
        import pip_app.auth as auth

        cls.auth = importlib.reload(auth)

    def test_correct_credentials(self):
        self.assertTrue(self.auth.verify("admin", "test-secret-123"))

    def test_username_is_case_insensitive(self):
        self.assertTrue(self.auth.verify("ADMIN", "test-secret-123"))

    def test_wrong_password(self):
        self.assertFalse(self.auth.verify("admin", "wrong"))

    def test_wrong_user(self):
        self.assertFalse(self.auth.verify("root", "test-secret-123"))

    def test_empty_inputs_rejected(self):
        self.assertFalse(self.auth.verify("", ""))
        self.assertFalse(self.auth.verify("admin", ""))
        self.assertFalse(self.auth.verify("", "test-secret-123"))

    def test_whitespace_trimmed_on_username(self):
        self.assertTrue(self.auth.verify("  admin  ", "test-secret-123"))

    def test_password_is_not_stored_in_plaintext(self):
        """模块里不应出现明文密码变量。"""
        self.assertFalse(hasattr(self.auth, "_PASSWORD_PLAIN"))
        self.assertTrue(hasattr(self.auth, "_PASSWORD_HASH"))


class SessionTest(unittest.TestCase):
    def setUp(self):
        from pip_app.auth import SessionStore

        self.store = SessionStore(ttl=60)

    def test_create_and_validate(self):
        token = self.store.create("admin")
        self.assertTrue(self.store.valid(token))
        self.assertGreater(len(token), 20)

    def test_invalid_token(self):
        self.assertFalse(self.store.valid("nope"))
        self.assertFalse(self.store.valid(None))
        self.assertFalse(self.store.valid(""))

    def test_tokens_are_unique(self):
        a = self.store.create("admin")
        b = self.store.create("admin")
        self.assertNotEqual(a, b)

    def test_expiry(self):
        from pip_app.auth import SessionStore

        store = SessionStore(ttl=0)
        token = store.create("admin")
        time.sleep(0.01)
        self.assertFalse(store.valid(token))

    def test_revoke(self):
        token = self.store.create("admin")
        self.store.revoke(token)
        self.assertFalse(self.store.valid(token))

    def test_cleanup_removes_expired(self):
        from pip_app.auth import SessionStore

        store = SessionStore(ttl=0)
        store.create("a")
        store.create("b")
        time.sleep(0.01)
        self.assertEqual(store.cleanup(), 2)
        self.assertEqual(store.cleanup(), 0)


class LockoutTest(unittest.TestCase):
    def setUp(self):
        from pip_app.auth import AttemptTracker

        self.tracker = AttemptTracker(max_failures=3, lock_seconds=60)

    def test_not_locked_initially(self):
        self.assertEqual(self.tracker.locked("1.2.3.4"), 0.0)

    def test_lock_after_threshold(self):
        for _ in range(3):
            self.tracker.fail("1.2.3.4")
        self.assertGreater(self.tracker.locked("1.2.3.4"), 0)

    def test_success_clears(self):
        for _ in range(3):
            self.tracker.fail("1.2.3.4")
        self.tracker.success("1.2.3.4")
        self.assertEqual(self.tracker.locked("1.2.3.4"), 0.0)

    def test_lock_expires(self):
        from pip_app.auth import AttemptTracker

        tracker = AttemptTracker(max_failures=1, lock_seconds=0)
        tracker.fail("9.9.9.9")
        time.sleep(0.01)
        self.assertEqual(tracker.locked("9.9.9.9"), 0.0)

    def test_other_ip_not_affected(self):
        for _ in range(3):
            self.tracker.fail("1.1.1.1")
        self.assertEqual(self.tracker.locked("2.2.2.2"), 0.0)


class CookieTest(unittest.TestCase):
    def test_cookie_attributes(self):
        from pip_app.auth import cookie_header

        header = cookie_header("tok123")
        self.assertIn("pip_session=tok123", header)
        self.assertIn("HttpOnly", header)
        self.assertIn("SameSite=Lax", header)
        self.assertIn("Path=/", header)

    def test_clear_cookie(self):
        from pip_app.auth import clear_cookie_header

        header = clear_cookie_header()
        self.assertIn("Max-Age=0", header)


class DefaultPasswordTest(unittest.TestCase):
    """没配 PIP_PASSWORD 时用固定默认密码，而不是随机值。"""

    def setUp(self):
        os.environ.pop("PIP_PASSWORD", None)
        os.environ["PIP_USER"] = "admin"
        import pip_app.auth as auth

        self.auth = importlib.reload(auth)

    def tearDown(self):
        os.environ["PIP_PASSWORD"] = "test-secret-123"
        importlib.reload(self.auth)

    def test_default_password_is_fixed(self):
        self.assertEqual(self.auth.DEFAULT_PASSWORD, "pip2026")

    def test_default_password_works(self):
        self.assertTrue(self.auth.verify("admin", "pip2026"))

    def test_notice_mentions_default(self):
        notice = self.auth.generated_password_notice()
        self.assertIn("pip2026", notice)
        self.assertIn("PIP_PASSWORD", notice)

    def test_env_overrides_default(self):
        os.environ["PIP_PASSWORD"] = "my-own-pass"
        reloaded = importlib.reload(self.auth)
        self.assertTrue(reloaded.verify("admin", "my-own-pass"))
        self.assertFalse(reloaded.verify("admin", "pip2026"))
        self.assertEqual(reloaded.generated_password_notice(), "")


if __name__ == "__main__":
    unittest.main()
