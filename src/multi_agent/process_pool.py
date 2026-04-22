"""
进程池管理器
管理多个Worker进程执行技能任务
"""

import multiprocessing as mp
import json
import time
import uuid
import threading
import queue
from concurrent.futures import ProcessPoolExecutor, Future
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass, field

from .ipc_protocol import WorkerMessage, AgentMessage


@dataclass
class WorkerState:
    """Worker状态"""
    worker_id: str
    process: Optional[mp.Process] = None
    conn: Optional[Any] = None
    is_busy: bool = False
    current_task_id: Optional[str] = None
    last_heartbeat: float = field(default_factory=time.time)
    task_queue: queue.Queue = field(default_factory=queue.Queue)


class ProcessPool:
    """进程池管理器"""

    def __init__(
        self,
        max_workers: int = 4,
        heartbeat_interval: float = 5.0,
        max_missed_heartbeats: int = 3,
        task_timeout: float = 30.0,
    ):
        self.max_workers = max_workers
        self.heartbeat_interval = heartbeat_interval
        self.max_missed_heartbeats = max_missed_heartbeats
        self.task_timeout = task_timeout

        self._workers: Dict[str, WorkerState] = {}
        self._task_callbacks: Dict[str, Callable] = {}
        self._pending_tasks: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self._shutdown = False

        # 启动Worker进程
        self._spawn_workers()

        # 启动心跳检测线程
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def _spawn_workers(self):
        """Spawn Worker进程"""
        for i in range(self.max_workers):
            worker_id = f"worker-{i}"
            self._spawn_single_worker(worker_id)

    def _spawn_single_worker(self, worker_id: str):
        """Spawn单个Worker"""
        # 创建管道
        parent_conn, child_conn = mp.Pipe()

        # 启动子进程
        p = mp.Process(
            target=self._worker_main,
            args=(worker_id, child_conn),
            daemon=True,
        )
        p.start()

        state = WorkerState(
            worker_id=worker_id,
            process=p,
            conn=parent_conn,
        )
        self._workers[worker_id] = state
        print(f"[ProcessPool] 启动 {worker_id}, pid={p.pid}")

    @staticmethod
    def _worker_main(worker_id: str, conn):
        """Worker进程主循环"""
        from .sub_agent import SubAgent

        agent = SubAgent(worker_id)
        print(f"[{worker_id}] Worker started")

        while True:
            try:
                # 等待消息（设置超时以便检测shutdown）
                if conn.poll(timeout=1.0):
                    msg = conn.recv()
                    if isinstance(msg, str):
                        worker_msg = WorkerMessage.from_json(msg)
                    else:
                        worker_msg = msg

                    if worker_msg.type == "shutdown":
                        print(f"[{worker_id}] Shutting down")
                        break

                    elif worker_msg.type == "ping":
                        pong = AgentMessage(
                            type="pong",
                            task_id="",
                            success=True,
                            dialogue=f"[{worker_id}] pong",
                        )
                        conn.send(pong.to_json() if isinstance(pong, AgentMessage) else pong)

                    elif worker_msg.type == "task":
                        print(f"[{worker_id}] Received task {worker_msg.task_id}: {worker_msg.skill_name}")
                        result = agent.execute_task(
                            task_id=worker_msg.task_id,
                            skill_name=worker_msg.skill_name,
                            skill_args=worker_msg.skill_args,
                            context=worker_msg.context,
                        )
                        conn.send(result.to_json() if isinstance(result, AgentMessage) else result)

            except Exception as e:
                print(f"[{worker_id}] Error: {e}")
                # 发送错误消息
                error_msg = AgentMessage(
                    type="error",
                    task_id="",
                    success=False,
                    error=str(e),
                )
                try:
                    conn.send(error_msg.to_json())
                except:
                    pass

        print(f"[{worker_id}] Worker exited")

    def submit_task(
        self,
        skill_name: str,
        skill_args: Dict[str, Any],
        context: Dict[str, Any],
        callback: Optional[Callable[[AgentMessage], None]] = None,
    ) -> str:
        """
        提交任务到进程池（同步等待结果）

        Returns:
            task_id: 任务ID
        """
        task_id = str(uuid.uuid4())

        # 找到空闲Worker
        worker = self._get_idle_worker()
        if not worker:
            # 如果没有空闲Worker，排队等待
            print(f"[ProcessPool] 没有空闲Worker，任务 {task_id} 进入等待队列")
            event = threading.Event()
            self._pending_tasks.put((task_id, skill_name, skill_args, context, callback, event))
            event.wait(timeout=self.task_timeout)
            return task_id

        # 发送任务
        worker.is_busy = True
        worker.current_task_id = task_id

        msg = WorkerMessage(
            type="task",
            task_id=task_id,
            skill_name=skill_name,
            skill_args=skill_args,
            context=context,
        )

        try:
            worker.conn.send(msg.to_json())
            # 等待结果
            if worker.conn.poll(timeout=self.task_timeout):
                result = worker.conn.recv()
                if callback:
                    if isinstance(result, str):
                        callback(AgentMessage.from_json(result))
                    else:
                        callback(result)
            else:
                print(f"[ProcessPool] 任务 {task_id} 超时")
                if callback:
                    callback(AgentMessage(
                        type="error",
                        task_id=task_id,
                        success=False,
                        error="任务超时",
                    ))
        except Exception as e:
            print(f"[ProcessPool] 任务 {task_id} 执行失败: {e}")
            if callback:
                callback(AgentMessage(
                    type="error",
                    task_id=task_id,
                    success=False,
                    error=str(e),
                ))
        finally:
            worker.is_busy = False
            worker.current_task_id = None

        return task_id

    def submit_task_async(
        self,
        skill_name: str,
        skill_args: Dict[str, Any],
        context: Dict[str, Any],
        callback: Optional[Callable[[AgentMessage], None]] = None,
    ) -> str:
        """
        异步提交任务到进程池

        Returns:
            task_id: 任务ID
        """
        task_id = str(uuid.uuid4())

        def run_async():
            self.submit_task(skill_name, skill_args, context, callback)

        thread = threading.Thread(target=run_async, daemon=True)
        thread.start()
        return task_id

    def _get_idle_worker(self) -> Optional[WorkerState]:
        """获取空闲Worker"""
        with self._lock:
            for worker in self._workers.values():
                if not worker.is_busy and worker.process and worker.process.is_alive():
                    return worker
        return None

    def _heartbeat_loop(self):
        """心跳检测循环"""
        while not self._shutdown:
            time.sleep(self.heartbeat_interval)
            self._check_heartbeats()

    def _check_heartbeats(self):
        """检查所有Worker的心跳"""
        current_time = time.time()
        for worker_id, worker in list(self._workers.items()):
            if worker.process and not worker.process.is_alive():
                print(f"[ProcessPool] {worker_id} 已退出，重启中...")
                self._respawn_worker(worker_id)

            elapsed = current_time - worker.last_heartbeat
            if elapsed > self.heartbeat_interval * self.max_missed_heartbeats and worker.is_busy:
                print(f"[ProcessPool] {worker_id} 心跳超时，重启中...")
                self._respawn_worker(worker_id)

    def _respawn_worker(self, worker_id: str):
        """重启Worker"""
        with self._lock:
            # 清理旧Worker
            if worker_id in self._workers:
                worker = self._workers[worker_id]
                try:
                    if worker.conn:
                        worker.conn.close()
                except:
                    pass
                try:
                    if worker.process and worker.process.is_alive():
                        worker.process.terminate()
                        worker.process.join(timeout=1)
                except:
                    pass
                del self._workers[worker_id]

            # 启动新Worker
            self._spawn_single_worker(worker_id)

    def get_status(self) -> Dict[str, Any]:
        """获取进程池状态"""
        total = len(self._workers)
        busy = sum(1 for w in self._workers.values() if w.is_busy)
        alive = sum(1 for w in self._workers.values() if w.process and w.process.is_alive())

        return {
            "total": total,
            "busy": busy,
            "ready": alive,
            "pending": self._pending_tasks.qsize(),
        }

    def shutdown(self, timeout: float = 5.0):
        """关闭进程池"""
        self._shutdown = True

        # 发送shutdown信号
        for worker in self._workers.values():
            try:
                msg = WorkerMessage(type="shutdown")
                worker.conn.send(msg.to_json() if isinstance(msg, WorkerMessage) else msg)
            except:
                pass

        # 等待进程结束
        time.sleep(0.5)
        for worker in self._workers.values():
            try:
                if worker.process and worker.process.is_alive():
                    worker.process.terminate()
                    worker.process.join(timeout=timeout)
            except:
                pass

        self._workers.clear()
        print("[ProcessPool] 进程池已关闭")
