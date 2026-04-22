"""
Tool基类定义
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    content: str
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self):
        return {
            'success': self.success,
            'content': self.content,
            'error': self.error,
            'metadata': self.metadata,
        }


class Tool:
    """Tool基类"""
    
    # 工具名称（LLM调用时使用）
    name: str = "tool"
    
    # 工具描述（告诉LLM这个工具能做什么）
    description: str = "A tool"
    
    # 参数schema（JSON Schema格式）
    parameters: Dict[str, Any] = {}
    
    def execute(self, **kwargs) -> ToolResult:
        """
        执行工具
        子类必须实现
        """
        raise NotImplementedError
    
    def get_schema(self) -> Dict[str, Any]:
        """获取tool的JSON Schema"""
        return {
            'name': self.name,
            'description': self.description,
            'parameters': self.parameters,
        }
