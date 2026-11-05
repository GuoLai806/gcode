import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
from gcode.agent import Agent
from gcode.agents.parser import AgentDef
from gcode.agents.task_manager import TaskManager
from gcode.agents.trace import TraceManager
from gcode.tools import ToolRegistry
from gcode.tools.agent_tool import AgentTool, AgentToolParams
from gcode.teams.models import BackendType


class Loader:
    def get(self, name):
        return (
            AgentDef(agent_type=name, when_to_use="test", max_turns=30)
            if name == "worker"
            else None
        )

    def list_agents(self):
        return [("worker", "")]


class TreeManager:
    def __init__(self, path):
        self.path = str(path)
        self.calls = 0

    async def create(self, name, base):
        self.calls += 1
        return SimpleNamespace(path=self.path, head_commit="base")

    async def auto_cleanup(self, name, head):
        return SimpleNamespace(kept=True, path=self.path, branch="branch")


def build(tmp_path, **kwargs):
    checker = MagicMock()
    parent = Agent(
        MagicMock(),
        ToolRegistry(),
        "anthropic",
        work_dir=str(tmp_path),
        max_iterations=3,
        permission_checker=checker,
    )
    inherited = MagicMock()
    parent.permission_ceilings = [inherited]
    manager = TaskManager(str(tmp_path / "runs.db"), scope_id="parent", **kwargs)
    trace = TraceManager()
    tree = TreeManager(tmp_path / "tree")
    tool = AgentTool(Loader(), manager, trace, parent, worktree_manager=tree)
    return tool, parent, manager, trace, tree, inherited, checker


@pytest.mark.asyncio
async def test_foreground_and_worktree_inherit_permission_and_budget(
    tmp_path, monkeypatch
):
    seen = []

    async def run(self, prompt, *args, **kwargs):
        seen.append(self)
        self.last_stop_reason = "completed"
        return "ok"

    monkeypatch.setattr(Agent, "run_to_completion", run)
    tool, parent, manager, trace, tree, inherited, checker = build(tmp_path)
    for isolation in (None, "worktree"):
        result = await tool.execute(
            AgentToolParams(
                prompt="do",
                description="d",
                subagent_type="worker",
                isolation=isolation,
            )
        )
        assert not result.is_error
    assert seen[0].permission_ceilings == [inherited, checker]
    assert seen[1].permission_ceilings == [inherited, checker]
    from gcode.permissions.checker import Decision

    inherited.check.return_value = Decision("allow", "ancestor allows")
    checker.check.return_value = Decision("deny", "parent denies")
    read_tool = SimpleNamespace(name="ReadFile", category="read")
    assert (
        seen[0]
        ._permission_decision(read_tool, {"file_path": str(tmp_path / "f")})
        .effect
        == "deny"
    )
    assert seen[0].max_iterations == seen[1].max_iterations == 3
    assert seen[0]._spawn_budget is seen[1]._spawn_budget and seen[1]._spawn_depth == 1
    assert tree.calls == 1 and seen[1].work_dir == tree.path


@pytest.mark.asyncio
async def test_isolation_and_pane_fail_closed_before_worktree(tmp_path):
    tool, parent, manager, trace, tree, _, _ = build(tmp_path)
    assert (
        await tool.execute(
            AgentToolParams(prompt="x", description="d", isolation="bogus")
        )
    ).is_error
    fake = MagicMock()
    fake.get_team.return_value = SimpleNamespace(members=[])
    fake.detect_backend.return_value = BackendType.TMUX
    tool._team_manager = fake
    result = await tool.execute(
        AgentToolParams(
            prompt="x", description="d", team_name="team", subagent_type="worker"
        )
    )
    assert result.is_error and tree.calls == 0


@pytest.mark.asyncio
async def test_limits_foreground_background_and_stop_reason(tmp_path, monkeypatch):
    gate = asyncio.Event()
    children = []

    async def run(self, prompt, *args, **kwargs):
        children.append(self)
        await gate.wait()
        self.last_stop_reason = "limit_reached"
        return "partial"

    monkeypatch.setattr(Agent, "run_to_completion", run)
    tool, parent, manager, trace, tree, _, _ = build(
        tmp_path, max_concurrent=1, max_spawns=2, max_depth=1
    )
    first = await tool.execute(
        AgentToolParams(
            prompt="x", description="d", subagent_type="worker", run_in_background=True
        )
    )
    assert not first.is_error
    await asyncio.sleep(0)
    rejected = await tool.execute(
        AgentToolParams(prompt="y", description="d", subagent_type="worker")
    )
    assert rejected.is_error and "concurrency" in rejected.output
    gate.set()
    await asyncio.gather(*list(manager._async_tasks.values()))
    await asyncio.sleep(0)
    assert manager.list_tasks()[0].status == "limit_reached"
    child = children[0]
    assert child._spawn_depth == 1
    nested = AgentTool(Loader(), manager, trace, child)
    assert (
        await nested.execute(
            AgentToolParams(prompt="x", description="d", subagent_type="worker")
        )
    ).is_error
    second = await tool.execute(
        AgentToolParams(prompt="z", description="d", subagent_type="worker")
    )
    assert second.is_error and "limit_reached" in second.output
    assert (
        await tool.execute(
            AgentToolParams(prompt="overflow", description="d", subagent_type="worker")
        )
    ).is_error


