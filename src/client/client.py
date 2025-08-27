from __future__ import annotations as _annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from collections import defaultdict
from uuid import uuid4

import fastapi
import logfire
from fastapi import Depends
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic_ai.messages import ModelMessagesTypeAdapter, ModelRequest, ModelResponse
from fastapi.middleware.cors import CORSMiddleware

from client_lib.cot import ChainOfThought
from client_lib.database import Database, get_db
from client_lib.sandbox import SandboxState, save_sandbox_state, load_sandbox_state
from client_lib.chat import to_chat_message
from client_lib.reasoning import ReasoningGraph, load_reasoning_graph, save_reasoning_graph


# 'if-token-present' means nothing will be sent (and the example will work) if you don't have logfire configured
logfire.configure(send_to_logfire="if-token-present")
THIS_DIR = Path(__file__).parent
REASONING_DIR = THIS_DIR / "reasoning_state"
SANDBOX_DIR = THIS_DIR / "sandbox_state"
# Global state (per-session objects)
sandbox_store: dict[str, SandboxState] = defaultdict(SandboxState)
reasoning_graph_store: dict[str, ReasoningGraph] = {}


@asynccontextmanager
async def lifespan(_app: fastapi.FastAPI):
    async with Database.connect() as db:
        yield {"db": db}


app = fastapi.FastAPI(lifespan=lifespan)
logfire.instrument_fastapi(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8081"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/chat/")
async def get_chat(
    session_id: str = fastapi.Query("default"),
    database: Database = Depends(get_db),
) -> Response:
    # Get messages from the database
    messages: list[ModelRequest | ModelResponse] = await database.get_messages()

    # If the database returns bytes objects, convert them to ModelRequest/ModelResponse
    if messages and isinstance(messages[0], bytes):
        parsed_messages: list[ModelRequest | ModelResponse] = []
        for record in messages:
            # record is JSON-utf8 bytes, e.g. b'[{"kind":"response",…}]'
            try:
                json_str = record.decode("utf-8")
                parsed_messages.extend(ModelMessagesTypeAdapter.validate_json(json_str))
            except UnicodeDecodeError:
                # Log the error and skip this record
                logfire.error("Failed to decode record as UTF-8", record=record.hex())
                continue
        messages = parsed_messages

    # 3) convert each dataclass back into the client‐facing shape
    #    (you already have `to_chat_message` for that)
    # Attempt to load sandbox to recover latest view for this session
    if session_id in sandbox_store:
        sb = sandbox_store[session_id]
    else:
        sb = load_sandbox_state(THIS_DIR / "sandbox_state", session_id) or SandboxState()
        sandbox_store[session_id] = sb

    latest_view = sb.latest_view
    out = b"\n".join(
        json.dumps(to_chat_message(msg, latest_view)).encode("utf-8") for msg in messages
    )
    return Response(out, media_type="text/plain")


@app.post("/chat/")
async def post_chat(
    prompt: Annotated[str, fastapi.Form()],
    session_id: Annotated[str, fastapi.Form(default_factory=lambda: str(uuid4()))],
    database: Database = Depends(get_db),
) -> StreamingResponse:
    async def stream_messages():
        yield (
            json.dumps(
                {
                    "role": "user",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "content": prompt,
                }
            ).encode("utf-8")
            + b"\n"
        )

        # Use per-session sandbox (load from disk if first time in this process)
        if session_id not in sandbox_store:
            loaded_sb = load_sandbox_state(SANDBOX_DIR, session_id)
            sandbox_store[session_id] = loaded_sb if loaded_sb else SandboxState()
        sandbox = sandbox_store[session_id]

        # Load or create reasoning graph for this session
        rg = reasoning_graph_store.get(session_id)
        if rg is None:
            loaded = load_reasoning_graph(REASONING_DIR, session_id)
            if loaded is not None:
                rg = loaded
            else:
                # Create a brand-new graph when none exists
                rg = ReasoningGraph()
            # keep the in-memory store up to date
            reasoning_graph_store[session_id] = rg

        cot = ChainOfThought(query=prompt, sandbox=sandbox, reasoning_graph=rg)
        await cot.run_cot()

        # Persist whatever graph the CoT used/updated
        if cot.reasoning_graph is not None:
            save_reasoning_graph(REASONING_DIR, session_id, cot.reasoning_graph)

        for part in cot.chain:
            if isinstance(part, tuple):  # safety
                part, _ = part
            blob: bytes = ModelMessagesTypeAdapter.dump_json([part])
            await database.add_messages(blob)
            if part == cot.chain[0]:
                continue  # Skip echo (initial user request already streamed)
            yield json.dumps(to_chat_message(part, sandbox.latest_view)).encode("utf-8") + b"\n"
            # Incremental sandbox persistence (resilient to refresh mid-stream)
            save_sandbox_state(SANDBOX_DIR, session_id, sandbox)

        # Persist sandbox state after processing (messages + latest_view)
        save_sandbox_state(SANDBOX_DIR, session_id, sandbox)

    return StreamingResponse(stream_messages(), media_type="text/plain")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("client:app", port=2002, reload=True, reload_dirs=[str(THIS_DIR)])
