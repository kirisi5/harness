# Harness 框架完全学习手册(基于 `D:\study\LLM API\harness` 项目)

> 本文档以该项目为**完整案例**,从零开始、不跳步地教会你掌握 **Harness 框架** 的核心概念、配置方式、执行流程与扩展方法。
> 阅读对象:刚 clone 下本仓库、想要"既懂用法又懂原理"的工程师。

---

## 目录

1. [一、项目目录树](#一项目目录树)
2. [二、Harness 框架核心概念速览](#二harness-框架核心概念速览)
3. [三、根目录文件逐个讲解](#三根目录文件逐个讲解)
   - [3.1 `__init__.py` —— 包的"门面"与架构图](#31-__init__py--包的门面与架构图)
   - [3.2 `config.py` —— 集中配置(Settings)](#32-configpy--集中配置settings)
   - [3.3 `main.py` —— CLI 交互入口](#33-mainpy--cli-交互入口)
   - [3.4 `smoke_test.py` —— 离线冒烟测试](#34-smoke_testpy--离线冒烟测试)
   - [3.5 `requirements.txt`、`.env`、`.env.example`](#35-requirementstxtenvenvexample)
4. [四、`core/` 引擎逐模块讲解](#四core-引擎逐模块讲解)
   - [4.1 `core/registry.py` —— 工具注册中心(装饰器 + 自动 schema)](#41-coreregistrypy--工具注册中心装饰器--自动-schema)
   - [4.2 `core/hooks.py` —— 横切关注点(Hook 链)](#42-corehookspy--横切关注点hook-链)
   - [4.3 `core/security.py` —— 安全层(命令黑名单 / 路径沙箱 / 环境清洗)](#43-coresecuritypy--安全层命令黑名单--路径沙箱--环境清洗)
   - [4.4 `core/messages.py` —— 消息工具(dict 化 / token 计数 / 轮次裁剪)](#44-coremessagespy--消息工具dict-化--token-计数--轮次裁剪)
   - [4.5 `core/memory.py` —— 跨会话持久化记忆](#45-corememorypy--跨会话持久化记忆)
   - [4.6 `core/skills.py` —— Skill 前置匹配加载](#46-coreskillspy--skill-前置匹配加载)
   - [4.7 `core/subagent.py` —— 子代理(隔离上下文 + 并行)](#47-coresubagentpy--子代理隔离上下文--并行)
   - [4.8 `core/agent.py` —— 主循环(大脑 + 手脚协调中枢)](#48-coreagentpy--主循环大脑--手脚协调中枢)
5. [五、`tools/` 内置工具逐文件讲解](#五tools-内置工具逐文件讲解)
   - [5.1 `tools/__init__.py` —— `load_all()` 注册入口](#51-tools__init__py--load_all-注册入口)
   - [5.2 `tools/bash.py` —— `run_bash` 沙箱 shell](#52-toolsbashpy--run_bash-沙箱-shell)
   - [5.3 `tools/filesystem.py` —— `read_file` / `write_file` / `list_dir`](#53-toolsfilesystempy--read_file--write_file--list_dir)
   - [5.4 `tools/search.py` —— `grep` 正则搜索](#54-toolssearchpy--grep-正则搜索)
6. [六、运行时数据目录(`data/`、`workspace/`、`logs/`)](#六运行时数据目录dataworkspacelogs)
7. [七、执行流程全景(从用户按下回车到文本输出)](#七执行流程全景从用户按下回车到文本输出)
8. [八、扩展方法:加一个工具 / 加一个 hook / 加一个 skill](#八扩展方法加一个工具--加一个-hook--加一个-skill)
9. [九、Harness 范式与最佳实践(从本项目提炼)](#九harness-范式与最佳实践从本项目提炼)

---

## 一、项目目录树

```
D:\study\LLM API\harness\
├── __init__.py               # 包门面 + 架构图注释 + 版本号
├── config.py                 # 集中配置(Settings 单例)
├── main.py                   # CLI 交互入口(REPL)
├── smoke_test.py             # 离线冒烟测试(不调用 LLM)
├── requirements.txt          # 第三方依赖
├── .env.example              # 配置模板(可入库)
├── .env                      # 用户私有配置(git 忽略)
│
├── core/                     # ─── 引擎层(所有横切能力) ───
│   ├── __init__.py
│   ├── registry.py           # 工具注册 + 自动 schema
│   ├── hooks.py              # pre/post LLM + pre/post tool 钩子
│   ├── security.py           # 黑名单 / 路径沙箱 / 环境清洗
│   ├── messages.py           # dict 化 / token 计数 / 裁剪
│   ├── memory.py             # 跨会话记忆(json 落盘)
│   ├── skills.py             # Skill 匹配加载
│   ├── subagent.py           # 子代理(隔离 + 并行)
│   └── agent.py              # 主循环(流式 / 重试 / 编排)
│
├── tools/                    # ─── 内置工具(由 @tool 装饰器注册) ───
│   ├── __init__.py           # load_all()
│   ├── bash.py               # run_bash
│   ├── filesystem.py         # read_file / write_file / list_dir
│   └── search.py             # grep
│
├── data/                     # 运行时数据
│   └── memory.json           # 跨会话记忆
│
├── workspace/                # 沙箱:Agent 文件/bash 只允许访问这里
│   └── hello.txt
│
└── logs/                     # 日志(滚动)
    └── harness.log
```

> **一句话理解整个项目**:`config.py` 决定一切参数;`core/agent.py` 负责"LLM 思考 + 工具调用"的循环;`core/registry.py` 是工具家谱;`core/hooks.py` 是安插在循环上的所有"侧切面";`tools/` 是默认带的几把刷子。

---

## 二、Harness 框架核心概念速览

学习任何 Harness 类项目,你都可以把它拆成 **8 个固定槽位** 来理解。本项目正好对应:

| 槽位 | 在本项目中的位置 | 一句话职责 |
|---|---|---|
| **配置中心** | `config.py` | 把环境变量、`.env`、默认值收敛成 `settings` 单例 |
| **消息工具** | `core/messages.py` | dict 化、token 统计、轮次安全的裁剪 |
| **工具注册** | `core/registry.py` | 装饰器注册 + 自动生成 OpenAI function schema |
| **安全层** | `core/security.py` | 路径沙箱 + 命令黑名单 + 环境清洗 |
| **Hook 链** | `core/hooks.py` | 在 LLM/工具前后挂横切逻辑 |
| **主循环** | `core/agent.py` | 调用 LLM → 解析工具 → 跑工具 → 回填 → 再调用 |
| **记忆/Skill/子代理** | `core/memory.py` `core/skills.py` `core/subagent.py` | 让"上下文"可持久化、可扩展、可并行 |
| **CLI** | `main.py` | 暴露给用户的"驾驶舱" |

**记住这张表,剩下所有代码都是它的展开。**

---

## 三、根目录文件逐个讲解

### 3.1 `__init__.py` —— 包的"门面"与架构图

```12:21:harness/__init__.py
"""LLM Agent Harness —— 企业级多文件版。
...
"""
__version__ = "0.1.0"
```

**作用**:
- 文档字符串里画了一张 **架构地图**(这其实是给你的最有用礼物)。
- 声明包级版本号 `__version__ = "0.1.0"`。

**怎么用**:
```python
import harness
print(harness.__version__)  # 0.1.0
```

**学到什么**:即使是"看似空"的 `__init__.py`,也至少要写明"自己有几块、每块叫什么",这是大型项目自解释的入口。

---

### 3.2 `config.py` —— 集中配置(Settings)

本文件解决一个最朴素的问题:**参数分散在哪儿?答:都集中到 `settings` 这一个对象**。

#### (1) 自制的 `.env` 解析器

```15:27:harness/config.py
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
```

- **关键点**:`os.environ.setdefault(...)` —— **只设置"还没有"的环境变量**。
- 因此优先级是:**真正的环境变量 > `.env` 文件 > 内置默认**。
- 它有意识地"不用第三方",因为增加了部署复杂度,不划算。

#### (2) 类型化的小工具

```30:52:harness/config.py
def _env(name: str, default: str) -> str: ...
def _env_int(name: str, default: int) -> int: ...
def _env_float(name: str, default: float) -> float: ...
def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")
```

这 4 个小函数把"环境变量 → Python 基本类型"的脏活封装了,且 `_env_bool` 接受 `"1"`/`"true"`/`"yes"`/`"on"`(大小写无关)。

#### (3) `Settings` 类:所有参数集中地

```55:103:harness/config.py
class Settings:
    def __init__(self) -> None:
        # ---- LLM ----
        self.API_KEY = _env("OPENAI_API_KEY", "")
        self.BASE_URL = _env("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.MODEL = _env("MODEL", "qwen3.7-plus")
        self.MAX_OUTPUT_TOKENS = _env_int("MAX_OUTPUT_TOKENS", 8000)
        self.CONTEXT_BUDGET_TOKENS = _env_int("CONTEXT_BUDGET_TOKENS", 32000)
        self.STREAM = _env_bool("STREAM", True)
        self.TEMPERATURE = _env_float("TEMPERATURE", 0.0)
        ...
```

按用途分块:**LLM / 循环-重试 / 记忆 / Skill / 沙箱-工具 / 日志 / 系统提示**。

**为什么不是 `pydantic-settings`?** 答案在文件头注释里:为了 0 第三方依赖、够用即可。这是个**有意取舍**。

#### (4) 单例

```103:harness/config.py
settings = Settings()
```

文件末尾立刻实例化一个 `settings`。任何地方 `from harness.config import settings` 即可。

#### 本节学到的范式

| 范式 | 在本项目的体现 |
|---|---|
| 配置中心化 | `Settings` 类一把收 |
| 优先级可控 | `.env` < 真正的环境变量 |
| 路径常量内嵌 | `BASE_DIR / "data"` / `"workspace"` 等 |
| 单例 | 文件级 `settings` |

---

### 3.3 `main.py` —— CLI 交互入口

#### (1) 兼容两种启动方式

```22:25:harness/main.py
if __package__ in (None, ""):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from harness.config import settings
```

这段保证:**`python harness/main.py` 和 `python -m harness.main` 都能跑**。`__package__` 为空说明是直接当脚本启动,需要把上级目录塞进 `sys.path`。

#### (2) 日志初始化:控制台 WARNING + 文件 INFO

```36:45:harness/main.py
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
```

**理念**:用户控制台要干净;一切细节写文件方便事后审计。`RotatingFileHandler(maxBytes=2MB, backupCount=3)` 防止日志爆盘。

#### (3) `banner()` 与 `main()` 主体

```60:80:harness/main.py
def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    setup_logging()
    if not settings.API_KEY:
        print("❌ 未设置 OPENAI_API_KEY。请把 harness/.env.example 复制为 harness/.env 并填入密钥。")
        return

    load_all()                 # ① 触发所有 @tool 装饰器,把工具塞进 registry
    hooks = make_default_hooks(settings)   # ② 拼装默认钩子链
    agent = Agent(
        registry=registry, hooks=hooks, settings=settings,
        skill_loader=lambda q: load_skills_for(q, settings.SKILLS_DIR),
    )                            # ③ 构造 Agent
    memory = MemoryStore(settings.MEMORY_FILE, keep_turns=settings.MEMORY_KEEP_TURNS)
    history = memory.load()     # ④ 加载上次会话记忆
    print(banner())
```

- **第 ① 步是关键**:必须先 `load_all()`,否则 registry 是空的。
- **第 ② 步** 的 `make_default_hooks` 把"安全 + 截断 + 审计"串起来,详见后面 `hooks.py`。
- **第 ③ 步** 把 `skill_loader` 用 lambda 注入,这是**可扩展点**:你想换 Skill 来源,只需传不同的 callable。
- **第 ④ 步**:记忆和 history **是同一个对象**,所以这个 REPL 不是"每次清零",而是"接续上次"。

#### (4) REPL 命令分发

```84:127:harness/main.py
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
            ...
            results = agent.orchestrate(tasks)
            ...

        # 普通用户输入
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
```

支持的"斜杠命令":

| 命令 | 作用 |
|---|---|
| `/help` | 打印 banner |
| `/tools` | 列出已注册工具名 |
| `/stats` | 看 token / 成本统计 |
| `/clear` | 清空当前 history + 落盘记忆 |
| `/agents 任务1 \|\| 任务2` | 并行派子代理 |
| `/exit`、`/quit` | 退出 |

**`finally` 里再 save 一次**是为了兜底:用户按 Ctrl+C 时也要保证记忆持久化。

**`agent.run(history)` 会就地修改列表**(Append消息),这是 main 的设计选择 —— **history 就是事实之源**,被 main 持有,也传进 agent。

#### 本节学到的范式

- **REPL 模式**:所有斜杠命令就地消费;普通输入走 AI。
- **history = 事实**:`history` 在 main 和 agent 之间共享,谁都不许"返回一份新的",只许"就地修改"。
- **崩溃也不要丢记忆**:`finally` 再保存一次。

---

### 3.4 `smoke_test.py` —— 离线冒烟测试

**目的**:**不依赖任何 LLM API**,验证本机环境 + Harness 各核心模块"都能 import、都能工作"。

#### 用例覆盖范围

```33:84:harness/smoke_test.py
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
out = registry.dispatch("read_file", json.dumps({"path": "hello.txt"}))

# 4-6. 沙箱拦截:路径越界 + 危险命令
out = registry.dispatch("read_file", json.dumps({"path": "../memory.json"}))
check_command_safety("rm -rf /")  # 应抛 ToolSecurityError
out = registry.dispatch("run_bash", json.dumps({"command": "rm -rf /"}))

# 7. 上下文裁剪:不拆散 tool 三件套
trimmed = trim_messages(msgs, max_tokens=80, model=settings.MODEL)

# 8. 记忆存取
mem = MemoryStore(settings.DATA_DIR / "smoke_memory.json", keep_turns=2)
mem.save(msgs)
```

#### 学到什么

| 用例 | 它在断言什么 |
|---|---|
| 工具全部注册 | `@tool` 装饰器 + `load_all` 工作正常 |
| schema 自动生成 | 函数签名 → OpenAI function schema 的链路 |
| dispatch 正常 | JSON 解析、参数过滤正确 |
| 路径越界拦截 | `resolve_within_workspace` 抛 `ToolSecurityError` → dispatch 返回 `BLOCKED:` |
| 危险命令拦截 | `check_command_safety` 抛异常 + dispatch 兜住 |
| 裁剪不拆散 tool | `trim_messages` 只在轮次边界切 |
| 记忆回读 | `MemoryStore` 落盘/读取正常 |

> **冒烟测试不是单测**,目的是:不管你换了模型、换了 API key,你都能用一条命令确认 Harness 自己没坏。

---

### 3.5 `requirements.txt`、`.env`、`.env.example`

```1:3:harness/requirements.txt
# LLM Agent Harness 依赖
openai>=1.30.0
tiktoken>=0.7.0
```

只两个:**OpenAI Python SDK**(`>=1.30`,因为用到了 `model_dump`、流式、BadRequestError)和 **tiktoken**(精确 token 计数)。

`.env.example` 是一份"配置模板",**可入库**;真正的 `.env` 在 `.gitignore` 里。

每条配置项的含义见 `config.py` 与 `.env.example` 内的中文注释,这里不重复列举。

---

## 四、`core/` 引擎逐模块讲解

引擎层是 Harness 的"心脏"。**模块之间是正交的**,通过 `agent.py` 串起来。

```
                     ┌────────────────────┐
                     │       Agent        │
                     │    (主循环)        │
                     └──────┬──────┬──────┘
                            │      │
       调用 LLM,处理消息  ◀──┘      └──▶ 调度工具
            │                                │
   ┌────────▼────────┐                ┌──────▼────────┐
   │   HookManager   │                │ ToolRegistry  │
   │ (4 个时机钩子)   │                │(装饰器+schema)│
   └────────┬────────┘                └──────┬────────┘
            │                                │
            ▼                                ▼
       [安全/审计/截断]                   [security]
```

### 4.1 `core/registry.py` —— 工具注册中心(装饰器 + 自动 schema)

这是 Harness **第一个"魔法"**:写一个普通函数,加 `@tool`,立刻就变成可被 LLM 调用的工具。

#### (1) Python 类型 → JSON Schema 类型

```18:51:harness/core/registry.py
_TYPE_MAP = {str: "string", int: "integer", float: "number", bool: "boolean",
             list: "array", dict: "object", pathlib.Path: "string"}

def _py_type_to_json(annotation: Any) -> str:
    if annotation is inspect.Parameter.empty:
        return "string"
    if annotation in _TYPE_MAP: return _TYPE_MAP[annotation]
    origin = getattr(annotation, "__origin__", None)
    if origin is not None and origin in (list, tuple, set): return "array"
    if origin is dict: return "object"
    try:
        if issubclass(annotation, bool): return "boolean"
        if issubclass(annotation, str): return "string"
        ...
    except TypeError: pass
    return "string"
```

**设计意图**:让函数签名成为"单一真相源"。改注解,schema 就改了,不用单独维护一份 JSON。

#### (2) 从 docstring 提取 `:param x:` 描述

```54:58:harness/core/registry.py
def _param_docs(fn: Callable) -> Dict[str, str]:
    doc = inspect.getdoc(fn) or ""
    return {m.group(1): m.group(2).strip()
            for m in re.finditer(r"^\s*:param\s+(\w+)\s*:\s*(.*)$", doc, re.MULTILINE)}
```

于是 docstring 也参与了 schema 生成。例:

```python
def run_bash(command: str, cwd: str = ".", timeout: int = 30) -> str:
    """在沙箱工作区执行 shell 命令。
    :param command: 要执行的 shell 命令
    :param cwd: 工作目录,相对 workspace
    :param timeout: 超时秒数,默认 30
    """
```

→ 自动生成 schema 片段:
```json
{
  "type": "object",
  "properties": {
    "command": {"type": "string", "description": "要执行的 shell 命令"},
    "cwd":     {"type": "string", "description": "工作目录,相对 workspace"},
    "timeout": {"type": "integer", "description": "超时秒数,默认 30"}
  },
  "required": ["command"]
}
```

#### (3) `Tool` 类与 `ToolRegistry`

```91:112:harness/core/registry.py
class Tool:
    __slots__ = ("name", "fn", "description", "schema", "sandboxed", "permission")
    def __init__(self, name, fn, description=None, schema=None,
                 sandboxed=True, permission="allow"): ...

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            logger.warning("覆盖已注册工具: %s", tool.name)
        self._tools[tool.name] = tool
    ...
```

**`__slots__` 节省内存,加速属性访问**;`sandboxed` / `permission` 留作未来的策略钩子(本项目没直接读它,但已占好位)。

#### (4) `dispatch` —— 万能工具分发表

```126:165:harness/core/registry.py
def dispatch(self, name: str, arguments: str, hooks=None) -> str:
    """永远返回字符串(给模型看),绝不向上抛工具执行异常。"""
    tool = self._tools.get(name)
    if tool is None:
        return f"unknown tool: {name}"

    # (a) JSON 解析
    try:
        args = json.loads(arguments or "{}")
    except json.JSONDecodeError as e:
        return f"ERROR: 工具参数不是合法 JSON: {e}\n原始参数: {arguments!r}"
    if not isinstance(args, dict):
        return f"ERROR: 工具参数必须是 JSON object,收到 {type(args).__name__}"

    # (b) 参数过滤:只传签名内存在的参数(防止 LLM 多塞了字段)
    sig = inspect.signature(tool.fn)
    allowed = {k: v for k, v in args.items() if k in sig.parameters}
    extra = set(args) - set(allowed)
    if extra:
        logger.warning("工具 %s 收到未知参数 %s,已丢弃", name, extra)
    args = allowed

    # (c) 执行 + hook 链 + 异常兜底
    try:
        if hooks is not None:
            hooks.run_pre_tool(name, args)
        result = tool.fn(**args)
    except ToolSecurityError as e:
        return f"BLOCKED: {e}"
    except Exception as e:
        result = f"ERROR: 工具执行异常 {type(e).__name__}: {e}"

    if hooks is not None:
        result = hooks.run_post_tool(name, args, result)
    return str(result)
```

这一段是 Harness 的"安全网":

| 处置 | 为什么 |
|---|---|
| 参数解析失败 → 返回 `ERROR:` | LLM 给的 JSON 常有语法错;**让它重试,不要崩** |
| 参数必须是 dict | Function calling 协议就要求 dict |
| 参数过滤丢掉未知字段 | 模型可能"幻想"出签名里不存在的字段,直接丢弃更稳 |
| `ToolSecurityError` 转为 `BLOCKED:` | 这是 hook 主动抛的,**故意让模型看见**,以便它自我修正 |
| 任意 `Exception` → `ERROR:` | **工具层绝不能让主循环挂掉** |
| 始终 `return str(...)` | LLM 只读字符串 |

#### (5) `@tool` 装饰器:裸用与带参双写法

```172:195:harness/core/registry.py
def tool(name=None, description=None, sandboxed=True, permission="allow"):
    def deco(fn):
        registry.register(Tool(name=name or fn.__name__, fn=fn, ...))
        return fn
    if callable(name):  # 裸 @tool 用法
        fn, name = name, None
        return deco(fn)
    return deco
```

写法示例:

```python
@tool
def read_file(path: str) -> str: ...

@tool(name="my_bash", description="自定义 shell")
def my_shell(cmd: str): ...
```

---

### 4.2 `core/hooks.py` —— 横切关注点(Hook 链)

> 企业级 Harness **所有"和主流程正交"的事**(安全 / 审计 / 限流 / 截断)都做成 hook,而不是散落在工具或主循环里。

#### (1) `HookManager`:4 个时机槽

```13:65:harness/core/hooks.py
class HookManager:
    def __init__(self):
        self._pre_llm: List[Callable] = []
        self._post_llm: List[Callable] = []
        self._pre_tool: List[Callable] = []
        self._post_tool: List[Callable] = []

    def on_pre_llm(self, fn): self._pre_llm.append(fn); return fn
    def on_post_llm(self, fn): self._post_llm.append(fn); return fn
    def on_pre_tool(self, fn): self._pre_tool.append(fn); return fn
    def on_post_tool(self, fn): self._post_tool.append(fn); return fn

    def run_pre_tool(self, name, args):
        for fn in self._pre_tool:
            fn(name, args)        # 不返回值(截断=抛 ToolSecurityError)

    def run_post_tool(self, name, args, output):
        for fn in self._post_tool:
            r = fn(name, args, output)
            if r is not None:
                output = r         # 后一个 hook 可消费前一个 hook 的产物
        return output
```

| 槽 | 签名 | 何时跑 | 返回值约定 |
|---|---|---|---|
| `pre_llm` | `(messages, **ctx)` | LLM 调用前 | 返回非 None 表示改写 messages |
| `post_llm` | `(msg_dict, **ctx)` | LLM 返回后 | 返回非 None 表示改写 msg_dict |
| `pre_tool` | `(name, args)` | 工具执行前 | **抛异常=拦截** |
| `post_tool` | `(name, args, output)` | 工具返回后 | 返回非 None=改写 output |

**返回 None 表示"不动"** —— 这是 Python 钩子里最优雅的契约。

#### (2) `make_default_hooks()` 出厂钩子链

```68:103:harness/core/hooks.py
def make_default_hooks(settings) -> HookManager:
    from .security import check_command_safety, ToolSecurityError

    hooks = HookManager()
    audit = getattr(settings, "ENABLE_AUDIT", True)

    # 1) 危险命令拦截(工具执行前)
    @hooks.on_pre_tool
    def _safety(name, args):
        if name == "run_bash":
            check_command_safety(args.get("command", ""))

    # 2) 超长工具输出截断(工具执行后)
    @hooks.on_post_tool
    def _truncate(name, args, output):
        cap = getattr(settings, "TOOL_OUTPUT_MAX_CHARS", 5000)
        if len(output) > cap:
            return output[:cap] + f"\n...(truncated by hook, total {len(output)} chars)..."
        return output

    # 3) 审计日志(LLM 前后)
    if audit:
        @hooks.on_pre_llm
        def _audit_in(messages, **ctx):
            logger.info("[LLM->] iteration=%s messages=%s chars=%s", ...)

        @hooks.on_post_llm
        def _audit_out(msg_dict, **ctx):
            logger.info("[<-LLM] finish=%s tool_calls=%s content_chars=%s", ...)
    return hooks
```

**这 5 行代码 (`@hooks.on_xxx`) 展示了 Harness 钩子模式的三种典型用例:**
1. **拦截式**(`_safety`):抛 `ToolSecurityError` 终止工具;
2. **改写式**(`_truncate`):返回新字符串;
3. **观察式**(`_audit_*`):什么都不返回,只写日志。

---

### 4.3 `core/security.py` —— 安全层(命令黑名单 / 路径沙箱 / 环境清洗)

Harness 铁律:**LLM 输出的内容一律不可信。任何触碰 OS 的操作都要过这里。**

#### (1) `ToolSecurityError`

```14:15:harness/core/security.py
class ToolSecurityError(Exception):
    """工具被安全层拦截(例如危险命令 / 路径越界)。"""
```

这个自定义异常在 `dispatch` 中被显式捕获,转成 `BLOCKED:` 字符串回到 LLM。

#### (2) 黑名单

```19:49:harness/core/security.py
DANGEROUS_SUBSTRINGS = [
    "rm -rf /", "rm -rf ~", "rm -fr /", "rm -fr ~",
    "chmod 777 /", "chmod -r 777 /",
    "curl | bash", "wget | bash",
    ":(){:|:&};:",          # fork bomb
    "mkfs.", "dd if=/dev/zero of=/dev/",
    "shutdown", "reboot", "halt",
    "format c:", "del /s /q c:", "rd /s /q c:",
    "> /dev/sda",
]

def check_command_safety(command: str) -> None:
    if not isinstance(command, str):
        raise ToolSecurityError(...)
    normalized = " ".join(command.split()).lower()  # 折叠空白 + 小写
    for bad in DANGEROUS_SUBSTRINGS:
        if bad.lower() in normalized:
            raise ToolSecurityError(f"危险命令被拦截: {command!r} (命中黑名单 {bad!r})")
```

**设计原则**:**宁可误杀,不可放过**。注释里明确写了这一点。

#### (3) 路径沙箱

```66:85:harness/core/security.py
def resolve_within_workspace(path, workspace, must_exist: bool = False) -> pathlib.Path:
    ws = pathlib.Path(workspace).resolve()
    p = pathlib.Path(str(path)).expanduser()
    if not p.is_absolute():
        p = ws / p
    p = p.resolve()  # resolve() 会解出 '..' 的真实位置
    try:
        p.relative_to(ws)
    except ValueError:
        raise ToolSecurityError(f"路径越界,不允许访问 workspace 之外: {p}")
    if must_exist and not p.exists():
        raise ToolSecurityError(f"路径不存在: {p}")
    return p
```

**关键之处**:`p.resolve()` 会把 `"../../../etc/passwd"` 这种相对路径解成绝对路径;然后用 `p.relative_to(ws)` 验证它仍在 ws 里 —— **这是抵御"目录穿越攻击"的标准操作**。

#### (4) 环境清洗

```52:63:harness/core/security.py
SENSITIVE_HINTS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIAL")

def sanitize_env(env=None) -> Dict[str, str]:
    src = dict(env if env is not None else os.environ)
    clean = {}
    for k, v in src.items():
        if any(hint in k.upper() for hint in SENSITIVE_HINTS):
            continue
        clean[k] = v
    return clean
```

**`run_bash` 调用时用 `env=sanitize_env(os.environ)`**,确保即使把命令给了一个外部脚本,**`OPENAI_API_KEY` 等不会被泄漏**。

---

### 4.4 `core/messages.py` —— 消息工具(dict 化 / token 计数 / 轮次裁剪)

#### (1) `to_dict` —— 把 SDK 的 Pydantic 对象统一化

```16:25:harness/core/messages.py
def to_dict(m) -> dict:
    if hasattr(m, "model_dump"):
        m = m.model_dump(exclude_none=True)
    if isinstance(m, dict) and m.get("tool_calls"):
        m["tool_calls"] = [
            tc.model_dump(exclude_none=True) if hasattr(tc, "model_dump") else tc
            for tc in m["tool_calls"]
        ]
    return m
```

为什么需要?**SDK 返回的是对象,JSON 落盘需要 dict**。这一行函数让所有上下游都以为消息一直是"普通字典"。

#### (2) `count_tokens` —— 精确 token 统计,带降级

```28:54:harness/core/messages.py
def _get_encoder(model: str):
    if tiktoken is None: return None
    try: return tiktoken.encoding_for_model(model)
    except Exception:
        try: return tiktoken.get_encoding("cl100k_base")
        except Exception: return None

def count_tokens(messages, model="gpt-4o-mini"):
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
```

**两层降级**:
- 拿不到该模型的精确编码 → 退回 `cl100k_base`(绝大多数模型通用);
- 拿不到任何编码 → 用 4 字符≈1 token 的估算式。

**为什么 json.dumps 后再 encode?** 因为 OpenAI 实际收费的方式接近"把整条消息序列化成 JSON 后编码",这样与账单最接近。

#### (3) `group_turns` —— 轮次切分

```57:74:harness/core/messages.py
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
```

**核心不变式**:每组以 `user` 开始。原因是:OpenAI API 要求"有 `assistant.tool_calls` 就必须有对应的 `tool` 回包",而一个 `tool_calls` 通常紧跟 user 之后产生。**只要按 user 切,就不会切坏"工具三件套"**。

#### (4) `trim_messages` —— 只在轮次边界裁

```77:113:harness/core/messages.py
def trim_messages(messages, max_tokens, model="gpt-4o-mini"):
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
        spare_chars = max((max_tokens - used) * 4 - 40, 40)
        for m in last_turn:
            content = m.get("content") or ""
            if isinstance(content, str) and len(content) > spare_chars:
                m["content"] = content[:spare_chars] + "...[truncated]..."
        kept = [last_turn]

    removed = max(0, total - used)
    placeholder = {"role": "system", "content": f"...(earlier context trimmed, removed ~{removed} tokens)..."}
    logger.info("trim: %s tokens -> %s tokens (removed %s tokens)", total, used, removed)
    return heads + [placeholder] + [m for g in kept for m in g]
```

**算法要点**:
1. **system 消息永不动**(它对模型行为最重要)。
2. 从最近的轮次开始装,装不下就停。
3. 全部装不下的话,对最近一轮的内容做字符级截断,**宁截不丢**(否则就把"完整三件套"也截烂了)。
4. 在 system 之后插入一条占位 `placeholder` 明示"context 已被裁",避免模型以为没发生过。

---

### 4.5 `core/memory.py` —— 跨会话持久化记忆

```12:46:harness/core/memory.py
class MemoryStore:
    def __init__(self, path, keep_turns: int = 3):
        self.path = pathlib.Path(path)
        self.keep_turns = keep_turns

    def load(self) -> List[dict]:
        if not self.path.exists(): return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("memory 读取失败,将清空重建: %s", e)
            return []
        if not isinstance(data, list): return []
        return [to_dict(m) for m in data]

    def save(self, messages, keep_turns=None) -> None:
        msgs = [to_dict(m) for m in messages]
        if not msgs: return
        keep_turns = keep_turns or self.keep_turns
        sys_msg = msgs[0] if msgs[0].get("role") == "system" else None
        body = [m for m in msgs if m.get("role") != "system"]
        turns = group_turns(body)
        keep = ([sys_msg] if sys_msg else []) + [m for g in turns[-keep_turns:] for m in g]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(keep, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("memory saved: %s messages (%s turns)", len(keep), min(len(turns), keep_turns))

    def clear(self) -> None:
        if self.path.exists(): self.path.unlink()
        logger.info("memory cleared")
```

#### 设计要点
- **`keep_turns`** 默认 3,只保留最近 3 轮对话。够长不会爆,够短不会丢上下文。
- **落盘时再裁剪** → **不裁"内存中的 history"**,只裁"下次启动时的初始 history"。
- **`to_dict` 必走** → 落盘的一定是 dict,不是 Pydantic 对象。

#### 与 `trim_messages` 的差别
| | `trim_messages` | `MemoryStore.save` |
|---|---|---|
| 时机 | 每次 LLM 调用前 | 每次用户消息后 |
| 触发对象 | `messages`(临时喂给模型) | `messages`(下次启动的历史) |
| 颗粒度 | token 预算 | 轮次计数 |

两者都用 `group_turns`,这是共同的"安全切刀"。

---

### 4.6 `core/skills.py` —— Skill 前置匹配加载

```1:32:harness/core/skills.py
"""Skill 加载:扫描 skills/ 下 .md 的 frontmatter,按 description 关键词匹配用户问题。"""

def load_skills_for(user_query: str, skills_dir) -> str:
    sd = pathlib.Path(skills_dir)
    if not sd.exists(): return ""
    matched = []
    for fn in sorted(os.listdir(sd)):
        if not fn.endswith(".md"): continue
        try:
            text = (sd / fn).read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("skill 读取失败 %s: %s", fn, e)
            continue
        m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        if not m: continue
        meta = dict(re.findall(r"^(\w+):\s*(.*)$", m.group(1), re.MULTILINE))
        desc = meta.get("description", "")
        if any(kw in user_query for kw in desc.split() if len(kw) > 2):
            matched.append(text)
            logger.info("skill 命中: %s", fn)
    return "\n\n".join(matched)
```

#### 工作机制
1. 扫描 `skills_dir` 下所有 `.md`。
2. 提取 `---` 之间的 frontmatter(类似 Markdown blog 的 metadata 头)。
3. 从 frontmatter 里读 `description: 关键词1 关键词2 ...`。
4. **匹配**:`description` 中长度 > 2 的每个词是否出现在用户问题中。
5. 命中则把整个文件内容拼到 system prompt 里。

示例 skill 文件:
```markdown
---
description: excel 表格 CSV 数据分析
---

# Excel 处理
## 何时加载
用户提到表格/分析/导出 CSV 时。
## 工作流
1. ...
```

> **注意**:本项目根目录里**没有 `skills/`**(`SKILLS_DIR` 默认指向 `<项目>/skills`)。你可以自己创建,详见后文"扩展方法"。

---

### 4.7 `core/subagent.py` —— 子代理(隔离上下文 + 并行)

```1:48:harness/core/subagent.py
"""Sub-Agent:独立上下文、受限工具集、只回传摘要;支持线程池并行。"""

DEFAULT_SUBAGENT_SYSTEM = (
    "你是子代理。只完成分配给你的任务,返回简洁的最终摘要,"
    "不要复述过程,不要回复与任务无关的内容。"
)

def run_subagent(task, system=None, tools=None, model=None,
                 max_tokens=2000, client=None) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system or DEFAULT_SUBAGENT_SYSTEM},
            {"role": "user",   "content": task},
        ],
        "max_tokens": max_tokens,
    }
    if tools: payload["tools"] = tools
    r = client.chat.completions.create(**payload)
    return r.choices[0].message.content or ""

def run_subagents_parallel(tasks, system=None, tools=None, model=None,
                           max_tokens=2000, client=None, workers=4) -> List[str]:
    def one(task):
        try:
            return run_subagent(task, system=system, tools=tools, model=model,
                                max_tokens=max_tokens, client=client)
        except Exception as e:
            logger.exception("子代理失败")
            return f"ERROR: {type(e).__name__}: {e}"
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(one, tasks))
```

#### 设计要点
- **隔离上下文**:子代理只看自己的 `task`,**完全不知道主 agent 的对话历史**。
- **强制摘要**:`DEFAULT_SUBAGENT_SYSTEM` 写明了"返回简洁最终摘要,不要复述过程",**避免子代理的内部推理污染主上下文**。
- **工具白名单**:由 `Agent.orchestrate` 通过 `tools=[...]` 传 schemas,**只给子代理有限工具**。
- **并行**:`ThreadPoolExecutor` 而不是 `ProcessPoolExecutor`,因为任务是 I/O 密集的(LLM 调用)。
- **错误隔离**:单个失败返回 `ERROR: ...` 占位,不拖垮整批。

#### 用法(`Agent.orchestrate`)
```python
def orchestrate(self, tasks, system=None, tools=None, workers=4, max_tokens=1200):
    schemas = self.registry.schemas_for(tools) if tools is not None else None
    return run_subagents_parallel(
        tasks, system=system, tools=schemas, model=self.settings.MODEL,
        max_tokens=max_tokens, client=self.client, workers=workers,
    )
```

CLI 触发:`/agents "查天气" || "算汇率" || "翻译句子"`。

---

### 4.8 `core/agent.py` —— 主循环(大脑 + 手脚协调中枢)

这是 Harness 最核心的"调度"。

#### (1) `AgentStats` —— 成本/调用统计

```31:54:harness/core/agent.py
@dataclass
class AgentStats:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    tool_calls: int = 0
    iterations: int = 0
    started_at: float = field(default_factory=time.time)

    def record(self, usage):
        if not usage: return
        self.prompt_tokens += getattr(usage, "prompt_tokens", 0) or 0
        self.completion_tokens += getattr(usage, "completion_tokens", 0) or 0
        self.total_tokens += getattr(usage, "total_tokens", 0) or 0

    def summary(self) -> str:
        return (f"calls={self.calls} iterations={self.iterations} tool_calls={self.tool_calls} "
                f"prompt_tokens={self.prompt_tokens} completion_tokens={self.completion_tokens} "
                f"total_tokens={self.total_tokens} elapsed={time.time() - self.started_at:.1f}s")
```

`/stats` 命令就是打印 `self.stats.summary()`。

#### (2) `build_system` —— 动态拼 system prompt

```68:77:harness/core/agent.py
def build_system(self, messages):
    parts = [self.settings.BASE_SYSTEM]
    last_user = next((str(m.get("content", "")) for m in reversed(messages)
                      if m.get("role") == "user"), "")
    if last_user:
        skill = self.skill_loader(last_user)
        if skill:
            parts.append("# 已加载 Skill\n" + skill)
    parts.append("可用工具: " + ", ".join(self.registry.names()) or "(无工具)")
    return "\n\n".join(parts)
```

三层拼接:**基础系统提示 + 动态加载的 Skill + 工具清单**。

#### (3) `_call` —— 指数退避重试

```80:110:harness/core/agent.py
RETRYABLE = (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError)

def _call(self, system, messages):
    payload = dict(model=self.settings.MODEL,
                   messages=[{"role": "system", "content": system}] + messages,
                   max_tokens=self.settings.MAX_OUTPUT_TOKENS,
                   temperature=self.settings.TEMPERATURE)
    schemas = self.registry.schemas()
    if schemas: payload["tools"] = schemas

    last_err = None
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
            logger.warning("LLM 调用失败(第 %s/%s 次) ... %.1fs 后重试", ...)
            if attempt < self.settings.RETRY_MAX:
                time.sleep(delay)
    raise last_err
```

- **重试白名单**:`RETRYABLE` 只对"网络/限流/服务端错"重试,`BadRequestError`(参数错)不重试 —— 错就是错,重试没用。
- **退避**:`RETRY_BASE_DELAY * 2^(attempt-1)` —— 第 1 次 1s,第 2 次 2s,第 3 次 4s,...

#### (4) `_call_stream` —— 流式 + 工具增量拼装

```112:161:harness/core/agent.py
def _call_stream(self, payload):
    payload = dict(payload, stream=True, stream_options={"include_usage": True})
    try:
        stream = self.client.chat.completions.create(**payload)
    except BadRequestError:
        # 某些兼容端点不支持 stream_options,降级
        logger.warning("服务端不支持 stream_options,降级为普通流")
        payload.pop("stream_options", None)
        stream = self.client.chat.completions.create(**payload)

    text_parts = []
    tool_calls = {}  # index -> {id, name, arguments}
    finish_reason = None
    usage = None

    for chunk in stream:
        if getattr(chunk, "usage", None) is not None: usage = chunk.usage
        choice = chunk.choices[0] if chunk.choices else None
        if choice is None: continue
        if choice.finish_reason: finish_reason = choice.finish_reason
        delta = choice.delta
        if delta is None: continue
        if delta.content:
            text_parts.append(delta.content)
            print(delta.content, end="", flush=True)   # 边到边打
        for tc in delta.tool_calls or []:
            slot = tool_calls.setdefault(tc.index, {"id": None, "function": {"name": None, "arguments": ""}})
            if tc.id: slot["id"] = tc.id
            if tc.function is not None:
                if tc.function.name: slot["function"]["name"] = tc.function.name
                if tc.function.arguments: slot["function"]["arguments"] += tc.function.arguments
    print(flush=True)

    msg_dict = {"role": "assistant", "content": "".join(text_parts) or None}
    if tool_calls:
        msg_dict["tool_calls"] = [
            {"id": s["id"], "type": "function",
             "function": {"name": s["function"]["name"], "arguments": s["function"]["arguments"]}}
            for _, s in sorted(tool_calls.items())
        ]
    self.stats.record(usage)
    return msg_dict, finish_reason
```

**核心难点:增量工具调用的拼装**。
- 流式 API 中,同一个工具的 `tool_calls` 增量可能跨多个 chunk。
- 解析策略:`tool_calls` 是 list,**按 `index` 索引**聚合。
  - `tc.id` 来一次就赋值一次(`if tc.id` 防重复)。
  - `tc.function.name` 同理。
  - `tc.function.arguments` **累加**(它是 JSON 的片段,要拼起来)。
- 最终按 `index` 排序,恢复成 OpenAI 协议的 `tool_calls` 列表。

`BadRequestError` 降级是因为有的兼容端点(比如某些国内代理)不支持 `stream_options`。

#### (5) `run` —— 主循环总成

```164:196:harness/core/agent.py
def run(self, messages, max_iterations=None) -> str:
    """在给定消息列表上运行 agent,直至模型停止调用工具。会就地修改 messages。"""
    max_iter = max_iterations or self.settings.MAX_ITERATIONS
    final_text = ""
    for iteration in range(1, max_iter + 1):
        self.stats.iterations = iteration
        # 裁剪上下文(只在轮次边界切)
        messages[:] = trim_messages(messages, self.settings.CONTEXT_BUDGET_TOKENS, self.settings.MODEL)

        system = self.build_system(messages)
        state = {"start": time.time()}
        self.hooks.run_pre_llm(messages, iteration=iteration, state=state)

        msg_dict, finish = self._call(system, messages)
        self.hooks.run_post_llm(msg_dict, iteration=iteration, state=state, finish_reason=finish)
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
            print(f"\n[工具 {name} 完成,输出 {len(output)} 字符]")
            logger.info("tool %s -> %s chars", name, len(output))

    logger.warning("达到最大迭代次数 %s,强制返回", max_iter)
    return final_text
```

**流程图(每一轮 = LLM 一次响应)**:
```
┌─────────── 轮 N ───────────┐
│ 1. 裁剪上下文              │
│ 2. 拼 system               │
│ 3. pre_llm hook            │
│ 4. _call LLM(重试+流式)    │
│ 5. post_llm hook           │
│ 6. append msg_dict         │
│ 7. 有 tool_calls?          │
│      ↓是           ↓否     │
│   dispatch  →  return      │
│   append tool 回复          │
│   pre/post_tool hook        │
│ 8. 进入下一轮              │
└────────────────────────────┘
```

**两个细节点**:
- `messages[:] = trim_messages(...)` —— **`messages` 是 main 持有的列表**,用切片赋值就地替换内容,实现在同一对象上的"重新清洗"。
- 返回 `""` 而非 raise —— **宁可让用户拿到空结果也不挂掉**(只有 LLM 自己停止才返回 `content`,如果到了迭代上限,前几次没产出 final text 就给空字符串)。

#### (6) `orchestrate` —— 派子代理

```199:207:harness/core/agent.py
def orchestrate(self, tasks, system=None, tools=None, workers=4, max_tokens=1200):
    schemas = self.registry.schemas_for(tools) if tools is not None else None
    return run_subagents_parallel(
        tasks, system=system, tools=schemas, model=self.settings.MODEL,
        max_tokens=max_tokens, client=self.client, workers=workers,
    )
```

只做了一件事:**把"主 agent 的工具集"过滤成"子代理的白名单"**,然后丢给 `subagent` 模块跑。

---

## 五、`tools/` 内置工具逐文件讲解

### 5.1 `tools/__init__.py` —— `load_all()` 注册入口

```1:13:harness/tools/__init__.py
def load_all() -> None:
    from . import bash, filesystem, search  # noqa: F401
    logger.info("tools registered: %s", ", ".join(registry.names()))
```

**关键**:导入即注册 —— `import` 会执行模块顶层的 `@tool` 装饰器。`main.py` 启动时调一次 `load_all()`,所有内置工具入册。

**新增工具只要两步**:
1. 在 `tools/` 下新建文件,写个 `@tool` 装饰的函数。
2. 在 `tools/__init__.py` 的 `load_all()` 里加一行 `from . import newtool`。

### 5.2 `tools/bash.py` —— `run_bash` 沙箱 shell

```13:41:harness/tools/bash.py
@tool(description="执行 shell 命令,返回 stdout/stderr。cwd 相对于工作区。")
def run_bash(command: str, cwd: str = ".", timeout: int = 30) -> str:
    """在沙箱工作区执行 shell 命令。
    :param command: 要执行的 shell 命令
    :param cwd: 工作目录,相对 workspace
    :param timeout: 超时秒数,默认 30
    """
    check_command_safety(command)                          # 1
    workdir = resolve_within_workspace(cwd, settings.WORKSPACE)  # 2
    workdir.mkdir(parents=True, exist_ok=True)
    env = sanitize_env(os.environ)                         # 3
    ...
    out = subprocess.run(command, shell=True, capture_output=True, text=True,
                         timeout=timeout, cwd=str(workdir), env=env,
                         encoding="utf-8", errors="replace")
    return f"exit={out.returncode}\nstdout:\n{out.stdout}\nstderr:\n{out.stderr}"
```

三层防御:
1. **黑名单** —— `check_command_safety`
2. **沙箱** —— `resolve_within_workspace` 确保 cwd 不出 workspace
3. **环境清洗** —— `sanitize_env`

`timeout=30s` 默认,**防止模型产生"无限循环命令"**。`errors="replace"` 让编码异常不会崩。

### 5.3 `tools/filesystem.py` —— `read_file` / `write_file` / `list_dir`

```12:65:harness/tools/filesystem.py
@tool(description="读取文本文件,返回前 max_chars 个字符。")
def read_file(path: str, max_chars: int = 20000) -> str:
    p = resolve_within_workspace(path, settings.WORKSPACE)
    if not p.exists(): return f"ERROR: 文件不存在: {p}"
    if p.is_dir():     return f"ERROR: 这是目录,请用 list_dir: {p}"
    data = p.read_text(encoding="utf-8", errors="replace")
    if len(data) > max_chars:
        return data[:max_chars] + f"\n...(truncated, total {len(data)} chars)..."
    return data

@tool(description="写入文件(覆盖已有内容),自动创建父目录,仅允许写入 workspace 内。")
def write_file(path: str, content: str) -> str:
    p = resolve_within_workspace(path, settings.WORKSPACE)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"written {len(content)} chars -> {p}"

@tool(description="列出目录内容(名称/类型/大小)。")
def list_dir(path: str = ".") -> str:
    p = resolve_within_workspace(path, settings.WORKSPACE)
    ...
    for entry in sorted(os.scandir(p), key=lambda e: e.name):
        ...
```

每个工具都**先过 `resolve_within_workspace`** —— 这是 Harness 的"最小权限"原则的实际体现:**任何工具拿了路径就先校验**。

### 5.4 `tools/search.py` —— `grep` 正则搜索

```13:44:harness/tools/search.py
SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", "__pycache__",
             ".venv", "venv", ".idea", ".vscode"}

@tool(description="在文件中按正则搜索,返回 文件:行号:内容(最多 max_results 条)。")
def grep(pattern: str, path: str = ".", max_results: int = 50) -> str:
    root = resolve_within_workspace(path, settings.WORKSPACE)
    ...
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]  # 就地改 skip
        for fn in filenames:
            ...
            for lineno, line in enumerate(lines, 1):
                if re.search(pattern, line):
                    rel = fp.relative_to(settings.WORKSPACE)
                    hits.append(f"{rel}:{lineno}: {line.strip()[:200]}")
                    if len(hits) >= max_results:
                        return "\n".join(hits) + "\n...(更多匹配被截断)"
    return "\n".join(hits) if hits else f"no matches for {pattern!r} in {root}"
```

**两个工程细节**:
- `dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]` —— **就地修改 os.walk 给的目录列表**,直接 pruning,省得递归进入。
- 返回格式 `file:line: content` —— 跟 `grep` 命令行输出对齐,**模型看着熟悉**。
- `max_results` 上限,**防止模型一查就 dump 几 MB 日志**。

---

## 六、运行时数据目录(`data/`、`workspace/`、`logs/`)

| 目录 | 来源 | 用途 |
|---|---|---|
| `data/memory.json` | `MemoryStore.save` | 跨会话记忆 |
| `data/smoke_memory.json` | `smoke_test.py` 临时 | 测试时创建,可删 |
| `workspace/` | `settings.WORKSPACE` | 沙箱根目录,所有文件/命令都被关在这里 |
| `workspace/hello.txt` | `smoke_test.py` 写入 | 测试时创建,可删 |
| `logs/harness.log` | `RotatingFileHandler` | 所有 INFO 级别日志,`maxBytes=2MB` 滚动 3 份 |

> **全部路径都是 `config.py` 里 `BASE_DIR / "子目录"`** —— 在哪里 clone 都能直接跑。

---

## 七、执行流程全景(从用户按下回车到文本输出)

下面按时间顺序把 **9 个文件**穿成一条线:

```
[1] main.py 拿到 ">>> ls workspace" 这条输入
       ↓
[2] main.py 发现它不是 / 命令,所以:
       history.append({role:user, content:"ls workspace"})
       agent.run(history)
       ↓
[3] agent.py 的 run() 启动循环 iteration=1
       messages[:] = trim_messages(...)         ← core/messages.py
       system  = build_system(messages)          ← agent.py 自己 + skill_loader
       ↓
[4] hooks.run_pre_llm(messages, ...)           ← core/hooks.py
       ↓
[5] _call(system, messages)
       payload = {model, messages, max_tokens, temperature, tools=[...registry.schemas()]}
       msg_dict, finish = _call_stream(payload)  ← agent.py(流式拼装)
       ↓
[6] hooks.run_post_llm(msg_dict, ...)          ← core/hooks.py
       messages.append(msg_dict)
       ↓
[7] msg_dict.get("tool_calls") 不空 → 进入工具执行分支
       for tc in tool_calls:
           hooks.run_pre_tool(name, args)       ← core/hooks.py + security
           result = registry.dispatch(name, args, hooks=self.hooks)
                                                 ↑ core/registry.py(走 JSON 解析、参数过滤、调用)
                                                     ↑ tools/list_dir 函数(过 workspace 沙箱)
           hooks.run_post_tool(name, args, result)
                                                 ↑ core/hooks.py(超长截断)
           messages.append({role:tool, tool_call_id, content:result})
       ↓
[8] 进入 iteration=2,再次调 LLM → 模型看完工具输出后写 final
       msg_dict 没有 tool_calls → return msg_dict["content"]
       ↓
[9] main.py: memory.save(history) 落盘
```

—— **下一次启动**:`main.py` 读 `data/memory.json` → `MemoryStore.load()` → `history = ...`。对话接续。

---

## 八、扩展方法:加一个工具 / 加一个 hook / 加一个 skill

### 8.1 加一个工具(3 步)

**例:加一个 `http_get` 工具**

1. **新建 `tools/http.py`**:
   ```python
   from ..config import settings
   from ..core.registry import tool
   import urllib.request

   @tool(description="发起 HTTP GET,返回响应体前 N 字符。")
   def http_get(url: str, max_chars: int = 5000) -> str:
       """发起 HTTP GET 请求。
       :param url: 完整 URL
       :param max_chars: 最多返回字符数
       """
       with urllib.request.urlopen(url, timeout=10) as resp:
           data = resp.read().decode("utf-8", errors="replace")
       if len(data) > max_chars:
           return data[:max_chars] + f"\n...(truncated, total {len(data)} chars)"
       return data
   ```

2. **`tools/__init__.py`** 加入口:
   ```python
   def load_all():
       from . import bash, filesystem, search, http  # 加这一行
   ```

3. **重启** → `registry.names()` 多一个 `http_get`。

> *无须改任何其他文件。装饰器 + 注册中心就这一好处。*

### 8.2 加一个 hook(2 步)

**例:加一个"工具调用超过 3 秒就告警"的 hook**

`main.py` 里:

```python
hooks = make_default_hooks(settings)

@hooks.on_pre_tool
def _timing_start(name, args):
    import time
    state[f"start_{name}"] = time.time()    # 需要外层 state

@hooks.on_post_tool
def _timing_end(name, args, output):
    start = state.pop(f"start_{name}", None)
    if start and time.time() - start > 3:
        logger.warning("SLOW TOOL: %s took %.2fs", name, time.time() - start)
    return output
```

(本示例需要外部 `state` dict。Agent 内部也有同名 `state`,是从 `run()` 传进 hook 的;若要引用 Agent 的 state,在你的 hook 包装函数里再自行构造一个即可。)

### 8.3 加一个 Skill(1 步)

**例:加一个"Excel 处理" Skill**

新建 `skills/excel.md`:

```markdown
---
description: excel 表格 CSV 数据分析 导出
---

# Excel 处理

## 工作流
1. 用 read_file 读 .csv
2. 用 run_bash 跑 `python -c "import pandas as pd; ..."`
3. 用 write_file 写结果
```

下一轮用户问"帮我分析这份 excel",`skills.py` 会自动命中、注入 system。**无需改 Python 代码。**

### 8.4 切换子代理工具白名单

```python
agent.orchestrate(
    tasks=["任务 A", "任务 B"],
    tools=["read_file", "grep"],   # 子代理只能用这两个
    workers=4,                      # 并行度
    max_tokens=800,                 # 每个子代理更省
)
```

---

## 九、Harness 范式与最佳实践(从本项目提炼)

下面这些可以**直接迁移到任何 Harness 类项目**。

### 9.1 永远把 "横向能力" 做成 hook,不要塞主循环
- 安全、审计、限流、截断、计时、指标…… **凡是"和 LLM/工具无关但每次都要做的",做成 hook**。
- 主循环只负责"调用 LLM,解析,分发",一旦发现自己在主循环里写"if … log …"就要警觉。

### 9.2 工具注册 = 函数签名 + docstring + 装饰器
- 用 `@tool` 让函数签名成为 schema 的单一真相源。
- docstring 用 `:param name:` 写参数说明,**自动喂给 LLM**。
- 不要去维护一份独立的 schema JSON —— 改一处忘改另一处的噩梦。

### 9.3 工具层不抛异常,只返回字符串
- `dispatch` 捕获一切异常,**统一转 `ERROR:` / `BLOCKED:` 字符串**。
- LLM 拿到字符串才能自我修正;上层一旦崩溃就不是 LLM 自己能解决的事。

### 9.4 安全策略永远在 hook 内、永远在工具外
- `security` 模块是单一真相,工具里只调用,不复写黑名单。
- 路径沙箱用 `resolve().relative_to(workspace)` 标准操作。

### 9.5 上下文管理"只在轮次边界切"
- 用 `group_turns` 把消息按 user 切组,**保证 tool_calls+tool 三件套永远成组**。
- 裁剪分两档:**token 超预算 → 切轮次**;**单轮还超 → 字符级截断 content**。

### 9.6 记忆跨会话、Skill 跨会话、子代理单会话
- **memory** = 跨会话 → 落盘。
- **skill** = 跨会话 → 落盘(markdown + frontmatter)。
- **subagent** = 单会话、隔离 → 只返回摘要,**不能让内部推理污染主上下文**。

### 9.7 重试只重试"可重试的错误"
- 网络、限流、服务端错 → 退避重试。
- 参数错(`BadRequestError`)、逻辑错 → 不重试,直接抛。
- 重试用 `2 ^ (attempt-1)` 指数退避。

### 9.8 流式响应 = 增量拼装工具调用
- 流式 chunk 不完整,同一 `tool_calls.index` 的字段必须靠 `dict.setdefault` + **累加 arguments** 才能拼回。
- `BadRequestError` 时降级 `stream_options`,保证兼容。

### 9.9 配置集中化、优先级明确
- `.env` < 真正的环境变量 < 代码默认(注意 `setdefault` 的语义)。
- 把配置按域分组(LLM / 循环 / 记忆 / 安全 / 日志),别揉成一锅。

### 9.10 入口只做装配,不在里面写业务
- `main.py` 干的事:加载配置 → 触发工具注册 → 装配 hook → 构造 Agent → 进入 REPL。
- 装配代码一旦超过 ~30 行,提示应该抽出"组装函数"或者"框架类"。

### 9.11 测试一条命令,不依赖任何外部
- `smoke_test.py` 是个好范式:**不调 LLM、不调网络**,只验证"骨架能不能用"。
- CI 里加进第一步,先跑 smoke 再跑集成测试,会省无数时间。

### 9.12 日志分两套:控制台干净、文件全量
- 控制台:WARNING+,只让用户看见问题。
- 文件:INFO+,把审计、token、工具调用都写进去,事后回放。

---

## 收尾:把项目当作 "可拆卸的乐高"

回头看这张图,你已经能把 **每一块** 单独拎出来换/扩/卸:

```
   .env              ← 改配置
   config.py         ← 加新字段(Settings 里加一行)
   core/skills.py    ← 改 Skill 源(frontmatter/网络/RAG)
   core/memory.py    ← 换 SQLite/Redis/PG
   core/registry.py  ← 加新工具(写个 @tool)
   core/hooks.py     ← 加新横切(限流/审计/metrics)
   core/security.py  ← 改黑名单/换 AST 校验
   core/subagent.py  ← 换多进程/换 LangGraph/CrewAI
   tools/            ← 增删具体工具
   main.py           ← 改 REPL/换 Web UI/换 API
```

**Harness 的"框架感"不在某一个文件,而在它们之间的合约**:Agent ↔ Hook ↔ Registry ↔ Tool ↔ Security。这五者对齐了,任何一块都能独立演进。
