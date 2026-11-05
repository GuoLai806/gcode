import asyncio
import subprocess
import pytest
from gcode.worktree.manager import WorktreeManager, WorktreeError
from gcode.worktree.changes import has_worktree_changes


def git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, text=True, capture_output=True, check=True
    ).stdout.strip()


def test_safety_real_git(tmp_path):
    git(tmp_path, "init")
    git(tmp_path, "config", "user.email", "x@example.com")
    git(tmp_path, "config", "user.name", "x")
    (tmp_path / "file").write_text("base")
    git(tmp_path, "add", "file")
    git(tmp_path, "commit", "-m", "base")
    manager = WorktreeManager(
        str(tmp_path), worktree_dir=str(tmp_path.parent / (tmp_path.name + "-wt"))
    )
    wt = asyncio.run(manager.create("one"))
    (tmp_path.parent / (tmp_path.name + "-wt") / "one" / "untracked").write_text("keep")
    assert has_worktree_changes(wt.path, wt.head_commit)
    result = asyncio.run(manager.auto_cleanup("one", wt.head_commit))
    assert result.kept
    with pytest.raises(WorktreeError):
        asyncio.run(manager.exit("one", action="remove", discard_changes=True))
    assert (tmp_path.parent / (tmp_path.name + "-wt") / "one" / "untracked").exists()
    assert has_worktree_changes(wt.path, "invalid-sha")


def test_existing_branch_not_reset(tmp_path):
    git(tmp_path, "init")
    git(tmp_path, "config", "user.email", "x@example.com")
    git(tmp_path, "config", "user.name", "x")
    (tmp_path / "f").write_text("a")
    git(tmp_path, "add", "f")
    git(tmp_path, "commit", "-m", "a")
    git(tmp_path, "branch", "worktree-one")
    before = git(tmp_path, "rev-parse", "worktree-one")
    manager = WorktreeManager(
        str(tmp_path), worktree_dir=str(tmp_path.parent / (tmp_path.name + "-wt"))
    )
    with pytest.raises(WorktreeError):
        asyncio.run(manager.create("one"))
    assert git(tmp_path, "rev-parse", "worktree-one") == before


def _create_owned_tree(repo, tree_dir):
    manager = WorktreeManager(repo, worktree_dir=tree_dir, owner_lease_seconds=0.05)
    asyncio.run(manager.create("one"))
    manager.seal_process_registry("one")


def test_cleanup_plan_rejects_changed_tree(tmp_path):
    import multiprocessing, time
    from pathlib import Path

    git(tmp_path, "init")
    git(tmp_path, "config", "user.email", "x@example.com")
    git(tmp_path, "config", "user.name", "x")
    (tmp_path / "f").write_text("a")
    git(tmp_path, "add", "f")
    git(tmp_path, "commit", "-m", "a")
    tree_dir = str(tmp_path.parent / (tmp_path.name + "-wt"))
    process = multiprocessing.Process(
        target=_create_owned_tree, args=(str(tmp_path), tree_dir)
    )
    process.start()
    process.join(20)
    assert process.exitcode == 0
    time.sleep(0.1)
    manager = WorktreeManager(str(tmp_path), worktree_dir=tree_dir)
    assert manager.reconcile()["one"] == "verified"
    manager.mark_inactive("one")
    plan = manager.plan_cleanup("one")
    path = Path(tree_dir) / "one"
    (path / "new").write_text("keep")
    with pytest.raises(WorktreeError):
        asyncio.run(manager.apply_cleanup(plan["id"]))
    assert (path / "new").read_text() == "keep"


def test_live_owner_never_inactive(tmp_path):
    git(tmp_path, "init")
    git(tmp_path, "config", "user.email", "x@example.com")
    git(tmp_path, "config", "user.name", "x")
    (tmp_path / "f").write_text("a")
    git(tmp_path, "add", "f")
    git(tmp_path, "commit", "-m", "a")
    manager = WorktreeManager(
        str(tmp_path),
        worktree_dir=str(tmp_path.parent / (tmp_path.name + "-wt")),
        owner_lease_seconds=0.001,
    )
    asyncio.run(manager.create("one"))
    import time

    time.sleep(0.01)
    with pytest.raises(WorktreeError):
        manager.mark_inactive("one")


def test_cleanup_plan_apply_and_git_failure_preserves_branch(tmp_path, monkeypatch):
    import multiprocessing, time

    git(tmp_path, "init")
    git(tmp_path, "config", "user.email", "x@example.com")
    git(tmp_path, "config", "user.name", "x")
    (tmp_path / "f").write_text("a")
    git(tmp_path, "add", "f")
    git(tmp_path, "commit", "-m", "a")
    tree_dir = str(tmp_path.parent / (tmp_path.name + "-wt"))
    process = multiprocessing.Process(
        target=_create_owned_tree, args=(str(tmp_path), tree_dir)
    )
    process.start()
    process.join(20)
    assert process.exitcode == 0
    time.sleep(0.1)
    manager = WorktreeManager(str(tmp_path), worktree_dir=tree_dir)
    manager.reconcile()
    manager.mark_inactive("one")
    plan = manager.plan_cleanup("one")
    before = git(tmp_path, "rev-parse", "worktree-one")
    original = manager._run_git

    def fake(args, cwd=None):
        if args[:2] == ["worktree", "remove"]:
            return subprocess.CompletedProcess(args, 1, "", "injected failure")
        return original(args, cwd)

    monkeypatch.setattr(manager, "_run_git", fake)
    with pytest.raises(WorktreeError):
        asyncio.run(manager.apply_cleanup(plan["id"]))
    assert git(tmp_path, "rev-parse", "worktree-one") == before
    assert (tmp_path.parent / (tmp_path.name + "-wt") / "one").exists()
    monkeypatch.setattr(manager, "_run_git", original)
    asyncio.run(manager.apply_cleanup(plan["id"]))
    assert git(tmp_path, "rev-parse", "worktree-one") == before
    assert not (tmp_path.parent / (tmp_path.name + "-wt") / "one").exists()


