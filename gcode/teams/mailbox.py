from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MailboxMessage:
    id: str
    from_agent: str
    to_agent: str
    content: str
    summary: str = ""
    message_type: str = "text"  # text | shutdown_request | shutdown_response
    timestamp: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MailboxMessage:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class Mailbox:
    def __init__(self, base_dir: str | Path) -> None:
        from gcode.runtime.store import RunStore

        self._base_dir = Path(base_dir)
        self._store = RunStore(self._base_dir / "mailbox.sqlite3")
        # Legacy files are imported without modifying or removing the originals.
        with self._store.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS mailbox_imports(path TEXT PRIMARY KEY)"
            )
            db.execute("BEGIN IMMEDIATE")
            for path in self._base_dir.glob("*/*.json"):
                source = str(path.resolve())
                if db.execute(
                    "SELECT 1 FROM mailbox_imports WHERE path=?", (source,)
                ).fetchone():
                    continue
                try:
                    message = MailboxMessage.from_dict(
                        json.loads(path.read_text(encoding="utf-8"))
                    )
                except (OSError, ValueError, TypeError, KeyError):
                    continue
                db.execute(
                    "INSERT OR IGNORE INTO messages(recipient,id,payload) VALUES(?,?,?)",
                    (
                        path.parent.name,
                        message.id,
                        json.dumps(message.to_dict(), ensure_ascii=False),
                    ),
                )
                db.execute("INSERT INTO mailbox_imports VALUES(?)", (source,))
            db.commit()

    def write(self, agent_id: str, message: MailboxMessage) -> None:
        payload = json.dumps(message.to_dict(), ensure_ascii=False, sort_keys=True)
        with self._store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT payload FROM messages WHERE recipient=? AND id=?",
                (agent_id, message.id),
            ).fetchone()
            if row and json.loads(row[0]) != json.loads(payload):
                db.rollback()
                raise ValueError("message id reused with different payload")
            db.execute(
                "INSERT OR IGNORE INTO messages(recipient,id,payload) VALUES(?,?,?)",
                (agent_id, message.id, payload),
            )
            db.commit()

    def read(self, agent_id: str) -> list[MailboxMessage]:
        with self._store.connect() as db:
            rows = db.execute(
                "SELECT payload FROM messages WHERE recipient=? AND state != 'acked' ORDER BY rowid",
                (agent_id,),
            ).fetchall()
        return [MailboxMessage.from_dict(json.loads(r[0])) for r in rows]

    def claim(self, agent_id: str, owner: str, ttl: float = 60) -> list[MailboxMessage]:
        if not owner or ttl <= 0:
            raise ValueError("owner and positive ttl required")
        # Expired claims are intentionally not replayed: a side effect may have happened.
        with self._store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                "SELECT id,payload FROM messages WHERE recipient=? AND state='pending' ORDER BY rowid",
                (agent_id,),
            ).fetchall()
            for row in rows:
                db.execute(
                    "UPDATE messages SET state='claimed', owner=?, expires=? WHERE recipient=? AND id=? AND state='pending'",
                    (owner, time.time() + ttl, agent_id, row["id"]),
                )
            db.commit()
        return [MailboxMessage.from_dict(json.loads(r["payload"])) for r in rows]

    def ack(self, agent_id: str, message_id: str, owner: str) -> bool:
        with self._store.connect() as db:
            return (
                db.execute(
                    "UPDATE messages SET state='acked' WHERE recipient=? AND id=? AND state='claimed' AND owner=?",
                    (agent_id, message_id, owner),
                ).rowcount
                == 1
            )

    def release(self, agent_id: str, message_id: str, owner: str) -> bool:
        with self._store.connect() as db:
            return (
                db.execute(
                    "UPDATE messages SET state='pending', owner=NULL, expires=NULL WHERE recipient=? AND id=? AND state='claimed' AND owner=?",
                    (agent_id, message_id, owner),
                ).rowcount
                == 1
            )

    def consume(self, agent_id: str) -> list[MailboxMessage]:
        # Compatibility read: callers must explicitly claim and ACK after durable use.
        return self.read(agent_id)

    def broadcast(
        self, team_members: list[str], message: MailboxMessage, exclude: str = ""
    ) -> None:
        for agent_id in team_members:
            if agent_id != exclude:
                self.write(agent_id, message)

    def cleanup(self, agent_id: str) -> None:
        # Retain durable receipts and legacy files for recovery.
        pass

    def cleanup_all(self) -> None:
        pass


def create_message(
    from_agent: str,
    to_agent: str,
    content: str,
    summary: str = "",
    message_type: str = "text",
    metadata: dict[str, Any] | None = None,
) -> MailboxMessage:
    return MailboxMessage(
        id=uuid.uuid4().hex[:12],
        from_agent=from_agent,
        to_agent=to_agent,
        content=content,
        summary=summary,
        message_type=message_type,
        timestamp=time.time(),
        metadata=metadata or {},
    )
