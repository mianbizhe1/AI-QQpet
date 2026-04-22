"""
生产力类技能
提醒、计时器等
"""

import subprocess
import time
import threading
from typing import Optional

from ..skill_registry import Skill, SkillResult, SkillCategory


class ReminderSkill(Skill):
    """提醒技能 - 向主人发送桌面提醒"""

    name = "reminder"
    description = "向主人发送桌面通知提醒，可以设置提醒标题和内容"
    category = SkillCategory.PRODUCTIVITY
    agent_type = "productivity"
    aliases = ["提醒", "通知", "提醒我", "记得"]

    parameters = [
        {"name": "title", "type": "string", "description": "提醒标题", "required": True},
        {"name": "message", "type": "string", "description": "提醒内容", "required": True},
        {"name": "urgency", "type": "string", "description": "紧急程度", "default": "normal"},
    ]

    def execute(self, title: str, message: str, urgency: str = "normal") -> SkillResult:
        """发送提醒"""
        if not message:
            return SkillResult(success=False, content="", error="提醒内容不能为空")

        try:
            # macOS通知
            cmd = [
                'osascript', '-e',
                f'display notification "{message}" with title "{title}"'
            ]
            subprocess.run(cmd, capture_output=True, timeout=5)

            content = f"✅ 已发送提醒「{title}」: {message}"
            return SkillResult(success=True, content=content)

        except subprocess.TimeoutExpired:
            return SkillResult(success=False, content="", error="发送提醒超时")
        except Exception as e:
            return SkillResult(success=False, content="", error=f"发送提醒失败: {str(e)}")


class TimerSkill(Skill):
    """计时器技能 - 设置倒计时并在时间到了时发送通知"""

    name = "timer"
    description = "设置倒计时器，时间到了会自动提醒主人"
    category = SkillCategory.PRODUCTIVITY
    agent_type = "productivity"
    aliases = ["计时", "倒计时", "计时器", "多久"]

    parameters = [
        {"name": "minutes", "type": "integer", "description": "分钟数"},
        {"name": "seconds", "type": "integer", "description": "秒数"},
        {"name": "label", "type": "string", "description": "计时器名称"},
    ]

    def execute(self, minutes: int = 0, seconds: int = 0, label: str = "") -> SkillResult:
        """设置计时器"""
        total_seconds = minutes * 60 + seconds

        if total_seconds <= 0:
            return SkillResult(success=False, content="", error="时间必须大于0")

        if total_seconds > 3600:  # 最大1小时
            return SkillResult(success=False, content="", error="计时器最长支持1小时")

        label_text = f"「{label}」" if label else "计时器"

        # 在新线程中运行计时器
        thread = threading.Thread(target=self._run_timer, args=(total_seconds, label), daemon=True)
        thread.start()

        time_desc = []
        if minutes > 0:
            time_desc.append(f"{minutes}分钟")
        if seconds > 0:
            time_desc.append(f"{seconds}秒")

        content = f"⏰ 已启动{label_text}，{' '.join(time_desc)}后提醒主人~"
        return SkillResult(success=True, content=content)

    def _run_timer(self, seconds: int, label: str):
        """运行计时器"""
        time.sleep(seconds)

        title = "⏰ 计时器提醒"
        message = f"{label}时间到啦！" if label else "时间到啦！"

        try:
            cmd = [
                'osascript', '-e',
                f'display notification "{message}" with title "{title}"'
            ]
            subprocess.run(cmd, capture_output=True, timeout=5)
        except:
            pass


class NotificationTool(Skill):
    """通知工具（从ai_tools迁移）"""

    name = "notify"
    description = "向主人发送桌面通知，可以用来提醒重要事项"
    category = SkillCategory.PRODUCTIVITY
    agent_type = "productivity"
    aliases = ["通知", "发通知", "弹窗"]

    parameters = [
        {"name": "title", "type": "string", "description": "通知标题", "required": True},
        {"name": "message", "type": "string", "description": "通知内容", "required": True},
        {"name": "urgency", "type": "string", "description": "紧急程度"},
    ]

    def execute(self, title: str = "小Q提醒", message: str = "", urgency: str = "normal") -> SkillResult:
        """发送通知"""
        if not message:
            return SkillResult(success=False, content="", error="通知内容不能为空")

        try:
            cmd = [
                'osascript', '-e',
                f'display notification "{message}" with title "{title}"'
            ]
            subprocess.run(cmd, capture_output=True, timeout=5)

            return SkillResult(
                success=True,
                content=f"✅ 已发送通知「{title}」: {message}",
            )

        except Exception as e:
            return SkillResult(success=False, content="", error=f"发送通知失败: {str(e)}")
