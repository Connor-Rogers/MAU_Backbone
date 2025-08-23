from typing import Literal, NamedTuple
from typing_extensions import TypedDict

class ChatMessage(TypedDict):
    """Format of messages sent to the browser."""

    role: Literal['user', 'model']
    timestamp: str
    content: str
    parts: list[dict]


class ToolResult(NamedTuple):
    view: str
    result: str
    tool: str