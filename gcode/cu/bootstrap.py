"""Explicit, opt-in local CU startup. Configuration values are never logged."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID
from pathlib import Path
from typing import Any

from gcode.cu.transport import CUTransport
from gcode.tools.desktop import desktop_tools_from_hello

_ENV_KEYS = frozenset(
    {
        "GCODE_PI_EXTENSION",
        "GCODE_PI_SDK_PACKAGE",
        "GCODE_PI_MANIFEST",
        "PI_AGENT_DESKTOP_BINARY",
        "PI_AGENT_DESKTOP_APP",
        "PI_AGENT_DESKTOP_ALLOWED_APPS",
        "PI_CU_WINDOW_KEYBOARD",
        "GCODE_CU_MACHINE_DIR",
    }
)
_PATH_KEYS = frozenset(
    {
        "GCODE_PI_EXTENSION",
        "GCODE_PI_SDK_PACKAGE",
        "GCODE_PI_MANIFEST",
        "PI_AGENT_DESKTOP_BINARY",
        "PI_CU_WINDOW_KEYBOARD",
        "GCODE_CU_MACHINE_DIR",
    }
)
_HASH = re.compile(r"^[0-9a-f]{64}$")


class CUConfigError(ValueError):
    pass


def _absolute(value: Any, field_name: str) -> Path:
    if not isinstance(value, str) or not value or not Path(value).is_absolute():
        raise CUConfigError(f"CU {field_name} must be an absolute path")
    return Path(value)


def default_server() -> Path:
    bundled = Path(__file__).resolve().parent / "sidecar" / "server.mjs"
    source = Path(__file__).resolve().parents[2] / "sidecar" / "server.mjs"
    return bundled if bundled.is_file() else source


@dataclass(frozen=True)
class CUConfig:
    node: Path
    provider: Path
    state_dir: Path
    server: Path
    allow_write: bool = False
    env: dict[str, str] = field(default_factory=dict, repr=False)
    expected_identity: dict[str, str] = field(default_factory=dict, repr=False)

    @classmethod
    def from_file(cls, path: str | Path) -> CUConfig:
        try:

            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError("duplicate field")
                    result[key] = value
                return result

            raw = json.loads(
                Path(path).read_text(encoding="utf-8"),
                object_pairs_hook=unique,
                parse_constant=lambda _: (_ for _ in ()).throw(
                    ValueError("invalid number")
                ),
            )
        except (OSError, UnicodeError, ValueError) as exc:
            raise CUConfigError("Cannot read valid CU configuration") from exc
        if not isinstance(raw, dict) or set(raw) - {
            "node",
            "provider",
            "state_dir",
            "server",
            "allow_write",
            "env",
            "expected_identity",
        }:
            raise CUConfigError("Invalid CU configuration fields")
        env = raw.get("env", {})
        expected = raw.get("expected_identity", {})
        if (
            not isinstance(env, dict)
            or set(env) - _ENV_KEYS
            or any(not isinstance(v, str) or not v for v in env.values())
        ):
            raise CUConfigError("Invalid CU environment fields")
        for key in _PATH_KEYS & env.keys():
            _absolute(env[key], key)
        if (
            not isinstance(expected, dict)
            or set(expected)
            - {
                "provider_sha256",
                "bridge_sha256",
                "native_sha256",
                "manifest_sha256",
                "schema_sha256",
                "server_sha256",
                "node_sha256",
            }
            or any(
                not isinstance(v, str) or not _HASH.fullmatch(v)
                for v in expected.values()
            )
        ):
            raise CUConfigError("Invalid CU expected identity")
        if type(raw.get("allow_write", False)) is not bool:
            raise CUConfigError("CU allow_write must be boolean")
        node = _absolute(raw.get("node"), "node")
        provider = _absolute(raw.get("provider"), "provider")
        state = _absolute(raw.get("state_dir"), "state_dir")
        server = _absolute(raw.get("server", str(default_server())), "server")
        if (
            not node.is_file()
            or not os.access(node, os.X_OK)
            or not provider.is_file()
            or not server.is_file()
        ):
            raise CUConfigError("CU executable, provider or sidecar is unavailable")
        if state.exists() and not state.is_dir():
            raise CUConfigError("CU state directory is invalid")
        return cls(
            node,
            provider,
            state,
            server,
            raw.get("allow_write", False),
            dict(env),
            dict(expected),
        )


class _ConfiguredTransport(CUTransport):
    def __init__(self, config: CUConfig):
        super().__init__(
            str(config.node), config.server, config.provider, config.state_dir
        )
        self._config = config

    async def start(self) -> None:
        if self._proc or self._dead:
            raise CUConfigError("CU transport already started or closed")
        env = {
            k: v
            for k, v in os.environ.items()
            if k in {"PATH", "HOME", "TMPDIR", "LANG", "SYSTEMROOT"}
            or k.startswith("LC_")
        }
        env.update(self._config.env)
        env.update(
            GCODE_CU_PROVIDER=str(self.provider), GCODE_CU_STATE_DIR=str(self.state_dir)
        )
        self._proc = await asyncio.create_subprocess_exec(
            self.node,
            str(self.server),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=env,
            limit=2 * 1024 * 1024 + 1,
        )


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def _schema_hash(node: Path, schemas: list[dict[str, Any]]) -> str:
    code = "let s='';process.stdin.setEncoding('utf8');process.stdin.on('data',x=>s+=x);process.stdin.on('end',()=>process.stdout.write(require('node:crypto').createHash('sha256').update(JSON.stringify(JSON.parse(s))).digest('hex')))"
    process = await asyncio.create_subprocess_exec(
        str(node),
        "-e",
        code,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        output, _ = await asyncio.wait_for(
            process.communicate(
                json.dumps(schemas, ensure_ascii=False, allow_nan=False).encode()
            ),
            5,
        )
    except BaseException:
        if process.returncode is None:
            process.kill()
            await process.wait()
        raise
    digest = output.decode("ascii", errors="replace")
    if process.returncode != 0 or not _HASH.fullmatch(digest):
        raise CUConfigError("CU schema digest could not be verified")
    return digest


class CUBootstrap:
    def __init__(self, config: CUConfig):
        self.config = config
        self.transport: CUTransport | None = None
        self._started = False
        self._closed = False
        self._owner: tuple[str, str] | None = None
        self.identity: dict[str, Any] | None = None

    async def start(self, agent: Any, registry: Any) -> None:
        if self._started or self._closed:
            raise CUConfigError("CU already initialized or closed")
        self._started = True
        if agent.parent_id is not None:
            raise CUConfigError("CU bootstrap requires a root agent")
        ctx = agent.execution_context()
        self._owner = (ctx.run_id, ctx.session_id)
        transport = _ConfiguredTransport(self.config)
        self.transport = transport
        try:
            await transport.start()
            hello = await transport.hello(*self._owner)
            ident = hello.get("runtime_identity")
            schemas = hello.get("capabilities")
            if (
                hello.get("ok") is not True
                or not isinstance(ident, dict)
                or type(ident.get("protocol")) is not int
                or ident.get("protocol") != 1
                or not transport._proc
                or ident.get("process_id") != transport._proc.pid
                or ident.get("platform")
                != ("darwin" if sys.platform == "darwin" else sys.platform)
                or not isinstance(ident.get("process_nonce"), str)
                or not ident["process_nonce"]
                or not isinstance(ident.get("process_started_at"), str)
            ):
                raise CUConfigError("CU runtime identity is invalid")
            try:
                UUID(ident["process_nonce"])
                datetime.fromisoformat(
                    ident["process_started_at"].replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                raise CUConfigError("CU runtime identity is invalid") from None
            provider_hash = _digest_file(self.config.provider)
            if ident.get("provider_sha256") != provider_hash:
                raise CUConfigError("CU provider identity mismatch")
            if "GCODE_PI_EXTENSION" in self.config.env:
                if ident.get("manifest_verified") is not True or any(
                    not isinstance(ident.get(k), str) or not _HASH.fullmatch(ident[k])
                    for k in ("bridge_sha256", "native_sha256", "manifest_sha256")
                ):
                    raise CUConfigError("CU native manifest identity is not verified")
                for env_key, id_key in (
                    ("GCODE_PI_EXTENSION", "bridge_sha256"),
                    ("PI_AGENT_DESKTOP_BINARY", "native_sha256"),
                    ("GCODE_PI_MANIFEST", "manifest_sha256"),
                    ("GCODE_PI_SDK_PACKAGE", "sdk_package_sha256"),
                ):
                    configured = self.config.env.get(env_key)
                    if not configured or ident.get(id_key) != _digest_file(
                        Path(configured)
                    ):
                        raise CUConfigError("CU local dependency identity mismatch")
            if (
                not isinstance(schemas, list)
                or not schemas
                or any(
                    not isinstance(x, dict)
                    or x.get("name")
                    not in {"ax_observe", "ax_query", "ax_action", "window_keyboard"}
                    or not isinstance(x.get("input_schema"), dict)
                    or x["input_schema"].get("type") != "object"
                    or not isinstance(x.get("description"), str)
                    for x in schemas
                )
            ):
                raise CUConfigError("CU capabilities are invalid")
            if "ax_observe" not in [x["name"] for x in schemas]:
                raise CUConfigError("CU read capability is unavailable")
            if hello.get("schema_sha256") != await _schema_hash(
                self.config.node, schemas
            ):
                raise CUConfigError("CU capability schema hash mismatch")
            local_identity = {
                "server_sha256": _digest_file(self.config.server),
                "node_sha256": _digest_file(self.config.node),
            }
            for key, expected in self.config.expected_identity.items():
                actual = (
                    hello.get(key)
                    if key == "schema_sha256"
                    else local_identity.get(key)
                    if key in local_identity
                    else ident.get(key)
                )
                if actual != expected:
                    raise CUConfigError("CU pinned identity mismatch")
            tools = desktop_tools_from_hello(
                transport, hello, allow_write=self.config.allow_write
            )
            if any(registry.get(tool.name) is not None for tool in tools):
                raise CUConfigError(
                    "CU tool registration conflicts with an existing tool"
                )
            for tool in tools:
                registry.register(tool)
            agent.allow_cu_write = self.config.allow_write
            self.identity = {
                **ident,
                **local_identity,
                "schema_sha256": hello["schema_sha256"],
            }
        except asyncio.CancelledError:
            await self.close()
            raise
        except Exception as exc:
            try:
                await self.close()
            finally:
                raise CUConfigError("CU startup failed") from exc

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.transport and self._owner:
            await self.transport.shutdown(*self._owner)
