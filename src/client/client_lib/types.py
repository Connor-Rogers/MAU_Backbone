from typing import Literal
from typing_extensions import TypedDict

class ChatMessage(TypedDict):
    """Format of messages sent to the browser."""

    role: Literal['user', 'model']
    timestamp: str
    content: str

class ModelMessage(TypedDict):
    """Format of messages sent to the model."""

    role: Literal['user', 'model']
    timestamp: str
    content: str
    parts: list[dict]
    tools_used: list[str]