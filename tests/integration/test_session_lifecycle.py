"""
Integration Tests for Session Lifecycle

Tests the complete session lifecycle including creation, execution,
saving, resuming, and finalization across multiple components.
"""

import pytest
import time
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from core.session_manager import SessionManager
from core.session_state import SessionState
from core.session_persistence import SessionPersistence


# ============================================================================
# Complete Session Lifecycle Tests
# ============================================================================

@pytest.mark.integration
class TestCompleteSessionLifecycle:
    """Tests for complete session workflows."""

    @patch('core.session_manager.SessionExecution')
    def test_create_execute_save_lifecycle(self, mock_execution_class, app_config, mock_db_connection):
        """Test creating, executing, and saving a session."""
        # Setup mock execution
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        manager = SessionManager(app_config, mock_db_connection)

        # Create session
        session = manager.start_session(first_user_input="Analyze records")

        assert session is not None
        assert session.metadata.session_id is not None

        # Save session
        session_file = manager.save_session()

        assert session_file.exists()

        # Verify file contains valid JSON
        with open(session_file, 'r') as f:
            data = json.load(f)

        assert data['session_metadata']['session_id'] == session.metadata.session_id

    @patch('core.session_manager.SessionExecution')
    def test_save_load_roundtrip(self, mock_execution_class, app_config, mock_db_connection):
        """Test that session survives save/load roundtrip."""
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        manager = SessionManager(app_config, mock_db_connection)

        # Create and save session
        original_session = manager.start_session(first_user_input="Test task")
        original_id = original_session.metadata.session_id

        session_file = manager.save_session()

        # Load session
        loaded_session = manager.persistence.load_session(session_file)

        assert loaded_session.metadata.session_id == original_id

    @patch('core.session_manager.SessionExecution')
    def test_resume_adds_iterations(self, mock_execution_class, app_config, mock_db_connection, sample_session):
        """Test that resuming a session works correctly."""
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        # Save sample session
        persistence = SessionPersistence(app_config.output_dir)
        session_file = persistence.save_session(sample_session)

        # Resume session
        manager = SessionManager(app_config, mock_db_connection)
        resumed_session = manager.start_session(
            session_file=session_file,
            first_user_input="Continue analysis"
        )

        assert resumed_session.metadata.session_id == sample_session.metadata.session_id
        assert manager.resume_with_task == "Continue analysis"

    @patch('core.session_manager.SessionExecution')
    def test_finalize_marks_session_complete(self, mock_execution_class, app_config, mock_db_connection):
        """Test that finalization marks session as complete."""
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        manager = SessionManager(app_config, mock_db_connection)

        session = manager.start_session(first_user_input="Test")
        session.metadata.pid = 12345

        manager.finalize_current_session()

        assert session.metadata.end_time is not None
        assert session.metadata.pid is None  # Cleared on completion


# ============================================================================
# Session Persistence Integration Tests
# ============================================================================

