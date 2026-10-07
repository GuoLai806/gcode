"""Opt-in real DeepSeek + actual Textual input + real Bash acceptance.

Run from the checkout with .venv/bin/python scripts/test_live_interruption.py.
Uses the existing private provider config without printing/storing credentials.
Only temporary fixtures are operated on; no tools run against the user's project.
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path

from gcode.app import ChatInput, GCodeApp
from gcode.config import load_config
from gcode.conversation import ConversationManager
from gcode.memory.session import SessionManager
from gcode.permissions import PermissionMode
from gcode.tools.bash import Bash


def assert_closed(history):
    for index, message in enumerate(history):
        if message.tool_uses:
            assert index + 1 < len(history), "missing result message"
            expected = {tu.tool_use_id for tu in message.tool_uses}
            actual = [tr.tool_use_id for tr in history[index + 1].tool_results]
            assert expected == set(actual) and len(actual) == len(expected), "broken tool chain"
        if message.tool_results:
            assert index > 0 and history[index - 1].tool_uses, "orphan result"


async def wait_until(predicate, timeout=90):
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(.025)


async def main():
    provider = load_config(Path.home() / ".gcode" / "config.yaml").providers[0]
    assert provider.model == "deepseek-flash"
    assert provider.base_url == "https://api.deepseek.com/anthropic"
    original_cwd = Path.cwd()
    fixture = Path(tempfile.mkdtemp(prefix="gcode-live-interruption-"))
    report = {"provider": provider.name, "model": provider.model,
              "endpoint": provider.base_url, "fixture_dir": str(fixture),
              "rounds": [], "requests": []}
    os.chdir(fixture)
    app = GCodeApp([provider], permission_mode=PermissionMode.BYPASS)
    errors = []
    original_show_error = app._show_error
    def record_error(message):
        errors.append(str(message))
        original_show_error(message)
    app._show_error = record_error
    running_sleep = asyncio.Event()
    executed = []
    real_execute = Bash.execute
    async def observed_execute(tool, params):
        executed.append(params.command)
        if "sleep 8" in params.command:
            running_sleep.set()
        return await real_execute(tool, params)
    Bash.execute = observed_execute
    try:
        async with app.run_test(size=(120, 40)) as pilot:
            assert app.agent and app.client
            # Restrict the real model's actions to Bash; no agent delegation.
            for tool in app.registry.list_tools():
                if tool.name != "Bash":
                    app.registry.disable(tool.name)
            sdk = app.client._client
            async def request_hook(request):
                if request.method != "POST":
                    return
                body = json.loads(request.content)
                uses = results = 0
                for message in body.get("messages", []):
                    content = message.get("content", [])
                    if isinstance(content, list):
                        uses += sum(block.get("type") == "tool_use" for block in content)
                        results += sum(block.get("type") == "tool_result" for block in content)
                entry = {"model": body.get("model"), "uses": uses, "results": results}
                request.extensions["gcode_acceptance_entry"] = entry
                report["requests"].append(entry)
                assert uses == results, "outgoing HTTP request has dangling tools"
            async def response_hook(response):
                if response.request.method == "POST":
                    response.request.extensions["gcode_acceptance_entry"]["http_status"] = response.status_code
            sdk._client.event_hooks["request"].append(request_hook)
            sdk._client.event_hooks["response"].append(response_hook)
            # No session synopsis exists. Isolate unrelated long-term memory calls.
            app.agent.memory_manager = None
            widget = app.query_one("#chat-input", ChatInput)
            for round_number, interruption in enumerate(["enter", "escape", "enter"], 1):
                start = time.monotonic()
                running_sleep.clear()
                before_requests = len(report["requests"])
                before_history = len(app.conversation.history)
                first = f"REAL_FIRST_{round_number}"
                queued = f"REAL_QUEUED_{round_number}"
                prompt = (
                    "This is a bounded interruption test. Use ONLY Bash. No Agent, no other tools, no explanation. "
                    "Bash calls execute SEQUENTIALLY in this harness even when emitted together. "
                    "In ONE assistant response issue EXACTLY THREE SEPARATE Bash calls in this order: "
                    f"1) printf '{first}\\n' 2) sleep 8 3) printf '{queued}\\n'. "
                    "Do not combine commands. Do not repeat or retry these calls after interruption."
                )
                widget.insert(prompt)
                await pilot.press("enter")
                await asyncio.wait_for(running_sleep.wait(), 90)
                await pilot.pause(.25)  # let the actual subprocess start before interruption
                during = app.conversation.history[before_history:]
                assert any(first in tr.content for m in during for tr in m.tool_results), "first result not committed"
                tool_message = next(m for m in reversed(during) if m.tool_uses)
                assert len(tool_message.tool_uses) in (2, 3), "missing queued call in the active batch"
                followup = (
                    f"Stop the previous task. Do NOT retry sleep or earlier printf calls. "
                    f"Use ONLY Bash to run exactly: printf 'REAL_CONTINUE_{round_number}\\n'; uname -s . "
                    "Then briefly report the marker and OS. This is the entire new task."
                ).replace("uname -s .", "uname -s")
                if interruption == "escape":
                    await pilot.press("escape")
                    await wait_until(lambda: not app._streaming, 10)
                    assert_closed(app.conversation.history)
                widget.insert(followup)
                await pilot.press("enter")
                marker = f"REAL_CONTINUE_{round_number}"
                await wait_until(lambda: not app._streaming and any(
                    marker in tr.content and "Darwin" in tr.content
                    for m in app.conversation.history for tr in m.tool_results))
                assert not errors, errors
                assert_closed(app.conversation.history)
                interrupted_results = app.conversation.history[
                    app.conversation.history.index(tool_message) + 1].tool_results
                assert len(interrupted_results) == len(tool_message.tool_uses)
                assert sum(tr.is_error for tr in interrupted_results) == 2
                assert any(first in tr.content and not tr.is_error for m in app.conversation.history
                           for tr in m.tool_results)
                assert all(queued not in command for command in executed), "queued side effect executed"
                result = {"round": round_number, "interruption": interruption,
                          "batch_tool_calls": len(tool_message.tool_uses),
                          "preserved_success": 1, "interrupted_errors": 2,
                          "continued_with_real_tool": True, "os": "Darwin", "errors": list(errors),
                          "seconds": round(time.monotonic() - start, 3),
                          "post_requests": len(report["requests"]) - before_requests}
                # Every task API response appears in main history. A stray
                # background synopsis request would not, even if the model split
                # the planned tool batch across two responses.
                task_responses = sum(m.role == "assistant" for m in app.conversation.history[before_history:])
                assert result["post_requests"] == task_responses, "unexpected background API call"
                report["rounds"].append(result)
                print(json.dumps(result, ensure_ascii=False), flush=True)
            session_id = app.session.session_id
            app.session.close()
            restored = SessionManager(str(fixture)).resume(session_id)
            assert restored is not None
            restored_conv = ConversationManager(history=restored.messages)
            assert_closed(restored_conv.history)
            for number in range(1, 4):
                marker = f"REAL_CONTINUE_{number}"
                assert sum(marker in m.content for m in restored_conv.history
                           if m.role == "user" and not m.tool_results) == 1, "duplicate persisted user message"
            assert any(tb.signature for m in restored_conv.history for tb in m.thinking_blocks), "thinking signature lost"
            app.agent.file_history = None
            answer = await app.agent.run_to_completion(
                "Do not repeat previous commands. Use only Bash: printf 'REAL_RESUMED_OK\\n'; uname -s. "
                "Report the marker and OS, then stop.", restored_conv)
            assert "REAL_RESUMED_OK" in answer and "Darwin" in answer
            assert_closed(restored_conv.history)
            restored.session.close()
            report["resume"] = {"real_api_and_tool": True, "thinking_preserved": True,
                                "answer": answer, "closed_chain": True}
            assert len(report["requests"]) == sum(row["post_requests"] for row in report["rounds"]) + 2
            report["session_synopsis_removed"] = True
            await wait_until(lambda: all("http_status" in req for req in report["requests"]), 15)
            await pilot.pause(.5)
            assert_closed(app.conversation.history)
            await sdk.close()
        report["passed"] = True
    except BaseException as error:
        report["passed"] = False
        report["failure"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        Bash.execute = real_execute
        os.chdir(original_cwd)
        report["executed_commands"] = executed
        # This generated evidence contains test prompts/outputs, never the provider key.
        path = fixture / "acceptance.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Evidence: " + str(path), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
