"""模块注册表读写（C7 §2）。

InboundRoute 的宿主「模块工作台」不分配端口、不转发业务请求，模块之间通过本地 HTTP 互相调用。
本模块提供两端公共的读写逻辑，**三个业务模块都必须用它，不要各写一份**。

放置位置约定：`<workspace>/contracts/runtime/registry.py`；
模块在 `plugin.py` 里把 workspace 根加入 sys.path 后 `from contracts.runtime import registry`。

纯标准库实现，无第三方依赖。
"""

from __future__ import annotations

import json
import os
import secrets
import socket
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

REGISTRY_DIRNAME = "_registry"
CONTRACT_VERSION = "0.3.3"
HEALTH_PATH = "/health"
TOKEN_HEADER = "X-Module-Token"
TOKEN_BYTES = 32


class RegistryError(RuntimeError):
    """注册表相关错误（端口占用、双实例、格式非法等）。"""


@dataclass
class Registration:
    """注册文件的内容。字段与 C7 §2 的格式一一对应，不要增删。"""

    module_id: str
    port: int
    base_url: str
    token: str
    pid: int
    contract_version: str
    started_at: int
    depends_on: list[str] = field(default_factory=list)
    endpoints: list[str] = field(default_factory=list)

    @property
    def health_url(self) -> str:
        return self.base_url + HEALTH_PATH

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, value: dict) -> "Registration":
        required = ("module_id", "port", "base_url", "token", "pid",
                    "contract_version", "started_at")
        missing = [key for key in required if key not in value]
        if missing:
            raise RegistryError(f"注册文件缺少字段：{', '.join(missing)}")
        return cls(
            module_id=value["module_id"],
            port=int(value["port"]),
            base_url=value["base_url"],
            token=value["token"],
            pid=int(value["pid"]),
            contract_version=value["contract_version"],
            started_at=int(value["started_at"]),
            depends_on=list(value.get("depends_on") or []),
            endpoints=list(value.get("endpoints") or []),
        )


# ---------------------------------------------------------------- 目录与路径

def registry_dir(workspace_root: Path | str) -> Path:
    """注册目录：<workspace>/data/_registry（所有模块共享，刻意放在各模块 data_dir 之外）。"""
    return Path(workspace_root) / "data" / REGISTRY_DIRNAME


def registry_path(workspace_root: Path | str, module_id: str) -> Path:
    return registry_dir(workspace_root) / f"{module_id}.json"


def workspace_root_from_module_dir(module_dir: Path | str) -> Path:
    """模块目录是 <workspace>/modules/<id>，上溯两级即 workspace 根。"""
    return Path(module_dir).resolve().parent.parent


# ---------------------------------------------------------------- 端口与令牌

def resolve_port(config: dict | None = None, module_id: str | None = None,
                 workspace: Path | str | None = None, host: str = "127.0.0.1") -> int:
    """决定模块监听端口；返回 0 表示「交给系统分配」。优先级：

    1. `config["port"]` 合法（1..65535）→ 直接用它（原有契约，显式配置永远说话）；
    2. 否则尝试复用该模块**上一次登记过的端口**——只有同时给出 module_id 与 workspace 才试，
       老调用（只传 config）的行为与以前完全一致；
    3. 都不成立则返回 0，由 OS 分配。

    为什么要有第 2 条（工程体验缺陷修复）：以前缺省恒为 0，模块每次启动都换端口，
    用户收藏 / 分享的 `http://127.0.0.1:<port>/…` 深链一重启就失效。复用之后，
    「上次正常停止 → 再次启动」这条正常路径端口保持不变。

    复用是**尽力而为**：读注册文件、判活、试绑定任何一步不成立都静默回落到 0，
    绝不因为端口复用失败而让模块起不来（`check_no_live_instance()` 仍然负责双实例报错）。
    """
    configured = _configured_port(config)
    if configured:
        return configured
    if module_id and workspace:
        try:
            return _remembered_port(module_id, workspace, host)
        except Exception:  # noqa: BLE001 —— 复用分支的任何意外都不允许影响模块启动
            return 0
    return 0


def _configured_port(config: dict | None) -> int:
    """`config["port"]` 的合法值；缺省、为 0 或非法时返回 0。"""
    value = (config or {}).get("port", 0)
    try:
        port = int(value)
    except (TypeError, ValueError):
        return 0
    return port if 0 < port < 65536 else 0


