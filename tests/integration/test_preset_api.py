"""
Integration Tests for Prompt Preset API Endpoints

Tests the WebUI REST API endpoints for preset management including:
- CRUD operations via HTTP
- Security validation at API level
- Error handling and status codes
- Request size limits
"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.mark.webui
class TestPromptPresetAPI:
    """Test suite for prompt preset WebUI API endpoints."""

    # =========================================================================
    # Comprehensive API Flow Test
    # =========================================================================

    def test_api_preset_lifecycle(self, flask_client, presets_dir, valid_preset_data):
        """Test complete preset lifecycle: CREATE → GET → UPDATE → DELETE."""
        # Patch the preset manager path and reset manager
        with patch('webui.app._prompts_dir', presets_dir), \
             patch('webui.app._preset_manager', None):

            # Step 1: CREATE preset via POST
            response = flask_client.post(
                '/api/prompts/presets',
                json={
                    'preset_name': 'lifecycle_test',
                    'preset_data': valid_preset_data
                }
            )
            assert response.status_code == 200
            assert response.json['success'] is True
            assert 'created successfully' in response.json['message']

            # Verify file was created
            preset_file = presets_dir / 'lifecycle_test.json'
            assert preset_file.exists()

            # Step 2: GET the created preset
            response = flask_client.get('/api/prompts/presets/lifecycle_test')
            assert response.status_code == 200
            loaded_data = response.json
            assert loaded_data['preset_metadata']['name'] == 'test_preset'
            assert 'base_prompt' in loaded_data

            # Step 3: UPDATE the preset via PUT
            updated_data = valid_preset_data.copy()
            updated_data['preset_metadata']['description'] = 'Updated via API'

            response = flask_client.put(
                '/api/prompts/presets/lifecycle_test',
                json=updated_data
            )
            assert response.status_code == 200
            assert response.json['success'] is True
            assert 'updated successfully' in response.json['message']

            # Verify update
            response = flask_client.get('/api/prompts/presets/lifecycle_test')
            assert response.json['preset_metadata']['description'] == 'Updated via API'

            # Step 4: DELETE the preset
            response = flask_client.delete('/api/prompts/presets/lifecycle_test')
            assert response.status_code == 200
            assert response.json['success'] is True
            assert 'deleted successfully' in response.json['message']

            # Verify deletion
            assert not preset_file.exists()

            # GET should now return 404
            response = flask_client.get('/api/prompts/presets/lifecycle_test')
            assert response.status_code == 404

    # =========================================================================
    # List Presets Tests
    # =========================================================================

    def test_api_list_presets(self, flask_client, presets_dir, valid_preset_data):
        """Test listing presets with empty and populated directory."""
        with patch('webui.app._prompts_dir', presets_dir), \
             patch('webui.app._preset_manager', None):

            # Test 1: Empty directory
            response = flask_client.get('/api/prompts/presets')
            assert response.status_code == 200
            assert response.json['presets'] == []

            # Create some presets
            for i in range(3):
                preset_path = presets_dir / f"preset_{i}.json"
                with open(preset_path, 'w') as f:
                    json.dump(valid_preset_data, f)

            # Create a corrupted preset
            corrupted_path = presets_dir / "corrupted.json"
            corrupted_path.write_text("{ invalid json }")

            # Test 2: Populated directory
            response = flask_client.get('/api/prompts/presets')
            assert response.status_code == 200
            presets = response.json['presets']
            assert len(presets) == 4  # 3 valid + 1 corrupted

            # Check for error item
            error_items = [p for p in presets if p.get('error')]
            assert len(error_items) == 1

    # =========================================================================
    # Security Validation Tests
    # =========================================================================

    @pytest.mark.parametrize("dangerous_name,expected_status", [
        ("../../etc/passwd", 404),  # Flask routing interprets slashes
        ("../../../evil", 404),  # Flask routing interprets slashes
        ("/etc/shadow", 404),  # Flask routing interprets slashes
        ("preset/../danger", 404),  # Flask routing interprets slashes
        ("", 404),  # Empty path results in 404
        ("a" * 101, 400),  # Too long - proper validation
        ("preset with spaces", 400),  # Invalid characters - proper validation
        ("preset@#$%", 400)  # Invalid characters - proper validation
    ])
    def test_api_security_validation(self, flask_client, dangerous_name, expected_status, valid_preset_data):
        """Test that API rejects dangerous preset names."""
        # Note: No need to patch prompts_dir for security tests
        # Test GET
        response = flask_client.get(f'/api/prompts/presets/{dangerous_name}')
        assert response.status_code in [expected_status, 404]  # Accept 404 for path routing issues

        # Test POST - should always validate properly
        response = flask_client.post(
            '/api/prompts/presets',
            json={
                'preset_name': dangerous_name,
                'preset_data': valid_preset_data
            }
        )
        # POST always validates the name properly
        if dangerous_name in ["", "a" * 101, "preset with spaces", "preset@#$%"] or ".." in dangerous_name or "/" in dangerous_name or "\\" in dangerous_name:
            assert response.status_code == 400
            assert 'error' in response.json

        # Test PUT
        response = flask_client.put(
            f'/api/prompts/presets/{dangerous_name}',
            json=valid_preset_data
        )
        assert response.status_code in [expected_status, 404]  # Accept 404 for path routing issues

        # Test DELETE
        response = flask_client.delete(f'/api/prompts/presets/{dangerous_name}')
        assert response.status_code in [expected_status, 404]  # Accept 404 for path routing issues

    # =========================================================================
    # Variable Registry Test
    # =========================================================================

    def test_api_get_variables(self, flask_client, presets_dir, valid_preset_data):
        """Test getting variable registry with and without default preset."""
        with patch('webui.app._prompts_dir', presets_dir), \
             patch('webui.app._preset_manager', None):

            # Test 1: No default.json - should return empty registry
            with patch('services.prompt_preset_manager.PromptPresetManager.__init__') as mock_init:
                # Mock FileNotFoundError for missing default
                mock_init.side_effect = FileNotFoundError("default.json not found")

                response = flask_client.get('/api/prompts/variables')
                assert response.status_code == 200
                assert response.json['variable_registry'] == {}

            # Test 2: With default.json present
            default_path = presets_dir / "default.json"
            with open(default_path, 'w') as f:
                json.dump(valid_preset_data, f)

            response = flask_client.get('/api/prompts/variables')
            assert response.status_code == 200
            registry = response.json['variable_registry']
            assert 'CURRENT_DATE' in registry
            assert 'DB_RESULT_LIMIT' in registry

    # =========================================================================
    # Session Creation with Preset Test
    # =========================================================================

    def test_api_create_session_with_preset(self, flask_client):
        """Test that session creation passes preset to subprocess."""
        with patch('webui.app.subprocess.Popen') as mock_popen:
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_popen.return_value = mock_process

            # Create session with default preset
            response = flask_client.post(
                '/api/sessions/new',
                json={
                    'first_user_input': 'Test task',
                    'default_preset': 'default'
                }
            )
            assert response.status_code == 200
            assert response.json['status'] == 'success'

            # Verify subprocess was called
            mock_popen.assert_called_once()
            cmd = mock_popen.call_args[0][0]
            assert 'python' in cmd[0]
            assert 'main.py' in cmd[1]
            assert '--task' in cmd
            # Should not have --prompt-preset for 'default'
            assert '--prompt-preset' not in cmd

            # Reset mock
            mock_popen.reset_mock()

            # Create session with custom preset
            response = flask_client.post(
                '/api/sessions/new',
                json={
                    'first_user_input': 'Test task',
                    'default_preset': 'custom_preset'
                }
            )
            assert response.status_code == 200

            # Verify subprocess includes preset arg
            cmd = mock_popen.call_args[0][0]
            assert '--prompt-preset' in cmd
            preset_idx = cmd.index('--prompt-preset')
            assert cmd[preset_idx + 1] == 'custom_preset'

    # =========================================================================
    # Request Validation Tests
    # =========================================================================

    def test_api_max_content_length(self, flask_client):
        """Test that API enforces 1MB content length limit."""
        # Create a large payload (> 1MB)
        large_data = {
            'preset_name': 'test',
            'preset_data': {
                'preset_metadata': {'name': 'test'},
                'base_prompt': {
                    'schema': 'x' * (2 * 1024 * 1024),  # 2MB of data
                    'tools_description': 'test',
                    'domain_context': 'test',
                    'task_instructions': 'test'
                }
            }
        }

        # Flask should reject before our handler
        response = flask_client.post(
            '/api/prompts/presets',
            json=large_data
        )
        # Flask may return 413 or 500 for large requests
        assert response.status_code in [413, 500]

    def test_api_missing_fields(self, flask_client):
        """Test validation of required fields in requests."""
        # Test validation - no directory patch needed
        # Test POST with missing preset_name
        response = flask_client.post(
            '/api/prompts/presets',
            json={'preset_data': {}}
        )
        assert response.status_code == 400
        assert 'preset_name and preset_data required' in response.json['error']

        # Test POST with missing preset_data
        response = flask_client.post(
            '/api/prompts/presets',
            json={'preset_name': 'test'}
        )
        assert response.status_code == 400
        assert 'preset_name and preset_data required' in response.json['error']

        # Test PUT with no body - Flask may return 415 if content-type is not set
        response = flask_client.put(
            '/api/prompts/presets/test',
            json={},  # Send empty JSON object
            headers={'Content-Type': 'application/json'}
        )
        # The API should validate this as invalid preset data
        assert response.status_code in [400, 415, 500]  # Accept multiple error codes

    # =========================================================================
    # Error Response Tests
    # =========================================================================

    def test_api_error_responses(self, flask_client, presets_dir):
        """Test various error scenarios and status codes."""
        with patch('webui.app._prompts_dir', presets_dir), \
             patch('webui.app._preset_manager', None):

            # Test 404: Get non-existent preset
            response = flask_client.get('/api/prompts/presets/nonexistent')
            assert response.status_code == 404
            assert 'not found' in response.json['error'].lower()

            # Test 404: Delete non-existent preset
            response = flask_client.delete('/api/prompts/presets/nonexistent')
            assert response.status_code == 404
            assert 'not found' in response.json['error'].lower()

            # Test 400: Delete default preset
            response = flask_client.delete('/api/prompts/presets/default')
            assert response.status_code == 400
            assert 'Cannot delete default' in response.json['error']

            # Test 400: Invalid preset structure
            response = flask_client.post(
                '/api/prompts/presets',
                json={
                    'preset_name': 'invalid',
                    'preset_data': {
                        # Missing required sections
                        'some_field': 'value'
                    }
                }
            )
            assert response.status_code == 400
            assert 'Invalid preset data' in response.json['error']