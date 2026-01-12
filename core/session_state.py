"""
Unified Session State Management

This module provides the complete session state as a single source of truth,
replacing fragmented state management across multiple components.
"""

import time
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
@dataclass
class SessionMetadata:
    """Session metadata container."""
    session_id: str
    start_time: float
    end_time: Optional[float] = None
    current_iteration: int = 0
    last_save_time: float = field(default_factory=time.time)
    pid: Optional[int] = None
    preset_name: Optional[str] = None  # Track which preset this session uses
    llm_backend: Optional[str] = None  # LLM backend used: 'qwen' or 'claude'
    name: Optional[str] = None  # Custom session name for display


@dataclass
class ToolCall:
    """Individual tool call data."""
    id: str
    tool: str
    timestamp: float
    input: Dict[str, Any]
    output: str
    execution_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemLog:
    """System log entry."""
    timestamp: float
    level: str
    message: str


@dataclass
class Iteration:
    """Complete iteration data."""
    iteration: int
    start_time: float
    end_time: Optional[float] = None
    prompt: str = ""
    user_input: Optional[str] = None
    tool_calls: List[ToolCall] = field(default_factory=list)
    llm_response: Optional[str] = None
    system_logs: List[SystemLog] = field(default_factory=list)
@dataclass
class ResumePoint:
    """Information about where to resume a session."""
    iteration: int
    should_restart_iteration: bool
    last_completed_tool_call: Optional[ToolCall]
    context_summary: str


# MemoryStore class removed - memory data now composed from tool calls


