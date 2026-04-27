"""
AI企鹅 Tools 工具模块
让企鹅能够主动感知世界、帮助主人干活
"""

import os
from runtime_paths import existing_paths, env_candidates

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - 允许无 dotenv 的轻量运行
    def load_dotenv(*args, **kwargs):
        return False

# 加载 .env 环境变量
for env_path in existing_paths(env_candidates()):
    load_dotenv(env_path, override=False)

from .base import Tool, ToolResult
from .screenshot import ScreenshotTool
from .browser import BrowserSearchTool, BrowserTool
from .weather import WeatherTool
from .system import SystemInfoTool, NotificationTool
from .bash import BashTool

__all__ = [
    'Tool',
    'ToolResult',
    'ScreenshotTool',
    'BrowserSearchTool',
    'BrowserTool',
    'WeatherTool',
    'SystemInfoTool',
    'NotificationTool',
    'BashTool',
]

def get_all_tools():
    """获取所有可用工具"""
    return [
        ScreenshotTool(),
        BrowserTool(),
        BrowserSearchTool(),
        WeatherTool(),
        SystemInfoTool(),
        NotificationTool(),
        BashTool(),
    ]
