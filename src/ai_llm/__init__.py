"""
AI LLM 模块
为QQ宠物提供LLM对话能力
"""

import os
from runtime_paths import existing_paths, env_candidates

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - 允许无 dotenv 的轻量运行
    def load_dotenv(*args, **kwargs):
        return False

# 加载 .env 环境变量
for env_path in existing_paths(env_candidates()):
    load_dotenv(env_path, override=False)

from .llm_client import LLMClient, Message, LLMResponse, get_llm_client, reset_llm_client, load_image_as_base64, get_image_mime_type
from .dialogue_generator import (
    DialogueGenerator,
    DialogueContext,
    get_dialogue_generator,
    generate_dialogue
)
from .prompt_templates import (
    SYSTEM_PROMPT,
    SCENE_PROMPTS,
    get_system_prompt,
    get_scene_prompt
)

__all__ = [
    'LLMClient',
    'Message',
    'LLMResponse',
    'get_llm_client',
    'reset_llm_client',
    'load_image_as_base64',
    'get_image_mime_type',
    'DialogueGenerator',
    'DialogueContext',
    'get_dialogue_generator',
    'generate_dialogue',
    'SYSTEM_PROMPT',
    'SCENE_PROMPTS',
    'get_system_prompt',
    'get_scene_prompt',
]
