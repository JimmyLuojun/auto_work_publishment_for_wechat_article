 # -*- coding: utf-8 -*-
"""
client.py - WeChat Official Account API Client.

Responsibilities:
- Communicate with WeChat Official Account API endpoints.
- Handle access token acquisition and caching.
- Provide methods for specific API calls:
    - Getting access token.
    - Uploading temporary media (images, videos).
    - Adding a new draft article.
- Manage API request/response logic and basic error handling.

Dependencies:
- requests: For making HTTP requests.
- logging: For logging API calls and errors.
- time: For managing token expiry.
- typing: For type hints.

Expected Input:
- settings (Dict): Application settings containing WECHAT_APPID and WECHAT_APPSECRET.
- Payloads for specific API calls (e.g., draft data, file paths).

Expected Output:
- Parsed JSON responses from WeChat API.
- Uploaded media IDs.
- Raises WeChatAPIError on failure.
"""

import logging
import os
import time
from typing import Dict, Any, Optional, Tuple

import requests # Ensure 'requests' is installed

logger = logging.getLogger(__name__)

# WeChat API Base URLs (can be moved to config.ini if preferred)
WECHAT_API_BASE_URL = "[https://api.weixin.qq.com/cgi-bin](https://www.google.com/search?q=https://api.weixin.qq.com/cgi-bin)"

class WeChatAPIError(Exception):
    """Custom exception for WeChat API errors."""
    def __init__(self, errcode: int, errmsg: str, *args):
        super().__init__(f"WeChat API Error {errcode}: {errmsg}", *args)
        self.errcode = errcode
        self.errmsg = errmsg

