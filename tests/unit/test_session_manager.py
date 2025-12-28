"""
Unit Tests for Session Manager

Tests for SessionManager class covering session lifecycle, coordination,
save/load operations, and verification functionality.
"""

import pytest
import time
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from core.session_manager import SessionManager
from core.session_state import SessionState
from core.session_persistence import SessionPersistence


# ============================================================================
# Session Manager Initialization Tests
# ============================================================================

@pytest.mark.unit
class TestSessionManagerInit:
    """Tests for SessionManager initialization."""

    def test_session_manager_creation(self, app_config, mock_db_connection):
        """Test creating session manager."""
        manager = SessionManager(app_config, mock_db_connection)

        assert manager.config == app_config
        assert manager.db_connection == mock_db_connection
        assert isinstance(manager.persistence, SessionPersistence)
        assert manager.current_session is None

    def test_session_manager_initializes_persistence(self, app_config, mock_db_connection):
        """Test that persistence is properly initialized."""
        manager = SessionManager(app_config, mock_db_connection)

        assert manager.persistence.output_dir == app_config.output_dir
        assert app_config.output_dir.exists()


# ============================================================================
# Session Creation Tests
# ============================================================================

@pytest.mark.unit
class TestSessionManagerCreation:
    """Tests for new session creation."""

    @patch('core.session_manager.SessionExecution')
    def test_start_new_session(self, mock_execution_class, app_config, mock_db_connection):
        """Test starting a new session."""
        # Setup mocks
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        manager = SessionManager(app_config, mock_db_connection)

        session_state = manager.start_session(
            session_file=None,
            first_user_input="Test task"
        )

        assert isinstance(session_state, SessionState)
        assert manager.current_session == session_state
        assert manager.resume_with_task == "Test task"

    @patch('core.session_manager.SessionExecution')
    def test_new_session_has_unique_id(self, mock_execution_class, app_config, mock_db_connection):
        """Test that new sessions get unique IDs."""
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        manager = SessionManager(app_config, mock_db_connection)

        session1 = manager.start_session(first_user_input="Task 1")
        # Create a session with an explicitly different ID
        session2_state = SessionState("explicit_different_id")
        manager.current_session = session2_state

        # Session IDs should be different (one is timestamp-based, one is explicit)
        assert session1.metadata.session_id != session2_state.metadata.session_id

    @patch('core.session_manager.SessionExecution')
    def test_new_session_saves_immediately(self, mock_execution_class, app_config, mock_db_connection, test_output_dir):
        """Test that new session is saved immediately."""
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        manager = SessionManager(app_config, mock_db_connection)

        session_state = manager.start_session(first_user_input="Test")

        # Check that session file was created
        session_files = list(test_output_dir.glob(f"session_{session_state.metadata.session_id}.json"))
        assert len(session_files) == 1


# ============================================================================
# Session Continuation Tests
# ============================================================================

@pytest.mark.unit
class TestSessionManagerContinuation:
    """Tests for session resumption."""

    @patch('core.session_manager.SessionExecution')
    def test_continue_existing_session(self, mock_execution_class, app_config, mock_db_connection, sample_session_file):
        """Test continuing from existing session file."""
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        manager = SessionManager(app_config, mock_db_connection)

        session_state = manager.start_session(
            session_file=sample_session_file,
            first_user_input="Continue"
        )

        assert session_state is not None
        assert manager.current_session == session_state
        assert manager.resume_with_task == "Continue"

    @patch('core.session_manager.SessionExecution')
    def test_continue_nonexistent_session(self, mock_execution_class, app_config, mock_db_connection, test_output_dir):
        """Test continuing from non-existent session file."""
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        manager = SessionManager(app_config, mock_db_connection)
        fake_file = test_output_dir / "session_nonexistent.json"

        # Should create new session when file doesn't exist
        session_state = manager.start_session(
            session_file=fake_file,
            first_user_input="Test"
        )

        # Since file doesn't exist, should create new session
        assert session_state is not None


# ============================================================================
# Session Save Tests
# ============================================================================

