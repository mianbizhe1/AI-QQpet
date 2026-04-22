"""
宠物角色封装器
将技能结果转换为角色化输出
"""

import random
from typing import Dict, Any, Optional


class PersonaWrapper:
    """宠物角色封装器"""

    # 基础语气前缀
    GREETINGS = [
        "主人好呀~", "嘿~主人~", "来啦来啦~", "主人叫我吗？",
    ]

    # 结果确认语
    CONFIRMATIONS = [
        "帮你搞定啦~", "已经处理好咯~", "完成啦完成啦~",
        "好嘞~", "嗯嗯~搞定了~", "主人请过目~",
    ]

    # 错误反馈
    ERRORS = [
        "唔...出了点小问题", "哎呀失败了呢", "有点不太顺利...",
    ]

    # 期望语
    HOPES = [
        "希望对主人有帮助呀~", "希望能帮到主人~", "主人喜欢吗~",
        "这样可以吗~", "有需要再叫我哦~",
    ]

    def __init__(self, pet_name: str = "小Q", personality: Optional[Dict[str, Any]] = None):
        self.pet_name = pet_name
        self.personality = personality or {}
        self.warmth = self.personality.get("warmth", 7)
        self.humor = self.personality.get("humor", 5)

    def wrap_success(self, result_content: str, skill_name: str = "") -> str:
        """
        封装成功结果为角色化输出

        Args:
            result_content: 技能原始输出
            skill_name: 技能名称（用于选择语气）

        Returns:
            角色化后的对话
        """
        parts = []

        # 根据技能类型选择开头语
        if skill_name in ["browser_search", "ai_paper_search", "news_search"]:
            parts.append(random.choice([
                "主人~我帮你搜了一下！",
                "帮主人查到了哦~",
                "嘿嘿，让我来告诉主人~",
            ]))
        elif skill_name in ["reminder", "notification", "notify"]:
            parts.append(random.choice([
                "提醒已经发出去啦~",
                "好嘞~通知已送达~",
            ]))
        elif skill_name in ["timer", "countdown"]:
            parts.append(random.choice([
                "计时开始啦~",
                "记下来啦~",
            ]))
        elif skill_name in ["joke", "entertainment"]:
            parts.append(random.choice([
                "嘿嘿~让我来逗逗主人~",
                "主人想听笑话吗~",
            ]))
        elif skill_name in ["screenshot"]:
            parts.append(random.choice([
                "截图搞定~",
                "已经截好啦~",
            ]))
        else:
            parts.append(random.choice(self.GREETINGS))

        # 添加结果内容
        if result_content:
            # 截断过长的内容
            if len(result_content) > 500:
                result_content = result_content[:500] + "..."
            parts.append(result_content)

        # 添加期望语（根据warmth调整概率）
        if self.warmth >= 7 and random.random() > 0.3:
            parts.append(random.choice(self.HOPES))

        return " ".join(parts)

    def wrap_error(self, error_message: str, skill_name: str = "") -> str:
        """
        封装错误为角色化输出
        """
        base = random.choice(self.ERRORS)
        if error_message:
            # 简化错误信息
            if "not found" in error_message.lower() or "不存在" in error_message:
                return f"{base}，没找到相关信息呢..."
            elif "timeout" in error_message.lower() or "超时" in error_message:
                return f"{base}，网络有点慢呢..."
            elif "permission" in error_message.lower() or "权限" in error_message:
                return f"{base}，好像没有权限呢..."
        return base

    def wrap_progress(self, progress: int, message: str = "") -> str:
        """
        封装进度信息
        """
        if progress < 30:
            return "正在准备中~"
        elif progress < 60:
            return "加油处理中~"
        elif progress < 90:
            return "快完成啦~"
        else:
            return "马上就好啦~"

    def format_reminder(self, title: str, message: str, delay_minutes: int = 0) -> str:
        """
        格式化提醒消息
        """
        if delay_minutes > 0:
            return f"好的主人~ {delay_minutes}分钟后提醒你「{title}」: {message}"
        else:
            return f"好的主人~稍后提醒你「{title}」: {message}"

    def wrap_multi_results(self, results: list) -> str:
        """
        封装多个技能的结果
        """
        if not results:
            return "处理完成啦~"

        success_count = sum(1 for r in results if r.get("success"))
        total_count = len(results)

        if success_count == total_count:
            base = random.choice(self.CONFIRMATIONS)
            return f"{base}一共{success_count}项任务都搞定啦~"
        elif success_count > 0:
            return f"完成了{success_count}/{total_count}项任务~有些小问题呢..."
        else:
            return random.choice(self.ERRORS) + "所有任务都失败了..."