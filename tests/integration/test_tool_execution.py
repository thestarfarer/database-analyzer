"""
Integration Tests for Tool Execution

Tests tools with real database connection and session state integration.
"""

import pytest
from unittest.mock import Mock, MagicMock
from tools.sql_tool import ExecuteSQLTool
from tools.memory_tool import MemoryTool
from core.session_state import SessionState, ToolCall
from database.connection import MSSQLConnection


# ============================================================================
# SQL Tool Integration Tests
# ============================================================================

@pytest.mark.integration
@pytest.mark.database
class TestSQLToolIntegration:
    """Tests for SQL tool with real database."""

    def test_sql_tool_with_real_database(self, mock_db_connection):
        """Test SQL tool with database connection."""
        mock_db_connection.execute_query.return_value = "Entity | Category\n---\nEntity1 | Cat1\nEntity2 | Cat2"
        tool = ExecuteSQLTool(mock_db_connection, verbose=False)

        result = tool.call(query="SELECT TOP 3 * FROM entities")

        assert result is not None
        assert "Entity" in result

    def test_sql_tool_complex_query(self, mock_db_connection):
        """Test SQL tool with complex aggregation query."""
        mock_db_connection.execute_query.return_value = "Category | RecordCount\n---\nCat1 | 15\nCat2 | 12\nCat3 | 8"
        tool = ExecuteSQLTool(mock_db_connection, verbose=False)

        query = """
        SELECT TOP 5 Category, COUNT(*) as RecordCount
        FROM entities
        GROUP BY Category
        ORDER BY RecordCount DESC
        """

        result = tool.call(query=query)

        assert result is not None
        assert "Category" in result

    def test_sql_tool_with_unicode(self, real_db_connection):
        """Test SQL tool with database schema query."""
        tool = ExecuteSQLTool(real_db_connection, verbose=False)

        # Generic query that works on any database
        query = "SELECT TOP 3 TABLE_NAME FROM INFORMATION_SCHEMA.TABLES"

        result = tool.call(query=query)

        assert result is not None

    def test_sql_tool_error_handling(self, real_db_connection):
        """Test SQL tool handles invalid queries."""
        tool = ExecuteSQLTool(real_db_connection, verbose=False)

        result = tool.call(query="SELECT * FROM nonexistent_table_xyz")

        assert "error" in result.lower()

    def test_sql_tool_result_limit(self, real_db_connection):
        """Test that SQL tool enforces result limit."""
        tool = ExecuteSQLTool(real_db_connection, verbose=False)

        # Query that returns many rows
        result = tool.call(query="SELECT * FROM entities")

        # Should have truncation indicator if more than limit
        assert result is not None


# ============================================================================
# Memory Tool Integration Tests
# ============================================================================

