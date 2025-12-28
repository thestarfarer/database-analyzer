"""
Unit Tests for Session Execution Engine

Tests for the SessionExecution class which handles LLM integration,
tool coordination, and execution flow.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from core.session_execution import SessionExecution, create_logging_wrapper
from core.session_state import SessionState, ToolCall
from tools.sql_tool import ExecuteSQLTool
from tools.memory_tool import MemoryTool


# ============================================================================
# SessionExecution Initialization Tests
# ============================================================================

@pytest.mark.unit
class TestSessionExecutionInit:
    """Tests for SessionExecution initialization."""

    def test_session_execution_creation(self, app_config, mock_db_connection):
        """Test creating SessionExecution instance."""
        execution = SessionExecution(app_config, mock_db_connection)

        assert execution.config == app_config
        assert execution.db_connection == mock_db_connection
        assert execution.save_callback is None
        assert execution.sql_tool is not None
        assert execution.memory_tool is not None

    def test_session_execution_with_callback(self, app_config, mock_db_connection):
        """Test SessionExecution with save callback."""
        callback = Mock()
        execution = SessionExecution(app_config, mock_db_connection, save_callback=callback)

        assert execution.save_callback == callback

    def test_session_execution_initializes_tools(self, app_config, mock_db_connection):
        """Test that tools are initialized properly."""
        execution = SessionExecution(app_config, mock_db_connection)

        assert isinstance(execution.sql_tool, ExecuteSQLTool)
        assert isinstance(execution.memory_tool, MemoryTool)
        assert execution.sql_tool.db_connection == mock_db_connection


# ============================================================================
# Session Initialization Tests
# ============================================================================

@pytest.mark.unit
class TestInitializeForSession:
    """Tests for initialize_for_session method."""

    @patch('core.session_execution.create_logging_wrapper')
    @patch('core.session_execution.LLMProviderFactory')
    @patch('core.session_execution.CLIInterface')
    @patch('core.session_execution.ReportService')
    def test_initialize_for_session(self, mock_report_class, mock_cli_class,
                                    mock_factory, mock_wrapper_func,
                                    app_config, mock_db_connection, session_id):
        """Test initializing execution for a session."""
        session = SessionState(session_id)
        execution = SessionExecution(app_config, mock_db_connection)

        # Setup mocks
        mock_wrapper_func.side_effect = [Mock(), Mock()]  # Two wrappers
        mock_factory.create.return_value = Mock()

        execution.initialize_for_session(session)

        assert execution.session_state == session
        assert execution.memory_tool.session_state == session
        assert mock_wrapper_func.call_count == 2  # SQL and Memory wrappers
        assert mock_factory.create.called
        assert mock_cli_class.called
        assert mock_report_class.called

    @patch('core.session_execution.create_logging_wrapper')
    @patch('core.session_execution.LLMProviderFactory')
    @patch('core.session_execution.CLIInterface')
    @patch('core.session_execution.ReportService')
    def test_initialize_creates_provider_with_tools(self, mock_report_class, mock_cli_class,
                                                     mock_factory, mock_wrapper_func,
                                                     app_config, mock_db_connection, session_id):
        """Test that provider is initialized with tool definitions."""
        session = SessionState(session_id)
        execution = SessionExecution(app_config, mock_db_connection)

        sql_wrapper = Mock(name='sql_wrapper')
        memory_wrapper = Mock(name='memory_wrapper')
        mock_wrapper_func.side_effect = [sql_wrapper, memory_wrapper]
        mock_factory.create.return_value = Mock()

        execution.initialize_for_session(session)

        # Check factory was called with tool definitions
        mock_factory.create.assert_called_once()
        call_args = mock_factory.create.call_args
        # First arg is config, second is tools list
        assert len(call_args[0]) >= 1 or 'tools' in call_args[1]


# ============================================================================
# Prompt Building Tests
# ============================================================================

@pytest.mark.unit
class TestPromptBuilding:
    """Tests for prompt building methods."""

    @patch('core.session_execution.create_logging_wrapper')
    @patch('core.session_execution.LLMProviderFactory')
    @patch('core.session_execution.CLIInterface')
    @patch('core.session_execution.ReportService')
    def test_build_base_prompt(self, mock_report_class, mock_cli_class,
                               mock_factory, mock_wrapper_func,
                               app_config, mock_db_connection, session_id):
        """Test building base prompt."""
        session = SessionState(session_id)
        execution = SessionExecution(app_config, mock_db_connection)
        mock_wrapper_func.side_effect = [Mock(), Mock()]
        mock_factory.create.return_value = Mock()
        execution.initialize_for_session(session)

        prompt = execution.build_base_prompt()

        assert isinstance(prompt, str)
        assert len(prompt) > 100
        assert "Database schema" in prompt
        assert "memory" in prompt.lower()
        assert "execute_sql" in prompt.lower()
        assert "YearMonth" in prompt

    @patch('core.session_execution.create_logging_wrapper')
    @patch('core.session_execution.LLMProviderFactory')
    @patch('core.session_execution.CLIInterface')
    @patch('core.session_execution.ReportService')
    def test_build_continuation_prompt(self, mock_report_class, mock_cli_class,
                                       mock_factory, mock_wrapper_func,
                                       app_config, mock_db_connection, session_id):
        """Test building continuation prompt."""
        session = SessionState(session_id)
        # Add some memory to session
        session.add_iteration(1, "base prompt", "Analyze records")
        tool_call = ToolCall(
            id="mem_1",
            tool="memory",
            timestamp=0,
            input={"action": "update", "key": "insights", "value": "test_insight:Test value"},
            output="Updated",
            execution_time=0.001
        )
        session.add_tool_call(1, tool_call)
        session.complete_iteration(1, "Analysis complete")

        execution = SessionExecution(app_config, mock_db_connection)
        mock_wrapper_func.side_effect = [Mock(), Mock()]
        mock_factory.create.return_value = Mock()
        execution.initialize_for_session(session)

        prompt = execution.build_continuation_prompt(session)

        assert isinstance(prompt, str)
        assert len(prompt) > 100
        assert "Database schema" in prompt
        # Memory should be included
        assert "insights" in prompt.lower() or "test_insight" in prompt.lower()

    @patch('core.session_execution.create_logging_wrapper')
    @patch('core.session_execution.LLMProviderFactory')
    @patch('core.session_execution.CLIInterface')
    @patch('core.session_execution.ReportService')
    def test_build_verification_prompt(self, mock_report_class, mock_cli_class,
                                       mock_factory, mock_wrapper_func,
                                       app_config, mock_db_connection, session_id):
        """Test building verification prompt."""
        session = SessionState(session_id)
        execution = SessionExecution(app_config, mock_db_connection)
        mock_wrapper_func.side_effect = [Mock(), Mock()]
        mock_factory.create.return_value = Mock()
        execution.initialize_for_session(session)

        prompt = execution.build_verification_prompt(
            session, "insights", "record_count", "There are 100 records"
        )

        assert isinstance(prompt, str)
        assert "insights" in prompt
        assert "record_count" in prompt
        assert "100 records" in prompt
        assert "verify" in prompt.lower() or "SQL" in prompt


# ============================================================================
# Tool Call Logging Tests
# ============================================================================

@pytest.mark.unit
class TestToolCallLogging:
    """Tests for log_tool_call method."""

    @patch('core.session_execution.create_logging_wrapper')
    @patch('core.session_execution.LLMProviderFactory')
    @patch('core.session_execution.CLIInterface')
    @patch('core.session_execution.ReportService')
    def test_log_tool_call(self, mock_report_class, mock_cli_class,
                          mock_factory, mock_wrapper_func,
                          app_config, mock_db_connection, session_id):
        """Test logging a tool call."""
        session = SessionState(session_id)
        session.add_iteration(1, "test prompt")

        execution = SessionExecution(app_config, mock_db_connection)
        mock_wrapper_func.side_effect = [Mock(), Mock()]
        mock_factory.create.return_value = Mock()
        execution.initialize_for_session(session)

        execution.log_tool_call(
            session_state=session,
            iteration=1,
            tool_name="execute_sql",
            input_data={"query": "SELECT * FROM entities"},
            output_data="Results...",
            execution_time=0.5
        )

        assert len(session.iterations[0].tool_calls) == 1
        tool_call = session.iterations[0].tool_calls[0]
        assert tool_call.tool == "execute_sql"
        assert tool_call.input == {"query": "SELECT * FROM entities"}
        assert tool_call.output == "Results..."
        assert tool_call.execution_time == 0.5

    @patch('core.session_execution.create_logging_wrapper')
    @patch('core.session_execution.LLMProviderFactory')
    @patch('core.session_execution.CLIInterface')
    @patch('core.session_execution.ReportService')
    def test_log_tool_call_with_callback(self, mock_report_class, mock_cli_class,
                                        mock_factory, mock_wrapper_func,
                                        app_config, mock_db_connection, session_id):
        """Test that save callback is triggered after logging tool call."""
        session = SessionState(session_id)
        session.add_iteration(1, "test prompt")

        callback = Mock()
        execution = SessionExecution(app_config, mock_db_connection, save_callback=callback)
        mock_wrapper_func.side_effect = [Mock(), Mock()]
        mock_factory.create.return_value = Mock()
        execution.initialize_for_session(session)

        execution.log_tool_call(
            session_state=session,
            iteration=1,
            tool_name="memory",
            input_data={"action": "update", "key": "insights", "value": "test"},
            output_data="Updated",
            execution_time=0.01
        )

        # Callback should be called
        callback.assert_called()


# ============================================================================
# LoggingWrapper Tests
# ============================================================================

@pytest.mark.unit
class TestLoggingWrapper:
    """Tests for create_logging_wrapper function and LoggingWrapper class."""

    def test_create_logging_wrapper_sql_tool(self, app_config, mock_db_connection, session_id):
        """Test creating logging wrapper for SQL tool."""
        session = SessionState(session_id)
        execution = SessionExecution(app_config, mock_db_connection)
        sql_tool = ExecuteSQLTool(mock_db_connection, verbose=False)

        wrapper = create_logging_wrapper(sql_tool, execution, session)

        assert wrapper.name == "execute_sql"
        assert hasattr(wrapper, 'call')

    def test_create_logging_wrapper_memory_tool(self, app_config, mock_db_connection, session_id):
        """Test creating logging wrapper for Memory tool."""
        session = SessionState(session_id)
        execution = SessionExecution(app_config, mock_db_connection)
        memory_tool = MemoryTool(session, verbose=False)

        wrapper = create_logging_wrapper(memory_tool, execution, session)

        assert wrapper.name == "memory"
        assert hasattr(wrapper, 'call')

    def test_logging_wrapper_calls_original_tool(self, app_config, mock_db_connection, session_id):
        """Test that wrapper calls original tool."""
        session = SessionState(session_id)
        session.add_iteration(1, "test")
        execution = SessionExecution(app_config, mock_db_connection)

        mock_db_connection.execute_query.return_value = "Entity | Count\n---\nEntity1 | 10"
        sql_tool = ExecuteSQLTool(mock_db_connection, verbose=False)

        wrapper = create_logging_wrapper(sql_tool, execution, session)
        result = wrapper.call(query="SELECT * FROM entities")

        assert "Entity" in result
        mock_db_connection.execute_query.assert_called_once()

    def test_logging_wrapper_logs_to_session(self, app_config, mock_db_connection, session_id):
        """Test that wrapper logs calls to session."""
        session = SessionState(session_id)
        session.add_iteration(1, "test")
        execution = SessionExecution(app_config, mock_db_connection)

        mock_db_connection.execute_query.return_value = "Results"
        sql_tool = ExecuteSQLTool(mock_db_connection, verbose=False)

        wrapper = create_logging_wrapper(sql_tool, execution, session)
        wrapper.call(query="SELECT COUNT(*) FROM entities")

        # Check tool call was logged
        assert len(session.iterations[0].tool_calls) == 1
        assert session.iterations[0].tool_calls[0].tool == "execute_sql"


# ============================================================================
# Handle User Input Tests
# ============================================================================

@pytest.mark.unit
class TestHandleUserInput:
    """Tests for handle_user_input method."""

    @patch('core.session_execution.create_logging_wrapper')
    @patch('core.session_execution.LLMProviderFactory')
    @patch('core.session_execution.CLIInterface')
    @patch('core.session_execution.ReportService')
    def test_handle_user_input_normal(self, mock_report_class, mock_cli_class,
                                      mock_factory, mock_wrapper_func,
                                      app_config, mock_db_connection, session_id):
        """Test handling normal user input."""
        session = SessionState(session_id)
        execution = SessionExecution(app_config, mock_db_connection)
        mock_wrapper_func.side_effect = [Mock(), Mock()]
        mock_factory.create.return_value = Mock()
        execution.initialize_for_session(session)

        # Mock CLI to return user input
        execution.cli_interface.get_user_input = Mock(return_value=("Continue analysis", False))

        user_input, should_report = execution.handle_user_input(session)

        assert user_input == "Continue analysis"
        assert should_report == False

    @patch('core.session_execution.create_logging_wrapper')
    @patch('core.session_execution.LLMProviderFactory')
    @patch('core.session_execution.CLIInterface')
    @patch('core.session_execution.ReportService')
    def test_handle_user_input_report_requested(self, mock_report_class, mock_cli_class,
                                                mock_factory, mock_wrapper_func,
                                                app_config, mock_db_connection, session_id):
        """Test handling user requesting report."""
        session = SessionState(session_id)
        execution = SessionExecution(app_config, mock_db_connection)
        mock_wrapper_func.side_effect = [Mock(), Mock()]
        mock_factory.create.return_value = Mock()
        execution.initialize_for_session(session)

        # Mock CLI to return report request
        execution.cli_interface.get_user_input = Mock(return_value=("report", True))

        user_input, should_report = execution.handle_user_input(session)

        assert user_input == "report"
        assert should_report == True


# ============================================================================
# Generate Report Tests
# ============================================================================

@pytest.mark.unit
class TestGenerateReport:
    """Tests for generate_report method."""

    @patch('core.session_execution.create_logging_wrapper')
    @patch('core.session_execution.LLMProviderFactory')
    @patch('core.session_execution.CLIInterface')
    @patch('core.session_execution.ReportService')
    def test_generate_report(self, mock_report_class, mock_cli_class,
                            mock_factory, mock_wrapper_func,
                            app_config, mock_db_connection, session_id):
        """Test generating a report."""
        session = SessionState(session_id)
        execution = SessionExecution(app_config, mock_db_connection)
        mock_wrapper_func.side_effect = [Mock(), Mock()]
        mock_factory.create.return_value = Mock()
        execution.initialize_for_session(session)

        # Mock report service
        from pathlib import Path
        mock_path = Path("/tmp/report.txt")
        execution.report_service.generate_report = Mock(
            return_value=("Report content here", mock_path)
        )

        content, path_str = execution.generate_report(session, "Analysis Summary")

        assert content == "Report content here"
        assert "/tmp/report.txt" in path_str
        execution.report_service.generate_report.assert_called_once_with("Analysis Summary")


# ============================================================================
# Helper Method Tests
# ============================================================================

@pytest.mark.unit
class TestHelperMethods:
    """Tests for helper logging methods."""

    @patch('core.session_execution.create_logging_wrapper')
    @patch('core.session_execution.LLMProviderFactory')
    @patch('core.session_execution.CLIInterface')
    @patch('core.session_execution.ReportService')
    def test_log_iteration_start(self, mock_report_class, mock_cli_class,
                                 mock_factory, mock_wrapper_func,
                                 app_config, mock_db_connection, session_id, capsys):
        """Test logging iteration start."""
        session = SessionState(session_id)
        execution = SessionExecution(app_config, mock_db_connection)
        mock_wrapper_func.side_effect = [Mock(), Mock()]
        mock_factory.create.return_value = Mock()
        execution.initialize_for_session(session)

        execution._log_iteration_start(5)

        captured = capsys.readouterr()
        assert "ITERATION 5" in captured.out or "Iteration 5" in captured.out

    @patch('core.session_execution.create_logging_wrapper')
    @patch('core.session_execution.LLMProviderFactory')
    @patch('core.session_execution.CLIInterface')
    @patch('core.session_execution.ReportService')
    def test_log_iteration_end(self, mock_report_class, mock_cli_class,
                               mock_factory, mock_wrapper_func,
                               app_config, mock_db_connection, session_id, capsys):
        """Test logging iteration end."""
        session = SessionState(session_id)
        execution = SessionExecution(app_config, mock_db_connection)
        mock_wrapper_func.side_effect = [Mock(), Mock()]
        mock_factory.create.return_value = Mock()
        execution.initialize_for_session(session)

        execution._log_iteration_end(3)

        captured = capsys.readouterr()
        assert "3" in captured.out or "COMPLETED" in captured.out
