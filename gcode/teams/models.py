from __future__ import annotations

import json
import fcntl
import os
import uuid
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from gcode.teams.progress import TeammateProgress


class BackendType(str, Enum):
    TMUX = "tmux"
    ITERM2 = "iterm2"
    IN_PROCESS = "in-process"


@dataclass
class TeammateInfo:
    name: str
    agent_id: str
    agent_type: str
    model: str
    worktree_path: str
    backend_type: str  # BackendType value
    is_active: bool | None = None
    progress: Optional[TeammateProgress] = None

    def to_dict(self) -> dict:
        # Exclude progress (runtime-only, contains threading.Lock)
        return {
            "name": self.name,
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "model": self.model,
            "worktree_path": self.worktree_path,
            "backend_type": self.backend_type,
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TeammateInfo:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def _sanitize_name(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]", "-", name.strip().lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "team"


@dataclass
class AgentTeam:
    name: str
    lead_agent_id: str
    members: list[TeammateInfo] = field(default_factory=list)
    config_path: str = ""
    description: str = ""
    _revision: int = field(default=0, repr=False, compare=False)

    def get_member(self, name: str) -> TeammateInfo | None:
        for m in self.members:
            if m.name == name or m.agent_id == name:
                return m
        return None

    def add_member(self, member: TeammateInfo) -> None:
        self.members.append(member)

    def remove_member(self, name: str) -> bool:
        for i, m in enumerate(self.members):
            if m.name == name or m.agent_id == name:
                self.members.pop(i)
                return True
        return False

    def set_member_active(self, name: str, is_active: bool | None) -> bool:
        member = self.get_member(name)
        if member is None:
            return False
        member.is_active = is_active
        return True

    def all_idle(self) -> bool:
        return all(m.is_active is False for m in self.members)

    def active_members(self) -> list[TeammateInfo]:
        return [m for m in self.members if m.is_active is not False]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "lead_agent_id": self.lead_agent_id,
            "members": [m.to_dict() for m in self.members],
            "config_path": self.config_path,
            "description": self.description,
            "revision": self._revision,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AgentTeam:
        members = [TeammateInfo.from_dict(m) for m in data.get("members", [])]
        return cls(
            name=data["name"],
            lead_agent_id=data["lead_agent_id"],
            members=members,
            config_path=data.get("config_path", ""),
            description=data.get("description", ""),
            _revision=data.get("revision", 0),
        )

    def save(self) -> None:
        path = Path(self.config_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.with_name(path.name + ".lock").open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                current = (
                    json.loads(path.read_text(encoding="utf-8")).get("revision", 0)
                    if path.exists()
                    else 0
                )
                if current != self._revision:
                    raise RuntimeError("team state changed; reload before saving")
                data = self.to_dict()
                data["revision"] = current + 1
                temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
                try:
                    with temporary.open("x", encoding="utf-8") as stream:
                        json.dump(data, stream, indent=2, ensure_ascii=False)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(temporary, path)
                    directory_fd = os.open(path.parent, os.O_RDONLY)
                    try:
                        os.fsync(directory_fd)
                    finally:
                        os.close(directory_fd)
                    self._revision = current + 1
                finally:
                    temporary.unlink(missing_ok=True)
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    @classmethod
    def load(cls, config_path: str) -> AgentTeam:
        data = json.loads(Path(config_path).read_text(encoding="utf-8"))
        team = cls.from_dict(data)
        team.config_path = config_path
        return team


def resolve_team_dir(team_name: str) -> Path:
    slug = _sanitize_name(team_name)
    return Path.home() / ".gcode" / "teams" / slug


def unique_team_name(team_name: str) -> str:
    slug = _sanitize_name(team_name)
    base_dir = Path.home() / ".gcode" / "teams"
    if not (base_dir / slug).exists():
        return slug
    counter = 2
    while (base_dir / f"{slug}-{counter}").exists():
        counter += 1
    return f"{slug}-{counter}"
