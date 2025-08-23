import re, json
from typing import Tuple
from mcp import ClientSession, Tool
from mcp.types import CallToolResult

from client_lib.server_utils import with_client_session

from client_lib.types import ToolResult

TOOL_PATTERN = re.compile(
    r'(?:```(?:json)?\s*)?'                     # optional opening fence  ``` or ```json
    r'\{\s*"name"\s*:\s*"([^"]+)"\s*,'         #   "name": "..."
    r'\s*"arguments"\s*:\s*({.*?})\s*'         #   "arguments": { ... }
    r'\}(?:\s*```)?',                          # trailing brace + optional closing fence
    re.DOTALL                                  # <-- let "." cross line-breaks
)

class Tooling:
    @staticmethod
    def detect_tool_calls(text: str) -> list[tuple[str, dict]]:
        """
        Detects tool calls in the given text and returns a list of tuples containing the tool name and arguments.
        """
        matches = re.findall(TOOL_PATTERN, text)
        if not matches:
            print("No tool calls detected.")
        return [(match[0], json.loads(match[1])) for match in matches]
    
    @staticmethod
    async def list_tools() -> list:
        """List all available tools."""
        async def fetch_tools(session: ClientSession):
            try:
                tools_result = await session.list_tools()
                return list(tools_result.tools)
            except Exception as e:
                print(f"Error fetching tools: {e}")
                return []

        try:
            result = await with_client_session(fetch_tools)
            return result
        except Exception as e:
            print(f"Error in list_tools: {e}")
            return []
    @staticmethod   
    async def call_tool(tool: Tool, arguments: dict) -> CallToolResult:
        """
        Calls a tool with the given arguments and returns the result.
        """
        async def call_tool(session: ClientSession):
            try:
                result = await session.call_tool(tool.name, arguments)
                return result
            except Exception as e:
                print(f"Error calling tool: {e}")
                return None

        try:
            result = await with_client_session(call_tool)
            return result
        except Exception as e:
            print(f"Error in call_tool: {e}")
            return None
    @staticmethod
    async def execute_tool_from_text(text: str) -> list[ToolResult]:
        """
        Detects tool calls in the given text, executes them, and returns the results.

        returns a list of tuples containing the view, response, and tool name.
        """
        tool_calls = Tooling.detect_tool_calls(text)
        results = []
        
        for tool_name, arguments in tool_calls:
            tools = await Tooling.list_tools()
            tool = next((t for t in tools if t.name == tool_name), None)
            
            if tool:
                result = await Tooling.call_tool(tool, arguments)
                if result:
                    blob: dict = json.loads("".join([item.text for item in result.content]))
                    
                    results.append((blob.get("view"), blob.get("response"), tool.name))
        
        return results