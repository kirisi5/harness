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
    /analyze [仓库相对路径]  四视角只读代码仓库分析
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
from . import __version__
from .config import settings
from .core.agent import Agent
from .core.hooks import make_default_hooks
from .core.memory import MemoryStore
from .core.registry import registry
from .core.repository_analysis import RepositoryAnalyzer
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
        f"  LLM Agent Harness v{__version__}\n"
        f"  model={settings.MODEL}\n"
        f"  tools={', '.join(registry.names()) or '(none)'}\n"
        "  commands: /help /tools /stats /clear /agents /exit\n"
        "========================================"
    )


def main() -> None:
    """启动 CLI REPL。"""
    # Windows 控制台 UTF-8 兼容
    try:
        stdout_reconfigure = getattr(sys.stdout, "reconfigure", None)
        stderr_reconfigure = getattr(sys.stderr, "reconfigure", None)
        if callable(stdout_reconfigure):
            stdout_reconfigure(encoding="utf-8")
        if callable(stderr_reconfigure):
            stderr_reconfigure(encoding="utf-8")
    except (OSError, ValueError):
        logger.debug("控制台编码配置失败", exc_info=True)

    setup_logging()
    if not settings.API_KEY:
        logger.error("未设置 OPENAI_API_KEY，请配置 .env 或环境变量")
        print("未设置 OPENAI_API_KEY，请配置 .env 或环境变量。")
        return

    load_all()
    hooks = make_default_hooks(settings)
    agent = Agent(
        registry=registry, hooks=hooks, settings=settings,
        skill_loader=lambda q: load_skills_for(q, settings.SKILLS_DIR),
        on_text=lambda text: print(text, end="", flush=True),
        on_tool=lambda name, output: print(
            f"\n[工具 {name} 完成,输出 {len(output)} 字符]",
        ),
    )
    repository_analyzer = RepositoryAnalyzer(agent)
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
            if cmd == "/agents" or cmd.startswith("/agents "):
                tasks = [t.strip() for t in user_input[len("/agents"):].split("||") if t.strip()]
                if not tasks:
                    print("用法: /agents 任务1 || 任务2 || 任务3")
                    continue
                print(f"→ 派发 {len(tasks)} 个子代理(并行,隔离上下文)...")
                results = agent.orchestrate(tasks)
                for i, (t, r) in enumerate(zip(tasks, results), 1):
                    print(f"\n──── 子代理 {i}: {t}\n{r}")
                continue
            if cmd == "/analyze" or cmd.startswith("/analyze "):
                repository = user_input[len("/analyze"):].strip() or "."
                try:
                    print(f"→ 分析仓库 {repository}（四个只读子代理并行）...")
                    report = repository_analyzer.analyze(repository)
                    print(report.to_markdown())
                except Exception as exc:
                    logger.exception("repository analysis failed")
                    print(f"分析失败: {type(exc).__name__}: {exc}")
                continue

            history.append({"role": "user", "content": user_input})
            try:
                result = agent.run(history)
                if result and not settings.STREAM:
                    print(result)
                print()
            except Exception as e:
                logger.exception("agent 运行失败")
                print(f"\n❌ {type(e).__name__}: {e}")
            finally:
                memory.save(history)
    finally:
        if history:
            memory.save(history)


if __name__ == "__main__":
    main()
