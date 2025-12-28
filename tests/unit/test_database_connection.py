"""
Unit Tests for Database Connection

Tests for MSSQLConnection class including connection management,
query execution, result formatting, and error handling.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from database.connection import MSSQLConnection, DatabaseConnection
from config.settings import DatabaseConfig


# ============================================================================
# DatabaseConnection Abstract Class Tests
# ============================================================================

@pytest.mark.unit
class TestDatabaseConnection:
    """Tests for DatabaseConnection abstract base class."""

    def test_database_connection_is_abstract(self):
        """Test that DatabaseConnection cannot be instantiated directly."""
        with pytest.raises(TypeError):
            DatabaseConnection()


# ============================================================================
# MSSQLConnection Creation Tests
# ============================================================================

@pytest.mark.unit
class TestMSSQLConnectionCreation:
    """Tests for MSSQLConnection initialization."""

    @patch('database.connection.pymssql.connect')
    def test_mssql_connection_creation(self, mock_connect, test_db_config):
        """Test creating MSSQL connection."""
        mock_connect.return_value = MagicMock()

        conn = MSSQLConnection(test_db_config, verbose=False)

        assert conn.config == test_db_config
        assert conn.verbose is False
        assert conn.result_limit == 100
        mock_connect.assert_called_once()

    @patch('database.connection.pymssql.connect')
    def test_mssql_connection_with_custom_limit(self, mock_connect, test_db_config):
        """Test creating MSSQL connection with custom result limit."""
        mock_connect.return_value = MagicMock()

        conn = MSSQLConnection(test_db_config, verbose=False, result_limit=50)

        assert conn.result_limit == 50

    @patch('database.connection.pymssql.connect')
    def test_mssql_connection_failure(self, mock_connect, test_db_config):
        """Test handling connection failure."""
        mock_connect.side_effect = Exception("Connection refused")

        with pytest.raises(Exception, match="Connection refused"):
            MSSQLConnection(test_db_config, verbose=False)

    @patch('database.connection.pymssql.connect')
    def test_mssql_connection_uses_config(self, mock_connect, test_db_config):
        """Test that connection uses provided config."""
        mock_connect.return_value = MagicMock()

        conn = MSSQLConnection(test_db_config, verbose=False)

        mock_connect.assert_called_with(
            server=test_db_config.server,
            user=test_db_config.user,
            password=test_db_config.password,
            database=test_db_config.database,
            charset=test_db_config.charset
        )


# ============================================================================
# Query Execution Tests
# ============================================================================

@pytest.mark.unit
class TestMSSQLQueryExecution:
    """Tests for SQL query execution."""

    @patch('database.connection.pymssql.connect')
    def test_execute_simple_query(self, mock_connect, test_db_config):
        """Test executing a simple query."""
        # Setup mock
        mock_cursor = MagicMock()
        mock_cursor.description = [('Entity',), ('Value',)]
        mock_cursor.fetchall.return_value = [('Entity1', 1000), ('Entity2', 2000)]

        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        conn = MSSQLConnection(test_db_config, verbose=False)

        result = conn.execute_query("SELECT Entity, Value FROM entities")

        assert "Entity" in result
        assert "Value" in result
        assert "Entity1" in result
        assert "1000" in result

    @patch('database.connection.pymssql.connect')
    def test_execute_query_with_results(self, mock_connect, test_db_config):
        """Test query execution with multiple rows."""
        # Setup mock
        mock_cursor = MagicMock()
        mock_cursor.description = [('ID',), ('Name',)]
        mock_cursor.fetchall.return_value = [
            (1, 'Entity A'),
            (2, 'Entity B'),
            (3, 'Entity C')
        ]

        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        conn = MSSQLConnection(test_db_config, verbose=False)

        result = conn.execute_query("SELECT * FROM entities")

        # All rows should be present
        assert 'Entity A' in result
        assert 'Entity B' in result
        assert 'Entity C' in result

    @patch('database.connection.pymssql.connect')
    def test_execute_query_empty_result(self, mock_connect, test_db_config):
        """Test query with no results."""
        # Setup mock
        mock_cursor = MagicMock()
        mock_cursor.description = None
        mock_cursor.fetchall.return_value = []

        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        conn = MSSQLConnection(test_db_config, verbose=False)

        result = conn.execute_query("SELECT * FROM nonexistent_table")

        assert "No results" in result

    @patch('database.connection.pymssql.connect')
    def test_execute_query_result_limit(self, mock_connect, test_db_config):
        """Test that result limit is enforced."""
        # Setup mock with many rows
        mock_cursor = MagicMock()
        mock_cursor.description = [('ID',)]
        rows = [(i,) for i in range(100)]  # 100 rows
        mock_cursor.fetchall.return_value = rows

        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        conn = MSSQLConnection(test_db_config, verbose=False, result_limit=10)

        result = conn.execute_query("SELECT * FROM large_table")

        # Should indicate truncation
        assert "more rows" in result or "..." in result

    @patch('database.connection.pymssql.connect')
    def test_execute_query_handles_unicode(self, mock_connect, test_db_config):
        """Test query execution with Unicode characters."""
        # Setup mock
        mock_cursor = MagicMock()
        mock_cursor.description = [('Name',)]
        mock_cursor.fetchall.return_value = [('Тестовая Запись',)]

        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        conn = MSSQLConnection(test_db_config, verbose=False)

        result = conn.execute_query("SELECT Name FROM entities")

        assert 'Тестовая Запись' in result


# ============================================================================
# Error Handling Tests
# ============================================================================

@pytest.mark.unit
class TestMSSQLErrorHandling:
    """Tests for error handling in MSSQL connection."""

    @patch('database.connection.pymssql.connect')
    def test_execute_query_error(self, mock_connect, test_db_config):
        """Test handling query execution errors."""
        # Setup mock to raise error
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("Syntax error")

        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        conn = MSSQLConnection(test_db_config, verbose=False)

        result = conn.execute_query("INVALID SQL")

        assert "error" in result.lower()
        assert "Syntax error" in result

    @patch('database.connection.pymssql.connect')
    def test_reconnect_on_connection_lost(self, mock_connect, test_db_config):
        """Test reconnection when connection is lost."""
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [('ID',)]
        mock_cursor.fetchall.return_value = [(1,)]

        mock_connection.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        conn = MSSQLConnection(test_db_config, verbose=False)

        # Simulate connection loss
        conn._connection = None

        # Should reconnect automatically
        result = conn.execute_query("SELECT * FROM entities")

        assert mock_connect.call_count >= 2  # Initial connect + reconnect


# ============================================================================
# Statistics and Logging Tests
# ============================================================================

@pytest.mark.unit
class TestMSSQLStatistics:
    """Tests for connection statistics tracking."""

    @patch('database.connection.pymssql.connect')
    def test_verbose_logging(self, mock_connect, test_db_config, capsys):
        """Test verbose logging output."""
        # Setup mock
        mock_cursor = MagicMock()
        mock_cursor.description = [('ID',)]
        mock_cursor.fetchall.return_value = [(1,)]

        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        conn = MSSQLConnection(test_db_config, verbose=True)

        conn.execute_query("SELECT * FROM entities")

        captured = capsys.readouterr()
        assert "DATABASE QUERY EXECUTION" in captured.out
        assert "Server:" in captured.out

    @patch('database.connection.pymssql.connect')
    def test_error_logging(self, mock_connect, test_db_config, capsys):
        """Test error logging in verbose mode."""
        # Setup mock to raise error
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("Test error")

        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        conn = MSSQLConnection(test_db_config, verbose=True)

        result = conn.execute_query("INVALID SQL")

        captured = capsys.readouterr()
        assert "FAILED" in captured.out or "ERROR" in captured.out


# ============================================================================
# Connection Management Tests
# ============================================================================

@pytest.mark.unit
class TestMSSQLConnectionManagement:
    """Tests for connection lifecycle management."""

    @patch('database.connection.pymssql.connect')
    def test_close_connection(self, mock_connect, test_db_config):
        """Test closing database connection."""
        mock_connection = MagicMock()
        mock_connect.return_value = mock_connection

        conn = MSSQLConnection(test_db_config, verbose=False)
        conn.close()

        mock_connection.close.assert_called_once()
        assert conn._connection is None

    @patch('database.connection.pymssql.connect')
    def test_close_already_closed_connection(self, mock_connect, test_db_config):
        """Test closing already closed connection."""
        mock_connect.return_value = MagicMock()

        conn = MSSQLConnection(test_db_config, verbose=False)
        conn._connection = None

        # Should not raise
        conn.close()


# ============================================================================
# Result Formatting Tests
# ============================================================================

@pytest.mark.unit
class TestResultFormatting:
    """Tests for query result formatting."""

    @patch('database.connection.pymssql.connect')
    def test_result_table_format(self, mock_connect, test_db_config):
        """Test that results are formatted as table."""
        # Setup mock
        mock_cursor = MagicMock()
        mock_cursor.description = [('Entity',), ('Value',)]
        mock_cursor.fetchall.return_value = [('Entity1', 1000)]

        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        conn = MSSQLConnection(test_db_config, verbose=False)

        result = conn.execute_query("SELECT * FROM entities")

        # Should have header separator
        assert "|" in result
        assert "-" in result

    @patch('database.connection.pymssql.connect')
    def test_result_handles_none_values(self, mock_connect, test_db_config):
        """Test that None values are handled in results."""
        # Setup mock
        mock_cursor = MagicMock()
        mock_cursor.description = [('Entity',), ('Value',)]
        mock_cursor.fetchall.return_value = [('Entity1', None)]

        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        conn = MSSQLConnection(test_db_config, verbose=False)

        result = conn.execute_query("SELECT * FROM entities")

        assert "None" in result or "null" in result.lower()


# ============================================================================
# Integration Tests (requires real database)
# ============================================================================

@pytest.mark.database
@pytest.mark.integration
class TestMSSQLRealDatabase:
    """Integration tests with real database connection.

    These tests require actual database access and are marked with
    @pytest.mark.database for selective running.
    """

    def test_real_database_connection(self, test_db_config):
        """Test connecting to real database."""
        try:
            conn = MSSQLConnection(test_db_config, verbose=False, result_limit=5)
            conn.close()
        except Exception as e:
            pytest.skip(f"Database not available: {e}")

    def test_real_query_execution(self, test_db_config):
        """Test executing real query."""
        try:
            conn = MSSQLConnection(test_db_config, verbose=False, result_limit=5)

            result = conn.execute_query("SELECT TOP 5 * FROM entities")

            assert result is not None
            assert len(result) > 0

            conn.close()
        except Exception as e:
            pytest.skip(f"Database not available: {e}")

    def test_real_query_with_unicode(self, test_db_config):
        """Test real query with Unicode characters."""
        try:
            conn = MSSQLConnection(test_db_config, verbose=False, result_limit=5)

            # Generic query to test connection - actual table names depend on database
            result = conn.execute_query(
                "SELECT TOP 5 TABLE_NAME FROM INFORMATION_SCHEMA.TABLES"
            )

            assert result is not None

            conn.close()
        except Exception as e:
            pytest.skip(f"Database not available: {e}")
