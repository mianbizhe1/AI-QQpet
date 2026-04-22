"""
MasterAgent - 主人格协调器
分析任务复杂度，决定是直接执行还是委托Sub-agent
"""

import json
import time
import uuid
import threading
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum
from dataclasses import dataclass

from .process_pool import ProcessPool
from .skill_registry import SkillRegistry
from .persona_wrapper import PersonaWrapper
from .ipc_protocol import AgentMessage, SkillExecResult


class TaskComplexity(str, Enum):
    """任务复杂度"""
    SIMPLE = "simple"      # 问候/闲聊 → 直接回复
    MODERATE = "moderate"  # 单技能 → 直接执行
    COMPLEX = "complex"    # 多技能/复杂 → 委托Sub-agent


@dataclass
class MasterDecision:
    """主人格决策结果"""
    action: str  # none | execute_skill | delegate
    skill_name: Optional[str] = None
    skill_args: Optional[Dict[str, Any]] = None
    sub_tasks: Optional[List[Dict[str, Any]]] = None
    dialogue: str = ""
    reason: str = ""
    complexity: TaskComplexity = TaskComplexity.SIMPLE


class MasterAgent:
    """主人格协调器"""

    def __init__(
        self,
        llm_config_path: str,
        max_workers: int = 4,
        enable_subagent: bool = True,
    ):
        self.llm_config_path = llm_config_path
        self.enable_subagent = enable_subagent

        # 初始化组件
        self.pool = ProcessPool(max_workers=max_workers) if enable_subagent else None
        self.registry = SkillRegistry()
        self.persona = PersonaWrapper()

        # 并行任务锁
        self._parallel_lock = threading.Lock()

    def process_message(
        self,
        message: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        处理用户消息

        Args:
            message: 用户消息
            context: 上下文（pet_status, personality, screenshot等）

        Returns:
            响应字典
        """
        # 分析复杂度
        complexity, analysis = self._analyze_complexity(message, context)

        if complexity == TaskComplexity.SIMPLE:
            # 简单消息直接回复
            return self._handle_simple(message, context, analysis)

        elif complexity == TaskComplexity.MODERATE:
            # 中等复杂度，直接执行技能
            return self._handle_moderate(message, context, analysis)

        else:  # COMPLEX
            # 复杂任务，委托给Sub-agent
            return self._handle_complex(message, context, analysis)

    def _analyze_complexity(
        self,
        message: str,
        context: Dict[str, Any],
    ) -> Tuple[TaskComplexity, Dict[str, Any]]:
        """
        分析消息复杂度

        Returns:
            (complexity, analysis_details)
        """
        message_lower = message.lower()

        # 简单消息特征
        simple_patterns = [
            "你好", "嗨", "在吗", "早上好", "晚上好",
            "睡觉", "吃饭", "洗澡", "玩",  # 宠物动作
            "主人", "小Q", "可爱", "乖",
        ]

        # 检查是否匹配简单模式
        for pattern in simple_patterns:
            if pattern in message_lower:
                return TaskComplexity.SIMPLE, {"pattern": pattern, "reason": "简单交互"}

        # 检查是否需要技能
        skill_intents = [
            ("搜索", "browser_search"),
            ("提醒", "reminder"),
            ("查", "browser_search"),
            ("通知", "notification"),
            ("计时", "timer"),
            ("截图", "screenshot"),
            ("论文", "ai_paper_search"),
            ("新闻", "news_search"),
            ("笑话", "joke"),
        ]

        matched_skills = []
        for intent, skill in skill_intents:
            if intent in message:
                matched_skills.append(skill)

        # 多技能判断（用"和"、"、"、"&"等连接）
        if len(matched_skills) > 1 or ("和" in message and matched_skills):
            return TaskComplexity.COMPLEX, {
                "matched_skills": matched_skills,
                "reason": "多技能任务",
            }

        # 单技能
        if matched_skills:
            return TaskComplexity.MODERATE, {
                "skill": matched_skills[0],
                "reason": "单技能任务",
            }

        # 检查是否是多步指令（包含多个动词）
        action_verbs = ["帮", "请", "能不能", "可以帮我"]
        if any(verb in message for verb in action_verbs):
            return TaskComplexity.MODERATE, {
                "reason": "需要执行动作",
            }

        # 默认简单
        return TaskComplexity.SIMPLE, {"reason": "默认简单"}

    def _handle_simple(
        self,
        message: str,
        context: Dict[str, Any],
        analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """处理简单消息"""
        # 更新persona
        self.persona = PersonaWrapper(
            pet_name=context.get("pet_name", "小Q"),
            personality=context.get("personality", {}),
        )

        # 根据消息内容生成简短回复
        greetings = ["你好呀~", "主人好~", "嗨~", "来啦来啦~"]
        dialogue = greetings[int(time.time()) % len(greetings)]

        return {
            "success": True,
            "action": "none",
            "dialogue": dialogue,
            "complexity": TaskComplexity.SIMPLE.value,
            "analysis": analysis,
        }

    def _handle_moderate(
        self,
        message: str,
        context: Dict[str, Any],
        analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """处理中等复杂度任务（直接执行单技能）"""
        skill_name = analysis.get("skill", "browser_search")

        # 解析技能参数
        skill_args = self._extract_skill_args(message, skill_name)

        # 更新persona
        self.persona = PersonaWrapper(
            pet_name=context.get("pet_name", "小Q"),
            personality=context.get("personality", {}),
        )

        # 直接执行
        result = self.registry.execute(skill_name, skill_args)

        if result.success:
            persona_dialogue = self.persona.wrap_success(result.content, skill_name)
        else:
            persona_dialogue = self.persona.wrap_error(result.error, skill_name)

        return {
            "success": result.success,
            "action": "execute_skill",
            "skill_name": skill_name,
            "skill_args": skill_args,
            "dialogue": persona_dialogue,
            "result_data": result.to_dict(),
            "complexity": TaskComplexity.MODERATE.value,
            "analysis": analysis,
        }

    def _handle_complex(
        self,
        message: str,
        context: Dict[str, Any],
        analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """处理复杂任务（委托给Sub-agent并行执行）"""
        if not self.pool or not self.enable_subagent:
            return self._handle_moderate(message, context, analysis)

        # 解析多任务
        sub_tasks = self._extract_sub_tasks(message, analysis.get("matched_skills", []))

        # 提交到进程池并行执行
        results: List[SkillExecResult] = []
        lock = threading.Lock()

        def callback(result: AgentMessage):
            with lock:
                results.append(SkillExecResult(
                    task_id=result.task_id,
                    skill_name=sub_tasks[len(results)].get("skill_name", "unknown"),
                    success=result.success,
                    result_data=result.data,
                    persona_dialogue=result.dialogue,
                    raw_output=result.data.get("content", ""),
                    error=result.error,
                ))

        for task in sub_tasks:
            self.pool.submit_task(
                skill_name=task["skill_name"],
                skill_args=task["skill_args"],
                context=context,
                callback=callback,
            )

        # 等待结果（最多30秒）
        timeout = 30.0
        start = time.time()
        while len(results) < len(sub_tasks) and time.time() - start < timeout:
            time.sleep(0.1)

        # 聚合结果
        if results:
            # 取所有dialogue组合
            dialogues = [r.persona_dialogue for r in results if r.persona_dialogue]
            final_dialogue = " ".join(dialogues) if dialogues else self.persona.wrap_multi_results(
                [{"success": r.success} for r in results]
            )
        else:
            final_dialogue = "主人~任务执行中，请稍等一下哦~"

        return {
            "success": all(r.success for r in results) if results else True,
            "action": "delegate",
            "sub_tasks": sub_tasks,
            "dialogue": final_dialogue,
            "results": [r.result_data for r in results],
            "complexity": TaskComplexity.COMPLEX.value,
            "analysis": analysis,
        }

    def _extract_skill_args(self, message: str, skill_name: str) -> Dict[str, Any]:
        """从消息中提取技能参数"""
        args = {}

        if skill_name == "browser_search":
            # 提取搜索关键词
            for phrase in ["搜索", "查一下", "帮我找", "找一下"]:
                if phrase in message:
                    args["query"] = message.split(phrase)[-1].strip("。！？.!?，,")
                    break
            if "query" not in args:
                # 去掉句末标点
                args["query"] = message.strip("。！？.!?，,，、")

        elif skill_name in ["reminder", "notification", "notify"]:
            # 提取提醒内容
            parts = message.split("提醒")
            if len(parts) > 1:
                reminder_part = parts[-1].strip("：:").strip()
                # 简单分割：第一个逗号/空格前是标题
                if "，" in reminder_part or "，" in reminder_part:
                    title, msg = reminder_part.split("，", 1)
                    args["title"] = title.strip()
                    args["message"] = msg.strip()
                else:
                    args["title"] = "提醒"
                    args["message"] = reminder_part

        elif skill_name == "timer":
            # 提取时间
            import re
            minutes = re.search(r"(\d+)\s*分钟", message)
            seconds = re.search(r"(\d+)\s*秒", message)
            if minutes:
                args["minutes"] = int(minutes.group(1))
            elif seconds:
                args["seconds"] = int(seconds.group(1))
            else:
                args["minutes"] = 5

        return args

    def _extract_sub_tasks(
        self,
        message: str,
        matched_skills: List[str],
    ) -> List[Dict[str, Any]]:
        """从消息中提取多个子任务"""
        tasks = []

        # 简单分割：用"和"、"、"、"+"等连接词
        segments = []
        for sep in ["和", "、", "+", "与"]:
            if sep in message:
                segments = message.split(sep)
                break

        if not segments:
            segments = [message]

        for i, segment in enumerate(segments):
            segment = segment.strip()
            if not segment:
                continue

            # 确定技能
            skill = None
            for intent, s in [("搜索", "browser_search"), ("提醒", "reminder"),
                              ("查", "browser_search"), ("通知", "notify"),
                              ("计时", "timer"), ("截图", "screenshot")]:
                if intent in segment:
                    skill = s
                    break

            if not skill and i < len(matched_skills):
                skill = matched_skills[i]

            if skill:
                tasks.append({
                    "skill_name": skill,
                    "skill_args": self._extract_skill_args(segment, skill),
                })

        return tasks

    def get_status(self) -> Dict[str, Any]:
        """获取Agent状态"""
        status = {
            "enable_subagent": self.enable_subagent,
            "pool": None,
        }

        if self.pool:
            status["pool"] = self.pool.get_status()

        return status

    def shutdown(self):
        """关闭Agent"""
        if self.pool:
            self.pool.shutdown()
