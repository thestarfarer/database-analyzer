"""
Unit Tests for LLM Provider System

Tests for the LLM provider abstraction including QwenAgentProvider,
ClaudeProvider, and LLMProviderFactory.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from llm import (
    LLMProvider, LLMMessage, LLMResponse, ToolDefinition, ToolCall,
    LLMProviderFactory, QwenAgentProvider, ClaudeProvider
)
from config.settings import AppConfig, DatabaseConfig, LLMConfig, ClaudeLLMConfig


# ============================================================================
# Data Classes Tests
# ============================================================================

@pytest.mark.unit
class TestDataClasses:
    """Tests for LLM data classes."""

    def test_tool_definition_creation(self):
        """Test creating a ToolDefinition."""
        def my_func(query: str) -> str:
            return f"Result: {query}"

        tool_def = ToolDefinition(
            name="my_tool",
            description="Does something",
            parameters=[{"query": "The query string"}],
            callable=my_func
        )

        assert tool_def.name == "my_tool"
        assert tool_def.description == "Does something"
        assert len(tool_def.parameters) == 1
        assert tool_def.callable("test") == "Result: test"

    def test_llm_message_creation(self):
        """Test creating an LLMMessage."""
        msg = LLMMessage(
            role="user",
            content="Hello world"
        )

        assert msg.role == "user"
        assert msg.content == "Hello world"
        assert msg.tool_calls is None

    def test_llm_message_with_tool_calls(self):
        """Test LLMMessage with tool calls."""
        tool_call = ToolCall(
            id="tc_1",
            name="execute_sql",
            arguments={"query": "SELECT * FROM entities"}
        )
        msg = LLMMessage(
            role="assistant",
            content="Let me query the database",
            tool_calls=[tool_call]
        )

        assert msg.role == "assistant"
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].name == "execute_sql"

    def test_llm_response_creation(self):
        """Test creating an LLMResponse."""
        response = LLMResponse(
            content="Analysis complete",
            thinking="I analyzed the data carefully",
            stop_reason="end_turn"
        )

        assert response.content == "Analysis complete"
        assert response.thinking == "I analyzed the data carefully"
        assert response.stop_reason == "end_turn"
        assert response.tool_calls is None

    def test_llm_response_with_tool_calls(self):
        """Test LLMResponse with tool calls."""
        tool_call = ToolCall(id="tc_1", name="memory", arguments={"action": "update"})
        response = LLMResponse(
            content="",
            tool_calls=[tool_call],
            stop_reason="tool_use"
        )

        assert len(response.tool_calls) == 1
        assert response.stop_reason == "tool_use"

    def test_tool_call_creation(self):
        """Test creating a ToolCall."""
        tc = ToolCall(
            id="call_123",
            name="execute_sql",
            arguments={"query": "SELECT 1"}
        )

        assert tc.id == "call_123"
        assert tc.name == "execute_sql"
        assert tc.arguments == {"query": "SELECT 1"}


# ============================================================================
# LLMProviderFactory Tests
# ============================================================================

@pytest.mark.unit
class TestLLMProviderFactory:
    """Tests for LLMProviderFactory."""

    @patch('llm.qwen_provider.Assistant')
    def test_create_qwen_provider(self, mock_assistant, app_config):
        """Test creating Qwen provider via factory."""
        app_config.llm_backend = 'qwen'

        tools = []
        result = LLMProviderFactory.create(app_config, tools)

        assert result.name == "qwen"
        mock_assistant.assert_called_once()

    @patch('llm.claude_provider.anthropic')
    @patch('llm.claude_provider.ANTHROPIC_AVAILABLE', True)
    def test_create_claude_provider(self, mock_anthropic, app_config):
        """Test creating Claude provider via factory."""
        app_config.llm_backend = 'claude'
        app_config.claude_config = ClaudeLLMConfig(api_key='test-key')

        tools = []
        result = LLMProviderFactory.create(app_config, tools)

        assert result.name == "claude"
        mock_anthropic.Anthropic.assert_called_once()

    def test_create_unknown_backend_raises_error(self, app_config):
        """Test that unknown backend raises ValueError."""
        app_config.llm_backend = 'unknown'

        with pytest.raises(ValueError) as exc_info:
            LLMProviderFactory.create(app_config, [])

        assert "Unknown LLM backend: unknown" in str(exc_info.value)

    def test_get_available_backends(self):
        """Test getting available backends."""
        backends = LLMProviderFactory.get_available_backends()

        assert isinstance(backends, list)
        assert len(backends) >= 2  # At least qwen and claude

        backend_ids = [b['id'] for b in backends]
        assert 'qwen' in backend_ids
        assert 'claude' in backend_ids

        for backend in backends:
            assert 'id' in backend
            assert 'name' in backend
            assert 'available' in backend

    def test_qwen_backend_always_available(self):
        """Test that Qwen backend is always marked available."""
        backends = LLMProviderFactory.get_available_backends()
        qwen = next(b for b in backends if b['id'] == 'qwen')
        assert qwen['available'] == True


# ============================================================================
# QwenAgentProvider Tests
# ============================================================================

@pytest.mark.unit
class TestQwenAgentProvider:
    """Tests for QwenAgentProvider."""

    @patch('llm.qwen_provider.Assistant')
    def test_provider_creation(self, mock_assistant_class):
        """Test creating QwenAgentProvider."""
        llm_config = LLMConfig.default()
        tools = []

        provider = QwenAgentProvider(llm_config, tools)

        assert provider.name == "qwen"
        mock_assistant_class.assert_called_once()

    @patch('llm.qwen_provider.Assistant')
    def test_provider_with_tools(self, mock_assistant_class):
        """Test QwenAgentProvider with tool definitions."""
        llm_config = LLMConfig.default()

        def sql_func(query: str) -> str:
            return "results"

        tools = [
            ToolDefinition(
                name="execute_sql",
                description="Execute SQL",
                parameters=[{"query": "SQL query"}],
                callable=sql_func
            )
        ]

        provider = QwenAgentProvider(llm_config, tools)

        # Verify Assistant was called with function_list
        call_kwargs = mock_assistant_class.call_args[1]
        assert 'function_list' in call_kwargs
        assert len(call_kwargs['function_list']) == 1

    @patch('llm.qwen_provider.Assistant')
    def test_run_simple(self, mock_assistant_class):
        """Test run_simple method."""
        llm_config = LLMConfig.default()

        # Mock assistant response
        mock_response = Mock()
        mock_response.content = "Analysis result"
        mock_assistant = Mock()
        mock_assistant.run.return_value = iter([mock_response])
        mock_assistant_class.return_value = mock_assistant

        provider = QwenAgentProvider(llm_config, [])

        messages = [LLMMessage(role="user", content="Analyze this")]
        result = provider.run_simple(messages)

        assert result.content == "Analysis result"

    @patch('llm.qwen_provider.Assistant')
    def test_run_with_tools(self, mock_assistant_class):
        """Test run method with tools."""
        llm_config = LLMConfig.default()

        mock_response = Mock()
        mock_response.content = "Query executed"
        mock_assistant = Mock()
        mock_assistant.run.return_value = iter([mock_response])
        mock_assistant_class.return_value = mock_assistant

        provider = QwenAgentProvider(llm_config, [])

        messages = [LLMMessage(role="user", content="Run query")]
        responses = list(provider.run(messages, [], verbose=False))

        assert len(responses) == 1
        assert responses[0].content == "Query executed"


# ============================================================================
# ClaudeProvider Tests
# ============================================================================

@pytest.mark.unit
class TestClaudeProvider:
    """Tests for ClaudeProvider."""

    @patch('llm.claude_provider.anthropic')
    @patch('llm.claude_provider.ANTHROPIC_AVAILABLE', True)
    def test_provider_creation(self, mock_anthropic):
        """Test creating ClaudeProvider."""
        config = ClaudeLLMConfig(api_key='test-key')
        tools = []

        provider = ClaudeProvider(config, tools)

        assert provider.name == "claude"
        mock_anthropic.Anthropic.assert_called_once_with(api_key='test-key')

    @patch('llm.claude_provider.ANTHROPIC_AVAILABLE', False)
    def test_provider_creation_without_anthropic(self):
        """Test that ClaudeProvider raises error when anthropic not installed."""
        config = ClaudeLLMConfig(api_key='test-key')

        with pytest.raises(ImportError) as exc_info:
            ClaudeProvider(config, [])

        assert "anthropic package not installed" in str(exc_info.value)

    @patch('llm.claude_provider.anthropic')
    @patch('llm.claude_provider.ANTHROPIC_AVAILABLE', True)
    def test_provider_requires_api_key(self, mock_anthropic):
        """Test that ClaudeProvider requires API key."""
        config = ClaudeLLMConfig(api_key='')

        with pytest.raises(ValueError) as exc_info:
            ClaudeProvider(config, [])

        assert "API key required" in str(exc_info.value)

    @patch('llm.claude_provider.anthropic')
    @patch('llm.claude_provider.ANTHROPIC_AVAILABLE', True)
    def test_run_simple(self, mock_anthropic):
        """Test run_simple method."""
        config = ClaudeLLMConfig(
            api_key='test-key',
            extended_thinking=False  # Disable for simpler test
        )

        # Mock API response
        mock_text_block = Mock()
        mock_text_block.type = "text"
        mock_text_block.text = "Analysis complete"

        mock_response = Mock()
        mock_response.content = [mock_text_block]
        mock_response.stop_reason = "end_turn"

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client

        provider = ClaudeProvider(config, [])

        messages = [LLMMessage(role="user", content="Analyze this")]
        result = provider.run_simple(messages)

        assert result.content == "Analysis complete"
        mock_client.messages.create.assert_called_once()

    @patch('llm.claude_provider.anthropic')
    @patch('llm.claude_provider.ANTHROPIC_AVAILABLE', True)
    def test_run_with_tool_use(self, mock_anthropic):
        """Test run method with tool use loop."""
        config = ClaudeLLMConfig(
            api_key='test-key',
            extended_thinking=False
        )

        def sql_func(query: str) -> str:
            return "Record1, Record2"

        tools = [
            ToolDefinition(
                name="execute_sql",
                description="Execute SQL",
                parameters=[{"query": "SQL query"}],
                callable=sql_func
            )
        ]

        # First response: tool_use
        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "execute_sql"
        mock_tool_block.input = {"query": "SELECT * FROM entities"}
        mock_tool_block.id = "tool_1"

        mock_first_response = Mock()
        mock_first_response.content = [mock_tool_block]
        mock_first_response.stop_reason = "tool_use"

        # Second response: end_turn
        mock_text_block = Mock()
        mock_text_block.type = "text"
        mock_text_block.text = "Found 2 records"

        mock_second_response = Mock()
        mock_second_response.content = [mock_text_block]
        mock_second_response.stop_reason = "end_turn"

        mock_client = Mock()
        mock_client.messages.create.side_effect = [mock_first_response, mock_second_response]
        mock_anthropic.Anthropic.return_value = mock_client

        provider = ClaudeProvider(config, tools)

        messages = [LLMMessage(role="user", content="List all records")]
        responses = list(provider.run(messages, tools, verbose=False))

        # Should have two responses: one for tool_use, one for end_turn
        assert len(responses) == 2
        assert responses[0].stop_reason == "tool_use"
        assert responses[1].content == "Found 2 records"
        assert mock_client.messages.create.call_count == 2

    @patch('llm.claude_provider.anthropic')
    @patch('llm.claude_provider.ANTHROPIC_AVAILABLE', True)
    def test_convert_tools_to_claude_format(self, mock_anthropic):
        """Test tool conversion to Claude format."""
        config = ClaudeLLMConfig(api_key='test-key')

        tools = [
            ToolDefinition(
                name="execute_sql",
                description="Execute a SQL query",
                parameters=[{"query": "The SQL query to run"}],
                callable=lambda q: "results"
            )
        ]

        provider = ClaudeProvider(config, tools)

        # Check converted tools
        assert len(provider.claude_tools) == 1
        claude_tool = provider.claude_tools[0]
        assert claude_tool['name'] == "execute_sql"
        assert claude_tool['description'] == "Execute a SQL query"
        assert 'input_schema' in claude_tool
        assert claude_tool['input_schema']['type'] == 'object'
        assert 'query' in claude_tool['input_schema']['properties']

    @patch('llm.claude_provider.anthropic')
    @patch('llm.claude_provider.ANTHROPIC_AVAILABLE', True)
    def test_extended_thinking_params(self, mock_anthropic):
        """Test that extended thinking parameters are set correctly."""
        config = ClaudeLLMConfig(
            api_key='test-key',
            extended_thinking=True,
            thinking_budget_tokens=5000
        )

        mock_text_block = Mock()
        mock_text_block.type = "text"
        mock_text_block.text = "Result"

        mock_response = Mock()
        mock_response.content = [mock_text_block]
        mock_response.stop_reason = "end_turn"

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client

        provider = ClaudeProvider(config, [])

        messages = [LLMMessage(role="user", content="Think about this")]
        provider.run_simple(messages)

        # Check that thinking params were passed
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs['temperature'] == 1  # Required for thinking
        assert 'thinking' in call_kwargs
        assert call_kwargs['thinking']['type'] == 'enabled'
        assert call_kwargs['thinking']['budget_tokens'] == 5000

    @patch('llm.claude_provider.anthropic')
    @patch('llm.claude_provider.ANTHROPIC_AVAILABLE', True)
    def test_response_with_thinking_block(self, mock_anthropic):
        """Test handling response with thinking block."""
        config = ClaudeLLMConfig(
            api_key='test-key',
            extended_thinking=True
        )

        # Response with thinking block
        mock_thinking_block = Mock()
        mock_thinking_block.type = "thinking"
        mock_thinking_block.thinking = "Let me analyze this step by step..."

        mock_text_block = Mock()
        mock_text_block.type = "text"
        mock_text_block.text = "The answer is 42"

        mock_response = Mock()
        mock_response.content = [mock_thinking_block, mock_text_block]
        mock_response.stop_reason = "end_turn"

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client

        provider = ClaudeProvider(config, [])

        messages = [LLMMessage(role="user", content="What is the answer?")]
        result = provider.run_simple(messages)

        assert result.content == "The answer is 42"
        assert result.thinking == "Let me analyze this step by step..."


# ============================================================================
# ClaudeProvider Error Path Tests
# ============================================================================

@pytest.mark.unit
class TestClaudeProviderErrorPaths:
    """Tests for ClaudeProvider error handling paths."""

    @patch('llm.claude_provider.anthropic')
    @patch('llm.claude_provider.ANTHROPIC_AVAILABLE', True)
    def test_execute_tool_calls_unknown_tool(self, mock_anthropic):
        """Test _execute_tool_calls with unknown tool name."""
        config = ClaudeLLMConfig(api_key='test-key')
        provider = ClaudeProvider(config, [])

        # Mock a tool_use block with unknown tool
        mock_block = Mock()
        mock_block.type = "tool_use"
        mock_block.name = "unknown_tool"
        mock_block.input = {"param": "value"}
        mock_block.id = "tool_123"

        content_blocks = [mock_block]
        tool_lookup = {}  # Empty - tool not registered

        results = provider._execute_tool_calls(content_blocks, tool_lookup, verbose=False)

        assert len(results) == 1
        assert results[0]['is_error'] is True
        assert "Unknown tool: unknown_tool" in results[0]['content']

    @patch('llm.claude_provider.anthropic')
    @patch('llm.claude_provider.ANTHROPIC_AVAILABLE', True)
    def test_execute_tool_calls_tool_exception(self, mock_anthropic):
        """Test _execute_tool_calls when tool raises exception."""
        config = ClaudeLLMConfig(api_key='test-key')

        def failing_tool(query: str) -> str:
            raise ValueError("Database connection failed")

        tools = [
            ToolDefinition(
                name="execute_sql",
                description="Execute SQL",
                parameters=[{"query": "SQL query"}],
                callable=failing_tool
            )
        ]

        provider = ClaudeProvider(config, tools)

        # Mock a tool_use block
        mock_block = Mock()
        mock_block.type = "tool_use"
        mock_block.name = "execute_sql"
        mock_block.input = {"query": "SELECT 1"}
        mock_block.id = "tool_456"

        content_blocks = [mock_block]
        tool_lookup = {"execute_sql": tools[0]}

        results = provider._execute_tool_calls(content_blocks, tool_lookup, verbose=False)

        assert len(results) == 1
        assert results[0]['is_error'] is True
        assert "Database connection failed" in results[0]['content']

    @patch('llm.claude_provider.anthropic')
    @patch('llm.claude_provider.ANTHROPIC_AVAILABLE', True)
    def test_execute_tool_calls_verbose_output(self, mock_anthropic, capsys):
        """Test _execute_tool_calls with verbose output."""
        config = ClaudeLLMConfig(api_key='test-key')

        def working_tool(query: str) -> str:
            return "Results: Record1, Record2"

        tools = [
            ToolDefinition(
                name="execute_sql",
                description="Execute SQL",
                parameters=[{"query": "SQL query"}],
                callable=working_tool
            )
        ]

        provider = ClaudeProvider(config, tools)

        mock_block = Mock()
        mock_block.type = "tool_use"
        mock_block.name = "execute_sql"
        mock_block.input = {"query": "SELECT * FROM entities"}
        mock_block.id = "tool_789"

        content_blocks = [mock_block]
        tool_lookup = {"execute_sql": tools[0]}

        results = provider._execute_tool_calls(content_blocks, tool_lookup, verbose=True)

        captured = capsys.readouterr()
        assert "Executing execute_sql" in captured.out
        assert "Result" in captured.out

    @patch('llm.claude_provider.anthropic')
    @patch('llm.claude_provider.ANTHROPIC_AVAILABLE', True)
    def test_run_with_empty_tools_list(self, mock_anthropic):
        """Test run method with empty tools list."""
        config = ClaudeLLMConfig(api_key='test-key', extended_thinking=False)

        mock_text_block = Mock()
        mock_text_block.type = "text"
        mock_text_block.text = "Simple response"

        mock_response = Mock()
        mock_response.content = [mock_text_block]
        mock_response.stop_reason = "end_turn"

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client

        provider = ClaudeProvider(config, [])

        messages = [LLMMessage(role="user", content="Hello")]
        responses = list(provider.run(messages, [], verbose=False))

        assert len(responses) == 1
        assert responses[0].content == "Simple response"

    @patch('llm.claude_provider.anthropic')
    @patch('llm.claude_provider.ANTHROPIC_AVAILABLE', True)
    def test_convert_response_empty_content(self, mock_anthropic):
        """Test _convert_response with empty content blocks."""
        config = ClaudeLLMConfig(api_key='test-key')
        provider = ClaudeProvider(config, [])

        mock_response = Mock()
        mock_response.content = []
        mock_response.stop_reason = "end_turn"

        result = provider._convert_response(mock_response)

        assert result.content == ""
        assert result.thinking is None
        assert result.tool_calls is None

    @patch('llm.claude_provider.anthropic')
    @patch('llm.claude_provider.ANTHROPIC_AVAILABLE', True)
    def test_run_verbose_output(self, mock_anthropic, capsys):
        """Test run method with verbose output."""
        config = ClaudeLLMConfig(api_key='test-key', extended_thinking=False)

        mock_text_block = Mock()
        mock_text_block.type = "text"
        mock_text_block.text = "Verbose test response"

        mock_response = Mock()
        mock_response.content = [mock_text_block]
        mock_response.stop_reason = "end_turn"

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client

        provider = ClaudeProvider(config, [])

        messages = [LLMMessage(role="user", content="Test")]
        list(provider.run(messages, [], verbose=True))

        captured = capsys.readouterr()
        assert "Calling Claude API" in captured.out
        assert "response complete" in captured.out


# ============================================================================
# QwenAgentProvider Error Path Tests
# ============================================================================

@pytest.mark.unit
class TestQwenProviderErrorPaths:
    """Tests for QwenAgentProvider error handling paths."""

    @patch('llm.qwen_provider.Assistant')
    def test_convert_response_with_none(self, mock_assistant_class):
        """Test _convert_response with None response."""
        llm_config = LLMConfig.default()
        provider = QwenAgentProvider(llm_config, [])

        result = provider._convert_response(None)

        assert result.content == "No response received"
        assert result.raw_response is None

    @patch('llm.qwen_provider.Assistant')
    def test_convert_response_with_list(self, mock_assistant_class):
        """Test _convert_response with list of responses."""
        llm_config = LLMConfig.default()
        provider = QwenAgentProvider(llm_config, [])

        # Mock a list of responses
        mock_msg1 = Mock()
        mock_msg1.content = "First message"
        mock_msg2 = Mock()
        mock_msg2.content = "Final message"

        result = provider._convert_response([mock_msg1, mock_msg2])

        # Should use last message content
        assert result.content == "Final message"

    @patch('llm.qwen_provider.Assistant')
    def test_convert_response_with_think_tags(self, mock_assistant_class):
        """Test _convert_response strips think tags."""
        llm_config = LLMConfig.default()
        provider = QwenAgentProvider(llm_config, [])

        mock_response = Mock()
        mock_response.content = "<think>Let me think about this...</think>The answer is 42"

        result = provider._convert_response(mock_response)

        assert result.thinking == "Let me think about this..."
        assert result.content == "The answer is 42"
        assert "<think>" not in result.content

    @patch('llm.qwen_provider.Assistant')
    def test_run_verbose_with_tool_keywords(self, mock_assistant_class, capsys):
        """Test run method verbose output with tool keywords."""
        llm_config = LLMConfig.default()

        mock_response = Mock()
        mock_response.content = "Calling execute_sql to query the database"

        mock_assistant = Mock()
        mock_assistant.run.return_value = iter([mock_response])
        mock_assistant_class.return_value = mock_assistant

        provider = QwenAgentProvider(llm_config, [])

        messages = [LLMMessage(role="user", content="Run query")]
        list(provider.run(messages, [], verbose=True))

        captured = capsys.readouterr()
        assert "Tool executing" in captured.out

    @patch('llm.qwen_provider.Assistant')
    def test_run_verbose_with_short_content(self, mock_assistant_class, capsys):
        """Test run method verbose output with short content."""
        llm_config = LLMConfig.default()

        mock_response = Mock()
        # Use content that doesn't contain trigger keywords (execute_sql, memory, tool)
        mock_response.content = "Brief analysis result"

        mock_assistant = Mock()
        mock_assistant.run.return_value = iter([mock_response])
        mock_assistant_class.return_value = mock_assistant

        provider = QwenAgentProvider(llm_config, [])

        messages = [LLMMessage(role="user", content="Hello")]
        list(provider.run(messages, [], verbose=True))

        captured = capsys.readouterr()
        # Short content should be printed with thinking emoji
        assert "Brief analysis" in captured.out


# ============================================================================
# DynamicQwenTool Tests
# ============================================================================

@pytest.mark.unit
class TestDynamicQwenTool:
    """Tests for DynamicQwenTool wrapper class."""

    def test_tool_properties(self):
        """Test DynamicQwenTool exposes correct properties."""
        from llm.qwen_provider import DynamicQwenTool

        def my_tool(param1: str) -> str:
            return f"Result: {param1}"

        tool_def = ToolDefinition(
            name="test_tool",
            description="Test tool description",
            parameters=[{"param1": "First parameter"}],
            callable=my_tool
        )

        qwen_tool = DynamicQwenTool(tool_def)

        assert qwen_tool.name == "test_tool"
        assert qwen_tool.description == "Test tool description"
        assert qwen_tool.parameters == [{"param1": "First parameter"}]

    def test_tool_call_executes_callable(self):
        """Test DynamicQwenTool.call() executes the wrapped callable."""
        from llm.qwen_provider import DynamicQwenTool

        def sql_tool(query: str) -> str:
            return f"Query result: {query}"

        tool_def = ToolDefinition(
            name="execute_sql",
            description="Execute SQL",
            parameters=[{"query": "SQL query"}],
            callable=sql_tool
        )

        qwen_tool = DynamicQwenTool(tool_def)
        result = qwen_tool.call(query="SELECT 1")

        assert result == "Query result: SELECT 1"
