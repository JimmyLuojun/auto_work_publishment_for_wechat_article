# -*- coding: utf-8 -*-
"""
base_client.py - Abstract Base Class for API Clients.

Responsibilities:
- Provide a common foundation for specific API client implementations (e.g., WeChat, OpenAI).
- Handle common HTTP request logic using the 'requests' library.
- Manage HTTP sessions for connection pooling and potential cookie persistence.
- Implement configurable request timeouts.
- Offer optional, configurable retry mechanisms for transient network errors or specific HTTP statuses.
- Define standardized error handling and custom exception types.
- Centralize logging for API interactions.

Dependencies:
- requests: For making HTTP requests and session management.
- requests.adapters: For mounting custom adapters (like retry).
- urllib3.util.retry: For configuring retry logic.
- logging: For logging requests, responses, and errors.
- typing: For type hinting.
- abc: For defining an Abstract Base Class (optional but good practice).

Expected Input (for subclasses): Configuration details like base URL, auth credentials.
Expected Output (from methods): Parsed API responses (e.g., dictionaries from JSON).
                                Raises specific APIClientError exceptions on failure.
"""

import logging
from abc import ABC, abstractmethod # Optional: Use ABC for stricter interface definition
from typing import Any, Dict, Optional, Union, Type

# Third-party libraries
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# --- Custom Exception Hierarchy ---

class APIClientError(Exception):
    """Base exception for all API client errors."""
    pass

class APIRequestError(APIClientError):
    """Exception for errors related to constructing or sending the request
       (e.g., connection errors, timeouts before response)."""
    def __init__(self, message: str, original_exception: Optional[Exception] = None):
        super().__init__(message)
        self.original_exception = original_exception

