from __future__ import annotations

import asyncio
import os
import re
import shlex
import signal
import subprocess
import tempfile
import uuid
from pathlib import Path

from pydantic import BaseModel, Field

from gcode.tools.base import Tool, ToolResult
from gcode.runtime.context import current_tool_context

MAX_TIMEOUT = 600

# 特殊命令的退出码语义映射
# 这些命令的 exit code 1 不代表错误，只有 >= 阈值才算真正的错误
# 例如 grep 返回 1 仅表示"没有匹配行"，不是执行出错
_COMMAND_ERROR_THRESHOLDS: dict[str, int] = {
    "grep": 2,  # exit 1 = 没有匹配到内容
    "egrep": 2,
    "fgrep": 2,
    "rg": 2,  # ripgrep，与 grep 语义一致
    "diff": 2,  # exit 1 = 文件内容有差异
    "find": 2,  # exit 1 = 部分成功（如权限不足跳过某些目录）
    "test": 2,  # exit 1 = 条件为假
    "[": 2,  # test 的别名形式
}


def _extract_last_command_name(command: str) -> str | None:
    """从命令字符串中提取最后一个管道段的基础命令名。

    管道中最后一个命令决定了整体退出码，所以只看最后一段。
    例如 "cat file | grep pattern" → "grep"
    """
    # 按管道符拆分，取最后一段
    last_segment = command.rsplit("|", maxsplit=1)[-1].strip()
    if not last_segment:
        return None

    # 跳过常见的环境变量赋值前缀，如 "FOO=bar command ..."
    # 也要处理 sudo/env 等包装命令
    try:
        tokens = shlex.split(last_segment)
    except ValueError:
        # shlex 解析失败时，用简单的空格分割兜底
        tokens = last_segment.split()

    for token in tokens:
        # 跳过形如 VAR=VALUE 的环境变量赋值
        if re.match(r"^[A-Za-z_]\w*=", token):
            continue
        # 取 basename（去掉路径前缀，如 /usr/bin/grep → grep）
        base = token.rsplit("/", maxsplit=1)[-1]
        return base

    return None


def _interpret_exit_code(command: str, exit_code: int) -> bool:
    """根据命令语义判断退出码是否代表真正的错误。

    返回 True 表示是错误，False 表示不是错误。
    """
    if exit_code == 0:
        return False

    cmd_name = _extract_last_command_name(command)
    if cmd_name and cmd_name in _COMMAND_ERROR_THRESHOLDS:
        # 只有退出码 >= 阈值时才视为错误
        return exit_code >= _COMMAND_ERROR_THRESHOLDS[cmd_name]

    # 默认行为：非零退出码即为错误
    return True


class Params(BaseModel):
    command: str = Field(description="Shell command to execute")
    timeout: int = Field(default=120, description="Timeout in seconds (max 600)")