def _remembered_port(module_id: str, workspace: Path | str, host: str = "127.0.0.1") -> int:
    """上一次注册记录里的端口；只有「上一任主人已死」且「端口现在真空闲」才发出去，否则 0。"""
    previous = try_read(workspace, module_id)
    try:
        if previous is not None:
            port = int(previous.port)
        else:
            # 历史只有端口，不含令牌、pid 或 base_url，不参与服务发现。
            history = registry_dir(workspace) / '_ports' / f'{module_id}.json'
            port = int(json.loads(history.read_text(encoding='utf-8'))['port'])
    except (OSError, TypeError, ValueError, KeyError):
        return 0
    if not 0 < port < 65536:
        return 0
    if previous is not None and process_alive(previous.pid):
        # 上一任实例还活着：这个端口是它的，不能发出去（此刻启动本身就是双实例，
        # 由 check_no_live_instance() 负责报错拦下）。
        return 0
    if not port_available(host, port):
        # 端口被别人占了（另一个程序，或上一任还没来得及退干净）→ 让 OS 另分配一个。
        return 0
    return port


def process_alive(pid: int) -> bool:
    """pid 是否仍在运行（只读探测，跨平台）。

    ⚠️ 刻意**不用** `os.kill(pid, 0)`：那套「信号 0 只做存在性检查」是 POSIX 语义，
    Windows 上 CPython 的 `os.kill()` 走 TerminateProcess（signal 值当退出码），
    对活着的进程调 `os.kill(pid, 0)` 会顺手把它杀掉。所以按平台分派：

    · POSIX：`os.kill(pid, 0)`；ProcessLookupError=已退出，PermissionError=存在但无权操作（算活着）；
    · Windows：`OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` + `GetExitCodeProcess`，
      STILL_ACTIVE(259) 即存活，不发送任何信号。

    拿不准（pid 非法、pid 被系统回收后指向了别的进程、权限受限）时返回 False（判死）：
    调用方 `_remembered_port()` 后面还有一次真实绑定探测兜底，pid 本来就无法 100% 判定。
    """
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        # 0 / 负数在 POSIX 上是「进程组」语义，不能拿来判活；注册文件里出现这种值视为无主。
        return False
    if os.name == "nt":
        return _windows_process_alive(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _windows_process_alive(pid: int) -> bool:
    """Windows 判活：只查询退出码，绝不发送信号/终止码。"""
    import ctypes
    from ctypes import wintypes

    process_query_limited_information = 0x1000
    error_access_denied = 5
    still_active = 259
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        # 打不开：进程不存在（ERROR_INVALID_PARAMETER，实测 pid=999999 → 87）算已退出；
        # 权限不足（ERROR_ACCESS_DENIED）说明它存在，只是不让我查 → 保守当活着。
        return ctypes.get_last_error() == error_access_denied
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return False
        return code.value == still_active
    finally:
        kernel32.CloseHandle(handle)


def port_available(host: str = "127.0.0.1", port: int = 0) -> bool:
    """host:port 现在能否被绑定（能绑定 = 空闲）。

    刻意**不复用** `bind_socket()`：它带 SO_REUSEADDR。Windows 上 SO_REUSEADDR 允许
    「抢占」已被监听的端口——占用方自己也设了 SO_REUSEADDR 时（模块的 bind_socket 就是这样），
    带 SO_REUSEADDR 的探测会绑定成功，把「已被占用」误判成「空闲」（实测 WinError 10048 vs
    绑成功）。所以这里用最朴素的 bind：Windows 上再加 SO_EXCLUSIVEADDRUSE，只要有人占着
    就一定失败；探测完立刻关闭，不占用端口（实测不影响随后的正常绑定）。
    """
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        probe.bind((host, port))
    except OSError:
        return False
    finally:
        probe.close()
    return True


def bind_socket(host: str = "127.0.0.1", port: int = 0) -> socket.socket:
    """绑定监听 socket 并开启地址复用；返回的 socket 上可读 getsockname() 拿真实端口。"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((host, port))
        server.listen(64)
    except OSError as exc:
        server.close()
        raise RegistryError(f"端口 {port or '自动'} 绑定失败：{exc}") from exc
    return server


def new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def now_seconds() -> int:
    import time
    return int(time.time())


# ---------------------------------------------------------------- 健康探测

def probe_health(base_url: str, timeout: float = 1.0) -> dict | None:
    """探测 /health；无响应或非法响应返回 None（不抛异常，供启动期轮询使用）。"""
    import urllib.error
    import urllib.request

    request = urllib.request.Request(base_url.rstrip("/") + HEALTH_PATH, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                return None
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return None


def wait_for_dependency(registration: Registration, timeout: float = 30.0,
                        initial_interval: float = 0.2, max_interval: float = 1.0) -> dict:
    """轮询依赖的 /health 直到 ready（C7 §5：最长 30s，200ms→1s 退避）。

    返回最后一次成功的 health 响应；超时抛 RegistryError，**不要静默降级**。

    ⚠️ 这个签名把 base_url 固定成传入值：只适合「注册信息不会变」的短等待。
    模块启动时请用 `wait_for_registration()`——被依赖方重启会换端口，
    固定 base_url 会让我们对着一个已死端口白等到超时（真实故障见
    `logs/rules_engine.log` 2026-09-29 22:52：等的是 53559，注册表里写的是 53182）。
    """
    import time

    deadline = time.monotonic() + timeout
    interval = initial_interval
    last_error = "未收到响应"
    while time.monotonic() < deadline:
        health = probe_health(registration.base_url)
        if health is not None:
            if health.get("ready") is False:
                last_error = "依赖已响应但未就绪（ready=false）"
            elif health.get("status") in (None, "ok", "degraded"):
                return health
            else:
                last_error = f"依赖状态异常：{health.get('status')}"
        time.sleep(interval)
        interval = min(interval * 2, max_interval)
    raise RegistryError(
        f"依赖 {registration.module_id} 在 {timeout:.0f}s 内未就绪（{last_error}）。"
        f"请先确认该模块已在管理页面「运行」。")


def wait_for_registration(workspace_root: Path | str, module_id: str, timeout: float = 30.0,
                          initial_interval: float = 0.2, max_interval: float = 1.0,
                          probe_timeout: float = 1.0) -> tuple[Registration, dict]:
    """等某个模块**注册**并 /health 就绪；返回 (最新注册信息, health 响应)。

    与 `wait_for_dependency()` 的两点差别，都是被真实故障逼出来的：

    1. **每一轮都重读注册文件**。模块重启会换端口和令牌；把 base_url 固定在第一次读到的值上，
       就会拿着一份「上一轮遗留、指向已死端口」的注册信息白等 30s 再退出，而新实例其实
       早就在另一个端口上跑起来了。
    2. **注册文件还没出现时继续等**，而不是立刻抛「未运行」。被依赖方晚几百毫秒登记是常态
       （launcher 并发启动、模块自己要加载数据）。

    超时仍然抛 RegistryError（契约：不静默降级），错误信息里带上最后一次尝试的地址。
    """
    import time

    deadline = time.monotonic() + timeout
    interval = initial_interval
    last_error = "未找到注册文件"
    latest: Registration | None = try_read(workspace_root, module_id)
    while time.monotonic() < deadline:
        current = try_read(workspace_root, module_id)
        if current is None:
            # 分清「还没登记」和「文件在但读不出来」：后者干等 30s 也等不到，得让用户看到原因
            last_error = (f"注册文件存在但无法解析（{registry_path(workspace_root, module_id)}）"
                          if registry_path(workspace_root, module_id).is_file()
                          else "未找到注册文件（模块尚未登记）")
        else:
            latest = current
            health = probe_health(current.base_url, timeout=probe_timeout)
            if health is None:
                last_error = f"未收到响应（{current.base_url}）"
            elif health.get("ready") is False:
                last_error = f"依赖已响应但未就绪（ready=false，{current.base_url}）"
            elif health.get("status") in (None, "ok", "degraded"):
                return current, health
            else:
                last_error = f"依赖状态异常：{health.get('status')}（{current.base_url}）"
        time.sleep(interval)
        interval = min(interval * 2, max_interval)
    raise RegistryError(
        f"依赖 {module_id} 在 {timeout:.0f}s 内未就绪（{last_error}）。"
        f"请先确认该模块已在管理页面「运行」。")


# ---------------------------------------------------------------- 读 / 写 / 删

def read(workspace_root: Path | str, module_id: str) -> Registration:
    """读取并校验注册文件；不存在或格式非法时抛 RegistryError。"""
    path = registry_path(workspace_root, module_id)
    if not path.is_file():
        raise RegistryError(f"未找到 {module_id} 的注册文件（{path}）。该模块可能未运行。")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryError(f"{module_id} 的注册文件无法解析：{exc}") from exc
    registration = Registration.from_dict(value)
    if registration.module_id != module_id:
        raise RegistryError(f"注册文件内容与文件名不一致：{registration.module_id} != {module_id}")
    return registration


def try_read(workspace_root: Path | str, module_id: str) -> Registration | None:
    try:
        return read(workspace_root, module_id)
    except RegistryError:
        return None


def check_no_live_instance(workspace_root: Path | str, module_id: str) -> None:
    """启动前检查：若已有同 id 的**存活**实例则拒绝启动（避免双实例）。

    残留注册文件（进程已死）不报错，交由 write() 覆盖。
    C7 §5：先探测其 /health —— 无响应则覆盖，有响应则报错退出。
    """
    existing = try_read(workspace_root, module_id)
    if existing is None:
        return
    if probe_health(existing.base_url, timeout=0.5) is not None:
        raise RegistryError(
            f"检测到 {module_id} 的另一个运行实例（pid={existing.pid}, port={existing.port}）。"
            f"请先在管理页面停止它，避免双实例写入同一份数据。")


def write(registration: Registration, workspace_root: Path | str) -> Path:
    """原子写入注册文件（临时文件 + 替换），并确保目录存在。"""
    directory = registry_dir(workspace_root)
    directory.mkdir(parents=True, exist_ok=True)
    target = registry_path(workspace_root, registration.module_id)
    handle, temp_name = tempfile.mkstemp(prefix=f".{registration.module_id}-", suffix=".tmp",
                                        dir=str(directory))
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(registration.to_json())
        os.replace(temp_name, target)
    except OSError as exc:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise RegistryError(f"写入注册文件失败：{exc}") from exc
    _remember_port(registration, workspace_root)
    return target


def _remember_port(registration: Registration, workspace_root: Path | str) -> None:
    """尽力保存端口历史；历史写入失败不影响服务启动。"""
    temp_name = None
    try:
        directory = registry_dir(workspace_root) / '_ports'
        directory.mkdir(parents=True, exist_ok=True)
        handle, temp_name = tempfile.mkstemp(prefix=f'.{registration.module_id}-',
                                            suffix='.tmp', dir=str(directory))
        with os.fdopen(handle, 'w', encoding='utf-8') as stream:
            json.dump({'port': registration.port}, stream)
        os.replace(temp_name, directory / f'{registration.module_id}.json')
    except OSError:
        if temp_name is not None:
            try:
                os.unlink(temp_name)
            except OSError:
                pass


def remove(workspace_root: Path | str, module_id: str) -> None:
    """退出时删除注册文件；文件不存在不报错。"""
    try:
        registry_path(workspace_root, module_id).unlink()
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise RegistryError(f"删除注册文件失败：{exc}") from exc


def build_registration(module_id: str, port: int, token: str, depends_on: list[str] | None = None,
                       endpoints: list[str] | None = None, host: str = "127.0.0.1") -> Registration:
    """按 C7 §2 组装注册信息；contract_version 固定取常量。"""
    return Registration(
        module_id=module_id,
        port=port,
        base_url=f"http://{host}:{port}",
        token=token,
        pid=os.getpid(),
        contract_version=CONTRACT_VERSION,
        started_at=now_seconds(),
        depends_on=list(depends_on or []),
        endpoints=list(endpoints or []),
    )


# ---------------------------------------------------------------- 调用辅助

def call_json(registration: Registration, method: str, path: str, payload: dict | None = None,
              timeout: float = 20.0) -> dict:
    """带令牌调用另一个模块的 JSON 端点（C7 §4：除 /health 外必须带 X-Module-Token）。"""
    import urllib.error
    import urllib.request

    url = registration.base_url.rstrip("/") + path
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, method=method.upper())
    request.add_header(TOKEN_HEADER, registration.token)
    request.add_header("Content-Type", "application/json; charset=utf-8")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RegistryError(f"调用 {registration.module_id}{path} 失败：HTTP {exc.code} {detail[:200]}") from exc
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        raise RegistryError(f"调用 {registration.module_id}{path} 失败：{exc}") from exc


def discover(workspace_root: Path | str, depends_on: list[str]) -> dict[str, Registration]:
    """按依赖清单发现上游模块（读注册表），缺失时抛错并列出缺哪个。"""
    found: dict[str, Registration] = {}
    missing: list[str] = []
    for module_id in depends_on:
        registration = try_read(workspace_root, module_id)
        if registration is None:
            missing.append(module_id)
        else:
            found[module_id] = registration
    if missing:
        raise RegistryError(
            "以下依赖模块未运行（无注册文件）：" + "、".join(missing) +
            "。请在管理页面依次启用并运行它们。")
    return found


def refresh(workspace_root: Path | str, module_ids) -> dict[str, Registration | None]:
    """按注册表重新解析一批依赖，返回 {module_id: Registration | None}（键与入参一致）。

    长期驻留的模块**必须**周期性地用这个刷新，而不是把启动时的快照一直用下去：
    上游重启会换端口和令牌，抱着旧快照不放的后果是——每个请求都打向已死端口，
    `/health` 还会永久显示 `degraded`，看起来像「对方挂了」，其实对方好好的。

    返回 `None` 表示该模块当前没有登记（已停止或正在启动）；调用方据此判定上游不可用。
    """
    return {module_id: try_read(workspace_root, module_id) for module_id in module_ids}
