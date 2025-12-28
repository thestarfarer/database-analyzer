"""
Pytest Configuration and Shared Fixtures

This module provides shared fixtures and configuration for the entire test suite.
Fixtures are organized by category for easy discovery and reuse.
"""

import pytest
import json
import time
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import AppConfig, DatabaseConfig, LLMConfig
from core.session_state import SessionState, SessionMetadata, Iteration, ToolCall, SystemLog
from database.connection import DatabaseConnection


# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture
def test_db_config():
    """Test database configuration."""
    return DatabaseConfig(
        server="test.database.local",
        user="test_user",
        password="test_pass",
        database="TestDB",
        charset="utf8"
    )


@pytest.fixture
def test_llm_config():
    """Test LLM configuration."""
    return LLMConfig(
        model='test-model',
        model_server='http://localhost:5001/api/v1',
        api_key='test-api-key',
        generate_cfg={
            'thought_in_content': True,
            'max_input_tokens': 100000,
            'max_tokens': 28000,
            'temperature': 0.6,
            'top_p': 0.95,
            'top_k': 20
        }
    )


@pytest.fixture
def test_output_dir(tmp_path):
    """Temporary output directory for test sessions."""
    output_dir = tmp_path / "test_output"
    output_dir.mkdir(exist_ok=True)
    yield output_dir
    # Cleanup happens automatically with tmp_path


@pytest.fixture
def app_config(test_db_config, test_llm_config, test_output_dir):
    """Complete test application configuration."""
    return AppConfig(
        db_config=test_db_config,
        llm_config=test_llm_config,
        output_dir=test_output_dir,
        log_level="DEBUG",
        max_iterations=10,  # Smaller for tests
        verbose_console_output=False,  # Quiet during tests
        db_result_limit=100
    )


# ============================================================================
# Session State Fixtures
# ============================================================================

