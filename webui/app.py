"""
Database Analyzer WebUI - Flask Application

This module provides the web interface for the Database Analyzer system.
It offers read-only access to session data with real-time monitoring
capabilities and session management features.

Key Features:
- Real-time session monitoring via SocketIO and file watching
- Session management (create, resume, stop, delete)
- Memory composition and visualization
- Multi-language support (i18n)
- Live status updates using PID lifecycle system

Architecture:
- Flask app with SocketIO for real-time communication
- FileWatcher monitors output directory for session changes
- UnifiedSessionReader provides read-only access to session data
- Independent process spawning for session creation/management

API Endpoints:
- GET /api/sessions - List all sessions with metadata
- GET /api/sessions/{id} - Detailed session data
- GET /api/sessions/{id}/memory - Memory composition from tool calls
- POST /api/sessions/new - Create new session via subprocess
- POST /api/sessions/{id}/resume - Resume session with optional guidance
- POST /api/sessions/{id}/stop - Gracefully terminate running session
- DELETE /api/sessions/{id} - Delete session file

Read-Only Philosophy:
The WebUI never modifies session data directly. All modifications
go through the main application via subprocess spawning to maintain
data integrity and separation of concerns.
"""

from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_socketio import SocketIO, emit
import os
import sys
import json
import logging
import subprocess
import signal
import psutil
from datetime import datetime
from pathlib import Path
import threading
import time

from .services.unified_session_reader import UnifiedSessionReader
from .services.file_watcher import FileWatcher

app = Flask(__name__)
app.config['SECRET_KEY'] = 'database_analyzer_webui_secret'
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024  # 1MB limit for request body
socketio = SocketIO(app, cors_allowed_origins="*")

# Global instances
unified_session_reader = UnifiedSessionReader()
file_watcher = None
_preset_manager = None  # Lazy-loaded singleton for preset operations
_prompts_dir = Path('prompts')  # Default prompts directory, can be overridden for testing


def _spawn_detached_process(cmd, cwd):
    """Spawn a detached subprocess independent from WebUI.

    Used for session creation and resume - fire-and-forget processes.
    """
    return subprocess.Popen(
        cmd,
        cwd=cwd,
        env=os.environ,  # Pass environment variables (DB_*, etc.)
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True  # Create new process group for independence
    )


def _run_blocking_subprocess(cmd, cwd, timeout=1200):
    """Run a blocking subprocess and capture output.

    Used for memory verification - needs to wait for result.
    """
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=os.environ,  # Pass environment variables (DB_*, etc.)
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout
    )


def get_language_from_request():
    """Extract language from request path or default to 'en'."""
    path = request.path
    lang_match = path.split('/')[1] if len(path.split('/')) > 1 else None
    # Accept any 2-letter language code
    if lang_match and len(lang_match) == 2 and lang_match.isalpha():
        return lang_match
    return 'en'

def _validate_language(lang):
    """Validate language code and return True if valid."""
    # Accept any 2-letter language code
    return lang and len(lang) == 2 and lang.isalpha()

def _validate_preset_name(preset_name):
    """
    Validate preset name to prevent path traversal and injection attacks.
    Returns tuple: (is_valid: bool, error_message: Optional[str])
    """
    import re

    if not preset_name:
        return False, "Preset name cannot be empty"

    # Allow only alphanumeric characters, hyphens, and underscores
    if not re.match(r'^[a-zA-Z0-9_-]+$', preset_name):
        return False, f"Invalid preset name: '{preset_name}'. Use only letters, numbers, hyphens, and underscores."

    # Prevent excessively long names
    if len(preset_name) > 100:
        return False, "Preset name too long (max 100 characters)"

    # Extra safety: check for path components
    if '..' in preset_name or '/' in preset_name or '\\' in preset_name:
        return False, f"Invalid characters in preset name: '{preset_name}'"

    return True, None

def _get_preset_manager():
    """
    Get or create shared PromptPresetManager instance.
    Lazy-loads to avoid initialization errors on app start.
    """
    global _preset_manager
    if _preset_manager is None:
        from services.prompt_preset_manager import PromptPresetManager

        # Initialize without loading preset to avoid crashes
        _preset_manager = PromptPresetManager(_prompts_dir, None)

    return _preset_manager

