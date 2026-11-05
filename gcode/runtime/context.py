"""Task-local tool context; never change the process working directory.

ContextVar propagation isolates concurrently executing asyncio agents. Context is
installed by Tool.invoke, including when legacy/third-party execute(params)
methods are used. It is a routing boundary, not an operating-system sandbox.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


@dataclass(frozen=True)
class ToolExecutionContext:
    run_id: str
    session_id: str
    cwd: Path
    artifact_dir: Path
    parent_run_id: str | None = None
    trace_id: str = ""
    deadline: float | None = None
    allow_cu_write: bool = False
    tool_call_id: str = ""

    def resolve_path(self, value: str | Path) -> Path:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = self.cwd / path
        return path.resolve()

    def normalize_arguments(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        fields = {
            "ReadFile": ("file_path",),
            "WriteFile": ("file_path",),
            "EditFile": ("file_path",),
            "Glob": ("path",),
            "Grep": ("path",),
        }.get(tool_name, ())
        result = dict(arguments)
        for field in fields:
            value = result.get(field, "." if field == "path" else None)
            if isinstance(value, str):
                result[field] = str(self.resolve_path(value))
        return result


_current: ContextVar[ToolExecutionContext | None] = ContextVar(
    "gcode_tool_context", default=None
)


def current_tool_context() -> ToolExecutionContext | None:
    return _current.get()


@contextmanager
def tool_context(context: ToolExecutionContext) -> Iterator[None]:
    token = _current.set(context)
    try:
        yield
    finally:
        _current.reset(token)


def resolve_tool_path(value: str | Path) -> Path:
    context = current_tool_context()
    if context is not None:
        return context.resolve_path(value)
    return Path(value).expanduser().resolve()