@pytest.fixture
def session_id():
    """Generate test session ID."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


@pytest.fixture
def sample_session_metadata(session_id):
    """Sample session metadata."""
    return SessionMetadata(
        session_id=session_id,
        start_time=time.time(),
        end_time=None,
        current_iteration=1,
        last_save_time=time.time(),
        pid=12345
    )


@pytest.fixture
def sample_tool_call():
    """Sample tool call for testing."""
    return ToolCall(
        id="tool_call_1",
        tool="execute_sql",
        timestamp=time.time(),
        input={"query": "SELECT * FROM entities"},
        output="Entity1 | Entity2\n---\nData | Data",
        execution_time=0.123,
        metadata={}
    )


@pytest.fixture
def sample_memory_tool_call():
    """Sample memory tool call."""
    return ToolCall(
        id="tool_call_mem_1",
        tool="memory",
        timestamp=time.time(),
        input={
            "action": "update",
            "key": "insights",
            "value": "record_count:Total of 100 records in database"
        },
        output="Memory updated: insights/record_count",
        execution_time=0.001,
        metadata={}
    )


@pytest.fixture
def sample_iteration(sample_tool_call):
    """Sample iteration with tool calls."""
    iteration = Iteration(
        iteration=1,
        start_time=time.time(),
        end_time=time.time() + 10,
        prompt="Analyze database data",
        user_input="Show me all records",
        llm_response="Found 100 records in the database.",
        tool_calls=[sample_tool_call],
        system_logs=[]
    )
    return iteration


@pytest.fixture
def sample_session(session_id, sample_iteration):
    """Complete sample session with iterations and tool calls."""
    session = SessionState(session_id=session_id)
    session.iterations.append(sample_iteration)
    return session


@pytest.fixture
def sample_session_with_memory(session_id, test_output_dir):
    """Session with memory tool calls and file on disk."""
    session = SessionState(session_id=session_id)

    # Add iteration with memory tool calls
    iteration = Iteration(
        iteration=1,
        start_time=time.time(),
        prompt="Analyze database",
        user_input="What's in the database?",
        llm_response="Database contains 100 records."
    )

    # Add memory tool calls
    iteration.tool_calls.extend([
        ToolCall(
            id="mem_1",
            tool="memory",
            timestamp=time.time(),
            input={
                "action": "update",
                "key": "insights",
                "value": "record_count:100 records total"
            },
            output="Memory updated",
            execution_time=0.001
        ),
        ToolCall(
            id="mem_2",
            tool="memory",
            timestamp=time.time(),
            input={
                "action": "update",
                "key": "key_findings",
                "value": "database_stats:Active database with current data"
            },
            output="Memory updated",
            execution_time=0.001
        )
    ])

    iteration.end_time = time.time()
    session.iterations.append(iteration)

    # Create session file on disk
    session_data = session.to_dict()
    session_file = test_output_dir / f"session_{session.metadata.session_id}.json"
    with open(session_file, 'w', encoding='utf-8') as f:
        json.dump(session_data, f, ensure_ascii=False, indent=2)

    return session


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture
def mock_db_connection():
    """Mock database connection for unit tests."""
    mock_conn = Mock(spec=DatabaseConnection)
    mock_conn.execute_query.return_value = "Entity | Value\n---\nEntity1 | 1000"
    mock_conn.close.return_value = None
    mock_conn.result_limit = 100  # Add result_limit attribute for variable replacement
    return mock_conn


@pytest.fixture
def real_db_connection(test_db_config):
    """Real database connection for integration tests.

    Mark tests using this with @pytest.mark.database
    """
    from database.connection import MSSQLConnection
    try:
        conn = MSSQLConnection(test_db_config, verbose=False, result_limit=10)
    except Exception as e:
        pytest.skip(f"Database connection unavailable: {e}")
    yield conn
    conn.close()


# ============================================================================
# LLM Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_llm_assistant():
    """Mock qwen-agent Assistant for testing."""
    mock_assistant = MagicMock()

    # Mock run() method to return responses
    mock_response = MagicMock()
    mock_response.content = "This is a test LLM response."
    mock_assistant.run.return_value = [mock_response]

    return mock_assistant


@pytest.fixture
def mock_llm_response_json():
    """Mock LLM response with JSON output (for verification)."""
    response = MagicMock()
    response.content = '''<think>Analyzing memory item...</think>
    {
        "verified": true,
        "confidence": "high",
        "evidence": "SELECT COUNT(*) returned 100",
        "recommendation": "keep",
        "reasoning": "Record count is accurate"
    }'''
    return [response]


# ============================================================================
# File System Fixtures
# ============================================================================

@pytest.fixture
def sample_session_file(test_output_dir, sample_session):
    """Create a sample session file for testing."""
    session_data = sample_session.to_dict()
    session_file = test_output_dir / f"session_{sample_session.metadata.session_id}.json"

    with open(session_file, 'w', encoding='utf-8') as f:
        json.dump(session_data, f, ensure_ascii=False, indent=2)

    return session_file


@pytest.fixture
def sample_session_with_file(test_output_dir, sample_session):
    """Create a sample session file and return both file and session object for testing."""
    session_data = sample_session.to_dict()
    session_file = test_output_dir / f"session_{sample_session.metadata.session_id}.json"

    with open(session_file, 'w', encoding='utf-8') as f:
        json.dump(session_data, f, ensure_ascii=False, indent=2)

    return {'file': session_file, 'session': sample_session, 'session_id': sample_session.metadata.session_id}


@pytest.fixture
def multiple_session_files(test_output_dir):
    """Create multiple session files for testing list operations."""
    session_files = []

    for i in range(3):
        session_id = f"2025092{i}_120000"
        session_data = {
            "session_metadata": {
                "session_id": session_id,
                "start_time": time.time() - (i * 3600),
                "end_time": time.time() - (i * 3600) + 600,
                "current_iteration": 2,
                "last_save_time": time.time() - (i * 3600) + 600,
                "pid": None
            },
            "iterations": [
                {
                    "iteration": 1,
                    "start_time": time.time() - (i * 3600),
                    "end_time": time.time() - (i * 3600) + 300,
                    "prompt": "Test prompt",
                    "user_input": f"Test task {i}",
                    "tool_calls": [],
                    "llm_response": f"Test response {i}",
                    "system_logs": []
                }
            ],
            "export_timestamp": datetime.now().isoformat()
        }

        session_file = test_output_dir / f"session_{session_id}.json"
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)

        session_files.append(session_file)

    return session_files


# ============================================================================
# Tool Fixtures
# ============================================================================

@pytest.fixture
def mock_sql_tool(mock_db_connection):
    """Mock SQL tool for testing."""
    from tools.sql_tool import ExecuteSQLTool
    return ExecuteSQLTool(mock_db_connection, verbose=False)


@pytest.fixture
def mock_memory_tool():
    """Mock memory tool for testing."""
    from tools.memory_tool import MemoryTool
    return MemoryTool()


# ============================================================================
# WebUI Fixtures (for WebUI tests)
# ============================================================================

@pytest.fixture
def flask_app(test_output_dir):
    """Flask app for testing."""
    from webui.app import app, unified_session_reader

    # Save original output_dir
    original_output_dir = unified_session_reader.output_dir

    # Set test output directory
    unified_session_reader.set_output_dir(test_output_dir)

    app.config['TESTING'] = True

    yield app

    # Restore original output directory
    unified_session_reader.set_output_dir(original_output_dir)


@pytest.fixture
def flask_client(flask_app):
    """Flask test client."""
    return flask_app.test_client()


@pytest.fixture
def socketio_client(flask_app):
    """SocketIO test client."""
    from flask_socketio import SocketIOTestClient
    from webui.app import socketio
    return socketio.test_client(flask_app)


@pytest.fixture
def live_server(flask_app, sample_session_file):
    """Flask test server running in background for E2E tests."""
    from werkzeug.serving import make_server
    import threading

    # Use a random available port
    server = make_server('127.0.0.1', 0, flask_app)
    port = server.socket.getsockname()[1]

    # Start server in background thread
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()

    # Create server info object
    class LiveServer:
        def __init__(self, host, port):
            self.host = host
            self.port = port
            self.url = f"http://{host}:{port}"

    yield LiveServer('127.0.0.1', port)

    # Shutdown server
    server.shutdown()


@pytest.fixture(scope="module")
def selenium_driver():
    """Selenium WebDriver for E2E testing.

    Module-scoped to reuse browser across tests in a module.
    Uses Selenium Manager (built into Selenium 4+) which automatically
    downloads both ChromeDriver AND Chrome browser if not installed.
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--disable-logging')
    chrome_options.add_argument('--log-level=3')

    try:
        # Selenium Manager automatically downloads Chrome browser + driver
        driver = webdriver.Chrome(options=chrome_options)
        driver.implicitly_wait(2)
        driver.set_page_load_timeout(10)
        yield driver
        driver.quit()
    except Exception as e:
        pytest.skip(f"Selenium WebDriver not available: {e}")


