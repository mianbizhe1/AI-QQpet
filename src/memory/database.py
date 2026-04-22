"""
Memory Database - SQLite connection and table initialization
"""

import os
import sqlite3
from contextlib import contextmanager
from typing import Optional
from pathlib import Path


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
                    importance      REAL NOT NULL DEFAULT 0.5,
                    source          TEXT NOT NULL,

                    -- 标签和分类
                    tags           TEXT NOT NULL DEFAULT '[]',
                    category       TEXT,

                    -- 访问统计
                    access_count   INTEGER NOT NULL DEFAULT 0,
                    last_accessed  DATETIME,

                    -- 主人关联
                    user_id        TEXT NOT NULL DEFAULT 'default',

                    -- 时间戳
                    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
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
                    confidence      REAL NOT NULL DEFAULT 0.5,

                    -- 来源
                    source         TEXT NOT NULL,
                    source_content TEXT,

                    -- 主人关联
                    user_id        TEXT NOT NULL DEFAULT 'default',

                    -- 时间戳
                    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

                    UNIQUE(user_id, preference_type, key)
                )
            """)

            # 创建索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_user_id ON memories(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_episodes_user_id ON episodes(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_preferences_user_id ON preferences(user_id)")

    @classmethod
    def get_instance(cls, db_path: Optional[str] = None) -> "Database":
        """获取数据库实例"""
        if db_path is None:
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "data", "memory.db"
            )
        return cls(db_path)