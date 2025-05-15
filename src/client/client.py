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
    msgs = await database.get_messages()
    return Response(
        b"\n".join(json.dumps(to_chat_message(m)).encode("utf-8") for m in msgs),
        media_type="text/plain",
    )


@app.post("/chat/")
async def post_chat(
    prompt: Annotated[str, fastapi.Form()], database: Database = Depends(get_db)
) -> StreamingResponse:
    async def stream_messages():
        """Streams new line delimited JSON `Message`s to the client."""
        # store original prompt to use in the user message
        original_prompt = prompt

        # stream the user prompt so that can be displayed straight away
        yield (
            json.dumps(
                {
                    "role": "user",
                    "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                    "content": original_prompt,
                }
            ).encode("utf-8")
            + b"\n"
        )

        # run the chain of thought
        cot = ChainOfThought(
            query=original_prompt,
            previous_messages=await database.get_messages(),
            database=database,
        )
        await cot.run_cot(max_iters=5)
        chat_thread = to_chat_message(cot.chain)
        if len(chat_thread) == 0:
            raise fastapi.HTTPException(
                status_code=500, detail="No messages in chat thread"
            )

        # Skip first message (user message) since we already yielded it earlier
        for i, message in enumerate(chat_thread):
            m = json.dumps(message).encode("utf-8") + b"\n"
            await database.add_messages(m)
            if i > 0:  # Skip the first message
                yield m

    return StreamingResponse(stream_messages(), media_type="text/plain")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("client:app", port=2002, reload=True, reload_dirs=[str(THIS_DIR)])
