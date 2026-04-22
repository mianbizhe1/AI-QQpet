#!/usr/bin/env python3
"""
AI企鹅 API服务器 v2
集成LLM能力，支持智能对话
"""

import os
import sys
import json
import time
import asyncio
import re
from datetime import datetime
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, os.path.dirname(__file__))

from qq_pet.pet_client import PetClient
from qq_pet.actions import feed, bath, play, heal, auto_care, diagnose, get_inventory

# 导入AI模块
from ai_llm import get_dialogue_generator, get_llm_client, DialogueContext

# 导入工具模块
try:
    from ai_tools import get_all_tools, WeatherTool
    TOOLS_AVAILABLE = True
except ImportError as e:
    print(f"[Warning] ai_tools模块不可用: {e}")
    TOOLS_AVAILABLE = False

# 导入多智能体模块
try:
    from multi_agent import MasterAgent, TaskScheduler, SkillRegistry
    MULTI_AGENT_AVAILABLE = True
except ImportError as e:
    print(f"[Warning] multi_agent模块不可用: {e}")
    MULTI_AGENT_AVAILABLE = False

# ==================== 配置 ====================
CONFIG_FILE = os.path.expanduser("~/Library/Application Support/qq-pet-macos/config-macos.json")
HOST = "127.0.0.1"
PORT = 18080

# LLM配置文件路径
LLM_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "ai_llm", "config.yaml")

# ==================== HTTP服务器 ====================
try:
    from http.server import HTTPServer, BaseHTTPRequestHandler
except ImportError:
    from http.server import HTTPServer, BaseHTTPRequestHandler


