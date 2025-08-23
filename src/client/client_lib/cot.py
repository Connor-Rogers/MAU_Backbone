from typing import List, Tuple
import re

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    ModelMessage,
    UserPromptPart,
    TextPart,
)


import logfire
from mcp.types import CallToolResult, TextContent

from client_lib.reasoning import ReasoningGraph
from client_lib.agent import agent
from client_lib.tooling import Tooling
from client_lib.sandbox import SandboxState


COT_END_PROMPT = "[END OF REASONING]"


class ChainOfThought:
    def __init__(
        self, query: str, sandbox: SandboxState, reasoning_graph: ReasoningGraph
    ):
        self.query = query
        self.view = None
        self.sandbox = sandbox
        self.tool_summaries = None
        self.chain: list[ModelMessage] = []

        # rg planning
        self.reasoning_graph = reasoning_graph
        self.plan = self.reasoning_graph.get_plan(query)
        self.expected_tool_steps = 0 if not self.plan else len(self.plan)

        if not sandbox.is_same_topic(query):
            sandbox.reset(query)

        # Seed the user query if not already present
        if not any(
            isinstance(m, ModelRequest) and m.parts[0].content == query
            for m in self.sandbox.messages
        ):
            user_req = ModelRequest(parts=[UserPromptPart(content=query)])
            self.chain.append(user_req)
            self.sandbox.extend(user_req)

    async def _generate_system_prompt(self, problem_description: str) -> str:
        plan_hint = ""
        if self.plan:
            plan_hint = (
                "A typical solution path for this kind of query is:\n"
                + " → ".join(self.plan)
                + "\n"
            )

        if self.tool_summaries is None:
            tools = await Tooling.list_tools()
            self.tool_summaries = (
                "\n".join(f"{t.name}: {t.description}" for t in tools)
                or "No tools available."
            )

        return (
            "You are a careful, step-by-step reasoning agent.\n"
            "You have access to the following tools:\n"
            f"{self.tool_summaries}\n\n"
            f"{plan_hint}"
            "When a tool is required:\n"
            "  - First, explain *why* the tool is needed.\n"
            "  - Then, format your tool call as JSON on a new line:\n"
            '{"name": TOOL_NAME, "arguments": {...}}\n\n'
            "Wait for the tool’s output before continuing reasoning.\n"
            f"Always try to follow the user’s instructions faithfully.\n"
            f'When you are done, give the final answer and end with "{COT_END_PROMPT}".\n\n'
            "USER PROBLEM:\n"
            f"{problem_description}"
        )

    async def run_cot(self, max_iters: int = 5):
        system_str = await self._generate_system_prompt(self.query)
        tool_steps_done = 0
        for iteration in range(max_iters):
            logfire.debug(f"--- Iteration {iteration + 1} ---")
            buffer: list[str] = []
            prev_chunk = ""

            async with agent.run_stream(
                system_str, message_history=self.sandbox.messages
            ) as stream:
                async for part in stream.stream(debounce_by=0.01):
                    if isinstance(part, CallToolResult):
                        chunk = "".join(
                            c.text for c in part.content if isinstance(c, TextContent)
                        )
                    else:
                        chunk = str(part)

                    delta = (
                        chunk[len(prev_chunk) :]
                        if chunk.startswith(prev_chunk)
                        else chunk
                    )
                    buffer.append(delta)
                    prev_chunk = chunk

            text = "".join(buffer)
            logfire.info(f"Model response: {text}")

            # Handle final output
            if COT_END_PROMPT in text:
                end_idx = text.find(COT_END_PROMPT)
                final_text = text[:end_idx].rstrip()

                final_resp = ModelResponse(
                    parts=[TextPart(content=final_text)],
                    model_name=f"ChainOfThought:Model:{agent.name}",
                    timestamp=stream.timestamp(),
                )
                self.chain.append(final_resp)
                self.sandbox.extend(final_resp, view=self.view)
                tool_path = [
                    (node.model_name.split(":")[-1], node.parts[0].content)
                    for node in self.chain
                    if isinstance(node, ModelResponse)
                    and node.model_name.startswith("ChainOfThought:Tool:")
                ]
                final_answer = self.chain[-1].parts[0].content if self.chain else ""

                self.reasoning_graph.add_trace(
                    query=self.query,
                    tool_calls=[(name, {"raw_text": args}) for name, args in tool_path],
                    final_answer=final_answer,
                )

                return  # Terminate

            # Try to parse tool explanation + JSON
            tool_match = re.search(
                r"(?P<explanation>.*?)\n*(?P<json>\{.*\})", text, re.DOTALL
            )
            if not tool_match:
                logfire.warning("No tool call detected; retrying loop.")
                continue

            reasoning = tool_match.group("explanation").strip()
            tool_json = tool_match.group("json").strip()

            if reasoning:
                reasoning_resp = ModelResponse(
                    parts=[TextPart(content=reasoning)],
                    model_name=f"ChainOfThought:Model:{agent.name}",
                    timestamp=stream.timestamp(),
                )
                self.chain.append(reasoning_resp)
                self.sandbox.extend(reasoning_resp, view=self.view)

            tool_result: List[Tuple[str, str, str]] = (
                await Tooling.execute_tool_from_text(tool_json)
            )
            if not tool_result:
                logfire.warning("Tool execution failed or returned no result.")
                continue

            tool_steps_done += 1
            if tool_steps_done >= self.expected_tool_steps:
                logfire.info("Early stopping based on known reasoning path.")
                return

            for view, result, tool in tool_result:
                tool_resp = ModelResponse(
                    parts=[TextPart(content=result)],
                    model_name=f"ChainOfThought:Tool:{tool}",
                    timestamp=stream.timestamp(),
                )
                self.view = view
                self.chain.append(tool_resp)
                self.sandbox.extend(tool_resp, view=view)

        logfire.warning(
            "Chain of thought exceeded max iterations without reaching end marker."
        )
        raise RuntimeError("Exceeded max iterations without a final answer.")