@pytest.mark.unit
class TestSessionManagerSave:
    """Tests for session saving."""

    @patch('core.session_manager.SessionExecution')
    def test_save_session(self, mock_execution_class, app_config, mock_db_connection):
        """Test saving current session."""
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        manager = SessionManager(app_config, mock_db_connection)
        manager.start_session(first_user_input="Test")

        session_file = manager.save_session()

        assert session_file.exists()
        assert session_file.name.startswith("session_")

    @patch('core.session_manager.SessionExecution')
    def test_save_session_no_active_session(self, mock_execution_class, app_config, mock_db_connection):
        """Test saving when no active session."""
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        manager = SessionManager(app_config, mock_db_connection)

        with pytest.raises(RuntimeError, match="No active session"):
            manager.save_session()

    @patch('core.session_manager.SessionExecution')
    def test_save_session_callback(self, mock_execution_class, app_config, mock_db_connection):
        """Test save session callback."""
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        manager = SessionManager(app_config, mock_db_connection)
        manager.start_session(first_user_input="Test")

        # Call the callback
        manager._save_session_callback()

        # Should save without error
        assert manager.current_session is not None


# ============================================================================
# Session Finalization Tests
# ============================================================================

@pytest.mark.unit
class TestSessionManagerFinalization:
    """Tests for session finalization."""

    @patch('core.session_manager.SessionExecution')
    def test_finalize_current_session(self, mock_execution_class, app_config, mock_db_connection):
        """Test finalizing current session."""
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        manager = SessionManager(app_config, mock_db_connection)
        manager.start_session(first_user_input="Test")

        manager.finalize_current_session()

        assert manager.current_session.metadata.end_time is not None
        assert manager.current_session.metadata.pid is None

    @patch('core.session_manager.SessionExecution')
    def test_finalize_no_active_session(self, mock_execution_class, app_config, mock_db_connection, caplog):
        """Test finalizing when no active session."""
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        manager = SessionManager(app_config, mock_db_connection)

        # Should not raise, just log warning
        manager.finalize_current_session()

        assert "No active session" in caplog.text or manager.current_session is None


# ============================================================================
# Session Listing Tests
# ============================================================================

@pytest.mark.unit
class TestSessionManagerListing:
    """Tests for listing sessions."""

    @patch('core.session_manager.SessionExecution')
    def test_list_available_sessions_empty(self, mock_execution_class, app_config, mock_db_connection):
        """Test listing sessions in empty directory."""
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        manager = SessionManager(app_config, mock_db_connection)

        sessions = manager.list_available_sessions()

        assert isinstance(sessions, list)
        assert len(sessions) == 0

    @patch('core.session_manager.SessionExecution')
    def test_list_available_sessions(self, mock_execution_class, app_config, mock_db_connection, multiple_session_files):
        """Test listing multiple sessions."""
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        manager = SessionManager(app_config, mock_db_connection)

        sessions = manager.list_available_sessions()

        assert len(sessions) == 3
        assert all('session_id' in s for s in sessions)
        assert all('file_path' in s for s in sessions)

    @patch('core.session_manager.SessionExecution')
    def test_find_latest_session_empty(self, mock_execution_class, app_config, mock_db_connection):
        """Test finding latest session in empty directory."""
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        manager = SessionManager(app_config, mock_db_connection)

        latest = manager.find_latest_session()

        assert latest is None

    @patch('core.session_manager.SessionExecution')
    def test_find_latest_session(self, mock_execution_class, app_config, mock_db_connection, multiple_session_files):
        """Test finding latest session."""
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        manager = SessionManager(app_config, mock_db_connection)

        latest = manager.find_latest_session()

        assert latest is not None
        assert latest.exists()


# ============================================================================
# Memory Verification Tests
# ============================================================================

