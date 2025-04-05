# /Users/junluo/Documents/auto_work_publishment_for_wechat_article/src/api/wechat/client.py

"""
WeChat Official Account API Client

Purpose:
Provides methods to interact with the WeChat Official Account API,
including fetching access tokens, uploading media, and managing drafts.

Dependencies:
- time (standard Python library)
- typing (standard Python library)
- src.api.base_client.BaseApiClient
- src.core.settings
- src.utils.logger

Expected Input: Requires WeChat App ID and Secret configured in settings.
Expected Output: Methods return data from WeChat API or raise exceptions on failure.
"""

import time
import json
from typing import Optional, Dict, Any, Tuple

from src.api.base_client import BaseApiClient
from src.core import settings
from src.utils.logger import log

# WeChat API Endpoints (relative to base URL)
# Consult WeChat documentation for the latest endpoints
ENDPOINT_ACCESS_TOKEN = '/cgi-bin/token'
ENDPOINT_UPLOAD_MEDIA = '/cgi-bin/material/add_material'  # For permanent media
ENDPOINT_UPLOAD_TEMP_MEDIA = '/cgi-bin/media/upload' # For temporary media (e.g., thumb for drafts)
ENDPOINT_ADD_DRAFT = '/cgi-bin/draft/add'
ENDPOINT_GET_DRAFT = '/cgi-bin/draft/get'
ENDPOINT_UPDATE_DRAFT = '/cgi-bin/draft/update'
ENDPOINT_BATCHGET_MATERIAL = '/cgi-bin/material/batchget_material' # To check existing permanent media? maybe less useful for drafts
ENDPOINT_BATCHGET_DRAFT = '/cgi-bin/draft/batchget' # To list drafts for idempotency

