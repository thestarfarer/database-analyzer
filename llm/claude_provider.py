"""
Claude API LLM Provider

Implements the LLMProvider interface using Anthropic's Claude API
with support for extended thinking and tool use.
"""

from typing import List, Dict, Any, Generator, Optional, TYPE_CHECKING

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    anthropic = None

from .provider import LLMProvider, LLMMessage, LLMResponse, ToolDefinition, ToolCall

if TYPE_CHECKING:
    from config.settings import ClaudeLLMConfig


class ClaudeProvider(LLMProvider):
    """
    LLM Provider implementation using Claude API.

    Handles tool execution loop and extended thinking.
    """

    def __init__(self, config: 'ClaudeLLMConfig', tools: Optional[List[ToolDefinition]] = None):
        """
        Initialize Claude provider.

        Args:
            config: ClaudeLLMConfig with API settings
            tools: List of tool definitions to register

        Raises:
            ImportError: If anthropic package is not installed
            ValueError: If API key is not provided
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError(
                "anthropic package not installed. "
                "Install with: pip install anthropic"
            )

        if not config.api_key:
            raise ValueError(
                "Claude API key required. "
                "Set ANTHROPIC_API_KEY environment variable."
            )

        self.config = config
        self.tools = tools or []
        self.client = anthropic.Anthropic(api_key=config.api_key)

        # Convert tools to Claude format
        self.claude_tools = self._convert_tools_to_claude_format(self.tools)

        # Build tool lookup for execution
        self._tool_lookup = {t.name: t for t in self.tools}

    @property
    def name(self) -> str:
        return "claude"

    def run(
        self,
        messages: List[LLMMessage],
        tools: List[ToolDefinition],
        verbose: bool = False
    ) -> Generator[LLMResponse, None, None]:
        """
        Execute LLM interaction with tools.

        Handles the Claude tool execution loop:
        1. Call API
        2. If stop_reason == "tool_use", execute tools and continue
        3. Repeat until stop_reason == "end_turn"
        """
        # Convert messages and tools
        claude_messages = self._convert_messages(messages)
        claude_tools = self._convert_tools_to_claude_format(tools)

        # Update tool lookup with provided tools
        tool_lookup = {t.name: t for t in tools}

        # Tool execution loop
        while True:
            # Build API call parameters
            params = {
                "model": self.config.model,
                "max_tokens": self.config.max_tokens,
                "messages": claude_messages,
            }

            # Add tools if available
            if claude_tools:
                params["tools"] = claude_tools

            # Add extended thinking if enabled
            if self.config.extended_thinking:
                params["temperature"] = 1  # Required for extended thinking
                params["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": self.config.thinking_budget_tokens
                }

            if verbose:
                print(f"🤖 Calling Claude API ({self.config.model})...")

            # Make API call
            response = self.client.messages.create(**params)

            # Extract content
            llm_response = self._convert_response(response)

            if response.stop_reason == "tool_use":
                if verbose:
                    print(f"🔧 Tool calls requested: {len(llm_response.tool_calls or [])}")

                # Execute tool calls
                tool_results = self._execute_tool_calls(
                    response.content,
                    tool_lookup,
                    verbose
                )

                # Add assistant response to conversation
                claude_messages.append({
                    "role": "assistant",
                    "content": response.content
                })

                # Add tool results
                claude_messages.append({
                    "role": "user",
                    "content": tool_results
                })

                # Yield intermediate response for logging
                yield llm_response

            else:
                # Done - yield final response
                if verbose:
                    print(f"✅ Claude response complete ({len(llm_response.content)} chars)")

                yield llm_response
                break

    def run_simple(
        self,
        messages: List[LLMMessage],
        verbose: bool = False
    ) -> LLMResponse:
        """Execute LLM interaction without tools."""
        claude_messages = self._convert_messages(messages)

        params = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": claude_messages,
        }

        # Add extended thinking if enabled
        if self.config.extended_thinking:
            params["temperature"] = 1
            params["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.config.thinking_budget_tokens
            }

        if verbose:
            print(f"🤖 Calling Claude API ({self.config.model})...")

        response = self.client.messages.create(**params)

        return self._convert_response(response)

    def _convert_messages(self, messages: List[LLMMessage]) -> List[Dict[str, Any]]:
        """Convert LLMMessage list to Claude message format."""
        claude_messages = []

        for msg in messages:
            claude_msg = {
                "role": msg.role if msg.role != "tool" else "user",
                "content": msg.content
            }

            # Handle tool results
            if msg.tool_results:
                claude_msg["content"] = msg.tool_results

            claude_messages.append(claude_msg)

        return claude_messages

    def _convert_tools_to_claude_format(self, tools: List[ToolDefinition]) -> List[Dict[str, Any]]:
        """Convert ToolDefinition list to Claude tool format."""
        claude_tools = []

        for tool in tools:
            # Build JSON Schema from parameters
            properties = {}
            required = []

            for param in tool.parameters:
                for param_name, desc in param.items():
                    properties[param_name] = {
                        "type": "string",
                        "description": desc
                    }
                    required.append(param_name)

            claude_tool = {
                "name": tool.name,
                "description": tool.description,
                "input_schema": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }

            claude_tools.append(claude_tool)

        return claude_tools

    def _execute_tool_calls(
        self,
        content_blocks: List,
        tool_lookup: Dict[str, ToolDefinition],
        verbose: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Execute tool calls from Claude response.

        Args:
            content_blocks: Response content blocks from Claude
            tool_lookup: Dictionary mapping tool names to ToolDefinition
            verbose: Whether to print progress

        Returns:
            List of tool result blocks for Claude
        """
        tool_results = []

        for block in content_blocks:
            if block.type == "tool_use":
                tool_name = block.name
                tool_input = block.input
                tool_use_id = block.id

                if verbose:
                    print(f"  🔧 Executing {tool_name}...")

                # Find and execute tool
                if tool_name in tool_lookup:
                    tool_def = tool_lookup[tool_name]
                    try:
                        # Execute tool with input arguments
                        result = tool_def.callable(**tool_input)

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": result
                        })

                        if verbose:
                            result_preview = result[:100] + "..." if len(result) > 100 else result
                            print(f"    ✅ Result: {result_preview}")

                    except Exception as e:
                        error_msg = f"Tool execution error: {str(e)}"
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": error_msg,
                            "is_error": True
                        })

                        if verbose:
                            print(f"    ❌ Error: {error_msg}")
                else:
                    error_msg = f"Unknown tool: {tool_name}"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": error_msg,
                        "is_error": True
                    })

                    if verbose:
                        print(f"    ❌ {error_msg}")

        return tool_results

    def _convert_response(self, response) -> LLMResponse:
        """Convert Claude API response to LLMResponse."""
        content_parts = []
        thinking_parts = []
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content_parts.append(block.text)
            elif block.type == "thinking":
                thinking_parts.append(block.thinking)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input
                ))

        return LLMResponse(
            content="\n".join(content_parts),
            thinking="\n\n".join(thinking_parts) if thinking_parts else None,
            tool_calls=tool_calls if tool_calls else None,
            stop_reason=response.stop_reason,
            raw_response=response
        )
