import asyncio
import json
import shutil
from pathlib import Path

import pytest
from gcode.cu.transport import CUError, CUTransport

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
pytestmark = [pytest.mark.asyncio, pytest.mark.skipif(not NODE, reason="Node required")]


@pytest.fixture
def setup_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("GCODE_CU_MACHINE_DIR", str(tmp_path / "state"))
    p = tmp_path / "synthetic.mjs"
    p.write_text(
        """export async function createBridge(){return {schemas:[{name:"ax_action",input_schema:{type:"object"}}],async call(method, params){if(params.hang) await new Promise(()=>{}); if(params.large) return {content:[{type:'text',text:'z'.repeat(2100000)}],details:{synthetic:true}}; return {content:[{type:"text",text:JSON.stringify(params)}],details:{synthetic:true},delivery_state:'delivered_unverified'}}}}"""
    )
    return p, tmp_path / "state"


def transport(setup_provider):
    p, state = setup_provider
    return CUTransport(NODE, ROOT / "sidecar/server.mjs", p, state)


async def test_roundtrip_duplicate_and_owner(setup_provider):
    t = transport(setup_provider)
    await t.start()
    assert (await t.hello("r", "s"))["capabilities"][0]["name"] == "ax_action"
    one = await t.call(
        "ax_action", {"x": "汉字"}, run_id="r", session_id="s", action_id="a"
    )
    two = await t.call(
        "ax_action", {"x": "汉字"}, run_id="r", session_id="s", action_id="a"
    )
    assert one["content"] == two["content"]
    assert (
        await t.call("ax_action", {}, run_id="other", session_id="s", action_id="a")
    )["error"]["code"] == "ACTION_OWNER_MISMATCH"
    assert (
        await t.call("ax_action", {}, run_id="other", session_id="s", action_id="b")
    )["error"]["code"] == "LEASE_HELD"
    await t.shutdown("r", "s")
    t = transport(setup_provider)
    await t.start()
    assert (
        await t.call(
            "ax_action", {"x": "汉字"}, run_id="r", session_id="s", action_id="a"
        )
    )["content"] == one["content"]
    await t.shutdown("r", "s")


async def test_timeout_persists_global_stop(setup_provider):
    t = transport(setup_provider)
    await t.start()
    r = await t.call(
        "ax_action",
        {"hang": True},
        run_id="r",
        session_id="s",
        action_id="a",
        timeout_ms=20,
    )
    assert r["delivery_state"] == "delivery_unknown"
    assert (await t.status("r", "s"))["details"]["stopped"]
    await t.shutdown("r", "s")
    t = transport(setup_provider)
    await t.start()
    assert (
        await t.call("ax_action", {}, run_id="new", session_id="new", action_id="b")
    )["error"]["code"] == "WRITES_STOPPED"
    await t.shutdown("r", "s")


async def test_frame_limit_and_crash(setup_provider):
    t = transport(setup_provider)
    await t.start()
    with pytest.raises(CUError, match="256 KiB"):
        await t.call("ax_query", {"x": "x" * 300000}, run_id="r", session_id="s")
    t._proc.kill()
    await t._proc.wait()
    with pytest.raises(CUError):
        await t.call("ax_query", {}, run_id="r", session_id="s")
    await t.shutdown("r", "s")


@pytest.mark.parametrize("request_fails", [False, True])
async def test_shutdown_bounds_uncooperative_process_and_always_cleans(
    tmp_path, request_fails
):
    server = tmp_path / "uncooperative.mjs"
    server.write_text("""process.on('SIGTERM',()=>{});process.stdin.setEncoding('utf8');let b='';
process.stdin.on('data',x=>{b+=x;let i;while((i=b.indexOf('\\n'))>=0){let r=JSON.parse(b.slice(0,i));b=b.slice(i+1);
console.log(JSON.stringify({v:1,id:r.id,ok:r.method==='hello'||r.method==='shutdown'}));}});
process.stdin.on('end',()=>{});setInterval(()=>{},1000);""")
    provider = tmp_path / "unused.mjs"
    provider.write_text("// synthetic process, no native calls")
    t = CUTransport(NODE, server, provider, tmp_path)
    await t.start()
    await t.hello("r", "s")
    if request_fails:
        # EOF in the response path must still run termination in finally.
        server_proc = t._proc
        original_call = t.call

        async def fail(*args, **kwargs):
            raise CUError("SYNTHETIC", "failed shutdown request")

        t.call = fail
        with pytest.raises(CUError, match="failed shutdown"):
            await asyncio.wait_for(t.shutdown("r", "s"), 4)
        t.call = original_call
        assert server_proc.returncode is not None
    else:
        await asyncio.wait_for(t.shutdown("r", "s"), 4)
    assert t._proc.returncode is not None and t._dead


