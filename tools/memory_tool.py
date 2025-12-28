"""
Memory Tool - Insight Storage and Retrieval System

This tool enables the LLM to store, retrieve, and manage analysis insights
across session iterations. It provides persistent memory for accumulating
findings, patterns, and discoveries.

Key Features:
- Categorized storage (insights, patterns, key_findings, etc.)
- Key:value format for structured insight management
- CRUD operations (update, remove, get) with validation
- Integration with session persistence system
- Context preservation across iterations

Categories:
- insights: General insights discovered
- patterns: Data patterns and trends identified
- explored_areas: What has already been analyzed
- key_findings: Important discoveries and conclusions
- opportunities: Specific improvement recommendations
- data_milestones: Important data milestones and temporal markers
- data_issues: Data quality or consistency problems
- metrics: Key metrics and calculations
- context: Domain context and understanding
- user_requests: Specific requests from user input

Usage Pattern:
- memory(action='update', key='insights', value='trend_q2:Q2 shows 15% increase')
- memory(action='get', key='insights')
- memory(action='remove', key='insights', value='outdated_analysis')
"""

from qwen_agent.tools.base import BaseTool
import json
import time
from datetime import datetime


class MemoryTool(BaseTool):
    name = "memory"
    description = """Access and update persistent memory across iterations.
    Use this to store insights, findings, patterns, and context from analysis.
    Actions (choose one): 'update' - add new information, 'remove' - delete memory entries.
    Update format: memory(action='update', key='category', value='memory_key:content')
    Remove format: memory(action='remove', key='category', value='memory_key')
    Choose meaningful memory_key identifiers for easy reference and deletion."""
    parameters = [
        {'action': 'Action to perform: update, or remove'},
        {'key': 'Memory category/key (required for update/remove)'},
        {'value': 'For update: memory_key:content. For remove: memory_key only'}
    ]

    def __init__(self, session_state, verbose: bool = True):
        """
        Initialize MemoryTool with session state.

        Args:
            session_state: SessionState object for direct memory access
            verbose: Whether to print verbose output
        """
        self.session_state = session_state
        self.verbose = verbose

    def call(self, action: str = None, key: str = None, value: str = None, **kwargs) -> str:
        # Handle parameters
        if action is None:
            action = kwargs.get('action', 'get')
        if key is None:
            key = kwargs.get('key')
        if value is None:
            value = kwargs.get('value')

        # Handle JSON-encoded parameters
        if isinstance(action, str) and action.startswith('{'):
            try:
                params = json.loads(action)
                action = params.get('action', 'get')
                key = params.get('key')
                value = params.get('value')
            except json.JSONDecodeError:
                pass

        try:
            if action == 'get':
                if key is None:
                    result = self.session_state.get_memory_summary()
                else:
                    memory_data = self.session_state.get_memory_data_from_tool_calls()
                    category_items = memory_data.get(key, [])
                    if category_items:
                        result = f"{key.upper()}:\n" + "\n".join(f"• {item}" for item in category_items)
                    else:
                        result = f"No memory found for key: {key}"
                return result
            elif action == 'update':
                if not key or not value:
                    return "Error: Both key and value are required for update"

                # Memory operations are now handled automatically through the session tool call system
                # This tool call itself will be logged and stored as memory data
                if self.verbose:
                    self._log_memory_operation_start('update', key, value)

                # Parse key:value format
                if ':' in value:
                    memory_key, content = value.split(':', 1)
                    memory_key = memory_key.strip()
                    content = content.strip()
                else:
                    memory_key = f"item_{int(time.time())}"
                    content = value

                result = f"Updated {key}: {memory_key}"

                if self.verbose:
                    new_state = self._get_memory_state_snapshot(key)
                    self._log_memory_operation_end('update', result, new_state)

                return result
            elif action == 'remove':
                if not key or not value:
                    return "Error: Both key and value are required for remove"

                # Memory operations are now handled automatically through the session tool call system
                if self.verbose:
                    self._log_memory_operation_start('remove', key, value)

                result = f"Removed from {key}: {value}"

                if self.verbose:
                    new_state = self._get_memory_state_snapshot(key)
                    self._log_memory_operation_end('remove', result, new_state)

                return result
            else:
                return f"Unknown action: {action}. Use 'get', 'update', or 'remove'"
        except Exception as e:
            if self.verbose:
                self._log_memory_operation_error(action, key, value, str(e))
            return f"Memory operation failed: {e}"

    def _log_memory_operation_start(self, action: str, key: str, value: str):
        """Log memory operation start."""
        print("\n" + "="*60)
        print(f"🧠 MEMORY {action.upper()} OPERATION - {datetime.now().strftime('%H:%M:%S')}")
        print("="*60)
        print(f"📂 Category: {key}")
        if value:
            print(f"📝 Value: {value}")
        print("-" * 60)

    def _log_memory_operation_end(self, action: str, result: str, new_state=None):
        """Log memory operation end with state changes."""
        print(f"✅ Operation Result: {result}")
        print("="*60 + "\n")

    def _log_memory_operation_error(self, action: str, key: str, value: str, error: str):
        """Log memory operation error."""
        print("\n" + "="*60)
        print(f"❌ MEMORY {action.upper()} OPERATION FAILED - {datetime.now().strftime('%H:%M:%S')}")
        print("="*60)
        print(f"📂 Category: {key}")
        if value:
            print(f"📝 Value: {value}")
        print(f"🚨 Error: {error}")
        print("="*60 + "\n")

    def _get_memory_state_snapshot(self, key: str) -> str:
        """Get a snapshot of memory state for a specific key."""
        try:
            memory_data = self.session_state.get_memory_data_from_tool_calls()
            category_items = memory_data.get(key, [])
            if category_items:
                memory_content = f"{key.upper()}:\n" + "\n".join(f"• {item}" for item in category_items)
                # Truncate long content for readability
                if len(memory_content) > 200:
                    return memory_content[:200] + "..."
                return memory_content
            return "No data"
        except Exception:
            return "No data"