@pytest.fixture
def file_watcher_test_dir(tmp_path):
    """Temporary directory for FileWatcher tests."""
    watcher_dir = tmp_path / "watcher_output"
    watcher_dir.mkdir(exist_ok=True)
    yield watcher_dir
    # Cleanup happens automatically with tmp_path


@pytest.fixture
def mock_psutil_process():
    """Mock psutil.Process for status testing."""
    mock_process = MagicMock()
    mock_process.is_running.return_value = True
    mock_process.pid = 12345
    mock_process.status.return_value = 'running'
    return mock_process


@pytest.fixture
def mock_psutil_pid_exists():
    """Mock psutil.pid_exists() function."""
    with patch('psutil.pid_exists') as mock_exists:
        mock_exists.return_value = True
        yield mock_exists


# ============================================================================
# Helper Functions
# ============================================================================

def create_test_session_dict(session_id="20250920_120000", iterations=1, with_memory=False):
    """Helper to create session dictionary for testing."""
    session_data = {
        "session_metadata": {
            "session_id": session_id,
            "start_time": time.time(),
            "end_time": None,
            "current_iteration": iterations,
            "last_save_time": time.time(),
            "pid": None
        },
        "iterations": [],
        "export_timestamp": datetime.now().isoformat()
    }

    for i in range(1, iterations + 1):
        iteration_data = {
            "iteration": i,
            "start_time": time.time(),
            "end_time": time.time() + 10,
            "prompt": f"Test prompt {i}",
            "user_input": f"Test task {i}",
            "tool_calls": [],
            "llm_response": f"Test response {i}",
            "system_logs": []
        }

        if with_memory:
            iteration_data["tool_calls"].append({
                "id": f"mem_{i}",
                "tool": "memory",
                "timestamp": time.time(),
                "input": {
                    "action": "update",
                    "key": "insights",
                    "value": f"test_insight_{i}:Test insight {i}"
                },
                "output": "Memory updated",
                "execution_time": 0.001,
                "metadata": {}
            })

        session_data["iterations"].append(iteration_data)

    return session_data


# ============================================================================
# Prompt Preset Fixtures
# ============================================================================

@pytest.fixture
def presets_dir(tmp_path):
    """Temporary presets directory for testing."""
    preset_dir = tmp_path / "prompts"
    preset_dir.mkdir(exist_ok=True)
    return preset_dir


