"""MCP 客户端系统的测试（第 6 章）。"""

from __future__ import annotations

import asyncio
import os
import textwrap
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from gcode.config import (
    AppConfig,
    ConfigError,
    MCPServerConfig,
    build_child_env,
    load_config,
    resolve_env_vars,
)

# ===========================================================================
# resolve_env_vars
# ===========================================================================


class TestResolveEnvVars:
    def test_substitutes_existing_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_TOKEN", "secret123")
        assert resolve_env_vars("${MY_TOKEN}") == "secret123"

    def test_preserves_missing_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NONEXISTENT_VAR", raising=False)
        assert resolve_env_vars("${NONEXISTENT_VAR}") == "${NONEXISTENT_VAR}"

    def test_no_placeholder_passthrough(self) -> None:
        assert resolve_env_vars("plain-text") == "plain-text"

    def test_multiple_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("A", "hello")
        monkeypatch.setenv("B", "world")
        assert resolve_env_vars("${A}-${B}") == "hello-world"

    def test_mixed_existing_and_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EXISTS", "yes")
        monkeypatch.delenv("NOPE", raising=False)
        assert resolve_env_vars("${EXISTS}/${NOPE}") == "yes/${NOPE}"


# ===========================================================================
# build_child_env
# ===========================================================================


class TestBuildChildEnv:
    def test_includes_path(self) -> None:
        env = build_child_env(None)
        assert "PATH" in env

    def test_includes_declared_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_SECRET", "abc")
        env = build_child_env({"TOKEN": "${MY_SECRET}"})
        assert env["TOKEN"] == "abc"
        assert "PATH" in env

    def test_excludes_host_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret")
        env = build_child_env({"FOO": "bar"})
        assert "ANTHROPIC_API_KEY" not in env
        assert env["FOO"] == "bar"

    def test_empty_declared_env(self) -> None:
        env = build_child_env({})
        assert "PATH" in env
        assert len(env) == 1


# ===========================================================================
# load_config：解析 mcp_servers
# ===========================================================================


class TestLoadConfigMCP:
    def _write_config(self, tmp_path: Path, content: str) -> Path:
        p = tmp_path / "config.yaml"
        p.write_text(textwrap.dedent(content))
        return p

    def test_no_mcp_servers(self, tmp_path: Path) -> None:
        path = self._write_config(
            tmp_path,
            """\
            providers:
              - name: test
                protocol: openai
                base_url: http://localhost
                model: gpt-4o
        """,
        )
        config = load_config(path)
        assert config.mcp_servers == []

    def test_stdio_server(self, tmp_path: Path) -> None:
        path = self._write_config(
            tmp_path,
            """\
            providers:
              - name: test
                protocol: openai
                base_url: http://localhost
                model: gpt-4o
            mcp_servers:
              - name: github
                command: npx
                args: ["-y", "@modelcontextprotocol/server-github"]
                env:
                  GITHUB_TOKEN: "${GITHUB_TOKEN}"
        """,
        )
        config = load_config(path)
        assert len(config.mcp_servers) == 1
        srv = config.mcp_servers[0]
        assert srv.name == "github"
        assert srv.command == "npx"
        assert srv.is_stdio is True
        assert srv.args == ["-y", "@modelcontextprotocol/server-github"]

    def test_http_server(self, tmp_path: Path) -> None:
        path = self._write_config(
            tmp_path,
            """\
            providers:
              - name: test
                protocol: openai
                base_url: http://localhost
                model: gpt-4o
            mcp_servers:
              - name: remote
                url: "https://api.example.com/mcp"
                headers:
                  Authorization: "Bearer ${TOKEN}"
        """,
        )
        config = load_config(path)
        srv = config.mcp_servers[0]
        assert srv.name == "remote"
        assert srv.url == "https://api.example.com/mcp"
        assert srv.is_stdio is False

    def test_both_command_and_url_errors(self, tmp_path: Path) -> None:
        path = self._write_config(
            tmp_path,
            """\
            providers:
              - name: test
                protocol: openai
                base_url: http://localhost
                model: gpt-4o
            mcp_servers:
              - name: bad
                command: npx
                url: "https://example.com"
        """,
        )
        with pytest.raises(ConfigError, match="cannot have both"):
            load_config(path)

    def test_neither_command_nor_url_errors(self, tmp_path: Path) -> None:
        path = self._write_config(
            tmp_path,
            """\
            providers:
              - name: test
                protocol: openai
                base_url: http://localhost
                model: gpt-4o
            mcp_servers:
              - name: bad
                env:
                  FOO: bar
        """,
        )
        with pytest.raises(ConfigError, match="must have either"):
            load_config(path)


# ===========================================================================
# MCPToolWrapper
# ===========================================================================


