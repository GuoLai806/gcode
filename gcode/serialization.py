from __future__ import annotations

import json
from typing import Any

from gcode.conversation import Message


def tool_result_text(result: Any) -> str:
    """Bounded model projection; raw native details remain in the transcript.

    Do not reinsert original text blocks after an output has been externalized
    or snipped. Only explicit delivery/authority metadata is projected.
    """
    text = result.content
    details = result.details or {}
    nested = details.get("details", {})
    if isinstance(nested, dict):
        details = {**nested, **details}
    state = {
        key: details[key]
        for key in (
            "delivery_state",
            "verification_state",
            "error",
            "artifact_reference",
            "artifacts",
            "runtime_identity",
            "scope",
            "nativeWritesStopped",
            "windowKeyboardStopped",
            "nativeObservationRequired",
            "nativeDecisionReadRequired",
            "scopeEpoch",
            "receipt_reused",
            "requires_new_observation",
        )
        if key in details
    }
    observation = details.get("axObservation", {})
    if isinstance(observation, dict):
        native = observation.get("native") or {}
        data = native.get("data", {}) if isinstance(native, dict) else {}
        if isinstance(data, dict) and observation.get("target") == "task":
            state["observation"] = {
                "snapshot_id": data.get("snapshot_id"),
                "complete": data.get("complete"),
                "window_id": data.get("window", {}).get("id"),
            }
    if details.get("axQuery"):
        state["query_is_partial"] = True
    if isinstance(state.get("error"), dict):
        state["error"] = {
            "code": state["error"].get("code", "ERROR"),
            "details": "Full error retained in the raw receipt",
        }
    if state:
        raw = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
        if len(raw) > 4000:
            state.pop("runtime_identity", None)
            raw = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
        text += (
            "\n<tool-state>"
            + (
                raw
                if len(raw) <= 4000
                else json.dumps(
                    {
                        "details": "Stored in the raw session receipt",
                        "delivery_state": details.get("delivery_state", "unknown"),
                    },
                    ensure_ascii=False,
                )
            )
            + "</tool-state>"
        )
    return text


def tool_result_blocks(result: Any, protocol: str) -> list[dict[str, Any]]:
    text = tool_result_text(result)
    blocks: list[dict[str, Any]] = [
        {"type": "text" if protocol == "anthropic" else "input_text", "text": text}
    ]
    for item in result.content_blocks or []:
        if item.get("type") == "image":
            source = item.get("source", {})
            if (
                source.get("type") != "base64"
                or not source.get("media_type", "").startswith("image/")
                or not isinstance(source.get("data"), str)
            ):
                raise ValueError("Unsupported image block; retain it as an artifact")
            if protocol == "anthropic":
                blocks.append({"type": "image", "source": source})
            else:
                blocks.append(
                    {
                        "type": "input_image",
                        "image_url": "data:"
                        + source["media_type"]
                        + ";base64,"
                        + source["data"],
                    }
                )
        elif item.get("type") not in {"text", "artifact"}:
            raise ValueError("Unsupported tool content block")
    return blocks


# 把 provider 无关的内部消息序列化成各家 API 的请求格式。
# 这一层属于「适配器」职责，对话层（ConversationManager）只管消息、不懂线上格式。


def build_anthropic_messages(messages: list[Message]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for m in messages:
        if m.tool_uses or m.thinking_blocks:
            content: list[dict[str, Any]] = []
            for tb in m.thinking_blocks:
                content.append(
                    {
                        "type": "thinking",
                        "thinking": tb.thinking,
                        "signature": tb.signature,
                    }
                )
            if m.content:
                content.append({"type": "text", "text": m.content})
            for tu in m.tool_uses:
                content.append(
                    {
                        "type": "tool_use",
                        "id": tu.tool_use_id,
                        "name": tu.tool_name,
                        "input": tu.arguments,
                    }
                )
            if not content:
                content.append({"type": "text", "text": ""})
            result.append({"role": "assistant", "content": content})
        elif m.tool_results:
            content = []
            for tr in m.tool_results:
                content.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tr.tool_use_id,
                        "content": tool_result_blocks(tr, "anthropic")
                        if any(
                            b.get("type") == "image" for b in tr.content_blocks or []
                        )
                        else tool_result_text(tr),
                        "is_error": tr.is_error,
                    }
                )
            if m.content:
                content.append({"type": "text", "text": m.content})
            result.append({"role": "user", "content": content})
        else:
            # 合并连续的 user 纯文本消息（system-reminder 或普通 user 文本）。
            # 不合并到 tool_result 类型的 user 消息中（content 是 list）。
            if (
                m.role == "user"
                and result
                and result[-1]["role"] == "user"
                and isinstance(result[-1]["content"], str)
            ):
                result[-1]["content"] = result[-1]["content"] + "\n" + m.content
            else:
                result.append({"role": m.role, "content": m.content})
    return result


def build_openai_input(messages: list[Message]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for m in messages:
        if m.tool_uses:
            if m.content:
                result.append({"role": "assistant", "content": m.content})
            for tu in m.tool_uses:
                result.append(
                    {
                        "type": "function_call",
                        "name": tu.tool_name,
                        "call_id": tu.tool_use_id,
                        "arguments": json.dumps(tu.arguments),
                    }
                )
        elif m.tool_results:
            for tr in m.tool_results:
                result.append(
                    {
                        "type": "function_call_output",
                        "call_id": tr.tool_use_id,
                        "output": tool_result_blocks(tr, "openai")
                        if any(
                            b.get("type") == "image" for b in tr.content_blocks or []
                        )
                        else tool_result_text(tr),
                    }
                )
            if m.content:
                result.append({"role": "user", "content": m.content})
        else:
            result.append({"role": m.role, "content": m.content})
    return result


def build_chat_completion_messages(messages: list[Message]) -> list[dict[str, Any]]:
    """OpenAI Chat Completions 格式。

    - 用户消息：{"role": "user", "content": "..."}
    - 助手文本+工具调用：{"role": "assistant", "content": "...", "tool_calls": [...]}
    - 工具结果：{"role": "tool", "tool_call_id": "...", "content": "..."}
    - thinking 块被跳过（Chat Completions 不支持）。
    """
    result: list[dict[str, Any]] = []
    for m in messages:
        if m.tool_uses:
            tool_calls = []
            for tu in m.tool_uses:
                tool_calls.append(
                    {
                        "id": tu.tool_use_id,
                        "type": "function",
                        "function": {
                            "name": tu.tool_name,
                            "arguments": json.dumps(tu.arguments),
                        },
                    }
                )
            result.append(
                {
                    "role": "assistant",
                    "content": m.content or None,
                    "tool_calls": tool_calls,
                }
            )
        elif m.tool_results:
            for tr in m.tool_results:
                result.append(
                    {
                        "role": "tool",
                        "tool_call_id": tr.tool_use_id,
                        "content": tool_result_text(tr),
                    }
                )
                if any(b.get("type") == "image" for b in tr.content_blocks or []):
                    images = tool_result_blocks(tr, "openai")[1:]
                    result.append(
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {"url": b["image_url"]},
                                }
                                for b in images
                            ],
                        }
                    )
            if m.content:
                result.append({"role": "user", "content": m.content})
        else:
            result.append({"role": m.role, "content": m.content})
    return result


def build_messages(
    messages: list[Message], protocol: str = "anthropic"
) -> list[dict[str, Any]]:
    if protocol == "openai":
        return build_openai_input(messages)
    if protocol == "openai-compat":
        return build_chat_completion_messages(messages)
    return build_anthropic_messages(messages)