class APIResponseError(APIClientError):
    """Exception for errors related to the API's response
       (e.g., non-2xx status codes, unexpected response format)."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[Any] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body # Store the raw or parsed body for debugging

# --- Base API Client Class ---

class BaseAPIClient(ABC): # Inherit from ABC if using abstract methods
    """
    Abstract base class providing common functionality for API clients.

    Subclasses should implement API-specific logic, such as:
    - Handling specific authentication methods.
    - Parsing specific API error formats within `_handle_api_error`.
    - Defining methods for specific API endpoints.
    """

    DEFAULT_TIMEOUT: float = 15.0  # Default request timeout in seconds
    DEFAULT_RETRY_STRATEGY = Retry(
        total=3,  # Total number of retries
        backoff_factor=0.5,  # Exponential backoff factor (e.g., 0.5s, 1s, 2s)
        status_forcelist=[429, 500, 502, 503, 504],  # HTTP status codes to retry on
        allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"] # Retry on common methods
    )

    def __init__(
        self,
        base_url: str,
        session: Optional[requests.Session] = None,
        timeout: float = DEFAULT_TIMEOUT,
        retry_strategy: Optional[Retry] = DEFAULT_RETRY_STRATEGY,
        default_headers: Optional[Dict[str, str]] = None,
    ):
        """
        Initializes the BaseAPIClient.

        Args:
            base_url (str): The base URL for the API (e.g., "https://api.example.com/v1").
                            Should generally not end with a slash.
            session (Optional[requests.Session]): An existing requests Session object.
                                                  If None, a new one is created.
            timeout (float): Default timeout for requests in seconds.
            retry_strategy (Optional[Retry]): A urllib3 Retry configuration object.
                                             Set to None to disable retries.
            default_headers (Optional[Dict[str, str]]): Default headers to include
                                                        in every request.
        """
        if not base_url:
            raise ValueError("base_url cannot be empty.")
        self.base_url = base_url.rstrip('/') # Ensure no trailing slash

        self.timeout = timeout
        self.session = session or requests.Session()

        # Configure default headers
        self.session.headers.update({
            'Accept': 'application/json', # Common default
            'Content-Type': 'application/json', # Common default for POST/PUT
        })
        if default_headers:
            self.session.headers.update(default_headers)
            logger.debug(f"Set default session headers: {default_headers}")

        # Configure retry strategy
        self.retry_strategy = retry_strategy
        if self.retry_strategy:
            adapter = HTTPAdapter(max_retries=self.retry_strategy)
            # Mount the adapter for both http and https prefixes
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)
            logger.info(f"Configured retry strategy: {self.retry_strategy}")
        else:
             logger.info("Retries disabled for this client instance.")


    def _build_url(self, endpoint: str) -> str:
        """Constructs the full API endpoint URL."""
        # Ensure endpoint doesn't have leading slash if base_url is properly set
        endpoint_cleaned = endpoint.lstrip('/')
        return f"{self.base_url}/{endpoint_cleaned}"

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Union[Dict[str, Any], str, bytes]] = None,
        json: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        files: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        **kwargs # Allow passing other requests options like 'stream', 'verify'
    ) -> Any:
        """
        Performs an HTTP request to the API.

        Args:
            method (str): HTTP method (e.g., 'GET', 'POST').
            endpoint (str): API endpoint path (e.g., '/users', 'status').
            params (Optional[Dict[str, Any]]): URL query parameters.
            data (Optional[Union[Dict[str, Any], str, bytes]]): Form data payload.
                                                               Use for form-encoded data.
            json (Optional[Any]): JSON payload. Automatically sets Content-Type header.
                                  If 'data' is also provided, 'json' takes precedence.
            headers (Optional[Dict[str, str]]): Additional headers for this request.
                                                These override session default headers.
            files (Optional[Dict[str, Any]]): Dictionary for multipart file uploads.
            timeout (Optional[float]): Specific timeout for this request (overrides default).
            **kwargs: Additional keyword arguments passed directly to requests.request.

        Returns:
            Any: The parsed JSON response if successful and content type is JSON.
                 Returns the raw Response object for non-JSON or failed parsing.

        Raises:
            APIRequestError: For connection errors, timeouts, or invalid request setup.
            APIResponseError: For non-2xx HTTP status codes or response parsing issues.
            APIClientError: For other client-related errors.
        """
        full_url = self._build_url(endpoint)
        request_timeout = timeout if timeout is not None else self.timeout

        # Prepare headers: Merge session defaults with request-specific headers
        request_headers = self.session.headers.copy()
        if headers:
            request_headers.update(headers)

        # Log request details (be careful with sensitive data in params/json/data)
        # Consider masking sensitive fields if necessary before logging
        log_params = params or {}
        log_payload_summary = f"JSON: {str(json)[:100]}..." if json else f"Data: {str(data)[:100]}..." if data else "None"
        logger.info(f"Sending Request: {method} {full_url}")
        logger.debug(f" > Params: {log_params}")
        logger.debug(f" > Headers: {request_headers}") # Headers might contain auth tokens! Mask if needed.
        logger.debug(f" > Payload: {log_payload_summary}")
        logger.debug(f" > Timeout: {request_timeout}")
        logger.debug(f" > Files: {list(files.keys()) if files else 'None'}")

        response: Optional[requests.Response] = None
        try:
            response = self.session.request(
                method=method,
                url=full_url,
                params=params,
                data=data,
                json=json,
                headers=request_headers,
                files=files,
                timeout=request_timeout,
                **kwargs
            )

            logger.info(f"Received Response: {response.status_code} {response.reason} from {method} {full_url}")
            logger.debug(f" > Response Headers: {response.headers}")

            # Check for HTTP errors (4xx or 5xx)
            response.raise_for_status() # Raises requests.exceptions.HTTPError for non-2xx codes

            # Attempt to parse JSON response if applicable
            try:
                # Handle cases with empty response body or non-json content type gracefully
                if response.content and 'application/json' in response.headers.get('Content-Type', '').lower():
                    parsed_response = response.json()
                    logger.debug(f" > Parsed Response JSON: {str(parsed_response)[:500]}...") # Log truncated JSON
                    return parsed_response
                elif response.content:
                    logger.debug(" > Response is not JSON or content is empty, returning raw response content.")
                    # Depending on needs, you might return response.text or response.content
                    return response.content # Or response.text
                else:
                     logger.debug(" > Response content is empty.")
                     return None # Return None for empty successful responses

            except requests.exceptions.JSONDecodeError as e:
                logger.error(f"Failed to decode JSON response from {full_url}: {e}", exc_info=True)
                logger.debug(f" > Raw Response Text: {response.text[:500]}...")
                raise APIResponseError(
                    f"Failed to decode JSON response: {e}",
                    status_code=response.status_code,
                    response_body=response.text # Provide raw text for debugging
                )

        except requests.exceptions.Timeout as e:
            logger.error(f"Request timed out after {request_timeout}s: {method} {full_url} - {e}", exc_info=True)
            raise APIRequestError(f"Request timed out: {e}", original_exception=e)
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error during request: {method} {full_url} - {e}", exc_info=True)
            raise APIRequestError(f"Connection error: {e}", original_exception=e)
        except requests.exceptions.HTTPError as e:
            # This catches non-2xx status codes after raise_for_status()
            status_code = response.status_code if response else None
            response_body = response.text if response else None # Get text if available
            logger.warning(f"HTTP Error {status_code} received from {method} {full_url}: {e}")
            logger.debug(f" > Failing Response Body: {response_body[:500] if response_body else 'N/A'}...")
            # Allow subclasses to potentially parse the specific API error format
            return self._handle_api_error(response, e)

        except requests.exceptions.RequestException as e:
            # Catch other potential requests exceptions
            logger.error(f"An unexpected requests error occurred: {method} {full_url} - {e}", exc_info=True)
            raise APIRequestError(f"An unexpected requests error occurred: {e}", original_exception=e)
        except Exception as e:
             # Catch any other non-requests errors during the process
             logger.exception(f"An unexpected error occurred in _request: {method} {full_url} - {e}")
             raise APIClientError(f"An unexpected error occurred: {e}")


    def _handle_api_error(self, response: requests.Response, http_error: requests.exceptions.HTTPError) -> Any:
        """
        Handles HTTP errors, allowing subclasses to parse specific API error formats.

        This base implementation attempts to parse the error response as JSON and
        raises a generic APIResponseError. Subclasses should override this method
        to parse their specific error structures (e.g., {"error": {"code": ..., "message": ...}})
        and potentially raise more specific custom exceptions.

        Args:
            response (requests.Response): The raw Response object.
            http_error (requests.exceptions.HTTPError): The original HTTPError raised.

        Returns:
            Should typically raise an exception. Returning a value indicates the
            error was handled in a non-exceptional way (less common).

        Raises:
            APIResponseError: Default exception raised if subclass doesn't override or handle.
        """
        status_code = response.status_code
        try:
            # Try to get more details from the response body (assuming JSON error format)
            error_details = response.json()
            message = f"API returned HTTP {status_code}. Details: {error_details}"
            logger.debug(f"Parsed API error details: {error_details}")
        except requests.exceptions.JSONDecodeError:
            # If body isn't JSON or is empty
            error_details = response.text
            message = f"API returned HTTP {status_code} with non-JSON body: {error_details[:200]}..." # Log truncated text

        # Raise the standard response error by default. Subclasses can override
        # this method to parse `error_details` and raise more specific errors.
        raise APIResponseError(
            message=message,
            status_code=status_code,
            response_body=error_details # Store parsed details or raw text
        ) from http_error # Chain the exception


    def close_session(self):
        """Closes the underlying requests Session."""
        logger.info("Closing API client session.")
        self.session.close()

    def __enter__(self):
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager, ensuring session is closed."""
        self.close_session()


