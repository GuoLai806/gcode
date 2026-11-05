"""Durable tool receipts and explicit, audited reconciliation; never replay."""

from __future__ import annotations
import hashlib
import json
import os
import re
import time
from dataclasses import asdict
from pathlib import Path
from gcode.runtime.store import RunStore
from gcode.tools.base import ToolResult


def _prepare_private_db(path):
    """Create new paths private without changing an existing path's permissions."""
    path = Path(path)
    missing = []
    parent = path.parent
    while not parent.exists():
        missing.append(parent)
        if parent == parent.parent:
            raise ValueError("invalid database path")
        parent = parent.parent
    for directory in reversed(missing):
        try:
            directory.mkdir(mode=0o700)
        except FileExistsError:
            pass
    if path.exists():
        return
    parent_stat = path.parent.stat()
    if parent_stat.st_mode & 0o077:
        # Tighten the application's dedicated runtime directory only; never change
        # permissions of an unrelated pre-existing user directory.
        if (
            path.parent.name == "runtime"
            and path.parent.parent.name == ".gcode"
            and not path.parent.is_symlink()
            and parent_stat.st_uid == os.geteuid()
        ):
            os.chmod(path.parent, 0o700)
        else:
            raise PermissionError(
                "new ledger database requires a private parent directory"
            )
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return
    os.close(fd)


