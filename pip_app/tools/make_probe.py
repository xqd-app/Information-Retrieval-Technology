"""生成 probe.html：在页面里注入宽度测量脚本，结果写进 <title>。"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "pip_app" / "web" / "index.html"
OUT = ROOT / "probe.html"

PROBE = """<script>
window.addEventListener("load", function(){
  setTimeout(function(){
    function w(sel){ var el = document.querySelector(sel); return el ? Math.round(el.getBoundingClientRect().width) : -1; }
    document.title = [
      "vw:" + window.innerWidth,
      "body:" + w("body"),
      "hero:" + w(".hero"),
      "panel:" + w(".panel"),
      "inner:" + w(".panel-inner"),
      "stats:" + w(".stats"),
      "stat:" + w(".stat"),
      "nav:" + w(".nav"),
      "globe:" + w(".globe-stage"),
      "cv:" + w("#globe"),
      "legend:" + w(".globe-legend"),
      "cap:" + w(".globe-caption"),
      "lede:" + w(".lede"),
      "actions:" + w(".actions")
    ].join(" | ");
  }, 1400);
});
</script>"""

html = SRC.read_text(encoding="utf-8")
OUT.write_text(html.replace("</body>", PROBE + "</body>"), encoding="utf-8")
print(f"生成 {OUT}")
