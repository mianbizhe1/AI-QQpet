"""
定时任务调度器
基于APScheduler的Cron调度器
"""

import uuid
import threading
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.jobstores.memory import MemoryJobStore
    from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScheduledTask:
    """定时任务定义"""
    id: str
    name: str
    cron: str  # 5字段cron表达式
    skill_name: str
    skill_args: Dict[str, Any]
    context: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    status: TaskStatus = TaskStatus.PENDING
    next_run: Optional[datetime] = None
    last_run: Optional[datetime] = None
    last_result: Optional[str] = None
    run_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "cron": self.cron,
            "skill_name": self.skill_name,
            "skill_args": self.skill_args,
            "context": self.context,
            "enabled": self.enabled,
            "status": self.status.value,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "last_result": self.last_result,
            "run_count": self.run_count,
            "created_at": self.created_at.isoformat(),
        }


class TaskScheduler:
    """定时任务调度器"""

    # 类级别的待显示通知列表（跨实例共享）
    _pending_notifications: List[Dict[str, Any]] = []
    _notifications_lock = threading.Lock()

    def __init__(
        self,
        db_path: Optional[str] = None,
        process_pool=None,
    ):
        """
        Args:
            db_path: SQLite数据库路径（持久化任务用）
            process_pool: 进程池实例（用于执行技能）
        """
        if not APSCHEDULER_AVAILABLE:
            print("[TaskScheduler] APScheduler不可用，请安装: pip install apscheduler")

        self.db_path = db_path or ":memory:"
        self.process_pool = process_pool
        self._scheduler: Optional[BackgroundScheduler] = None
        self._tasks: Dict[str, ScheduledTask] = {}
        self._lock = threading.Lock()
        self._persist_conn: Optional[sqlite3.Connection] = None

        # 初始化调度器
        if APSCHEDULER_AVAILABLE:
            self._init_scheduler()
            self._init_db()
            self._load_tasks()

    def _init_scheduler(self):
        """初始化APScheduler"""
        jobstores = {
            'default': MemoryJobStore(),
        }
        job_defaults = {
            'coalesce': False,
            'max_instances': 1,
            'misfire_grace_time': 60,
        }

        # 使用固定的时区（避免tzdata依赖问题）
        # APScheduler 需要 IANA 时区格式
        self._scheduler = BackgroundScheduler(
            jobstores=jobstores,
            job_defaults=job_defaults,
            timezone='Asia/Shanghai',  # 中国时区
        )

        # 注册事件监听
        self._scheduler.add_listener(
            self._on_job_executed,
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR,
        )

        # 启动调度器
        self._scheduler.start()
        print("[TaskScheduler] APScheduler已启动")

    def _init_db(self):
        """初始化SQLite数据库"""
        try:
            self._persist_conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._persist_conn.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_tasks (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    cron TEXT NOT NULL,
                    skill_name TEXT NOT NULL,
                    skill_args TEXT NOT NULL,
                    context TEXT NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'pending',
                    last_run TEXT,
                    last_result TEXT,
                    run_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """)
            self._persist_conn.commit()
        except Exception as e:
            print(f"[TaskScheduler] 数据库初始化失败: {e}")
            self._persist_conn = None

    def _load_tasks(self):
        """从数据库加载任务"""
        if not self._persist_conn:
            return

        try:
            cursor = self._persist_conn.execute(
                "SELECT * FROM scheduled_tasks"
            )
            for row in cursor.fetchall():
                task = ScheduledTask(
                    id=row[0],
                    name=row[1],
                    cron=row[2],
                    skill_name=row[3],
                    skill_args=eval(row[4]),
                    context=eval(row[5]),
                    enabled=bool(row[6]),
                    status=TaskStatus(row[7]),
                    last_run=datetime.fromisoformat(row[8]) if row[8] else None,
                    last_result=row[9],
                    run_count=row[10],
                    created_at=datetime.fromisoformat(row[11]),
                )
                self._tasks[task.id] = task

                # 添加到调度器
                if task.enabled and APSCHEDULER_AVAILABLE:
                    self._add_to_apscheduler(task)

            print(f"[TaskScheduler] 从数据库加载了 {len(self._tasks)} 个任务")
        except Exception as e:
            print(f"[TaskScheduler] 加载任务失败: {e}")

    def add_task(
        self,
        name: str,
        cron_expr: str,
        skill_name: str,
        skill_args: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ScheduledTask:
        """
        添加定时任务

        Args:
            name: 任务名称
            cron_expr: Cron表达式（5字段，标准格式）
            skill_name: 技能名称
            skill_args: 技能参数
            context: 执行上下文

        Returns:
            ScheduledTask: 创建的任务
        """
        task_id = str(uuid.uuid4())
        task = ScheduledTask(
            id=task_id,
            name=name,
            cron=cron_expr,
            skill_name=skill_name,
            skill_args=skill_args or {},
            context=context or {},
        )

        with self._lock:
            self._tasks[task_id] = task
            self._save_task(task)

            if task.enabled and APSCHEDULER_AVAILABLE:
                self._add_to_apscheduler(task)

        print(f"[TaskScheduler] 添加任务: {name} ({cron_expr})")
        return task

    def _add_to_apscheduler(self, task: ScheduledTask):
        """将任务添加到APScheduler"""
        if not self._scheduler:
            return

        try:
            # 解析cron表达式
            fields = task.cron.split()
            if len(fields) == 5:
                trigger = CronTrigger(
                    minute=fields[0],
                    hour=fields[1],
                    day=fields[2],
                    month=fields[3],
                    day_of_week=fields[4],
                )
            else:
                print(f"[TaskScheduler] 无效的cron表达式: {task.cron}")
                return

            self._scheduler.add_job(
                func=self._execute_task_wrapper,
                trigger=trigger,
                id=task.id,
                args=[task.id],
                replace_existing=True,
            )

            # 获取下次执行时间
            job = self._scheduler.get_job(task.id)
            if job:
                task.next_run = job.next_run_time

        except Exception as e:
            print(f"[TaskScheduler] 添加到APScheduler失败: {e}")

    def _execute_task_wrapper(self, task_id: str):
        """任务执行包装器"""
        task = self._tasks.get(task_id)
        if not task:
            return

        task.status = TaskStatus.RUNNING
        task.last_run = datetime.now()

        try:
            if self.process_pool:
                # 提交到进程池执行
                self.process_pool.submit_task(
                    skill_name=task.skill_name,
                    skill_args=task.skill_args,
                    context=task.context,
                    callback=lambda r: self._on_task_result(task_id, r),
                )
            else:
                # 直接执行
                from .skill_registry import SkillRegistry
                registry = SkillRegistry()
                result = registry.execute(task.skill_name, task.skill_args)

                # 添加到待显示通知
                self.add_pending_notification(
                    task_name=task.name,
                    result=result.content,
                    skill_name=task.skill_name,
                )

                task.last_result = result.content if result.success else result.error

            task.run_count += 1
            task.status = TaskStatus.COMPLETED

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.last_result = str(e)
            print(f"[TaskScheduler] 任务执行失败: {e}")

        self._save_task(task)

    def _on_task_result(self, task_id: str, result):
        """任务结果回调"""
        task = self._tasks.get(task_id)
        if not task:
            return

        if result.success:
            result_content = result.dialogue or result.content

            # 添加到待显示通知
            self.add_pending_notification(
                task_name=task.name,
                result=result_content,
                skill_name=task.skill_name,
            )

            task.last_result = result_content
            task.status = TaskStatus.COMPLETED
        else:
            task.last_result = result.error
            task.status = TaskStatus.FAILED

        self._save_task(task)

    def _on_job_executed(self, event):
        """APScheduler任务执行完成回调"""
        if event.exception:
            print(f"[TaskScheduler] 任务 {event.job_id} 执行出错: {event.exception}")

    def _save_task(self, task: ScheduledTask):
        """保存任务到数据库"""
        if not self._persist_conn:
            return

        try:
            self._persist_conn.execute("""
                INSERT OR REPLACE INTO scheduled_tasks
                (id, name, cron, skill_name, skill_args, context, enabled, status,
                 last_run, last_result, run_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.id,
                task.name,
                task.cron,
                task.skill_name,
                str(task.skill_args),
                str(task.context),
                int(task.enabled),
                task.status.value,
                task.last_run.isoformat() if task.last_run else None,
                task.last_result,
                task.run_count,
                task.created_at.isoformat(),
            ))
            self._persist_conn.commit()
        except Exception as e:
            print(f"[TaskScheduler] 保存任务失败: {e}")

    def remove_task(self, task_id: str) -> bool:
        """
        删除任务

        Returns:
            bool: 是否成功删除
        """
        with self._lock:
            if task_id not in self._tasks:
                return False

            task = self._tasks[task_id]
            task.status = TaskStatus.CANCELLED

            # 从APScheduler移除
            if self._scheduler and self._scheduler.get_job(task_id):
                self._scheduler.remove_job(task_id)

            # 从数据库删除
            if self._persist_conn:
                self._persist_conn.execute(
                    "DELETE FROM scheduled_tasks WHERE id = ?",
                    (task_id,),
                )
                self._persist_conn.commit()

            del self._tasks[task_id]
            print(f"[TaskScheduler] 删除任务: {task.name}")
            return True

    def enable_task(self, task_id: str, enabled: bool = True) -> bool:
        """
        启用/禁用任务

        Returns:
            bool: 是否成功
        """
        with self._lock:
            if task_id not in self._tasks:
                return False

            task = self._tasks[task_id]
            task.enabled = enabled

            if enabled:
                task.status = TaskStatus.PENDING
                self._add_to_apscheduler(task)
            else:
                if self._scheduler and self._scheduler.get_job(task_id):
                    self._scheduler.remove_job(task_id)
                task.next_run = None

            self._save_task(task)
            return True

    def list_tasks(self) -> List[Dict[str, Any]]:
        """列出所有任务"""
        return [task.to_dict() for task in self._tasks.values()]

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取单个任务"""
        task = self._tasks.get(task_id)
        return task.to_dict() if task else None

    def get_next_run_times(self, num: int = 5) -> List[Dict[str, Any]]:
        """获取接下来几次执行时间"""
        if not self._scheduler:
            return []

        jobs = self._scheduler.get_jobs()
        results = []

        for job in jobs:
            if job.next_run_time:
                results.append({
                    "job_id": job.id,
                    "task_name": self._tasks[job.id].name if job.id in self._tasks else "unknown",
                    "next_run": job.next_run_time.isoformat(),
                })

        # 按时间排序
        results.sort(key=lambda x: x["next_run"])
        return results[:num]

    # ==================== 待显示通知 ====================

    @classmethod
    def add_pending_notification(cls, task_name: str, result: str, skill_name: str):
        """
        添加待显示的通知（定时任务执行后会调用这个）

        Args:
            task_name: 任务名称
            result: 执行结果
            skill_name: 技能名称
        """
        with cls._notifications_lock:
            notification = {
                "task_name": task_name,
                "result": result,
                "skill_name": skill_name,
                "timestamp": datetime.now().isoformat(),
            }
            # 最多保留5条通知
            if len(cls._pending_notifications) >= 5:
                cls._pending_notifications.pop(0)
            cls._pending_notifications.append(notification)
            print(f"[TaskScheduler] 添加待显示通知: {task_name}")

    @classmethod
    def get_pending_notifications(cls) -> List[Dict[str, Any]]:
        """获取所有待显示的通知"""
        with cls._notifications_lock:
            return list(cls._pending_notifications)

    @classmethod
    def clear_pending_notifications(cls):
        """清空待显示通知"""
        with cls._notifications_lock:
            cls._pending_notifications.clear()

    def shutdown(self):
        """关闭调度器"""
        if self._scheduler:
            self._scheduler.shutdown()
        if self._persist_conn:
            self._persist_conn.close()
        print("[TaskScheduler] 调度器已关闭")
