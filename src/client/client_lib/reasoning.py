"""
Knowledge Graph Reasoning Module
"""

from typing import Dict, List, Optional, Tuple
from pathlib import Path
import pickle
import hashlib
import logfire

import networkx as nx
from sentence_transformers import SentenceTransformer, util


THIS_DIR = Path(__file__).parent
REASONING_DIR = THIS_DIR / "reasoning_state"
REASONING_DIR.mkdir(exist_ok=True)
class ReasoningGraph:
    """
    A class to represent the reasoning graph for query tracing and tool call management.
    """
    def __init__(self):
        """
        Initializes an instance of the class.

        Attributes:
            graph (networkx.DiGraph): A directed graph used for reasoning tasks.
            embedder (SentenceTransformer): A pre-trained sentence transformer model 
                for embedding text, initialized with the "all-MiniLM-L6-v2" model.
            query_index (Dict[str, str]): A dictionary mapping query hashes to their 
                corresponding canonical IDs.
        """
        self.graph = nx.DiGraph()
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
        self.query_index: Dict[str, str] = {}  # query_hash -> canonical_id

    def _canonicalize(self, query: str) -> str:
        """Hash-based canonical ID for similar queries."""
        tokens = sorted(query.lower().split())
        text = " ".join(tokens)
        return hashlib.sha256(text.encode()).hexdigest()

    def _embed(self, query: str):
        """Embed a query using the pre-trained sentence transformer model."""
        return self.embedder.encode(query, convert_to_tensor=True)

    def add_trace(
        self,
        query: str,
        tool_calls: List[Tuple[str, dict]],
        final_answer: Optional[str] = None,
    ):
        """
        Adds a trace of the reasoning process to the internal graph representation.

        This method records the sequence of tool calls and the final answer (if provided)
        for a given query. Each query, tool call, and answer is represented as a node in
        the graph, with edges describing the relationships between them.

        Args:
            query (str): The input query string to be traced.
            tool_calls (List[Tuple[str, dict]]): A list of tuples where each tuple contains
                the name of the tool (str) and its arguments (dict) used during the reasoning process.
            final_answer (Optional[str], optional): The final answer to the query, if available.
                Defaults to None.

        Side Effects:
            - Updates the `query_index` dictionary with the canonicalized query ID and the query string.
            - Adds nodes and edges to the internal graph (`self.graph`) to represent the reasoning process.

        Example:
            add_trace(
                query="What is the capital of France?",
                tool_calls=[
                    ("search_tool", {"query": "capital of France"}),
                    ("lookup_tool", {"key": "Paris"})
                ],
                final_answer="Paris"
            )
        """
        q_id = self._canonicalize(query)
        self.query_index[q_id] = query
        self.graph.add_node(q_id, type="query", text=query)

        prev_node = q_id
        for tool_name, args in tool_calls:
            tool_id = f"{tool_name}:{hashlib.md5(str(args).encode()).hexdigest()}"
            self.graph.add_node(tool_id, type="tool", tool=tool_name, args=args)
            self.graph.add_edge(prev_node, tool_id, relation="calls")
            prev_node = tool_id

        if final_answer:
            answer_id = f"answer:{hashlib.md5(final_answer.encode()).hexdigest()}"
            self.graph.add_node(answer_id, type="answer", text=final_answer)
            self.graph.add_edge(prev_node, answer_id, relation="answers")

    def match_query(self, query: str, threshold=0.85) -> Optional[str]:
        """
        Matches a given query string against a set of known queries and returns the 
        identifier of the best match if the similarity score meets or exceeds the threshold.

        Args:
            query (str): The input query string to match.
            threshold (float, optional): The minimum similarity score required to consider 
                a match valid. Defaults to 0.85.

        Returns:
            Optional[str]: The identifier of the best matching query if the similarity 
            score is above the threshold; otherwise, None.
        """
        q_vec = self._embed(query)
        best_match = None
        best_score = 0.0

        for q_id, known_query in self.query_index.items():
            k_vec = self._embed(known_query)
            score = util.cos_sim(q_vec, k_vec).item()
            if score > best_score:
                best_score = score
                best_match = q_id

        return best_match if best_score >= threshold else None

    def get_plan(self, query: str) -> Optional[List[str]]:
        """
        Generates a plan based on the given query by traversing a directed graph.
        This method attempts to find a sequence of tools or steps associated with
        nodes in a graph, starting from the node that matches the given query and
        following its successors until no more successors are found.
        Args:
            query (str): The input query string used to find the starting node in the graph.
        Returns:
            Optional[List[str]]: A list of tools or steps (as strings) representing the plan,
            or None if the query does not match any node in the graph.
        """
        q_id = self.match_query(query)
        if not q_id:
            return None

        path = []
        current = q_id
        while True:
            successors = list(self.graph.successors(current))
            if not successors:
                break
            next_node = successors[0]
            path.append(self.graph.nodes[next_node].get("tool"))
            current = next_node
        return path

    def print_plan(self, query: str):
        """
        Prints the reasoning plan for a given query.

        This method retrieves the reasoning plan associated with the provided query
        and prints it as a sequence of steps. If no matching plan is found, it 
        notifies the user.

        Args:
            query (str): The input query for which the reasoning plan is to be retrieved.

        Returns:
            None
        """
        plan = self.get_plan(query)
        if not plan:
            print("No matching reasoning plan found.")
        else:
            print(" -> ".join(plan))

    def save(self, filepath: str):
        """
        Save the current graph and query index to a file atomically.

        This method serializes the `graph` and `query_index` attributes into a 
        dictionary and writes it to the specified file. The operation is performed 
        atomically by first writing to a temporary file and then replacing the 
        target file with the temporary file.

        Args:
            filepath (str): The path to the file where the data should be saved.

        Notes:
            - The embedder is not persisted as part of this operation.
            - If the target directory does not exist, it will be created.
            - In case of an error during the write operation, the temporary file 
              will be cleaned up if possible.
        """
        data = {
            "graph": self.graph,
            "query_index": self.query_index,
        }
        target = Path(filepath)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target.with_suffix(target.suffix + ".tmp")
        try:
            with open(tmp_path, "wb") as f:
                pickle.dump(data, f)
            tmp_path.replace(target)
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    logfire.warning("Failed to remove temporary file", path=str(tmp_path))

    @classmethod
    def load(cls, filepath: str) -> "ReasoningGraph":
        """
        Load a ReasoningGraph instance from a file.

        This method deserializes a previously saved ReasoningGraph object from a
        file using Python's `pickle` module. It initializes a new instance of the
        class and restores the graph and query index from the loaded data.

        Args:
            filepath (str): The path to the file containing the serialized
                ReasoningGraph object.

        Returns:
            ReasoningGraph: A new instance of the ReasoningGraph class with the
            graph and query index restored from the file.

        Raises:
            FileNotFoundError: If the specified file does not exist.
            pickle.UnpicklingError: If the file cannot be unpickled.
            KeyError: If the required keys ("graph", "query_index") are missing
                from the loaded data.
        """
        with open(filepath, "rb") as f:
            data = pickle.load(f)
        inst = cls()  # re-init embedder fresh
        inst.graph = data.get("graph", nx.DiGraph())
        inst.query_index = data.get("query_index", {})
        return inst


