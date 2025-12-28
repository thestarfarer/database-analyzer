"""
Unit Tests for Configuration Settings

Tests for config/settings.py including DatabaseConfig, LLMConfig,
ClaudeLLMConfig, and AppConfig classes.
"""

import pytest
import os
from pathlib import Path
from unittest.mock import patch

from config.settings import (
    DatabaseConfig,
    LLMConfig,
    ClaudeLLMConfig,
    AppConfig,
    DEFAULT_ANALYSIS_TASK
)


# ============================================================================
# DatabaseConfig Tests
# ============================================================================

@pytest.mark.unit
class TestDatabaseConfig:
    """Tests for DatabaseConfig dataclass."""

    def test_default_charset(self):
        """Test default charset is cp1251."""
        config = DatabaseConfig(
            server="localhost",
            user="test",
            password="pass",
            database="testdb"
        )
        assert config.charset == "cp1251"

    def test_custom_charset(self):
        """Test custom charset can be set."""
        config = DatabaseConfig(
            server="localhost",
            user="test",
            password="pass",
            database="testdb",
            charset="utf8"
        )
        assert config.charset == "utf8"

    def test_dataclass_fields(self):
        """Test all required fields are present."""
        config = DatabaseConfig(
            server="test.database.local",
            user="test_user",
            password="test_pass",
            database="TestDB"
        )
        assert config.server == "test.database.local"
        assert config.user == "test_user"
        assert config.password == "test_pass"
        assert config.database == "TestDB"

    def test_from_env_requires_env_vars(self, monkeypatch):
        """Test from_env raises ValueError when env vars not set."""
        # Clear any existing env vars
        monkeypatch.delenv("DB_SERVER", raising=False)
        monkeypatch.delenv("DB_USER", raising=False)
        monkeypatch.delenv("DB_PASSWORD", raising=False)
        monkeypatch.delenv("DB_NAME", raising=False)

        with pytest.raises(ValueError) as exc_info:
            DatabaseConfig.from_env()

        assert "Missing required environment variables" in str(exc_info.value)
        assert "DB_SERVER" in str(exc_info.value)
        assert "DB_USER" in str(exc_info.value)

    def test_from_env_with_all_vars_set(self, monkeypatch):
        """Test from_env reads all environment variables."""
        monkeypatch.setenv("DB_SERVER", "custom.server.com")
        monkeypatch.setenv("DB_USER", "custom_user")
        monkeypatch.setenv("DB_PASSWORD", "custom_pass")
        monkeypatch.setenv("DB_NAME", "CustomDB")

        config = DatabaseConfig.from_env()

        assert config.server == "custom.server.com"
        assert config.user == "custom_user"
        assert config.password == "custom_pass"
        assert config.database == "CustomDB"

    def test_from_env_partial_vars_fails(self, monkeypatch):
        """Test from_env fails with partial environment variables."""
        monkeypatch.delenv("DB_SERVER", raising=False)
        monkeypatch.setenv("DB_USER", "override_user")
        monkeypatch.delenv("DB_PASSWORD", raising=False)
        monkeypatch.setenv("DB_NAME", "OverrideDB")

        with pytest.raises(ValueError) as exc_info:
            DatabaseConfig.from_env()

        # Should report only the missing variables
        assert "DB_SERVER" in str(exc_info.value)
        assert "DB_PASSWORD" in str(exc_info.value)
        assert "DB_USER" not in str(exc_info.value)  # This one was set

    def test_dataclass_equality(self):
        """Test dataclass equality comparison."""
        config1 = DatabaseConfig(
            server="localhost",
            user="test",
            password="pass",
            database="testdb"
        )
        config2 = DatabaseConfig(
            server="localhost",
            user="test",
            password="pass",
            database="testdb"
        )
        assert config1 == config2


# ============================================================================
# LLMConfig Tests
# ============================================================================