class TestMCPToolWrapper:
    def test_name_format(self) -> None:
        from mcp import types as mcp_types
        from gcode.mcp.tool_wrapper import MCPToolWrapper
        from gcode.mcp.client import MCPClient

        tool_def = mcp_types.Tool(
            name="search_issues",
            description="Search GitHub issues",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "query": {"type": "string"},
                },
                "required": ["repo"],
            },
        )
        mock_client = MagicMock(spec=MCPClient)
        wrapper = MCPToolWrapper("github", tool_def, mock_client)

        assert wrapper.name == "mcp_github_search_issues"
        assert wrapper.category == "command"
        assert wrapper.description == "Search GitHub issues"

    def test_get_schema_uses_original_input_schema(self) -> None:
        from mcp import types as mcp_types
        from gcode.mcp.tool_wrapper import MCPToolWrapper

        input_schema = {
            "type": "object",
            "properties": {"q": {"type": "string"}},
            "required": ["q"],
        }
        tool_def = mcp_types.Tool(
            name="search",
            description="Search",
            inputSchema=input_schema,
        )
        mock_client = MagicMock()
        wrapper = MCPToolWrapper("srv", tool_def, mock_client)

        schema = wrapper.get_schema()
        assert schema["name"] == "mcp_srv_search"
        assert schema["input_schema"] == input_schema


# ===========================================================================
# _extract_text
# ===========================================================================


class TestExtractText:
    def test_text_content(self) -> None:
        from mcp import types as mcp_types
        from gcode.mcp.tool_wrapper import _extract_text

        content = [
            mcp_types.TextContent(type="text", text="hello"),
            mcp_types.TextContent(type="text", text="world"),
        ]
        assert _extract_text(content) == "hello\nworld"

    def test_empty_content(self) -> None:
        from gcode.mcp.tool_wrapper import _extract_text

        assert _extract_text([]) == "(no output)"

    def test_image_content(self) -> None:
        from mcp import types as mcp_types
        from gcode.mcp.tool_wrapper import _extract_text

        content = [
            mcp_types.ImageContent(type="image", data="...", mimeType="image/png")
        ]
        assert "[image: image/png]" in _extract_text(content)


# ===========================================================================
# MCPManager：部分失败容错
# ===========================================================================


class TestMCPManagerPartialFailure:
    @pytest.mark.asyncio
    async def test_single_server_failure_does_not_block_others(self) -> None:
        from gcode.mcp.manager import MCPManager
        from gcode.tools import ToolRegistry

        good_config = MCPServerConfig(
            name="good",
            command="echo",
            args=["hello"],
        )
        bad_config = MCPServerConfig(
            name="bad",
            command="nonexistent_command_xyz_12345",
        )

        manager = MCPManager()
        manager.load_configs([bad_config, good_config])

        registry = ToolRegistry()

        with patch("gcode.mcp.manager.MCPClient") as MockClient:
            good_instance = AsyncMock()
            good_instance.is_alive = True

            from mcp import types as mcp_types

            good_instance.list_tools.return_value = [
                mcp_types.Tool(
                    name="test_tool",
                    description="A test",
                    inputSchema={"type": "object", "properties": {}},
                )
            ]

            bad_instance = AsyncMock()
            bad_instance.connect.side_effect = RuntimeError("command not found")

            def make_client(config: MCPServerConfig) -> AsyncMock:
                if config.name == "bad":
                    return bad_instance
                return good_instance

            MockClient.side_effect = make_client

            errors = await manager.register_all_tools(registry)

        assert len(errors) == 1
        assert "bad" in errors[0]
        assert registry.get("mcp_good_test_tool") is not None


class TestMCPFieldCompatibility:
    def test_legacy_camel_case_fields(self) -> None:
        from types import SimpleNamespace
        from gcode.mcp.tool_wrapper import MCPToolWrapper, _extract_text

        legacy = SimpleNamespace(
            name="lookup",
            description="lookup",
            inputSchema={
                "type": "object",
                "properties": {"q": {"type": "string"}},
                "required": ["q"],
            },
        )
        wrapper = MCPToolWrapper("legacy", legacy, MagicMock())
        assert wrapper.get_schema()["input_schema"] == legacy.inputSchema
        assert (
            _extract_text([SimpleNamespace(type="image", mimeType="image/png")])
            == "[image: image/png]"
        )

    @pytest.mark.asyncio
    async def test_current_error_receipt_and_structured_content_preserved(self) -> None:
        from mcp import types
        from gcode.mcp.tool_wrapper import MCPToolWrapper

        tool = types.Tool(
            name="lookup", inputSchema={"type": "object", "properties": {}}
        )
        client = MagicMock(is_alive=True)
        client.call_tool = AsyncMock(
            return_value=types.CallToolResult(
                content=[types.TextContent(type="text", text="failed")],
                isError=True,
                structuredContent={"code": "NO_DATA"},
            )
        )
        result = await MCPToolWrapper("srv", tool, client).execute(
            MCPToolWrapper("srv", tool, client).params_model()
        )
        assert result.is_error is True and result.output == "failed"
        assert result.details["structured_content"] == {"code": "NO_DATA"}
        assert result.content[0]["text"] == "failed"

    def test_mapping_config_remains_invalid(self, tmp_path: Path) -> None:
        from gcode.validator import validate_mcp_servers

        with pytest.raises(ConfigError, match="must be a list"):
            validate_mcp_servers({"not_a_list": {"command": "echo"}})


