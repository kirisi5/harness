"""run_bash:沙箱化 shell 执行(工作目录约束 + 危险命令拦截 + 环境清洗 + 超时)。"""
import logging
import os
import subprocess

from ..config import settings
from ..core.registry import tool
from ..core.security import check_command_safety, resolve_within_workspace, sanitize_env

logger = logging.getLogger("harness.tools.bash")


@tool(description="执行 shell 命令,返回 stdout/stderr。cwd 相对于工作区。")
def run_bash(command: str, cwd: str = ".", timeout: int = 30) -> str:
    """在沙箱工作区执行 shell 命令。

    :param command: 要执行的 shell 命令
    :param cwd: 工作目录,相对 workspace
    :param timeout: 超时秒数,默认 30
    """
    # 1) 危险命令拦截
    check_command_safety(command)
    # 2) 工作目录必须落在 workspace 内
    workdir = resolve_within_workspace(cwd, settings.WORKSPACE)
    workdir.mkdir(parents=True, exist_ok=True)
    # 3) 环境变量剔除敏感项
    env = sanitize_env(os.environ)

    logger.info("run_bash cwd=%s cmd=%r", workdir, command)
    try:
        out = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=str(workdir), env=env,
            encoding="utf-8", errors="replace",
        )
        return f"exit={out.returncode}\nstdout:\n{out.stdout}\nstderr:\n{out.stderr}"
    except subprocess.TimeoutExpired:
        return f"exit=-1\nstdout:\n(stderr: command timed out after {timeout}s)"
    except OSError as e:
        return f"ERROR: 无法启动命令: {e}"
