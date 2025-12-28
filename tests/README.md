# Database Analyzer Test Suite

Comprehensive test suite for the Database Analyzer system with 580+ tests covering unit, integration, end-to-end, performance, and WebUI testing.

## Quick Start

```bash
# Install test dependencies
pip install -r tests/requirements-test.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test suite
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/

# Run tests in parallel (faster)
pytest -n auto

# Run only fast tests (skip slow/database/e2e tests)
pytest -m "not slow and not database and not e2e"
```

## Test Organization

### Unit Tests (`tests/unit/`)
Fast, isolated tests for individual components with mocked dependencies. **348 tests total**.

- **test_session_state.py** (41 tests) - SessionState, Iteration, ToolCall, memory composition
- **test_session_persistence.py** (32 tests) - File I/O, serialization, session loading
- **test_tools.py** (35 tests) - ExecuteSQLTool and MemoryTool functionality
- **test_database_connection.py** (23 tests) - MSSQLConnection, query execution, Unicode handling
- **test_session_manager.py** (26 tests) - SessionManager coordination and lifecycle
- **test_session_execution.py** (19 tests) - LLM integration, prompt building, tool logging
- **test_settings.py** (32 tests) - DatabaseConfig, LLMConfig, ClaudeLLMConfig, AppConfig
- **test_main.py** (40 tests) - CLI entry point, graceful_shutdown, verification mode, argument parsing
- **test_llm_providers.py** (36 tests) - Qwen and Claude provider implementations, error paths
- **test_cli_interface.py** (13 tests) - CLI user interaction, input/output handling
- **test_memory_verification.py** (12 tests) - Memory verification coordinator, JSON extraction
- **test_report_service.py** (9 tests) - Report generation, LLM-based analysis
- **test_prompt_preset_manager.py** (10 tests) - Preset loading, saving, variable substitution

### Integration Tests (`tests/integration/`)
Tests for component interactions with real database and filesystem. **44 tests total**.

- **test_session_lifecycle.py** (15 tests) - Full session create/resume/save workflows
- **test_tool_execution.py** (14 tests) - Tools + database integration
- **test_preset_integration.py** (7 tests) - Preset system integration with sessions
- **test_preset_api.py** (8 tests) - Preset API integration tests

### End-to-End Tests (`tests/e2e/`)
Complete workflow tests simulating real user scenarios. **12 tests total**.

- **test_cli_workflows.py** (12 tests) - main.py CLI scenarios, argument parsing, signal handling

### Performance Tests (`tests/performance/`)
Load testing and performance benchmarks. **10 tests total**.

- **test_large_sessions.py** (10 tests) - Many iterations, large outputs, serialization performance

### WebUI Tests (`tests/webui/`)
WebUI-specific tests for Flask application, real-time features, and frontend. **147 tests total**.

- **test_api_endpoints.py** (39 tests) - Flask REST API endpoints
  - Session listing and filtering
  - Session detail with status computation (running/completed/interrupted)
  - Iteration detail and tool call display
  - Memory API (GET, POST verify/update)
  - Session control (new, resume, stop, delete)
  - Language support (i18n routing)
  - Error handling (404, 500, concurrent requests)

- **test_socketio.py** (24 tests) - SocketIO real-time communication
  - Connection/disconnection/reconnection
  - Session subscription and room isolation
  - File change events (created/modified/deleted)
  - Broadcasting and event debouncing
  - Integration with Flask routes

- **test_session_reader.py** (30 tests) - UnifiedSessionReader service
  - Session discovery and pattern matching
  - Metadata parsing and counting (iterations, queries, memory items)
  - PID-based status computation (running/completed/interrupted)
  - Memory composition from tool calls
  - Iteration detail extraction

- **test_file_watcher.py** (23 tests) - FileWatcher service
  - Watcher lifecycle (start/stop/restart)
  - Event detection (created/modified/deleted)
  - File filtering (session_*.json only)
  - Error handling (Observer errors, callback exceptions)
  - SessionFileHandler integration

- **frontend/test_ui_interactions.py** (17 tests) - Selenium E2E browser tests
  - Navigation and page loading
  - Session list interactions and filtering
  - Session detail page and iteration tabs
  - Memory verification UI (modal, buttons)
  - Language switching (EN/RU)

## Test Markers

Tests are categorized with pytest markers for selective execution:

```bash
# Run only unit tests (fast)
pytest -m unit

# Run only integration tests
pytest -m integration

# Run only E2E tests
pytest -m e2e

# Run only performance tests
pytest -m performance

# Skip database tests (no DB required)
pytest -m "not database"

# Skip slow tests
pytest -m "not slow"

# Run WebUI tests only
pytest -m webui
```

