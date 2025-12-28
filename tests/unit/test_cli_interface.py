"""
Unit Tests for CLI Interface

Tests for the CLIInterface which handles user interaction in the terminal.
"""

import pytest
from unittest.mock import Mock, patch, call
from ui.cli_interface import CLIInterface
from core.session_state import SessionState


# ============================================================================
# CLI Interface Initialization Tests
# ============================================================================

@pytest.mark.unit
class TestCLIInterfaceInit:
    """Tests for CLIInterface initialization."""

    def test_cli_interface_creation(self, session_id):
        """Test creating CLIInterface instance."""
        session = SessionState(session_id)
        cli = CLIInterface(session)

        assert cli.session_state == session

    def test_cli_interface_stores_session_reference(self, session_id):
        """Test that CLI stores session reference."""
        session = SessionState(session_id)
        cli = CLIInterface(session)

        assert cli.session_state is session


# ============================================================================
# Get Initial Task Tests
# ============================================================================

@pytest.mark.unit
class TestGetInitialTask:
    """Tests for get_initial_task method."""

    @patch('builtins.input', return_value='')
    def test_get_initial_task_default(self, mock_input, session_id):
        """Test getting initial task with default option."""
        session = SessionState(session_id)
        cli = CLIInterface(session)

        task = cli.get_initial_task()

        assert isinstance(task, str)
        assert len(task) > 10
        # Should return default task
        assert "explore" in task.lower() or "database" in task.lower()

    @patch('builtins.input', return_value='Analyze data trends')
    def test_get_initial_task_custom(self, mock_input, session_id):
        """Test getting initial task with custom input."""
        session = SessionState(session_id)
        cli = CLIInterface(session)

        task = cli.get_initial_task()

        assert task == "Analyze data trends"

    @patch('builtins.input', return_value='   ')
    def test_get_initial_task_whitespace(self, mock_input, session_id):
        """Test that whitespace-only input returns default."""
        session = SessionState(session_id)
        cli = CLIInterface(session)

        task = cli.get_initial_task()

        # Should return default, not empty string
        assert len(task) > 5


# ============================================================================
# Get User Input Tests
# ============================================================================

@pytest.mark.unit
class TestGetUserInput:
    """Tests for get_user_input method."""

    @patch('builtins.input', return_value='')
    def test_get_user_input_continue(self, mock_input, session_id):
        """Test user input for continuing analysis."""
        session = SessionState(session_id)
        cli = CLIInterface(session)

        user_input, should_report = cli.get_user_input()

        assert user_input == ""
        assert should_report == False

    @patch('builtins.input', side_effect=['report', 'Test report topic'])
    def test_get_user_input_report_command(self, mock_input, session_id):
        """Test user requesting report."""
        session = SessionState(session_id)
        cli = CLIInterface(session)

        user_input, should_report = cli.get_user_input()

        assert user_input == "Test report topic"
        assert should_report == True

    @patch('builtins.input', side_effect=['REPORT', 'Q2 analysis'])
    def test_get_user_input_report_case_insensitive(self, mock_input, session_id):
        """Test report command is case insensitive."""
        session = SessionState(session_id)
        cli = CLIInterface(session)

        user_input, should_report = cli.get_user_input()

        assert user_input == "Q2 analysis"
        assert should_report == True

    @patch('builtins.input', return_value='Focus on Q2 data')
    def test_get_user_input_custom(self, mock_input, session_id):
        """Test custom user guidance."""
        session = SessionState(session_id)
        cli = CLIInterface(session)

        user_input, should_report = cli.get_user_input()

        assert user_input == "Focus on Q2 data"
        assert should_report == False

    @patch('builtins.input', side_effect=KeyboardInterrupt())
    def test_get_user_input_keyboard_interrupt(self, mock_input, session_id):
        """Test handling Ctrl+C."""
        session = SessionState(session_id)
        cli = CLIInterface(session)

        user_input, should_report = cli.get_user_input()

        assert user_input == "EXIT"
        assert should_report == False




# ============================================================================
# Helper Methods Tests
# ============================================================================

@pytest.mark.unit
class TestHelperMethods:
    """Tests for CLI helper methods."""

    def test_session_state_access(self, session_id):
        """Test that CLI can access session state."""
        from core.session_state import ToolCall

        session = SessionState(session_id)
        session.add_iteration(1, "test")

        tool_call = ToolCall(
            id="mem_1",
            tool="memory",
            timestamp=0,
            input={"action": "update", "key": "insights", "value": "record_count:100 records"},
            output="Updated",
            execution_time=0.001
        )
        session.add_tool_call(1, tool_call)

        cli = CLIInterface(session)
        memory_data = session.get_memory_data_from_tool_calls()

        assert 'insights' in memory_data
        assert any('record_count' in item for item in memory_data['insights'])


# ============================================================================
# Edge Cases Tests
# ============================================================================

@pytest.mark.unit
class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @patch('builtins.input', return_value='')
    def test_multiple_empty_inputs(self, mock_input, session_id):
        """Test handling multiple empty inputs."""
        session = SessionState(session_id)
        cli = CLIInterface(session)

        # First call
        input1, report1 = cli.get_user_input()
        # Second call
        input2, report2 = cli.get_user_input()

        assert input1 == ""
        assert input2 == ""
        assert report1 == False
        assert report2 == False

    @patch('builtins.input', side_effect=['  report  ', 'Whitespace topic test'])
    def test_report_with_whitespace(self, mock_input, session_id):
        """Test report command with extra whitespace."""
        session = SessionState(session_id)
        cli = CLIInterface(session)

        user_input, should_report = cli.get_user_input()

        assert user_input == "Whitespace topic test"
        assert should_report == True
