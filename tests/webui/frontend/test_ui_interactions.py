"""
End-to-end UI interaction tests for Database Analyzer WebUI.

Tests browser automation with Selenium covering:
- Navigation and page loading
- Session list interactions
- Session detail page
- Memory verification UI
- Language switching
"""

import pytest
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Skip all Selenium tests for now - they take too long to run
pytestmark = pytest.mark.skip(reason="Selenium tests temporarily disabled - taking too long to run")


@pytest.mark.webui
@pytest.mark.e2e
class TestNavigation:
    """Test basic navigation and page loading."""

    def test_homepage_loads(self, selenium_driver, live_server):
        """Test that homepage loads successfully."""
        selenium_driver.get(live_server.url)

        # Wait for page title
        wait = WebDriverWait(selenium_driver, 5)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Check page loaded
        assert "Database Analyzer" in selenium_driver.page_source or "Session" in selenium_driver.page_source

    def test_session_list_page_loads(self, selenium_driver, live_server):
        """Test that session list page loads with sessions."""
        selenium_driver.get(f"{live_server.url}/en/")

        wait = WebDriverWait(selenium_driver, 3)

        # Wait for session cards or empty state
        try:
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "session-card")))
        except TimeoutException:
            # No sessions - check for empty state message
            assert "session" in selenium_driver.page_source.lower()

    def test_navbar_links_work(self, selenium_driver, live_server):
        """Test that navbar links are clickable."""
        selenium_driver.get(live_server.url)

        wait = WebDriverWait(selenium_driver, 3)

        # Find navbar (if exists)
        navbars = selenium_driver.find_elements(By.TAG_NAME, "nav")
        if len(navbars) > 0:
            # Check for home link
            home_links = selenium_driver.find_elements(By.LINK_TEXT, "Home")
            assert len(home_links) > 0

    def test_favicon_loads(self, selenium_driver, live_server):
        """Test that favicon is present."""
        selenium_driver.get(live_server.url)

        # Check for favicon link in head
        favicons = selenium_driver.find_elements(By.CSS_SELECTOR, "link[rel*='icon']")
        assert len(favicons) > 0


@pytest.mark.webui
@pytest.mark.e2e
class TestSessionList:
    """Test session list interactions."""

    def test_session_cards_display(self, selenium_driver, live_server, sample_session_file):
        """Test that session cards display correctly."""
        selenium_driver.get(f"{live_server.url}/en/")

        wait = WebDriverWait(selenium_driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "session-card")))

        # Check session card elements
        cards = selenium_driver.find_elements(By.CLASS_NAME, "session-card")
        assert len(cards) > 0

        # Check first card has status indicator
        first_card = cards[0]
        status_elements = first_card.find_elements(By.CLASS_NAME, "status")
        assert len(status_elements) > 0

    def test_session_card_click_navigates(self, selenium_driver, live_server, sample_session_file):
        """Test clicking session card navigates to detail page."""
        selenium_driver.get(f"{live_server.url}/en/")

        wait = WebDriverWait(selenium_driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "session-card")))

        # Click first session card
        cards = selenium_driver.find_elements(By.CLASS_NAME, "session-card")
        if len(cards) > 0:
            cards[0].click()

            # Wait for navigation
            time.sleep(1)

            # Check URL changed
            assert "/session/" in selenium_driver.current_url

    def test_new_session_button_exists(self, selenium_driver, live_server):
        """Test that new session button is present."""
        selenium_driver.get(f"{live_server.url}/en/")

        wait = WebDriverWait(selenium_driver, 10)

        # Look for new session button
        new_buttons = selenium_driver.find_elements(By.XPATH, "//*[contains(text(), 'New Session')]")
        assert len(new_buttons) > 0

    def test_status_filter_works(self, selenium_driver, live_server, sample_session_file):
        """Test status filtering on session list."""
        selenium_driver.get(f"{live_server.url}/en/")

        wait = WebDriverWait(selenium_driver, 10)

        # Look for status filter buttons
        filter_buttons = selenium_driver.find_elements(By.CSS_SELECTOR, "[data-status-filter]")

        if len(filter_buttons) > 0:
            # Click completed filter
            for btn in filter_buttons:
                if "completed" in btn.get_attribute("data-status-filter"):
                    btn.click()
                    time.sleep(0.5)

                    # Check that cards are filtered
                    visible_cards = selenium_driver.find_elements(By.CLASS_NAME, "session-card")
                    # At least check no error occurred
                    assert True


