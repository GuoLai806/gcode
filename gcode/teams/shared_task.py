from __future__ import annotations
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from gcode.runtime.store import RunStore


@dataclass
class SharedTask:
    id: str
    title: str
    description: str = ""
    status: str = "pending"
    assignee: str = ""
    blocks: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)
    created_by: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class SharedTaskStore:
    def __init__(self, path):
        self._path = Path(path)
        self._db = RunStore(str(self._path) + ".sqlite3")
        with self._db.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS shared_tasks(id INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0)"
            )
            db.execute("CREATE TABLE IF NOT EXISTS imports(source TEXT PRIMARY KEY)")
            db.execute("BEGIN IMMEDIATE")
            source = str(self._path.resolve())
            if (
                self._path.exists()
                and not db.execute(
                    "SELECT 1 FROM imports WHERE source=?", (source,)
                ).fetchone()
            ):
                data = json.loads(self._path.read_text(encoding="utf-8"))
                for item in data.get("tasks", []):
                    db.execute(
                        "INSERT OR IGNORE INTO shared_tasks(id,payload) VALUES(?,?)",
                        (int(item["id"]), json.dumps(item, ensure_ascii=False)),
                    )
                next_id = int(data.get("next_id", 1))
                if next_id > 1:
                    db.execute(
                        "INSERT OR IGNORE INTO sqlite_sequence(name,seq) VALUES('shared_tasks',?)",
                        (next_id - 1,),
                    )
                    db.execute(
                        "UPDATE sqlite_sequence SET seq=MAX(seq,?) WHERE name='shared_tasks'",
                        (next_id - 1,),
                    )
                db.execute("INSERT INTO imports VALUES(?)", (source,))
            db.commit()

    def init_empty(self):
        # Initialization is deliberately non-destructive, including for a reopened store.
        pass

    def create(
        self,
        title,
        description="",
        assignee="",
        blocks=None,
        blocked_by=None,
        created_by="",
    ):
        with self._db.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            cur = db.execute("INSERT INTO shared_tasks(payload) VALUES('{}')")
            task = SharedTask(
                str(cur.lastrowid),
                title,
                description,
                assignee=assignee,
                blocks=blocks or [],
                blocked_by=blocked_by or [],
                created_by=created_by,
            )
            db.execute(
                "UPDATE shared_tasks SET payload=? WHERE id=?",
                (json.dumps(task.to_dict(), ensure_ascii=False), cur.lastrowid),
            )
            db.commit()
            return task

    def get(self, task_id):
        with self._db.connect() as db:
            row = db.execute(
                "SELECT payload FROM shared_tasks WHERE id=?", (task_id,)
            ).fetchone()
            return SharedTask.from_dict(json.loads(row[0])) if row else None

    def list_tasks(self, status=None, assignee=None):
        with self._db.connect() as db:
            rows = db.execute("SELECT payload FROM shared_tasks ORDER BY id").fetchall()
        tasks = [SharedTask.from_dict(json.loads(r[0])) for r in rows]
        return [
            t
            for t in tasks
            if (not status or t.status == status)
            and (not assignee or t.assignee == assignee)
        ]

    def update(
        self,
        task_id,
        status=None,
        assignee=None,
        description=None,
        add_blocks=None,
        add_blocked_by=None,
    ):
        with self._db.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT payload FROM shared_tasks WHERE id=?", (task_id,)
            ).fetchone()
            if not row:
                db.rollback()
                return None
            task = SharedTask.from_dict(json.loads(row[0]))
            for key, value in [
                ("status", status),
                ("assignee", assignee),
                ("description", description),
            ]:
                if value is not None:
                    setattr(task, key, value)
            for attr, values in [
                ("blocks", add_blocks),
                ("blocked_by", add_blocked_by),
            ]:
                for value in values or []:
                    if value not in getattr(task, attr):
                        getattr(task, attr).append(value)
            db.execute(
                "UPDATE shared_tasks SET payload=?,revision=revision+1 WHERE id=?",
                (json.dumps(task.to_dict(), ensure_ascii=False), task_id),
            )
            db.commit()
            return task
