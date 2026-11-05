from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from gcode.tools.base import SKIP_DIRS, Tool, ToolResult
from gcode.runtime.context import resolve_tool_path


class Params(BaseModel):
    pattern: str = Field(description="Glob pattern to match (e.g. '**/*.py')")
    path: str = Field(default=".", description="Base directory to search from")


class Glob(Tool):
    name = "Glob"
    description = "Find files matching a glob pattern, returning relative paths."
    params_model = Params
    category = "read"
    is_concurrency_safe = True

    async def execute(self, params: Params) -> ToolResult:
        base = resolve_tool_path(params.path)
        if Path(params.pattern).is_absolute() or ".." in Path(params.pattern).parts:
            return ToolResult(
                output="Glob pattern must stay inside its search directory",
                is_error=True,
            )
        if not base.exists():
            return ToolResult(
                output=f"Error: path not found: {params.path}", is_error=True
            )

        try:
            found = [
                p
                for p in base.glob(params.pattern)
                if p.is_file()
                and p.resolve().is_relative_to(base)
                and not any(part in SKIP_DIRS for part in p.parts)
            ]
            # 按修改时间倒序，最近修改的排前面
            found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            matches = [str(p.relative_to(base)) for p in found]
        except Exception as e:
            return ToolResult(output=f"Error: {e}", is_error=True)

        if not matches:
            return ToolResult(output="No files matched the pattern.")
        return ToolResult(output="\n".join(matches))
