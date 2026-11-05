import asyncio
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from gcode.cu.bootstrap import CUConfig, CUConfigError, CUBootstrap
from gcode.runtime.context import ToolExecutionContext
from gcode.tools import ToolRegistry
from gcode.tools.desktop import DesktopParams

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(not NODE, reason="Node required")


@pytest.fixture
def config_file(tmp_path):
    provider = tmp_path / "synthetic.mjs"
    provider.write_text(
        """export async function createBridge(){return {schemas:[{name:'ax_observe',description:'synthetic read',input_schema:{type:'object'}},{name:'ax_action',description:'synthetic write',input_schema:{type:'object'}}],async call(method){return {content:[{type:'text',text:method}],details:{synthetic:true},delivery_state:'delivered_unverified'}}}}"""
    )
    config = {
        "node": str(Path(NODE).resolve()),
        "provider": str(provider),
        "state_dir": str(tmp_path / "state"),
        "env": {"GCODE_CU_MACHINE_DIR": str(tmp_path / "machine")},
    }
    file = tmp_path / "cu.json"
    file.write_text(json.dumps(config))
    return file, config


class Agent:
    def __init__(self, tmp_path, parent=None):
        self.parent_id = parent
        self.allow_cu_write = False
        self.path = tmp_path

    def execution_context(self):
        return ToolExecutionContext(
            run_id="run",
            session_id="session",
            cwd=self.path,
            artifact_dir=self.path / "artifacts",
            parent_run_id=self.parent_id,
            allow_cu_write=self.allow_cu_write,
        )


@pytest.mark.asyncio
async def test_real_subprocess_registers_only_reads_and_closes(config_file, tmp_path):
    file, _ = config_file
    agent = Agent(tmp_path)
    registry = ToolRegistry()
    b = CUBootstrap(CUConfig.from_file(file))
    await b.start(agent, registry)
    assert registry.get("ax_observe") is not None and registry.get("ax_action") is None
    result = await registry.get("ax_observe").invoke(
        DesktopParams(), agent.execution_context()
    )
    assert result.output == "ax_observe" and not result.is_error
    with pytest.raises(CUConfigError):
        await b.start(agent, registry)
    proc = b.transport._proc
    await b.close()
    await b.close()
    assert proc.returncode == 0


@pytest.mark.asyncio
async def test_write_opt_in_and_child_is_denied(config_file, tmp_path):
    file, raw = config_file
    raw["allow_write"] = True
    file.write_text(json.dumps(raw))
    agent = Agent(tmp_path)
    registry = ToolRegistry()
    b = CUBootstrap(CUConfig.from_file(file))
    try:
        await b.start(agent, registry)
        assert agent.allow_cu_write and registry.get("ax_action") is not None
        child = Agent(tmp_path, parent="run")
        child.allow_cu_write = True
        denied = await registry.get("ax_action").invoke(
            DesktopParams(), child.execution_context()
        )
        assert denied.is_error and "not authorized" in denied.output
    finally:
        await b.close()


@pytest.mark.asyncio
async def test_root_only_and_invalid_hello_closed(config_file, tmp_path):
    file, raw = config_file
    bad = tmp_path / "bad.mjs"
    bad.write_text('export async function createBridge(){throw Error("bad")}')
    raw["provider"] = str(bad)
    file.write_text(json.dumps(raw))
    b = CUBootstrap(CUConfig.from_file(file))
    with pytest.raises(CUConfigError):
        await b.start(Agent(tmp_path), ToolRegistry())
    assert b.transport._proc.returncode is not None
    c = CUBootstrap(CUConfig.from_file(file))
    with pytest.raises(CUConfigError):
        await c.start(Agent(tmp_path, parent="parent"), ToolRegistry())
    assert c.transport is None


@pytest.mark.parametrize(
    "update",
    [
        {"node": "node"},
        {"provider": "relative"},
        {"allow_write": "true"},
        {"env": {"SECRET": "x"}},
        {"extra": 1},
        {"expected_identity": {"native_sha256": "not-hash"}},
    ],
)
def test_invalid_config_fails_without_leaking_values(config_file, update):
    file, raw = config_file
    raw.update(update)
    file.write_text(json.dumps(raw))
    with pytest.raises(CUConfigError) as err:
        CUConfig.from_file(file)
    assert "SECRET" not in str(err.value)


