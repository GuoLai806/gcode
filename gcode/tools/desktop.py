"""Opt-in desktop tools. The caller supplies configured transport and schema."""

from __future__ import annotations
import json
import uuid
import hashlib
import os
from pathlib import Path
from typing import Any
from pydantic import BaseModel, ConfigDict
from gcode.cu.transport import CUError, CUTransport, WRITES
from gcode.tools.base import Tool, ToolResult


class DesktopParams(BaseModel):
    model_config = ConfigDict(extra="allow")


class DesktopTool(Tool):
    params_model = DesktopParams
    is_concurrency_safe = False

    def __init__(
        self,
        transport: CUTransport,
        method: str,
        schema: dict[str, Any],
        description: str,
    ):
        if method not in {"ax_observe", "ax_query", "ax_action", "window_keyboard"}:
            raise ValueError("unsupported desktop method")
        self._transport, self.method, self.name, self.description, self._schema = (
            transport,
            method,
            method,
            description,
            schema,
        )
        self.category = "write" if method in WRITES else "read"

    def get_schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self._schema,
        }

    async def execute(self, params: BaseModel) -> ToolResult:
        from gcode.runtime.context import current_tool_context

        ctx = current_tool_context()
        if ctx is None or not ctx.run_id or not ctx.session_id:
            return ToolResult(
                output="CU requires a run and session context", is_error=True
            )
        if self.method in WRITES and (
            ctx.parent_run_id is not None or not ctx.allow_cu_write
        ):
            return ToolResult(
                output="CU write is not authorized for this run", is_error=True
            )
        try:
            response = await self._transport.call(
                self.method,
                params.model_dump(exclude_none=True),
                run_id=ctx.run_id,
                session_id=ctx.session_id,
                action_id=str(uuid.uuid4()) if self.method in WRITES else None,
            )
        except CUError as exc:
            return ToolResult(
                output=f"{exc.code}: {exc} ({exc.delivery_state})",
                is_error=True,
                details={
                    "error": {"code": exc.code},
                    "delivery_state": exc.delivery_state,
                },
            )
        artifact = response.get("artifact_reference")
        if artifact:
            try:
                digest = artifact["sha256"]
                if (
                    not isinstance(digest, str)
                    or len(digest) != 64
                    or any(c not in "0123456789abcdef" for c in digest)
                ):
                    raise ValueError("invalid artifact digest")
                source = Path(artifact["path"]).resolve(strict=True)
                expected = (
                    self._transport.state_dir / "artifacts" / (digest + ".json")
                ).resolve(strict=True)
                if source != expected:
                    raise ValueError("artifact outside configured transport store")
                data = source.read_bytes()
                if hashlib.sha256(data).hexdigest() != digest:
                    raise ValueError("artifact digest mismatch")
                target_dir = ctx.artifact_dir.resolve()
                target_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
                target = target_dir / ("cu-" + digest + ".json")
                try:
                    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                except FileExistsError:
                    if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                        raise ValueError("existing artifact digest mismatch")
                else:
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(data)
                        stream.flush()
                        os.fsync(stream.fileno())
                response["artifact_reference"] = {
                    "sha256": digest,
                    "path": str(target),
                    "size": len(data),
                }
            except (KeyError, OSError, TypeError, ValueError) as exc:
                return ToolResult(
                    output=f"CU artifact could not be retained: {exc}; delivery remains {response.get('delivery_state', 'unknown')}",
                    is_error=True,
                    details=response,
                )
            summary = f"CU response stored as artifact {digest} ({len(data)} bytes); delivery: {response.get('delivery_state', 'unknown')}"
            return ToolResult(
                output=summary,
                is_error=not response["ok"],
                details=response,
                content=[
                    {"type": "text", "text": summary},
                    {"type": "artifact", **response["artifact_reference"]},
                ],
            )
        content = response.get("content") or []
        output = "\n".join(
            str(block.get("text", ""))
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
        if not response.get("ok"):
            output = output or json.dumps(response.get("error", {}), ensure_ascii=False)
        return ToolResult(
            output=output,
            is_error=not response["ok"],
            details=response,
            content=content,
        )


def desktop_tools_from_hello(
    transport: CUTransport, hello: dict[str, Any], *, allow_write: bool = False
) -> list[DesktopTool]:
    """Register only recognized provider-advertised schemas; writes remain opt-in."""
    if hello.get("ok") is not True or not isinstance(hello.get("capabilities"), list):
        raise ValueError("invalid desktop hello")
    result: list[DesktopTool] = []
    seen: set[str] = set()
    for item in hello["capabilities"]:
        if not isinstance(item, dict):
            raise ValueError("invalid desktop capability")
        name, schema, description = (
            item.get("name"),
            item.get("input_schema"),
            item.get("description"),
        )
        if name not in {"ax_observe", "ax_query", "ax_action", "window_keyboard"}:
            continue
        if (
            name in seen
            or not isinstance(schema, dict)
            or not isinstance(description, str)
        ):
            raise ValueError("invalid or duplicated desktop capability")
        seen.add(name)
        if name in WRITES and not allow_write:
            continue
        result.append(DesktopTool(transport, name, schema, description))
    return result
