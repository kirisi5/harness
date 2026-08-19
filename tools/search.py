"""文本搜索工具:正则搜索文件内容,限制结果数量,只搜 workspace。"""
import logging
import os
import pathlib
import re

from ..config import settings
from ..core.registry import tool
from ..core.security import resolve_within_workspace

logger = logging.getLogger("harness.tools.search")

SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", "__pycache__",
             ".venv", "venv", ".idea", ".vscode"}


@tool(description="在文件中按正则搜索,返回 文件:行号:内容(最多 max_results 条)。")
def grep(pattern: str, path: str = ".", max_results: int = 50) -> str:
    """正则搜索文本内容。

    :param pattern: 正则表达式
    :param path: 搜索根目录,相对 workspace
    :param max_results: 最多返回的匹配数
    """
    root = resolve_within_workspace(path, settings.WORKSPACE)
    if not root.exists():
        return f"ERROR: 路径不存在: {root}"

    hits = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            fp = pathlib.Path(dirpath) / fn
            try:
                lines = fp.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for lineno, line in enumerate(lines, 1):
                if re.search(pattern, line):
                    rel = fp.relative_to(settings.WORKSPACE)
                    hits.append(f"{rel}:{lineno}: {line.strip()[:200]}")
                    if len(hits) >= max_results:
                        return "\n".join(hits) + "\n...(更多匹配被截断)"
    return "\n".join(hits) if hits else f"no matches for {pattern!r} in {root}"
