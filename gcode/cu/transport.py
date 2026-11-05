from __future__ import annotations

import asyncio
import json
import os
import signal
import uuid
from pathlib import Path
from typing import Any

MAX_REQUEST = 256 * 1024
MAX_RESPONSE = 2 * 1024 * 1024
WRITES = {"ax_action", "window_keyboard"}


class CUError(RuntimeError):
    def __init__(self, code: str, message: str, delivery_state: str = "not_dispatched"):
        super().__init__(message)
        self.code, self.delivery_state = code, delivery_state


class CUTransport:
    """One explicit subprocess, no retries. Caller retains action IDs across uncertainty."""

    def __init__(self, node: str, server: Path, provider: Path, state_dir: Path):
        for p in (server, provider, state_dir):
            if not p.is_absolute():
                raise ValueError(
                    "CU paths must be explicitly configured absolute paths"
                )
        self.node, self.server, self.provider, self.state_dir = (
            node,
            server,
            provider,
            state_dir,
        )
        self._proc: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()
        self._dead = False

    async def start(self) -> None:
        import os

        if self._proc or self._dead:
            raise CUError("TRANSPORT_CLOSED", "Transport cannot be restarted or reused")
        env = dict(
            os.environ,
            GCODE_CU_PROVIDER=str(self.provider),
            GCODE_CU_STATE_DIR=str(self.state_dir),
        )
        self._proc = await asyncio.create_subprocess_exec(
            self.node,
            str(self.server),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=None,
            env=env,
            limit=MAX_RESPONSE + 1,
            start_new_session=(os.name == "posix"),
        )

    async def call(
        self,
        method: str,
        params: dict[str, Any],
        *,
        run_id: str,
        session_id: str,
        timeout_ms: int = 10000,
        action_id: str | None = None,
        scope_epoch: int | None = None,
    ) -> dict[str, Any]:
        if not self._proc or self._dead or self._proc.returncode is not None:
            raise CUError("TRANSPORT_CLOSED", "Sidecar is not running")
        if method in WRITES and not action_id:
            raise ValueError("action_id is required for writes")
        request: dict[str, Any] = {
            "v": 1,
            "id": str(uuid.uuid4()),
            "run_id": run_id,
            "session_id": session_id,
            "method": method,
            "params": params,
            "timeout_ms": timeout_ms,
        }
        if action_id is not None:
            request["action_id"] = action_id
        if scope_epoch is not None:
            request["scope_epoch"] = scope_epoch
        raw = (
            json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode()
            + b"\n"
        )
        if len(raw) - 1 > MAX_REQUEST:
            raise CUError("FRAME_TOO_LARGE", "Request exceeds 256 KiB")
        async with self._lock:
            if self._dead:
                raise CUError("TRANSPORT_CLOSED", "Sidecar is no longer usable")
            try:
                assert self._proc.stdin and self._proc.stdout
                self._proc.stdin.write(raw)
                await self._proc.stdin.drain()
                line = await asyncio.wait_for(
                    self._proc.stdout.readline(), timeout_ms / 1000 + 2
                )
                if not line or len(line) - 1 > MAX_RESPONSE or not line.endswith(b"\n"):
                    raise ValueError("EOF or oversized response")
                result = json.loads(line)
                if (
                    not isinstance(result, dict)
                    or result.get("v") != 1
                    or result.get("id") != request["id"]
                    or not isinstance(result.get("ok"), bool)
                ):
                    raise ValueError("Invalid or uncorrelated response")
                return result
            except (Exception, asyncio.CancelledError) as exc:
                self._dead = True
                if self._proc.stdin:
                    self._proc.stdin.close()
                if isinstance(exc, asyncio.CancelledError):
                    raise
                state = "delivery_unknown" if method in WRITES else "not_dispatched"
                raise CUError("TRANSPORT_FAILURE", str(exc), state) from exc

    async def hello(self, run_id: str, session_id: str) -> dict[str, Any]:
        return await self.call("hello", {}, run_id=run_id, session_id=session_id)

    async def status(self, run_id: str, session_id: str) -> dict[str, Any]:
        return await self.call("status", {}, run_id=run_id, session_id=session_id)

    async def cancel(self, run_id: str, session_id: str) -> dict[str, Any]:
        if self._lock.locked():
            raise CUError(
                "CANCEL_UNCONFIRMED",
                "An active request may already have dispatched; cancellation is not confirmed",
                "delivery_unknown",
            )
        return await self.call("cancel", {}, run_id=run_id, session_id=session_id)

    async def shutdown(self, run_id: str, session_id: str) -> None:
        try:
            if self._proc and not self._dead and self._proc.returncode is None:
                await self.call(
                    "shutdown",
                    {},
                    run_id=run_id,
                    session_id=session_id,
                    timeout_ms=1000,
                )
        finally:
            self._dead = True
            cleanup = asyncio.create_task(self._stop_process())
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                await asyncio.shield(cleanup)
                raise

    async def _stop_process(self) -> None:
        proc = self._proc
        if not proc:
            return
        if proc.stdin:
            proc.stdin.close()
        for timeout, signal_name in ((1.0, "terminate"), (1.0, "kill"), (1.0, None)):
            try:
                await asyncio.wait_for(proc.wait(), timeout)
                # Even a cleanly exited sidecar can leave its own helpers alive.
                # The session was created solely for this transport. App launches
                # owned by the OS are outside it; no unrelated process is targeted.
                if os.name == "posix":
                    self._signal_group(signal.SIGTERM)
                    await asyncio.sleep(0.05)
                    self._signal_group(signal.SIGKILL)
                return
            except asyncio.TimeoutError:
                if signal_name is None:
                    raise CUError(
                        "SHUTDOWN_UNCONFIRMED",
                        "Sidecar exit was not confirmed",
                        "delivery_unknown",
                    )
                if os.name == "posix":
                    self._signal_group(
                        signal.SIGTERM if signal_name == "terminate" else signal.SIGKILL
                    )
                elif proc.returncode is None:
                    try:
                        getattr(proc, signal_name)()
                    except ProcessLookupError:
                        pass

    def _signal_group(self, sig: int) -> None:
        if self._proc:
            try:
                os.killpg(self._proc.pid, sig)
            except ProcessLookupError:
                pass
