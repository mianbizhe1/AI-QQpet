"""
技能注册中心
注册、管理、执行技能
"""

import json
import uuid
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum


class SkillCategory(str, Enum):
    """技能分类"""
    RESEARCH = "research"           # 搜索、论文、新闻
    PRODUCTIVITY = "productivity"    # 提醒、计时器、笔记
    ENTERTAINMENT = "entertainment" # 笑话、故事
    SYSTEM = "system"               # 截图、系统信息、通知
    PET_CARE = "pet_care"           # 宠物护理


@dataclass
class SkillParameter:
    """技能参数定义"""
    name: str
    type: str
    description: str = ""
    default: Any = None
    required: bool = False


@dataclass
class SkillResult:
    """技能执行结果"""
    success: bool
    content: str
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self):
        return {
            "success": self.success,
            "content": self.content,
            "data": self.data,
            "error": self.error,
        }


class Skill:
    """技能基类"""

    name: str = "skill"
    description: str = "A skill"
    category: SkillCategory = SkillCategory.SYSTEM
    parameters: List[SkillParameter] = []
    agent_type: str = "tool"  # tool | research | productivity
    aliases: List[str] = []   # 别名，如 ["搜索", "查一下"]

    def execute(self, **kwargs) -> SkillResult:
        """执行技能，子类必须实现"""
        raise NotImplementedError

    def get_schema(self) -> Dict[str, Any]:
        """获取技能JSON Schema"""
        # 处理parameters（可能是dict、SkillParameter列表或dict列表）
        parameters = getattr(self, 'parameters', {})

        if isinstance(parameters, dict):
            # 已经是dict格式（JSON Schema格式）
            schema_params = parameters

        elif isinstance(parameters, list):
            # 是列表，检查是SkillParameter对象列表还是dict列表
            if len(parameters) > 0:
                first_item = parameters[0]
                if hasattr(first_item, 'name') and hasattr(first_item, 'type'):
                    # SkillParameter对象列表
                    props = {}
                    required = []
                    for p in parameters:
                        props[p.name] = {
                            "type": p.type,
                            "description": p.description,
                        }
                        if hasattr(p, 'default') and p.default is not None:
                            props[p.name]["default"] = p.default
                        if hasattr(p, 'required') and p.required:
                            required.append(p.name)
                    schema_params = {
                        "type": "object",
                        "properties": props,
                        "required": required,
                    }
                else:
                    # dict列表
                    props = {}
                    required = []
                    for p in parameters:
                        props[p["name"]] = {
                            "type": p.get("type", "string"),
                            "description": p.get("description", ""),
                        }
                        if "default" in p:
                            props[p["name"]]["default"] = p["default"]
                        if p.get("required"):
                            required.append(p["name"])
                    schema_params = {
                        "type": "object",
                        "properties": props,
                        "required": required,
                    }
            else:
                schema_params = {"type": "object", "properties": {}}

        else:
            schema_params = {"type": "object", "properties": {}}

        # 处理category（可能是SkillCategory枚举或字符串）
        category = getattr(self, 'category', None)
        if category is None:
            category_value = "system"
        elif isinstance(category, SkillCategory):
            category_value = category.value
        else:
            category_value = str(category)

        return {
            "name": self.name,
            "description": self.description,
            "category": category_value,
            "parameters": schema_params,
            "agent_type": getattr(self, 'agent_type', 'tool'),
            "aliases": getattr(self, 'aliases', []) or [],
        }


class SkillRegistry:
    """技能注册中心（单例）"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._skills: Dict[str, Skill] = {}
        self._aliases: Dict[str, str] = {}  # alias -> skill_name
        self._category_index: Dict[str, List[str]] = {}  # category -> [skill_names]
        self._register_builtin_skills()

    def _register_builtin_skills(self):
        """注册内置技能"""
        from .skills.research_skills import AIPaperSearchSkill, NewsSearchSkill, WeiboHotSearchSkill
        from .skills.productivity_skills import ReminderSkill, TimerSkill
        from .skills.entertainment_skills import JokeSkill, StorySkill
        from .skills.entertainment_skill import EntertainmentSkill, EntertainmentUpdateSkill
        from .skills.skillhub_skills import SkillHubSearchSkill

        builtin_skills = [
            AIPaperSearchSkill(),
            NewsSearchSkill(),
            WeiboHotSearchSkill(),
            ReminderSkill(),
            TimerSkill(),
            JokeSkill(),
            StorySkill(),
            EntertainmentSkill(),
            EntertainmentUpdateSkill(),
            SkillHubSearchSkill(),
        ]

        # 注册从ai_tools迁移的技能
        try:
            from ai_tools import (
                BrowserSearchTool,
                SystemInfoTool, NotificationTool, BashTool
            )
            self.register(BrowserSearchTool())
            self.register(SystemInfoTool())
            self.register(NotificationTool())
            self.register(BashTool())
        except ImportError as e:
            print(f"[SkillRegistry] 迁移ai_tools失败: {e}")

        for skill in builtin_skills:
            self.register(skill)

    def register(self, skill: Skill) -> None:
        """注册技能"""
        self._skills[skill.name] = skill

        # 处理aliases属性
        aliases = getattr(skill, 'aliases', []) or []
        for alias in aliases:
            self._aliases[alias] = skill.name

        # 处理category（可能是SkillCategory枚举、字符串或不存在）
        category = getattr(skill, 'category', None)
        if category is None:
            category_value = "system"
        elif isinstance(category, SkillCategory):
            category_value = category.value
        else:
            category_value = str(category)

        if category_value not in self._category_index:
            self._category_index[category_value] = []
        if skill.name not in self._category_index[category_value]:
            self._category_index[category_value].append(skill.name)

        print(f"[SkillRegistry] 注册技能: {skill.name} ({category_value})")

    def get(self, name: str) -> Optional[Skill]:
        """获取技能"""
        # 优先通过别名查找
        if name in self._aliases:
            name = self._aliases[name]
        return self._skills.get(name)

    def execute(self, skill_name: str, args: Dict[str, Any]) -> SkillResult:
        """执行技能"""
        skill = self.get(skill_name)
        if not skill:
            return SkillResult(
                success=False,
                content="",
                error=f"技能不存在: {skill_name}"
            )

        try:
            result = skill.execute(**args)
            return result
        except Exception as e:
            return SkillResult(
                success=False,
                content="",
                error=f"技能执行失败: {str(e)}"
            )

    def list_all(self) -> List[Dict[str, Any]]:
        """列出所有技能"""
        return [skill.get_schema() for skill in self._skills.values()]

    def list_by_category(self, category: str) -> List[Dict[str, Any]]:
        """按分类列出技能"""
        skill_names = self._category_index.get(category, [])
        return [self._skills[name].get_schema() for name in skill_names if name in self._skills]

    def get_categories(self) -> List[str]:
        """获取所有分类"""
        return list(self._category_index.keys())

    def search(self, query: str) -> List[Dict[str, Any]]:
        """搜索技能（通过名称、别名、描述）"""
        query_lower = query.lower()
        results = []
        for skill in self._skills.values():
            if (query_lower in skill.name.lower() or
                query_lower in skill.description.lower() or
                any(query_lower in alias.lower() for alias in skill.aliases)):
                results.append(skill.get_schema())
        return results