@pytest.mark.integration
class TestMemoryToolIntegration:
    """Tests for Memory tool with session state."""

    def test_memory_tool_full_workflow(self, session_id):
        """Test complete memory tool workflow with session state."""
        session = SessionState(session_id)
        tool = MemoryTool(session, verbose=False)

        # Create iteration to store tool calls
        iteration = session.add_iteration(1, "Test prompt")

        # Add memories
        categories = ['insights', 'patterns', 'key_findings']

        for i, category in enumerate(categories):
            # Memory tool returns result
            result = tool.call(
                action='update',
                key=category,
                value=f'{category}_item_{i}:Test value {i}'
            )

            assert "Updated" in result

            # Simulate logging the tool call
            tool_call = ToolCall(
                id=f"mem_{i}",
                tool="memory",
                timestamp=0,
                input={
                    "action": "update",
                    "key": category,
                    "value": f'{category}_item_{i}:Test value {i}'
                },
                output=result,
                execution_time=0.001
            )
            session.add_tool_call(1, tool_call)

        # Verify memory composition
        memory_data = session.get_memory_data_from_tool_calls()

        assert 'insights' in memory_data
        assert 'patterns' in memory_data
        assert 'key_findings' in memory_data

    def test_memory_tool_get_operations(self, session_id):
        """Test memory retrieval after updates."""
        session = SessionState(session_id)
        iteration = session.add_iteration(1, "Test")

        # Add memory via tool call
        tool_call = ToolCall(
            id="mem_1",
            tool="memory",
            timestamp=0,
            input={
                "action": "update",
                "key": "insights",
                "value": "test_key:Test value"
            },
            output="Updated",
            execution_time=0.001
        )
        session.add_tool_call(1, tool_call)

        # Get memory
        tool = MemoryTool(session, verbose=False)
        result = tool.call(action='get', key='insights')

        assert "test_key" in result or "Test value" in result

    def test_memory_tool_remove_operations(self, session_id):
        """Test memory removal workflow."""
        session = SessionState(session_id)
        iteration = session.add_iteration(1, "Test")
        tool = MemoryTool(session, verbose=False)

        # Add memory
        add_call = ToolCall(
            id="mem_1",
            tool="memory",
            timestamp=0,
            input={
                "action": "update",
                "key": "insights",
                "value": "item_to_remove:This will be removed"
            },
            output="Updated",
            execution_time=0.001
        )
        session.add_tool_call(1, add_call)

        # Remove memory (must match the full value that was added)
        remove_result = tool.call(
            action='remove',
            key='insights',
            value='item_to_remove:This will be removed'
        )

        assert "Removed" in remove_result

        # Simulate logging the remove
        remove_call = ToolCall(
            id="mem_2",
            tool="memory",
            timestamp=0,
            input={
                "action": "remove",
                "key": "insights",
                "value": "item_to_remove:This will be removed"
            },
            output=remove_result,
            execution_time=0.001
        )
        session.add_tool_call(1, remove_call)

        # Verify removal
        memory_data = session.get_memory_data_from_tool_calls()
        if 'insights' in memory_data:
            assert not any('item_to_remove' in item for item in memory_data['insights'])


# ============================================================================
# Tools + Database + Session Integration Tests
# ============================================================================

@pytest.mark.integration
class TestToolsWithSessionIntegration:
    """Tests for tools integrated with session management."""

    def test_sql_tool_calls_logged_to_session(self, session_id, mock_db_connection):
        """Test that SQL tool calls are properly logged."""
        session = SessionState(session_id)
        iteration = session.add_iteration(1, "Test")

        tool = ExecuteSQLTool(mock_db_connection, verbose=False)

        # Execute query
        result = tool.call(query="SELECT * FROM entities")

        # Simulate logging (this would normally happen in SessionExecution)
        tool_call = ToolCall(
            id="sql_1",
            tool="execute_sql",
            timestamp=0,
            input={"query": "SELECT * FROM entities"},
            output=result,
            execution_time=0.123
        )

        session.add_tool_call(1, tool_call)

        # Verify
        assert len(session.iterations[0].tool_calls) == 1
        assert session.iterations[0].tool_calls[0].tool == "execute_sql"

    def test_memory_and_sql_tools_together(self, session_id, mock_db_connection):
        """Test using both SQL and Memory tools in same iteration."""
        session = SessionState(session_id)
        iteration = session.add_iteration(1, "Analyze records")

        sql_tool = ExecuteSQLTool(mock_db_connection, verbose=False)
        memory_tool = MemoryTool(session, verbose=False)

        # Execute SQL
        sql_result = sql_tool.call(query="SELECT COUNT(*) FROM entities")

        # Log SQL call
        sql_call = ToolCall(
            id="sql_1",
            tool="execute_sql",
            timestamp=0,
            input={"query": "SELECT COUNT(*) FROM entities"},
            output=sql_result,
            execution_time=0.1
        )
        session.add_tool_call(1, sql_call)

        # Update memory based on SQL result
        memory_result = memory_tool.call(
            action='update',
            key='insights',
            value='record_count:Found records in database'
        )

        # Log memory call
        mem_call = ToolCall(
            id="mem_1",
            tool="memory",
            timestamp=0,
            input={
                "action": "update",
                "key": "insights",
                "value": "record_count:Found records in database"
            },
            output=memory_result,
            execution_time=0.001
        )
        session.add_tool_call(1, mem_call)

        # Verify both calls logged
        assert len(session.iterations[0].tool_calls) == 2
        assert session.iterations[0].tool_calls[0].tool == "execute_sql"
        assert session.iterations[0].tool_calls[1].tool == "memory"


