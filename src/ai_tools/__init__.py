"""
AI企鹅 Tools 工具模块
让企鹅能够主动感知世界、帮助主人干活
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 环境变量
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

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
