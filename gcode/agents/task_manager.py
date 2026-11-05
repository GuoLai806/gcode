from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from gcode.agent import Agent

log = logging.getLogger(__name__)


@dataclass
class ProgressInfo:
    tool_call_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    last_activity: str = ""


@dataclass
class BackgroundTask:
    id: str
    name: str
    agent: Agent
    task: str
    status: str = "running"
    result: str = ""
    start_time: float = field(default_factory=time.monotonic)
    end_time: float | None = None
    cancel: Callable[[], None] | None = None
    progress: ProgressInfo = field(default_factory=ProgressInfo)
    process_state: str = "unknown"
    stop_reason: str = ""


class TaskManager:
    def __init__(
        self,
        store_path: str | None = None,
        max_concurrent: int | None = 4,
        max_spawns: int = 32,
        max_depth: int = 2,
        heartbeat_interval: float = 5.0,
        scope_id: str | None = None,
    ) -> None:
        from gcode.runtime.store import RunStore

        self._store = RunStore(store_path) if store_path else None
        self._max_concurrent = max_concurrent
        self._max_spawns = max_spawns
        self._max_depth = max_depth
        self._heartbeat_interval = heartbeat_interval
        if (
            max_spawns < 1
            or max_depth < 0
            or heartbeat_interval <= 0
            or (max_concurrent is not None and max_concurrent < 1)
        ):
            raise ValueError("invalid task limits")
        self._scope_id = scope_id or uuid.uuid4().hex
        self._spawned = 0
        self._owner = uuid.uuid4().hex
        self._heartbeats: dict[str, asyncio.Task[None]] = {}
        self._adopted_sources: dict[str, asyncio.Task] = {}
        self._tasks: dict[str, BackgroundTask] = {}
        self._notify_queue: asyncio.Queue[str] = asyncio.Queue()
        self._async_tasks: dict[str, asyncio.Task[None]] = {}

    @property
    def scope_id(self) -> str:
        return self._scope_id

    @scope_id.setter
    def scope_id(self, value: str) -> None:
        if not value:
            raise ValueError("scope_id must be non-empty")
        if value != self._scope_id:
            self._scope_id = value
            self._spawned = 0

    def launch(
        self,
        agent: Agent,
        task: str,
        name: str = "",
        fork_conversation: Any = None,
        idempotency_key: str | None = None,
        depth: int = 0,
        partial_result: str = "",
        conversation_fingerprint: str | None = None,
        budget_reserved: bool = False,
    ) -> str:
        asyncio.get_running_loop()  # Fail before reserving a durable run outside an event loop.
        if (
            fork_conversation is not None
            and idempotency_key
            and not conversation_fingerprint
        ):
            raise ValueError(
                "idempotent fork requires a stable conversation fingerprint"
            )
        spec = {
            "task": task,
            "name": name,
            "depth": depth,
            "partial_result": partial_result,
            "has_fork": fork_conversation is not None,
            "conversation_fingerprint": conversation_fingerprint,
        }
        if depth < 0 or depth > self._max_depth:
            raise RuntimeError("task depth limit reached")
        if (
            self._max_concurrent is not None
            and len(self._async_tasks) >= self._max_concurrent
        ):
            if self._store and idempotency_key:
                existing = self._store.create_or_get(
                    idempotency_key, spec, max_active=0
                )
                if not existing["_created"]:
                    return existing["id"]
            raise RuntimeError("task concurrency limit reached")
        if self._spawned >= self._max_spawns:
            if self._store and idempotency_key:
                existing = self._store.create_or_get(
                    idempotency_key, spec, max_active=0
                )
                if not existing["_created"]:
                    return existing["id"]
            raise RuntimeError("task spawn limit reached")
        if self._store:
            run = self._store.create_or_get(
                idempotency_key or uuid.uuid4().hex,
                spec,
                max_active=self._max_concurrent,
                scope=None if budget_reserved else self.scope_id,
                max_spawns=self._max_spawns,
            )
            task_id = run["id"]
            if not run["_created"]:
                return task_id
            self._store.transition(
                task_id,
                run["revision"],
                {
                    "state": "running",
                    "result": partial_result,
                    "owner": self._owner,
                    "heartbeat": time.time(),
                    "process_state": "unknown",
                },
            )
        else:
            task_id = uuid.uuid4().hex[:8]
        bg = BackgroundTask(
            id=task_id,
            name=name or task_id,
            agent=agent,
            task=task,
            result=partial_result,
        )
        self._spawned += 1
        self._tasks[task_id] = bg

        async_task = asyncio.create_task(
            self._run_background(task_id, fork_conversation)
        )
        self._async_tasks[task_id] = async_task
        if self._store:
            self._heartbeats[task_id] = asyncio.create_task(self._heartbeat(task_id))

        async_task.add_done_callback(lambda done: self._finish_unstarted(task_id, done))
        bg.cancel = lambda: self.cancel(task_id)
        return task_id

    def _finish_unstarted(self, task_id: str, done: asyncio.Task[None]) -> None:
        # A task cancelled before its coroutine first runs cannot execute its finally block.
        if task_id not in self._async_tasks:
            return
        bg = self._tasks[task_id]
        self._async_tasks.pop(task_id, None)
        self._adopted_sources.pop(task_id, None)
        heartbeat = self._heartbeats.pop(task_id, None)
        if heartbeat:
            heartbeat.cancel()
        bg.status = "cancelled" if done.cancelled() else "failed"
        bg.stop_reason = (
            "cancelled_before_start" if done.cancelled() else "runner_failed"
        )
        bg.result = "Task coroutine did not start; external process state is unknown"
        bg.end_time = time.monotonic()
        if self._store:
            run = self._store.get(task_id)
            if run:
                self._store.transition(
                    task_id,
                    run["revision"],
                    {
                        "state": bg.status,
                        "result": bg.result,
                        "stop_reason": bg.stop_reason,
                        "process_state": "unknown",
                    },
                )
        self._notify_queue.put_nowait(task_id)

    async def _heartbeat(self, task_id: str) -> None:
        try:
            while True:
                await asyncio.sleep(self._heartbeat_interval)
                if not self._store.heartbeat(task_id, self._owner):
                    return
        except asyncio.CancelledError:
            return
        except Exception:
            log.exception(
                "Task %s heartbeat failed; execution state is unknown", task_id
            )

    async def _run_background(
        self, task_id: str, fork_conversation: Any = None
    ) -> None:
        bg = self._tasks.get(task_id)
        if bg is None:
            return

        try:
            if fork_conversation is not None:
                result = await bg.agent.run_to_completion("", fork_conversation)
            else:
                result = await bg.agent.run_to_completion(bg.task)
            bg.result = (bg.result + "\n" + result).strip() if bg.result else result
            reason = getattr(bg.agent, "last_stop_reason", "completed")
            bg.status = (
                reason
                if reason
                in (
                    "completed",
                    "limit_reached",
                    "budget_exhausted",
                    "failed",
                    "cancelled",
                )
                else "completed"
            )
            bg.stop_reason = bg.status
            if self._store:
                run = self._store.get(task_id)
                self._store.transition(
                    task_id,
                    run["revision"],
                    {
                        "state": "running"
                        if bg.status == "completed"
                        and bg.agent.team_name
                        and bg.agent._team_manager
                        else bg.status,
                        "result": bg.result,
                        "stop_reason": bg.stop_reason,
                        "process_state": bg.process_state,
                    },
                )

            if (
                bg.status == "completed"
                and bg.agent.team_name
                and bg.agent._team_manager
            ):
                mailbox = bg.agent._team_manager.get_mailbox(bg.agent.team_name)
                if mailbox:
                    bg.status = "idle"
                    if self._store:
                        run = self._store.get(task_id)
                        self._store.transition(
                            task_id,
                            run["revision"],
                            {
                                "state": "idle",
                                "result": bg.result,
                                "stop_reason": "waiting_for_messages",
                                "process_state": "unknown",
                            },
                        )
                    from gcode.teams.mailbox import create_message

                    msg = create_message(
                        from_agent=bg.name,
                        to_agent="lead",
                        content=f"[idle] {bg.name}: completed initial task",
                        summary=f"{bg.name} idle",
                    )
                    mailbox.write("lead", msg)

                    for _ in range(60):
                        await asyncio.sleep(1)
                        # Without durable result storage there is no safe ACK point.
                        if not self._store:
                            break
                        msgs = mailbox.claim(bg.agent.agent_id, task_id)
                        if not msgs:
                            continue
                        bg.status = "running"
                        run = self._store.get(task_id)
                        self._store.transition(
                            task_id,
                            run["revision"],
                            {"state": "running", "result": bg.result},
                        )
                        prompt = "\n\n".join(
                            f"[Message from {m.from_agent}] {m.content}" for m in msgs
                        )
                        result = await bg.agent.run_to_completion(prompt)
                        bg.result = result
                        reason = getattr(bg.agent, "last_stop_reason", "completed")
                        bg.status = (
                            "idle"
                            if reason == "completed"
                            else (
                                reason
                                if reason
                                in (
                                    "limit_reached",
                                    "budget_exhausted",
                                    "failed",
                                    "cancelled",
                                )
                                else "failed"
                            )
                        )
                        bg.stop_reason = (
                            "waiting_for_messages" if bg.status == "idle" else bg.status
                        )
                        run = self._store.get(task_id)
                        self._store.transition(
                            task_id,
                            run["revision"],
                            {
                                "state": bg.status,
                                "result": result,
                                "stop_reason": bg.stop_reason,
                                "process_state": "unknown",
                            },
                        )
                        for received in msgs:
                            mailbox.ack(bg.agent.agent_id, received.id, task_id)
                        if bg.status != "idle":
                            break
                        msg = create_message(
                            from_agent=bg.name,
                            to_agent="lead",
                            content=f"[idle] {bg.name}: completed follow-up",
                            summary=f"{bg.name} idle",
                        )
                        mailbox.write("lead", msg)
                    if bg.status == "idle":
                        bg.status = "completed"
                        bg.stop_reason = "completed"

        except asyncio.CancelledError:
            bg.status = "cancelled"
            bg.stop_reason = "cancelled"
            bg.result = (
                "Task coroutine was cancelled; external process state is unknown"
            )
        except Exception as e:
            log.error("Background task %s failed: %s", task_id, e)
            bg.status = "failed"
            bg.stop_reason = "error"
            bg.result = f"Error: {e}"
        finally:
            bg.end_time = time.monotonic()
            bg.progress.input_tokens = bg.agent.total_input_tokens
            bg.progress.output_tokens = bg.agent.total_output_tokens
            self._async_tasks.pop(task_id, None)
            heartbeat = self._heartbeats.pop(task_id, None)
            if heartbeat:
                heartbeat.cancel()
            if self._store:
                run = self._store.get(task_id)
                if run:
                    self._store.transition(
                        task_id,
                        run["revision"],
                        {
                            "state": bg.status,
                            "result": bg.result,
                            "stop_reason": bg.stop_reason,
                            "process_state": bg.process_state,
                        },
                    )
            await self._notify_queue.put(task_id)

    def adopt_running(
        self,
        agent: Agent | asyncio.Task,
        task_description: str,
        partial_result: str = "",
        name: str = "",
    ) -> str:
        asyncio.get_running_loop()
        if not isinstance(agent, asyncio.Task):
            # Explicit continuation of an Agent is a new run, persisted before dispatch.
            return self.launch(
                agent, task_description, name=name, partial_result=partial_result
            )
        # Observe the already-running coroutine; never invoke a second model/tool run.
        if (
            self._max_concurrent is not None
            and len(self._async_tasks) >= self._max_concurrent
        ):
            raise RuntimeError("task concurrency limit reached")
        if self._spawned >= self._max_spawns:
            raise RuntimeError("task spawn limit reached")
        if self._store:
            run = self._store.create_or_get(
                uuid.uuid4().hex,
                {"task": task_description, "name": name, "adopted": True},
                max_active=self._max_concurrent,
                scope=self.scope_id,
                max_spawns=self._max_spawns,
            )
            task_id = run["id"]
            self._store.transition(
                task_id,
                run["revision"],
                {
                    "state": "running",
                    "result": partial_result,
                    "owner": self._owner,
                    "heartbeat": time.time(),
                    "process_state": "unknown",
                },
            )
        else:
            task_id = uuid.uuid4().hex[:8]
        bg = BackgroundTask(
            id=task_id,
            name=name or task_id,
            agent=None,
            task=task_description,
            result=partial_result,
        )
        self._spawned += 1
        self._tasks[task_id] = bg
        self._adopted_sources[task_id] = agent
        observer = asyncio.create_task(self._observe_existing(task_id, agent))
        self._async_tasks[task_id] = observer
        if self._store:
            self._heartbeats[task_id] = asyncio.create_task(self._heartbeat(task_id))
        observer.add_done_callback(lambda done: self._finish_unstarted(task_id, done))
        bg.cancel = lambda: self.cancel(task_id)
        return task_id

    async def _observe_existing(self, task_id: str, source: asyncio.Task) -> None:
        bg = self._tasks[task_id]
        try:
            result = await source
            text = "" if result is None else str(result)
            bg.result = (bg.result + "\n" + text).strip() if bg.result else text
            bg.status = "completed"
            bg.stop_reason = "completed"
        except asyncio.CancelledError:
            bg.status = "cancelled"
            bg.stop_reason = "cancelled"
            bg.result = (
                "Task coroutine was cancelled; external process state is unknown"
            )
        except Exception as exc:
            bg.status = "failed"
            bg.stop_reason = "error"
            bg.result = f"Error: {exc}"
        finally:
            bg.end_time = time.monotonic()
            self._async_tasks.pop(task_id, None)
            self._adopted_sources.pop(task_id, None)
            heartbeat = self._heartbeats.pop(task_id, None)
            if heartbeat:
                heartbeat.cancel()
            if self._store:
                run = self._store.get(task_id)
                if run:
                    self._store.transition(
                        task_id,
                        run["revision"],
                        {
                            "state": bg.status,
                            "result": bg.result,
                            "stop_reason": bg.stop_reason,
                            "process_state": "unknown",
                        },
                    )
            await self._notify_queue.put(task_id)

    def get(self, task_id: str) -> BackgroundTask | None:
        task = self._tasks.get(task_id)
        if task or not self._store:
            return task
        run = self._store.get(task_id)
        if not run:
            return None
        import json

        spec = json.loads(run["spec"])
        # Running across a restart has unknown execution outcome; never replay it.
        status = (
            "unknown"
            if run["state"] in ("running", "pending", "idle", "cancellation_requested")
            else run["state"]
        )
        return BackgroundTask(
            id=task_id,
            name=spec.get("name") or task_id,
            agent=None,
            task=spec.get("task", ""),
            status=status,
            result=run["result"] or "",
            stop_reason=run.get("stop_reason")
            or ("recovery_unknown" if status == "unknown" else ""),
            process_state=run.get("process_state") or "unknown",
        )

    def list_tasks(self) -> list[BackgroundTask]:
        if not self._store:
            return list(self._tasks.values())
        return [self.get(run["id"]) for run in self._store.list_runs()]

    def cancel(self, task_id: str) -> bool:
        bg = self._tasks.get(task_id)
        if bg is None or bg.status not in ("running", "idle"):
            return False
        async_task = self._async_tasks.get(task_id)
        if async_task and not async_task.done():
            bg.status = "cancellation_requested"
            bg.stop_reason = "cancellation_requested"
            if self._store:
                run = self._store.get(task_id)
                self._store.transition(
                    task_id,
                    run["revision"],
                    {
                        "state": "cancellation_requested",
                        "result": bg.result,
                        "stop_reason": bg.stop_reason,
                        "process_state": "unknown",
                    },
                )
            source = self._adopted_sources.get(task_id)
            if source and not source.done():
                source.cancel()
            async_task.cancel()
            return True
        return False

    def poll_completed(self) -> list[BackgroundTask]:
        completed: list[BackgroundTask] = []
        while not self._notify_queue.empty():
            try:
                task_id = self._notify_queue.get_nowait()
                bg = self._tasks.get(task_id)
                if bg is not None:
                    completed.append(bg)
            except asyncio.QueueEmpty:
                break
        return completed
