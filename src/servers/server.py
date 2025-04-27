from mcp.server.fastmcp import FastMCP

from pydantic_ai import Agent

server = FastMCP('PydanticAI Server')
server_agent = Agent(
    'openai:gpt-4o-mini', system_prompt=''
)


@server.tool("poet", "Generates a poem. args: theme: (str) - 'the theme of the poem'")
async def poet(theme: str) -> str:
    """Poem generator"""
    r = await server_agent.run(f'write a poem about {theme}')
    return r.output


if __name__ == '__main__':
    server.run()