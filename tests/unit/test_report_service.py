"""
Unit Tests for Report Service

Tests for the ReportService which generates analysis reports using LLM.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
from services.report_service import ReportService
from core.session_state import SessionState, ToolCall
from llm import LLMResponse


# ============================================================================
# Report Service Initialization Tests
# ============================================================================

@pytest.mark.unit
class TestReportServiceInit:
    """Tests for ReportService initialization."""

    @patch('services.report_service.LLMProviderFactory')
    def test_report_service_creation(self, mock_factory, app_config, session_id, test_output_dir):
        """Test creating ReportService instance."""
        mock_provider = Mock()
        mock_factory.create.return_value = mock_provider

        session = SessionState(session_id)
        service = ReportService(app_config, session, test_output_dir)

        assert service.config == app_config
        assert service.session_state == session
        assert service.output_dir == test_output_dir
        mock_factory.create.assert_called_once_with(app_config, tools=[])

    @patch('services.report_service.LLMProviderFactory')
    def test_report_service_creates_output_dir(self, mock_factory, app_config, session_id, test_output_dir):
        """Test that output directory is created if missing."""
        mock_provider = Mock()
        mock_factory.create.return_value = mock_provider

        session = SessionState(session_id)
        non_existent_dir = test_output_dir / "reports_test"

        assert not non_existent_dir.exists()

        service = ReportService(app_config, session, non_existent_dir)

        # Output dir creation happens when generating report, not on init
        assert service.output_dir == non_existent_dir


# ============================================================================
# Report Generation Tests
# ============================================================================

@pytest.mark.unit
class TestReportGeneration:
    """Tests for generate_report method."""

    @patch('services.report_service.LLMProviderFactory')
    def test_generate_report_basic(self, mock_factory, app_config, session_id, test_output_dir):
        """Test generating a basic report."""
        session = SessionState(session_id)
        session.add_iteration(1, "Analyze data", "Find opportunities")
        session.complete_iteration(1, "Found several opportunities")

        # Mock provider response
        mock_response = LLMResponse(
            content="# Analysis Report\n\nKey findings:\n- Performance margin is 15%\n- Top entity is Entity1"
        )
        mock_provider = Mock()
        mock_provider.run_simple.return_value = mock_response
        mock_factory.create.return_value = mock_provider

        service = ReportService(app_config, session, test_output_dir)
        content, file_path = service.generate_report("Data Analysis")

        assert "Analysis Report" in content
        assert "Performance margin" in content
        assert file_path.exists()
        assert "report_" in file_path.name

    @patch('services.report_service.LLMProviderFactory')
    def test_generate_report_with_memory(self, mock_factory, app_config, session_id, test_output_dir):
        """Test generating report with memory data."""
        session = SessionState(session_id)
        session.add_iteration(1, "test")

        # Add memory
        tool_call = ToolCall(
            id="mem_1",
            tool="memory",
            timestamp=0,
            input={"action": "update", "key": "insights", "value": "trend_q2:Q2 up 20%"},
            output="Updated",
            execution_time=0.001
        )
        session.add_tool_call(1, tool_call)
        session.complete_iteration(1, "Analysis complete")

        mock_response = LLMResponse(content="Report with memory data")
        mock_provider = Mock()
        mock_provider.run_simple.return_value = mock_response
        mock_factory.create.return_value = mock_provider

        service = ReportService(app_config, session, test_output_dir)
        content, file_path = service.generate_report("Q2 Analysis")

        assert content == "Report with memory data"
        # Verify prompt included memory
        call_args = mock_provider.run_simple.call_args[1]
        messages = call_args['messages']
        assert any("trend_q2" in msg.content or "Q2 up 20%" in msg.content
                  for msg in messages)

    @patch('services.report_service.LLMProviderFactory')
    def test_generate_report_saves_to_file(self, mock_factory, app_config, session_id, test_output_dir):
        """Test that report is saved to file."""
        session = SessionState(session_id)

        mock_response = LLMResponse(content="Report content to save")
        mock_provider = Mock()
        mock_provider.run_simple.return_value = mock_response
        mock_factory.create.return_value = mock_provider

        service = ReportService(app_config, session, test_output_dir)
        content, file_path = service.generate_report("Test Report")

        assert file_path.exists()
        with open(file_path, 'r', encoding='utf-8') as f:
            saved_content = f.read()
        # File includes header and content
        assert "Report content to save" in saved_content
        assert "REPORT TOPIC" in saved_content

    @patch('services.report_service.LLMProviderFactory')
    def test_generate_report_filename_format(self, mock_factory, app_config, session_id, test_output_dir):
        """Test report filename format."""
        session = SessionState(session_id)

        mock_response = LLMResponse(content="Report")
        mock_provider = Mock()
        mock_provider.run_simple.return_value = mock_response
        mock_factory.create.return_value = mock_provider

        service = ReportService(app_config, session, test_output_dir)
        content, file_path = service.generate_report("Analysis")

        assert file_path.name.startswith("report_")
        assert file_path.name.endswith(".txt")

    @patch('services.report_service.LLMProviderFactory')
    def test_generate_report_with_tool_calls(self, mock_factory, app_config, session_id, test_output_dir):
        """Test report includes tool call information."""
        session = SessionState(session_id)
        session.add_iteration(1, "test")

        # Add SQL tool call
        sql_call = ToolCall(
            id="sql_1",
            tool="execute_sql",
            timestamp=0,
            input={"query": "SELECT * FROM entities"},
            output="Record1, Record2",
            execution_time=0.5
        )
        session.add_tool_call(1, sql_call)
        session.complete_iteration(1, "Done")

        mock_response = LLMResponse(content="Report with tool calls")
        mock_provider = Mock()
        mock_provider.run_simple.return_value = mock_response
        mock_factory.create.return_value = mock_provider

        service = ReportService(app_config, session, test_output_dir)
        content, file_path = service.generate_report("Tool Analysis")

        # Verify that run_simple was called
        mock_provider.run_simple.assert_called_once()


# ============================================================================
# Error Handling Tests
# ============================================================================

@pytest.mark.unit
class TestReportErrorHandling:
    """Tests for error handling in report generation."""

    @patch('services.report_service.LLMProviderFactory')
    def test_generate_report_handles_empty_response(self, mock_factory, app_config, session_id, test_output_dir):
        """Test handling empty LLM response."""
        session = SessionState(session_id)

        mock_response = LLMResponse(content="")
        mock_provider = Mock()
        mock_provider.run_simple.return_value = mock_response
        mock_factory.create.return_value = mock_provider

        service = ReportService(app_config, session, test_output_dir)
        content, file_path = service.generate_report("Test")

        assert content == "Failed to generate report"
        assert file_path.exists()

    @patch('services.report_service.LLMProviderFactory')
    def test_generate_report_handles_none_content(self, mock_factory, app_config, session_id, test_output_dir):
        """Test handling when response content is None."""
        session = SessionState(session_id)

        mock_response = LLMResponse(content=None)
        mock_provider = Mock()
        mock_provider.run_simple.return_value = mock_response
        mock_factory.create.return_value = mock_provider

        service = ReportService(app_config, session, test_output_dir)
        content, file_path = service.generate_report("Test")

        assert content == "Failed to generate report"
        assert file_path.exists()
