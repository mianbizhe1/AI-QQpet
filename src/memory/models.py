"""
Memory Data Models
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Any, Optional


@dataclass
class MasterProfile:
    """主人画像"""
    user_id: str = "default"
    name: Optional[str] = None
    nickname: Optional[str] = None
    interests: List[str] = field(default_factory=list)
    entertainment: Dict[str, Any] = field(default_factory=dict)
    interaction_style: Dict[str, Any] = field(default_factory=dict)
    hot_topics: List[str] = field(default_factory=list)
    active_hours: Dict[str, str] = field(default_factory=dict)
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "nickname": self.nickname,
            "interests": self.interests,
            "entertainment": self.entertainment,
            "interaction_style": self.interaction_style,
            "hot_topics": self.hot_topics,
            "active_hours": self.active_hours,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_markdown(self) -> str:
        """导出为markdown格式"""
        lines = ["# 主人画像\n"]
        if self.name:
            lines.append(f"**称呼**: {self.name}")
        if self.nickname:
            lines.append(f"**昵称**: {self.nickname}")
        lines.append(f"\n## 兴趣领域\n")
        if self.interests:
            for interest in self.interests:
                lines.append(f"- {interest}")
        else:
            lines.append("_暂无_")
        lines.append(f"\n## 娱乐偏好\n")
        if self.entertainment:
            for category, values in self.entertainment.items():
                lines.append(f"**{category}**: {', '.join(values) if isinstance(values, list) else values}")
        else:
            lines.append("_暂无_")
        lines.append(f"\n## 热点话题\n")
        if self.hot_topics:
            for topic in self.hot_topics:
                lines.append(f"- {topic}")
        else:
            lines.append("_暂无_")
        lines.append(f"\n## 互动风格\n")
        if self.interaction_style:
            for key, value in self.interaction_style.items():
                lines.append(f"- **{key}**: {value}")
        else:
            lines.append("_暂无_")
        return "\n".join(lines)

    @classmethod
    def from_row(cls, row: dict) -> "MasterProfile":
        """从数据库行创建"""
        return cls(
            user_id=row["user_id"],
            name=row["name"],
            nickname=row["nickname"],
            interests=json.loads(row["interests"]) if row["interests"] else [],
            entertainment=json.loads(row["entertainment"]) if row["entertainment"] else {},
            interaction_style=json.loads(row["interaction_style"]) if row["interaction_style"] else {},
            hot_topics=json.loads(row["hot_topics"]) if row["hot_topics"] else [],
            active_hours=json.loads(row["active_hours"]) if row["active_hours"] else {},
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
        )


@dataclass
class Memory:
    """长期记忆"""
    id: Optional[int] = None
    memory_type: str = ""  # preference | fact | relationship | event
    content: str = ""
    importance: float = 0.5
    source: str = ""  # conversation | observation | explicit
    tags: List[str] = field(default_factory=list)
    category: Optional[str] = None  # entertainment | news | personal | skill
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    user_id: str = "default"
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "memory_type": self.memory_type,
            "content": self.content,
            "importance": self.importance,
            "source": self.source,
            "tags": self.tags,
            "category": self.category,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_row(cls, row: dict) -> "Memory":
        """从数据库行创建"""
        return cls(
            id=row["id"],
            memory_type=row["memory_type"],
            content=row["content"],
            importance=row["importance"],
            source=row["source"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            category=row["category"],
            access_count=row["access_count"],
            last_accessed=datetime.fromisoformat(row["last_accessed"]) if row["last_accessed"] else None,
            user_id=row["user_id"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        )


@dataclass
class Episode:
    """对话片段"""
    id: Optional[int] = None
    episode_type: str = ""  # conversation | action | event
    summary: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    emotional_tags: List[str] = field(default_factory=list)
    user_id: str = "default"
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "episode_type": self.episode_type,
            "summary": self.summary,
            "details": self.details,
            "emotional_tags": self.emotional_tags,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_row(cls, row: dict) -> "Episode":
        """从数据库行创建"""
        return cls(
            id=row["id"],
            episode_type=row["episode_type"],
            summary=row["summary"],
            details=json.loads(row["details"]) if row["details"] else {},
            emotional_tags=json.loads(row["emotional_tags"]) if row["emotional_tags"] else [],
            user_id=row["user_id"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        )


@dataclass
class Preference:
    """学习到的偏好"""
    id: Optional[int] = None
    preference_type: str = ""  # topic | entertainment | interaction
    key: str = ""
    value: Any = None
    confidence: float = 0.5
    source: str = ""  # conversation | observation | explicit
    source_content: Optional[str] = None
    user_id: str = "default"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "preference_type": self.preference_type,
            "key": self.key,
            "value": self.value,
            "confidence": self.confidence,
            "source": self.source,
            "source_content": self.source_content,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_row(cls, row: dict) -> "Preference":
        """从数据库行创建"""
        return cls(
            id=row["id"],
            preference_type=row["preference_type"],
            key=row["key"],
            value=json.loads(row["value"]) if row["value"] else None,
            confidence=row["confidence"],
            source=row["source"],
            source_content=row["source_content"],
            user_id=row["user_id"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
        )


@dataclass
class LearningResult:
    """学习结果"""
    interests: List[str] = field(default_factory=list)
    entertainment: Dict[str, List[str]] = field(default_factory=dict)
    new_memories: List[str] = field(default_factory=list)
    hot_topics: List[str] = field(default_factory=list)
    preferences: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)
