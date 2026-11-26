"""把「采集端实时同步」接到服务：/api/origin + 采集后自动同步 + 前端轮询。"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "server.py"
BUILD = ROOT / "tools" / "build_web.py"


def patch_server() -> None:
    text = SERVER.read_text(encoding="utf-8")

    # 1) 导入
    old = "from . import repo"
    new = "from . import origin as origin_mod\nfrom . import repo"
    if old in text and "origin as origin_mod" not in text:
        text = text.replace(old, new, 1)

    # 2) 路由
    old_route = '        if path == "/api/world":'
    new_route = '''        if path == "/api/origin":
            return self._serve_origin(query)
        if path == "/api/world":'''
    if "/api/origin" not in text:
        text = text.replace(old_route, new_route, 1)

    # 3) 处理函数
    anchor = "    def _serve_world(self) -> int:"
    handler = '''    def _serve_origin(self, query) -> int:
        """采集端当前位置。?refresh=1 会立即重新检测（会打一次外部接口）。"""
        refresh = (query.get("refresh") or ["0"])[0] == "1"
        if refresh and origin_mod.auto_enabled():
            result = origin_mod.sync(rebuild=False, force=True)
            payload = {"origin": origin_mod.current(), **result}
        else:
            payload = {"origin": origin_mod.current()}
        self._json(200, payload)
        return 200

    def _serve_world(self) -> int:'''
    if "_serve_origin" not in text:
        text = text.replace(anchor, handler, 1)

    # 4) 定时采集后同步位置
    old_sched = '''                cli_main(["collect"])
                cli_main(["health"])'''
    new_sched = '''                cli_main(["collect"])
                cli_main(["health"])
                if origin_mod.auto_enabled():
                    sync_result = origin_mod.sync(rebuild=True)
                    LOG.info("origin sync after collect: %s", sync_result.get("reason"))'''
    if "origin sync after collect" not in text and old_sched in text:
        text = text.replace(old_sched, new_sched, 1)

    SERVER.write_text(text, encoding="utf-8")
    print("patched server: /api/origin + scheduler")


def patch_frontend() -> None:
    text = BUILD.read_text(encoding="utf-8")

    # 在 init 之后加定时轮询：位置变了就更新 GLOBE.origin 并重绘
    old_init = "bind(rows);\n\n/* 支持 #world / #dist 直达视图"
    new_init = """bind(rows);

/* 采集端位置实时同步：每 5 分钟问一次后端，变了就重绘地球 */
(function watchOrigin(){
  const LABEL_INTERVAL = 5 * 60 * 1000;
  let lastCity = (GLOBE && GLOBE.origin && GLOBE.origin.city) || "";

  async function tick(first){
    try{
      const resp = await fetch("/api/origin" + (first ? "?refresh=1" : ""), {credentials: "same-origin"});
      if(!resp.ok) return;
      const data = await resp.json();
      const o = data.origin || {};
      if(!o.city) return;
      if(o.city !== lastCity){
        lastCity = o.city;
        if(GLOBE) GLOBE.origin = {city: o.city, lat: o.lat, lon: o.lon,
                                 source: o.source, ip: o.ip, detected_at: o.detected_at};
        renderGlobe();
        const legend = $("globe-legend");
        if(legend){
          const tag = String(o.source || "").indexOf("ip-detected") === 0 ? "AUTO IP" : "MANUAL";
          legend.innerHTML = "NODE " + tag + "<br>" +
            ((GLOBE && GLOBE.sources) || []).length + " SOURCE NODES";
        }
      }
    }catch(e){ /* 离线或未登录，忽略 */ }
  }
  tick(true);
  setInterval(() => tick(false), LABEL_INTERVAL);
})();

/* 支持 #world / #dist 直达视图"""
    if "watchOrigin" not in text and old_init in text:
        text = text.replace(old_init, new_init, 1)

    BUILD.write_text(text, encoding="utf-8")
    print("patched build_web: origin polling")


if __name__ == "__main__":
    patch_server()
    patch_frontend()
