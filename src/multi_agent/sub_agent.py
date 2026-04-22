"""
SubAgent实现
运行在独立进程中，执行技能任务
"""

import json
import sys
import os
import traceback
from typing import Dict, Any, Optional

from .ipc_protocol import WorkerMessage, AgentMessage
from .skill_registry import SkillRegistry
from .persona_wrapper import PersonaWrapper


class SubAgent:
    """子Agent实现"""

    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        self.registry = SkillRegistry()
        self.persona = PersonaWrapper()

        # 加载LLM配置路径
        self.llm_config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "ai_llm",
            "config.yaml"
        )

    def execute_task(
        self,
        task_id: str,
        skill_name: str,
        skill_args: Dict[str, Any],
        context: Dict[str, Any],
    ) -> AgentMessage:
        """
        执行技能任务

        Args:
            task_id: 任务ID
            skill_name: 技能名称
            skill_args: 技能参数
            context: 执行上下文（包含pet_name, personality等）

        Returns:
            AgentMessage: 执行结果消息
        """
        # 更新persona
        if context:
            self.persona = PersonaWrapper(
                pet_name=context.get("pet_name", "小Q"),
                personality=context.get("personality", {}),
            )

        try:
            # 执行技能
            skill_result = self.registry.execute(skill_name, skill_args)

            if skill_result.success:
                # 角色化输出
                persona_dialogue = self.persona.wrap_success(
                    skill_result.content,
                    skill_name,
                )

                return AgentMessage(
                    type="result",
                    task_id=task_id,
                    success=True,
                    data=skill_result.to_dict(),
                    dialogue=persona_dialogue,
                )
            else:
                persona_dialogue = self.persona.wrap_error(
                    skill_result.error or "执行失败",
                    skill_name,
                )

                return AgentMessage(
                    type="error",
                    task_id=task_id,
                    success=False,
                    error=skill_result.error,
                    dialogue=persona_dialogue,
                )

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            traceback.print_exc()

            persona_dialogue = self.persona.wrap_error(error_msg, skill_name)

            return AgentMessage(
                type="error",
                task_id=task_id,
                success=False,
                error=error_msg,
                dialogue=persona_dialogue,
            )

    def chat(self, message: str, context: Dict[str, Any]) -> AgentMessage:
        """
        使用LLM进行对话

        Args:
            message: 用户消息
            context: 上下文

        Returns:
            AgentMessage: 对话结果
        """
        try:
            from ai_llm import get_llm_client, Message

            llm_client = get_llm_client(self.llm_config_path)
            if not llm_client.is_configured():
                return AgentMessage(
                    type="error",
                    task_id="",
                    success=False,
                    error="LLM未配置",
                    dialogue="唔...主人，我还没配置大脑呢~",
                )

            # 构建prompt
            system_prompt = f"""你是{context.get('pet_name', '小Q')}，一只可爱的QQ企鹅。
你的性格：温暖、活泼、有点小幽默。
你正在帮主人执行任务。

当你完成技能后，用简短的企鹅语气告诉主人结果。
保持友好、活泼的风格。"""

            response = llm_client.chat(
                [Message(role="user", content=message)],
                system_prompt=system_prompt,
            )

            return AgentMessage(
                type="result",
                task_id="",
                success=True,
                dialogue=response.content,
            )

        except Exception as e:
            return AgentMessage(
                type="error",
                task_id="",
                success=False,
                error=str(e),
                dialogue="唔...出了点小问题呢~",
            )


def run_worker(worker_id: str):
    """Worker进程入口"""
    agent = SubAgent(worker_id)

    # Worker主循环在ProcessPool中通过stdin/stdout通信
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break

            msg = WorkerMessage.from_json(line.strip())

            if msg.type == "shutdown":
                break

            elif msg.type == "task":
                result = agent.execute_task(
                    task_id=msg.task_id,
                    skill_name=msg.skill_name,
                    skill_args=msg.skill_args,
                    context=msg.context,
                )
                # 输出结果到stdout
                print(result.to_json(), flush=True)

            elif msg.type == "ping":
                pong = AgentMessage(
                    type="pong",
                    task_id="",
                    success=True,
                    dialogue=f"[{worker_id}] pong",
                )
                print(pong.to_json(), flush=True)

        except Exception as e:
            error_msg = AgentMessage(
                type="error",
                task_id="",
                success=False,
                error=str(e),
            )
            print(error_msg.to_json(), flush=True)


if __name__ == "__main__":
    worker_id = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    run_worker(worker_id)
