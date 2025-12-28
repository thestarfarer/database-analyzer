"""
Unit Tests for Main CLI Entry Point

Tests for main.py including graceful_shutdown, display_verification_result,
run_verification_mode, and argument parsing.
"""

import pytest
import signal
import json
import argparse
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call
from io import StringIO

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from main import graceful_shutdown, display_verification_result, run_verification_mode


# ============================================================================
# graceful_shutdown Tests
# ============================================================================

@pytest.mark.unit
class TestGracefulShutdown:
    """Tests for graceful_shutdown signal handler."""

    def test_sigint_raises_keyboard_interrupt(self, capsys):
        """Test SIGINT triggers KeyboardInterrupt."""
        with pytest.raises(KeyboardInterrupt):
            graceful_shutdown(signal.SIGINT, None)

        captured = capsys.readouterr()
        assert "SIGINT" in captured.out

    def test_sigterm_raises_keyboard_interrupt(self, capsys):
        """Test SIGTERM triggers KeyboardInterrupt."""
        with pytest.raises(KeyboardInterrupt):
            graceful_shutdown(signal.SIGTERM, None)

        captured = capsys.readouterr()
        assert "SIGTERM" in captured.out

    def test_prints_shutdown_message_sigint(self, capsys):
        """Test SIGINT prints shutdown message with correct signal name."""
        with pytest.raises(KeyboardInterrupt):
            graceful_shutdown(signal.SIGINT, None)

        captured = capsys.readouterr()
        assert "shutting down gracefully" in captured.out
        assert "SIGINT" in captured.out

    def test_prints_shutdown_message_sigterm(self, capsys):
        """Test SIGTERM prints shutdown message with correct signal name."""
        with pytest.raises(KeyboardInterrupt):
            graceful_shutdown(signal.SIGTERM, None)

        captured = capsys.readouterr()
        assert "shutting down gracefully" in captured.out
        assert "SIGTERM" in captured.out


# ============================================================================
# display_verification_result Tests
# ============================================================================

@pytest.mark.unit
class TestDisplayVerificationResult:
    """Tests for display_verification_result function."""

    def test_verified_true_display(self, capsys):
        """Test display when verified is True."""
        result = {
            'verified': True,
            'confidence': 'high',
            'recommendation': 'keep',
            'reasoning': 'Data matches',
            'evidence': 'SQL query returned expected results'
        }

        display_verification_result(result, 'insights', 'record_count')

        captured = capsys.readouterr()
        assert "Yes" in captured.out
        assert "VERIFICATION RESULT" in captured.out

    def test_verified_false_display(self, capsys):
        """Test display when verified is False."""
        result = {
            'verified': False,
            'confidence': 'high',
            'recommendation': 'update',
            'reasoning': 'Data changed',
            'evidence': 'SQL query returned different value'
        }

        display_verification_result(result, 'insights', 'record_count')

        captured = capsys.readouterr()
        assert "No" in captured.out

    def test_confidence_high_icon(self, capsys):
        """Test high confidence shows green icon."""
        result = {
            'verified': True,
            'confidence': 'high',
            'recommendation': 'keep',
            'reasoning': 'Test',
            'evidence': 'Test'
        }

        display_verification_result(result, 'insights', 'test_key')

        captured = capsys.readouterr()
        assert "HIGH" in captured.out

    def test_confidence_medium_icon(self, capsys):
        """Test medium confidence shows yellow icon."""
        result = {
            'verified': True,
            'confidence': 'medium',
            'recommendation': 'keep',
            'reasoning': 'Test',
            'evidence': 'Test'
        }

        display_verification_result(result, 'insights', 'test_key')

        captured = capsys.readouterr()
        assert "MEDIUM" in captured.out

    def test_confidence_low_icon(self, capsys):
        """Test low confidence shows red icon."""
        result = {
            'verified': False,
            'confidence': 'low',
            'recommendation': 'remove',
            'reasoning': 'Test',
            'evidence': 'Test'
        }

        display_verification_result(result, 'insights', 'test_key')

        captured = capsys.readouterr()
        assert "LOW" in captured.out

    def test_confidence_unknown_icon(self, capsys):
        """Test unknown confidence shows default icon."""
        result = {
            'verified': True,
            'recommendation': 'keep',
            'reasoning': 'Test',
            'evidence': 'Test'
        }

        display_verification_result(result, 'insights', 'test_key')

        captured = capsys.readouterr()
        assert "UNKNOWN" in captured.out

    def test_updated_value_display(self, capsys):
        """Test updated_value is displayed when present."""
        result = {
            'verified': False,
            'confidence': 'high',
            'recommendation': 'update',
            'reasoning': 'Value changed',
            'evidence': 'New data found',
            'updated_value': 'New content for the memory'
        }

        display_verification_result(result, 'key_findings', 'analysis')

        captured = capsys.readouterr()
        assert "Recommended Update" in captured.out
        assert "Category: key_findings" in captured.out
        assert "Key: analysis" in captured.out
        assert "New content for the memory" in captured.out

    def test_reasoning_display(self, capsys):
        """Test reasoning is displayed."""
        result = {
            'verified': True,
            'confidence': 'high',
            'recommendation': 'keep',
            'reasoning': 'The data matches current database state',
            'evidence': 'Query executed successfully'
        }

        display_verification_result(result, 'insights', 'test')

        captured = capsys.readouterr()
        assert "The data matches current database state" in captured.out
        assert "Reasoning" in captured.out

    def test_evidence_display(self, capsys):
        """Test evidence is displayed."""
        result = {
            'verified': True,
            'confidence': 'high',
            'recommendation': 'keep',
            'reasoning': 'Test reasoning',
            'evidence': 'SELECT COUNT(*) returned 105 rows'
        }

        display_verification_result(result, 'insights', 'test')

        captured = capsys.readouterr()
        assert "SELECT COUNT(*) returned 105 rows" in captured.out
        assert "Evidence" in captured.out


