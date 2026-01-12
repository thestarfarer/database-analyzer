"""
Unified Session Manager - Core System Coordinator

This module provides the central controller for the Database Analyzer system,
coordinating all session operations through a unified architecture.

Key Responsibilities:
- Session lifecycle management (create, load, continue, finalize)
- Execution coordination between LLM, tools, and user interaction
- Live session persistence and recovery
- Error handling and graceful degradation
- User interaction flow and progress reporting

Architecture:
- SessionState: Maintains complete session state and metadata
- SessionExecution: Handles LLM integration and tool execution
- SessionPersistence: Manages session file I/O and recovery
- CLI Interface: Handles user input and console output

Session Logic:
- Supports resume from any completed iteration
- Incomplete iterations are auto-cleaned on resume
- PID-based process tracking for session status
- Live saving after each tool call prevents data loss
"""

import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from config.settings import AppConfig
from database.connection import DatabaseConnection

from .session_state import SessionState
from .session_persistence import SessionPersistence
from .session_execution import SessionExecution


class SessionManager:
    """
    Central session controller for the Database Analyzer.

    This unified manager coordinates:
    - Session lifecycle (create, load, save, continue)
    - Execution flow (iterations, tool calls, user input)
    - State persistence and recovery
    - Session completion and reporting
    """

    def __init__(self, config: AppConfig, db_connection: DatabaseConnection):
        self.config = config
        self.db_connection = db_connection
        self.logger = logging.getLogger(__name__)

        # Initialize unified components
        self.persistence = SessionPersistence(Path(config.output_dir))
        self.execution = SessionExecution(config, db_connection, save_callback=self._save_session_callback)

        # Current session state
        self.current_session: Optional[SessionState] = None
        self.resume_with_task: str = ""  # Store task provided for resumed sessions

        # Live saving after each action via save_callback

    def start_session(self, session_file: Optional[Path] = None, first_user_input: str = "", session_name: Optional[str] = None) -> SessionState:
        """
        Start a new session or continue an existing one.

        Args:
            session_file: Path to existing session file to continue, or None for new session
            first_user_input: First user input for new sessions OR user input for resumed sessions
            session_name: Optional custom name for the session (new sessions only)

        Returns:
            SessionState object for the started session
        """
        if session_file and session_file.exists():
            return self._continue_session(session_file, first_user_input)
        else:
            return self._create_new_session(first_user_input, session_name)

    def _create_new_session(self, first_user_input: str, session_name: Optional[str] = None) -> SessionState:
        """
        Create a new session with unique ID and first user input.

        Args:
            first_user_input: First user input for new session (optional)
            session_name: Optional custom name for display (defaults to None)

        Returns:
            SessionState: Newly created session ready for execution

        Core Logic:
        - Session IDs use YYYYMMDD_HHMMSS format for WebUI compatibility
        - If no input provided, prompts user via CLI interface
        - PID is automatically captured for process tracking
        - Session is immediately saved to prevent data loss
        """
        # Generate unique session ID in YYYYMMDD_HHMMSS format for WebUI compatibility
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Create session state
        self.current_session = SessionState(session_id=session_id)

        # Store preset name in session metadata for persistence
        self.current_session.metadata.preset_name = self.config.prompt_preset_name

        # Store custom session name if provided
        self.current_session.metadata.name = session_name

        # Get first user input from user if not provided via command line
        if not first_user_input:
            # Create temporary CLI interface just for getting initial task
            # (avoids initializing full execution stack twice)
            from ui.cli_interface import CLIInterface
            temp_cli = CLIInterface(self.current_session)
            first_user_input = temp_cli.get_initial_task()

        # Store first user input for the first iteration
        self.resume_with_task = first_user_input

        # Initialize execution components for this session (LLM, tools, CLI)
        self.execution.initialize_for_session(self.current_session)

        self.logger.info(f"Started new session: {session_id}")
        if self.config.verbose_console_output:
            display_name = session_name or session_id
            print(f"\n🎯 New Session: {display_name}")
            if session_name:
                print(f"🔖 Session ID: {session_id}")
            print(f"📋 First Input: {first_user_input}")
            print("-" * 50)

        # Save session immediately after creation to prevent data loss if interrupted
        self.save_session()

        return self.current_session


    def _continue_session(self, session_file: Path, resume_task: str = "") -> SessionState:
        """Continue an existing session."""
        try:
            # Store resume task for later use in execution loop
            self.resume_with_task = resume_task

            # Load session state
            self.current_session = self.persistence.load_session(session_file)

            # Override config preset with session's saved preset for consistency
            if self.current_session.metadata.preset_name is not None:
                original_preset = self.config.prompt_preset_name
                self.config.prompt_preset_name = self.current_session.metadata.preset_name
                if original_preset != self.current_session.metadata.preset_name:
                    self.logger.info(f"Using session's preset '{self.current_session.metadata.preset_name}' instead of config preset '{original_preset}'")
                    # Reinitialize SessionExecution with the correct preset
                    self.execution = SessionExecution(self.config, self.db_connection, save_callback=self._save_session_callback)

            # Initialize execution components for this session
            self.execution.initialize_for_session(self.current_session)

            resume_point = self.current_session.get_resume_point()

            self.logger.info(f"Continued session: {self.current_session.metadata.session_id}")
            if self.config.verbose_console_output:
                print(f"\n🔄 Continuing Session: {self.current_session.metadata.session_id}")
                # Get first iteration user input for display
                first_user_input = ""
                if self.current_session.iterations:
                    first_user_input = self.current_session.iterations[0].user_input or ""
                if first_user_input:
                    print(f"📋 Original Task: {first_user_input}")
                print(f"🎯 Resume Point: {resume_point.context_summary}")
                print(f"📊 Completed Iterations: {self.current_session.get_completed_iterations_count()}")
                print(f"💾 Memory Categories: {len(self.current_session.get_memory_data_from_tool_calls())}")
                print("-" * 50)

            return self.current_session

        except Exception as e:
            self.logger.error(f"Failed to continue session from {session_file}: {e}")
            raise RuntimeError(f"Cannot continue session: {e}") from e

    def run_session(self) -> None:
        """
        Run the complete session until completion.

        This is the main execution loop for the Database Analyzer.
        """
        if not self.current_session:
            raise RuntimeError("No active session. Call start_session() first.")

        try:
            # Determine starting point
            resume_point = self.current_session.get_resume_point()
            current_iteration = resume_point.iteration

            # Build initial prompt
            if resume_point.should_restart_iteration:
                # Restarting incomplete iteration
                prompt = self.execution.build_continuation_prompt(self.current_session)
            else:
                # Starting new iteration or continuing from base
                if current_iteration == 1 and not self.current_session.iterations:
                    # First iteration of new session - user input will be provided later
                    prompt = ""  # Will be set after user input
                else:
                    # Continuing from completed iteration
                    prompt = self.execution.build_continuation_prompt(self.current_session)

            # Main execution loop
            while current_iteration <= self.config.max_iterations:
                try:
                    # Collect user input for this iteration FIRST
                    if current_iteration == 1 and not self.current_session.iterations:
                        # First iteration of new session - use resume_with_task or prompt user
                        if self.resume_with_task:
                            user_input_for_iteration = self.resume_with_task
                            self.resume_with_task = ""  # Clear it after use
                        else:
                            # Prompt user for first input
                            user_input_for_iteration = self.execution.cli_interface.get_initial_task()
                        # Now build the base prompt (user input will be in user_commands_history)
                        prompt = self.execution.build_base_prompt()
                    elif self.resume_with_task:
                        # Resumed session with --task provided - use it as user input
                        user_input_for_iteration = self.resume_with_task
                        self.resume_with_task = ""  # Clear it after first use
                        print(f"\n{'='*60}")
                        print(f"🚀 STARTING ITERATION {current_iteration} (RESUMED WITH TASK)")
                        print(f"{'='*60}")
                    else:
                        # Get user input for this iteration (new iteration or interactive resume)
                        print(f"\n{'='*60}")
                        print(f"🚀 STARTING ITERATION {current_iteration}")
                        print(f"{'='*60}")

                        user_input_for_iteration, should_generate_report = self.execution.handle_user_input(self.current_session)

                        if user_input_for_iteration == "EXIT":
                            self.logger.info("User requested exit")
                            break
                        elif should_generate_report:
                            self._generate_final_report(user_input_for_iteration)
                            break

                    # Create iteration with user input
                    iteration = self.current_session.add_iteration(current_iteration, prompt, user_input_for_iteration)

                    # Execute iteration with the user input
                    response = self.execution.execute_iteration(
                        self.current_session,
                        current_iteration,
                        prompt,
                        user_input_for_iteration
                    )

                    # Live saving happens after each action via callback

                    # Show iteration completion message
                    if self.config.verbose_console_output:
                        print(f"\n{'='*60}")
                        print(f"🏁 ITERATION {current_iteration} COMPLETED")
                        print(f"{'='*60}")

                    # Move to next iteration
                    current_iteration += 1

                    # Build prompt for next iteration
                    if current_iteration <= self.config.max_iterations:
                        prompt = self.execution.build_continuation_prompt(self.current_session)

                except KeyboardInterrupt:
                    self.logger.info("Session completed by user")
                    self.current_session.finalize_session()
                    self.save_session()  # Save session before breaking
                    break
                except Exception as e:
                    self.logger.error(f"Error in iteration {current_iteration}: {e}")
                    self.current_session.finalize_session()
                    break

            # Check if we reached max iterations
            if current_iteration > self.config.max_iterations:
                self.logger.info(f"Reached maximum iterations ({self.config.max_iterations})")
                if self.config.verbose_console_output:
                    print(f"\n⏰ Reached maximum iterations ({self.config.max_iterations})")

                # Ask user if they want to generate a report
                report_topic, should_generate_report = self.execution.handle_user_input(self.current_session)
                if should_generate_report:
                    self._generate_final_report(report_topic)

            # Finalize session
            self.current_session.finalize_session()

            # Final save
            self.save_session()

            if self.config.verbose_console_output:
                self._print_session_summary()

        except Exception as e:
            self.logger.error(f"Session execution failed: {e}")
            if self.current_session:
                self.save_session()
            raise

    def save_session(self) -> Path:
        """
        Save current session state.

        Returns:
            Path to saved session file
        """
        if not self.current_session:
            raise RuntimeError("No active session to save")

        session_file = self.persistence.save_session(self.current_session)
        return session_file

    def finalize_current_session(self) -> None:
        """
        Gracefully finalize the current session for shutdown.

        This method should be called when receiving termination signals
        to ensure proper session cleanup and data persistence.
        """
        if not self.current_session:
            self.logger.warning("No active session to finalize")
            return

        try:
            self.logger.info(f"Finalizing session {self.current_session.metadata.session_id}")

            # Mark session as completed with proper end time
            self.current_session.finalize_session()

            # Save final session state
            session_file = self.save_session()
            self.logger.info(f"Session finalized and saved to {session_file}")

        except Exception as e:
            self.logger.error(f"Error finalizing session: {e}")
            # Still try to save even if finalization fails
            try:
                self.save_session()
            except Exception as save_error:
                self.logger.error(f"Error saving session during finalization: {save_error}")

    def _save_session_callback(self) -> None:
        """Callback for live session saving after tool calls."""
        self.logger.info(f"[DEBUG] _save_session_callback called")
        if self.current_session:
            try:
                self.logger.info(f"[DEBUG] Calling save_session() for session {self.current_session.metadata.session_id}")
                session_file = self.save_session()
                self.logger.info(f"[DEBUG] Session saved successfully to {session_file}")
            except Exception as e:
                self.logger.error(f"[DEBUG] Live save failed: {e}")
        else:
            self.logger.warning(f"[DEBUG] No current_session available for save")

    def _generate_final_report(self, report_topic: str = None) -> None:
        """Generate and display final report."""
        try:
            # Use provided topic - no fallback, user must specify what they want
            if not report_topic:
                raise ValueError("Report topic must be specified - no default fallback")
            topic = report_topic
            content, file_path = self.execution.generate_report(self.current_session, topic)

            if self.config.verbose_console_output:
                print(f"\n📊 Final report generated: {file_path}")

        except Exception as e:
            self.logger.error(f"Report generation failed: {e}")
            if self.config.verbose_console_output:
                print(f"❌ Failed to generate report: {e}")

    def _print_session_summary(self) -> None:
        """Print session completion summary."""
        session = self.current_session
        completed_iterations = session.get_completed_iterations_count()
        total_iterations = len(session.iterations)

        duration = datetime.fromtimestamp(session.metadata.end_time or time.time()) - datetime.fromtimestamp(session.metadata.start_time)
        duration_str = str(duration).split('.')[0]  # Remove microseconds

        print(f"\n{'='*60}")
        print(f"📋 SESSION COMPLETED: {session.metadata.session_id}")
        print(f"{'='*60}")
        # Get first iteration user input for display
        first_user_input = ""
        if session.iterations:
            first_user_input = session.iterations[0].user_input or ""
        if first_user_input:
            print(f"🎯 Task: {first_user_input}")
        print(f"⏱️  Duration: {duration_str}")
        print(f"🔄 Iterations: {completed_iterations}/{total_iterations} completed")
        memory_data = session.get_memory_data_from_tool_calls()
        total_items = sum(len(items) for items in memory_data.values())
        print(f"💾 Memory Items: {total_items}")

        # Show tool call summary
        total_tool_calls = sum(len(iter.tool_calls) for iter in session.iterations)
        if total_tool_calls > 0:
            print(f"🔧 Tool Calls: {total_tool_calls}")

        # Show user input summary
        user_inputs = [iter.user_input for iter in session.iterations if iter.user_input and iter.user_input.strip()]
        if user_inputs:
            print(f"💬 User Inputs: {len(user_inputs)} entries")

        print(f"{'='*60}")

    def list_available_sessions(self) -> list:
        """
        List all available session files.

        Returns:
            List of session file information dictionaries
        """
        session_files = self.persistence.list_session_files()
        session_info = []

        for session_file in session_files:
            try:
                summary = self.persistence.get_session_summary(session_file)
                session_info.append({
                    "file_path": str(session_file),
                    "file_name": session_file.name,
                    **summary
                })
            except Exception as e:
                session_info.append({
                    "file_path": str(session_file),
                    "file_name": session_file.name,
                    "error": str(e),
                    "status": "error"
                })

        return session_info

    def find_latest_session(self) -> Optional[Path]:
        """Find the most recent session file."""
        return self.persistence.find_latest_session()

    def verify_memory_item(self, session_state: SessionState, category: str, key: str) -> Dict[str, Any]:
        """
        Verify a specific memory item using SQL evidence.

        Args:
            session_state: Session state containing memory
            category: Memory category
            key: Memory key

        Returns:
            Verification result dictionary
        """
        memory_data = session_state.get_memory_data_from_tool_calls()
        if category not in memory_data:
            raise ValueError(f"Category {category} not found in memory")

        memory_value = None
        for item in memory_data[category]:
            if item.startswith(f"{key}:"):
                memory_value = item.split(':', 1)[1]
                break

        if not memory_value:
            raise ValueError(f"Memory key {key} not found in category {category}")

        from services.memory_verification import MemoryVerificationCoordinator
        verifier = MemoryVerificationCoordinator(self.config, self.db_connection, self.execution)

        result = verifier.verify_memory_item(session_state, category, key, memory_value)

        return result