async def test_crash_after_dispatch_never_replays(setup_provider):
    t = transport(setup_provider)
    await t.start()
    pending = asyncio.create_task(
        t.call(
            "ax_action",
            {"hang": True},
            run_id="r",
            session_id="s",
            action_id="crash",
            timeout_ms=5000,
        )
    )
    ledger = setup_provider[1] / "ledger.json"
    for _ in range(100):
        if ledger.exists() and json.loads(ledger.read_text()).get("actions", {}).get(
            "crash"
        ):
            break
        await asyncio.sleep(0.01)
    assert json.loads(ledger.read_text())["actions"]["crash"]["state"] == "dispatching"
    t._proc.kill()
    await t._proc.wait()
    with pytest.raises(CUError) as e:
        await pending
    assert e.value.delivery_state == "delivery_unknown"
    # Crash lock requires explicit operator confirmation that the previous process is gone.
    (setup_provider[1] / "writer.lock" / "owner.json").unlink()
    (setup_provider[1] / "writer.lock").rmdir()
    t = transport(setup_provider)
    await t.start()
    again = await t.call(
        "ax_action", {"hang": True}, run_id="r", session_id="s", action_id="crash"
    )
    assert again["delivery_state"] == "delivery_unknown"
    assert (await t.call("ax_action", {}, run_id="r", session_id="s", action_id="new"))[
        "error"
    ]["code"] == "WRITES_STOPPED"
    await t.shutdown("r", "s")