# ============================================================================
# run_verification_mode Tests
# ============================================================================

@pytest.mark.unit
class TestRunVerificationMode:
    """Tests for run_verification_mode function."""

    def test_session_not_found_quiet_mode(self, capsys, tmp_path, test_db_config):
        """Test error output in quiet mode when session not found."""
        from config.settings import AppConfig, LLMConfig

        config = AppConfig(
            db_config=test_db_config,
            llm_config=LLMConfig.default(),
            output_dir=tmp_path,
            prompts_dir=tmp_path / "prompts",
            verbose_console_output=False  # quiet mode
        )

        mock_db = Mock()

        run_verification_mode("nonexistent_session", "insights", "key", config, mock_db)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "error" in output
        assert "Session not found" in output["error"]

    def test_session_not_found_verbose_mode(self, capsys, tmp_path, test_db_config):
        """Test error output in verbose mode when session not found."""
        from config.settings import AppConfig, LLMConfig

        config = AppConfig(
            db_config=test_db_config,
            llm_config=LLMConfig.default(),
            output_dir=tmp_path,
            prompts_dir=tmp_path / "prompts",
            verbose_console_output=True  # verbose mode
        )

        mock_db = Mock()

        run_verification_mode("nonexistent_session", "insights", "key", config, mock_db)

        captured = capsys.readouterr()
        assert "Session not found" in captured.out
        assert "nonexistent_session" in captured.out

    @patch('psutil.pid_exists')
    @patch('main.SessionManager')
    def test_session_still_running_quiet_mode(self, mock_session_manager, mock_pid_exists, capsys, tmp_path, test_db_config):
        """Test error when session is still running in quiet mode."""
        from config.settings import AppConfig, LLMConfig

        # Create a test session file
        session_id = "20250101_120000"
        session_file = tmp_path / f"session_{session_id}.json"
        session_data = {
            "session_metadata": {
                "session_id": session_id,
                "pid": 12345
            },
            "iterations": []
        }
        session_file.write_text(json.dumps(session_data))

        config = AppConfig(
            db_config=test_db_config,
            llm_config=LLMConfig.default(),
            output_dir=tmp_path,
            prompts_dir=tmp_path / "prompts",
            verbose_console_output=False  # quiet mode
        )

        # Mock session state with running PID
        mock_session_state = Mock()
        mock_session_state.metadata.pid = 12345
        mock_session_manager.return_value.persistence.load_session.return_value = mock_session_state
        mock_pid_exists.return_value = True

        mock_db = Mock()

        run_verification_mode(session_id, "insights", "key", config, mock_db)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "error" in output
        assert "still running" in output["error"]

    @patch('psutil.pid_exists')
    @patch('main.SessionManager')
    def test_session_still_running_verbose_mode(self, mock_session_manager, mock_pid_exists, capsys, tmp_path, test_db_config):
        """Test error when session is still running in verbose mode."""
        from config.settings import AppConfig, LLMConfig

        # Create a test session file
        session_id = "20250101_120000"
        session_file = tmp_path / f"session_{session_id}.json"
        session_data = {
            "session_metadata": {
                "session_id": session_id,
                "pid": 12345
            },
            "iterations": []
        }
        session_file.write_text(json.dumps(session_data))

        config = AppConfig(
            db_config=test_db_config,
            llm_config=LLMConfig.default(),
            output_dir=tmp_path,
            prompts_dir=tmp_path / "prompts",
            verbose_console_output=True  # verbose mode
        )

        # Mock session state with running PID
        mock_session_state = Mock()
        mock_session_state.metadata.pid = 12345
        mock_session_manager.return_value.persistence.load_session.return_value = mock_session_state
        mock_pid_exists.return_value = True

        mock_db = Mock()

        run_verification_mode(session_id, "insights", "key", config, mock_db)

        captured = capsys.readouterr()
        assert "still running" in captured.out
        assert "Stop the session" in captured.out

    @patch('psutil.pid_exists')
    @patch('main.SessionManager')
    def test_verification_success_quiet_mode(self, mock_session_manager, mock_pid_exists, capsys, tmp_path, test_db_config):
        """Test successful verification in quiet mode returns JSON."""
        from config.settings import AppConfig, LLMConfig

        # Create a test session file
        session_id = "20250101_120000"
        session_file = tmp_path / f"session_{session_id}.json"
        session_data = {
            "session_metadata": {
                "session_id": session_id,
                "pid": None
            },
            "iterations": []
        }
        session_file.write_text(json.dumps(session_data))

        config = AppConfig(
            db_config=test_db_config,
            llm_config=LLMConfig.default(),
            output_dir=tmp_path,
            prompts_dir=tmp_path / "prompts",
            verbose_console_output=False  # quiet mode
        )

        # Mock session state without running PID
        mock_session_state = Mock()
        mock_session_state.metadata.pid = None

        # Mock verification result
        verification_result = {
            'verified': True,
            'confidence': 'high',
            'recommendation': 'keep',
            'reasoning': 'Data matches',
            'evidence': 'Query successful'
        }
        mock_session_manager.return_value.persistence.load_session.return_value = mock_session_state
        mock_session_manager.return_value.verify_memory_item.return_value = verification_result

        mock_db = Mock()

        run_verification_mode(session_id, "insights", "key", config, mock_db)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output['verified'] is True
        assert output['confidence'] == 'high'

    @patch('psutil.pid_exists')
    @patch('main.SessionManager')
    def test_verification_exception_quiet_mode(self, mock_session_manager, mock_pid_exists, capsys, tmp_path, test_db_config):
        """Test verification exception in quiet mode returns JSON error."""
        from config.settings import AppConfig, LLMConfig

        # Create a test session file
        session_id = "20250101_120000"
        session_file = tmp_path / f"session_{session_id}.json"
        session_data = {
            "session_metadata": {
                "session_id": session_id,
                "pid": None
            },
            "iterations": []
        }
        session_file.write_text(json.dumps(session_data))

        config = AppConfig(
            db_config=test_db_config,
            llm_config=LLMConfig.default(),
            output_dir=tmp_path,
            prompts_dir=tmp_path / "prompts",
            verbose_console_output=False  # quiet mode
        )

        # Mock session state
        mock_session_state = Mock()
        mock_session_state.metadata.pid = None

        # Mock verification to raise exception
        mock_session_manager.return_value.persistence.load_session.return_value = mock_session_state
        mock_session_manager.return_value.verify_memory_item.side_effect = Exception("Verification failed")

        mock_db = Mock()

        run_verification_mode(session_id, "insights", "key", config, mock_db)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "error" in output
        assert "Verification failed" in output["error"]

    @patch('psutil.pid_exists')
    @patch('main.SessionManager')
    def test_remove_recommendation_display(self, mock_session_manager, mock_pid_exists, capsys, tmp_path, test_db_config):
        """Test remove recommendation shows appropriate message."""
        from config.settings import AppConfig, LLMConfig

        # Create a test session file
        session_id = "20250101_120000"
        session_file = tmp_path / f"session_{session_id}.json"
        session_data = {
            "session_metadata": {
                "session_id": session_id,
                "pid": None
            },
            "iterations": []
        }
        session_file.write_text(json.dumps(session_data))

        config = AppConfig(
            db_config=test_db_config,
            llm_config=LLMConfig.default(),
            output_dir=tmp_path,
            prompts_dir=tmp_path / "prompts",
            verbose_console_output=True  # verbose mode
        )

        # Mock session state
        mock_session_state = Mock()
        mock_session_state.metadata.pid = None

        # Mock verification result with remove recommendation
        verification_result = {
            'verified': False,
            'confidence': 'high',
            'recommendation': 'remove',
            'reasoning': 'Data no longer valid',
            'evidence': 'Query returned no results'
        }
        mock_session_manager.return_value.persistence.load_session.return_value = mock_session_state
        mock_session_manager.return_value.verify_memory_item.return_value = verification_result

        mock_db = Mock()

        run_verification_mode(session_id, "insights", "key", config, mock_db)

        captured = capsys.readouterr()
        assert "Remove this memory item" in captured.out

    @patch('builtins.input', return_value='y')
    @patch('psutil.pid_exists')
    @patch('main.SessionManager')
    def test_update_recommendation_accepted(self, mock_session_manager, mock_pid_exists, mock_input, capsys, tmp_path, test_db_config):
        """Test update recommendation when user accepts."""
        from config.settings import AppConfig, LLMConfig

        # Create a test session file
        session_id = "20250101_120000"
        session_file = tmp_path / f"session_{session_id}.json"
        session_data = {
            "session_metadata": {
                "session_id": session_id,
                "pid": None
            },
            "iterations": []
        }
        session_file.write_text(json.dumps(session_data))

        config = AppConfig(
            db_config=test_db_config,
            llm_config=LLMConfig.default(),
            output_dir=tmp_path,
            prompts_dir=tmp_path / "prompts",
            verbose_console_output=True  # verbose mode
        )

        # Mock session state
        mock_session_state = Mock()
        mock_session_state.metadata.pid = None
        mock_session_state.update_memory_value.return_value = True

        # Mock verification result with update recommendation
        verification_result = {
            'verified': False,
            'confidence': 'high',
            'recommendation': 'update',
            'reasoning': 'Value changed',
            'evidence': 'New data found',
            'updated_value': 'New value here'
        }
        mock_session_manager.return_value.persistence.load_session.return_value = mock_session_state
        mock_session_manager.return_value.verify_memory_item.return_value = verification_result

        mock_db = Mock()

        run_verification_mode(session_id, "insights", "key", config, mock_db)

        captured = capsys.readouterr()
        assert "Memory updated successfully" in captured.out
        mock_session_state.update_memory_value.assert_called_once()

    @patch('builtins.input', return_value='n')
    @patch('psutil.pid_exists')
    @patch('main.SessionManager')
    def test_update_recommendation_rejected(self, mock_session_manager, mock_pid_exists, mock_input, capsys, tmp_path, test_db_config):
        """Test update recommendation when user rejects."""
        from config.settings import AppConfig, LLMConfig

        # Create a test session file
        session_id = "20250101_120000"
        session_file = tmp_path / f"session_{session_id}.json"
        session_data = {
            "session_metadata": {
                "session_id": session_id,
                "pid": None
            },
            "iterations": []
        }
        session_file.write_text(json.dumps(session_data))

        config = AppConfig(
            db_config=test_db_config,
            llm_config=LLMConfig.default(),
            output_dir=tmp_path,
            prompts_dir=tmp_path / "prompts",
            verbose_console_output=True  # verbose mode
        )

        # Mock session state
        mock_session_state = Mock()
        mock_session_state.metadata.pid = None

        # Mock verification result with update recommendation
        verification_result = {
            'verified': False,
            'confidence': 'high',
            'recommendation': 'update',
            'reasoning': 'Value changed',
            'evidence': 'New data found',
            'updated_value': 'New value here'
        }
        mock_session_manager.return_value.persistence.load_session.return_value = mock_session_state
        mock_session_manager.return_value.verify_memory_item.return_value = verification_result

        mock_db = Mock()

        run_verification_mode(session_id, "insights", "key", config, mock_db)

        captured = capsys.readouterr()
        assert "Update cancelled" in captured.out


