from typing import Any, Dict, Literal
from pydantic import BaseModel


class ToolWithView(BaseModel):
    view: Literal["table", "text", "list", "graph", "none"]
    response: Dict[Any, Any] | str 