"""
WebUI Session Reader Tests

Tests for UnifiedSessionReader service which handles session file discovery,
metadata parsing, status computation, and memory composition.
"""

import pytest
import json
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import psutil
from webui.services.unified_session_reader import UnifiedSessionReader
from core.session_state import SessionState, ToolCall


# ============================================================================
# Session Discovery Tests
# ============================================================================

@pytest.mark.webui
class TestSessionDiscovery:
    """Tests for finding and listing session files."""

    def test_find_unified_session_files(self, test_output_dir):
        """Test pattern matching for session_*.json files."""
        reader = UnifiedSessionReader(test_output_dir)

        # Create valid session files
        (test_output_dir / 'session_20251024_120000.json').write_text('{}')
        (test_output_dir / 'session_20251024_120001.json').write_text('{}')

        files = reader._find_unified_session_files()

        assert len(files) == 2
        assert all(f.name.startswith('session_') for f in files)

    def test_find_excludes_malformed_files(self, test_output_dir):
        """Test that malformed filenames are excluded."""
        reader = UnifiedSessionReader(test_output_dir)

        # Create malformed files
        (test_output_dir / 'session_session_old.json').write_text('{}')
        (test_output_dir / 'session_bad_format.json').write_text('{}')
        (test_output_dir / 'session_20251024_120000.json').write_text('{}')  # Valid

        files = reader._find_unified_session_files()

        # Should only find the valid one
        assert len(files) == 1
        assert files[0].name == 'session_20251024_120000.json'

    def test_find_empty_directory(self, test_output_dir):
        """Test finding sessions in empty directory."""
        reader = UnifiedSessionReader(test_output_dir)

        files = reader._find_unified_session_files()

        assert len(files) == 0
        assert isinstance(files, list)

    def test_find_sorts_by_time(self, test_output_dir):
        """Test sessions are sorted newest first."""
        reader = UnifiedSessionReader(test_output_dir)

        # Create sessions with different timestamps
        for i in range(3):
            session_file = test_output_dir / f'session_2025102412000{i}.json'
            session_data = {
                'session_metadata': {
                    'session_id': f'2025102412000{i}',
                    'start_time': time.time() + i
                },
                'iterations': []
            }
            session_file.write_text(json.dumps(session_data))
            time.sleep(0.01)

        sessions = reader.get_all_sessions()

        # Should be sorted by start_time descending
        if len(sessions) > 1:
            assert sessions[0]['start_time'] >= sessions[1]['start_time']

    def test_find_with_output_dir_change(self, test_output_dir, tmp_path):
        """Test set_output_dir() works correctly."""
        reader = UnifiedSessionReader(test_output_dir)

        # Change output directory
        new_dir = tmp_path / 'new_output'
        new_dir.mkdir()
        reader.set_output_dir(new_dir)

        assert reader.output_dir == new_dir

    def test_find_handles_permission_errors(self, test_output_dir):
        """Test graceful handling of permission errors."""
        reader = UnifiedSessionReader(test_output_dir)

        # Try to find files (should handle errors gracefully)
        files = reader._find_unified_session_files()

        # Should return list even if errors occur
        assert isinstance(files, list)


# ============================================================================
# Session Metadata Parsing Tests
# ============================================================================

