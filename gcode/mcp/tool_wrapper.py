from __future__ import annotations

from typing import Any, Mapping

from mcp import types as mcp_types
from pydantic import BaseModel, create_model

from gcode.mcp.client import MCPClient
from gcode.tools.base import Tool, ToolResult


_MISSING = object()


def _field(value: Any, snake: str, camel: str, default: Any = _MISSING) -> Any:
    """SDK 2 uses snake_case attributes; SDK 1 and wire dictionaries use aliases."""
    for name in (snake, camel):
        if isinstance(value, Mapping):
            if name in value:
                return value[name]
        else:
            found = getattr(value, name, _MISSING)
            if found is not _MISSING:
                return found
    if default is _MISSING:
        raise ValueError(f"Missing MCP field: {snake}/{camel}")
    return default


def _block_data(block: Any) -> dict[str, Any]:
    if hasattr(block, "model_dump"):
        return block.model_dump(mode="json", by_alias=True, exclude_none=True)
    if isinstance(block, Mapping):
        return dict(block)
    if hasattr(block, "dict"):
        return block.dict(by_alias=True, exclude_none=True)
    raise ValueError("Unsupported MCP content block")


def _build_params_model(
    tool_name: str, input_schema: dict[str, Any]
) -> type[BaseModel]:
    properties = input_schema.get("properties", {})
    required = set(input_schema.get("required", []))

    field_definitions: dict[str, Any] = {}
    for name, prop in properties.items():
        py_type = _json_type_to_python(prop.get("type", "string"))
        if name in required:
            field_definitions[name] = (py_type, ...)
        else:
            field_definitions[name] = (py_type | None, None)

    return create_model(f"{tool_name}Params", **field_definitions)


def _json_type_to_python(json_type: str) -> type:
    mapping: dict[str, type] = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "object": dict,
        "array": list,
    }
    return mapping.get(json_type, str)


def _extract_text(content: list[Any]) -> str:
    parts: list[str] = []
    for block in content:
        kind = _field(block, "type", "type", None)
        if kind == "text":
            parts.append(_field(block, "text", "text"))
        elif kind == "image":
            parts.append(f"[image: {_field(block, 'mime_type', 'mimeType')}]")
        elif kind == "resource":
            resource = _field(block, "resource", "resource")
            text = _field(resource, "text", "text", None)
            if text is not None:
                parts.append(text)
            else:
                parts.append(f"[binary resource: {_field(resource, 'uri', 'uri')}]")
    return "\n".join(parts) if parts else "(no output)"


class MCPToolWrapper(Tool):
    def __init__(
        self,
        server_name: str,
        tool_def: mcp_types.Tool,
        client: MCPClient,
    ) -> None:
        self._server_name = server_name
        self._tool_def = tool_def
        self._client = client
        self.name = f"mcp_{server_name}_{tool_def.name}"
        self.description = tool_def.description or tool_def.name
        self.category = "command"
        self.is_concurrency_safe = False
        self.should_defer = True
        self._input_schema = _field(tool_def, "input_schema", "inputSchema")
        if not isinstance(self._input_schema, dict):
            raise ValueError("MCP tool input schema must be an object")
        self.params_model = _build_params_model(tool_def.name, self._input_schema)

    @property
    def mcp_tool_name(self) -> str:
        return self._tool_def.name

    def get_schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self._input_schema,
        }

    async def execute(self, params: BaseModel) -> ToolResult:
        if not self._client.is_alive:
            try:
                await self._client.connect()
            except Exception as e:
                return ToolResult(
                    output=f"MCP server '{self._server_name}' reconnect failed: {e}",
                    is_error=True,
                )

        try:
            result = await self._client.call_tool(
                self._tool_def.name, params.model_dump(exclude_none=True)
            )
        except Exception as e:
            self._client._alive = False
            return ToolResult(
                output=f"MCP tool call failed: {e}",
                is_error=True,
            )

        text = _extract_text(result.content)
        raw_content = [_block_data(block) for block in result.content]
        details = {
            "is_error": bool(_field(result, "is_error", "isError", False)),
            "structured_content": _field(
                result, "structured_content", "structuredContent", None
            ),
        }
        return ToolResult(
            output=text,
            is_error=details["is_error"],
            details=details,
            content=raw_content,
        )