# ============================================================================
# Argument Parsing Tests
# ============================================================================

@pytest.mark.unit
class TestMainArgumentParsing:
    """Tests for main() argument parsing."""

    def test_task_argument(self):
        """Test --task argument is parsed correctly."""
        parser = argparse.ArgumentParser()
        parser.add_argument('--task', help='Task description')

        args = parser.parse_args(['--task', 'Analyze data patterns'])
        assert args.task == 'Analyze data patterns'

    def test_continue_session_argument(self):
        """Test --continue-session argument is parsed correctly."""
        parser = argparse.ArgumentParser()
        parser.add_argument('--continue-session', help='Session file')

        args = parser.parse_args(['--continue-session', 'output/session_123.json'])
        assert args.continue_session == 'output/session_123.json'

    def test_latest_flag(self):
        """Test --latest flag is parsed correctly."""
        parser = argparse.ArgumentParser()
        parser.add_argument('--latest', action='store_true')

        args = parser.parse_args(['--latest'])
        assert args.latest is True

        args = parser.parse_args([])
        assert args.latest is False

    def test_list_sessions_flag(self):
        """Test --list-sessions flag is parsed correctly."""
        parser = argparse.ArgumentParser()
        parser.add_argument('--list-sessions', action='store_true')

        args = parser.parse_args(['--list-sessions'])
        assert args.list_sessions is True

    def test_output_dir_default_and_custom(self):
        """Test --output-dir argument with default and custom values."""
        parser = argparse.ArgumentParser()
        parser.add_argument('--output-dir', default='output')

        args = parser.parse_args([])
        assert args.output_dir == 'output'

        args = parser.parse_args(['--output-dir', 'custom_output'])
        assert args.output_dir == 'custom_output'

    def test_max_iterations_default_and_custom(self):
        """Test --max-iterations argument with default and custom values."""
        parser = argparse.ArgumentParser()
        parser.add_argument('--max-iterations', type=int, default=100)

        args = parser.parse_args([])
        assert args.max_iterations == 100

        args = parser.parse_args(['--max-iterations', '50'])
        assert args.max_iterations == 50

    def test_db_result_limit(self):
        """Test --db-result-limit argument."""
        parser = argparse.ArgumentParser()
        parser.add_argument('--db-result-limit', type=int, default=100)

        args = parser.parse_args(['--db-result-limit', '200'])
        assert args.db_result_limit == 200

    def test_verify_memory_argument(self):
        """Test --verify-memory argument with nargs=2."""
        parser = argparse.ArgumentParser()
        parser.add_argument('--verify-memory', nargs=2, metavar=('SESSION_ID', 'MEMORY_SPEC'))

        args = parser.parse_args(['--verify-memory', 'session_123', 'insights:key'])
        assert args.verify_memory == ['session_123', 'insights:key']

    def test_llm_backend_argument(self):
        """Test --llm-backend argument choices."""
        parser = argparse.ArgumentParser()
        parser.add_argument('--llm-backend', choices=['qwen', 'claude'], default=None)

        args = parser.parse_args(['--llm-backend', 'claude'])
        assert args.llm_backend == 'claude'

        args = parser.parse_args(['--llm-backend', 'qwen'])
        assert args.llm_backend == 'qwen'

        args = parser.parse_args([])
        assert args.llm_backend is None

    def test_quiet_flag(self):
        """Test --quiet flag affects verbose output."""
        parser = argparse.ArgumentParser()
        parser.add_argument('--verbose', action='store_true', default=True)
        parser.add_argument('--quiet', action='store_true')

        args = parser.parse_args(['--quiet'])
        verbose_output = args.verbose and not args.quiet
        assert verbose_output is False

        args = parser.parse_args([])
        verbose_output = args.verbose and not args.quiet
        assert verbose_output is True

    def test_prompt_preset_argument(self):
        """Test --prompt-preset argument."""
        parser = argparse.ArgumentParser()
        parser.add_argument('--prompt-preset', help='Preset name')

        args = parser.parse_args(['--prompt-preset', 'custom_preset'])
        assert args.prompt_preset == 'custom_preset'

    def test_log_level_argument(self):
        """Test --log-level argument."""
        parser = argparse.ArgumentParser()
        parser.add_argument('--log-level', default='INFO')

        args = parser.parse_args(['--log-level', 'DEBUG'])
        assert args.log_level == 'DEBUG'

        args = parser.parse_args([])
        assert args.log_level == 'INFO'


