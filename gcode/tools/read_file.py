from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from gcode.tools.base import Tool, ToolResult
from gcode.runtime.context import resolve_tool_path

if TYPE_CHECKING:
    from gcode.cache import FileCache
    from gcode.tools.file_state_cache import FileStateCache


class Params(BaseModel):
    file_path: str = Field(description="Absolute or relative path to the file to read")
    offset: int = Field(
        default=0, description="Line offset to start reading from (0-based)"
    )
    limit: int = Field(default=2000, description="Maximum number of lines to read")


class ReadFile(Tool):
    name = "ReadFile"
    description = "Read a file and return its contents with line numbers."
    params_model = Params
    category = "read"
    is_concurrency_safe = True

    def __init__(
        self,
        file_cache: FileCache | None = None,
        file_state_cache: FileStateCache | None = None,
    ) -> None:
        self._cache = file_cache
        self._state_cache = file_state_cache

    async def execute(self, params: Params) -> ToolResult:
        path = resolve_tool_path(params.file_path)
        if not path.exists():
            return ToolResult(
                output=f"Error: file not found: {params.file_path}", is_error=True
            )
        if not path.is_file():
            return ToolResult(
                output=f"Error: not a file: {params.file_path}", is_error=True
            )

        resolved = str(path.resolve())

        try:
            from gcode.cache import FileCache, read_stable
            from gcode.tools.file_state_cache import FileStateCache

            text, snapshot, digest = read_stable(path)
            if (
                path.parent.name == "objects"
                and path.parent.parent.name == "artifact-store"
                and digest != path.name
            ):
                raise ValueError("Content-addressed artifact hash mismatch")
            if isinstance(self._cache, FileCache):
                self._cache.put_snapshot(resolved, text, snapshot, digest)
            elif self._cache is not None:
                self._cache.put(resolved, text)
            if isinstance(self._state_cache, FileStateCache):
                self._state_cache.record_snapshot(
                    resolved, text, snapshot.st_mtime_ns, digest
                )
            elif self._state_cache is not None:
                self._state_cache.record(resolved, text, snapshot.st_mtime_ns)
        except Exception as e:
            return ToolResult(output=f"Error reading file: {e}", is_error=True)

        lines = text.splitlines()
        selected = lines[params.offset : params.offset + params.limit]
        numbered = [
            f"{i + params.offset + 1}\t{line}" for i, line in enumerate(selected)
        ]
        return ToolResult(output="\n".join(numbered))
