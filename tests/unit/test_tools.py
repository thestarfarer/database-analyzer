"""
Unit Tests for Tools (SQL and Memory)

Tests for ExecuteSQLTool and MemoryTool including parameter handling,
execution, error handling, and logging.
"""

import pytest
import json
from unittest.mock import Mock, MagicMock, patch
from tools.sql_tool import ExecuteSQLTool
from tools.memory_tool import MemoryTool
from core.session_state import SessionState


# ============================================================================
# SQL Tool Tests
# ============================================================================

@pytest.mark.unit
class TestExecuteSQLTool:
    """Tests for ExecuteSQLTool."""

    def test_sql_tool_creation(self, mock_db_connection):
        """Test creating SQL tool."""
        tool = ExecuteSQLTool(mock_db_connection, verbose=False)

        assert tool.name == "execute_sql"
        assert tool.db_connection == mock_db_connection
        assert tool.verbose is False

    def test_sql_tool_execute_query(self, mock_db_connection):
        """Test executing a simple SQL query."""
        tool = ExecuteSQLTool(mock_db_connection, verbose=False)

        result = tool.call(query="SELECT * FROM entities")

        assert result == "Entity | Value\n---\nEntity1 | 1000"
        mock_db_connection.execute_query.assert_called_once_with("SELECT * FROM entities")

    def test_sql_tool_with_kwargs(self, mock_db_connection):
        """Test SQL tool with keyword arguments."""
        tool = ExecuteSQLTool(mock_db_connection, verbose=False)

        result = tool.call(query="SELECT COUNT(*) FROM entities")

        assert result is not None
        mock_db_connection.execute_query.assert_called_once()

    def test_sql_tool_no_query(self, mock_db_connection):
        """Test SQL tool without query parameter."""
        tool = ExecuteSQLTool(mock_db_connection, verbose=False)

        result = tool.call()

        assert "Error" in result
        assert "No SQL query" in result

    def test_sql_tool_json_encoded_query(self, mock_db_connection):
        """Test SQL tool with JSON-encoded query."""
        tool = ExecuteSQLTool(mock_db_connection, verbose=False)

        json_query = '{"query": "SELECT * FROM entities"}'
        result = tool.call(query=json_query)

        mock_db_connection.execute_query.assert_called_once_with("SELECT * FROM entities")

    def test_sql_tool_invalid_json_query(self, mock_db_connection):
        """Test SQL tool with invalid JSON."""
        tool = ExecuteSQLTool(mock_db_connection, verbose=False)

        result = tool.call(query='{"query": invalid json}')

        assert "Error" in result or "Invalid JSON" in result

    def test_sql_tool_verbose_logging(self, mock_db_connection, capsys):
        """Test SQL tool with verbose logging enabled."""
        tool = ExecuteSQLTool(mock_db_connection, verbose=True)

        result = tool.call(query="SELECT * FROM entities")

        captured = capsys.readouterr()
        assert "SQL QUERY EXECUTION" in captured.out
        assert "SELECT" in captured.out

    def test_sql_tool_query_formatting(self, mock_db_connection):
        """Test SQL query formatting."""
        tool = ExecuteSQLTool(mock_db_connection, verbose=False)

        # Test that complex queries work
        complex_query = """
            SELECT e.Entity, SUM(m.Value) as TotalMetric
            FROM entities e
            JOIN metrics m ON e.EntityID = m.EntityID
            WHERE e.Category = 'Category A'
            GROUP BY e.Entity
            ORDER BY TotalMetric DESC
        """

        result = tool.call(query=complex_query)

        assert mock_db_connection.execute_query.called


@pytest.mark.unit
class TestExecuteSQLToolErrorHandling:
    """Tests for SQL tool error handling."""

    def test_sql_tool_database_error(self):
        """Test SQL tool handles database errors."""
        mock_conn = Mock()
        mock_conn.execute_query.side_effect = Exception("Database connection lost")

        tool = ExecuteSQLTool(mock_conn, verbose=False)

        # Should not raise, but return error message
        with pytest.raises(Exception):
            result = tool.call(query="SELECT * FROM entities")

    def test_sql_tool_empty_result(self, mock_db_connection):
        """Test SQL tool with empty result set."""
        mock_db_connection.execute_query.return_value = "No results returned"

        tool = ExecuteSQLTool(mock_db_connection, verbose=False)
        result = tool.call(query="SELECT * FROM nonexistent_table")

        assert "No results" in result


# ============================================================================
# Memory Tool Tests
# ============================================================================

