from __future__ import annotations

from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from gcode.agent import Agent
from gcode.client import OpenAICompatClient
from gcode.config import ProviderConfig
from gcode.conversation import ConversationManager
from gcode.tools import create_default_registry
from gcode.tools.base import StreamEnd


def client_with_chunks(chunks):
    client = OpenAICompatClient(
        ProviderConfig(
            name="fixture",
            protocol="openai-compat",
            base_url="http://127.0.0.1:1/v1",
            model="fixture",
            api_key="fixture-not-a-credential",
        )
    )

    async def output():
        for chunk in chunks:
            yield chunk

    client._client.chat.completions.create = AsyncMock(return_value=output())
    return client


def chunk(reason=None, text=None):
    return NS(
        choices=[NS(finish_reason=reason, delta=NS(content=text, tool_calls=None))],
        usage=None,
    )


@pytest.mark.asyncio
async def test_compatible_length_stop_survives_usage_trailer():
    client = client_with_chunks(
        [
            chunk(text="partial"),
            chunk(reason="length"),
            NS(
                choices=[],
                usage=NS(
                    prompt_tokens=20,
                    completion_tokens=3,
                    prompt_tokens_details=NS(cached_tokens=5),
                ),
            ),
        ]
    )
    try:
        events = [event async for event in client.stream(ConversationManager())]
    finally:
        await client._client.close()
    ends = [event for event in events if isinstance(event, StreamEnd)]
    assert len(ends) == 1
    assert ends[0].stop_reason == "max_tokens"
    assert ends[0].input_tokens == 15 and ends[0].cache_read == 5
    assert ends[0].usage_valid


@pytest.mark.asyncio
async def test_missing_usage_is_explicit_and_blocks_next_request(tmp_path):
    client = client_with_chunks([chunk(text="answer"), chunk(reason="stop")])
    agent = Agent(client, create_default_registry(), "openai-compat", str(tmp_path))
    try:
        answer = await agent.run_to_completion("question")
        assert answer == "answer"
        assert not agent.token_budget.snapshot()["usage_complete"]
        await agent.run_to_completion("next question")
        assert client._client.chat.completions.create.await_count == 1
        assert agent.last_stop_reason == "budget_exhausted"
    finally:
        await client._client.close()


@pytest.mark.asyncio
async def test_usage_on_finishing_choice_is_counted_without_trailer():
    final = chunk(reason="stop", text="answer")
    final.usage = NS(
        prompt_tokens=30,
        completion_tokens=4,
        prompt_tokens_details=None,
        prompt_cache_hit_tokens=20,
    )
    client = client_with_chunks([final])
    try:
        events = [event async for event in client.stream(ConversationManager())]
    finally:
        await client._client.close()
    end = next(event for event in events if isinstance(event, StreamEnd))
    assert end.usage_valid and end.stop_reason == "end_turn"
    assert (end.input_tokens, end.cache_read, end.output_tokens) == (10, 20, 4)