@pytest.mark.integration
class TestSessionPersistenceIntegration:
    """Tests for session persistence with real filesystem."""

    def test_multiple_saves_same_session(self, test_output_dir, sample_session):
        """Test that multiple saves of same session work correctly."""
        persistence = SessionPersistence(test_output_dir)

        # Save multiple times
        file1 = persistence.save_session(sample_session)
        time.sleep(0.01)
        file2 = persistence.save_session(sample_session)

        # Should save to same file
        assert file1 == file2

        # Load and verify
        loaded = persistence.load_session(file1)
        assert loaded.metadata.session_id == sample_session.metadata.session_id

    def test_session_file_format(self, test_output_dir, sample_session):
        """Test that saved session files have correct format."""
        persistence = SessionPersistence(test_output_dir)

        session_file = persistence.save_session(sample_session)

        # Load raw JSON
        with open(session_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Verify structure
        assert 'session_metadata' in data
        assert 'iterations' in data
        assert 'export_timestamp' in data

        # Verify metadata
        assert data['session_metadata']['session_id'] == sample_session.metadata.session_id

    def test_concurrent_session_saves(self, test_output_dir):
        """Test that multiple sessions can be saved concurrently."""
        persistence = SessionPersistence(test_output_dir)

        # Create multiple sessions
        sessions = []
        for i in range(3):
            session = SessionState(f"session_{i}")
            sessions.append(session)

        # Save all
        files = []
        for session in sessions:
            file = persistence.save_session(session)
            files.append(file)

        # All should exist
        assert all(f.exists() for f in files)
        assert len(files) == 3
        assert len(set(files)) == 3  # All unique


# ============================================================================
# Session State Integration Tests
# ============================================================================

@pytest.mark.integration
class TestSessionStateIntegration:
    """Tests for session state management with iterations and tool calls."""

    def test_session_with_multiple_iterations(self, session_id):
        """Test session with multiple iterations and tool calls."""
        session = SessionState(session_id)

        # Add multiple iterations
        for i in range(1, 4):
            iteration = session.add_iteration(
                iteration_num=i,
                prompt=f"Prompt {i}",
                user_input=f"Task {i}"
            )

            # Add tool calls to iteration
            from core.session_state import ToolCall
            tool_call = ToolCall(
                id=f"call_{i}",
                tool="execute_sql",
                timestamp=time.time(),
                input={"query": f"SELECT * FROM table{i}"},
                output=f"Results {i}",
                execution_time=0.1
            )

            session.add_tool_call(i, tool_call)

            # Complete iteration
            session.complete_iteration(i, f"Response {i}")

        # Verify state
        assert len(session.iterations) == 3
        assert session.get_completed_iterations_count() == 3

        # Each iteration should have tool call
        for iteration in session.iterations:
            assert len(iteration.tool_calls) == 1

    def test_session_memory_accumulation(self, session_id):
        """Test memory accumulation across iterations."""
        session = SessionState(session_id)

        # Add iterations with memory updates
        for i in range(1, 4):
            iteration = session.add_iteration(i, f"Prompt {i}")

            # Add memory tool call
            from core.session_state import ToolCall
            memory_call = ToolCall(
                id=f"mem_{i}",
                tool="memory",
                timestamp=time.time(),
                input={
                    "action": "update",
                    "key": "insights",
                    "value": f"insight_{i}:Finding {i}"
                },
                output="Updated",
                execution_time=0.001
            )

            session.add_tool_call(i, memory_call)
            session.complete_iteration(i, f"Response {i}")

        # Verify memory accumulation
        memory_data = session.get_memory_data_from_tool_calls()

        assert 'insights' in memory_data
        assert len(memory_data['insights']) == 3

    def test_session_resume_point_calculation(self, session_id):
        """Test resume point calculation with completed and incomplete iterations."""
        session = SessionState(session_id)

        # Add completed iteration
        iter1 = session.add_iteration(1, "Prompt 1", "Task 1")
        iter1.llm_response = "Done"
        iter1.end_time = time.time()

        # Add incomplete iteration
        iter2 = session.add_iteration(2, "Prompt 2", "Task 2")
        # No llm_response = incomplete

        # Get resume point
        resume = session.get_resume_point()

        # Should resume from iteration 2 (after removing incomplete iteration)
        assert resume.iteration == 2
        assert len(session.iterations) == 1  # Incomplete removed


# ============================================================================
# Manager + Persistence Integration Tests
# ============================================================================

@pytest.mark.integration
class TestManagerPersistenceIntegration:
    """Tests for SessionManager and SessionPersistence integration."""

    @patch('core.session_manager.SessionExecution')
    def test_manager_uses_persistence_correctly(self, mock_execution_class, app_config, mock_db_connection):
        """Test that manager uses persistence layer correctly."""
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        manager = SessionManager(app_config, mock_db_connection)

        # Create and save session
        session = manager.start_session(first_user_input="Test")
        session_id = session.metadata.session_id

        # List sessions should find it
        sessions = manager.list_available_sessions()

        session_ids = [s['session_id'] for s in sessions]
        assert session_id in session_ids

    @patch('core.session_manager.SessionExecution')
    def test_manager_handles_corrupted_session_file(self, mock_execution_class, app_config, mock_db_connection):
        """Test manager handles corrupted session files gracefully."""
        mock_execution = MagicMock()
        mock_execution_class.return_value = mock_execution

        # Create corrupted file
        corrupted_file = app_config.output_dir / "session_corrupted.json"
        with open(corrupted_file, 'w') as f:
            f.write("{ invalid json ")

        manager = SessionManager(app_config, mock_db_connection)

        # List sessions should handle corrupted file
        sessions = manager.list_available_sessions()

        # Should return error for corrupted file
        corrupted_sessions = [s for s in sessions if 'error' in s]
        assert len(corrupted_sessions) > 0


# ============================================================================
# Memory System Integration Tests
# ============================================================================

@pytest.mark.integration
class TestMemorySystemIntegration:
    """Tests for memory system across components."""

    def test_memory_persists_across_save_load(self, test_output_dir):
        """Test that memory data persists through save/load cycle."""
        persistence = SessionPersistence(test_output_dir)

        # Create session with memory
        session = SessionState("test_session")
        iteration = session.add_iteration(1, "Test")

        # Add memory tool calls
        from core.session_state import ToolCall
        for i in range(3):
            memory_call = ToolCall(
                id=f"mem_{i}",
                tool="memory",
                timestamp=time.time(),
                input={
                    "action": "update",
                    "key": "insights",
                    "value": f"key_{i}:Value {i}"
                },
                output="Updated",
                execution_time=0.001
            )
            session.add_tool_call(1, memory_call)

        # Save
        session_file = persistence.save_session(session)

        # Load
        loaded_session = persistence.load_session(session_file)

        # Verify memory
        original_memory = session.get_memory_data_from_tool_calls()
        loaded_memory = loaded_session.get_memory_data_from_tool_calls()

        assert original_memory == loaded_memory

    def test_memory_update_after_verification(self, test_output_dir):
        """Test memory update workflow after verification."""
        session = SessionState("test_session")
        iteration = session.add_iteration(1, "Test")

        # Add original memory
        from core.session_state import ToolCall
        memory_call = ToolCall(
            id="mem_1",
            tool="memory",
            timestamp=time.time(),
            input={
                "action": "update",
                "key": "insights",
                "value": "record_count:100 records"
            },
            output="Updated",
            execution_time=0.001
        )
        session.add_tool_call(1, memory_call)

        # Update memory (simulating verification)
        success = session.update_memory_value(
            category="insights",
            key="record_count",
            new_value="106 records (verified)"
        )

        assert success is True

        # Verify update persists
        persistence = SessionPersistence(test_output_dir)
        session_file = persistence.save_session(session)

        loaded_session = persistence.load_session(session_file)
        memory = loaded_session.get_memory_data_from_tool_calls()

        assert "106 records" in memory['insights'][0]


# ============================================================================
# Error Recovery Integration Tests
# ============================================================================

@pytest.mark.integration
class TestErrorRecoveryIntegration:
    """Tests for error recovery across components."""

    def test_session_recovery_after_crash(self, test_output_dir):
        """Test that sessions can be recovered after crash."""
        persistence = SessionPersistence(test_output_dir)

        # Create session with partial data
        session = SessionState("crashed_session")
        iter1 = session.add_iteration(1, "Prompt 1", "Task 1")
        iter1.llm_response = "Done"
        iter1.end_time = time.time()

        # Add incomplete iteration (simulating crash)
        session.add_iteration(2, "Prompt 2", "Task 2")

        # Save
        session_file = persistence.save_session(session)

        # Load (simulating recovery)
        loaded = persistence.load_session(session_file)

        # Get resume point (should clean up incomplete iteration)
        resume = loaded.get_resume_point()

        assert resume.iteration == 2
        assert loaded.get_completed_iterations_count() == 1
