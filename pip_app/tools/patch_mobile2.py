"""移动端修复 v2：解决 flex/grid 的 min-width:auto 导致的横向溢出。"""

from pathlib import Path

PATH = Path(__file__).resolve().parent / "build_web.py"
text = PATH.read_text(encoding="utf-8")

# ---------- 1) 平板断点：解除 grid/flex 的固有宽度 ----------
old_tablet = """@media (max-width:1080px){
  .hero{grid-template-columns:1fr;min-height:auto;padding:64px 16px 90px;gap:16px}"""
new_tablet = """@media (max-width:1080px){
  .hero{grid-template-columns:1fr;min-height:auto;padding:64px 16px 90px;gap:16px;
    width:100%;max-width:100%;min-width:0}
  .panel,.globe-stage,.tabs{min-width:0;max-width:100%}
  .globe-stage canvas{min-width:0;width:100%!important;max-width:100%!important}"""
assert old_tablet in text, "平板断点未找到"
text = text.replace(old_tablet, new_tablet, 1)

# ---------- 2) 手机断点：再加一层兜底 ----------
old_first = """@media (max-width:760px){
  .hero{padding:16px 12px 96px;gap:8px}"""
new_first = """@media (max-width:760px){
  /* 兜底：任何子项都不许按内容固有宽度撑开容器 */
  html,body{max-width:100vw;overflow-x:hidden}
  .hero,.panel,.panel-inner,.panel-list,.list,.filters,.stats,.nav,.actions,
  .list-head,.meta,.dist-grid,.wgrid,.hgrid,.globe-stage{min-width:0;max-width:100%}
  .hero > *, .stats > *, .filters > *, .nav > *, .actions > *{min-width:0}
  .hero{padding:16px 12px 96px;gap:8px}"""
assert old_first in text, "手机断点首行未找到"
text = text.replace(old_first, new_first, 1)

# ---------- 3) 底部 tabs 在手机上不能太宽 ----------
text = text.replace(
    "  .tabs{position:fixed;left:10px;right:10px;bottom:10px;justify-content:space-between;",
    "  .tabs{position:fixed;left:10px;right:10px;bottom:10px;max-width:calc(100vw - 20px);\n    justify-content:space-between;",
    1,
)

PATH.write_text(text, encoding="utf-8")
print("patched mobile fix v2")
