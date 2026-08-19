"""内置工具集:导入即注册。"""
import logging

from ..core.registry import registry

logger = logging.getLogger("harness.tools")


def load_all() -> None:
    """导入所有工具模块,触发 @tool 注册。"""
    from . import bash, filesystem, search  # noqa: F401

    logger.info("tools registered: %s", ", ".join(registry.names()))
