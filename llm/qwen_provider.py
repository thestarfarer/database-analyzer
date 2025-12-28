"""
Qwen-Agent LLM Provider

Wraps the existing qwen-agent Assistant to implement the LLMProvider interface.
"""

from dataclasses import asdict
from typing import List, Generator, Optional
import re

from qwen_agent.agents import Assistant
from qwen_agent.llm.schema import Message
from qwen_agent.tools.base import BaseTool

from .provider import LLMProvider, LLMMessage, LLMResponse, ToolDefinition
from config.settings import LLMConfig


class DynamicQwenTool(BaseTool):
    """
    Dynamic BaseTool wrapper that delegates to a ToolDefinition callable.

    This allows us to wrap any tool function as a qwen-agent compatible tool.
    """

    def __init__(self, tool_def: ToolDefinition):
        # Set attributes BEFORE calling super().__init__() since BaseTool
        # accesses the name property during initialization
        self._name = tool_def.name
        self._description = tool_def.description
        self._parameters = tool_def.parameters
        self._callable = tool_def.callable
        super().__init__()

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> List:
        return self._parameters

    def call(self, *args, **kwargs) -> str:
        """Execute the wrapped tool callable."""
        return self._callable(*args, **kwargs)


class QwenAgentProvider(LLMProvider):
    """
    LLM Provider implementation using qwen-agent.

    Wraps the existing qwen-agent Assistant to provide a unified interface.
    """

    def __init__(self, config: LLMConfig, tools: Optional[List[ToolDefinition]] = None):
        """
        Initialize Qwen provider.

        Args:
            config: LLMConfig with model settings
            tools: List of tool definitions to register
        """
        self.config = config
        self.tools = tools or []

        # Convert tools to qwen-agent format
        self.qwen_tools = [DynamicQwenTool(t) for t in self.tools]

        # Initialize Assistant
        self.assistant = Assistant(
            llm=asdict(config),
            function_list=self.qwen_tools if self.qwen_tools else None
        )

    @property
    def name(self) -> str:
        return "qwen"

    def run(
        self,
        messages: List[LLMMessage],
        tools: List[ToolDefinition],
        verbose: bool = False
    ) -> Generator[LLMResponse, None, None]:
        """
        Execute LLM interaction with tools.

        Note: qwen-agent handles the tool execution loop internally.
        We just need to convert messages and yield responses.
        """
        # Convert messages to qwen-agent format
        qwen_messages = self._convert_messages(messages)

        # Stream responses
        responses = None
        for response in self.assistant.run(messages=qwen_messages):
            if verbose and hasattr(response, 'content'):
                if response.content and response.content.strip():
                    if any(kw in response.content.lower() for kw in ['execute_sql', 'memory', 'tool']):
                        print(f"🔧 Tool executing... ", end='', flush=True)
                    elif len(response.content) < 200:
                        print(f"💭 {response.content[:100]}...")

            responses = response

        # Extract final response
        yield self._convert_response(responses)

    def run_simple(
        self,
        messages: List[LLMMessage],
        verbose: bool = False
    ) -> LLMResponse:
        """Execute LLM interaction without tools."""
        # Create a simple assistant without tools
        simple_assistant = Assistant(
            llm=asdict(self.config),
            function_list=None
        )

        qwen_messages = self._convert_messages(messages)

        responses = None
        for response in simple_assistant.run(messages=qwen_messages):
            responses = response

        return self._convert_response(responses)

    def _convert_messages(self, messages: List[LLMMessage]) -> List[Message]:
        """Convert LLMMessage list to qwen-agent Message list."""
        return [
            Message(role=msg.role, content=msg.content)
            for msg in messages
        ]

    def _convert_response(self, response) -> LLMResponse:
        """Convert qwen-agent response to LLMResponse."""
        if response is None:
            return LLMResponse(content="No response received", raw_response=None)

        # Handle list response (multiple messages)
        if isinstance(response, list):
            content = response[-1].content if response else ""
        else:
            content = response.content if hasattr(response, 'content') else str(response)

        # Extract thinking content if present
        thinking = None
        clean_content = content
        if content:
            think_match = re.search(r'<think>(.*?)</think>', content, re.DOTALL)
            if think_match:
                thinking = think_match.group(1).strip()
                clean_content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

        return LLMResponse(
            content=clean_content,
            thinking=thinking,
            raw_response=response
        )
