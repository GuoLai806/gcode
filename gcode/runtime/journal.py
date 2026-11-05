"""Atomic run checkpoints, separate from the append-only user transcript."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from gcode.conversation import (
    ConversationManager,
    Message,
    ToolResultBlock,
    ToolUseBlock,
    ThinkingBlock,
)


def save_checkpoint(
    path: Path, conversation: ConversationManager, **state: Any
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "messages": [asdict(message) for message in conversation.history],
        "env_injected": conversation.env_injected,
        "ltm_injected": conversation.ltm_injected,
        **state,
    }
    fd, temporary = tempfile.mkstemp(prefix=".checkpoint-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


def load_checkpoint(path: Path) -> tuple[ConversationManager, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("version") != 1:
        raise ValueError("Unsupported run checkpoint")
    messages = [
        Message(
            role=item["role"],
            content=item["content"],
            origin=item.get("origin", ""),
            preserved_constraints=item.get("preserved_constraints", []),
            notification_ids=item.get("notification_ids", []),
            tool_uses=[ToolUseBlock(**block) for block in item.get("tool_uses", [])],
            tool_results=[
                ToolResultBlock(**block) for block in item.get("tool_results", [])
            ],
            thinking_blocks=[
                ThinkingBlock(**block) for block in item.get("thinking_blocks", [])
            ],
        )
        for item in payload["messages"]
    ]
    conversation = ConversationManager(history=messages)
    conversation.env_injected = payload.get("env_injected", False)
    conversation.ltm_injected = payload.get("ltm_injected", False)
    conversation.repair_tool_chain()
    return conversation, {
        key: value
        for key, value in payload.items()
        if key not in {"messages", "version", "env_injected", "ltm_injected"}
    }


def recovery_state(ledger, scope: str, saved: dict[str, Any]) -> dict[str, Any]:
    """Resolve only durable completed receipts or explicit audited resolutions."""
    rows = {row["call_id"]: row for row in ledger.list(scope)}
    resolved = ledger.audit_resolved_ids(scope)
    pending = {
        identifier: category
        for identifier, category in saved.get("pending_calls", {}).items()
        if rows.get(identifier, {}).get("state") != "completed"
        and identifier not in resolved
    }
    recorded_unknown = set(saved.get("unknown_call_ids", []))
    unknown = (recorded_unknown | ledger.current_unknown_ids(scope)) - resolved
    unknown = {
        identifier
        for identifier in unknown
        if rows.get(identifier, {}).get("category") != "read"
    }
    unattributed = bool(saved.get("recovery_writes_stopped")) and not (
        recorded_unknown or saved.get("pending_calls")
    )
    return {
        "pending_calls": pending,
        "unknown_call_ids": sorted(unknown),
        "recovery_writes_stopped": unattributed
        or bool(unknown)
        or any(category != "read" for category in pending.values()),
    }
