"""
Unit Tests for PromptPresetManager

Tests the core functionality of the prompt preset management system including:
- Security validation (path traversal prevention)
- CRUD operations on preset files
- Preset structure validation
- Variable replacement in templates
"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch, mock_open

from services.prompt_preset_manager import PromptPresetManager


class TestPromptPresetManager:
    """Test suite for PromptPresetManager class."""

    # =========================================================================
    # Security & Validation Tests
    # =========================================================================

    @pytest.mark.parametrize("preset_name,should_pass,error_pattern", [
        # Valid names
        ("valid_preset", True, None),
        ("valid-preset-123", True, None),
        ("preset_with_underscore", True, None),
        ("123numeric", True, None),

        # Path traversal attempts
        ("../../etc/passwd", False, "Invalid"),
        ("../../../evil", False, "Invalid"),
        ("..\\..\\windows\\system32", False, "Invalid"),
        ("/etc/shadow", False, "Invalid"),
        ("C:\\Windows\\System32", False, "Invalid"),
        ("preset/../../../danger", False, "Invalid"),
        ("preset\\..\\..\\danger", False, "Invalid"),

        # Invalid characters
        ("", False, "empty"),
        ("a" * 101, False, "too long"),
        ("preset with spaces", False, "Invalid"),
        ("preset@#$%", False, "Invalid"),
        ("preset;rm -rf /", False, "Invalid"),
        ("${variable}", False, "Invalid"),
        ("'; DROP TABLE --", False, "Invalid"),
    ])
    def test_validate_preset_name(self, preset_name, should_pass, error_pattern):
        """Test preset name validation against various attack patterns."""
        manager = PromptPresetManager(Path("prompts"), None)

        if should_pass:
            # Should not raise
            manager._validate_preset_name(preset_name)
        else:
            with pytest.raises(ValueError, match=error_pattern):
                manager._validate_preset_name(preset_name)

    # =========================================================================
    # CRUD Operations Tests
    # =========================================================================

    def test_load_preset_scenarios(self, presets_dir, valid_preset_data):
        """Test loading presets: valid, missing, and corrupted files."""
        manager = PromptPresetManager(presets_dir, None)

        # Test 1: Load valid preset
        preset_path = presets_dir / "valid.json"
        with open(preset_path, 'w') as f:
            json.dump(valid_preset_data, f)

        loaded = manager._load_preset("valid")
        assert loaded["preset_metadata"]["name"] == "test_preset"
        assert "base_prompt" in loaded

        # Test 2: Load missing preset
        with pytest.raises(FileNotFoundError, match="not found"):
            manager._load_preset("nonexistent")

        # Test 3: Load corrupted JSON
        corrupted_path = presets_dir / "corrupted.json"
        with open(corrupted_path, 'w') as f:
            f.write("{ invalid json }")

        with pytest.raises(ValueError, match="Invalid JSON"):
            manager._load_preset("corrupted")

    def test_save_and_load_preset(self, presets_dir, valid_preset_data):
        """Test save → load → verify cycle."""
        manager = PromptPresetManager(presets_dir, None)

        # Save preset
        manager.save_preset("test_save", valid_preset_data)

        # Verify file exists
        preset_path = presets_dir / "test_save.json"
        assert preset_path.exists()

        # Load and verify content
        loaded = manager.get_preset_content("test_save")
        assert loaded == valid_preset_data

        # Verify JSON formatting (indented)
        with open(preset_path, 'r') as f:
            content = f.read()
            assert "  " in content  # Check for indentation

    def test_delete_preset_scenarios(self, presets_dir, valid_preset_data):
        """Test deleting presets: existing, missing, and protected default."""
        manager = PromptPresetManager(presets_dir, None)

        # Create a preset to delete
        manager.save_preset("to_delete", valid_preset_data)
        assert (presets_dir / "to_delete.json").exists()

        # Test 1: Delete existing preset
        manager.delete_preset("to_delete")
        assert not (presets_dir / "to_delete.json").exists()

        # Test 2: Delete non-existent preset
        with pytest.raises(FileNotFoundError, match="not found"):
            manager.delete_preset("nonexistent")

        # Test 3: Protect default preset
        with pytest.raises(ValueError, match="Cannot delete default"):
            manager.delete_preset("default")

    def test_list_presets_with_mixed_files(self, presets_dir, valid_preset_data):
        """Test listing presets with valid and corrupted files."""
        manager = PromptPresetManager(presets_dir, None)

        # Create valid preset
        manager.save_preset("valid1", valid_preset_data)

        # Create another valid preset
        modified_data = valid_preset_data.copy()
        modified_data["preset_metadata"]["name"] = "valid2"
        manager.save_preset("valid2", modified_data)

        # Create corrupted preset
        corrupted_path = presets_dir / "corrupted.json"
        with open(corrupted_path, 'w') as f:
            f.write("{ invalid json }")

        # Create non-JSON file (should be ignored)
        (presets_dir / "readme.txt").write_text("Not a preset")

        # List presets
        presets = manager.list_presets()

        # Should have 3 items (2 valid + 1 error item)
        assert len(presets) == 3

        # Check valid presets
        valid_names = [p["filename"] for p in presets if "error" not in p]
        assert "valid1" in valid_names
        assert "valid2" in valid_names

        # Check corrupted preset marked with error
        error_presets = [p for p in presets if p.get("error")]
        assert len(error_presets) == 1
        assert error_presets[0]["filename"] == "corrupted"

    # =========================================================================
    # Preset Structure Validation Tests
    # =========================================================================

    @pytest.mark.parametrize("preset_data,should_pass,error_pattern", [
        # Valid structure
        (
            {
                "preset_metadata": {"name": "test"},
                "base_prompt": {
                    "schema": "test",
                    "tools_description": "test",
                    "domain_context": "test",
                    "task_instructions": "test"
                }
            },
            True,
            None
        ),
        # Missing preset_metadata
        (
            {"base_prompt": {"schema": "test"}},
            False,
            "Missing required section: preset_metadata"
        ),
        # Missing base_prompt
        (
            {"preset_metadata": {"name": "test"}},
            False,
            "Missing required section: base_prompt"
        ),
        # Missing required field in base_prompt
        (
            {
                "preset_metadata": {"name": "test"},
                "base_prompt": {
                    "tools_description": "test",
                    "domain_context": "test",
                    "task_instructions": "test"
                    # Missing 'schema'
                }
            },
            False,
            "Missing required field.*schema"
        ),
    ])
    def test_validate_preset_structure(self, preset_data, should_pass, error_pattern):
        """Test preset structure validation with various configurations."""
        manager = PromptPresetManager(Path("prompts"), None)

        if should_pass:
            # Should not raise
            manager._validate_preset(preset_data)
        else:
            with pytest.raises(ValueError, match=error_pattern):
                manager._validate_preset(preset_data)

    # =========================================================================
    # Variable Replacement Tests
    # =========================================================================

    def test_build_prompt_with_variables(self, preset_manager):
        """Test variable replacement in templates with multiple scenarios."""
        template = "Hello {{NAME}}, today is {{DATE}}. Limit is {{LIMIT}}."
        context = {
            "NAME": "World",
            "DATE": "2025-01-01",
            # LIMIT is intentionally missing to test unreplaced
        }

        # Test non-strict mode (default)
        result, unreplaced = preset_manager.build_prompt_with_variables(template, context)

        # Check replacements
        assert "Hello World" in result
        assert "today is 2025-01-01" in result
        assert "{{LIMIT}}" in result  # Should remain unreplaced

        # Check unreplaced list
        assert unreplaced == ["LIMIT"]

        # Test with all variables present
        context["LIMIT"] = "100"
        result, unreplaced = preset_manager.build_prompt_with_variables(template, context)

        assert result == "Hello World, today is 2025-01-01. Limit is 100."
        assert unreplaced == []

    def test_build_prompt_strict_mode(self, preset_manager):
        """Test strict mode behavior for variable replacement."""
        template = "Value: {{MISSING_VAR}}"
        context = {"OTHER_VAR": "value"}

        # Non-strict mode: returns result with unreplaced
        result, unreplaced = preset_manager.build_prompt_with_variables(
            template, context, strict=False
        )
        assert "{{MISSING_VAR}}" in result
        assert unreplaced == ["MISSING_VAR"]

        # Strict mode: raises exception
        with pytest.raises(ValueError, match="Unreplaced template variables.*MISSING_VAR"):
            preset_manager.build_prompt_with_variables(
                template, context, strict=True
            )

    # =========================================================================
    # Integration Tests
    # =========================================================================

    def test_preset_crud_operations(self, presets_dir, valid_preset_data):
        """Comprehensive test of all CRUD operations in sequence."""
        manager = PromptPresetManager(presets_dir, None)

        # Initially empty
        presets = manager.list_presets()
        assert len(presets) == 0

        # Create
        manager.save_preset("test1", valid_preset_data)
        assert (presets_dir / "test1.json").exists()

        # Read
        loaded = manager.get_preset_content("test1")
        assert loaded["preset_metadata"]["name"] == "test_preset"

        # Update
        updated_data = valid_preset_data.copy()
        updated_data["preset_metadata"]["description"] = "Updated description"
        manager.save_preset("test1", updated_data)

        # Verify update
        loaded = manager.get_preset_content("test1")
        assert loaded["preset_metadata"]["description"] == "Updated description"

        # List
        presets = manager.list_presets()
        assert len(presets) == 1
        assert presets[0]["filename"] == "test1"

        # Delete
        manager.delete_preset("test1")
        assert not (presets_dir / "test1.json").exists()

        # Verify deleted
        presets = manager.list_presets()
        assert len(presets) == 0

    def test_initialization_with_preset(self, presets_dir, valid_preset_data):
        """Test PromptPresetManager initialization with and without preset loading."""
        # Create a preset file
        preset_path = presets_dir / "init_test.json"
        with open(preset_path, 'w') as f:
            json.dump(valid_preset_data, f)

        # Test 1: Initialize with valid preset
        manager = PromptPresetManager(presets_dir, "init_test")
        assert manager.active_preset is not None
        assert manager.active_preset["preset_metadata"]["name"] == "test_preset"

        # Test 2: Initialize with missing preset
        with pytest.raises(FileNotFoundError):
            PromptPresetManager(presets_dir, "nonexistent")

        # Test 3: Initialize without preset (None)
        manager = PromptPresetManager(presets_dir, None)
        assert manager.active_preset is None

        # Test 4: Get variable registry from active preset
        manager = PromptPresetManager(presets_dir, "init_test")
        registry = manager.get_variable_registry()
        assert "CURRENT_DATE" in registry
        assert "DB_RESULT_LIMIT" in registry