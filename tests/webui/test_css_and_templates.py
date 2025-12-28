"""
Tests for CSS refactoring and new UI components.

Tests cover:
- CSS file accessibility and imports
- Resume Session modal markup
- Translation file completeness
"""

import pytest
import json
from pathlib import Path


# ============================================================================
# CSS File Loading Tests
# ============================================================================

@pytest.mark.webui
class TestCSSFileLoading:
    """Tests for CSS static file accessibility."""

    CSS_FILES = [
        'colors.css',
        'styles.css',
        'base.css',
        'header.css',
        'buttons.css',
        'sessions.css',
        'session-detail.css',
        'iterations.css',
        'modals.css',
        'memory.css',
        'forms.css',
        'toasts.css',
        'preset-editor.css',
        'animations.css',
    ]

    @pytest.mark.parametrize('css_file', CSS_FILES)
    def test_css_file_accessible(self, flask_client, css_file):
        """Test that each CSS file is accessible via Flask static route."""
        response = flask_client.get(f'/static/css/{css_file}')

        assert response.status_code == 200, f"CSS file {css_file} not accessible"
        assert response.content_type == 'text/css; charset=utf-8'
        assert len(response.data) > 0, f"CSS file {css_file} is empty"

    def test_styles_css_contains_imports(self, flask_client):
        """Test that styles.css contains @import statements."""
        response = flask_client.get('/static/css/styles.css')

        assert response.status_code == 200
        content = response.data.decode('utf-8')

        # Check for @import statements
        assert '@import' in content
        assert 'colors.css' in content
        assert 'base.css' in content
        assert 'animations.css' in content

    def test_all_css_imports_are_valid(self, flask_client):
        """Test that all CSS files imported in styles.css exist."""
        response = flask_client.get('/static/css/styles.css')
        content = response.data.decode('utf-8')

        # Extract @import statements
        import re
        imports = re.findall(r"@import url\('([^']+)'\)", content)

        for css_file in imports:
            response = flask_client.get(f'/static/css/{css_file}')
            assert response.status_code == 200, f"Imported CSS file {css_file} not found"

    def test_colors_css_has_required_variables(self, flask_client):
        """Test that colors.css defines required CSS variables."""
        response = flask_client.get('/static/css/colors.css')
        content = response.data.decode('utf-8')

        required_vars = [
            '--primary',
            '--primary-hover',
            '--status-running',
            '--status-completed',
            '--status-interrupted',
            '--text-primary',
            '--text-secondary',
            '--bg-primary',
        ]

        for var in required_vars:
            assert var in content, f"CSS variable {var} not found in colors.css"

    def test_colors_css_has_memory_category_variables(self, flask_client):
        """Test that colors.css defines all 10 memory category CSS variables."""
        response = flask_client.get('/static/css/colors.css')
        content = response.data.decode('utf-8')

        # All 10 memory categories (using CSS naming convention with hyphens)
        memory_categories = [
            'insights',
            'patterns',
            'explored-areas',
            'key-findings',
            'opportunities',
            'data-milestones',
            'data-issues',
            'metrics',
            'context',
            'user-requests'
        ]

        for category in memory_categories:
            var_main = f'--memory-{category}'
            var_bg = f'--memory-{category}-bg'
            var_text = f'--memory-{category}-text'

            assert var_main in content, f"Missing main color: {var_main}"
            assert var_bg in content, f"Missing background color: {var_bg}"
            assert var_text in content, f"Missing text color: {var_text}"


# ============================================================================
# Resume Session Modal Tests
# ============================================================================

