"""
BaseTool - 所有工具的抽象基类

所有内置工具都应继承此基类，实现统一接口。
这使得 ToolLoader 可以通过多态调用 tool.execute(**kwargs)，
而不需要为每个工具维护独立的参数提取逻辑。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseTool(ABC):
    """工具抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称（必须与 tool_definition 中的 name 一致）"""
        pass

    @abstractmethod
    def get_tool_definition(self) -> Dict[str, Any]:
        """返回 OpenAI function calling 格式的工具定义"""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """
        执行工具

        所有参数通过 **kwargs 传入，工具内部自行提取所需参数。
        这样 ToolLoader 可以统一调用 tool.execute(**arguments)。
        """
        pass
