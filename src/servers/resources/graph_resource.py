from server_lib.graph_networkx import NetworkXGraph
from typing import List, Dict, Optional, Any

class GraphResource:
    def __init__(self):
        self.nx_adapter = NetworkXGraph()
        self.graph = self.nx_adapter.load_graph(directed=True)

    def list_nodes(self) -> List[Dict]:
        """Return all nodes with attributes."""
        return [ {'id': nid, **attrs} for nid, attrs in self.graph.nodes(data=True) ]

    def get_node(self, node_id: str) -> Optional[Dict]:
        """Return a single node and its outgoing edges."""
        if node_id not in self.graph:
            return None
        attrs = dict(self.graph.nodes[node_id])
        edges = []
        for _, tgt, data in self.graph.out_edges(node_id, data=True):
            edge = {'target': tgt, **data}
            edges.append(edge)
        return {'id': node_id, **attrs, 'edges': edges}

    def get_graph_stats(self) -> Dict:
        """Return graph statistics."""
        return self.nx_adapter.get_graph_stats()

    def list_communities(self) -> Dict[str, List[str]]:
        """Return detected communities mapping ids to member lists."""
        return self.nx_adapter.get_communities()

    def get_central(self, measure: str = 'pagerank', top_n: int = 10) -> List[Dict]:
        """Return top-N central nodes by given measure."""
        top = self.nx_adapter.get_central_nodes(measure, top_n)
        return [ {'id': nid, 'score': score} for nid, score in top ]

    def subgraph_by_type(self, rel_type: str) -> Dict:
        """Return nodes and edges of subgraph filtered by relationship type."""
        sub = self.nx_adapter.get_subgraph_by_relationship(rel_type)
        nodes = [ {'id': nid, **attrs} for nid, attrs in sub.nodes(data=True) ]
        edges = [ {'source': u, 'target': v, **data} for u, v, data in sub.edges(data=True) ]
        return {'nodes': nodes, 'edges': edges}

    def to_json(self, data: Any) -> str:
        """Serialize data to JSON string."""
        import json
        return json.dumps(data, indent=2)


