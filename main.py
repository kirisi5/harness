"""CLI 入口:交互式 REPL。

支持的三种启动方式(详见 harness/__init__.py 顶部说明):
    1) cd "d:/study/LLM API" && python -m harness.main
    2) cd "d:/study/LLM API" && python harness/main.py
    3) cd harness             && python main.py     ← harness 当项目根目录

命令:
    /help              查看帮助
    /tools             列出已注册工具
    /stats             查看 token / 成本统计
    /clear             清空记忆
    /agents 任务1 || 任务2   并行派发子代理
    /exit              退出
"""
import logging
import pathlib
import sys
from logging.handlers import RotatingFileHandler

# ---------------------------------------------------------------------------
# 兼容 shim:让本文件能在三种启动方式下都被解析。
#
# - `python -m harness.main`:__package__ 已被识别为 "harness",以下跳过。
# - `python harness/main.py` 或 `cd harness && python main.py`:__package__ 为空,
#   需要把 harness 的父目录加进 sys.path,这样 `from harness.xxx` 才能找到包;
#   同时把当前模块的 __package__ 显式设为 "harness",让下面的包内相对导入
#   (from .config import ...) 也能解析。
# ---------------------------------------------------------------------------
if __package__ in (None, ""):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    __package__ = "harness"

# 注意:用包内相对导入(. 开头),与启动方式无关,
# 只要当前 __package__ 能解析为 "harness" 即可。
from .config import settings
from .core.agent import Agent
from .core.hooks import make_default_hooks
from .core.memory import MemoryStore
from .core.registry import registry
from .core.skills import load_skills_for
from .tools import load_all

logger = logging.getLogger("harness")


def setup_logging() -> None:
    fmt = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
    logging.basicConfig(level=logging.WARNING, format=fmt)  # 控制台只显示警告以上
    handler = RotatingFileHandler(
        settings.LOG_DIR / "harness.log",
        maxBytes=2_000_000, backupCount=3, encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(fmt))
    handler.setLevel(logging.INFO)
    logging.getLogger().addHandler(handler)


def banner() -> str:
    return (
        "\n"
        "========================================\n"
        "  LLM Agent Harness v0.1.0\n"
        f"  model={settings.MODEL}\n"
        f"  tools={', '.join(registry.names()) or '(none)'}\n"
        "  commands: /help /tools /stats /clear /agents /exit\n"
        "========================================"
    )


def main() -> None:
    # Windows 控制台 UTF-8 兼容
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    setup_logging()
    if not settings.API_KEY:
        print("❌ 未设置 OPENAI_API_KEY。请把 harness/.env.example 复制为 harness/.env 并填入密钥。")
        return

    load_all()
    hooks = make_default_hooks(settings)
    agent = Agent(
        registry=registry, hooks=hooks, settings=settings,
        skill_loader=lambda q: load_skills_for(q, settings.SKILLS_DIR),
    )
    memory = MemoryStore(settings.MEMORY_FILE, keep_turns=settings.MEMORY_KEEP_TURNS)
    history = memory.load()
    print(banner())

    try:
        while True:
            try:
                user_input = input(">>> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nbye")
                break
            if not user_input:
                continue

            cmd = user_input.lower()
            if cmd in ("/exit", "/quit", "exit", "quit"):
                break
            if cmd == "/help":
                print(banner())
                continue
            if cmd == "/tools":
                print("tools: " + ", ".join(registry.names()))
                continue
            if cmd == "/stats":
                print(agent.stats.summary())
                continue
            if cmd == "/clear":
                history.clear()
                memory.clear()
                print("memory cleared")
                continue
            if cmd.startswith("/agents "):
                tasks = [t.strip() for t in user_input[len("/agents "):].split("||") if t.strip()]
                if not tasks:
                    print("用法: /agents 任务1 || 任务2 || 任务3")
                    continue
                print(f"→ 派发 {len(tasks)} 个子代理(并行,隔离上下文)...")
                results = agent.orchestrate(tasks)
                for i, (t, r) in enumerate(zip(tasks, results), 1):
                    print(f"\n──── 子代理 {i}: {t}\n{r}")
                continue

            history.append({"role": "user", "content": user_input})
            try:
                agent.run(history)
            except Exception as e:
                logger.exception("agent 运行失败")
                print(f"\n❌ {type(e).__name__}: {e}")
            memory.save(history)
    finally:
        if history:
            memory.save(history)


if __name__ == "__main__":
    main()
