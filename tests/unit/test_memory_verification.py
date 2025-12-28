"""
Unit Tests for Memory Verification Service

Tests for the MemoryVerificationCoordinator which validates memory items
using SQL evidence.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import json
from services.memory_verification import MemoryVerificationCoordinator
from core.session_state import SessionState, ToolCall
from llm import LLMResponse


# ============================================================================
# Memory Verification Coordinator Tests
# ============================================================================

@pytest.mark.unit
class TestMemoryVerificationCoordinator:
    """Tests for MemoryVerificationCoordinator."""

    def test_coordinator_creation(self, app_config, mock_db_connection):
        """Test creating coordinator instance."""
        mock_execution = Mock()
        coordinator = MemoryVerificationCoordinator(app_config, mock_db_connection, mock_execution)

        assert coordinator.config == app_config
        assert coordinator.db_connection == mock_db_connection
        assert coordinator.session_execution == mock_execution

    @patch('services.memory_verification.LLMProviderFactory')
    def test_verify_memory_item_verified(self, mock_factory, app_config,
                                        mock_db_connection, session_id):
        """Test verifying a memory item that is verified."""
        session = SessionState(session_id)
        session.add_iteration(1, "test")
        tool_call = ToolCall(
            id="mem_1",
            tool="memory",
            timestamp=0,
            input={"action": "update", "key": "insights", "value": "record_count:There are 100 records"},
            output="Updated",
            execution_time=0.001
        )
        session.add_tool_call(1, tool_call)

        mock_execution = Mock()
        mock_execution.build_verification_prompt = Mock(return_value="Verify this memory")

        # Mock provider response
        mock_response = LLMResponse(content=json.dumps({
            "verified": True,
            "confidence": "high",
            "evidence": "SQL query confirmed 100 records",
            "recommendation": "keep",
            "updated_value": None,
            "reasoning": "Count matches database"
        }))
        mock_provider = Mock()
        mock_provider.run.return_value = iter([mock_response])
        mock_factory.create.return_value = mock_provider

        coordinator = MemoryVerificationCoordinator(app_config, mock_db_connection, mock_execution)
        result = coordinator.verify_memory_item(session, "insights", "record_count", "There are 100 records")

        assert result['verified'] == True
        assert result['confidence'] == "high"
        assert result['recommendation'] == "keep"
        mock_execution.build_verification_prompt.assert_called_once()

    @patch('services.memory_verification.LLMProviderFactory')
    def test_verify_memory_item_needs_update(self, mock_factory, app_config,
                                             mock_db_connection, session_id):
        """Test verifying a memory item that needs update."""
        session = SessionState(session_id)

        mock_execution = Mock()
        mock_execution.build_verification_prompt = Mock(return_value="Verify this memory")

        # Mock provider response suggesting update
        mock_response = LLMResponse(content=json.dumps({
            "verified": False,
            "confidence": "high",
            "evidence": "SQL shows 100 records, not 100",
            "recommendation": "update",
            "updated_value": "record_count:There are 100 records",
            "reasoning": "Count has changed"
        }))
        mock_provider = Mock()
        mock_provider.run.return_value = iter([mock_response])
        mock_factory.create.return_value = mock_provider

        coordinator = MemoryVerificationCoordinator(app_config, mock_db_connection, mock_execution)
        result = coordinator.verify_memory_item(session, "insights", "record_count", "There are 100 records")

        assert result['verified'] == False
        assert result['confidence'] == "high"
        assert result['recommendation'] == "update"
        assert result['updated_value'] == "record_count:There are 100 records"

    @patch('services.memory_verification.LLMProviderFactory')
    def test_verify_memory_item_remove(self, mock_factory, app_config,
                                       mock_db_connection, session_id):
        """Test verifying a memory item that should be removed."""
        session = SessionState(session_id)

        mock_execution = Mock()
        mock_execution.build_verification_prompt = Mock(return_value="Verify this memory")

        # Mock provider response suggesting removal
        mock_response = LLMResponse(content=json.dumps({
            "verified": False,
            "confidence": "high",
            "evidence": "No data supports this claim",
            "recommendation": "remove",
            "updated_value": None,
            "reasoning": "Incorrect information"
        }))
        mock_provider = Mock()
        mock_provider.run.return_value = iter([mock_response])
        mock_factory.create.return_value = mock_provider

        coordinator = MemoryVerificationCoordinator(app_config, mock_db_connection, mock_execution)
        result = coordinator.verify_memory_item(session, "insights", "bad_info", "Wrong data")

        assert result['verified'] == False
        assert result['recommendation'] == "remove"

    @patch('services.memory_verification.LLMProviderFactory')
    def test_verify_memory_item_with_think_tags(self, mock_factory, app_config,
                                                mock_db_connection, session_id):
        """Test that verification strips think tags from response."""
        session = SessionState(session_id)

        mock_execution = Mock()
        mock_execution.build_verification_prompt = Mock(return_value="Verify this memory")

        # Mock provider response with think tags
        mock_response = LLMResponse(content='<think>Let me analyze this...</think>' + json.dumps({
            "verified": True,
            "confidence": "medium",
            "evidence": "SQL data supports this",
            "recommendation": "keep",
            "updated_value": None,
            "reasoning": "Looks good"
        }))
        mock_provider = Mock()
        mock_provider.run.return_value = iter([mock_response])
        mock_factory.create.return_value = mock_provider

        coordinator = MemoryVerificationCoordinator(app_config, mock_db_connection, mock_execution)
        result = coordinator.verify_memory_item(session, "insights", "test", "Test value")

        assert result['verified'] == True
        assert result['confidence'] == "medium"

    @patch('services.memory_verification.LLMProviderFactory')
    def test_verify_memory_item_invalid_json(self, mock_factory, app_config,
                                             mock_db_connection, session_id):
        """Test handling invalid JSON response."""
        session = SessionState(session_id)

        mock_execution = Mock()
        mock_execution.build_verification_prompt = Mock(return_value="Verify this memory")

        # Mock provider response with invalid JSON
        mock_response = LLMResponse(content="This is not JSON")
        mock_provider = Mock()
        mock_provider.run.return_value = iter([mock_response])
        mock_factory.create.return_value = mock_provider

        coordinator = MemoryVerificationCoordinator(app_config, mock_db_connection, mock_execution)
        result = coordinator.verify_memory_item(session, "insights", "test", "Test value")

        assert result['verified'] == False
        assert result['confidence'] == "low"
        assert "not return valid JSON" in result['reasoning']

    @patch('services.memory_verification.LLMProviderFactory')
    def test_verify_memory_uses_sql_tool_definition(self, mock_factory, app_config,
                                                    mock_db_connection, session_id):
        """Test that verification uses SQL tool definition."""
        session = SessionState(session_id)

        mock_execution = Mock()
        mock_execution.build_verification_prompt = Mock(return_value="Verify")

        mock_response = LLMResponse(content=json.dumps({
            "verified": True,
            "confidence": "high",
            "evidence": "SQL confirmed",
            "recommendation": "keep",
            "updated_value": None,
            "reasoning": "Correct"
        }))
        mock_provider = Mock()
        mock_provider.run.return_value = iter([mock_response])
        mock_factory.create.return_value = mock_provider

        coordinator = MemoryVerificationCoordinator(app_config, mock_db_connection, mock_execution)
        coordinator.verify_memory_item(session, "insights", "test", "Value")

        # Check factory was called with SQL tool definition
        call_args = mock_factory.create.call_args
        tools = call_args[1]['tools']
        assert len(tools) == 1  # Only SQL tool
        assert tools[0].name == "execute_sql"


# ============================================================================
# JSON Extraction Tests
# ============================================================================

@pytest.mark.unit
class TestJSONExtraction:
    """Tests for _extract_json_from_response method."""

    def test_extract_json_simple(self, app_config, mock_db_connection):
        """Test extracting simple JSON."""
        coordinator = MemoryVerificationCoordinator(app_config, mock_db_connection, Mock())

        json_str = '{"verified": true, "confidence": "high"}'
        result = coordinator._extract_json_from_response(json_str)

        assert result['verified'] == True
        assert result['confidence'] == "high"

    def test_extract_json_with_think_tags(self, app_config, mock_db_connection):
        """Test extracting JSON with think tags."""
        coordinator = MemoryVerificationCoordinator(app_config, mock_db_connection, Mock())

        text = '<think>Analyzing...</think>{"verified": true, "confidence": "medium"}'
        result = coordinator._extract_json_from_response(text)

        assert result['verified'] == True
        assert result['confidence'] == "medium"

    def test_extract_json_with_surrounding_text(self, app_config, mock_db_connection):
        """Test extracting JSON with surrounding text."""
        coordinator = MemoryVerificationCoordinator(app_config, mock_db_connection, Mock())

        text = 'Here is the result: {"verified": false, "recommendation": "remove"} and that is all.'
        result = coordinator._extract_json_from_response(text)

        assert result['verified'] == False
        assert result['recommendation'] == "remove"

    def test_extract_json_no_json_found(self, app_config, mock_db_connection):
        """Test error when no JSON found."""
        coordinator = MemoryVerificationCoordinator(app_config, mock_db_connection, Mock())

        with pytest.raises(json.JSONDecodeError):
            coordinator._extract_json_from_response("No JSON here")

    def test_extract_json_multiline_think_tags(self, app_config, mock_db_connection):
        """Test extracting JSON with multiline think tags."""
        coordinator = MemoryVerificationCoordinator(app_config, mock_db_connection, Mock())

        text = '''<think>
        Let me think about this...
        I need to verify the data.
        </think>
        {"verified": true, "confidence": "low"}'''

        result = coordinator._extract_json_from_response(text)

        assert result['verified'] == True
        assert result['confidence'] == "low"
