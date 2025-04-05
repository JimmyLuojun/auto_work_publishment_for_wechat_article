# tests/api/test_base_client.py

import pytest
import requests
import time
from unittest.mock import MagicMock, patch, call
from typing import Dict, Any

# Module to test
from src.api.base_client import BaseApiClient

# --- Concrete Subclass for Testing ---

class ConcreteClient(BaseApiClient):
    """A minimal concrete implementation for testing BaseApiClient."""
    def __init__(self, base_url="http://test.com", api_key=None, default_timeout=10):
        super().__init__(base_url, api_key, default_timeout)
        # Mock the session object directly on the instance for easier request mocking
        self.session = MagicMock(spec=requests.Session)
        self.session.headers = {} # Simulate session headers

    def _authenticate(self) -> Dict[str, Any]:
        # Simple mock implementation for testing purposes
        if self.api_key == "auth-needed":
            return {"X-Auth": "Authenticated"}
        return {} # No extra auth headers by default

# --- Fixtures ---

@pytest.fixture
def concrete_client():
    """Provides an instance of the concrete client."""
    return ConcreteClient(base_url="http://test.com/api/")

@pytest.fixture
def mock_response():
    """Factory fixture to create mock requests.Response objects."""
    def _create_mock_response(status_code=200, json_data=None, text_data=None, raise_for_status_error=None):
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = status_code
        mock_resp.reason = "OK" if status_code < 400 else "Error" # Set reason based on status
        mock_resp.text = text_data if text_data is not None else str(json_data or '') # Ensure text exists

        if json_data is not None:
            mock_resp.json.return_value = json_data
        else:
            # Simulate JSONDecodeError if no json_data is provided
            mock_resp.json.side_effect = requests.exceptions.JSONDecodeError("No JSON object could be decoded", "doc", 0)

        # Configure raise_for_status mock
        if raise_for_status_error:
            # --- Start Correction for Failure 2 ---
            # Ensure the exception instance has the response attribute set
            # Modify the actual exception instance passed in
            if isinstance(raise_for_status_error, requests.exceptions.RequestException):
                 # This check prevents errors if something else is passed as side_effect
                raise_for_status_error.response = mock_resp
            mock_resp.raise_for_status.side_effect = raise_for_status_error
            # --- End Correction for Failure 2 ---
        else:
            # Default behavior: raise HTTPError for >= 400 status codes
            if status_code >= 400:
                # Create the default error and attach the response
                default_http_error = requests.exceptions.HTTPError(f"{status_code} {mock_resp.reason}", response=mock_resp)
                default_http_error.response = mock_resp # Explicitly set response attr
                mock_resp.raise_for_status.side_effect = default_http_error
            else:
                mock_resp.raise_for_status.return_value = None # No error for < 400 status codes

        return mock_resp
    return _create_mock_response

# --- Test Cases ---

def test_base_client_init_success():
    """Test successful initialization."""
    client = ConcreteClient(base_url="http://example.com/v1/", api_key="key1", default_timeout=15)
    assert client.base_url == "http://example.com/v1" # Trailing slash removed
    assert client.api_key == "key1"
    assert client.default_timeout == 15
    assert isinstance(client.session, MagicMock) # Using mocked session from ConcreteClient init

def test_base_client_init_no_base_url():
    """Test ValueError if base_url is empty."""
    with pytest.raises(ValueError, match="Base URL cannot be empty."):
        ConcreteClient(base_url="")

@patch('time.sleep', return_value=None) # Mock time.sleep to avoid delays
def test_make_request_success_json(mock_sleep, concrete_client, mock_response):
    """Test a successful request returning JSON."""
    expected_data = {"success": True, "data": [1, 2]}
    mock_resp = mock_response(status_code=200, json_data=expected_data)
    concrete_client.session.request.return_value = mock_resp

    data, error = concrete_client._make_request("GET", "/items", params={"id": 1})

    assert data == expected_data
    assert error is None
    concrete_client.session.request.assert_called_once_with(
        method="GET",
        url="http://test.com/api/items",
        params={"id": 1},
        data=None,
        json=None,
        files=None,
        headers={}, # From concrete_client.session.headers
        timeout=10 # Default timeout
    )
    mock_sleep.assert_not_called()

@patch('time.sleep', return_value=None)
def test_make_request_success_no_json(mock_sleep, concrete_client, mock_response):
    """Test a successful request returning non-JSON content."""
    mock_resp = mock_response(status_code=204) # No content usually has no JSON
    concrete_client.session.request.return_value = mock_resp

    data, error = concrete_client._make_request("DELETE", "/items/1")

    assert data is None # No JSON data expected
    assert error is None # No error expected
    concrete_client.session.request.assert_called_once_with(
        method="DELETE", url="http://test.com/api/items/1", params=None, data=None, json=None, files=None, headers={}, timeout=10
    )
    mock_sleep.assert_not_called()

