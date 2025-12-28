"""
Unit Tests for Session State Management

Tests for SessionState, SessionMetadata, Iteration, ToolCall, and related classes.
Covers session lifecycle, memory composition, resume logic, and serialization.
"""

import pytest
import time
from datetime import datetime
from core.session_state import (
    SessionState, SessionMetadata, Iteration, ToolCall, SystemLog,
    ResumePoint
)


# ============================================================================
# SessionMetadata Tests
# ============================================================================

@pytest.mark.unit
class TestSessionMetadata:
    """Tests for SessionMetadata dataclass."""

    def test_metadata_creation(self, session_id):
        """Test creating session metadata with required fields."""
        metadata = SessionMetadata(
            session_id=session_id,
            start_time=time.time()
        )

        assert metadata.session_id == session_id
        assert isinstance(metadata.start_time, float)
        assert metadata.end_time is None
        assert metadata.current_iteration == 0
        assert metadata.pid is None

    def test_metadata_with_pid(self, session_id):
        """Test metadata with PID tracking."""
        metadata = SessionMetadata(
            session_id=session_id,
            start_time=time.time(),
            pid=12345
        )

        assert metadata.pid == 12345

    def test_metadata_with_end_time(self, session_id):
        """Test completed session metadata."""
        start = time.time()
        end = start + 100

        metadata = SessionMetadata(
            session_id=session_id,
            start_time=start,
            end_time=end
        )

        assert metadata.end_time == end
        assert metadata.end_time > metadata.start_time


# ============================================================================
# ToolCall Tests
# ============================================================================

@pytest.mark.unit
class TestToolCall:
    """Tests for ToolCall dataclass."""

    def test_tool_call_creation(self):
        """Test creating a tool call."""
        tool_call = ToolCall(
            id="call_1",
            tool="execute_sql",
            timestamp=time.time(),
            input={"query": "SELECT * FROM entities"},
            output="Results...",
            execution_time=0.123
        )

        assert tool_call.id == "call_1"
        assert tool_call.tool == "execute_sql"
        assert isinstance(tool_call.timestamp, float)
        assert tool_call.input["query"] == "SELECT * FROM entities"
        assert tool_call.execution_time == 0.123
        assert tool_call.metadata == {}

    def test_tool_call_with_metadata(self):
        """Test tool call with metadata."""
        tool_call = ToolCall(
            id="call_1",
            tool="memory",
            timestamp=time.time(),
            input={"action": "update"},
            output="Updated",
            execution_time=0.001,
            metadata={"verified": True, "verified_at": time.time()}
        )

        assert tool_call.metadata["verified"] is True
        assert "verified_at" in tool_call.metadata

    def test_memory_tool_call(self, sample_memory_tool_call):
        """Test memory-specific tool call structure."""
        assert sample_memory_tool_call.tool == "memory"
        assert "action" in sample_memory_tool_call.input
        assert "key" in sample_memory_tool_call.input
        assert "value" in sample_memory_tool_call.input


# ============================================================================
# Iteration Tests
# ============================================================================

@pytest.mark.unit
class TestIteration:
    """Tests for Iteration dataclass."""

    def test_iteration_creation(self):
        """Test creating an iteration."""
        iteration = Iteration(
            iteration=1,
            start_time=time.time(),
            prompt="Test prompt",
            user_input="Test task"
        )

        assert iteration.iteration == 1
        assert iteration.prompt == "Test prompt"
        assert iteration.user_input == "Test task"
        assert iteration.end_time is None
        assert iteration.llm_response is None
        assert len(iteration.tool_calls) == 0
        assert len(iteration.system_logs) == 0

    def test_iteration_with_tool_calls(self, sample_tool_call):
        """Test iteration with tool calls."""
        iteration = Iteration(
            iteration=1,
            start_time=time.time(),
            prompt="Test",
            tool_calls=[sample_tool_call]
        )

        assert len(iteration.tool_calls) == 1
        assert iteration.tool_calls[0].tool == "execute_sql"

    def test_iteration_completion(self):
        """Test completing an iteration."""
        start = time.time()
        iteration = Iteration(
            iteration=1,
            start_time=start,
            prompt="Test"
        )

        # Complete iteration
        end = time.time()
        iteration.end_time = end
        iteration.llm_response = "Analysis complete"

        assert iteration.end_time >= iteration.start_time
        assert iteration.llm_response == "Analysis complete"


