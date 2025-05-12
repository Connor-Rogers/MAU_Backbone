from client_lib.types import ChatMessage
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from typing import List

def to_chat_message(resoponse_chain: List[(ModelMessage, str)]) -> ChatMessage:
    """
    Convert a response chain to a chat message format.
    """
    output_chain = []
    for response in resoponse_chain:
        message, tool = response
        if isinstance(message, ModelRequest):
            if isinstance(message, UserPromptPart):
                assert isinstance(message.content, str)
                output_chain.append(
                    {
                        "role": "user",
                        "timestamp": message.timestamp.isoformat(),
                        "content": message.content,
                    }
                )
        elif isinstance(message, ModelResponse):
            if isinstance(message, TextPart):
                assert isinstance(message.content, str)
                output_chain.append(
                    {
                        "type": "model",
                        "tool": tool,
                        "role": "model",
                        "timestamp": message.timestamp.isoformat(),
                        "content": message.content,
                    }
                )
        else:
            raise UnexpectedModelBehavior(f"Unexpected message type: {type(message)}")
