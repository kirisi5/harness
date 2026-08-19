"""集中配置管理:环境变量 / .env / 内置默认值,全部归一到一个 Settings。

用法:
    from harness.config import settings
    print(settings.MODEL)

优先级: 环境变量 > .env 文件 > 内置默认值
"""
import os
import pathlib

BASE_DIR = pathlib.Path(__file__).resolve().parent


def _load_dotenv(path: pathlib.Path) -> None:
    """极简 .env 解析器(无第三方依赖,够用即可)。"""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR / ".env")


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    """所有可调参数集中于此,改配置只动这里或 .env。"""

    def __init__(self) -> None:
        # ---- LLM ----
        self.API_KEY = _env("OPENAI_API_KEY", "")
        self.BASE_URL = _env(
            "OPENAI_BASE_URL",
            "https://api.openai.com/v1",
        )
        self.MODEL = _env("MODEL", "qwen3.7-plus")
        self.MAX_OUTPUT_TOKENS = _env_int("MAX_OUTPUT_TOKENS", 8000)
        self.CONTEXT_BUDGET_TOKENS = _env_int("CONTEXT_BUDGET_TOKENS", 32000)
        self.STREAM = _env_bool("STREAM", True)
        self.TEMPERATURE = _env_float("TEMPERATURE", 0.0)

        # ---- 循环 / 重试 ----
        self.MAX_ITERATIONS = _env_int("MAX_ITERATIONS", 50)
        self.RETRY_MAX = _env_int("RETRY_MAX", 4)
        self.RETRY_BASE_DELAY = _env_float("RETRY_BASE_DELAY", 1.0)

        # ---- 记忆 ----
        self.DATA_DIR = BASE_DIR / "data"
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.MEMORY_FILE = self.DATA_DIR / "memory.json"
        self.MEMORY_KEEP_TURNS = _env_int("MEMORY_KEEP_TURNS", 3)

        # ---- Skill ----
        self.SKILLS_DIR = pathlib.Path(_env("SKILLS_DIR", str(BASE_DIR / "skills")))

        # ---- 沙箱 / 工具 ----
        self.WORKSPACE = pathlib.Path(_env("WORKSPACE", str(BASE_DIR / "workspace")))
        self.WORKSPACE.mkdir(parents=True, exist_ok=True)
        self.TOOL_OUTPUT_MAX_CHARS = _env_int("TOOL_OUTPUT_MAX_CHARS", 5000)

        # ---- 日志 ----
        self.LOG_DIR = BASE_DIR / "logs"
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.ENABLE_AUDIT = _env_bool("ENABLE_AUDIT", True)

        # ---- 系统提示 ----
        self.BASE_SYSTEM = _env(
            "BASE_SYSTEM",
            "你是一个运行在沙箱中的编程智能体。可以调用工具完成用户请求,"
            "回答尽量简洁,不要复述工具输出。",
        )


settings = Settings()
