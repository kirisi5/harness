"""安全层:危险命令拦截 + 路径沙箱校验 + 环境变量清洗。

原则:LLM 输出的内容一律不可信,任何触碰 OS 的操作都要过这里。
"""
import os
import pathlib
from typing import Dict, Optional

import logging

logger = logging.getLogger("harness.security")


class ToolSecurityError(Exception):
    """工具被安全层拦截(例如危险命令 / 路径越界)。"""


# 子串黑名单:命中即拒绝(保守策略,宁可误杀不可放过)
DANGEROUS_SUBSTRINGS = [
    "rm -rf /",
    "rm -rf ~",
    "rm -fr /",
    "rm -fr ~",
    "chmod 777 /",
    "chmod -r 777 /",
    "curl | bash",
    "wget | bash",
    ":(){:|:&};:",
    "mkfs.",
    "dd if=/dev/zero of=/dev/",
    "shutdown",
    "reboot",
    "halt",
    "format c:",
    "del /s /q c:",
    "rd /s /q c:",
    "> /dev/sda",
]


def check_command_safety(command: str) -> None:
    """校验 shell 命令,命中黑名单直接抛 ToolSecurityError。"""
    if not isinstance(command, str):
        raise ToolSecurityError(f"command 必须是字符串,收到 {type(command).__name__}")
    normalized = " ".join(command.split()).lower()
    for bad in DANGEROUS_SUBSTRINGS:
        if bad.lower() in normalized:
            logger.warning("危险命令被拦截: %r (命中 %r)", command, bad)
            raise ToolSecurityError(f"危险命令被拦截: {command!r} (命中黑名单 {bad!r})")


SENSITIVE_HINTS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIAL")


def sanitize_env(env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """复制环境变量,但剔除疑似敏感项,避免泄漏给子进程。"""
    src = dict(env if env is not None else os.environ)
    clean = {}
    for k, v in src.items():
        if any(hint in k.upper() for hint in SENSITIVE_HINTS):
            continue
        clean[k] = v
    return clean


def resolve_within_workspace(path, workspace, must_exist: bool = False) -> pathlib.Path:
    """把任意路径解析为 workspace 内的绝对路径,越界直接抛 ToolSecurityError。

    :param path: 相对路径(相对 workspace)或绝对路径
    :param workspace: 允许访问的根目录
    :param must_exist: 为 True 时路径必须存在
    """
    ws = pathlib.Path(workspace).resolve()
    p = pathlib.Path(str(path)).expanduser()
    if not p.is_absolute():
        p = ws / p
    p = p.resolve()
    try:
        p.relative_to(ws)
    except ValueError:
        logger.warning("路径越界被拦截: %s (workspace=%s)", p, ws)
        raise ToolSecurityError(f"路径越界,不允许访问 workspace 之外: {p}")
    if must_exist and not p.exists():
        raise ToolSecurityError(f"路径不存在: {p}")
    return p
