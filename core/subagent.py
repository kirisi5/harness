"""Sub-Agent:独立上下文、受限工具集、只回传摘要;支持线程池并行。

用途:把一个大任务拆成多个互不依赖的子任务并行跑,主 agent 只接收摘要,
避免把中间产物全部塞进主上下文。
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

logger = logging.getLogger("harness.subagent")

DEFAULT_SUBAGENT_SYSTEM = (
    "你是子代理。只完成分配给你的任务,返回简洁的最终摘要,"
    "不要复述过程,不要回复与任务无关的内容。"
)


def run_subagent(task: str, system: Optional[str] = None, tools: Optional[List[dict]] = None,
                 model: Optional[str] = None, max_tokens: int = 2000, client=None) -> str:
    """运行一个隔离的子代理对话,返回其文字回复。"""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system or DEFAULT_SUBAGENT_SYSTEM},
            {"role": "user", "content": task},
        ],
        "max_tokens": max_tokens,
    }
    if tools:
        payload["tools"] = tools
    r = client.chat.completions.create(**payload)
    return r.choices[0].message.content or ""


def run_subagents_parallel(tasks: List[str], system: Optional[str] = None,
                           tools: Optional[List[dict]] = None, model: Optional[str] = None,
                           max_tokens: int = 2000, client=None, workers: int = 4) -> List[str]:
    """并行跑多个子代理,单个失败不拖垮整体。"""
    def one(task: str) -> str:
        try:
            return run_subagent(task, system=system, tools=tools, model=model,
                                max_tokens=max_tokens, client=client)
        except Exception as e:  # noqa: BLE001
            logger.exception("子代理失败")
            return f"ERROR: {type(e).__name__}: {e}"

    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(one, tasks))
