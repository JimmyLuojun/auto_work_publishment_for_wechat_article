# -*- coding: utf-8 -*-
"""
publisher.py - Orchestrates the WeChat article publishing workflow.

Responsibilities:
- Take a parsed Article object.
- Coordinate media uploading using WeChatMediaUploader.
- Coordinate HTML formatting using WeChatFormatter.
- Prepare the final payload for the WeChat 'add_draft' API.
- Use the WeChatAPIClient to send the draft to WeChat.
- Handle the overall success/failure reporting of the publishing process.

Dependencies:
- logging: For logging workflow steps and errors.
- src.core.article_model: Defines the Article structure.
- src.api.wechat.client: For interacting with the WeChat API.
- src.platforms.wechat.media_uploader: For uploading media.
- src.platforms.wechat.formatter: For generating HTML.
- typing: For type hints.

Expected Input:
- article (Article): The parsed article object.
- settings (Dict): Application configuration settings.

Expected Output:
- Optional[str]: The media_id of the created draft if successful, None otherwise.
"""

import logging
import os
from typing import TYPE_CHECKING, Optional, Dict, Any, List, Tuple

from src.core.article_model import Article, ImagePlaceholder, VideoPlaceholder, ContentBlock # Import necessary block types
from src.platforms.wechat.media_uploader import WeChatMediaUploader
from src.platforms.wechat.formatter import WeChatFormatter
# Use TYPE_CHECKING to avoid circular import if client instantiates publisher or vice versa
if TYPE_CHECKING:
    from src.api.wechat.client import WeChatAPIClient, WeChatAPIError
    from requests.exceptions import RequestException


logger = logging.getLogger(__name__)

