"""
Unit Tests for Session Persistence

Tests for SessionPersistence class covering save/load operations,
file management, and error handling.
"""

import pytest
import json
import time
from pathlib import Path
from freezegun import freeze_time
from core.session_persistence import SessionPersistence
from core.session_state import SessionState


# ============================================================================
# Basic Save/Load Tests
# ============================================================================

@pytest.mark.unit
class TestSessionPersistenceBasics:
    """Tests for basic save and load operations."""

    def test_init_creates_output_dir(self, tmp_path):
        """Test that initialization creates output directory."""
        output_dir = tmp_path / "test_output"
        persistence = SessionPersistence(output_dir)

        assert output_dir.exists()
        assert output_dir.is_dir()

    def test_save_session(self, test_output_dir, sample_session):
        """Test saving a session to file."""
        persistence = SessionPersistence(test_output_dir)

        session_file = persistence.save_session(sample_session)

        assert session_file.exists()
        assert session_file.name == f"session_{sample_session.metadata.session_id}.json"

    def test_save_updates_timestamp(self, test_output_dir, sample_session):
        """Test that save updates last_save_time."""
        persistence = SessionPersistence(test_output_dir)

        # Set old_time explicitly to a known value in the past
        old_time = time.time() - 1.0
        sample_session.metadata.last_save_time = old_time

        persistence.save_session(sample_session)

        # The save should update the timestamp to current time (which is > old_time)
        assert sample_session.metadata.last_save_time > old_time

    def test_load_session(self, test_output_dir, sample_session_file):
        """Test loading a session from file."""
        persistence = SessionPersistence(test_output_dir)

        loaded_session = persistence.load_session(sample_session_file)

        assert loaded_session is not None
        assert isinstance(loaded_session, SessionState)

    def test_load_nonexistent_file(self, test_output_dir):
        """Test loading non-existent session file."""
        persistence = SessionPersistence(test_output_dir)
        fake_file = test_output_dir / "session_nonexistent.json"

        with pytest.raises(FileNotFoundError):
            persistence.load_session(fake_file)

    def test_save_load_roundtrip(self, test_output_dir, sample_session):
        """Test that save and load preserve session data."""
        persistence = SessionPersistence(test_output_dir)

        # Save
        session_file = persistence.save_session(sample_session)

        # Load
        loaded_session = persistence.load_session(session_file)

        # Compare key attributes
        assert loaded_session.metadata.session_id == sample_session.metadata.session_id
        assert len(loaded_session.iterations) == len(sample_session.iterations)
        if sample_session.iterations:
            assert loaded_session.iterations[0].llm_response == sample_session.iterations[0].llm_response


# ============================================================================
# File Type Detection Tests (via load_session behavior)
# ============================================================================

@pytest.mark.unit
class TestFileTypeDetection:
    """Tests for file type detection through load_session behavior."""

    def test_load_valid_session_file(self, test_output_dir, sample_session_file):
        """Test that valid session file loads successfully."""
        persistence = SessionPersistence(test_output_dir)

        # Should load without error
        session = persistence.load_session(sample_session_file)

        assert session is not None
        assert session.metadata.session_id is not None

    def test_load_invalid_structure_raises_error(self, test_output_dir):
        """Test that invalid JSON structure raises error."""
        persistence = SessionPersistence(test_output_dir)

        # Create invalid JSON file (valid JSON but wrong structure)
        invalid_file = test_output_dir / "invalid.json"
        with open(invalid_file, 'w') as f:
            f.write("{\"invalid\": \"data\"}")

        with pytest.raises(RuntimeError, match="Unknown file format"):
            persistence.load_session(invalid_file)

    def test_load_nonexistent_file_raises_error(self, test_output_dir):
        """Test that non-existent file raises error."""
        persistence = SessionPersistence(test_output_dir)
        fake_file = test_output_dir / "fake.json"

        with pytest.raises(FileNotFoundError, match="Session file not found"):
            persistence.load_session(fake_file)

    def test_load_corrupted_json_raises_error(self, test_output_dir):
        """Test that corrupted JSON file raises error."""
        persistence = SessionPersistence(test_output_dir)

        # Create corrupted JSON file
        corrupted_file = test_output_dir / "corrupted.json"
        with open(corrupted_file, 'w') as f:
            f.write("{ invalid json }")

        with pytest.raises(RuntimeError, match="Corrupted session file"):
            persistence.load_session(corrupted_file)


# ============================================================================
# File Listing and Discovery Tests
# ============================================================================

@pytest.mark.unit
class TestFileListingAndDiscovery:
    """Tests for listing and finding session files."""

    def test_list_session_files_empty(self, test_output_dir):
        """Test listing files in empty directory."""
        persistence = SessionPersistence(test_output_dir)

        files = persistence.list_session_files()

        assert isinstance(files, list)
        assert len(files) == 0

    def test_list_session_files(self, test_output_dir, multiple_session_files):
        """Test listing multiple session files."""
        persistence = SessionPersistence(test_output_dir)

        files = persistence.list_session_files()

        assert len(files) == 3
        assert all(f.name.startswith("session_") for f in files)

    def test_list_session_files_sorted(self, test_output_dir, multiple_session_files):
        """Test that session files are sorted by modification time."""
        persistence = SessionPersistence(test_output_dir)

        files = persistence.list_session_files()

        # Should be sorted newest first
        mod_times = [f.stat().st_mtime for f in files]
        assert mod_times == sorted(mod_times, reverse=True)

    def test_find_latest_session_empty(self, test_output_dir):
        """Test finding latest session in empty directory."""
        persistence = SessionPersistence(test_output_dir)

        latest = persistence.find_latest_session()

        assert latest is None

    def test_find_latest_session(self, test_output_dir, multiple_session_files):
        """Test finding latest session file."""
        persistence = SessionPersistence(test_output_dir)

        latest = persistence.find_latest_session()

        assert latest is not None
        assert latest.exists()
        assert latest.name.startswith("session_")