@pytest.mark.asyncio
async def test_inprocess_teammate_keeps_permission_ceiling(tmp_path, monkeypatch):
    seen = []

    async def run(self, prompt, *args, **kwargs):
        seen.append(self)
        self.last_stop_reason = "completed"
        return "ok"

    monkeypatch.setattr(Agent, "run_to_completion", run)
    tool, parent, manager, trace, tree, inherited, checker = build(tmp_path)

    class TeamManager:
        def get_team(self, name):
            return SimpleNamespace(members=[])

        def detect_backend(self):
            return BackendType.IN_PROCESS

        def register_member(self, name, member):
            self.member = member

        def get_mailbox(self, name):
            return None

    team = TeamManager()
    tool._team_manager = team
    result = await tool.execute(
        AgentToolParams(
            prompt="x", description="d", team_name="team", subagent_type="worker"
        )
    )
    assert not result.is_error
    await asyncio.gather(*list(manager._async_tasks.values()))
    assert seen[0].permission_ceilings == [inherited, checker]
    assert seen[0]._spawn_depth == 1 and seen[0].work_dir == tree.path
    assert seen[0].registry.list_tools() == []


@pytest.mark.asyncio
async def test_spawn_budget_enforced_across_recreated_manager(tmp_path, monkeypatch):
    async def run(self, prompt, *args, **kwargs):
        self.last_stop_reason = "completed"
        return "ok"

    monkeypatch.setattr(Agent, "run_to_completion", run)
    first, parent, manager, trace, tree, _, _ = build(tmp_path, max_spawns=1)
    assert not (
        await first.execute(
            AgentToolParams(prompt="x", description="d", subagent_type="worker")
        )
    ).is_error
    other, _, _, _, _, _, _ = build(tmp_path, max_spawns=1)
    rejected = await other.execute(
        AgentToolParams(prompt="y", description="d", subagent_type="worker")
    )
    assert rejected.is_error and "spawn limit" in rejected.output


@pytest.mark.asyncio
async def test_missing_parent_policy_denies_child(tmp_path):
    tool, parent, manager, trace, tree, _, _ = build(tmp_path)
    parent.permission_checker = None
    parent.permission_ceilings = []
    result = await tool.execute(
        AgentToolParams(prompt="x", description="d", subagent_type="worker")
    )
    assert result.is_error and "permission policy" in result.output
    assert not manager._tasks and tree.calls == 0


@pytest.mark.asyncio
async def test_headless_entry_uses_durable_session_scope(tmp_path, monkeypatch, capsys):
    from gcode.__main__ import _run_prompt
    from gcode.permissions import PermissionMode
    import gcode.client, gcode.agents.task_manager

    created = []
    seen = []

    class CapturingManager(TaskManager):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            created.append(self)

    async def context(provider):
        return None

    async def run(self, prompt, conversation):
        seen.append((self.session_id, self.token_budget.max_total_tokens))
        self.last_stop_reason = "completed"
        return "ok"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gcode.client, "create_client", lambda provider: MagicMock())
    monkeypatch.setattr(gcode.client, "resolve_context_window", context)
    monkeypatch.setattr(gcode.agents.task_manager, "TaskManager", CapturingManager)
    monkeypatch.setattr(Agent, "run_to_completion", run)
    provider = SimpleNamespace(protocol="anthropic", get_context_window=lambda: 10000)
    config = SimpleNamespace(
        providers=[provider],
        worktree=None,
        enable_verification_agent=False,
        enable_fork=False,
        enable_coordinator_mode=False,
    )
    await _run_prompt(config, PermissionMode.DONT_ASK, None, "hello", 137)
    assert capsys.readouterr().out.strip() == "ok"
    assert seen[0][0] and created[0].scope_id == seen[0][0]
    assert seen[0][1] == 137
    assert created[0]._store.path == tmp_path / ".gcode" / "runtime" / "runs.sqlite3"
    assert (tmp_path / ".gcode" / "sessions" / (seen[0][0] + ".meta")).exists()