class WeChatClient(BaseApiClient):
    """
    Client for interacting with the WeChat Official Account API.
    Handles access token management and common API calls.
    """

    def __init__(self):
        """Initializes the WeChatClient."""
        if not settings.WECHAT_APP_ID or not settings.WECHAT_APP_SECRET:
            raise ValueError("WECHAT_APP_ID and WECHAT_APP_SECRET must be configured.")

        super().__init__(base_url=settings.WECHAT_API_BASE_URL)
        self.app_id = settings.WECHAT_APP_ID
        self.app_secret = settings.WECHAT_APP_SECRET
        self._access_token: Optional[str] = None
        self._token_expiry_time: float = 0.0
        log.info("WeChatClient initialized.")

    def _authenticate(self) -> Dict[str, Any]:
        """
        WeChat uses access_token in query params, not typically headers for auth.
        This method ensures the token is valid, fetching/refreshing if needed.
        It's called implicitly by methods needing the token.
        """
        if not self._access_token or time.time() >= self._token_expiry_time:
            log.info("Access token is invalid or expired. Fetching new token...")
            if not self._fetch_access_token():
                # Error already logged in _fetch_access_token
                raise ConnectionError("Failed to retrieve WeChat access token.")
        # Return empty dict as token is added to params, not headers usually
        return {}

    def _get_valid_access_token(self) -> Optional[str]:
        """Ensures a valid access token is available and returns it."""
        self._authenticate() # Trigger refresh if needed
        return self._access_token

    def _fetch_access_token(self) -> bool:
        """
        Fetches a new access token from the WeChat API.

        Returns:
            bool: True if token fetch was successful, False otherwise.
        """
        params = {
            'grant_type': 'client_credential',
            'appid': self.app_id,
            'secret': self.app_secret,
        }
        # Use _make_request without retries for token fetch? Or keep retries? Keeping for robustness.
        response_data, error = self._make_request('GET', ENDPOINT_ACCESS_TOKEN, params=params)

        if error or not response_data:
            log.error(f"Failed to fetch access token. Error: {error or 'No data received'}")
            self._access_token = None
            self._token_expiry_time = 0.0
            return False

        if 'access_token' in response_data and 'expires_in' in response_data:
            self._access_token = response_data['access_token']
            # Add a buffer (e.g., 5 minutes) to expiry time for safety
            expires_in = int(response_data['expires_in']) - 300
            self._token_expiry_time = time.time() + max(expires_in, 0) # Ensure non-negative expiry
            log.info(f"Successfully fetched new access token. Expires in approx {expires_in / 60:.1f} minutes.")
            return True
        else:
            log.error(f"Error fetching access token: WeChat API response missing token or expiry. Response: {response_data}")
            self._access_token = None
            self._token_expiry_time = 0.0
            return False

    def upload_media(self, file_path: str, media_type: str, is_permanent: bool = True) -> Optional[Dict[str, Any]]:
        """
        Uploads a media file (image, video, etc.) to WeChat.

        Args:
            file_path (str): The local path to the media file.
            media_type (str): The type of media ('image', 'video', 'voice', 'thumb').
                                Use 'thumb' for cover images needed for drafts/articles.
            is_permanent (bool): If True, upload as permanent material.
                                 If False, upload as temporary media (valid 3 days).
                                 Draft covers often require permanent ('thumb'). Content images
                                 can also be permanent. Check WeChat docs.

        Returns:
            Optional[Dict[str, Any]]: Dictionary containing 'media_id' and potentially 'url'
                                      if successful, None otherwise.
        """
        access_token = self._get_valid_access_token()
        if not access_token:
            return None

        endpoint = ENDPOINT_UPLOAD_MEDIA if is_permanent else ENDPOINT_UPLOAD_TEMP_MEDIA
        params = {'access_token': access_token, 'type': media_type}

        try:
            with open(file_path, 'rb') as f:
                files = {'media': (file_path, f)} # Let requests handle Content-Type
                # For permanent video uploads, a description JSON might be needed in `data`
                # data = None
                # if media_type == 'video' and is_permanent:
                #     data = {'description': json.dumps({'title': 'Video Title', 'introduction': 'Video Intro'})}

                log.info(f"Uploading {'permanent' if is_permanent else 'temporary'} {media_type} from {file_path}...")
                response_data, error = self._make_request(
                    'POST',
                    endpoint,
                    params=params,
                    files=files,
                    # data=data # Add if needed for video
                )

                if error or not response_data:
                    log.error(f"Failed to upload media {file_path}. Error: {error or 'No data received'}")
                    return None

                # Check specific WeChat error codes if necessary
                if response_data.get('errcode') and response_data.get('errcode') != 0:
                    log.error(f"WeChat API error during media upload: {response_data.get('errmsg')} (Code: {response_data.get('errcode')})")
                    return None

                # Successful upload returns media_id (and sometimes url for permanent)
                if 'media_id' in response_data:
                    log.info(f"Media uploaded successfully: media_id={response_data['media_id']}")
                    return response_data
                else:
                     log.error(f"Media upload response did not contain media_id: {response_data}")
                     return None

        except FileNotFoundError:
            log.error(f"Media file not found: {file_path}")
            return None
        except IOError as e:
            log.error(f"Error reading media file {file_path}: {e}")
            return None
        except Exception as e:
            log.error(f"An unexpected error occurred during media upload: {e}")
            return None

    def add_draft(self, article_data: Dict[str, Any]) -> Optional[str]:
        """
        Creates a new draft article in WeChat.

        Args:
            article_data (Dict[str, Any]): A dictionary representing the article,
                                           following the structure required by the
                                           WeChat /cgi-bin/draft/add API.
                                           Must contain an 'articles' list with one article dict.
                                           Example keys for article dict: 'title', 'author',
                                           'content', 'content_source_url', 'thumb_media_id',
                                           'need_open_comment', 'only_fans_can_comment', etc.

        Returns:
            Optional[str]: The media_id of the created draft if successful, None otherwise.
        """
        access_token = self._get_valid_access_token()
        if not access_token:
            return None

        endpoint = ENDPOINT_ADD_DRAFT
        params = {'access_token': access_token}
        payload = {'articles': [article_data]} # API expects a list of articles

        log.info(f"Attempting to add new draft: Title '{article_data.get('title', 'N/A')}'")
        log.debug(f"Draft payload: {json.dumps(payload, ensure_ascii=False)}") # Log full payload in debug

        response_data, error = self._make_request('POST', endpoint, params=params, json_payload=payload)

        if error or not response_data:
            log.error(f"Failed to add draft. Error: {error or 'No data received'}")
            return None

        if response_data.get('errcode') and response_data.get('errcode') != 0:
            log.error(f"WeChat API error adding draft: {response_data.get('errmsg')} (Code: {response_data.get('errcode')})")
            return None

        if 'media_id' in response_data:
            draft_media_id = response_data['media_id']
            log.info(f"Draft created successfully. Draft media_id: {draft_media_id}")
            return draft_media_id
        else:
            log.error(f"Add draft response did not contain media_id: {response_data}")
            return None

    def update_draft(self, draft_media_id: str, article_index: int, article_data: Dict[str, Any]) -> bool:
        """
        Updates an existing draft article in WeChat.

        Args:
            draft_media_id (str): The media_id of the draft to update.
            article_index (int): The index of the article within the draft to update (usually 0 for single articles).
            article_data (Dict[str, Any]): Dictionary with the updated article fields.

        Returns:
            bool: True if update was successful, False otherwise.
        """
        access_token = self._get_valid_access_token()
        if not access_token:
            return False

        endpoint = ENDPOINT_UPDATE_DRAFT
        params = {'access_token': access_token}
        payload = {
            "media_id": draft_media_id,
            "index": article_index,
            "articles": article_data # API expects the article structure directly
        }

        log.info(f"Attempting to update draft {draft_media_id} at index {article_index}: Title '{article_data.get('title', 'N/A')}'")
        log.debug(f"Update Draft payload: {json.dumps(payload, ensure_ascii=False)}")

        response_data, error = self._make_request('POST', endpoint, params=params, json_payload=payload)

        # Update API typically returns {"errcode":0,"errmsg":"ok"} on success
        if error:
            log.error(f"Failed to update draft {draft_media_id}. Error: {error}")
            return False

        if response_data and response_data.get('errcode') == 0:
            log.info(f"Draft {draft_media_id} updated successfully.")
            return True
        else:
            errcode = response_data.get('errcode', 'N/A') if response_data else 'N/A'
            errmsg = response_data.get('errmsg', 'Unknown error or no data') if response_data else 'Unknown error or no data'
            log.error(f"WeChat API error updating draft {draft_media_id}: {errmsg} (Code: {errcode})")
            log.debug(f"Failed update response: {response_data}")
            return False

    def find_draft_by_title(self, title: str, count: int = 20, offset: int = 0) -> Optional[str]:
        """
        Attempts to find a draft's media_id by its title.
        NOTE: This requires iterating through drafts, which can be inefficient.
              WeChat API might have limitations on draft listing frequency/quantity.

        Args:
            title (str): The exact title of the draft to find.
            count (int): Number of drafts to fetch per API call (max usually 20).
            offset (int): Offset for pagination.

        Returns:
            Optional[str]: The media_id of the found draft, or None if not found or error occurs.
        """
        access_token = self._get_valid_access_token()
        if not access_token:
            return None

        log.info(f"Searching for existing draft with title: '{title}'")
        endpoint = ENDPOINT_BATCHGET_DRAFT
        params = {'access_token': access_token}
        payload = {"offset": offset, "count": count, "no_content": 1} # no_content=1 to speed up query

        response_data, error = self._make_request('POST', endpoint, params=params, json_payload=payload)

        if error or not response_data:
             log.error(f"Failed to list drafts. Error: {error or 'No data received'}")
             return None

        if response_data.get('errcode') and response_data.get('errcode') != 0:
            log.error(f"WeChat API error listing drafts: {response_data.get('errmsg')} (Code: {response_data.get('errcode')})")
            return None

        items = response_data.get('item', [])
        total_count = response_data.get('total_count', 0)
        log.debug(f"Fetched {len(items)} drafts (offset {offset}, total {total_count}).")

        for item in items:
            # The 'item' structure contains 'media_id' and 'content'.
            # 'content' contains 'news_item' list. We need the title from there.
            try:
                # Check if 'content' and 'news_item' exist and 'news_item' is not empty
                if 'content' in item and 'news_item' in item['content'] and item['content']['news_item']:
                     draft_title = item['content']['news_item'][0].get('title')
                     if draft_title == title:
                         media_id = item['media_id']
                         log.info(f"Found existing draft with title '{title}'. Media ID: {media_id}")
                         return media_id
            except (KeyError, IndexError, TypeError) as e:
                log.warning(f"Could not parse title from draft item: {item}. Error: {e}")
                continue # Skip malformed item


        # Recursive call or loop for pagination if needed and total_count > offset + len(items)
        # Be mindful of API rate limits if implementing pagination
        # if total_count > offset + len(items):
        #     log.debug("Checking next page of drafts...")
        #     # return self.find_draft_by_title(title, count=count, offset=offset + count) # Example recursion

        log.info(f"No draft found with title: '{title}'")
        return None