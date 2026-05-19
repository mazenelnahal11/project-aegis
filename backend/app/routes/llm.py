"""LLM chat: SSE stream that drives a tool-use loop."""
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
from ..llm.client import call_model
from ..llm.executor import execute_tool

router = APIRouter(prefix="/api/llm", tags=["llm"], dependencies=[Depends(require_admin)])


class ChatBody(BaseModel):
    session_id: str | None = None
    message: str


def _load_session(session_id: str) -> list[dict]:
    row = conn().execute(
        "SELECT messages_json FROM chat_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    return loads(row["messages_json"]) if row else []


def _save_session(session_id: str, messages: list[dict]) -> None:
    with tx() as c:
        c.execute(
            """INSERT INTO chat_sessions (id, created_at, updated_at, messages_json)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at,
                                              messages_json=excluded.messages_json""",
            (session_id, now_iso(), now_iso(), dumps(messages)),
        )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _chat_stream(body: ChatBody) -> AsyncIterator[str]:
    session_id = body.session_id or str(uuid.uuid4())
    messages = _load_session(session_id)
    messages.append({"role": "user", "content": body.message})

    yield _sse("session", {"session_id": session_id})

    for _ in range(8):  # bound the tool-use loop
        try:
            resp = await asyncio.to_thread(call_model, messages)
        except Exception as e:
            yield _sse("error", {"message": str(e)})
            return

        assistant_blocks: list[dict] = []
        tool_uses: list[tuple[str, str, dict]] = []
        for block in resp.content:
            block_dict = block.model_dump() if hasattr(block, "model_dump") else dict(block)
            assistant_blocks.append(block_dict)
            if block.type == "text":
                yield _sse("text", {"text": block.text})
            elif block.type == "tool_use":
                tool_uses.append((block.id, block.name, dict(block.input)))
                yield _sse("tool_use", {
                    "id": block.id, "name": block.name, "input": dict(block.input)
                })
        messages.append({"role": "assistant", "content": assistant_blocks})

        if resp.stop_reason != "tool_use":
            _save_session(session_id, messages)
            yield _sse("end", {"stop_reason": resp.stop_reason})
            return

        tool_results: list[dict] = []
        for tool_use_id, name, args in tool_uses:
            try:
                result = await asyncio.to_thread(
                    execute_tool, name, args,
                    chat_session_id=session_id, tool_use_id=tool_use_id,
                )
            except Exception as e:
                result = {"error": str(e)}
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": json.dumps(result),
            })
            yield _sse("tool_result", {"tool_use_id": tool_use_id, "result": result})

        messages.append({"role": "user", "content": tool_results})
        _save_session(session_id, messages)

    yield _sse("error", {"message": "tool-use loop exceeded max iterations"})


@router.post("/chat")
async def chat(body: ChatBody) -> StreamingResponse:
    return StreamingResponse(_chat_stream(body), media_type="text/event-stream")


@router.post("/resume")
async def resume(session_id: str, gate_id: int) -> StreamingResponse:
    """Resume a paused conversation after a gate has been approved or rejected.
    Synthesizes a tool_result for the prior `propose_*` call and continues the loop.
    """
    try:
        gate = get_gate(gate_id)
    except KeyError:
        raise HTTPException(404, "gate not found")

    messages = _load_session(session_id)
    if not messages:
        raise HTTPException(404, "session not found")

    if gate["status"] not in {"executed", "failed", "rejected"}:
        raise HTTPException(400, "gate not yet decided")

    synth = {
        "type": "tool_result",
        "tool_use_id": gate["tool_use_id"] or "unknown",
        "content": json.dumps({
            "gate_id": gate["id"],
            "status": gate["status"],
            "executed": gate["status"] == "executed",
            "result": gate["result"],
        }),
    }
    messages.append({"role": "user", "content": [synth]})

    async def _resume_stream() -> AsyncIterator[str]:
        yield _sse("session", {"session_id": session_id})
        body = ChatBody(session_id=session_id, message="")
        body_messages = messages  # already includes synthetic tool_result
        _save_session(session_id, body_messages)
        for _ in range(4):
            try:
                resp = await asyncio.to_thread(call_model, body_messages)
            except Exception as e:
                yield _sse("error", {"message": str(e)})
                return
            assistant_blocks = []
            tool_uses = []
            for block in resp.content:
                block_dict = block.model_dump() if hasattr(block, "model_dump") else dict(block)
                assistant_blocks.append(block_dict)
                if block.type == "text":
                    yield _sse("text", {"text": block.text})
                elif block.type == "tool_use":
                    tool_uses.append((block.id, block.name, dict(block.input)))
                    yield _sse("tool_use", {
                        "id": block.id, "name": block.name, "input": dict(block.input)
                    })
            body_messages.append({"role": "assistant", "content": assistant_blocks})
            if resp.stop_reason != "tool_use":
                _save_session(session_id, body_messages)
                yield _sse("end", {"stop_reason": resp.stop_reason})
                return
            results = []
            for tool_use_id, name, args in tool_uses:
                try:
                    result = await asyncio.to_thread(
                        execute_tool, name, args,
                        chat_session_id=session_id, tool_use_id=tool_use_id,
                    )
                except Exception as e:
                    result = {"error": str(e)}
                results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": json.dumps(result),
                })
                yield _sse("tool_result", {"tool_use_id": tool_use_id, "result": result})
            body_messages.append({"role": "user", "content": results})
            _save_session(session_id, body_messages)

    return StreamingResponse(_resume_stream(), media_type="text/event-stream")