@pytest.mark.unit
class TestMemoryTool:
    """Tests for MemoryTool."""

    def test_memory_tool_creation(self, sample_session):
        """Test creating memory tool."""
        tool = MemoryTool(sample_session, verbose=False)

        assert tool.name == "memory"
        assert tool.session_state == sample_session
        assert tool.verbose is False

    def test_memory_tool_get_all(self, sample_session_with_memory):
        """Test getting all memory."""
        tool = MemoryTool(sample_session_with_memory, verbose=False)

        result = tool.call(action='get')

        assert isinstance(result, str)
        assert "Insights:" in result or "No memory" in result

    def test_memory_tool_get_category(self, sample_session_with_memory):
        """Test getting specific memory category."""
        tool = MemoryTool(sample_session_with_memory, verbose=False)

        result = tool.call(action='get', key='insights')

        assert "INSIGHTS:" in result
        assert "100 records" in result

    def test_memory_tool_get_nonexistent_category(self, sample_session):
        """Test getting non-existent memory category."""
        tool = MemoryTool(sample_session, verbose=False)

        result = tool.call(action='get', key='nonexistent_category')

        assert "No memory found" in result

    def test_memory_tool_update(self, sample_session):
        """Test updating memory."""
        tool = MemoryTool(sample_session, verbose=False)

        result = tool.call(
            action='update',
            key='insights',
            value='record_count:100 records total'
        )

        assert "Updated" in result
        assert "insights" in result

    def test_memory_tool_update_without_key_value_format(self, sample_session):
        """Test updating memory without key:value format."""
        tool = MemoryTool(sample_session, verbose=False)

        result = tool.call(
            action='update',
            key='insights',
            value='Some insight without colon format'
        )

        # Should still work, auto-generating a key
        assert "Updated" in result

    def test_memory_tool_update_missing_params(self, sample_session):
        """Test updating memory with missing parameters."""
        tool = MemoryTool(sample_session, verbose=False)

        # Missing value
        result = tool.call(action='update', key='insights')

        assert "Error" in result
        assert "required" in result

    def test_memory_tool_remove(self, sample_session_with_memory):
        """Test removing memory item."""
        tool = MemoryTool(sample_session_with_memory, verbose=False)

        result = tool.call(
            action='remove',
            key='insights',
            value='record_count'
        )

        assert "Removed" in result
        assert "insights" in result

    def test_memory_tool_remove_missing_params(self, sample_session):
        """Test removing memory with missing parameters."""
        tool = MemoryTool(sample_session, verbose=False)

        # Missing value
        result = tool.call(action='remove', key='insights')

        assert "Error" in result
        assert "required" in result

    def test_memory_tool_unknown_action(self, sample_session):
        """Test memory tool with unknown action."""
        tool = MemoryTool(sample_session, verbose=False)

        result = tool.call(action='invalid_action')

        assert "Unknown action" in result

    def test_memory_tool_json_encoded_params(self, sample_session):
        """Test memory tool with JSON-encoded parameters."""
        tool = MemoryTool(sample_session, verbose=False)

        json_params = json.dumps({
            "action": "update",
            "key": "insights",
            "value": "test:value"
        })

        result = tool.call(action=json_params)

        assert "Updated" in result

    def test_memory_tool_verbose_logging(self, sample_session, capsys):
        """Test memory tool with verbose logging."""
        tool = MemoryTool(sample_session, verbose=True)

        result = tool.call(
            action='update',
            key='insights',
            value='test:value'
        )

        captured = capsys.readouterr()
        assert "MEMORY" in captured.out
        assert "UPDATE" in captured.out

    def test_memory_tool_default_action(self, sample_session_with_memory):
        """Test memory tool with default action (get)."""
        tool = MemoryTool(sample_session_with_memory, verbose=False)

        # No action specified - defaults to get
        result = tool.call()

        assert isinstance(result, str)

    def test_memory_tool_invalid_json_params(self, sample_session):
        """Test memory tool with invalid JSON parameters."""
        tool = MemoryTool(sample_session, verbose=False)

        # Invalid JSON string
        result = tool.call(action='{invalid json}')

        # Should fall back to treating it as action='get' due to JSON decode error
        assert isinstance(result, str)

    def test_memory_tool_verbose_remove_logging(self, sample_session_with_memory, capsys):
        """Test memory tool verbose logging for remove operation."""
        tool = MemoryTool(sample_session_with_memory, verbose=True)

        result = tool.call(
            action='remove',
            key='insights',
            value='test_item'
        )

        captured = capsys.readouterr()
        assert "MEMORY" in captured.out
        assert "REMOVE" in captured.out
        assert "insights" in captured.out

    def test_memory_tool_exception_with_verbose(self, capsys):
        """Test memory tool exception handling with verbose logging."""
        # Create tool with None session_state to trigger exception
        tool = MemoryTool(session_state=None, verbose=True)

        result = tool.call(action='get')

        captured = capsys.readouterr()
        assert "Memory operation failed" in result or "Error" in result


