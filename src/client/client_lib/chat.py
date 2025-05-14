from typing import List
from client_lib.types import ChatMessage
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
    ToolReturnPart,
)

def to_chat_message(response_chain: List[ModelMessage]) -> ChatMessage:
    """
    Convert a chain of ModelMessage into your ChatMessage format.
    """
    chat: ChatMessage = []
    for msg in response_chain:
        # requests contain user (and system) prompts
        print(type(msg))
        
        
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, UserPromptPart):
                    # we know content is str here
                    chat.append({
                        "role": "user",
                        "timestamp": part.timestamp.isoformat(),
                        "content": part.content,
                    })

        # responses contain text and tool-return parts
        elif isinstance(msg, ModelResponse):
            for part in msg.parts:
                if isinstance(part, TextPart):
                    chat.append({
                        "role": "model",
                        "timestamp": msg.timestamp.isoformat(),
                        "content": part.content,
                    })
                elif isinstance(part, ToolReturnPart):
                    chat.append({
                        "role":      "tool",
                        "tool":      part.tool_name,
                        "timestamp": part.timestamp.isoformat(),
                        "content":   part.content,
                    })
        else:
            raise UnexpectedModelBehavior(f"Unexpected message type: {type(msg)}")
    return chat