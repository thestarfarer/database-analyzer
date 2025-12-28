"""
Report Generation Service

Generates comprehensive analysis reports using LLM integration.
Compiles session data, memory, and tool call history into executive
summaries and recommendations saved as text files.
"""

from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional, TYPE_CHECKING
import logging

from llm import LLMProviderFactory, LLMMessage
from services.prompt_preset_manager import PromptPresetManager

if TYPE_CHECKING:
    from config.settings import AppConfig


class ReportService:
    """Generates comprehensive analysis reports using LLM."""
    def __init__(self, config: 'AppConfig', session_state, output_dir: Path,
                 prompt_preset_manager: Optional[PromptPresetManager] = None):
        """
        Initialize ReportService.

        Args:
            config: AppConfig with LLM backend settings
            session_state: SessionState that contains all memory and session data
            output_dir: Output directory for reports
            prompt_preset_manager: Optional PromptPresetManager for custom prompts
        """
        self.config = config
        self.session_state = session_state
        self.output_dir = output_dir
        self.prompt_preset_manager = prompt_preset_manager
        self.logger = logging.getLogger(__name__)
        # Create provider without tools (report generation is tool-free)
        self.provider = LLMProviderFactory.create(config, tools=[])
    
    def generate_report(self, task_description: str) -> Tuple[str, Path]:
        # Use preset if available
        if self.prompt_preset_manager:
            try:
                preset = self.prompt_preset_manager.get_active_preset()
                report_config = preset.get('report_prompt', {})

                # Build runtime context for variable replacement
                runtime_context = {
                    'TASK_DESCRIPTION': task_description,
                    'MEMORY_SUMMARY': self.session_state.get_memory_summary(),
                    'CURRENT_DATE': datetime.now().strftime("%Y-%m-%d"),
                    'DB_RESULT_LIMIT': 100,  # Default from config
                    'CURRENT_ITERATION': self.session_state.metadata.current_iteration,
                    'COMPLETED_ITERATIONS': self.session_state.get_completed_iterations_count()
                }

                # Apply variables to report instructions template
                report_prompt, unreplaced = self.prompt_preset_manager.build_prompt_with_variables(
                    report_config.get('report_instructions', ''), runtime_context
                )

                # Warn about unreplaced variables
                if unreplaced:
                    self.logger.warning(f"Unreplaced variables in report prompt: {unreplaced}")

            except Exception as e:
                self.logger.warning(f"Failed to build report prompt from preset: {e}, falling back to hardcoded")
                # Fall through to hardcoded version
                report_prompt = self._build_hardcoded_report_prompt(task_description)
        else:
            # Hardcoded fallback
            report_prompt = self._build_hardcoded_report_prompt(task_description)

        messages = [LLMMessage(role="user", content=report_prompt)]

        # Use provider's simple run (no tools)
        response = self.provider.run_simple(
            messages=messages,
            verbose=self.config.verbose_console_output
        )

        report_content = response.content if response.content else "Failed to generate report"
        
        # Save report to file
        safe_topic = task_description[:50].replace('/', '_').replace('\\', '_').replace(':', '_')
        report_filename = f'report_{safe_topic}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
        report_path = self.output_dir / report_filename

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"REPORT TOPIC: {task_description}\n")
            f.write("="*70 + "\n\n")
            f.write(report_content)

        return report_content, report_path

    def _build_hardcoded_report_prompt(self, task_description: str) -> str:
        """Build hardcoded report prompt as fallback."""
        return f"""Based on all the findings stored in memory, generate a detailed report on the following topic:

REPORT TOPIC: {task_description}

Current Memory State:
{self.session_state.get_memory_summary()}

Create a comprehensive report specifically focused on the requested topic. The report should:
1. Directly address the user's specific request: "{task_description}"
2. Use relevant findings from memory to support the analysis
3. Provide concrete, data-backed recommendations
4. Include specific examples from the analyzed data
5. Suggest actionable next steps

Structure the report with clear sections relevant to the topic.
Focus on insights and recommendations that directly relate to: {task_description}"""