"""把文件里所有字面量 \\n 还原成真实换行（PowerShell 写坏的多处）。"""

from pathlib import Path

PATH = Path(__file__).resolve().parent / "build_land_data.py"
text = PATH.read_text(encoding="utf-8")

count = text.count("\\n")
text = text.replace("\\n", "\n")
PATH.write_text(text, encoding="utf-8")
print(f"replaced {count} literal backslash-n")

import ast  # noqa: E402

ast.parse(text)
print("语法 OK")
