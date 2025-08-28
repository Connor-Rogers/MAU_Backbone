"""
Chain of Though Modial
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import List, Tuple, Optional, Set, Dict, Any
import re
import json
import logfire

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    ModelMessage,
    UserPromptPart,
    TextPart,
)
from mcp.types import CallToolResult, TextContent

from client_lib.reasoning import ReasoningGraph
from client_lib.agent import agent
from client_lib.tooling import Tooling
from client_lib.sandbox import SandboxState


COT_END_PROMPT = "[END OF REASONING]"


# ______Public API Types_______

class Mode(Enum):
    """High-level mode of the CoT controller."""
    INTERACTIVE = auto()     # normal: model may call tools
    FINALIZING = auto()      # produce final answer; tools are disallowed


@dataclass(frozen=True)
class CoTConfig:
    """Tunable limits and knobs."""
    max_iters: int = 5
    max_tool_steps: int = 5
    max_finalize_nudges: int = 2
    # If True, after any successful tool execution we immediately switch to FINALIZING mode
    # so the model is forced to synthesize a final answer instead of repeatedly invoking tools.
    auto_finalize_after_tool: bool = False  # disabled by default to let model view tool output itself


@dataclass
class CoTState:
    """Mutable state tracked across the run."""
    iteration: int = 0
    tools_run: int = 0
    mode: Mode = Mode.INTERACTIVE
    finalize_nudges: int = 0
    executed_tool_calls: Set[str] = field(default_factory=set)
    last_tool_id: Optional[str] = None
    justification_nudges: int = 0  # times we've asked model to justify tool call


# ______Chain of Thought______

class ChainOfThought:
    """
    ChainOfThought is a class designed to facilitate step-by-step reasoning for solving complex queries. 
    It interacts with a sandbox environment, a reasoning graph, and a set of tools to iteratively generate 
    solutions or final answers. The class is designed to handle tool execution, manage reasoning states, 
    and persist traces of the reasoning process.
    
    Attributes:
        query (str): The user-provided query or problem description.
        sandbox (SandboxState): The sandbox environment that maintains the state of the reasoning process.
        reasoning_graph (ReasoningGraph): A graph structure used to manage reasoning paths and traces.
        config (CoTConfig): Configuration options for the reasoning process, such as maximum iterations.
        chain (List[ModelMessage]): A list of messages representing the reasoning chain.
        tool_summaries (Optional[str]): A summary of available tools, fetched dynamically.
        plan (Optional[List[str]]): An optional plan or hint for solving the query.
        expected_tool_steps (int): The number of tool steps expected based on the plan.
    """
    def __init__(self, query: str, sandbox: SandboxState, reasoning_graph: ReasoningGraph, config: Optional[CoTConfig] = None):
        """
        Initializes a new instance of the class.
        Args:
            query (str): The query string provided by the user.
            sandbox (SandboxState): The current sandbox state for managing the session.
            reasoning_graph (ReasoningGraph): The reasoning graph used for generating plans and reasoning steps.
            config (Optional[CoTConfig]): Optional configuration for the instance. Defaults to a new CoTConfig instance.
        Notes:
            - Resets the sandbox if the query topic differs from the current topic.
            - Ensures the user request is seeded exactly once in the sandbox messages.
        """
        self.query = query
        self.sandbox = sandbox
        self.reasoning_graph = reasoning_graph
        self.config = config or CoTConfig()

        self.chain: List[ModelMessage] = []
        self.tool_summaries: Optional[str] = None

        # Plan is optional; used only for hints. Clean it to avoid None/invalid entries.
        raw_plan = self.reasoning_graph.get_plan(query)
        cleaned_plan: Optional[List[str]] = None
        if raw_plan:
            try:
                cleaned = [str(p).strip() for p in raw_plan if p is not None and str(p).strip()]
                cleaned_plan = cleaned or None
            except Exception:
                cleaned_plan = None
        self.plan: Optional[List[str]] = cleaned_plan
        self.expected_tool_steps: int = 0 if not self.plan else len(self.plan)

        # Topic handling
        if not sandbox.is_same_topic(query):
            sandbox.reset(query)

        # Ensure the user request is seeded exactly once
        if not any(isinstance(m, ModelRequest) and m.parts and m.parts[0].content == query for m in sandbox.messages):
            user_req = ModelRequest(parts=[UserPromptPart(content=query)])
            self._append(user_req)

    # ______ Public entrypoint ______

    async def run_cot(self) -> None:
        """
        Executes the Chain-of-Thought (CoT) reasoning process for the given query.

        This method orchestrates an iterative reasoning process, where the system
        generates responses, evaluates them, and optionally invokes tools to refine
        its understanding or reach a conclusion. The process continues until a final
        answer is determined, a maximum number of iterations is reached, or other
        termination conditions are met.

        The method operates in two modes:
        1. Interactive Mode: The system attempts to detect and execute tool calls
           based on the model's response.
        2. Finalizing Mode: The system avoids tool calls and focuses on summarizing
           or finalizing the response.

        Key Steps:
        - Builds the initial system prompt based on the query.
        - Iteratively generates model responses and evaluates them.
        - Detects and executes tool calls when appropriate.
        - Handles duplicate tool calls, tool execution failures, and mode transitions.
        - Finalizes the reasoning process when a valid final answer is detected or
          when termination conditions are met.

        Raises:
            RuntimeError: If the maximum number of iterations is exceeded without
                          reaching a valid conclusion.

        Logs:
            - Iteration start, including the current mode and tools run.
            - Model responses and reasoning blocks.
            - Tool execution results and mode transitions.

        Returns:
            None
        """
        base_system = await self._build_system_prompt(self.query)
        state = CoTState()

        for state.iteration in range(self.config.max_iters):
            system_prompt = self._attach_turn_state(base_system, state)
            logfire.debug("cot_iteration_start", iter=state.iteration, mode=state.mode.name, tools_run=state.tools_run)

            text = await self._stream_model_text(system_prompt)
            logfire.info("cot_model_response", text=text)

            if self._contains_final_answer(text):
                final_resp = self._emit_final_answer(text)
                self._persist_trace(final_resp)
                return

            if state.mode is Mode.FINALIZING:
                # In finalize mode we forbid more tool calls; keep nudging
                if self._looks_like_tool_json(text):
                    self._nudge_no_tools_in_finalize(state)
                    if state.finalize_nudges > self.config.max_finalize_nudges:
                        self._force_summarized_exit(text)
                        return
                    continue
                self._append_model_text(text)
                continue

            # Normal (interactive) mode: try to find a tool call
            detected = Tooling.detect_tool_calls(text)
            if not detected:
                self._nudge_need_tool_or_final()
                continue

            tool_name, arguments = detected[0]
            tool_id = self._canonical_tool_id(tool_name, arguments)

            # Enforce presence of explanation BEFORE JSON (at least a short sentence)
            try:
                import re as _re
                m_first = _re.search(r'`?\{\s*"name"\s*:\s*"', text)
                prefix_len = 0
                if m_first:
                    prefix_raw = text[:m_first.start()].strip()
                    prefix_len = len(prefix_raw)
                if m_first and prefix_len < 12 and state.justification_nudges < 3:
                    state.justification_nudges += 1
                    self._append_model_note(
                        "Provide a brief natural language justification (one sentence) before the tool JSON call explaining why the tool is needed, then repeat the tool JSON."
                    )
                    continue  # ask model to try again before executing tool
            except Exception:
                pass

            # If duplicate tool call, don't re-add the reasoning block (which would just repeat)
            if self._is_duplicate_tool_call(tool_id, state):
                self._enter_finalize_due_to_duplicate(state, tool_name)
                continue

            # Split explanation (prefix) and JSON tool call; store separately for UI clarity
            explanation_added = False
            json_added = False
            try:
                import re as _re
                m_json = _re.search(r'`?\{\s*"name"\s*:\s*"', text)
                if m_json:
                    prefix = text[:m_json.start()].strip('\n ')
                    json_and_after = text[m_json.start():].strip()
                    # Isolate just the JSON object for clarity (up to first closing brace balance)
                    json_obj_match = _re.match(r'`?(\{.*\})`?$', json_and_after, _re.DOTALL)
                    json_block = json_and_after
                    if json_obj_match:
                        json_block = json_obj_match.group(1)
                    # Append explanation if substantive
                    if prefix and len(prefix) > 8:
                        last_msg = next((m for m in reversed(self.sandbox.messages) if isinstance(m, ModelResponse)), None)
                        last_content = last_msg.parts[0].content if last_msg and getattr(last_msg, 'parts', None) else None
                        if prefix != last_content:
                            self._append_model_text(prefix)
                            explanation_added = True
                    # Append JSON block if not duplicate
                    last_msg2 = next((m for m in reversed(self.sandbox.messages) if isinstance(m, ModelResponse)), None)
                    last_content2 = last_msg2.parts[0].content if last_msg2 and getattr(last_msg2, 'parts', None) else None
                    if json_block and json_block != last_content2:
                        self._append_model_text(json_block)
                        json_added = True
                else:
                    # No JSON found; treat entire text as explanation
                    cleaned = text.strip()
                    if cleaned:
                        last_msg = next((m for m in reversed(self.sandbox.messages) if isinstance(m, ModelResponse)), None)
                        last_content = last_msg.parts[0].content if last_msg and getattr(last_msg, 'parts', None) else None
                        if cleaned != last_content:
                            self._append_model_text(cleaned)
                            explanation_added = True
            except Exception:
                cleaned = text.strip()
                if cleaned:
                    self._append_model_text(cleaned)

            # Execute exactly one tool call (after recording reasoning)
            success = await self._execute_tool(tool_name, arguments, tool_id, state)
            if not success:
                self._append_model_note("Tool returned no result; attempt final answer or different tool.")
                continue

            # Step accounting and mode transitions
            state.tools_run += 1
            # Immediately force finalization if configured (prevents endless tool loops)
            if self.config.auto_finalize_after_tool:
                state.mode = Mode.FINALIZING
                self._append_model_note(
                    f"Tool step complete. Use the tool output above. Provide final answer ending with {COT_END_PROMPT} or justify ONE new tool if truly needed."
                )
                continue
            if state.tools_run >= self.config.max_tool_steps:
                self._enter_finalize_due_to_cap(state)
                continue

        # Exceeded iterations without a sentinel
        self._dump_history_and_raise()

    # ______ Prompt construction ______

    async def _build_system_prompt(self, problem_description: str) -> str:
        """
        Constructs a system prompt string based on the provided problem description,
        available tools, and an optional solution plan.

        This method generates a detailed prompt for a reasoning agent, including
        instructions on how to use tools, format tool calls, and handle tool responses.
        It ensures the agent follows a step-by-step reasoning process and adheres to
        the user's instructions.

        Args:
            problem_description (str): A description of the user's problem or query.

        Returns:
            str: The constructed system prompt string.

        Notes:
            - If a solution plan (`self.plan`) is available, it is included as a hint.
            - If tool summaries (`self.tool_summaries`) are not preloaded, they are
              fetched asynchronously using the `Tooling.list_tools()` method.
            - The prompt includes instructions for tool usage, response handling, and
              when to terminate reasoning.
        """
        plan_hint = ""
        if self.plan:
            try:
                plan_hint = "A typical solution path for this kind of query is:\n" + " → ".join(
                    [p for p in self.plan if isinstance(p, str) and p]
                ) + "\n"
            except Exception:
                plan_hint = ""

        if self.tool_summaries is None:
            tools = await Tooling.list_tools()
            self.tool_summaries = "\n".join(f"{t.name}: {t.description}" for t in tools) or "No tools available."

        return (
            "You are a careful, step-by-step reasoning agent.\n"
            "You have access to the following tools:\n"
            f"{self.tool_summaries}\n\n"
            f"{plan_hint}"
            "When a tool is required:\n"
            "  - Ensure you are NOT repeating steps"
            "  - First, explain *why* the tool is needed.\n"
            "  - Then, output ONE inline backticked JSON object exactly like: \n"
            "    `{\"name\": \"tool_name\", \"arguments\": {...}}`\n"
            "    (Do NOT use triple backtick code fences; use a single pair of backticks.)\n\n"
            "Tools will return JSON responses. Wait for the tool’s (ModelResponse, ChainOfThought:Tool:<Tool Used>) output before continuing.\n"
            "Follow the user’s instructions faithfully.\n"
            f'If the tool call directly answers the user, give the final answer and end with "{COT_END_PROMPT}".\n'
            "Final answers should always be concise and to the point and summarize the operations performed."
            f'Keep reasoning only for multi-tool queries. Always end with "{COT_END_PROMPT}".\n\n'
            f'If tools are not answering the problem, just say you cannot answer the user problem and end with "{COT_END_PROMPT}".\n\n'
            "USER PROBLEM:\n"
            f"{problem_description}"
        )

    @staticmethod
    def _attach_turn_state(base_system: str, state: CoTState) -> str:
        """
        Attaches the turn state information to the base system string.
        This method appends a formatted string representation of the current state
        to the provided base system string. The appended information includes the
        `finalize_mode` status and the number of tools run. The behavior differs
        based on the mode of the provided `CoTState`.
        Args:
            base_system (str): The base system string to which the state information
                will be appended.
            state (CoTState): The current state object containing the mode and tools
                run information.
        Returns:
            str: The base system string with the appended state information. The
            appended string provides instructions based on the mode:
                - If `state.mode` is `Mode.FINALIZING`, it instructs to provide the
                final answer and avoid calling any tools.
                - Otherwise, it instructs to either provide an answer or output a
                tool call JSON after a brief justification.
        """
        if state.mode is Mode.FINALIZING:
            return (
                base_system
                + f"\n(STATE: finalize_mode=true, tools_run={state.tools_run}). "
                  f"Provide the final answer now and end with {COT_END_PROMPT}. "
                  "Do NOT call any tools."
            )
        return (
            base_system
            + f"\n(STATE: finalize_mode=false, tools_run={state.tools_run}). "
              f"If you can answer, end with {COT_END_PROMPT}. Otherwise output ONE tool call JSON after a brief justification."
        )

    # ----------------------------- Model I/O helpers -----------------------------

    async def _stream_model_text(self, system_prompt: str) -> str:
        """
        Asynchronously streams text generated by a model based on a given system prompt.

        This method interacts with an agent to stream text responses in real-time. It processes
        the streamed content, appending new text chunks to a buffer, and returns the complete
        generated text once the stream ends.

        Args:
            system_prompt (str): The initial prompt provided to the model to generate text.

        Returns:
            str: The complete text generated by the model after processing the stream.

        Notes:
            - The method uses a debounce mechanism to process streamed parts with minimal delay.
            - It handles different types of streamed content, including tool call results and
              plain text parts.
        """
        buffer: List[str] = []
        prev_chunk = ""

        async with agent.run_stream(system_prompt, message_history=self.sandbox.messages) as stream:
            async for part in stream.stream(debounce_by=0.01):
                if isinstance(part, CallToolResult):
                    chunk = "".join(c.text for c in part.content if isinstance(c, TextContent))
                else:
                    chunk = str(part)
                delta = chunk[len(prev_chunk):] if chunk.startswith(prev_chunk) else chunk
                buffer.append(delta)
                prev_chunk = chunk

        return "".join(buffer)

    # ______ Finalization Utills ______

    @staticmethod
    def _contains_final_answer(text: str) -> bool:
        """
        Checks if the given text contains a final answer by looking for the end prompt.
        
        Args:
            text (str): The text to check.
        
        Returns:
            bool: True if the text contains a final answer, False otherwise.
        """
        return COT_END_PROMPT in text

    @staticmethod
    def _looks_like_tool_json(text: str) -> bool:
        """
        Checks if the given text looks like a tool JSON by searching for the expected structure.

        Args:
            text (str): The text to check.

        Returns:
            bool: True if the text looks like a tool JSON, False otherwise.
        """
        return re.search(r'\{\s*"name"\s*:\s*', text) is not None

    def _emit_final_answer(self, text: str) -> ModelResponse:
        """
        Extract and append the final answer (without the sentinel).

        Args:
            text (str): The text containing the final answer.

        Returns:
            ModelResponse: The model response containing the final answer.
        """
        end_idx = text.find(COT_END_PROMPT)
        final_text = text[:end_idx].rstrip()
        final_resp = ModelResponse(
            parts=[TextPart(content=final_text)],
            model_name=f"ChainOfThought:Model:{agent.name}",
            timestamp=datetime.now(timezone.utc),
        )
        self._append(final_resp)
        return final_resp

    def _nudge_no_tools_in_finalize(self, state: CoTState) -> None:
        """
        Nudges the model not to use tools in finalize mode.

        Args:
            state (CoTState): The current state of the Chain of Thought.
        """
        state.finalize_nudges += 1
        self._append_model_note(f"Do not call tools in finalize mode. Provide final answer ending with {COT_END_PROMPT}.")

    def _force_summarized_exit(self, text: str) -> None:
        """
        Forces a summarized exit by appending a model note with the provided text.

        Args:
            text (str): The text to include in the model note.
        """
        summary = (
            "Final answer unavailable from model after multiple finalize nudges; summarizing best effort: "
            + text.strip()[:500]
        )
        final_with_sentinel = summary + f" {COT_END_PROMPT}"
        final_resp = self._emit_final_answer(final_with_sentinel)
        self._persist_trace(final_resp)

    def _nudge_need_tool_or_final(self) -> None:
        """
        Nudges the model to either provide a final answer or use a tool.

        Args:
            state (CoTState): The current state of the Chain of Thought.
        """
        self._append_model_note(f"No tool JSON detected. Either answer with {COT_END_PROMPT} or output a single tool JSON.")

    def _enter_finalize_due_to_duplicate(self, state: CoTState, tool_name: str) -> None:
        """
        Enters finalize mode due to a duplicate tool call.

        Args:
            state (CoTState): The current state of the Chain of Thought.
        """
        state.mode = Mode.FINALIZING
        self._append_model_note(f"Duplicate tool call blocked ({tool_name}). Move to final answer with {COT_END_PROMPT}.")

    def _enter_finalize_due_to_cap(self, state: CoTState) -> None:
        """
        Enters finalize mode due to reaching the maximum tool steps.

        Args:
            state (CoTState): The current state of the Chain of Thought.
        """
        state.mode = Mode.FINALIZING
        self._append_model_note(f"Max tool steps reached. Provide final answer ending with {COT_END_PROMPT}.")

    # ______ Tool execution ______

    @staticmethod
    def _canonical_tool_id(tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        Stable identifier for duplicate detection.

        Args:
            tool_name (str): The name of the tool.
            arguments (Dict[str, Any]): The arguments passed to the tool.
        
        Returns:
            str: A stable identifier for the tool call.
        """
        try:
            canonical_args = json.dumps(arguments, sort_keys=True, separators=(",", ":"))
        except Exception:
            canonical_args = str(arguments)
        return f"{tool_name}:{canonical_args}"

    @staticmethod
    def _preserve_reasoning_block(text: str) -> None:  # legacy no-op retained for compatibility
        return

    def _is_duplicate_tool_call(self, tool_id: str, state: CoTState) -> bool:
        """
        Check if the tool call is a duplicate.

        Args:
            tool_id (str): The ID of the tool call.
            state (CoTState): The current state of the Chain of Thought.

        Returns:
            bool: True if the tool call is a duplicate, False otherwise.
        """
        return tool_id in state.executed_tool_calls or tool_id == state.last_tool_id

    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any], tool_id: str, state: CoTState) -> bool:
        """
        Execute one tool and append its result(s). Returns True if any results were produced.
        """
        # Minimal JSON string expected by your executor
        try:
            canonical_args = tool_id.split(":", 1)[1]
            minimal_json = f'{{"name": "{tool_name}", "arguments": {canonical_args}}}'
        except Exception:
            # Fallback if parsing somehow fails
            minimal_json = json.dumps({"name": tool_name, "arguments": arguments})
            canonical_args = json.dumps(arguments, sort_keys=True)

        tool_result: List[Tuple[str, str, str]] = await Tooling.execute_tool_from_text(minimal_json)
        state.executed_tool_calls.add(tool_id)
        state.last_tool_id = tool_id

        if not tool_result:
            return False

        for view, result, tool_used in tool_result:

            tool_resp = ModelResponse(
                parts=[TextPart(content=result),],
                model_name=f"ChainOfThought:Tool:{tool_used}",
                timestamp=datetime.now(timezone.utc),
            )
            self._append(tool_resp, view=view)

        # Add a succinct follow-up guidance message to steer model toward synthesis instead of re-calling.
        try:
            summary_hint = (
                "Summarize or proceed. If the above tool output answers the user, provide the final answer "
                f"ending with {COT_END_PROMPT}. Otherwise justify the next distinct tool (do not repeat the same one)."
            )
            self._append_model_note(summary_hint)
        except Exception:
            pass

        return True

    # ______ Persistence & Utility ______

    def _persist_trace(self, final_resp: ModelResponse) -> None:
        """
        Persist a minimal, readable trace: only Tool responses, plus the final answer.
        """
        tool_path = [
            (node.model_name.split(":")[-1], node.parts[0].content)
            for node in self.chain
            if isinstance(node, ModelResponse) and node.model_name.startswith("ChainOfThought:Tool:")
        ]
        self.reasoning_graph.add_trace(
            query=self.query,
            tool_calls=[(name, {"raw_text": args}) for name, args in tool_path],
            final_answer=final_resp.parts[0].content,
        )

    def _append(self, msg: ModelMessage, view: Optional[str] = None) -> None:
        """Append a message to local chain and sandbox in a single place."""
        self.chain.append(msg)
        self.sandbox.extend(msg, view=view)

    def _append_model_text(self, text: str) -> None:
        self._append(ModelResponse(parts=[TextPart(content=text)],
                                   model_name=f"ChainOfThought:Model:{agent.name}",
                                   timestamp=datetime.now(timezone.utc),))

    def _append_model_note(self, note: str) -> None:
        self._append(ModelResponse(parts=[TextPart(content=note)],
                                   model_name=f"ChainOfThought:Model:{agent.name}",
                                   timestamp=datetime.now(timezone.utc),))

    # ----------------------------- Auto Finalize Helpers -----------------------------
    def _auto_finalize_from_last_tool(self) -> None:
        """Create and emit a final answer immediately using the most recent tool result.

        Avoids another model generation round (which was looping) and ensures
        termination with sentinel.
        """
        last_tool_msg: Optional[ModelResponse] = None
        for m in reversed(self.chain):
            if isinstance(m, ModelResponse) and m.model_name.startswith("ChainOfThought:Tool:"):
                last_tool_msg = m
                break
        snippet = "No tool output available."
        if last_tool_msg and last_tool_msg.parts:
            raw = last_tool_msg.parts[0].content
            try:
                marker = 'raw_response:'
                idx = raw.find(marker)
                extracted = raw[idx+len(marker):].strip() if idx != -1 else raw
                snippet = extracted[:400]
            except Exception:
                snippet = raw[:400]
        final_text = (
            f"Answer derived from tool output: {snippet}\n"
            "(Auto-finalized to prevent looping.)"
        )
        final_with_sentinel = final_text + f" {COT_END_PROMPT}"
        final_resp = self._emit_final_answer(final_with_sentinel)
        self._persist_trace(final_resp)

    def _dump_history_and_raise(self) -> None:
        logfire.warning("cot_no_final_answer", max_iters=self.config.max_iters)
        dump = "\n".join(m.parts[0].content for m in self.sandbox.messages if getattr(m, "parts", None))
        with open("sandbox_messages_dump.txt", "w") as f:
            f.write(dump)
        raise RuntimeError("Exceeded max iterations without final answer sentinel.")