# ============================================================================
# SessionState Tests - Basic Operations
# ============================================================================

@pytest.mark.unit
class TestSessionStateBasics:
    """Tests for basic SessionState operations."""

    def test_session_creation(self, session_id):
        """Test creating a new session."""
        session = SessionState(session_id=session_id)

        assert session.metadata.session_id == session_id
        assert isinstance(session.metadata.start_time, float)
        assert len(session.iterations) == 0

    def test_add_iteration(self, session_id):
        """Test adding an iteration to session."""
        session = SessionState(session_id=session_id)

        iteration = session.add_iteration(
            iteration_num=1,
            prompt="Test prompt",
            user_input="Test task"
        )

        assert len(session.iterations) == 1
        assert session.iterations[0].iteration == 1
        assert session.metadata.current_iteration == 1

    def test_add_multiple_iterations(self, session_id):
        """Test adding multiple iterations."""
        session = SessionState(session_id=session_id)

        for i in range(1, 4):
            session.add_iteration(
                iteration_num=i,
                prompt=f"Prompt {i}",
                user_input=f"Task {i}"
            )

        assert len(session.iterations) == 3
        assert session.metadata.current_iteration == 3

    def test_add_tool_call(self, session_id, sample_tool_call):
        """Test adding a tool call to an iteration."""
        session = SessionState(session_id=session_id)
        session.add_iteration(1, "Test")

        session.add_tool_call(1, sample_tool_call)

        assert len(session.iterations[0].tool_calls) == 1
        assert session.iterations[0].tool_calls[0].id == "tool_call_1"

    def test_complete_iteration(self, session_id):
        """Test completing an iteration."""
        session = SessionState(session_id=session_id)
        session.add_iteration(1, "Test", "Test task")

        session.complete_iteration(1, "Analysis complete")

        iteration = session.iterations[0]
        assert iteration.llm_response == "Analysis complete"
        assert iteration.end_time is not None


# ============================================================================
# SessionState Tests - Status and Resume Logic
# ============================================================================

@pytest.mark.unit
class TestSessionStateStatus:
    """Tests for session status and resume logic."""

    def test_get_iteration_status_completed(self, sample_iteration):
        """Test iteration status for completed iteration."""
        session = SessionState("test_session")
        assert session.get_iteration_status(sample_iteration) == "completed"

    def test_get_iteration_status_interrupted(self):
        """Test iteration status for interrupted iteration."""
        session = SessionState("test_session")
        iteration = Iteration(
            iteration=1,
            start_time=time.time(),
            prompt="Test"
        )
        # No llm_response = interrupted
        assert session.get_iteration_status(iteration) == "interrupted"

    def test_get_completed_iterations_count(self, sample_session):
        """Test counting completed iterations."""
        count = sample_session.get_completed_iterations_count()
        assert count == 1  # sample_session has 1 completed iteration

    def test_get_last_completed_iteration(self, sample_session):
        """Test getting last completed iteration."""
        last = sample_session.get_last_completed_iteration()
        assert last is not None
        assert last.iteration == 1

    def test_resume_point_new_session(self):
        """Test resume point for new session."""
        session = SessionState("new_session")
        resume = session.get_resume_point()

        assert resume.iteration == 1
        assert resume.should_restart_iteration is False
        assert resume.last_completed_tool_call is None
        assert "new session" in resume.context_summary.lower()

    def test_resume_point_after_completed_iteration(self, sample_session):
        """Test resume point after completed iteration."""
        resume = sample_session.get_resume_point()

        assert resume.iteration == 2  # Next after completed iteration 1
        assert resume.should_restart_iteration is False
        assert "iteration 1" in resume.context_summary.lower()

    def test_resume_point_removes_incomplete_iterations(self):
        """Test that resume point removes incomplete iterations."""
        session = SessionState("test_session")

        # Add completed iteration
        iter1 = session.add_iteration(1, "Completed", "Task 1")
        iter1.llm_response = "Done"
        iter1.end_time = time.time()

        # Add incomplete iteration
        session.add_iteration(2, "Incomplete", "Task 2")

        # Get resume point
        resume = session.get_resume_point()

        # Should clean up incomplete iteration and start from 2
        assert len(session.iterations) == 1
        assert resume.iteration == 2


