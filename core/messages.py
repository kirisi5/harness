"""消息工具:统一 dict 化、token 计数(精确)、按轮次裁剪上下文。"""
import json
import logging
from typing import List

try:
    import tiktoken
except Exception:  # pragma: no cover - tiktoken 未安装时降级
    tiktoken = None

logger = logging.getLogger("harness.messages")

Message = dict


def to_dict(m) -> dict:
    """把 OpenAI SDK 的 Pydantic 对象转成纯 dict,递归处理 tool_calls。"""
    if hasattr(m, "model_dump"):
        m = m.model_dump(exclude_none=True)
    if isinstance(m, dict) and m.get("tool_calls"):
        m["tool_calls"] = [
            tc.model_dump(exclude_none=True) if hasattr(tc, "model_dump") else tc
            for tc in m["tool_calls"]
        ]
    return m


def _get_encoder(model: str):
    """按模型取 tiktoken 编码器;取不到就返回 None(触发字符估算降级)。"""
    if tiktoken is None:
        return None
    try:
        return tiktoken.encoding_for_model(model)
    except Exception:
        try:
            return tiktoken.get_encoding("cl100k_base")
        except Exception:
            return None


def count_tokens(messages: List[Message], model: str = "gpt-4o-mini") -> int:
    """统计整份 messages 的 token 数。tiktoken 不可用时按 4 字符≈1 token 估算。"""
    msgs = [to_dict(m) for m in messages]
    enc = _get_encoder(model)
    if enc is None:
        return sum(len(str(m.get("content", ""))) for m in msgs) // 4 + 1
    total = 0
    for m in msgs:
        try:
            text = json.dumps(m, ensure_ascii=False, default=str)
        except TypeError:
            text = str(m)
        total += len(enc.encode(text))
    return total


def group_turns(msgs: List[Message]) -> List[List[Message]]:
    """以 user 为界把消息切成一轮轮,保证 assistant(tool_calls)+tool 回包不拆散。"""
    groups, cur = [], []
    for m in msgs:
        d = to_dict(m)
        role = d.get("role")
        if not cur:
            cur.append(d)
            continue
        last_role = cur[-1].get("role")
        if role == "user" and last_role in ("assistant", "tool"):
            groups.append(cur)
            cur = [d]
        else:
            cur.append(d)
    if cur:
        groups.append(cur)
    return groups


def trim_messages(messages: List[Message], max_tokens: int, model: str = "gpt-4o-mini") -> List[Message]:
    """超出预算就从中间裁掉旧轮次,保留 system 头 + 最近若干完整轮次。

    只在轮次边界裁剪,永远不会出现"有 tool_calls 却没有 tool 回包"的畸形消息。
    """
    msgs = [to_dict(m) for m in messages]
    total = count_tokens(msgs, model)
    if total <= max_tokens or not msgs:
        return msgs

    heads, body = [], []
    for m in msgs:
        (heads if m.get("role") == "system" else body).append(m)

    turns = group_turns(body)
    kept, used = [], count_tokens(heads, model)
    for turn in reversed(turns):
        tok = count_tokens(turn, model)
        if used + tok <= max_tokens:
            kept.insert(0, turn)
            used += tok
        else:
            break
    if not kept and turns:
        # 没有任何整轮放得下 → 保底最近一轮,并对其 content 做字符级截断
        last_turn = [dict(m) for m in turns[-1]]
        spare_chars = max((max_tokens - used) * 4 - 40, 40)  # 给 placeholder 预留
        for m in last_turn:
            content = m.get("content") or ""
            if isinstance(content, str) and len(content) > spare_chars:
                m["content"] = content[:spare_chars] + "...[truncated]..."
        kept = [last_turn]

    removed = max(0, total - used)
    placeholder = {"role": "system", "content": f"...(earlier context trimmed, removed ~{removed} tokens)..."}
    logger.info("trim: %s tokens -> %s tokens (removed %s tokens)", total, used, removed)
    return heads + [placeholder] + [m for g in kept for m in g]
