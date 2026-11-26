"""把提示文案改成「使用默认密码」。"""

from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "auth.py"
text = PATH.read_text(encoding="utf-8")

OLD = '''        return f"[auth] 已生成初始密码：{_PASSWORD}（可改环境变量 PIP_PASSWORD 覆盖）"'''

NEW = '''        return (
            f"[auth] 默认密码：{_PASSWORD}  用户名：{USERNAME}\\n"
            f"[auth] 生产环境请设置环境变量 PIP_PASSWORD 覆盖它"
        )'''

assert OLD in text, "提示文案未找到"
text = text.replace(OLD, NEW, 1)
PATH.write_text(text, encoding="utf-8")
print("patched notice")
