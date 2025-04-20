from prompts.prompts import Prompts
from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("agents")



mcp.add_prompt(prompt=Prompts.get_prompt("greeting"), name="greeting")


@mcp.tool("hotel_finder", description="Find hotels in a given location.")
def find_hotels() -> Any:
    """
    Find hotels in a given location.
    """