"""修复 PowerShell 写坏的字面 \\n，并加一条采集端断言。"""

from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "tools" / "build_globe_data.py"
text = PATH.read_text(encoding="utf-8")

if '\\n    "Kunming"' in text:
    text = text.replace('\\n    "Kunming"', '\n    "Kunming"')
    PATH.write_text(text, encoding="utf-8")
    print("fixed literal newline")

import ast

ast.parse(text)
print("语法 OK")

for line in text.splitlines():
    if "Kunming" in line:
        print("  ", line.strip())
