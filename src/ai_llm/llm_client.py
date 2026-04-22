"""
LLM客户端 - 支持多种LLM服务的OpenAI兼容格式
"""

import os
import json
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict
from pathlib import Path

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    import urllib.request as urllib2

import yaml


@dataclass
class Message:
    """对话消息 - content可以是字符串或混合内容列表(用于多模态)"""
    role: str  # system, user, assistant
    content: str  # 字符串或 [{"type": "text"|"image_url", ...}, ...]


@dataclass
class LLMResponse:
    """LLM响应"""
    content: str
    model: str
    usage: Dict
    raw: Optional[Dict] = None


@dataclass
class LLMConfig:
    """LLM配置"""
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-3.5-turbo"
    timeout: int = 30
    max_retries: int = 3
    temperature: float = 0.8
    max_tokens: int = 200


import base64
import os


def load_image_as_base64(image_path: str) -> str:
    """将图片文件转为base64字符串（用于多模态输入）"""
    with open(image_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


def get_image_mime_type(image_path: str) -> str:
    """根据文件扩展名返回MIME类型"""
    ext = os.path.splitext(image_path.lower())[1]
    mime_types = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
    }
    return mime_types.get(ext, 'image/png')


class LLMClient:
    """LLM客户端"""

    MINIMAX_MAX_OUTPUT_TOKENS = 1000

    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self._client = None

    def _load_config(self, config_path: Optional[str]) -> LLMConfig:
        """加载配置"""
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__),
                "config.yaml"
            )

        config_file = Path(config_path)
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                llm_config = data.get('llm', {})
                # 环境变量优先于配置文件
                api_key = os.getenv("LLM_API_KEY") or llm_config.get('api_key', '')
                return LLMConfig(
                    base_url=os.getenv("LLM_BASE_URL") or llm_config.get('base_url', 'https://api.openai.com/v1'),
                    api_key=api_key,
                    model=llm_config.get('model', 'gpt-3.5-turbo'),
                    timeout=llm_config.get('timeout', 30),
                    max_retries=llm_config.get('max_retries', 3),
                    temperature=llm_config.get('temperature', 0.8),
                    max_tokens=llm_config.get('max_tokens', 200),
                )
        else:
            print(f"[LLM] 配置文件不存在: {config_path}，使用默认配置")
            return LLMConfig()

    def is_configured(self) -> bool:
        """检查是否已配置"""
        return bool(self.config.api_key and self.config.base_url)

    def _get_client(self):
        """获取HTTP客户端"""
        if HTTPX_AVAILABLE:
            if self._client is None:
                self._client = httpx.Client(
                    timeout=self.config.timeout,
                    follow_redirects=True
                )
            return self._client
        return None

    def _make_request(
        self,
        messages: List[Dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict:
        """发送请求到LLM"""
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        payload_max_tokens = self.config.max_tokens if max_tokens is None else max_tokens
        if "minimax" in self.config.base_url.lower():
            payload_max_tokens = min(int(payload_max_tokens), self.MINIMAX_MAX_OUTPUT_TOKENS)

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature if temperature is None else temperature,
            "max_tokens": payload_max_tokens,
        }

        if any(isinstance(msg.get("content"), list) for msg in messages):
            print(
                "[LLM] 多模态请求结构:",
                json.dumps(
                    {
                        "model": payload.get("model"),
                        "messages": [
                            {
                                "role": msg.get("role"),
                                "content_types": [
                                    part.get("type") if isinstance(part, dict) else type(part).__name__
                                    for part in msg.get("content", [])
                                ] if isinstance(msg.get("content"), list) else "text",
                            }
                            for msg in messages
                        ],
                    },
                    ensure_ascii=False,
                ),
            )

        # 检测API服务商并调整请求格式
        base_url = self.config.base_url.lower()

        if "hunyuan" in base_url or "tencent" in base_url:
            # 腾讯混元API格式
            url = f"{self.config.base_url.rstrip('/')}/hunyuan/v1/chat/completions"
        elif "ollama" in base_url:
            # Ollama本地API格式
            url = f"{self.config.base_url.rstrip('/')}/chat"
            payload["model"] = self.config.model.split('/')[-1]  # Ollama只用模型名
        elif "minimax" in base_url:
            # MiniMax API格式 - 使用标准OpenAI兼容端点
            url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        else:
            # OpenAI兼容格式
            url = f"{self.config.base_url.rstrip('/')}/chat/completions"

        if HTTPX_AVAILABLE:
            client = self._get_client()
            response = client.post(url, json=payload, headers=headers)
            if response.status_code >= 400:
                print(
                    "[LLM] 请求被拒绝:",
                    json.dumps(
                        {
                            "status_code": response.status_code,
                            "url": url,
                            "model": payload.get("model"),
                            "message_roles": [msg.get("role") for msg in messages],
                            "max_tokens": payload.get("max_tokens"),
                            "temperature": payload.get("temperature"),
                            "response_text": response.text[:2000],
                        },
                        ensure_ascii=False,
                    ),
                )
            response.raise_for_status()
            return response.json()
        else:
            # 使用标准库
            data = json.dumps(payload).encode('utf-8')
            req = urllib2.Request(
                url,
                data=data,
                headers=headers,
                method='POST'
            )
            with urllib2.urlopen(req, timeout=self.config.timeout) as response:
                return json.loads(response.read().decode('utf-8'))

    def chat(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        对话接口

        Args:
            messages: 对话历史
            system_prompt: 系统提示词
            **kwargs: 其他参数（temperature, max_tokens等）

        Returns:
            LLMResponse: LLM响应
        """
        if not self.is_configured():
            raise ValueError("LLM未配置，请检查config.yaml")

        # 构建消息列表
        all_messages = []

        # 添加系统提示词
        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})

        # 添加对话历史
        for msg in messages:
            # 支持多模态：content可能是字符串或混合内容列表
            msg_content = msg.content
            all_messages.append({"role": msg.role, "content": msg_content})

        # 覆盖参数
        if kwargs.get("temperature") is not None:
            payload_temperature = kwargs["temperature"]
        else:
            payload_temperature = self.config.temperature

        if kwargs.get("max_tokens") is not None:
            payload_max_tokens = kwargs["max_tokens"]
        else:
            payload_max_tokens = self.config.max_tokens

        # 重试逻辑
        last_error = None
        for attempt in range(self.config.max_retries):
            try:
                result = self._make_request(
                    all_messages,
                    temperature=payload_temperature,
                    max_tokens=payload_max_tokens,
                )

                # 解析响应
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0]["message"]["content"]
                    return LLMResponse(
                        content=content,
                        model=result.get("model", self.config.model),
                        usage=result.get("usage", {}),
                        raw=result
                    )
                else:
                    raise ValueError(f"LLM响应格式异常: {result}")

            except Exception as e:
                last_error = e
                print(f"[LLM] 请求失败 ({attempt + 1}/{self.config.max_retries}): {e}")
                if attempt < self.config.max_retries - 1:
                    import time
                    time.sleep(2 ** attempt)  # 指数退避

        raise last_error or ValueError("LLM请求最终失败")


# 全局实例
_client_instance = None


def get_llm_client(config_path: Optional[str] = None) -> LLMClient:
    """获取LLM客户端单例"""
    global _client_instance
    if _client_instance is None:
        _client_instance = LLMClient(config_path)
    return _client_instance


def reset_llm_client() -> None:
    """重置LLM客户端单例（用于重新加载配置）"""
    global _client_instance
    _client_instance = None
