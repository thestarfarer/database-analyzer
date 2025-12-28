"""
Configuration Settings for Database Analyzer

Defines database, LLM, and application configuration classes with
environment variable support.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
import os
from pathlib import Path


# Default analysis task used when no task is specified
DEFAULT_ANALYSIS_TASK = """Explore the database and identify patterns, trends, and insights."""


@dataclass
class DatabaseConfig:
    server: str
    user: str
    password: str
    database: str
    charset: str = "cp1251"
    
    @classmethod
    def from_env(cls):
        """
        Create DatabaseConfig from environment variables.

        Required environment variables:
            DB_SERVER: Database server address
            DB_USER: Database username
            DB_PASSWORD: Database password
            DB_NAME: Database name

        Raises:
            ValueError: If any required environment variable is missing
        """
        server = os.getenv("DB_SERVER")
        user = os.getenv("DB_USER")
        password = os.getenv("DB_PASSWORD")
        database = os.getenv("DB_NAME")

        missing = []
        if not server:
            missing.append("DB_SERVER")
        if not user:
            missing.append("DB_USER")
        if not password:
            missing.append("DB_PASSWORD")
        if not database:
            missing.append("DB_NAME")

        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}. "
                "Please set these variables or create a .env file."
            )

        return cls(
            server=server,
            user=user,
            password=password,
            database=database
        )


@dataclass
class LLMConfig:
    model: str
    model_server: str
    api_key: str
    generate_cfg: Dict[str, Any]

    @classmethod
    def default(cls):
        """Create config from environment variables with sensible defaults."""
        return cls(
            model=os.getenv('QWEN_MODEL', 'qwen-max'),
            model_server=os.getenv('QWEN_MODEL_SERVER', 'http://localhost:5001/api/v1'),
            api_key=os.getenv('QWEN_API_KEY', 'EMPTY'),
            generate_cfg={
                'thought_in_content': True,
                'max_input_tokens': 100000,
                'max_tokens': 28000,
                'temperature': 0.6,
                'top_p': 0.95,
                'top_k': 20
            }
        )


@dataclass
class ClaudeLLMConfig:
    """Claude API configuration."""
    model: str = 'claude-opus-4-5'
    api_key: str = ''
    max_tokens: int = 16000
    extended_thinking: bool = True
    thinking_budget_tokens: int = 10000
    temperature: float = 1.0  # Required for extended thinking

    @classmethod
    def from_env(cls):
        """Create config from environment variables."""
        return cls(
            model=os.getenv('CLAUDE_MODEL', 'claude-opus-4-5'),
            api_key=os.getenv('ANTHROPIC_API_KEY', ''),
            max_tokens=int(os.getenv('CLAUDE_MAX_TOKENS', '16000')),
            extended_thinking=os.getenv('CLAUDE_EXTENDED_THINKING', 'true').lower() == 'true',
            thinking_budget_tokens=int(os.getenv('CLAUDE_THINKING_BUDGET', '10000'))
        )


@dataclass
class AppConfig:
    db_config: DatabaseConfig
    llm_config: LLMConfig
    output_dir: Path = Path("output")
    log_level: str = "INFO"
    max_iterations: int = 100
    verbose_console_output: bool = True
    db_result_limit: int = 100
    prompts_dir: Path = Path("prompts")
    prompt_preset_name: Optional[str] = None  # Name of preset to load (without .json extension)
    llm_backend: str = 'qwen'  # 'qwen' or 'claude'
    claude_config: Optional[ClaudeLLMConfig] = None

    def __post_init__(self):
        self.output_dir.mkdir(exist_ok=True)
        self.prompts_dir.mkdir(exist_ok=True)
        # Initialize Claude config from environment if not provided
        if self.claude_config is None:
            self.claude_config = ClaudeLLMConfig.from_env()