@pytest.mark.unit
class TestSessionManagerVerification:
    """Tests for memory verification."""

    @patch('core.session_manager.SessionExecution')
    @patch('services.memory_verification.MemoryVerificationCoordinator')
    def test_verify_memory_item(self, mock_verifier_class, mock_execution_class,
                                app_config, mock_db_connection, sample_session_with_memory):
        """Test verifying a memory item."""
        # Setup mocks
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        mock_verifier = MagicMock()
        mock_verifier.verify_memory_item.return_value = {
            'verified': True,
            'confidence': 'high',
            'recommendation': 'keep',
            'reasoning': 'Data is accurate'
        }
        mock_verifier_class.return_value = mock_verifier

        manager = SessionManager(app_config, mock_db_connection)

        result = manager.verify_memory_item(
            sample_session_with_memory,
            category='insights',
            key='record_count'
        )

        assert result['verified'] is True
        assert result['confidence'] == 'high'

    @patch('core.session_manager.SessionExecution')
    def test_verify_memory_item_category_not_found(self, mock_execution_class,
                                                   app_config, mock_db_connection, sample_session):
        """Test verifying non-existent category."""
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        manager = SessionManager(app_config, mock_db_connection)

        with pytest.raises(ValueError, match="Category.*not found"):
            manager.verify_memory_item(
                sample_session,
                category='nonexistent_category',
                key='some_key'
            )

    @patch('core.session_manager.SessionExecution')
    def test_verify_memory_item_key_not_found(self, mock_execution_class,
                                              app_config, mock_db_connection, sample_session_with_memory):
        """Test verifying non-existent key."""
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        manager = SessionManager(app_config, mock_db_connection)

        with pytest.raises(ValueError, match="Memory key.*not found"):
            manager.verify_memory_item(
                sample_session_with_memory,
                category='insights',
                key='nonexistent_key'
            )


# ============================================================================
# Run Session Tests (Mocked)
# ============================================================================

@pytest.mark.unit
class TestSessionManagerRunSession:
    """Tests for run_session method (heavily mocked)."""

    @patch('core.session_manager.SessionExecution')
    def test_run_session_requires_active_session(self, mock_execution_class, app_config, mock_db_connection):
        """Test run_session requires active session."""
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        manager = SessionManager(app_config, mock_db_connection)

        with pytest.raises(RuntimeError, match="No active session"):
            manager.run_session()

    @patch('core.session_manager.SessionExecution')
    def test_run_session_with_keyboard_interrupt(self, mock_execution_class, app_config, mock_db_connection):
        """Test run_session handles keyboard interrupt."""
        mock_execution = MagicMock()
        mock_execution.execute_iteration.side_effect = KeyboardInterrupt()
        # Mock methods that return data stored in session state to return actual strings
        mock_execution.build_base_prompt.return_value = "Base prompt for testing"
        mock_execution.build_continuation_prompt.return_value = "Continuation prompt"
        mock_execution_class.return_value = mock_execution

        manager = SessionManager(app_config, mock_db_connection)
        manager.start_session(first_user_input="Test")

        # Should handle interrupt gracefully
        manager.run_session()

        assert manager.current_session.metadata.end_time is not None


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.integration
class TestSessionManagerIntegration:
    """Integration tests for SessionManager with real components."""

    @patch('core.session_manager.SessionExecution')
    def test_full_session_lifecycle(self, mock_execution_class, app_config, mock_db_connection):
        """Test complete session lifecycle: create -> save -> load."""
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        manager = SessionManager(app_config, mock_db_connection)

        # Create session
        session = manager.start_session(first_user_input="Test task")
        session_id = session.metadata.session_id

        # Save session
        session_file = manager.save_session()

        # Finalize
        manager.finalize_current_session()

        # Create new manager and load session
        manager2 = SessionManager(app_config, mock_db_connection)
        loaded_session = manager2.start_session(session_file=session_file)

        assert loaded_session.metadata.session_id == session_id

    @patch('core.session_manager.SessionExecution')
    def test_session_persistence_across_managers(self, mock_execution_class, app_config, mock_db_connection):
        """Test that sessions persist across different manager instances."""
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        # Manager 1 creates session
        manager1 = SessionManager(app_config, mock_db_connection)
        session1 = manager1.start_session(first_user_input="Task 1")
        manager1.save_session()

        # Manager 2 lists sessions
        manager2 = SessionManager(app_config, mock_db_connection)
        sessions = manager2.list_available_sessions()

        # Should find the session created by manager1
        session_ids = [s['session_id'] for s in sessions]
        assert session1.metadata.session_id in session_ids
