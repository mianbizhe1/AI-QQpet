"""
技能模块
"""

from .research_skills import AIPaperSearchSkill, NewsSearchSkill
from .productivity_skills import ReminderSkill, TimerSkill
from .entertainment_skills import JokeSkill, StorySkill
from .skillhub_skills import SkillHubSearchSkill

__all__ = [
    'AIPaperSearchSkill',
    'NewsSearchSkill',
    'ReminderSkill',
    'TimerSkill',
    'JokeSkill',
    'StorySkill',
    'SkillHubSearchSkill',
]