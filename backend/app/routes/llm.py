"""LLM chat: SSE stream that drives a provider-agnostic tool-use loop."""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..auth import require_admin
from ..db import conn, dumps, loads, now_iso, tx
from ..gates import get_gate
from ..llm.executor import execute_tool
from ..llm.messages import (
    LLMResponse,
    Message,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)
from ..llm.providers import get_provider

router = APIRouter(prefix="/api/llm", tags=["llm"], dependencies=[Depends(require_admin)])


class ChatBody(BaseModel):
    session_id: str | None = None
    message: str


def _load_session(session_id: str) -> list[Message]:
    row = conn().execute(
        "SELECT messages_json FROM chat_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    raw = loads(row["messages_json"]) if row else []
    return [Message.model_validate(m) for m in (raw or [])]


def _save_session(session_id: str, messages: list[Message]) -> None:
    payload = dumps([m.model_dump() for m in messages])
    with tx() as c:
        c.execute(
            """INSERT INTO chat_sessions (id, created_at, updated_at, messages_json)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at,
                                              messages_json=excluded.messages_json""",
            (session_id, now_iso(), now_iso(), payload),
        )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _run_loop(
    messages: list[Message],
    session_id: str,
    *,
    max_iterations: int = 8,
) -> AsyncIterator[str]:
    """Shared provider-agnostic tool-use loop. Yields SSE frames."""
    try:
        provider = get_provider()
    except Exception as e:
        yield _sse("error", {"message": f"LLM provider unavailable: {e}"})
        return

    for _ in range(max_iterations):
        try:
            resp: LLMResponse = await asyncio.to_thread(provider.chat, messages)
        except Exception as e:
            yield _sse("error", {"message": str(e)})
            return

        assistant_blocks: list = []
        for text in resp.text_blocks:
            assistant_blocks.append(TextBlock(text=text))
            yield _sse("text", {"text": text})
        for tu in resp.tool_calls:
            assistant_blocks.append(tu)
            yield _sse("tool_use", {"id": tu.id, "name": tu.name, "input": tu.input})

        messages.append(Message(role="assistant", content=assistant_blocks))

        if resp.stop_reason != "tool_use":
            _save_session(session_id, messages)
            yield _sse("end", {"stop_reason": resp.stop_reason})
            return

        # Execute every tool call requested in this turn, append results, loop again.
        tool_results: list = []
        for tu in resp.tool_calls:
            try:
                result = await asyncio.to_thread(
                    execute_tool, tu.name, tu.input,
                    chat_session_id=session_id, tool_use_id=tu.id,
                )
            except Exception as e:
                result = {"error": str(e)}
            tool_results.append(ToolResultBlock(
                tool_use_id=tu.id,
                content=json.dumps(result),
            ))
            yield _sse("tool_result", {"tool_use_id": tu.id, "result": result})

        messages.append(Message(role="user", content=tool_results))
        _save_session(session_id, messages)

    yield _sse("error", {"message": "tool-use loop exceeded max iterations"})


async def _chat_stream(body: ChatBody) -> AsyncIterator[str]:
    session_id = body.session_id or str(uuid.uuid4())
    messages = _load_session(session_id)
    messages.append(Message(role="user", content=[TextBlock(text=body.message)]))
    yield _sse("session", {"session_id": session_id})
    async for frame in _run_loop(messages, session_id):
        yield frame


@router.post("/chat")
async def chat(body: ChatBody) -> StreamingResponse:
    return StreamingResponse(_chat_stream(body), media_type="text/event-stream")


@router.post("/resume")
async def resume(session_id: str, gate_id: int) -> StreamingResponse:
    """Resume a paused conversation after a gate has been approved/rejected."""
    try:
        gate = get_gate(gate_id)
    except KeyError:
        raise HTTPException(404, "gate not found")

    messages = _load_session(session_id)
    if not messages:
        raise HTTPException(404, "session not found")
    if gate["status"] not in {"executed", "failed", "rejected"}:
        raise HTTPException(400, "gate not yet decided")

    synth = ToolResultBlock(
        tool_use_id=gate["tool_use_id"] or "unknown",
        content=json.dumps({
            "gate_id": gate["id"],
            "status": gate["status"],
            "executed": gate["status"] == "executed",
            "result": gate["result"],
        }),
    )
    messages.append(Message(role="user", content=[synth]))
    _save_session(session_id, messages)

    async def _resume_stream() -> AsyncIterator[str]:
        yield _sse("session", {"session_id": session_id})
        async for frame in _run_loop(messages, session_id, max_iterations=4):
            yield frame

    return StreamingResponse(_resume_stream(), media_type="text/event-stream")
