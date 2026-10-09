import io
import re
import shutil
import stat
import uuid
import zipfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

from .manifest import RESERVED, read_manifest

MAX_UPLOAD = 20 * 1024 * 1024
MAX_EXPANDED = 80 * 1024 * 1024
MAX_ENTRIES = 2000
# 从文件夹安装时页面会把内容编码为 JSON 文本，体积约为原始内容的 1.34 倍。
MAX_FOLDER_UPLOAD = MAX_EXPANDED + MAX_EXPANDED // 2
# 本地开发目录常见的缓存文件，安装时忽略，避免 __pycache__ 之类的残留导致失败。
IGNORED = ("__pycache__", ".git")


def _ignored(name):
    parts = name.rstrip("/").split("/")
    return any(part in IGNORED for part in parts) or name.lower().endswith((".pyc", ".pyo"))


@contextmanager
def _staging_dir(modules: Path):
    """在 .staging 下建立独占暂存目录；成功或失败后都清理，残留失败不掩盖真实错误。"""
    staging = modules.parent / ".staging"
    staging.mkdir(parents=True, exist_ok=True)
    temp = staging / f"install-{uuid.uuid4().hex}"
    temp.mkdir()
    try:
        yield temp
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def _safe_parts(raw):
    """按 ZIP 与文件夹通用的规则拆分相对路径，返回各级目录名。"""
    if not isinstance(raw, str):
        raise ValueError("路径必须是文本")
    path = PurePosixPath(raw)
    parts = raw.rstrip("/").split("/")
    if (not parts or path.is_absolute() or "\\" in raw or "\x00" in raw or
            any(p in ("", ".", "..") or re.search(r'[<>:"|?*\x00-\x1f]', p) or
                p.endswith((".", " ")) or p.split(".")[0].lower() in RESERVED for p in parts)):
        raise ValueError(f"路径不安全：{raw}")
    return parts


def _write_entries(entries, temp):
    """把 (相对路径, 内容) 写入暂存目录；路径安全已在调用前校验。"""
    root = Path(temp)
    for name, data in entries:
        target = root.joinpath(*_safe_parts(name))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def _module_root(temp):
    """定位模块根目录：文件直接在暂存根目录，或只含唯一一层模块目录。"""
    root = Path(temp)
    if (root / "manifest.json").is_file():
        return root
    children = list(root.iterdir())
    if len(children) == 1 and children[0].is_dir() and (children[0] / "manifest.json").is_file():
        return children[0]
    raise ValueError("模块必须在根目录直接包含 manifest.json，或只含一层模块目录")


def _finalize(candidate, module_id, modules: Path):
    """校验清单后把模块目录原子移动到 modules/<id>，不覆盖同名模块。"""
    manifest = read_manifest(candidate)
    if module_id is not None and manifest["id"] != module_id:
        raise ValueError(f"文件夹名必须与清单 id 一致：应为 {manifest['id']}，实际为 {module_id}")
    destination = modules / manifest["id"]
    if destination.exists():
        raise ValueError("同名模块已存在，请先禁用并卸载旧版本")
    candidate.rename(destination)
    return manifest["id"]


def install_zip(payload: bytes, modules: Path):
    if len(payload) > MAX_UPLOAD:
        raise ValueError("ZIP 最大允许 20 MB")
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > MAX_ENTRIES:
                raise ValueError(f"ZIP 为空或文件数量超过 {MAX_ENTRIES}")
            if sum(x.file_size for x in entries if not _ignored(x.orig_filename)) > MAX_EXPANDED:
                raise ValueError("ZIP 解压后不能超过 80 MB")
            seen = set()
            for item in entries:
                raw = item.orig_filename
                if _ignored(raw):
                    continue
                _safe_parts(raw)
                mode = item.external_attr >> 16
                if stat.S_ISLNK(mode) or stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
                    raise ValueError(f"ZIP 含不安全路径或特殊文件：{raw}")
                key = str(PurePosixPath(raw)).casefold()
                if key in seen:
                    raise ValueError(f"ZIP 含重复路径：{raw}")
                seen.add(key)
                if item.flag_bits & 1:
                    raise ValueError("不支持加密 ZIP")
            with _staging_dir(modules) as temp:
                archive.extractall(temp)
                return _finalize(_module_root(temp), None, modules)
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError, OSError) as exc:
        raise ValueError(f"无法安装 ZIP：{exc}") from exc


def install_folder(folder_name, files, modules: Path):
    """从浏览器选择的本地文件夹安装，校验规则与 ZIP 安装保持一致。"""
    if not isinstance(files, dict):
        raise ValueError("files 必须是相对路径到文本内容的映射")
    if len(files) > MAX_ENTRIES:
        raise ValueError(f"文件夹文件数量超过 {MAX_ENTRIES}")
    parts = _safe_parts(folder_name)
    if len(parts) != 1:
        raise ValueError("文件夹名必须是单层名称")
    entries = []
    total = 0
    for name, content in files.items():
        if _ignored(name):
            continue
        _safe_parts(name)
        if not isinstance(content, str):
            raise ValueError(f"文件内容必须是文本：{name}")
        try:
            data = content.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValueError(f"文件内容不是有效文本：{name}") from exc
        total += len(data)
        if total > MAX_EXPANDED:
            raise ValueError("文件夹内容不能超过 80 MB")
        entries.append((name, data))
    if not entries:
        raise ValueError("文件夹为空，或只包含被忽略的缓存文件")
    try:
        with _staging_dir(modules) as temp:
            _write_entries(entries, temp)
            return _finalize(_module_root(temp), folder_name, modules)
    except (RuntimeError, OSError) as exc:
        raise ValueError(f"无法安装文件夹：{exc}") from exc
