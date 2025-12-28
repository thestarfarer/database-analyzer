"""
File Watcher Service

Watches the output directory for session file changes and notifies the WebUI
via WebSocket events for real-time updates.
"""

import logging
from pathlib import Path
from typing import Callable, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent


class SessionFileHandler(FileSystemEventHandler):
    """Handles file system events for session files."""

    def __init__(self, callback: Callable[[str, str], None]):
        """
        Initialize the file handler.

        Args:
            callback: Function to call when session files change (event_type, file_path)
        """
        self.callback = callback
        self.logger = logging.getLogger(__name__)

    def on_created(self, event: FileSystemEvent):
        """Handle file creation events."""
        if not event.is_directory and self._is_session_file(event.src_path):
            self.logger.info(f"Session file created: {event.src_path}")
            self.callback("created", event.src_path)

    def on_modified(self, event: FileSystemEvent):
        """Handle file modification events."""
        if not event.is_directory and self._is_session_file(event.src_path):
            self.logger.info(f"Session file modified: {event.src_path}")
            self.callback("modified", event.src_path)

    def on_deleted(self, event: FileSystemEvent):
        """Handle file deletion events."""
        if not event.is_directory and self._is_session_file(event.src_path):
            self.logger.info(f"Session file deleted: {event.src_path}")
            self.callback("deleted", event.src_path)

    def _is_session_file(self, file_path: str) -> bool:
        """Check if the file is a session JSON file."""
        path = Path(file_path)
        return (path.suffix == '.json' and
                path.name.startswith('session_') and
                not path.name.startswith('session_session_'))  # Exclude old malformed files


class FileWatcher:
    """Watches the output directory for session file changes."""

    def __init__(self, output_dir: Path, change_callback: Callable[[str, str], None]):
        """
        Initialize the file watcher.

        Args:
            output_dir: Directory to watch for file changes
            change_callback: Function to call when files change (event_type, file_path)
        """
        self.output_dir = output_dir
        self.change_callback = change_callback
        self.observer: Optional[Observer] = None
        self.logger = logging.getLogger(__name__)

        # Ensure output directory exists
        self.output_dir.mkdir(exist_ok=True)

    def start(self):
        """Start watching the output directory."""
        if self.observer and self.observer.is_alive():
            self.logger.warning("File watcher is already running")
            return

        self.logger.info(f"Starting file watcher for {self.output_dir}")

        # Create observer and event handler
        self.observer = Observer()
        event_handler = SessionFileHandler(self._handle_file_change)

        # Start watching the output directory
        self.observer.schedule(event_handler, str(self.output_dir), recursive=False)
        self.observer.start()

        self.logger.info("File watcher started successfully")

    def stop(self):
        """Stop watching the output directory."""
        if self.observer and self.observer.is_alive():
            self.logger.info("Stopping file watcher")
            self.observer.stop()
            self.observer.join()
            self.logger.info("File watcher stopped")

    def _handle_file_change(self, event_type: str, file_path: str):
        """
        Handle file change events.

        Args:
            event_type: Type of change (created, modified, deleted)
            file_path: Path to the changed file
        """
        try:
            # Extract session ID from file path
            file_name = Path(file_path).name
            if file_name.startswith('session_') and file_name.endswith('.json'):
                session_id = file_name[8:-5]  # Remove 'session_' prefix and '.json' suffix

                self.logger.debug(f"File {event_type}: {file_name} -> session {session_id}")

                # Call the callback with session info
                self.change_callback(event_type, session_id)

        except Exception as e:
            self.logger.error(f"Error handling file change {file_path}: {e}")

    def is_running(self) -> bool:
        """Check if the file watcher is currently running."""
        return self.observer is not None and self.observer.is_alive()