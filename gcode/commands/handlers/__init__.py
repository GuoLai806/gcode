from __future__ import annotations

from gcode.commands.handlers.clear import CLEAR_COMMAND
from gcode.commands.handlers.compact import COMPACT_COMMAND
from gcode.commands.handlers.help import HELP_COMMAND
from gcode.commands.handlers.mcp import MCP_COMMAND
from gcode.commands.handlers.memory import MEMORY_COMMAND
from gcode.commands.handlers.permission import PERMISSION_COMMAND
from gcode.commands.handlers.plan import PLAN_COMMAND
from gcode.commands.handlers.do import DO_COMMAND
from gcode.commands.handlers.session import SESSION_COMMAND
from gcode.commands.handlers.skill import SKILL_COMMAND
from gcode.commands.handlers.rewind import REWIND_COMMAND
from gcode.commands.handlers.status import STATUS_COMMAND
from gcode.commands.registry import CommandRegistry


ALL_COMMANDS = [
    HELP_COMMAND,
    COMPACT_COMMAND,
    CLEAR_COMMAND,
    PLAN_COMMAND,
    DO_COMMAND,
    SESSION_COMMAND,
    MCP_COMMAND,
    MEMORY_COMMAND,
    PERMISSION_COMMAND,
    REWIND_COMMAND,
    STATUS_COMMAND,
    SKILL_COMMAND,
]


def register_all_commands(registry: CommandRegistry) -> None:
    for cmd in ALL_COMMANDS:
        registry.register_sync(cmd)
