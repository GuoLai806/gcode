import pytest
from gcode.runtime.store import RunStore, ConflictError


def test_idempotency_cas_and_lease(tmp_path):
    s = RunStore(tmp_path / "state.db")
    a = s.create_or_get("key", {"prompt": "x"})
    assert s.create_or_get("key", {"prompt": "x"})["id"] == a["id"]
    with pytest.raises(ConflictError):
        s.create_or_get("key", {"prompt": "y"})
    b = s.transition(a["id"], 0, {"state": "running"})
    with pytest.raises(ConflictError):
        s.transition(a["id"], 0, {"state": "completed"})
    assert b["revision"] == 1
    assert s.acquire_lease("desktop", "a", 30)
    assert not s.acquire_lease("desktop", "b", 30)
    assert not s.release_lease("desktop", "b")
    assert s.release_lease("desktop", "a")


@pytest.mark.asyncio
async def test_taskmanager_idempotency_and_restart_no_replay(tmp_path):
    import asyncio
    from gcode.agents.task_manager import TaskManager

    class Agent:
        team_name = ""
        total_input_tokens = 0
        total_output_tokens = 0
        calls = 0

        async def run_to_completion(self, task):
            self.calls += 1
            return "done"

    agent = Agent()
    path = str(tmp_path / "runs.db")
    manager = TaskManager(path)
    first = manager.launch(agent, "task", idempotency_key="same")
    assert manager.launch(agent, "task", idempotency_key="same") == first
    await asyncio.gather(*list(manager._async_tasks.values()))
    recovered = TaskManager(path)
    assert recovered.get(first).status == "completed"
    assert recovered.get(first).result == "done"
    assert recovered.launch(agent, "task", idempotency_key="same") == first
    assert agent.calls == 1


@pytest.mark.asyncio
async def test_cancel_before_start_is_durable_and_unknown_process(tmp_path):
    import asyncio
    from gcode.agents.task_manager import TaskManager

    class Agent:
        total_input_tokens = 0
        total_output_tokens = 0

        async def run_to_completion(self, task):
            raise AssertionError("must not start")

    path = str(tmp_path / "state.db")
    manager = TaskManager(path)
    task_id = manager.launch(Agent(), "task")
    assert manager.cancel(task_id)
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    recovered = TaskManager(path).get(task_id)
    assert recovered.status == "cancelled"
    assert recovered.stop_reason == "cancelled_before_start"
    assert recovered.process_state == "unknown"


@pytest.mark.asyncio
async def test_limits_and_heartbeat(tmp_path):
    import asyncio
    from gcode.agents.task_manager import TaskManager

    class Agent:
        team_name = ""
        total_input_tokens = 0
        total_output_tokens = 0

        async def run_to_completion(self, task):
            await gate.wait()
            return "ok"

    gate = asyncio.Event()
    path = str(tmp_path / "state.db")
    manager = TaskManager(path, max_concurrent=1, max_depth=1, heartbeat_interval=0.01)
    task = manager.launch(Agent(), "one", idempotency_key="one", depth=1)
    assert manager.launch(Agent(), "one", idempotency_key="one", depth=1) == task
    with pytest.raises(RuntimeError):
        manager.launch(Agent(), "two")
    with pytest.raises(RuntimeError):
        manager.launch(Agent(), "deep", depth=2)
    first = manager._store.get(task)["heartbeat"]
    await asyncio.sleep(0.05)
    assert manager._store.get(task)["heartbeat"] > first
    gate.set()
    await asyncio.gather(*list(manager._async_tasks.values()))


def _reserve_slot(path, key, gate, output):
    from gcode.runtime.store import RunStore

    store = RunStore(path)
    gate.wait()
    try:
        store.create_or_get(key, {"key": key}, max_active=1)
        output.put("created")
    except RuntimeError:
        output.put("limited")


def test_cross_process_capacity_atomic(tmp_path):
    import multiprocessing

    path = str(tmp_path / "capacity.db")
    RunStore(path)
    gate = multiprocessing.Event()
    output = multiprocessing.Queue()
    children = [
        multiprocessing.Process(target=_reserve_slot, args=(path, str(i), gate, output))
        for i in range(2)
    ]
    for child in children:
        child.start()
    gate.set()
    for child in children:
        child.join(20)
        assert child.exitcode == 0
    assert sorted(output.get(timeout=2) for _ in children) == ["created", "limited"]


