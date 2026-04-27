"""
Memory Learner - 从对话中学习偏好（LLM驱动）
"""

import json
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .database import Database
from .models import LearningResult, Preference
from .master_profile import MasterProfileManager
from .long_term_memory import LongTermMemory


class MemoryLearner:
    """记忆学习器 - 从对话中提取和学习"""

    def __init__(self, llm_config_path: Optional[str] = None, db: Optional[Database] = None):
        self.llm_config_path = llm_config_path
        self.db = db or Database.get_instance()
        self.profile_manager = MasterProfileManager(self.db)
        self.memory_manager = LongTermMemory(self.db)
        self._llm_client = None

    def _get_llm_client(self):
        """获取LLM客户端（延迟加载）"""
        if self._llm_client is None:
            try:
                from ai_llm import get_llm_client
                if self.llm_config_path:
                    self._llm_client = get_llm_client(self.llm_config_path)
                else:
                    self._llm_client = get_llm_client()
            except Exception as e:
                print(f"[MemoryLearner] LLM客户端初始化失败: {e}")
                return None
        return self._llm_client

    def learn_from_conversation(
        self,
        messages: List[Dict[str, str]],
        pet_name: str = "小Q",
        user_id: str = "default",
        source_episode_id: Optional[int] = None,
    ) -> LearningResult:
        """
        从对话中学习

        Args:
            messages: 对话消息列表 [{"role": "user/assistant", "content": "..."}]
            pet_name: 宠物名字
            user_id: 用户ID

        Returns:
            LearningResult
        """
        if not messages:
            return LearningResult()

        # 构建对话文本
        conversation_text = self._build_conversation_text(messages)

        # 使用LLM分析对话
        llm_client = self._get_llm_client()
        if llm_client and llm_client.is_configured():
            try:
                return self._learn_with_llm(
                    conversation_text,
                    messages,
                    pet_name,
                    user_id,
                    source_episode_id=source_episode_id,
                )
            except Exception as e:
                print(f"[MemoryLearner] LLM学习失败: {e}")

        # 降级：使用规则提取
        return self._learn_with_rules(conversation_text, user_id, source_episode_id=source_episode_id)

    def _build_conversation_text(self, messages: List[Dict[str, str]]) -> str:
        """构建对话文本"""
        lines = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                lines.append(f"主人: {content}")
            else:
                lines.append(f"宠物: {content}")
        return "\n".join(lines)

    def _learn_with_llm(
        self,
        conversation_text: str,
        messages: List[Dict[str, str]],
        pet_name: str,
        user_id: str,
        source_episode_id: Optional[int] = None,
    ) -> LearningResult:
        """使用LLM从对话中学习"""
        from ai_llm import Message

        llm_client = self._get_llm_client()

        system_prompt = f"""你是QQ宠物{pet_name}的记忆分析助手。
你的任务是从主人和宠物的对话中分析主人的兴趣、偏好和热点话题。

请分析以下对话，提取出：
1. interests - 主人感兴趣的领域（如：科技、美食、旅游、游戏等）
2. entertainment - 娱乐偏好（如：喜欢看的综艺、剧集、明星等）
3. hot_topics - 热点话题（如：正在追的剧、正在讨论的事件等）
4. new_memories - 重要的事实或关系（如：主人的工作、家里的人口等）

请只输出一个JSON对象，不要其他内容：
{{
  "interests": ["兴趣1", "兴趣2"],
  "entertainment": {{
    "variety_shows": ["综艺1", "综艺2"],
    "drama": ["剧集1"],
    "celebrities": ["明星1"],
    "genres": ["类型1"]
  }},
  "hot_topics": ["话题1", "话题2"],
  "new_memories": ["记忆1", "记忆2"],
  "preferences": {{
    "key": "value"
  }}
}}

如果没有发现任何信息，请返回空数组/对象：
{{
  "interests": [],
  "entertainment": {{}},
  "hot_topics": [],
  "new_memories": [],
  "preferences": {{}}
}}"""

        response = llm_client.chat(
            [Message(role="user", content=conversation_text)],
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=500,
        )

        # 解析LLM响应
        result = self._parse_llm_response(response.content)

        # 保存学习结果
        self._save_learning_result(result, user_id, source_episode_id=source_episode_id)

        return result

    def _parse_llm_response(self, content: str) -> LearningResult:
        """解析LLM响应"""
        text = (content or "").strip()

        # 尝试提取JSON
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text).strip()
            text = re.sub(r"```$", "", text).strip()

        try:
            data = json.loads(text)
            return LearningResult(
                interests=data.get("interests", []),
                entertainment=data.get("entertainment", {}),
                hot_topics=data.get("hot_topics", []),
                new_memories=data.get("new_memories", []),
                preferences=data.get("preferences", {}),
            )
        except json.JSONDecodeError:
            # 尝试从文本中提取
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                    return LearningResult(
                        interests=data.get("interests", []),
                        entertainment=data.get("entertainment", {}),
                        hot_topics=data.get("hot_topics", []),
                        new_memories=data.get("new_memories", []),
                        preferences=data.get("preferences", {}),
                    )
                except:
                    pass
            return LearningResult()

    def _learn_with_rules(self, text: str, user_id: str, source_episode_id: Optional[int] = None) -> LearningResult:
        """使用规则从文本中提取信息（降级方案）"""
        result = LearningResult()

        # 简单的规则提取
        # 综艺节目
        variety_shows = re.findall(r"《([^》]+)》", text)
        if variety_shows:
            result.entertainment["variety_shows"] = variety_shows

        # 话题提取（以"关于"、"讨论"、"关注"等开头）
        topics = re.findall(r"(?:关于|讨论|关注|听说)([^。，,]+)", text)
        if topics:
            result.hot_topics = topics[:5]

        # 兴趣提取（以"喜欢"、"感兴趣"等开头）
        interests = re.findall(r"喜欢([^。，,]+)", text)
        if interests:
            result.interests = list(set(interests[:5]))

        # 保存规则提取的结果
        self._save_learning_result(result, user_id, source_episode_id=source_episode_id)

        return result

    def _save_learning_result(self, result: LearningResult, user_id: str, source_episode_id: Optional[int] = None):
        """保存学习结果"""
        # 更新兴趣
        if result.interests:
            profile = self.profile_manager.get_profile(user_id)
            for interest in result.interests:
                if interest not in profile.interests:
                    profile.interests.append(interest)
            self.profile_manager.update_profile(profile, user_id)

        # 更新娱乐偏好
        if result.entertainment:
            for category, values in result.entertainment.items():
                if isinstance(values, list):
                    for value in values:
                        self.profile_manager.add_entertainment_preference(category, value, user_id)

        # 更新热点话题
        if result.hot_topics:
            profile = self.profile_manager.get_profile(user_id)
            for topic in result.hot_topics:
                if topic not in profile.hot_topics:
                    profile.hot_topics.append(topic)
            self.profile_manager.update_profile(profile, user_id)

        # 保存新记忆
        for memory_content in result.new_memories:
            category = self._infer_memory_category(memory_content)
            self.memory_manager.add_memory(
                memory_type="fact",
                content=memory_content,
                source="conversation",
                importance=self.calculate_importance(memory_content, "conversation"),
                category=category,
                user_id=user_id,
                canonical_key=self.memory_manager.build_canonical_key("fact", memory_content, category),
                source_episode_id=source_episode_id,
            )

        # 保存偏好（新增）
        if result.preferences:
            for key, value in result.preferences.items():
                # 检查是否已存在更高置信度的偏好
                existing = self.memory_manager.get_preference(key, user_id)
                if existing:
                    existing_value = json.loads(existing["value"]) if existing["value"] else None
                    if (existing.get("confidence", 0) >= 0.7) and existing_value == value:
                        # 已存在的偏好置信度更高且值相同，跳过
                        continue
                self.memory_manager.add_preference(
                    preference_type="topic",
                    key=key,
                    value=value,
                    confidence=0.6,
                    source="conversation",
                    user_id=user_id,
                    source_episode_id=source_episode_id,
                )

    def _infer_memory_category(self, content: str) -> str:
        text = str(content or "")
        if any(keyword in text for keyword in ["工作", "上班", "同事", "老板"]):
            return "personal"
        if any(keyword in text for keyword in ["喜欢", "爱看", "追", "综艺", "剧", "电影"]):
            return "entertainment"
        if any(keyword in text for keyword in ["学习", "写代码", "编程", "技术"]):
            return "skill"
        return "personal"

    def extract_interests(self, text: str) -> List[str]:
        """从文本中提取兴趣领域"""
        # 使用规则提取
        interests = []

        # 喜欢XXX
        likes = re.findall(r"喜欢(.{2,10})", text)
        interests.extend(likes)

        # 对XXX感兴趣
        interested = re.findall(r"对(.{2,10})感兴趣", text)
        interests.extend(interested)

        return list(set(interests))[:10]

    def extract_entertainment_prefs(self, text: str) -> Dict[str, List[str]]:
        """从文本中提取娱乐偏好"""
        prefs = {}

        # 综艺节目
        variety_shows = re.findall(r"《([^》]+)》", text)
        if variety_shows:
            prefs["variety_shows"] = variety_shows

        # 电视剧
        dramas = re.findall(r"《([^》]+)》", text)
        if dramas:
            prefs["drama"] = dramas

        return prefs

    def calculate_importance(self, content: str, source: str) -> float:
        """计算记忆重要性"""
        base_importance = 0.5

        # 来源加权
        source_weights = {
            "explicit": 0.9,  # 明确表达
            "conversation": 0.6,  # 对话
            "observation": 0.4,  # 观察
        }
        importance = source_weights.get(source, 0.5)

        # 内容长度加权
        if len(content) > 100:
            importance += 0.1

        # 关键词加权
        important_keywords = ["重要", "记得", "一定", "千万", "特别"]
        for keyword in important_keywords:
            if keyword in content:
                importance += 0.1
                break

        return min(1.0, max(0.0, importance))
