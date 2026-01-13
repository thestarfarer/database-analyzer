"""
Abstract LLM Provider Interface

Defines the contract that all LLM backends must implement, along with
backend-agnostic data structures for messages, tools, and responses.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Callable, Generator, Literal


@dataclass
class ToolDefinition:
    """Backend-agnostic tool definition."""
    name: str
    description: str
    parameters: List[Dict[str, str]]  # [{'param_name': 'description'}, ...]
    callable: Callable[..., str]


@dataclass
class ToolCall:
    """Represents a tool call request from the LLM."""
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class LLMMessage:
    """Backend-agnostic message format."""
    role: Literal['user', 'assistant', 'tool']
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    tool_results: Optional[List[Dict[str, Any]]] = None
    thinking: Optional[str] = None  # Extended thinking text (for display)
    thinking_blocks: Optional[List[Dict[str, Any]]] = None  # Raw thinking blocks with signatures (Claude API)


@dataclass
class LLMResponse:
    """Backend-agnostic response from LLM."""
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    thinking: Optional[str] = None  # Extended thinking text (for display)
    thinking_blocks: Optional[List[Dict[str, Any]]] = None  # Raw thinking blocks with signatures (Claude API)
    stop_reason: Optional[str] = None
    raw_response: Any = None  # Backend-specific response for debugging


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging/config."""
        pass

    @abstractmethod
    def run(
        self,
        messages: List[LLMMessage],
        tools: List[ToolDefinition],
        verbose: bool = False
    ) -> Generator[LLMResponse, None, None]:
        """
        Execute LLM interaction with tools.

        Args:
            messages: Conversation history
            tools: Available tools for the LLM to use
            verbose: Whether to print progress output

        Yields:
            LLMResponse objects (intermediate for tool calls, final for completion)
        """
        pass

    @abstractmethod
    def run_simple(
        self,
        messages: List[LLMMessage],
        verbose: bool = False
    ) -> LLMResponse:
        """
        Execute LLM interaction without tools (for reports, simple queries).

        Args:
            messages: Conversation history
            verbose: Whether to print progress output

        Returns:
            Final LLMResponse
        """
        pass