@pytest.fixture
def valid_preset_data():
    """Valid complete preset JSON structure for testing."""
    return {
        "preset_metadata": {
            "name": "test_preset",
            "description": "Test preset for unit tests",
            "version": "1.0",
            "created": "2025-01-01",
            "author": "Test Suite"
        },
        "base_prompt": {
            "schema": "Test database schema with {{DB_RESULT_LIMIT}} row limit",
            "tools_description": "Test tool description for {{CURRENT_DATE}}",
            "domain_context": "Test domain context",
            "task_instructions": "Test task instructions",
            "assembly_template": "Database schema:\n{schema}\n\n{tools_description}\n\n{domain_context}\n\n{task_instructions}"
        },
        "verification_prompt": {
            "verification_task_template": "Verify {{CATEGORY}} {{KEY}} = {{VALUE}}",
            "assembly_template": "{base_prompt}\n\n{memory_summary}\n\n{verification_task_template}"
        },
        "continuation_prompt": {
            "iteration_context_template": "Iteration {{CURRENT_ITERATION}} of {{COMPLETED_ITERATIONS}}",
            "assembly_template": "{base_prompt}{iteration_context_template}"
        },
        "report_prompt": {
            "report_instructions": "Generate report for {{TASK_DESCRIPTION}}",
            "assembly_template": "{report_instructions}"
        },
        "variable_registry": {
            "CURRENT_DATE": {
                "description": "Today's date in YYYY-MM-DD format",
                "example": "2025-01-01"
            },
            "DB_RESULT_LIMIT": {
                "description": "Maximum rows returned from database",
                "example": "100"
            }
        }
    }


@pytest.fixture
def preset_manager(presets_dir):
    """PromptPresetManager instance with test directory."""
    from services.prompt_preset_manager import PromptPresetManager
    return PromptPresetManager(presets_dir, None)


@pytest.fixture
def sample_preset_file(presets_dir, valid_preset_data):
    """Create a sample preset file on disk."""
    import json
    preset_path = presets_dir / "test_preset.json"
    with open(preset_path, 'w') as f:
        json.dump(valid_preset_data, f, indent=2)
    return preset_path


@pytest.fixture
def malicious_preset_names():
    """Collection of dangerous preset names for security testing."""
    return [
        "../../etc/passwd",
        "../../../evil",
        "..\\..\\windows\\system32",
        "/etc/shadow",
        "C:\\Windows\\System32",
        "preset/../../../danger",
        "preset\\..\\..\\danger",
        "",  # Empty string
        "a" * 101,  # Too long
        "preset with spaces",
        "preset@#$%",
        "preset;rm -rf /",
        "${variable}",
        "'; DROP TABLE --"
    ]


@pytest.fixture
def flask_app_with_presets(flask_app, presets_dir):
    """Flask app configured with test presets directory."""
    # Patch the app to use our test presets dir
    with patch('webui.app.Path', return_value=presets_dir):
        yield flask_app


@pytest.fixture
def app_config_with_preset(app_config, presets_dir):
    """AppConfig with preset configuration."""
    app_config.prompts_dir = presets_dir
    app_config.prompt_preset_name = "test_preset"
    return app_config


# ============================================================================
# Factory Classes for Test Data Generation
# ============================================================================

class SessionFactory:
    """
    Factory for creating test sessions with various configurations.

    Provides a unified way to create SessionState objects with
    customizable parameters for different test scenarios.
    """

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self._counter = 0

    def create(
        self,
        session_id: str = None,
        iterations: int = 1,
        with_memory: bool = False,
        with_sql_calls: bool = False,
        with_file: bool = False,
        status: str = 'completed',
        pid: int = None
    ):
        """
        Create a test session with specified configuration.

        Args:
            session_id: Custom session ID (auto-generated if None)
            iterations: Number of iterations to create
            with_memory: Add memory tool calls
            with_sql_calls: Add SQL tool calls
            with_file: Also create JSON file on disk
            status: Session status ('running', 'completed', 'interrupted')
            pid: Process ID (for status simulation)

        Returns:
            SessionState object (and file path if with_file=True)
        """
        self._counter += 1

        if session_id is None:
            session_id = f"2025010{self._counter}_120000"

        session = SessionState(session_id=session_id)

        # Set PID based on status
        if status == 'running':
            session.metadata.pid = pid or 99999
        elif status == 'interrupted':
            session.metadata.pid = pid or 88888
        else:  # completed
            session.metadata.pid = None

        # Add iterations
        for i in range(1, iterations + 1):
            iteration = Iteration(
                iteration=i,
                start_time=time.time() - (iterations - i) * 60,
                prompt=f"Test prompt {i}",
                user_input=f"Test task {i}"
            )

            if with_sql_calls:
                iteration.tool_calls.append(ToolCall(
                    id=f"sql_{i}",
                    tool="execute_sql",
                    timestamp=time.time(),
                    input={"query": f"SELECT * FROM table_{i}"},
                    output="Column1 | Column2\n---\nData | Data",
                    execution_time=0.05
                ))

            if with_memory:
                iteration.tool_calls.append(ToolCall(
                    id=f"mem_{i}",
                    tool="memory",
                    timestamp=time.time(),
                    input={
                        "action": "update",
                        "key": "insights",
                        "value": f"test_insight_{i}:Test insight from iteration {i}"
                    },
                    output="Memory updated",
                    execution_time=0.001
                ))

            iteration.llm_response = f"Test response for iteration {i}"
            iteration.end_time = time.time()
            session.iterations.append(iteration)

        if with_file:
            session_data = session.to_dict()
            session_file = self.output_dir / f"session_{session_id}.json"
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)
            return {'session': session, 'file': session_file, 'session_id': session_id}

        return session