@pytest.mark.asyncio
async def test_running_record_is_unknown_and_never_replayed(tmp_path):
    import asyncio
    from gcode.agents.task_manager import TaskManager

    class Agent:
        team_name = ""
        total_input_tokens = 0
        total_output_tokens = 0
        calls = 0

        async def run_to_completion(self, task):
            self.calls += 1
            await gate.wait()
            return "done"

    gate = asyncio.Event()
    path = str(tmp_path / "runs.db")
    agent = Agent()
    first = TaskManager(path, max_concurrent=1)
    run = first.launch(agent, "request", idempotency_key="x")
    await asyncio.sleep(0)
    other = TaskManager(path, max_concurrent=1)
    assert other.get(run).status == "unknown"
    assert other.launch(agent, "request", idempotency_key="x") == run
    with pytest.raises(RuntimeError):
        other.launch(agent, "another")
    assert agent.calls == 1
    gate.set()
    await asyncio.gather(*list(first._async_tasks.values()))


def test_spawn_scope_persists_and_is_transactional(tmp_path):
    s = RunStore(tmp_path / "scope.db")
    first = s.create_or_get("one", {"x": 1}, scope="session", max_spawns=1)
    assert not s.create_or_get("one", {"x": 1}, scope="session", max_spawns=1)[
        "_created"
    ]
    with pytest.raises(RuntimeError):
        RunStore(tmp_path / "scope.db").create_or_get(
            "two", {"x": 2}, scope="session", max_spawns=1
        )
    assert first["_created"]


def test_completion_requires_persistent_result(tmp_path):
    s = RunStore(tmp_path / "completion.db")
    run = s.create_or_get("key", {})
    with pytest.raises(ValueError):
        s.transition(run["id"], 0, {"state": "completed"})
    assert s.get(run["id"])["state"] == "pending"
    completed = s.transition(run["id"], 0, {"state": "completed", "result": ""})
    assert completed["result"] == ""


@pytest.mark.asyncio
async def test_adopt_existing_coroutine_does_not_replay(tmp_path):
    import asyncio
    from gcode.agents.task_manager import TaskManager

    gate = asyncio.Event()
    calls = []

    async def source():
        calls.append(1)
        await gate.wait()
        return "finished"

    existing = asyncio.create_task(source())
    await asyncio.sleep(0)
    manager = TaskManager(str(tmp_path / "adopt.db"))
    task_id = manager.adopt_running(existing, "existing task", partial_result="prefix")
    gate.set()
    await asyncio.gather(*list(manager._async_tasks.values()))
    assert calls == [1]
    recovered = TaskManager(str(tmp_path / "adopt.db")).get(task_id)
    assert recovered.status == "completed" and recovered.result == "prefix\nfinished"


@pytest.mark.asyncio
async def test_idempotent_fork_requires_conversation_identity(tmp_path):
    from gcode.agents.task_manager import TaskManager

    manager = TaskManager(str(tmp_path / "state.db"))
    with pytest.raises(ValueError):
        manager.launch(
            object(), "fork", fork_conversation=object(), idempotency_key="key"
        )
    assert manager._store.list_runs() == []


@pytest.mark.asyncio
async def test_manager_spawn_budget_survives_restart_in_same_scope(tmp_path):
    import asyncio
    from gcode.agents.task_manager import TaskManager

    class Agent:
        team_name = ""
        total_input_tokens = 0
        total_output_tokens = 0

        async def run_to_completion(self, task):
            return "done"

    path = str(tmp_path / "tasks.db")
    first = TaskManager(path, max_spawns=1, scope_id="parent")
    first.launch(Agent(), "one")
    await asyncio.gather(*list(first._async_tasks.values()))
    restarted = TaskManager(path, max_spawns=1, scope_id="parent")
    with pytest.raises(RuntimeError):
        restarted.launch(Agent(), "two")


@pytest.mark.asyncio
async def test_new_session_scope_gets_its_own_spawn_budget(tmp_path):
    import asyncio
    from gcode.agents.task_manager import TaskManager

    class Agent:
        team_name = ""
        total_input_tokens = total_output_tokens = 0

        async def run_to_completion(self, task):
            return "done"

    manager = TaskManager(str(tmp_path / "tasks.db"), max_spawns=1, scope_id="first")
    manager.launch(Agent(), "one")
    await asyncio.gather(*list(manager._async_tasks.values()))
    manager.scope_id = "second"
    manager.launch(Agent(), "two")
    await asyncio.gather(*list(manager._async_tasks.values()))
    manager.scope_id = "first"
    with pytest.raises(RuntimeError):
        manager.launch(Agent(), "three")


@pytest.mark.asyncio
async def test_budget_exhausted_is_not_completed(tmp_path):
    import asyncio
    from gcode.agents.task_manager import TaskManager

    class Agent:
        team_name = ""
        total_input_tokens = total_output_tokens = 0
        last_stop_reason = "budget_exhausted"

        async def run_to_completion(self, task):
            return "partial"

    manager = TaskManager(str(tmp_path / "tasks.db"))
    task = manager.launch(Agent(), "x")
    await asyncio.gather(*list(manager._async_tasks.values()))
    assert manager.get(task).status == "budget_exhausted"
    assert (
        TaskManager(str(tmp_path / "tasks.db")).get(task).stop_reason
        == "budget_exhausted"
    )
