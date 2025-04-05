# /Users/junluo/Documents/auto_work_publishment_for_wechat_article/src/api/base_client.py

"""
Abstract Base Class for API Clients

Purpose:
Defines a common structure and basic HTTP request functionality
for different API clients used in the application (e.g., WeChat, DeepSeek).
Promotes consistency and code reuse.

Dependencies:
- abc (standard Python library)
- requests (external library)
- typing (standard Python library)
- src.utils.logger

Expected Input: Subclasses must implement abstract methods.
Expected Output: Provides a foundational class for API interaction.
"""

from abc import ABC, abstractmethod
import requests
import time
from typing import Optional, Dict, Any, Tuple

from src.utils.logger import log

class BaseApiClient(ABC):
    """
    Abstract base class for API clients.

    Attributes:
        base_url (str): The base URL for the API endpoint.
        api_key (Optional[str]): The API key, if required.
        session (requests.Session): A session object for persistent connections.
    """

    def __init__(self, base_url: str, api_key: Optional[str] = None, default_timeout: int = 30):
        """
        Initializes the BaseApiClient.

        Args:
            base_url (str): The base URL for the API.
            api_key (Optional[str]): API key for authentication, if needed.
            default_timeout (int): Default timeout for requests in seconds.
        """
        if not base_url:
            raise ValueError("Base URL cannot be empty.")
        self.base_url = base_url.rstrip('/') # Ensure no trailing slash
        self.api_key = api_key
        self.session = requests.Session() # Use a session for potential performance benefits
        self.default_timeout = default_timeout
        log.debug(f"{self.__class__.__name__} initialized with base URL: {self.base_url}")

    @abstractmethod
    def _authenticate(self) -> Dict[str, Any]:
        """
        Abstract method for handling authentication.
        Should return headers or parameters needed for authenticated requests.
        Subclasses must implement this. For APIs without specific auth steps
        (e.g., key in header), this can return an empty dict or handle it
        within _make_request.
        """
        pass

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json_payload: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        retries: int = 3,
        backoff_factor: float = 0.5
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Makes an HTTP request to the specified API endpoint with retry logic.

        Args:
            method (str): HTTP method (e.g., 'GET', 'POST').
            endpoint (str): API endpoint path (relative to base_url).
            params (Optional[Dict[str, Any]]): URL parameters.
            data (Optional[Dict[str, Any]]): Form data payload.
            json_payload (Optional[Dict[str, Any]]): JSON payload.
            files (Optional[Dict[str, Any]]): Files to upload.
            headers (Optional[Dict[str, str]]): Custom headers.
            timeout (Optional[int]): Request timeout in seconds. Overrides default.
            retries (int): Number of times to retry on failure.
            backoff_factor (float): Factor to determine delay between retries (delay = backoff_factor * (2 ** retry_attempt)).

        Returns:
            Tuple[Optional[Dict[str, Any]], Optional[str]]:
                - The JSON response dictionary if successful and response is JSON.
                - An error message string if the request fails after retries or response is not JSON.
                  Returns (None, None) for non-JSON success.
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        request_timeout = timeout if timeout is not None else self.default_timeout
        merged_headers = self.session.headers.copy()
        if headers:
            merged_headers.update(headers)

        # Note: Authentication handling might need adjustment based on API
        # It could be applied here, or within specific client methods.
        # auth_headers = self._authenticate()
        # merged_headers.update(auth_headers)

        last_exception = None

        for attempt in range(retries + 1):
            try:
                log.debug(f"Request Attempt {attempt + 1}/{retries + 1}: {method} {url}")
                log.debug(f"Params: {params}, JSON: {json_payload}, Data: {data}, Files: {files is not None}")

                response = self.session.request(
                    method=method.upper(),
                    url=url,
                    params=params,
                    data=data,
                    json=json_payload,
                    files=files,
                    headers=merged_headers,
                    timeout=request_timeout
                )
                response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

                log.debug(f"Request successful: Status {response.status_code}")
                try:
                    # Try to parse JSON, but don't fail if it's not JSON
                    json_response = response.json()
                    log.debug(f"Response JSON: {json_response}")
                    return json_response, None
                except requests.exceptions.JSONDecodeError:
                    log.debug("Response was not JSON.")
                    # Return raw content if needed, or just indicate success without JSON
                    # return response.content, None # Example
                    return None, None # Success, but not JSON

            except requests.exceptions.Timeout as e:
                last_exception = e
                log.warning(f"Request timed out: {e}")
            except requests.exceptions.ConnectionError as e:
                last_exception = e
                log.warning(f"Connection error: {e}")
            except requests.exceptions.HTTPError as e:
                last_exception = e
                log.error(f"HTTP error: {e.response.status_code} {e.response.reason} - {e.response.text}")
                # Stop retrying on client errors (4xx) unless specifically designed otherwise
                if 400 <= e.response.status_code < 500:
                     # Check specific WeChat/DeepSeek error codes within response text/json if needed
                    return None, f"HTTP {e.response.status_code}: {e.response.text}"
            except requests.exceptions.RequestException as e:
                last_exception = e
                log.error(f"An unexpected error occurred during request: {e}")

            # If it's not the last attempt, wait before retrying
            if attempt < retries:
                delay = backoff_factor * (2 ** attempt)
                log.info(f"Retrying in {delay:.2f} seconds...")
                time.sleep(delay)

        error_message = f"Request failed after {retries + 1} attempts: {last_exception}"
        log.error(error_message)
        return None, error_message

    def close_session(self):
        """Closes the underlying requests session."""
        log.debug(f"Closing session for {self.__class__.__name__}")
        self.session.close()