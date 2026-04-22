"""
Qwen-VL 视觉分析
"""

import base64
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import httpx
import yaml


class QwenVisionAnalyzer:
    """使用 DashScope OpenAI 兼容接口分析截图。"""

    MAX_IMAGE_BASE64_CHARS = 900_000

    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)

    def _load_config(self, config_path: str) -> dict:
        defaults = {
            "enabled": True,
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key": "",
            "model": "qwen3.6-plus",
            "timeout": 30,
            "max_tokens": 300,
        }

        path = Path(config_path)
        if not path.exists():
            return defaults

        with path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}

        vision_config = data.get("vision", {}) or {}
        # 环境变量优先于配置文件
        if os.getenv("VISION_API_KEY"):
            vision_config["api_key"] = os.getenv("VISION_API_KEY")
        if os.getenv("VISION_BASE_URL"):
            vision_config["base_url"] = os.getenv("VISION_BASE_URL")
        return {**defaults, **vision_config}

    def is_configured(self) -> bool:
        return bool(self.config.get("enabled") and self._api_key())

    def analyze(self, image_path: str, prompt: Optional[str] = None) -> Optional[str]:
        if not self.is_configured():
            print("[QwenVision] 未配置 vision.api_key，跳过视觉分析")
            return None

        data_url = self._image_to_data_url(image_path)
        if not data_url:
            return None

        prompt = prompt or "请简短描述这张电脑截图里主人正在做什么，重点说明前台应用、页面内容和可能的任务。"
        payload = {
            "model": self.config.get("model", "qwen3.6-plus"),
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "max_tokens": int(self.config.get("max_tokens", 300)),
        }

        url = f"{self.config.get('base_url').rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key()}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=int(self.config.get("timeout", 30))) as client:
                response = client.post(url, json=payload, headers=headers)
                if response.status_code >= 400:
                    print(
                        "[QwenVision] 请求失败:",
                        json.dumps(
                            {
                                "status_code": response.status_code,
                                "response_text": response.text[:1000],
                            },
                            ensure_ascii=False,
                        ),
                    )
                response.raise_for_status()
                data = response.json()
        except Exception as error:
            print(f"[QwenVision] 视觉分析异常: {error}")
            return None

        try:
            content = data["choices"][0]["message"]["content"]
        except Exception:
            print(f"[QwenVision] 响应格式异常: {data}")
            return None

        if isinstance(content, list):
            texts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    texts.append(str(part.get("text", "")))
            content = "\n".join(texts)

        content = str(content or "").strip()
        if content:
            print(f"[QwenVision] 视觉摘要: {content[:200]}")
        return content or None

    def _api_key(self) -> str:
        return self.config.get("api_key", "")

    def _image_to_data_url(self, image_path: str) -> Optional[str]:
        compressed_path = self._compress_image(image_path)
        if not compressed_path:
            return None

        try:
            with open(compressed_path, "rb") as image_file:
                img_b64 = base64.b64encode(image_file.read()).decode("utf-8")
        except Exception as error:
            print(f"[QwenVision] 读取图片失败: {error}")
            return None
        finally:
            try:
                os.unlink(compressed_path)
            except OSError:
                pass

        if len(img_b64) > self.MAX_IMAGE_BASE64_CHARS:
            print(f"[QwenVision] 图片过大，跳过视觉分析: {len(img_b64)} chars")
            return None

        return f"data:image/jpeg;base64,{img_b64}"

    def _compress_image(self, image_path: str) -> Optional[str]:
        if not os.path.exists(image_path):
            print(f"[QwenVision] 图片不存在: {image_path}")
            return None

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            compressed_path = tmp.name

        try:
            subprocess.run(
                [
                    "sips",
                    "-s", "format", "jpeg",
                    "-s", "formatOptions", "55",
                    "-Z", "1024",
                    image_path,
                    "--out",
                    compressed_path,
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            return compressed_path
        except Exception as error:
            print(f"[QwenVision] 图片压缩失败: {error}")
            try:
                os.unlink(compressed_path)
            except OSError:
                pass
            return None