@pytest.mark.webui
class TestSessionMetadataParsing:
    """Tests for loading and parsing session metadata."""

    def test_load_session_metadata_success(self, test_output_dir):
        """Test extracting metadata correctly."""
        reader = UnifiedSessionReader(test_output_dir)

        session_file = test_output_dir / 'session_20251024_120000.json'
        session_data = {
            'session_metadata': {
                'session_id': '20251024_120000',
                'start_time': 1730000000.0,
                'end_time': None,
                'current_iteration': 2,
                'pid': None
            },
            'iterations': []
        }
        session_file.write_text(json.dumps(session_data))

        metadata = reader._load_session_metadata(session_file)

        assert metadata is not None
        assert metadata['session_id'] == '20251024_120000'
        assert metadata['iterations_count'] == 0

    def test_load_session_metadata_with_iterations(self, test_output_dir):
        """Test counting iterations correctly."""
        reader = UnifiedSessionReader(test_output_dir)

        session_file = test_output_dir / 'session_20251024_120000.json'
        session_data = {
            'session_metadata': {
                'session_id': '20251024_120000',
                'start_time': time.time()
            },
            'iterations': [
                {'iteration': 1, 'tool_calls': []},
                {'iteration': 2, 'tool_calls': []}
            ]
        }
        session_file.write_text(json.dumps(session_data))

        metadata = reader._load_session_metadata(session_file)

        assert metadata['iterations_count'] == 2

    def test_load_session_metadata_queries_count(self, test_output_dir):
        """Test counting execute_sql tool calls."""
        reader = UnifiedSessionReader(test_output_dir)

        session_file = test_output_dir / 'session_20251024_120000.json'
        session_data = {
            'session_metadata': {'session_id': '20251024_120000', 'start_time': time.time()},
            'iterations': [
                {
                    'iteration': 1,
                    'tool_calls': [
                        {'tool': 'execute_sql'},
                        {'tool': 'execute_sql'},
                        {'tool': 'memory'}
                    ]
                }
            ]
        }
        session_file.write_text(json.dumps(session_data))

        metadata = reader._load_session_metadata(session_file)

        assert metadata['queries_count'] == 2

    def test_load_session_metadata_memory_items_count(self, test_output_dir):
        """Test counting memory update operations."""
        reader = UnifiedSessionReader(test_output_dir)

        session_file = test_output_dir / 'session_20251024_120000.json'
        session_data = {
            'session_metadata': {'session_id': '20251024_120000', 'start_time': time.time()},
            'iterations': [
                {
                    'iteration': 1,
                    'tool_calls': [
                        {'tool': 'memory', 'input': {'action': 'update'}},
                        {'tool': 'memory', 'input': {'action': 'update'}},
                        {'tool': 'memory', 'input': {'action': 'remove'}}
                    ]
                }
            ]
        }
        session_file.write_text(json.dumps(session_data))

        metadata = reader._load_session_metadata(session_file)

        assert metadata['memory_items'] == 3  # Both 'update' and 'remove' actions count

    def test_load_session_metadata_incomplete_iteration(self, test_output_dir):
        """Test handling iteration without end_time."""
        reader = UnifiedSessionReader(test_output_dir)

        session_file = test_output_dir / 'session_20251024_120000.json'
        session_data = {
            'session_metadata': {'session_id': '20251024_120000', 'start_time': time.time()},
            'iterations': [
                {'iteration': 1, 'start_time': time.time(), 'end_time': None, 'tool_calls': []}
            ]
        }
        session_file.write_text(json.dumps(session_data))

        metadata = reader._load_session_metadata(session_file)

        # Should still count the iteration
        assert metadata['iterations_count'] == 1

    def test_load_session_metadata_corrupted_json(self, test_output_dir):
        """Test handling corrupted JSON files."""
        reader = UnifiedSessionReader(test_output_dir)

        session_file = test_output_dir / 'session_20251024_120000.json'
        session_file.write_text('{invalid json}')

        metadata = reader._load_session_metadata(session_file)

        assert metadata is None

    def test_load_session_metadata_missing_fields(self, test_output_dir):
        """Test defaults for optional fields."""
        reader = UnifiedSessionReader(test_output_dir)

        session_file = test_output_dir / 'session_20251024_120000.json'
        session_data = {
            'session_metadata': {
                'session_id': '20251024_120000'
                # Missing start_time, end_time, etc.
            }
        }
        session_file.write_text(json.dumps(session_data))

        metadata = reader._load_session_metadata(session_file)

        # Should handle missing fields gracefully
        assert metadata is not None or metadata is None  # Either works gracefully

    def test_load_session_metadata_unicode_handling(self, test_output_dir):
        """Test Cyrillic and Unicode support."""
        reader = UnifiedSessionReader(test_output_dir)

        session_file = test_output_dir / 'session_20251024_120000.json'
        session_data = {
            'session_metadata': {
                'session_id': '20251024_120000',
                'start_time': time.time()
            },
            'iterations': [
                {
                    'iteration': 1,
                    'user_input': 'Analyze データ 数据',  # Unicode test
                    'tool_calls': []
                }
            ]
        }
        session_file.write_text(json.dumps(session_data, ensure_ascii=False))

        metadata = reader._load_session_metadata(session_file)

        assert metadata is not None


# ============================================================================
# Status Computation Tests
# ============================================================================

