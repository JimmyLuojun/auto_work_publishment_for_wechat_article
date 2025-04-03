# -*- coding: utf-8 -*-
"""
formatter.py - Formats Article objects into WeChat-compatible HTML.

Responsibilities:
- Take a structured Article object (containing ContentBlocks).
- Convert each ContentBlock into its corresponding HTML representation suitable
  for the WeChat Official Account editor.
- Replace media placeholders (ImagePlaceholder, VideoPlaceholder) with HTML tags
  that correctly reference the WeChat media_id (or constructed URL).
- Optionally apply basic styling (e.g., from a CSS template file).

Dependencies:
- logging: For logging formatting process.
- html: For basic HTML escaping.
- src.core.article_model: Defines Article and ContentBlock structures.
- typing: For type hints.

Expected Input:
- article (Article): The Article object, potentially with media_ids populated.
- settings (Dict): Application settings (optional, for styling info).

Expected Output:
- str: A string containing the full HTML content for the WeChat editor body.
"""

import html
import logging
import os
from typing import TYPE_CHECKING, List, Optional, Dict, Any

# Use TYPE_CHECKING to avoid circular imports if needed, although unlikely here
if TYPE_CHECKING:
    from src.core.article_model import (Article, ContentBlock, Paragraph, Heading,
                                       ImagePlaceholder, VideoPlaceholder, CodeBlock,
                                       UnparsedBlock)

logger = logging.getLogger(__name__)

# Assumes formatter.py is in src/platforms/wechat/
SRC_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_TEMPLATE_PATH = os.path.join(SRC_ROOT, 'templates', 'wechat_style.css')

