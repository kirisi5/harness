import json
import tempfile
from pathlib import Path

from harness.core.hooks import HookManager
from harness.core.memory import MemoryStore
from harness.core.registry import Tool, ToolRegistry
from harness.core.security import ToolSecurityError, resolve_within_workspace


def test_registry_rejects_unknown_and_missing_arguments():
    registry = ToolRegistry()

    def add(left: int, right: int) -> str:
        return str(left + right)

    registry.register(Tool("add", add))
    assert "未知参数" in registry.dispatch("add", json.dumps({"left": 1, "right": 2, "extra": 3}))
    assert "缺少必需参数" in registry.dispatch("add", json.dumps({"left": 1}))
    assert registry.dispatch("add", json.dumps({"left": 1, "right": 2})) == "3"


def test_registry_permission_and_post_hook_failure_are_safe():
    registry = ToolRegistry()
    registry.register(Tool("blocked", lambda: "no", permission="deny"))
    assert registry.dispatch("blocked", "{}").startswith("BLOCKED")

    hooks = HookManager()

    @hooks.on_post_tool
    def broken(name, args, output):
        raise RuntimeError("hook failure")

    registry.register(Tool("ok", lambda: "yes"))
    assert "后处理异常" in registry.dispatch("ok", "{}", hooks=hooks)


def test_workspace_rejects_escape():
    with tempfile.TemporaryDirectory() as directory:
        try:
            resolve_within_workspace("../outside", directory)
        except ToolSecurityError:
            pass
        else:
            raise AssertionError("workspace escape was not rejected")


def test_memory_round_trip_is_atomic_shape():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "memory.json"
        store = MemoryStore(path, keep_turns=1)
        messages = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "world"}]
        store.save(messages)
        assert store.load() == messages
