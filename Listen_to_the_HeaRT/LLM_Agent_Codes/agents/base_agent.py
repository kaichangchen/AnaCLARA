from openai import OpenAI
import os
import json
import time
from typing import Callable, Dict, List, Any
import tiktoken


# All LLM calls route through the NVIDIA OpenAI-compatible proxy.
# Aliases below map friendly names to actual NVIDIA endpoint strings.
NVIDIA_OPENAI_BASE_URL = os.getenv(
    "NVIDIA_OPENAI_BASE_URL", "https://inference-api.nvidia.com/v1"
)
NVIDIA_MODEL_ENDPOINTS = {
    "GPT_BEST":       "azure/openai/gpt-5.5",
    "CLAUDE_SONNET":  "azure/anthropic/claude-sonnet-4-6",
    "CLAUDE_OPUS":    "azure/anthropic/claude-opus-4-7",
    "GEMINI_PRO":     "gcp/google/gemini-3.1-pro-preview",
    "GEMINI_STABLE":  "gcp/google/gemini-2.5-pro",
}
DEFAULT_MODEL_ENDPOINT = NVIDIA_MODEL_ENDPOINTS["GPT_BEST"]


def resolve_model_endpoint(model: str) -> str:
    """Translate a friendly alias (e.g. 'GPT_BEST') to its NVIDIA endpoint string.
    If `model` isn't an alias, it's passed through unchanged."""
    return NVIDIA_MODEL_ENDPOINTS.get(model, model)


class Agent:
    def __init__(
        self,
        name: str,
        tools: List[dict],
        available_functions: Dict[str, Callable],
        system_prompt: str,
        model: str = DEFAULT_MODEL_ENDPOINT,
    ):
        """
        Initialize an agent with its own system prompt, tools, and functions.
        All LLM calls go through the NVIDIA OpenAI-compatible proxy.
        """
        self.name = name

        self.openai_client = OpenAI(
            base_url=NVIDIA_OPENAI_BASE_URL,
            api_key=os.getenv("NVIDIA_API_KEY"),
        )

        self.system_prompt = system_prompt
        self.messages = [{"role": "system", "content": system_prompt}]
        self.tools = tools
        self.available_functions = available_functions
        self.model = resolve_model_endpoint(model)
        ###################### Token Usage ###########################
        self.last_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    # Actuator
    def _execute_tool_call_recommended_by_assistant_and_get_outputs(
        self, tool_call
    ) -> Dict[str, Any]:
        """
        Executes a tool call requested by the assistant.
        """
        func_name = tool_call.function.name
        func_args = json.loads(
            tool_call.function.arguments
        )  # dict of argument names to their values

        print(
            f"[{self.name}] Calling function '{func_name}' with arguments: {func_args}"
        )

        # Look up the function dynamically
        func_to_call = self.available_functions.get(func_name)

        if func_to_call is None:
            print(f"Function '{func_name}' is not available.")
            return {"role": "tool", "tool_call_id": tool_call.id, "content": "null"}

        try:
            # Call the function with unpacked arguments
            output = func_to_call(**func_args)
            # Convert the output to a JSON string if it's a dict or list
            if isinstance(output, (dict, list)):
                output = json.dumps(output)
            elif not isinstance(output, str):
                # Convert other non-string outputs to string
                output = str(output)

        except Exception as e:
            print(f"[{self.name}] Error calling '{func_name}': {e}")
            output = None

        return {"role": "tool", "tool_call_id": tool_call.id, "content": output}

    # A ROUGH TOKEN COUNTER:

    def _estimate_openai_tokens_from_messages(self, model: str, messages: list) -> int:
        """
        Rough token estimate for Chat Completions messages.
        """
        try:
            enc = tiktoken.encoding_for_model(model)
        except Exception:
            enc = tiktoken.get_encoding("cl100k_base")

        # Heuristic constants used for chat-format estimates
        tokens_per_message = 3
        tokens_per_name = 1

        total = 0
        for m in messages:
            total += tokens_per_message
            for k, v in m.items():
                if v is None:
                    continue
                text = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
                total += len(enc.encode(text))
                if k == "name":
                    total += tokens_per_name
        total += 3  # assistant priming
        return total

    def run(
        self, user_message: str, temperature: float = 0.03, reasoning_effort="medium"
    ) -> str:
        """
        Run the agent on a user message. Handles multi-turn tool calls automatically.
        All providers (OpenAI/Claude/Gemini/...) are reached via the NVIDIA proxy
        using the OpenAI-compatible chat.completions API.
        """
        print()
        print()
        self.messages.append({"role": "user", "content": user_message})

        # Rough count for tokens
        # est_in = self._estimate_openai_tokens_from_messages(self.model, self.messages)
        # print(f"[{self.name}] OPENAI est input tokens (full self.messages): {est_in}")

        while True:
            run = self.openai_client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                tools=self.tools,
                tool_choice="auto",
                # temperature=temperature,
                # reasoning={"effort": reasoning_effort},  # Default is "medium". "high" is in depth reasoning. "minimal" for shallow.
            )

            usage = getattr(run, "usage", None)
            if usage is not None:
                self.last_usage = {
                    "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                    "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
                    "total_tokens": getattr(usage, "total_tokens", 0) or 0,
                }

            # print(run)
            # print()

            msg = run.choices[0].message
            finish_reason = run.choices[0].finish_reason

            # If tool call needed based on the agent's decision
            if finish_reason == "tool_calls":  # Also msg.tool_calls works
                tool_calls = msg.tool_calls
                tool_outputs = map(
                    self._execute_tool_call_recommended_by_assistant_and_get_outputs,
                    tool_calls,
                )
                tool_outputs = list(tool_outputs)
                # print(tool_outputs)
                # print()
                # print()

                # Time for Second Pass with these results
                self.messages.append(msg)  # assistant’s function call
                self.messages.extend(tool_outputs)  # tool results
                continue  # loop again (model will now answer with final summary)
            else:  # Normal Query which doesn't need function call
                # print("Assistant:", msg.content)
                # break
                self.messages.append(msg)
                return msg.content

    # Just adding placeholders for integration for context engineering: Later, we can refine this to a structured JSON format to capture the most important gist only
    # To support local context → global compression.
    def summarize_context(self) -> str:
        """
        Return a compressed summary of this agent's conversation so far.
        Useful for passing to a global coordinator.
        """
        # Right now, just return the last assistant message
        return self.messages[-1]["content"] if self.messages else ""
