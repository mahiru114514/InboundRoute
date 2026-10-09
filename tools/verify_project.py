"""从任意工作目录执行项目回归；每组独立进程，失败时返回非零退出码。"""
from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    # Python 与 Node 统一输出 UTF-8，Windows 重定向的验收日志也能直接阅读。
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    child_env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    commands = [
        [sys.executable, '-m', 'unittest', 'discover', '-s', folder]
        for folder in ('tests', 'modules/rules_engine/tests', 'modules/route_adapter/tests',
                       'modules/offline_kit/tests', 'modules/recommendation_engine/tests')
    ]
    node = shutil.which('node')
    if node is None:
        print('缺少 Node.js，无法运行前端测试。', file=sys.stderr)
        return 1
    commands.extend([node, str(path.relative_to(ROOT))] for path in sorted((ROOT / 'tests').glob('*.test.js')))
    commands.extend([
        [sys.executable, 'contracts/scripts/validate.py'],
        [sys.executable, 'contracts/scripts/check_runtime.py'],
        [sys.executable, 'contracts/scripts/generate.py', '--check'],
        [sys.executable, 'start_software.py', '--list'],
    ])
    failed = []
    for command in commands:
        label = ' '.join(command[1:])
        print(f'\n[验证] {label}', flush=True)
        result = subprocess.run(command, cwd=ROOT, env=child_env)
        if result.returncode:
            failed.append((label, result.returncode))
    print(f'\n验证组数：{len(commands)}；失败组数：{len(failed)}', flush=True)
    for label, code in failed:
        print(f'  失败（退出码 {code}）：{label}')
    return int(bool(failed))


if __name__ == '__main__':
    raise SystemExit(main())
