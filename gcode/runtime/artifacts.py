"""Per-session, content-addressed artifacts with durable reference tracking.

Garbage collection is a dry-run only. Existing corrupt or unknown content is
never overwritten or deleted automatically.
"""

from __future__ import annotations
import hashlib
import os
import re
import stat
import tempfile
import time
from pathlib import Path
from gcode.runtime.store import RunStore
from gcode.runtime.tool_ledger import _prepare_private_db

_ID = re.compile(r"^[0-9a-f]{64}$")


class ArtifactStore:
    def __init__(self, directory):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._root = directory.resolve() / "artifact-store"
        if self._root.is_symlink():
            raise ValueError("artifact store cannot be a symlink")
        self._root.mkdir(exist_ok=True, mode=0o700)
        if self._root.stat().st_mode & 0o077:
            raise PermissionError("artifact store directory must be private")
        self._objects = self._root / "objects"
        if self._objects.is_symlink():
            raise ValueError("artifact object directory cannot be a symlink")
        self._objects.mkdir(exist_ok=True, mode=0o700)
        if self._objects.stat().st_mode & 0o077:
            raise PermissionError("artifact object directory must be private")
        db_path = self._root / "index.sqlite3"
        if db_path.is_symlink():
            raise ValueError("artifact index cannot be a symlink")
        _prepare_private_db(db_path)
        self._db = RunStore(db_path)
        with self._db.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY, size INTEGER NOT NULL, mime TEXT NOT NULL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS artifact_media(id TEXT NOT NULL, mime TEXT NOT NULL, PRIMARY KEY(id,mime));
                CREATE TABLE IF NOT EXISTS artifact_references(id TEXT NOT NULL, owner TEXT NOT NULL, reference TEXT NOT NULL, PRIMARY KEY(id,owner,reference));
                CREATE TABLE IF NOT EXISTS artifact_calls(call_id TEXT PRIMARY KEY, id TEXT NOT NULL);
            """)

    @staticmethod
    def _validate_id(artifact_id):
        if not isinstance(artifact_id, str) or not _ID.fullmatch(artifact_id):
            raise ValueError("invalid artifact id")

    def _read_object(self, artifact_id):
        self._validate_id(artifact_id)
        path = self._objects / artifact_id
        if not hasattr(os, "O_NOFOLLOW"):
            raise OSError("safe no-follow file access is unavailable")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ValueError("artifact object is not a regular file")
            with os.fdopen(fd, "rb") as stream:
                fd = -1
                data = stream.read()
        finally:
            if fd != -1:
                os.close(fd)
        if hashlib.sha256(data).hexdigest() != artifact_id:
            raise ValueError("artifact hash mismatch")
        return data

    def _record(self, row):
        return {
            "artifact_id": row["id"],
            "path": str((self._objects / row["id"]).absolute()),
            "size": row["size"],
            "mime": row["mime"],
        }

    def _verify_object(self, artifact_id, expected_size=None):
        self._validate_id(artifact_id)
        if not hasattr(os, "O_NOFOLLOW"):
            raise OSError("safe no-follow file access is unavailable")
        fd = os.open(self._objects / artifact_id, os.O_RDONLY | os.O_NOFOLLOW)
        digest = hashlib.sha256()
        size = 0
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ValueError("artifact object is not a regular file")
            with os.fdopen(fd, "rb") as stream:
                fd = -1
                while True:
                    chunk = stream.read(65536)
                    if not chunk:
                        break
                    digest.update(chunk)
                    size += len(chunk)
        finally:
            if fd != -1:
                os.close(fd)
        if digest.hexdigest() != artifact_id:
            raise ValueError("artifact hash mismatch")
        if expected_size is not None and size != expected_size:
            raise ValueError("artifact size mismatch")
        return size

    def put(self, text_or_bytes, mime="text/plain", source_tool_call_id=None):
        import io

        if isinstance(text_or_bytes, str):
            data = text_or_bytes.encode("utf-8")
        elif isinstance(text_or_bytes, bytes):
            data = text_or_bytes
        else:
            raise TypeError("artifact must be str or bytes")
        return self.put_stream(io.BytesIO(data), mime, source_tool_call_id)

    def put_file(self, path, mime="application/octet-stream", source_tool_call_id=None):
        if not hasattr(os, "O_NOFOLLOW"):
            raise OSError("safe no-follow file access is unavailable")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode):
                raise ValueError("source is not a regular file")
            with os.fdopen(fd, "rb") as stream:
                fd = -1
                # Read into the pending object, but do not bind it until a stable
                # source snapshot is checked. The spool is private and closed by caller.
                result = self.put_stream(stream, mime, None)
                after = os.fstat(stream.fileno())
            current = os.stat(path, follow_symlinks=False)
            sig = lambda x: (
                x.st_dev,
                x.st_ino,
                x.st_size,
                x.st_mtime_ns,
                x.st_ctime_ns,
            )
            if sig(before) != sig(after) or sig(after) != sig(current):
                raise ValueError("source changed while importing")
            if source_tool_call_id is not None:
                self.bind_call(source_tool_call_id, result["artifact_id"])
            return result
        finally:
            if fd != -1:
                os.close(fd)

    def put_stream(
        self, source, mime="application/octet-stream", source_tool_call_id=None
    ):
        if not isinstance(mime, str) or not mime.strip():
            raise ValueError("mime must be non-empty")
        if source_tool_call_id is not None and (
            not isinstance(source_tool_call_id, str) or not source_tool_call_id
        ):
            raise ValueError("call id must be non-empty")
        fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=self._objects)
        digest = hashlib.sha256()
        size = 0
        try:
            with os.fdopen(fd, "wb") as stream:
                while True:
                    chunk = source.read(65536)
                    if not isinstance(chunk, bytes):
                        raise TypeError("source stream must yield bytes")
                    if not chunk:
                        break
                    if len(chunk) > 65536:
                        raise ValueError("source stream exceeded requested chunk size")
                    digest.update(chunk)
                    size += len(chunk)
                    stream.write(chunk)
                stream.flush()
                os.fsync(stream.fileno())
            artifact_id = digest.hexdigest()
            try:
                os.link(temporary, self._objects / artifact_id)
                dir_fd = os.open(self._objects, os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except FileExistsError:
                self._verify_object(artifact_id, size)
            with self._db.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT * FROM artifacts WHERE id=?", (artifact_id,)
                ).fetchone()
                if row and row["size"] != size:
                    db.rollback()
                    raise ValueError("conflicting immutable artifact size")
                db.execute(
                    "INSERT OR IGNORE INTO artifacts VALUES(?,?,?,?)",
                    (artifact_id, size, mime, time.time()),
                )
                db.execute(
                    "INSERT OR IGNORE INTO artifact_media VALUES(?,?)",
                    (artifact_id, mime),
                )
                if source_tool_call_id is not None:
                    prior = db.execute(
                        "SELECT id FROM artifact_calls WHERE call_id=?",
                        (source_tool_call_id,),
                    ).fetchone()
                    if prior and prior["id"] != artifact_id:
                        db.rollback()
                        raise ValueError(
                            "tool call already bound to different artifact"
                        )
                    db.execute(
                        "INSERT OR IGNORE INTO artifact_calls VALUES(?,?)",
                        (source_tool_call_id, artifact_id),
                    )
                row = db.execute(
                    "SELECT * FROM artifacts WHERE id=?", (artifact_id,)
                ).fetchone()
                record = self._record(row)
                record["mime"] = mime
                db.commit()
                return record
        finally:
            Path(temporary).unlink(missing_ok=True)

    def get(self, artifact_id):
        self._validate_id(artifact_id)
        with self._db.connect() as db:
            row = db.execute(
                "SELECT size FROM artifacts WHERE id=?", (artifact_id,)
            ).fetchone()
        if row is None:
            raise KeyError("artifact not found")
        data = self._read_object(artifact_id)
        if len(data) != row["size"]:
            raise ValueError("artifact size mismatch")
        return data

    def _assert_registered(self, artifact_id):
        self._validate_id(artifact_id)
        with self._db.connect() as db:
            row = db.execute(
                "SELECT size FROM artifacts WHERE id=?", (artifact_id,)
            ).fetchone()
        if row is None:
            raise KeyError("artifact not found")
        self._verify_object(artifact_id, row["size"])

    def bind_call(self, call_id, artifact_id):
        self._validate_id(artifact_id)
        if not isinstance(call_id, str) or not call_id:
            raise ValueError("call id must be non-empty")
        self._assert_registered(artifact_id)
        with self._db.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute(
                "SELECT id FROM artifact_calls WHERE call_id=?", (call_id,)
            ).fetchone()
            if prior and prior["id"] != artifact_id:
                db.rollback()
                raise ValueError("tool call already bound to different artifact")
            db.execute(
                "INSERT OR IGNORE INTO artifact_calls VALUES(?,?)",
                (call_id, artifact_id),
            )
            db.commit()
        return artifact_id

    def retain(self, artifact_id, owner, reference):
        self._validate_id(artifact_id)
        if not all(isinstance(x, str) and x for x in (owner, reference)):
            raise ValueError("owner and reference are required")
        self._assert_registered(artifact_id)
        with self._db.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO artifact_references VALUES(?,?,?)",
                (artifact_id, owner, reference),
            )

    def release(self, artifact_id, owner, reference):
        self._validate_id(artifact_id)
        if not all(isinstance(x, str) and x for x in (owner, reference)):
            raise ValueError("owner and reference are required")
        with self._db.connect() as db:
            return (
                db.execute(
                    "DELETE FROM artifact_references WHERE id=? AND owner=? AND reference=?",
                    (artifact_id, owner, reference),
                ).rowcount
                == 1
            )

    def plan_gc(self):
        with self._db.connect() as db:
            rows = db.execute("""SELECT a.* FROM artifacts a WHERE NOT EXISTS
                                 (SELECT 1 FROM artifact_references r WHERE r.id=a.id)
                                 AND NOT EXISTS (SELECT 1 FROM artifact_calls c WHERE c.id=a.id) ORDER BY a.created,a.id""").fetchall()
        for row in rows:
            self._verify_object(row["id"], row["size"])  # Fail closed on corruption.
        return [self._record(row) for row in rows]