@pytest.mark.unit
class TestLLMConfig:
    """Tests for LLMConfig dataclass."""

    def test_default_factory_method(self):
        """Test default() factory method creates valid config."""
        config = LLMConfig.default()

        assert config is not None
        assert isinstance(config, LLMConfig)

    def test_default_model_settings(self, monkeypatch):
        """Test default model configuration values."""
        # Clear env vars to test defaults
        monkeypatch.delenv("QWEN_MODEL", raising=False)
        monkeypatch.delenv("QWEN_MODEL_SERVER", raising=False)
        monkeypatch.delenv("QWEN_API_KEY", raising=False)

        config = LLMConfig.default()

        assert config.model == 'qwen-max'
        assert config.model_server == 'http://localhost:5001/api/v1'
        assert config.api_key == 'EMPTY'

    def test_default_generate_cfg_keys(self):
        """Test generate_cfg contains all required keys."""
        config = LLMConfig.default()

        required_keys = ['thought_in_content', 'max_input_tokens', 'max_tokens',
                         'temperature', 'top_p', 'top_k']
        for key in required_keys:
            assert key in config.generate_cfg, f"Missing key: {key}"

    def test_default_generate_cfg_values(self):
        """Test generate_cfg has expected default values."""
        config = LLMConfig.default()

        assert config.generate_cfg['thought_in_content'] is True
        assert config.generate_cfg['max_input_tokens'] == 100000
        assert config.generate_cfg['max_tokens'] == 28000
        assert config.generate_cfg['temperature'] == 0.6
        assert config.generate_cfg['top_p'] == 0.95
        assert config.generate_cfg['top_k'] == 20

    def test_custom_llm_config(self):
        """Test creating custom LLM config."""
        config = LLMConfig(
            model='custom-model',
            model_server='http://custom:8000',
            api_key='my-api-key',
            generate_cfg={'temperature': 0.8}
        )

        assert config.model == 'custom-model'
        assert config.model_server == 'http://custom:8000'
        assert config.api_key == 'my-api-key'
        assert config.generate_cfg['temperature'] == 0.8

    def test_dataclass_equality(self):
        """Test dataclass equality comparison."""
        config1 = LLMConfig.default()
        config2 = LLMConfig.default()
        assert config1 == config2


# ============================================================================
# ClaudeLLMConfig Tests
# ============================================================================

@pytest.mark.unit
class TestClaudeLLMConfig:
    """Tests for ClaudeLLMConfig dataclass."""

    def test_default_values(self):
        """Test default field values."""
        config = ClaudeLLMConfig()

        assert config.model == 'claude-opus-4-5'
        assert config.api_key == ''
        assert config.max_tokens == 16000
        assert config.extended_thinking is True
        assert config.thinking_budget_tokens == 10000
        assert config.temperature == 1.0

    def test_from_env_without_api_key(self, monkeypatch):
        """Test from_env when ANTHROPIC_API_KEY is not set."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("CLAUDE_MODEL", raising=False)
        monkeypatch.delenv("CLAUDE_MAX_TOKENS", raising=False)
        monkeypatch.delenv("CLAUDE_EXTENDED_THINKING", raising=False)
        monkeypatch.delenv("CLAUDE_THINKING_BUDGET", raising=False)

        config = ClaudeLLMConfig.from_env()

        assert config.api_key == ''
        assert config.model == 'claude-opus-4-5'

    def test_from_env_with_api_key(self, monkeypatch):
        """Test from_env reads ANTHROPIC_API_KEY."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")

        config = ClaudeLLMConfig.from_env()

        assert config.api_key == "sk-ant-test-key"

    def test_from_env_custom_model(self, monkeypatch):
        """Test from_env reads CLAUDE_MODEL."""
        monkeypatch.setenv("CLAUDE_MODEL", "claude-3-sonnet")

        config = ClaudeLLMConfig.from_env()

        assert config.model == "claude-3-sonnet"

    def test_from_env_max_tokens_override(self, monkeypatch):
        """Test from_env reads CLAUDE_MAX_TOKENS as integer."""
        monkeypatch.setenv("CLAUDE_MAX_TOKENS", "32000")

        config = ClaudeLLMConfig.from_env()

        assert config.max_tokens == 32000

    def test_from_env_extended_thinking_true(self, monkeypatch):
        """Test from_env parses CLAUDE_EXTENDED_THINKING=true."""
        monkeypatch.setenv("CLAUDE_EXTENDED_THINKING", "true")

        config = ClaudeLLMConfig.from_env()

        assert config.extended_thinking is True

    def test_from_env_extended_thinking_false(self, monkeypatch):
        """Test from_env parses CLAUDE_EXTENDED_THINKING=false."""
        monkeypatch.setenv("CLAUDE_EXTENDED_THINKING", "false")

        config = ClaudeLLMConfig.from_env()

        assert config.extended_thinking is False

    def test_from_env_thinking_budget_override(self, monkeypatch):
        """Test from_env reads CLAUDE_THINKING_BUDGET as integer."""
        monkeypatch.setenv("CLAUDE_THINKING_BUDGET", "20000")

        config = ClaudeLLMConfig.from_env()

        assert config.thinking_budget_tokens == 20000


# ============================================================================
# AppConfig Tests
# ============================================================================

