from mcp.server.fastmcp import FastMCP

from pydantic_ai import Agent
from resources.graph_resource import GraphResource
from prompts.prompts import Prompts
from server_lib.models import ToolWithView

server = FastMCP('PydanticAI Server')
server_agent = Agent(
    'openai:gpt-4o-mini', system_prompt=''
)

# initialize graph resource and prompts
graph_res = GraphResource()
prompts = Prompts()

@server.tool("list_nodes", "List all companies in the supply network")
async def list_nodes() -> str:
    data = graph_res.list_nodes()
    return ToolWithView(view="table", response=graph_res.to_json(data))


@server.tool("get_node", "Get details for a company. args: node_id: (str) - ID of the company")
async def get_node(node_id: str) -> str:
    node = graph_res.get_node(node_id)
    return ToolWithView(view="none", response=graph_res.to_json(node) if node else f"Node {node_id} not found.")


@server.tool("graph_stats", "Get statistics for the supply network graph")
async def graph_stats() -> str:
    stats = graph_res.get_graph_stats()
    return ToolWithView(view="none", response=graph_res.to_json(stats))


@server.tool("list_communities", "Get detected community clusters in the network")
async def list_communities() -> str:
    comm = graph_res.list_communities()
    return ToolWithView(view="graph", response=graph_res.to_json(comm))



@server.tool("get_central", "Get top central companies. args: measure: (str) - centrality measure, top_n: (int) - number of companies")
async def get_central(measure: str = 'pagerank', top_n: int = 10) -> str:
    central = graph_res.get_central(measure, top_n)
    return ToolWithView(view="table", response=graph_res.to_json(central))


@server.tool("subgraph_by_type", "Get subgraph filtered by relationship type. args: rel_type: (str) - type of relationship")
async def subgraph_by_type(rel_type: str) -> str:
    sub = graph_res.subgraph_by_type(rel_type)
    return ToolWithView(view="graph", response=graph_res.to_json(sub))


if __name__ == '__main__':
    server.run()