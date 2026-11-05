from __future__ import annotations
import threading
from pathlib import Path
from gcode.cache import read_stable
from gcode.runtime.context import current_tool_context


class FileStateCache:
    """Read-before-write snapshots are isolated by run and verified by content."""

    def __init__(self) -> None:
        self._cache: dict[tuple[bool, str, str], tuple[int, str]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _key(path):
        context = current_tool_context()
        return (
            context is None,
            context.run_id if context else "",
            str(Path(path).resolve()),
        )

    def record_snapshot(
        self, path: str, content: str, mtime_ns: int, raw_hash: str
    ) -> None:
        with self._lock:
            self._cache[self._key(path)] = (mtime_ns, raw_hash)

    def record(self, path: str, content: str, mtime_ns: int) -> None:
        # Legacy caller: obtain and verify the bytes before authorizing edits.
        try:
            text, current, raw_hash = read_stable(path)
            if text != content or current.st_mtime_ns != mtime_ns:
                raise OSError("snapshot changed")
            self.record_snapshot(path, content, mtime_ns, raw_hash)
        except (OSError, UnicodeError):
            with self._lock:
                self._cache.pop(self._key(path), None)

    def check(self, path: str) -> tuple[bool, str]:
        with self._lock:
            entry = self._cache.get(self._key(path))
        if entry is None:
            return (
                False,
                "Error: file has not been read yet. Read it first before editing.",
            )
        try:
            _, current, raw_hash = read_stable(path)
        except (OSError, UnicodeError):
            return (
                False,
                "Error: file is missing or changed while checking. Read it again before editing.",
            )
        if current.st_mtime_ns != entry[0] or raw_hash != entry[1]:
            return (
                False,
                "Error: file has been modified since last read. Read it again before editing.",
            )
        return True, ""

    def update(self, path: str) -> None:
        try:
            content, current, raw_hash = read_stable(path)
            self.record_snapshot(path, content, current.st_mtime_ns, raw_hash)
        except (OSError, UnicodeError):
            with self._lock:
                self._cache.pop(self._key(path), None)
