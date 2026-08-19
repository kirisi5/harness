"""Hook 链:LLM 前后 + 工具前后,按注册顺序执行,可插拔、可组合。

企业级 Harness 的一切"横切关注点"(安全 / 审计 / 限流 / 截断)都做成 hook,
而不是散落在工具或主循环里。
"""
import logging
import time
from typing import Callable, List, Optional

logger = logging.getLogger("harness.hooks")


class HookManager:
    def __init__(self) -> None:
        self._pre_llm: List[Callable] = []
        self._post_llm: List[Callable] = []
        self._pre_tool: List[Callable] = []
        self._post_tool: List[Callable] = []

    # ---- 注册 ----
    def on_pre_llm(self, fn: Callable) -> Callable:
        """调用 LLM 之前:可改写 messages,返回 None 表示不改。"""
        self._pre_llm.append(fn)
        return fn

    def on_post_llm(self, fn: Callable) -> Callable:
        """拿到 LLM 回复之后:可改写 msg_dict,返回 None 表示不改。"""
        self._post_llm.append(fn)
        return fn

    def on_pre_tool(self, fn: Callable) -> Callable:
        """工具执行之前:签名 fn(name, args),可抛异常拦截。"""
        self._pre_tool.append(fn)
        return fn

    def on_post_tool(self, fn: Callable) -> Callable:
        """工具执行之后:签名 fn(name, args, output) -> 新 output。"""
        self._post_tool.append(fn)
        return fn

    # ---- 执行 ----
    def run_pre_llm(self, messages, **ctx):
        for fn in self._pre_llm:
            r = fn(messages, **ctx)
            if r is not None:
                messages = r
        return messages

    def run_post_llm(self, msg_dict, **ctx):
        for fn in self._post_llm:
            r = fn(msg_dict, **ctx)
            if r is not None:
                msg_dict = r
        return msg_dict

    def run_pre_tool(self, name: str, args: dict) -> None:
        for fn in self._pre_tool:
            fn(name, args)

    def run_post_tool(self, name: str, args: dict, output: str) -> str:
        for fn in self._post_tool:
            r = fn(name, args, output)
            if r is not None:
                output = r
        return output


def make_default_hooks(settings) -> HookManager:
    """组装出厂默认 hook 链:安全拦截 + 输出截断 + 审计日志。"""
    from .security import check_command_safety, ToolSecurityError

    hooks = HookManager()
    audit = getattr(settings, "ENABLE_AUDIT", True)

    # 1) 危险命令拦截(工具执行前)
    @hooks.on_pre_tool
    def _safety(name: str, args: dict) -> None:
        if name == "run_bash":
            check_command_safety(args.get("command", ""))

    # 2) 超长工具输出截断(工具执行后)
    @hooks.on_post_tool
    def _truncate(name: str, args: dict, output: str) -> str:
        cap = getattr(settings, "TOOL_OUTPUT_MAX_CHARS", 5000)
        if len(output) > cap:
            return output[:cap] + f"\n...(truncated by hook, total {len(output)} chars)..."
        return output

    # 3) 审计日志(LLM 前后)
    if audit:
        @hooks.on_pre_llm
        def _audit_in(messages, **ctx) -> None:
            logger.info("[LLM->] iteration=%s messages=%s chars=%s",
                        ctx.get("iteration"), len(messages),
                        sum(len(str(m.get("content", ""))) for m in messages))

        @hooks.on_post_llm
        def _audit_out(msg_dict, **ctx) -> None:
            logger.info("[<-LLM] finish=%s tool_calls=%s content_chars=%s",
                        ctx.get("finish_reason"), len(msg_dict.get("tool_calls") or []),
                        len(msg_dict.get("content") or ""))

    return hooks
