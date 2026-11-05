import multiprocessing as mp
import pytest
from gcode.runtime.budget import TokenBudget


def _record(path, gate):
    budget = TokenBudget(path, "scope", 10000)
    gate.wait()
    for _ in range(50):
        budget.record_usage(2, 1, 3, 4)


def test_concurrent_usage_and_immutable_limit(tmp_path):
    path = str(tmp_path / "tokens.db")
    budget = TokenBudget(path, "scope", 10000)
    gate = mp.Event()
    workers = [mp.Process(target=_record, args=(path, gate)) for _ in range(2)]
    for worker in workers:
        worker.start()
    gate.set()
    for worker in workers:
        worker.join(30)
        assert worker.exitcode == 0
    state = budget.snapshot()
    assert state["observed_total"] == 1000 and state["revision"] == 100
    assert (
        state["prompt_uncached"] == 200
        and state["output"] == 100
        and state["cache_read"] == 300
        and state["cache_write"] == 400
    )
    assert state["cost_usd"] is None and budget.before_request()
    with pytest.raises(ValueError):
        TokenBudget(path, "scope", 20000)


def test_overrun_observed_and_next_request_blocked(tmp_path):
    budget = TokenBudget(str(tmp_path / "tokens.db"), "scope", 10)
    assert budget.before_request()
    state = budget.record_usage(8, 4, 1, 0)
    assert (
        state["observed_total"] == 13
        and state["overrun"] == 3
        and state["remaining"] == 0
    )
    assert not budget.before_request()
    with pytest.raises(ValueError):
        budget.record_usage(-1, 0)


def test_missing_usage_fails_closed_across_restart(tmp_path):
    path = str(tmp_path / "tokens.db")
    budget = TokenBudget(path, "scope", 100)
    budget.mark_usage_unknown()
    reopened = TokenBudget(path, "scope", 100)
    assert not reopened.before_request()
    assert reopened.snapshot()["usage_complete"] is False


def test_unknown_usage_reconciliation_is_cas_and_idempotent(tmp_path):
    budget = TokenBudget(str(tmp_path / "b.db"), "scope", 100)
    budget.mark_usage_unknown()
    budget.mark_usage_unknown()
    revision = budget.snapshot()["revision"]
    state = budget.resolve_unknown("receipt-1", revision, 10, 5)
    assert not state["usage_complete"] and state["observed_total"] == 15
    assert budget.resolve_unknown("receipt-1", revision, 10, 5)["observed_total"] == 15
    with pytest.raises(ValueError):
        budget.resolve_unknown("receipt-1", revision, 99, 1)
    with pytest.raises(RuntimeError):
        budget.resolve_unknown("receipt-2", revision, 1, 1)
    state = budget.resolve_unknown("receipt-2", state["revision"], 1, 1)
    assert state["usage_complete"] and state["observed_total"] == 17


def _race_limit(path, limit, gate, results):
    gate.wait()
    try:
        TokenBudget(path, "shared", limit)
        results.put("created")
    except ValueError:
        results.put("conflict")


def test_concurrent_different_caps_cannot_both_initialize(tmp_path):
    path = str(tmp_path / "budget.db")
    gate = mp.Event()
    results = mp.Queue()
    workers = [
        mp.Process(target=_race_limit, args=(path, limit, gate, results))
        for limit in (100, 200)
    ]
    for worker in workers:
        worker.start()
    gate.set()
    for worker in workers:
        worker.join(30)
        assert worker.exitcode == 0
    assert sorted(results.get(timeout=2) for _ in workers) == ["conflict", "created"]


def test_root_can_set_budget_before_session_and_resume(tmp_path):
    from unittest.mock import MagicMock
    from gcode.agent import Agent
    from gcode.tools import ToolRegistry

    path = str(tmp_path / ".gcode" / "runtime" / "token-budget.sqlite3")
    first = Agent(MagicMock(), ToolRegistry(), "anthropic", work_dir=str(tmp_path))
    first.token_budget = TokenBudget(path, "bootstrap", 50)
    first.session_id = "durable-session"
    first.token_budget.record_usage(7, 3)
    resumed = Agent(MagicMock(), ToolRegistry(), "anthropic", work_dir=str(tmp_path))
    resumed.token_budget = TokenBudget(path, "another-bootstrap", 50)
    resumed.session_id = "durable-session"
    assert resumed.token_budget.snapshot()["observed_total"] == 10
    assert resumed.token_budget.max_total_tokens == 50