@pytest.mark.asyncio
async def test_pinned_identity_mismatch_closes(config_file, tmp_path):
    file, raw = config_file
    raw["expected_identity"] = {"schema_sha256": "0" * 64}
    file.write_text(json.dumps(raw))
    registry = ToolRegistry()
    b = CUBootstrap(CUConfig.from_file(file))
    with pytest.raises(CUConfigError):
        await b.start(Agent(tmp_path), registry)
    assert (
        registry.get("ax_observe") is None and b.transport._proc.returncode is not None
    )


class FakeLLM:
    def __init__(self):
        self.tool_names = []

    async def stream(self, conversation, system="", tools=None):
        from gcode.tools.base import TextDelta, StreamEnd

        self.tool_names = [
            x.get("name") or x.get("function", {}).get("name") for x in (tools or [])
        ]
        yield TextDelta("synthetic answer")
        yield StreamEnd("end_turn", input_tokens=10, output_tokens=2)


@pytest.mark.asyncio
async def test_real_textual_app_registration_and_cleanup(
    config_file, tmp_path, monkeypatch
):
    from gcode.app import GCodeApp
    from gcode.config import ProviderConfig
    import gcode.app as module

    monkeypatch.chdir(tmp_path)
    client = FakeLLM()
    monkeypatch.setattr(module, "create_client", lambda p: client)

    async def no_resolve(p):
        return None

    monkeypatch.setattr(module, "resolve_context_window", no_resolve)
    app = GCodeApp(
        [
            ProviderConfig(
                "fixture",
                "anthropic",
                "https://example.invalid",
                "fixture",
                "x",
                context_window=200000,
            )
        ],
        cu_config=CUConfig.from_file(config_file[0]),
    )
    async with app.run_test(size=(90, 30)) as pilot:
        await asyncio.wait_for(app._cu_init_task, 5)
        assert not app._cu_failed and app.registry.get("ax_observe") is not None
        assert (
            app.registry.get("ax_action") is None and app.agent.allow_cu_write is False
        )
        proc = app._cu_bootstrap.transport._proc
    assert proc.returncode is not None


@pytest.mark.asyncio
async def test_headless_entry_registers_tools_and_cleans_up(
    config_file, tmp_path, monkeypatch, capsys
):
    from gcode import __main__ as cli
    from gcode.config import ProviderConfig, WorktreeConfig
    from gcode.permissions import PermissionMode
    import gcode.client as client_module

    monkeypatch.chdir(tmp_path)
    client = FakeLLM()
    monkeypatch.setattr(client_module, "create_client", lambda p: client)

    async def no_resolve(p):
        return None

    monkeypatch.setattr(client_module, "resolve_context_window", no_resolve)
    config = SimpleNamespace(
        providers=[
            ProviderConfig(
                "fixture",
                "anthropic",
                "https://example.invalid",
                "fixture",
                "x",
                context_window=200000,
            )
        ],
        worktree=WorktreeConfig(),
        enable_verification_agent=False,
        enable_fork=False,
        enable_coordinator_mode=False,
    )
    await cli._run_prompt(
        config,
        PermissionMode.DEFAULT,
        None,
        "hello",
        1234,
        CUConfig.from_file(config_file[0]),
    )
    assert "ax_observe" in client.tool_names and "ax_action" not in client.tool_names
    assert "synthetic answer" in capsys.readouterr().out
    assert not (tmp_path / "machine" / "writer.lock").exists()


@pytest.mark.asyncio
async def test_app_failed_hello_blocks_model_request(
    config_file, tmp_path, monkeypatch
):
    from gcode.app import GCodeApp
    from gcode.config import ProviderConfig
    import gcode.app as module

    file, raw = config_file
    bad = tmp_path / "bad.mjs"
    bad.write_text('export async function createBridge(){throw Error("unavailable")}')
    raw["provider"] = str(bad)
    file.write_text(json.dumps(raw))
    monkeypatch.chdir(tmp_path)
    client = FakeLLM()
    monkeypatch.setattr(module, "create_client", lambda p: client)

    async def no_resolve(p):
        return None

    monkeypatch.setattr(module, "resolve_context_window", no_resolve)
    app = GCodeApp(
        [
            ProviderConfig(
                "fixture",
                "anthropic",
                "https://example.invalid",
                "fixture",
                "x",
                context_window=200000,
            )
        ],
        cu_config=CUConfig.from_file(file),
    )
    async with app.run_test(size=(90, 30)):
        await asyncio.wait_for(app._cu_init_task, 5)
        assert app._cu_failed and app.registry.get("ax_observe") is None
        await app._send_message_impl("must not reach model")
        assert client.tool_names == []
        assert app._cu_bootstrap.transport._proc.returncode is not None


