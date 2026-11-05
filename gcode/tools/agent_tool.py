from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from gcode.tools.base import Tool, ToolResult

if TYPE_CHECKING:
    from gcode.agent import Agent
    from gcode.agents.parser import AgentDef
    from gcode.agents.loader import AgentLoader
    from gcode.agents.task_manager import TaskManager
    from gcode.agents.trace import TraceManager
    from gcode.client import LLMClient

log = logging.getLogger(__name__)
_spawn_reservation: ContextVar = ContextVar("agent_spawn_reservation", default=None)


class AgentToolParams(BaseModel):
    prompt: str
    description: str
    subagent_type: str | None = None
    model: str | None = None
    run_in_background: bool = False
    name: str | None = None
    isolation: str | None = None
    team_name: str | None = Field(
        default=None,
        description=(
            "REQUIRED when creating team members. Spawns the agent as a long-running "
            "teammate under this team (created via TeamCreate). Unlike regular sub-agents, "
            "team members run in their own terminal, persist after the lead returns, and "
            "communicate with each other via SendMessage. Without team_name the agent "
            "runs as a one-shot sub-agent that blocks and returns inline."
        ),
    )


PERMISSION_MODE_MAP = {
    "default": "DEFAULT",
    "acceptEdits": "ACCEPT_EDITS",
    "dontAsk": "DONT_ASK",
}


TEAMMATE_ADDENDUM = (
    "\n\nIMPORTANT: You are running as an agent in a team.\n"
    "Just writing a response in text is not visible to others\n"
    "on your team - you MUST use the SendMessage tool.\n"
    "The user interacts primarily with the team lead.\n"
    "Your work is coordinated through the task system\n"
    "and teammate messaging.\n\n"
    "You are working in an isolated Git worktree. "
    "All file paths you use MUST be relative to your current working directory. "
    "Do NOT use absolute paths from the original project — they are outside your sandbox and will be rejected."
)


