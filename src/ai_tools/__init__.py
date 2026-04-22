"""
AI企鹅 Tools 工具模块
让企鹅能够主动感知世界、帮助主人干活
"""

from .base import Tool, ToolResult
from .screenshot import ScreenshotTool
from .weather import WeatherTool
from .system import SystemInfoTool, NotificationTool
from .bash import BashTool

__all__ = [
    'Tool',
    'ToolResult',
    'ScreenshotTool',
    'WeatherTool',
    'SystemInfoTool',
    'NotificationTool',
    'BashTool',
]

def get_all_tools():
    """获取所有可用工具"""
    return [
        ScreenshotTool(),
        WeatherTool(),
        SystemInfoTool(),
        NotificationTool(),
        BashTool(),
    ]