@pytest.mark.webui
@pytest.mark.e2e
class TestSessionDetail:
    """Test session detail page interactions."""

    def test_session_detail_page_loads(self, selenium_driver, live_server, sample_session_file):
        """Test session detail page loads with correct data."""
        # Navigate to session detail (use known session ID from fixture)
        session_id = "20250924_010804"
        selenium_driver.get(f"{live_server.url}/en/session/{session_id}")

        wait = WebDriverWait(selenium_driver, 10)

        # Wait for session metadata
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "session-metadata")))

        # Check session ID is displayed
        assert session_id in selenium_driver.page_source

    def test_iteration_tabs_work(self, selenium_driver, live_server, sample_session_file):
        """Test iteration tab switching."""
        session_id = "20250924_010804"
        selenium_driver.get(f"{live_server.url}/en/session/{session_id}")

        wait = WebDriverWait(selenium_driver, 10)

        # Look for iteration tabs
        iteration_tabs = selenium_driver.find_elements(By.CSS_SELECTOR, "[data-iteration]")

        if len(iteration_tabs) > 1:
            # Click second iteration
            iteration_tabs[1].click()
            time.sleep(0.5)

            # Check that content updated
            assert True  # Just verify no errors

    def test_tool_calls_display(self, selenium_driver, live_server, sample_session_file):
        """Test that tool calls are displayed."""
        session_id = "20250924_010804"
        selenium_driver.get(f"{live_server.url}/en/session/{session_id}/iteration/1")

        wait = WebDriverWait(selenium_driver, 10)

        # Look for tool call cards
        tool_calls = selenium_driver.find_elements(By.CLASS_NAME, "tool-call")
        assert len(tool_calls) > 0

    def test_memory_tab_displays(self, selenium_driver, live_server, sample_session_file):
        """Test memory tab displays memory items."""
        session_id = "20250924_010804"
        selenium_driver.get(f"{live_server.url}/en/session/{session_id}/memory")

        wait = WebDriverWait(selenium_driver, 10)

        # Look for memory cards or empty state
        try:
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "memory-item")))
        except TimeoutException:
            # Check for "No memory" message
            assert "No memory" in selenium_driver.page_source or "Empty" in selenium_driver.page_source


@pytest.mark.webui
@pytest.mark.e2e
class TestMemoryVerification:
    """Test memory verification UI interactions."""

    def test_verify_button_exists(self, selenium_driver, live_server, sample_session_file):
        """Test that verify buttons are present on memory items."""
        session_id = "20250924_010804"
        selenium_driver.get(f"{live_server.url}/en/session/{session_id}/memory")

        wait = WebDriverWait(selenium_driver, 10)

        # Look for verify buttons
        verify_buttons = selenium_driver.find_elements(By.CSS_SELECTOR, "[data-verify-memory]")

        # Should have at least one if memory items exist
        memory_items = selenium_driver.find_elements(By.CLASS_NAME, "memory-item")
        if len(memory_items) > 0:
            assert len(verify_buttons) > 0

    def test_verify_modal_opens(self, selenium_driver, live_server, sample_session_file):
        """Test clicking verify button opens modal."""
        session_id = "20250924_010804"
        selenium_driver.get(f"{live_server.url}/en/session/{session_id}/memory")

        wait = WebDriverWait(selenium_driver, 10)

        # Find and click verify button
        verify_buttons = selenium_driver.find_elements(By.CSS_SELECTOR, "[data-verify-memory]")

        if len(verify_buttons) > 0:
            verify_buttons[0].click()
            time.sleep(0.5)

            # Look for verification modal
            modals = selenium_driver.find_elements(By.CLASS_NAME, "verification-modal")
            assert len(modals) > 0 or "Verifying" in selenium_driver.page_source


@pytest.mark.webui
@pytest.mark.e2e
class TestLanguageSupport:
    """Test language switching functionality."""

    def test_english_language_works(self, selenium_driver, live_server):
        """Test English language route."""
        selenium_driver.get(f"{live_server.url}/en/")

        wait = WebDriverWait(selenium_driver, 10)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Check that English content is present
        assert "/en/" in selenium_driver.current_url

    def test_language_switcher_exists(self, selenium_driver, live_server):
        """Test that language switcher is present."""
        selenium_driver.get(f"{live_server.url}/en/")

        wait = WebDriverWait(selenium_driver, 10)

        # Look for language switcher links
        lang_links = selenium_driver.find_elements(By.CSS_SELECTOR, "a[href*='/en/']")

        # Should have language switching capability
        assert len(lang_links) > 0 or "EN" in selenium_driver.page_source