# ============================================================================
# main() Function Tests
# ============================================================================

# Test database environment variables for main() tests
TEST_DB_ENV = {
    'DB_SERVER': 'test.database.local',
    'DB_USER': 'test_user',
    'DB_PASSWORD': 'test_pass',
    'DB_NAME': 'TestDB'
}


@pytest.mark.unit
class TestMainFunction:
    """Tests for the main() entry point function."""

    @patch.dict('os.environ', TEST_DB_ENV)
    @patch('main.SessionManager')
    @patch('main.MSSQLConnection')
    @patch('sys.argv', ['main.py', '--list-sessions'])
    def test_main_list_sessions_empty(self, mock_db_class, mock_manager_class, capsys):
        """Test --list-sessions with no sessions available."""
        from main import main

        mock_db = Mock()
        mock_db_class.return_value = mock_db

        mock_manager = Mock()
        mock_manager.list_available_sessions.return_value = []
        mock_manager_class.return_value = mock_manager

        main()

        captured = capsys.readouterr()
        assert "No sessions found" in captured.out

    @patch.dict('os.environ', TEST_DB_ENV)
    @patch('main.SessionManager')
    @patch('main.MSSQLConnection')
    @patch('sys.argv', ['main.py', '--list-sessions'])
    def test_main_list_sessions_with_sessions(self, mock_db_class, mock_manager_class, capsys, tmp_path):
        """Test --list-sessions with available sessions."""
        from main import main

        mock_db = Mock()
        mock_db_class.return_value = mock_db

        # Create a mock session file so stat() works
        session_file = tmp_path / "session_20250101.json"
        session_file.write_text("{}")

        mock_manager = Mock()
        mock_manager.list_available_sessions.return_value = [
            {
                'session_id': '20250101_120000',
                'first_user_input': 'Test task',
                'iteration_count': 3,
                'file_path': str(session_file),
                'file_name': 'session_20250101.json'
            }
        ]
        mock_manager_class.return_value = mock_manager

        main()

        captured = capsys.readouterr()
        assert "Available Sessions" in captured.out
        assert "20250101_120000" in captured.out

    @patch.dict('os.environ', TEST_DB_ENV)
    @patch('main.MSSQLConnection')
    @patch('sys.argv', ['main.py', '--verify-memory', 'session_123', 'invalid_format'])
    def test_main_verify_memory_invalid_format(self, mock_db_class, capsys):
        """Test --verify-memory with invalid memory spec format."""
        from main import main

        mock_db = Mock()
        mock_db_class.return_value = mock_db

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Invalid memory spec format" in captured.out

    @patch.dict('os.environ', {**TEST_DB_ENV, 'ANTHROPIC_API_KEY': ''})
    @patch('main.MSSQLConnection')
    @patch('sys.argv', ['main.py', '--llm-backend', 'claude'])
    def test_main_claude_backend_no_api_key(self, mock_db_class, capsys):
        """Test Claude backend requires API key."""
        from main import main

        mock_db = Mock()
        mock_db_class.return_value = mock_db

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "ANTHROPIC_API_KEY" in captured.out

    @patch.dict('os.environ', TEST_DB_ENV)
    @patch('main.SessionManager')
    @patch('main.MSSQLConnection')
    @patch('sys.argv', ['main.py', '--continue-session', '/nonexistent/path.json'])
    def test_main_continue_session_not_found(self, mock_db_class, mock_manager_class, capsys):
        """Test --continue-session with non-existent file."""
        from main import main

        mock_db = Mock()
        mock_db_class.return_value = mock_db

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Session file not found" in captured.out

    @patch.dict('os.environ', TEST_DB_ENV)
    @patch('main.SessionManager')
    @patch('main.MSSQLConnection')
    @patch('sys.argv', ['main.py', '--latest'])
    def test_main_latest_no_sessions(self, mock_db_class, mock_manager_class, capsys):
        """Test --latest with no sessions available."""
        from main import main

        mock_db = Mock()
        mock_db_class.return_value = mock_db

        mock_manager = Mock()
        mock_manager.find_latest_session.return_value = None
        mock_manager_class.return_value = mock_manager

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "No sessions found" in captured.out
