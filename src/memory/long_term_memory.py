"""
Long Term Memory - 长期记忆存储和检索
"""

import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

from .database import Database
from .models import Memory


class LongTermMemory:
    """长期记忆管理器"""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database.get_instance()

    def normalize_memory_text(self, content: str) -> str:
        """对记忆文本做最小规范化，便于去重与检索。"""
        text = re.sub(r"\s+", "", str(content or "")).strip().lower()
        text = re.sub(r"[^\w\u4e00-\u9fff]", "", text)
        return text

    def build_canonical_key(self, memory_type: str, content: str, category: Optional[str] = None) -> Optional[str]:
        """基于类型和规范化内容生成稳定去重键。"""
        normalized = self.normalize_memory_text(content)
        if not normalized:
            return None
        prefix = f"{memory_type}:{category or 'general'}"
        return f"{prefix}:{normalized[:120]}"

    def add_memory(
        self,
        memory_type: str,
        content: str,
        source: str,
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
        category: Optional[str] = None,
        user_id: str = "default",
        canonical_key: Optional[str] = None,
        source_episode_id: Optional[int] = None,
    ) -> Memory:
        """添加新记忆"""
        tags = tags or []
        normalized_content = self.normalize_memory_text(content)
        canonical_key = canonical_key or self.build_canonical_key(memory_type, content, category)
        now = datetime.now().isoformat()
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            existing = None
            if canonical_key:
                cursor.execute(
                    """
                    SELECT * FROM memories
                    WHERE user_id = ? AND canonical_key = ? AND is_active = 1
                    ORDER BY updated_at DESC, created_at DESC
                    LIMIT 1
                    """,
                    (user_id, canonical_key),
                )
                existing = cursor.fetchone()

            if existing:
                merged_tags = list(dict.fromkeys((json.loads(existing["tags"]) if existing["tags"] else []) + tags))
                stored_importance = max(float(existing["importance"]), importance)
                stored_source_episode_id = source_episode_id or existing["source_episode_id"]
                cursor.execute(
                    """
                    UPDATE memories
                    SET content = ?, normalized_content = ?, importance = ?, source = ?,
                        source_episode_id = COALESCE(?, source_episode_id),
                        tags = ?, category = ?, is_active = 1, updated_at = ?
                    WHERE id = ? AND user_id = ?
                    """,
                    (
                        content,
                        normalized_content,
                        stored_importance,
                        source,
                        source_episode_id,
                        json.dumps(merged_tags, ensure_ascii=False),
                        category or existing["category"],
                        now,
                        existing["id"],
                        user_id,
                    ),
                )
                memory_id = existing["id"]
                created_at = existing["created_at"]
                access_count = existing["access_count"]
                last_accessed = existing["last_accessed"]
                is_active = bool(existing["is_active"]) if existing["is_active"] is not None else True
                stored_category = category or existing["category"]
                stored_tags = merged_tags
                stored_canonical_key = existing["canonical_key"] or canonical_key
            else:
                cursor.execute("""
                    INSERT INTO memories
                    (memory_type, content, normalized_content, canonical_key, importance, source,
                     source_episode_id, tags, category, is_active, user_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """, (
                    memory_type,
                    content,
                    normalized_content,
                    canonical_key,
                    importance,
                    source,
                    source_episode_id,
                    json.dumps(tags, ensure_ascii=False),
                    category,
                    user_id,
                    now,
                    now,
                ))
                memory_id = cursor.lastrowid
                created_at = now
                access_count = 0
                last_accessed = None
                is_active = True
                stored_category = category
                stored_tags = tags
                stored_importance = importance
                stored_source_episode_id = source_episode_id
                stored_canonical_key = canonical_key

        return Memory(
            id=memory_id,
            memory_type=memory_type,
            content=content,
            normalized_content=normalized_content,
            canonical_key=stored_canonical_key,
            importance=stored_importance,
            source=source,
            source_episode_id=stored_source_episode_id,
            tags=stored_tags,
            category=stored_category,
            is_active=is_active,
            access_count=access_count,
            last_accessed=datetime.fromisoformat(last_accessed) if last_accessed else None,
            user_id=user_id,
            created_at=datetime.fromisoformat(created_at) if created_at else datetime.now(),
            updated_at=datetime.fromisoformat(now),
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

            query = "SELECT * FROM memories WHERE user_id = ? AND is_active = 1"
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
                WHERE user_id = ? AND is_active = 1
                  AND (content LIKE ? OR tags LIKE ? OR normalized_content LIKE ?)
                ORDER BY importance DESC, created_at DESC
                LIMIT ?
            """, (
                user_id,
                f"%{keyword}%",
                f"%{keyword}%",
                f"%{self.normalize_memory_text(keyword)}%",
                limit,
            ))

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
                WHERE user_id = ? AND is_active = 1 AND importance >= ?
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
                "SELECT COUNT(*) FROM memories WHERE user_id = ? AND is_active = 1",
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

    def search_episodes(
        self,
        keyword: str,
        user_id: str = "default",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """按摘要和详情搜索对话片段。"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM episodes
                WHERE user_id = ? AND (summary LIKE ? OR details LIKE ?)
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user_id, f"%{keyword}%", f"%{keyword}%", limit),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

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
        source_episode_id: Optional[int] = None,
    ) -> int:
        """添加或更新偏好（使用 INSERT OR REPLACE 实现 upsert）"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            canonical_key = f"{preference_type}:{key.strip().lower()}"
            # 如果 value 已经是字符串，直接使用；否则 JSON 序列化
            if isinstance(value, str):
                stored_value = value
            else:
                stored_value = json.dumps(value, ensure_ascii=False)
            cursor.execute("""
                INSERT OR REPLACE INTO preferences
                (preference_type, key, value, canonical_key, confidence, source, source_content,
                 source_episode_id, user_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                preference_type,
                key,
                stored_value,
                canonical_key,
                confidence,
                source,
                source_content,
                source_episode_id,
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
