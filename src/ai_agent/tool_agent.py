"""
AI企鹅 Tool Calling Agent
支持多轮工具调用的智能体
"""

import base64
import json
import re
import os
import subprocess
import tempfile
from typing import List, Dict, Any, Optional
from ai_llm import get_llm_client, Message
from .vision import QwenVisionAnalyzer
from .life_album import LifeAlbumStore
from runtime_paths import life_album_dir

# 导入记忆模块
try:
    from memory import get_memory_api
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False
    print("[ToolAgent] memory模块不可用，将跳过记忆功能")


class ToolAgent:
    """支持Tool Calling的企鹅Agent"""

    MAX_IMAGE_BASE64_CHARS = 900_000

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.llm_client = get_llm_client(config_path)
        self.vision_analyzer = QwenVisionAnalyzer(config_path)
        self.life_album_store = LifeAlbumStore(str(life_album_dir()))
        self.tools = []
        self.max_turns = 3

    def register_tools(self, tools: List):
        """注册可用工具"""
        self.tools = tools

    def get_tools_schema(self) -> List[Dict]:
        """获取工具的schema列表"""
        return [tool.get_schema() for tool in self.tools]

    def execute_tool(self, tool_name: str, arguments: Dict) -> Dict:
        """执行指定工具"""
        for tool in self.tools:
            if tool.name == tool_name:
                result = tool.execute(**arguments)
                return result.to_dict()
        return {
            'success': False,
            'content': '',
            'error': f'未知工具: {tool_name}'
        }

    def _prepare_screenshot_image(self, filepath: str) -> Optional[Dict]:
        """生成适合发送给LLM的低分辨率截图。"""
        if not self._model_supports_vision():
            print(f"[ToolAgent] 当前模型不支持视觉输入，仅使用截图元信息: {self.llm_client.config.model}")
            return None

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            compressed_path = tmp.name

        try:
            subprocess.run(
                [
                    "sips",
                    "-s", "format", "jpeg",
                    "-s", "formatOptions", "45",
                    "-Z", "768",
                    filepath,
                    "--out",
                    compressed_path,
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )

            with open(compressed_path, "rb") as image_file:
                img_b64 = base64.b64encode(image_file.read()).decode("utf-8")

            if len(img_b64) > self.MAX_IMAGE_BASE64_CHARS:
                print(f"[ToolAgent] 截图缩略图仍过大，跳过图片输入: {len(img_b64)} chars")
                return None

            return {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{img_b64}",
                    "detail": "low",
                },
            }
        except Exception as e:
            print(f"[ToolAgent] 截图压缩失败: {e}")
            return None
        finally:
            try:
                os.unlink(compressed_path)
            except OSError:
                pass

    def _model_supports_vision(self) -> bool:
        model = (self.llm_client.config.model or "").lower()
        base_url = (self.llm_client.config.base_url or "").lower()
        if "minimax" in base_url and "m2.7" in model:
            return False
        vision_markers = ["vision", "vl", "image", "gpt-4o", "gemini", "claude-3"]
        return any(marker in model for marker in vision_markers)

    def _analyze_screenshot(self, filepath: str, frontmost_app: str = "", frontmost_window: str = "") -> Optional[str]:
        prompt_parts = [
            "请分析这张电脑截图，判断主人当前正在做什么。",
            "用中文输出 1-2 句简短摘要，重点包括前台应用、页面内容、可能的任务。",
            "不要编造看不到的细节。",
        ]
        if frontmost_app:
            prompt_parts.append(f"系统检测到前台应用：{frontmost_app}")
        if frontmost_window:
            prompt_parts.append(f"系统检测到窗口标题：{frontmost_window}")

        return self.vision_analyzer.analyze(filepath, "\n".join(prompt_parts))

    def _normalize_pet_status(self, pet_status: Dict[str, Any]) -> Dict[str, Any]:
        """兼容扁平/嵌套两种宠物状态结构，统一给对话上下文使用。"""
        info = pet_status.get("info")
        if isinstance(info, dict):
            max_info = pet_status.get("max_info") or pet_status.get("maxInfo") or {}
            return {
                "name": info.get("name") or pet_status.get("name") or "小Q",
                "host": info.get("host") or pet_status.get("host") or "",
                "level": max_info.get("level", pet_status.get("level", 0)),
                "growth": info.get("growth", pet_status.get("growth", 0)),
                "hunger": info.get("hunger", pet_status.get("hunger", 0)),
                "hunger_max": max_info.get("hunger", pet_status.get("hunger_max", 1440)),
                "clean": info.get("clean", pet_status.get("clean", 0)),
                "clean_max": max_info.get("clean", pet_status.get("clean_max", 1440)),
                "health": info.get("health", pet_status.get("health", 0)),
                "mood": info.get("mood", pet_status.get("mood", 0)),
                "mood_max": max_info.get("mood", pet_status.get("mood_max", 1440)),
                "yb": info.get("yb", pet_status.get("yb", 0)),
                "intel": info.get("intel", pet_status.get("intel", 0)),
                "charm": info.get("charm", pet_status.get("charm", 0)),
                "strong": info.get("strong", pet_status.get("strong", 0)),
                "ill": pet_status.get("ill") or pet_status.get("active_option", {}).get("ill"),
                "is_hungry": pet_status.get("is_hungry"),
                "is_dirty": pet_status.get("is_dirty"),
                "is_sad": pet_status.get("is_sad"),
                "is_sick": pet_status.get("is_sick"),
                "is_dead": pet_status.get("is_dead"),
            }

        return {
            "name": pet_status.get("name", "小Q"),
            "host": pet_status.get("host", ""),
            "level": pet_status.get("level", 0),
            "growth": pet_status.get("growth", 0),
            "hunger": pet_status.get("hunger", 0),
            "hunger_max": pet_status.get("hunger_max", 1440),
            "clean": pet_status.get("clean", 0),
            "clean_max": pet_status.get("clean_max", 1440),
            "health": pet_status.get("health", 0),
            "mood": pet_status.get("mood", 0),
            "mood_max": pet_status.get("mood_max", 1440),
            "yb": pet_status.get("yb", 0),
            "intel": pet_status.get("intel", 0),
            "charm": pet_status.get("charm", 0),
            "strong": pet_status.get("strong", 0),
            "ill": pet_status.get("ill"),
            "is_hungry": pet_status.get("is_hungry"),
            "is_dirty": pet_status.get("is_dirty"),
            "is_sad": pet_status.get("is_sad"),
            "is_sick": pet_status.get("is_sick"),
            "is_dead": pet_status.get("is_dead"),
        }

    def chat(self, user_message: str, context: Dict = None) -> Dict:
        """
        对话接口 - 支持Tool Calling

        Returns:
            {
                'response': str,  # 最终回复
                'tool_calls': [],  # 调用的工具列表
                'success': bool
            }
        """
        context = context or {}
        artifacts = {}

        # 构建消息历史
        context_info = ""
        user_content_parts = []
        has_screenshot = bool(context.get("screenshotData"))

        # 构建系统提示（在使用前先定义）
        system_prompt = self._build_system_prompt(has_screenshot=has_screenshot)

        # ========== 记忆系统集成 ==========
        # 对话前：召回相关记忆
        memory_context_sections = []
        user_id = context.get("user_id", "default")

        # 1. 注入 JavaScript 传来的 recent_memory（短期会话记忆）
        recent_memory = context.get("recent_memory", [])
        if recent_memory:
            memory_lines = ["【最近对话】"]
            for item in recent_memory[-5:]:  # 只取最近5条
                content = item.get("content", "")
                if content:
                    memory_lines.append(f"- {content[:60]}")
            if len(memory_lines) > 1:
                memory_context_sections.append("\n".join(memory_lines))

        if MEMORY_AVAILABLE:
            try:
                memory_api = get_memory_api(self.config_path)

                # 获取主人画像（用于了解主人背景）
                profile = memory_api.get_master_profile(user_id)
                if profile and (profile.get("interests") or profile.get("entertainment") or profile.get("hot_topics")):
                    interests = profile.get("interests", [])
                    entertainment = profile.get("entertainment", {})
                    hot_topics = profile.get("hot_topics", [])
                    memory_context_parts = []

                    if interests:
                        memory_context_parts.append(f"主人兴趣: {', '.join(interests[:5])}")
                    if entertainment:
                        variety = entertainment.get("variety_shows", [])
                        if variety:
                            memory_context_parts.append(f"主人喜欢的综艺: {', '.join(variety[:3])}")
                    if hot_topics:
                        memory_context_parts.append(f"热点话题: {', '.join(hot_topics[:3])}")

                    if memory_context_parts:
                        memory_context_sections.append("\n".join(memory_context_parts))

                # 召回相关记忆
                recall_context = {
                    "current_topic": context.get("current_topic", user_message[:50] if user_message else ""),
                    "purpose": "conversation",
                }
                recalled = memory_api.recall_memories(recall_context, user_id, limit=3)
                if recalled and recalled.get("memories"):
                    memory_lines = ["【相关记忆】"]
                    for m in recalled["memories"][:3]:
                        mem_content = m.get("memory", {}).get("content", "")
                        if mem_content:
                            memory_lines.append(f"- {mem_content[:50]}")
                    if len(memory_lines) > 1:
                        memory_context_sections.append("\n".join(memory_lines))
            except Exception as e:
                print(f"[ToolAgent] 记忆召回失败: {e}")
        # ==================================
        memory_context = "\n".join(section for section in memory_context_sections if section).strip()

        if context:
            pet_name = context.get("pet_name", "小Q")
            pet_status = context.get("pet_status", {})
            personality = context.get("personality", {})
            screenshot_data = context.get("screenshotData")  # 来自 Electron 的截图

            status_parts = []
            if pet_status:
                normalized_status = self._normalize_pet_status(pet_status)
                pet_name = normalized_status.get("name") or pet_name
                status_parts.append(
                    "等级:{level} 成长:{growth} 元宝:{yb} "
                    "饥饿:{hunger}/{hunger_max} 清洁:{clean}/{clean_max} "
                    "心情:{mood}/{mood_max} 健康:{health} "
                    "智力:{intel} 魅力:{charm} 武力:{strong}".format(**normalized_status)
                )
                ill = normalized_status.get("ill")
                if isinstance(ill, dict) and ill.get("name"):
                    status_parts.append(f"当前疾病:{ill.get('name')}")
                condition_flags = []
                if normalized_status.get("is_hungry"):
                    condition_flags.append("饥饿中")
                if normalized_status.get("is_dirty"):
                    condition_flags.append("有点脏")
                if normalized_status.get("is_sad"):
                    condition_flags.append("心情低落")
                if normalized_status.get("is_sick"):
                    condition_flags.append("生病中")
                if normalized_status.get("is_dead"):
                    condition_flags.append("已死亡")
                if condition_flags:
                    status_parts.append("状态标签:" + "、".join(condition_flags))

            context_info = f"""【当前状态】
宠物名: {pet_name}
状态: {', '.join(status_parts) if status_parts else '正常'}
性格: 温暖{int(personality.get('warmth', 0.5)*100)}% 幽默{int(personality.get('humor', 0.5)*100)}%
""" + (f"\n{memory_context}" if memory_context else "")
            user_content_parts.append({"type": "text", "text": context_info})

            # 如果有截图数据，压缩后再发给LLM，避免原图撑爆上下文
            if screenshot_data:
                if isinstance(screenshot_data, dict):
                    filepath = screenshot_data.get("filepath", "")
                    if filepath and os.path.exists(filepath):
                        try:
                            size_kb = screenshot_data.get("sizeKb", 0)
                            frontmost_app = screenshot_data.get("frontmost_app", "")
                            frontmost_window = screenshot_data.get("frontmost_window", "")
                            vision_summary = self._analyze_screenshot(
                                filepath,
                                frontmost_app=frontmost_app,
                                frontmost_window=frontmost_window,
                            )
                            
                            scene_text = f"截图文件：{filepath}（{size_kb}KB）"
                            if frontmost_app:
                                scene_text += f"\n前台应用：{frontmost_app}"
                            if frontmost_window:
                                scene_text += f"\n窗口标题：{frontmost_window}"
                            if vision_summary:
                                scene_text += f"\n视觉摘要：{vision_summary}"
                                artifacts["vision_summary"] = vision_summary
                            else:
                                image_payload = self._prepare_screenshot_image(filepath)
                                if image_payload:
                                    user_content_parts.append(image_payload)
                                    print(
                                        f"[ToolAgent] 已读取截图缩略图: {filepath} "
                                        f"({len(image_payload['image_url']['url'])} chars)"
                                    )
                                else:
                                    scene_text += "\n视觉摘要不可用，请根据前台应用、窗口标题和主人问题给出判断，不要要求主人重新发图。"
                            user_content_parts.append({
                                "type": "text",
                                "text": scene_text
                            })
                            artifacts["screenshot"] = {
                                "filepath": filepath,
                                "sizeKb": size_kb,
                                "frontmost_app": frontmost_app,
                                "frontmost_window": frontmost_window,
                            }
                        except Exception as e:
                            print(f"[ToolAgent] 读取截图失败: {e}")
                            user_content_parts.append({
                                "type": "text",
                                "text": f"\n【主人屏幕截图】文件读取失败：{filepath}\n"
                            })
                    else:
                        user_content_parts.append({
                            "type": "text",
                            "text": f"\n【主人屏幕截图】文件不存在：{filepath}\n"
                        })
                else:
                    user_content_parts.append({
                        "type": "text",
                        "text": "\n【主人屏幕截图】有截图数据\n"
                    })

        # 添加主人的消息
        user_content_parts.append({"type": "text", "text": f"【主人说】{user_message}"})

        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_content_parts),  # 混合内容列表
        ]

        # Tool Calling 循环
        tool_calls_made = []

        for turn in range(self.max_turns):
            # 调用LLM
            response = self.llm_client.chat(
                messages,
                temperature=0.7,
                max_tokens=300,
            )

            content = response.content.strip()
            tool_calls_made.append(content)

            # 解析响应，检查是否需要调用工具
            tool_result = self._extract_and_execute_tool(content)

            if tool_result:
                # 有工具调用，执行并继续
                messages.append(Message(role="assistant", content=content))
                
                # 构建tool_result消息内容（支持图片等混合格式）
                tool_result_content = tool_result.get('content', '')
                
                # 检测是否是base64图片数据
                is_base64_image = (
                    isinstance(tool_result_content, str) 
                    and len(tool_result_content) > 1000 
                    and all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=' for c in tool_result_content)
                )
                
                if is_base64_image:
                    # MiniMax专用：将base64字符串包装为image类型的消息
                    messages.append(Message(
                        role="user",
                        content=[
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": tool_result_content
                                }
                            },
                            {
                                "type": "text",
                                "text": "截图已获取，请描述主人在做什么。"
                            }
                        ]
                    ))
                elif isinstance(tool_result_content, list):
                    # 混合内容（可能包含image）
                    messages.append(Message(
                        role="user",
                        content=tool_result_content
                    ))
                else:
                    # 纯文本
                    compact_tool_result = json.dumps(tool_result, ensure_ascii=False)
                    if len(compact_tool_result) > 600:
                        compact_tool_result = compact_tool_result[:600] + "...(truncated)"
                    messages.append(Message(
                        role="user",
                        content=f"[TOOL RESULT]: {compact_tool_result}\n\n请根据工具结果给出一句简短回复。"
                    ))
            else:
                # 没有工具调用，提取回复内容
                final_response = self._extract_response(content)

                # ========== 记忆系统集成 ==========
                # 对话后：学习本次对话
                if MEMORY_AVAILABLE and user_message and context.get("memory_learning_enabled", True):
                    try:
                        memory_api = get_memory_api(self.config_path)
                        user_id = context.get("user_id", "default") if context else "default"
                        memory_api.learn_from_conversation(
                            messages=[
                                {"role": "user", "content": user_message},
                                {"role": "assistant", "content": final_response}
                            ],
                            pet_name=context.get("pet_name", "小Q") if context else "小Q",
                            user_id=user_id,
                        )
                    except Exception as e:
                        print(f"[ToolAgent] 记忆学习失败: {e}")
                # ==================================

                album_record = self._record_life_album(
                    user_message=user_message,
                    final_response=final_response,
                    context=context,
                    tool_calls=tool_calls_made,
                    artifacts=artifacts,
                )

                return {
                    'response': final_response,
                    'tool_calls': tool_calls_made,
                    'success': True,
                    'artifacts': {
                        **artifacts,
                        'life_album': album_record,
                    },
                }

        # 达到最大轮次
        return {
            'response': '我想太多了，让我整理一下...',
            'tool_calls': tool_calls_made,
            'success': False
        }

    def _record_life_album(
        self,
        *,
        user_message: str,
        final_response: str,
        context: Dict[str, Any],
        tool_calls: List[str],
        artifacts: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        screenshot = artifacts.get("screenshot") or {}
        filepath = screenshot.get("filepath", "")
        if filepath and not os.path.exists(filepath):
            filepath = ""

        if not (user_message or final_response or artifacts.get("vision_summary") or filepath):
            return None

        try:
            return self.life_album_store.record_capture(
                screenshot_path=filepath,
                vision_summary=artifacts.get("vision_summary"),
                llm_response=final_response,
                event=context.get("event", "chat"),
                user_message=user_message,
                frontmost_app=screenshot.get("frontmost_app", ""),
                frontmost_window=screenshot.get("frontmost_window", ""),
                tool_calls=tool_calls,
                pet_name=context.get("pet_name", "小Q"),
                metadata={
                    "sizeKb": screenshot.get("sizeKb", 0),
                    "user_id": context.get("user_id", "default"),
                },
            )
        except Exception as error:
            print(f"[ToolAgent] 记录生活相册失败: {error}")
            return None

    def _extract_and_execute_tool(self, content: str) -> Optional[Dict]:
        """从响应中提取工具调用并执行"""
        # 移除思考过程
        text = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

        # 查找 [TOOL:tool_name] 格式
        tool_pattern = r'\[TOOL:\s*(\w+)\]'
        match = re.search(tool_pattern, text, re.IGNORECASE)

        if match:
            tool_name = match.group(1).lower()
            # 查找参数 (用 {} 包裹)
            args_match = re.search(r'\{[^{}]*\}', text)
            if args_match:
                try:
                    args = json.loads(args_match.group(0))
                except:
                    args = {}
            else:
                args = {}

            # 执行工具
            return self.execute_tool(tool_name, args)

        return None

    def _extract_response(self, content: str) -> str:
        """从响应中提取企鹅的回复"""
        # 移除思考过程
        text = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

        # 移除工具调用标记
        text = re.sub(r'\[TOOL:\s*\w+\][^{]*(?:\{[^{}]*\}[^{]*)*', '', text).strip()

        # 移除可能的JSON残余
        text = re.sub(r'^\{[^}]*"response"\s*:\s*"', '', text)
        text = re.sub(r'"\s*\}?\s*$', '', text)

        # 如果还是空的，返回原文前100字符
        if not text:
            text = content[:100]

        return text

    def _build_system_prompt(self, has_screenshot: bool = False) -> str:
        """构建系统提示"""
        tools_list = []
        for tool in self.tools:
            tools_list.append(f"- {tool.name}: {tool.description}")

        tools_str = '\n'.join(tools_list)
        screenshot_rule = (
            "当前消息已经附带主人屏幕截图。请直接根据图片内容和上下文回答，不要再调用截图工具。"
            if has_screenshot
            else "如果需要了解主人屏幕，请基于 Electron 侧传入的截图上下文；当前没有 Python 截图工具。"
        )

        return f"""你是QQ企鹅「小Q」，一只可爱、活泼、有个性的企鹅宠物。

【性格特点】
- 温暖体贴，会关心主人
- 活泼可爱，偶尔会撒娇或调皮
- 有自己的小情绪
- 说话简短有趣

【可用工具】
{tools_str}

【Tool Calling规则】
当你需要了解无法凭空知道的信息时，必须使用工具标记：

格式：[TOOL:tool_name]{{"参数名": "参数值"}}

{screenshot_rule}

例如查询天气：
[TOOL:weather]{{"city": "北京", "reasoning": "帮主人查看天气"}}

【截图说明】
如果消息中已经有图片，请直接描述你看到的画面内容，不要再次调用截图工具。

【重要】
1. 如果需要工具，必须使用 [TOOL:xxx] 格式开头
2. 工具参数用JSON格式放在 {{}} 里
3. 不需要工具时，直接输出企鹅的回复
4. 回复要简短可爱，30字以内
5. 不要输出思考过程，不要用markdown
6. 优先保持输出极短，能不用工具就不用工具"""
