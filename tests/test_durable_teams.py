import json
import multiprocessing as mp
from gcode.teams.shared_task import SharedTaskStore
from gcode.teams.mailbox import Mailbox, create_message


def _create(path, count):
    store = SharedTaskStore(path)
    for i in range(count):
        store.create(str(i))


def test_multiprocess_no_lost_tasks(tmp_path):
    path = str(tmp_path / "tasks.json")
    workers = [mp.Process(target=_create, args=(path, 20)) for _ in range(4)]
    for p in workers:
        p.start()
    for p in workers:
        p.join(30)
        assert p.exitcode == 0
    items = SharedTaskStore(path).list_tasks()
    assert len(items) == len({t.id for t in items}) == 80


def test_legacy_import_read_only(tmp_path):
    path = tmp_path / "tasks.json"
    original = json.dumps({"next_id": 9, "tasks": [{"id": "3", "title": "legacy"}]})
    path.write_text(original)
    store = SharedTaskStore(path)
    assert store.get("3").title == "legacy"
    assert int(store.create("new").id) >= 9
    assert path.read_text() == original
    assert len(SharedTaskStore(path).list_tasks()) == 2


def test_mail_claim_ack_and_idempotency(tmp_path):
    a = Mailbox(tmp_path)
    m = create_message("a", "b", "hello")
    a.write("b", m)
    a.write("b", m)
    assert len(a.claim("b", "owner")) == 1
    b = Mailbox(tmp_path)
    assert b.claim("b", "other") == []
    assert not b.ack("b", m.id, "other")
    assert b.ack("b", m.id, "owner")
    assert b.read("b") == []
    b.write("b", m)
    assert b.read("b") == []


def test_team_config_stale_writer_cannot_clobber(tmp_path):
    import pytest
    from gcode.teams.models import AgentTeam, TeammateInfo

    path = str(tmp_path / "config.json")
    first = AgentTeam(name="team", lead_agent_id="lead", config_path=path)
    first.save()
    second = AgentTeam.load(path)
    first.add_member(TeammateInfo("first", "a", "general", "m", "", "in-process"))
    first.save()
    second.add_member(TeammateInfo("second", "b", "general", "m", "", "in-process"))
    with pytest.raises(RuntimeError):
        second.save()
    assert [m.name for m in AgentTeam.load(path).members] == ["first"]


def test_lead_ack_only_after_persist(tmp_path):
    import pytest
    from gcode.teams.manager import TeamManager
    from gcode.teams.models import AgentTeam

    manager = TeamManager()
    mailbox = Mailbox(tmp_path / "mailbox")
    team = AgentTeam(name="t", lead_agent_id="lead")
    manager._teams["t"] = team
    manager._mailboxes["t"] = mailbox
    message = create_message("worker", "lead", "finished")
    mailbox.write("lead", message)
    assert len(manager.drain_lead_mailbox()) == 1 and len(mailbox.read("lead")) == 1
    seen = []
    assert len(manager.drain_lead_mailbox(persist=lambda note: seen.append(note))) == 1
    assert message.id in seen[0] and mailbox.read("lead") == []
    bad = create_message("worker", "lead", "uncertain")
    mailbox.write("lead", bad)

    def failed(note):
        raise RuntimeError("checkpoint failed")

    with pytest.raises(RuntimeError):
        manager.drain_lead_mailbox(persist=failed)
    assert [m.id for m in mailbox.read("lead")] == [bad.id]
    assert mailbox.claim("lead", "second") == []