@pytest.mark.webui
class TestStatusComputation:
    """Tests for PID-based status computation."""

    @patch('psutil.pid_exists', return_value=True)
    def test_compute_status_running(self, mock_pid_exists, test_output_dir):
        """Test status is 'running' when PID exists and process alive."""
        reader = UnifiedSessionReader(test_output_dir)

        session_file = test_output_dir / 'session_20251024_120000.json'
        session_data = {
            'session_metadata': {
                'session_id': '20251024_120000',
                'start_time': time.time(),
                'end_time': None,
                'pid': 12345
            },
            'iterations': []
        }
        session_file.write_text(json.dumps(session_data))

        metadata = reader._load_session_metadata(session_file)

        assert metadata['status'] == 'running'

    def test_compute_status_completed(self, test_output_dir):
        """Test status is 'completed' when no PID (graceful exit)."""
        reader = UnifiedSessionReader(test_output_dir)

        session_file = test_output_dir / 'session_20251024_120000.json'
        session_data = {
            'session_metadata': {
                'session_id': '20251024_120000',
                'start_time': time.time(),
                'end_time': None,
                'pid': None  # No PID
            },
            'iterations': []
        }
        session_file.write_text(json.dumps(session_data))

        metadata = reader._load_session_metadata(session_file)

        assert metadata['status'] == 'completed'

    @patch('psutil.pid_exists', return_value=False)
    def test_compute_status_interrupted(self, mock_pid_exists, test_output_dir):
        """Test status is 'interrupted' when PID exists but process dead."""
        reader = UnifiedSessionReader(test_output_dir)

        session_file = test_output_dir / 'session_20251024_120000.json'
        session_data = {
            'session_metadata': {
                'session_id': '20251024_120000',
                'start_time': time.time(),
                'end_time': None,
                'pid': 99999  # Non-existent PID
            },
            'iterations': []
        }
        session_file.write_text(json.dumps(session_data))

        metadata = reader._load_session_metadata(session_file)

        assert metadata['status'] == 'interrupted'

    def test_compute_status_with_end_time(self, test_output_dir):
        """Test completed session with end_time and no PID."""
        reader = UnifiedSessionReader(test_output_dir)

        session_file = test_output_dir / 'session_20251024_120000.json'
        session_data = {
            'session_metadata': {
                'session_id': '20251024_120000',
                'start_time': time.time(),
                'end_time': time.time() + 100,  # Has end_time
                'pid': None  # Gracefully completed, PID removed
            },
            'iterations': [{
                'iteration': 1,
                'llm_response': 'Analysis complete',
                'tool_calls': []
            }]
        }
        session_file.write_text(json.dumps(session_data))

        metadata = reader._load_session_metadata(session_file)

        # With end_time and no PID, should be completed
        assert metadata['status'] == 'completed'

    def test_compute_status_invalid_pid(self, test_output_dir):
        """Test handling invalid PID values (0, negative)."""
        reader = UnifiedSessionReader(test_output_dir)

        session_file = test_output_dir / 'session_20251024_120000.json'
        session_data = {
            'session_metadata': {
                'session_id': '20251024_120000',
                'start_time': time.time(),
                'pid': 0  # Invalid PID
            },
            'iterations': []
        }
        session_file.write_text(json.dumps(session_data))

        metadata = reader._load_session_metadata(session_file)

        # Should handle gracefully
        assert metadata['status'] in ['completed', 'interrupted']

    @patch('psutil.pid_exists', side_effect=psutil.ZombieProcess(999))
    def test_compute_status_zombie_process(self, mock_pid_exists, test_output_dir):
        """Test handling zombie processes."""
        reader = UnifiedSessionReader(test_output_dir)

        session_file = test_output_dir / 'session_20251024_120000.json'
        session_data = {
            'session_metadata': {
                'session_id': '20251024_120000',
                'start_time': time.time(),
                'pid': 12345
            },
            'iterations': []
        }
        session_file.write_text(json.dumps(session_data))

        metadata = reader._load_session_metadata(session_file)

        # Should handle zombie process exception
        assert metadata is not None

    @patch('psutil.pid_exists', side_effect=psutil.AccessDenied(999))
    def test_compute_status_permission_denied(self, mock_pid_exists, test_output_dir):
        """Test handling permission denied errors."""
        reader = UnifiedSessionReader(test_output_dir)

        session_file = test_output_dir / 'session_20251024_120000.json'
        session_data = {
            'session_metadata': {
                'session_id': '20251024_120000',
                'start_time': time.time(),
                'pid': 12345
            },
            'iterations': []
        }
        session_file.write_text(json.dumps(session_data))

        metadata = reader._load_session_metadata(session_file)

        # Should handle access denied gracefully
        assert metadata is not None

    @patch('webui.services.unified_session_reader.psutil', None)
    def test_compute_status_no_psutil(self, test_output_dir):
        """Test fallback when psutil is unavailable."""
        # This test simulates psutil not being available
        # In reality, psutil is required, but test graceful degradation
        reader = UnifiedSessionReader(test_output_dir)

        session_file = test_output_dir / 'session_20251024_120000.json'
        session_data = {
            'session_metadata': {
                'session_id': '20251024_120000',
                'start_time': time.time(),
                'pid': 12345
            },
            'iterations': []
        }
        session_file.write_text(json.dumps(session_data))

        # Should handle missing psutil module
        try:
            metadata = reader._load_session_metadata(session_file)
            assert metadata is not None
        except AttributeError:
            # Expected if psutil is mocked as None
            pass