class SessionState:
    """
    Complete session state - single source of truth for all session data.

    This replaces fragmented state management across multiple components,
    providing unified iteration tracking and memory composition.
    """

    def __init__(self, session_id: str):
        self.metadata = SessionMetadata(
            session_id=session_id,
            start_time=time.time(),
            pid=None
        )
        self.iterations: List[Iteration] = []

    def get_last_completed_iteration(self) -> Optional[Iteration]:
        """Get the last completed iteration."""
        for iteration in reversed(self.iterations):
            if self.get_iteration_status(iteration) == "completed":
                return iteration
        return None

    def get_iteration_status(self, iteration: 'Iteration') -> str:
        """Get iteration status based on LLM response content."""
        if not iteration.llm_response:
            return "interrupted"
        return "completed"

    def get_completed_iterations_count(self) -> int:
        """Get count of completed iterations."""
        return len([i for i in self.iterations if self.get_iteration_status(i) == "completed"])

    def get_resume_point(self) -> ResumePoint:
        """Determine where to resume the session."""
        # Find last COMPLETED iteration
        last_completed = self.get_last_completed_iteration()

        if not last_completed:
            # No completed iterations, start from iteration 1
            return ResumePoint(
                iteration=1,
                should_restart_iteration=False,
                last_completed_tool_call=None,
                context_summary="Starting new session"
            )

        # Check if there are incomplete iterations after last completed
        incomplete_iterations = [i for i in self.iterations
                               if i.iteration > last_completed.iteration]

        if incomplete_iterations:
            # Remove incomplete iterations and restart from next number after last completed
            self.iterations = [i for i in self.iterations if self.get_iteration_status(i) == "completed"]
            print(f"[DEBUG] Removed {len(incomplete_iterations)} incomplete iteration(s) after iteration {last_completed.iteration}")

        # Always continue from next iteration after last completed, requiring fresh user input
        return ResumePoint(
            iteration=last_completed.iteration + 1,
            should_restart_iteration=False,
            last_completed_tool_call=last_completed.tool_calls[-1] if last_completed.tool_calls else None,
            context_summary=f"Continuing from completed iteration {last_completed.iteration}"
        )

    def add_iteration(self, iteration_num: int, prompt: str, user_input: Optional[str] = None) -> Iteration:
        """Add a new iteration."""
        iteration = Iteration(
            iteration=iteration_num,
            start_time=time.time(),
            prompt=prompt,
            user_input=user_input
        )

        # Update or add iteration
        existing_index = None
        for i, existing_iter in enumerate(self.iterations):
            if existing_iter.iteration == iteration_num:
                existing_index = i
                break

        if existing_index is not None:
            # Preserve important data from existing iteration when updating
            existing_iter = self.iterations[existing_index]
            iteration.tool_calls = existing_iter.tool_calls  # Preserve tool calls
            iteration.llm_response = existing_iter.llm_response  # Preserve LLM response
            iteration.system_logs = existing_iter.system_logs  # Preserve system logs
            if existing_iter.end_time:  # Preserve end time if set
                iteration.end_time = existing_iter.end_time
            if existing_iter.user_input and not user_input:  # Preserve existing user input if not overriding
                iteration.user_input = existing_iter.user_input

            self.iterations[existing_index] = iteration
            print(f"[DEBUG] Updated existing iteration {iteration_num} in session {self.metadata.session_id} (preserved {len(iteration.tool_calls)} tool calls)")
        else:
            self.iterations.append(iteration)
            print(f"[DEBUG] Added new iteration {iteration_num} to session {self.metadata.session_id}, total iterations: {len(self.iterations)}")

        self.metadata.current_iteration = iteration_num
        return iteration

    def complete_iteration(self, iteration_num: int, llm_response: str) -> None:
        """Complete an iteration."""
        for iteration in self.iterations:
            if iteration.iteration == iteration_num:
                iteration.end_time = time.time()
                iteration.llm_response = llm_response

                # Advance current_iteration to prepare for next iteration (if completed successfully)
                if self.get_iteration_status(iteration) == "completed":
                    self.metadata.current_iteration = iteration_num + 1

                break

    def add_tool_call(self, iteration_num: int, tool_call: ToolCall) -> None:
        """Add a tool call to an iteration."""
        for iteration in self.iterations:
            if iteration.iteration == iteration_num:
                iteration.tool_calls.append(tool_call)
                break


    def get_user_commands_history(self) -> str:
        """Get chronological history of completed user commands."""
        user_commands = []

        for iteration in self.iterations:
            if iteration.user_input and iteration.user_input.strip():
                # Only include COMPLETED iterations in history
                # Interrupted/incomplete iterations are excluded from prompts
                status = self.get_iteration_status(iteration)
                if status == "completed":
                    user_commands.append(f"[COMPLETED] Iteration {iteration.iteration}: {iteration.user_input}")

        if not user_commands:
            return ""

        return "\n\nUSER COMMANDS HISTORY:\n" + "\n".join(user_commands) + "\n"

    def get_memory_summary(self) -> str:
        """Get memory summary composed from tool calls."""
        return self._compose_memory_from_tool_calls()

    def _compose_memory_from_tool_calls(self) -> str:
        """Compose memory summary from memory tool calls in iterations with temporal markers."""
        memory_data = self.get_memory_data_from_tool_calls()

        if not memory_data:
            return "No memory stored yet."

        # Add temporal context header to prevent confusion about which iteration's work this is
        header = """

ACCUMULATED MEMORY FROM COMPLETED ITERATIONS:
(This information was discovered in previous iterations. Use it as context, but DO NOT repeat these analyses.)
"""

        summary_parts = [header]
        for category in ['insights', 'patterns', 'explored_areas', 'key_findings',
                        'opportunities', 'data_issues', 'metrics', 'context',
                        'data_milestones', 'user_requests']:
            items = memory_data.get(category, [])
            if items:
                formatted_category = category.replace('_', ' ').title()
                summary_parts.append(f"\n{formatted_category}:")
                for item in items:
                    summary_parts.append(f"• {item}")

        return '\n'.join(summary_parts) if len(summary_parts) > 1 else "No memory stored yet."

    def get_memory_data_from_tool_calls(self) -> Dict[str, List[str]]:
        """Extract current memory state from tool call history."""
        memory_data = {}

        # Process all memory tool calls in chronological order
        for iteration in self.iterations:
            for tool_call in iteration.tool_calls:
                if tool_call.tool == 'memory':
                    input_data = tool_call.input
                    action = input_data.get('action')
                    category = input_data.get('key')
                    value = input_data.get('value')

                    if action == 'update' and category and value:
                        if category not in memory_data:
                            memory_data[category] = []
                        memory_data[category].append(value)
                    elif action == 'remove' and category and value:
                        if category in memory_data and value in memory_data[category]:
                            memory_data[category].remove(value)

        return memory_data

    def get_memory_data_with_metadata(self) -> Dict[str, Any]:
        """
        Extract memory state with metadata (iteration, timestamp) for WebUI display.

        Returns:
            Dict with memory data including metadata for each item
        """
        memory_data = {}
        last_updated = None

        # Process all memory tool calls in chronological order
        for iteration in self.iterations:
            for tool_call in iteration.tool_calls:
                if tool_call.tool == 'memory':
                    input_data = tool_call.input
                    action = input_data.get('action')
                    category = input_data.get('key')
                    value = input_data.get('value')
                    timestamp = tool_call.timestamp

                    if action == 'update' and category and value:
                        if category not in memory_data:
                            memory_data[category] = []
                        memory_data[category].append({
                            'content': value,
                            'iteration': iteration.iteration,
                            'timestamp': timestamp or ''
                        })
                        last_updated = timestamp
                    elif action == 'remove' and category and value:
                        if category in memory_data:
                            memory_data[category] = [item for item in memory_data[category]
                                                   if item['content'] != value]

        return {
            'memory_data': memory_data,
            'last_updated': last_updated
        }

    def update_memory_value(self, category: str, key: str, new_value: str) -> bool:
        """
        Update a specific memory value in tool call history.

        Args:
            category: Memory category
            key: Memory key
            new_value: New value for the memory item

        Returns:
            True if update successful, False otherwise
        """
        for iteration in reversed(self.iterations):
            for tool_call in reversed(iteration.tool_calls):
                if tool_call.tool == 'memory':
                    input_data = tool_call.input
                    if (input_data.get('action') == 'update' and
                        input_data.get('key') == category and
                        input_data.get('value', '').startswith(f"{key}:")):

                        old_content = input_data['value'].split(':', 1)[1]
                        input_data['value'] = f"{key}:{new_value}"

                        tool_call.metadata['verified'] = True
                        tool_call.metadata['verified_at'] = time.time()
                        tool_call.metadata['old_value'] = old_content

                        return True

        return False

    def finalize_session(self) -> None:
        """Finalize the session by ensuring incomplete iterations have interrupted messages."""
        self.metadata.end_time = time.time()

        # Clear PID to mark session as gracefully completed
        self.metadata.pid = None

        # Set end times for incomplete iterations
        for iteration in self.iterations:
            if not iteration.end_time:
                iteration.end_time = self.metadata.end_time

    def to_dict(self) -> Dict[str, Any]:
        """Convert complete session state to dictionary for serialization."""
        print(f"[DEBUG] Serializing session {self.metadata.session_id}: {len(self.iterations)} iterations in memory")

        serialized_iterations = []
        for iter in self.iterations:
            serialized_iterations.append({
                "iteration": iter.iteration,
                "start_time": iter.start_time,
                "end_time": iter.end_time,
                "prompt": iter.prompt,
                "user_input": iter.user_input,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "tool": tc.tool,
                        "timestamp": tc.timestamp,
                        "input": tc.input,
                        "output": tc.output,
                        "execution_time": tc.execution_time,
                        "metadata": tc.metadata
                    } for tc in iter.tool_calls
                ],
                "llm_response": iter.llm_response,
                "system_logs": [
                    {
                        "timestamp": log.timestamp,
                        "level": log.level,
                        "message": log.message
                    } for log in iter.system_logs
                ]
            })

        print(f"[DEBUG] Serialized {len(serialized_iterations)} iterations for session {self.metadata.session_id}")

        return {
            "session_metadata": {
                "session_id": self.metadata.session_id,
                "start_time": self.metadata.start_time,
                "end_time": self.metadata.end_time,
                "current_iteration": self.metadata.current_iteration,
                "last_save_time": self.metadata.last_save_time,
                "pid": self.metadata.pid,
                "preset_name": self.metadata.preset_name,
                "llm_backend": self.metadata.llm_backend,
                "name": self.metadata.name
            },
            "iterations": serialized_iterations,
            "export_timestamp": datetime.now().isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionState':
        """Create SessionState from dictionary."""
        metadata_dict = data.get("session_metadata", {})

        session_state = cls(
            session_id=metadata_dict.get("session_id", "")
        )

        # Restore metadata
        session_state.metadata.start_time = metadata_dict.get("start_time", time.time())
        session_state.metadata.end_time = metadata_dict.get("end_time")
        session_state.metadata.current_iteration = metadata_dict.get("current_iteration", 0)
        session_state.metadata.last_save_time = metadata_dict.get("last_save_time", time.time())
        session_state.metadata.preset_name = metadata_dict.get("preset_name")
        session_state.metadata.pid = metadata_dict.get("pid")
        session_state.metadata.llm_backend = metadata_dict.get("llm_backend")
        session_state.metadata.name = metadata_dict.get("name")

        # Memory data composed from tool calls history

        # Restore iterations
        for iter_data in data.get("iterations", []):
            iteration = Iteration(
                iteration=iter_data["iteration"],
                start_time=iter_data["start_time"],
                end_time=iter_data.get("end_time"),
                prompt=iter_data.get("prompt", ""),
                user_input=iter_data.get("user_input"),
                llm_response=iter_data.get("llm_response")
            )

            # Restore tool calls
            for tc_data in iter_data.get("tool_calls", []):
                tool_call = ToolCall(
                    id=tc_data["id"],
                    tool=tc_data["tool"],
                    timestamp=tc_data["timestamp"],
                    input=tc_data["input"],
                    output=tc_data["output"],
                    execution_time=tc_data["execution_time"],
                    metadata=tc_data.get("metadata", {})
                )
                iteration.tool_calls.append(tool_call)

            # Restore system logs
            for log_data in iter_data.get("system_logs", []):
                log = SystemLog(
                    timestamp=log_data["timestamp"],
                    level=log_data["level"],
                    message=log_data["message"]
                )
                iteration.system_logs.append(log)

            session_state.iterations.append(iteration)

        return session_state