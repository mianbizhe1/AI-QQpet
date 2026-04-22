"""
系统工具 - 获取系统信息、发送通知
"""

import os
import subprocess
from datetime import datetime
from .base import Tool, ToolResult

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class SystemInfoTool(Tool):
    """系统信息工具 - 了解主人设备状态"""

    name = "system_info"
    description = "获取当前系统信息，包括时间、CPU、内存、电池等。"
    
    parameters = {
        "type": "object",
        "properties": {
            "check_items": {
                "type": "array",
                "items": {"type": "string"},
                "description": "要检查的项目，可选: time, cpu, memory, battery, all"
            }
        }
    }

    def execute(self, **kwargs) -> ToolResult:
        check_items = kwargs.get('check_items', ['all'])
        if 'all' in check_items:
            check_items = ['time', 'cpu', 'memory', 'battery']

        info_parts = []

        try:
            # 时间信息（始终可用）
            if 'time' in check_items:
                now = datetime.now()
                info_parts.append(f"🕐 当前时间: {now.strftime('%Y年%m月%d日 %H:%M:%S')}")
                info_parts.append(f"   星期{'一二三四五六日'[now.weekday()]}")

            # CPU/内存/电池需要psutil
            if PSUTIL_AVAILABLE:
                if 'cpu' in check_items:
                    cpu_percent = psutil.cpu_percent(interval=0.5)
                    cpu_count = psutil.cpu_count()
                    info_parts.append(f"💻 CPU: {cpu_percent}% (共{cpu_count}核)")

                if 'memory' in check_items:
                    mem = psutil.virtual_memory()
                    mem_used = mem.used / (1024**3)
                    mem_total = mem.total / (1024**3)
                    info_parts.append(f"🧠 内存: {mem_used:.1f}GB / {mem_total:.1f}GB ({mem.percent}%)")

                if 'battery' in check_items:
                    battery = psutil.sensors_battery()
                    if battery:
                        plugged = "🔌 正在充电" if battery.power_plugged else "🔋 使用电池"
                        info_parts.append(f"🔋 电池: {battery.percent}% {plugged}")
                    else:
                        info_parts.append("🔋 电池: 无电池或不支持")
            else:
                if any(x in check_items for x in ['cpu', 'memory', 'battery']):
                    info_parts.append("💡 系统详情需要安装psutil: pip install psutil")

            content = '\n'.join(info_parts) if info_parts else "系统信息获取中..."
            return ToolResult(
                success=True,
                content=content,
                metadata={'checked_items': check_items, 'psutil_available': PSUTIL_AVAILABLE}
            )

        except Exception as e:
            return ToolResult(
                success=False,
                content="",
                error=f"获取系统信息失败: {str(e)}"
            )


class NotificationTool(Tool):
    """通知工具 - 向主人发送通知"""

    name = "notify"
    description = "向主人发送桌面通知。可以用来提醒主人重要事项。"
    
    parameters = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "通知标题"
            },
            "message": {
                "type": "string", 
                "description": "通知内容"
            },
            "urgency": {
                "type": "string",
                "enum": ["low", "normal", "critical"],
                "description": "紧急程度"
            }
        },
        "required": ["title", "message"]
    }

    def execute(self, **kwargs) -> ToolResult:
        title = kwargs.get('title', '小Q提醒')
        message = kwargs.get('message', '')
        urgency = kwargs.get('urgency', 'normal')

        if not message:
            return ToolResult(
                success=False,
                content="",
                error="通知内容不能为空"
            )

        try:
            # macOS通知
            cmd = [
                'osascript', '-e', 
                f'display notification "{message}" with title "{title}"'
            ]
            subprocess.run(cmd, capture_output=True, timeout=5)
            
            return ToolResult(
                success=True,
                content=f"✅ 已发送通知「{title}」: {message}",
                metadata={'urgency': urgency}
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                content="",
                error="发送通知超时"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                content="",
                error=f"发送通知失败: {str(e)}"
            )
