from __future__ import annotations
import hashlib
import os
import threading
from pathlib import Path


def _signature(stat):
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def read_stable(path: str | Path):
    """Read a stable file snapshot and confirm the path still names that inode."""
    path = Path(path)
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        data = stream.read()
        after = os.fstat(stream.fileno())
    current = path.stat()
    if (
        _signature(before) != _signature(after)
        or _signature(after) != _signature(current)
        or len(data) != after.st_size
    ):
        raise OSError("file changed while being read; retry")
    # Match the universal-newline behavior of Path.read_text().
    text = data.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return text, after, hashlib.sha256(data).hexdigest()


class FileCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[str, tuple | None, str | None]] = {}
        self._lock = threading.Lock()

    def get(self, path: str) -> str | None:
        with self._lock:
            entry = self._store.get(path)
        if entry is None:
            return None
        content, signature, digest = entry
        if signature is None:
            # Preserve the legacy in-memory API for values not backed by a file.
            return content if not Path(path).exists() else None
        try:
            text, current, current_digest = read_stable(path)
        except (OSError, UnicodeError):
            self.invalidate(path)
            return None
        if (
            _signature(current) != signature
            or current_digest != digest
            or text != content
        ):
            self.invalidate(path)
            return None
        return content

    def put(self, path: str, content: str) -> None:
        try:
            text, current, digest = read_stable(path)
            if text != content:
                self.invalidate(path)
                return
            entry = (content, _signature(current), digest)
        except (OSError, UnicodeError):
            entry = (content, None, None)
        with self._lock:
            self._store[path] = entry

    def put_snapshot(self, path: str, content: str, stat, digest: str) -> None:
        with self._lock:
            self._store[path] = (content, _signature(stat), digest)

    def invalidate(self, path: str) -> None:
        with self._lock:
            self._store.pop(path, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)
