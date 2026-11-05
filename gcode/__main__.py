from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from gcode.config import ConfigError, load_config
from gcode.hooks import HookConfigError, HookEngine, load_hooks
from gcode.permissions import PermissionMode


def _positive_tokens(value: str) -> int:
    try:
        limit = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "token limit must be a positive integer"
        ) from exc
    if limit <= 0 or limit > 9_223_372_036_854_775_807:
        raise argparse.ArgumentTypeError(
            "token limit must be a positive 64-bit integer"
        )
    return limit


def main() -> None:
    # 先确保 .gcode/ 目录存在，否则下面写 debug.log 会因目录不存在而崩溃
    Path(".gcode").mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(message)s",
        filename=".gcode/debug.log",
        filemode="w",
    )

    parser = argparse.ArgumentParser(
        prog="gcode", description="GCode AI coding assistant"
    )
    parser.add_argument(
        "--mode",
        choices=[m.value for m in PermissionMode],
        default=None,
        help="Permission mode (overrides config.yaml)",
    )
    parser.add_argument(
        "-p",
        metavar="PROMPT",
        default=None,
        help="Run non-interactively: execute the prompt and print the result to stdout",
    )
    parser.add_argument(
        "--max-total-tokens",
        type=_positive_tokens,
        default=1_000_000,
        help="Total observed token budget per session (default: 1000000)",
    )
    parser.add_argument(
        "--cu-config",
        metavar="PATH",
        default=None,
        help="Enable local computer use with an explicit JSON configuration",
    )
    args = parser.parse_args()
    from gcode.cu.bootstrap import CUConfig, CUConfigError

    cu_config = None
    if args.cu_config:
        try:
            cu_config = CUConfig.from_file(args.cu_config)
        except CUConfigError:
            print("CU configuration is invalid or unavailable", file=sys.stderr)
            sys.exit(1)

    try:
        config = load_config()
    except ConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    mode_str = args.mode if args.mode else config.permission_mode
    permission_mode = PermissionMode(mode_str)

    try:
        hooks = load_hooks(config.raw_hooks)
    except HookConfigError as e:
        print(f"Hook config error: {e}", file=sys.stderr)
        sys.exit(1)

    hook_engine = HookEngine(hooks) if hooks else None

    if args.p is not None:
        try:
            asyncio.run(
                _run_prompt(
                    config,
                    permission_mode,
                    hook_engine,
                    args.p,
                    args.max_total_tokens,
                    cu_config,
                )
            )
        except CUConfigError:
            print("CU startup failed", file=sys.stderr)
            sys.exit(1)
        return

    from gcode.app import GCodeApp
    from gcode.driver import NoAltScreenDriver

    app = GCodeApp(
        providers=config.providers,
        permission_mode=permission_mode,
        mcp_servers=config.mcp_servers,
        hook_engine=hook_engine,
        enable_fork=config.enable_fork,
        enable_verification_agent=config.enable_verification_agent,
        worktree_config=config.worktree,
        teammate_mode=config.teammate_mode,
        enable_coordinator_mode=config.enable_coordinator_mode,
        max_total_tokens=args.max_total_tokens,
        cu_config=cu_config,
        driver_class=NoAltScreenDriver,
    )
    app.run()


async def _run_prompt(
    config,
    permission_mode,
    hook_engine,
    prompt: str,
    max_total_tokens: int = 1_000_000,
    cu_config=None,
) -> None:
    from gcode.cu.bootstrap import CUBootstrap

    bootstrap = CUBootstrap(cu_config) if cu_config else None
    try:
        await _run_prompt_impl(
            config, permission_mode, hook_engine, prompt, max_total_tokens, bootstrap
        )
    finally:
        try:
            if bootstrap:
                await bootstrap.close()
        finally:
            if hook_engine:
                await hook_engine.aclose()


