from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import AsyncGenerator

import src.agent as agent

# Manages application startup and shutdown work, including memory persistence.
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage the FastAPI application lifecycle.
    """
    # Code before yield runs on server STARTUP
    print("Server starting up...")
    yield
    # Code after yield runs on server SHUTDOWN
    print("Server shutting down. Saving long-term memory...")
    if agent.chat_instance is not None:
        agent.close_chat()

# FastAPI application instance used to serve the API and static frontend.
app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatPayload(BaseModel):
    """Request body containing a chat session identifier and user message."""

    session_id: str
    message: str

async def sse_event_formatter(token_generator: AsyncGenerator[str, None]) -> AsyncGenerator[str, None]:
    """Format generated text chunks as Server-Sent Events.

    Parameters:
        token_generator: Asynchronous stream of response text chunks.

    Yields:
        SSE-formatted chunks followed by a completion marker.
    """
    async for token in token_generator:
        yield f"data: {token}\n\n"
    
    yield "data: [DONE]\n\n"

@app.get("/api/history")
def get_chat_history():
    """Return the complete persisted chat history.

    Returns:
        A list of saved user and agent messages.
    """
    return agent.get_full_history()

@app.post("/api/chat")
async def chat_endpoint(payload: ChatPayload):
    """Stream the agent's response to a submitted chat message.

    Parameters:
        payload: Session identifier and message supplied by the frontend.

    Returns:
        A streaming HTTP response containing SSE-formatted agent tokens.
    """
    agent_stream = agent.run_agent_stream(
        session_id=payload.session_id, 
        message=payload.message
    )

    return StreamingResponse(
        sse_event_formatter(agent_stream),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.delete("/api/reset")
def reset_memory():
    """Clear persisted chat history, long-term memory, and active session.

    Returns:
        A success status object for the frontend.
    """
    agent.reset_all_memory()
    return {"status": "success"}

app.mount("/", StaticFiles(directory="static", html=True), name="static")