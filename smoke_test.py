"""离线冒烟测试:不调用任何 LLM API,验证 harness 各核心模块可用。

运行: python -m harness.smoke_test
"""
import json
import sys
import pathlib

if __package__ in (None, ""):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from harness.config import settings
from harness.core.registry import registry
from harness.core.security import ToolSecurityError, check_command_safety
from harness.core.messages import trim_messages, count_tokens
from harness.core.memory import MemoryStore
from harness.tools import load_all

FAIL = []


def check(name, cond):
    tag = "PASS" if cond else "FAIL"
    print(f"[{tag}] {name}")
    if not cond:
        FAIL.append(name)


def main():
    print(f"== smoke test (model={settings.MODEL}, workspace={settings.WORKSPACE}) ==")

    # 1. 工具注册
    load_all()
    names = registry.names()
    check("工具全部注册", {"run_bash", "read_file", "write_file", "list_dir", "grep"} <= set(names))

    # 2. 自动 schema
    schemas = registry.schemas()
    check("schema 数量 == 工具数量", len(schemas) == len(names))
    bash_schema = next(s for s in schemas if s["function"]["name"] == "run_bash")
    check("run_bash schema 含 command 且必填", "command" in bash_schema["function"]["parameters"]["required"])

    # 3. dispatch:正常工具
    out = registry.dispatch("write_file", json.dumps({"path": "hello.txt", "content": "hello harness"}))
    check("write_file 写入成功", "written" in out)
    out = registry.dispatch("read_file", json.dumps({"path": "hello.txt"}))
    check("read_file 读回内容", "hello harness" in out)

    # 4. 沙箱拦截:路径越界
    out = registry.dispatch("read_file", json.dumps({"path": "../memory.json"}))
    check("路径越界被拦截", out.startswith("BLOCKED"))
    # 5. 沙箱拦截:危险命令(直接函数调用抛异常)
    try:
        check_command_safety("rm -rf /")
        check("危险命令抛出", False)
    except ToolSecurityError:
        check("危险命令抛出", True)
    # 6. dispatch 兜住危险命令(不崩,返回 BLOCKED)
    out = registry.dispatch("run_bash", json.dumps({"command": "rm -rf /"}))
    check("危险命令经 dispatch 返回 BLOCKED", out.startswith("BLOCKED"))

    # 7. 上下文裁剪:不拆散 tool 三件套
    # 构造:老对话撑爆预算,最近一轮是"完整三件套"→ 裁剪后必须整组保留
    msgs = [
        {"role": "user", "content": "OLD" * 300},  # 老对话,填满预算
        {"role": "assistant", "content": "old reply"},
        {"role": "user", "content": "u1"},
        {"role": "assistant", "tool_calls": [{"id": "c1", "type": "function",
                                              "function": {"name": "x", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "c1", "content": "t1"},
    ]
    trimmed = trim_messages(msgs, max_tokens=80, model=settings.MODEL)
    tool_ids = [m.get("tool_call_id") for m in trimmed if m.get("role") == "tool"]
    check("裁剪后 tool_call_id 仍然存在", "c1" in tool_ids)
    check("裁剪后 token 不超过预算", count_tokens(trimmed, settings.MODEL) <= 100)
    check("裁剪确实丢弃了老对话", all("OLD" not in (m.get("content") or "") for m in trimmed))

    # 8. 记忆存取:轮次保存
    mem = MemoryStore(settings.DATA_DIR / "smoke_memory.json", keep_turns=2)
    mem.save(msgs)
    loaded = mem.load()
    check("记忆回读非空", len(loaded) > 0)
    check("记忆保存 system 头", loaded[0].get("role") == "user" or loaded[0].get("role") == "system")
    mem.clear()

    # 9. 危险命令黑名单确实在工作区
    print(f"\n== 结果: {'全部通过' if not FAIL else '失败: ' + str(FAIL)} ==")
    if FAIL:
        sys.exit(1)


if __name__ == "__main__":
    main()
