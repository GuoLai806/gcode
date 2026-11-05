"""Operator-only tool receipt inspection and evidence-based reconciliation.

This module is not registered as a model tool. Reconciliation records an operator
statement and does not verify the evidence or replay the external action.
"""

from __future__ import annotations
import argparse
import json
import sqlite3
import sys
from pathlib import Path
from gcode.runtime.tool_ledger import ToolLedger


def inspect_readonly(path, scope):
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError("ledger database not found")
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        rows = [
            dict(row)
            for row in db.execute(
                "SELECT * FROM tool_calls WHERE scope=? ORDER BY call_id", (scope,)
            )
        ]
        has_audit = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tool_reconciliations'"
        ).fetchone()
        audit = (
            [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM tool_reconciliations WHERE scope=? ORDER BY created,evidence_id",
                    (scope,),
                )
            ]
            if has_audit
            else []
        )
        return {"scope": scope, "calls": rows, "reconciliations": audit}
    finally:
        db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Inspect tool receipts or record an operator reconciliation; does not replay actions."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("--db", required=True)
    inspect.add_argument("--scope", required=True)
    reconcile = commands.add_parser("reconcile")
    reconcile.add_argument("--db", required=True)
    reconcile.add_argument("--scope", required=True)
    reconcile.add_argument("--call-id", required=True)
    reconcile.add_argument("--revision", required=True, type=int)
    reconcile.add_argument(
        "--evidence",
        required=True,
        help="Path to an operator-supplied JSON evidence record",
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            result = inspect_readonly(args.db, args.scope)
        else:
            if not Path(args.db).is_file():
                raise FileNotFoundError("ledger database not found")
            evidence = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
            result = ToolLedger(args.db).reconcile(
                args.scope, args.call_id, args.revision, evidence
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        print(f"Recovery failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
