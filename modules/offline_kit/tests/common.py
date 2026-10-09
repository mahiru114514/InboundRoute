"""offline_kit 测试公共工具。"""
import os
import sys

_MODULE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WORKSPACE = os.path.dirname(os.path.dirname(_MODULE_DIR))
for _p in (_MODULE_DIR, _WORKSPACE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

WORKSPACE = _WORKSPACE
MODULE_DIR = _MODULE_DIR