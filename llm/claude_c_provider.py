"""
Claude-C Subprocess LLM Provider

Implements the LLMProvider interface using the claude-c binary via subprocess.
Uses JSON file input for requests and JSON output for responses.
"""

import json
import subprocess
import tempfile
import os
import shutil
import logging
from typing import List, Dict, Any, Generator, Optional, TYPE_CHECKING
from pathlib import Path

from .provider import LLMProvider, LLMMessage, LLMResponse, ToolDefinition, ToolCall

if TYPE_CHECKING:
    from config.settings import ClaudeCLLMConfig

logger = logging.getLogger(__name__)


class ClaudeCProvider(LLMProvider):
    """
    LLM Provider using claude-c subprocess.

    Communicates with Claude API via the claude-c binary, passing
    full request JSON via file and parsing JSON response output.
    """

    def __init__(self, config: 'ClaudeCLLMConfig', tools: Optional[List[ToolDefinition]] = None):
        """
        Initialize Claude-C provider.

        Args:
            config: ClaudeCLLMConfig with binary path and settings
            tools: List of tool definitions to register

        Raises:
            FileNotFoundError: If claude-c binary not found
        """
        self.config = config
        self.tools = tools or []

        # Verify binary exists
        self._binary_path = self._find_binary()
        if not self._binary_path:
            raise FileNotFoundError(
                f"claude-c binary not found at: {self.config.binary_path}. "
                "Set CLAUDEC_PATH environment variable or install claude-c to PATH."
            )

        # Build tool lookup for execution
        self._tool_lookup = {t.name: t for t in self.tools}

        logger.info(f"ClaudeCProvider initialized with binary: {self._binary_path}")

    @property
    def name(self) -> str:
        return "claude-c"

    def _find_binary(self) -> Optional[str]:
        """Find the claude-c binary path."""
        binary_path = self.config.binary_path

        # Check if it's an absolute or relative path that exists
        if os.path.isfile(binary_path) and os.access(binary_path, os.X_OK):
            return os.path.abspath(binary_path)

        # Try finding in PATH
        found = shutil.which(binary_path)
        if found:
            return found

        return None

    def _build_request_json(
        self,
        messages: List[LLMMessage],
        tools: List[ToolDefinition],
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build complete API request JSON.

        Note: Identity string and metadata are injected by claude-c.
        """
        request = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "stream": False,
            "messages": self._convert_messages(messages)
        }

        # Add system prompt if provided
        if system_prompt:
            request["system"] = [
                {"type": "text", "text": system_prompt}
            ]

        # Add tools if available
        if tools:
            request["tools"] = self._convert_tools(tools)

        # Add extended thinking if enabled
        if self.config.extended_thinking:
            request["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.config.thinking_budget_tokens
            }

        return request

    def _convert_messages(self, messages: List[LLMMessage]) -> List[Dict[str, Any]]:
        """Convert LLMMessage list to Claude API format."""
        result = []
        for msg in messages:
            claude_msg: Dict[str, Any] = {"role": msg.role if msg.role != "tool" else "user"}

            if msg.tool_results:
                claude_msg["content"] = msg.tool_results
            elif msg.tool_calls:
                # Convert tool calls to content blocks
                content = []
                if msg.content:
                    content.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    content.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments
                    })
                claude_msg["content"] = content
            else:
                claude_msg["content"] = msg.content

            result.append(claude_msg)
        return result

    def _convert_tools(self, tools: List[ToolDefinition]) -> List[Dict[str, Any]]:
        """Convert ToolDefinition list to Claude tool format."""
        result = []
        for tool in tools:
            properties = {}
            required = []

            for param in tool.parameters:
                for param_name, desc in param.items():
                    properties[param_name] = {
                        "type": "string",
                        "description": desc
                    }
                    required.append(param_name)

            result.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            })
        return result

    def _call_claude_c(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call claude-c binary with request JSON.

        Returns parsed response JSON.
        Raises RuntimeError on failure.
        """
        # Write request to temp file
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False, encoding='utf-8'
        ) as f:
            json.dump(request, f, ensure_ascii=False)
            request_file = f.name

        try:
            cmd = [
                self._binary_path,
                '-p',  # Print mode (required)
                '-r', f'@{request_file}',  # Request from file
                '-J'  # JSON output
            ]

            logger.debug(f"Calling claude-c: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout_seconds,
                env={**os.environ}  # Inherit environment for OAuth
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else f"claude-c exited with code {result.returncode}"
                raise RuntimeError(f"claude-c error: {error_msg}")

            # Parse JSON response
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse claude-c output: {result.stdout[:500]}")
                raise RuntimeError(f"Invalid JSON from claude-c: {e}")

        except subprocess.TimeoutExpired:
            raise RuntimeError(f"claude-c timed out after {self.config.timeout_seconds} seconds")

        finally:
            try:
                os.unlink(request_file)
            except OSError:
                pass

    def _parse_response(self, response: Dict[str, Any]) -> LLMResponse:
        """Parse Claude API response into LLMResponse."""
        content_parts = []
        thinking_parts = []
        tool_calls = []

        for block in response.get("content", []):
            block_type = block.get("type")

            if block_type == "text":
                content_parts.append(block.get("text", ""))
            elif block_type == "thinking":
                thinking_parts.append(block.get("thinking", ""))
            elif block_type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.get("id", ""),
                    name=block.get("name", ""),
                    arguments=block.get("input", {})
                ))

        return LLMResponse(
            content="\n".join(content_parts),
            thinking="\n\n".join(thinking_parts) if thinking_parts else None,
            tool_calls=tool_calls if tool_calls else None,
            stop_reason=response.get("stop_reason"),
            raw_response=response
        )

    def _execute_tool_calls(
        self,
        tool_calls: List[ToolCall],
        tool_lookup: Dict[str, ToolDefinition],
        verbose: bool = False
    ) -> List[Dict[str, Any]]:
        """Execute tool calls and return results in Claude format."""
        results = []

        for tc in tool_calls:
            if verbose:
                print(f"  🔧 Executing {tc.name}...")

            if tc.name in tool_lookup:
                tool_def = tool_lookup[tc.name]
                try:
                    result = tool_def.callable(**tc.arguments)
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": result
                    })
                    if verbose:
                        preview = result[:100] + "..." if len(result) > 100 else result
                        print(f"    ✅ Result: {preview}")
                except Exception as e:
                    error_msg = f"Tool execution error: {str(e)}"
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": error_msg,
                        "is_error": True
                    })
                    if verbose:
                        print(f"    ❌ Error: {error_msg}")
            else:
                error_msg = f"Unknown tool: {tc.name}"
                results.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": error_msg,
                    "is_error": True
                })
                if verbose:
                    print(f"    ❌ {error_msg}")

        return results

    def run(
        self,
        messages: List[LLMMessage],
        tools: List[ToolDefinition],
        verbose: bool = False
    ) -> Generator[LLMResponse, None, None]:
        """
        Execute LLM interaction with tools.

        Implements tool execution loop similar to ClaudeProvider.
        """
        tool_lookup = {t.name: t for t in tools}
        current_messages = list(messages)

        while True:
            # Build and send request
            request = self._build_request_json(current_messages, tools)

            if verbose:
                print(f"🤖 Calling claude-c ({self.config.model})...")

            response_json = self._call_claude_c(request)
            llm_response = self._parse_response(response_json)

            if response_json.get("stop_reason") == "tool_use":
                if verbose:
                    print(f"🔧 Tool calls requested: {len(llm_response.tool_calls or [])}")

                # Execute tools
                tool_results = self._execute_tool_calls(
                    llm_response.tool_calls or [],
                    tool_lookup,
                    verbose
                )

                # Add assistant response to conversation
                current_messages.append(LLMMessage(
                    role="assistant",
                    content=llm_response.content,
                    tool_calls=llm_response.tool_calls
                ))

                # Add tool results
                current_messages.append(LLMMessage(
                    role="user",
                    content="",
                    tool_results=tool_results
                ))

                yield llm_response
            else:
                if verbose:
                    print(f"✅ Claude-c response complete ({len(llm_response.content)} chars)")
                yield llm_response
                break

    def run_simple(
        self,
        messages: List[LLMMessage],
        verbose: bool = False
    ) -> LLMResponse:
        """Execute LLM interaction without tools."""
        request = self._build_request_json(messages, [])

        if verbose:
            print(f"🤖 Calling claude-c ({self.config.model})...")

        response_json = self._call_claude_c(request)
        return self._parse_response(response_json)
