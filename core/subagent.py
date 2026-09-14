"""Sub-Agent:独立上下文、受限工具集、只回传摘要;支持线程池并行。

用途:把一个大任务拆成多个互不依赖的子任务并行跑,主 agent 只接收摘要,
避免把中间产物全部塞进主上下文。
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from .hooks import HookManager
from .registry import ToolRegistry

logger = logging.getLogger("harness.subagent")

DEFAULT_SUBAGENT_SYSTEM = (
    "你是子代理。只完成分配给你的任务,返回简洁的最终摘要,"
    "不要复述过程,不要回复与任务无关的内容。"
)


def run_subagent(task: str, system: Optional[str] = None, tools: Optional[List[dict]] = None,
                 model: Optional[str] = None, max_tokens: int = 2000, client=None,
                 registry: Optional[ToolRegistry] = None, max_iterations: int = 5,
                 hooks: Optional[HookManager] = None, allowed_tools: Optional[List[str]] = None) -> str:
    """运行隔离的子代理；如提供 registry，则支持受限工具调用循环。"""
    messages = [
        {"role": "system", "content": system or DEFAULT_SUBAGENT_SYSTEM},
        {"role": "user", "content": task},
    ]
    for _ in range(max(1, max_iterations)):
        payload = {"model": model, "messages": messages, "max_tokens": max_tokens}
        if tools:
            payload["tools"] = tools
        response = client.chat.completions.create(**payload)
        message = response.choices[0].message
        message_dict = message.model_dump(exclude_none=True) if hasattr(message, "model_dump") else message
        if not isinstance(message_dict, dict):
            return "ERROR: 子代理返回了无效消息"
        messages.append(message_dict)
        tool_calls = message_dict.get("tool_calls") or []
        if not tool_calls or registry is None:
            return message_dict.get("content") or ""
        for call in tool_calls:
            function = call.get("function") or {}
            name = function.get("name", "")
            if allowed_tools is not None and name not in allowed_tools:
                output = f"BLOCKED: 子代理不允许调用工具 {name}"
            else:
                output = registry.dispatch(name, function.get("arguments", "{}"), hooks=hooks)
            messages.append({"role": "tool", "tool_call_id": call.get("id"), "content": output})
    return "子代理达到最大迭代次数，未产生最终答案。"


def run_subagents_parallel(tasks: List[str], system: Optional[str] = None,
                           tools: Optional[List[dict]] = None, model: Optional[str] = None,
                           max_tokens: int = 2000, client=None, workers: int = 4,
                           registry: Optional[ToolRegistry] = None,
                           max_iterations: int = 5, hooks: Optional[HookManager] = None,
                           allowed_tools: Optional[List[str]] = None) -> List[str]:
    """并行跑多个子代理,单个失败不拖垮整体。"""
    if not tasks:
        return []
    workers = min(max(1, workers), len(tasks), 8)

    def one(task: str) -> str:
        try:
            return run_subagent(task, system=system, tools=tools, model=model,
                                max_tokens=max_tokens, client=client, registry=registry,
                                max_iterations=max_iterations, hooks=hooks,
                                allowed_tools=allowed_tools)
        except Exception as e:  # noqa: BLE001
            logger.exception("子代理失败")
            return f"ERROR: {type(e).__name__}: {e}"

    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(one, tasks))
