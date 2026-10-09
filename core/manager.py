import json
import multiprocessing
import threading
import time
import uuid
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest

from .installer import install_folder, install_zip
from .manifest import read_manifest, validate_id
from .runtime import run_worker

HEALTH_TIMEOUT = 0.4      # 单次健康探测超时（秒）
HEALTH_CACHE_TTL = 2.0    # 探测结果缓存时长（秒），避免 3 秒轮询每次都打服务


class Manager:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.modules = self.root / "modules"
        for folder in ("modules", "config", "data", "logs", ".staging", ".trash"):
            (self.root / folder).mkdir(parents=True, exist_ok=True)
        self.state_path = self.root / "config/state.json"
        self.state = json.loads(self.state_path.read_text(encoding="utf-8")) if self.state_path.exists() else {}
        if not isinstance(self.state, dict) or any(not isinstance(v, dict) or
                not isinstance(v.get("enabled", False), bool) or not isinstance(v.get("config", {}), dict)
                for v in self.state.values()):
            raise ValueError("config/state.json 格式无效，请修复后重启")
        self.processes = {}
        self.lock = threading.RLock()
        self.mp = multiprocessing.get_context("spawn")
        self.registry_dir = self.root / "data" / "_registry"
        self._health_cache = {}

    def _save(self):
        temp = self.state_path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.state_path)

    def _discover(self):
        found = {}
        for path in sorted(self.modules.iterdir()):
            if not path.is_dir() or path.name.startswith("."):
                continue
            try:
                info = read_manifest(path)
                if info["id"] != path.name:
                    raise ValueError("文件夹名必须与清单 id 一致")
                info["error"] = ""
            except (ValueError, OSError) as exc:
                info = {"id": path.name, "name": path.name, "version": "—", "description": "",
                        "dependencies": [], "error": str(exc)}
            found[path.name] = info
        return found

    def _get(self, module_id):
        validate_id(module_id)
        info = self._discover().get(module_id)
        if not info:
            raise ValueError(f"模块不存在：{module_id}")
        if info["error"]:
            raise ValueError(info["error"])
        return info

    def _running(self, module_id):
        record = self.processes.get(module_id)
        return bool(record and record[0].is_alive())

    def _active(self, module_id):
        """约束看实际运行状态；进程回收仍只处理本宿主拥有的实例。"""
        return self._running(module_id) or self._external_alive(module_id)

    def _enabled(self, module_id):
        return self.state.get(module_id, {}).get("enabled", False)

    def _service_meta(self, folder):
        """读清单里的 service 段（宿主本身忽略该字段，这里只用于界面展示与健康探测）。"""
        try:
            value = json.loads((folder / "manifest.json").read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            return None
        service = value.get("service") if isinstance(value, dict) else None
        if not isinstance(service, dict) or not service.get("enabled"):
            return None
        health_path = service.get("health_path")
        return {
            "enabled": True,
            "health_path": health_path if isinstance(health_path, str) and health_path.startswith("/") else "/health",
            "open_path": service.get("open_path") if isinstance(service.get("open_path"), str) else None,
            "title": service.get("title") if isinstance(service.get("title"), str) else "",
        }

    def _probe_health(self, base_url, health_path):
        """短超时探测 /health；失败不抛异常（页面轮询不能因为一个模块卡住）。"""
        url = base_url.rstrip("/") + health_path
        try:
            with urlrequest.urlopen(url, timeout=HEALTH_TIMEOUT) as response:
                payload = json.loads(response.read(1024).decode("utf-8", errors="replace"))
        except (urlerror.URLError, OSError, ValueError):
            return None
        if isinstance(payload, dict):
            return {"status": str(payload.get("status", "ok")), "ready": bool(payload.get("ready", True))}
        return {"status": "ok", "ready": True}

    def _service_info(self, module_id, folder):
        """服务型模块的端口与健康状态（供管理页面显示）。

        health 取值：ok（/health 通过）/ down（注册了端口但探测失败）/ no_port（尚未注册端口）
        / starting（正在运行但还没写注册文件）/ stopped（未运行）/ not_service（非服务模块）
        """
        service = self._service_meta(folder)
        if not service:
            return None
        info = {
            "service": True,
            "health_path": service["health_path"],
            "open_path": service["open_path"],
            "title": service["title"],
            "port": None,
            "base_url": "",
            "health": "no_port",
            "detail": "尚未注册端口",
            "checked_at": int(time.time()),
        }
        # 注册文件有两个约定位置：共享 data/_registry/<id>.json（启动器/契约 runtime 用）
        # 与模块自己的 data/<id>/registry.json（模块自行登记时用）。两处都读，共享目录优先。
        record = None
        for candidate in (self.registry_dir / f"{module_id}.json",
                          self.root / "data" / module_id / "registry.json"):
            try:
                candidate_record = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(candidate_record, dict) and candidate_record.get("base_url"):
                record = candidate_record
                break
        if isinstance(record, dict) and record.get("base_url"):
            info["port"] = record.get("port")
            info["base_url"] = str(record["base_url"])
            cache_key = f"{info['base_url']}{service['health_path']}"
            cached = self._health_cache.get(cache_key)
            now = time.monotonic()
            if cached and now - cached[0] < HEALTH_CACHE_TTL:
                result, detail = cached[1], cached[2]
            else:
                result = self._probe_health(info["base_url"], service["health_path"])
                detail = ("/health 通过" if result else "无法连接 /health")
                self._health_cache[cache_key] = (now, result, detail)
            if result:
                info["health"], info["detail"] = "ok", detail
            else:
                info["health"], info["detail"] = "down", detail
        elif self._running(module_id):
            info["health"], info["detail"] = "starting", "正在启动，等待注册端口"
        return info

    def _external_alive(self, module_id, service=None):
        """模块**不是本进程启动的**，但确实在运行（由启动器 / 另一个管理台 / 另一个窗口拉起）。

        为什么必须有这个概念：`start_software.py` 拉起的模块是**另一个进程**的子进程，
        而管理台（`manager.py` / `start.bat`）只认识自己 spawn 过的进程，于是会把正在运行的
        模块显示成「未运行」。用户自然会去点「运行」，接着撞上模块自己的
        「检测到另一个运行实例」而失败 —— 表现就是「明明 --all 起过了，还要一个个手动启动」。

        判断依据用「有没有在跑」的证据（权威来源），而不是「谁启动的」：
          · 服务型模块：/health 探测通过。**刻意不看注册文件里的 pid** ——
            系统会复用 pid，残留注册文件的 pid 一旦被别的进程占用，就会误报「在运行」，
            反而把用户挡在「启动模块」之外（这比漏报更糟）。
          · 非服务型模块：没有 /health，只能看模块进程自己写的运行标记
            `data/_registry/<id>.run` 里的 pid；pid 已死就顺手把残留标记清掉，
            否则它会长期挡住这个模块的启动。
        """
        service = service if service is not None else self._service_info(module_id, self.modules / module_id)
        if service is not None:
            # 服务型模块只能以 /health 为外部实例的运行证据。
            # run_worker 也会为服务写 .run；崩溃残留的 pid 被浏览器等进程
            # 复用后仍然存活，不能因此覆盖失败的健康探测并禁用「运行」。
            return service.get("health") == "ok"
        try:
            from contracts.runtime import registry
        except ImportError:      # 契约包不可用时不猜，按「不是外部实例」处理
            return False
        # 非服务型模块没有 /health，只能看模块进程自己写的运行标记。
        path = self.registry_dir / f"{module_id}.run"
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        pid = record.get("pid")
        if isinstance(pid, int) and registry.process_alive(pid):
            return True
        try:
            path.unlink()        # 残留标记（进程已死）：清掉，否则会一直挡住启动
        except OSError:
            pass
        return False

    def list(self):
        with self.lock:
            found = self._discover()
            for module_id, info in found.items():
                record = self.processes.get(module_id)
                ours = self._running(module_id)
                info["service"] = self._service_info(module_id, self.modules / module_id)
                # 由别的进程拉起的实例也必须如实显示成「运行中」，否则管理台会把正在跑的
                # 模块显示成「未运行」+「/health 健康」这种自相矛盾的状态。
                info["external"] = bool(not ours and not info["error"]
                                        and self._external_alive(module_id, info["service"]))
                info["enabled"] = self._enabled(module_id)
                info["status"] = ("invalid" if info["error"] else
                                  "running" if (ours or info["external"]) else
                                  "failed" if record and record[0].exitcode not in (None, 0) else
                                  "completed" if record else "stopped")
                missing = [dep for dep in info["dependencies"] if dep not in found or found[dep]["error"]]
                info["warning"] = "缺少有效依赖：" + ", ".join(missing) if missing else ""
                if ours:
                    stopped = [dep for dep in info["dependencies"] if not self._active(dep)]
                    if stopped:
                        info["warning"] = "依赖已停止：" + ", ".join(stopped)
            return list(found.values())


    def _check_graph(self, module_id, trail=None):
        trail = trail or []
        if module_id in trail:
            raise ValueError("循环依赖：" + " → ".join(trail + [module_id]))
        info = self._get(module_id)
        for dep in info["dependencies"]:
            self._check_graph(dep, trail + [module_id])

    def _dependents(self, module_id, condition):
        return [key for key, info in self._discover().items()
                if module_id in info["dependencies"] and condition(key)]

    def _installed(self, module_id):
        """新安装的模块默认禁用并保留同名模块的历史配置。"""
        self.state.setdefault(module_id, {})["enabled"] = False
        self._save()
        return module_id

    def install(self, payload):
        with self.lock:
            return self._installed(install_zip(payload, self.modules))

    def install_folder(self, folder_name, files):
        with self.lock:
            return self._installed(install_folder(folder_name, files, self.modules))

    def enable(self, module_id):
        with self.lock:
            self._check_graph(module_id)
            missing = [dep for dep in self._get(module_id)["dependencies"] if not self._enabled(dep)]
            if missing:
                raise ValueError("请先启用依赖：" + ", ".join(missing))
            self.state.setdefault(module_id, {})["enabled"] = True
            self._save()

    def disable(self, module_id):
        with self.lock:
            self._get(module_id)
            users = self._dependents(module_id, self._enabled)
            if users:
                raise ValueError("请先禁用依赖此模块的模块：" + ", ".join(users))
            self.stop(module_id)
            self.state.setdefault(module_id, {})["enabled"] = False
            self._save()

    def start(self, module_id):
        with self.lock:
            self._check_graph(module_id)
            if self._running(module_id):
                return
            # 「已经在运行」必须排在「请先启用模块」前面：它明明在跑，却要求用户先去启用，
            # 只会把人带偏（启用之后也依然不能重复启动）。
            if self._external_alive(module_id):
                # 另一个进程已经把它拉起来了。再 spawn 一个只会被模块自己的
                # 「检测到另一个运行实例」拒绝，白起一次并让调用方以为失败。
                raise ValueError(f"{module_id} 已经在运行（由启动器或另一个窗口启动），不需要重复启动；"
                                 "要停止它请到那个窗口按 Ctrl+C，或关闭该窗口")
            if not self._enabled(module_id):
                raise ValueError("请先启用模块")
            missing = [dep for dep in self._get(module_id)["dependencies"] if not self._active(dep)]
            if missing:
                raise ValueError("请先运行依赖：" + ", ".join(missing))
            event = self.mp.Event()
            process = self.mp.Process(target=run_worker, args=(str(self.modules / module_id), self.config(module_id),
                str(self.root / "data" / module_id), str(self.root / "logs" / f"{module_id}.log"), event), daemon=True)
            process.start()
            old = self.processes.get(module_id)
            if old:
                old[0].close()
            self.processes[module_id] = (process, event)

    def _stop(self, module_id):
        record = self.processes.get(module_id)
        if record:
            process, event = record
            event.set()
            process.join(2)
            if process.is_alive():
                process.terminate()
                process.join(2)
            if process.is_alive():
                raise ValueError("模块未能停止，请稍后重试")
            process.close()
            del self.processes[module_id]

    def stop(self, module_id):
        with self.lock:
            validate_id(module_id)
            users = self._dependents(module_id, self._active)
            if users:
                raise ValueError("请先停止依赖此模块的模块：" + ", ".join(users))
            if module_id not in self.processes and self._external_alive(module_id):
                # 不是本进程启动的：_stop() 会静默什么都不做，那会让用户以为已经停掉了。
                raise ValueError(f"{module_id} 由启动器（start_software）或另一个窗口启动，本页面停不掉它；"
                                 "请到那个窗口按 Ctrl+C，或关闭该窗口")
            self._stop(module_id)

    def config(self, module_id):
        with self.lock:
            self._get(module_id)
            return json.loads(json.dumps(self.state.get(module_id, {}).get("config", {})))

    def configure(self, module_id, config):
        with self.lock:
            self._get(module_id)
            if self._active(module_id):
                raise ValueError("请先停止模块再修改配置")
            if not isinstance(config, dict):
                raise ValueError("配置必须是 JSON 对象")
            self.state.setdefault(module_id, {})["config"] = config
            self._save()

    def logs(self, module_id):
        with self.lock:
            validate_id(module_id)
            path = self.root / "logs" / f"{module_id}.log"
            if not path.exists():
                return ""
            with path.open("rb") as stream:
                stream.seek(max(0, path.stat().st_size - 65536))
                return stream.read(65536).decode("utf-8", errors="replace")

    def uninstall(self, module_id):
        with self.lock:
            validate_id(module_id)
            users = self._dependents(module_id, lambda _: True)
            if users:
                raise ValueError("请先移除依赖此模块的模块：" + ", ".join(users))
            if self._enabled(module_id) or self._active(module_id):
                raise ValueError("请先禁用模块再卸载")
            source = self.modules / module_id
            if not source.exists() or source.is_symlink() or source.resolve().parent != self.modules.resolve():
                raise ValueError("模块目录不存在或不是安全的本地目录")
            source.rename(self.root / ".trash" / f"{module_id}-{uuid.uuid4().hex}")

    def close(self):
        with self.lock:
            for _, event in self.processes.values():
                event.set()
            for module_id in list(self.processes):
                self._stop(module_id)
