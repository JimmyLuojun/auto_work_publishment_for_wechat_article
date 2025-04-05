# /Users/junluo/Documents/auto_work_publishment_for_wechat_article/src/platforms/wechat/media_uploader.py

"""
Refined WeChat Media Uploading Module

Purpose:
Handles uploading media files (cover, content) to WeChat, using the richer
information provided by the refined Article model (frontmatter metadata,
explicit file paths from standard Markdown links).

Dependencies:
- typing (standard Python library)
- pathlib (standard Python library)
- src.api.wechat.client.WeChatClient
- src.core.article_model.Article
- src.core.settings
- src.utils.logger

Expected Input:
- An Article object populated by the refined MarkdownParser.
- A WeChatClient instance.
- Configuration settings (media mode, paths).

Expected Output:
- Updates the Article object's placeholders with upload results (media_id, url).
- Returns True if cover upload succeeds, False otherwise (content media failures only logged).
"""

from typing import Dict, Optional, Tuple
from pathlib import Path

from src.api.wechat.client import WeChatClient
from src.core.article_model import Article, MediaPlaceholder
from src.core import settings
from src.utils.logger import log

class WeChatMediaUploader:
    """Handles uploading media associated with an Article to WeChat."""

    def __init__(self, client: WeChatClient):
        """
        Initializes the media uploader.

        Args:
            client (WeChatClient): An authenticated WeChat API client instance.
        """
        self.client = client
        log.info("WeChatMediaUploader initialized.")

    def upload_article_media(self, article: Article) -> bool:
        """
        Uploads the cover image and all content media referenced in the article.
        Updates the MediaPlaceholder objects within the article with upload results.

        Args:
            article (Article): The article object containing media references.

        Returns:
            bool: True if the cover image upload was successful, False otherwise.
                  Failures in content media uploads are logged but do not cause a False return.
        """
        log.info(f"Starting media upload process for article: '{article.title}'")
        upload_success_count = 0
        upload_failure_count = 0

        # --- 1. Handle Cover Image Upload ---
        cover_success = self._upload_cover_image(article)
        if not cover_success:
            log.critical("Critical failure: Cover image upload failed. Halting media upload for this article.")
            return False # Cover image is mandatory

        upload_success_count += 1 # Count cover as one success

        # --- 2. Handle Content Media Uploads ---
        log.info("Processing content media uploads...")
        if not article.media_placeholders:
            log.info("No content media references found in the article.")
        else:
            for placeholder in article.media_placeholders:
                if placeholder.uploaded_media_id:
                    log.debug(f"Skipping already uploaded media: {placeholder.placeholder_id}")
                    upload_success_count +=1
                    continue

                # Determine the absolute path of the media file
                media_file_path = self._find_media_file(placeholder, is_cover=False, article_base_dir=settings.INPUT_DIR) # Assume article path relative to INPUT_DIR

                if not media_file_path:
                    log.warning(f"Could not find file for content media placeholder ID='{placeholder.placeholder_id}', Path='{placeholder.file_path}'. Skipping upload.")
                    upload_failure_count += 1
                    continue # Skip this file

                # Perform the upload (Content images/videos are usually permanent)
                media_type = placeholder.media_type # 'image', 'video', etc. (set by parser)
                log.info(f"Uploading content media ({media_type}) from: {media_file_path}")
                upload_result = self.client.upload_media(
                    file_path=str(media_file_path),
                    media_type=media_type,
                    is_permanent=True # Content media should typically be permanent
                )

                if upload_result and 'media_id' in upload_result:
                    placeholder.uploaded_media_id = upload_result['media_id']
                    placeholder.uploaded_url = upload_result.get('url') # URL is important!
                    log.info(f"Content media '{placeholder.placeholder_id}' uploaded. Media ID: {placeholder.uploaded_media_id}, URL: {placeholder.uploaded_url}")
                    upload_success_count += 1
                else:
                    log.error(f"Failed to upload content media: {media_file_path} (Placeholder ID: {placeholder.placeholder_id})")
                    upload_failure_count += 1
                    # Continue trying other media

        # --- 3. Log Summary ---
        total_media = 1 + len(article.media_placeholders) # Cover + Content
        log.info(f"Media upload process finished for article: '{article.title}'.")
        log.info(f"Upload Summary: {upload_success_count} succeeded, {upload_failure_count} failed (out of {total_media} total media items).")
        if upload_failure_count > 0:
            log.warning("There were failures uploading some content media items. Check logs above.")

        # Return True because cover succeeded (content failures don't block)
        return True


    def _upload_cover_image(self, article: Article) -> bool:
        """
        Finds and uploads the cover image specified for the article.
        Prioritizes frontmatter references.

        Args:
            article (Article): The article object.

        Returns:
            bool: True if cover upload was successful, False otherwise.
        """
        log.info("Processing cover image upload...")
        cover_file_path: Optional[Path] = None
        cover_placeholder = article.cover_image_placeholder # May contain ID and/or relative path

        if not cover_placeholder and not article.cover_image_file_path:
             log.error("No cover image reference found in article frontmatter ('cover_image' or 'cover_image_path'). Cannot determine cover image.")
             # Add fallback logic here if desired (e.g., check settings.INPUT_COVER_IMAGE_DIR)
             log.warning(f"Attempting fallback: Searching for cover image in {settings.INPUT_COVER_IMAGE_DIR}")
             try:
                # Example fallback: look for file matching article title or first image
                 potential_path = settings.INPUT_COVER_IMAGE_DIR / f"{article.title}.jpg"
                 if potential_path.is_file():
                     cover_file_path = potential_path
                 else:
                     potential_path = settings.INPUT_COVER_IMAGE_DIR / f"{article.title}.png"
                     if potential_path.is_file():
                         cover_file_path = potential_path
                     else: # Last resort: first file
                        first_img = next(settings.INPUT_COVER_IMAGE_DIR.glob('*.*'))
                        cover_file_path = first_img
                 log.info(f"Using fallback cover image: {cover_file_path}")
                 # Create a placeholder object for the fallback if needed for consistency
                 if not cover_placeholder:
                      cover_placeholder = MediaPlaceholder(placeholder_id=cover_file_path.name, media_type="thumb")
                      article.cover_image_placeholder = cover_placeholder # Add to article
             except StopIteration:
                 log.error(f"Fallback failed: No cover image found in {settings.INPUT_COVER_IMAGE_DIR}.")
                 return False # Cannot proceed without cover


        # If we don't have an absolute path yet, find it using the placeholder/path info
        if not cover_file_path:
            # Base directory for resolving cover paths could be INPUT_DIR or specific cover dir
            cover_base_dir = settings.INPUT_COVER_IMAGE_DIR # Usually covers are here
            cover_file_path = self._find_media_file(
                placeholder=cover_placeholder,
                explicit_relative_path=article.cover_image_file_path,
                is_cover=True,
                article_base_dir=cover_base_dir # Resolve relative to cover dir
            )

        if not cover_file_path:
            log.error(f"Could not find the specified cover image file. Placeholder: {cover_placeholder}, Path: {article.cover_image_file_path}")
            return False

        # Ensure the placeholder exists in the article for storing results
        if not article.cover_image_placeholder:
             article.cover_image_placeholder = MediaPlaceholder(placeholder_id=cover_file_path.name, media_type="thumb")

        # Perform the upload (Covers *must* be 'thumb' type for WeChat drafts)
        log.info(f"Uploading cover image ('thumb') from: {cover_file_path}")
        upload_result = self.client.upload_media(
            file_path=str(cover_file_path),
            media_type='thumb', # Hardcoded to thumb for cover
            is_permanent=True # Often required for `thumb_media_id` in drafts
        )

        if upload_result and 'media_id' in upload_result:
            # Store results back into the placeholder object within the article
            article.cover_image_placeholder.uploaded_media_id = upload_result['media_id']
            article.cover_image_placeholder.uploaded_url = upload_result.get('url')
            article.cover_image_placeholder.file_path = str(cover_file_path) # Store resolved path
            log.info(f"Cover image uploaded successfully. Media ID: {article.cover_image_placeholder.uploaded_media_id}")
            return True
        else:
            log.error(f"Failed to upload cover image: {cover_file_path}")
            return False


    def _find_media_file(self,
                         placeholder: Optional[MediaPlaceholder],
                         explicit_relative_path: Optional[str] = None,
                         is_cover: bool = False,
                         article_base_dir: Path = settings.INPUT_DIR) -> Optional[Path]:
        """
        Finds the absolute path for a media item based on placeholder info or explicit path.

        Args:
            placeholder (Optional[MediaPlaceholder]): The placeholder object from the article.
            explicit_relative_path (Optional[str]): An explicit relative path (e.g., from cover_image_path).
            is_cover (bool): Flag indicating if this is the cover image.
            article_base_dir (Path): The base directory to resolve relative paths against.
                                     (e.g., settings.INPUT_DIR or settings.INPUT_COVER_IMAGE_DIR)

        Returns:
            Optional[Path]: The resolved absolute path to the media file, or None if not found.
        """
        # Priority 1: Use explicit relative path if provided (e.g., standard MD link or cover_image_path)
        target_path_str = explicit_relative_path or (placeholder.file_path if placeholder else None)
        if target_path_str:
            try:
                # Resolve relative path based on the article's input directory
                # Security note: Ensure article_base_dir is trusted / within project
                resolved_path = (article_base_dir / target_path_str).resolve()
                if resolved_path.is_file():
                    log.debug(f"Found media file via relative path '{target_path_str}': {resolved_path}")
                    return resolved_path
                else:
                    log.warning(f"Media file specified by path '{target_path_str}' not found at resolved location: {resolved_path}")
                    # Fall through to try finding by ID if path fails
            except Exception as e:
                 log.warning(f"Error resolving media path '{target_path_str}': {e}. Trying lookup by ID.")
                 # Fall through

        # Priority 2: Look for file by placeholder ID in the designated directory
        if placeholder and placeholder.placeholder_id:
            media_dir = settings.INPUT_COVER_IMAGE_DIR if is_cover else settings.INPUT_CONTENT_IMAGE_DIR
            potential_path = media_dir / placeholder.placeholder_id
            if potential_path.is_file():
                log.debug(f"Found media file via placeholder ID '{placeholder.placeholder_id}' in {media_dir}: {potential_path}")
                return potential_path
            else:
                # Try adding common extensions if ID has none? Could be risky.
                log.warning(f"Media file not found by matching placeholder ID '{placeholder.placeholder_id}' in directory {media_dir}")

        # Priority 3: (Optional / Fallback for cover only in _upload_cover_image)
        # Could add more fallbacks here if needed

        log.debug(f"Could not find file for placeholder: {placeholder}, explicit path: {explicit_relative_path}")
        return None