class MockFactory:
    """
    Factory for creating commonly used mocks.

    Provides static methods to create consistently configured
    mock objects for database connections, LLM responses, etc.
    """

    @staticmethod
    def db_connection(
        return_value: str = "Entity | Value\n---\nEntity1 | 1000",
        should_fail: bool = False,
        error_message: str = "Connection failed"
    ) -> Mock:
        """
        Create mock database connection.

        Args:
            return_value: Result to return from execute_query
            should_fail: If True, execute_query raises Exception
            error_message: Error message when should_fail=True

        Returns:
            Mock DatabaseConnection
        """
        mock_conn = Mock(spec=DatabaseConnection)
        if should_fail:
            mock_conn.execute_query.side_effect = Exception(error_message)
        else:
            mock_conn.execute_query.return_value = return_value
        mock_conn.close.return_value = None
        mock_conn.result_limit = 100
        return mock_conn

    @staticmethod
    def llm_response(
        content: str = "Test LLM response",
        tool_calls: list = None,
        thinking: str = None
    ) -> MagicMock:
        """
        Create mock LLM response.

        Args:
            content: Response content text
            tool_calls: List of tool call dicts (optional)
            thinking: Thinking/reasoning text (optional)

        Returns:
            MagicMock response object
        """
        response = MagicMock()
        response.content = content
        response.tool_calls = tool_calls or []

        if thinking:
            response.content = f"<think>{thinking}</think>{content}"

        return response

    @staticmethod
    def llm_response_with_tool_call(
        tool_name: str = "execute_sql",
        tool_arguments: dict = None
    ) -> list:
        """
        Create mock LLM response with a tool call.

        Args:
            tool_name: Name of the tool to call
            tool_arguments: Arguments for the tool call

        Returns:
            List containing mock response with tool calls
        """
        response = MagicMock()
        response.content = f"I'll use {tool_name}."
        response.tool_calls = [
            {
                'id': 'call_1',
                'function': {
                    'name': tool_name,
                    'arguments': json.dumps(tool_arguments or {"query": "SELECT 1"})
                }
            }
        ]
        return [response]

    @staticmethod
    def subprocess_popen(
        pid: int = 12345,
        returncode: int = 0,
        stdout: str = "",
        stderr: str = ""
    ) -> MagicMock:
        """
        Create mock subprocess.Popen.

        Args:
            pid: Process ID
            returncode: Return code for poll()
            stdout: Standard output content
            stderr: Standard error content

        Returns:
            MagicMock Popen object
        """
        mock_popen = MagicMock()
        mock_popen.pid = pid
        mock_popen.poll.return_value = returncode
        mock_popen.stdout.read.return_value = stdout
        mock_popen.stderr.read.return_value = stderr
        mock_popen.communicate.return_value = (stdout, stderr)
        mock_popen.returncode = returncode
        return mock_popen

    @staticmethod
    def session_state(
        session_id: str = "20250101_120000",
        iterations: int = 1,
        pid: int = None
    ) -> MagicMock:
        """
        Create mock SessionState.

        Args:
            session_id: Session identifier
            iterations: Number of iterations
            pid: Process ID (None = completed)

        Returns:
            MagicMock SessionState
        """
        mock_state = MagicMock()
        mock_state.metadata.session_id = session_id
        mock_state.metadata.pid = pid
        mock_state.metadata.current_iteration = iterations
        mock_state.iterations = [MagicMock() for _ in range(iterations)]
        return mock_state


@pytest.fixture
def session_factory(test_output_dir) -> SessionFactory:
    """Factory fixture for creating test sessions."""
    return SessionFactory(test_output_dir)


@pytest.fixture
def test_mock_factory() -> MockFactory:
    """
    Factory fixture for creating mocks.

    Named 'test_mock_factory' to avoid collision with @patch decorator
    parameters commonly named 'mock_factory' in test files.
    """
    return MockFactory()


# Export helper function
__all__ = ['create_test_session_dict', 'SessionFactory', 'MockFactory']