def _race_create(repo, tree_dir, gate, output):
    manager = WorktreeManager(repo, worktree_dir=tree_dir)
    gate.wait()
    try:
        asyncio.run(manager.create("race"))
        output.put("created")
    except WorktreeError:
        output.put("preserved")


def test_cross_process_worktree_lock(tmp_path):
    import multiprocessing

    git(tmp_path, "init")
    git(tmp_path, "config", "user.email", "x@example.com")
    git(tmp_path, "config", "user.name", "x")
    (tmp_path / "f").write_text("a")
    git(tmp_path, "add", "f")
    git(tmp_path, "commit", "-m", "a")
    tree_dir = str(tmp_path.parent / (tmp_path.name + "-wt"))
    gate = multiprocessing.Event()
    output = multiprocessing.Queue()
    children = [
        multiprocessing.Process(
            target=_race_create, args=(str(tmp_path), tree_dir, gate, output)
        )
        for _ in range(2)
    ]
    for child in children:
        child.start()
    gate.set()
    for child in children:
        child.join(20)
        assert child.exitcode == 0
    assert sorted(output.get(timeout=2) for _ in children) == ["created", "preserved"]
    assert git(tmp_path, "rev-parse", "worktree-race") == git(
        tmp_path, "rev-parse", "HEAD"
    )


def _owner_with_registered_child(repo, tree_dir, output):
    import sys

    manager = WorktreeManager(repo, worktree_dir=tree_dir, owner_lease_seconds=0.05)
    asyncio.run(manager.create("one"))
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(20)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    manager.register_owner_process("one", child.pid)
    manager.seal_process_registry("one")
    output.put(child.pid)


def test_registered_live_child_blocks_cleanup_after_owner_exit(tmp_path):
    import multiprocessing, os, signal, time

    git(tmp_path, "init")
    git(tmp_path, "config", "user.email", "x@example.com")
    git(tmp_path, "config", "user.name", "x")
    (tmp_path / "f").write_text("a")
    git(tmp_path, "add", "f")
    git(tmp_path, "commit", "-m", "a")
    tree_dir = str(tmp_path.parent / (tmp_path.name + "-wt"))
    output = multiprocessing.Queue()
    process = multiprocessing.Process(
        target=_owner_with_registered_child, args=(str(tmp_path), tree_dir, output)
    )
    process.start()
    child = output.get(timeout=10)
    process.join(10)
    try:
        assert process.exitcode == 0
        time.sleep(0.1)
        manager = WorktreeManager(str(tmp_path), worktree_dir=tree_dir)
        assert manager.reconcile()["one"] == "verified"
        with pytest.raises(WorktreeError):
            manager.mark_inactive("one")
    finally:
        try:
            os.kill(child, signal.SIGTERM)
        except ProcessLookupError:
            pass


def test_git_status_nonzero_and_ignored_preserved(tmp_path, monkeypatch):
    from pathlib import Path
    import gcode.worktree.changes as changes

    git(tmp_path, "init")
    git(tmp_path, "config", "user.email", "x@example.com")
    git(tmp_path, "config", "user.name", "x")
    (tmp_path / ".gitignore").write_text("ignored.txt\n")
    (tmp_path / "f").write_text("a")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "a")
    manager = WorktreeManager(
        str(tmp_path), worktree_dir=str(tmp_path.parent / (tmp_path.name + "-wt"))
    )
    wt = asyncio.run(manager.create("one"))
    ignored = Path(wt.path) / "ignored.txt"
    ignored.write_text("keep")
    assert changes.has_worktree_changes(wt.path, wt.head_commit)
    ignored.unlink()
    original = changes._run_git

    def fake(args, cwd):
        if args[0] == "status":
            return subprocess.CompletedProcess(args, 1, "", "failed")
        return original(args, cwd)

    monkeypatch.setattr(changes, "_run_git", fake)
    assert changes.has_worktree_changes(wt.path, wt.head_commit)


def _create_unsealed(repo, tree_dir):
    manager = WorktreeManager(repo, worktree_dir=tree_dir, owner_lease_seconds=0.05)
    asyncio.run(manager.create("one"))


def test_unsealed_process_registry_preserves_unknown(tmp_path):
    import multiprocessing, time

    git(tmp_path, "init")
    git(tmp_path, "config", "user.email", "x@example.com")
    git(tmp_path, "config", "user.name", "x")
    (tmp_path / "f").write_text("a")
    git(tmp_path, "add", "f")
    git(tmp_path, "commit", "-m", "a")
    tree_dir = str(tmp_path.parent / (tmp_path.name + "-wt"))
    owner = multiprocessing.Process(
        target=_create_unsealed, args=(str(tmp_path), tree_dir)
    )
    owner.start()
    owner.join(20)
    assert owner.exitcode == 0
    time.sleep(0.1)
    manager = WorktreeManager(str(tmp_path), worktree_dir=tree_dir)
    assert manager.reconcile()["one"] == "verified"
    with pytest.raises(WorktreeError):
        manager.mark_inactive("one")


def test_unknown_worktree_auto_cleanup_reports_preserved(tmp_path):
    manager = WorktreeManager(str(tmp_path))
    assert asyncio.run(manager.auto_cleanup("unknown", "unknown")).kept
