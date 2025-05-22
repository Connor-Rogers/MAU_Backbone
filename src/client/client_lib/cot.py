from typing import List, Tuple
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    ModelMessage,
    UserPromptPart,
    TextPart,
)
import logfire
from mcp.types import CallToolResult
from client_lib.agent import agent
from client_lib.tooling import Tooling
import re

COT_END_PROMPT = "End of chain of thought"
class ChainOfThought:
    """
    Chain of Thought (CoT) reasoning agent.

    This class implements a chain of thought reasoning agent that interacts with a model to generate
    responses based on user queries. It uses a system prompt to guide the model's reasoning process
    and can handle tool calls within the reasoning chain.
    Attributes:
        query (str): The user query to be processed.
        previous_messages (list[ModelMessage]): A list of previous messages in the conversation.
        chain (list[ModelMessage]): A list of messages representing the reasoning chain.
    Methods:
        _generate_system_prompt(problem_description: str) -> str:
            Generates a system prompt based on the provided problem description.
        run_cot(max_iters: int = 5):
            Runs the chain of thought reasoning process, iteratively generating responses and handling
            tool calls until a final answer is reached or the maximum number of iterations is exceeded.
    """
    def __init__(self, query: str, previous_messages: list[ModelMessage] = None, database=None):
        self.previous_messages = previous_messages or []
        self.query = query
        self.view = None
        self.tool_summaries = None
        self.chain: list[ModelMessage] = []
        

    async def _generate_system_prompt(self, problem_description: str) -> str:
        if self.tool_summaries is None:
            tools = await Tooling.list_tools()
            self.tool_summaries = "\n".join(f"{t.name}: {t.description}" for t in tools) or "No tools available."
       
        return (
            "You are a careful, step-by-step reasoning agent.\n"
            "You've got these tools available:\n"
            f"{self.tool_summaries}\n\n"
            "When you need to use a tool, respond with a JSON call:\n"
            '{"name": TOOL_NAME, "arguments": {...}}\n'
            'Then wait for the tool\'s output before continuing your reasoning.\n'
            'When you have the final answer, give it clearly and end with '
            f'"{COT_END_PROMPT}".\n\nUSER PROBLEM: \n'
            f'{problem_description}'
        )
    async def run_cot(self, max_iters: int = 5):
        # 1) seed with user message
        user_req = ModelRequest(
            parts=[UserPromptPart(content=self.query)],
            instructions=None,
        )
        # 2) build initial history
        self.chain.append(user_req)
        history = self.previous_messages + [user_req]
        terminate = False
        # 3) add system prompt
        system_str = await self._generate_system_prompt(self.query)
        # 4) iterative chain-of-thought loop
        for _ in range(max_iters):
            
            buffer: list[str] = []
            prev_chunk = None
            async with agent.run_stream(system_str, message_history=history) as stream:
                async for part in stream.stream(debounce_by=0.01):
                    system_str = f"'When you have the final answer, give it clearly and end with {COT_END_PROMPT}' \
                                    you have the following tools available: {self.tool_summaries}"
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


            # Assemble the full text response
            text = "".join(buffer)
            logfire.info(f"Full text response: {text}")
           
            # Check for end marker
            if COT_END_PROMPT in text:
                # Remove the end prompt and anything after it, plus whitespace before it
                end_marker_index = text.find(COT_END_PROMPT)
                if end_marker_index > 0:
                    text = text[:end_marker_index].rstrip()
                terminate = True
            
            if not terminate:
                tool_result:List[Tuple[str, str, str]]= await Tooling.execute_tool_from_text(text)
            
            if tool_result:
                text = re.sub(r'\{.*?\}', '', text, flags=re.DOTALL).strip()
                text = re.sub(r'[\{\}]', '', text).strip()
            
            # Append Model Response
            resp = ModelResponse(
                parts=[TextPart(content=text)],
                model_name=f"ChainOfThought:Model:{agent.name}",
                timestamp=stream.timestamp(),
            ) 
            self.chain.append(resp)
            history.append(resp)

            if terminate:
                return
    
            if tool_result:
                # If tool calls were detected, handle them
                for view, result, tool in tool_result:
                    resp = ModelResponse(
                        parts=[TextPart(content=result)],
                        model_name=f"ChainOfThought:Tool:{tool}",
                        timestamp=stream.timestamp(),
                    )
                    logfire.info(f"Tool result: {resp}")
                    self.view = view
                    self.chain.append((resp, view))
                    history.append(resp)

        # 5) if we get here, we didn't find the end marker (aka we thought to hard)     
        logfire.warning("Chain of thought exceeded max iterations without finding end marker.")
        raise RuntimeError("Exceeded max iterations without a final answer")