async def test_large_response_preserves_artifact(setup_provider):
    import hashlib

    t = transport(setup_provider)
    await t.start()
    r = await t.call("ax_query", {"large": True}, run_id="r", session_id="s")
    ref = r["artifact_reference"]
    data = Path(ref["path"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == ref["sha256"]
    assert len(json.loads(data)["content"][0]["text"]) == 2100000
    await t.shutdown("r", "s")


async def test_raw_oversized_frame_rejected(setup_provider):
    import os

    provider, state = setup_provider
    env = dict(
        os.environ, GCODE_CU_PROVIDER=str(provider), GCODE_CU_STATE_DIR=str(state)
    )
    proc = await asyncio.create_subprocess_exec(
        NODE,
        str(ROOT / "sidecar/server.mjs"),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        env=env,
    )
    out, _ = await proc.communicate(b"x" * (256 * 1024 + 1) + b"\n")
    assert json.loads(out)["error"]["code"] == "FRAME_TOO_LARGE"


async def test_machine_lease_across_distinct_state_directories(
    setup_provider, tmp_path
):
    provider, state = setup_provider
    first = transport(setup_provider)
    await first.start()
    assert (await first.hello("r", "s"))["ok"]
    second = CUTransport(
        NODE, ROOT / "sidecar/server.mjs", provider, tmp_path / "other-state"
    )
    await second.start()
    with pytest.raises(CUError):
        await second.hello("r2", "s2")
    await second.shutdown("r2", "s2")
    await first.shutdown("r", "s")


async def test_cancel_active_action_is_uncertain(setup_provider):
    t = transport(setup_provider)
    await t.start()
    action = asyncio.create_task(
        t.call(
            "ax_action",
            {"hang": True},
            run_id="r",
            session_id="s",
            action_id="cancel",
            timeout_ms=100,
        )
    )
    await asyncio.sleep(0.03)
    with pytest.raises(CUError) as error:
        await t.cancel("r", "s")
    assert (
        error.value.code == "CANCEL_UNCONFIRMED"
        and error.value.delivery_state == "delivery_unknown"
    )
    assert (await action)["delivery_state"] == "delivery_unknown"
    await t.shutdown("r", "s")


async def test_original_receipt_classifier():
    provider = ROOT / "sidecar/pi-local-provider.mjs"
    source = """import {classifyReceipt as c} from process.argv[1];"""
    # Dynamic import keeps the tested adapter independent of the private bridge.
    source = """const {classifyReceipt:c}=await import(process.argv[1]);
    const e=(obj)=>[{mutating:true,command:'click',result:{stdout:JSON.stringify(obj),code:0,killed:false}}];
    const good={ok:true,command:'click',data:{action:'click',disposition:{delivery:'delivered_unverified',retry:'unsafe'}}};
    const bad={ok:true,command:'click',data:{action:'click'}};
    const safe={ok:false,command:'click',error:{disposition:{delivery:'not_delivered',retry:'safe'}}};
    console.log(JSON.stringify([c({},e(good),{}).delivery_state,c({},e(bad),{}).delivery_state,c({},e(safe),{}).delivery_state,c({details:{nativeWritesStopped:true}},e(good),{}).delivery_state]));"""
    proc = await asyncio.create_subprocess_exec(
        NODE,
        "--input-type=module",
        "-e",
        source,
        provider.as_uri(),
        stdout=asyncio.subprocess.PIPE,
    )
    output, _ = await proc.communicate()
    assert proc.returncode == 0
    assert json.loads(output) == [
        "delivered_unverified",
        "delivery_unknown",
        "not_delivered",
        "delivery_unknown",
    ]


async def test_manifest_hashes_detect_changed_dependencies(tmp_path):
    import hashlib, os

    core = tmp_path / "core"
    (core / "desktop-stability").mkdir(parents=True)
    dep = core / "bridge.mjs"
    dep.write_text("bridge")
    binary = tmp_path / "binary"
    binary.write_text("binary")
    sdk = tmp_path / "package.json"
    sdk.write_text("{}")
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = core / "desktop-stability" / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "files": [{"path": "bridge.mjs", "sha256": sha(dep)}],
                "dependencies": [{"file": str(binary), "sha256": sha(binary)}],
            }
        )
    )
    env = dict(
        os.environ,
        GCODE_PI_EXTENSION=str(dep),
        PI_AGENT_DESKTOP_BINARY=str(binary),
        GCODE_PI_SDK_PACKAGE=str(sdk),
        GCODE_PI_MANIFEST=str(manifest),
    )
    script = "const p=await import(process.argv[1]); console.log(JSON.stringify(await p.identity()))"

    async def run():
        proc = await asyncio.create_subprocess_exec(
            NODE,
            "--input-type=module",
            "-e",
            script,
            (ROOT / "sidecar/pi-local-provider.mjs").as_uri(),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        return proc.returncode, out, err

    code, out, _ = await run()
    assert code == 0 and json.loads(out)["manifest_verified"] is True
    dep.write_text("changed")
    code, _, err = await run()
    assert code != 0 and b"hash mismatch" in err


async def test_unknown_action_is_sticky_and_status_scoped(setup_provider):
    provider, state = setup_provider
    provider.write_text(
        "export async function createBridge(){return {schemas:[],async call(){return {content:[],details:{}}}}}"
    )
    t = transport(setup_provider)
    await t.start()
    action = await t.call("ax_action", {}, run_id="r", session_id="s", action_id="id")
    assert action["delivery_state"] == "delivery_unknown"
    assert (await t.status("other", "s"))["details"]["actions"] == {}
    assert (
        await t.call("ax_action", {}, run_id="other", session_id="s", action_id="next")
    )["error"]["code"] == "WRITES_STOPPED"
    await t.shutdown("r", "s")


async def test_duplicate_id_different_payload_rejected(setup_provider):
    t = transport(setup_provider)
    await t.start()
    await t.call("ax_action", {"v": 1}, run_id="r", session_id="s", action_id="same")
    result = await t.call(
        "ax_action", {"v": 2}, run_id="r", session_id="s", action_id="same"
    )
    assert result["error"]["code"] == "ACTION_ID_CONFLICT"
    await t.shutdown("r", "s")


async def test_uncorrelated_response_is_never_accepted(tmp_path):
    fake = tmp_path / "fake-server.mjs"
    fake.write_text(
        "process.stdin.once('data',()=>{console.log(JSON.stringify({v:1,id:'wrong',ok:true}));process.exit(0)})"
    )
    provider = tmp_path / "unused.mjs"
    provider.write_text("")
    t = CUTransport(NODE, fake, provider, tmp_path / "state")
    await t.start()
    with pytest.raises(CUError) as error:
        await t.call("ax_action", {}, run_id="r", session_id="s", action_id="a")
    assert error.value.delivery_state == "delivery_unknown"
    await t.shutdown("r", "s")


async def test_native_read_outcome_requires_matching_success_receipt():
    provider = ROOT / "sidecar/pi-local-provider.mjs"
    script = """const {classifyRead:c}=await import(process.argv[1]);
    const e=(n,code=0,killed=false)=>[{command:'list-windows',result:{stdout:JSON.stringify(n),code,killed}}];
    const good={ok:true,command:'list-windows',data:[]};
    const absent={ok:false,command:'list-windows',error:{code:'APP_NOT_FOUND'}};
    const values=[c({},e(good)),c({},e(absent,1)),c({},e(good,1)),c({},e({...good,command:'snapshot'})),c({},[]),c({details:{originalCli:false,nativeDecisionSurfaceCurrent:true,decisionSurface:{snapshotId:'s'}}},[])];
    console.log(JSON.stringify(values.map(v=>({isError:v.isError,outcome:v.read_outcome,code:v.receipt[0]?.native?.error?.code}))));"""
    proc = await asyncio.create_subprocess_exec(
        NODE,
        "--input-type=module",
        "-e",
        script,
        provider.as_uri(),
        stdout=asyncio.subprocess.PIPE,
    )
    out, _ = await proc.communicate()
    assert proc.returncode == 0
    results = json.loads(out)
    assert [r["isError"] for r in results] == [False, True, True, True, True, False]
    assert results[1]["code"] == "APP_NOT_FOUND"
    assert results[-1]["outcome"] == "current_surface_reused"


def preparation_fixture(tmp_path):
    import hashlib

    dump = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
    sha = lambda b: hashlib.sha256(b).hexdigest()
    app = "SyntheticApp"
    inst = "macos-proc-v1:100:200"
    wid = "w-12"
    pid = 321
    params = {"type": "launch", "app": app, "activate": False}
    fingerprint = sha(dump(["ax_action", params, None]).encode())
    launch = {
        "ok": True,
        "command": "launch",
        "data": {
            "app": app,
            "pid": pid,
            "process_instance": inst,
            "window": {"id": wid, "pid": pid, "process_instance": inst},
        },
    }
    snapshot = {
        "ok": True,
        "command": "snapshot",
        "data": {"app": app, "complete": True, "window": {"id": wid}},
    }
    observation = {"target": "task", "native": snapshot}
    response = {
        "ok": True,
        "content": [
            {
                "type": "text",
                "text": "ORIGINAL NATIVE ACTION RECEIPT (not proof of task success)\n"
                + dump(launch)
                + "\n\nCLI exit=0, killed=false\n",
            }
        ],
        "details": {"nativeWritesStopped": False, "axObservation": observation},
        "receipt": None,
        "delivery_state": "delivery_unknown",
        "verification_state": "unknown",
    }
    identity = {
        "native_sha256": "a" * 64,
        "bridge_sha256": "b" * 64,
        "manifest_sha256": "c" * 64,
        "manifest_verified": True,
        "process_nonce": "old",
        "process_started_at": "2026-11-05T12:00:00Z",
    }
    original = {
        "result": {
            "is_error": False,
            "details": {"runtime_identity": identity, **response},
        }
    }
    inventory = {
        "ok": True,
        "command": "list-windows",
        "data": [{"id": wid, "pid": pid, "process_instance": inst, "app_name": app}],
    }
    fresh_identity = {
        **identity,
        "process_nonce": "fresh",
        "process_started_at": "2026-11-05T12:00:01Z",
    }
    fresh = {
        "result": {
            "is_error": False,
            "details": {
                "ok": True,
                "runtime_identity": fresh_identity,
                "details": {"nativeWritesStopped": False},
                "receipt": [
                    {
                        "command": "list-windows",
                        "exit_code": 0,
                        "killed": False,
                        "native": inventory,
                    }
                ],
            },
        }
    }
    state = tmp_path / "machine"
    state.mkdir()
    action = "action1"
    owner = '["run","session"]'
    ledger = {
        "version": 1,
        "stopped": True,
        "owner": owner,
        "actions": {
            action: {
                "owner": owner,
                "fingerprint": fingerprint,
                "state": "delivery_unknown",
                "response": response,
            }
        },
    }
    (state / "ledger.json").write_text(dump(ledger))

    def file(name, obj):
        p = tmp_path / name
        p.write_text(dump(obj))
        return p, sha(p.read_bytes())

    orig, oh = file("original.json", original)
    f, fh = file("fresh.json", fresh)
    return state, action, params, orig, oh, f, fh, ledger, original, fresh


async def run_reconcile(case):
    state, action, params, orig, oh, f, fh, *_ = case
    import hashlib

    original = json.loads(orig.read_text())
    receipt = original["result"]["details"]["content"][0]["text"]
    receipt_hash = hashlib.sha256(receipt.encode()).hexdigest()
    proc = await asyncio.create_subprocess_exec(
        NODE,
        str(ROOT / "sidecar/reconcile-preparation.mjs"),
        "--machine-dir",
        str(state),
        "--action-id",
        action,
        "--params-json",
        json.dumps(params, separators=(",", ":")),
        "--original-evidence",
        str(orig),
        "--original-sha256",
        oh,
        "--receipt-sha256",
        receipt_hash,
        "--fresh-evidence",
        str(f),
        "--fresh-sha256",
        fh,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    return proc.returncode, out, err


async def test_reconcile_only_proven_launch_preserves_original(tmp_path, monkeypatch):
    case = preparation_fixture(tmp_path)
    state = case[0]
    code, out, err = await run_reconcile(case)
    assert code == 0, err
    assert json.loads(out)["classification"] == "delivered_unverified"
    ledger = json.loads((state / "ledger.json").read_text())
    a = ledger["actions"]["action1"]
    assert (
        a["state"] == "preparation_reconciled"
        and a["response"]["delivery_state"] == "delivery_unknown"
    )
    assert (
        ledger["stopped"] is False
        and ledger["reconciliation"]["old_state"] == "delivery_unknown"
    )
    monkeypatch.setenv("GCODE_CU_MACHINE_DIR", str(state))
    p = tmp_path / "synthetic.mjs"
    p.write_text(
        "export async function createBridge(){return {schemas:[],async call(){return {content:[],details:{}}}}}"
    )
    t = CUTransport(NODE, ROOT / "sidecar/server.mjs", p, tmp_path / "transport")
    await t.start()
    status = await t.status("run", "session")
    assert status["details"]["stopped"] is False
    await t.shutdown("run", "session")


@pytest.mark.parametrize(
    "mutation",
    [
        "pid",
        "instance",
        "window",
        "hash",
        "payload",
        "fingerprint",
        "extra_action",
        "bridge_stopped",
        "incomplete_snapshot",
        "manifest",
        "native_error",
        "same_process",
        "stale_file",
    ],
)
async def test_reconcile_rejects_uncertain_or_nonlaunch(tmp_path, mutation):
    import hashlib

    case = list(preparation_fixture(tmp_path))
    state, action, params, orig, oh, f, fh, ledger, original, fresh = case
    if mutation == "pid":
        fresh["result"]["details"]["receipt"][0]["native"]["data"][0]["pid"] = 999
    elif mutation == "instance":
        fresh["result"]["details"]["receipt"][0]["native"]["data"][0][
            "process_instance"
        ] = "macos-proc-v1:999:999"
    elif mutation == "window":
        fresh["result"]["details"]["receipt"][0]["native"]["data"][0]["id"] = "w-99"
    elif mutation == "hash":
        case[4] = "0" * 64
    elif mutation == "payload":
        params["type"] = "click"
    elif mutation == "fingerprint":
        ledger["actions"][action]["fingerprint"] = "0" * 64
    elif mutation == "extra_action":
        ledger["actions"]["other"] = {"state": "delivery_unknown"}
    elif mutation == "bridge_stopped":
        fresh["result"]["details"]["details"]["nativeWritesStopped"] = True
    elif mutation == "incomplete_snapshot":
        # Both copies must agree with the persisted original; then the observation itself is invalid.
        ledger["actions"][action]["response"]["details"]["axObservation"]["native"][
            "data"
        ]["complete"] = False
        original["result"]["details"]["details"]["axObservation"]["native"]["data"][
            "complete"
        ] = False
    elif mutation == "manifest":
        fresh["result"]["details"]["runtime_identity"]["manifest_verified"] = False
    elif mutation == "same_process":
        fresh["result"]["details"]["runtime_identity"]["process_nonce"] = "old"
    elif mutation == "native_error":
        fresh["result"]["details"]["receipt"][0]["native"]["ok"] = False
    dump = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
    (state / "ledger.json").write_text(dump(ledger))
    orig.write_text(dump(original))
    f.write_text(dump(fresh))
    if mutation != "hash":
        case[4] = hashlib.sha256(orig.read_bytes()).hexdigest()
    case[6] = hashlib.sha256(f.read_bytes()).hexdigest()
    if mutation == "stale_file":
        import os, time

        os.utime(f, (time.time() - 600, time.time() - 600))
    code, _, _ = await run_reconcile(case)
    assert code != 0
    assert json.loads((state / "ledger.json").read_text())["stopped"] is True


async def test_launch_classification_requires_process_and_fresh_observation():
    provider = ROOT / "sidecar/pi-local-provider.mjs"
    script = """const {classifyReceipt:c}=await import(process.argv[1]);
    const pid=123, pi='macos-proc-v1:1:2', id='w-1', app='SyntheticApp';
    const launch={ok:true,command:'launch',data:{app,pid,process_instance:pi,window:{id,pid,process_instance:pi}}};
    const snap={ok:true,command:'snapshot',data:{app,complete:true,window:{id}}};
    const inventory={ok:true,command:'list-windows',data:[{id,pid,process_instance:pi,app_name:app}]};
    const e=(command,n)=>({command,mutating:command==='launch',result:{code:0,killed:false,stdout:JSON.stringify(n)}});
    const detail={details:{nativeWritesStopped:false,axObservation:{target:'task',native:snap}}};
    const p={type:'launch',app,activate:false};
    const values=[c(detail,[e('launch',launch),e('list-windows',inventory)],p),c(detail,[e('launch',launch),e('list-windows',{...inventory,data:[]})],p),c(detail,[e('launch',launch),e('list-windows',inventory)],{...p,activate:true}),c({...detail,details:{...detail.details,nativeWritesStopped:true}},[e('launch',launch),e('list-windows',inventory)],p)];
    console.log(JSON.stringify(values.map(v=>v.delivery_state)));"""
    proc = await asyncio.create_subprocess_exec(
        NODE,
        "--input-type=module",
        "-e",
        script,
        provider.as_uri(),
        stdout=asyncio.subprocess.PIPE,
    )
    out, _ = await proc.communicate()
    assert proc.returncode == 0
    assert json.loads(out) == [
        "delivered_unverified",
        "delivery_unknown",
        "delivery_unknown",
        "delivery_unknown",
    ]


async def test_reconciled_launch_cannot_clear_later_unknown_input(
    tmp_path, monkeypatch
):
    case = preparation_fixture(tmp_path)
    state = case[0]
    code, _, err = await run_reconcile(case)
    assert code == 0, err
    monkeypatch.setenv("GCODE_CU_MACHINE_DIR", str(state))
    p = tmp_path / "synthetic.mjs"
    p.write_text(
        "export async function createBridge(){return {schemas:[],async call(){return {content:[],details:{}}}}}"
    )
    t = CUTransport(NODE, ROOT / "sidecar/server.mjs", p, tmp_path / "transport")
    await t.start()
    res = await t.call(
        "ax_action",
        {"type": "click"},
        run_id="run",
        session_id="session",
        action_id="input",
    )
    assert res["delivery_state"] == "delivery_unknown"
    await t.shutdown("run", "session")
    code, _, _ = await run_reconcile(case)
    assert code != 0
    t = CUTransport(NODE, ROOT / "sidecar/server.mjs", p, tmp_path / "transport")
    await t.start()
    assert (await t.status("run", "session"))["details"]["stopped"] is True
    await t.shutdown("run", "session")


async def test_reconcile_rejects_wrong_native_receipt_hash(tmp_path):
    state, action, params, orig, oh, f, fh, *_ = preparation_fixture(tmp_path)
    proc = await asyncio.create_subprocess_exec(
        NODE,
        str(ROOT / "sidecar/reconcile-preparation.mjs"),
        "--machine-dir",
        str(state),
        "--action-id",
        action,
        "--params-json",
        json.dumps(params, separators=(",", ":")),
        "--original-evidence",
        str(orig),
        "--original-sha256",
        oh,
        "--receipt-sha256",
        "0" * 64,
        "--fresh-evidence",
        str(f),
        "--fresh-sha256",
        fh,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    assert proc.returncode != 0 and b"receipt hash mismatch" in err
    assert json.loads((state / "ledger.json").read_text())["stopped"] is True


@pytest.fixture
def scoped_provider(tmp_path, monkeypatch):
    state = tmp_path / "state"
    monkeypatch.setenv("GCODE_CU_MACHINE_DIR", str(state))
    provider = tmp_path / "scope.mjs"
    provider.write_text(
        """export async function createBridge(){return {schemas:[],async call(method,params){if(method==='ax_observe'){const complete=params.complete!==false;return {content:[],details:{scope:{appName:'SyntheticApp',windowId:'w-1'},axObservation:{target:'task',native:{ok:true,command:'snapshot',data:{app:'SyntheticApp',complete,window:{id:'w-1'},tree:{role:'window'}}}}}}}return {content:[{type:'text',text:'ack'}],details:{},delivery_state:'delivered_unverified'}}}}"""
    )
    return provider, state


async def test_clean_close_retains_receipts_and_new_owner_requires_binding(
    scoped_provider,
):
    t = transport(scoped_provider)
    await t.start()
    first = await t.call("ax_action", {}, run_id="r", session_id="s", action_id="a")
    assert first["delivery_state"] == "delivered_unverified"
    await t.shutdown("r", "s")
    ledger = json.loads((scoped_provider[1] / "ledger.json").read_text())
    assert (
        ledger["clean_shutdown"]["closed_owner"] == '["r","s"]'
        and ledger["owner"] is None
    )
    t = transport(scoped_provider)
    await t.start()
    replay = await t.call("ax_action", {}, run_id="r", session_id="s", action_id="a")
    assert replay["content"] == first["content"]
    assert (
        await t.call("ax_action", {}, run_id="r", session_id="s", action_id="other")
    )["error"]["code"] == "OWNER_CLOSED"
    assert (
        await t.call("ax_action", {}, run_id="new", session_id="new", action_id="b")
    )["error"]["code"] == "FRESH_BINDING_REQUIRED"
    await t.call("ax_observe", {"complete": False}, run_id="new", session_id="new")
    assert (
        await t.call("ax_action", {}, run_id="new", session_id="new", action_id="b")
    )["error"]["code"] == "FRESH_BINDING_REQUIRED"
    await t.call("ax_observe", {}, run_id="new", session_id="new")
    assert (
        await t.call("ax_action", {}, run_id="new", session_id="new", action_id="b")
    )["delivery_state"] == "delivered_unverified"
    await t.shutdown("new", "new")
    ledger = json.loads((scoped_provider[1] / "ledger.json").read_text())
    assert len(ledger["actions"]) == 2 and len(ledger["closed_owners"]) == 2


async def test_eof_after_known_action_never_clean_closes(scoped_provider):
    t = transport(scoped_provider)
    await t.start()
    await t.call("ax_action", {}, run_id="r", session_id="s", action_id="a")
    t._proc.stdin.close()
    await t._proc.wait()
    ledger = json.loads((scoped_provider[1] / "ledger.json").read_text())
    assert not ledger.get("clean_shutdown")
    t = transport(scoped_provider)
    await t.start()
    assert (await t.status("r", "s"))["details"]["stopped"] is True
    await t.shutdown("r", "s")


async def test_shutdown_unknown_action_does_not_clear_stop(setup_provider):
    p, _ = setup_provider
    p.write_text(
        "export async function createBridge(){return {schemas:[],async call(){return {content:[],details:{}}}}}"
    )
    t = transport(setup_provider)
    await t.start()
    assert (await t.call("ax_action", {}, run_id="r", session_id="s", action_id="a"))[
        "delivery_state"
    ] == "delivery_unknown"
    await t.shutdown("r", "s")
    ledger = json.loads((setup_provider[1] / "ledger.json").read_text())
    assert ledger["stopped"] is True and not ledger.get("clean_shutdown")


def known_scope_fixture(tmp_path):
    import hashlib

    dump = lambda x: json.dumps(x, separators=(",", ":"), ensure_ascii=False)
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    state = tmp_path / "machine"
    state.mkdir()
    owner = ["r", "s"]
    owner_key = dump(owner)
    pid = 99999999
    nonce = "fixture-process-uuid"
    response = {
        "ok": True,
        "content": [{"type": "text", "text": "ack"}],
        "details": {},
        "receipt": {},
        "delivery_state": "delivered_unverified",
        "verification_state": "unknown",
    }
    ledger = {
        "version": 1,
        "stopped": False,
        "owner": owner_key,
        "actions": {
            "a": {
                "owner": owner_key,
                "fingerprint": "x" * 64,
                "state": "delivered_unverified",
                "response": response,
            }
        },
    }
    (state / "ledger.json").write_text(dump(ledger))
    native = {
        "ok": True,
        "command": "snapshot",
        "data": {
            "app": "SyntheticApp",
            "complete": True,
            "window": {"id": "w-1"},
            "tree": {"role": "window"},
        },
    }
    final = {
        "request": {"method": "ax_observe", "params": {}},
        "response": {
            "is_error": False,
            "details": {
                "ok": True,
                "runtime_identity": {
                    "process_id": pid,
                    "process_nonce": nonce,
                    "manifest_verified": True,
                },
                "details": {
                    "nativeWritesStopped": False,
                    "scope": {"appName": "SyntheticApp", "windowId": "w-1"},
                    "axObservation": {"target": "task", "native": native},
                },
            },
        },
    }
    final_path = tmp_path / "final.json"
    final_path.write_text(dump(final))
    final_hash = sha(final_path)
    exit_data = {
        "version": 1,
        "owner": owner,
        "pid": pid,
        "process_nonce": nonce,
        "exit_code": 0,
        "termination": "clean_shutdown",
        "final_evidence_sha256": final_hash,
    }
    exit_path = tmp_path / "exit.json"
    exit_path.write_text(dump(exit_data))
    return (
        state,
        owner,
        final_path,
        final_hash,
        exit_path,
        sha(exit_path),
        ledger,
        final,
        exit_data,
    )


async def run_close_known(case):
    state, owner, final, fh, exit, eh, *_ = case
    proc = await asyncio.create_subprocess_exec(
        NODE,
        str(ROOT / "sidecar/close-known-run.mjs"),
        "--machine-dir",
        str(state),
        "--owner-json",
        json.dumps(owner, separators=(",", ":")),
        "--final-evidence",
        str(final),
        "--final-sha256",
        fh,
        "--exit-evidence",
        str(exit),
        "--exit-sha256",
        eh,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    return proc.returncode, out, err


async def test_offline_known_scope_closure_preserves_all_receipts(tmp_path):
    case = known_scope_fixture(tmp_path)
    state = case[0]
    before = (state / "ledger.json").read_bytes()
    code, out, err = await run_close_known(case)
    assert code == 0, err
    closed = json.loads((state / "ledger.json").read_text())
    assert closed["actions"] == json.loads(before)["actions"]
    assert (
        closed["owner"] is None
        and closed["clean_shutdown"]["source"] == "offline_operator"
    )
    assert (
        closed["clean_shutdown"]["final_evidence_sha256"] == case[3]
        and json.loads(out)["closed"]
    )
    code, _, _ = await run_close_known(case)
    assert code != 0


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown",
        "dispatching",
        "stopped",
        "owner",
        "bad_hash",
        "exit_code",
        "pid",
        "active_process",
        "incomplete",
        "bridge_stopped",
        "missing_manifest",
        "scope_mismatch",
        "wrong_method",
    ],
)
async def test_offline_closure_rejects_unsafe_states(tmp_path, mutation):
    import hashlib, os

    case = list(known_scope_fixture(tmp_path))
    state, owner, final, fh, exit, eh, ledger, observation, exit_data = case
    if mutation == "unknown":
        ledger["actions"]["a"]["state"] = "delivery_unknown"
    elif mutation == "dispatching":
        ledger["actions"]["a"]["state"] = "dispatching"
    elif mutation == "stopped":
        ledger["stopped"] = True
    elif mutation == "owner":
        case[1] = ["other", "s"]
    elif mutation == "bad_hash":
        case[3] = "0" * 64
    elif mutation == "exit_code":
        exit_data["exit_code"] = 1
    elif mutation == "pid":
        exit_data["pid"] = 99999998
    elif mutation == "active_process":
        observation["response"]["details"]["runtime_identity"]["process_id"] = (
            os.getpid()
        )
        exit_data["pid"] = os.getpid()
    elif mutation == "incomplete":
        observation["response"]["details"]["details"]["axObservation"]["native"][
            "data"
        ]["complete"] = False
    elif mutation == "bridge_stopped":
        observation["response"]["details"]["details"]["nativeWritesStopped"] = True
    elif mutation == "missing_manifest":
        observation["response"]["details"]["runtime_identity"]["manifest_verified"] = (
            False
        )
    elif mutation == "scope_mismatch":
        observation["response"]["details"]["details"]["scope"]["windowId"] = "w-2"
    elif mutation == "wrong_method":
        observation["request"]["method"] = "ax_action"
    dump = lambda x: json.dumps(x, separators=(",", ":"), ensure_ascii=False)
    (state / "ledger.json").write_text(dump(ledger))
    final.write_text(dump(observation))
    if mutation != "bad_hash":
        case[3] = hashlib.sha256(final.read_bytes()).hexdigest()
    exit_data["final_evidence_sha256"] = case[3]
    exit.write_text(dump(exit_data))
    case[5] = hashlib.sha256(exit.read_bytes()).hexdigest()
    before = (state / "ledger.json").read_bytes()
    code, _, _ = await run_close_known(case)
    assert code != 0 and (state / "ledger.json").read_bytes() == before


async def test_crash_after_ack_never_records_clean_close(scoped_provider):
    t = transport(scoped_provider)
    await t.start()
    await t.call("ax_action", {}, run_id="r", session_id="s", action_id="a")
    t._proc.kill()
    await t._proc.wait()
    ledger = json.loads((scoped_provider[1] / "ledger.json").read_text())
    assert not ledger.get("clean_shutdown")
    lock = scoped_provider[1] / "writer.lock"
    (lock / "owner.json").unlink()
    lock.rmdir()
    t = transport(scoped_provider)
    await t.start()
    assert (await t.status("r", "s"))["details"]["stopped"] is True
    await t.shutdown("r", "s")


async def test_only_active_owner_can_clean_shutdown(scoped_provider):
    t = transport(scoped_provider)
    await t.start()
    await t.call("ax_action", {}, run_id="r", session_id="s", action_id="a")
    denied = await t.call("shutdown", {}, run_id="other", session_id="other")
    assert (
        denied["error"]["code"] == "LEASE_OWNER_MISMATCH" and t._proc.returncode is None
    )
    assert not json.loads((scoped_provider[1] / "ledger.json").read_text()).get(
        "clean_shutdown"
    )
    await t.shutdown("r", "s")


async def test_shutdown_terminates_owned_descendant_process_group(
    tmp_path, monkeypatch
):
    import os
    import subprocess

    if os.name != "posix":
        pytest.skip("POSIX process group")
    child = tmp_path / "owned-descendant.mjs"
    child.write_text("process.on('SIGTERM',()=>{});setInterval(()=>{},1000)")
    server = tmp_path / "parent.mjs"
    server.write_text("""import {spawn} from 'node:child_process';
const child=spawn(process.execPath,[process.env.GCODE_SYNTHETIC_CHILD],{stdio:'ignore'});
process.on('SIGTERM',()=>{});process.stdin.setEncoding('utf8');let b='';
process.stdin.on('data',x=>{b+=x;let i;while((i=b.indexOf('\\n'))>=0){let r=JSON.parse(b.slice(0,i));b=b.slice(i+1);
console.log(JSON.stringify({v:1,id:r.id,ok:true,child_pid:child.pid}));}});
process.stdin.on('end',()=>{});setInterval(()=>{},1000);""")
    provider = tmp_path / "unused.mjs"
    provider.write_text("// synthetic only")
    monkeypatch.setenv("GCODE_SYNTHETIC_CHILD", str(child))
    t = CUTransport(NODE, server, provider, tmp_path)
    await t.start()
    hello = await t.hello("r", "s")
    pid = hello["child_pid"]
    await asyncio.sleep(0.1)
    await asyncio.wait_for(t.shutdown("r", "s"), 4)
    command = subprocess.run(
        ["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True
    ).stdout
    assert str(child) not in command
    assert t._proc.returncode is not None
