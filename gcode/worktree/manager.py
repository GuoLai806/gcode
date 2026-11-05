from __future__ import annotations

import asyncio
import contextlib
import fcntl
import json
import hashlib
import uuid
import logging
import os
import socket
import subprocess
import time
from datetime import datetime
from pathlib import Path

from gcode.worktree.changes import (
    CleanupResult,
    Changes,
    count_worktree_changes,
    has_worktree_changes,
)
from gcode.worktree.models import Worktree, WorktreeSession
from gcode.worktree.session import load_worktree_session, save_worktree_session
from gcode.worktree.setup import perform_post_creation_setup
from gcode.worktree.slug import flatten_slug, validate_slug

log = logging.getLogger(__name__)

GIT_ENV = {"GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": ""}


class WorktreeError(Exception):
    pass


class WorktreeManager:
    def __init__(
        self,
        repo_root: str,
        symlink_directories: list[str] | None = None,
        worktree_dir: str | None = None,
        owner_lease_seconds: float = 30.0,
    ) -> None:
        if owner_lease_seconds <= 0:
            raise ValueError("owner lease must be positive")
        self._owner_lease_seconds = owner_lease_seconds
        self.repo_root = repo_root
        self.symlink_directories = symlink_directories or []
        self.worktree_dir = worktree_dir or str(
            Path(repo_root) / ".gcode" / "worktrees"
        )
        self._GCode_dir = Path(repo_root) / ".gcode"
        self._lock = asyncio.Lock()
        self.active: dict[str, Worktree] = {}
        self.current_session: WorktreeSession | None = None

    def _run_git(
        self, args: list[str], cwd: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, **GIT_ENV}
        return subprocess.run(
            ["git"] + args,
            cwd=cwd or self.repo_root,
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            env=env,
        )

    @contextlib.contextmanager
    def _repository_lock(self):
        result = self._run_git(["rev-parse", "--git-common-dir"])
        if result.returncode != 0 or not result.stdout.strip():
            raise WorktreeError("cannot determine common git directory")
        common = Path(result.stdout.strip())
        if not common.is_absolute():
            common = Path(self.repo_root) / common
        common = common.resolve()
        with (common / "gcode-worktree.lock").open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield common
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _manifest_path(self, common: Path, name: str) -> Path:
        directory = common / "gcode-worktrees"
        directory.mkdir(exist_ok=True)
        return directory / (flatten_slug(name) + ".json")

    @staticmethod
    def _write_json(path: Path, value: dict) -> None:
        # A crash can leave an orphan temporary file, but never a partial manifest.
        temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
        try:
            with temporary.open("x", encoding="utf-8") as stream:
                json.dump(value, stream, ensure_ascii=False, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _process_birth(pid: int) -> str | None:
        try:
            result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "lstart="],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return (
            result.stdout.strip()
            if result.returncode == 0 and result.stdout.strip()
            else None
        )

    def _owner_gone(self, record: dict) -> bool:
        owner = record.get("owner")
        if not isinstance(owner, dict) or owner.get("host") != socket.gethostname():
            return False
        pid = owner.get("pid")
        birth = owner.get("birth")
        if (
            not isinstance(pid, int)
            or pid <= 0
            or not birth
            or time.time() < owner.get("lease_until", float("inf"))
        ):
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except (PermissionError, OSError):
            return False
        # Even a reused PID may have acquired the directory; preserve on ambiguity.
        return False

    def _owners_gone(self, record: dict) -> bool:
        processes = record.get("processes", [])
        if record.get("process_registry_sealed") is not True or not isinstance(
            processes, list
        ):
            return False
        if not self._owner_gone(record):
            return False
        return all(self._owner_gone({"owner": owner}) for owner in processes)

    def register_owner_process(self, name: str, pid: int) -> None:
        """Register a launched process before it can use the worktree."""
        with self._repository_lock() as common:
            path = self._manifest_path(common, name)
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                owner = record["owner"]
            except (OSError, ValueError, KeyError) as exc:
                raise WorktreeError("unknown owner") from exc
            if (
                record.get("name") != name
                or record.get("state") != "active"
                or owner.get("host") != socket.gethostname()
                or owner.get("pid") != os.getpid()
                or owner.get("birth") != self._process_birth(os.getpid())
            ):
                raise WorktreeError("owner identity mismatch")
            if record.get("process_registry_sealed"):
                raise WorktreeError("process registry is sealed")
            birth = self._process_birth(pid)
            if pid <= 0 or not birth:
                raise WorktreeError("process identity unavailable")
            entry = {
                "pid": pid,
                "birth": birth,
                "host": socket.gethostname(),
                "lease_until": time.time() + self._owner_lease_seconds,
            }
            processes = record.setdefault("processes", [])
            if any(p.get("pid") == pid and p.get("birth") == birth for p in processes):
                return
            processes.append(entry)
            self._write_json(path, record)

    def seal_process_registry(self, name: str) -> None:
        """Freeze the owner's complete registry; integration must prevent further spawns."""
        with self._repository_lock() as common:
            path = self._manifest_path(common, name)
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                owner = record["owner"]
            except (OSError, ValueError, KeyError) as exc:
                raise WorktreeError("unknown owner") from exc
            if (
                record.get("name") != name
                or record.get("state") != "active"
                or owner.get("host") != socket.gethostname()
                or owner.get("pid") != os.getpid()
                or owner.get("birth") != self._process_birth(os.getpid())
            ):
                raise WorktreeError("owner identity mismatch")
            record["process_registry_sealed"] = True
            self._write_json(path, record)

    def heartbeat_owner(self, name: str) -> None:
        with self._repository_lock() as common:
            path = self._manifest_path(common, name)
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                owner = record["owner"]
            except (OSError, ValueError, KeyError) as exc:
                raise WorktreeError("unknown owner") from exc
            if (
                owner.get("host") != socket.gethostname()
                or owner.get("pid") != os.getpid()
                or owner.get("birth") != self._process_birth(os.getpid())
                or record.get("state") != "active"
            ):
                raise WorktreeError("owner identity mismatch")
            owner["lease_until"] = time.time() + self._owner_lease_seconds
            self._write_json(path, record)

    def reconcile(self) -> dict[str, str]:
        """Rehydrate verified manifests; unknown records are reported and preserved."""
        report = {}
        with self._repository_lock() as common:
            result = self._run_git(["worktree", "list", "--porcelain"])
            if result.returncode:
                raise WorktreeError("cannot list worktrees")
            registered = {
                line[9:]
                for line in result.stdout.splitlines()
                if line.startswith("worktree ")
            }
            directory = common / "gcode-worktrees"
            if not directory.exists():
                return report
            for path in directory.glob("*.json"):
                try:
                    record = json.loads(path.read_text(encoding="utf-8"))
                    name, wt_path, branch, base = (
                        record[k] for k in ("name", "path", "branch", "base")
                    )
                    if (
                        validate_slug(name)
                        or path != self._manifest_path(common, name)
                        or record["state"] not in ("active", "inactive")
                    ):
                        raise ValueError("invalid record")
                    if str(Path(wt_path).resolve()) not in registered or str(
                        Path(wt_path).resolve()
                    ) != str(Path(self.worktree_dir, flatten_slug(name)).resolve()):
                        raise ValueError("path mismatch")
                    ref = self._run_git(
                        ["symbolic-ref", "--short", "HEAD"], cwd=wt_path
                    )
                    base_ref = self._run_git(
                        ["rev-parse", "--verify", f"{base}^{{commit}}"]
                    )
                    if (
                        ref.returncode
                        or ref.stdout.strip() != branch
                        or base_ref.returncode
                        or base_ref.stdout.strip() != base
                    ):
                        raise ValueError("identity mismatch")
                    self.active[name] = Worktree(
                        name=name,
                        path=wt_path,
                        branch=branch,
                        based_on=base,
                        head_commit=base,
                    )
                    report[name] = "verified"
                except (OSError, ValueError, KeyError, TypeError):
                    report[path.stem] = "unknown"
        return report

    # ------------------------------------------------------------------
    # 快速恢复：直接从文件系统读取 HEAD SHA，无需启动 git 子进程
    # ------------------------------------------------------------------

    @staticmethod
    def read_worktree_head_sha(wt_path: str) -> str | None:
        wt = Path(wt_path)
        git_file = wt / ".git"
        if not git_file.exists():
            return None

        try:
            content = git_file.read_text(encoding="utf-8").strip()
            if not content.startswith("gitdir:"):
                return None
            gitdir = Path(content.split(":", 1)[1].strip())
            if not gitdir.is_absolute():
                gitdir = (wt / gitdir).resolve()

            commondir_file = gitdir / "commondir"
            if commondir_file.exists():
                commondir_rel = commondir_file.read_text(encoding="utf-8").strip()
                commondir = (gitdir / commondir_rel).resolve()
            else:
                commondir = gitdir

            head_file = gitdir / "HEAD"
            if not head_file.exists():
                return None
            head_content = head_file.read_text(encoding="utf-8").strip()

            if head_content.startswith("ref:"):
                ref_path = head_content.split(":", 1)[1].strip()
                ref_file = gitdir / ref_path
                if not ref_file.exists():
                    ref_file = commondir / ref_path
                if ref_file.exists():
                    return ref_file.read_text(encoding="utf-8").strip()
                packed_refs = commondir / "packed-refs"
                if packed_refs.exists():
                    for line in packed_refs.read_text(encoding="utf-8").splitlines():
                        if line.strip() and not line.startswith("#"):
                            parts = line.split()
                            if len(parts) == 2 and parts[1] == ref_path:
                                return parts[0]
                return None
            return head_content
        except OSError:
            return None

    # ------------------------------------------------------------------
    # 创建 worktree
    # ------------------------------------------------------------------

    async def create(self, name: str, base_branch: str = "HEAD") -> Worktree:
        async with self._lock:
            err = validate_slug(name)
            if err:
                raise WorktreeError(err)
            with self._repository_lock() as common:
                if name in self.active:
                    raise WorktreeError(f"worktree already exists: {name}")
                flat = flatten_slug(name)
                wt_path = str(Path(self.worktree_dir, flat).resolve())
                branch = f"worktree-{flat}"
                manifest = self._manifest_path(common, name)
                if Path(wt_path).exists() or manifest.exists():
                    raise WorktreeError(
                        "worktree or ownership record already exists; manual reconciliation required"
                    )
                base = self._run_git(
                    ["rev-parse", "--verify", f"{base_branch}^{{commit}}"]
                )
                if base.returncode != 0:
                    raise WorktreeError("cannot resolve base commit")
                Path(self.worktree_dir).mkdir(parents=True, exist_ok=True)
                # -b fails if the branch exists; never reset a pre-existing branch.
                result = self._run_git(
                    ["worktree", "add", "-b", branch, wt_path, base.stdout.strip()]
                )
                if result.returncode != 0:
                    raise WorktreeError(
                        f"git worktree add failed: {result.stderr.strip()}"
                    )
                birth = self._process_birth(os.getpid())
                record = {
                    "name": name,
                    "path": wt_path,
                    "branch": branch,
                    "base": base.stdout.strip(),
                    "state": "active",
                    "owner": {
                        "pid": os.getpid(),
                        "birth": birth,
                        "host": socket.gethostname(),
                        "lease_until": time.time() + self._owner_lease_seconds,
                    },
                }
                self._write_json(manifest, record)
                perform_post_creation_setup(
                    self.repo_root,
                    wt_path,
                    symlink_directories=self.symlink_directories,
                )
                wt = Worktree(
                    name=name,
                    path=wt_path,
                    branch=branch,
                    based_on=base_branch,
                    head_commit=base.stdout.strip(),
                )
                self.active[name] = wt
                return wt

    # ------------------------------------------------------------------
    # 进入 worktree
    # ------------------------------------------------------------------

    async def enter(self, name: str) -> WorktreeSession:
        wt = self.active.get(name)
        if wt is None:
            raise WorktreeError(f"worktree not found: {name}")

        original_cwd = os.getcwd()
        original_branch = self._get_current_branch()
        original_head = self._get_head_commit()

        session = WorktreeSession(
            original_cwd=original_cwd,
            worktree_path=wt.path,
            worktree_name=name,
            original_branch=original_branch,
            original_head_commit=original_head,
        )
        self.current_session = session
        save_worktree_session(self._GCode_dir, session)
        return session

    # ------------------------------------------------------------------
    # 退出 worktree
    # ------------------------------------------------------------------

    async def exit(
        self,
        name: str,
        action: str = "keep",
        discard_changes: bool = False,
    ) -> None:
        wt = self.active.get(name)
        if wt is None:
            raise WorktreeError(f"worktree not found: {name}")

        if action == "remove" and not discard_changes:
            changes = count_worktree_changes(wt.path, wt.head_commit)
            if changes.uncommitted > 0 or changes.new_commits > 0:
                raise WorktreeError(
                    f"worktree has changes ({changes.uncommitted} uncommitted, "
                    f"{changes.new_commits} new commits). "
                    "Set discard_changes=True to force removal."
                )

        if action == "remove":
            await self._remove_worktree(name, wt)
        self.current_session = None
        save_worktree_session(self._GCode_dir, None)

    # ------------------------------------------------------------------
    # 删除 worktree（内部方法）
    # ------------------------------------------------------------------

    async def _remove_worktree(self, name: str, wt: Worktree) -> None:
        raise WorktreeError(
            "direct removal disabled; mark inactive and apply a reviewed cleanup plan"
        )

    def mark_inactive(self, name: str) -> None:
        with self._repository_lock() as common:
            manifest = self._manifest_path(common, name)
            try:
                record = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise WorktreeError("unknown ownership") from exc
            if record.get("name") != name or record.get("state") != "active":
                raise WorktreeError("invalid ownership state")
            if not self._owners_gone(record):
                raise WorktreeError(
                    "owner or registered process may still be alive; preserving worktree"
                )
            record["state"] = "inactive"
            self._write_json(manifest, record)

    def plan_cleanup(self, name: str) -> dict:
        with self._repository_lock() as common:
            manifest = self._manifest_path(common, name)
            try:
                raw = manifest.read_bytes()
                record = json.loads(raw)
            except (OSError, ValueError) as exc:
                raise WorktreeError("unknown ownership") from exc
            if (
                record.get("name") != name
                or record.get("state") != "inactive"
                or not self._owners_gone(record)
            ):
                raise WorktreeError("worktree owner is not verified inactive")
            wt = self.active.get(name)
            if not wt or str(Path(wt.path).resolve()) != record.get("path"):
                raise WorktreeError("worktree is not reconciled")
            if has_worktree_changes(wt.path, record["base"]):
                raise WorktreeError("dirty or unknown worktree")
            head = self._run_git(["rev-parse", "HEAD"], cwd=wt.path)
            branch = self._run_git(["symbolic-ref", "--short", "HEAD"], cwd=wt.path)
            if (
                head.returncode
                or branch.returncode
                or head.stdout.strip() != record["base"]
                or branch.stdout.strip() != record["branch"]
            ):
                raise WorktreeError("unknown worktree identity")
            plan = {
                "id": uuid.uuid4().hex,
                "name": name,
                "manifest_hash": hashlib.sha256(raw).hexdigest(),
                "head": head.stdout.strip(),
                "branch": branch.stdout.strip(),
            }
            plans = common / "gcode-cleanup-plans"
            plans.mkdir(exist_ok=True)
            self._write_json(plans / (plan["id"] + ".json"), plan)
            return plan

    async def apply_cleanup(self, plan_id: str) -> None:
        if not plan_id or any(c not in "0123456789abcdef" for c in plan_id):
            raise WorktreeError("invalid plan id")
        with self._repository_lock() as common:
            plan_path = common / "gcode-cleanup-plans" / (plan_id + ".json")
            try:
                plan = json.loads(plan_path.read_text(encoding="utf-8"))
                raw = self._manifest_path(common, plan["name"]).read_bytes()
                record = json.loads(raw)
            except (OSError, ValueError, KeyError) as exc:
                raise WorktreeError("unknown cleanup plan") from exc
            wt = self.active.get(plan["name"])
            if (
                not wt
                or record.get("state") != "inactive"
                or not self._owners_gone(record)
                or hashlib.sha256(raw).hexdigest() != plan["manifest_hash"]
            ):
                raise WorktreeError("cleanup preconditions changed")
            head = self._run_git(["rev-parse", "HEAD"], cwd=wt.path)
            branch = self._run_git(["symbolic-ref", "--short", "HEAD"], cwd=wt.path)
            if (
                head.returncode
                or branch.returncode
                or head.stdout.strip() != plan["head"]
                or branch.stdout.strip() != plan["branch"]
                or has_worktree_changes(wt.path, record["base"])
            ):
                raise WorktreeError("cleanup preconditions changed")
            result = self._run_git(["worktree", "remove", wt.path])
            if result.returncode:
                raise WorktreeError(
                    f"git worktree remove failed: {result.stderr.strip()}"
                )
            record["state"] = "removed"
            self._write_json(self._manifest_path(common, plan["name"]), record)
            self.active.pop(plan["name"], None)
            plan_path.unlink()

    async def auto_cleanup(self, name: str, head_commit: str) -> CleanupResult:
        wt = self.active.get(name)
        # Age or an apparently clean tree is not authorization for cleanup.
        return CleanupResult(
            kept=True, path=wt.path if wt else "", branch=wt.branch if wt else ""
        )

    # ------------------------------------------------------------------
    # 列出 / 查询
    # ------------------------------------------------------------------

    def list_worktrees(self) -> list[Worktree]:
        return list(self.active.values())

    def get_current_session(self) -> WorktreeSession | None:
        return self.current_session

    # ------------------------------------------------------------------
    # 从持久化的 session 中恢复
    # ------------------------------------------------------------------

    def restore_session(self) -> WorktreeSession | None:
        session = load_worktree_session(self._GCode_dir)
        if session is None:
            return None
        report = self.reconcile()
        wt = self.active.get(session.worktree_name)
        if (
            report.get(session.worktree_name) != "verified"
            or wt is None
            or str(Path(session.worktree_path).resolve()) != wt.path
        ):
            # Preserve the session for investigation; do not erase unknown state.
            return None
        self.current_session = session
        return session

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _get_current_branch(self) -> str:
        try:
            result = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
            return result.stdout.strip() if result.returncode == 0 else "HEAD"
        except (subprocess.SubprocessError, OSError):
            return "HEAD"

    def _get_head_commit(self) -> str:
        try:
            result = self._run_git(["rev-parse", "HEAD"])
            return result.stdout.strip() if result.returncode == 0 else ""
        except (subprocess.SubprocessError, OSError):
            return ""
