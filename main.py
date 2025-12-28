"""
Database Analyzer - Main CLI Entry Point

This is the primary command-line interface for the Database Analyzer system.
It handles session creation, resumption, and coordination between the LLM,
database tools, and user interaction.

Key Features:
- Session lifecycle management (create, resume, list)
- Database query execution with LLM analysis
- Tool integration (SQL, memory)
- Live session persistence and recovery
- Comprehensive error handling and user feedback

Usage Examples:
    python main.py --task "Explore the database"
    python main.py --continue-session output/session_20250920_182840.json
    python main.py --latest --task "Focus on specific patterns"
    python main.py --list-sessions
"""

import sys
import signal
import json
from pathlib import Path
import argparse

from config.settings import AppConfig, DatabaseConfig, LLMConfig
from database.connection import MSSQLConnection
from core.session_manager import SessionManager

# Global reference for graceful shutdown
session_manager_instance = None


def graceful_shutdown(signum, frame):
    """
    Handle SIGTERM and SIGINT for graceful session termination.

    This function converts SIGTERM to KeyboardInterrupt to ensure it can
    interrupt blocking I/O operations like LLM calls, making SIGTERM behave
    exactly like Ctrl+C.
    """
    signal_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
    print(f"\n🛑 Received {signal_name}, shutting down gracefully...")

    # Raise KeyboardInterrupt to interrupt blocking I/O operations
    # This will be caught by existing KeyboardInterrupt handlers
    raise KeyboardInterrupt()


def run_verification_mode(session_id: str, category: str, key: str, config: AppConfig, db_connection: MSSQLConnection):
    """Run memory verification for a specific memory item."""

    quiet_mode = not config.verbose_console_output
    session_file = config.output_dir / f"session_{session_id}.json"

    if not session_file.exists():
        if quiet_mode:
            print(json.dumps({"error": f"Session not found: {session_id}"}))
        else:
            print(f"❌ Session not found: {session_id}")
            print(f"   Tried: {session_file}")
        return

    # Read session metadata to get preset name before creating SessionManager
    with open(session_file, 'r', encoding='utf-8') as f:
        session_data = json.load(f)
    preset_name = session_data.get('session_metadata', {}).get('preset_name')
    if preset_name:
        config.prompt_preset_name = preset_name

    if not quiet_mode:
        print(f"\n{'='*60}")
        print(f"🔍 MEMORY VERIFICATION MODE")
        print(f"{'='*60}")
        print(f"Session: {session_id}")
        print(f"Memory: {category}:{key}")
        if preset_name:
            print(f"Preset: {preset_name}")
        print(f"{'='*60}\n")

    session_manager = SessionManager(config, db_connection)
    session_state = session_manager.persistence.load_session(session_file)

    if session_state.metadata.pid:
        import psutil
        if psutil.pid_exists(session_state.metadata.pid):
            if quiet_mode:
                print(json.dumps({"error": f"Session is still running (PID {session_state.metadata.pid})"}))
            else:
                print(f"⚠️  Session is still running (PID {session_state.metadata.pid})")
                print("   Stop the session before verifying memory")
            return

    try:
        result = session_manager.verify_memory_item(session_state, category, key)

        if quiet_mode:
            # JSON output for WebUI
            print(json.dumps(result))
        else:
            # Human-readable output for CLI
            display_verification_result(result, category, key)

            if result['recommendation'] == 'update' and result.get('updated_value'):
                response = input("\n🔄 Apply recommended update? (y/n): ").strip().lower()
                if response == 'y':
                    success = session_state.update_memory_value(category, key, result['updated_value'])
                    if success:
                        # Save the modified session state back to file
                        session_manager.persistence.save_session(session_state)
                        print("✅ Memory updated successfully")
                    else:
                        print("❌ Failed to update memory")
                else:
                    print("❌ Update cancelled")
            elif result['recommendation'] == 'remove':
                print("\n💡 Recommendation: Remove this memory item")
                print("   (Manual removal not yet implemented)")
            else:
                print("✅ Memory verification complete - no changes needed")

    except Exception as e:
        if quiet_mode:
            print(json.dumps({"error": str(e)}))
        else:
            print(f"❌ Verification failed: {e}")
            import traceback
            traceback.print_exc()


def display_verification_result(result: dict, category: str, key: str):
    """Display verification result with formatting."""

    confidence_icons = {
        'high': '🟢',
        'medium': '🟡',
        'low': '🔴'
    }

    print(f"\n{'='*60}")
    print(f"📊 VERIFICATION RESULT")
    print(f"{'='*60}")
    print(f"Verified: {'✅ Yes' if result.get('verified') else '❌ No'}")
    print(f"Confidence: {confidence_icons.get(result.get('confidence'), '⚪')} {result.get('confidence', 'unknown').upper()}")
    print(f"Recommendation: {result.get('recommendation', 'unknown').upper()}")
    print(f"\n💭 Reasoning:\n{result.get('reasoning', 'No reasoning provided')}")
    print(f"\n🔍 Evidence:\n{result.get('evidence', 'No evidence provided')}")

    if result.get('updated_value'):
        print(f"\n📝 Recommended Update:")
        print(f"Category: {category}")
        print(f"Key: {key}")
        print(f"New Value: {result['updated_value']}")

    print(f"{'='*60}")