class AgentTool(Tool):
    name = "Agent"
    description = (
        "Launch a sub-agent to handle a task in an isolated context. "
        "Use subagent_type to select a predefined agent type (e.g. Explore, Plan, general-purpose), "
        "or leave it empty to fork the current conversation. "
        "Use team_name to spawn a teammate in an existing team."
    )
    params_model = AgentToolParams
    category = "command"
    is_concurrency_safe = False

    def __init__(
        self,
        agent_loader: AgentLoader,
        task_manager: TaskManager,
        trace_manager: TraceManager,
        parent_agent: Agent,
        enable_fork: bool = False,
        provider_config: Any = None,
        worktree_manager: Any = None,
        team_manager: Any = None,
    ) -> None:
        self._agent_loader = agent_loader
        self._task_manager = task_manager
        self._trace_manager = trace_manager
        self._parent_agent = parent_agent
        self._enable_fork = enable_fork
        self._provider_config = provider_config
        self._worktree_manager = worktree_manager
        self._team_manager = team_manager

    @staticmethod
    def _bounded_child_registry(allowed_names):
        from gcode.tools import ToolRegistry

        class ChildRegistry(ToolRegistry):
            def register(self, tool):
                if tool.name not in allowed_names:
                    raise PermissionError(
                        "child cannot add a tool outside its inherited capabilities"
                    )
                previous = self.get(tool.name)
                if previous is not None and previous is not tool:
                    raise PermissionError("child cannot replace an inherited tool")
                super().register(tool)

        return ChildRegistry()

    def _configure_child(self, child: Agent, approved_worktree: bool = False) -> None:
        import copy
        from gcode.permissions import PathSandbox, PermissionChecker
        from gcode.permissions.rules import ScopedRuleView

        parent = self._parent_agent
        ceilings = list(getattr(parent, "permission_ceilings", [])) + (
            [parent.permission_checker] if parent.permission_checker else []
        )
        if approved_worktree:
            rebased = []
            for checker in ceilings:
                if isinstance(checker, PermissionChecker):
                    checker = copy.copy(checker)
                    # Rebase filesystem scope only. Mode, rules and detector stay inherited.
                    checker.sandbox = PathSandbox(child.work_dir)
                    checker.rule_engine = ScopedRuleView(
                        checker.rule_engine, child.work_dir, parent.work_dir
                    )
                rebased.append(checker)
            ceilings = rebased
        child.permission_ceilings = ceilings
        child.token_budget = getattr(parent, "token_budget", None)
        child._spawn_budget = self._current_budget()
        child._spawn_depth = getattr(parent, "_spawn_depth", 0) + 1
        # Clone mutable per-agent tool state and prevent parent-session worktree tools.
        from gcode.cache import FileCache
        from gcode.filehistory import FileHistory
        from gcode.tools.file_state_cache import FileStateCache

        allowed_names = {
            item.name
            for item in child.registry.list_tools()
            if item.name not in ("EnterWorktree", "ExitWorktree")
        }
        registry = self._bounded_child_registry(allowed_names)
        state_cache, file_cache = FileStateCache(), FileCache()
        history = FileHistory(child.work_dir, child.agent_id)
        cloned = []
        for tool in child.registry.list_tools():
            if tool.name in ("EnterWorktree", "ExitWorktree"):
                continue
            if (
                approved_worktree
                and tool.name.startswith("mcp_")
                and not getattr(tool, "scope_independent", False)
            ):
                # Opaque server cwd cannot be rebased into the child's worktree.
                continue
            local = copy.copy(tool)
            if hasattr(local, "_state_cache") and local._state_cache is not None:
                local._state_cache = state_cache
            if hasattr(local, "_cache") and local._cache is not None:
                local._cache = file_cache
            if hasattr(local, "file_history"):
                local.file_history = history
            if hasattr(local, "_agent") and (
                local._agent is parent or local.name == "LoadSkill"
            ):
                local._agent = child
            if hasattr(local, "_parent_agent") and local._parent_agent is parent:
                local._parent_agent = child
            registry.register(local)
            if parent.registry.is_discovered(tool.name):
                registry.mark_discovered(tool.name)
            cloned.append(local)
        for local in cloned:
            if hasattr(local, "_registry") and local._registry is child.registry:
                local._registry = registry
            # ToolSearch can point at the parent registry rather than the filtered one.
            elif local.name == "ToolSearch" and hasattr(local, "_registry"):
                local._registry = registry
        child.registry = registry
        child.file_history = history
        if parent.hook_engine is not None:
            from gcode.hooks.engine import HookEngine

            hooks = copy.deepcopy(parent.hook_engine.hooks)
            for hook in hooks:
                hook.executed = False
            child.hook_engine = HookEngine(hooks)

    def _enabled_parent_registry(self):
        from gcode.tools import ToolRegistry

        registry = ToolRegistry()
        parent_registry = self._parent_agent.registry
        for tool in parent_registry.list_tools():
            if parent_registry.is_enabled(tool.name):
                registry.register(tool)
        return registry

    def _current_budget(self):
        from gcode.runtime.spawn import SpawnBudget

        budget = getattr(self._parent_agent, "_spawn_budget", None)
        manager = self._task_manager
        if isinstance(budget, SpawnBudget) and (
            getattr(self._parent_agent, "_spawn_depth", 0) > 0
            or budget.scope == manager.scope_id
        ):
            return budget
        budget = SpawnBudget(
            manager.scope_id,
            manager._store,
            manager._max_spawns,
            manager._max_concurrent,
            manager._max_depth,
        )
        self._parent_agent._spawn_budget = budget
        self._parent_agent._spawn_depth = 0
        return budget

    def _defer_reservation(self, task_id: str) -> None:
        reservation = _spawn_reservation.get()
        task = self._task_manager._async_tasks.get(task_id)
        if reservation is None or task is None:
            raise RuntimeError("background spawn receipt is unavailable")
        reservation["deferred"] = True
        task.add_done_callback(
            lambda _task: reservation["budget"].release(reservation["id"])
        )

    async def execute(self, params: BaseModel) -> ToolResult:
        p: AgentToolParams = params  # type: ignore[assignment]
        if (
            not self._parent_agent.permission_checker
            and not self._parent_agent.permission_ceilings
        ):
            return ToolResult(
                output="Parent permission policy is unavailable; child launch denied",
                is_error=True,
            )
        token_budget = getattr(self._parent_agent, "token_budget", None)
        if token_budget is not None and not token_budget.before_request():
            return ToolResult(
                output="Shared token budget exhausted or unknown; child launch denied",
                is_error=True,
            )
        if p.isolation not in (None, "none", "worktree"):
            return ToolResult(output="Unsupported isolation mode", is_error=True)
        if p.team_name and p.isolation == "none":
            return ToolResult(
                output="Teammates require worktree isolation", is_error=True
            )
        definition = (
            self._agent_loader.get(p.subagent_type) if p.subagent_type else None
        )
        if definition and definition.isolation == "worktree" and p.isolation == "none":
            return ToolResult(
                output="Agent definition requires worktree isolation", is_error=True
            )
        isolation = (
            "worktree"
            if p.isolation == "worktree"
            else (definition.isolation if definition and p.isolation is None else "")
        )
        if isolation not in ("", None, "none", "worktree"):
            return ToolResult(
                output="Unsupported isolation in agent definition", is_error=True
            )
        if (
            isolation == "worktree"
            and (p.run_in_background or (definition and definition.background))
            and not p.team_name
        ):
            return ToolResult(
                output="Background worktree agents are not supported", is_error=True
            )
        budget = self._current_budget()
        depth = getattr(self._parent_agent, "_spawn_depth", 0) + 1
        try:
            reservation_id = budget.reserve(depth)
        except RuntimeError as exc:
            return ToolResult(output=str(exc), is_error=True)
        reservation = {"budget": budget, "id": reservation_id, "deferred": False}
        token = _spawn_reservation.set(reservation)
        try:
            return await self._execute_impl(p, isolation)
        finally:
            _spawn_reservation.reset(token)
            if not reservation["deferred"]:
                budget.release(reservation_id)

    async def _execute_impl(self, p: AgentToolParams, isolation: str) -> ToolResult:
        if p.team_name:
            return await self._execute_as_teammate(p)
        if isolation == "worktree":
            return await self._execute_with_worktree(p)

        from gcode.agents.fork import ForkError, build_forked_messages
        from gcode.agents.parser import AgentDef
        from gcode.agents.tool_filter import resolve_agent_tools
        from gcode.agent import Agent as AgentClass
        from gcode.conversation import ConversationManager
        from gcode.permissions import (
            DangerousCommandDetector,
            PathSandbox,
            PermissionChecker,
            PermissionMode,
            RuleEngine,
        )

        definition: AgentDef | None = None
        conversation: ConversationManager

        if p.subagent_type:
            definition = self._agent_loader.get(p.subagent_type)
            if definition is None:
                return ToolResult(
                    output=f"Unknown agent type: '{p.subagent_type}'. "
                    f"Available types: {', '.join(t for t, _ in self._agent_loader.list_agents())}",
                    is_error=True,
                )
            conversation = ConversationManager()
        else:
            if not self._enable_fork:
                return ToolResult(
                    output="Fork mode is not enabled. "
                    "Set 'enable_fork: true' in config.yaml to use fork, "
                    "or specify a subagent_type parameter.",
                    is_error=True,
                )
            try:
                parent_conv = getattr(self._parent_agent, "_current_conversation", None)
                if parent_conv is None:
                    return ToolResult(
                        output="Cannot fork: no active conversation in parent agent.",
                        is_error=True,
                    )
                conversation = build_forked_messages(parent_conv, p.prompt)
            except ForkError as e:
                return ToolResult(output=str(e), is_error=True)

            definition = AgentDef(
                agent_type="fork",
                when_to_use="Forked from parent agent",
                system_prompt="",
                disallowed_tools=[],
                model="inherit",
                max_turns=self._parent_agent.max_iterations,
                permission_mode="dontAsk",
                source="builtin",
            )

        # 选择 LLM 客户端
        client = self._select_llm(p, definition)

        # 判断是否后台运行
        is_background = p.run_in_background or definition.background
        if self._enable_fork:
            is_background = True

        # 过滤工具（coordinator 模式可能缩减了注册表，这里用完整注册表）
        _base_registry = self._enabled_parent_registry()
        filtered_registry = resolve_agent_tools(
            _base_registry, definition, is_background
        )

        # 为子 agent 创建权限检查器
        pm_str = definition.permission_mode
        pm_enum = getattr(
            PermissionMode,
            PERMISSION_MODE_MAP.get(pm_str, "DEFAULT"),
            PermissionMode.DEFAULT,
        )
        checker = PermissionChecker(
            detector=DangerousCommandDetector(),
            sandbox=PathSandbox(self._parent_agent.work_dir),
            rule_engine=RuleEngine(),
            mode=pm_enum,
        )

        # 创建子 agent
        sub_agent = AgentClass(
            client=client,
            registry=filtered_registry,
            protocol=self._parent_agent.protocol,
            work_dir=self._parent_agent.work_dir,
            max_iterations=min(definition.max_turns, self._parent_agent.max_iterations),
            permission_checker=checker,
            context_window=self._parent_agent.context_window,
            instructions_content=definition.system_prompt,
            hook_engine=self._parent_agent.hook_engine,
        )
        self._configure_child(sub_agent)
        sub_agent.parent_id = self._parent_agent.agent_id
        sub_agent.trace_id = self._parent_agent.trace_id or self._parent_agent.agent_id

        # fork 子 agent 继承父 agent 的替换状态，确保共享的 tool_use_id 做出一致的
        # 决策——这样父子共享的 prompt cache 前缀才能保持字节级一致
        if p.subagent_type is None:
            from gcode.context import clone_replacement_state

            sub_agent.replacement_state = clone_replacement_state(
                self._parent_agent.replacement_state
            )

        # 注册追踪节点
        trace_node = self._trace_manager.create(
            agent_type=definition.agent_type,
            parent_id=self._parent_agent.agent_id,
            trace_id=sub_agent.trace_id,
        )
        sub_agent.agent_id = trace_node.agent_id

        agent_name = p.name or p.subagent_type or f"agent-{trace_node.agent_id}"
        is_fork = p.subagent_type is None

        if is_background:
            if is_fork:
                sub_agent._fork_conversation = conversation
            task_id = self._task_manager.launch(
                agent=sub_agent,
                task="" if is_fork else p.prompt,
                name=agent_name,
                fork_conversation=conversation if is_fork else None,
                depth=sub_agent._spawn_depth,
                budget_reserved=True,
            )
            self._defer_reservation(task_id)
            return ToolResult(
                output=f"Sub-agent launched in background.\n"
                f"Task ID: {task_id}\n"
                f"Agent: {agent_name}\n"
                f"Type: {definition.agent_type}\n"
                f"The system will notify automatically when it completes.\n"
                f"Do NOT wait, sleep, or poll. Report the task ID to the user and move on.",
            )

        # 前台同步执行
        try:
            if is_fork:
                result_text = await sub_agent.run_to_completion("", conversation)
            else:
                result_text = await sub_agent.run_to_completion(p.prompt)
        except Exception as e:
            self._trace_manager.complete(trace_node.agent_id, "failed")
            return ToolResult(output=f"Sub-agent failed: {e}", is_error=True)

        self._trace_manager.update(
            trace_node.agent_id,
            input_tokens=sub_agent.total_input_tokens,
            output_tokens=sub_agent.total_output_tokens,
        )
        reason = getattr(sub_agent, "last_stop_reason", "completed")
        if reason != "completed":
            self._trace_manager.complete(trace_node.agent_id, reason)
            return ToolResult(
                output=f"Sub-agent stopped: {reason}\n{result_text or ''}",
                is_error=True,
            )
        self._trace_manager.complete(trace_node.agent_id, "completed")
        return ToolResult(output=result_text or "(sub-agent returned no output)")

    async def _execute_as_teammate(self, p: AgentToolParams) -> ToolResult:
        if self._team_manager is None:
            return ToolResult(output="TeamManager not configured.", is_error=True)
        if self._worktree_manager is None:
            return ToolResult(
                output="WorktreeManager not configured for team spawn.", is_error=True
            )

        from gcode.agents.fork import ForkError, build_forked_messages
        from gcode.agents.parser import AgentDef
        from gcode.agents.tool_filter import build_teammate_tools
        from gcode.agent import Agent as AgentClass
        from gcode.conversation import ConversationManager
        from gcode.permissions import (
            DangerousCommandDetector,
            PathSandbox,
            PermissionChecker,
            PermissionMode,
            RuleEngine,
        )
        from gcode.teams.models import BackendType, TeammateInfo
        from gcode.teams.registry import AgentNameRegistry

        team = self._team_manager.get_team(p.team_name)
        if team is None:
            return ToolResult(
                output=f"Team '{p.team_name}' not found. Create it first with TeamCreate.",
                is_error=True,
            )

        backend = self._team_manager.detect_backend()
        if backend != BackendType.IN_PROCESS:
            return ToolResult(
                output="Pane teammates cannot inherit verified parent permissions and budgets; use in-process mode.",
                is_error=True,
            )

        base_name = p.name or p.subagent_type or "worker"
        existing_names = {m.name for m in team.members}
        teammate_name = base_name
        if teammate_name in existing_names:
            counter = 2
            while f"{base_name}-{counter}" in existing_names:
                counter += 1
            teammate_name = f"{base_name}-{counter}"

        # 1. 加载 agent 定义
        definition: AgentDef
        conversation: ConversationManager | None = None
        is_fork = False

        if p.subagent_type:
            defn = self._agent_loader.get(p.subagent_type)
            if defn is None:
                return ToolResult(
                    output=f"Unknown agent type: '{p.subagent_type}'. "
                    f"Available: {', '.join(t for t, _ in self._agent_loader.list_agents())}",
                    is_error=True,
                )
            definition = defn
        else:
            if self._enable_fork:
                try:
                    parent_conv = getattr(
                        self._parent_agent, "_current_conversation", None
                    )
                    if parent_conv is None:
                        return ToolResult(
                            output="Cannot fork: no active conversation.", is_error=True
                        )
                    conversation = build_forked_messages(parent_conv, p.prompt)
                    is_fork = True
                except ForkError as e:
                    return ToolResult(output=str(e), is_error=True)

            definition = AgentDef(
                agent_type="teammate",
                when_to_use="Team member",
                system_prompt="",
                disallowed_tools=[],
                model="inherit",
                max_turns=self._parent_agent.max_iterations,
                permission_mode="dontAsk",
                source="builtin",
            )

        # 2. 创建 worktree
        wt_name = f"team-{p.team_name}/{teammate_name}"
        try:
            wt = await self._worktree_manager.create(wt_name, "HEAD")
        except Exception as e:
            return ToolResult(
                output=f"Failed to create worktree for teammate: {e}", is_error=True
            )

        # 3. 选择 LLM
        client = self._select_llm(p, definition)

        # Backend was checked before creating any worktree.

        # 5. 构建队友的工具集
        trace_node = self._trace_manager.create(
            agent_type=definition.agent_type,
            parent_id=self._parent_agent.agent_id,
            trace_id=self._parent_agent.trace_id or self._parent_agent.agent_id,
        )
        agent_id = trace_node.agent_id

        _has_full = getattr(self._parent_agent, "_full_registry", None) is not None
        full_registry = self._enabled_parent_registry()
        _full_tools = [t.name for t in full_registry.list_tools()]
        log.info(
            "[teammate] has_full_registry=%s full_tools=%d names=%s backend=%s def_tools=%s def_disallowed=%s",
            _has_full,
            len(_full_tools),
            _full_tools,
            backend.value,
            getattr(definition, "tools", []),
            getattr(definition, "disallowed_tools", []),
        )
        teammate_registry = build_teammate_tools(
            parent_registry=full_registry,
            team_manager=self._team_manager,
            team_name=p.team_name,
            agent_id=agent_id,
            agent_name=teammate_name,
            backend_type=backend.value,
            definition=definition,
        )
        # Coordination tools also require parent authorization; never widen the tool set.
        from gcode.tools import ToolRegistry

        parent_names = {
            tool.name
            for tool in self._parent_agent.registry.list_tools()
            if self._parent_agent.registry.is_enabled(tool.name)
        }
        bounded_registry = ToolRegistry()
        for tool in teammate_registry.list_tools():
            if tool.name in parent_names:
                bounded_registry.register(tool)
        teammate_registry = bounded_registry
        _tm_tools = [t.name for t in teammate_registry.list_tools()]
        log.info("[teammate] result_tools=%d names=%s", len(_tm_tools), _tm_tools)

        # 6. 创建子 agent 并附加队友专属指令
        instructions = (definition.system_prompt or "") + TEAMMATE_ADDENDUM

        checker = PermissionChecker(
            detector=DangerousCommandDetector(),
            sandbox=PathSandbox(wt.path),
            rule_engine=RuleEngine(),
            mode=PermissionMode.DONT_ASK,
        )

        sub_agent = AgentClass(
            client=client,
            registry=teammate_registry,
            protocol=self._parent_agent.protocol,
            work_dir=wt.path,
            max_iterations=min(definition.max_turns, self._parent_agent.max_iterations),
            permission_checker=checker,
            context_window=self._parent_agent.context_window,
            instructions_content=instructions,
            hook_engine=self._parent_agent.hook_engine,
        )
        self._configure_child(sub_agent, approved_worktree=True)
        sub_agent.parent_id = self._parent_agent.agent_id
        sub_agent.trace_id = self._parent_agent.trace_id or self._parent_agent.agent_id
        sub_agent.agent_id = agent_id
        sub_agent.team_name = p.team_name
        sub_agent._team_manager = self._team_manager

        # 7. 注册名称和成员信息
        AgentNameRegistry.instance().register(teammate_name, agent_id)

        member = TeammateInfo(
            name=teammate_name,
            agent_id=agent_id,
            agent_type=definition.agent_type,
            model=p.model or definition.model,
            worktree_path=wt.path,
            backend_type=backend.value,
            is_active=True,
        )
        self._team_manager.register_member(p.team_name, member)

        # 8. 按后端类型启动队友
        if backend in (BackendType.TMUX, BackendType.ITERM2):
            return self._spawn_pane_teammate(
                p, team, member, backend, wt, agent_id, teammate_name
            )

        # 进程内模式：直接用 task_manager 执行并通知结果
        task_id = self._task_manager.launch(
            agent=sub_agent,
            task="" if is_fork else p.prompt,
            name=teammate_name,
            fork_conversation=conversation if is_fork else None,
            depth=sub_agent._spawn_depth,
            budget_reserved=True,
        )
        self._defer_reservation(task_id)

        return ToolResult(
            output=(
                f"Teammate '{teammate_name}' spawned in team '{p.team_name}'.\n"
                f"Agent ID: {agent_id}\n"
                f"Backend: {backend.value}\n"
                f"Worktree: {wt.path}\n"
                f"Task ID: {task_id}\n"
                f"The system will notify when it completes."
            )
        )

    def _spawn_pane_teammate(
        self,
        p: Any,
        team: Any,
        member: Any,
        backend: Any,
        wt: Any,
        agent_id: str,
        teammate_name: str,
    ) -> ToolResult:
        # No secure cross-process transfer exists for parent permission ceilings and quota.
        return ToolResult(
            output="Pane teammates cannot inherit verified parent permissions and budgets; use in-process mode.",
            is_error=True,
        )

    def _select_llm(
        self,
        params: AgentToolParams,
        definition: AgentDef,
    ) -> LLMClient:
        from gcode.agents.parser import AgentDef

        model_override = params.model or (
            definition.model if definition.model != "inherit" else None
        )

        if model_override and model_override != "inherit":
            client = self._create_client_for_model(model_override)
            if client is not None:
                return client

        return self._parent_agent.client

    async def _execute_with_worktree(self, p: AgentToolParams) -> ToolResult:
        if self._worktree_manager is None:
            return ToolResult(
                output="Worktree isolation is not available: WorktreeManager not configured.",
                is_error=True,
            )

        from gcode.agents.parser import AgentDef
        from gcode.agents.tool_filter import resolve_agent_tools
        from gcode.agent import Agent as AgentClass
        from gcode.conversation import ConversationManager
        from gcode.permissions import (
            DangerousCommandDetector,
            PathSandbox,
            PermissionChecker,
            PermissionMode,
            RuleEngine,
        )
        from gcode.worktree.integration import (
            build_worktree_notice,
            generate_worktree_name,
        )

        definition: AgentDef | None = None
        if p.subagent_type:
            definition = self._agent_loader.get(p.subagent_type)
            if definition is None:
                return ToolResult(
                    output=f"Unknown agent type: '{p.subagent_type}'. "
                    f"Available types: {', '.join(t for t, _ in self._agent_loader.list_agents())}",
                    is_error=True,
                )
        else:
            definition = AgentDef(
                agent_type="worktree-agent",
                when_to_use="Isolated worktree agent",
                system_prompt="",
                disallowed_tools=[],
                model="inherit",
                max_turns=self._parent_agent.max_iterations,
                permission_mode="dontAsk",
                source="builtin",
            )

        wt_name = generate_worktree_name()
        try:
            wt = await self._worktree_manager.create(wt_name, "HEAD")
        except Exception as e:
            return ToolResult(
                output=f"Failed to create worktree: {e}",
                is_error=True,
            )

        notice = build_worktree_notice(self._parent_agent.work_dir, wt.path)
        task = notice + "\n\n" + p.prompt

        client = self._select_llm(p, definition)

        _base_registry = self._enabled_parent_registry()
        filtered_registry = resolve_agent_tools(_base_registry, definition, False)

        pm_str = definition.permission_mode
        pm_enum = getattr(
            PermissionMode,
            PERMISSION_MODE_MAP.get(pm_str, "DEFAULT"),
            PermissionMode.DEFAULT,
        )
        checker = PermissionChecker(
            detector=DangerousCommandDetector(),
            sandbox=PathSandbox(wt.path),
            rule_engine=RuleEngine(),
            mode=pm_enum,
        )

        sub_agent = AgentClass(
            client=client,
            registry=filtered_registry,
            protocol=self._parent_agent.protocol,
            work_dir=wt.path,
            max_iterations=min(definition.max_turns, self._parent_agent.max_iterations),
            permission_checker=checker,
            context_window=self._parent_agent.context_window,
            instructions_content=definition.system_prompt,
            hook_engine=self._parent_agent.hook_engine,
        )
        self._configure_child(sub_agent, approved_worktree=True)
        sub_agent.parent_id = self._parent_agent.agent_id
        sub_agent.trace_id = self._parent_agent.trace_id or self._parent_agent.agent_id

        trace_node = self._trace_manager.create(
            agent_type=definition.agent_type,
            parent_id=self._parent_agent.agent_id,
            trace_id=sub_agent.trace_id,
        )
        sub_agent.agent_id = trace_node.agent_id

        try:
            result_text = await sub_agent.run_to_completion(task)
        except Exception as e:
            self._trace_manager.complete(trace_node.agent_id, "failed")
            return ToolResult(
                output=f"Sub-agent in worktree failed: {e}",
                is_error=True,
            )

        self._trace_manager.update(
            trace_node.agent_id,
            input_tokens=sub_agent.total_input_tokens,
            output_tokens=sub_agent.total_output_tokens,
        )
        reason = getattr(sub_agent, "last_stop_reason", "completed")
        self._trace_manager.complete(trace_node.agent_id, reason)

        cleanup = await self._worktree_manager.auto_cleanup(wt_name, wt.head_commit)
        if cleanup.kept:
            result_text = (result_text or "") + (
                f"\n[Worktree preserved at {cleanup.path}, branch {cleanup.branch}]"
            )

        if reason != "completed":
            return ToolResult(
                output=f"Sub-agent stopped: {reason}\n{result_text or ''}",
                is_error=True,
            )
        return ToolResult(output=result_text or "(sub-agent returned no output)")

    def _create_client_for_model(self, model_alias: str) -> LLMClient | None:
        if self._provider_config is None:
            return None

        from gcode.client import create_client
        from gcode.config import ProviderConfig

        model_map = {
            "haiku": "claude-haiku-4-5-20251001",
            "sonnet": "claude-sonnet-4-6-20250514",
            "opus": "claude-opus-4-6-20250514",
        }
        model_id = model_map.get(model_alias, model_alias)

        config = ProviderConfig(
            name=f"sub-{model_alias}",
            protocol=self._provider_config.protocol,
            base_url=self._provider_config.base_url,
            model=model_id,
            api_key=self._provider_config.api_key,
            context_window=self._provider_config.context_window,
        )
        try:
            return create_client(config)
        except Exception:
            return None
