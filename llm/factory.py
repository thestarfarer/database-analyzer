"""
LLM Provider Factory

Creates appropriate LLM provider based on configuration.
"""

from typing import List, Optional, TYPE_CHECKING
import logging

from .provider import LLMProvider, ToolDefinition

if TYPE_CHECKING:
    from config.settings import AppConfig

logger = logging.getLogger(__name__)


class LLMProviderFactory:
    """Factory for creating LLM providers based on configuration."""

    @staticmethod
    def create(
        config: 'AppConfig',
        tools: Optional[List[ToolDefinition]] = None
    ) -> LLMProvider:
        """
        Create an LLM provider based on configuration.

        Args:
            config: AppConfig containing backend selection and provider configs
            tools: List of tool definitions to register with the provider

        Returns:
            LLMProvider instance (QwenAgentProvider or ClaudeProvider)

        Raises:
            ValueError: If unknown backend specified
            ImportError: If required package not available
        """
        backend = getattr(config, 'llm_backend', 'qwen')
        tools = tools or []

        logger.info(f"Creating LLM provider: {backend}")

        if backend == 'claude':
            from .claude_provider import ClaudeProvider
            from config.settings import ClaudeLLMConfig

            # Get Claude config from AppConfig or create from env
            claude_config = getattr(config, 'claude_config', None)
            if claude_config is None:
                claude_config = ClaudeLLMConfig.from_env()

            return ClaudeProvider(claude_config, tools)

        elif backend == 'qwen':
            from .qwen_provider import QwenAgentProvider

            return QwenAgentProvider(config.llm_config, tools)

        else:
            raise ValueError(
                f"Unknown LLM backend: {backend}. "
                f"Supported backends: 'qwen', 'claude'"
            )

    @staticmethod
    def get_available_backends() -> List[dict]:
        """
        Get list of available LLM backends.

        Returns:
            List of backend info dictionaries with 'id', 'name', 'available' keys
        """
        import os

        backends = [
            {
                'id': 'qwen',
                'name': 'Qwen (Local)',
                'available': True  # Always available if qwen-agent installed
            },
            {
                'id': 'claude',
                'name': 'Claude (Anthropic)',
                'available': bool(os.getenv('ANTHROPIC_API_KEY'))
            }
        ]

        return backends
