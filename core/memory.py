"""跨会话持久化记忆:按"轮次"保存,保证 assistant(tool_calls)+tool 回包不拆散。"""
import json
import logging
import pathlib
from typing import List, Optional

from .messages import to_dict, group_turns

logger = logging.getLogger("harness.memory")


class MemoryStore:
    def __init__(self, path, keep_turns: int = 3) -> None:
        self.path = pathlib.Path(path)
        self.keep_turns = keep_turns

    def load(self) -> List[dict]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("memory 读取失败,将清空重建: %s", e)
            return []
        if not isinstance(data, list):
            return []
        return [to_dict(m) for m in data]

    def save(self, messages, keep_turns: Optional[int] = None) -> None:
        msgs = [to_dict(m) for m in messages]
        if not msgs:
            return
        keep_turns = keep_turns or self.keep_turns
        sys_msg = msgs[0] if msgs[0].get("role") == "system" else None
        body = [m for m in msgs if m.get("role") != "system"]
        turns = group_turns(body)
        keep = ([sys_msg] if sys_msg else []) + [m for g in turns[-keep_turns:] for m in g]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(keep, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("memory saved: %s messages (%s turns)", len(keep), min(len(turns), keep_turns))

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()
        logger.info("memory cleared")
