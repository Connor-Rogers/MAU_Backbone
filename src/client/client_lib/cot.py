from client_lib.agent import agent
from client_lib.context_generator import ContextGenerator
from datetime import datetime, timezone
from mcp.types import CallToolResult

from pydantic_ai.messages import ModelResponse, ModelMessage, TextPart


COT_END_PROMPT = "End of chain of thought"


class ChainOfThought:
    def __init__(self, query: str, previous_messages: list[ModelMessage] = None):
        self.previous_messages = previous_messages or []
        self.query = query
        self.chain: list[ModelMessage] = []
        self.ctx = ContextGenerator(agent)

    async def _generate_system_prompt(self, problem_description: str) -> str:
        # build tool summary list
        tools = await self.ctx.list_tools()
        tool_summaries = "\n".join(f"{tool.name}: {tool.description}" for tool in tools)
        if not tool_summaries:
            tool_summaries = "No tools available."
        return f"""
You are a careful, step-by-step reasoning agent.
You've got these tools available:
{tool_summaries}

When you need to use a tool, respond with a JSON call:
{{"name": TOOL_NAME, "arguments": {{…}}}}
Then wait for the tool's output before continuing your reasoning.
When you have the final answer, give it clearly and end with "End of chain of thought.""".strip()+ "USER PROBLEM: "
    async def run_cot(self, max_iters=5):
        # seed chain with user query
        self.chain.append(
            ModelMessage(
                role="user",
                content=self.query,
                timestamp=datetime.now(timezone.utc).isoformat(),
                parts=[],
                tools_used=[],
            )
        )
        # prepare history
        history = self.previous_messages + self.chain
        # generate system prompt
        system_prompt = await self._generate_system_prompt(self.query)
        for _ in range(max_iters):
            # run agent in streaming mode
            async with agent.run_stream(
                system_prompt, message_history=history
            ) as stream:
                buffer = []
                async for part in stream.stream(debounce_by=0.01):
                    if isinstance(part, CallToolResult):
                        # handle tool result
                        tool_msg = ModelMessage(
                            role="model",
                            content=str(part),
                            timestamp=stream.timestamp(),
                            parts=[],
                            tools_used=[part.name],
                        )
                        self.chain.append(tool_msg)
                        history.append(tool_msg)
                    else:
                        buffer.append(part)
                # assemble model response
                response_text = "".join(buffer)
                
                # check for end marker
                if "End of chain of thought" in response_text:
                    final = response_text.replace("End of chain of thought", "").strip()
                    return final
                # normal response
                model_msg = ModelMessage(
                    role="model",
                    content=response_text,
                    timestamp=stream.timestamp(),
                    parts=[TextPart(response_text)],
                    tools_used=[],
                )
                self.chain.append(model_msg)
                history.append(model_msg)
        raise RuntimeError("Exceeded max iterations without a final answer")
