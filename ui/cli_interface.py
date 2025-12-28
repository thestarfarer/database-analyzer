"""
CLI Interface Module

Handles all command-line user interaction with rich formatting,
task collection, iteration guidance, and report display for the
Database Analyzer system.
"""

from typing import Tuple


class CLIInterface:
    """Handles all CLI user interaction with rich formatting."""

    def __init__(self, session_state):
        """
        Initialize CLIInterface.

        Args:
            session_state: SessionState object for direct memory access
        """
        self.session_state = session_state

    def get_initial_task(self) -> str:
        print("\n" + "="*50)
        print("INITIAL TASK SETUP")
        print("="*50)
        print("Define the main objective for this analysis session.")
        print("Press ENTER to use the default task, or type your custom task.")

        from config.settings import DEFAULT_ANALYSIS_TASK
        default_task = DEFAULT_ANALYSIS_TASK

        print(f"\nDefault task:\n  {default_task}")
        print("-"*50)

        # Simple console input
        try:
            user_input = input("\nEnter your task (or press ENTER for default): ").strip()
            if not user_input:
                return default_task
            return user_input
        except (EOFError, KeyboardInterrupt):
            print("\nUsing default task...")
            return default_task

    def get_user_input(self) -> Tuple[str, bool]:
        """
        Get user input for iteration guidance.

        Returns:
            Tuple of (user_input, should_generate_report)
        """
        # Check if this is a resumed session by looking at iteration history
        is_resumed_session = len(self.session_state.iterations) > 0

        if is_resumed_session:
            last_completed = self.session_state.get_last_completed_iteration()
            if last_completed:
                print(f"\n📝 Last completed: Iteration {last_completed.iteration}")
                if last_completed.user_input:
                    print(f"    Previous task: {last_completed.user_input}")

        print("\n" + "="*50)
        print("USER GUIDANCE")
        print("="*50)
        print("Provide guidance for the next iteration:")
        print("• Enter specific instructions or questions")
        print("• Type 'report' to generate final analysis report")
        print("• Press ENTER to continue with general analysis")
        print("• Press Ctrl+C to exit")
        print("-"*50)

        # Simple console input
        try:
            user_input = input("\nYour guidance: ").strip()

            if user_input.lower() in ['report', 'generate report', 'final report']:
                # Prompt for specific report topic
                print("\n" + "="*50)
                print("REPORT TOPIC")
                print("="*50)
                print("What should the report focus on?")
                print("Examples:")
                print("• 'Q2 data analysis for key entities'")
                print("• 'Metric trends across all records'")
                print("• 'Comparison of different entity categories'")
                print("-"*50)

                try:
                    report_topic = input("\nReport topic: ").strip()
                    if not report_topic:
                        print("Using default topic: General analysis summary")
                        report_topic = "General analysis summary based on current findings"
                    return report_topic, True
                except (EOFError, KeyboardInterrupt):
                    print("\nReport generation cancelled.")
                    return "", False

            return user_input, False

        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            return "EXIT", False

    def display_report(self, content: str, file_path: str) -> None:
        """Display generated report content."""
        print("\n" + "="*50)
        print("GENERATED REPORT")
        print("="*50)
        print(f"Saved to: {file_path}")
        print("-"*50)
        print(content)
        print("="*50)