class WeChatFormatter:
    """Formats an Article object into WeChat-compatible HTML."""

    def __init__(self, settings: Dict[str, Any]):
        """
        Initializes the formatter.

        Args:
            settings (Dict[str, Any]): Application settings, potentially containing
                                       paths to CSS templates or styling options.
        """
        self.settings = settings
        self.css_styles: Optional[str] = self._load_css()

    def _load_css(self) -> Optional[str]:
        """Loads CSS styles from a template file specified in settings or default."""
        template_path = self.settings.get('platforms', {}).get('wechat', {}).get('css_template', DEFAULT_TEMPLATE_PATH)
        resolved_path = template_path
        if not os.path.isabs(template_path):
             # Assume relative to project root if not absolute
             project_root = os.path.dirname(os.path.dirname(SRC_ROOT))
             resolved_path = os.path.join(project_root, template_path)

        if os.path.exists(resolved_path):
            try:
                with open(resolved_path, 'r', encoding='utf-8') as f:
                    styles = f.read()
                    logger.info(f"Loaded CSS styles from: {resolved_path}")
                    return styles
            except Exception as e:
                logger.error(f"Error reading CSS template file {resolved_path}: {e}", exc_info=True)
                return None
        else:
            logger.warning(f"CSS template file not found at: {resolved_path}. Proceeding without custom styles.")
            return None

    def _format_paragraph(self, block: 'Paragraph') -> str:
        """Formats a Paragraph block into <p> HTML."""
        # Basic HTML escaping for text content
        escaped_text = html.escape(block.text)
        return f"<p>{escaped_text}</p>"

    def _format_heading(self, block: 'Heading') -> str:
        """Formats a Heading block into <hN> HTML."""
        escaped_text = html.escape(block.text)
        level = max(1, min(6, block.level)) # Ensure level is between 1 and 6
        return f"<h{level}>{escaped_text}</h{level}>"

    def _format_image(self, block: 'ImagePlaceholder') -> str:
        """Formats an ImagePlaceholder block into an <img> HTML tag."""
        if not block.wechat_media_id:
            logger.warning(f"Image block missing wechat_media_id for local path: {block.local_path}. Skipping.")
            # Return placeholder text or empty string
            alt_text = html.escape(block.alt_text or "Image placeholder")
            return f'<p style="color:red;">[Image upload failed or pending: {alt_text}]</p>'

        # IMPORTANT: Constructing the actual displayable URL for WeChat images
        # from a media_id is non-trivial and might not be directly possible
        # for temporary media used in drafts. The WeChat editor typically handles
        # resolving media_ids internally when the draft is saved or previewed.
        # A common workaround is to use a placeholder recognized by some editors
        # or to rely on the editor resolving the media_id itself.
        #
        # Approach 1: Use data-src attribute (Some editors might pick this up)
        # escaped_alt = html.escape(block.alt_text or '')
        # return f'<img data-src="weixin://resourceid/{block.wechat_media_id}" alt="{escaped_alt}" />'
        #
        # Approach 2: Use a format expected by specific tools (e.g., Markdown Nice)
        # return f'![{block.alt_text or ""}]({block.wechat_media_id})' # This is Markdown, not HTML!
        #
        # Approach 3: Rely on the draft API accepting media_ids and resolving them.
        # This is the most likely correct approach for the 'add_draft' content field.
        # However, generating a preview HTML that works requires knowing the CDN URL format,
        # which is typically for *permanent* media.
        #
        # Let's generate a simple img tag assuming the editor *might* handle it,
        # or acknowledging this preview HTML won't show the image directly.
        # For a *real* preview, you'd likely need permanent media + get_material call.

        logger.info(f"Formatting image with media_id: {block.wechat_media_id}")
        escaped_alt = html.escape(block.alt_text or '')
        # Placeholder src - unlikely to work directly in browser preview
        placeholder_src = f"WECHAT_MEDIA_ID_{block.wechat_media_id}"
        return f'<p><img src="{placeholder_src}" alt="{escaped_alt}" data-mediaid="{block.wechat_media_id}"/></p>'
        # Wrapping in <p> often helps with WeChat editor spacing

    def _format_video(self, block: 'VideoPlaceholder') -> str:
        """Formats a VideoPlaceholder block into HTML (likely needs WeChat editor handling)."""
        if not block.wechat_media_id:
            logger.warning(f"Video block missing wechat_media_id for local path: {block.local_path}. Skipping.")
            return '<p style="color:red;">[Video upload failed or pending]</p>'

        # Similar to images, embedding video via media_id in HTML for direct preview
        # is difficult. The 'add_draft' API should handle the media_id.
        # We generate a placeholder representation.
        logger.info(f"Formatting video with media_id: {block.wechat_media_id}")
        return f'<p>[WeChat Video Placeholder - Media ID: {block.wechat_media_id}]</p>'
        # Alternatively, use a <video> tag with a data attribute if aiming for a specific tool:
        # return f'<video src="WECHAT_MEDIA_ID_{block.wechat_media_id}" data-mediaid="{block.wechat_media_id}" controls></video>'


    def _format_codeblock(self, block: 'CodeBlock') -> str:
        """Formats a CodeBlock into <pre><code> HTML."""
        escaped_code = html.escape(block.code)
        lang_class = f"language-{block.language}" if block.language else ""
        # Basic pre/code structure. WeChat has limited support for syntax highlighting CSS.
        return f'<pre><code class="{lang_class}">\n{escaped_code}\n</code></pre>'

    def _format_unparsed(self, block: 'UnparsedBlock') -> str:
        """Formats an UnparsedBlock (e.g., log a warning and escape)."""
        logger.warning(f"Formatting unparsed block: {block.raw_content[:100]}...")
        escaped_content = html.escape(block.raw_content)
        return f"<p><em>[Unparsed content: {escaped_content}]</em></p>"


    def format_article(self, article: 'Article') -> str:
        """
        Converts the entire Article object into a single HTML string.

        Args:
            article (Article): The article object with content blocks, potentially
                               including wechat_media_ids on image/video blocks.

        Returns:
            str: The generated HTML content string.
        """
        logger.info(f"Starting HTML formatting for article: '{article.title}'")
        html_parts: List[str] = []

        # Add CSS styles if loaded
        if self.css_styles:
            html_parts.append(f"<style>\n{self.css_styles}\n</style>")
            logger.debug("Added CSS styles to HTML output.")

        # Process each content block
        for block in article.content_blocks:
            if isinstance(block, Paragraph):
                html_parts.append(self._format_paragraph(block))
            elif isinstance(block, Heading):
                html_parts.append(self._format_heading(block))
            elif isinstance(block, ImagePlaceholder):
                html_parts.append(self._format_image(block))
            elif isinstance(block, VideoPlaceholder):
                html_parts.append(self._format_video(block))
            elif isinstance(block, CodeBlock):
                html_parts.append(self._format_codeblock(block))
            elif isinstance(block, UnparsedBlock): # Handle potential fallback
                 html_parts.append(self._format_unparsed(block))
            else:
                logger.warning(f"Unsupported content block type encountered: {type(block)}. Skipping.")

        final_html = "\n".join(html_parts)
        logger.info(f"Finished HTML formatting for article: '{article.title}'. Length: {len(final_html)}")
        # logger.debug(f"Generated HTML sample: {final_html[:500]}...") # Log sample for debugging
        return final_html

    def save_preview(self, html_content: str, output_path: str):
         """
         Saves the generated HTML content to a local file for preview.

         Args:
             html_content (str): The HTML content generated by format_article.
             output_path (str): The file path to save the preview (e.g., data/output/preview.html).
         """
         try:
             # Ensure output directory exists
             output_dir = os.path.dirname(output_path)
             if output_dir and not os.path.exists(output_dir):
                 os.makedirs(output_dir)
                 logger.info(f"Created output directory: {output_dir}")

             with open(output_path, 'w', encoding='utf-8') as f:
                 f.write(html_content)
             logger.info(f"HTML preview saved to: {output_path}")

         except Exception as e:
             logger.error(f"Failed to save HTML preview to {output_path}: {e}", exc_info=True)


