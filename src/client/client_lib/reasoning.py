from typing import Dict, List, Optional, Tuple
import hashlib
import networkx as nx
from sentence_transformers import SentenceTransformer, util

class ReasoningGraph:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
        self.query_index: Dict[str, str] = {}  # query_hash -> canonical_id

    def _canonicalize(self, query: str) -> str:
        """Hash-based canonical ID for similar queries."""
        tokens = sorted(query.lower().split())
        text = " ".join(tokens)
        return hashlib.sha256(text.encode()).hexdigest()

    def _embed(self, query: str):
        return self.embedder.encode(query, convert_to_tensor=True)

    def add_trace(
        self,
        query: str,
        tool_calls: List[Tuple[str, dict]],
        final_answer: Optional[str] = None,
    ):
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
        """Find closest known query and return its canonical ID."""
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
        plan = self.get_plan(query)
        if not plan:
            print("No matching reasoning plan found.")
        else:
            print(" → ".join(plan))
