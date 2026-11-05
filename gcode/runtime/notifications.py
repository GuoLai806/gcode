"""Durable notification records written before delivery ACK."""

from __future__ import annotations
import hashlib
import time
from gcode.runtime.store import RunStore
from gcode.runtime.tool_ledger import _prepare_private_db


class NotificationStore:
    def __init__(self, path):
        _prepare_private_db(path)
        self.store = RunStore(path)
        with self.store.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS durable_notifications(
                scope TEXT NOT NULL, id TEXT NOT NULL, text TEXT NOT NULL, created REAL NOT NULL,
                PRIMARY KEY(scope,id))""")

    def put(self, scope, note):
        if not isinstance(scope, str) or not scope or not isinstance(note, str):
            raise ValueError("scope and text required")
        identifier = hashlib.sha256(note.encode("utf-8")).hexdigest()
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT text FROM durable_notifications WHERE scope=? AND id=?",
                (scope, identifier),
            ).fetchone()
            if row and row[0] != note:
                db.rollback()
                raise ValueError("notification id collision")
            db.execute(
                "INSERT OR IGNORE INTO durable_notifications VALUES(?,?,?,?)",
                (scope, identifier, note, time.time()),
            )
            db.commit()
        return identifier

    def list(self, scope):
        with self.store.connect() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT id,text,created FROM durable_notifications WHERE scope=? ORDER BY created,id",
                    (scope,),
                )
            ]