@pytest.mark.webui
class TestResumeSessionModal:
    """Tests for Resume Session modal markup in templates."""

    def test_resume_modal_exists_in_sessions_template(self, flask_client):
        """Test that Resume Session modal is present in sessions page."""
        response = flask_client.get('/en/')

        assert response.status_code == 200
        content = response.data.decode('utf-8')

        # Check for modal container
        assert 'id="resume-session-modal"' in content

    def test_resume_modal_has_required_elements(self, flask_client):
        """Test Resume modal has all required UI elements."""
        response = flask_client.get('/en/')
        content = response.data.decode('utf-8')

        required_elements = [
            'id="resume-session-modal"',
            'id="resume-session-guidance"',
            'id="resume-session-id"',
            'id="resume-session-backend"',
            'id="submit-resume-btn"',
            'closeResumeSessionModal',
        ]

        for element in required_elements:
            assert element in content, f"Required element {element} not found in modal"

    def test_resume_modal_has_i18n_attributes(self, flask_client):
        """Test Resume modal elements have translation attributes."""
        response = flask_client.get('/en/')
        content = response.data.decode('utf-8')

        # Check for data-i18n attributes on resume modal elements
        assert 'data-i18n="navigation.resume"' in content
        assert 'data-i18n="sessions.resume_guidance_label"' in content
        assert 'data-i18n-placeholder="sessions.resume_guidance_placeholder"' in content

    def test_resume_modal_has_keyboard_hints(self, flask_client):
        """Test Resume modal displays keyboard shortcuts."""
        response = flask_client.get('/en/')
        content = response.data.decode('utf-8')

        # Check for keyboard hints
        assert '<kbd>ESC</kbd>' in content
        assert '<kbd>Ctrl+Enter</kbd>' in content
        assert 'to_resume' in content or 'to resume' in content


# ============================================================================
# New Session Modal Tests
# ============================================================================

@pytest.mark.webui
class TestNewSessionModal:
    """Tests for New Session modal structure."""

    def test_new_session_modal_exists(self, flask_client):
        """Test that New Session modal is present."""
        response = flask_client.get('/en/')
        content = response.data.decode('utf-8')

        assert 'id="new-session-modal"' in content

    def test_new_session_modal_has_backend_dropdown(self, flask_client):
        """Test New Session modal has LLM backend dropdown."""
        response = flask_client.get('/en/')
        content = response.data.decode('utf-8')

        assert 'id="backend-dropdown"' in content
        assert 'id="llm-backend-select"' in content

    def test_new_session_modal_rounded_corners_css(self, flask_client):
        """Test that modals have rounded corner styling."""
        response = flask_client.get('/static/css/modals.css')
        content = response.data.decode('utf-8')

        # Check for border-radius on new session modal
        assert 'new-session-modal-content' in content
        assert 'border-radius: 16px' in content


# ============================================================================
# Translation File Tests
# ============================================================================

@pytest.mark.webui
class TestTranslationFiles:
    """Tests for translation file completeness."""

    TRANSLATION_PATH = Path(__file__).parent.parent.parent / 'webui' / 'static' / 'translations'

    def test_english_translations_exist(self):
        """Test that English translation file exists."""
        en_file = self.TRANSLATION_PATH / 'en.json'
        assert en_file.exists(), "English translation file not found"

        with open(en_file, 'r', encoding='utf-8') as f:
            translations = json.load(f)

        assert isinstance(translations, dict)
        assert len(translations) > 0

    def test_resume_modal_translations_in_english(self):
        """Test that resume modal translations exist in English."""
        en_file = self.TRANSLATION_PATH / 'en.json'

        with open(en_file, 'r', encoding='utf-8') as f:
            translations = json.load(f)

        sessions = translations.get('sessions', {})

        required_keys = [
            'resume_guidance_label',
            'resume_guidance_placeholder',
            'to_resume',
        ]

        for key in required_keys:
            assert key in sessions, f"Translation key 'sessions.{key}' missing in en.json"


# ============================================================================
# JavaScript File Tests
# ============================================================================

@pytest.mark.webui
class TestJavaScriptFiles:
    """Tests for JavaScript file accessibility and content."""

    JS_FILES = [
        'i18n.js',
        'sessions.js',
        'utils.js',
        'language-selector.js',
        'preset-editor.js',
    ]

    @pytest.mark.parametrize('js_file', JS_FILES)
    def test_js_file_accessible(self, flask_client, js_file):
        """Test that each JavaScript file is accessible."""
        response = flask_client.get(f'/static/js/{js_file}')

        assert response.status_code == 200, f"JS file {js_file} not accessible"
        assert len(response.data) > 0, f"JS file {js_file} is empty"

    def test_i18n_supports_placeholder_translation(self, flask_client):
        """Test that i18n.js supports data-i18n-placeholder attribute."""
        response = flask_client.get('/static/js/i18n.js')
        content = response.data.decode('utf-8')

        # Check for placeholder translation support
        assert 'data-i18n-placeholder' in content

    def test_sessions_js_has_resume_modal_functions(self, flask_client):
        """Test that sessions.js has resume modal functions."""
        response = flask_client.get('/static/js/sessions.js')
        content = response.data.decode('utf-8')

        required_functions = [
            'openResumeSessionModal',
            'closeResumeSessionModal',
            'submitResumeSession',
        ]

        for func in required_functions:
            assert func in content, f"Function {func} not found in sessions.js"

    def test_sessions_js_exports_resume_functions(self, flask_client):
        """Test that sessions.js exports resume modal functions to window."""
        response = flask_client.get('/static/js/sessions.js')
        content = response.data.decode('utf-8')

        # Check window exports
        assert 'window.openResumeSessionModal' in content or 'openResumeSessionModal' in content
        assert 'window.closeResumeSessionModal' in content or 'closeResumeSessionModal' in content