class WeChatAPIClient:
    """Handles communication with the WeChat Official Account API."""

    def __init__(self, settings: Dict[str, Any]):
        """
        Initializes the API client.

        Args:
            settings (Dict[str, Any]): Application settings dictionary containing
                                       'WECHAT_APPID' and 'WECHAT_APPSECRET'.
        """
        self.app_id = settings.get('WECHAT_APPID')
        self.app_secret = settings.get('WECHAT_APPSECRET')
        self.session = requests.Session() # Use a session for connection pooling
        self.access_token: Optional[str] = None
        self.token_expires_at: float = 0 # Timestamp when the token expires

        if not self.app_id or not self.app_secret:
            logger.error("WeChatAPIClient initialized without APPID or APPSECRET.")
            # Consider raising an error here if credentials are required immediately
            # raise ValueError("Missing WeChat AppID or AppSecret in settings")

    def _request(self, method: str, endpoint_path: str, params: Optional[Dict] = None,
                 data: Optional[Any] = None, json: Optional[Dict] = None,
                 files: Optional[Dict] = None, add_token: bool = True) -> Dict[str, Any]:
        """
        Internal helper method to make requests to the WeChat API.

        Args:
            method (str): HTTP method (GET, POST, etc.).
            endpoint_path (str): API endpoint path (e.g., '/token').
            params (Optional[Dict]): URL query parameters.
            data (Optional[Any]): Form data payload.
            json (Optional[Dict]): JSON payload.
            files (Optional[Dict]): Files for multipart/form-data upload.
            add_token (bool): Whether to automatically add the access token to params.

        Returns:
            Dict[str, Any]: The parsed JSON response from the API.

        Raises:
            WeChatAPIError: If the API returns an error code.
            requests.exceptions.RequestException: For network or request-related issues.
        """
        if add_token:
            token = self.get_access_token() # Ensure token is valid
            if not params:
                params = {}
            params['access_token'] = token

        url = f"{WECHAT_API_BASE_URL}{endpoint_path}"
        headers = {'Accept': 'application/json'}
        # WeChat API sometimes requires specific User-Agent, add if necessary
        # headers['User-Agent'] = 'MyWeChatPublisherApp/1.0'

        try:
            logger.debug(f"Making WeChat API request: {method} {url}")
            # logger.debug(f"Params: {params}")
            # Avoid logging full JSON/data payload if it contains sensitive info or is large
            # logger.debug(f"JSON Payload: {json}")

            response = self.session.request(
                method=method,
                url=url,
                params=params,
                data=data,
                json=json,
                files=files,
                headers=headers,
                timeout=30 # Set a reasonable timeout (adjust as needed)
            )
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

            response_json = response.json()
            logger.debug(f"WeChat API Response ({url}): {response_json}")

            # Check for WeChat specific error codes in the response body
            if 'errcode' in response_json and response_json['errcode'] != 0:
                errcode = response_json['errcode']
                errmsg = response_json.get('errmsg', 'Unknown error')
                 # Handle specific token errors if needed
                if errcode in [40001, 40014, 42001]: # Invalid credential, invalid token, token expired
                    logger.warning(f"Access token error ({errcode}). Invalidating cached token.")
                    self.access_token = None # Invalidate token
                raise WeChatAPIError(errcode, errmsg)

            return response_json

        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP request failed to {url}: {e}", exc_info=True)
            raise # Re-raise the requests error
        except WeChatAPIError as e:
            logger.error(f"WeChat API returned error: Code={e.errcode}, Msg='{e.errmsg}'")
            raise # Re-raise the custom API error
        except Exception as e:
            logger.error(f"An unexpected error occurred during API request to {url}: {e}", exc_info=True)
            raise # Re-raise unexpected errors


    def get_access_token(self) -> str:
        """
        Retrieves the WeChat API access token, caching it until expiry.

        Returns:
            str: The valid access token.

        Raises:
            ValueError: If AppID or AppSecret are missing.
            WeChatAPIError: If the token request fails.
            requests.exceptions.RequestException: For network issues.
        """
        if not self.app_id or not self.app_secret:
            logger.error("Cannot get access token: AppID or AppSecret is missing.")
            raise ValueError("Missing WeChat AppID or AppSecret")

        # Check if cached token is still valid (with a small buffer, e.g., 5 minutes)
        buffer_seconds = 300
        if self.access_token and self.token_expires_at > (time.time() + buffer_seconds):
            logger.debug("Using cached access token.")
            return self.access_token

        logger.info("Requesting new WeChat access token.")
        params = {
            'grant_type': 'client_credential',
            'appid': self.app_id,
            'secret': self.app_secret,
        }
        try:
            response_json = self._request('GET', '/token', params=params, add_token=False) # Don't add token to token request
            self.access_token = response_json.get('access_token')
            expires_in = response_json.get('expires_in', 7200) # Default to 2 hours

            if not self.access_token:
                 logger.error("Access token not found in WeChat API response.")
                 raise WeChatAPIError(-1, "Access token missing in API response.")

            self.token_expires_at = time.time() + expires_in
            logger.info(f"Successfully retrieved new access token. Expires in {expires_in} seconds.")
            return self.access_token

        except (WeChatAPIError, requests.exceptions.RequestException) as e:
            # If token request fails, ensure cache is cleared
            self.access_token = None
            self.token_expires_at = 0
            logger.error(f"Failed to retrieve access token: {e}")
            raise # Re-raise the caught exception

    def upload_temporary_media(self, file_path: str, media_type: str) -> str:
        """
        Uploads temporary media (image, video, voice, thumb) to WeChat servers.
        Temporary media is valid for 3 days.

        Args:
            file_path (str): The path to the media file to upload.
            media_type (str): Type of media ('image', 'video', 'voice', 'thumb').

        Returns:
            str: The media_id returned by WeChat.

        Raises:
            FileNotFoundError: If the file_path does not exist.
            WeChatAPIError: If the upload fails according to API response.
            requests.exceptions.RequestException: For network/upload issues.
            ValueError: If media_type is invalid.
        """
        valid_media_types = ['image', 'video', 'voice', 'thumb']
        if media_type not in valid_media_types:
             raise ValueError(f"Invalid media_type '{media_type}'. Must be one of {valid_media_types}")

        if not os.path.exists(file_path):
            logger.error(f"Media file not found for upload: {file_path}")
            raise FileNotFoundError(f"Media file not found: {file_path}")

        logger.info(f"Uploading temporary {media_type} media from: {file_path}")
        params = {'type': media_type}
        endpoint = '/media/upload'

        # Note on Video Upload: For larger videos (>10MB for temp), WeChat might require
        # a different endpoint or chunked upload, which is not implemented here.
        # The 'add_draft' API might also have limitations on video size/format within content.

        try:
            with open(file_path, 'rb') as f:
                files = {'media': (os.path.basename(file_path), f)}
                response_json = self._request('POST', endpoint, params=params, files=files)

            media_id = response_json.get('media_id') or response_json.get('thumb_media_id')
            if not media_id:
                logger.error(f"media_id not found in response for {media_type} upload.")
                raise WeChatAPIError(-1, f"media_id missing in {media_type} upload response.")

            logger.info(f"Successfully uploaded {media_type}. Media ID: {media_id}")
            return media_id

        except (FileNotFoundError, WeChatAPIError, requests.exceptions.RequestException, ValueError) as e:
            logger.error(f"Failed to upload temporary media ({file_path}): {e}")
            raise # Re-raise caught exceptions

    def add_draft(self, article_payload: Dict[str, Any]) -> str:
        """
        Adds a new draft article to the WeChat Official Account.

        Args:
            article_payload (Dict[str, Any]): The dictionary representing the article(s)
                                            payload structure required by the API,
                                            typically under an 'articles' key.
                                            Example: {'articles': [{...article data...}]}

        Returns:
            str: The media_id of the created draft returned by WeChat.

        Raises:
            WeChatAPIError: If the API call fails.
            requests.exceptions.RequestException: For network issues.
        """
        logger.info("Adding new draft article via WeChat API.")
        endpoint = '/draft/add'

        if 'articles' not in article_payload or not isinstance(article_payload['articles'], list):
             logger.error("Invalid payload structure for add_draft. Missing 'articles' list.")
             raise ValueError("Payload for add_draft must contain an 'articles' list.")

        try:
            response_json = self._request('POST', endpoint, json=article_payload)
            media_id = response_json.get('media_id')

            if not media_id:
                logger.error("media_id not found in add_draft response.")
                raise WeChatAPIError(-1, "media_id missing in add_draft response.")

            logger.info(f"Successfully created draft. Draft Media ID: {media_id}")
            return media_id

        except (WeChatAPIError, requests.exceptions.RequestException, ValueError) as e:
             logger.error(f"Failed to add draft: {e}")
             raise # Re-raise caught exceptions


    # Add methods for other API calls as needed:
    # - get_material_count
    # - get_material_list
    # - upload_permanent_media (requires different handling)
    # - get_material (to get URLs for permanent media)
    # - publish_draft (if direct publishing is desired)

