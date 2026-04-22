"""
IPC消息协议定义
主进程 ↔ Worker进程之间通过JSON over stdin/stdout通信
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
from enum import Enum


class TaskType(str, Enum):
    """任务类型"""
    TASK = "task"
    CANCEL = "cancel"
    SHUTDOWN = "shutdown"
    PING = "ping"


class MessageType(str, Enum):
    """消息类型"""
    RESULT = "result"
    ERROR = "error"
    PROGRESS = "progress"
    PONG = "pong"


@dataclass
class WorkerMessage:
    """主进程 → Worker的消息"""
    type: str  # task | cancel | shutdown | ping
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    skill_name: str = ""
    skill_args: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, data: str) -> "WorkerMessage":
        d = json.loads(data)
        return cls(**d)


@dataclass
class AgentMessage:
    """Worker → 主进程的消息"""
    type: str  # result | error | progress | pong
    task_id: str
    success: bool = True
    data: Dict[str, Any] = field(default_factory=dict)
    dialogue: str = ""  # 角色化输出
    error: Optional[str] = None
    progress: Optional[int] = None  # 0-100

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, data: str) -> "AgentMessage":
        d = json.loads(data)
        return cls(**d)


@dataclass
class SkillExecResult:
    """技能执行结果（供MasterAgent聚合用）"""
    task_id: str
    skill_name: str
    success: bool
    result_data: Dict[str, Any]
    persona_dialogue: str
    raw_output: str
    error: Optional[str] = None