class QQPETHandler(BaseHTTPRequestHandler):
    """处理QQ宠物API请求"""
    
    def __init__(self, *args, **kwargs):
        self.client = PetClient()
        self.dialogue_generator = None
        self._init_ai()
        super().__init__(*args, **kwargs)

    def _init_ai(self):
        """初始化AI模块"""
        try:
            # 检查LLM配置
            llm_client = get_llm_client(LLM_CONFIG_PATH)
            if llm_client.is_configured():
                self.dialogue_generator = get_dialogue_generator(LLM_CONFIG_PATH)
                print(f"[AI] LLM已配置: {llm_client.config.model}")
                print(f"[AI] Base URL: {llm_client.config.base_url}")
            else:
                print("[AI] LLM未配置，使用模板对话")
                self.dialogue_generator = get_dialogue_generator(LLM_CONFIG_PATH)
        except Exception as e:
            print(f"[AI] AI初始化失败: {e}")
            self.dialogue_generator = None

    def do_GET(self):
        """处理GET请求"""
        path = self.path.split('?')[0]

        if path == "/pet/status":
            self.handle_status()
        elif path == "/pet/inventory":
            self.handle_inventory()
        elif path == "/pet/diagnose":
            self.handle_diagnose()
        elif path == "/ai/status":
            self.handle_ai_status()
        elif path == "/ai/health":
            self.handle_ai_health_check()
        elif path == "/ai/personality":
            self.handle_ai_personality()
        elif path == "/ai/vision/status":
            self.handle_ai_vision_status()
        elif path == "/ai/skill/list":
            self.handle_skill_list()
        elif path == "/ai/skill/categories":
            self.handle_skill_categories()
        elif path == "/scheduler/task/list":
            self.handle_scheduler_list()
        elif path == "/agent/status":
            self.handle_agent_status()
        elif path == "/health":
            self.send_json({"status": "ok", "time": datetime.now().isoformat()})
        # Memory API
        elif path == "/memory/master":
            self.handle_memory_master()
        elif path == "/memory/master/interests":
            self.handle_memory_master_interests()
        elif path == "/memory/master/hot_topics":
            self.handle_memory_master_hot_topics()
        elif path == "/memory/master/markdown":
            self.handle_memory_master_markdown()
        elif path == "/memory/recall":
            self.handle_memory_recall()
        elif path == "/memory/recommend":
            self.handle_memory_recommend()
        elif path == "/memory/stats":
            self.handle_memory_stats()
        else:
            self.send_error(404, "Not Found")
    
    def do_POST(self):
        """处理POST请求"""
        path = self.path.split('?')[0]
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else '{}'
        
        try:
            data = json.loads(body) if body else {}
        except:
            data = {}
        
        if path == "/pet/feed":
            self.handle_feed(data)
        elif path == "/pet/bath":
            self.handle_bath(data)
        elif path == "/pet/play":
            self.handle_play(data)
        elif path == "/pet/heal":
            self.handle_heal(data)
        elif path == "/pet/auto_care":
            self.handle_auto_care(data)
        elif path == "/ai/dialogue":
            self.handle_ai_dialogue(data)
        elif path == "/ai/perception":
            self.handle_ai_perception(data)
        elif path == "/ai/decide":
            self.handle_ai_decide(data)
        elif path == "/ai/chat":
            self.handle_ai_chat(data)
        elif path == "/ai/skill/execute":
            self.handle_skill_execute(data)
        elif path == "/weather/briefing":
            self.handle_weather_briefing(data)
        elif path == "/scheduler/task/add":
            self.handle_scheduler_add(data)
        elif path == "/scheduler/task/remove":
            self.handle_scheduler_remove(data)
        elif path == "/scheduler/task/enable":
            self.handle_scheduler_enable(data)
        # Memory API
        elif path == "/memory/master":
            self.handle_memory_master_put(data)
        elif path == "/memory/master/interests":
            self.handle_memory_master_interests_post(data)
        elif path == "/memory/master/hot_topics":
            self.handle_memory_master_hot_topics_post(data)
        elif path == "/memory/recall":
            self.handle_memory_recall_post(data)
        elif path == "/memory/learn":
            self.handle_memory_learn(data)
        elif path == "/memory/memories":
            self.handle_memory_memories(data)
        else:
            self.send_error(404, "Not Found")
    
    # ==================== 宠物状态接口 ====================
    def handle_status(self):
        """获取宠物状态"""
        try:
            status = self.client.get_status()
            self.send_json(status.to_status_dict())
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)
    
    def handle_inventory(self):
        """获取背包物品"""
        try:
            inv = get_inventory(self.client)
            self.send_json(inv)
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)
    
    def handle_diagnose(self):
        """诊断宠物健康"""
        try:
            result = diagnose(self.client)
            self.send_json(result)
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)
    
    # ==================== 宠物动作接口 ====================
    def handle_feed(self, data):
        """喂食"""
        try:
            amount = data.get("amount", 1000)
            result = feed(self.client, amount)
            self.send_json(result)
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)
    
    def handle_bath(self, data):
        """洗澡"""
        try:
            amount = data.get("amount", 1000)
            result = bath(self.client, amount)
            self.send_json(result)
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)
    
    def handle_play(self, data):
        """逗玩"""
        try:
            mood_boost = data.get("mood_boost", 100)
            result = play(self.client, mood_boost)
            self.send_json(result)
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)
    
    def handle_heal(self, data):
        """治病"""
        try:
            result = heal(self.client)
            self.send_json(result)
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)
    
    def handle_auto_care(self, data):
        """一键养护"""
        try:
            config = {
                "feed_amount": data.get("feed_amount", 1000),
                "bath_amount": data.get("bath_amount", 1000),
                "play_mood_boost": data.get("play_mood_boost", 100)
            }
            result = auto_care(self.client, config)
            self.send_json(result)
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)
    
    # ==================== AI感知接口 ====================
    def handle_ai_status(self):
        """获取AI系统状态"""
        try:
            llm_client = get_llm_client(LLM_CONFIG_PATH)
            status = {
                "llm_configured": llm_client.is_configured(),
                "llm_model": llm_client.config.model if llm_client.is_configured() else None,
                "llm_base_url": llm_client.config.base_url if llm_client.is_configured() else None,
                "timestamp": datetime.now().isoformat(),
            }
            self.send_json(status)
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)
    
    def handle_ai_health_check(self):
        """LLM健康检查"""
        try:
            llm_client = get_llm_client(LLM_CONFIG_PATH)
            if not llm_client.is_configured():
                self.send_json({
                    "status": "error",
                    "message": "LLM未配置"
                }, status=400)
                return

            # 发送一个简单测试
            from ai_llm import Message
            response = llm_client.chat(
                [Message(role="user", content="你好，请回复'OK'")],
                system_prompt="你是一个友好的AI助手。"
            )

            if response.content.strip() == "OK" or "ok" in response.content.lower():
                self.send_json({
                    "status": "ok",
                    "model": response.model,
                    "usage": response.usage
                })
            else:
                self.send_json({
                    "status": "warning",
                    "message": "LLM响应异常",
                    "response": response.content
                })
        except Exception as e:
            self.send_json({
                "status": "error",
                "message": str(e)
            }, status=500)

    def handle_ai_personality(self):
        """获取派生AI个性"""
        try:
            personality = self.client.get_personality()
            pet_status = self.client.get_status()
            self.send_json({
                "personality": personality,
                "derived_from": {
                    "interaction_count": pet_status.info.interaction_count,
                    "charm": pet_status.info.charm,
                    "intel": pet_status.info.intel,
                    "mood": pet_status.info.mood,
                    "mood_history_len": len(pet_status.info.mood_history),
                },
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)
    
    def handle_ai_dialogue(self, data):
        """AI对话生成接口"""
        try:
            scene = data.get("scene", "click_response")
            pet_name = data.get("pet_name", "小Q")
            user_message = data.get("message")

            # 从 electron-store 获取派生个性（而非请求体）
            personality = self.client.get_personality()

            # 获取宠物状态
            pet_status = self.client.get_status()
            pet_status_dict = {
                "mood": pet_status.info.mood,
                "hunger": pet_status.info.hunger,
                "clean": pet_status.info.clean,
                "health": pet_status.info.health
            }

            # 生成对话
            if self.dialogue_generator:
                response = self.dialogue_generator.generate_dialogue(
                    scene=scene,
                    pet_name=pet_name,
                    personality=personality,
                    pet_status=pet_status_dict,
                    user_message=user_message
                )
            else:
                response = "[AI未初始化]"

            self.send_json({
                "scene": scene,
                "response": response,
                "personality": personality,
                "pet_status": pet_status_dict,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)
    
    def handle_ai_perception(self, data):
        """AI感知接口"""
        try:
            pet_status = self.client.get_status()
            
            perception = {
                "pet": {
                    "name": pet_status.info.name or "小Q",
                    "mood": pet_status.info.mood,
                    "mood_level": self._get_mood_level(pet_status.info.mood),
                    "hunger": pet_status.info.hunger,
                    "clean": pet_status.info.clean,
                    "health": pet_status.info.health,
                    "level": pet_status.max_info.level
                },
                "alerts": [],
                "suggestions": [],
                "dialogue_scene": None
            }
            
            # 检测问题并生成建议
            if pet_status.is_dead:
                perception["alerts"].append({
                    "type": "dead",
                    "message": "宠物已死亡，需要还魂丹"
                })
                perception["dialogue_scene"] = "dead"
            elif pet_status.is_sick:
                ill_name = pet_status.active_option.ill.get("name", "未知疾病") if pet_status.active_option.ill else "未知疾病"
                perception["alerts"].append({
                    "type": "sick",
                    "message": f"宠物生病了：{ill_name}"
                })
                perception["dialogue_scene"] = "sick"
            
            if pet_status.is_hungry:
                perception["alerts"].append({
                    "type": "hungry",
                    "message": "宠物饿了"
                })
                perception["suggestions"].append({
                    "action": "feed",
                    "priority": 8,
                    "message": "建议喂食"
                })
                if not perception["dialogue_scene"]:
                    perception["dialogue_scene"] = "hungry"
            
            if pet_status.is_dirty:
                perception["alerts"].append({
                    "type": "dirty",
                    "message": "宠物需要洗澡"
                })
                perception["suggestions"].append({
                    "action": "bath",
                    "priority": 6,
                    "message": "建议洗澡"
                })
                if not perception["dialogue_scene"]:
                    perception["dialogue_scene"] = "dirty"
            
            if pet_status.is_sad:
                perception["alerts"].append({
                    "type": "sad",
                    "message": "宠物心情不好"
                })
                perception["suggestions"].append({
                    "action": "play",
                    "priority": 4,
                    "message": "建议逗玩"
                })
                if not perception["dialogue_scene"]:
                    perception["dialogue_scene"] = "sad"
            
            self.send_json(perception)
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def handle_ai_decide(self, data):
        """统一AI入口：聊天优先走ToolAgent，其余事件走结构化决策"""
        try:
            self.send_json(self._build_ai_response(data))
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def handle_ai_chat(self, data):
        """兼容旧路由，内部复用统一AI入口"""
        try:
            chat_data = {
                **data,
                "event": "chat",
            }
            self.send_json(self._build_ai_response(chat_data))
        except Exception as e:
            print(f"[AI Chat] Error: {e}")
            self.send_json({"error": str(e)}, status=500)

    def handle_weather_briefing(self, data):
        """直接查询天气并返回适合宠物播报的内容"""
        if not TOOLS_AVAILABLE:
            self.send_json({"success": False, "error": "天气工具不可用"}, status=500)
            return

        try:
            tool = WeatherTool()
            result = tool.execute(
                city=data.get("city", ""),
                lat=data.get("lat"),
                lon=data.get("lon"),
                auto_locate=bool(data.get("auto_locate", False)),
                reasoning=data.get("reasoning", "启动时给主人播报天气"),
            )
            result_dict = result.to_dict()
            reminder = ""
            if result.success:
                reminder = self._build_weather_reminder(result.content, result.metadata or {})
            self.send_json({
                **result_dict,
                "reminder": reminder,
                "timestamp": datetime.now().isoformat(),
            })
        except Exception as e:
            self.send_json({"success": False, "error": str(e)}, status=500)

    def _build_weather_reminder(self, weather_text, metadata):
        city = metadata.get("city") or "主人那边"
        lines = [line.strip() for line in str(weather_text or "").splitlines() if line.strip()]
        now_line = next((line for line in lines if line.startswith("现在：")), "")
        tomorrow_line = next((line for line in lines if "明天(" in line), "")
        summary_parts = []
        if now_line:
            summary_parts.append(now_line.replace("现在：", "今天"))
        if tomorrow_line:
            summary_parts.append(tomorrow_line)
        if not summary_parts:
            summary_parts.append("天气我已经帮你看过啦")
        return f"主人~ {city}{'，'.join(summary_parts)}，记得照顾好自己哦~"

    def handle_ai_vision_status(self):
        """获取视觉模型配置状态"""
        try:
            from ai_agent.vision import QwenVisionAnalyzer

            analyzer = QwenVisionAnalyzer(LLM_CONFIG_PATH)
            self.send_json({
                "enabled": analyzer.is_configured(),
                "model": analyzer.config.get("model", ""),
                "base_url": analyzer.config.get("base_url", ""),
            })
        except Exception as e:
            self.send_json({"enabled": False, "error": str(e)})

    def _build_ai_response(self, data):
        """统一构造AI响应，保证聊天与决策返回同一格式"""
        event = data.get("event", "tick")
        execute = data.get("execute", True)
        message = data.get("message", "")
        user_context = data.get("user_context", {})
        recent_memory = data.get("recent_memory", [])

        if event == "chat" and not str(message or "").strip():
            raise ValueError("message不能为空")

        status = self.client.get_status()
        personality = self.client.get_personality()
        status_dict = status.to_status_dict()
        inventory = {
            "food_count": len(status.inventory.food),
            "commodity_count": len(status.inventory.commodity),
            "medicine_count": len(status.inventory.medicine),
            "food": status.inventory.food[:5],
            "commodity": status.inventory.commodity[:5],
            "medicine": status.inventory.medicine[:5],
        }

        tool_calls = []
        agent_name = "python_llm"

        if event in {"chat", "vision_watch"} and TOOLS_AVAILABLE:
            tool_result = self._run_tool_agent_chat(
                message=message,
                status_dict=status_dict,
                personality=personality,
                screenshot_data=user_context.get("screenshotData"),
                user_context=user_context,
            )
            if tool_result:
                agent_name = "tool_agent"
                tool_calls = tool_result.get("tool_calls", [])
                decision = self._normalize_decision(
                    {
                        "action": "none",
                        "action_args": {},
                        "dialogue": tool_result.get("response", ""),
                        "reason": "tool chat" if event == "chat" else "periodic vision context",
                        "priority": 1,
                    },
                    self._fallback_decision(event, status_dict),
                )
                return {
                    "agent": agent_name,
                    "event": event,
                    "message": message,
                    "response": decision.get("dialogue", ""),
                    "decision": decision,
                    "tool_calls": tool_calls,
                    "success": bool(tool_result.get("success", False)),
                    "pet_status": status_dict,
                    "personality": personality,
                    "timestamp": datetime.now().isoformat(),
                }

        decision = self._llm_decide(
            event=event,
            status=status_dict,
            personality=personality,
            inventory=inventory,
            message=message,
            user_context=user_context,
            recent_memory=recent_memory,
        )

        action_result = None
        action = decision.get("action", "none")
        if execute and action != "none":
            action_result = self._execute_agent_action(action, decision.get("action_args", {}))
            decision["action_result"] = action_result

        if action_result and action_result.get("success") and not decision.get("dialogue"):
            decision["dialogue"] = "我自己处理好啦~"

        # 检查是否有待显示的定时任务通知（tick事件时）
        pending_notifications = []
        if event == "tick" and MULTI_AGENT_AVAILABLE:
            try:
                scheduler = self._get_scheduler()
                if scheduler:
                    pending_notifications = scheduler.get_pending_notifications()
                    # 清空已获取的通知
                    scheduler.clear_pending_notifications()
            except Exception as e:
                print(f"[AI] 获取待显示通知失败: {e}")

        # 保存到记忆系统（异步，不阻塞响应）
        self._save_to_memory(
            event=event,
            message=message,
            dialogue=decision.get("dialogue", ""),
            decision=decision,
            status_dict=status_dict,
            user_context=user_context,
        )

        return {
            "agent": agent_name,
            "event": event,
            "message": message,
            "response": decision.get("dialogue", ""),
            "decision": decision,
            "tool_calls": tool_calls,
            "success": True,
            "pet_status": status_dict,
            "personality": personality,
            "pending_notifications": pending_notifications,
            "timestamp": datetime.now().isoformat(),
        }

    def _run_tool_agent_chat(self, message, status_dict, personality, screenshot_data=None, user_context=None):
        """聊天事件优先尝试ToolAgent"""
        try:
            from ai_agent import ToolAgent

            agent = ToolAgent(LLM_CONFIG_PATH)
            tools = get_all_tools()
            agent.register_tools(tools)

            context = {
                "pet_name": "小Q",
                "pet_status": status_dict,
                "personality": personality,
                "screenshotData": screenshot_data,
                "user_context": user_context or {},
                "user_id": (user_context or {}).get("user_id", "default"),
            }
            result = agent.chat(message, context)
            print(
                "[AI Chat] ToolAgent result:",
                json.dumps(
                    {
                        "message": message,
                        "response": result.get("response", ""),
                        "success": result.get("success", False),
                    },
                    ensure_ascii=False,
                ),
            )
            return result
        except Exception as e:
            print(f"[AI Chat] ToolAgent failed, fallback to decide: {e}")
            return None

    def _llm_decide(self, event, status, personality, inventory, message, user_context, recent_memory):
        """调用LLM产生结构化决策，失败时降级到最小安全策略"""
        fallback = self._fallback_decision(event, status)

        try:
            llm_client = get_llm_client(LLM_CONFIG_PATH)
            if not llm_client.is_configured():
                return fallback

            from ai_llm import Message

            system_prompt = """你是QQ企鹅的同一个AI agent，负责同时决定企鹅要说什么和做什么。

必须只输出一个JSON对象，不要Markdown，不要解释。
JSON格式：
{
  "action": "none|feed|bath|play|heal|auto_care",
  "action_args": {},
  "dialogue": "给主人看的短句，30字以内",
  "reason": "极短原因",
  "priority": 0-10
}

决策原则：
1. 宠物死亡或生病时优先 heal。
2. 饥饿时优先 feed，脏污时优先 bath，心情极低时 play。
3. 没有明显需求时通常 action=none，只做简短陪伴或不打扰。
4. 如果 event 是 click，优先生成亲昵回应，可选择 play。
5. 说话像可爱QQ企鹅，简短、有动作感，不输出思考过程。"""

            prompt = {
                "event": event,
                "pet_status": status,
                "personality": personality,
                "inventory": inventory,
                "message": message,
                "user_context": user_context,
                "recent_memory": recent_memory[-8:],
                "available_actions": {
                    "none": "不执行动作",
                    "feed": "增加饥饿值",
                    "bath": "增加清洁值",
                    "play": "增加心情值",
                    "heal": "治疗疾病或复活",
                    "auto_care": "按治病、喂食、洗澡、逗玩顺序自动养护",
                },
            }

            response = llm_client.chat(
                [Message(role="user", content=json.dumps(prompt, ensure_ascii=False))],
                system_prompt=system_prompt,
                temperature=0.2,
                max_tokens=300,
            )
            print(
                "[AI Agent] LLM raw response:",
                json.dumps(
                    {
                        "event": event,
                        "message": message,
                        "content": response.content,
                    },
                    ensure_ascii=False,
                ),
            )
            decision = self._parse_decision_json(response.content)
            print(
                "[AI Agent] LLM parsed decision:",
                json.dumps(decision, ensure_ascii=False),
            )
            return self._normalize_decision(decision, fallback)
        except Exception as e:
            print(f"[AI Agent] LLM决策失败，降级规则: {e}")
            return fallback

    def _parse_decision_json(self, content):
        """从LLM输出中解析JSON对象"""
        text = (content or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text).strip()
            text = re.sub(r"```$", "", text).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if not match:
                raise
            return json.loads(match.group(0))

    def _normalize_decision(self, decision, fallback):
        """校验并收敛LLM决策"""
        allowed = {"none", "feed", "bath", "play", "heal", "auto_care"}
        if not isinstance(decision, dict):
            return fallback

        action = decision.get("action", "none")
        if action not in allowed:
            action = fallback["action"]

        dialogue = str(decision.get("dialogue") or "").strip()
        if not dialogue:
            dialogue = str(fallback.get("dialogue") or "").strip()
        if len(dialogue) > 80:
            dialogue = dialogue[:80]

        priority = decision.get("priority", fallback.get("priority", 0))
        try:
            priority = max(0, min(10, int(priority)))
        except Exception:
            priority = fallback.get("priority", 0)

        return {
            "action": action,
            "action_args": decision.get("action_args") if isinstance(decision.get("action_args"), dict) else {},
            "dialogue": dialogue,
            "reason": str(decision.get("reason") or fallback.get("reason") or "")[:80],
            "priority": priority,
        }

    def _fallback_decision(self, event, status):
        """LLM不可用时的安全降级，只保证企鹅不会饿死/病死"""
        if status.get("is_dead") or status.get("is_sick"):
            return {"action": "heal", "action_args": {}, "dialogue": "我有点不舒服，先吃药药...", "reason": "健康异常", "priority": 10}
        if status.get("is_hungry"):
            return {"action": "feed", "action_args": {"amount": 1000}, "dialogue": "肚子咕噜叫，我先吃点东西~", "reason": "饥饿", "priority": 8}
        if status.get("is_dirty"):
            return {"action": "bath", "action_args": {"amount": 1000}, "dialogue": "我去洗香香啦~", "reason": "清洁过低", "priority": 6}
        if status.get("is_sad"):
            return {"action": "play", "action_args": {"mood_boost": 100}, "dialogue": "陪我玩一小会儿嘛~", "reason": "心情过低", "priority": 4}
        if event == "chat":
            return {"action": "none", "action_args": {}, "dialogue": "我在呢，主人想聊什么呀？", "reason": "聊天事件", "priority": 1}
        if event == "click":
            return {"action": "play", "action_args": {"mood_boost": 30}, "dialogue": "嘿嘿，主人摸摸真开心~", "reason": "互动反馈", "priority": 2}
        return {"action": "none", "action_args": {}, "dialogue": "", "reason": "状态稳定", "priority": 0}

    def _execute_agent_action(self, action, args):
        """执行agent选择的动作"""
        args = args or {}
        if action == "feed":
            return feed(self.client, int(args.get("amount", 1000)))
        if action == "bath":
            return bath(self.client, int(args.get("amount", 1000)))
        if action == "play":
            return play(self.client, int(args.get("mood_boost", 100)))
        if action == "heal":
            return heal(self.client)
        if action == "auto_care":
            return auto_care(self.client, args)
        return {"success": True, "action": "none"}
    
    def _get_mood_level(self, mood):
        """获取心情等级描述"""
        if mood >= 800:
            return "非常开心"
        elif mood >= 600:
            return "开心"
        elif mood >= 400:
            return "一般"
        elif mood >= 200:
            return "低落"
        else:
            return "非常难过"

    # ==================== 技能接口 ====================
    def handle_skill_list(self):
        """列出所有技能"""
        if not MULTI_AGENT_AVAILABLE:
            self.send_json({"error": "multi_agent模块不可用"}, status=500)
            return

        try:
            registry = SkillRegistry()
            skills = registry.list_all()
            self.send_json({
                "skills": skills,
                "total": len(skills),
            })
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def handle_skill_categories(self):
        """获取技能分类"""
        if not MULTI_AGENT_AVAILABLE:
            self.send_json({"error": "multi_agent模块不可用"}, status=500)
            return

        try:
            registry = SkillRegistry()
            categories = registry.get_categories()
            result = {}
            for cat in categories:
                result[cat] = registry.list_by_category(cat)
            self.send_json({
                "categories": result,
            })
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def handle_skill_execute(self, data):
        """执行技能"""
        if not MULTI_AGENT_AVAILABLE:
            self.send_json({"error": "multi_agent模块不可用"}, status=500)
            return

        try:
            skill_name = data.get("skill_name")
            skill_args = data.get("skill_args", {})
            context = data.get("context", {})

            if not skill_name:
                self.send_json({"error": "skill_name不能为空"}, status=400)
                return

            registry = SkillRegistry()
            result = registry.execute(skill_name, skill_args)

            if result.success:
                self.send_json({
                    "success": True,
                    "skill_name": skill_name,
                    "result": result.to_dict(),
                })
            else:
                self.send_json({
                    "success": False,
                    "error": result.error,
                }, status=400)

        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    # ==================== 调度器接口 ====================
    def _get_scheduler(self):
        """获取或创建调度器实例"""
        if not hasattr(self, "_scheduler"):
            if MULTI_AGENT_AVAILABLE:
                db_path = os.path.join(os.path.dirname(__file__), "data", "scheduler.db")
                os.makedirs(os.path.dirname(db_path), exist_ok=True)
                self._scheduler = TaskScheduler(db_path=db_path)
            else:
                self._scheduler = None
        return self._scheduler

    def _get_master_agent(self):
        """获取或创建MasterAgent实例"""
        if not hasattr(self, "_master_agent"):
            if MULTI_AGENT_AVAILABLE:
                self._master_agent = MasterAgent(LLM_CONFIG_PATH)
            else:
                self._master_agent = None
        return self._master_agent

    def handle_scheduler_list(self):
        """列出所有定时任务"""
        scheduler = self._get_scheduler()
        if not scheduler:
            self.send_json({"error": "scheduler不可用"}, status=500)
            return

        try:
            tasks = scheduler.list_tasks()
            self.send_json({
                "tasks": tasks,
                "total": len(tasks),
                "next_runs": scheduler.get_next_run_times(5),
            })
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def handle_scheduler_add(self, data):
        """添加定时任务"""
        scheduler = self._get_scheduler()
        if not scheduler:
            self.send_json({"error": "scheduler不可用"}, status=500)
            return

        try:
            name = data.get("name")
            cron_expr = data.get("cron")
            skill_name = data.get("skill_name")
            skill_args = data.get("skill_args", {})
            context = data.get("context", {})

            if not name or not cron_expr or not skill_name:
                self.send_json({
                    "error": "name, cron, skill_name不能为空"
                }, status=400)
                return

            task = scheduler.add_task(
                name=name,
                cron_expr=cron_expr,
                skill_name=skill_name,
                skill_args=skill_args,
                context=context,
            )

            self.send_json({
                "success": True,
                "task": task.to_dict(),
            })

        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def handle_scheduler_remove(self, data):
        """删除定时任务"""
        scheduler = self._get_scheduler()
        if not scheduler:
            self.send_json({"error": "scheduler不可用"}, status=500)
            return

        try:
            task_id = data.get("task_id")
            if not task_id:
                self.send_json({"error": "task_id不能为空"}, status=400)
                return

            success = scheduler.remove_task(task_id)
            self.send_json({"success": success})

        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def handle_scheduler_enable(self, data):
        """启用/禁用定时任务"""
        scheduler = self._get_scheduler()
        if not scheduler:
            self.send_json({"error": "scheduler不可用"}, status=500)
            return

        try:
            task_id = data.get("task_id")
            enabled = data.get("enabled", True)

            if not task_id:
                self.send_json({"error": "task_id不能为空"}, status=400)
                return

            success = scheduler.enable_task(task_id, enabled)
            self.send_json({"success": success})

        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    # ==================== Memory API ====================
    def _get_memory_api(self):
        """获取MemoryAPI实例"""
        if not hasattr(self, "_memory_api"):
            try:
                from memory import get_memory_api
                self._memory_api = get_memory_api(LLM_CONFIG_PATH)
            except ImportError as e:
                print(f"[MemoryAPI] 模块导入失败: {e}")
                self._memory_api = None
        return self._memory_api

    def handle_memory_master(self):
        """获取主人画像"""
        api = self._get_memory_api()
        if not api:
            self.send_json({"error": "memory模块不可用"}, status=500)
            return

        try:
            user_id = self._get_user_id()
            result = api.get_master_profile(user_id)
            self.send_json(result)
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def handle_memory_master_put(self, data):
        """更新主人画像"""
        api = self._get_memory_api()
        if not api:
            self.send_json({"error": "memory模块不可用"}, status=500)
            return

        try:
            user_id = self._get_user_id()
            result = api.update_master_profile(data, user_id)
            self.send_json(result)
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def handle_memory_master_interests(self):
        """获取兴趣领域"""
        api = self._get_memory_api()
        if not api:
            self.send_json({"error": "memory模块不可用"}, status=500)
            return

        try:
            user_id = self._get_user_id()
            result = api.get_interests(user_id)
            self.send_json(result)
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def handle_memory_master_interests_post(self, data):
        """添加兴趣领域"""
        api = self._get_memory_api()
        if not api:
            self.send_json({"error": "memory模块不可用"}, status=500)
            return

        try:
            interests = data.get("interests", [])
            if not isinstance(interests, list):
                self.send_json({"error": "interests必须是数组"}, status=400)
                return
            user_id = self._get_user_id()
            result = api.add_interests(interests, user_id)
            self.send_json(result)
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def handle_memory_master_hot_topics(self):
        """获取热点话题"""
        api = self._get_memory_api()
        if not api:
            self.send_json({"error": "memory模块不可用"}, status=500)
            return

        try:
            user_id = self._get_user_id()
            result = api.get_hot_topics(user_id)
            self.send_json(result)
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def handle_memory_master_hot_topics_post(self, data):
        """更新热点话题"""
        api = self._get_memory_api()
        if not api:
            self.send_json({"error": "memory模块不可用"}, status=500)
            return

        try:
            topics = data.get("hot_topics", [])
            if not isinstance(topics, list):
                self.send_json({"error": "hot_topics必须是数组"}, status=400)
                return
            user_id = self._get_user_id()
            result = api.update_hot_topics(topics, user_id)
            self.send_json(result)
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def handle_memory_master_markdown(self):
        """获取主人画像的Markdown格式"""
        api = self._get_memory_api()
        if not api:
            self.send_json({"error": "memory模块不可用"}, status=500)
            return

        try:
            user_id = self._get_user_id()
            markdown = api.get_master_markdown(user_id)
            self.send_json({"markdown": markdown})
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def handle_memory_recall(self):
        """召回相关记忆（GET方式简单调用）"""
        api = self._get_memory_api()
        if not api:
            self.send_json({"error": "memory模块不可用"}, status=500)
            return

        try:
            user_id = self._get_user_id()
            context = {
                "current_topic": self._get_query_param("topic", ""),
                "emotional_state": self._get_query_param("emotion", ""),
                "purpose": self._get_query_param("purpose", ""),
            }
            limit = int(self._get_query_param("limit", 10))
            result = api.recall_memories(context, user_id, limit)
            self.send_json(result)
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def handle_memory_recall_post(self, data):
        """召回相关记忆（POST方式）"""
        api = self._get_memory_api()
        if not api:
            self.send_json({"error": "memory模块不可用"}, status=500)
            return

        try:
            user_id = self._get_user_id()
            context = data.get("context", {})
            limit = data.get("limit", 10)
            personality = data.get("personality", {})

            if personality:
                result = api.recall_with_personality(context, personality, user_id, limit)
            else:
                result = api.recall_memories(context, user_id, limit)
            self.send_json(result)
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def handle_memory_recommend(self):
        """获取推荐内容"""
        api = self._get_memory_api()
        if not api:
            self.send_json({"error": "memory模块不可用"}, status=500)
            return

        try:
            user_id = self._get_user_id()
            num = int(self._get_query_param("num", 3))
            result = api.get_recommendations(user_id, num)
            self.send_json(result)
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def handle_memory_learn(self, data):
        """从对话中学习"""
        api = self._get_memory_api()
        if not api:
            self.send_json({"error": "memory模块不可用"}, status=500)
            return

        try:
            messages = data.get("messages", [])
            pet_name = data.get("pet_name", "小Q")
            user_id = self._get_user_id()
            result = api.learn_from_conversation(messages, pet_name, user_id)
            self.send_json(result)
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def handle_memory_memories(self, data):
        """记忆管理"""
        api = self._get_memory_api()
        if not api:
            self.send_json({"error": "memory模块不可用"}, status=500)
            return

        try:
            user_id = self._get_user_id()
            action = data.get("action", "list")

            if action == "list":
                limit = data.get("limit", 100)
                offset = data.get("offset", 0)
                category = data.get("category")
                result = api.get_memories(user_id, limit, offset, category)
            elif action == "add":
                memory_type = data.get("memory_type", "fact")
                content = data.get("content", "")
                source = data.get("source", "explicit")
                importance = data.get("importance", 0.5)
                tags = data.get("tags")
                category = data.get("category")
                result = api.add_memory(
                    memory_type, content, source, importance, tags, category, user_id
                )
            elif action == "delete":
                memory_id = data.get("memory_id")
                if not memory_id:
                    self.send_json({"error": "memory_id不能为空"}, status=400)
                    return
                result = api.delete_memory(memory_id, user_id)
            elif action == "search":
                keyword = data.get("keyword", "")
                limit = data.get("limit", 20)
                result = api.search_memories(keyword, user_id, limit)
            else:
                self.send_json({"error": f"未知action: {action}"}, status=400)
                return
            self.send_json(result)
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def handle_memory_stats(self):
        """获取记忆统计"""
        api = self._get_memory_api()
        if not api:
            self.send_json({"error": "memory模块不可用"}, status=500)
            return

        try:
            user_id = self._get_user_id()
            result = api.get_stats(user_id)
            self.send_json(result)
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def _save_to_memory(
        self,
        event: str,
        message: str,
        dialogue: str,
        decision: dict,
        status_dict: dict,
        user_context: dict,
    ):
        """保存对话到记忆系统"""
        try:
            api = self._get_memory_api()
            if not api:
                return

            user_id = user_context.get("user_id", "default")

            # 1. 保存对话片段
            api.save_tick_episode(
                event=event,
                dialogue=dialogue,
                decision=decision,
                pet_status=status_dict,
                user_message=message,
                user_id=user_id,
            )

            # 2. 如果有用户消息，学习用户偏好
            if message and event == "chat":
                messages = [{"role": "user", "content": message}]
                # 只有对话事件才学习用户偏好
                try:
                    api.learn_from_conversation(
                        messages=messages,
                        pet_name="小Q",
                        user_id=user_id,
                    )
                except Exception as e:
                    print(f"[AI] 学习用户偏好失败: {e}")

            # 3. 如果有推荐内容，更新热点话题
            if event == "tick" and decision.get("action") != "none":
                try:
                    # 保存执行的动作作为记忆
                    action = decision.get("action", "")
                    if action:
                        api.add_memory(
                            memory_type="event",
                            content=f"宠物执行了{action}动作",
                            source="observation",
                            importance=0.3,
                            tags=[action, "pet_action"],
                            category="pet_behavior",
                            user_id=user_id,
                        )
                except Exception as e:
                    print(f"[AI] 保存动作记忆失败: {e}")

        except Exception as e:
            # 记忆保存失败不影响主流程
            print(f"[AI] 保存记忆失败: {e}")

    def _get_user_id(self) -> str:
        """从请求中获取user_id"""
        return self._get_query_param("user_id", "default")

    def _get_query_param(self, name: str, default: str = "") -> str:
        """获取查询参数"""
        if "?" in self.path:
            query = self.path.split("?")[1]
            for param in query.split("&"):
                if "=" in param:
                    key, value = param.split("=", 1)
                    if key == name:
                        return value
        return default

    def handle_agent_status(self):
        """获取Agent和进程池状态"""
        master = self._get_master_agent()
        if not master:
            self.send_json({"error": "agent不可用"}, status=500)
            return

        try:
            self.send_json(master.get_status())
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)
    
    # ==================== 辅助方法 ====================
    def send_json(self, data, status=200):
        """发送JSON响应"""
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
        except (BrokenPipeError, ConnectionResetError):
            print("[AI Server] client disconnected before response was sent")
    
    def log_message(self, format, *args):
        """自定义日志格式"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")


def run_server(port=PORT):
    """启动API服务器"""
    # 检查配置文件
    config_path = Path(CONFIG_FILE)
    if not config_path.exists():
        print(f"[Warning] 配置文件不存在: {CONFIG_FILE}")
        print("[Warning] 将使用默认配置")

    # 检查LLM配置
    llm_config_path = Path(LLM_CONFIG_PATH)
    if llm_config_path.exists():
        print(f"[Info] LLM配置: {LLM_CONFIG_PATH}")
    else:
        print(f"[Warning] LLM配置文件不存在: {LLM_CONFIG_PATH}")
        print("[Warning] 将使用模板对话")

    # 启动服务器
    server = HTTPServer((HOST, port), QQPETHandler)
    print(f"""
╔══════════════════════════════════════════════════════════╗
║              AI企鹅 API 服务器 v2                        ║
║              (LLM Powered)                               ║
╠══════════════════════════════════════════════════════════╣
║  HTTP API:  http://{HOST}:{port}                         ║
║                                                        ║
║  Pet Endpoints:                                         ║
║    GET  /pet/status      - 获取宠物状态                  ║
║    GET  /pet/inventory   - 获取背包物品                  ║
║    GET  /pet/diagnose    - 诊断健康状态                  ║
║    POST /pet/feed        - 喂食                          ║
║    POST /pet/bath        - 洗澡                          ║
║    POST /pet/play        - 逗玩                          ║
║    POST /pet/heal        - 治病                          ║
║    POST /pet/auto_care   - 一键养护                      ║
║                                                        ║
║  AI Endpoints:                                          ║
║    GET  /ai/status       - AI系统状态                   ║
║    GET  /ai/health       - LLM健康检查                  ║
║    POST /ai/dialogue    - AI对话生成                   ║
║    POST /ai/perception  - AI感知分析                   ║
║                                                        ║
║  Examples:                                              ║
║    curl http://localhost:{port}/pet/status              ║
║    curl -X POST http://localhost:{port}/ai/perception  ║
║    curl -X POST http://localhost:{port}/ai/dialogue    ║
║      -d '{{"scene":"click_response"}}'                   ║
║                                                        ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Server] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    run_server()
