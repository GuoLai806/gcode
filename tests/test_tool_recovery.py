import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import pytest
from gcode.runtime.tool_ledger import ToolLedger
from gcode.runtime.notifications import NotificationStore
from gcode.tools.base import ToolResult


def evidence(row, evidence_id="e1", outcome="not_delivered"):
    return {
        "evidence_id": evidence_id,
        "original_fingerprint": row["fingerprint"],
        "outcome": outcome,
        "evidence_refs": [{"ref": "local receipt", "sha256": "a" * 64}],
        "operator_statement": "Inspected the receipt and target state.",
    }


def test_unknown_action_never_replayed_even_after_manual_resolution(tmp_path):
    ledger = ToolLedger(tmp_path / "private" / "ledger.db")
    counter = []

    def attempt():
        prior = ledger.begin("s", "call", "WriteFile", {"path": "x"}, "write")
        if prior is not None:
            return prior
        counter.append("effect")
        ledger.finish(
            "s",
            "call",
            ToolResult(
                "delivery uncertain", True, {"delivery_state": "delivery_unknown"}
            ),
        )

    attempt()
    assert ledger.has_unknown_mutation("s")
    assert ledger.current_unknown_ids("s") == {"call"}
    prior = attempt()
    assert prior.is_error and counter == ["effect"]
    row = ledger.list("s")[0]
    receipt = evidence(row)
    first = ledger.reconcile("s", "call", row["revision"], receipt)
    assert ledger.reconcile("s", "call", row["revision"], receipt) == first
    assert not ledger.has_unknown_mutation("s")
    assert ledger.current_unknown_ids("s") == set() and ledger.audit_resolved_ids(
        "s"
    ) == {"call"}
    after = ledger.list("s")[0]
    assert after["state"] == "unknown" and "delivery uncertain" in after["result"]
    assert json.loads(after["reconciliations"][0]["evidence_json"]) == receipt
    assert attempt().is_error and counter == ["effect"]


def test_evidence_required_cas_and_conflicts(tmp_path):
    ledger = ToolLedger(tmp_path / "ledger.db")
    ledger.begin("s", "c", "Bash", {"command": "x"}, "command")
    row = ledger.list("s")[0]
    receipt = evidence(row)
    for invalid in (
        {},
        {**receipt, "original_fingerprint": "bad"},
        {**receipt, "evidence_refs": []},
        {**receipt, "operator_statement": ""},
        {**receipt, "evidence_refs": [{"ref": "r", "sha256": "bad"}]},
    ):
        with pytest.raises(ValueError):
            ledger.reconcile("s", "c", row["revision"], invalid)
    with pytest.raises(RuntimeError):
        ledger.reconcile("s", "c", 99, receipt)
    ledger.reconcile("s", "c", row["revision"], receipt)
    with pytest.raises(ValueError):
        ledger.reconcile(
            "s", "c", row["revision"], {**receipt, "outcome": "delivered_unverified"}
        )
    with pytest.raises(RuntimeError):
        ledger.reconcile("s", "c", row["revision"], evidence(row, "e2"))
    assert len(ledger.list("s")[0]["reconciliations"]) == 1


def test_late_finish_invalidates_prior_audit_without_erasing_it(tmp_path):
    ledger = ToolLedger(tmp_path / "ledger.db")
    ledger.begin("s", "c", "Bash", {}, "command")
    row = ledger.list("s")[0]
    ledger.reconcile("s", "c", row["revision"], evidence(row))
    ledger.finish("s", "c", ToolResult("late receipt", False))
    record = ledger.list("s")[0]
    assert record["state"] == "completed" and "late receipt" in record["result"]
    assert (
        len(record["reconciliations"]) == 1 and ledger.audit_resolved_ids("s") == set()
    )
    assert ledger.begin("s", "c", "Bash", {}, "command").output == "late receipt"


def test_private_new_files_and_legacy_migration(tmp_path):
    path = tmp_path / "new-private" / "state.db"
    ledger = ToolLedger(path)
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
    old = tmp_path / "old.db"
    db = sqlite3.connect(old)
    db.execute(
        "CREATE TABLE tool_calls(scope TEXT, call_id TEXT, fingerprint TEXT, category TEXT, state TEXT, result TEXT, PRIMARY KEY(scope,call_id))"
    )
    db.execute(
        "INSERT INTO tool_calls VALUES('s','c','legacy','write','unknown','raw')"
    )
    db.commit()
    db.close()
    migrated = ToolLedger(old)
    row = migrated.list("s")[0]
    assert (
        row["fingerprint"] == "legacy"
        and row["result"] == "raw"
        and row["revision"] == 0
    )
    assert migrated.current_unknown_ids("s") == {"c"}


