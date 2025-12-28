"""
Integration Tests for Preset System with Core Components

Tests the integration of the preset system with:
- SessionExecution for prompt building
- ReportService for report generation
- End-to-end session workflow with presets
"""

import pytest
import json
import time
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from core.session_execution import SessionExecution
from core.session_state import SessionState, SessionMetadata
from services.report_service import ReportService
from services.prompt_preset_manager import PromptPresetManager


@pytest.mark.integration
class TestPresetIntegration:
    """Test suite for preset system integration with core components."""

    # =========================================================================
    # SessionExecution Integration Tests
    # =========================================================================

    def test_session_execution_with_preset(self, app_config_with_preset, sample_preset_file,
                                           mock_db_connection, mock_llm_assistant):
        """Test SessionExecution initialization and prompt building with preset."""
        # Initialize SessionExecution with preset config
        session_exec = SessionExecution(app_config_with_preset, mock_db_connection)

        # Verify preset manager was initialized
        assert session_exec.prompt_preset_manager is not None
        assert session_exec.prompt_preset_manager.active_preset is not None

        # Test base prompt building with preset
        base_prompt = session_exec.build_base_prompt()

        # Should contain content from preset
        assert "Test database schema" in base_prompt
        assert "Test tool description" in base_prompt
        assert "Test domain context" in base_prompt
        assert "Test task instructions" in base_prompt

        # Variables should be replaced
        assert "{{DB_RESULT_LIMIT}}" not in base_prompt
        assert "{{CURRENT_DATE}}" not in base_prompt
        assert str(mock_db_connection.result_limit) in base_prompt
        assert datetime.now().strftime("%Y-%m-%d") in base_prompt

    def test_session_execution_fallback(self, app_config, mock_db_connection, mock_llm_assistant):
        """Test SessionExecution falls back to hardcoded prompts when preset unavailable."""
        # Create config with non-existent preset
        app_config.prompt_preset_name = "nonexistent"
        app_config.prompts_dir = Path("/tmp/nonexistent_dir")

        # Initialize - should not crash
        session_exec = SessionExecution(app_config, mock_db_connection)

        # Preset manager should exist but with no active preset (fallback)
        assert session_exec.prompt_preset_manager is not None
        assert session_exec.prompt_preset_manager.active_preset is None

        # Should still be able to build prompts (using hardcoded)
        base_prompt = session_exec.build_base_prompt()
        assert "Database schema" in base_prompt  # Part of hardcoded prompt
        assert "schema not configured" in base_prompt  # Generic fallback content

    def test_session_execution_variable_replacement(self, app_config_with_preset, sample_preset_file,
                                                    mock_db_connection, sample_session):
        """Test that all prompt builders correctly replace variables."""
        session_exec = SessionExecution(app_config_with_preset, mock_db_connection)
        session_state = sample_session  # sample_session is already a SessionState object

        # Test 1: Base prompt variables
        base_prompt = session_exec.build_base_prompt()
        assert str(mock_db_connection.result_limit) in base_prompt
        assert datetime.now().strftime("%Y-%m-%d") in base_prompt

        # Test 2: Verification prompt variables
        verification_prompt = session_exec.build_verification_prompt(
            session_state, "insights", "test_key", "test_value"
        )
        assert "insights" in verification_prompt
        assert "test_key" in verification_prompt
        assert "test_value" in verification_prompt

        # Test 3: Continuation prompt variables
        continuation_prompt = session_exec.build_continuation_prompt(session_state)
        assert str(session_state.metadata.current_iteration) in continuation_prompt

    # =========================================================================
    # ReportService Integration Tests
    # =========================================================================

    @patch('services.report_service.LLMProviderFactory')
    def test_report_service_with_preset(self, mock_factory, app_config_with_preset, sample_preset_file,
                                       sample_session):
        """Test ReportService generates report using preset templates."""
        from llm import LLMResponse
        # Initialize session state
        session_state = sample_session  # sample_session is already a SessionState object

        # Initialize preset manager
        preset_manager = PromptPresetManager(app_config_with_preset.prompts_dir, "test_preset")

        # Mock provider
        mock_response = LLMResponse(content="Generated report content")
        mock_provider = Mock()
        mock_provider.run_simple.return_value = mock_response
        mock_factory.create.return_value = mock_provider

        # Initialize report service with preset
        report_service = ReportService(
            config=app_config_with_preset,
            session_state=session_state,
            output_dir=app_config_with_preset.output_dir,
            prompt_preset_manager=preset_manager
        )

        # Generate report
        report_content, report_path = report_service.generate_report("Test task description")

        # Verify report was generated
        assert "Generated report content" in report_content
        assert report_path.exists()
        assert report_path.name.startswith("report_") and report_path.name.endswith(".txt")

        # Verify prompt used preset template
        call_args = mock_provider.run_simple.call_args
        messages = call_args[1]['messages']
        prompt = messages[0].content

        # Should contain preset template content with replaced variables
        assert "Test task description" in prompt  # {{TASK_DESCRIPTION}} replaced

    @patch('services.report_service.LLMProviderFactory')
    def test_report_service_fallback(self, mock_factory, sample_session, app_config):
        """Test ReportService falls back to hardcoded prompt when preset unavailable."""
        from llm import LLMResponse
        # Initialize session state
        session_state = sample_session  # sample_session is already a SessionState object

        # Mock provider
        mock_response = LLMResponse(content="Generated report content")
        mock_provider = Mock()
        mock_provider.run_simple.return_value = mock_response
        mock_factory.create.return_value = mock_provider

        # Initialize report service without preset
        report_service = ReportService(
            config=app_config,
            session_state=session_state,
            output_dir=app_config.output_dir,
            prompt_preset_manager=None  # No preset manager
        )

        # Generate report
        report_content, report_path = report_service.generate_report("Test task")

        # Should still work with hardcoded prompt
        assert "Generated report content" in report_content
        assert report_path.exists()

        # Verify hardcoded prompt was used
        call_args = mock_provider.run_simple.call_args
        messages = call_args[1]['messages']
        prompt = messages[0].content

        # Should contain hardcoded prompt markers
        assert "comprehensive report" in prompt.lower()

    # =========================================================================
    # End-to-End Integration Tests
    # =========================================================================

    @patch('core.session_execution.LLMProviderFactory')
    def test_full_session_with_preset(self, mock_factory, app_config_with_preset, sample_preset_file,
                                      mock_db_connection, mock_llm_assistant):
        """Test complete session workflow with custom preset from CLI to report."""
        from llm import LLMResponse

        # Initialize SessionManager with preset config
        from core.session_manager import SessionManager
        session_manager = SessionManager(app_config_with_preset, mock_db_connection)

        # Mock provider response
        mock_llm_response = LLMResponse(content="Analysis complete")
        mock_provider = Mock()
        mock_provider.run.return_value = iter([mock_llm_response])
        mock_factory.create.return_value = mock_provider

        # Create new session
        session_state = session_manager.start_session(first_user_input="Analyze data with preset")
        assert session_state is not None

        # Run an iteration (would normally be in a loop)
        session_exec = SessionExecution(
            app_config_with_preset,
            mock_db_connection,
            save_callback=lambda: session_manager.persistence.save_session(session_state)
        )

        # Initialize for session - provider is already mocked via factory
        session_exec.initialize_for_session(session_state)

        # Build prompts - should use preset
        base_prompt = session_exec.build_base_prompt()
        assert "Test database schema" in base_prompt

        # Add iteration to session state
        from core.session_state import Iteration
        iteration = Iteration(
            iteration=1,
            start_time=time.time(),
            user_input="Continue analysis"
        )
        session_state.iterations.append(iteration)

        # Execute iteration
        user_input = "Continue analysis"
        prompt = f"{base_prompt}\n\nUser: {user_input}"

        session_exec.execute_iteration(
            session_state=session_state,
            iteration_num=1,
            prompt=prompt,
            user_input=user_input
        )

        # Verify iteration was recorded
        assert len(session_state.iterations) == 1
        assert session_state.iterations[0].llm_response == "Analysis complete"

        # Generate final report with preset (skip in this test - focus on session workflow)
        # Report generation is tested separately in test_report_service_with_preset
        assert len(session_state.iterations) >= 1

    def test_resume_session_with_preset(self, app_config_with_preset, sample_preset_file,
                                        mock_db_connection, sample_session):
        """Test that preset configuration is preserved when resuming a session."""
        # Create session manager with preset
        from core.session_manager import SessionManager
        session_manager = SessionManager(app_config_with_preset, mock_db_connection)

        # Create and save a session
        session_data = sample_session.to_dict()  # Convert SessionState to dict
        session_data['session_metadata']['session_id'] = '20250101_120000'
        session_state = SessionState.from_dict(session_data)

        # Save session
        session_file = session_manager.persistence.save_session(session_state)
        assert session_file.exists()

        # Simulate resume by loading session
        loaded_state = session_manager.persistence.load_session(session_file)
        assert loaded_state.metadata.session_id == '20250101_120000'

        # Initialize new SessionExecution with same preset config
        session_exec = SessionExecution(app_config_with_preset, mock_db_connection)

        # Should still use preset for prompt building
        continuation_prompt = session_exec.build_continuation_prompt(loaded_state)

        # Should contain preset template content
        assert "Test database schema" in continuation_prompt
        # Should have replaced iteration variables
        assert str(loaded_state.metadata.current_iteration) in continuation_prompt