# ============================================================================
# SessionState Tests - Memory Composition
# ============================================================================

@pytest.mark.unit
class TestSessionStateMemory:
    """Tests for memory composition from tool calls."""

    def test_get_memory_data_empty(self, session_id):
        """Test memory data for session without memory tool calls."""
        session = SessionState(session_id=session_id)
        memory_data = session.get_memory_data_from_tool_calls()

        assert isinstance(memory_data, dict)
        assert len(memory_data) == 0

    def test_get_memory_data_with_updates(self, sample_session_with_memory):
        """Test memory data composition from updates."""
        memory_data = sample_session_with_memory.get_memory_data_from_tool_calls()

        assert "insights" in memory_data
        assert "key_findings" in memory_data
        assert len(memory_data["insights"]) == 1
        assert "100 records" in memory_data["insights"][0]

    def test_memory_summary_empty(self, session_id):
        """Test memory summary for empty session."""
        session = SessionState(session_id=session_id)
        summary = session.get_memory_summary()

        assert "No memory stored" in summary

    def test_memory_summary_with_data(self, sample_session_with_memory):
        """Test memory summary formatting."""
        summary = sample_session_with_memory.get_memory_summary()

        assert "Insights:" in summary
        assert "100 records" in summary
        assert "Key Findings:" in summary

    def test_update_memory_value(self, sample_session_with_memory):
        """Test updating a memory value."""
        success = sample_session_with_memory.update_memory_value(
            category="insights",
            key="record_count",
            new_value="101 records total (updated)"
        )

        assert success is True

        # Verify update
        memory_data = sample_session_with_memory.get_memory_data_from_tool_calls()
        assert "101 records" in memory_data["insights"][0]

    def test_update_memory_value_adds_metadata(self, sample_session_with_memory):
        """Test that memory update adds verification metadata."""
        sample_session_with_memory.update_memory_value(
            category="insights",
            key="record_count",
            new_value="Updated value"
        )

        # Find the tool call
        tool_call = sample_session_with_memory.iterations[0].tool_calls[0]

        assert tool_call.metadata.get("verified") is True
        assert "verified_at" in tool_call.metadata
        assert "old_value" in tool_call.metadata

    def test_get_memory_data_with_metadata(self, sample_session_with_memory):
        """Test getting memory data with iteration metadata."""
        result = sample_session_with_memory.get_memory_data_with_metadata()

        assert "memory_data" in result
        assert "last_updated" in result
        assert "insights" in result["memory_data"]

        # Check metadata on items
        insights = result["memory_data"]["insights"]
        assert len(insights) > 0
        assert "content" in insights[0]
        assert "iteration" in insights[0]
        assert "timestamp" in insights[0]


# ============================================================================
# SessionState Tests - User Commands and Conversation
# ============================================================================

@pytest.mark.unit
class TestSessionStateConversation:
    """Tests for conversation and user command tracking."""

    def test_get_user_commands_history_empty(self, session_id):
        """Test user commands history for new session."""
        session = SessionState(session_id=session_id)
        history = session.get_user_commands_history()

        assert history == ""

    def test_get_user_commands_history(self, sample_session):
        """Test user commands history formatting."""
        history = sample_session.get_user_commands_history()

        assert "USER COMMANDS HISTORY:" in history
        assert "Iteration 1:" in history
        assert sample_session.iterations[0].user_input in history


