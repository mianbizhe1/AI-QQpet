"""
Memory Recall - 记忆召回和推荐生成
"""

import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from .database import Database
from .models import Memory, MasterProfile
from .long_term_memory import LongTermMemory
from .master_profile import MasterProfileManager


class MemoryRecall:
    """记忆召回器 - 上下文感知的记忆检索"""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database.get_instance()
        self.memory_manager = LongTermMemory(self.db)
        self.profile_manager = MasterProfileManager(self.db)
        self._llm_client = None

    def _get_llm_client(self):
        """获取LLM客户端（延迟加载）"""
        if self._llm_client is None:
            try:
                from ai_llm import get_llm_client
                self._llm_client = get_llm_client()
            except Exception as e:
                print(f"[MemoryRecall] LLM客户端初始化失败: {e}")
                return None
        return self._llm_client

    def recall_relevant(
        self,
        context: Dict[str, Any],
        user_id: str = "default",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        召回相关记忆

        Args:
            context: 上下文 {"current_topic": "...", "emotional_state": "...", "purpose": "..."}
            user_id: 用户ID
            limit: 返回数量

        Returns:
            List[Dict] - 相关记忆列表
        """
        current_topic = context.get("current_topic", "")
        emotional_state = context.get("emotional_state", "")
        purpose = context.get("purpose", "")

        results = []

        # 0. 获取主人画像（用于热点话题和偏好匹配）
        profile = self.profile_manager.get_profile(user_id)

        # 1. 基于话题检索（改进：支持短消息的语义提取）
        search_keyword = current_topic
        if current_topic and len(current_topic) < 5:
            # 短消息用 LLM 提取语义话题
            search_keyword = self._extract_topic_with_llm(current_topic, user_id) or current_topic

        if search_keyword:
            memories = self.memory_manager.search_memories(
                keyword=search_keyword,
                user_id=user_id,
                limit=limit,
            )
            for memory in memories:
                results.append({
                    "memory": memory.to_dict(),
                    "relevance": self._calculate_relevance(memory, context),
                    "reason": f"与「{search_keyword}」相关",
                })

        # 2. 基于主人热点话题匹配
        if profile.hot_topics:
            for topic in profile.hot_topics[:3]:
                if search_keyword and topic in search_keyword:
                    continue  # 避免重复
                memories = self.memory_manager.search_memories(
                    keyword=topic,
                    user_id=user_id,
                    limit=3,
                )
                for memory in memories:
                    if not any(r["memory"]["id"] == memory.id for r in results):
                        results.append({
                            "memory": memory.to_dict(),
                            "relevance": self._calculate_relevance(memory, context) * 0.9,
                            "reason": f"热点话题「{topic}」相关",
                        })

        # 3. 基于主人兴趣匹配
        if profile.interests:
            for interest in profile.interests[:3]:
                memories = self.memory_manager.search_memories(
                    keyword=interest,
                    user_id=user_id,
                    limit=2,
                )
                for memory in memories:
                    if not any(r["memory"]["id"] == memory.id for r in results):
                        results.append({
                            "memory": memory.to_dict(),
                            "relevance": self._calculate_relevance(memory, context) * 0.85,
                            "reason": f"主人兴趣「{interest}」相关",
                        })

        # 4. 基于情感状态筛选
        if emotional_state:
            emotional_memories = self._get_emotional_memories(emotional_state, user_id)
            for memory in emotional_memories:
                if not any(r["memory"]["id"] == memory.id for r in results):
                    results.append({
                        "memory": memory.to_dict(),
                        "relevance": self._calculate_relevance(memory, context),
                        "reason": f"情感状态「{emotional_state}」相关",
                    })

        # 5. 获取重要记忆
        important_memories = self.memory_manager.get_important(
            user_id=user_id,
            limit=5,
            threshold=0.7,
        )
        for memory in important_memories:
            if not any(r["memory"]["id"] == memory.id for r in results):
                results.append({
                    "memory": memory.to_dict(),
                    "relevance": self._calculate_relevance(memory, context) * 0.8,
                    "reason": "重要记忆",
                })

        # 6. 基于时间衰减排序
        results = self._apply_time_decay(results)

        # 7. 基于重要性加权
        results = self._apply_importance_weight(results)

        # 排序并返回
        results.sort(key=lambda x: x["relevance"], reverse=True)
        return results[:limit]

    def _extract_topic_with_llm(self, short_text: str, user_id: str) -> Optional[str]:
        """用 LLM 从短消息中提取语义话题"""
        if not short_text or len(short_text.strip()) < 2:
            return None

        llm_client = self._get_llm_client()
        if not llm_client or not llm_client.is_configured():
            return short_text

        try:
            from ai_llm import Message
            response = llm_client.chat(
                [Message(role="user", content=f"从下列短句中提取一个关键词话题（只输出话题词，不要其他内容）：{short_text}")],
                system_prompt="你是一个话题提取助手。请从用户输入中提取核心话题词。",
                temperature=0.1,
                max_tokens=20,
            )
            topic = response.content.strip()
            # 只返回有意义的话题（过滤掉太短或太长的）
            if 2 < len(topic) < 20:
                return topic
        except Exception as e:
            print(f"[MemoryRecall] 话题提取失败: {e}")
        return short_text

    def _calculate_relevance(self, memory: Memory, context: Dict[str, Any]) -> float:
        """计算记忆与上下文的关联度（改进：更大的区分度）"""
        # 基础分 0.3-0.5，基于重要性
        relevance = 0.3 + (memory.importance or 0.5) * 0.4

        current_topic = context.get("current_topic", "")
        if current_topic:
            # 话题匹配（更细粒度）
            if current_topic in memory.content:
                relevance += 0.4
            elif any(word in memory.content for word in current_topic.split() if len(word) > 1):
                relevance += 0.2

        # 检查标签匹配
        memory_tags = set(memory.tags)
        context_tags = set(context.get("tags", []))
        if memory_tags & context_tags:
            relevance += 0.3

        # 访问次数加权（被多次访问的记忆更相关）
        if memory.access_count > 0:
            relevance += min(0.2, memory.access_count * 0.02)

        return max(0.1, min(1.0, relevance))

    def _get_emotional_memories(
        self,
        emotional_state: str,
        user_id: str,
    ) -> List[Memory]:
        """获取与情感状态相关的记忆"""
        # 情感状态到类别的映射
        emotional_categories = {
            "happy": ["positive", "entertainment"],
            "sad": ["comfort", "positive"],
            "anxious": ["comfort", "support"],
            "excited": ["entertainment", "news"],
        }

        categories = emotional_categories.get(emotional_state.lower(), [])
        memories = []
        for category in categories:
            category_memories = self.memory_manager.get_by_category(
                category=category,
                user_id=user_id,
                limit=5,
            )
            memories.extend(category_memories)
        return memories

    def _apply_time_decay(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """应用时间衰减"""
        now = datetime.now()
        for result in results:
            memory_data = result["memory"]
            created_at = memory_data.get("created_at")
            if created_at:
                if isinstance(created_at, str):
                    try:
                        created_at = datetime.fromisoformat(created_at)
                    except:
                        continue
                days_since_creation = (now - created_at).days
                # 每天衰减5%
                decay = max(0.5, 1.0 - (days_since_creation * 0.05))
                result["relevance"] *= decay
        return results

    def _apply_importance_weight(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """应用重要性权重"""
        for result in results:
            importance = result["memory"].get("importance", 0.5)
            result["relevance"] *= (0.5 + importance * 0.5)
        return results

    def generate_recommendations(
        self,
        user_id: str = "default",
        num: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        生成推荐内容

        Returns:
            [
                {"type": "entertainment", "content": "某综艺更新了", "reason": "主人喜欢这类节目"},
                {"type": "news", "content": "某热点新闻", "reason": "与主人兴趣相关"}
            ]
        """
        recommendations = []
        profile = self.profile_manager.get_profile(user_id)

        # 1. 基于娱乐偏好推荐
        if profile.entertainment:
            for category, values in profile.entertainment.items():
                if values:
                    # 选择一个随机偏好作为推荐理由
                    fav = values[0] if values else ""
                    recommendations.append({
                        "type": "entertainment",
                        "content": f"主人喜欢{category}类的{fav}呢~",
                        "reason": f"基于主人喜欢的{category}",
                        "category": category,
                    })

        # 2. 基于热点话题推荐
        if profile.hot_topics:
            for topic in profile.hot_topics[:2]:
                recommendations.append({
                    "type": "hot_topic",
                    "content": f"「{topic}」最近很火哦~",
                    "reason": "热点话题",
                    "topic": topic,
                })

        # 3. 基于兴趣推荐
        if profile.interests:
            for interest in profile.interests[:2]:
                recommendations.append({
                    "type": "interest",
                    "content": f"主人对{interest}感兴趣，要不要聊聊？",
                    "reason": f"基于主人兴趣",
                    "interest": interest,
                })

        return recommendations[:num]

    def recall_with_personality(
        self,
        context: Dict[str, Any],
        personality: Dict[str, Any],
        user_id: str = "default",
    ) -> List[Dict[str, Any]]:
        """
        根据宠物性格调整召回策略

        Args:
            context: 上下文
            personality: 宠物性格 {"warmth": 0-1, "humor": 0-1, "curiosity": 0-1}
            user_id: 用户ID
        """
        warmth = personality.get("warmth", 0.5)
        humor = personality.get("humor", 0.5)
        curiosity = personality.get("curiosity", 0.7)

        # 根据性格调整权重
        weights = {
            "emotional": warmth * 0.4,
            "entertainment": humor * 0.3,
            "learning": curiosity * 0.3,
        }

        results = self.recall_relevant(context, user_id)

        # 根据性格重新排序
        def personality_score(result):
            memory = result["memory"]
            category = memory.get("category", "")
            score = result["relevance"]

            if category == "emotional" or "情感" in memory.get("tags", []):
                score *= (1 + weights["emotional"])
            elif category == "entertainment":
                score *= (1 + weights["entertainment"])
            elif category == "learning" or category == "skill":
                score *= (1 + weights["learning"])

            return score

        results.sort(key=personality_score, reverse=True)
        return results

    def get_conversation_context(
        self,
        user_id: str = "default",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """获取对话上下文（用于传递给LLM）"""
        memories = self.memory_manager.get_recent(user_id=user_id, limit=limit)

        context = []
        for memory in memories:
            context.append({
                "type": memory.memory_type,
                "content": memory.content,
                "importance": memory.importance,
                "created_at": memory.created_at.isoformat() if memory.created_at else None,
            })

        return context