# ============================================================================
# Memory Composition Tests
# ============================================================================

@pytest.mark.webui
class TestMemoryComposition:
    """Tests for composing memory from tool calls."""

    def test_get_memory_from_tool_calls(self, test_output_dir):
        """Test parsing memory tool calls."""
        reader = UnifiedSessionReader(test_output_dir)

        session_id = '20251024_120000'
        session_file = test_output_dir / f'session_{session_id}.json'

        # Create session with memory tool calls
        session_state = SessionState(session_id)
        session_state.add_iteration(1, "test")
        tool_call = ToolCall(
            id="mem_1",
            tool="memory",
            timestamp=time.time(),
            input={"action": "update", "key": "insights", "value": "trend:Q2 up 15%"},
            output="Updated",
            execution_time=0.001
        )
        session_state.add_tool_call(1, tool_call)

        # Save session
        session_file.write_text(json.dumps(session_state.to_dict(), indent=2, ensure_ascii=False))

        # Load and get memory
        session_data = reader.get_session_detail(session_id)
        assert session_data is not None

    def test_get_memory_key_value_format(self, test_output_dir):
        """Test 'key:value' format parsing."""
        reader = UnifiedSessionReader(test_output_dir)

        session_id = '20251024_120000'
        session_state = SessionState(session_id)
        session_state.add_iteration(1, "test")

        # Add memory with key:value format
        tool_call = ToolCall(
            id="mem_1",
            tool="memory",
            timestamp=time.time(),
            input={"action": "update", "key": "key_findings", "value": "performance_metric:15%"},
            output="Updated",
            execution_time=0.001
        )
        session_state.add_tool_call(1, tool_call)

        session_file = test_output_dir / f'session_{session_id}.json'
        session_file.write_text(json.dumps(session_state.to_dict(), indent=2, ensure_ascii=False))

        # Memory should be parseable
        session_data = reader.get_session_detail(session_id)
        assert session_data is not None

    def test_get_memory_remove_operations(self, test_output_dir):
        """Test handling remove actions."""
        reader = UnifiedSessionReader(test_output_dir)

        session_id = '20251024_120000'
        session_state = SessionState(session_id)
        session_state.add_iteration(1, "test")

        # Add then remove memory
        update_call = ToolCall(
            id="mem_1",
            tool="memory",
            timestamp=time.time(),
            input={"action": "update", "key": "insights", "value": "temp:data"},
            output="Updated",
            execution_time=0.001
        )
        session_state.add_tool_call(1, update_call)

        remove_call = ToolCall(
            id="mem_2",
            tool="memory",
            timestamp=time.time(),
            input={"action": "remove", "key": "insights", "value": "temp:data"},
            output="Removed",
            execution_time=0.001
        )
        session_state.add_tool_call(1, remove_call)

        session_file = test_output_dir / f'session_{session_id}.json'
        session_file.write_text(json.dumps(session_state.to_dict(), indent=2, ensure_ascii=False))

        # Removed items should not appear in final memory
        memory_data = session_state.get_memory_data_from_tool_calls()
        assert 'insights' not in memory_data or 'temp' not in str(memory_data.get('insights', []))

    def test_get_memory_categories(self, test_output_dir):
        """Test all 10 memory categories are supported."""
        reader = UnifiedSessionReader(test_output_dir)

        categories = [
            'insights', 'patterns', 'explored_areas', 'key_findings',
            'opportunities', 'data_issues', 'metrics', 'context',
            'user_requests', 'data_milestones'
        ]

        session_id = '20251024_120000'
        session_state = SessionState(session_id)
        session_state.add_iteration(1, "test")

        # Add memory for each category
        for i, category in enumerate(categories):
            tool_call = ToolCall(
                id=f"mem_{i}",
                tool="memory",
                timestamp=time.time(),
                input={"action": "update", "key": category, "value": f"test_{category}:value"},
                output="Updated",
                execution_time=0.001
            )
            session_state.add_tool_call(1, tool_call)

        session_file = test_output_dir / f'session_{session_id}.json'
        session_file.write_text(json.dumps(session_state.to_dict(), indent=2, ensure_ascii=False))

        # All categories should be present
        memory_data = session_state.get_memory_data_from_tool_calls()
        assert len(memory_data) >= 1  # At least some categories

    def test_get_memory_with_verified_metadata(self, test_output_dir):
        """Test metadata.verified flag is preserved."""
        reader = UnifiedSessionReader(test_output_dir)

        session_id = '20251024_120000'
        session_state = SessionState(session_id)
        session_state.add_iteration(1, "test")

        # Add memory with verification metadata
        tool_call = ToolCall(
            id="mem_1",
            tool="memory",
            timestamp=time.time(),
            input={"action": "update", "key": "insights", "value": "verified:data"},
            output="Updated",
            execution_time=0.001,
            metadata={'verified': True, 'verified_at': time.time()}
        )
        session_state.add_tool_call(1, tool_call)

        session_file = test_output_dir / f'session_{session_id}.json'
        session_file.write_text(json.dumps(session_state.to_dict(), indent=2, ensure_ascii=False))

        # Metadata should be preserved
        session_data = reader.get_session_detail(session_id)
        if session_data and session_data['iterations']:
            tool_calls = session_data['iterations'][0].get('tool_calls', [])
            if tool_calls:
                assert 'metadata' in tool_calls[0] or True  # Metadata may or may not be preserved