# --- Explanation ---
# Purpose: Provides a dedicated interface for all interactions with the WeChat
#          Official Account API, encapsulating request logic, authentication,
#          and error handling.
# Design Choices:
# - Uses the `requests` library for HTTP communication and sessions for efficiency.
# - Implements automatic access token fetching and caching based on expiry time,
#   reducing redundant token requests.
# - Defines a private `_request` method to centralize common request logic,
#   including URL construction, timeout, error checking (both HTTP and WeChat specific),
#   and token injection.
# - Defines a custom `WeChatAPIError` for specific API-level errors, making
#   error handling clearer in calling modules.
# - Provides specific public methods (`get_access_token`, `upload_temporary_media`,
#   `add_draft`) for common operations, abstracting the endpoint details.
# - Includes logging for requests, responses (debugging), token management, and errors.
# Improvements/Alternatives:
# - **Token Storage:** For multi-process or distributed environments, token caching
#   should use a shared store (like Redis, Memcached) instead of instance memory.
# - **Rate Limiting:** Implement mechanisms to handle WeChat API rate limits (e.g.,
#   using exponential backoff on specific errors or tracking usage).
# - **Permanent Media:** Add methods for handling permanent media uploads and retrieval,
#   which have different API calls and often return URLs directly.
# - **Error Handling:** Add more granular error handling for specific WeChat error codes
#   if needed (e.g., differentiating between temporary and permanent failures).
# - **Async Support:** Could be implemented using `aiohttp` or `httpx` for asynchronous
#   applications.