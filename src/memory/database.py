"""
Memory Database - SQLite connection and table initialization
"""

import os
import sqlite3
from contextlib import contextmanager
from typing import Optional
from pathlib import Path
from runtime_paths import memory_db_path


class Database:
    """SQLite数据库管理器"""

    _instances = {}  # path -> Database instance

    def __new__(cls, db_path: str):
        """单例模式，每个db_path一个实例"""
        if db_path not in cls._instances:
            instance = super().__new__(cls)
            instance._initialized = False
            cls._instances[db_path] = instance
        return cls._instances[db_path]

    def __init__(self, db_path: str):
        if self._initialized:
            return
        self._initialized = True
        self.db_path = db_path
        self._ensure_db_dir()
        self._init_db()

    def _ensure_db_dir(self):
        """确保数据库目录存在"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    @contextmanager
    def get_connection(self):
        """获取数据库连接的上下文管理器"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        """初始化数据库表"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. master_profile 表（主人画像）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS master_profile (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id         TEXT UNIQUE NOT NULL DEFAULT 'default',
                    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

                    -- 称呼和昵称
                    name            TEXT,
                    nickname        TEXT,

                    -- 兴趣领域（JSON数组）
                    interests       TEXT NOT NULL DEFAULT '[]',

                    -- 娱乐偏好（JSON对象）
                    entertainment   TEXT NOT NULL DEFAULT '{}',

                    -- 互动风格（JSON对象）
                    interaction_style TEXT NOT NULL DEFAULT '{}',

                    -- 热点话题（JSON数组）
                    hot_topics      TEXT NOT NULL DEFAULT '[]',

                    -- 活跃时间段（JSON对象）
                    active_hours    TEXT NOT NULL DEFAULT '{}'
                )
            """)

            # 2. memories 表（长期记忆）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    memory_type     TEXT NOT NULL,
                    content         TEXT NOT NULL,
                    normalized_content TEXT,
                    canonical_key   TEXT,
                    importance      REAL NOT NULL DEFAULT 0.5,
                    source          TEXT NOT NULL,
                    source_episode_id INTEGER,

                    -- 标签和分类
                    tags           TEXT NOT NULL DEFAULT '[]',
                    category       TEXT,
                    is_active      INTEGER NOT NULL DEFAULT 1,

                    -- 访问统计
                    access_count   INTEGER NOT NULL DEFAULT 0,
                    last_accessed  DATETIME,

                    -- 主人关联
                    user_id        TEXT NOT NULL DEFAULT 'default',

                    -- 时间戳
                    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 3. episodes 表（对话片段）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    episode_type    TEXT NOT NULL,

                    -- 对话摘要
                    summary         TEXT NOT NULL,
                    summary_embedding TEXT,

                    -- 详细内容（JSON）
                    details         TEXT NOT NULL DEFAULT '{}',

                    -- 情感标签
                    emotional_tags TEXT NOT NULL DEFAULT '[]',

                    -- 主人关联
                    user_id        TEXT NOT NULL DEFAULT 'default',

                    -- 时间戳
                    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 4. preferences 表（学习到的偏好）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS preferences (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    preference_type TEXT NOT NULL,
                    key             TEXT NOT NULL,
                    value           TEXT NOT NULL,
                    canonical_key   TEXT,
                    confidence      REAL NOT NULL DEFAULT 0.5,

                    -- 来源
                    source         TEXT NOT NULL,
                    source_content TEXT,
                    source_episode_id INTEGER,

                    -- 主人关联
                    user_id        TEXT NOT NULL DEFAULT 'default',

                    -- 时间戳
                    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

                    UNIQUE(user_id, preference_type, key)
                )
            """)

            # 创建索引
            self._ensure_column(cursor, "memories", "normalized_content", "TEXT")
            self._ensure_column(cursor, "memories", "canonical_key", "TEXT")
            self._ensure_column(cursor, "memories", "source_episode_id", "INTEGER")
            self._ensure_column(cursor, "memories", "is_active", "INTEGER NOT NULL DEFAULT 1")
            self._ensure_column(cursor, "memories", "updated_at", "DATETIME")
            self._ensure_column(cursor, "preferences", "canonical_key", "TEXT")
            self._ensure_column(cursor, "preferences", "source_episode_id", "INTEGER")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_user_id ON memories(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_canonical_key ON memories(user_id, canonical_key)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_episodes_user_id ON episodes(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_preferences_user_id ON preferences(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_preferences_canonical_key ON preferences(user_id, canonical_key)")

    def _ensure_column(self, cursor, table_name: str, column_name: str, column_def: str):
        """为旧数据库补齐后续版本新增列。"""
        cursor.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row[1] for row in cursor.fetchall()}
        if column_name not in existing_columns:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")

    @classmethod
    def get_instance(cls, db_path: Optional[str] = None) -> "Database":
        """获取数据库实例"""
        if db_path is None:
            db_path = str(memory_db_path())
        return cls(db_path)
