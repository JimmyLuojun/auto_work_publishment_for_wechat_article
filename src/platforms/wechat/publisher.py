# /Users/junluo/Documents/auto_work_publishment_for_wechat_article/src/platforms/wechat/publisher.py

"""
WeChat Article Publisher Module

Purpose:
Takes a processed Article object, assembles the final HTML content
(inserting media URLs/tags), generates a summary (if needed),
and uses the WeChatClient to create or update a draft article on the
WeChat Official Account platform.

Dependencies:
- typing (standard Python library)
- re (standard Python library)
- src.api.wechat.client.WeChatClient
- src.api.deepseek.deepseek_api.DeepSeekClient
- src.core.article_model.Article
- src.core.settings
- src.utils.logger

Expected Input:
- An Article object (populated with parsed content and uploaded media details).
- A WeChatClient instance.
- A DeepSeekClient instance (optional, for summary).

Expected Output:
- The media_id of the created/updated WeChat draft (or None on failure).
"""

import re
import json
from typing import Optional, Dict, Any

from src.api.wechat.client import WeChatClient
from src.api.deepseek.deepseek_api import DeepSeekClient
from src.core.article_model import Article
from src.core import settings
from src.utils.logger import log

# --- HTML Template fragments (Could be loaded from files) ---
# Basic structure, assuming CSS handles most styling
HTML_WRAPPER_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        /* Embed basic styles directly or use WeChat-compatible classes */
        body {{ font-family: sans-serif; line-height: 1.6; margin: 20px; }}
        h1, h2, h3 {{ color: #333; }}
        img {{ max-width: 100%; height: auto; display: block; margin: 1em 0; }}
        /* Add more styles based on wechat_style.css, ensuring compatibility */
    </style>
</head>
<body>
    <div class="article-content">
        {content}
    </div>
</body>
</html>
"""

# Corrected Regex (same as before, group count analysis was the issue)
# Group 1: (<img.*?src=)
# Group 2: (["\'])
# Group 3: placeholder:(.*?)
# \2: Matches closing quote (not a group)
# Group 4: (.*?>) - Rest of tag
HTML_PLACEHOLDER_SRC_RE = re.compile(r'(<img.*?src=)(["\'])placeholder:(.*?)\2(.*?>)', re.IGNORECASE)


class WeChatPublisher:
    """Publishes a processed Article object to WeChat drafts."""

    def __init__(self, wechat_client: WeChatClient, deepseek_client: Optional[DeepSeekClient] = None):
        """
        Initializes the publisher.

        Args:
            wechat_client (WeChatClient): An authenticated WeChat API client.
            deepseek_client (Optional[DeepSeekClient]): Client for generating summaries.
        """
        self.wechat_client = wechat_client
        self.deepseek_client = deepseek_client
        log.info("WeChatPublisher initialized.")

    def publish_draft(self, article: Article, check_existing: bool = True) -> Optional[str]:
        """
        Assembles the article content, generates summary, and saves/updates a WeChat draft.

        Args:
            article (Article): The processed article object with uploaded media info.
            check_existing (bool): If True, try to find and update an existing draft
                                   with the same title before creating a new one.

        Returns:
            Optional[str]: The media_id of the draft, or None on failure.
        """
        log.info(f"Starting publication process for article: '{article.title}'")

        # 1. Ensure Cover Image is Ready
        if not article.cover_image_placeholder or not article.cover_image_placeholder.uploaded_media_id:
            log.error(f"Cannot publish draft: Cover image media ID is missing for article '{article.title}'.")
            return None
        cover_media_id = article.cover_image_placeholder.uploaded_media_id
        log.info(f"Using cover image media ID: {cover_media_id}")

        # 2. Assemble Final HTML Content (Replace Placeholders)
        final_html_content = self._assemble_html_content(article)
        if not final_html_content:
            log.error(f"Cannot publish draft: Failed to assemble final HTML content for '{article.title}'.")
            return None
        article.final_html_content = final_html_content # Store it back if needed

        # 3. Generate Article Summary (Abstract)
        if not article.summary: # Only generate if not already present
            if self.deepseek_client:
                log.info("Generating article summary using DeepSeek...")
                content_for_summary = article.get_content_as_text()
                if not content_for_summary:
                     log.warning("Content for summary generation is empty. Trying HTML content.")
                     content_for_summary = article.final_html_content[:1000]

                if content_for_summary:
                    article.summary = self.deepseek_client.generate_summary(content_for_summary)
                    if article.summary:
                        log.info(f"Generated summary: '{article.summary}'")
                    else:
                        log.warning("Failed to generate summary from DeepSeek. Proceeding without summary.")
                else:
                    log.warning("Could not get text content for summary generation.")
            else:
                log.warning("DeepSeekClient not provided. Skipping summary generation.")
        else:
             log.info(f"Using existing summary for article: '{article.summary}'")

        summary = article.summary or ""
        MAX_SUMMARY_LENGTH = 120
        if len(summary) > MAX_SUMMARY_LENGTH:
             log.warning(f"Summary exceeds estimated length limit ({MAX_SUMMARY_LENGTH} chars), truncating.")
             summary = summary[:MAX_SUMMARY_LENGTH]


        # 4. Prepare WeChat Draft Payload
        draft_payload = {
            "title": article.title,
            "author": settings.ARTICLE_AUTHOR,
            "digest": summary,
            "content": article.final_html_content,
            "content_source_url": "",
            "thumb_media_id": cover_media_id,
            "need_open_comment": 1 if settings.ENABLE_COMMENTS else 0,
            "only_fans_can_comment": 0,
            "is_original": 1 if settings.MARK_AS_ORIGINAL else 0,
            "show_cover_pic": 1,
        }
        log.debug(f"Prepared draft payload (excluding content): { {k:v for k,v in draft_payload.items() if k != 'content'} }")

        # 5. Idempotency Check
        existing_draft_media_id: Optional[str] = None
        if check_existing:
            try:
                log.info(f"Checking for existing draft with title: '{article.title}'")
                existing_draft_media_id = self.wechat_client.find_draft_by_title(article.title)
                if existing_draft_media_id:
                    log.info(f"Found existing draft with media_id: {existing_draft_media_id}")
                else:
                    log.info("No existing draft found with this title.")
            except Exception as e:
                log.warning(f"Failed to check for existing draft due to error: {e}. Will attempt to create a new draft.")

        # 6. Save Draft to WeChat
        draft_media_id: Optional[str] = None
        try:
            if existing_draft_media_id:
                log.info(f"Attempting to update existing draft {existing_draft_media_id}.")
                success = self.wechat_client.update_draft(
                    draft_media_id=existing_draft_media_id,
                    article_index=0,
                    article_data=draft_payload
                )
                if success:
                    log.info(f"Successfully updated draft {existing_draft_media_id}.")
                    draft_media_id = existing_draft_media_id
                else:
                    log.error(f"Failed to update existing draft {existing_draft_media_id}. Check WeChatClient logs for details.")
                    return None
            else:
                log.info("Attempting to create new draft.")
                draft_media_id = self.wechat_client.add_draft(draft_payload)
                if draft_media_id:
                     log.info(f"Successfully created new draft with media_id: {draft_media_id}")
                else:
                     log.error(f"Failed to create new draft for '{article.title}'. Check WeChatClient logs for details.")
                     return None

        except Exception as e:
            log.exception(f"An unexpected error occurred during draft creation/update for '{article.title}': {e}")
            return None

        # 7. Logging Final Status
        log.info(f"--- Draft Publication Summary for '{article.title}' ---")
        log.info(f"  Operation Status: {'Updated' if existing_draft_media_id and draft_media_id else 'Created'}")
        log.info(f"  Draft Media ID: {draft_media_id}")
        log.info(f"  Title: {draft_payload['title']}")
        log.info(f"  Author: {draft_payload['author']}")
        log.info(f"  Cover Media ID: {draft_payload['thumb_media_id']}")
        log.info(f"  Summary Provided: {'Yes' if draft_payload['digest'] else 'No'}")
        log.info(f"  Originality Marked: {settings.MARK_AS_ORIGINAL}")
        log.info(f"  Comments Enabled: {bool(draft_payload['need_open_comment'])}")
        log.info("-----------------------------------------------------")

        return draft_media_id


    def _assemble_html_content(self, article: Article) -> Optional[str]:
        """
        Takes the base HTML content from the first ContentElement and replaces
        media placeholders with actual WeChat image URLs. Wraps content in a
        basic HTML structure.

        Args:
            article (Article): The article object containing ContentElements and
                               uploaded media details in placeholders.

        Returns:
            Optional[str]: The final HTML string ready for WeChat, or None on error.
        """
        if not article.content_elements or not hasattr(article.content_elements[0], 'content') or not article.content_elements[0].content:
            log.error("Cannot assemble HTML: No base content found in the first content element of the article.")
            return None
        current_html = article.content_elements[0].content

        log.debug("Starting HTML media placeholder replacement...")

        # Use a function for the replacement logic in re.sub
        def replace_placeholder(match):
            # Group 1: <img...src=
            img_tag_start_before_quote = match.group(1)
            # Group 2: The quote character (" or ')
            quote = match.group(2)
            # Group 3: The placeholder ID
            placeholder_id = match.group(3)
            # *** CORRECTED SECTION ***
            # Group 4: The rest of the tag (after the closing quote of src)
            img_tag_end_after_quote = match.group(4)
            # *** END CORRECTION ***

            placeholder = article.get_placeholder_by_id(placeholder_id)
            if placeholder and placeholder.uploaded_url:
                log.debug(f"Replacing placeholder '{placeholder_id}' with URL: {placeholder.uploaded_url}")
                # Reconstruct the tag correctly: G1 + G2 + url + G2 + G4
                return f'{img_tag_start_before_quote}{quote}{placeholder.uploaded_url}{quote}{img_tag_end_after_quote}'
            else:
                log.warning(f"Could not find uploaded URL for placeholder ID '{placeholder_id}' referenced in HTML. Removing corresponding img tag.")
                return "" # Return empty string to remove the tag

        # Perform the replacement using the corrected regex and replacement function
        final_content_html = HTML_PLACEHOLDER_SRC_RE.sub(replace_placeholder, current_html)

        # Wrap in full HTML structure
        try:
            # Optional: Load CSS styles here if needed
            pass
        except Exception as e:
            log.warning(f"Could not load or embed CSS styles: {e}")

        full_html = HTML_WRAPPER_TEMPLATE.format(title=article.title, content=final_content_html)

        log.info("Successfully assembled final HTML content.")
        log.debug(f"Final HTML (first 500 chars): {full_html[:500]}...")
        return full_html