async def _run_prompt_impl(
    config, permission_mode, hook_engine, prompt: str, max_total_tokens: int, bootstrap
) -> None:
    from gcode.agent import Agent
    from gcode.client import create_client, resolve_context_window
    from gcode.conversation import ConversationManager
    from gcode.memory.instructions import load_instructions
    from gcode.memory.session import SessionManager
    from gcode.permissions import (
        DangerousCommandDetector,
        PathSandbox,
        PermissionChecker,
        RuleEngine,
    )
    from gcode.tools import create_default_registry
    from gcode.agents.loader import AgentLoader
    from gcode.agents.task_manager import TaskManager
    from gcode.agents.trace import TraceManager
    from gcode.tools.agent_tool import AgentTool
    from gcode.tools.impl.tool_search import ToolSearchTool
    from gcode.teams.manager import TeamManager
    from gcode.teams.models import BackendType
    from gcode.tools.team_create import TeamCreateTool
    from gcode.tools.team_delete import TeamDeleteTool
    from gcode.worktree import WorktreeManager
    from gcode.config import WorktreeConfig

    provider = config.providers[0]
    client = create_client(provider)
    # 第 2 层：尽力从 provider 自动拉取模型的 context window（缓存在 provider 上）。
    # 不会抛异常或阻塞启动；失败则退化到映射表。
    await resolve_context_window(provider)
    work_dir = os.getcwd()
    home = Path.home()

    checker = PermissionChecker(
        detector=DangerousCommandDetector(),
        sandbox=PathSandbox(work_dir),
        rule_engine=RuleEngine(
            user_rules_path=home / ".gcode" / "permissions.yaml",
            project_rules_path=Path(work_dir) / ".gcode" / "permissions.yaml",
            local_rules_path=Path(work_dir) / ".gcode" / "permissions.local.yaml",
        ),
        mode=permission_mode,
    )

    instructions = load_instructions(work_dir)
    registry = create_default_registry()
    registry.register(ToolSearchTool(registry, protocol=provider.protocol))

    agent = Agent(
        client=client,
        registry=registry,
        protocol=provider.protocol,
        work_dir=work_dir,
        permission_checker=checker,
        context_window=provider.get_context_window(),
        instructions_content=instructions,
        hook_engine=hook_engine,
        max_total_tokens=max_total_tokens,
    )

    wt_cfg = config.worktree or WorktreeConfig()
    wt_manager = WorktreeManager(
        repo_root=work_dir,
        symlink_directories=wt_cfg.symlink_directories,
    )
    session = SessionManager(work_dir).create()
    session.close()
    agent.session_id = session.session_id
    if bootstrap:
        await bootstrap.start(agent, registry)
    trace_manager = TraceManager()
    task_manager = TaskManager(
        store_path=str(Path(work_dir) / ".gcode" / "runtime" / "runs.sqlite3"),
        scope_id=session.session_id,
    )
    agent_loader = AgentLoader(
        work_dir, enable_verification=config.enable_verification_agent
    )
    agent_loader.load_all()
    team_manager = TeamManager(worktree_manager=wt_manager, trace_manager=trace_manager)

    agent_tool = AgentTool(
        agent_loader=agent_loader,
        task_manager=task_manager,
        trace_manager=trace_manager,
        parent_agent=agent,
        enable_fork=config.enable_fork,
        provider_config=provider,
        worktree_manager=wt_manager,
        team_manager=team_manager,
    )
    registry.register(agent_tool)
    registry.register(
        TeamCreateTool(
            team_manager=team_manager,
            parent_agent=agent,
            teammate_mode="in-process",
            is_interactive=False,
            enable_coordinator_mode=config.enable_coordinator_mode,
        )
    )
    registry.register(TeamDeleteTool(team_manager=team_manager, parent_agent=agent))

    conv = ConversationManager()

    def persist_notification(note: str) -> None:
        agent.persist_notification(conv, note)

    def drain_notifications() -> list[str]:
        notes: list[str] = []
        for t in task_manager.poll_completed():
            notes.append(
                f"<task-notification>\n<task_id>{t.id}</task_id>\n"
                f"<status>{t.status}</status>\n<result>{t.result}</result>\n"
                f"</task-notification>"
            )
        notes.extend(team_manager.drain_lead_mailbox(persist=persist_notification))
        return notes

    def drain_mailbox_only() -> list[str]:
        team_manager.drain_lead_mailbox(persist=persist_notification)
        return []

    agent.notification_fn = drain_mailbox_only
    last_result = await agent.run_to_completion(prompt, conv)
    print(last_result, flush=True)
    if agent.last_stop_reason != "completed":
        print(f"Agent stopped: {agent.last_stop_reason}", file=sys.stderr, flush=True)
        raise SystemExit(1)

    if not team_manager._teams:
        return

    for i in range(90):
        await asyncio.sleep(2)
        running = {k: not t.done() for k, t in task_manager._async_tasks.items()}
        completed_ids = [
            t.id for t in task_manager._tasks.values() if t.status != "running"
        ]
        print(
            f"[poll {i}] running={running} completed={completed_ids} teams={list(team_manager._teams.keys())} queue_size={task_manager._notify_queue.qsize()}",
            file=sys.stderr,
            flush=True,
        )
        notes = drain_notifications()
        if not notes:
            has_running = any(v for v in running.values())
            if not has_running:
                print(
                    f"[poll {i}] no running tasks, breaking",
                    file=sys.stderr,
                    flush=True,
                )
                break
            continue
        # Mailbox notes are already checkpointed; persist task notifications too.
        for note in notes:
            if not note.startswith("<team-notification"):
                persist_notification(note)
        last_result = await agent.run_to_completion(
            "Teammate notifications received. Process them and continue.", conv
        )
        print(last_result, flush=True)
        if agent.last_stop_reason != "completed":
            print(
                f"Agent stopped: {agent.last_stop_reason}", file=sys.stderr, flush=True
            )
            raise SystemExit(1)


if __name__ == "__main__":
    main()
