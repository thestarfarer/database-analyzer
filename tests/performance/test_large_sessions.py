"""
Performance Tests for Large Sessions

Tests system performance with large datasets, many iterations,
and extensive tool calls.
"""

import pytest
import time
from core.session_state import SessionState, ToolCall
from core.session_persistence import SessionPersistence


# ============================================================================
# Large Session Performance Tests
# ============================================================================

@pytest.mark.performance
@pytest.mark.slow
class TestLargeSessionPerformance:
    """Tests for performance with large session data."""

    def test_many_iterations_performance(self, test_output_dir):
        """Test performance with many iterations."""
        session = SessionState("perf_test_session")

        # Create 100 iterations
        start = time.time()

        for i in range(1, 101):
            iteration = session.add_iteration(
                iteration_num=i,
                prompt=f"Prompt {i}",
                user_input=f"Task {i}"
            )

            # Add tool call
            tool_call = ToolCall(
                id=f"call_{i}",
                tool="execute_sql",
                timestamp=time.time(),
                input={"query": f"SELECT * FROM table{i}"},
                output=f"Results for iteration {i}",
                execution_time=0.1
            )

            session.add_tool_call(i, tool_call)
            session.complete_iteration(i, f"Response {i}")

        creation_time = time.time() - start

        # Should complete in reasonable time (< 5 seconds)
        assert creation_time < 5.0
        assert len(session.iterations) == 100

    def test_many_tool_calls_performance(self, test_output_dir):
        """Test performance with many tool calls per iteration."""
        session = SessionState("perf_test_tool_calls")

        iteration = session.add_iteration(1, "Test")

        # Add 1000 tool calls
        start = time.time()

        for i in range(1000):
            tool_call = ToolCall(
                id=f"call_{i}",
                tool="execute_sql",
                timestamp=time.time(),
                input={"query": f"SELECT {i}"},
                output=f"Result {i}",
                execution_time=0.01
            )

            session.add_tool_call(1, tool_call)

        addition_time = time.time() - start

        # Should complete in reasonable time
        assert addition_time < 2.0
        assert len(session.iterations[0].tool_calls) == 1000

    def test_large_session_save_performance(self, test_output_dir):
        """Test save performance with large session."""
        session = SessionState("perf_test_save")

        # Create large session
        for i in range(1, 51):
            iteration = session.add_iteration(i, f"Prompt {i}", f"Task {i}")

            # Add multiple tool calls
            for j in range(10):
                tool_call = ToolCall(
                    id=f"call_{i}_{j}",
                    tool="execute_sql",
                    timestamp=time.time(),
                    input={"query": f"SELECT * FROM table{i}_{j}"},
                    output="Results...",
                    execution_time=0.1
                )
                session.add_tool_call(i, tool_call)

            session.complete_iteration(i, f"Response {i}")

        # Measure save performance
        persistence = SessionPersistence(test_output_dir)

        start = time.time()
        session_file = persistence.save_session(session)
        save_time = time.time() - start

        # Should save in reasonable time (< 1 second)
        assert save_time < 1.0
        assert session_file.exists()

    def test_large_session_load_performance(self, test_output_dir):
        """Test load performance with large session."""
        session = SessionState("perf_test_load")

        # Create and save large session
        for i in range(1, 51):
            iteration = session.add_iteration(i, f"Prompt {i}", f"Task {i}")

            for j in range(10):
                tool_call = ToolCall(
                    id=f"call_{i}_{j}",
                    tool="memory",
                    timestamp=time.time(),
                    input={
                        "action": "update",
                        "key": f"category_{j}",
                        "value": f"key_{i}_{j}:Value {i}_{j}"
                    },
                    output="Updated",
                    execution_time=0.001
                )
                session.add_tool_call(i, tool_call)

            session.complete_iteration(i, f"Response {i}")

        persistence = SessionPersistence(test_output_dir)
        session_file = persistence.save_session(session)

        # Measure load performance
        start = time.time()
        loaded_session = persistence.load_session(session_file)
        load_time = time.time() - start

        # Should load in reasonable time (< 1 second)
        assert load_time < 1.0
        assert len(loaded_session.iterations) == 50

    def test_memory_composition_performance(self, test_output_dir):
        """Test memory composition performance with many items."""
        session = SessionState("perf_test_memory")

        iteration = session.add_iteration(1, "Test")

        # Add many memory updates
        for i in range(500):
            tool_call = ToolCall(
                id=f"mem_{i}",
                tool="memory",
                timestamp=time.time(),
                input={
                    "action": "update",
                    "key": f"category_{i % 10}",
                    "value": f"key_{i}:Value {i}"
                },
                output="Updated",
                execution_time=0.001
            )
            session.add_tool_call(1, tool_call)

        # Measure memory composition performance
        start = time.time()
        memory_data = session.get_memory_data_from_tool_calls()
        composition_time = time.time() - start

        # Should compose memory quickly (< 0.5 seconds)
        assert composition_time < 0.5
        assert len(memory_data) > 0


