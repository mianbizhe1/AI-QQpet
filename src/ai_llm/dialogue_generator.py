"""
AI企鹅对话生成器
结合LLM和模板生成智能对话
"""

import os
import json
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from pathlib import Path

from .llm_client import LLMClient, Message, get_llm_client
from .prompt_templates import (
    get_system_prompt,
    get_scene_prompt,
    SCENE_PROMPTS
)


@dataclass
class DialogueContext:
    """对话上下文"""
    pet_name: str = "小Q"
    personality: Dict[str, float] = field(default_factory=lambda: {
        "warmth": 0.6,
        "humor": 0.5,
        "boldness": 0.4,
        "curiosity": 0.7
    })
    pet_status: Dict[str, Any] = field(default_factory=lambda: {
        "mood": 500,
        "hunger": 1500,
        "clean": 1500,
        "health": 5
    })
    recent_memory: List[str] = field(default_factory=list)
    current_scene: str = "idle"


class DialogueGenerator:
    """对话生成器"""

    def __init__(self, config_path: Optional[str] = None, llm_client: Optional[LLMClient] = None):
        # 加载配置
        self.config = self._load_config(config_path)
        
        # LLM客户端
        if llm_client:
            self.llm = llm_client
        else:
            self.llm = get_llm_client(config_path)

        # 模板缓存（LLM不可用时使用）
        self._template_cache = {}

    def _load_config(self, config_path: Optional[str]) -> dict:
        """加载配置"""
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__),
                "config.yaml"
            )

        config_file = Path(config_path)
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                import yaml
                return yaml.safe_load(f)
        return {"features": {"enabled": True}}

    def generate(
        self,
        scene: str,
        context: DialogueContext,
        user_message: Optional[str] = None
    ) -> str:
        """
        生成对话

        Args:
            scene: 场景类型（click_response, hungry, dirty等）
            context: 对话上下文
            user_message: 用户消息（可选）

        Returns:
            str: 生成的对话
        """
        # 检查LLM是否可用
        if self.config.get("features", {}).get("enabled", True) and self.llm.is_configured():
            return self._generate_with_llm(scene, context, user_message)
        else:
            return self._generate_with_template(scene, context)

    def _generate_with_llm(
        self,
        scene: str,
        context: DialogueContext,
        user_message: Optional[str] = None
    ) -> str:
        """使用LLM生成对话"""
        try:
            # 构建系统提示词
            system_prompt = get_system_prompt(
                context.pet_name,
                context.personality,
                context.pet_status
            )

            # 构建用户消息
            scene_prompt = get_scene_prompt(scene)
            if user_message:
                user_prompt = f"{scene_prompt}\n\n主人说：{user_message}"
            else:
                user_prompt = scene_prompt

            # 如果有记忆上下文，添加
            if context.recent_memory and self.config.get("features", {}).get("memory_context", True):
                memory_turns = self.config.get("features", {}).get("memory_turns", 5)
                memory_context = "\n".join(context.recent_memory[-memory_turns:])
                user_prompt = f"最近的对话记忆：\n{memory_context}\n\n{user_prompt}"

            # 调用LLM
            messages = [Message(role="user", content=user_prompt)]
            response = self.llm.chat(messages, system_prompt=system_prompt)

            # 清理输出
            content = response.content.strip()
            content = self._clean_response(content)

            return content

        except Exception as e:
            print(f"[DialogueGenerator] LLM生成失败: {e}")
            # 降级到模板
            return self._generate_with_template(scene, context)

    def _generate_with_template(
        self,
        scene: str,
        context: DialogueContext
    ) -> str:
        """使用模板生成对话（降级方案）"""
        templates = {
            "click_response": [
                "好开心！（蹦蹦跳跳）",
                "主人最好了~",
                "（撒娇地蹭了蹭）",
                "再摸摸我嘛~",
                "嘿嘿~",
            ],
            "hungry": [
                "肚子咕噜咕噜叫了...",
                "主人，我饿了~",
                "（眼巴巴地看着你）",
                "有好吃的吗？",
            ],
            "dirty": [
                "身上有点痒痒的...",
                "好久没洗澡了...",
                "（扭来扭去）",
            ],
            "sad": [
                "心情不太好...",
                "主人陪我玩一会儿嘛...",
                "（蔫蔫地趴着）",
            ],
            "sick": [
                "咳咳...有点不舒服",
                "头有点晕...",
                "（趴在原地不动）",
            ],
            "dead": [
                "主人...我先睡一会儿...",
                "谢谢你...一直照顾我...",
            ],
            "greeting": [
                "你好呀~",
                "主人来啦！",
                "（开心地跳了一下）",
            ],
            "praise": [
                "嘿嘿~谢谢夸奖！",
                "（得意地挺起胸脯）",
                "主人眼光真好~",
            ],
            "care_after": [
                "谢谢主人~",
                "舒服~",
                "（满足地眯起眼睛）",
            ],
            "late_night": [
                "主人，该睡觉了哦~",
                "（轻声）晚安...",
                "别太累了~",
            ],
            "morning": [
                "早上好！",
                "新的一天开始啦~",
                "（伸懒腰）",
            ],
            "主人_sad": [
                "怎么了？要我陪陪你吗？",
                "（安静地坐在你身边）",
                "我在呢~",
            ],
            "主人_happy": [
                "看起来好开心呀~",
                "（跟着开心）",
                "发生什么好事了吗？",
            ],
            "long_time_no_interact": [
                "主人~好久没理我了...",
                "（委屈巴巴）",
                "你在忙吗？",
            ],
            "want_job": [
                "有什么我能帮忙的吗？",
                "想帮主人做点事~",
            ],
        }

        # 根据性格调整选择
        humor = context.personality.get("humor", 0.5)
        warmth = context.personality.get("warmth", 0.6)

        pool = templates.get(scene, templates["click_response"])

        # 特殊处理某些场景
        if scene == "click_response":
            if humor > 0.7:
                pool = ["嘿嘿嘿~", "太好玩了！", "（乐得直蹦）"]
            elif warmth > 0.7:
                pool = ["主人最好了~", "好温暖呀...", "（蹭蹭）"]

        # 根据心情调整
        mood = context.pet_status.get("mood", 500)
        if mood < 200 and scene == "click_response":
            pool = ["谢谢主人...", "（感动地眼泪汪汪）", "有你真好..."]

        # 随机选择一个
        import random
        return random.choice(pool)

    def _clean_response(self, content: str) -> str:
        """清理LLM输出"""
        # 移除思考标签及其内容（如「思考过程:...」）
        import re
        content = re.sub(r'「.*?思考.*?」', '', content, flags=re.DOTALL)
        content = re.sub(r'\[.*?思考.*?\]', '', content, flags=re.DOTALL)
        content = re.sub(r'思考过程[：:].*', '', content)
        content = re.sub(r'思考[：:].*', '', content)
        content = re.sub(r'分析[：:].*', '', content)
        content = re.sub(r'\[OP\d+\].*', '', content)  # 移除[OP1]等标记

        # 移除引号
        content = content.strip('"\'').strip()

        # 如果还有换行，只取第一段（对话内容）
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        if lines:
            # 过滤掉看起来像思考过程的行
            content_lines = []
            for line in lines:
                # 跳过包含特定关键词的行
                skip_patterns = ['思考', '分析', '根据', '按照', '要求', '需要']
                if any(p in line for p in skip_patterns) and len(line) < 50:
                    continue
                content_lines.append(line)
            if content_lines:
                content = content_lines[0]
            else:
                content = lines[0]

        # 限制长度
        max_length = self.config.get("personality", {}).get("response_length", "short")
        if max_length == "short" and len(content) > 50:
            content = content[:50]

        return content

    def generate_dialogue(
        self,
        scene: str,
        pet_name: str = "小Q",
        personality: Optional[Dict] = None,
        pet_status: Optional[Dict] = None,
        user_message: Optional[str] = None,
        recent_memory: Optional[List[str]] = None
    ) -> str:
        """
        便捷对话生成接口

        Args:
            scene: 场景类型
            pet_name: 企鹅名字
            personality: 性格参数
            pet_status: 宠物状态
            user_message: 用户消息
            recent_memory: 最近对话记忆

        Returns:
            str: 生成的对话
        """
        if personality is None:
            personality = {"warmth": 0.6, "humor": 0.5, "boldness": 0.4, "curiosity": 0.7}
        if pet_status is None:
            pet_status = {"mood": 500, "hunger": 1500, "clean": 1500, "health": 5}
        if recent_memory is None:
            recent_memory = []

        context = DialogueContext(
            pet_name=pet_name,
            personality=personality,
            pet_status=pet_status,
            recent_memory=recent_memory,
            current_scene=scene
        )

        return self.generate(scene, context, user_message)


# ==================== 便捷函数 ====================

_generator: Optional[DialogueGenerator] = None


def get_dialogue_generator(config_path: Optional[str] = None) -> DialogueGenerator:
    """获取对话生成器单例"""
    global _generator
    if _generator is None:
        _generator = DialogueGenerator(config_path)
    return _generator


def generate_dialogue(
    scene: str,
    pet_name: str = "小Q",
    personality: Optional[Dict] = None,
    pet_status: Optional[Dict] = None
) -> str:
    """便捷对话生成函数"""
    generator = get_dialogue_generator()
    return generator.generate_dialogue(scene, pet_name, personality, pet_status)
