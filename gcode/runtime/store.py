"""Durable, transactional primitives for runs, leases and messages.

A claimed message is not proof that an external effect happened. Expired claims
are available for inspection/recovery, never automatically re-dispatched.
"""

from __future__ import annotations
import json
import sqlite3
import time
import uuid
from pathlib import Path


class ConflictError(RuntimeError):
    pass


class _ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


class RunStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, idempotency_key TEXT UNIQUE NOT NULL, spec TEXT NOT NULL, state TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0, result TEXT);
                CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, event TEXT NOT NULL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS leases(name TEXT PRIMARY KEY, owner TEXT NOT NULL, expires REAL NOT NULL, revision INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS spawn_scopes(scope TEXT PRIMARY KEY, count INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS spawn_reservations(id TEXT PRIMARY KEY, scope TEXT NOT NULL, state TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS messages(recipient TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending', owner TEXT, expires REAL, PRIMARY KEY(recipient,id));
                PRAGMA user_version=1;
            """)
            columns = {row[1] for row in db.execute("PRAGMA table_info(runs)")}
            for name, sql_type in (
                ("stop_reason", "TEXT"),
                ("process_state", "TEXT"),
                ("heartbeat", "REAL"),
                ("owner", "TEXT"),
            ):
                if name not in columns:
                    try:
                        db.execute(f"ALTER TABLE runs ADD COLUMN {name} {sql_type}")
                    except sqlite3.OperationalError as exc:
                        if "duplicate column" not in str(exc):
                            raise

    def connect(self):
        db = sqlite3.connect(
            self.path, timeout=30, isolation_level=None, factory=_ClosingConnection
        )
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=30000")
        deadline = time.monotonic() + 30
        while True:
            try:
                db.execute("PRAGMA journal_mode=WAL")
                break
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower() or time.monotonic() >= deadline:
                    db.close()
                    raise
                time.sleep(0.02)
        return db

    def create_or_get(
        self, idempotency_key, spec, max_active=None, scope=None, max_spawns=None
    ):
        payload = json.dumps(spec, sort_keys=True, ensure_ascii=False)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT 1 FROM runs WHERE idempotency_key=?", (idempotency_key,)
            ).fetchone()
            if not existing and max_active is not None:
                count = db.execute(
                    "SELECT count(*) FROM runs WHERE state IN ('pending','running','idle','cancellation_requested')"
                ).fetchone()[0]
                if count >= max_active:
                    db.rollback()
                    raise RuntimeError(
                        "task concurrency limit reached, including unknown prior runs"
                    )
            if not existing and scope is not None and max_spawns is not None:
                used = db.execute(
                    "SELECT count FROM spawn_scopes WHERE scope=?", (scope,)
                ).fetchone()
                if used and used[0] >= max_spawns:
                    db.rollback()
                    raise RuntimeError("task spawn limit reached for scope")
                db.execute(
                    "INSERT INTO spawn_scopes(scope,count) VALUES(?,1) ON CONFLICT(scope) DO UPDATE SET count=count+1",
                    (scope,),
                )
            inserted = (
                db.execute(
                    "INSERT OR IGNORE INTO runs(id,idempotency_key,spec,state) VALUES(?,?,?,?)",
                    (uuid.uuid4().hex, idempotency_key, payload, "pending"),
                ).rowcount
                == 1
            )
            row = db.execute(
                "SELECT * FROM runs WHERE idempotency_key=?", (idempotency_key,)
            ).fetchone()
            if row["spec"] != payload:
                db.rollback()
                raise ConflictError("idempotency key reused with different spec")
            db.commit()
            result = dict(row)
            result["_created"] = inserted
            return result

    def get(self, run_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            return dict(row) if row else None

    def list_runs(self):
        with self.connect() as db:
            return [
                dict(row) for row in db.execute("SELECT * FROM runs ORDER BY rowid")
            ]

    def transition(self, run_id, expected_revision, transition):
        state = transition["state"]
        result = transition.get("result")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute(
                "SELECT revision FROM runs WHERE id=?", (run_id,)
            ).fetchone()
            if current is None or current[0] != expected_revision:
                db.rollback()
                raise ConflictError("stale or missing run")
            if state == "completed" and result is None:
                db.rollback()
                raise ValueError("completed run requires a durable result")
            cur = db.execute(
                "UPDATE runs SET state=?,result=?,stop_reason=?,process_state=?,owner=COALESCE(?,owner),heartbeat=COALESCE(?,heartbeat),revision=revision+1 WHERE id=? AND revision=?",
                (
                    state,
                    result,
                    transition.get("stop_reason"),
                    transition.get("process_state", "unknown"),
                    transition.get("owner"),
                    transition.get("heartbeat"),
                    run_id,
                    expected_revision,
                ),
            )
            if cur.rowcount != 1:
                db.rollback()
                raise ConflictError("stale or missing run")
            db.execute(
                "INSERT INTO events(run_id,event,created) VALUES(?,?,?)",
                (run_id, json.dumps(transition, ensure_ascii=False), time.time()),
            )
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            db.commit()
            return dict(row)

    def reserve_spawn(self, scope, max_spawns, max_concurrent):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            used = db.execute(
                "SELECT count FROM spawn_scopes WHERE scope=?", (scope,)
            ).fetchone()
            if used and used[0] >= max_spawns:
                db.rollback()
                raise RuntimeError("task spawn limit reached for scope")
            active = db.execute(
                "SELECT count(*) FROM spawn_reservations WHERE scope=? AND state='active'",
                (scope,),
            ).fetchone()[0]
            if max_concurrent is not None and active >= max_concurrent:
                db.rollback()
                raise RuntimeError("spawn concurrency limit reached")
            reservation = uuid.uuid4().hex
            db.execute(
                "INSERT INTO spawn_scopes(scope,count) VALUES(?,1) ON CONFLICT(scope) DO UPDATE SET count=count+1",
                (scope,),
            )
            db.execute(
                "INSERT INTO spawn_reservations VALUES(?,?,'active')",
                (reservation, scope),
            )
            db.commit()
            return reservation

    def release_spawn(self, scope, reservation):
        with self.connect() as db:
            return (
                db.execute(
                    "UPDATE spawn_reservations SET state='released' WHERE scope=? AND id=? AND state='active'",
                    (scope, reservation),
                ).rowcount
                == 1
            )

    def heartbeat(self, run_id, owner):
        with self.connect() as db:
            return (
                db.execute(
                    "UPDATE runs SET heartbeat=? WHERE id=? AND owner=? AND state IN ('running','idle','cancellation_requested','completed')",
                    (time.time(), run_id, owner),
                ).rowcount
                == 1
            )

    def acquire_lease(self, name, owner, ttl):
        if ttl <= 0:
            raise ValueError("ttl must be positive")
        now = time.time()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM leases WHERE name=?", (name,)).fetchone()
            if row and row["expires"] > now and row["owner"] != owner:
                db.rollback()
                return False
            db.execute(
                "INSERT INTO leases VALUES(?,?,?,0) ON CONFLICT(name) DO UPDATE SET owner=excluded.owner, expires=excluded.expires, revision=leases.revision+1",
                (name, owner, now + ttl),
            )
            db.commit()
            return True

    def release_lease(self, name, owner):
        with self.connect() as db:
            return (
                db.execute(
                    "DELETE FROM leases WHERE name=? AND owner=?", (name, owner)
                ).rowcount
                == 1
            )
