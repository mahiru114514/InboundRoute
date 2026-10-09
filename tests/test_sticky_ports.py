"""端口粘性：模块重启必须复用上一次登记的端口（工程体验缺陷修复）。

缺陷现象：每次启动模块端口都会变，旧链接（书签 / 分享出去的深链
`http://127.0.0.1:<port>/…`）在重启后一律失效。

修法：`resolve_port()` 在「config 里没有显式 port」时，尝试复用该模块上一次注册记录里的
端口，但有三条安全约束——
    1. 上一任实例还活着（pid 存活）就不复用，端口是它的；
    2. 端口现在被别人占着就不复用（真实绑定探测，不能只看注册文件）；
    3. 任何一步失败都回落到 0（系统分配），绝不让端口复用把模块启动搞崩。

这个文件只钉这些行为，外加「显式配置仍然优先」的向后兼容。
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for candidate in (str(ROOT), str(ROOT / "contracts")):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from contracts.runtime import registry  # noqa: E402

MODULE_ID = "sticky_svc"


def free_port() -> int:
    """向系统要一个当前空闲的端口再立刻释放（测试里不写死端口号，避免环境差异）。"""
    probe = registry.bind_socket("127.0.0.1", 0)
    try:
        return probe.getsockname()[1]
    finally:
        probe.close()


def pick_dead_pid() -> int:
    """找一个**确定不在运行**的 pid（模拟「上一任实例已经退出」的注册文件）。

    从常见 pid_max 上限附近往下退，用 registry 自己的判活逻辑确认；
    不给任何进程发信号，因此不会误伤。
    """
    candidate = 4194304
    while candidate > 1:
        if not registry.process_alive(candidate):
            return candidate
        candidate -= 1
    raise AssertionError("找不到已退出的 pid")


class StickyPortTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.workspace = Path(self._temp.name)

    # ------------------------------------------------------------ 工具
    def write_record(self, port, pid=None):
        """写一份注册记录；默认 pid 取「已退出」的值，即模块正常停止后的残留状态。"""
        registration = registry.build_registration(MODULE_ID, port, registry.new_token())
        registration.pid = pick_dead_pid() if pid is None else pid
        registry.write(registration, self.workspace)
        return registration

    def resolve(self, config=None):
        return registry.resolve_port(config or {}, MODULE_ID, self.workspace)

    # ------------------------------------------------------------ 用例
    def test_first_start_without_config_allocates_and_records(self):
        """首次启动：没有配置也没有注册文件 → 0（系统分配），绑定后的真实端口要能登记下来。"""
        self.assertIsNone(registry.try_read(self.workspace, MODULE_ID))
        self.assertEqual(self.resolve(), 0)

        server = registry.bind_socket("127.0.0.1", 0)   # 模块真正的启动路径
        try:
            actual = server.getsockname()[1]
            self.assertGreater(actual, 0)
            registry.write(registry.build_registration(MODULE_ID, actual, registry.new_token()),
                           self.workspace)
        finally:
            server.close()

        record = registry.read(self.workspace, MODULE_ID)
        self.assertEqual(record.port, actual)
        self.assertEqual(record.base_url, f"http://127.0.0.1:{actual}")

    def test_restart_reuses_recorded_port(self):
        """上一次已退出 → 重启（同一 workspace）拿回同一个端口。"""
        server = registry.bind_socket("127.0.0.1", 0)
        try:
            actual = server.getsockname()[1]
        finally:
            server.close()
        self.write_record(actual, pid=pick_dead_pid())

        self.assertEqual(self.resolve(), actual)
        # 连续两次调用（相当于连续两次重启）都要稳定返回同一个端口
        self.assertEqual(self.resolve(), actual)

    def test_clean_stop_preserves_port_without_live_registration(self):
        actual = free_port()
        self.write_record(actual)
        registry.remove(self.workspace, MODULE_ID)
        self.assertIsNone(registry.try_read(self.workspace, MODULE_ID))
        self.assertEqual(self.resolve(), actual)
        # 端口历史不应被 discover 误认为正在运行的服务。
        self.assertFalse(registry.registry_path(self.workspace, MODULE_ID).exists())

    def test_clean_stop_history_does_not_reuse_occupied_port(self):
        holder = registry.bind_socket('127.0.0.1', 0)
        self.addCleanup(holder.close)
        actual = holder.getsockname()[1]
        self.write_record(actual)
        registry.remove(self.workspace, MODULE_ID)
        self.assertEqual(self.resolve(), 0)

    def test_occupied_remembered_port_falls_back_to_zero(self):
        """记住的端口被别人占着 → 回落 0，而不是抛异常或硬用这个端口。"""
        # 占用方带上 SO_REUSEADDR，和真实模块的 bind_socket() 一致：
        # 这正是「用 SO_REUSEADDR 探测会误判成空闲」的那种情况，必须能识别出来。
        holder = registry.bind_socket("127.0.0.1", 0)
        port = holder.getsockname()[1]
        try:
            self.write_record(port, pid=pick_dead_pid())
            self.assertEqual(self.resolve(), 0)
        finally:
            holder.close()

        # 占用方走了，端口又能复用了
        self.assertEqual(self.resolve(), port)

    def test_explicit_config_port_still_wins(self):
        """config["port"] 永远优先（原契约不变）：即便记录里记着别的端口。"""
        remembered = free_port()
        self.write_record(remembered, pid=pick_dead_pid())
        self.assertEqual(self.resolve({"port": 51420}), 51420)
        self.assertEqual(self.resolve({"port": "51420"}), 51420)   # 字符串写法也认
        # 非法 / 为 0 的显式配置不算「显式」→ 回到复用逻辑
        self.assertEqual(self.resolve({"port": "0"}), remembered)
        self.assertEqual(self.resolve({"port": "abc"}), remembered)

    def test_explicit_config_port_wins_even_when_occupied(self):
        """显式端口连「占用中 / 主人还活着」都不看——契约就是配了就用。"""
        holder = registry.bind_socket("127.0.0.1", 0)
        port = holder.getsockname()[1]
        try:
            self.write_record(port, pid=os.getpid())
            self.assertEqual(self.resolve({"port": port}), port)
        finally:
            holder.close()

    def test_live_owner_port_is_not_reused(self):
        """注册文件里的 pid 还活着（用本进程的 pid）→ 不许复用它的端口。"""
        self.assertTrue(registry.process_alive(os.getpid()))
        self.write_record(free_port(), pid=os.getpid())
        self.assertEqual(self.resolve(), 0)

    def test_dead_owner_port_is_reused(self):
        """同一个端口、同一个 workspace，只是因为主人已退出 → 可以复用。"""
        self.assertFalse(registry.process_alive(pick_dead_pid()))
        remembered = free_port()
        self.write_record(remembered, pid=pick_dead_pid())
        self.assertEqual(self.resolve(), remembered)

    def test_stale_or_broken_record_never_crashes_resolution(self):
        """坏注册文件 / 非法端口字段 → 一律回落 0，不抛异常。"""
        registry.registry_dir(self.workspace).mkdir(parents=True, exist_ok=True)
        path = registry.registry_path(self.workspace, MODULE_ID)
        path.write_text("{ 这不是 JSON", encoding="utf-8")
        self.assertEqual(self.resolve(), 0)

        self.write_record(0, pid=pick_dead_pid())        # 端口字段非法
        self.assertEqual(self.resolve(), 0)

    def test_backwards_compatible_signature(self):
        """老调用（只传 config）行为不变：缺省 / 非法都是 0；只给 module_id 也不去猜。"""
        self.assertEqual(registry.resolve_port(None), 0)
        self.assertEqual(registry.resolve_port({"port": "0"}), 0)
        self.assertEqual(registry.resolve_port({"port": "abc"}), 0)
        self.assertEqual(registry.resolve_port({"port": 4711}), 4711)
        self.assertEqual(registry.resolve_port({}, MODULE_ID), 0)


if __name__ == "__main__":
    unittest.main()
