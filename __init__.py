"""LLM Agent Harness —— 企业级多文件版。

架构:
    harness/
    ├── config.py         # 集中配置(.env / 环境变量 / 默认值)
    ├── core/             # 引擎
    │   ├── registry.py   # Tool Registry(装饰器注册 + 自动 schema)
    │   ├── hooks.py      # Hook 链(pre/post LLM + pre/post tool)
    │   ├── security.py   # 危险命令拦截 + 路径沙箱
    │   ├── messages.py   # token 计数 / 上下文裁剪
    │   ├── memory.py     # 跨会话持久化记忆
    │   ├── skills.py     # Skill 加载(frontmatter 匹配)
    │   ├── subagent.py   # 子代理(隔离上下文 / 并行)
    │   └── agent.py      # 主循环(流式 / 重试 / 成本统计)
    ├── tools/            # 内置工具集
    ├── main.py           # CLI 入口
    ├── .env              # 密钥与配置(不入库)
    └── .env.example      # 配置模板

支持的三种启动方式(全部可用):
    # A. 把 harness 视作 Python 包(推荐,适合 CI / 部署)
    cd "d:/study/LLM API"
    python -m harness.main
    python -m harness.smoke_test

    # B. 父目录下直接传脚本路径(老习惯)
    cd "d:/study/LLM API"
    python harness/main.py
    python harness/smoke_test.py

    # C. 把 harness 自身当作项目根目录(IDE 场景,最常用)
    cd harness
    python main.py        # 这里就是 cwd == harness
    python smoke_test.py
"""

import sys as _sys

__version__ = "0.2.0"

# ---------------------------------------------------------------------------
# 兼容 shim:让 harness 在"作为项目根目录直接运行"时也能被解析。
#
# 关键场景:`cd harness && python main.py`(cwd 就是 harness 自己)
# 此时 sys.path[0] 就是 harness/ 自身,Python 找不到名为 'harness' 的顶层包。
#
# 利用 `__init__.py` 必定会在 harness 被 import 时被触发的特性,
# 主动把当前包对象注册到 sys.modules['harness'],作为顶层导入的兜底。
#
# 注意:仅在被 import 时生效(`__name__ != "__main__"`),直接 `python __init__.py`
# 这种诡异调用方式不会受此 shim 影响。
# ---------------------------------------------------------------------------
if __name__ != "__main__":
    _sys.modules.setdefault("harness", _sys.modules[__name__])
