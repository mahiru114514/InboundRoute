"""本地 HTTP 入口：Host 与令牌鉴权、严格 JSON 及标准信封。"""
from __future__ import annotations

import json
import secrets
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from .client import UpstreamError

MAX_BODY = 64 * 1024


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'JSON 字段重复：{key}')
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f'JSON 不允许 {value}')


def build_handler(service, token):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'
        server_version = 'recommendation_engine/0.1'

        def setup(self):
            super().setup()
            self.connection.settimeout(20)

        def log_message(self, *_):
            pass

        def reply(self, status, value):
            body = json.dumps(value, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(body)
            self.close_connection = True

        def ok(self, data):
            self.reply(200, {'ok': True, 'data': data, 'meta': {
                'contract_version': service.contract_version, 'server_time': int(time.time())}})

        def fail(self, status, code, message, details=None):
            self.reply(status, {'ok': False, 'error': {'code': code, 'message': message,
                                                      'details': details or {}, 'retryable': status >= 500}})

        def body(self):
            if self.headers.get('Transfer-Encoding'):
                raise ValueError('不支持 Transfer-Encoding')
            lengths = self.headers.get_all('Content-Length', [])
            if len(lengths) != 1 or not lengths[0].isdigit():
                raise ValueError('Content-Length 必须是非负整数')
            length = int(lengths[0])
            if length > MAX_BODY:
                raise UpstreamError(413, 'BAD_REQUEST', f'请求体超过 {MAX_BODY} 字节')
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError('请求体长度不完整')
            try:
                return json.loads(raw.decode('utf-8'), object_pairs_hook=_object, parse_constant=_invalid_constant)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError('请求体必须是有效 JSON') from exc

        def dispatch(self, method):
            host = self.headers.get_all('Host', [])
            if len(host) != 1 or host[0] not in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}:
                return self.fail(403, 'FORBIDDEN', '请求 Host 必须为本地模块地址')
            path = urlsplit(self.path).path
            if path != '/health':
                tokens = self.headers.get_all('X-Module-Token', [])
                if len(tokens) != 1 or not secrets.compare_digest(tokens[0].encode('utf-8'), token.encode('utf-8')):
                    return self.fail(403, 'FORBIDDEN', '缺少或错误的 X-Module-Token')
            try:
                if path == '/health':
                    if method != 'GET':
                        return self.fail(405, 'BAD_REQUEST', 'health 仅支持 GET')
                    return self.ok(service.health())
                if path == '/recommendations:generate':
                    if method != 'POST':
                        return self.fail(405, 'BAD_REQUEST', '推荐生成仅支持 POST')
                    return self.ok(service.generate(self.body()))
                return self.fail(404, 'BAD_REQUEST', '操作不存在')
            except UpstreamError as exc:
                return self.fail(exc.status, exc.code, exc.message, exc.details)
            except (ValueError, TypeError) as exc:
                return self.fail(400, 'BAD_REQUEST', str(exc))
            except Exception:
                return self.fail(500, 'UPSTREAM_BAD_RESPONSE', '推荐生成失败，请稍后重试。')

        def do_GET(self):
            self.dispatch('GET')

        def do_POST(self):
            self.dispatch('POST')

        def do_PATCH(self):
            self.dispatch('PATCH')

        def do_PUT(self):
            self.dispatch('PUT')

        def do_DELETE(self):
            self.dispatch('DELETE')

    return Handler


def build_server(service, token, port=0, host='127.0.0.1'):
    server = ThreadingHTTPServer((host, port), build_handler(service, token))
    server.daemon_threads = True
    return server