# ============================================================================
# SessionState Tests - Finalization
# ============================================================================

@pytest.mark.unit
class TestSessionStateFinalization:
    """Tests for session finalization."""

    def test_finalize_session(self, session_id):
        """Test finalizing a session."""
        session = SessionState(session_id=session_id)
        session.metadata.pid = 12345

        session.finalize_session()

        assert session.metadata.end_time is not None
        assert session.metadata.pid is None  # Cleared on finalization

    def test_finalize_sets_end_times(self, session_id):
        """Test that finalization sets end times on incomplete iterations."""
        session = SessionState(session_id=session_id)
        session.add_iteration(1, "Test")

        # Iteration has no end_time
        assert session.iterations[0].end_time is None

        session.finalize_session()

        # Should now have end_time
        assert session.iterations[0].end_time is not None


# ============================================================================
# SessionState Tests - Serialization
# ============================================================================

@pytest.mark.unit
class TestSessionStateSerialization:
    """Tests for session serialization and deserialization."""

    def test_to_dict_basic(self, session_id):
        """Test basic session serialization."""
        session = SessionState(session_id=session_id)
        data = session.to_dict()

        assert isinstance(data, dict)
        assert "session_metadata" in data
        assert "iterations" in data
        assert "export_timestamp" in data
        assert data["session_metadata"]["session_id"] == session_id

    def test_to_dict_with_iterations(self, sample_session):
        """Test serialization with iterations."""
        data = sample_session.to_dict()

        assert len(data["iterations"]) == 1
        iteration_data = data["iterations"][0]

        assert iteration_data["iteration"] == 1
        assert "prompt" in iteration_data
        assert "user_input" in iteration_data
        assert "tool_calls" in iteration_data
        assert "llm_response" in iteration_data

    def test_to_dict_with_tool_calls(self, sample_session):
        """Test serialization with tool calls."""
        data = sample_session.to_dict()

        tool_calls = data["iterations"][0]["tool_calls"]
        assert len(tool_calls) == 1
        assert tool_calls[0]["tool"] == "execute_sql"
        assert "input" in tool_calls[0]
        assert "output" in tool_calls[0]

    def test_from_dict_basic(self, session_id):
        """Test basic session deserialization."""
        data = {
            "session_metadata": {
                "session_id": session_id,
                "start_time": time.time(),
                "end_time": None,
                "current_iteration": 0,
                "last_save_time": time.time(),
                "pid": None
            },
            "iterations": [],
            "export_timestamp": datetime.now().isoformat()
        }

        session = SessionState.from_dict(data)

        assert session.metadata.session_id == session_id
        assert len(session.iterations) == 0

    def test_from_dict_with_iterations(self):
        """Test deserialization with iterations."""
        data = {
            "session_metadata": {
                "session_id": "test_123",
                "start_time": time.time(),
                "end_time": None,
                "current_iteration": 1,
                "last_save_time": time.time(),
                "pid": None
            },
            "iterations": [
                {
                    "iteration": 1,
                    "start_time": time.time(),
                    "end_time": time.time() + 10,
                    "prompt": "Test",
                    "user_input": "Task",
                    "tool_calls": [],
                    "llm_response": "Response",
                    "system_logs": []
                }
            ],
            "export_timestamp": datetime.now().isoformat()
        }

        session = SessionState.from_dict(data)

        assert len(session.iterations) == 1
        assert session.iterations[0].llm_response == "Response"

    def test_serialization_roundtrip(self, sample_session):
        """Test that serialization and deserialization preserve data."""
        # Serialize
        data = sample_session.to_dict()

        # Deserialize
        restored_session = SessionState.from_dict(data)

        # Compare
        assert restored_session.metadata.session_id == sample_session.metadata.session_id
        assert len(restored_session.iterations) == len(sample_session.iterations)
        assert restored_session.iterations[0].llm_response == sample_session.iterations[0].llm_response
