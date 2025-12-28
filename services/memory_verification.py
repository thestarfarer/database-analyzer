"""
Memory Verification Coordinator - SQL-based Memory Validation

This coordinator runs a verification agent (same LLM as main session) with SQL tool only
to validate memory items against database evidence.
"""

import json
import logging
import re
from typing import Dict, Any

from llm import LLMProviderFactory, LLMMessage, ToolDefinition
from tools.sql_tool import ExecuteSQLTool


class MemoryVerificationCoordinator:
    """Coordinator for memory verification using SQL-only agent."""

    def __init__(self, config, db_connection, session_execution):
        self.config = config
        self.db_connection = db_connection
        self.session_execution = session_execution
        self.logger = logging.getLogger(__name__)

    def verify_memory_item(self, session_state, category: str, key: str, value: str) -> Dict[str, Any]:
        """
        Run verification agent to validate memory item.

        Args:
            session_state: SessionState for full memory context
            category: Memory category (insights, patterns, etc.)
            key: Memory key identifier
            value: Current memory value to verify

        Returns:
            Dictionary with verification result
        """
        # Create SQL tool and wrap in ToolDefinition
        sql_tool = ExecuteSQLTool(self.db_connection, verbose=self.config.verbose_console_output)

        sql_tool_def = ToolDefinition(
            name=sql_tool.name,
            description=sql_tool.description,
            parameters=sql_tool.parameters,
            callable=sql_tool.call
        )

        # Create provider with SQL tool only
        provider = LLMProviderFactory.create(self.config, tools=[sql_tool_def])

        prompt = self.session_execution.build_verification_prompt(session_state, category, key, value)

        messages = [LLMMessage(role="user", content=prompt)]

        if self.config.verbose_console_output:
            print(f"\n{'='*60}")
            print(f"🔍 VERIFICATION AGENT RUNNING")
            print(f"{'='*60}\n")

        # Run provider with SQL tool
        final_response = None
        for response in provider.run(
            messages=messages,
            tools=[sql_tool_def],
            verbose=self.config.verbose_console_output
        ):
            if self.config.verbose_console_output and response.content:
                print(response.content)
            final_response = response

        response_text = final_response.content if final_response else ""

        if self.config.verbose_console_output:
            print(f"\n{'='*60}")
            print(f"📄 AGENT OUTPUT FOR JSON PARSING:")
            print(f"{'='*60}")
            print(response_text)
            print(f"{'='*60}\n")

        try:
            result = self._extract_json_from_response(response_text)
            return result
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse verification response: {e}")
            return {
                "verified": False,
                "confidence": "low",
                "evidence": "Could not parse agent response",
                "recommendation": "keep",
                "updated_value": None,
                "reasoning": "Verification agent did not return valid JSON"
            }

    def _extract_json_from_response(self, text: str) -> Dict[str, Any]:
        """Extract JSON object from agent response, handling think tags."""
        # Remove <think>...</think> blocks first
        clean_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)

        # Find JSON object
        start = clean_text.find('{')
        end = clean_text.rfind('}') + 1

        if start != -1 and end > start:
            json_str = clean_text[start:end]
            return json.loads(json_str)

        raise json.JSONDecodeError("No JSON found in response", text, 0)