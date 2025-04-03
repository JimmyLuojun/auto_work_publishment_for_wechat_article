# -*- coding: utf-8 -*-
"""
media_uploader.py - Handles uploading media assets specifically for WeChat.

Responsibilities:
- Take local file paths for media (images, videos).
- Use the WeChatAPIClient to upload these files to WeChat servers.
- Return the WeChat media_id for each uploaded asset.
- Abstract the media type determination logic (basic version here).

Dependencies:
- logging: For logging upload process.
- src.api.wechat.client: The client used for actual API communication.
- typing: For type hints.

Expected Input:
- wechat_api_client: An instance of WeChatAPIClient.
- local_file_path (str): Path to the media file on the local system.

Expected Output:
- str: The WeChat media_id for the uploaded asset.
"""

import logging
import os
from typing import TYPE_CHECKING

# Use TYPE_CHECKING to avoid circular imports for type hints
if TYPE_CHECKING:
    from src.api.wechat.client import WeChatAPIClient, WeChatAPIError
    from requests.exceptions import RequestException

logger = logging.getLogger(__name__)

class WeChatMediaUploader:
    """Handles the process of uploading media files to WeChat."""

    def __init__(self, api_client: 'WeChatAPIClient'):
        """
        Initializes the media uploader.

        Args:
            api_client (WeChatAPIClient): An initialized WeChat API client instance.
        """
        self.api_client = api_client
        # Define supported extensions (can be expanded)
        self.image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
        self.video_extensions = ['.mp4'] # WeChat has strict format/size limits
        self.thumb_extensions = self.image_extensions # Thumbs are usually images
        # Add voice extensions if needed: ['.amr', '.mp3']

    def _determine_media_type(self, file_path: str) -> str:
        """
        Determines the WeChat media type based on file extension.

        Args:
            file_path (str): Path to the media file.

        Returns:
            str: The determined media type ('image', 'video', 'thumb', 'voice') or raises ValueError.
        """
        _, ext = os.path.splitext(file_path)
        ext_lower = ext.lower()

        if ext_lower in self.image_extensions:
            # Simple logic: treat all images as 'image' for draft content uploads.
            # If specific thumbnail uploads are needed, add logic here or pass type explicitly.
            return 'image'
        elif ext_lower in self.video_extensions:
            return 'video'
        # Add voice logic if needed
        # elif ext_lower in self.voice_extensions:
        #    return 'voice'
        else:
            logger.error(f"Unsupported file extension '{ext}' for WeChat upload: {file_path}")
            raise ValueError(f"Unsupported media file extension: {ext}")

    def upload_media(self, local_file_path: str) -> str:
        """
        Uploads a single media file to WeChat as temporary media.

        Args:
            local_file_path (str): The path to the local media file.

        Returns:
            str: The WeChat media_id for the uploaded file.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the media type is unsupported.
            WeChatAPIError: If the API reports an error during upload.
            RequestException: For network issues during upload.
        """
        logger.info(f"Preparing to upload media file: {local_file_path}")

        if not os.path.exists(local_file_path):
            logger.error(f"Local media file not found: {local_file_path}")
            raise FileNotFoundError(f"Local media file not found: {local_file_path}")

        try:
            # Determine media type based on extension
            media_type = self._determine_media_type(local_file_path)
            logger.debug(f"Determined media type as '{media_type}' for {local_file_path}")

            # Use the API client to perform the upload
            media_id = self.api_client.upload_temporary_media(local_file_path, media_type)
            logger.info(f"Media upload successful for {local_file_path}. Media ID: {media_id}")
            return media_id

        except (FileNotFoundError, ValueError, 'WeChatAPIError', 'RequestException') as e:
            logger.error(f"Media upload failed for {local_file_path}: {e}", exc_info=False) # Avoid redundant stack trace if already logged in client
            raise # Re-raise the exception to be handled by the caller

# --- Explanation ---
# Purpose: To abstract the specific logic of uploading media files *for WeChat*.
#          It acts as an intermediary between the publisher (which knows about
#          local files) and the API client (which knows how to talk to the API).
# Design Choices:
# - Takes an initialized `WeChatAPIClient` instance upon creation (Dependency Injection).
#   This makes it testable, as you can pass a mock API client during tests.
# - Includes a basic `_determine_media_type` helper based on file extensions. This
#   is simple but might need refinement for edge cases or specific WeChat requirements
#   (e.g., differentiating 'thumb' uploads if needed).
# - The main `upload_media` method orchestrates: checking file existence, determining
#   type, and calling the appropriate API client method.
# - It focuses on uploading *temporary* media, suitable for draft creation. Permanent
#   media upload would likely require a separate method or different logic.
# Improvements/Alternatives:
# - **Media Type Determination:** Could be made more robust, perhaps by inspecting
#   file headers (using libraries like `python-magic`) or by requiring the type
#   to be passed explicitly if extension isn't reliable.
# - **Error Handling:** Could potentially add retries for temporary network errors.
# - **Permanent Media:** Add a separate `upload_permanent_media` method if needed.
# - **Configuration:** Media type mappings (extensions) could be moved to `config.ini`.