def main():
    """
    Main entry point for Database Analyzer CLI.

    Handles argument parsing, configuration setup, and session coordination.
    Supports both new session creation and resumption of existing sessions.
    """
    parser = argparse.ArgumentParser(description='Database Analyzer - Database Analysis Tool')

    # Session control arguments
    parser.add_argument('--continue-session', help='Continue from existing session file')
    parser.add_argument('--task', help='Initial task description for new sessions OR guidance for resumed sessions')
    parser.add_argument('--latest', action='store_true', help='Continue from the latest session')
    parser.add_argument('--list-sessions', action='store_true', help='List available sessions and exit')

    # Configuration arguments
    parser.add_argument('--output-dir', default='output', help='Output directory for session files')
    parser.add_argument('--max-iterations', type=int, default=100, help='Maximum analysis iterations per session')
    parser.add_argument('--log-level', default='INFO', help='Log level (DEBUG, INFO, WARNING, ERROR)')
    parser.add_argument('--db-result-limit', type=int, default=100, help='Maximum database rows returned to LLM (default: 100)')
    parser.add_argument('--prompt-preset', help='Prompt preset name or path to load (default: default)')

    # Memory verification arguments
    parser.add_argument('--verify-memory', nargs=2, metavar=('SESSION_ID', 'MEMORY_SPEC'),
                        help='Verify memory item: session_id category:key')

    # Output control arguments
    parser.add_argument('--verbose', action='store_true', default=True, help='Enable verbose console output (default: True)')
    parser.add_argument('--quiet', action='store_true', help='Disable verbose console output')

    # LLM backend selection
    parser.add_argument('--llm-backend', choices=['qwen', 'claude'], default=None,
                        help='LLM backend to use (default: qwen)')

    args = parser.parse_args()

    # Create application configuration with environment overrides
    verbose_output = args.verbose and not args.quiet

    # Determine LLM backend (CLI arg overrides environment)
    import os
    llm_backend = args.llm_backend or os.getenv('LLM_BACKEND', 'qwen')

    config = AppConfig(
        db_config=DatabaseConfig.from_env(),  # Uses DB_* environment variables
        llm_config=LLMConfig.default(),       # Qwen model configuration
        output_dir=Path(args.output_dir),
        max_iterations=args.max_iterations,
        log_level=args.log_level,
        verbose_console_output=verbose_output,
        db_result_limit=args.db_result_limit,
        prompt_preset_name=args.prompt_preset,
        llm_backend=llm_backend
    )

    # Validate Claude backend requirements
    if config.llm_backend == 'claude':
        if not config.claude_config.api_key:
            print("❌ Error: ANTHROPIC_API_KEY environment variable is required for Claude backend")
            sys.exit(1)
        if verbose_output:
            print(f"🤖 Using Claude backend (model: {config.claude_config.model})")

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, graceful_shutdown)
    signal.signal(signal.SIGINT, graceful_shutdown)

    try:
        # Initialize database connection
        db_connection = MSSQLConnection(config.db_config, verbose=config.verbose_console_output, result_limit=config.db_result_limit)

        # Handle verification mode
        if args.verify_memory:
            session_id, memory_spec = args.verify_memory
            if ':' not in memory_spec:
                print(f"❌ Invalid memory spec format. Use: category:key")
                sys.exit(1)
            category, key = memory_spec.split(':', 1)
            run_verification_mode(session_id, category, key, config, db_connection)
            return

        # Initialize session manager and store global reference
        global session_manager_instance
        session_manager = SessionManager(config, db_connection)
        session_manager_instance = session_manager

        # Handle special commands that don't require full session execution
        if args.list_sessions:
            sessions = session_manager.list_available_sessions()
            if not sessions:
                print("No sessions found.")
                return

            print("\nAvailable Sessions:")
            print("=" * 80)
            for session in sessions:
                if "error" in session:
                    print(f"❌ {session['file_name']}: {session['error']}")
                else:
                    print(f"📁 {session['session_id']}")
                    # Get first iteration user input for display
                    first_user_input = session.get('first_user_input', '')
                    if first_user_input:
                        print(f"   📋 Task: {first_user_input}")
                    print(f"   🔄 Iterations: {session.get('iteration_count', 0)}")
                    print(f"   📅 Modified: {Path(session['file_path']).stat().st_mtime}")
                    print()
            return

        # Determine session file for continuation
        session_file = None
        if args.continue_session:
            # Explicit session file provided
            session_file = Path(args.continue_session)
            if not session_file.exists():
                print(f"❌ Session file not found: {session_file}")
                sys.exit(1)
        elif args.latest:
            # Find most recently modified session file
            session_file = session_manager.find_latest_session()
            if not session_file:
                print("❌ No sessions found to continue from")
                sys.exit(1)

        # Start or continue session with optional task guidance
        session_state = session_manager.start_session(
            session_file=session_file,
            first_user_input=args.task or ""  # Used as first input for new sessions OR user input for resumed sessions
        )

        # Run the main session execution loop
        session_manager.run_session()

    except KeyboardInterrupt:
        # This should now be handled by the signal handler, but keep as fallback
        print("\n👋 Exiting...")
        if session_manager_instance and session_manager_instance.current_session:
            session_manager_instance.finalize_current_session()
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()