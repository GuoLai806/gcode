"""Shared parent/child spawn quota, independent of process isolation claims."""

from __future__ import annotations
import threading
import uuid


class SpawnBudget:
    def __init__(self, scope, store=None, max_spawns=32, max_concurrent=4, max_depth=2):
        self.scope, self.store = scope, store
        self.max_spawns, self.max_concurrent, self.max_depth = (
            max_spawns,
            max_concurrent,
            max_depth,
        )
        self._lock = threading.Lock()
        self._count = 0
        self._active = set()

    def reserve(self, depth):
        if depth < 1 or depth > self.max_depth:
            raise RuntimeError("child depth limit reached")
        if self.store:
            return self.store.reserve_spawn(
                self.scope, self.max_spawns, self.max_concurrent
            )
        with self._lock:
            if self._count >= self.max_spawns:
                raise RuntimeError("child spawn limit reached")
            if (
                self.max_concurrent is not None
                and len(self._active) >= self.max_concurrent
            ):
                raise RuntimeError("child concurrency limit reached")
            key = uuid.uuid4().hex
            self._count += 1
            self._active.add(key)
            return key

    def release(self, key):
        if self.store:
            return self.store.release_spawn(self.scope, key)
        with self._lock:
            if key not in self._active:
                return False
            self._active.remove(key)
            return True
