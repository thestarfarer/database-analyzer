"""
End-to-End Tests for CLI Workflows

Tests complete user workflows through the main.py CLI interface.
"""

import pytest
import subprocess
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


# ============================================================================
# CLI Argument Parsing Tests
# ============================================================================

@pytest.mark.e2e
class TestCLIArgumentParsing:
    """Tests for CLI argument parsing and validation."""

    @patch('sys.argv', ['main.py', '--list-sessions'])
    def test_list_sessions_argument(self):
        """Test --list-sessions argument."""
        from main import main
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument('--list-sessions', action='store_true')

        args = parser.parse_args(['--list-sessions'])

        assert args.list_sessions is True

    @patch('sys.argv', ['main.py', '--task', 'Analyze records'])
    def test_task_argument(self):
        """Test --task argument."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument('--task')

        args = parser.parse_args(['--task', 'Analyze records'])

        assert args.task == 'Analyze records'

    @patch('sys.argv', ['main.py', '--continue-session', 'output/session_123.json'])
    def test_continue_session_argument(self):
        """Test --continue-session argument."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument('--continue-session')

        args = parser.parse_args(['--continue-session', 'output/session_123.json'])

        assert args.continue_session == 'output/session_123.json'


# ============================================================================
# New Session Workflow Tests
# ============================================================================

@pytest.mark.e2e
class TestNewSessionWorkflow:
    """Tests for creating new sessions via CLI."""

    @patch('core.session_manager.SessionExecution')
    @patch('sys.argv', ['main.py', '--task', 'Test task', '--max-iterations', '1'])
    def test_new_session_with_task(self, mock_execution_class, test_output_dir, test_db_config, monkeypatch):
        """Test creating a new session with --task argument."""
        # Setup mocks
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        # Monkeypatch output directory
        monkeypatch.setenv('OUTPUT_DIR', str(test_output_dir))

        # This would normally run the full main(), but we'll test components
        from config.settings import AppConfig, LLMConfig
        from database.connection import MSSQLConnection
        from core.session_manager import SessionManager

        config = AppConfig(
            db_config=test_db_config,
            llm_config=LLMConfig.default(),
            output_dir=test_output_dir,
            max_iterations=1
        )

        # Mock database
        with patch.object(MSSQLConnection, '__init__', return_value=None):
            mock_db = MagicMock()

            manager = SessionManager(config, mock_db)
            session = manager.start_session(first_user_input="Test task")

            assert session is not None
            assert session.metadata.session_id is not None


# ============================================================================
# Session Continuation Workflow Tests
# ============================================================================

@pytest.mark.e2e
class TestSessionContinuationWorkflow:
    """Tests for resuming existing sessions."""

    @patch('core.session_manager.SessionExecution')
    def test_continue_session_workflow(self, mock_execution_class, sample_session_file, test_output_dir, test_db_config):
        """Test continuing from existing session file."""
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        from config.settings import AppConfig, LLMConfig
        from core.session_manager import SessionManager

        config = AppConfig(
            db_config=test_db_config,
            llm_config=LLMConfig.default(),
            output_dir=test_output_dir
        )

        mock_db = MagicMock()

        manager = SessionManager(config, mock_db)
        session = manager.start_session(
            session_file=sample_session_file,
            first_user_input="Continue"
        )

        assert session is not None
        assert manager.resume_with_task == "Continue"

    @patch('core.session_manager.SessionExecution')
    def test_latest_session_workflow(self, mock_execution_class, multiple_session_files, test_output_dir, test_db_config):
        """Test continuing from latest session."""
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        from config.settings import AppConfig, LLMConfig
        from core.session_manager import SessionManager

        config = AppConfig(
            db_config=test_db_config,
            llm_config=LLMConfig.default(),
            output_dir=test_output_dir
        )

        mock_db = MagicMock()

        manager = SessionManager(config, mock_db)

        # Find latest
        latest_file = manager.find_latest_session()

        assert latest_file is not None

        # Continue from latest
        session = manager.start_session(session_file=latest_file)

        assert session is not None


# ============================================================================
# List Sessions Workflow Tests
# ============================================================================

@pytest.mark.e2e
class TestListSessionsWorkflow:
    """Tests for listing sessions."""

    @patch('core.session_manager.SessionExecution')
    def test_list_sessions_workflow(self, mock_execution_class, multiple_session_files, test_output_dir, test_db_config):
        """Test listing all sessions."""
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        from config.settings import AppConfig, LLMConfig
        from core.session_manager import SessionManager

        config = AppConfig(
            db_config=test_db_config,
            llm_config=LLMConfig.default(),
            output_dir=test_output_dir
        )

        mock_db = MagicMock()

        manager = SessionManager(config, mock_db)

        sessions = manager.list_available_sessions()

        assert len(sessions) == 3
        assert all('session_id' in s for s in sessions)


# ============================================================================
# Memory Verification Workflow Tests
# ============================================================================