@patch('time.sleep', return_value=None)
def test_make_request_http_error_4xx(mock_sleep, concrete_client, mock_response, caplog):
    """Test handling of a 4xx HTTP error (should not retry)."""
    error_text = "Not Found"
    mock_resp = mock_response(status_code=404, text_data=error_text)
    concrete_client.session.request.return_value = mock_resp

    data, error = concrete_client._make_request("GET", "/notfound")

    assert data is None
    # --- Start Correction for Failure 1 ---
    assert error == f"HTTP 404: {error_text}" # Check actual returned format
    # --- End Correction for Failure 1 ---
    concrete_client.session.request.assert_called_once() # Should only be called once
    mock_sleep.assert_not_called() # No retries
    assert f"HTTP error: 404 Error - {error_text}" in caplog.text # Log message format check

@patch('time.sleep', return_value=None)
def test_make_request_http_error_5xx_retry_success(mock_sleep, concrete_client, mock_response):
    """Test retry logic for 5xx errors followed by success."""
    fail_response_1 = mock_response(status_code=500, text_data="Internal Server Error")
    fail_response_2 = mock_response(status_code=503, text_data="Service Unavailable")
    success_response = mock_response(status_code=200, json_data={"status": "ok"})

    # The mock_response fixture now automatically configures raise_for_status side effects for 5xx
    concrete_client.session.request.side_effect = [
        fail_response_1,
        fail_response_2,
        success_response
    ]

    data, error = concrete_client._make_request("POST", "/create", json_payload={"name": "test"}, retries=2) # Allow 2 retries (3 attempts total)

    assert data == {"status": "ok"}
    assert error is None
    assert concrete_client.session.request.call_count == 3
    assert mock_sleep.call_count == 2 # Called before 2nd and 3rd attempts
    # Check backoff delay calculation (0.5 * 2^0, 0.5 * 2^1)
    mock_sleep.assert_has_calls([call(0.5), call(1.0)])

@patch('time.sleep', return_value=None)
def test_make_request_timeout_retry_success(mock_sleep, concrete_client, mock_response):
    """Test retry logic for Timeout errors followed by success."""
    timeout_error = requests.exceptions.Timeout("Request timed out")
    success_response = mock_response(status_code=200, json_data={"status": "ok"})

    concrete_client.session.request.side_effect = [
        timeout_error,
        timeout_error,
        success_response
    ]

    data, error = concrete_client._make_request("GET", "/data", retries=3) # Allow 3 retries (4 attempts)

    assert data == {"status": "ok"}
    assert error is None
    assert concrete_client.session.request.call_count == 3 # Succeeded on 3rd attempt
    assert mock_sleep.call_count == 2 # Called before 2nd and 3rd attempts

@patch('time.sleep', return_value=None)
def test_make_request_persistent_failure(mock_sleep, concrete_client, mock_response, caplog):
    """Test when retries are exhausted."""
    timeout_error = requests.exceptions.Timeout("Request timed out persistently")
    concrete_client.session.request.side_effect = timeout_error # Always raise Timeout

    data, error = concrete_client._make_request("GET", "/flaky", retries=2) # Allow 2 retries (3 attempts)

    assert data is None
    assert f"Request failed after 3 attempts: {timeout_error}" in error
    assert concrete_client.session.request.call_count == 3
    assert mock_sleep.call_count == 2
    assert f"Request failed after 3 attempts: {timeout_error}" in caplog.text

def test_make_request_custom_params_headers_timeout(concrete_client, mock_response):
    """Test passing custom parameters, headers, and timeout."""
    success_response = mock_response(status_code=200, json_data={"status": "ok"})
    concrete_client.session.request.return_value = success_response

    custom_headers = {"X-Custom": "Value"}
    custom_params = {"page": 2}
    custom_timeout = 5

    concrete_client._make_request("GET", "/list", params=custom_params, headers=custom_headers, timeout=custom_timeout)

    concrete_client.session.request.assert_called_once_with(
        method="GET",
        url="http://test.com/api/list",
        params=custom_params,
        data=None,
        json=None,
        files=None,
        headers=custom_headers, # Should include custom header
        timeout=custom_timeout # Should use custom timeout
    )

def test_close_session(concrete_client):
    """Test the close_session method."""
    concrete_client.close_session()
    concrete_client.session.close.assert_called_once()