@pytest.mark.asyncio
async def test_disabled_parent_tool_is_not_reenabled(tmp_path, monkeypatch):
    from gcode.tools.read_file import ReadFile

    seen = []

    async def run(self, prompt, *args, **kwargs):
        seen.append(self)
        self.last_stop_reason = "completed"
        return "ok"

    monkeypatch.setattr(Agent, "run_to_completion", run)
    tool, parent, manager, trace, tree, _, _ = build(tmp_path)
    parent.registry.register(ReadFile())
    parent.registry.disable("ReadFile")
    assert not (
        await tool.execute(
            AgentToolParams(prompt="x", description="d", subagent_type="worker")
        )
    ).is_error
    assert seen[0].registry.get("ReadFile") is None


@pytest.mark.asyncio
async def test_owned_sibling_worktree_rebases_path_only_and_preserves_denies(
    tmp_path, monkeypatch
):
    from gcode.permissions import (
        DangerousCommandDetector,
        PathSandbox,
        PermissionChecker,
        PermissionMode,
        RuleEngine,
    )
    from gcode.runtime.budget import TokenBudget
    from pathlib import Path

    seen = []

    async def run(self, prompt, *args, **kwargs):
        seen.append(self)
        self.last_stop_reason = "completed"
        return "ok"

    monkeypatch.setattr(Agent, "run_to_completion", run)
    parentroot = tmp_path / "repo"
    parentroot.mkdir()
    sibling = tmp_path / "sibling"
    sibling.mkdir()
    import subprocess

    for args in (
        ["init"],
        ["config", "user.email", "x@example.com"],
        ["config", "user.name", "x"],
    ):
        subprocess.run(["git", *args], cwd=parentroot, check=True, capture_output=True)
    (parentroot / "file").write_text("base")
    subprocess.run(
        ["git", "add", "file"], cwd=parentroot, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "-m", "base"], cwd=parentroot, check=True, capture_output=True
    )
    tool, parent, manager, trace, tree, _, _ = build(parentroot)
    from gcode.worktree.manager import WorktreeManager

    tool._worktree_manager = WorktreeManager(
        str(parentroot), worktree_dir=str(sibling / "trees")
    )
    rule_file = tmp_path / "rules.yaml"
    rule_file.write_text(
        '- rule: "ReadFile(*secret*)"\n  effect: deny\n'
        + f'- rule: "WriteFile({parentroot / "secret"})"\n  effect: deny\n'
    )
    sandbox = PathSandbox(str(parentroot))
    sandbox._allowed_roots = [parentroot.resolve()]
    checker = PermissionChecker(
        DangerousCommandDetector(),
        sandbox,
        RuleEngine(project_rules_path=rule_file),
        PermissionMode.DEFAULT,
    )
    parent.permission_checker = checker
    parent.permission_ceilings = []
    parent.token_budget = TokenBudget(str(tmp_path / "budget.db"), "scope", 100)
    result = await tool.execute(
        AgentToolParams(
            prompt="x", description="d", subagent_type="worker", isolation="worktree"
        )
    )
    assert not result.is_error
    child = seen[0]
    inherited = child.permission_ceilings[0]
    assert inherited is not checker and inherited.mode == checker.mode
    assert (
        inherited.rule_engine.base is checker.rule_engine
        and inherited.detector is checker.detector
    )
    assert child.token_budget is parent.token_budget
    read = SimpleNamespace(name="ReadFile", category="read")
    assert not checker.sandbox.check(str(Path(child.work_dir) / "public"))[0]
    assert (
        child._permission_decision(
            read, {"file_path": str(Path(child.work_dir) / "public")}
        ).effect
        == "allow"
    )
    assert (
        child._permission_decision(
            read, {"file_path": str(Path(child.work_dir) / "secret")}
        ).effect
        == "deny"
    )
    write = SimpleNamespace(name="WriteFile", category="write")
    assert (
        child._permission_decision(
            write, {"file_path": str(Path(child.work_dir) / "secret")}
        ).effect
        == "deny"
    )


@pytest.mark.asyncio
async def test_exhausted_parent_budget_blocks_child_before_worktree(tmp_path):
    tool, parent, manager, trace, tree, _, _ = build(tmp_path)
    parent.token_budget.mark_usage_unknown()
    result = await tool.execute(
        AgentToolParams(
            prompt="x", description="d", subagent_type="worker", isolation="worktree"
        )
    )
    assert result.is_error and "budget" in result.output and tree.calls == 0


