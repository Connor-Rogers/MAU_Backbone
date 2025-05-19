from __future__ import annotations as _annotations

import json
from contextlib import asynccontextmanager

from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import fastapi
import logfire
from fastapi import Depends
from fastapi.responses import FileResponse, Response, StreamingResponse

from client_lib.cot import ChainOfThought
from client_lib.database import Database, get_db
from client_lib.chat import to_chat_message
from pydantic_ai.messages import ModelMessagesTypeAdapter, ModelRequest, ModelResponse

from fastapi.middleware.cors import CORSMiddleware

# 'if-token-present' means nothing will be sent (and the example will work) if you don't have logfire configured
logfire.configure(send_to_logfire="if-token-present")

THIS_DIR = Path(__file__).parent


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


@app.get("/")
async def index() -> FileResponse:
    return FileResponse((THIS_DIR / "chat_app.html"), media_type="text/html")


@app.get("/chat_app.ts")
async def main_ts() -> FileResponse:
    """Get the raw typescript code, it's compiled in the browser, forgive me."""
    return FileResponse((THIS_DIR / "chat_app.ts"), media_type="text/plain")


@app.get("/chat/")
async def get_chat(database: Database = Depends(get_db)) -> Response:
    # Get messages from the database
    messages: list[ModelRequest | ModelResponse] = await database.get_messages()

    # If the database returns bytes objects, convert them to ModelRequest/ModelResponse
    if messages and isinstance(messages[0], bytes):
        parsed_messages: list[ModelRequest | ModelResponse] = []
        for record in messages:
            # record is JSON-utf8 bytes, e.g. b'[{"kind":"response",…}]'
            try:
                json_str = record.decode("utf-8")
                parsed_messages.extend(
                    ModelMessagesTypeAdapter.validate_json(json_str)
                )
            except UnicodeDecodeError:
                # Log the error and skip this record
                logfire.error("Failed to decode record as UTF-8", record=record.hex())
                continue
        messages = parsed_messages

    # 3) convert each dataclass back into the client‐facing shape
    #    (you already have `to_chat_message` for that)
    out = b"\n".join(
        json.dumps(to_chat_message(msg)).encode("utf-8")
        for msg in messages
    )
    return Response(out, media_type="text/plain")


@app.post("/chat/")
async def post_chat(
    prompt: Annotated[str, fastapi.Form()], database: Database = Depends(get_db)
) -> StreamingResponse:
    async def stream_messages():
        # echo the user prompt immediately
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
        # COT
        cot = ChainOfThought(
            query=prompt,
            previous_messages=await database.get_messages(),
            database=database,
        )
        await cot.run_cot(max_iters=5)

        # 1) serialize & persist each ModelMessage
        # 2) yield its client‐facing representation
        for part in cot.chain:
            # part is either a ModelRequest or ModelResponse
            blob: bytes = ModelMessagesTypeAdapter.dump_json([part])

            await database.add_messages(blob)

            client_json = json.dumps(to_chat_message(part)).encode("utf-8") + b"\n"
            logfire.debug(
                f"Yielding message: {client_json}",
            )
            yield client_json

    return StreamingResponse(stream_messages(), media_type="text/plain")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("client:app", port=2002, reload=True, reload_dirs=[str(THIS_DIR)])