## Coverage

Run tests with coverage reporting:

```bash
# Generate HTML coverage report
pytest --cov=. --cov-report=html
open htmlcov/index.html

# Generate terminal coverage report
pytest --cov=. --cov-report=term-missing

# Generate XML coverage report (for CI)
pytest --cov=. --cov-report=xml
```

**Current Coverage (580+ tests):**
- **Overall: 90%**
- Core modules:
  - `config/settings.py`: 100%
  - `core/session_persistence.py`: 95%
  - `core/session_state.py`: 91%
  - `core/session_manager.py`: 59%
  - `core/session_execution.py`: 65%
- Tools and database:
  - `database/connection.py`: 98%
  - `tools/sql_tool.py`: 98%
  - `tools/memory_tool.py`: 90%
- Services:
  - `services/report_service.py`: 90%
  - `services/memory_verification.py`: 81%
  - `ui/cli_interface.py`: 72%
- WebUI:
  - `webui/app.py`: 63%
  - `webui/services/unified_session_reader.py`: 85%+
  - `webui/services/file_watcher.py`: 82%+
- Main entry point:
  - `main.py`: 50%

**Coverage Targets:**
- Core modules: 90%+ ✅ (most modules achieved)
- Tools and database: 85%+ ✅ (achieved)
- Services: 80%+ ✅ (achieved)
- WebUI: 75%+ ✅ (achieved)
- Overall: 90%+ ✅ (achieved)

## Fixtures

Reusable test fixtures are defined in `conftest.py`:

### Configuration Fixtures
- `test_db_config` - Test database configuration
- `test_llm_config` - Test LLM configuration
- `test_output_dir` - Temporary output directory
- `app_config` - Complete application config

### Session Fixtures
- `session_id` - Generate test session ID
- `sample_session` - Complete session with iterations
- `sample_session_with_memory` - Session with memory tool calls
- `sample_iteration` - Single iteration with tool calls
- `sample_tool_call` - Example tool call

### Database Fixtures
- `mock_db_connection` - Mocked database for unit tests
- `real_db_connection` - Real database for integration tests (requires DB)

### LLM Fixtures
- `mock_llm_assistant` - Mocked qwen-agent Assistant
- `mock_llm_response_json` - LLM JSON response for verification

### File Fixtures
- `sample_session_file` - Pre-created session file
- `multiple_session_files` - Multiple session files for listing

### Factory Fixtures
- `session_factory` - SessionFactory for creating test sessions with various configurations
- `test_mock_factory` - MockFactory for creating consistent mocks (db connections, LLM responses)

### WebUI Fixtures
- `flask_app` - Flask test app
- `flask_client` - Flask test client
- `socketio_client` - SocketIO test client
- `live_server` - Flask test server running in background for E2E tests
- `selenium_driver` - Selenium WebDriver with headless Chrome
- `file_watcher_test_dir` - Temporary directory for FileWatcher tests
- `mock_psutil_process` - Mock psutil.Process for status testing
- `mock_psutil_pid_exists` - Mock psutil.pid_exists() function

## WebUI Testing

### Running WebUI Tests

```bash
# Run all WebUI tests
pytest -m webui

# Run specific WebUI test files
pytest tests/webui/test_api_endpoints.py
pytest tests/webui/test_socketio.py
pytest tests/webui/test_session_reader.py
pytest tests/webui/test_file_watcher.py

# Run frontend E2E tests (requires Chrome/chromedriver)
pytest tests/webui/frontend/test_ui_interactions.py

# Run WebUI tests with coverage
pytest -m webui --cov=webui --cov-report=html

# Skip E2E tests (faster)
pytest -m "webui and not e2e"
```

### WebUI Test Requirements

WebUI tests require additional dependencies:

```bash
# Install WebUI test dependencies
pip install pytest-flask flask-socketio selenium

# For Selenium E2E tests, install chromedriver
# Ubuntu/Debian:
sudo apt-get install chromium-chromedriver

# macOS:
brew install chromedriver

# Or use webdriver-manager (automatic):
pip install webdriver-manager
```

### WebUI Test Structure

WebUI tests are organized into four categories:

1. **API Tests** (`test_api_endpoints.py`)
   - Test Flask REST API endpoints
   - Use `flask_client` fixture
   - Mock subprocess spawning with patches
   - Example:
   ```python
   @pytest.mark.webui
   def test_session_list(flask_client, sample_session_file):
       response = flask_client.get('/api/sessions')
       assert response.status_code == 200
   ```

