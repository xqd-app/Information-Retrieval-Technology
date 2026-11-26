"""启动期代码同步的契约：非 git 目录跳过、失败不阻塞、开关生效。"""

import importlib
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))


def load_app():
    """重新导入 app 模块并把 ROOT 指向给定目录后的版本。"""
    if "app" in sys.modules:
        del sys.modules["app"]
    import app  # noqa: PLC0415

    return importlib.reload(app)


class SyncCodeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.module = load_app()
        self.original_root = self.module.ROOT
        self.module.ROOT = Path(self.tmp.name)
        os.environ.pop("PIP_AUTO_UPDATE", None)

    def tearDown(self):
        self.module.ROOT = self.original_root
        self.tmp.cleanup()
        os.environ.pop("PIP_AUTO_UPDATE", None)

    def run_sync(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.module.sync_code()
        return buf.getvalue()

    def test_skips_when_not_a_git_repo(self):
        """上传部署（没有 .git）必须直接跳过，不能报错。"""
        output = self.run_sync()
        self.assertIn("非 git 目录", output)

    def test_switch_off(self):
        os.environ["PIP_AUTO_UPDATE"] = "0"
        output = self.run_sync()
        self.assertIn("PIP_AUTO_UPDATE=0", output)

    def test_never_raises_without_git(self):
        (Path(self.tmp.name) / ".git").mkdir()
        try:
            self.run_sync()  # 目录不是真仓库，git 会报错，但函数不能抛
        except Exception as exc:  # noqa: BLE001
            self.fail(f"sync_code 不应抛异常：{exc}")

    def test_generated_files_are_declared(self):
        for rel in ("pip_app/data/globe.json", "pip_app/web/index.html"):
            self.assertIn(rel, self.module.GENERATED_TRACKED)


class EnsureCodeTest(unittest.TestCase):
    def test_skips_when_code_present(self):
        module = load_app()
        module.ROOT = ROOT  # 本仓库，pip_app/server.py 存在
        buf = io.StringIO()
        with redirect_stdout(buf):
            module.ensure_code()
        self.assertNotIn("代码缺失", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