@pytest.mark.asyncio
async def test_headless_always_closes_hooks_on_start_failure(
    config_file, tmp_path, monkeypatch
):
    from gcode import __main__ as cli
    from gcode.config import ProviderConfig, WorktreeConfig
    from gcode.permissions import PermissionMode
    import gcode.client as client_module
    from unittest.mock import AsyncMock

    file, raw = config_file
    bad = tmp_path / "bad.mjs"
    bad.write_text('export async function createBridge(){throw Error("unavailable")}')
    raw["provider"] = str(bad)
    file.write_text(json.dumps(raw))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(client_module, "create_client", lambda p: FakeLLM())

    async def no_resolve(p):
        return None

    monkeypatch.setattr(client_module, "resolve_context_window", no_resolve)
    config = SimpleNamespace(
        providers=[
            ProviderConfig(
                "fixture",
                "anthropic",
                "https://example.invalid",
                "fixture",
                "x",
                context_window=200000,
            )
        ],
        worktree=WorktreeConfig(),
        enable_verification_agent=False,
        enable_fork=False,
        enable_coordinator_mode=False,
    )
    hooks = SimpleNamespace(aclose=AsyncMock())
    with pytest.raises(CUConfigError):
        await cli._run_prompt(
            config,
            PermissionMode.DEFAULT,
            hooks,
            "hello",
            1234,
            CUConfig.from_file(file),
        )
    hooks.aclose.assert_awaited_once()
    assert not (tmp_path / "machine" / "writer.lock").exists()


@pytest.mark.asyncio
async def test_textual_unmount_closes_hooks(config_file, tmp_path, monkeypatch):
    from gcode.app import GCodeApp
    from gcode.config import ProviderConfig
    from gcode.hooks import HookEngine
    import gcode.app as module
    from unittest.mock import AsyncMock

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "create_client", lambda p: FakeLLM())

    async def no_resolve(p):
        return None

    monkeypatch.setattr(module, "resolve_context_window", no_resolve)
    hooks = HookEngine([])
    hooks.aclose = AsyncMock()
    app = GCodeApp(
        [
            ProviderConfig(
                "fixture",
                "anthropic",
                "https://example.invalid",
                "fixture",
                "x",
                context_window=200000,
            )
        ],
        cu_config=CUConfig.from_file(config_file[0]),
        hook_engine=hooks,
    )
    async with app.run_test(size=(90, 30)):
        await asyncio.wait_for(app._cu_init_task, 5)
    hooks.aclose.assert_awaited()


@pytest.mark.asyncio
async def test_schema_hash_mismatch_prevents_registration(
    config_file, tmp_path, monkeypatch
):
    import gcode.cu.bootstrap as module

    async def bad_hash(*_args):
        return "0" * 64

    monkeypatch.setattr(module, "_schema_hash", bad_hash)
    b = CUBootstrap(CUConfig.from_file(config_file[0]))
    registry = ToolRegistry()
    with pytest.raises(CUConfigError):
        await b.start(Agent(tmp_path), registry)
    assert (
        registry.get("ax_observe") is None and b.transport._proc.returncode is not None
    )


def test_duplicate_config_fields_are_rejected(config_file):
    file, _ = config_file
    file.write_text('{"node":"one","node":"two"}')
    with pytest.raises(CUConfigError):
        CUConfig.from_file(file)


def test_cli_passes_explicit_cu_config_and_token_budget(
    config_file, tmp_path, monkeypatch
):
    import sys
    from gcode import __main__ as cli

    seen = {}

    async def fake_prompt(config, mode, hooks, prompt, budget, cu):
        seen.update(prompt=prompt, budget=budget, cu=cu)

    cfg = SimpleNamespace(permission_mode="default", raw_hooks=[])
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "gcode",
            "--cu-config",
            str(config_file[0]),
            "--max-total-tokens",
            "431",
            "-p",
            "hello",
        ],
    )
    monkeypatch.setattr(cli, "load_config", lambda: cfg)
    monkeypatch.setattr(cli, "load_hooks", lambda _: [])
    monkeypatch.setattr(cli, "_run_prompt", fake_prompt)
    cli.main()
    assert (
        seen["prompt"] == "hello"
        and seen["budget"] == 431
        and seen["cu"].allow_write is False
    )