#_______ Utility Functions __________

def load_reasoning_graph(path: Path, session_id: str) -> ReasoningGraph | None:
    """
    Loads a reasoning graph from a file based on the given session ID.

    This function attempts to load a serialized `ReasoningGraph` object from a
    file located at `path/session_id.pkl`. If the file exists and is valid, the
    reasoning graph is loaded and returned. If the file is corrupt or an error
    occurs during loading, a warning is logged, and the function returns `None`.

    Args:
        path (Path): The base directory where session files are stored.
        session_id (str): The unique identifier for the session.

    Returns:
        ReasoningGraph | None: The loaded `ReasoningGraph` object if successful,
        or `None` if the file does not exist or an error occurs during loading.
    """
    session_path = path / f"{session_id}.pkl"
    if session_path.exists():
        try:
            return ReasoningGraph.load(str(session_path))
        except Exception as e:  # Corrupt file; log & ignore
            logfire.warning(
                "Failed to load reasoning graph; ignoring for this session",
                session_id=session_id,
                error=str(e),
            )
    return None


def save_reasoning_graph(path: Path, session_id: str, graph: ReasoningGraph | None):
    """
    Saves a reasoning graph to a specified file path.
    Args:
        path (Path): The directory where the reasoning graph should be saved.
        session_id (str): A unique identifier for the session, used to name the saved file.
        graph (ReasoningGraph | None): The reasoning graph object to be saved. If None, the function does nothing.
    Returns:
        None
    Notes:
        - The reasoning graph is saved as a pickle file with the name format "{session_id}.pkl".
        - If the directory does not exist, it will be created.
        - Logs an error message if saving the graph fails for any reason.
    """
    if graph is None:
        return
    session_path = path / f"{session_id}.pkl"
    try:
        path.mkdir(parents=True, exist_ok=True)
        graph.save(str(session_path))
    except Exception as e:
        logfire.error("Failed to save reasoning graph", session_id=session_id, error=str(e))