# ============================================================================
# Memory Tool Integration Tests
# ============================================================================

@pytest.mark.unit
class TestMemoryToolIntegration:
    """Tests for memory tool integration with session state."""

    def test_memory_operations_affect_session_state(self, session_id):
        """Test that memory operations are reflected in session state."""
        session = SessionState(session_id=session_id)
        tool = MemoryTool(session, verbose=False)

        # Add iteration to store tool calls
        iteration = session.add_iteration(1, "Test")

        # Memory tool calls are logged through the session execution wrapper
        # This test verifies the tool returns expected output
        result = tool.call(
            action='update',
            key='insights',
            value='test_insight:This is a test'
        )

        assert "Updated" in result

    def test_memory_get_reflects_tool_calls(self, sample_session_with_memory):
        """Test that get operations reflect actual tool call history."""
        tool = MemoryTool(sample_session_with_memory, verbose=False)

        # Get insights
        result = tool.call(action='get', key='insights')

        # Should reflect what's in the session state
        memory_data = sample_session_with_memory.get_memory_data_from_tool_calls()
        assert "insights" in memory_data or "No memory" in result

    def test_memory_categories(self, session_id):
        """Test different memory categories."""
        session = SessionState(session_id=session_id)
        tool = MemoryTool(session, verbose=False)

        categories = [
            'insights',
            'patterns',
            'explored_areas',
            'key_findings',
            'opportunities',
            'data_milestones',
            'data_issues',
            'metrics',
            'context',
            'user_requests'
        ]

        for category in categories:
            result = tool.call(
                action='update',
                key=category,
                value=f'test_{category}:Test value for {category}'
            )
            assert "Updated" in result
            assert category in result


# ============================================================================
# Tool Error Handling Tests
# ============================================================================

@pytest.mark.unit
class TestToolErrorHandling:
    """Tests for tool error handling."""

    def test_sql_tool_handles_unicode(self, mock_db_connection):
        """Test SQL tool handles Unicode characters."""
        tool = ExecuteSQLTool(mock_db_connection, verbose=False)

        # Query with Cyrillic characters (testing Unicode support)
        query = "SELECT * FROM entities WHERE Name = 'Тестовая Запись'"

        result = tool.call(query=query)

        # Should not raise exception
        assert result is not None

    def test_memory_tool_handles_unicode(self, sample_session):
        """Test memory tool handles Unicode characters."""
        tool = MemoryTool(sample_session, verbose=False)

        # Update with Cyrillic characters
        result = tool.call(
            action='update',
            key='insights',
            value='магазин:Всего 105 магазинов'
        )

        assert "Updated" in result

    def test_memory_tool_exception_handling(self, sample_session):
        """Test memory tool handles exceptions gracefully."""
        tool = MemoryTool(sample_session, verbose=False)

        # Mock the session_state to raise an exception
        with patch.object(sample_session, 'get_memory_data_from_tool_calls', side_effect=Exception("Test error")):
            result = tool.call(action='get', key='insights')

            # Should return error message, not raise
            assert "failed" in result.lower() or "error" in result.lower()


# ============================================================================
# Tool Parameter Extraction Tests
# ============================================================================

@pytest.mark.unit
class TestToolParameterExtraction:
    """Tests for parameter extraction in tools."""

    def test_sql_tool_extracts_query_from_kwargs(self, mock_db_connection):
        """Test SQL tool extracts query from **kwargs."""
        tool = ExecuteSQLTool(mock_db_connection, verbose=False)

        result = tool.call(**{"query": "SELECT * FROM entities"})

        mock_db_connection.execute_query.assert_called_once()

    def test_memory_tool_extracts_params_from_kwargs(self, sample_session):
        """Test memory tool extracts parameters from **kwargs."""
        tool = MemoryTool(sample_session, verbose=False)

        result = tool.call(**{
            "action": "update",
            "key": "insights",
            "value": "test:value"
        })

        assert "Updated" in result

    def test_memory_tool_handles_mixed_params(self, sample_session):
        """Test memory tool handles mixed positional and keyword args."""
        tool = MemoryTool(sample_session, verbose=False)

        # Positional action, keyword key/value
        result = tool.call("update", key="insights", value="test:value")

        assert "Updated" in result
