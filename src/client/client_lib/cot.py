from typing import List, Tuple
import uuid
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    ModelMessage,
    UserPromptPart,
    SystemPromptPart,
    TextPart,
    ToolReturnPart,
)
import logfire
from mcp.types import CallToolResult
from client_lib.agent import agent
from client_lib.tooling import Tooling
import re
import json

COT_END_PROMPT = "End of chain of thought"

class ChainOfThought:
    def __init__(self, query: str, previous_messages: list[ModelMessage] = None, database=None):
        self.previous_messages = previous_messages or []
        self.query = query
        # now ModeMessage (ModelRequest | ModelResponse)
        self.chain: list[ModelMessage] = []
        

    async def _generate_system_prompt(self, problem_description: str) -> str:
        tools = await Tooling.list_tools()
        tool_summaries = "\n".join(f"{t.name}: {t.description}" for t in tools) or "No tools available."
        return (
            "You are a careful, step-by-step reasoning agent.\n"
            "You've got these tools available:\n"
            f"{tool_summaries}\n\n"
            "When you need to use a tool, respond with a JSON call:\n"
            '{"name": TOOL_NAME, "arguments": {...}}\n'
            'Then wait for the tool\'s output before continuing your reasoning.\n'
            'When you have the final answer, give it clearly and end with '
            f'"{COT_END_PROMPT}".\n\nUSER PROBLEM: \n'
            f'{problem_description}'
        )

    async def run_cot(self, max_iters: int = 5) -> str:
        # 1) seed with user message
        user_req = ModelRequest(
            parts=[UserPromptPart(content=self.query)],
            instructions=None,
        )
        self.chain.append(user_req)

        # 2) build initial history
        history = self.previous_messages + [user_req]

        # 3) add system prompt
        system_str = await self._generate_system_prompt(self.query)
        sys_req = ModelRequest(
            parts=[SystemPromptPart(content=system_str)],
            instructions=None,
        )
        self.chain.append(sys_req)

        # 4) iterative chain-of-thought loop
        for _ in range(max_iters):
            buffer: list[str] = []
            prev_chunk = None
            async with agent.run_stream(system_str, message_history=history) as stream:
                async for part in stream.stream(debounce_by=0.01):
                    system_str = f"'When you have the final answer, give it clearly and end with {COT_END_PROMPT}'"
                    if isinstance(part, CallToolResult):
                        resp = ModelResponse(
                        parts=[TextPart(content=result)],
                        model_name=f"ChainOfThought:{tool}",
                        timestamp=stream.timestamp(),
                    )
                       
                        self.chain.append(resp)
                        history.append(resp)
                    else:
                        # `part` is the full text-so-far; strip off what we've already seen
                        if prev_chunk is not None and part.startswith(prev_chunk):
                            delta = part[len(prev_chunk):]
                        else:
                            # in case of resets or jumps, just take everything
                            delta = part
                        buffer.append(delta)
                        prev_chunk = part


            # assemble the full text response
            text = "".join(buffer)
            print(f"Full text response: {text}")
            # Try to find and handle tool calls in the text
            text_part = TextPart(content=text)
            resp = ModelResponse(
                parts=[text_part],
                model_name=None,
                timestamp=stream.timestamp(),
            )
            self.chain.append(resp)
            history.append(resp)
            
            tool_result:List[Tuple[str, str]]= await Tooling.execute_tool_from_text(text)
            if tool_result:

                # If tool calls were detected, handle them
                for result, tool in tool_result:
                    resp = ModelResponse(
                        parts=[TextPart(content=result)],
                        model_name=f"ChainOfThought:{tool}",
                        timestamp=stream.timestamp(),
                    )
                    print(f"Tool result: {resp}")
                    self.chain.append(resp)
                    history.append(resp)


            
            

            # check for end marker
            if COT_END_PROMPT in text:
                return text.replace(COT_END_PROMPT, "").strip()

        raise RuntimeError("Exceeded max iterations without a final answer")
