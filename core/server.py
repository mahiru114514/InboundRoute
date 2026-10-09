import base64
import binascii
import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .installer import MAX_FOLDER_UPLOAD, MAX_UPLOAD

WEB = Path(__file__).resolve().parent.parent / "web"


def parse_install(raw, format_name):
    """把安装请求体解析为 (类型, 载荷)。folder 由页面把本地文件夹编码为 JSON。"""
    if format_name == "zip":
        return "zip", raw
    if format_name == "folder":
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"文件夹安装请求不是有效的 JSON：{exc}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("folder"), str) or \
                not isinstance(payload.get("files"), dict):
            raise ValueError("请求必须包含 folder 文本和 files 对象")
        files = {}
        for name, content in payload["files"].items():
            if not isinstance(content, str):
                raise ValueError(f"文件内容必须是 base64 文本：{name}")
            try:
                files[name] = base64.b64decode(content, validate=True).decode("utf-8")
            except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
                raise ValueError(f"文件内容不是有效的 UTF-8 文本：{name}") from exc
        return "folder", (payload["folder"], files)
    raise ValueError("安装格式必须是 zip 或 folder")


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, *_):
        pass

    def reply(self, status, value, content_type="application/json; charset=utf-8"):
        data = json.dumps(value, ensure_ascii=False).encode("utf-8") if content_type.startswith("application/json") else value
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(data)

    def trusted(self, writing=False):
        allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        if self.headers.get("Host") not in allowed:
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in {"http://" + host for host in allowed}:
            return False
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            return False
        return not writing or secrets.compare_digest(self.headers.get("X-Manager-Token", ""), self.server.token)

    def do_GET(self):
        if not self.trusted():
            return self.reply(403, {"error": "仅允许从本机管理页面访问"})
        path = urlsplit(self.path).path
        manager = self.server.manager
        try:
            if path == "/api/state":
                return self.reply(200, {"modules": manager.list(), "token": self.server.token})
            parts = path.strip("/").split("/")
            if len(parts) == 3 and parts[:2] == ["api", "modules"]:
                return self.reply(200, {"config": manager.config(parts[2]), "logs": manager.logs(parts[2])})
            assets = {"/": ("index.html", "text/html; charset=utf-8"),
                      "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                      "/style.css": ("style.css", "text/css; charset=utf-8")}
            if path in assets:
                filename, mime = assets[path]
                return self.reply(200, (WEB / filename).read_bytes(), mime)
            return self.reply(404, {"error": "页面不存在"})
        except (ValueError, OSError) as exc:
            return self.reply(400, {"error": str(exc)})

    def do_POST(self):
        try:
            path = urlsplit(self.path).path
            length = int(self.headers.get("Content-Length", "0"))
            if path == "/api/install":
                format_name = (self.headers.get("X-Install-Format") or "zip").strip().lower()
                limit = MAX_FOLDER_UPLOAD if format_name == "folder" else MAX_UPLOAD
            else:
                limit = 65536
            if not 0 <= length <= limit:
                return self.reply(413, {"error": "上传内容超过大小限制"})
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError("请求内容不完整")
            # 消费有界请求体后再返回拒绝响应，避免 Windows 因未读数据而重置连接。
            if not self.trusted(writing=True):
                return self.reply(403, {"error": "请求校验失败，请刷新管理页面"})
            manager = self.server.manager
            if path == "/api/install":
                kind, payload = parse_install(raw, format_name)
                if kind == "folder":
                    module_id = manager.install_folder(*payload)
                    return self.reply(200, {"message": f"{module_id} 已从本地文件夹安装，默认禁用"})
                module_id = manager.install(payload)
                return self.reply(200, {"message": f"{module_id} 安装成功，默认禁用"})
            if path == "/api/shutdown":
                self.reply(200, {"message": "正在停止模块并关闭管理服务"})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            parts = path.strip("/").split("/")
            if len(parts) != 4 or parts[:2] != ["api", "modules"]:
                return self.reply(404, {"error": "操作不存在"})
            module_id, action = parts[2:]
            actions = {"enable": manager.enable, "disable": manager.disable, "start": manager.start,
                       "stop": manager.stop, "uninstall": manager.uninstall}
            if action == "config":
                manager.configure(module_id, json.loads(raw))
            elif action in actions:
                actions[action](module_id)
            else:
                return self.reply(404, {"error": "操作不存在"})
            self.reply(200, {"message": "操作完成"})
        except (ValueError, OSError, RuntimeError) as exc:
            self.reply(400, {"error": str(exc)})


def create_server(manager, port=8765):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.manager = manager
    server.token = secrets.token_urlsafe(32)
    return server