class ToolLedger:
    def __init__(self, path):
        _prepare_private_db(path)
        self.store = RunStore(path)
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("""CREATE TABLE IF NOT EXISTS tool_calls(
                scope TEXT NOT NULL, call_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
                category TEXT NOT NULL, state TEXT NOT NULL, result TEXT,
                tool_name TEXT, arguments_json TEXT, created REAL, revision INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(scope,call_id))""")
            columns = {row[1] for row in db.execute("PRAGMA table_info(tool_calls)")}
            for name, kind in (
                ("tool_name", "TEXT"),
                ("arguments_json", "TEXT"),
                ("created", "REAL"),
                ("revision", "INTEGER NOT NULL DEFAULT 0"),
            ):
                if name not in columns:
                    db.execute(f"ALTER TABLE tool_calls ADD COLUMN {name} {kind}")
            db.execute("""CREATE TABLE IF NOT EXISTS tool_reconciliations(
                scope TEXT NOT NULL, evidence_id TEXT NOT NULL, call_id TEXT NOT NULL,
                evidence_json TEXT NOT NULL, resolved_revision INTEGER NOT NULL, created REAL NOT NULL,
                PRIMARY KEY(scope,evidence_id))""")
            db.commit()

    def begin(self, scope, call_id, tool_name, arguments, category):
        fingerprint = hashlib.sha256(
            json.dumps(
                [tool_name, arguments], sort_keys=True, ensure_ascii=False
            ).encode()
        ).hexdigest()
        arguments_json = json.dumps(arguments, sort_keys=True, ensure_ascii=False)
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM tool_calls WHERE scope=? AND call_id=?", (scope, call_id)
            ).fetchone()
            if row:
                if row["fingerprint"] != fingerprint:
                    raise ValueError(
                        "Tool call ID reused with different tool or arguments"
                    )
                if row["state"] == "completed" and row["result"]:
                    return ToolResult(**json.loads(row["result"]))
                return ToolResult(
                    "Prior invocation outcome is unknown; do not replay this tool call",
                    True,
                    {"delivery_state": "delivery_unknown", "tool_call_id": call_id},
                )
            db.execute(
                """INSERT INTO tool_calls(scope,call_id,fingerprint,category,state,result,tool_name,arguments_json,created,revision)
                          VALUES(?,?,?,?,?,NULL,?,?,?,0)""",
                (
                    scope,
                    call_id,
                    fingerprint,
                    category,
                    "dispatching",
                    tool_name,
                    arguments_json,
                    time.time(),
                ),
            )
        return None

    def finish(self, scope, call_id, result):
        state = (
            "unknown"
            if (result.details or {}).get("delivery_state") == "delivery_unknown"
            else "completed"
        )
        payload = json.dumps(asdict(result), ensure_ascii=False)
        with self.store.connect() as db:
            changed = db.execute(
                """UPDATE tool_calls SET state=?,result=?,revision=revision+1
                                  WHERE scope=? AND call_id=? AND state='dispatching' """,
                (state, payload, scope, call_id),
            ).rowcount
            if changed != 1:
                raise RuntimeError("Missing tool dispatch receipt")

    def list(self, scope):
        with self.store.connect() as db:
            rows = db.execute(
                "SELECT * FROM tool_calls WHERE scope=? ORDER BY created,call_id",
                (scope,),
            ).fetchall()
            output = []
            for row in rows:
                item = dict(row)
                item["reconciliations"] = [
                    dict(audit)
                    for audit in db.execute(
                        "SELECT * FROM tool_reconciliations WHERE scope=? AND call_id=? ORDER BY created,evidence_id",
                        (scope, row["call_id"]),
                    )
                ]
                output.append(item)
            return output

    def current_unknown_ids(self, scope):
        with self.store.connect() as db:
            rows = db.execute(
                """SELECT t.call_id FROM tool_calls t WHERE t.scope=? AND t.state IN ('dispatching','unknown')
                AND NOT EXISTS (SELECT 1 FROM tool_reconciliations a WHERE a.scope=t.scope AND a.call_id=t.call_id AND a.resolved_revision=t.revision)""",
                (scope,),
            ).fetchall()
            return {row[0] for row in rows}

    def audit_resolved_ids(self, scope):
        with self.store.connect() as db:
            rows = db.execute(
                """SELECT DISTINCT t.call_id FROM tool_calls t JOIN tool_reconciliations a
                ON a.scope=t.scope AND a.call_id=t.call_id AND a.resolved_revision=t.revision WHERE t.scope=?""",
                (scope,),
            ).fetchall()
            return {row[0] for row in rows}

    def has_unknown_mutation(self, scope):
        with self.store.connect() as db:
            return (
                db.execute(
                    """SELECT 1 FROM tool_calls t WHERE t.scope=? AND t.category!='read' AND t.state IN ('dispatching','unknown')
                AND NOT EXISTS (SELECT 1 FROM tool_reconciliations a WHERE a.scope=t.scope AND a.call_id=t.call_id AND a.resolved_revision=t.revision) LIMIT 1""",
                    (scope,),
                ).fetchone()
                is not None
            )

    def reconcile(self, scope, call_id, expected_revision, evidence):
        if not isinstance(evidence, dict):
            raise ValueError("evidence must be an object")
        evidence_id = evidence.get("evidence_id")
        statement = evidence.get("operator_statement")
        refs = evidence.get("evidence_refs")
        if (
            not isinstance(evidence_id, str)
            or not evidence_id.strip()
            or not isinstance(statement, str)
            or not statement.strip()
        ):
            raise ValueError("evidence_id and operator_statement are required")
        if evidence.get("outcome") not in ("not_delivered", "delivered_unverified"):
            raise ValueError("invalid outcome")
        if not isinstance(refs, list) or not refs:
            raise ValueError("at least one evidence ref and sha256 is required")
        for ref in refs:
            if (
                not isinstance(ref, dict)
                or not isinstance(ref.get("ref"), str)
                or not ref["ref"].strip()
                or not isinstance(ref.get("sha256"), str)
                or not re.fullmatch(r"[0-9a-fA-F]{64}", ref["sha256"])
            ):
                raise ValueError("invalid evidence ref or sha256")
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("invalid expected revision")
        payload = json.dumps(
            evidence, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        )
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute(
                "SELECT * FROM tool_reconciliations WHERE scope=? AND evidence_id=?",
                (scope, evidence_id),
            ).fetchone()
            if prior:
                if prior["call_id"] != call_id or prior["evidence_json"] != payload:
                    db.rollback()
                    raise ValueError("evidence ID reused with different evidence")
                current = db.execute(
                    "SELECT revision FROM tool_calls WHERE scope=? AND call_id=?",
                    (scope, call_id),
                ).fetchone()
                result = dict(prior)
                result["active"] = bool(
                    current and current[0] == prior["resolved_revision"]
                )
                db.commit()
                return result
            row = db.execute(
                "SELECT * FROM tool_calls WHERE scope=? AND call_id=?", (scope, call_id)
            ).fetchone()
            if (
                row is None
                or row["revision"] != expected_revision
                or row["state"] not in ("dispatching", "unknown")
            ):
                db.rollback()
                raise RuntimeError("stale revision or call is not unknown")
            if evidence.get("original_fingerprint") != row["fingerprint"]:
                db.rollback()
                raise ValueError("original fingerprint mismatch")
            existing = db.execute(
                "SELECT 1 FROM tool_reconciliations WHERE scope=? AND call_id=? AND resolved_revision=?",
                (scope, call_id, expected_revision),
            ).fetchone()
            if existing:
                db.rollback()
                raise RuntimeError("call already reconciled at this revision")
            changed = db.execute(
                "UPDATE tool_calls SET revision=revision+1 WHERE scope=? AND call_id=? AND revision=?",
                (scope, call_id, expected_revision),
            ).rowcount
            if changed != 1:
                db.rollback()
                raise RuntimeError("stale revision")
            now = time.time()
            db.execute(
                "INSERT INTO tool_reconciliations VALUES(?,?,?,?,?,?)",
                (scope, evidence_id, call_id, payload, expected_revision + 1, now),
            )
            row = db.execute(
                "SELECT * FROM tool_reconciliations WHERE scope=? AND evidence_id=?",
                (scope, evidence_id),
            ).fetchone()
            result = dict(row)
            result["active"] = True
            db.commit()
            return result