def render_template_with_lang(template_name, **context):
    """Render template with language context."""
    language = get_language_from_request()
    return render_template(template_name, language=language, **context)

@app.route('/')
def index():
    """Main dashboard showing all sessions."""
    return render_template_with_lang('sessions.html')

@app.route('/<lang>/')
def index_with_lang(lang):
    """Main dashboard with language prefix."""
    if not _validate_language(lang):
        return redirect(url_for('index'))
    return render_template_with_lang('sessions.html')

@app.route('/api/sessions')
def get_sessions():
    """Get all sessions with metadata."""
    try:
        # Use unified session reader (primary method)
        sessions = unified_session_reader.get_all_sessions()
        return jsonify(sessions)
    except Exception as e:
        app.logger.error(f"Error in get_sessions: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/sessions/<session_id>')
def get_session_detail(session_id):
    """Get detailed session data."""
    try:
        # Use unified session reader (primary method)
        session_data = unified_session_reader.get_session_detail(session_id)
        if not session_data:
            return jsonify({'error': 'Session not found'}), 404
        return jsonify(session_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sessions/<session_id>/iteration/<int:iteration>')
def get_iteration_detail(session_id, iteration):
    """Get detailed iteration data with tool calls."""
    try:
        # Use unified session reader (primary method)
        iteration_data = unified_session_reader.get_iteration_detail(session_id, iteration)
        if not iteration_data:
            return jsonify({'error': 'Iteration not found'}), 404
        return jsonify(iteration_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sessions/<session_id>/memory')
def get_session_memory(session_id):
    """Get formatted memory data for a session."""
    try:
        # Load session state to use centralized memory parsing
        from core.session_state import SessionState

        session_data = unified_session_reader.get_session_detail(session_id)
        if not session_data:
            return jsonify({'error': 'Session not found'}), 404

        # Use SessionState for centralized memory parsing with metadata
        session_state = SessionState.from_dict(session_data)
        memory_result = session_state.get_memory_data_with_metadata()

        memory_data = memory_result['memory_data']
        last_updated = memory_result['last_updated']

        # Format for WebUI display
        formatted_memory = {
            'session_id': session_id,
            'memory_categories': {},
            'total_items': 0,
            'last_updated': last_updated
        }

        for category, items in memory_data.items():
            if items:  # Only include categories that have items
                # Parse key:value format for new memory system while preserving metadata
                parsed_items = {}
                for item in items:
                    # Items are dicts with 'content', 'iteration', 'timestamp' properties
                    content_value = item['content']
                    iteration = item.get('iteration', 0)
                    timestamp = item.get('timestamp', '')

                    if ':' in content_value:
                        # Split only on first colon - everything after goes into content
                        key, content = content_value.split(':', 1)
                        parsed_items[key.strip()] = {
                            'content': content.strip(),
                            'iteration': iteration,
                            'timestamp': timestamp
                        }
                    else:
                        # Fallback for items without colon
                        item_key = f"item_{len(parsed_items) + 1}"
                        parsed_items[item_key] = {
                            'content': content_value,
                            'iteration': iteration,
                            'timestamp': timestamp
                        }

                formatted_memory['memory_categories'][category] = {
                    'count': len(parsed_items),
                    'items': parsed_items
                }
                formatted_memory['total_items'] += len(parsed_items)

        return jsonify(formatted_memory)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """Delete a session file."""
    try:
        # Find the session file
        session_file = unified_session_reader.output_dir / f"session_{session_id}.json"

        if not session_file.exists():
            return jsonify({'error': 'Session not found'}), 404

        # Delete the file
        os.remove(session_file)

        return jsonify({'message': 'Session deleted successfully'}), 200
    except Exception as e:
        app.logger.error(f"Error deleting session {session_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/sessions/<session_id>/memory/verify', methods=['POST'])
def verify_memory_item(session_id):
    """Verify a specific memory item via subprocess."""
    try:
        data = request.json
        category = data.get('category')
        key = data.get('key')

        if not category or not key:
            return jsonify({'error': 'category and key required'}), 400

        # Get LLM backend from session metadata
        session_file = unified_session_reader.output_dir / f"session_{session_id}.json"
        if not session_file.exists():
            return jsonify({'error': 'Session not found'}), 404

        with open(session_file, 'r', encoding='utf-8') as f:
            session_data = json.load(f)

        llm_backend = session_data.get('session_metadata', {}).get('llm_backend')

        memory_spec = f"{category}:{key}"
        cmd = [
            sys.executable, 'main.py',
            '--verify-memory', session_id, memory_spec,
            '--output-dir', 'output',
            '--quiet'
        ]

        # Add LLM backend if specified in session
        if llm_backend:
            cmd.extend(['--llm-backend', llm_backend])

        project_root = os.path.dirname(os.path.dirname(__file__))
        result = _run_blocking_subprocess(cmd, project_root)

        if result.returncode != 0:
            return jsonify({
                'error': 'Verification failed',
                'stderr': result.stderr
            }), 500

        # With --quiet flag, CLI outputs clean JSON
        try:
            verification_result = json.loads(result.stdout)
            return jsonify(verification_result)
        except json.JSONDecodeError as e:
            app.logger.error(f"Failed to parse verification JSON: {e}")
            return jsonify({
                'error': 'Invalid JSON response',
                'output': result.stdout,
                'stderr': result.stderr
            }), 500

    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Verification timeout'}), 504
    except Exception as e:
        app.logger.error(f"Verification error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/sessions/<session_id>/memory/update', methods=['POST'])
def update_memory_item(session_id):
    """Apply memory update to session."""
    try:
        data = request.json
        category = data.get('category')
        key = data.get('key')
        new_value = data.get('new_value')

        if not category or not key or not new_value:
            return jsonify({'error': 'category, key, and new_value required'}), 400

        from config.settings import AppConfig, DatabaseConfig, LLMConfig
        from database.connection import MSSQLConnection
        from core.session_manager import SessionManager

        config = AppConfig(
            db_config=DatabaseConfig.from_env(),
            llm_config=LLMConfig.default(),
            output_dir=unified_session_reader.output_dir
        )
        db_connection = MSSQLConnection(config.db_config, verbose=False)
        session_manager = SessionManager(config, db_connection)

        session_file = unified_session_reader.output_dir / f"session_{session_id}.json"
        if not session_file.exists():
            return jsonify({'error': 'Session not found'}), 404

        session_state = session_manager.persistence.load_session(session_file)
        success = session_state.update_memory_value(category, key, new_value)

        if success:
            # Save the modified session state back to file
            session_manager.persistence.save_session(session_state)
            return jsonify({'success': True, 'message': 'Memory updated successfully'})
        else:
            return jsonify({'error': 'Failed to update memory'}), 500

    except Exception as e:
        app.logger.error(f"Update error: {e}")
        return jsonify({'error': str(e)}), 500

# Prompt Preset API Endpoints
@app.route('/api/prompts/presets', methods=['GET'])
def get_presets():
    """List all available prompt presets."""
    try:
        preset_manager = _get_preset_manager()
        presets = preset_manager.list_presets()

        return jsonify({'presets': presets})
    except Exception as e:
        app.logger.error(f"Error listing presets: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/prompts/presets/<preset_name>', methods=['GET'])
def get_preset(preset_name):
    """Get specific preset content."""
    try:
        # Validate preset name
        is_valid, error_msg = _validate_preset_name(preset_name)
        if not is_valid:
            return jsonify({'error': error_msg}), 400

        preset_manager = _get_preset_manager()
        preset_content = preset_manager.get_preset_content(preset_name)

        return jsonify(preset_content)
    except FileNotFoundError:
        return jsonify({'error': f'Preset "{preset_name}" not found'}), 404
    except ValueError as e:
        # Catch validation errors from PromptPresetManager
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        app.logger.error(f"Error getting preset {preset_name}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/prompts/presets', methods=['POST'])
def create_preset():
    """Create a new prompt preset."""
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'Missing preset data'}), 400

        preset_name = data.get('preset_name')
        preset_data = data.get('preset_data')

        if not preset_name or not preset_data:
            return jsonify({'error': 'preset_name and preset_data required'}), 400

        # Validate preset name
        is_valid, error_msg = _validate_preset_name(preset_name)
        if not is_valid:
            return jsonify({'error': error_msg}), 400

        preset_manager = _get_preset_manager()
        preset_manager.save_preset(preset_name, preset_data)

        return jsonify({'success': True, 'message': f'Preset "{preset_name}" created successfully'})
    except ValueError as e:
        return jsonify({'error': f'Invalid preset data: {str(e)}'}), 400
    except Exception as e:
        app.logger.error(f"Error creating preset: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/prompts/presets/<preset_name>', methods=['PUT'])
def update_preset(preset_name):
    """Update an existing prompt preset."""
    try:
        # Validate preset name
        is_valid, error_msg = _validate_preset_name(preset_name)
        if not is_valid:
            return jsonify({'error': error_msg}), 400

        data = request.json
        if not data:
            return jsonify({'error': 'Missing preset data'}), 400

        preset_manager = _get_preset_manager()
        preset_manager.save_preset(preset_name, data)

        return jsonify({'success': True, 'message': f'Preset "{preset_name}" updated successfully'})
    except ValueError as e:
        return jsonify({'error': f'Invalid preset data: {str(e)}'}), 400
    except Exception as e:
        app.logger.error(f"Error updating preset {preset_name}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/prompts/presets/<preset_name>', methods=['DELETE'])
def delete_preset(preset_name):
    """Delete a prompt preset."""
    try:
        # Validate preset name
        is_valid, error_msg = _validate_preset_name(preset_name)
        if not is_valid:
            return jsonify({'error': error_msg}), 400

        preset_manager = _get_preset_manager()
        preset_manager.delete_preset(preset_name)

        return jsonify({'success': True, 'message': f'Preset "{preset_name}" deleted successfully'})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except FileNotFoundError:
        return jsonify({'error': f'Preset "{preset_name}" not found'}), 404
    except Exception as e:
        app.logger.error(f"Error deleting preset {preset_name}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/prompts/variables', methods=['GET'])
def get_variables():
    """Get variable registry documentation."""
    try:
        # Try to load default preset to get variable registry
        from services.prompt_preset_manager import PromptPresetManager

        try:
            # Load default preset for variable registry (don't use shared manager)
            temp_manager = PromptPresetManager(_prompts_dir, 'default')
            variable_registry = temp_manager.get_variable_registry()
        except FileNotFoundError:
            # If default.json missing, return empty registry
            variable_registry = {}

        return jsonify({'variable_registry': variable_registry})
    except Exception as e:
        app.logger.error(f"Error getting variable registry: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/i18n/languages', methods=['GET'])
def get_available_languages():
    """List available translation files from static/translations/."""
    translations_dir = Path(app.static_folder) / 'translations'
    languages = []

    if translations_dir.exists():
        for f in translations_dir.glob('*.json'):
            code = f.stem
            # Read language name from the file itself
            try:
                with open(f, 'r', encoding='utf-8') as fp:
                    data = json.load(fp)
                    name = data.get('app', {}).get('language_name', code.upper())
            except (json.JSONDecodeError, IOError):
                name = code.upper()

            languages.append({
                'code': code,
                'name': name
            })

    # Sort with English first, then alphabetically
    languages.sort(key=lambda x: (x['code'] != 'en', x['code']))
    return jsonify({'languages': languages})

@app.route('/session/<session_id>')
def session_detail(session_id):
    """Session detail view."""
    return render_template_with_lang('session.html', session_id=session_id)

@app.route('/<lang>/session/<session_id>')
def session_detail_with_lang(lang, session_id):
    """Session detail view with language prefix."""
    if not _validate_language(lang):
        return redirect(url_for('session_detail', session_id=session_id))
    return render_template_with_lang('session.html', session_id=session_id)

@app.route('/session/<session_id>/iteration/<int:iteration>')
def iteration_detail(session_id, iteration):
    """Iteration detail view."""
    return render_template_with_lang('iteration.html', session_id=session_id, iteration=iteration)

@app.route('/<lang>/session/<session_id>/iteration/<int:iteration>')
def iteration_detail_with_lang(lang, session_id, iteration):
    """Iteration detail view with language prefix."""
    if not _validate_language(lang):
        return redirect(url_for('iteration_detail', session_id=session_id, iteration=iteration))
    return render_template_with_lang('iteration.html', session_id=session_id, iteration=iteration)

@app.route('/session/<session_id>/memory')
def memory_detail(session_id):
    """Memory detail view."""
    return render_template_with_lang('memory.html', session_id=session_id)

@app.route('/<lang>/session/<session_id>/memory')
def memory_detail_with_lang(lang, session_id):
    """Memory detail view with language prefix."""
    if not _validate_language(lang):
        return redirect(url_for('memory_detail', session_id=session_id))
    return render_template_with_lang('memory.html', session_id=session_id)

@app.route('/session/<session_id>/chat')
def session_chat(session_id):
    """Chat view for a session."""
    return render_template_with_lang('chat.html', session_id=session_id)

@app.route('/<lang>/session/<session_id>/chat')
def session_chat_with_lang(lang, session_id):
    """Chat view with language prefix."""
    if not _validate_language(lang):
        return redirect(url_for('session_chat', session_id=session_id))
    return render_template_with_lang('chat.html', session_id=session_id)

@app.route('/api/llm/backends', methods=['GET'])
def get_llm_backends():
    """Get list of available LLM backends."""
    try:
        from llm import LLMProviderFactory
        backends = LLMProviderFactory.get_available_backends()
        return jsonify({'backends': backends}), 200
    except Exception as e:
        app.logger.error(f"Error getting LLM backends: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/sessions/new', methods=['POST'])
def create_new_session():
    """Create a new session by spawning main.py process."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Missing request data'}), 400

        first_user_input = data.get('first_user_input', '').strip()
        if not first_user_input:
            # Use default task when no input is provided (same as CLI behavior)
            from config.settings import DEFAULT_ANALYSIS_TASK
            first_user_input = DEFAULT_ANALYSIS_TASK
            app.logger.info("Using default analysis task for new session")

        # Get default preset from request (sent from frontend localStorage)
        default_preset = data.get('default_preset', 'default')

        # Get LLM backend selection
        llm_backend = data.get('llm_backend', 'qwen')

        # Get custom session name (optional)
        session_name = data.get('name', '').strip() or None

        # Validate preset name if provided
        if default_preset and default_preset != 'default':
            is_valid, error_msg = _validate_preset_name(default_preset)
            if not is_valid:
                return jsonify({'error': f'Invalid preset name: {error_msg}'}), 400

        # Get project root directory (parent of webui directory)
        project_root = Path(__file__).parent.parent
        main_py_path = project_root / 'main.py'

        # Verify main.py exists before spawning process
        if not main_py_path.exists():
            app.logger.error(f"main.py not found at {main_py_path}")
            return jsonify({'error': 'main.py not found in project directory'}), 500

        # Spawn main.py process with the task (independent of WebUI)
        try:
            cmd = [
                'python', 'main.py',
                '--task', first_user_input,
                '--verbose'
            ]

            # Add preset argument if not using default
            if default_preset and default_preset != 'default':
                cmd.extend(['--prompt-preset', default_preset])
                app.logger.info(f"Using prompt preset: {default_preset}")

            # Add LLM backend argument if not using default
            if llm_backend and llm_backend != 'qwen':
                cmd.extend(['--llm-backend', llm_backend])
                app.logger.info(f"Using LLM backend: {llm_backend}")

            # Add session name if provided
            if session_name:
                cmd.extend(['--name', session_name])
                app.logger.info(f"Using session name: {session_name}")

            app.logger.info(f"Starting independent session with command: {' '.join(cmd)} in directory: {project_root}")

            process = _spawn_detached_process(cmd, project_root)

            app.logger.info(f"Session process started independently with PID: {process.pid}")

        except Exception as e:
            app.logger.error(f"Error starting independent session: {e}")
            return jsonify({'error': f'Failed to start session: {str(e)}'}), 500

        # Generate a session ID for tracking (we'll use timestamp for now)
        session_id = datetime.now().strftime('%Y%m%d_%H%M%S')

        return jsonify({
            'status': 'success',
            'message': 'Session started successfully',
            'session_id': session_id
        }), 200

    except Exception as e:
        app.logger.error(f"Error creating new session: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/sessions/<session_id>/resume', methods=['POST'])
def resume_session(session_id):
    """Resume a session by stopping current process (if running) and starting a new one."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Missing request data'}), 400

        resume_guidance = data.get('resume_guidance', '').strip()

        # Get project root directory (parent of webui directory)
        project_root = Path(__file__).parent.parent
        main_py_path = project_root / 'main.py'

        # Verify main.py exists
        if not main_py_path.exists():
            app.logger.error(f"main.py not found at {main_py_path}")
            return jsonify({'error': 'main.py not found in project directory'}), 500

        # Check if session file exists
        session_file = unified_session_reader.output_dir / f'session_{session_id}.json'
        if not session_file.exists():
            return jsonify({'error': f'Session file not found: session_{session_id}.json'}), 404

        # Get session status to determine if it's running
        session_data = unified_session_reader.get_session_detail(session_id)
        if not session_data:
            return jsonify({'error': 'Session not found'}), 404

        session_status = session_data.get('status', 'unknown')

        # If session is running, try to gracefully stop it first
        if session_status == 'running':
            app.logger.info(f"Attempting to stop running session {session_id}")
            stopped = _stop_running_session(session_id, project_root)
            if not stopped:
                app.logger.warning(f"Could not stop running session {session_id}, proceeding anyway")

        # Get LLM backend from session metadata (nested in session_metadata)
        metadata = session_data.get('session_metadata', {})
        llm_backend = metadata.get('llm_backend', 'qwen')

        # Build command for resuming session
        cmd = [
            'python', 'main.py',
            '--continue-session', str(session_file),
            '--verbose'
        ]

        # Add LLM backend if not using default
        if llm_backend and llm_backend != 'qwen':
            cmd.extend(['--llm-backend', llm_backend])
            app.logger.info(f"Resuming with LLM backend: {llm_backend}")

        # Add task guidance if provided
        if resume_guidance:
            cmd.extend(['--task', resume_guidance])

        app.logger.info(f"Resuming session {session_id} with command: {' '.join(cmd)} in directory: {project_root}")

        process = _spawn_detached_process(cmd, project_root)

        app.logger.info(f"Resume process started independently with PID: {process.pid}")

        return jsonify({
            'status': 'success',
            'message': 'Session resumed successfully',
            'session_id': session_id,
            'process_pid': process.pid,
            'had_guidance': bool(resume_guidance)
        }), 200

    except Exception as e:
        app.logger.error(f"Error resuming session {session_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/sessions/<session_id>/stop', methods=['POST'])
def stop_session(session_id):
    """Stop a running session by gracefully terminating its process."""
    try:
        # Get project root directory (parent of webui directory)
        project_root = Path(__file__).parent.parent

        # Check if session file exists
        session_file = unified_session_reader.output_dir / f'session_{session_id}.json'
        if not session_file.exists():
            return jsonify({'error': f'Session file not found: session_{session_id}.json'}), 404

        # Get session status to verify it exists
        session_data = unified_session_reader.get_session_detail(session_id)
        if not session_data:
            return jsonify({'error': 'Session not found'}), 404

        # Attempt to stop the running session
        app.logger.info(f"Attempting to stop session {session_id}")
        stopped = _stop_running_session(session_id, project_root)

        if stopped:
            app.logger.info(f"Successfully stopped session {session_id}")
            return jsonify({
                'status': 'success',
                'message': 'Session stopped gracefully',
                'session_id': session_id,
                'was_running': True,
                'method': 'graceful_shutdown'
            }), 200
        else:
            # Check if process was found but didn't stop
            session_data = unified_session_reader.get_session_detail(session_id)
            if session_data and session_data.get('session_metadata', {}).get('pid'):
                app.logger.warning(f"Process exists but failed to stop gracefully for session {session_id}")
                return jsonify({
                    'status': 'warning',
                    'message': 'Process found but failed to stop gracefully within timeout',
                    'session_id': session_id,
                    'was_running': True,
                    'requires_manual_intervention': True
                }), 200
            else:
                app.logger.info(f"No running process found for session {session_id}")
                return jsonify({
                    'status': 'success',
                    'message': 'No running process found for this session',
                    'session_id': session_id,
                    'was_running': False
                }), 200

    except Exception as e:
        app.logger.error(f"Error stopping session {session_id}: {e}")
        return jsonify({'error': str(e)}), 500

def _stop_running_session(session_id, project_root):
    """
    Attempt to gracefully stop a running session process.

    Args:
        session_id: The session ID to stop
        project_root: Project root directory path

    Returns:
        bool: True if process was found and stopped, False otherwise
    """
    try:
        # Get the PID from the session file instead of searching by command line
        session_data = unified_session_reader.get_session_detail(session_id)
        if not session_data or not session_data.get('session_metadata', {}).get('pid'):
            app.logger.info(f"No PID found in session {session_id} metadata")
            return False

        session_pid = session_data['session_metadata']['pid']
        app.logger.info(f"Found PID {session_pid} for session {session_id}")

        # Check if the process with this PID exists and is a main.py process
        try:
            found_process = psutil.Process(session_pid)
            cmdline = found_process.cmdline()

            # Verify it's actually a main.py process to avoid killing wrong process
            if not (cmdline and 'python' in cmdline[0] and 'main.py' in ' '.join(cmdline)):
                app.logger.warning(f"PID {session_pid} is not a main.py process: {' '.join(cmdline) if cmdline else 'no cmdline'}")
                return False

            app.logger.info(f"Verified running process for session {session_id}: PID {session_pid}")

        except psutil.NoSuchProcess:
            app.logger.info(f"Process {session_pid} for session {session_id} no longer exists")
            return False
        except (psutil.AccessDenied, psutil.ZombieProcess):
            app.logger.warning(f"Cannot access process {session_pid} for session {session_id}")
            return False

        # Try to gracefully stop the process
        app.logger.info(f"Sending SIGTERM to process {found_process.pid} for session {session_id}")
        found_process.send_signal(signal.SIGTERM)

        # Wait for process to exit gracefully (reduced timeout for faster feedback)
        try:
            found_process.wait(timeout=10)
            app.logger.info(f"Process {found_process.pid} for session {session_id} stopped gracefully")
            return True
        except psutil.TimeoutExpired:
            app.logger.warning(f"Process {found_process.pid} for session {session_id} did not stop within 10 seconds")
            app.logger.warning(f"Graceful shutdown failed - process may need manual intervention")
            return False

    except Exception as e:
        app.logger.error(f"Error stopping running session {session_id}: {e}")
        return False

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    print('Client connected')
    emit('connected', {'status': 'Connected to Database Analyzer WebUI'})

@socketio.on('subscribe_session')
def handle_session_subscription(data):
    """Subscribe to session updates."""
    session_id = data.get('session_id')
    if session_id:
        # Join room for this session
        from flask_socketio import join_room
        join_room(session_id)
        emit('subscribed', {'session_id': session_id})

def broadcast_session_update(session_id, update_data):
    """Broadcast session update to subscribed clients."""
    socketio.emit('session_update', update_data, room=session_id)

def handle_file_change(event_type: str, session_id: str):
    """Handle file system changes and broadcast to WebUI."""
    try:
        # Broadcast file change event to all connected clients
        socketio.emit('file_changed', {
            'event_type': event_type,
            'session_id': session_id,
            'timestamp': time.time()
        })

        app.logger.info(f"Broadcasted file change: {event_type} for session {session_id}")

    except Exception as e:
        app.logger.error(f"Error broadcasting file change: {e}")

def start_file_watcher():
    """Start file watcher for live updates."""
    global file_watcher

    try:
        output_dir = Path('output')
        file_watcher = FileWatcher(output_dir, handle_file_change)
        file_watcher.start()
        app.logger.info("File watcher started successfully")

    except Exception as e:
        app.logger.error(f"Failed to start file watcher: {e}")


def create_app(output_dir=None):
    """Create and configure the Flask app."""
    # Suppress Flask and Werkzeug logs
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    logging.getLogger('socketio').setLevel(logging.ERROR)
    logging.getLogger('engineio').setLevel(logging.ERROR)
    
    if output_dir:
        unified_session_reader.set_output_dir(Path(output_dir))
    
    # Start file watcher in a separate thread
    watcher_thread = threading.Thread(target=start_file_watcher, daemon=True)
    watcher_thread.start()
    
    return app

if __name__ == '__main__':
    app = create_app()
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)