import logging
from mcp import ClientSession, StdioServerParameters, stdio_client, Tool
from pydantic_ai import Agent
import os
from client_lib.database import Database
import difflib
from client_lib.chat import to_chat_message
from pydantic_ai.messages import TextPart


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

    async def getTool(self, query: str) -> list:
        print(f"Starting getTool with query: {query}")
        
        # Check for empty query
        if not query or query.strip() == "":
            logging.warning("Empty query provided to getTool")
            return []

        async def fetch_tools(session: ClientSession):
            logging.debug("Fetching tools from MCP server...")
            try:
                tools_result = await session.list_tools()
                
                # Convert ListToolsResult to a list we can work with
                tools = list(tools_result.tools)
                
                if not tools:
                    logging.warning("No tools available on the MCP server.")
                    return []

                print(f"Fetched {len(tools)} tools from MCP server.")
                logging.debug(f"Available tools: {tools}")

                # Check for exact match first
                query_lower = query.strip().lower()
                for tool in tools:
                    if tool.name.lower() == query_lower:
                        print(f"Found exact tool match for query: {query}")
                        return [tool]

                print("No exact match found. Proceeding with fuzzy matching.")

                # Normalize for fuzzy matching
                tool_strings = [
                    (tool.name, f"{tool.name} {tool.description if hasattr(tool, 'description') else ''}".lower())
                    for tool in tools
                ]
                logging.debug(f"Normalized tool strings for fuzzy matching: {tool_strings}")

                # Fuzzy matching using difflib
                scores = []
                for name, text in tool_strings:
                    match_score = difflib.SequenceMatcher(None, query_lower, text).ratio()
                    scores.append((match_score, name))
                    logging.debug(f"Fuzzy match score for tool '{name}': {match_score}")

                scores.sort(reverse=True)  # Best matches first
                print(f"Sorted tools by fuzzy match scores: {scores}")

                if scores and scores[0][0] > 0.3:  # Lower threshold slightly
                    best_tool_name = scores[0][1]
                    print(f"Best fuzzy match tool: {best_tool_name} with score: {scores[0][0]}")
                    # Find the full tool info
                    best_tool = next((tool for tool in tools if tool.name == best_tool_name), None)
                    if best_tool:
                        logging.debug(f"Best tool details: {best_tool}")
                        return [best_tool]
                
                # If we get here, no tool matched
                logging.warning(f"No matching tool found for query: '{query}'")
                return []
                
            except Exception as e:
                print(f"Error fetching tools: {e}")
                return []

        print("Calling with_client_session to fetch tools.")
        try:
            result = await self.with_client_session(fetch_tools)
            print(f"getTool completed successfully for query: '{query}'")
            return result
        except Exception as e:
            print(f"Error in getTool: {e}")
            return []


    async def extract_tool_args(self, query: str, tool_name: str, tool:Tool) -> dict:
        """Extract tool arguments from the query based on the tool's schema."""
        try:
            # If the tool has a parameter schema, use it to extract arguments
            if tool.description:
                # Use the agent to extract parameters based on the tool's schema
                prompt = f"""
                Extract the parameters for the tool '{tool_name}' from this user query:
                
                Query: {query}
                
                Tool parameter schema: {tool.description}
                
                Return only a valid JSON object with the extracted parameters.
                """
                
                result = await self.agent.run(prompt)
                try:
                    # Try to find a JSON block in the response
                    response_text = result.output
                    
                    # Look for JSON between ``` markers
                    import re
                    import json
                    
                    # Try to find JSON in code blocks
                    json_matches = re.findall(r'```(?:json)?\s*(.*?)\s*```', response_text, re.DOTALL)
                    if json_matches:
                        for match in json_matches:
                            try:
                                return json.loads(match.strip())
                            except:
                                continue
                    
                    # Try to find JSON without code blocks
                    try:
                        return json.loads(response_text.strip())
                    except:
                        pass
                    
                    # Fallback: try to extract parameters from any text
                    param_matches = re.findall(r'"(\w+)":\s*(?:"([^"]*)"|\[([^\]]*)\]|(\d+)|(\{.*?\})|(null)|(true|false))', response_text)
                    if param_matches:
                        params = {}
                        for match in param_matches:
                            key = match[0]
                            # Find the first non-empty value in the groups
                            value = next((val for val in match[1:] if val), None)
                            if key and value is not None:
                                try:
                                    # Try to parse as JSON if possible
                                    params[key] = json.loads(value)
                                except:
                                    params[key] = value
                        return params
                except Exception as e:
                    print(f"Error parsing agent response for tool args: {e}")
            
            # If no parameters were extracted or tool has no schema, return empty dict
            return {}
        except Exception as e:
            print(f"Error extracting tool args: {e}")
            return {}

    async def executeTool(self, tool_name: str, tool_args: dict | None = None) -> str:
        if tool_args is None:
            tool_args = {}

        async def execute(session: ClientSession):
            try:
                return await session.call_tool(tool_name, tool_args)
            except Exception as e:
                print(f"Error executing tool {tool_name}: {e}")
                return f"Error executing tool {tool_name}: {str(e)}"

        return await self.with_client_session(execute)
    
    async def get_and_execute_tool(self, query: str) -> str | None:
        try:
            # If query is empty or only whitespace, don't try to match tools
            if not query or query.strip() == "":
                return ""
                
            # Continue with normal fuzzy matching
            tools = await self.getTool(query)
            if tools and len(tools) > 0:
                tool = tools[0]
                tool_name = tool.name if hasattr(tool, 'name') else str(tool)
                
                # Extract tool arguments from the query
                tool_args = await self.extract_tool_args(query, tool_name, tool)

                print(f"Executing tool: {tool_name} with args: {tool_args}")
                return await self.executeTool(tool_name, tool_args)
            else:
                # Don't return error messages for empty results - this might be just normal text
                if not query or query.strip() == "":
                    return None
                return None  # Return empty string instead of an error message
        except ValueError as e:
            print(f"Error in get_and_execute_tool: {e}")
            # Return empty string instead of an error message
            return None
        except Exception as e:
            print(f"Unexpected error in get_and_execute_tool: {e}")
            # Return empty string instead of an error message
            return None
