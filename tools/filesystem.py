"""文件系统工具:全部限制在 workspace 内,越界抛 ToolSecurityError。"""
import logging
import os

from ..config import settings
from ..core.registry import tool
from ..core.security import resolve_within_workspace

logger = logging.getLogger("harness.tools.filesystem")


@tool(description="读取文本文件,返回前 max_chars 个字符。")
def read_file(path: str, max_chars: int = 20000) -> str:
    """读取文本文件内容。

    :param path: 文件路径,相对 workspace 或绝对路径(必须在 workspace 内)
    :param max_chars: 最多返回的字符数
    """
    p = resolve_within_workspace(path, settings.WORKSPACE)
    if not p.exists():
        return f"ERROR: 文件不存在: {p}"
    if p.is_dir():
        return f"ERROR: 这是目录,请用 list_dir: {p}"
    data = p.read_text(encoding="utf-8", errors="replace")
    if len(data) > max_chars:
        return data[:max_chars] + f"\n...(truncated, total {len(data)} chars)..."
    return data


@tool(description="写入文件(覆盖已有内容),自动创建父目录,仅允许写入 workspace 内。")
def write_file(path: str, content: str) -> str:
    """写入文本文件。

    :param path: 目标路径,必须在 workspace 内
    :param content: 文件内容
    """
    p = resolve_within_workspace(path, settings.WORKSPACE)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    logger.info("write_file %s (%s chars)", p, len(content))
    return f"written {len(content)} chars -> {p}"


@tool(description="列出目录内容(名称/类型/大小)。")
def list_dir(path: str = ".") -> str:
    """列出目录内容。

    :param path: 目录路径,相对 workspace
    """
    p = resolve_within_workspace(path, settings.WORKSPACE)
    if not p.exists():
        return f"ERROR: 目录不存在: {p}"
    if not p.is_dir():
        return f"ERROR: 不是目录: {p}"
    lines = []
    for entry in sorted(os.scandir(p), key=lambda e: e.name):
        if entry.is_dir():
            lines.append(f"[DIR]  {entry.name}/")
        else:
            try:
                size = entry.stat().st_size
            except OSError:
                size = -1
            lines.append(f"[FILE] {entry.name}  ({size} B)")
    return "\n".join(lines) or "(empty directory)"
