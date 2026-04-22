"""
Bash 工具 - 执行命令行
"""

import subprocess
from pathlib import Path
from .base import Tool, ToolResult


class BashTool(Tool):
    """执行bash命令的工具"""

    name = "bash"
    description = "执行bash命令，如截图、文件操作等。输入完整的命令行指令。"
    
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "要执行的bash命令（不要包含sudo或交互式命令）"
            },
            "timeout": {
                "type": "number",
                "description": "超时时间（秒），默认30秒"
            },
            "reasoning": {
                "type": "string",
                "description": "执行这个命令的原因/用途"
            }
        },
        "required": ["command"]
    }

    def execute(self, command: str, timeout: int = 30, reasoning: str = "", **kwargs) -> ToolResult:
        """
        执行bash命令
        
        Args:
            command: bash命令
            timeout: 超时秒数
            reasoning: 执行原因
        """
        if not command:
            return ToolResult(
                success=False,
                content="",
                error="命令不能为空"
            )

        # 安全检查：禁止某些危险命令
        dangerous = ['rm -rf /', 'mkfs', 'dd if=', ':(){:|:&};:']
        for d in dangerous:
            if d in command:
                return ToolResult(
                    success=False,
                    content="",
                    error=f"禁止执行危险命令: {d}"
                )

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            output = result.stdout.strip() if result.stdout else ""
            error = result.stderr.strip() if result.stderr else ""

            if result.returncode == 0:
                return ToolResult(
                    success=True,
                    content=output or "(命令执行成功，无输出)",
                    metadata={
                        'returncode': result.returncode,
                        'reasoning': reasoning,
                    }
                )
            else:
                return ToolResult(
                    success=False,
                    content=output or "",
                    error=error or f"命令执行失败 (exit {result.returncode})"
                )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                content="",
                error=f"命令超时（{timeout}秒）"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                content="",
                error=f"执行异常: {str(e)}"
            )