class WeChatPublisher:
    """Orchestrates publishing an Article object as a WeChat draft."""

    def __init__(self, settings: Dict[str, Any], api_client: 'WeChatAPIClient'):
        """
        Initializes the publisher.

        Args:
            settings (Dict[str, Any]): Application configuration settings.
            api_client (WeChatAPIClient): An initialized WeChat API client instance.
        """
        self.settings = settings
        self.api_client = api_client
        self.media_uploader = WeChatMediaUploader(api_client)
        self.formatter = WeChatFormatter(settings)
        logger.info("WeChatPublisher initialized.")

    def _upload_article_media(self, article: Article) -> bool:
        """
        Uploads all media assets found in the article content blocks.
        Updates the ImagePlaceholder/VideoPlaceholder blocks with the media_id.

        Args:
            article (Article): The article object with content blocks.

        Returns:
            bool: True if all required media uploads were successful, False otherwise.
        """
        logger.info(f"Starting media upload process for article: '{article.title}'")
        all_successful = True
        media_blocks_found = 0

        for i, block in enumerate(article.content_blocks):
            media_path: Optional[str] = None
            block_type = ""

            if isinstance(block, ImagePlaceholder):
                media_path = block.local_path
                block_type = "Image"
            elif isinstance(block, VideoPlaceholder):
                media_path = block.local_path
                block_type = "Video"

            if media_path:
                media_blocks_found += 1
                logger.debug(f"Found {block_type} block requiring upload: {media_path}")
                # Skip upload if media_id is already present (e.g., from a previous attempt)
                if isinstance(block, (ImagePlaceholder, VideoPlaceholder)) and block.wechat_media_id:
                     logger.info(f"Skipping upload for {media_path}, media_id already present: {block.wechat_media_id}")
                     continue

                try:
                    # Check if it's a web URL, skip upload if so
                    if media_path.startswith(('http://', 'https://')):
                         logger.info(f"Skipping upload for web URL: {media_path}")
                         # Decide how to handle web URLs in formatting - maybe remove block or special format?
                         # For now, we'll leave the block, formatter needs to handle it.
                         # Or, modify the block type/content here.
                         continue # Skip upload for web URLs

                    media_id = self.media_uploader.upload_media(media_path)
                    # Update the block directly with the media_id
                    if isinstance(block, (ImagePlaceholder, VideoPlaceholder)):
                        block.wechat_media_id = media_id
                        logger.info(f"Successfully uploaded {block_type} {media_path}. Media ID: {media_id}. Updated block {i}.")
                    else: # Should not happen based on initial check
                         logger.error("Logic error: Block type changed during media upload check.")
                         all_successful = False


                except FileNotFoundError:
                    logger.error(f"Media file not found during upload: {media_path}. Article draft may be incomplete.")
                    all_successful = False
                    # Decide whether to continue or fail the entire process
                    # break # Option: Stop processing on first failed upload
                except (ValueError, 'WeChatAPIError', 'RequestException') as e:
                    logger.error(f"Failed to upload {block_type} media {media_path}: {e}. Article draft may be incomplete.")
                    all_successful = False
                    # Decide whether to continue or fail
                    # break # Option: Stop processing on first failed upload
                except Exception as e:
                    logger.exception(f"Unexpected error uploading {block_type} media {media_path}: {e}") # Use .exception for stack trace
                    all_successful = False
                    # break # Option: Stop processing

        if media_blocks_found == 0:
             logger.info("No local media blocks found requiring upload.")
        elif all_successful:
            logger.info("All media uploads completed successfully.")
        else:
            logger.warning("Some media uploads failed. Proceeding to format and save draft, but it may be incomplete.")

        return all_successful # Or return False if *any* upload failed, depending on strictness


    def _get_thumbnail_media_id(self, article: Article) -> Optional[str]:
        """
        Determines the media_id to use for the article's cover image (thumb_media_id).

        Args:
            article (Article): The article object, after media uploads.

        Returns:
            Optional[str]: The media_id of the first uploaded image, or None.
        """
        # Strategy: Use the media_id of the first ImagePlaceholder encountered.
        # Could be made configurable via self.settings['wechat']['cover_image_strategy']
        strategy = self.settings.get('wechat', {}).get('cover_image_strategy', 'first')
        logger.debug(f"Determining thumbnail media ID using strategy: {strategy}")

        if strategy == 'first':
            for block in article.content_blocks:
                if isinstance(block, ImagePlaceholder) and block.wechat_media_id:
                    logger.info(f"Using media_id from first image for thumbnail: {block.wechat_media_id}")
                    return block.wechat_media_id
        elif strategy == 'none':
             return None
        # Add other strategies if needed (e.g., find image marked in frontmatter)

        logger.warning("Could not find a suitable image media_id for the thumbnail.")
        return None


    def publish_draft(self, article: Article) -> Optional[str]:
        """
        Executes the full workflow to publish an article as a WeChat draft.

        1. Uploads media found in the article.
        2. Formats the article content into HTML.
        3. Prepares the payload for the 'add_draft' API.
        4. Calls the API to create the draft.
        5. Optionally saves an HTML preview.

        Args:
            article (Article): The parsed article object.

        Returns:
            Optional[str]: The media_id of the created draft if successful, None otherwise.
        """
        logger.info(f"Starting publish_draft workflow for article: '{article.title}'")

        # 1. Upload Media - updates media_id in article.content_blocks
        # Decide if failure here should halt the process
        media_upload_success = self._upload_article_media(article)
        if not media_upload_success:
             # Option: Halt if any media failed criticaly
             # logger.error("Halting draft creation due to media upload failures.")
             # return None
             logger.warning("Continuing draft creation despite media upload failures.")


        # 2. Format Article Content to HTML
        try:
            html_content = self.formatter.format_article(article)
        except Exception as e:
            logger.exception(f"Error during HTML formatting for article '{article.title}': {e}")
            return None # Cannot proceed without HTML content

        # 3. Optional: Save HTML Preview
        try:
            output_dir = self.settings.get('paths', {}).get('output_dir', 'data/output')
            preview_filename = f"wechat_preview_{article.title[:20].replace(' ','_')}.html"
             # Ensure output path is absolute or relative to project root
            if not os.path.isabs(output_dir):
                 project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                 output_dir = os.path.join(project_root, output_dir)

            preview_path = os.path.join(output_dir, preview_filename)
            self.formatter.save_preview(html_content, preview_path)
        except Exception as e:
             logger.error(f"Failed to save HTML preview: {e}", exc_info=False)
             # Continue anyway, preview is optional


        # 4. Prepare 'add_draft' API Payload
        logger.debug("Preparing payload for add_draft API call.")
        thumb_media_id = self._get_thumbnail_media_id(article)
        default_author = self.settings.get('wechat', {}).get('default_author', '')
        need_open_comment = self.settings.get('wechat', {}).get('need_open_comment', 1)
        only_fans_can_comment = self.settings.get('wechat', {}).get('only_fans_can_comment', 0)

        article_data = {
            "title": article.title,
            "author": article.metadata.get('author', default_author), # Prioritize frontmatter author
            "content": html_content,
            "content_source_url": article.metadata.get('source_url', ''), # Optional original URL
            "thumb_media_id": thumb_media_id,
            "need_open_comment": int(need_open_comment),
            "only_fans_can_comment": int(only_fans_can_comment)
            # Add "is_original": 1 if specified in metadata/config
        }
        # Remove None values, especially thumb_media_id if not found
        article_data_cleaned = {k: v for k, v in article_data.items() if v is not None}

        payload = {"articles": [article_data_cleaned]}
        logger.debug(f"API Payload (content truncated): title='{article_data['title']}', "
                     f"author='{article_data['author']}', thumb_media_id='{thumb_media_id}', "
                     f"content_len={len(html_content)}")

        # 5. Call 'add_draft' API
        try:
            draft_media_id = self.api_client.add_draft(payload)
            logger.info(f"Successfully published draft for article '{article.title}'. Draft Media ID: {draft_media_id}")
            return draft_media_id
        except ('WeChatAPIError', 'RequestException', ValueError) as e:
            logger.error(f"Failed to publish draft for article '{article.title}': {e}")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error during final draft submission for article '{article.title}': {e}")
            return None

