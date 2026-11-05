"""Retain literal user paragraphs across lossy conversation compaction.

No keyword classifier can reliably identify every constraint or correction.
Keep all attributed user prose up to a fixed cap; refuse compaction over it.
This historical text does not itself grant new authorization.
"""

from __future__ import annotations
import re
from collections.abc import Iterable
from typing import Any

MAX_CONSTRAINT_CHARS = 30_000


class ConstraintLimitError(ValueError):
    """The complete ledger cannot fit; the caller must retain the original history."""


_EXCLUDED_TAGS = (
    r"system-reminder|tool[_-]result|environment|instructions|runtime|recovery"
)
_BLOCK = re.compile(
    rf"<({_EXCLUDED_TAGS})\b[^>]*>.*?</\1\s*>", re.IGNORECASE | re.DOTALL
)
_TAG = re.compile(rf"</?(?:{_EXCLUDED_TAGS})\b", re.IGNORECASE)
_LEGACY_SUMMARY_PREFIXES = (
    "本次会话延续自之前的对话，因上下文空间不足进行了压缩。以下是早期对话的摘要：",
    "This session is being continued from a previous conversation that ran out of context.",
)


def _validated_add(output: list[str], seen: set[str], entry: str, size: int) -> int:
    if not isinstance(entry, str):
        raise TypeError("preserved constraints must be strings")
    if not entry:
        return size
    if entry in seen:
        # Keep the LAST occurrence: A -> B -> A must render B -> A, so a
        # repeated revocation cannot disappear behind an earlier permission.
        output.remove(entry)
        output.append(entry)
        return size
    size += len(entry)
    if size > MAX_CONSTRAINT_CHARS:
        raise ConstraintLimitError(
            "user constraints exceed 30000 characters; preserve original history"
        )
    seen.add(entry)
    output.append(entry)
    return size


def collect_constraints(history: Iterable[Any]) -> list[str]:
    """Return ordered attributed user paragraphs without mutating history."""
    result: list[str] = []
    seen: set[str] = set()
    size = 0
    for message in history:
        previous = getattr(message, "preserved_constraints", None) or []
        if not isinstance(previous, (list, tuple)):
            raise TypeError("preserved_constraints must be a list of strings")
        for entry in previous:
            size = _validated_add(result, seen, entry, size)
        if getattr(message, "role", None) != "user" or getattr(
            message, "origin", ""
        ) not in ("", "user"):
            continue
        if getattr(message, "tool_results", None) or getattr(
            message, "tool_uses", None
        ):
            continue
        content = getattr(message, "content", "")
        if not isinstance(content, str):
            continue
        if getattr(message, "origin", "") != "user" and content.lstrip().startswith(
            _LEGACY_SUMMARY_PREFIXES
        ):
            continue
        # Provenance, not tag spelling, determines the source. Modern runtime,
        # tool and instruction messages already have distinct origins above.
        # An attributed user may legitimately paste XML, including a literal
        # <INSTRUCTIONS> block; retain it as historical quoted user text.
        # Legacy origin-less messages can contain synthetic runtime fragments,
        # so keep the conservative fallback only for that ambiguous format.
        if getattr(message, "origin", "") != "user":
            content = _BLOCK.sub("", content)
            if _TAG.search(content):
                continue
        for paragraph in re.split(r"\r?\n[ \t]*\r?\n+", content):
            paragraph = paragraph.strip()
            if paragraph:
                size = _validated_add(result, seen, paragraph, size)
    return result


def render_constraints(constraints: Iterable[str]) -> str:
    """Label historical text without converting it into fresh authorization."""
    result: list[str] = []
    seen: set[str] = set()
    size = 0
    for entry in constraints:
        size = _validated_add(result, seen, entry, size)
    if not result:
        return ""
    lines = ["历史用户原文与更正（原文；不构成新的授权）："]
    for index, entry in enumerate(result, 1):
        lines.append(f"[{index}] {entry}")
    return "\n\n".join(lines)