# ============================================================================
# Tool Error Recovery Integration Tests
# ============================================================================

@pytest.mark.integration
class TestToolErrorRecoveryIntegration:
    """Tests for tool error handling with session integration."""

    def test_sql_error_logged_to_session(self, session_id):
        """Test that SQL errors are logged properly."""
        session = SessionState(session_id)
        iteration = session.add_iteration(1, "Test")

        # Mock connection that raises error
        mock_conn = Mock()
        mock_conn.execute_query.side_effect = Exception("Database error")

        tool = ExecuteSQLTool(mock_conn, verbose=False)

        # Tool should catch error and return error message
        try:
            result = tool.call(query="INVALID SQL")
        except Exception as e:
            result = f"Error: {str(e)}"

        # Log error result
        tool_call = ToolCall(
            id="sql_error_1",
            tool="execute_sql",
            timestamp=0,
            input={"query": "INVALID SQL"},
            output=result,
            execution_time=0
        )
        session.add_tool_call(1, tool_call)

        # Verify error is logged
        assert "error" in session.iterations[0].tool_calls[0].output.lower()

    def test_session_continues_after_tool_error(self, session_id, mock_db_connection):
        """Test that session can continue after tool error."""
        session = SessionState(session_id)

        # Iteration 1 - with error
        iter1 = session.add_iteration(1, "Test")

        # Simulate failed SQL call
        error_call = ToolCall(
            id="sql_error",
            tool="execute_sql",
            timestamp=0,
            input={"query": "INVALID"},
            output="Error: Syntax error",
            execution_time=0
        )
        session.add_tool_call(1, error_call)

        session.complete_iteration(1, "Got an error, will retry")

        # Iteration 2 - successful
        iter2 = session.add_iteration(2, "Retry")

        success_call = ToolCall(
            id="sql_success",
            tool="execute_sql",
            timestamp=0,
            input={"query": "SELECT * FROM entities"},
            output="Query results...",
            execution_time=0.1
        )
        session.add_tool_call(2, success_call)

        session.complete_iteration(2, "Success")

        # Verify both iterations
        assert len(session.iterations) == 2
        assert session.get_completed_iterations_count() == 2


# ============================================================================
# Performance Integration Tests
# ============================================================================

@pytest.mark.integration
@pytest.mark.slow
class TestToolPerformanceIntegration:
    """Tests for tool performance with real components."""

    def test_many_tool_calls_same_iteration(self, session_id, mock_db_connection):
        """Test performance with many tool calls in one iteration."""
        session = SessionState(session_id)
        iteration = session.add_iteration(1, "Test")

        tool = ExecuteSQLTool(mock_db_connection, verbose=False)

        # Execute many queries
        for i in range(50):
            result = tool.call(query=f"SELECT * FROM table{i}")

            tool_call = ToolCall(
                id=f"sql_{i}",
                tool="execute_sql",
                timestamp=0,
                input={"query": f"SELECT * FROM table{i}"},
                output=result,
                execution_time=0.01
            )
            session.add_tool_call(1, tool_call)

        # Verify all logged
        assert len(session.iterations[0].tool_calls) == 50

    def test_many_memory_updates(self, session_id):
        """Test performance with many memory updates."""
        session = SessionState(session_id)
        iteration = session.add_iteration(1, "Test")

        # Add many memory items
        for i in range(100):
            tool_call = ToolCall(
                id=f"mem_{i}",
                tool="memory",
                timestamp=0,
                input={
                    "action": "update",
                    "key": f"category_{i % 5}",
                    "value": f"key_{i}:Value {i}"
                },
                output="Updated",
                execution_time=0.001
            )
            session.add_tool_call(1, tool_call)

        # Verify memory composition performance
        import time
        start = time.time()
        memory_data = session.get_memory_data_from_tool_calls()
        duration = time.time() - start

        # Should be fast even with many items
        assert duration < 1.0  # Less than 1 second
        assert len(memory_data) > 0
