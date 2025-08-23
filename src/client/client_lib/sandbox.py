from dataclasses import dataclass, field
from typing import List, Optional
from pydantic_ai.messages import ModelMessage
import logfire
import difflib

@dataclass
class SandboxState:
    """Holds persistent execution state for CoT refinement."""
    topic_anchor: Optional[str] = None
    messages: List[ModelMessage] = field(default_factory=list)
    latest_view: Optional[str] = None

    def is_same_topic(self, new_query: str, threshold: float = 0.65) -> bool:
        if not self.topic_anchor:
            return False
        similarity = difflib.SequenceMatcher(None, self.topic_anchor, new_query).ratio()
        logfire.info(f"Query similarity: {similarity}")
        return similarity >= threshold

    def reset(self, query: str):
        logfire.info(f"Resetting sandbox for new query: {query}")
        self.topic_anchor = query
        self.messages.clear()
        self.latest_view = None

    def extend(self, message: ModelMessage, view: Optional[str] = None):
        self.messages.append(message)
        if view:
            self.latest_view = view