# ============================================================================
# Session Summary Tests
# ============================================================================

@pytest.mark.unit
class TestSessionSummary:
    """Tests for session summary extraction."""

    def test_get_session_summary(self, test_output_dir, sample_session_file):
        """Test getting session summary."""
        persistence = SessionPersistence(test_output_dir)

        summary = persistence.get_session_summary(sample_session_file)

        assert isinstance(summary, dict)
        assert "session_id" in summary
        assert "iteration_count" in summary
        assert "file_size" in summary
        assert "modified_time" in summary

    def test_get_session_summary_with_iterations(self, test_output_dir, sample_session):
        """Test summary includes iteration count."""
        persistence = SessionPersistence(test_output_dir)
        session_file = persistence.save_session(sample_session)

        summary = persistence.get_session_summary(session_file)

        assert summary["iteration_count"] == len(sample_session.iterations)

    def test_get_session_summary_error_handling(self, test_output_dir):
        """Test summary handles corrupted files gracefully."""
        persistence = SessionPersistence(test_output_dir)

        # Create corrupted file
        corrupted_file = test_output_dir / "session_corrupted.json"
        with open(corrupted_file, 'w') as f:
            f.write("{ invalid }")

        summary = persistence.get_session_summary(corrupted_file)

        assert summary["session_id"] == "error"
        assert "error" in summary


# ============================================================================
# Error Handling Tests
# ============================================================================

@pytest.mark.unit
class TestErrorHandling:
    """Tests for error handling in persistence operations."""

    def test_load_corrupted_json(self, test_output_dir):
        """Test loading corrupted JSON file."""
        persistence = SessionPersistence(test_output_dir)

        # Create corrupted file
        corrupted_file = test_output_dir / "session_corrupted.json"
        with open(corrupted_file, 'w') as f:
            f.write("{ invalid json ")

        with pytest.raises(RuntimeError, match="Corrupted session file"):
            persistence.load_session(corrupted_file)

    def test_load_invalid_structure(self, test_output_dir):
        """Test loading file with invalid structure."""
        persistence = SessionPersistence(test_output_dir)

        # Create file with invalid structure
        invalid_file = test_output_dir / "session_invalid.json"
        with open(invalid_file, 'w') as f:
            json.dump({"invalid": "structure"}, f)

        with pytest.raises(RuntimeError):
            persistence.load_session(invalid_file)

    def test_save_handles_encoding(self, test_output_dir, session_id):
        """Test that save handles non-ASCII characters properly."""
        persistence = SessionPersistence(test_output_dir)

        # Create session with Cyrillic characters
        session = SessionState(session_id=session_id)
        iteration = session.add_iteration(
            iteration_num=1,
            prompt="Analyze",
            user_input="Проанализируй магазины"  # Cyrillic text
        )

        # Save should not raise
        session_file = persistence.save_session(session)

        # Load and verify
        loaded = persistence.load_session(session_file)
        assert loaded.iterations[0].user_input == "Проанализируй магазины"


# ============================================================================
# Integration with SessionState Tests
# ============================================================================

@pytest.mark.unit
class TestSessionStateIntegration:
    """Tests for integration with SessionState."""

    def test_save_preserves_tool_calls(self, test_output_dir, sample_session):
        """Test that tool calls are preserved through save/load."""
        persistence = SessionPersistence(test_output_dir)

        session_file = persistence.save_session(sample_session)
        loaded = persistence.load_session(session_file)

        original_tool_calls = sample_session.iterations[0].tool_calls
        loaded_tool_calls = loaded.iterations[0].tool_calls

        assert len(loaded_tool_calls) == len(original_tool_calls)
        assert loaded_tool_calls[0].tool == original_tool_calls[0].tool

    def test_save_preserves_metadata(self, test_output_dir, sample_session):
        """Test that metadata is preserved through save/load."""
        persistence = SessionPersistence(test_output_dir)

        # Add PID to metadata
        sample_session.metadata.pid = 12345

        session_file = persistence.save_session(sample_session)
        loaded = persistence.load_session(session_file)

        assert loaded.metadata.session_id == sample_session.metadata.session_id
        assert loaded.metadata.start_time == sample_session.metadata.start_time
        assert loaded.metadata.pid == sample_session.metadata.pid

    def test_save_preserves_memory_data(self, test_output_dir, sample_session_with_memory):
        """Test that memory data is preserved through save/load."""
        persistence = SessionPersistence(test_output_dir)

        original_memory = sample_session_with_memory.get_memory_data_from_tool_calls()

        session_file = persistence.save_session(sample_session_with_memory)
        loaded = persistence.load_session(session_file)

        loaded_memory = loaded.get_memory_data_from_tool_calls()

        assert loaded_memory == original_memory
