"""run_bash:沙箱化 shell 执行(工作目录约束 + 危险命令拦截 + 环境清洗 + 超时)。"""
import logging
import os
import subprocess
import sys

from ..config import settings
from ..core.redaction import redact
from ..core.registry import tool
from ..core.security import ToolSecurityError, check_command_safety, resolve_within_workspace, sanitize_env

logger = logging.getLogger("harness.tools.bash")


@tool(description="执行 shell 命令,返回 stdout/stderr。cwd 相对于工作区。")
def run_bash(command: str, cwd: str = ".", timeout: int = 30) -> str:
    """在沙箱工作区执行 shell 命令。

    :param command: 要执行的 shell 命令
    :param cwd: 工作目录,相对 workspace
    :param timeout: 超时秒数,默认 30
    """
    if not settings.ENABLE_BASH:
        raise ToolSecurityError("run_bash 已禁用；生产环境请使用隔离容器并显式设置 ENABLE_BASH=true")
    # 1) 危险命令拦截
    check_command_safety(command)
    timeout = min(max(int(timeout), 1), settings.MAX_BASH_TIMEOUT)
    # 2) 工作目录必须落在 workspace 内
    workdir = resolve_within_workspace(cwd, settings.WORKSPACE)
    workdir.mkdir(parents=True, exist_ok=True)
    # 3) 环境变量剔除敏感项
    env = sanitize_env(os.environ)
    env["PYTHONUNBUFFERED"] = "1"

    logger.info("run_bash cwd=%s cmd=%s", workdir, redact(command, max_chars=500))
    try:
        if sys.platform == "win32":
            executable = os.environ.get("COMSPEC", "cmd.exe")
            args = [executable, "/d", "/s", "/c", command]
        else:
            executable = "/bin/sh"
            args = [executable, "-c", command]
        out = subprocess.run(
            args, shell=False, capture_output=True, text=True,
            timeout=timeout, cwd=str(workdir), env=env,
            encoding="utf-8", errors="replace",
        )
        stdout = redact(out.stdout)
        stderr = redact(out.stderr)
        return f"exit={out.returncode}\nstdout:\n{stdout}\nstderr:\n{stderr}"
    except subprocess.TimeoutExpired as exc:
        partial_stdout = redact(exc.stdout or "")
        partial_stderr = redact(exc.stderr or "")
        return (
            f"exit=-1\nstdout:\n{partial_stdout}\n"
            f"stderr:\n{partial_stderr}\n"
            f"(command timed out after {timeout}s)"
        )
    except (OSError, ValueError) as e:
        logger.exception("run_bash 启动失败")
        return f"ERROR: 无法启动命令: {type(e).__name__}: {redact(e)}"