# --- Explanation ---
# Purpose: Translates the platform-agnostic `Article` object into HTML specifically
#          formatted and styled for pasting into the WeChat Official Account editor
#          via the API.
# Design Choices:
# - Uses a class `WeChatFormatter` to encapsulate formatting logic.
# - Implements separate private helper methods (`_format_paragraph`, `_format_heading`, etc.)
#   for each `ContentBlock` type. This promotes modularity and makes it easy to
#   adjust the HTML generation for specific block types.
# - Handles basic HTML escaping using `html.escape` to prevent XSS issues.
# - **Media Handling:** Acknowledges the difficulty of embedding temporary media directly
#   into previewable HTML. It generates placeholder `<img>` or `<p>` tags containing the
#   `media_id` (e.g., in a `data-mediaid` attribute), assuming the WeChat backend
#   will resolve these when the draft is created. *Generating a visually accurate
#   HTML preview with images/videos would require using permanent media uploads and
#   potentially additional API calls (`get_material`) to fetch usable URLs.*
# - Optionally loads and includes CSS from a template file (`templates/wechat_style.css`)
#   within `<style>` tags for basic styling consistency in the editor.
# - Provides a `save_preview` method for debugging and verification.
# Improvements/Alternatives:
# - **HTML Generation:** Use a dedicated HTML generation library (like `BeautifulSoup`
#   for modification or template engines like Jinja2) for more complex structures,
#   though simple string formatting is often sufficient here.
# - **CSS Styling:** Could implement more sophisticated CSS inlining if needed, as
#   WeChat editor support for external or complex CSS is limited. Libraries exist
#   for CSS inlining.
# - **Media Preview:** If accurate preview is essential, implement logic to upload
#   media as *permanent* material and use the `get_material` API call to retrieve
#   actual `url` fields to embed in the preview HTML's `src` attributes. This adds
#   complexity and uses permanent media quotas.
# - **Block Handling:** Add formatting logic for other `ContentBlock` types (Lists, Tables, etc.)
#   as they are added to the `article_model`.