# ============================================================================
# Memory Performance Tests
# ============================================================================

@pytest.mark.performance
class TestMemoryPerformance:
    """Tests for memory system performance."""

    def test_memory_update_performance(self):
        """Test performance of memory updates."""
        session = SessionState("mem_update_perf")

        iteration = session.add_iteration(1, "Test")

        # Add initial memory
        for i in range(100):
            tool_call = ToolCall(
                id=f"mem_init_{i}",
                tool="memory",
                timestamp=time.time(),
                input={
                    "action": "update",
                    "key": "insights",
                    "value": f"key_{i}:Initial value {i}"
                },
                output="Updated",
                execution_time=0.001
            )
            session.add_tool_call(1, tool_call)

        # Measure update performance
        start = time.time()

        success = session.update_memory_value(
            category="insights",
            key="key_50",
            new_value="Updated value 50"
        )

        update_time = time.time() - start

        # Should update quickly
        assert update_time < 0.1
        assert success is True

    def test_memory_get_performance(self):
        """Test performance of memory retrieval."""
        session = SessionState("mem_get_perf")

        iteration = session.add_iteration(1, "Test")

        # Add many memory items across categories
        categories = ['insights', 'patterns', 'key_findings', 'metrics', 'context']

        for cat in categories:
            for i in range(50):
                tool_call = ToolCall(
                    id=f"mem_{cat}_{i}",
                    tool="memory",
                    timestamp=time.time(),
                    input={
                        "action": "update",
                        "key": cat,
                        "value": f"key_{i}:Value {i}"
                    },
                    output="Updated",
                    execution_time=0.001
                )
                session.add_tool_call(1, tool_call)

        # Measure retrieval performance
        start = time.time()
        summary = session.get_memory_summary()
        retrieval_time = time.time() - start

        # Should retrieve quickly even with many items
        assert retrieval_time < 0.5
        assert len(summary) > 0


# ============================================================================
# Serialization Performance Tests
# ============================================================================

@pytest.mark.performance
class TestSerializationPerformance:
    """Tests for serialization/deserialization performance."""

    def test_large_session_serialization(self):
        """Test serialization performance for large sessions."""
        session = SessionState("serialize_perf")

        # Create large session
        for i in range(1, 101):
            iteration = session.add_iteration(i, f"Prompt {i}", f"Task {i}")

            for j in range(5):
                tool_call = ToolCall(
                    id=f"call_{i}_{j}",
                    tool="execute_sql",
                    timestamp=time.time(),
                    input={"query": f"SELECT * FROM table{i}_{j}"},
                    output="Large result set..." * 10,
                    execution_time=0.1
                )
                session.add_tool_call(i, tool_call)

            session.complete_iteration(i, f"Response {i}")

        # Measure serialization
        start = time.time()
        data = session.to_dict()
        serialize_time = time.time() - start

        # Should serialize quickly
        assert serialize_time < 1.0
        assert 'session_metadata' in data

    def test_large_session_deserialization(self):
        """Test deserialization performance for large sessions."""
        # Create large session data
        session = SessionState("deserialize_perf")

        for i in range(1, 101):
            iteration = session.add_iteration(i, f"Prompt {i}", f"Task {i}")
            session.complete_iteration(i, f"Response {i}")

        data = session.to_dict()

        # Measure deserialization
        start = time.time()
        loaded_session = SessionState.from_dict(data)
        deserialize_time = time.time() - start

        # Should deserialize quickly
        assert deserialize_time < 1.0
        assert len(loaded_session.iterations) == 100
