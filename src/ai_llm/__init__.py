"""
AI LLM 模块
为QQ宠物提供LLM对话能力
"""

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