class Bash(Tool):
    name = "Bash"
    description = "Execute a shell command and return stdout and stderr."
    params_model = Params
    category = "command"

    @staticmethod
    async def _pump(reader, capture):
        try:
            while True:
                chunk = await reader.read(65536)
                if not chunk:
                    break
                capture["spool"].write(chunk)
                capture["size"] += len(chunk)
                remaining = 10000 - len(capture["preview"])
                if remaining > 0:
                    capture["preview"].extend(chunk[:remaining])
        except BaseException:
            # Do not leave an unread pipe keeping a killed process unreaped.
            transport = getattr(reader, "_transport", None)
            if transport is not None:
                transport.close()
            raise

    async def _terminate_and_drain(self, proc, readers, waiter):
        await self._stop_process(proc)
        tasks = [task for task in [*readers, waiter] if task is not None]
        if tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True), timeout=3
                )
            except asyncio.TimeoutError:
                for reader in (proc.stdout, proc.stderr):
                    transport = getattr(reader, "_transport", None)
                    if transport is not None:
                        transport.close()
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

    async def execute(self, params: Params) -> ToolResult:
        timeout = min(params.timeout, MAX_TIMEOUT)
        context = current_tool_context()
        proc = None
        creation = None
        readers = []
        waiter = None
        monitor = None
        captures = []
        try:
            # Anonymous private spools are removed on close, including cancellation.
            for _ in range(2):
                captures.append(
                    {
                        "spool": tempfile.TemporaryFile(mode="w+b"),
                        "size": 0,
                        "preview": bytearray(),
                    }
                )
            options = (
                {"start_new_session": True}
                if os.name == "posix"
                else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
            )
            creation = asyncio.create_task(
                asyncio.create_subprocess_shell(
                    params.command,
                    cwd=str(context.cwd) if context else None,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    **options,
                )
            )
            proc = await asyncio.shield(creation)
            readers = [
                asyncio.create_task(self._pump(proc.stdout, captures[0])),
                asyncio.create_task(self._pump(proc.stderr, captures[1])),
            ]
            waiter = asyncio.create_task(proc.wait())
            monitor = asyncio.gather(waiter, *readers)
            await asyncio.wait_for(asyncio.shield(monitor), timeout=timeout)
            return self._result_from_captures(
                params, proc, captures, context, timed_out=False
            )
        except asyncio.TimeoutError:
            if proc is not None:
                cleanup = asyncio.create_task(
                    self._terminate_and_drain(proc, readers, waiter)
                )
                await self._finish_cleanup(cleanup)
            if monitor is not None:
                await asyncio.gather(monitor, return_exceptions=True)
            try:
                return self._result_from_captures(
                    params, proc, captures, context, timed_out=True
                )
            except Exception as exc:
                return ToolResult(
                    output=f"Error: command timed out; failed to persist captured output: {str(exc)[:1000]}",
                    is_error=True,
                    details={
                        "delivery_state": "delivery_unknown",
                        "process_state": "exited"
                        if proc and proc.returncode is not None
                        else "unknown",
                        "business_outcome": "unverified",
                    },
                )
        except asyncio.CancelledError:
            if proc is None and creation is not None:
                try:
                    proc = await self._finish_cleanup(creation)
                    readers = [
                        asyncio.create_task(self._pump(proc.stdout, captures[0])),
                        asyncio.create_task(self._pump(proc.stderr, captures[1])),
                    ]
                    waiter = asyncio.create_task(proc.wait())
                except Exception:
                    pass
            if proc is not None:
                cleanup = asyncio.create_task(
                    self._terminate_and_drain(proc, readers, waiter)
                )
                await self._finish_cleanup(cleanup)
            if monitor is not None:
                await self._finish_cleanup(
                    asyncio.ensure_future(
                        asyncio.gather(monitor, return_exceptions=True)
                    )
                )
            raise
        except Exception as exc:
            if proc is not None and (
                proc.returncode is None or any(not reader.done() for reader in readers)
            ):
                cleanup = asyncio.create_task(
                    self._terminate_and_drain(proc, readers, waiter)
                )
                await self._finish_cleanup(cleanup)
            if monitor is not None:
                await asyncio.gather(monitor, return_exceptions=True)
            return ToolResult(
                output=f"Error executing command or reading output: {str(exc)[:1000]}",
                is_error=True,
                details={
                    "delivery_state": "delivery_unknown" if proc else "not_dispatched",
                    "process_state": "exited"
                    if proc and proc.returncode is not None
                    else "unknown",
                    "business_outcome": "unverified",
                },
            )
        finally:
            for capture in captures:
                capture["spool"].close()

    @staticmethod
    def _result_from_captures(params, proc, captures, context, timed_out):
        from gcode.runtime.artifacts import ArtifactStore

        stdout, stderr = captures
        labels = ("STDOUT", "STDERR")
        parts = [
            f"{label}:\n{bytes(item['preview']).decode(errors='replace')}"
            for label, item in zip(labels, captures)
            if item["size"]
        ]
        rendered = "\n".join(parts) if parts else "(no output)"
        large = sum(item["size"] for item in captures) > 10000 or len(rendered) > 10000
        artifacts = []
        if large:
            base = (
                Path(context.artifact_dir)
                if context
                else Path(tempfile.mkdtemp(prefix="gcode-bash-artifacts-"))
            )
            store = ArtifactStore(base)
            call_id = getattr(context, "tool_call_id", None) if context else None
            call_id = call_id or uuid.uuid4().hex
            for label, item in zip(labels, captures):
                if item["size"]:
                    item["spool"].flush()
                    item["spool"].seek(0)
                    record = store.put_stream(
                        item["spool"],
                        mime="application/octet-stream",
                        source_tool_call_id=f"{call_id}:{label.lower()}",
                    )
                    artifacts.append(
                        {"stream": label.lower(), **record, "complete": not timed_out}
                    )
            suffix = (
                "\n[Output truncated; full captured streams are stored as artifacts.]"
            )
            nonempty = [
                (label, item) for label, item in zip(labels, captures) if item["size"]
            ]
            share = max(0, (10000 - len(suffix) - 32) // len(nonempty))
            rendered = (
                "\n".join(
                    f"{label}:\n{bytes(item['preview'][:share]).decode(errors='replace')}"
                    for label, item in nonempty
                )
                + suffix
            )
            rendered = rendered[:10000]
        details = {
            "process_state": "exited"
            if proc and proc.returncode is not None
            else "unknown",
            "exit_code": proc.returncode if proc else None,
            "delivery_state": "delivery_unknown" if timed_out else "delivered",
            "business_outcome": "unverified",
            "stdout_bytes": stdout["size"],
            "stderr_bytes": stderr["size"],
            "artifacts": artifacts,
        }
        if timed_out:
            rendered = (
                f"Error: command timed out after {min(params.timeout, MAX_TIMEOUT)}s\n"
                + rendered
            )
            rendered = rendered[:10000]
        return ToolResult(
            output=rendered,
            is_error=timed_out
            or _interpret_exit_code(params.command, proc.returncode or 0),
            details=details,
        )

    @staticmethod
    async def _finish_cleanup(task: asyncio.Task):
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
        return task.result()

    @staticmethod
    async def _stop_process(proc: asyncio.subprocess.Process) -> None:
        """Stop only the owned process group; readers drain pipes separately."""
        if os.name == "posix":
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(proc.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pass
            finally:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        else:
            if proc.returncode is None:
                killer = await asyncio.create_subprocess_exec(
                    "taskkill",
                    "/PID",
                    str(proc.pid),
                    "/T",
                    "/F",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                try:
                    await asyncio.wait_for(killer.wait(), timeout=3.0)
                except asyncio.TimeoutError:
                    killer.kill()
                    await killer.wait()
                if proc.returncode is None:
                    try:
                        proc.kill()
                    except ProcessLookupError:
                        pass
        await asyncio.wait_for(proc.wait(), timeout=3.0)