@pytest.mark.e2e
class TestMemoryVerificationWorkflow:
    """Tests for memory verification workflow."""

    @patch('core.session_manager.SessionExecution')
    @patch('services.memory_verification.MemoryVerificationCoordinator')
    def test_verify_memory_workflow(self, mock_verifier_class, mock_execution_class,
                                    sample_session_with_memory, test_output_dir, test_db_config):
        """Test verifying a memory item via CLI."""
        # Setup mocks
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        mock_verifier = MagicMock()
        mock_verifier.verify_memory_item.return_value = {
            'verified': True,
            'confidence': 'high',
            'recommendation': 'keep',
            'reasoning': 'Data is accurate',
            'evidence': 'SQL query confirmed count'
        }
        mock_verifier_class.return_value = mock_verifier

        from config.settings import AppConfig, LLMConfig
        from core.session_manager import SessionManager
        from core.session_persistence import SessionPersistence

        config = AppConfig(
            db_config=test_db_config,
            llm_config=LLMConfig.default(),
            output_dir=test_output_dir
        )

        # Save session
        persistence = SessionPersistence(test_output_dir)
        session_file = persistence.save_session(sample_session_with_memory)

        mock_db = MagicMock()

        manager = SessionManager(config, mock_db)

        # Load session
        session_state = persistence.load_session(session_file)

        # Verify memory
        result = manager.verify_memory_item(
            session_state,
            category='insights',
            key='record_count'
        )

        assert result['verified'] is True
        assert 'reasoning' in result


# ============================================================================
# Signal Handling Tests
# ============================================================================

@pytest.mark.e2e
class TestSignalHandling:
    """Tests for graceful shutdown on signals."""

    def test_keyboard_interrupt_handling(self):
        """Test that KeyboardInterrupt is handled gracefully."""
        from main import graceful_shutdown
        import signal

        # Should raise KeyboardInterrupt
        with pytest.raises(KeyboardInterrupt):
            graceful_shutdown(signal.SIGINT, None)

    def test_sigterm_handling(self):
        """Test that SIGTERM is handled gracefully."""
        from main import graceful_shutdown
        import signal

        # Should raise KeyboardInterrupt (converted from SIGTERM)
        with pytest.raises(KeyboardInterrupt):
            graceful_shutdown(signal.SIGTERM, None)


# ============================================================================
# Complete User Journey Tests
# ============================================================================

@pytest.mark.e2e
@pytest.mark.slow
class TestCompleteUserJourneys:
    """Tests for complete user workflows from start to finish."""

    @patch('core.session_manager.SessionExecution')
    def test_complete_analysis_journey(self, mock_execution_class, test_output_dir, test_db_config):
        """Test complete journey: create -> analyze -> save -> resume."""
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        from config.settings import AppConfig, LLMConfig
        from core.session_manager import SessionManager

        config = AppConfig(
            db_config=test_db_config,
            llm_config=LLMConfig.default(),
            output_dir=test_output_dir,
            max_iterations=2
        )

        mock_db = MagicMock()

        # Step 1: Create new session
        manager1 = SessionManager(config, mock_db)
        session1 = manager1.start_session(first_user_input="Analyze records")

        session_id = session1.metadata.session_id

        # Step 2: Save session
        session_file = manager1.save_session()

        # Step 3: Finalize
        manager1.finalize_current_session()

        # Step 4: Resume in new manager instance
        manager2 = SessionManager(config, mock_db)
        session2 = manager2.start_session(
            session_file=session_file,
            first_user_input="Continue analysis"
        )

        # Verify
        assert session2.metadata.session_id == session_id
        assert manager2.resume_with_task == "Continue analysis"

    @patch('core.session_manager.SessionExecution')
    def test_error_recovery_journey(self, mock_execution_class, test_output_dir, test_db_config):
        """Test recovery from interrupted session."""
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        from config.settings import AppConfig, LLMConfig
        from core.session_manager import SessionManager
        from core.session_state import SessionState

        config = AppConfig(
            db_config=test_db_config,
            llm_config=LLMConfig.default(),
            output_dir=test_output_dir
        )

        # Create interrupted session
        session = SessionState("interrupted_session")
        iter1 = session.add_iteration(1, "Prompt 1", "Task 1")
        iter1.llm_response = "Completed"
        iter1.end_time = 0

        # Add incomplete iteration
        session.add_iteration(2, "Prompt 2", "Task 2")

        # Save
        from core.session_persistence import SessionPersistence
        persistence = SessionPersistence(test_output_dir)
        session_file = persistence.save_session(session)

        # Resume
        mock_db = MagicMock()
        manager = SessionManager(config, mock_db)

        resumed_session = manager.start_session(session_file=session_file)

        # Should have cleaned up incomplete iteration
        resume_point = resumed_session.get_resume_point()

        assert resume_point.iteration == 2
        assert len(resumed_session.iterations) == 1  # Incomplete removed
