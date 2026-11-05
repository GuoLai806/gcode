"""Meter auxiliary recall/extraction calls under the same root run budget."""

from __future__ import annotations

from typing import Any

from gcode.client import LLMClient
from gcode.tools.base import StreamEnd


class BudgetedSideClient(LLMClient):
    def __init__(self, client: LLMClient, owner: Any):
        self.client, self.owner = client, owner

    def set_max_output_tokens(self, tokens: int) -> None:
        self.client.set_max_output_tokens(tokens)

    async def stream(self, conversation, system="", tools=None):
        if not self.owner.token_budget.before_request():
            raise RuntimeError(
                "Shared token budget exhausted; auxiliary request not sent"
            )
        observed = False
        stream = self.client.stream(conversation, system=system, tools=tools)
        try:
            async for event in stream:
                if isinstance(event, StreamEnd):
                    observed = True
                    if event.usage_valid:
                        self.owner._record_usage(
                            event.input_tokens,
                            event.output_tokens,
                            event.cache_read,
                            event.cache_creation,
                        )
                    else:
                        self.owner.token_budget.mark_usage_unknown()
                yield event
        finally:
            await stream.aclose()
            if not observed:
                self.owner.token_budget.mark_usage_unknown()
