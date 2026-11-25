"""删除误写的无效 CSS 行。"""

from pathlib import Path

PATH = Path(__file__).resolve().parent / "build_web.py"
text = PATH.read_text(encoding="utf-8")
before = text
text = text.replace("--paper:{display:none}\n", "")
text = text.replace("--paper:{display:none}", "")
PATH.write_text(text, encoding="utf-8")
print("removed" if text != before else "nothing to remove")
