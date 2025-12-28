"""
Unified Session Persistence

This module handles all session save/load operations, replacing the fragmented
file handling across MemoryService and UnifiedSessionLogger.
"""

import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from enum import Enum
import logging

from .session_state import SessionState


class FileType(Enum):
    """File type enumeration."""
    SESSION = "session"
    UNKNOWN = "unknown"


class SessionPersistence:
    """
    Unified session persistence replacing fragmented file handling.

    This replaces:
    - UnifiedSessionLogger._save_session_data()
    - MemoryService.save_to_file()
    - MemoryService.load_from_file()
    """

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)
        self.logger = logging.getLogger(__name__)

    def save_session(self, session_state: SessionState) -> Path:
        """
        Save complete session state to file.

        Args:
            session_state: Complete session state to save

        Returns:
            Path to saved session file
        """
        session_file = self.output_dir / f'session_{session_state.metadata.session_id}.json'

        try:
            # Update save timestamp
            session_state.metadata.last_save_time = time.time()

            # Convert to dictionary
            session_data = session_state.to_dict()

            # Write to file with proper encoding
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)

            self.logger.info(f"Session saved to {session_file}")

            return session_file

        except Exception as e:
            error_msg = f"Failed to save session: {e}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def load_session(self, session_file: Path) -> SessionState:
        """
        Load complete session state from file.

        Args:
            session_file: Path to session file

        Returns:
            Complete SessionState object

        Raises:
            FileNotFoundError: If session file doesn't exist
            RuntimeError: If file is corrupted or incompatible
        """
        if not session_file.exists():
            raise FileNotFoundError(f"Session file not found: {session_file}")

        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)

            # Detect file type and handle accordingly
            file_type = self._detect_file_type(session_data)

            if file_type == FileType.SESSION:
                session_state = SessionState.from_dict(session_data)
                self.logger.info(f"Loaded session {session_state.metadata.session_id} from {session_file}")
                return session_state
            else:
                raise RuntimeError(f"Unknown file format: {session_file}")

        except json.JSONDecodeError as e:
            raise RuntimeError(f"Corrupted session file: {session_file}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to load session: {e}") from e

    def _detect_file_type(self, data: Dict[str, Any]) -> FileType:
        """Internal method to detect file type from data structure."""
        # New unified session format
        if "session_metadata" in data and "iterations" in data:
            return FileType.SESSION

        return FileType.UNKNOWN


    def list_session_files(self) -> List[Path]:
        """
        List all session files in output directory.

        Returns:
            List of session file paths sorted by modification time (newest first)
        """
        session_files = list(self.output_dir.glob('session_*.json'))
        return sorted(session_files, key=lambda f: f.stat().st_mtime, reverse=True)

    def find_latest_session(self) -> Optional[Path]:
        """
        Find the most recently modified session file.

        Returns:
            Path to latest session file, or None if no sessions found
        """
        session_files = self.list_session_files()
        return session_files[0] if session_files else None

    def get_session_summary(self, session_file: Path) -> Dict[str, Any]:
        """
        Get session summary without loading full state.

        Args:
            session_file: Path to session file

        Returns:
            Dictionary with session summary info
        """
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            metadata = data.get("session_metadata", {})
            iterations = data.get("iterations", [])

            return {
                "session_id": metadata.get("session_id", "unknown"),
                "status": metadata.get("status", "unknown"),
                # Get first iteration user input for display
                "first_user_input": (iterations[0].get("user_input", "")[:100] + "..." if len(iterations[0].get("user_input", "")) > 100 else iterations[0].get("user_input", "")) if iterations else "",
                "start_time": metadata.get("start_time"),
                "end_time": metadata.get("end_time"),
                "iteration_count": len(iterations),
                "last_iteration": iterations[-1].get("iteration", 0) if iterations else 0,
                "last_iteration_status": iterations[-1].get("status", "unknown") if iterations else "none",
                "file_size": session_file.stat().st_size,
                "modified_time": session_file.stat().st_mtime
            }
        except Exception as e:
            return {
                "session_id": "error",
                "status": "error",
                "error": str(e),
                "file_size": session_file.stat().st_size if session_file.exists() else 0,
                "modified_time": session_file.stat().st_mtime if session_file.exists() else 0
            }