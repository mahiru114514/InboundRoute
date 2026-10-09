#!/usr/bin/env python3
"""InboundRoute 软件启动器 —— 一条命令拉起整套软件。

它在进程内创建 Manager（与 manager.py 同一实现），因此**不会**和单独运行的管理页面抢状态文件；
启动哪些模块完全由「工作台上已安装 + 已启用的模块」决定，并严格按 manifest 的 dependencies 顺序启动。

用法：
    python start_software.py                 # 启动已启用的全部模块（含依赖），并打开主界面
    python start_software.py --list          # 只打印启动计划，不启动任何东西
    python start_software.py --all           # 把已安装的模块全部启用并启动（首次体验用）
    python start_software.py --only trip_engine,rules_engine
    python start_software.py --exclude greeting
    python start_software.py --no-browser    # 不自动打开浏览器
    python start_software.py --port 8766     # 工作台端口
    python start_software.py --stop          # 逆序停止所有模块
    python start_software.py --status        # 打印各模块状态与健康检查结果

约定（manifest.json 可选字段，见 contracts/MODULE_RUNTIME.md）：
    "service": {"enabled": true, "health_path": "/health", "open_path": "/", "title": "..."}
    非服务模块（不起 HTTP）不需要该字段，启动器只保证其进程运行，不做健康探测。

退出码：0 成功；1 参数/状态错误；2 工作台端口被占用；3 有模块启动失败；130 用户中断。
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.manager import Manager  # noqa: E402
from core.server import create_server  # noqa: E402

REGISTRY_DIRNAME = "_registry"


# ---------------------------------------------------------------- 工具

def read_manifests(root: Path) -> dict[str, dict]:
    """直接读磁盘上的清单，拿到 service 元信息（宿主只认 id/name/version/description/dependencies）。"""
    found: dict[str, dict] = {}
    modules_dir = root / "modules"
    if not modules_dir.is_dir():
        return found
    for path in sorted(modules_dir.iterdir()):
        if not path.is_dir() or path.name.startswith("."):
            continue
        manifest_path = path / "manifest.json"
        try:
            found[path.name] = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            found[path.name] = {}
    return found


def optional_dependencies(manifests: dict[str, dict], module_id: str) -> list[str]:
    """清单里声明的「可选依赖」：未安装/未运行不影响本模块启动（模块自行降级展示）。

    放在 manifest 的 service.optional_dependencies 里，因此不会被宿主的依赖保护当成硬依赖。
    """
    service = manifests.get(module_id, {}).get("service")
    value = service.get("optional_dependencies") if isinstance(service, dict) else None
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def topo_order(ids: list[str], manifests: dict[str, dict], installed: set[str]) -> list[str]:
    """按依赖拓扑排序；**硬依赖**缺失或成环时抛出明确错误。

    可选依赖不参与硬校验，也不要求被启动；但它若恰好也在启动列表里，顺序仍要排在前面。
    """
    order: list[str] = []
    state: dict[str, int] = {}

    def visit(module_id: str, trail: list[str]) -> None:
        if module_id in state and state[module_id] == 2:
            return
        if module_id in trail:
            raise ValueError("检测到循环依赖：" + " → ".join(trail + [module_id]))
        if module_id not in installed:
            raise ValueError(f"依赖缺失：{' → '.join(trail + [module_id])} 中的 {module_id} 未安装")
        state[module_id] = 1
        for dependency in manifests.get(module_id, {}).get("dependencies") or []:
            visit(dependency, trail + [module_id])
        state[module_id] = 2
        order.append(module_id)

    for module_id in ids:
        visit(module_id, [])

    # 可选依赖若也在启动列表里，把它挪到被依赖方之前（保持依赖先起）
    changed = True
    while changed:
        changed = False
        for module_id in list(order):
            for optional in optional_dependencies(manifests, module_id):
                if optional not in order:
                    continue
                if order.index(optional) > order.index(module_id):
                    order.remove(optional)
                    order.insert(order.index(module_id), optional)
                    changed = True
    return order


def dependency_levels(order: list[str], manifests: dict[str, dict]) -> list[list[str]]:
    """把拓扑序切成「层」：同一层内的模块互不依赖，可并行启动（宿主逐个启动）。"""
    level_of = {module_id: 0 for module_id in order}
    changed = True
    while changed:
        changed = False
        for module_id in order:
            related = list(manifests.get(module_id, {}).get("dependencies") or [])
            related += optional_dependencies(manifests, module_id)
            for dependency in related:
                if dependency in level_of and level_of[module_id] <= level_of[dependency]:
                    level_of[module_id] = level_of[dependency] + 1
                    changed = True
    levels: list[list[str]] = []
    for module_id in order:
        index = level_of[module_id]
        while len(levels) <= index:
            levels.append([])
        levels[index].append(module_id)
    return [level for level in levels if level]


def registration_path(root: Path, module_id: str) -> Path:
    return root / "data" / REGISTRY_DIRNAME / f"{module_id}.json"


def probe_health(base_url: str, path: str = "/health", timeout: float = 2.0) -> tuple[bool, str]:
    url = base_url.rstrip("/") + (path or "/health")
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
        return True, body.strip()[:120]
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except (urllib.error.URLError, OSError) as exc:
        return False, type(exc).__name__


def open_url_for(root: Path, manifest: dict) -> str | None:
    """服务型模块：从注册文件读 base_url，拼上 open_path。"""
    service = manifest.get("service") or {}
    if not service.get("enabled"):
        return None
    path = registration_path(root, manifest.get("id", ""))
    if not path.is_file():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return record.get("base_url", "").rstrip("/") + (service.get("open_path") or "/")


def human_status(status: str) -> str:
    return {"running": "运行中", "stopped": "未运行", "failed": "运行异常",
            "completed": "已完成", "invalid": "格式异常"}.get(status, status)


# ---------------------------------------------------------------- 启动计划

def build_plan(args, manager: Manager, manifests: dict[str, dict]) -> tuple[list[str], dict[str, bool]]:
    """返回 (按依赖排序的启动列表, {模块: 是否需要先启用})。"""
    cards = {card["id"]: card for card in manager.list()}
    installed = set(cards)
    if not installed:
        print("没有发现任何模块。请把模块放进 modules/ ，或先用 --all 前先安装模块。")
        return [], {}

    if args.only:
        wanted = [item.strip() for item in args.only.split(",") if item.strip()]
        unknown = [item for item in wanted if item not in installed]
        if unknown:
            raise ValueError("--only 指定了未安装的模块：" + ", ".join(unknown))
    elif args.all:
        wanted = sorted(installed)
    else:
        wanted = [module_id for module_id, card in cards.items() if card["enabled"]]
        if not wanted and sys.stdin.isatty():
            answer = input("当前没有已启用的模块。要启用并启动全部模块吗？[y/N] ").strip().lower()
            if answer in ("y", "yes"):
                wanted = sorted(installed)

    wanted = [module_id for module_id in wanted if module_id not in set(args.exclude or [])]
    wanted = [module_id for module_id in wanted if not cards[module_id]["error"]]
    invalid = [module_id for module_id, card in cards.items() if card["error"]]
    if invalid:
        # 空目录/半成品目录以前只显示截断到 40 字符的英文异常，使用者看不出下一步该做什么。
        # 这里完整打印原因，并明确「跳过它不影响其他模块」。
        print("以下模块目录未安装完成，已跳过（不影响其他模块启动）：")
        for item in invalid:
            print(f"  · {item}：{cards[item]['error']}")

    order = topo_order(wanted, manifests, installed)
    need_enable = {module_id: not cards[module_id]["enabled"] for module_id in order}
    return order, need_enable


def print_plan(root: Path, manager: Manager, order: list[str], need_enable: dict[str, bool],
               manifests: dict[str, dict]) -> None:
    cards = {card["id"]: card for card in manager.list()}
    print(f"工作台根目录：{root}")
    print(f"启动计划（{len(order)} 个模块，按依赖分层；同一层互不依赖）：")
    for index, level in enumerate(dependency_levels(order, manifests), start=1):
        print(f"  ── 第 {index} 层 ──")
        print(f"     {'模块':<16}{'状态':<10}{'服务':<8}{'启用':<8}{'依赖':<24}名称")
        for module_id in level:
            card = cards[module_id]
            service = manifests.get(module_id, {}).get("service") or {}
            dependencies = ",".join(manifests.get(module_id, {}).get("dependencies") or []) or "—"
            optional = optional_dependencies(manifests, module_id)
            if optional:
                dependencies += f"（可选：{','.join(optional)}）"
            print(f"     {module_id:<16}{human_status(card['status']):<10}"
                  f"{('是' if service.get('enabled') else '否'):<8}"
                  f"{('将启用' if need_enable[module_id] else '已启用'):<8}"
                  f"{dependencies:<40}{manifest_name(manifests, module_id) or card['name']}")


def manifest_name(manifests: dict[str, dict], module_id: str) -> str:
    return (manifests.get(module_id) or {}).get("name", "")


# ---------------------------------------------------------------- 动作

def start_all(args, manager: Manager, order: list[str], need_enable: dict[str, bool],
              manifests: dict[str, dict]) -> list[str]:
    started: list[str] = []
    for module_id in order:
        card = {item["id"]: item for item in manager.list()}[module_id]
        try:
            if card["status"] == "running":
                # 已经在运行就不要重复启动：可能是本进程起过的，也可能是**另一个窗口**
                # （上一次没关掉的启动器、或管理台页面）拉起来的。
                # 重复 spawn 的实例会被模块自己的「检测到另一个运行实例」拒绝，上一次的代码
                # 正是在这里失败 → 整批回滚退出 → 用户只好一个个手动启动。所以这里必须跳过。
                note = "（由其他窗口启动）" if card.get("external") else ""
                print(f"[已在运行] {module_id}{note}")
                started.append(module_id)
                continue
            if need_enable.get(module_id):
                manager.enable(module_id)
                print(f"[启用] {module_id}")
            manager.start(module_id)
            print(f"[启动] {module_id}")
            started.append(module_id)
        except (ValueError, OSError) as exc:
            print(f"[失败] {module_id}：{exc}")
            return started
    return started


def start_layers(args, manager: Manager, order: list[str], need_enable: dict[str, bool],
                 manifests: dict[str, dict], timeout: float) -> list[str]:
    """按依赖层启动：每层起来并探活通过后，再启动依赖它的下一层。

    为什么必须分层等：被依赖方还没来得及写下注册文件时，依赖方就已经去读注册表了，
    于是它可能读到**上一轮遗留、指向已死端口**的注册文件，然后白等到超时退出
    （真实故障：logs/rules_engine.log 2026-09-29 22:52，rules_engine 等 53559，
    trip_engine 实际登记在 53182）。模块侧现在也会重读注册表兜底，这里让它不必兜底。

    返回已启动的模块列表；某一层没起全就立即返回，由调用方回收。
    """
    started: list[str] = []
    levels = dependency_levels(order, manifests)
    for index, level in enumerate(levels):
        level_started = start_all(args, manager, level, need_enable, manifests)
        started.extend(level_started)
        if len(level_started) != len(level):
            return started
        if index == len(levels) - 1:
            break
        health = wait_ready(level_started, manifests, timeout=timeout)
        for module_id, (ok, detail) in health.items():
            if not ok:
                print(f"  · {module_id} 尚未就绪（{detail}）；依赖它的模块会继续等待它")
    return started


def wait_ready(started: list[str], manifests: dict[str, dict], timeout: float = 10.0) -> dict[str, tuple[bool, str]]:
    """对所有服务型模块**并发轮询**健康检查（最多等 timeout 秒）。

    这里的等待是「全部一起等」而不是「一个一个等」：N 个模块各自的等待窗口重叠，
    总耗时约等于 timeout，而不是 N × timeout。
    """
    results: dict[str, tuple[bool, str]] = {}
    pending: dict[str, tuple[str, str]] = {}   # module_id -> (base_url, health_path)
    for module_id in started:
        service = manifests.get(module_id, {}).get("service") or {}
        if not service.get("enabled"):
            results[module_id] = (True, "非服务模块（不探测）")
            continue
        pending[module_id] = ("", service.get("health_path") or "/health")

    deadline = time.monotonic() + timeout
    last: dict[str, str] = {module_id: "等待注册文件" for module_id in pending}
    while pending and time.monotonic() < deadline:
        for module_id in list(pending):
            base_url, health_path = pending[module_id]
            if not base_url:
                path = registration_path(ROOT, module_id)
                if not path.is_file():
                    continue
                try:
                    base_url = json.loads(path.read_text(encoding="utf-8")).get("base_url", "")
                except (OSError, json.JSONDecodeError) as exc:
                    last[module_id] = type(exc).__name__
                    continue
                if not base_url:
                    continue
                pending[module_id] = (base_url, health_path)
            ok, detail = probe_health(base_url, health_path, timeout=0.8)
            if ok:
                results[module_id] = (True, base_url)
                del pending[module_id]
            else:
                last[module_id] = detail
        if pending:
            time.sleep(0.25)

    for module_id, detail in last.items():
        if module_id in pending:
            results[module_id] = (False, detail)
    return results


def print_status(manager: Manager, manifests: dict[str, dict]) -> None:
    print(f"  {'模块':<16}{'状态':<10}{'健康':<8}地址")
    for card in manager.list():
        module_id = card["id"]
        service = manifests.get(module_id, {}).get("service") or {}
        if service.get("enabled"):
            path = registration_path(ROOT, module_id)
            if path.is_file():
                try:
                    record = json.loads(path.read_text(encoding="utf-8"))
                    ok, detail = probe_health(record.get("base_url", ""), service.get("health_path") or "/health")
                    health = "正常" if ok else "异常"
                    address = record.get("base_url", "")
                except (OSError, json.JSONDecodeError):
                    health, address = "未知", ""
            else:
                health, address = "无注册", ""
        else:
            health, address = "—", ""
        print(f"  {module_id:<16}{human_status(card['status']):<10}{health:<8}{address}")


def stop_all(manager: Manager) -> None:
    cards = manager.list()
    order: list[str] = []
    state: dict[str, int] = {}

    def visit(module_id: str) -> None:
        if state.get(module_id) == 2 or module_id not in {c["id"] for c in cards}:
            return
        state[module_id] = 1
        for dependency in next((c["dependencies"] for c in cards if c["id"] == module_id), []):
            visit(dependency)
        state[module_id] = 2
        order.append(module_id)

    for card in cards:
        visit(card["id"])
    for module_id in reversed(order):
        try:
            manager.stop(module_id)
            print(f"[停止] {module_id}")
        except KeyboardInterrupt:
            # 收尾过程中再按一次 Ctrl+C：忽略，继续把剩下的模块停干净
            continue
        except (ValueError, OSError) as exc:
            if "不存在" not in str(exc):
                print(f"[跳过] {module_id}：{exc}")


# ---------------------------------------------------------------- 主流程

def main() -> int:
    parser = argparse.ArgumentParser(description="InboundRoute 软件启动器：按工作台里已启用的模块拉起整套软件")
    parser.add_argument("--port", type=int, default=8765, help="工作台端口（默认 8765）")
    parser.add_argument("--list", action="store_true", help="只打印启动计划")
    parser.add_argument("--status", action="store_true", help="打印模块状态与健康检查结果后退出")
    parser.add_argument("--stop", action="store_true", help="逆序停止所有模块后退出")
    parser.add_argument("--all", action="store_true", help="启用并启动所有已安装模块")
    parser.add_argument("--only", default="", help="只启动指定模块（逗号分隔，会自动带上依赖）")
    parser.add_argument("--exclude", action="append", default=[], help="排除某模块（可重复）")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--no-server", action="store_true", help="不启动工作台 Web UI（只拉起模块）")
    parser.add_argument("--timeout", type=float, default=10.0, help="服务就绪等待秒数（默认 10，并发等待）")
    args = parser.parse_args()

    try:
        manager = Manager(ROOT)
    except ValueError as exc:
        print(f"工作台状态文件有问题：{exc}")
        return 1

    manifests = read_manifests(ROOT)

    if args.status:
        print(f"工作台根目录：{ROOT}")
        print_status(manager, manifests)
        manager.close()
        return 0

    if args.stop:
        print(f"停止所有模块：{ROOT}")
        stop_all(manager)
        manager.close()
        return 0

    try:
        order, need_enable = build_plan(args, manager, manifests)
    except ValueError as exc:
        print(f"启动计划失败：{exc}")
        manager.close()
        return 1
    if not order:
        manager.close()
        return 0

    print_plan(ROOT, manager, order, need_enable, manifests)
    if args.list:
        manager.close()
        return 0

    if not args.no_server:
        try:
            server = create_server(manager, args.port)
        except OSError:
            print(f"端口 {args.port} 无法使用：可能已有一个工作台在运行。")
            print("  · 想复用现有工作台：关闭本脚本启动的模块会自动停止；")
            print("  · 想直接看状态：python start_software.py --status")
            manager.close()
            return 2
        print(f"工作台页面：http://127.0.0.1:{server.server_port}")
        if not args.no_browser:
            threading.Timer(0.8, webbrowser.open, args=(f"http://127.0.0.1:{server.server_port}",)).start()
        threading.Thread(target=server.serve_forever, daemon=True).start()

    print("\n正在启动模块……")
    started = start_layers(args, manager, order, need_enable, manifests, args.timeout)
    if len(started) != len(order):
        print("部分模块未能启动，正在回收已启动的模块……")
        for module_id in reversed(started):
            try:
                manager.stop(module_id)
            except (ValueError, OSError):
                pass
        if not args.no_server:
            print(f"提示：工作台页面 http://127.0.0.1:{args.port} 仍在运行，关闭本窗口即可。")
        manager.close()
        return 3

    print("\n等待服务就绪……")
    health = wait_ready(started, manifests, timeout=args.timeout)
    print(f"  {'模块':<16}{'健康':<8}地址/说明")
    for module_id in started:
        ok, detail = health.get(module_id, (False, "未探测"))
        print(f"  {module_id:<16}{('正常' if ok else '未就绪'):<8}{detail}")

    main_url = next((open_url_for(ROOT, {**manifests[module_id], "id": module_id})
                     for module_id in reversed(order)
                     if manifests.get(module_id, {}).get("service", {}).get("open_path")), None)
    if main_url:
        print(f"\n软件主界面：{main_url}")
        if not args.no_browser:
            webbrowser.open(main_url)

    if any(not ok for ok, _ in health.values()):
        print("\n有服务模块未通过健康检查（可能仍在启动）。可用 --status 复查。")

    print("\n按 Ctrl+C 停止全部模块并退出。")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n收到中断，正在停止模块……")
    finally:
        stop_all(manager)
        manager.close()
    return 130


if __name__ == "__main__":
    # 注意：本脚本会被模块子进程以 __main__ 重新 import（Windows spawn 语义），
    # 因此所有执行逻辑都放在 main() 里，顶层只允许定义。
    sys.exit(main())
