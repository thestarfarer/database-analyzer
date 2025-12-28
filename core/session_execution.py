"""
Unified Session Execution Engine

This module handles all session execution logic for the Database Analyzer.
"""

import time
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from qwen_agent.tools.base import BaseTool

from config.settings import AppConfig
from database.connection import DatabaseConnection
from tools.sql_tool import ExecuteSQLTool
from tools.memory_tool import MemoryTool
from ui.cli_interface import CLIInterface
from services.report_service import ReportService
from services.prompt_preset_manager import PromptPresetManager
from llm import LLMProviderFactory, ToolDefinition, LLMMessage

from .session_state import SessionState, ToolCall


class SessionExecution:
    """
    Unified execution engine for Database Analyzer.

    Handles:
    - LLM iteration execution
    - Tool execution coordination
    - User input management
    - Session state updates
    """

    def __init__(self, config: AppConfig, db_connection: DatabaseConnection, save_callback=None):
        self.config = config
        self.db_connection = db_connection
        self.logger = logging.getLogger(__name__)
        self.save_callback = save_callback  # Callback to save session after tool calls
        self.logger.info(f"[DEBUG] SessionExecution initialized with save_callback: {save_callback is not None}")

        # Initialize prompt preset manager using factory method
        preset_name = config.prompt_preset_name if config.prompt_preset_name else "default"
        self.prompt_preset_manager = PromptPresetManager.create_with_fallback(
            config.prompts_dir,
            preset_name,
            fallback_to_default=True,
            logger=self.logger
        )

        if self.prompt_preset_manager and self.prompt_preset_manager.active_preset:
            self.logger.info(f"[DEBUG] Loaded prompt preset: {preset_name}")
        else:
            self.logger.warning(f"[DEBUG] No preset loaded, using hardcoded prompts")

        # Initialize tools
        self.sql_tool = ExecuteSQLTool(db_connection, verbose=config.verbose_console_output)
        self.memory_tool = MemoryTool(None, verbose=config.verbose_console_output)  # Will be set per session

        # Create wrapper tools for logging
        self.sql_tool_wrapper = None  # Will be created per session
        self.memory_tool_wrapper = None  # Will be created per session

        # LLM provider (will be created per session via factory)
        self.provider = None
        self.tool_definitions = None

        # Initialize CLI and report service
        self.cli_interface = None  # Will be initialized per session
        self.report_service = None  # Will be initialized per session

    def initialize_for_session(self, session_state: SessionState) -> None:
        """Initialize execution components for a specific session."""
        # Store session state reference
        self.session_state = session_state

        # Pass session state directly to memory tool
        self.memory_tool.session_state = session_state

        # Create tool wrappers that log calls and trigger saves
        self.sql_tool_wrapper = create_logging_wrapper(self.sql_tool, self, session_state)
        self.memory_tool_wrapper = create_logging_wrapper(self.memory_tool, self, session_state)

        # Create ToolDefinition objects for the provider
        self.tool_definitions = [
            ToolDefinition(
                name=self.sql_tool_wrapper.name,
                description=self.sql_tool_wrapper.description,
                parameters=self.sql_tool_wrapper.parameters,
                callable=self.sql_tool_wrapper.call
            ),
            ToolDefinition(
                name=self.memory_tool_wrapper.name,
                description=self.memory_tool_wrapper.description,
                parameters=self.memory_tool_wrapper.parameters,
                callable=self.memory_tool_wrapper.call
            )
        ]

        # Create LLM provider using factory
        self.provider = LLMProviderFactory.create(self.config, self.tool_definitions)
        self.logger.info(f"[DEBUG] Using LLM provider: {self.provider.name}")

        # Store backend in session metadata
        session_state.metadata.llm_backend = self.config.llm_backend

        # Initialize CLI and report service
        self.cli_interface = CLIInterface(session_state)
        self.report_service = ReportService(
            self.config,
            self.session_state,
            self.config.output_dir,
            self.prompt_preset_manager
        )

    def execute_iteration(self, session_state: SessionState, iteration_num: int, prompt: str, user_input: Optional[str] = None) -> str:
        """
        Execute a complete iteration.

        Args:
            session_state: Current session state
            iteration_num: Iteration number to execute
            prompt: Base prompt for the iteration (from build_base_prompt or build_continuation_prompt)
            user_input: User input for this iteration (will be appended to final prompt sent to LLM)

        Returns:
            LLM response content
        """
        # Set PID to mark session as running
        import os
        session_state.metadata.pid = os.getpid()

        if self.config.verbose_console_output:
            self._log_iteration_start(iteration_num)

        # Note: Iteration already added by session_manager before calling this method
        # Save session immediately after iteration creation for live WebUI visibility
        if self.save_callback:
            try:
                self.logger.info(f"[DEBUG] Calling save_callback after iteration {iteration_num} creation")
                self.save_callback()
                self.logger.info(f"[DEBUG] Session saved successfully after iteration {iteration_num} creation")
            except Exception as e:
                self.logger.error(f"[DEBUG] Failed to save session after iteration creation: {e}")
        else:
            self.logger.warning(f"[DEBUG] No save_callback available for iteration {iteration_num} creation")

        try:
            # Build LLM message with memory context and user commands history
            memory_summary = session_state.get_memory_summary()
            user_commands_history = session_state.get_user_commands_history()
            message_content = prompt + '\n\n' + memory_summary + user_commands_history

            # Add current iteration's user input if provided
            if user_input and user_input.strip():
                message_content += f"""

TASK FOR THIS ITERATION:
{user_input}
"""

            messages = [LLMMessage(role="user", content=message_content)]

            if self.config.verbose_console_output:
                print(f"\n=== Iteration {iteration_num} Request ===\n{message_content}\n")

            # Save session before starting LLM execution for live WebUI visibility
            if self.save_callback:
                try:
                    self.save_callback()
                    self.logger.debug(f"Session saved before starting LLM execution for iteration {iteration_num}")
                except Exception as e:
                    self.logger.warning(f"Failed to save session before LLM execution: {e}")

            # Execute LLM interaction via provider
            final_response = None
            for response in self.provider.run(
                messages,
                self.tool_definitions,
                verbose=self.config.verbose_console_output
            ):
                final_response = response

                # Log thinking content if present (Claude extended thinking)
                if response.thinking and self.config.verbose_console_output:
                    thinking_preview = response.thinking[:200] + "..." if len(response.thinking) > 200 else response.thinking
                    print(f"🧠 Thinking: {thinking_preview}")

            # Extract response content
            if final_response:
                response_content = final_response.content
            else:
                response_content = "No response received"

            if self.config.verbose_console_output:
                print(f"\n=== Iteration {iteration_num} Response ===\n{response_content}\n")

            # Complete iteration
            session_state.complete_iteration(iteration_num, response_content)

            # Save session after iteration completion for live WebUI visibility
            if self.save_callback:
                try:
                    self.save_callback()
                    self.logger.debug(f"Session saved after iteration {iteration_num} completion")
                except Exception as e:
                    self.logger.warning(f"Failed to save session after iteration completion: {e}")

            if self.config.verbose_console_output:
                # Show completion status with response length
                response_length = len(response_content) if response_content else 0
                print(f"\n✅ Response generated ({response_length} characters)")
                self._log_iteration_end(iteration_num)

            return response_content

        except Exception as e:
            error_response = f"[Iteration failed: {str(e)}]"
            session_state.complete_iteration(iteration_num, error_response)

            # Save session after iteration error for live WebUI visibility
            if self.save_callback:
                try:
                    self.save_callback()
                    self.logger.debug(f"Session saved after iteration {iteration_num} error")
                except Exception as save_e:
                    self.logger.warning(f"Failed to save session after iteration error: {save_e}")

            self.logger.error(f"Iteration {iteration_num} failed: {e}")
            raise

    def handle_user_input(self, session_state: SessionState) -> tuple[str, bool]:
        """
        Handle user input for next iteration.

        Args:
            session_state: Current session state

        Returns:
            Tuple of (user_input, should_generate_report)
        """
        user_input, should_generate_report = self.cli_interface.get_user_input()

        # Save session after user input for live WebUI visibility
        if self.save_callback:  # Save after all user input to show interaction occurred
            try:
                self.save_callback()
                self.logger.debug(f"Session saved after user input")
            except Exception as e:
                self.logger.warning(f"Failed to save session after user input: {e}")

        return user_input, should_generate_report

    def generate_report(self, session_state: SessionState, topic: str) -> tuple[str, str]:
        """
        Generate and return final report.

        Args:
            session_state: Current session state
            topic: Report topic

        Returns:
            Tuple of (report_content, file_path_str)
        """
        if self.config.verbose_console_output:
            print(f"\n{'='*50}")
            print(f"GENERATING REPORT: {topic}")
            print('='*50)

        content, file_path = self.report_service.generate_report(topic)
        file_path_str = str(file_path)

        if self.config.verbose_console_output:
            self.cli_interface.display_report(content, file_path_str)

        return content, file_path_str

    def build_base_prompt(self) -> str:
        """Build the base prompt for analysis."""
        # Use preset if available, otherwise use hardcoded prompts
        if self.prompt_preset_manager and self.prompt_preset_manager.active_preset:
            try:
                preset = self.prompt_preset_manager.get_active_preset()
                base_prompt_config = preset['base_prompt']

                # Build runtime context for variable replacement
                runtime_context = {
                    'CURRENT_DATE': datetime.now().strftime("%Y-%m-%d"),
                    'DB_RESULT_LIMIT': self.db_connection.result_limit
                }

                # Apply variables to each component
                schema, unreplaced_schema = self.prompt_preset_manager.build_prompt_with_variables(
                    base_prompt_config['schema'], runtime_context
                )
                tools_description, unreplaced_tools = self.prompt_preset_manager.build_prompt_with_variables(
                    base_prompt_config['tools_description'], runtime_context
                )
                domain_context, unreplaced_context = self.prompt_preset_manager.build_prompt_with_variables(
                    base_prompt_config['domain_context'], runtime_context
                )
                task_instructions, unreplaced_task = self.prompt_preset_manager.build_prompt_with_variables(
                    base_prompt_config['task_instructions'], runtime_context
                )

                # Warn about unreplaced variables
                all_unreplaced = unreplaced_schema + unreplaced_tools + unreplaced_context + unreplaced_task
                if all_unreplaced:
                    self.logger.warning(f"Unreplaced variables in base prompt: {list(set(all_unreplaced))}")

                # Assemble using template (with {field} placeholders for Python format)
                assembly_template = base_prompt_config.get('assembly_template',
                    "Database schema:\n{schema}\n\n{tools_description}\n\n{domain_context}\n\n{task_instructions}")

                return assembly_template.format(
                    schema=schema,
                    tools_description=tools_description,
                    domain_context=domain_context,
                    task_instructions=task_instructions
                )

            except KeyError as e:
                self.logger.warning(f"Missing required field in preset: {e}, falling back to hardcoded")
                # Fall through to hardcoded version
            except ValueError as e:
                self.logger.warning(f"Invalid preset data: {e}, falling back to hardcoded")
                # Fall through to hardcoded version
            except Exception as e:
                self.logger.error(f"Unexpected error building prompt from preset: {e}, falling back to hardcoded")
                # Fall through to hardcoded version

        # Hardcoded fallback - generic placeholder prompts
        # For production use, create a prompt preset in prompts/ directory
        schema = """[Database schema not configured]

To use this tool effectively, please create a prompt preset in the prompts/ directory
with your database schema. See prompts/default.json for an example structure.

You can explore the database schema using queries like:
- SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
- SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'your_table'"""

        memory_prompt = """
You have access to two tools:
1. execute_sql - for running SQL queries on the database
2. memory - for storing and retrieving information across iterations
   - Use 'memory' with action='update', key='category', value='memory_key:detailed_content' to store new findings
   - Use 'memory' with action='remove', key='category', value='memory_key' to remove a specific entry

IMPORTANT: At the start of each iteration:
1. Review context from previous iterations (summarized below)
2. Pay attention to user input for research direction
3. Conduct substantive analysis: explore data, identify patterns, evaluate hypotheses, and answer user questions
4. When you execute SQL queries, store all key insights and findings in memory after analyzing the results
5. Remove outdated or incorrect entries when necessary

Memory categories available:
- insights: General insights discovered
- patterns: Data patterns and trends discovered
- explored_areas: What has already been analyzed
- key_findings: Important discoveries
- opportunities: Specific opportunities identified
- data_issues: Data quality or consistency issues found
- metrics: Key metrics discovered (use format 'metric_name:value' for updates)
- context: Domain context and understanding
- user_requests: Specific requests from user input
- data_milestones: Important data milestones and temporal markers"""

        domain_context = f"""Today is: {datetime.now().strftime("%Y-%m-%d")}

You are an AI assistant helping to analyze a database.
Answering general questions on any topic is allowed and encouraged.

Note: For domain-specific context, use a prompt preset configured for your database."""

        task_instructions = f"""Explore the database and identify patterns, trends, and insights based on user guidance.

Memory usage guidelines:
- After executing SQL queries and analyzing results, store all findings using memory tool
- Several memories can be added at once by calling memory tool multiple times
- Use delete function of the memory tool to remove incorrect memories when needed
- Record precise details when relevant

Technical guidelines:
- Avoid making decisions and creating memories based on truncated SQL data
- Adapt queries to fit into {self.db_connection.result_limit} rows limit for analysis"""

        return f"Database schema:\n{schema}\n\n{memory_prompt}\n\n{domain_context}\n\n{task_instructions}"

    def build_verification_prompt(self, session_state: SessionState, category: str, key: str, value: str) -> str:
        """
        Build prompt for memory verification agent.

        Args:
            session_state: Current session state for memory context
            category: Memory category
            key: Memory key
            value: Current memory value

        Returns:
            Verification prompt with full context
        """
        base_prompt = self.build_base_prompt()
        memory_summary = session_state.get_memory_summary()

        # Use preset if available
        if self.prompt_preset_manager and self.prompt_preset_manager.active_preset:
            try:
                preset = self.prompt_preset_manager.get_active_preset()
                verification_config = preset.get('verification_prompt', {})

                # Build runtime context for variable replacement
                runtime_context = {
                    'CATEGORY': category,
                    'KEY': key,
                    'VALUE': value
                }

                # Apply variables to verification task template
                verification_task, unreplaced_vars = self.prompt_preset_manager.build_prompt_with_variables(
                    verification_config.get('verification_task_template', ''), runtime_context
                )

                # Warn about unreplaced variables
                if unreplaced_vars:
                    self.logger.warning(f"Unreplaced variables in verification prompt: {unreplaced_vars}")

                # Assemble using template
                assembly_template = verification_config.get('assembly_template',
                    "{base_prompt}\n\n{memory_summary}\n\n{verification_task_template}")

                return assembly_template.format(
                    base_prompt=base_prompt,
                    memory_summary=memory_summary,
                    verification_task_template=verification_task
                )

            except KeyError as e:
                self.logger.warning(f"Missing required field in verification preset: {e}, falling back to hardcoded")
                # Fall through to hardcoded version
            except ValueError as e:
                self.logger.warning(f"Invalid verification preset data: {e}, falling back to hardcoded")
                # Fall through to hardcoded version
            except Exception as e:
                self.logger.error(f"Unexpected error building verification prompt from preset: {e}, falling back to hardcoded")
                # Fall through to hardcoded version

        # Hardcoded fallback
        verification_task = f"""

MEMORY VERIFICATION TASK:

You are verifying the accuracy of ONE SPECIFIC memory item from the accumulated analysis above.

>>> MEMORY ITEM TO VERIFY <<<
Category: {category}
Key: {key}
Current Value: {value}
>>> END OF ITEM TO VERIFY <<<

Your task:
1. Review the memory item in context of ALL accumulated memories above
2. Use execute_sql to verify this SPECIFIC item against current database state
3. Check if the statement is accurate, outdated, or incorrect
4. Provide evidence from your SQL queries
5. Determine confidence level (high/medium/low)
6. Recommend action: keep/update/remove

IMPORTANT: You must respond with ONLY a JSON object in this exact format:
{{
    "verified": true/false,
    "confidence": "high/medium/low",
    "evidence": "Description of SQL queries run and results",
    "recommendation": "keep/update/remove",
    "updated_value": "New memory content if update recommended (or null)",
    "reasoning": "Explanation of your decision"
}}

Use execute_sql tool to gather evidence, then provide the JSON response.
"""

        return f"{base_prompt}\n\n{memory_summary}\n\n{verification_task}"

    def build_continuation_prompt(self, session_state: SessionState) -> str:
        """
        Build continuation prompt that acknowledges previous work.

        Args:
            session_state: Current session state

        Returns:
            Continuation prompt incorporating session history

        Note:
            Current iteration's user input is added separately in execute_iteration()
            to ensure it appears in the final message sent to LLM.
        """
        base_prompt = self.build_base_prompt()

        # Use preset if available
        if self.prompt_preset_manager and self.prompt_preset_manager.active_preset:
            try:
                preset = self.prompt_preset_manager.get_active_preset()
                continuation_config = preset.get('continuation_prompt', {})

                # Build runtime context for variable replacement
                runtime_context = {
                    'CURRENT_ITERATION': session_state.metadata.current_iteration,
                    'COMPLETED_ITERATIONS': session_state.get_completed_iterations_count()
                }

                # Apply variables to iteration context template
                iteration_context, unreplaced_vars = self.prompt_preset_manager.build_prompt_with_variables(
                    continuation_config.get('iteration_context_template', ''), runtime_context
                )

                # Warn about unreplaced variables
                if unreplaced_vars:
                    self.logger.warning(f"Unreplaced variables in continuation prompt: {unreplaced_vars}")

                # Assemble using template
                assembly_template = continuation_config.get('assembly_template',
                    "{base_prompt}{iteration_context_template}")

                return assembly_template.format(
                    base_prompt=base_prompt,
                    iteration_context_template=iteration_context
                )

            except KeyError as e:
                self.logger.warning(f"Missing required field in continuation preset: {e}, falling back to hardcoded")
                # Fall through to hardcoded version
            except ValueError as e:
                self.logger.warning(f"Invalid continuation preset data: {e}, falling back to hardcoded")
                # Fall through to hardcoded version
            except Exception as e:
                self.logger.error(f"Unexpected error building continuation prompt from preset: {e}, falling back to hardcoded")
                # Fall through to hardcoded version

        # Hardcoded fallback
        iteration_context = f"""

═══════════════════════════════════════════════════════════════
EXECUTION STATUS:
- Current Iteration: {session_state.metadata.current_iteration}
- Completed Iterations: {session_state.get_completed_iterations_count()}
- You are STARTING a new iteration now
═══════════════════════════════════════════════════════════════
"""

        return base_prompt + iteration_context


    def log_tool_call(self, session_state: SessionState, iteration: int, tool_name: str,
                      input_data: Dict[str, Any], output_data: str, execution_time: float) -> None:
        """Log a tool call to the session state."""
        # Generate unique call ID
        total_calls = sum(len(iter.tool_calls) for iter in session_state.iterations)
        call_id = f"call_{total_calls + 1:03d}"

        tool_call = ToolCall(
            id=call_id,
            tool=tool_name,
            timestamp=time.time(),
            input=input_data,
            output=output_data,
            execution_time=execution_time
        )

        session_state.add_tool_call(iteration, tool_call)

        # Save session after each tool call for live WebUI visibility
        if self.save_callback:
            try:
                self.save_callback()
                self.logger.debug(f"Session saved after tool call: {tool_name}")
            except Exception as e:
                self.logger.warning(f"Failed to save session after tool call: {e}")

    def _log_iteration_start(self, iteration: int):
        """Log iteration start with enhanced formatting."""
        print("\n" + "🔄" + "="*78 + "🔄")
        print(f"🚀 STARTING ITERATION {iteration} - {datetime.now().strftime('%H:%M:%S')}")
        print("🔄" + "="*78 + "🔄")
        print(f"🎯 Max Iterations: {self.config.max_iterations}")
        print(f"📊 Progress: {iteration}/{self.config.max_iterations} ({iteration/self.config.max_iterations*100:.1f}%)")
        print("-" * 80)

    def _log_iteration_end(self, iteration: int):
        """Log iteration end."""
        print("\n" + "-" * 80)
        print(f"✅ COMPLETED ITERATION {iteration} - {datetime.now().strftime('%H:%M:%S')}")
        print("🔄" + "="*78 + "🔄\n")