def test_notifications_are_durable_content_addressed_and_scoped(tmp_path):
    path = tmp_path / "notice" / "db"
    store = NotificationStore(path)
    ident = store.put("s", "重要消息")
    assert ident == hashlib.sha256("重要消息".encode()).hexdigest()
    assert store.put("s", "重要消息") == ident
    assert len(NotificationStore(path).list("s")) == 1
    assert NotificationStore(path).list("other") == []
    assert store.list("s")[0]["text"] == "重要消息"
    assert path.stat().st_mode & 0o777 == 0o600


def test_operator_cli_inspect_and_reconcile(tmp_path):
    path = tmp_path / "ledger.db"
    ledger = ToolLedger(path)
    ledger.begin("scope", "c", "Bash", {}, "command")
    row = ledger.list("scope")[0]

    def cli(*args):
        return subprocess.run(
            [sys.executable, "-m", "gcode.runtime.recover", *args],
            capture_output=True,
            text=True,
        )

    inspected = cli("inspect", "--db", str(path), "--scope", "scope")
    assert (
        inspected.returncode == 0
        and json.loads(inspected.stdout)["calls"][0]["fingerprint"]
        == row["fingerprint"]
    )
    receipt = tmp_path / "evidence.json"
    receipt.write_text(json.dumps(evidence(row)))
    result = cli(
        "reconcile",
        "--db",
        str(path),
        "--scope",
        "scope",
        "--call-id",
        "c",
        "--revision",
        str(row["revision"]),
        "--evidence",
        str(receipt),
    )
    assert result.returncode == 0 and ledger.audit_resolved_ids("scope") == {"c"}
    assert (
        len(
            json.loads(cli("inspect", "--db", str(path), "--scope", "scope").stdout)[
                "reconciliations"
            ]
        )
        == 1
    )
    missing = tmp_path / "absent.db"
    assert (
        cli("inspect", "--db", str(missing), "--scope", "scope").returncode != 0
        and not missing.exists()
    )


def test_existing_dedicated_runtime_tightened_but_unrelated_parent_preserved(tmp_path):
    runtime = tmp_path / ".gcode" / "runtime"
    runtime.mkdir(parents=True)
    runtime.chmod(0o755)
    ToolLedger(runtime / "ledger.db")
    assert runtime.stat().st_mode & 0o777 == 0o700
    unrelated = tmp_path / "shared"
    unrelated.mkdir(mode=0o755)
    unrelated.chmod(0o755)
    with pytest.raises(PermissionError):
        ToolLedger(unrelated / "ledger.db")
    assert (
        unrelated.stat().st_mode & 0o777 == 0o755
        and not (unrelated / "ledger.db").exists()
    )


def test_late_unknown_receipt_reopens_fence_and_retains_audit(tmp_path):
    ledger = ToolLedger(tmp_path / "ledger.db")
    ledger.begin("s", "c", "Bash", {}, "command")
    row = ledger.list("s")[0]
    ledger.reconcile("s", "c", row["revision"], evidence(row))
    assert not ledger.has_unknown_mutation("s")
    ledger.finish(
        "s",
        "c",
        ToolResult("still unknown", True, {"delivery_state": "delivery_unknown"}),
    )
    assert ledger.has_unknown_mutation("s") and ledger.current_unknown_ids("s") == {"c"}
    assert (
        ledger.audit_resolved_ids("s") == set()
        and len(ledger.list("s")[0]["reconciliations"]) == 1
    )


def _reconcile_race(path, gate, outcome, suffix, row):
    ledger = ToolLedger(path)
    gate.wait()
    try:
        ledger.reconcile("s", "c", row["revision"], evidence(row, suffix))
        outcome.put("committed")
    except RuntimeError:
        outcome.put("stale")


def test_concurrent_operator_resolutions_use_revision_cas(tmp_path):
    import multiprocessing as mp

    path = str(tmp_path / "race.db")
    ledger = ToolLedger(path)
    ledger.begin("s", "c", "Bash", {}, "command")
    row = ledger.list("s")[0]
    gate = mp.Event()
    outcome = mp.Queue()
    workers = [
        mp.Process(target=_reconcile_race, args=(path, gate, outcome, suffix, row))
        for suffix in ("a", "b")
    ]
    for worker in workers:
        worker.start()
    gate.set()
    for worker in workers:
        worker.join(20)
        assert worker.exitcode == 0
    assert sorted(outcome.get(timeout=2) for _ in workers) == ["committed", "stale"]
    assert len(ledger.list("s")[0]["reconciliations"]) == 1


def test_replayed_old_receipt_reports_it_is_no_longer_active(tmp_path):
    ledger = ToolLedger(tmp_path / "ledger.db")
    ledger.begin("s", "c", "Bash", {}, "command")
    row = ledger.list("s")[0]
    receipt = evidence(row)
    assert ledger.reconcile("s", "c", row["revision"], receipt)["active"] is True
    ledger.finish(
        "s",
        "c",
        ToolResult("late uncertain", True, {"delivery_state": "delivery_unknown"}),
    )
    assert ledger.reconcile("s", "c", row["revision"], receipt)["active"] is False
    assert ledger.has_unknown_mutation("s")
