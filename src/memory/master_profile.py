"""
Master Profile Manager - 主人画像管理
"""

import json
from datetime import datetime
from typing import List, Dict, Any, Optional

from .database import Database
from .models import MasterProfile


class MasterProfileManager:
    """主人画像管理器"""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database.get_instance()

    def get_profile(self, user_id: str = "default") -> MasterProfile:
        """获取主人画像"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM master_profile WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()

            if row:
                return MasterProfile.from_row(dict(row))
            else:
                # 创建默认画像
                profile = MasterProfile(user_id=user_id)
                self._save_profile(profile)
                return profile

    def _save_profile(self, profile: MasterProfile):
        """保存主人画像"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO master_profile
                (user_id, name, nickname, interests, entertainment,
                 interaction_style, hot_topics, active_hours, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                profile.user_id,
                profile.name,
                profile.nickname,
                json.dumps(profile.interests, ensure_ascii=False),
                json.dumps(profile.entertainment, ensure_ascii=False),
                json.dumps(profile.interaction_style, ensure_ascii=False),
                json.dumps(profile.hot_topics, ensure_ascii=False),
                json.dumps(profile.active_hours, ensure_ascii=False),
                datetime.now().isoformat(),
            ))

    def update_profile(self, profile: MasterProfile, user_id: str = "default") -> MasterProfile:
        """更新主人画像"""
        profile.user_id = user_id
        profile.updated_at = datetime.now()
        self._save_profile(profile)
        return profile

    def update_interests(self, interests: List[str], user_id: str = "default") -> MasterProfile:
        """更新兴趣领域"""
        profile = self.get_profile(user_id)
        profile.interests = interests
        return self.update_profile(profile, user_id)

    def add_interest(self, interest: str, user_id: str = "default") -> MasterProfile:
        """添加单个兴趣"""
        profile = self.get_profile(user_id)
        if interest not in profile.interests:
            profile.interests.append(interest)
        return self.update_profile(profile, user_id)

    def add_entertainment_preference(
        self,
        category: str,
        value: str,
        user_id: str = "default"
    ) -> MasterProfile:
        """添加娱乐偏好"""
        profile = self.get_profile(user_id)
        if category not in profile.entertainment:
            profile.entertainment[category] = []
        if value not in profile.entertainment[category]:
            profile.entertainment[category].append(value)
        return self.update_profile(profile, user_id)

    def update_entertainment(
        self,
        entertainment: Dict[str, List[str]],
        user_id: str = "default"
    ) -> MasterProfile:
        """更新娱乐偏好"""
        profile = self.get_profile(user_id)
        profile.entertainment = entertainment
        return self.update_profile(profile, user_id)

    def update_hot_topics(self, topics: List[str], user_id: str = "default") -> MasterProfile:
        """更新热点话题"""
        profile = self.get_profile(user_id)
        profile.hot_topics = topics
        return self.update_profile(profile, user_id)

    def add_hot_topic(self, topic: str, user_id: str = "default") -> MasterProfile:
        """添加单个热点话题"""
        profile = self.get_profile(user_id)
        if topic not in profile.hot_topics:
            profile.hot_topics.append(topic)
        return self.update_profile(profile, user_id)

    def update_interaction_style(
        self,
        interaction_style: Dict[str, Any],
        user_id: str = "default"
    ) -> MasterProfile:
        """更新互动风格"""
        profile = self.get_profile(user_id)
        profile.interaction_style = interaction_style
        return self.update_profile(profile, user_id)

    def set_nickname(self, nickname: str, user_id: str = "default") -> MasterProfile:
        """设置昵称"""
        profile = self.get_profile(user_id)
        profile.nickname = nickname
        return self.update_profile(profile, user_id)

    def set_name(self, name: str, user_id: str = "default") -> MasterProfile:
        """设置称呼"""
        profile = self.get_profile(user_id)
        profile.name = name
        return self.update_profile(profile, user_id)

    def to_markdown(self, user_id: str = "default") -> str:
        """导出为markdown格式（master.md）"""
        profile = self.get_profile(user_id)
        return profile.to_markdown()

    def get_all_as_dict(self, user_id: str = "default") -> dict:
        """获取所有画像数据为字典"""
        profile = self.get_profile(user_id)
        return profile.to_dict()
