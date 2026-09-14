"""Agent 主循环:流式输出、指数退避重试、上下文管理、成本统计、工具分发。

这是 harness 的"大脑 + 手脚协调中枢"。
"""
import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional

from openai import (
    APIConnectionError,
    APITimeoutError,
    BadRequestError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)

from ..config import Settings, settings as default_settings
from .hooks import HookManager
from .messages import trim_messages
from .registry import ToolRegistry
from .subagent import run_subagents_parallel

logger = logging.getLogger("harness.agent")

# 可重试的异常集合(指数退避处理)
RETRYABLE = (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError)


@dataclass
class AgentStats:
    """成本 / 调用统计。"""
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    tool_calls: int = 0
    iterations: int = 0
    started_at: float = field(default_factory=time.time)

    def record(self, usage) -> None:
        if not usage:
            return
        self.prompt_tokens += getattr(usage, "prompt_tokens", 0) or 0
        self.completion_tokens += getattr(usage, "completion_tokens", 0) or 0
        self.total_tokens += getattr(usage, "total_tokens", 0) or 0

    def summary(self) -> str:
        return (
            f"calls={self.calls} iterations={self.iterations} tool_calls={self.tool_calls} "
            f"prompt_tokens={self.prompt_tokens} completion_tokens={self.completion_tokens} "
            f"total_tokens={self.total_tokens} elapsed={time.time() - self.started_at:.1f}s"
        )