def create_logging_wrapper(original_tool, session_execution, session_state):
    """
    Create a wrapper tool that logs all calls and triggers session saves.

    This ensures that every tool call is logged to the session state
    and triggers a save for live WebUI visibility.
    """

    class LoggingWrapper(BaseTool):
        # Copy tool attributes for qwen-agent compatibility
        name = getattr(original_tool, 'name', 'unknown')
        description = getattr(original_tool, 'description', '')
        parameters = getattr(original_tool, 'parameters', [])

        def __init__(self):
            self.original_tool = original_tool
            self.session_execution = session_execution
            self.session_state = session_state

        def _extract_tool_parameters(self, args, kwargs):
            """Extract only relevant tool parameters for logging."""
            # For SQL tool - only log the query parameter
            if self.name == 'execute_sql':
                query = kwargs.get('query') or (args[0] if args else None)
                return {'query': query}

            # For memory tool - handle both kwargs and JSON string calling patterns
            elif self.name == 'memory':
                params = {}

                # First try kwargs (direct parameter calling)
                if 'action' in kwargs and kwargs['action'] is not None:
                    params['action'] = kwargs['action']
                if 'key' in kwargs and kwargs['key'] is not None:
                    params['key'] = kwargs['key']
                if 'value' in kwargs and kwargs['value'] is not None:
                    params['value'] = kwargs['value']

                # If no kwargs, try JSON string in first argument (qwen-agent pattern)
                if not params and args and isinstance(args[0], str) and args[0].startswith('{'):
                    try:
                        parsed = json.loads(args[0])
                        if 'action' in parsed and parsed['action'] is not None:
                            params['action'] = parsed['action']
                        if 'key' in parsed and parsed['key'] is not None:
                            params['key'] = parsed['key']
                        if 'value' in parsed and parsed['value'] is not None:
                            params['value'] = parsed['value']
                    except json.JSONDecodeError:
                        pass

                return params

            # For other tools - log basic kwargs only (no args to avoid Message objects)
            else:
                # Only include simple JSON-serializable values
                simple_kwargs = {}
                for k, v in kwargs.items():
                    if isinstance(v, (str, int, float, bool, type(None))):
                        simple_kwargs[k] = v
                    else:
                        simple_kwargs[k] = str(v)
                return simple_kwargs

        def call(self, *args, **kwargs):
            """Call the original tool and log the execution."""
            start_time = time.time()

            try:
                # Call the original tool
                result = self.original_tool.call(*args, **kwargs)
                execution_time = time.time() - start_time

                # Get current iteration number
                current_iteration = self.session_state.metadata.current_iteration

                # Log the tool call (this will trigger save callback)
                # Extract only relevant tool parameters for logging
                input_data = self._extract_tool_parameters(args, kwargs)
                self.session_execution.log_tool_call(
                    session_state=self.session_state,
                    iteration=current_iteration,
                    tool_name=self.name,
                    input_data=input_data,
                    output_data=result,
                    execution_time=execution_time
                )

                return result

            except Exception as e:
                execution_time = time.time() - start_time
                error_result = f"Error: {str(e)}"

                # Log failed tool call
                current_iteration = self.session_state.metadata.current_iteration
                input_data = self._extract_tool_parameters(args, kwargs)
                self.session_execution.log_tool_call(
                    session_state=self.session_state,
                    iteration=current_iteration,
                    tool_name=self.name,
                    input_data=input_data,
                    output_data=error_result,
                    execution_time=execution_time
                )

                raise

    return LoggingWrapper()


