"""Tool Registry:装饰器注册工具 + 自动从 Python 签名生成 OpenAI function schema。

加一个工具只需要写一个普通函数 + @tool 装饰器,schema 自动同步,
分发(dispatch)自动做 JSON 解析、参数过滤、异常兜底,不用再手写 if-elif。
"""
import inspect
import json
import logging
import pathlib
import re
from typing import Any, Callable, Dict, List, Optional

from .security import ToolSecurityError

logger = logging.getLogger("harness.registry")


# ---------- 类型映射 ----------
_TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
    pathlib.Path: "string",
}


def _py_type_to_json(annotation: Any) -> str:
    if annotation is inspect.Parameter.empty:
        return "string"
    if annotation in _TYPE_MAP:
        return _TYPE_MAP[annotation]
    origin = getattr(annotation, "__origin__", None)
    if origin is not None and origin in (list, tuple, set):
        return "array"
    if origin is dict:
        return "object"
    try:
        if issubclass(annotation, bool):
            return "boolean"
        if issubclass(annotation, str):
            return "string"
        if issubclass(annotation, int):
            return "integer"
        if issubclass(annotation, float):
            return "number"
    except TypeError:
        pass
    return "string"


def _param_docs(fn: Callable) -> Dict[str, str]:
    """从 docstring 里提取 :param name: 描述。"""
    doc = inspect.getdoc(fn) or ""
    return {m.group(1): m.group(2).strip()
            for m in re.finditer(r"^\s*:param\s+(\w+)\s*:\s*(.*)$", doc, re.MULTILINE)}


def auto_schema(fn: Callable, description: str, name: Optional[str] = None) -> dict:
    """根据函数签名 + docstring 自动生成 OpenAI function schema。"""
    sig = inspect.signature(fn)
    param_docs = _param_docs(fn)
    properties, required = {}, []
    for pname, p in sig.parameters.items():
        if pname in ("self", "cls"):
            continue
        if p.default is inspect.Parameter.empty:
            required.append(pname)
        properties[pname] = {
            "type": _py_type_to_json(p.annotation),
            "description": param_docs.get(pname, f"{pname} 参数"),
        }
    first_line = (inspect.getdoc(fn) or "").strip().splitlines()
    desc = description or (first_line[0] if first_line else fn.__name__)
    return {
        "type": "function",
        "function": {
            "name": name or fn.__name__,
            "description": desc,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


class Tool:
    __slots__ = ("name", "fn", "description", "schema", "sandboxed", "permission")

    def __init__(self, name: str, fn: Callable, description: Optional[str] = None,
                 schema: Optional[dict] = None, sandboxed: bool = True,
                 permission: str = "allow") -> None:
        self.name = name
        self.fn = fn
        self.description = description or fn.__name__
        self.schema = schema or auto_schema(fn, description, name=name)
        self.sandboxed = sandboxed
        self.permission = permission


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            logger.warning("覆盖已注册工具: %s", tool.name)
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def names(self) -> List[str]:
        return sorted(self._tools)

    def schemas(self) -> List[dict]:
        return [t.schema for t in self._tools.values()]

    def schemas_for(self, names) -> List[dict]:
        return [t.schema for n in names if (t := self._tools.get(n))]

    def dispatch(self, name: str, arguments: str, hooks=None) -> str:
        """执行工具,自动处理:JSON 解析 / 参数过滤 / hook 链 / 异常兜底。

        永远返回字符串(给模型看),绝不向上抛工具执行异常。
        """
        tool = self._tools.get(name)
        if tool is None:
            return f"unknown tool: {name}"

        # 解析参数
        try:
            args = json.loads(arguments or "{}")
        except json.JSONDecodeError as e:
            return f"ERROR: 工具参数不是合法 JSON: {e}\n原始参数: {arguments!r}"
        if not isinstance(args, dict):
            return f"ERROR: 工具参数必须是 JSON object,收到 {type(args).__name__}"

        # 只传签名内存在的参数
        sig = inspect.signature(tool.fn)
        allowed = {k: v for k, v in args.items() if k in sig.parameters}
        extra = set(args) - set(allowed)
        if extra:
            logger.warning("工具 %s 收到未知参数 %s,已丢弃", name, extra)
        args = allowed

        # 执行(hook 抛的 ToolSecurityError 也在这里兜住)
        try:
            if hooks is not None:
                hooks.run_pre_tool(name, args)
            result = tool.fn(**args)
        except ToolSecurityError as e:
            logger.warning("安全拦截 %s: %s", name, e)
            return f"BLOCKED: {e}"
        except Exception as e:  # noqa: BLE001 - 工具异常必须回传而不是崩溃
            logger.exception("工具 %s 执行异常", name)
            result = f"ERROR: 工具执行异常 {type(e).__name__}: {e}"

        if hooks is not None:
            result = hooks.run_post_tool(name, args, result)
        return str(result)


# 全局单例,工具模块 import 它来注册
registry = ToolRegistry()


def tool(name: Optional[str] = None, description: Optional[str] = None,
         sandboxed: bool = True, permission: str = "allow"):
    """工具装饰器。支持两种写法:

        @tool
        def read_file(path: str) -> str: ...

        @tool(name="read_file", description="读文件")
        def read_file(path: str) -> str: ...
    """
    def deco(fn: Callable) -> Callable:
        registry.register(Tool(
            name=name or fn.__name__,
            fn=fn,
            description=description,
            sandboxed=sandboxed,
            permission=permission,
        ))
        return fn

    if callable(name):  # 裸 @tool 用法
        fn, name = name, None
        return deco(fn)
    return deco
