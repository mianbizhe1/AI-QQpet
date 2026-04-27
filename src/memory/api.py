"""
Memory API - 记忆相关的API端点
"""

import json
from typing import Dict, Any, Optional, List

from .database import Database
from .models import MasterProfile, Memory, Episode, Preference, LearningResult
from .master_profile import MasterProfileManager
from .long_term_memory import LongTermMemory
from .memory_learner import MemoryLearner
from .memory_recall import MemoryRecall


class MemoryAPI:
    """记忆API"""

    def __init__(self, llm_config_path: Optional[str] = None):
        self.db = Database.get_instance()
        self.profile_manager = MasterProfileManager(self.db)
        self.memory_manager = LongTermMemory(self.db)
        self.learner = MemoryLearner(llm_config_path, self.db)
        self.recall = MemoryRecall(self.db)

    # ==================== 主人画像接口 ====================

    def get_master_profile(self, user_id: str = "default") -> Dict[str, Any]:
        """获取主人画像"""
        profile = self.profile_manager.get_profile(user_id)
        return profile.to_dict()

    def update_master_profile(
        self,
        data: Dict[str, Any],
        user_id: str = "default",
    ) -> Dict[str, Any]:
        """更新主人画像"""
        profile = self.profile_manager.get_profile(user_id)

        if "name" in data:
            profile.name = data["name"]
        if "nickname" in data:
            profile.nickname = data["nickname"]
        if "interests" in data:
            profile.interests = data["interests"]
        if "entertainment" in data:
            profile.entertainment = data["entertainment"]
        if "interaction_style" in data:
            profile.interaction_style = data["interaction_style"]
        if "hot_topics" in data:
            profile.hot_topics = data["hot_topics"]
        if "active_hours" in data:
            profile.active_hours = data["active_hours"]

        updated = self.profile_manager.update_profile(profile, user_id)
        return updated.to_dict()

    def get_interests(self, user_id: str = "default") -> Dict[str, Any]:
        """获取兴趣领域"""
        profile = self.profile_manager.get_profile(user_id)
        return {"interests": profile.interests}

    def add_interests(
        self,
        interests: list,
        user_id: str = "default",
    ) -> Dict[str, Any]:
        """添加兴趣领域"""
        for interest in interests:
            self.profile_manager.add_interest(interest, user_id)
        profile = self.profile_manager.get_profile(user_id)
        return {"interests": profile.interests}

    def get_hot_topics(self, user_id: str = "default") -> Dict[str, Any]:
        """获取热点话题"""
        profile = self.profile_manager.get_profile(user_id)
        return {"hot_topics": profile.hot_topics}

    def update_hot_topics(
        self,
        topics: list,
        user_id: str = "default",
    ) -> Dict[str, Any]:
        """更新热点话题"""
        profile = self.profile_manager.update_hot_topics(topics, user_id)
        return {"hot_topics": profile.hot_topics}

    def get_master_markdown(self, user_id: str = "default") -> str:
        """获取主人画像的Markdown格式"""
        return self.profile_manager.to_markdown(user_id)

    # ==================== 记忆召回接口 ====================

    def recall_memories(
        self,
        context: Dict[str, Any],
        user_id: str = "default",
        limit: int = 10,
    ) -> Dict[str, Any]:
        """召回相关记忆"""
        results = self.recall.recall_relevant(context, user_id, limit)
        return {
            "memories": results,
            "total": len(results),
        }

    def recall_with_personality(
        self,
        context: Dict[str, Any],
        personality: Dict[str, Any],
        user_id: str = "default",
        limit: int = 10,
    ) -> Dict[str, Any]:
        """根据宠物性格召回记忆"""
        results = self.recall.recall_with_personality(context, personality, user_id)
        return {
            "memories": results[:limit],
            "total": len(results),
        }

    def get_recommendations(
        self,
        user_id: str = "default",
        num: int = 3,
    ) -> Dict[str, Any]:
        """获取推荐内容"""
        recommendations = self.recall.generate_recommendations(user_id, num)
        return {
            "recommendations": recommendations,
            "total": len(recommendations),
        }

    def get_conversation_context(
        self,
        user_id: str = "default",
        limit: int = 10,
    ) -> Dict[str, Any]:
        """获取对话上下文"""
        context = self.recall.get_conversation_context(user_id, limit)
        return {
            "context": context,
            "total": len(context),
        }

    # ==================== 记忆学习接口 ====================

    def learn_from_conversation(
        self,
        messages: list,
        pet_name: str = "小Q",
        user_id: str = "default",
        source_episode_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """从对话中学习"""
        result = self.learner.learn_from_conversation(
            messages,
            pet_name,
            user_id,
            source_episode_id=source_episode_id,
        )
        return result.to_dict()

    # ==================== 记忆管理接口 ====================

    def get_memories(
        self,
        user_id: str = "default",
        limit: int = 100,
        offset: int = 0,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取记忆列表"""
        memories = self.memory_manager.get_memories(
            user_id=user_id,
            limit=limit,
            offset=offset,
            category=category,
        )
        return {
            "memories": [m.to_dict() for m in memories],
            "total": len(memories),
        }

    def add_memory(
        self,
        memory_type: str,
        content: str,
        source: str,
        importance: float = 0.5,
        tags: Optional[list] = None,
        category: Optional[str] = None,
        user_id: str = "default",
        canonical_key: Optional[str] = None,
        source_episode_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """添加记忆"""
        memory = self.memory_manager.add_memory(
            memory_type=memory_type,
            content=content,
            source=source,
            importance=importance,
            tags=tags,
            category=category,
            user_id=user_id,
            canonical_key=canonical_key,
            source_episode_id=source_episode_id,
        )
        return memory.to_dict()

    def delete_memory(
        self,
        memory_id: int,
        user_id: str = "default",
    ) -> Dict[str, Any]:
        """删除记忆"""
        self.memory_manager.delete_memory(memory_id, user_id)
        return {"success": True, "memory_id": memory_id}

    def search_memories(
        self,
        keyword: str,
        user_id: str = "default",
        limit: int = 20,
    ) -> Dict[str, Any]:
        """搜索记忆"""
        memories = self.memory_manager.search_memories(keyword, user_id, limit)
        return {
            "memories": [m.to_dict() for m in memories],
            "total": len(memories),
        }

    # ==================== 统计接口 ====================

    def get_stats(self, user_id: str = "default") -> Dict[str, Any]:
        """获取记忆统计"""
        return {
            "total_memories": self.memory_manager.count(user_id),
            "profile": self.profile_manager.get_profile(user_id).to_dict(),
        }

    # ==================== 对话片段接口 ====================

    def save_episode(
        self,
        episode_type: str,
        summary: str,
        details: Optional[Dict[str, Any]] = None,
        emotional_tags: Optional[List[str]] = None,
        user_id: str = "default",
    ) -> Dict[str, Any]:
        """保存对话片段"""
        episode_id = self.memory_manager.add_episode(
            episode_type=episode_type,
            summary=summary,
            details=details,
            emotional_tags=emotional_tags,
            user_id=user_id,
        )
        return {"success": True, "episode_id": episode_id}

    def get_episodes(
        self,
        user_id: str = "default",
        limit: int = 50,
        offset: int = 0,
        episode_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取对话片段"""
        episodes = self.memory_manager.get_episodes(
            user_id=user_id,
            limit=limit,
            offset=offset,
            episode_type=episode_type,
        )
        return {
            "episodes": episodes,
            "total": len(episodes),
        }

    def save_tick_episode(
        self,
        event: str,
        dialogue: str,
        decision: Dict[str, Any],
        pet_status: Dict[str, Any],
        user_message: str = "",
        user_id: str = "default",
    ) -> Dict[str, Any]:
        """保存tick事件的对话片段"""
        details = {
            "event": event,
            "user_message": user_message,
            "decision": decision,
            "pet_status": {
                "mood": pet_status.get("info", {}).get("mood"),
                "hunger": pet_status.get("info", {}).get("hunger"),
                "clean": pet_status.get("info", {}).get("clean"),
                "health": pet_status.get("info", {}).get("health"),
            },
        }

        # 根据事件类型确定摘要
        if user_message:
            summary = f"[{event}] 主人: {user_message[:50]}... → 宠物: {dialogue[:50]}..."
        else:
            summary = f"[{event}] 宠物: {dialogue[:80]}..."

        return self.save_episode(
            episode_type=event,
            summary=summary,
            details=details,
            user_id=user_id,
        )


# 全局API实例
_memory_api: Optional[MemoryAPI] = None


def get_memory_api(llm_config_path: Optional[str] = None) -> MemoryAPI:
    """获取MemoryAPI单例"""
    global _memory_api
    if _memory_api is None:
        _memory_api = MemoryAPI(llm_config_path)
    return _memory_api