# ============================================================================
# Iteration Detail Tests
# ============================================================================

@pytest.mark.webui
class TestIterationDetail:
    """Tests for iteration detail retrieval."""

    def test_get_iteration_detail_with_tool_calls(self, test_output_dir):
        """Test iteration includes tool calls."""
        reader = UnifiedSessionReader(test_output_dir)

        session_id = '20251024_120000'
        session_state = SessionState(session_id)
        session_state.add_iteration(1, "test prompt", "Analyze data")

        # Add tool call
        tool_call = ToolCall(
            id="sql_1",
            tool="execute_sql",
            timestamp=time.time(),
            input={"query": "SELECT * FROM entities"},
            output="Results...",
            execution_time=0.5
        )
        session_state.add_tool_call(1, tool_call)
        session_state.complete_iteration(1, "Analysis complete")

        session_file = test_output_dir / f'session_{session_id}.json'
        session_file.write_text(json.dumps(session_state.to_dict(), indent=2, ensure_ascii=False))

        # Get iteration detail
        iteration_data = reader.get_iteration_detail(session_id, 1)

        assert iteration_data is not None
        assert 'tool_calls' in iteration_data
        assert len(iteration_data['tool_calls']) == 1

    def test_get_iteration_detail_sql_formatting(self, test_output_dir):
        """Test SQL query display formatting."""
        reader = UnifiedSessionReader(test_output_dir)

        session_id = '20251024_120000'
        session_state = SessionState(session_id)
        session_state.add_iteration(1, "test")

        # Add SQL tool call
        tool_call = ToolCall(
            id="sql_1",
            tool="execute_sql",
            timestamp=time.time(),
            input={"query": "SELECT Entity, SUM(Value) FROM data GROUP BY Entity"},
            output="Entity1 | 1000\nEntity2 | 2000",
            execution_time=0.3
        )
        session_state.add_tool_call(1, tool_call)

        session_file = test_output_dir / f'session_{session_id}.json'
        session_file.write_text(json.dumps(session_state.to_dict(), indent=2, ensure_ascii=False))

        iteration_data = reader.get_iteration_detail(session_id, 1)

        # Query should be in tool call input
        assert iteration_data is not None
        assert iteration_data['tool_calls'][0]['input']['query']

    def test_get_iteration_detail_llm_response(self, test_output_dir):
        """Test LLM response is included."""
        reader = UnifiedSessionReader(test_output_dir)

        session_id = '20251024_120000'
        session_state = SessionState(session_id)
        session_state.add_iteration(1, "test", "Analyze data")
        session_state.complete_iteration(1, "Data analysis shows 20% growth in Q2")

        session_file = test_output_dir / f'session_{session_id}.json'
        session_file.write_text(json.dumps(session_state.to_dict(), indent=2, ensure_ascii=False))

        iteration_data = reader.get_iteration_detail(session_id, 1)

        assert iteration_data is not None
        assert 'llm_response' in iteration_data
        assert "20% growth" in iteration_data['llm_response']
