"""
Sandbox State Management Module
"""

from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path
import json
import difflib

from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter
import logfire

@dataclass
class SandboxState:
    """
    A class representing the state of a sandbox, which includes a topic anchor,
    a list of messages, and the latest view. It provides methods for managing
    the state, checking topic similarity, and serializing/deserializing the state.
    """

    # Attributes
    topic_anchor: Optional[str] = None
    messages: List[ModelMessage] = field(default_factory=list)
    latest_view: Optional[str] = None

    def is_same_topic(self, new_query: str, threshold: float = 0.65) -> bool:
        """
        Determines if the given query is similar to the stored topic anchor 
        based on a similarity threshold.
        Args:
            new_query (str): The new query string to compare against the topic anchor.
            threshold (float, optional): The similarity threshold for determining if 
                the topics are the same. Defaults to 0.65.
        Returns:
            bool: True if the similarity ratio between the topic anchor and the 
            new query is greater than or equal to the threshold, False otherwise.
        """
        if not self.topic_anchor:
            return False
        similarity = difflib.SequenceMatcher(None, self.topic_anchor, new_query).ratio()
        logfire.info(f"Query similarity: {similarity}")
        return similarity >= threshold

    def reset(self, query: str):
        """
        Resets the sandbox state for a new query.
        This method clears the current messages, sets the latest view to None, 
        and updates the topic anchor with the provided query. It also logs the 
        reset action for debugging purposes.
        Args:
            query (str): The new query string to reset the sandbox with.
        """
        logfire.info(f"Resetting sandbox for new query: {query}")
        self.topic_anchor = query
        self.messages.clear()
        self.latest_view = None

    def extend(self, message: ModelMessage, view: Optional[str] = None):
        """
        Adds a message to the list of messages and optionally updates the latest view.

        Args:
            message (ModelMessage): The message object to be added to the messages list.
            view (Optional[str]): An optional string representing the view to be updated. 
                                  If provided, it updates the `latest_view` attribute.
        """
        self.messages.append(message)
        if view:
            self.latest_view = view

    def to_dict(self) -> dict:
        """
        Converts the sandbox object into a dictionary representation.

        Returns:
            dict: A dictionary containing the following keys:
                - "topic_anchor" (str): The anchor topic associated with the sandbox.
                - "latest_view" (Any): The latest view information of the sandbox.
                - "messages" (list): A list of messages in the sandbox. If serialization
                  of messages fails, this will be an empty list.

        Notes:
            - The `messages` attribute is serialized to JSON and then deserialized back
              into a Python object. If an error occurs during this process, it is logged
              and an empty list is returned for the "messages" key.
        """
        try:
            raw_bytes = ModelMessagesTypeAdapter.dump_json(self.messages)
            msgs = json.loads(raw_bytes)
        except Exception as e:
            logfire.error("Failed serializing sandbox messages", error=str(e))
            msgs = []
        return {
            "topic_anchor": self.topic_anchor,
            "latest_view": self.latest_view,
            "messages": msgs,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SandboxState":
        """
        Create an instance of SandboxState from a dictionary.
        Args:
            data (dict): A dictionary containing the data to initialize the SandboxState instance.
                Expected keys:
                    - "topic_anchor" (optional): The topic anchor value.
                    - "latest_view" (optional): The latest view value.
                    - "messages" (optional): A list of raw message data.
        Returns:
            SandboxState: An instance of the SandboxState class populated with the provided data.
        Notes:
            - The "messages" key in the input dictionary is expected to contain a list of raw message data.
            These messages are serialized to JSON and validated using the ModelMessagesTypeAdapter.
            - If an error occurs during message deserialization, an error is logged, and the `messages`
            attribute is set to an empty list.
        """
        inst = cls()
        inst.topic_anchor = data.get("topic_anchor")
        inst.latest_view = data.get("latest_view")
        msgs_raw = data.get("messages", [])
        try:
            msgs_json = json.dumps(msgs_raw)
            inst.messages = list(ModelMessagesTypeAdapter.validate_json(msgs_json))
        except Exception as e:
            logfire.error("Failed deserializing sandbox messages", error=str(e))
            inst.messages = []
        return inst


#_______ Utility Functions __________

def save_sandbox_state(dir_path: Path, session_id: str, sandbox: SandboxState) -> None:
    """
    Saves the state of a sandbox to a JSON file.

    This function creates the specified directory if it does not exist, writes the sandbox
    state to a temporary file, and then renames the temporary file to the final JSON file.
    If an error occurs during the process, it logs the error.

    Args:
        dir_path (Path): The directory path where the sandbox state file will be saved.
        session_id (str): A unique identifier for the session, used as the filename.
        sandbox (SandboxState): The sandbox state object to be saved.

    Raises:
        Exception: If an error occurs during the file operations, it is logged but not re-raised.

    Logs:
        Logs an error message if saving the sandbox state fails, including the session ID
        and the error message.
    """
    try:
        dir_path.mkdir(parents=True, exist_ok=True)
        tmp = dir_path / f"{session_id}.tmp"
        final = dir_path / f"{session_id}.json"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(sandbox.to_dict(), f, ensure_ascii=False, indent=2)
        tmp.replace(final)
    except Exception as e:
        logfire.error("Failed saving sandbox state", session_id=session_id, error=str(e))


def load_sandbox_state(dir_path: Path, session_id: str) -> Optional[SandboxState]:
    """
    Load the sandbox state from a JSON file.

    Args:
        dir_path (Path): The directory path where the sandbox state files are stored.
        session_id (str): The unique identifier for the session.

    Returns:
        Optional[SandboxState]: The loaded sandbox state as a `SandboxState` object 
        if the file exists and is successfully parsed, otherwise `None`.

    Notes:
        - The function constructs the file path by combining `dir_path` and 
          the `session_id` with a `.json` extension.
        - If the file does not exist, the function returns `None`.
        - If an error occurs during file reading or JSON parsing, the function logs 
          the error and returns `None`.
    """
    fp = dir_path / f"{session_id}.json"
    if not fp.exists():
        return None
    try:
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        return SandboxState.from_dict(data)
    except Exception as e:
        logfire.error("Failed loading sandbox state", session_id=session_id, error=str(e))
        return None