# ============================================================================
# CSS Class Consistency Tests
# ============================================================================

@pytest.mark.webui
class TestCSSClassConsistency:
    """Tests that CSS classes used in templates are defined in CSS files."""

    def test_session_card_classes_defined(self, flask_client):
        """Test that session-card classes are defined in sessions.css."""
        response = flask_client.get('/static/css/sessions.css')
        content = response.data.decode('utf-8')

        required_classes = [
            '.session-card',
            '.session-header',
            '.session-content',
            '.session-actions',
            '.session-metrics',
            '.session-status',
        ]

        for cls in required_classes:
            assert cls in content, f"CSS class {cls} not defined in sessions.css"

    def test_modal_classes_defined(self, flask_client):
        """Test that modal classes are defined in modals.css."""
        response = flask_client.get('/static/css/modals.css')
        content = response.data.decode('utf-8')

        required_classes = [
            '.modal',
            '.modal-content',
            '.modal-header',
            '.modal-body',
            '.modal-footer',
            '.modal-close',
            '.new-session-modal-content',
        ]

        for cls in required_classes:
            assert cls in content, f"CSS class {cls} not defined in modals.css"

    def test_button_classes_defined(self, flask_client):
        """Test that button classes are defined in buttons.css."""
        response = flask_client.get('/static/css/buttons.css')
        content = response.data.decode('utf-8')

        required_classes = [
            '.btn',
            '.btn-primary',
            '.btn-secondary',
            '.btn-warning',
            '.btn-success',
        ]

        for cls in required_classes:
            assert cls in content, f"CSS class {cls} not defined in buttons.css"

    def test_animation_keyframes_defined(self, flask_client):
        """Test that animation keyframes are defined in animations.css."""
        response = flask_client.get('/static/css/animations.css')
        content = response.data.decode('utf-8')

        required_keyframes = [
            '@keyframes fadeIn',
            '@keyframes slideIn',
            '@keyframes pulse',
            '@keyframes heartbeat',
            '@keyframes dropdown-enter',
        ]

        for keyframe in required_keyframes:
            assert keyframe in content, f"Keyframe {keyframe} not defined in animations.css"


# ============================================================================
# Template Consistency Tests
# ============================================================================

@pytest.mark.webui
class TestTemplateConsistency:
    """Tests for HTML template consistency."""

    def test_base_template_loads_styles(self, flask_client):
        """Test that base template loads styles.css."""
        response = flask_client.get('/en/')
        content = response.data.decode('utf-8')

        # Should load styles.css which imports all component CSS
        assert 'css/styles.css' in content

    def test_base_template_does_not_duplicate_colors(self, flask_client):
        """Test that base template doesn't load colors.css separately."""
        response = flask_client.get('/en/')
        content = response.data.decode('utf-8')

        # Should NOT have a separate colors.css link (it's imported via styles.css)
        # Count occurrences of colors.css in link tags
        import re
        link_colors_count = len(re.findall(r'<link[^>]+colors\.css', content))

        assert link_colors_count == 0, "colors.css should not be loaded separately (imported via styles.css)"

    def test_sessions_page_has_both_modals(self, flask_client):
        """Test sessions page has both New Session and Resume Session modals."""
        response = flask_client.get('/en/')
        content = response.data.decode('utf-8')

        assert 'id="new-session-modal"' in content
        assert 'id="resume-session-modal"' in content

    def test_sessions_page_has_session_grid(self, flask_client):
        """Test sessions page has session grid container."""
        response = flask_client.get('/en/')
        content = response.data.decode('utf-8')

        assert 'id="sessions-grid"' in content
        assert 'class="sessions-grid"' in content or 'sessions-grid' in content