# --- Explanation ---
# Purpose: This `BaseAPIClient` provides a reusable and robust foundation for interacting
#          with various RESTful APIs. It centralizes common logic like session handling,
#          request execution, timeouts, retries, basic error handling, and logging.
# Design Choices:
# - **Session Management:** Uses `requests.Session` for performance benefits (connection
#   pooling, keep-alive) and managing default headers or cookies.
# - **Centralized Request Method (`_request`):** All API calls go through this private
#   method, ensuring consistent URL building, logging, timeout application, header merging,
#   and error handling.
# - **Configurable Retries:** Integrates with `urllib3.util.retry` via `requests.adapters.HTTPAdapter`
#   to automatically retry requests on transient network issues or specific server errors (e.g., 503),
#   improving resilience. This is optional and configurable.
# - **Custom Exceptions:** Defines a clear exception hierarchy (`APIClientError`, `APIRequestError`,
#   `APIResponseError`) making it easier for calling code to catch specific types of failures.
# - **Error Handling Hook (`_handle_api_error`):** Provides a standardized way to handle non-2xx
#   responses. The base implementation raises a generic error, but subclasses (like `WeChatAPIClient`)
#   *should override* this method to parse the *specific error message format* returned by their API
#   and potentially raise more specific, informative exceptions based on API error codes.
# - **Context Manager:** Implements `__enter__` and `__exit__` to allow using the client
#   with a `with` statement, ensuring the session is always closed properly.
# - **Logging:** Includes INFO level logging for requests/responses and DEBUG level for more details
#   (headers, payload snippets, parsed responses), aiding in debugging. Careful logging of potentially
#   sensitive data (headers, payloads) is important - masking might be needed in production.
# - **ABC (Optional):** Marked as inheriting from `ABC`. If you define `@abstractmethod` for methods
#   that subclasses *must* implement (like perhaps `_authenticate_request` if you added it),
#   this provides a stricter contract.
# How Subclasses Use It:
# - `MySpecificClient(BaseAPIClient):`
# - Call `super().__init__(base_url="...", ...)` in their `__init__`.
# - Implement methods for specific endpoints (e.g., `get_user(user_id)`). Inside these methods:
#     - Prepare specific params, data, json payloads.
#     - Handle authentication (e.g., adding an 'Authorization' header before calling `_request`).
#     - Call `self._request('GET', f'/users/{user_id}', ...)`.
# - Optionally override `_handle_api_error` to parse errors like `{"error_code": 123, "message": "..."}`
#   from the specific API and raise custom exceptions.
# Improvements/Alternatives:
# - **Authentication:** Could add more structured support for common auth patterns (e.g., helper
#   methods for Bearer tokens, API key headers) or use libraries like `requests-oauthlib`.
# - **Async Support:** Create an `AsyncBaseAPIClient` using `httpx` or `aiohttp` for asynchronous applications.
# - **Response Models:** Use libraries like Pydantic to parse JSON responses into typed data models
#   instead of returning raw dictionaries.
# - **Rate Limiting:** Add explicit handling for API rate limit headers (like `X-RateLimit-Remaining`,
#   `Retry-After`) to pause requests proactively.