@pytest.mark.unit
class TestAppConfig:
    """Tests for AppConfig dataclass."""

    def test_default_values(self, tmp_path, test_db_config):
        """Test default field values."""
        output_dir = tmp_path / "output"
        prompts_dir = tmp_path / "prompts"

        config = AppConfig(
            db_config=test_db_config,
            llm_config=LLMConfig.default(),
            output_dir=output_dir,
            prompts_dir=prompts_dir
        )

        assert config.log_level == "INFO"
        assert config.max_iterations == 100
        assert config.verbose_console_output is True
        assert config.db_result_limit == 100
        assert config.prompt_preset_name is None
        assert config.llm_backend == 'qwen'

    def test_post_init_creates_output_dir(self, tmp_path, test_db_config):
        """Test __post_init__ creates output directory."""
        output_dir = tmp_path / "new_output"
        prompts_dir = tmp_path / "prompts"

        assert not output_dir.exists()

        config = AppConfig(
            db_config=test_db_config,
            llm_config=LLMConfig.default(),
            output_dir=output_dir,
            prompts_dir=prompts_dir
        )

        assert output_dir.exists()
        assert output_dir.is_dir()

    def test_post_init_creates_prompts_dir(self, tmp_path, test_db_config):
        """Test __post_init__ creates prompts directory."""
        output_dir = tmp_path / "output"
        prompts_dir = tmp_path / "new_prompts"

        assert not prompts_dir.exists()

        config = AppConfig(
            db_config=test_db_config,
            llm_config=LLMConfig.default(),
            output_dir=output_dir,
            prompts_dir=prompts_dir
        )

        assert prompts_dir.exists()
        assert prompts_dir.is_dir()

    def test_post_init_initializes_claude_config(self, tmp_path, test_db_config, monkeypatch):
        """Test __post_init__ initializes claude_config from environment."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")

        config = AppConfig(
            db_config=test_db_config,
            llm_config=LLMConfig.default(),
            output_dir=tmp_path / "output",
            prompts_dir=tmp_path / "prompts"
        )

        assert config.claude_config is not None
        assert config.claude_config.api_key == "test-key-123"

    def test_llm_backend_default(self, tmp_path, test_db_config):
        """Test llm_backend defaults to 'qwen'."""
        config = AppConfig(
            db_config=test_db_config,
            llm_config=LLMConfig.default(),
            output_dir=tmp_path / "output",
            prompts_dir=tmp_path / "prompts"
        )

        assert config.llm_backend == 'qwen'

    def test_llm_backend_claude(self, tmp_path, test_db_config):
        """Test llm_backend can be set to 'claude'."""
        config = AppConfig(
            db_config=test_db_config,
            llm_config=LLMConfig.default(),
            output_dir=tmp_path / "output",
            prompts_dir=tmp_path / "prompts",
            llm_backend='claude'
        )

        assert config.llm_backend == 'claude'

    def test_prompt_preset_name_optional(self, tmp_path, test_db_config):
        """Test prompt_preset_name is optional."""
        config = AppConfig(
            db_config=test_db_config,
            llm_config=LLMConfig.default(),
            output_dir=tmp_path / "output",
            prompts_dir=tmp_path / "prompts",
            prompt_preset_name="custom_preset"
        )

        assert config.prompt_preset_name == "custom_preset"

    def test_existing_directories_not_error(self, tmp_path, test_db_config):
        """Test __post_init__ doesn't error on existing directories."""
        output_dir = tmp_path / "output"
        prompts_dir = tmp_path / "prompts"

        # Pre-create directories
        output_dir.mkdir()
        prompts_dir.mkdir()

        # Should not raise
        config = AppConfig(
            db_config=test_db_config,
            llm_config=LLMConfig.default(),
            output_dir=output_dir,
            prompts_dir=prompts_dir
        )

        assert output_dir.exists()
        assert prompts_dir.exists()


# ============================================================================
# DEFAULT_ANALYSIS_TASK Tests
# ============================================================================

@pytest.mark.unit
class TestDefaultAnalysisTask:
    """Tests for DEFAULT_ANALYSIS_TASK constant."""

    def test_default_task_is_string(self):
        """Test DEFAULT_ANALYSIS_TASK is a non-empty string."""
        assert isinstance(DEFAULT_ANALYSIS_TASK, str)
        assert len(DEFAULT_ANALYSIS_TASK) > 0

    def test_default_task_contains_analysis_keywords(self):
        """Test DEFAULT_ANALYSIS_TASK contains relevant keywords."""
        assert "explore" in DEFAULT_ANALYSIS_TASK.lower()
        assert "database" in DEFAULT_ANALYSIS_TASK.lower()
