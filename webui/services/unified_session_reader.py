import json
import re
import psutil
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple


class UnifiedSessionReader:
    """Service for reading and parsing unified session data files."""

    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path('output')

    def set_output_dir(self, output_dir: Path):
        """Set the output directory for session files."""
        self.output_dir = output_dir

    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """Get all sessions with metadata."""
        sessions = []

        # Find all unified session files
        session_files = self._find_unified_session_files()

        for session_file in session_files:
            session_data = self._load_session_metadata(session_file)
            if session_data:
                sessions.append(session_data)

        # Sort by start time (newest first)
        sessions.sort(key=lambda x: x.get('start_time', 0), reverse=True)
        return sessions

    def get_session_detail(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed session data including iterations."""
        session_file = self.output_dir / f'session_{session_id}.json'

        if not session_file.exists():
            return None

        session_data = self._load_json_file(session_file)
        if not session_data:
            return None

        # Extract and format session details
        return self._format_session_detail(session_data)

    def get_iteration_detail(self, session_id: str, iteration: int) -> Optional[Dict[str, Any]]:
        """Get detailed iteration data with tool calls."""
        session_data = self.get_session_detail(session_id)
        if not session_data:
            return None

        # Find the specific iteration
        iterations = session_data.get('iterations', [])
        for iter_data in iterations:
            if iter_data.get('iteration') == iteration:
                return iter_data

        return None

    def _find_unified_session_files(self) -> List[Path]:
        """Find all unified session files."""
        session_files = []

        if not self.output_dir.exists():
            return session_files

        # Pattern for unified session files
        pattern = r'session_(\d{8}_\d{6})\.json'

        for file_path in self.output_dir.iterdir():
            if file_path.is_file() and re.match(pattern, file_path.name):
                session_files.append(file_path)

        return session_files

    def _load_session_metadata(self, session_file: Path) -> Optional[Dict[str, Any]]:
        """Load basic session metadata from unified session file."""
        session_data = self._load_json_file(session_file)
        if not session_data:
            return None

        # Extract metadata from unified structure
        metadata = session_data.get('session_metadata', {})
        iterations = session_data.get('iterations', [])

        # Use only data directly from session file - no derived calculations
        iterations_count = len(iterations)

        # Calculate queries and memory items from tool calls
        queries_count = 0
        memory_items = 0

        for iteration in iterations:
            for tool_call in iteration.get('tool_calls', []):
                tool_name = tool_call.get('tool', '')
                if tool_name == 'execute_sql':
                    queries_count += 1
                elif tool_name == 'memory':
                    # Count memory operations that modify memory (update/remove), not reads (get)
                    input_data = tool_call.get('input', {})
                    action = input_data.get('action')
                    if action in ('update', 'remove'):
                        memory_items += 1

        # Get latest user input from iterations
        latest_user_input = self._get_latest_user_input(iterations)
        display_task = latest_user_input

        # Derive session status using enhanced PID lifecycle logic
        actual_status = self._compute_session_status(metadata, iterations)

        session_summary = {
            'session_id': metadata.get('session_id'),
            'name': metadata.get('name'),  # Custom session name for display
            'start_time': metadata.get('start_time', 0),
            'end_time': metadata.get('end_time'),
            'status': actual_status,
            'latest_user_input': display_task,
            'iterations_count': iterations_count,
            'current_iteration': metadata.get('current_iteration', 0),
            'queries_count': queries_count,
            'memory_items': memory_items,
            'session_file': str(session_file),
            'pid': metadata.get('pid'),
            'llm_backend': metadata.get('llm_backend')
        }

        return session_summary

    def _format_session_detail(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format session data for detailed view."""
        metadata = session_data.get('session_metadata', {})
        iterations = session_data.get('iterations', [])

        # Format iterations with enhanced PID lifecycle logic
        formatted_iterations = []
        session_pid = metadata.get('pid')

        for i, iteration in enumerate(iterations):
            tool_calls = iteration.get('tool_calls', [])

            # Derive iteration status: all completed except last one
            if i < len(iterations) - 1:
                # All iterations except the last are completed
                iteration_status = 'completed'
            else:
                # Last iteration uses same logic as session status
                iteration_status = self._compute_session_status(metadata, [iteration])

            # Extract thinking content from LLM response
            raw_llm_response = iteration.get('llm_response') or ''
            main_response, thinking_content = self._extract_thinking_tags(raw_llm_response)

            formatted_iteration = {
                'iteration': iteration.get('iteration'),
                'status': iteration_status,
                'start_time': iteration.get('start_time'),
                'end_time': iteration.get('end_time'),
                'prompt': iteration.get('prompt', ''),
                'user_input': iteration.get('user_input'),
                'llm_response': main_response,  # Cleaned response without thinking tags
                'llm_thinking': thinking_content,  # Extracted thinking content
                'llm_response_raw': raw_llm_response,  # Keep raw response for debugging
                'system_logs': iteration.get('system_logs', []),
                'tool_calls': tool_calls
            }
            formatted_iterations.append(formatted_iteration)

        # Add computed session status using same logic as _load_session_metadata
        session_status = self._compute_session_status(metadata, iterations)

        # Add computed status to metadata
        enhanced_metadata = dict(metadata)
        enhanced_metadata['status'] = session_status

        # Return only raw session data - no formatting or derived statistics
        return {
            'session_metadata': enhanced_metadata,
            'iterations': formatted_iterations
        }

    def _compute_session_status(self, metadata: Dict[str, Any], iterations: List[Dict[str, Any]]) -> str:
        """Compute session status using enhanced PID lifecycle logic."""
        session_pid = metadata.get('pid')

        # Check if process is still running (with exception handling for zombie/permission issues)
        process_exists = False
        if session_pid:
            try:
                process_exists = psutil.pid_exists(session_pid)
            except (psutil.ZombieProcess, psutil.AccessDenied, psutil.NoSuchProcess):
                # Zombie process, access denied, or no such process → treat as dead
                process_exists = False

        if session_pid and process_exists:
            # Has PID and process exists → check if awaiting input or running
            if iterations:
                last_iteration = iterations[-1]
                if last_iteration.get('llm_response'):
                    # Last iteration completed with LLM response → awaiting input
                    return 'awaiting_input'
                else:
                    # Last iteration incomplete → running
                    return 'running'
            else:
                # No iterations yet → running
                return 'running'
        elif session_pid is None:
            # No PID → check if last iteration truly completed
            if iterations:
                last_iteration = iterations[-1]
                if last_iteration.get('llm_response'):
                    # Gracefully completed with LLM response → completed
                    return 'completed'
                else:
                    # Gracefully exited but incomplete iteration → interrupted
                    return 'interrupted'
            else:
                # No iterations at all → completed (edge case)
                return 'completed'
        else:
            # Has PID but process dead → interrupted
            return 'interrupted'

    def _get_latest_user_input(self, iterations: List[Dict[str, Any]]) -> str:
        """Get the latest user input from iterations, falling back to empty string."""
        # Find the latest iteration with user input (iterate in reverse chronological order)
        for iteration in reversed(iterations):
            user_input = iteration.get('user_input')
            if user_input and user_input.strip():
                return user_input.strip()
        return ""

    def _extract_thinking_tags(self, text: str) -> Tuple[str, str]:
        """Extract thinking content from text and return (main_content, thinking_content)."""
        if not text:
            return "", ""

        # Pattern to match <think>...</think> tags (including nested content)
        think_pattern = r'<think>(.*?)</think>'

        # Find all thinking sections
        thinking_sections = re.findall(think_pattern, text, re.DOTALL)

        # Remove thinking tags from main content
        main_content = re.sub(think_pattern, '', text, flags=re.DOTALL).strip()

        # Join all thinking sections with separators if multiple exist
        thinking_content = '\n\n'.join(thinking_sections).strip() if thinking_sections else ""

        return main_content, thinking_content


    # Removed derived statistics methods - WebUI now displays only raw session data

    def _load_json_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Load JSON file safely."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, Exception):
            return None