"""底图提供方配置和页面内容安全策略；独立于 HTTP 代理。"""
from __future__ import annotations

import os

# 高德 JS API（在线加载，官方要求不得本地转存）：loader 与各项服务域名
AMAP_LOADER = "https://webapi.amap.com/loader.js"
AMAP_SCRIPT_HOSTS = "https://webapi.amap.com https://a.amap.com"
AMAP_CONNECT_HOSTS = "https://restapi.amap.com https://webapi.amap.com https://a.amap.com"
AMAP_IMG_HOSTS = "https://a.amap.com https://webapi.amap.com https://restapi.amap.com data:"

# Leaflet（免费方案，无需注册与 key）：SDK 走 CDN，瓦片默认用高德公共瓦片。
# SDK 按顺序尝试多个 CDN（任一可用即可），避免单个 CDN 抖动导致底图整体不可用。
LEAFLET_CDNS = [
    {"name": "unpkg", "js": "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js",
     "css": "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"},
    {"name": "cdnjs", "js": "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js",
     "css": "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css"},
]
# 高德公共瓦片（无 key、中文双语标注，坐标是 GCJ-02）。官方底图请配 AMAP_JS_KEY。
DEFAULT_TILE_URL = "https://wprd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&style=7&x={x}&y={y}&z={z}"
DEFAULT_TILE_SUBDOMAINS = "1234"
DEFAULT_TILE_ATTRIBUTION = "底图 © 高德地图"
LEAFLET_CSP = (
    "script-src 'self' https://unpkg.com https://cdnjs.cloudflare.com; "
    "style-src 'self' 'unsafe-inline' https://unpkg.com https://cdnjs.cloudflare.com; "
    "img-src 'self' data: https://*.amap.com https://*.autonavi.com "
    "https://*.tile.openstreetmap.org https://unpkg.com; "
    "connect-src 'self'"
)


def build_csp(map_config: dict) -> str:
    """页面 CSP。未配置任何底图时必须保持严格（只允许 'self'）。"""
    provider = map_config.get("provider")
    if not map_config.get("ready") or provider not in ("amap", "leaflet"):
        return ("default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
    if provider == "amap":
        # 官方明确要求在线加载 JS API（禁止本地转存/打包），因此只放行高德域名。
        return (f"default-src 'self'; script-src 'self' {AMAP_SCRIPT_HOSTS}; "
                f"style-src 'self' 'unsafe-inline'; "
                f"img-src 'self' {AMAP_IMG_HOSTS}; "
                f"connect-src 'self' {AMAP_CONNECT_HOSTS}; "
                "frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
    return (f"default-src 'self'; {LEAFLET_CSP}; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'self'")


def map_config(config: dict) -> dict:
    """地图配置：key 与安全密钥从环境变量或 context.config 读，并为前端准备好可注入的值。

    环境变量优先（便于本地临时试用，不必写进被页面展示的配置）：
        AMAP_JS_KEY         Web端(JS API) 的 key
        AMAP_SECURITY_CODE  安全密钥（2021-12-02 之后申请的 key 必需）
        MAP_PROVIDER        强制指定底图：amap / leaflet / none

    默认策略：配了 key 用高德；没配 key 用 Leaflet（免费、无需注册）；显式 none 则用示意地图。
    """
    source = config or {}
    key = os.environ.get("AMAP_JS_KEY") or source.get("amap_js_key") or ""
    security = os.environ.get("AMAP_SECURITY_CODE") or source.get("amap_security_code") or ""
    forced = (os.environ.get("MAP_PROVIDER") or source.get("map_provider") or "").strip().lower()

    provider = forced if forced in ("amap", "leaflet", "none") else ("amap" if key else "leaflet")
    common = {
        "provider": provider,
        "ready": provider in ("amap", "leaflet") and (provider != "amap" or bool(key)),
        "hint": "",
        "tile_url": source.get("tile_url") or DEFAULT_TILE_URL,
        "tile_attribution": source.get("tile_attribution") or DEFAULT_TILE_ATTRIBUTION,
        "tile_subdomains": source.get("tile_subdomains", DEFAULT_TILE_SUBDOMAINS),
        "tile_crs": source.get("tile_crs") or (
            "gcj02" if "autonavi.com" in (source.get("tile_url") or DEFAULT_TILE_URL) or
            "amap.com" in (source.get("tile_url") or DEFAULT_TILE_URL) else "wgs84"),
    }
    if provider == "amap":
        plugins = source.get("amap_plugins") or ["AMap.Scale", "AMap.ToolBar"]
        return {**common,
                "key": key,
                "security_code": security,
                "security_mode": "plain" if security else "none",
                "version": str(source.get("amap_version") or "2.0"),
                "plugins": [item for item in plugins if isinstance(item, str)],
                "loader_url": AMAP_LOADER,
                "hint": "" if key else "未配置高德 key。"}
    if provider == "leaflet":
        cdns = source.get("leaflet_cdns") if isinstance(source.get("leaflet_cdns"), list) else None
        selected = cdns if cdns else LEAFLET_CDNS
        # 备用瓦片源：高德瓦片连不上时前端自动切过去（OSM 是 WGS84，不做 GCJ 转换）
        fallback = source.get("fallback_tile")
        if fallback is None and common["tile_crs"] == "gcj02":
            fallback = {"name": "OpenStreetMap",
                        "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
                        "attribution": "底图 © OpenStreetMap contributors",
                        "crs": "wgs84"}
        return {**common,
                "fallback_tile": fallback,
                "leaflet_cdns": selected,
                "leaflet_js": selected[0]["js"],
                "leaflet_css": selected[0]["css"],
                "hint": "使用 Leaflet + 免费瓦片（无需注册与 key）。想换高德官方底图请设置 AMAP_JS_KEY。"}
    return {**common, "ready": False, "hint": "已指定不使用底图（map_provider=none），使用示意地图。"}
