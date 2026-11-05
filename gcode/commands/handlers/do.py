"""An explicit user command to leave the read-only planning mode."""

from gcode.commands.registry import Command, CommandContext, CommandType


async def handle_do(ctx: CommandContext) -> None:
    ctx.ui.set_plan_mode(False)
    ctx.ui.add_system_message("已切换到执行模式，仍按当前执行权限检查工具")
    if ctx.args:
        ctx.ui.send_user_message(ctx.args)


DO_COMMAND = Command(
    name="do",
    description="退出只读计划模式",
    usage="/do [任务]",
    type=CommandType.LOCAL_UI,
    handler=handle_do,
)
