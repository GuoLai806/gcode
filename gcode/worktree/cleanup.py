from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from gcode.worktree.changes import has_unpushed_commits, has_worktree_changes
from gcode.worktree.manager import WorktreeManager

log = logging.getLogger(__name__)

EPHEMERAL_PATTERNS = [
    re.compile(r"^agent-a[0-9a-f]{7}$"),
    re.compile(r"^wf_[0-9a-f]{8}-[0-9a-f]{3}-\d+$"),
    re.compile(r"^wf-\d+$"),
    re.compile(r"^bridge-[A-Za-z0-9_]+(-[A-Za-z0-9_]+)*$"),
    re.compile(r"^job-[a-zA-Z0-9._-]{1,55}-[0-9a-f]{8}$"),
]


def _is_ephemeral(name: str) -> bool:
    return any(p.match(name) for p in EPHEMERAL_PATTERNS)


async def cleanup_stale_worktrees(manager: WorktreeManager, cutoff_hours: int) -> int:
    # A timestamp is not evidence of ownership, inactivity, or disposable work.
    # Cleanup requires a reviewed, durable plan; until available preserve all.
    return 0


async def start_stale_cleanup_task(
    manager: WorktreeManager,
    interval: int,
    cutoff_hours: int,
) -> None:
    while True:
        await asyncio.sleep(interval)
        try:
            count = await cleanup_stale_worktrees(manager, cutoff_hours)
            if count:
                log.info("Stale worktree cleanup removed %d worktrees", count)
        except Exception as e:
            log.warning("Stale worktree cleanup error: %s", e)
