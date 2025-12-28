"""
WebUI API Test Helpers

Provides common utilities for testing Flask API endpoints.
These helpers reduce boilerplate in API tests and ensure
consistent assertion patterns.
"""

import json
import pytest
from typing import Any, Dict, List, Optional


class APITestHelper:
    """
    Helper class for testing Flask API endpoints.

    Provides convenience methods for common API testing patterns
    including JSON parsing, status assertions, and response validation.
    """

    def __init__(self, client):
        """
        Initialize with Flask test client.

        Args:
            client: Flask test client from flask_client fixture
        """
        self.client = client

    def get_json(self, url: str, expected_status: int = 200) -> Dict[str, Any]:
        """
        Make GET request and parse JSON response.

        Args:
            url: API endpoint URL
            expected_status: Expected HTTP status code

        Returns:
            Parsed JSON response as dictionary

        Raises:
            AssertionError: If status code doesn't match expected
        """
        response = self.client.get(url)
        assert response.status_code == expected_status, \
            f"Expected {expected_status}, got {response.status_code}: {response.data.decode()}"
        return json.loads(response.data)

    def post_json(
        self,
        url: str,
        data: Dict[str, Any] = None,
        expected_status: int = 200
    ) -> Dict[str, Any]:
        """
        Make POST request with JSON body and parse response.

        Args:
            url: API endpoint URL
            data: Request body (will be JSON encoded)
            expected_status: Expected HTTP status code

        Returns:
            Parsed JSON response as dictionary

        Raises:
            AssertionError: If status code doesn't match expected
        """
        response = self.client.post(url, json=data or {})
        assert response.status_code == expected_status, \
            f"Expected {expected_status}, got {response.status_code}: {response.data.decode()}"
        return json.loads(response.data)

    def delete_json(
        self,
        url: str,
        expected_status: int = 200
    ) -> Dict[str, Any]:
        """
        Make DELETE request and parse JSON response.

        Args:
            url: API endpoint URL
            expected_status: Expected HTTP status code

        Returns:
            Parsed JSON response as dictionary

        Raises:
            AssertionError: If status code doesn't match expected
        """
        response = self.client.delete(url)
        assert response.status_code == expected_status, \
            f"Expected {expected_status}, got {response.status_code}: {response.data.decode()}"
        return json.loads(response.data)

    def put_json(
        self,
        url: str,
        data: Dict[str, Any] = None,
        expected_status: int = 200
    ) -> Dict[str, Any]:
        """
        Make PUT request with JSON body and parse response.

        Args:
            url: API endpoint URL
            data: Request body (will be JSON encoded)
            expected_status: Expected HTTP status code

        Returns:
            Parsed JSON response as dictionary

        Raises:
            AssertionError: If status code doesn't match expected
        """
        response = self.client.put(url, json=data or {})
        assert response.status_code == expected_status, \
            f"Expected {expected_status}, got {response.status_code}: {response.data.decode()}"
        return json.loads(response.data)

    # =========================================================================
    # Response Assertion Methods
    # =========================================================================

    def assert_session_list_response(self, data: List) -> None:
        """
        Assert valid session list response structure.

        Args:
            data: Response data (should be list)

        Raises:
            AssertionError: If response structure is invalid
        """
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        for session in data:
            assert 'session_id' in session, "Missing session_id in session"
            assert 'start_time' in session or 'session_metadata' in session, \
                "Missing start_time or session_metadata in session"

    def assert_session_detail_response(self, data: Dict) -> None:
        """
        Assert valid session detail response structure.

        Args:
            data: Response data (should be dict)

        Raises:
            AssertionError: If response structure is invalid
        """
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"
        assert 'session_metadata' in data, "Missing session_metadata"
        assert 'iterations' in data, "Missing iterations"
        assert isinstance(data['iterations'], list), "iterations should be list"

    def assert_error_response(
        self,
        data: Dict,
        expected_message: Optional[str] = None
    ) -> None:
        """
        Assert valid error response structure.

        Args:
            data: Response data (should be dict with 'error' key)
            expected_message: Optional substring to check in error message

        Raises:
            AssertionError: If response structure is invalid
        """
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"
        assert 'error' in data, "Missing 'error' key in error response"
        if expected_message:
            assert expected_message in data['error'], \
                f"Expected '{expected_message}' in error: {data['error']}"

    def assert_success_response(
        self,
        data: Dict,
        expected_message: Optional[str] = None
    ) -> None:
        """
        Assert valid success response structure.

        Args:
            data: Response data
            expected_message: Optional substring to check in message

        Raises:
            AssertionError: If response structure is invalid
        """
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"
        # Check for common success indicators
        success = (
            data.get('status') == 'success' or
            data.get('success') is True or
            'message' in data
        )
        assert success, f"Response doesn't indicate success: {data}"

        if expected_message and 'message' in data:
            assert expected_message in data['message'], \
                f"Expected '{expected_message}' in message: {data['message']}"

    def assert_memory_response(self, data: Dict) -> None:
        """
        Assert valid memory response structure.

        Args:
            data: Response data from /api/sessions/{id}/memory

        Raises:
            AssertionError: If response structure is invalid
        """
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"
        assert 'session_id' in data, "Missing session_id in memory response"
        assert 'memory_categories' in data, "Missing memory_categories"
        assert 'total_items' in data, "Missing total_items"

    def assert_iteration_response(self, data: Dict) -> None:
        """
        Assert valid iteration detail response structure.

        Args:
            data: Response data from /api/sessions/{id}/iteration/{num}

        Raises:
            AssertionError: If response structure is invalid
        """
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"
        assert 'iteration' in data, "Missing iteration number"
        assert 'tool_calls' in data, "Missing tool_calls"

    # =========================================================================
    # Common Test Patterns
    # =========================================================================

    def test_not_found(self, url: str) -> Dict:
        """
        Test that endpoint returns 404 for non-existent resource.

        Args:
            url: API endpoint URL

        Returns:
            Response data (for additional assertions)
        """
        data = self.get_json(url, expected_status=404)
        self.assert_error_response(data)
        return data

    def test_invalid_method(self, url: str, method: str = 'PATCH') -> None:
        """
        Test that endpoint returns 405 for unsupported HTTP method.

        Args:
            url: API endpoint URL
            method: HTTP method to test
        """
        if method == 'PATCH':
            response = self.client.patch(url)
        elif method == 'DELETE':
            response = self.client.delete(url)
        else:
            response = self.client.open(url, method=method)

        assert response.status_code in [405, 404], \
            f"Expected 405/404, got {response.status_code}"


@pytest.fixture
def api_helper(flask_client) -> APITestHelper:
    """
    API test helper fixture.

    Provides convenient methods for testing Flask API endpoints.

    Usage:
        def test_get_sessions(api_helper):
            data = api_helper.get_json('/api/sessions')
            api_helper.assert_session_list_response(data)
    """
    return APITestHelper(flask_client)


# ============================================================================
# Standalone Assertion Functions (for use without fixture)
# ============================================================================

def assert_json_response(response, expected_status: int = 200) -> Dict:
    """
    Parse JSON response and assert status code.

    Args:
        response: Flask response object
        expected_status: Expected HTTP status code

    Returns:
        Parsed JSON as dictionary
    """
    assert response.status_code == expected_status, \
        f"Expected {expected_status}, got {response.status_code}: {response.data.decode()}"
    return json.loads(response.data)


def assert_contains_keys(data: Dict, keys: List[str]) -> None:
    """
    Assert dictionary contains all specified keys.

    Args:
        data: Dictionary to check
        keys: List of required keys

    Raises:
        AssertionError: If any key is missing
    """
    for key in keys:
        assert key in data, f"Missing required key: {key}"
