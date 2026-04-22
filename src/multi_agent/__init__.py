"""
QQ宠物多智能体技能系统
支持进程池、技能注册、定时任务
"""

from .process_pool import ProcessPool
from .master_agent import MasterAgent
from .sub_agent import SubAgent
from .skill_registry import SkillRegistry, Skill, SkillResult
from .task_scheduler import TaskScheduler
from .persona_wrapper import PersonaWrapper
from .ipc_protocol import WorkerMessage, AgentMessage

__all__ = [
    'ProcessPool',
    'MasterAgent',
    'SubAgent',
    'SkillRegistry',
    'Skill',
    'SkillResult',
    'TaskScheduler',
    'PersonaWrapper',
    'WorkerMessage',
    'AgentMessage',
]