@pytest.mark.asyncio
async def test_child_clones_tools_skill_history_and_once_hooks(tmp_path, monkeypatch):
    from gcode.cache import FileCache
    from gcode.filehistory import FileHistory
    from gcode.hooks.engine import HookEngine
    from gcode.hooks.models import Hook, Action
    from gcode.tools import create_default_registry
    from gcode.tools.load_skill import LoadSkill, LoadSkillParams
    from gcode.tools.impl.tool_search import ToolSearchTool
    from gcode.tools.enter_worktree import EnterWorktreeTool
    from gcode.tools.exit_worktree import ExitWorktreeTool

    tool, parent, manager, trace, tree, _, _ = build(tmp_path)
    parent.registry = create_default_registry(file_cache=FileCache())
    parent.file_history = FileHistory(str(tmp_path), "parent")
    for item in parent.registry.list_tools():
        if hasattr(item, "file_history"):
            item.file_history = parent.file_history
    skill = LoadSkill()
    skill.set_agent(parent)
    skill.set_loader(
        SimpleNamespace(
            get=lambda name: SimpleNamespace(
                name=name, prompt_body="child sop", is_directory=False
            ),
            get_catalog=lambda: [],
        )
    )
    parent.registry.register(skill)
    parent.registry.register(ToolSearchTool(parent.registry))
    parent.registry.register(EnterWorktreeTool(MagicMock()))
    parent.registry.register(ExitWorktreeTool(MagicMock()))
    parent.hook_engine = HookEngine(
        [Hook(id="once", event="start", action=Action(type="prompt"), once=True)]
    )
    children = []

    async def run(self, prompt, *args, **kwargs):
        children.append(self)
        local = self.registry.get("LoadSkill")
        assert not (await local.execute(LoadSkillParams(name="child-skill"))).is_error
        self.hook_engine.hooks[0].mark_executed()
        self.last_stop_reason = "completed"
        return "ok"

    monkeypatch.setattr(Agent, "run_to_completion", run)
    for _ in range(2):
        assert not (
            await tool.execute(
                AgentToolParams(prompt="x", description="d", subagent_type="worker")
            )
        ).is_error
    a, b = children
    assert (
        parent.active_skills == {}
        and "child-skill" in a.active_skills
        and "child-skill" in b.active_skills
    )
    assert (
        not parent.hook_engine.hooks[0].executed and a.hook_engine is not b.hook_engine
    )
    assert a.registry.get("ReadFile") is not parent.registry.get("ReadFile")
    assert (
        a.registry.get("ReadFile")._state_cache
        is a.registry.get("WriteFile")._state_cache
    )
    assert (
        a.registry.get("ReadFile")._state_cache
        is not b.registry.get("ReadFile")._state_cache
    )
    assert (
        a.registry.get("ReadFile")._state_cache
        is not parent.registry.get("ReadFile")._state_cache
    )
    assert (
        a.file_history is not parent.file_history
        and a.file_history is not b.file_history
    )
    assert a.registry.get("WriteFile").file_history is a.file_history
    assert a.registry.get("LoadSkill")._agent is a and skill._agent is parent
    assert a.registry.get("ToolSearch")._registry is a.registry
    assert (
        a.registry.get("EnterWorktree") is None
        and a.registry.get("ExitWorktree") is None
    )
    assert (
        parent.registry.get("EnterWorktree") is not None
        and parent.registry.get("ExitWorktree") is not None
    )


@pytest.mark.asyncio
async def test_child_registry_cannot_add_or_replace_tools(tmp_path, monkeypatch):
    from gcode.tools import create_default_registry
    from gcode.tools.read_file import ReadFile
    from gcode.tools.bash import Bash

    tool, parent, manager, trace, tree, _, _ = build(tmp_path)
    parent.registry = create_default_registry()
    captured = []

    async def run(self, prompt, *args, **kwargs):
        captured.append(self)
        self.last_stop_reason = "completed"
        return "ok"

    monkeypatch.setattr(Agent, "run_to_completion", run)
    assert not (
        await tool.execute(
            AgentToolParams(prompt="x", description="d", subagent_type="worker")
        )
    ).is_error
    child = captured[0]

    class Extra:
        name = "UnexpectedCapability"

    with pytest.raises(PermissionError):
        child.registry.register(Extra())
    with pytest.raises(PermissionError):
        child.registry.register(ReadFile())
    assert child.registry.get("UnexpectedCapability") is None
    assert parent.registry.get("UnexpectedCapability") is None
