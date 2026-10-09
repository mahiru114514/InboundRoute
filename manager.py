"""本机可视化模块管理入口；不需要第三方包。"""
import argparse
import multiprocessing
import threading
import webbrowser
from pathlib import Path

from core.manager import Manager
from core.server import create_server


def main():
    parser = argparse.ArgumentParser(description="启动可视化模块管理页面")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    manager = Manager(Path(__file__).resolve().parent)
    try:
        server = create_server(manager, args.port)
    except OSError:
        manager.close()
        raise SystemExit(f"端口 {args.port} 无法使用。请检查管理页面是否已经打开，或更换端口。")
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"模块工作台：{url}", flush=True)
    if not args.no_browser:
        threading.Timer(.5, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        manager.close()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
