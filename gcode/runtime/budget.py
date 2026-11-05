"""Persistent observed-token budget shared across parent and child runs.

The cap is checked before dispatch, not reserved against an in-flight request.
Concurrent or large requests may therefore exceed it; no hard provider cap is implied.
"""

from __future__ import annotations
from gcode.runtime.store import RunStore


class TokenBudget:
    def __init__(
        self, store_path: str, scope_id: str, max_total_tokens: int = 1_000_000
    ):
        if not scope_id or type(max_total_tokens) is not int or max_total_tokens <= 0:
            raise ValueError(
                "non-empty scope and positive integer token limit required"
            )
        self.scope_id = scope_id
        self.max_total_tokens = max_total_tokens
        self._store = RunStore(store_path)
        with self._store.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS token_budgets(
                scope TEXT PRIMARY KEY, max_total INTEGER NOT NULL, prompt_uncached INTEGER NOT NULL DEFAULT 0,
                output INTEGER NOT NULL DEFAULT 0, cache_read INTEGER NOT NULL DEFAULT 0,
                cache_write INTEGER NOT NULL DEFAULT 0, revision INTEGER NOT NULL DEFAULT 0,
                usage_unknown INTEGER NOT NULL DEFAULT 0)""")
            db.execute("""CREATE TABLE IF NOT EXISTS token_reconciliations(
                scope TEXT NOT NULL, evidence_id TEXT NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY(scope,evidence_id))""")
            columns = {row[1] for row in db.execute("PRAGMA table_info(token_budgets)")}
            if "usage_unknown" not in columns:
                try:
                    db.execute(
                        "ALTER TABLE token_budgets ADD COLUMN usage_unknown INTEGER NOT NULL DEFAULT 0"
                    )
                except Exception as exc:
                    if "duplicate column" not in str(exc):
                        raise
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT OR IGNORE INTO token_budgets(scope,max_total) VALUES(?,?)",
                (scope_id, max_total_tokens),
            )
            limit = db.execute(
                "SELECT max_total FROM token_budgets WHERE scope=?", (scope_id,)
            ).fetchone()[0]
            if limit != max_total_tokens:
                db.rollback()
                raise ValueError("token limit for existing scope is immutable")
            db.commit()

    def snapshot(self) -> dict:
        with self._store.connect() as db:
            row = db.execute(
                "SELECT * FROM token_budgets WHERE scope=?", (self.scope_id,)
            ).fetchone()
        if row is None:
            raise RuntimeError("token budget scope missing")
        result = dict(row)
        total = sum(
            result[k]
            for k in ("prompt_uncached", "output", "cache_read", "cache_write")
        )
        result.update(
            max_total_tokens=result["max_total"],
            observed_total=total,
            remaining=max(0, result["max_total"] - total),
            overrun=max(0, total - result["max_total"]),
            usage_complete=not bool(result["usage_unknown"]),
            cost_usd=None,
        )
        return result

    def before_request(self) -> bool:
        state = self.snapshot()
        return (
            state["usage_complete"]
            and state["observed_total"] < state["max_total_tokens"]
        )

    def mark_usage_unknown(self) -> None:
        """Prevent further dispatch if provider usage for a call is unavailable."""
        with self._store.connect() as db:
            db.execute(
                "UPDATE token_budgets SET usage_unknown=usage_unknown+1, revision=revision+1 WHERE scope=?",
                (self.scope_id,),
            )

    def resolve_unknown(
        self,
        evidence_id: str,
        expected_revision: int,
        prompt_uncached: int,
        output: int,
        cache_read: int = 0,
        cache_write: int = 0,
    ) -> dict:
        """Reconcile one unknown call using a stable external receipt, never a replay."""
        import json

        values = (prompt_uncached, output, cache_read, cache_write)
        if not evidence_id or any(
            type(value) is not int or value < 0 for value in values
        ):
            raise ValueError("receipt and non-negative integer usage required")
        payload = json.dumps(values)
        with self._store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute(
                "SELECT payload FROM token_reconciliations WHERE scope=? AND evidence_id=?",
                (self.scope_id, evidence_id),
            ).fetchone()
            if prior:
                if prior[0] != payload:
                    db.rollback()
                    raise ValueError("receipt reused with different usage")
                db.commit()
                return self.snapshot()
            updated = db.execute(
                """UPDATE token_budgets SET usage_unknown=usage_unknown-1,
                prompt_uncached=prompt_uncached+?, output=output+?, cache_read=cache_read+?, cache_write=cache_write+?,
                revision=revision+1 WHERE scope=? AND revision=? AND usage_unknown>0""",
                (*values, self.scope_id, expected_revision),
            )
            if updated.rowcount != 1:
                db.rollback()
                raise RuntimeError("stale revision or no unknown usage")
            db.execute(
                "INSERT INTO token_reconciliations VALUES(?,?,?)",
                (self.scope_id, evidence_id, payload),
            )
            db.commit()
        return self.snapshot()

    def record_usage(
        self,
        prompt_uncached: int,
        output: int,
        cache_read: int = 0,
        cache_write: int = 0,
    ) -> dict:
        values = (prompt_uncached, output, cache_read, cache_write)
        if any(type(value) is not int or value < 0 for value in values):
            raise ValueError("usage values must be non-negative integers")
        with self._store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            updated = db.execute(
                """UPDATE token_budgets SET prompt_uncached=prompt_uncached+?, output=output+?,
                               cache_read=cache_read+?, cache_write=cache_write+?, revision=revision+1 WHERE scope=?""",
                (*values, self.scope_id),
            )
            if updated.rowcount != 1:
                db.rollback()
                raise RuntimeError("token budget scope missing")
            db.commit()
        return self.snapshot()