2. **SocketIO Tests** (`test_socketio.py`)
   - Test real-time WebSocket communication
   - Use `socketio_client` fixture
   - Test event emission and broadcasting
   - Example:
   ```python
   @pytest.mark.webui
   def test_file_change_event(socketio_client):
       socketio_client.emit('subscribe_session', {'session_id': '123'})
       # Verify event handling
   ```

3. **Service Tests** (`test_session_reader.py`, `test_file_watcher.py`)
   - Test UnifiedSessionReader and FileWatcher services
   - Use `test_output_dir` and `file_watcher_test_dir` fixtures
   - Mock psutil for status computation
   - Example:
   ```python
   @pytest.mark.webui
   def test_status_computation(sample_session_file):
       with patch('psutil.pid_exists', return_value=True):
           status = reader.compute_status(session_metadata)
           assert status == 'running'
   ```

4. **E2E Tests** (`frontend/test_ui_interactions.py`)
   - Test complete user workflows in browser
   - Use `selenium_driver` and `live_server` fixtures
   - Headless Chrome by default
   - Example:
   ```python
   @pytest.mark.webui
   @pytest.mark.e2e
   def test_session_navigation(selenium_driver, live_server):
       selenium_driver.get(f"{live_server.url}/en/")
       # Interact with page elements
   ```

### WebUI Coverage Targets

- `webui/app.py` (Flask routes): 80%+
- `webui/services/unified_session_reader.py`: 85%+
- `webui/services/file_watcher.py`: 80%+
- Overall WebUI: 75%+

## Writing Tests

### Basic Test Structure

```python
import pytest

@pytest.mark.unit
def test_example(sample_session):
    """Test description."""
    # Arrange
    expected = "value"

    # Act
    result = sample_session.some_method()

    # Assert
    assert result == expected
```

### Using Fixtures

```python
@pytest.mark.unit
def test_with_fixtures(test_output_dir, sample_session):
    """Test using multiple fixtures."""
    session_file = test_output_dir / "test.json"
    # Test logic
```

### Parametrized Tests

```python
@pytest.mark.parametrize("input,expected", [
    ("value1", "result1"),
    ("value2", "result2"),
])
def test_parametrized(input, expected):
    assert process(input) == expected
```

### Mocking

```python
from unittest.mock import Mock, patch

@patch('module.external_function')
def test_with_mock(mock_function):
    mock_function.return_value = "mocked"
    # Test logic
```

## Database Tests

Tests marked with `@pytest.mark.database` require real database access:

```bash
# Run tests WITHOUT database tests
pytest -m "not database"

# Run ONLY database tests (requires DB_* env vars)
pytest -m database

# Set database credentials for tests
export DB_SERVER=10.10.9.48
export DB_USER=fao_read
export DB_PASSWORD=fao888
export DB_NAME=Data_BI
```

## Performance Tests

Performance tests establish benchmarks and detect regressions:

```bash
# Run performance tests
pytest -m performance

# Run with detailed timing
pytest -m performance --durations=10
```

## Continuous Integration

Tests run automatically in CI/CD pipeline:

```yaml
# .github/workflows/tests.yml
- name: Run tests
  run: |
    pytest --cov=. --cov-report=xml

- name: Upload coverage
  uses: codecov/codecov-action@v3
```

## Troubleshooting

### Common Issues

**Import errors:**
```bash
# Ensure Python path includes project root
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest
```

**Database connection failures:**
```bash
# Check database credentials
echo $DB_SERVER $DB_USER $DB_NAME

# Skip database tests
pytest -m "not database"
```

**Slow tests:**
```bash
# Run tests in parallel
pytest -n auto

# Skip slow tests
pytest -m "not slow"
```

**Permission errors:**
```bash
# Ensure temp directories are writable
chmod 755 output/
pytest
```

## Test Development Guidelines

1. **Naming Conventions**
   - Test files: `test_*.py`
   - Test classes: `Test*`
   - Test functions: `test_*`

2. **Test Organization**
   - Group related tests in classes
   - Use descriptive test names
   - One assertion focus per test

3. **Markers**
   - Mark tests appropriately (`@pytest.mark.unit`, etc.)
   - Mark slow tests with `@pytest.mark.slow`
   - Mark database tests with `@pytest.mark.database`

4. **Documentation**
   - Include docstrings for test classes and functions
   - Explain non-obvious test logic
   - Document test data requirements

5. **Mocking Strategy**
   - Mock external dependencies (LLM, network)
   - Use real database for integration tests
   - Use real filesystem with temp directories

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest Fixtures](https://docs.pytest.org/en/stable/fixture.html)
- [Coverage.py](https://coverage.readthedocs.io/)
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
