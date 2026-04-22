"""
Long Term Memory - 长期记忆存储和检索
"""

import json
from datetime import datetime
from typing import List, Dict, Any, Optional

from .database import Database
from .models import Memory


class LongTermMemory:
    """长期记忆管理器"""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database.get_instance()

    def add_memory(
        self,
        memory_type: str,
        content: str,
        source: str,
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
        category: Optional[str] = None,
        user_id: str = "default",
    ) -> Memory:
        """添加新记忆"""
        tags = tags or []
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO memories
                (memory_type, content, importance, source, tags, category, user_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                memory_type,
                content,
                importance,
                source,
                json.dumps(tags, ensure_ascii=False),
                category,
                user_id,
                datetime.now().isoformat(),
            ))
            memory_id = cursor.lastrowid

        return Memory(
            id=memory_id,
            memory_type=memory_type,
            content=content,
            importance=importance,
            source=source,
            tags=tags,
            category=category,
            user_id=user_id,
            created_at=datetime.now(),
        )

    def get_memory(self, memory_id: int, user_id: str = "default") -> Optional[Memory]:
        """获取单个记忆"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM memories WHERE id = ? AND user_id = ?",
                (memory_id, user_id)
            )
            row = cursor.fetchone()
            if row:
                return Memory.from_row(dict(row))
            return None

    def get_memories(
        self,
        user_id: str = "default",
        limit: int = 100,
        offset: int = 0,
        category: Optional[str] = None,
        memory_type: Optional[str] = None,
    ) -> List[Memory]:
        """获取记忆列表"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM memories WHERE user_id = ?"
            params = [user_id]

            if category:
                query += " AND category = ?"
                params.append(category)

            if memory_type:
                query += " AND memory_type = ?"
                params.append(memory_type)

            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [Memory.from_row(dict(row)) for row in rows]

    def search_memories(
        self,
        keyword: str,
        user_id: str = "default",
        limit: int = 20,
    ) -> List[Memory]:
        """搜索记忆（基于关键词）"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM memories
                WHERE user_id = ? AND (content LIKE ? OR tags LIKE ?)
                ORDER BY importance DESC, created_at DESC
                LIMIT ?
            """, (user_id, f"%{keyword}%", f"%{keyword}%", limit))

            rows = cursor.fetchall()
            return [Memory.from_row(dict(row)) for row in rows]

    def update_access(self, memory_id: int, user_id: str = "default"):
        """更新记忆访问时间和次数"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE memories
                SET access_count = access_count + 1, last_accessed = ?
                WHERE id = ? AND user_id = ?
            """, (datetime.now().isoformat(), memory_id, user_id))

    def delete_memory(self, memory_id: int, user_id: str = "default"):
        """删除记忆"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM memories WHERE id = ? AND user_id = ?",
                (memory_id, user_id)
            )

    def get_by_category(
        self,
        category: str,
        user_id: str = "default",
        limit: int = 50,
    ) -> List[Memory]:
        """按分类获取记忆"""
        return self.get_memories(user_id=user_id, limit=limit, category=category)

    def get_by_type(
        self,
        memory_type: str,
        user_id: str = "default",
        limit: int = 50,
    ) -> List[Memory]:
        """按类型获取记忆"""
        return self.get_memories(user_id=user_id, limit=limit, memory_type=memory_type)

    def get_recent(
        self,
        user_id: str = "default",
        limit: int = 20,
    ) -> List[Memory]:
        """获取最近的记忆"""
        return self.get_memories(user_id=user_id, limit=limit)

    def get_important(
        self,
        user_id: str = "default",
        limit: int = 20,
        threshold: float = 0.7,
    ) -> List[Memory]:
        """获取重要记忆"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM memories
                WHERE user_id = ? AND importance >= ?
                ORDER BY importance DESC, created_at DESC
                LIMIT ?
            """, (user_id, threshold, limit))

            rows = cursor.fetchall()
            return [Memory.from_row(dict(row)) for row in rows]

    def count(self, user_id: str = "default") -> int:
        """获取记忆总数"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM memories WHERE user_id = ?",
                (user_id,)
            )
            return cursor.fetchone()[0]

    # ==================== Episodes (对话片段) ====================

    def add_episode(
        self,
        episode_type: str,
        summary: str,
        details: Optional[Dict[str, Any]] = None,
        emotional_tags: Optional[List[str]] = None,
        user_id: str = "default",
    ) -> int:
        """添加对话片段"""
        details = details or {}
        emotional_tags = emotional_tags or []
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO episodes
                (episode_type, summary, details, emotional_tags, user_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                episode_type,
                summary,
                json.dumps(details, ensure_ascii=False),
                json.dumps(emotional_tags, ensure_ascii=False),
                user_id,
                datetime.now().isoformat(),
            ))
            return cursor.lastrowid

    def get_episodes(
        self,
        user_id: str = "default",
        limit: int = 50,
        offset: int = 0,
        episode_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """获取对话片段列表"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM episodes WHERE user_id = ?"
            params = [user_id]

            if episode_type:
                query += " AND episode_type = ?"
                params.append(episode_type)

            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_recent_episodes(
        self,
        user_id: str = "default",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """获取最近的对话片段"""
        return self.get_episodes(user_id=user_id, limit=limit)

    # ==================== Preferences (学习到的偏好) ====================

    def add_preference(
        self,
        preference_type: str,
        key: str,
        value: Any,
        confidence: float = 0.5,
        source: str = "conversation",
        source_content: Optional[str] = None,
        user_id: str = "default",
    ) -> int:
        """添加或更新偏好（使用 INSERT OR REPLACE 实现 upsert）"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            # 如果 value 已经是字符串，直接使用；否则 JSON 序列化
            if isinstance(value, str):
                stored_value = value
            else:
                stored_value = json.dumps(value, ensure_ascii=False)
            cursor.execute("""
                INSERT OR REPLACE INTO preferences
                (preference_type, key, value, confidence, source, source_content, user_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                preference_type,
                key,
                stored_value,
                confidence,
                source,
                source_content,
                user_id,
                now,
                now,
            ))
            return cursor.lastrowid

    def get_preferences(
        self,
        user_id: str = "default",
        preference_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """获取偏好列表"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM preferences WHERE user_id = ?"
            params = [user_id]

            if preference_type:
                query += " AND preference_type = ?"
                params.append(preference_type)

            query += " ORDER BY updated_at DESC"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_preference(self, key: str, user_id: str = "default") -> Optional[Dict[str, Any]]:
        """获取单个偏好"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM preferences WHERE user_id = ? AND key = ?",
                (user_id, key)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
