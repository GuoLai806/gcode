from types import SimpleNamespace
import sys
import pytest
from gcode import __main__ as cli


@pytest.mark.parametrize("value", ["0", "-1", "abc", "9223372036854775808"])
def test_budget_option_rejects_nonpositive_and_invalid(monkeypatch, tmp_path, value):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["gcode", "--max-total-tokens", value])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2


def test_budget_option_reaches_desktop_app(monkeypatch, tmp_path):
    import gcode.app

    seen = {}

    class App:
        def __init__(self, **kwargs):
            seen.update(kwargs)

        def run(self):
            seen["ran"] = True

    config = SimpleNamespace(
        permission_mode="default",
        raw_hooks=[],
        providers=[],
        mcp_servers=[],
        enable_fork=False,
        enable_verification_agent=False,
        worktree=None,
        teammate_mode="",
        enable_coordinator_mode=False,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["gcode", "--max-total-tokens", "321"])
    monkeypatch.setattr(cli, "load_config", lambda: config)
    monkeypatch.setattr(cli, "load_hooks", lambda raw: [])
    monkeypatch.setattr(gcode.app, "GCodeApp", App)
    cli.main()
    assert seen["max_total_tokens"] == 321 and seen["ran"]


def test_real_desktop_app_accepts_budget(monkeypatch, tmp_path):
    from gcode.app import GCodeApp

    monkeypatch.chdir(tmp_path)
    app = GCodeApp(providers=[], max_total_tokens=321)
    assert app._max_total_tokens == 321
