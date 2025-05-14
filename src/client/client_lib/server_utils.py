from mcp import ClientSession, StdioServerParameters, stdio_client, Tool
import os

server_params = StdioServerParameters(
    command="uv", args=["run", "../servers/server.py", "server"], env=os.environ
)

async def with_client_session(func):
        """Wrapper to open stdio_client and ClientSession."""
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await func(session)