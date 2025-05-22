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
def determine_agent_role(msg: ModelResponse) -> str:
    """
    Determine the role of the message based on its type.
    """
    if isinstance(msg, ModelResponse):
        if msg.model_name.startswith("ChainOfThought:Model:"):
            return "model"
        elif msg.model_name.startswith("ChainOfThought:Tool:"):
            return "tool"
        return f"ChainOfThought:Model:{msg.model_name}"

def to_chat_message(msg: ModelMessage, view=None) -> ChatMessage:
    """
    Convert a chain of ModelMessage into your ChatMessage format.
    """
    if isinstance(msg, ModelRequest):
        for part in msg.parts:
            if isinstance(part, UserPromptPart):
                # we know content is str here
                return {
                    "role": "user",
                    "timestamp": part.timestamp.isoformat(),
                    "content": part.content,
                }

        # responses contain text and tool-return parts
    elif isinstance(msg, ModelResponse):
        for part in msg.parts:
            if isinstance(part, TextPart):
                return{
                    "role": determine_agent_role(msg),
                    "view": view,
                    "timestamp": msg.timestamp.isoformat(),
                    "content": part.content,
                }
    else:
        raise UnexpectedModelBehavior(f"Unexpected message type: {type(msg)}")