class Agent:
    def __init__(self, registry: ToolRegistry, hooks: HookManager, settings: Optional[Settings] = None,
                 client: Optional[OpenAI] = None, skill_loader=None, on_text=None,
                 on_tool=None) -> None:
        self.settings = settings or default_settings
        self.registry = registry
        self.hooks = hooks or HookManager()
        self.client = client or OpenAI(
            api_key=self.settings.API_KEY,
            base_url=self.settings.BASE_URL,
            timeout=self.settings.LLM_TIMEOUT,
        )
        self.skill_loader = skill_loader or (lambda user_query: "")
        self.on_text = on_text
        self.on_tool = on_tool
        self.request_id: Optional[str] = None
        self.stats = AgentStats()
        self._run_started = 0.0

    # ---------- system 组装 ----------
    def build_system(self, messages: List[dict]) -> str:
        parts = [self.settings.BASE_SYSTEM]
        last_user = next((str(m.get("content", "")) for m in reversed(messages)
                          if m.get("role") == "user"), "")
        if last_user:
            skill = self.skill_loader(last_user)
            if skill:
                parts.append("# 已加载 Skill\n" + skill)
        parts.append("可用工具: " + ", ".join(self.registry.names()) or "(无工具)")
        return "\n\n".join(parts)

    # ---------- LLM 调用(带重试) ----------
    def _call(self, system: str, messages: List[dict]):
        payload = dict(
            model=self.settings.MODEL,
            messages=[{"role": "system", "content": system}] + messages,
            max_tokens=self.settings.MAX_OUTPUT_TOKENS,
            temperature=self.settings.TEMPERATURE,
        )
        schemas = self.registry.schemas()
        if schemas:
            payload["tools"] = schemas

        last_err: Optional[Exception] = None
        for attempt in range(1, self.settings.RETRY_MAX + 1):
            try:
                if self.settings.STREAM:
                    msg_dict, finish = self._call_stream(payload)
                else:
                    r = self.client.chat.completions.create(**payload)
                    msg_dict = r.choices[0].message.model_dump(exclude_none=True)
                    finish = r.choices[0].finish_reason
                    self.stats.record(getattr(r, "usage", None))
                self.stats.calls += 1
                return msg_dict, finish
            except RETRYABLE as e:
                last_err = e
                delay = self.settings.RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning("LLM 调用失败(第 %s/%s 次) %s: %s,%.1fs 后重试",
                               attempt, self.settings.RETRY_MAX, type(e).__name__, e, delay)
                if attempt < self.settings.RETRY_MAX:
                    time.sleep(delay)
        raise last_err  # type: ignore[misc]

    def _call_stream(self, payload: dict):
        """流式调用:边输出边累积,同时拼装 tool_calls 增量。"""
        payload = dict(payload, stream=True, stream_options={"include_usage": True})
        try:
            stream = self.client.chat.completions.create(**payload)
        except BadRequestError:
            # 某些兼容端点不支持 stream_options,降级为普通流
            logger.warning("服务端不支持 stream_options,降级为普通流")
            payload.pop("stream_options", None)
            stream = self.client.chat.completions.create(**payload)

        text_parts: List[str] = []
        tool_calls: dict = {}  # index -> {id, name, arguments}
        finish_reason = None
        usage = None

        for chunk in stream:
            if getattr(chunk, "usage", None) is not None:
                usage = chunk.usage
            choice = chunk.choices[0] if chunk.choices else None
            if choice is None:
                continue
            if choice.finish_reason:
                finish_reason = choice.finish_reason
            delta = choice.delta
            if delta is None:
                continue
            if delta.content:
                text_parts.append(delta.content)
                if self.on_text is not None:
                    self.on_text(delta.content)
            for tc in delta.tool_calls or []:
                slot = tool_calls.setdefault(tc.index, {"id": None, "function": {"name": None, "arguments": ""}})
                if tc.id:
                    slot["id"] = tc.id
                if tc.function is not None:
                    if tc.function.name:
                        slot["function"]["name"] = tc.function.name
                    if tc.function.arguments:
                        slot["function"]["arguments"] += tc.function.arguments
        msg_dict = {"role": "assistant", "content": "".join(text_parts) or None}
        if tool_calls:
            msg_dict["tool_calls"] = [
                {"id": s["id"], "type": "function",
                 "function": {"name": s["function"]["name"], "arguments": s["function"]["arguments"]}}
                for _, s in sorted(tool_calls.items())
            ]
        self.stats.record(usage)
        return msg_dict, finish_reason

    # ---------- 主循环 ----------
    def run(self, messages: List[dict], max_iterations: Optional[int] = None) -> str:
        """在给定消息列表上运行 agent,直至模型停止调用工具。会就地修改 messages。"""
        max_iter = max_iterations or self.settings.MAX_ITERATIONS
        final_text = ""
        run_started = time.monotonic()
        self._run_started = run_started
        for iteration in range(1, max_iter + 1):
            self.stats.iterations = iteration
            if self.settings.MAX_RUN_SECONDS > 0 and (time.monotonic() - run_started) >= self.settings.MAX_RUN_SECONDS:
                logger.warning("达到单次运行时间上限 %.1fs", self.settings.MAX_RUN_SECONDS)
                return final_text or "任务因达到运行时间上限而停止。"
            if self.settings.MAX_TOTAL_TOKENS > 0 and self.stats.total_tokens >= self.settings.MAX_TOTAL_TOKENS:
                logger.warning("达到单次运行 token 上限 %s", self.settings.MAX_TOTAL_TOKENS)
                return final_text or "任务因达到 token 预算上限而停止。"
            # 裁剪上下文(只在轮次边界切,不拆散工具三件套)
            messages[:] = trim_messages(messages, self.settings.CONTEXT_BUDGET_TOKENS, self.settings.MODEL)

            system = self.build_system(messages)
            state = {"start": time.time()}
            hooked_messages = self.hooks.run_pre_llm(
                messages, iteration=iteration, state=state,
                request_id=getattr(self, "request_id", None),
            )
            if hooked_messages is not messages:
                messages[:] = hooked_messages

            msg_dict, finish = self._call(system, messages)
            msg_dict = self.hooks.run_post_llm(
                msg_dict, iteration=iteration, state=state, finish_reason=finish,
                request_id=self.request_id,
            )
            messages.append(msg_dict)

            tool_calls = msg_dict.get("tool_calls") or []
            if not tool_calls:
                return msg_dict.get("content") or ""

            # 逐个执行工具并回填
            for tc in tool_calls:
                name = tc["function"].get("name")
                arguments = tc["function"].get("arguments") or "{}"
                self.stats.tool_calls += 1
                output = self.registry.dispatch(name, arguments, hooks=self.hooks)
                messages.append({"role": "tool", "tool_call_id": tc.get("id"), "content": output})
                if self.on_tool is not None:
                    self.on_tool(name, output)
                logger.info("tool %s -> %s chars", name, len(output))

        logger.warning("达到最大迭代次数 %s,强制返回", max_iter)
        return final_text or "任务达到最大迭代次数，未产生最终答案。"

    # ---------- 子代理编排 ----------
    def orchestrate(self, tasks: List[str], system: Optional[str] = None,
                    tools: Optional[List[str]] = None, workers: int = 4,
                    max_tokens: int = 1200, max_iterations: Optional[int] = None) -> List[str]:
        """把多个独立子任务并行派发给子代理；tools 是强制工具白名单。"""
        schemas = self.registry.schemas_for(tools) if tools is not None else None
        allowed_tools = list(tools) if tools is not None else None
        return run_subagents_parallel(
            tasks, system=system, tools=schemas, model=self.settings.MODEL,
            max_tokens=max_tokens, client=self.client, workers=workers,
            registry=self.registry, hooks=self.hooks, allowed_tools=allowed_tools,
            max_iterations=max_iterations or min(self.settings.MAX_ITERATIONS, 10),
        )
