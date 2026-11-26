"""移动端适配：canvas 响应式尺寸 + 手机布局重排。"""

from pathlib import Path

PATH = Path(__file__).resolve().parent / "build_web.py"
text = PATH.read_text(encoding="utf-8")

# ---------- 1) canvas 尺寸改为跟随容器 ----------
old = """  const ctx = cv.getContext("2d");
  const SIZE = 880, dpr = Math.min(window.devicePixelRatio || 1, 2);
  cv.width = SIZE * dpr; cv.height = SIZE * dpr;
  cv.style.width = SIZE + "px"; cv.style.height = SIZE + "px";
  ctx.scale(dpr, dpr);"""
new = """  const ctx = cv.getContext("2d");
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  // 尺寸跟随容器：手机上不再被 880px 撑破布局
  const stage = cv.parentElement;
  const availW = stage ? Math.max(260, stage.clientWidth || window.innerWidth || 880) : 880;
  const SIZE = Math.min(880, Math.round(availW));
  cv.width = SIZE * dpr; cv.height = SIZE * dpr;
  cv.style.width = "100%"; cv.style.maxWidth = SIZE + "px"; cv.style.height = "auto";
  ctx.scale(dpr, dpr);"""
assert old in text, "canvas 尺寸段未找到"
text = text.replace(old, new, 1)

# ---------- 2) 字号随尺寸缩放 ----------
text = text.replace(
    'ctx.font = "11.5px \'Orbitron\', ui-monospace, monospace";',
    'ctx.font = FS + "px \'Orbitron\', ui-monospace, monospace";',
)
text = text.replace(
    'ctx.font = "11px \'Orbitron\', ui-monospace, monospace";',
    'ctx.font = (FS - 0.5) + "px \'Orbitron\', ui-monospace, monospace";',
)
anchor = "  let lat0 = 24, lon0 = -55"
assert anchor in text
text = text.replace(
    anchor,
    "  const FS = SIZE < 520 ? 9 : 11.5;   // 小屏缩字号，避免标签糊在一起\n" + anchor,
    1,
)

# ---------- 3) 窗口变化时重建 ----------
old_init = "const rows = DATA.items || [];"
new_init = """/* 窗口尺寸变化（含手机旋转）时重建地球，debounce 避免抖动 */
let __pipResizeTimer = null;
window.addEventListener("resize", () => {
  clearTimeout(__pipResizeTimer);
  __pipResizeTimer = setTimeout(() => renderGlobe(), 280);
});

const rows = DATA.items || [];"""
assert old_init in text
text = text.replace(old_init, new_init, 1)

# ---------- 4) 手机断点重排 ----------
old_mobile = """@media (max-width:760px){
  .brand h1{font-size:26px;letter-spacing:2px}
  .brand,.sub{padding-left:0}
  .hacker-out{display:none}
  .stats{grid-template-columns:repeat(2,1fr)}
  .stat b{font-size:26px}
  .globe-stage{min-height:300px}
}"""
new_mobile = """@media (max-width:760px){
  .hero{padding:16px 12px 96px;gap:8px}
  .panel-inner{padding:16px 14px 16px}
  .brand{padding-left:0;min-height:0;margin-bottom:6px}
  .brand h1{font-size:24px;letter-spacing:1px}
  .sub{padding-left:0;font-size:9px;letter-spacing:1.4px;margin-bottom:12px}
  .hacker-out{display:none}
  .nav{gap:2px 10px;padding-bottom:10px;margin-bottom:12px}
  .nav a{font-size:12.5px;padding:4px 6px;gap:5px}
  .nav a svg{width:13px;height:13px}
  .lede{font-size:13.5px;line-height:1.65;margin-bottom:14px;padding-left:10px}
  .stats{grid-template-columns:repeat(2,1fr);gap:8px;margin-bottom:14px}
  .stat{padding:9px 8px 8px}
  .stat .ico{font-size:8px;letter-spacing:.8px}
  .stat b{font-size:24px}
  .stat span{font-size:9px;letter-spacing:1.2px}
  .actions{gap:12px}
  .btn{padding:9px 18px 9px 14px;font-size:13px;letter-spacing:1px}
  .updated{font-size:9.5px;letter-spacing:.6px;margin-top:12px;padding-top:10px}
  .globe-stage{min-height:auto;padding:6px 0 0}
  .globe-stage canvas{width:100%!important;max-width:100%!important}
  .globe-legend{position:static;text-align:left;margin:4px 0 0;font-size:8.5px}
  .globe-caption{position:static;transform:none;margin:8px auto 0;font-size:9px;padding:5px 12px;gap:8px}
  .tabs{position:fixed;left:10px;right:10px;bottom:10px;justify-content:space-between;
    background:rgba(4,16,28,.96);box-shadow:0 6px 24px rgba(0,0,0,.7)}
  .tab{flex:1;padding:9px 0;font-size:12px;letter-spacing:.6px}
  .panel-list{padding:0 12px 104px}
  .list-head h2{font-size:18px;letter-spacing:1.4px}
  .list-head span{font-size:9px;letter-spacing:.6px}
  .filters{gap:6px;padding:10px 0}
  .fchip{font-size:11px;padding:4px 9px}
  .filters input{min-width:0;width:100%;order:9}
  .filters select{max-width:none!important;flex:1}
  .item{padding:11px 12px}
  .item h3{font-size:15px;line-height:1.4}
  .meta{font-size:9px;gap:6px;margin:6px 0}
  .tag{font-size:8.5px;padding:1px 5px}
  .src{font-size:10.5px}
  .sum{font-size:12px;line-height:1.55}
  .dist-grid,.wgrid{grid-template-columns:1fr}
  .wcover{gap:16px}
  .wring{width:80px;height:80px}
  .wring span{font-size:20px}
  .wstats{grid-template-columns:repeat(2,1fr);gap:6px 14px}
  .hgrid{grid-template-columns:1fr}
  .bars{height:140px;gap:6px}
  .bar .cc{font-size:7.5px;letter-spacing:0}
  .hud-system{display:none}
  .foot{font-size:8.5px;letter-spacing:1px;padding:8px 12px 90px}
}"""
assert old_mobile in text, "手机断点未找到"
text = text.replace(old_mobile, new_mobile, 1)

# ---------- 5) 平板断点也修一下 ----------
old_tablet = """  .tabs{position:static;margin-top:6px}"""
new_tablet = """  .tabs{position:static;margin-top:10px;align-self:flex-start}"""
if old_tablet in text:
    text = text.replace(old_tablet, new_tablet, 1)

PATH.write_text(text, encoding="utf-8")
print("patched mobile responsive")
