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
"""

__version__ = "0.1.0"