# --- Explanation ---
# Purpose: Acts as the central coordinator for the WeChat publishing process. It ties
#          together media uploading, formatting, and API interaction for creating a draft.
# Design Choices:
# - Takes `settings` and an initialized `WeChatAPIClient` (Dependency Injection).
# - Instantiates its dependencies (`WeChatMediaUploader`, `WeChatFormatter`) itself,
#   passing the necessary client/settings.
# - Breaks the process into logical private methods (`_upload_article_media`,
#   `_get_thumbnail_media_id`) and a main public method (`publish_draft`).
# - **Media Upload:** Iterates through content blocks, calls the `MediaUploader`, and
#   *updates the `Article` object in place* by setting the `wechat_media_id` on the
#   relevant blocks. Includes logic to handle upload failures (currently logs warnings
#   but continues; could be changed to halt). Skips web URLs.
# - **Thumbnail:** Implements a simple strategy (first image) to select the cover image
#   `media_id`. This is configurable via settings.
# - **Payload Prep:** Constructs the dictionary required by the `add_draft` API,
#   pulling data from the `Article` object, settings (`author`, comment flags), and
#   the generated HTML. Handles potential `None` values for optional fields.
# - **API Call:** Uses the `WeChatAPIClient` to send the final payload.
# - **Error Handling:** Catches exceptions from underlying components (uploader, formatter,
#   API client) and logs them appropriately. Returns `None` on failure.
# Improvements/Alternatives:
# - **Transactionality:** The current process isn't transactional. If `add_draft` fails
#   after media uploads, the media remains uploaded. Implementing cleanup logic
#   (deleting temporary media) would add complexity.
# - **Failure Strategy:** Make the handling of media upload failures configurable
#   (e.g., stop immediately vs. continue with warnings).
# - **State Management:** For very complex workflows, a more formal state machine
#   pattern could be used.
# - **Decoupling:** Could further decouple by having `_upload_article_media` return a
#   mapping ` {local_path: media_id}` instead of modifying the `Article` object directly,
#   passing this map to the formatter. Modifying in place is simpler here but less pure.