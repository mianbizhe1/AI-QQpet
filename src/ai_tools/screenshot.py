"""
截图工具 - 使用 screencapture 命令截取屏幕
"""

import subprocess
from datetime import datetime
from pathlib import Path
from .base import Tool, ToolResult


class ScreenshotTool(Tool):
    """截图工具 - 使用 macOS screencapture 命令"""

    name = "screenshot"
    description = "截取当前主人屏幕，了解主人正在做什么。截图会保存到 screen 目录。"
    
    parameters = {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "截图目的，如'看看主人在做什么'"
            }
        }
    }

    def __init__(self):
        super().__init__()
        self.screen_dir = Path("./screen")
        self.screen_dir.mkdir(exist_ok=True)

    def execute(self, description: str = "", **kwargs) -> ToolResult:
        """使用 screencapture 截取屏幕"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            save_path = self.screen_dir / filename

            cmd = ['screencapture', '-x', '-D', '1', str(save_path)]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15
            )

            if result.returncode != 0:
                return ToolResult(
                    success=False,
                    content="",
                    error=f"截屏失败 (exit {result.returncode})"
                )

            if not save_path.exists():
                return ToolResult(
                    success=False,
                    content="",
                    error="截屏文件未生成"
                )

            file_size = save_path.stat().st_size
            size_kb = file_size / 1024

            return ToolResult(
                success=True,
                content=f"截屏成功！保存到 {save_path} ({size_kb:.1f}KB)",
                metadata={
                    'timestamp': timestamp,
                    'filename': filename,
                    'filepath': str(save_path),
                    'size_kb': round(size_kb, 1),
                }
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                content="",
                error="截屏超时"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                content="",
                error=f"截屏异常: {str(e)}"
            )