@pytest.mark.asyncio
async def test_real_local_mcp_stdio_read_only(tmp_path: Path) -> None:
    import json, sys, importlib.metadata
    from gcode.mcp.manager import MCPManager
    from gcode.tools import ToolRegistry

    server = tmp_path / "fixture_server.py"
    server.write_text(
        """try:\n from mcp.server.mcpserver import MCPServer\nexcept ImportError:\n from mcp.server.fastmcp import FastMCP as MCPServer\nserver=MCPServer("synthetic-local-fixture")\n@server.tool()\ndef echo_readonly(value: str) -> str:\n return "fixture:" + value\nif __name__ == "__main__": server.run(transport="stdio")\n"""
    )
    manager = MCPManager()
    manager.load_configs(
        [MCPServerConfig(name="fixture", command=sys.executable, args=[str(server)])]
    )
    registry = ToolRegistry()
    try:
        assert await manager.register_all_tools(registry) == []
        wrapper = registry.get("mcp_fixture_echo_readonly")
        assert wrapper is not None
        result = await wrapper.execute(wrapper.params_model(value="hello"))
        assert not result.is_error and result.output == "fixture:hello"
        assert result.content and result.content[0]["text"] == "fixture:hello"
        print(
            "MCP_FIXTURE_EVIDENCE "
            + json.dumps(
                {
                    "mcp_version": importlib.metadata.version("mcp"),
                    "transport": "local stdio",
                    "server": "synthetic-local-fixture",
                    "tool": "echo_readonly",
                    "input": {"value": "hello"},
                    "output": result.output,
                    "is_error": result.is_error,
                    "input_schema": wrapper.get_schema()["input_schema"],
                    "content": result.content,
                    "details": result.details,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_failed_tool_discovery_closes_client() -> None:
    from gcode.mcp.manager import MCPManager
    from gcode.tools import ToolRegistry

    manager = MCPManager()
    manager.load_configs([MCPServerConfig(name="broken", command="echo")])
    client = AsyncMock()
    client.list_tools.side_effect = RuntimeError("invalid schema")
    with patch("gcode.mcp.manager.MCPClient", return_value=client):
        errors = await manager.register_all_tools(ToolRegistry())
    assert len(errors) == 1 and "broken" in errors[0]
    client.close.assert_awaited_once()
    assert await manager.get_client("missing") is None
    assert "broken" not in manager._clients


@pytest.mark.asyncio
async def test_http_transport_uses_installed_sdk_client(monkeypatch) -> None:
    from contextlib import AsyncExitStack, asynccontextmanager
    from gcode.mcp.client import MCPClient, streamable_http_module
    from gcode.mcp import client as module
    import httpx

    capture = {}

    @asynccontextmanager
    async def fake_transport(url, *, http_client):
        capture["client"] = http_client
        yield ("read", "write", lambda: None)

    monkeypatch.setattr(module, "streamable_http_client", fake_transport)
    client = MCPClient(
        MCPServerConfig(
            name="local", url="http://127.0.0.1:12345/mcp", headers={"X-Test": "yes"}
        )
    )
    async with AsyncExitStack() as stack:
        client._stack = stack
        assert await client._connect_http() == ("read", "write")
        lib = getattr(streamable_http_module, "httpx2", httpx)
        assert isinstance(capture["client"], lib.AsyncClient)
        assert capture["client"].headers["X-Test"] == "yes"
        assert capture["client"].follow_redirects is (lib is httpx)


@pytest.mark.asyncio
async def test_malformed_tool_does_not_register_partial_server() -> None:
    from types import SimpleNamespace
    from gcode.mcp.manager import MCPManager
    from gcode.tools import ToolRegistry

    manager = MCPManager()
    manager.load_configs([MCPServerConfig(name="bad", command="echo")])
    client = AsyncMock()
    client.list_tools.return_value = [
        SimpleNamespace(
            name="valid",
            description="",
            inputSchema={"type": "object", "properties": {}},
        ),
        SimpleNamespace(name="invalid", description=""),
    ]
    registry = ToolRegistry()
    with patch("gcode.mcp.manager.MCPClient", return_value=client):
        errors = await manager.register_all_tools(registry)
    assert len(errors) == 1 and registry.get("mcp_bad_valid") is None
    client.close.assert_awaited_once()
