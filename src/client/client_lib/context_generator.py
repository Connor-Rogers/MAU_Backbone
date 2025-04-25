from mcp import ClientSession, StdioServerParameters, stdio_client
from pydantic_ai import Agent
import os
from client_lib.database import Database
from client_lib.chat import to_chat_message


server_params = StdioServerParameters(
    command="uv", args=["run", "../servers/server.py", "server"], env=os.environ
)


class ContextGenerator:
    def __init__(self, agent: Agent, database: Database):
        self.agent = agent
        self.database = database

    async def query_context(self, chat) -> str:
        """Generate context for the chat"""
        chat_messages = await self.database.get_messages()
        chat_messages = [to_chat_message(m) for m in chat_messages]
        context = "\n".join(f"{m['role']}: {m['content']}" for m in chat_messages)
        return context

    async def with_client_session(self, func):
        """Wrapper to open stdio_client and ClientSession."""
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await func(session)

    async def getTool(self, query: str) -> str:
        async def fetch_tools(session: ClientSession):
            tools = await session.list_tools()
            matching_tools = [
                tool
                for tool in tools
                if any(
                    keyword in tool[0].lower() or (isinstance(tool[1], str) and keyword in tool[1].lower())
                    for keyword in query.lower().split()
                )
            ]
            if matching_tools:
                return matching_tools
            else:
                raise ValueError(
                    "No matching tools or adjacent phrases found on the MCP server based on the query keywords"
                )

        return await self.with_client_session(fetch_tools)

    async def executeTool(self, tool_name: str, tool_args: dict | None = None) -> str:
        if tool_args is None:
            tool_args = {}

        async def execute(session: ClientSession):
            return await session.call_tool(tool_name, tool_args)

        return await self.with_client_session(execute)
    
    async def get_and_execute_tool(self, query: str) -> str:
        try:
            tools = await self.getTool(query)
            if tools:
                tool_name = tools[0][0]
                tool_args = tools[0][1]
                return await self.executeTool(tool_name, tool_args)
            else:
                return "No matching tools found."
        except ValueError as e:
            return str(e)
    