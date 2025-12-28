"""
Prompt Preset Manager

Handles loading, saving, and managing prompt presets stored as JSON files.
Provides template variable replacement for dynamic runtime values.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


class PromptPresetManager:
    """Manages prompt presets with template variable support."""

    @classmethod
    def create_with_fallback(cls, presets_dir: Path, preset_name: Optional[str] = None,
                            fallback_to_default: bool = True, logger: Optional[logging.Logger] = None) -> Optional['PromptPresetManager']:
        """
        Factory method to create PromptPresetManager with consistent error handling.

        Args:
            presets_dir: Directory containing preset JSON files
            preset_name: Name of preset to load, or None
            fallback_to_default: If True and preset_name fails, try 'default' preset
            logger: Logger instance for warnings

        Returns:
            PromptPresetManager instance or None if all attempts fail
        """
        if not logger:
            logger = logging.getLogger(__name__)

        # Try the specified preset
        if preset_name:
            try:
                return cls(presets_dir, preset_name)
            except (FileNotFoundError, ValueError) as e:
                logger.warning(f"Failed to load preset '{preset_name}': {e}")
                if not fallback_to_default:
                    return None

        # Try default preset if requested
        if fallback_to_default and preset_name != 'default':
            try:
                return cls(presets_dir, 'default')
            except (FileNotFoundError, ValueError) as e:
                logger.warning(f"Failed to load default preset: {e}")

        # Return manager without active preset for management operations
        try:
            return cls(presets_dir, None)
        except Exception as e:
            logger.error(f"Failed to create preset manager: {e}")
            return None

    def __init__(self, presets_dir: Path, preset_name: Optional[str] = None):
        """
        Initialize PromptPresetManager.

        Args:
            presets_dir: Directory containing preset JSON files
            preset_name: Name of preset to load (without .json extension), or None to skip loading

        Raises:
            ValueError: If preset_name is invalid
            FileNotFoundError: If preset file doesn't exist
        """
        self.presets_dir = presets_dir
        self.presets_dir.mkdir(exist_ok=True)
        self.logger = logging.getLogger(__name__)
        self.active_preset = None

        # Load the specified preset if provided
        if preset_name:
            self._validate_preset_name(preset_name)
            try:
                self.active_preset = self._load_preset(preset_name)
            except FileNotFoundError:
                self.logger.warning(f"Preset '{preset_name}' not found, active_preset is None")
                raise

    def _validate_preset_name(self, preset_name: str) -> None:
        """
        Validate preset name to prevent path traversal and injection attacks.

        Args:
            preset_name: Preset name to validate

        Raises:
            ValueError: If preset name is invalid
        """
        if not preset_name:
            raise ValueError("Preset name cannot be empty")

        # Allow only alphanumeric characters, hyphens, and underscores
        if not re.match(r'^[a-zA-Z0-9_-]+$', preset_name):
            raise ValueError(
                f"Invalid preset name: '{preset_name}'. "
                "Use only letters, numbers, hyphens, and underscores."
            )

        # Prevent excessively long names
        if len(preset_name) > 100:
            raise ValueError("Preset name too long (max 100 characters)")

        # Extra safety: check for path components
        if '..' in preset_name or '/' in preset_name or '\\' in preset_name:
            raise ValueError(f"Invalid characters in preset name: '{preset_name}'")

    def _load_preset(self, preset_name: str) -> Dict[str, Any]:
        """
        Load a preset from file.

        Args:
            preset_name: Name of preset file (without .json extension)

        Returns:
            Preset dictionary

        Raises:
            FileNotFoundError: If preset file doesn't exist
            ValueError: If preset JSON is invalid

        Note:
            preset_name must be already validated via _validate_preset_name
        """
        # Validation should have been done in caller, but double-check for safety
        self._validate_preset_name(preset_name)

        preset_path = self.presets_dir / f"{preset_name}.json"

        if not preset_path.exists():
            self.logger.warning(f"Preset file not found: {preset_path}")
            raise FileNotFoundError(f"Preset '{preset_name}' not found")

        try:
            with open(preset_path, 'r', encoding='utf-8') as f:
                preset = json.load(f)

            # Validate preset structure
            self._validate_preset(preset)

            self.logger.info(f"Loaded preset: {preset_name}")
            return preset

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in preset {preset_name}: {e}")
            raise ValueError(f"Invalid JSON in preset '{preset_name}': {e}")

    def _validate_preset(self, preset: Dict[str, Any]) -> None:
        """
        Validate preset structure.

        Args:
            preset: Preset dictionary to validate

        Raises:
            ValueError: If preset structure is invalid
        """
        required_sections = ['preset_metadata', 'base_prompt']

        for section in required_sections:
            if section not in preset:
                raise ValueError(f"Missing required section: {section}")

        # Validate base_prompt subsections
        required_base = ['schema', 'tools_description', 'domain_context', 'task_instructions']
        for field in required_base:
            if field not in preset['base_prompt']:
                raise ValueError(f"Missing required field in base_prompt: {field}")

    def get_active_preset(self) -> Dict[str, Any]:
        """Get the currently active preset."""
        return self.active_preset

    def list_presets(self) -> List[Dict[str, Any]]:
        """
        List all available presets.

        Returns:
            List of preset metadata dictionaries
        """
        presets = []

        for preset_file in self.presets_dir.glob("*.json"):
            try:
                with open(preset_file, 'r', encoding='utf-8') as f:
                    preset = json.load(f)

                presets.append({
                    'filename': preset_file.stem,
                    'name': preset.get('preset_metadata', {}).get('name', preset_file.stem),
                    'description': preset.get('preset_metadata', {}).get('description', ''),
                    'version': preset.get('preset_metadata', {}).get('version', ''),
                    'path': str(preset_file)
                })
            except Exception as e:
                self.logger.warning(f"Failed to load preset {preset_file}: {e}")
                presets.append({
                    'filename': preset_file.stem,
                    'name': preset_file.stem,
                    'description': f'Error loading preset: {e}',
                    'error': True
                })

        return presets

    def get_preset_content(self, preset_name: str) -> Dict[str, Any]:
        """
        Get full content of a specific preset.

        Args:
            preset_name: Name of preset file (without .json extension)

        Returns:
            Complete preset dictionary

        Raises:
            ValueError: If preset_name is invalid
            FileNotFoundError: If preset doesn't exist
        """
        self._validate_preset_name(preset_name)
        return self._load_preset(preset_name)

    def save_preset(self, preset_name: str, preset_data: Dict[str, Any]) -> None:
        """
        Save a preset to file.

        Args:
            preset_name: Name of preset file (without .json extension)
            preset_data: Complete preset dictionary

        Raises:
            ValueError: If preset_name or preset data is invalid
        """
        # Validate preset name for security
        self._validate_preset_name(preset_name)

        # Validate before saving
        self._validate_preset(preset_data)

        preset_path = self.presets_dir / f"{preset_name}.json"

        try:
            with open(preset_path, 'w', encoding='utf-8') as f:
                json.dump(preset_data, f, indent=2, ensure_ascii=False)

            self.logger.info(f"Saved preset: {preset_name}")

        except Exception as e:
            self.logger.error(f"Failed to save preset {preset_name}: {e}")
            raise

    def delete_preset(self, preset_name: str) -> None:
        """
        Delete a preset file.

        Args:
            preset_name: Name of preset file (without .json extension)

        Raises:
            ValueError: If preset_name is invalid or trying to delete default preset
            FileNotFoundError: If preset doesn't exist
        """
        # Validate preset name for security
        self._validate_preset_name(preset_name)

        if preset_name == 'default':
            raise ValueError("Cannot delete default preset")

        preset_path = self.presets_dir / f"{preset_name}.json"

        if not preset_path.exists():
            raise FileNotFoundError(f"Preset '{preset_name}' not found")

        preset_path.unlink()
        self.logger.info(f"Deleted preset: {preset_name}")

    def build_prompt_with_variables(
        self,
        template: str,
        context: Dict[str, Any],
        strict: bool = False
    ) -> Tuple[str, List[str]]:
        """
        Replace template placeholders with runtime values.

        Args:
            template: Prompt template with {{VARIABLE}} placeholders
            context: Dictionary of variable names to values
            strict: If True, raise ValueError when unreplaced placeholders found

        Returns:
            Tuple of (processed_prompt, list_of_unreplaced_variables)

        Raises:
            ValueError: If strict=True and unreplaced placeholders are found
        """
        result = template

        for key, value in context.items():
            placeholder = f"{{{{{key}}}}}"  # {{KEY}} format
            result = result.replace(placeholder, str(value))

        # Check for unreplaced placeholders
        unreplaced = re.findall(r'\{\{([^}]+)\}\}', result)

        if unreplaced:
            self.logger.warning(f"Unreplaced placeholders in prompt: {unreplaced}")

            if strict:
                raise ValueError(
                    f"Unreplaced template variables found: {unreplaced}. "
                    f"Available variables: {list(context.keys())}"
                )

        return result, unreplaced

    def get_variable_registry(self) -> Dict[str, Any]:
        """
        Get the variable registry from active preset.

        Returns:
            Variable registry dictionary or empty dict if not present
        """
        return self.active_preset.get('variable_registry', {})
