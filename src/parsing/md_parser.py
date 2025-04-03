# -*- coding: utf-8 -*-
"""
md_parser.py - Parses Markdown files into Article objects.

Responsibilities:
- Read content from a given Markdown file path.
- Parse the Markdown syntax using a suitable library.
- Extract title, content blocks (paragraphs, headings, images, code),
  and potentially frontmatter metadata.
- Construct and return an Article object (defined in src.core.article_model).

Dependencies:
- os: For path manipulation (finding images relative to the markdown file).
- logging: For logging parsing process and errors.
- markdown_it: Recommended Markdown parsing library (or 'markdown').
- src.core.article_model: Defines the Article and ContentBlock structures.
- typing: For type hints.

Expected Input:
- file_path (str): Path to the input Markdown file.

Expected Output:
- Article: An instance of the Article class populated with parsed content.
"""

import logging
import os
from typing import List, Optional, Tuple

# Recommended: Use markdown-it-py for better control and features
from markdown_it import MarkdownIt
from markdown_it.token import Token
# from markdown_it.utils import read_normalize_str # Helper for reading file

# Alternative (simpler, less features):
# import markdown

from src.core.article_model import (Article, ContentBlock, Heading, ImagePlaceholder,
                                    Paragraph, CodeBlock, VideoPlaceholder, UnparsedBlock) # Add others as needed

logger = logging.getLogger(__name__)

class MarkdownParser:
    """Parses Markdown files into structured Article objects."""

    def __init__(self):
        """Initializes the Markdown parser."""
        # Configure markdown-it parser
        # Enable desired features. 'linkify=True' automatically finds URLs.
        # 'typographer=True' enables smart quotes, etc.
        self.md = (
            MarkdownIt('commonmark', {'breaks': True, 'html': False, 'linkify': True})
            # .enable('table') # Enable tables if needed
            .enable('strikethrough')
            # Add plugins here if needed, e.g., for frontmatter
        )
        # Note: Handling frontmatter usually requires a plugin or separate parsing step before this.
        logger.info("Markdown parser initialized (using markdown-it-py).")

    def _get_absolute_media_path(self, media_path: str, md_file_dir: str) -> str:
        """
        Resolves the absolute path for a media file referenced in Markdown.

        Args:
            media_path (str): The path as written in the Markdown (e.g., "images/pic.jpg").
            md_file_dir (str): The directory containing the Markdown file.

        Returns:
            str: The absolute path to the media file.
        """
        if os.path.isabs(media_path):
            return media_path
        # Simple check for web URLs (skip path joining)
        if media_path.startswith(('http://', 'https://')):
            return media_path
        # Assume relative path from the Markdown file's directory
        return os.path.abspath(os.path.join(md_file_dir, media_path))


    def parse_file(self, file_path: str) -> Article:
        """
        Parses the Markdown file at the given path.

        Args:
            file_path (str): The absolute or relative path to the Markdown file.

        Returns:
            Article: The structured Article object.

        Raises:
            FileNotFoundError: If the markdown file does not exist.
            Exception: For general parsing errors.
        """
        logger.info(f"Starting parsing of Markdown file: {file_path}")
        if not os.path.exists(file_path):
            logger.error(f"Markdown file not found: {file_path}")
            raise FileNotFoundError(f"Markdown file not found: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Error reading Markdown file {file_path}: {e}", exc_info=True)
            raise

        try:
            # --- Optional: Frontmatter Parsing ---
            # Use a library like 'python-frontmatter' here before parsing Markdown
            # import frontmatter
            # post = frontmatter.load(file_path)
            # content = post.content
            # metadata = post.metadata # Store this in Article.metadata
            # logger.info(f"Parsed frontmatter metadata: {metadata}")
            metadata = {} # Placeholder

            # --- Markdown Parsing ---
            tokens: List[Token] = self.md.parse(content)
            # logger.debug(f"Markdown Tokens: {[t.type for t in tokens]}") # For debugging

            article_title = "Untitled Article" # Default title
            content_blocks: List[ContentBlock] = []
            md_file_dir = os.path.dirname(file_path)

            # --- Token Processing Logic ---
            # This requires careful handling based on markdown-it's token stream.
            # It's more complex than simple regex but more robust.
            i = 0
            first_heading_found = False
            while i < len(tokens):
                token = tokens[i]
                # logger.debug(f"Processing token: {token.type} (Level: {token.level}, Tag: {token.tag}, Content: '{token.content}')")

                if token.type == 'heading_open':
                    level = int(token.tag[1])
                    inline_token = tokens[i+1] # Should be inline content
                    if inline_token.type == 'inline' and inline_token.children:
                        heading_text = inline_token.content.strip()
                        if not first_heading_found:
                            article_title = heading_text
                            first_heading_found = True
                            logger.debug(f"Extracted title (H{level}): {article_title}")
                        else:
                            content_blocks.append(Heading(level=level, text=heading_text))
                            logger.debug(f"Added Heading block (H{level}): {heading_text}")
                    i += 3 # Skip heading_open, inline, heading_close
                    continue

                elif token.type == 'paragraph_open':
                    inline_token = tokens[i+1]
                    if inline_token.type == 'inline':
                        # Handle images within paragraphs separately
                        if inline_token.children and any(t.type == 'image' for t in inline_token.children):
                             for child_token in inline_token.children:
                                 if child_token.type == 'image':
                                     alt_text = child_token.content
                                     src = child_token.attrs.get('src', '')
                                     if src:
                                         abs_path = self._get_absolute_media_path(src, md_file_dir)
                                         # Simple check for video extensions
                                         if any(src.lower().endswith(ext) for ext in ['.mp4', '.mov', '.avi']):
                                             content_blocks.append(VideoPlaceholder(local_path=abs_path))
                                             logger.debug(f"Added VideoPlaceholder block: {abs_path}")
                                         else:
                                             content_blocks.append(ImagePlaceholder(alt_text=alt_text, local_path=abs_path))
                                             logger.debug(f"Added ImagePlaceholder block: {abs_path} (Alt: {alt_text})")
                                     else:
                                         logger.warning(f"Image tag found with no src: {child_token}")
                                 elif child_token.content.strip(): # Add text between/around images as paragraphs
                                    # This might split paragraphs unnaturally if text is complexly interleaved.
                                    # A more sophisticated approach might group inline elements better.
                                    para_text = child_token.content.strip()
                                    content_blocks.append(Paragraph(text=para_text))
                                    logger.debug(f"Added inline Paragraph block: {para_text[:50]}...")

                        elif inline_token.content.strip(): # Regular paragraph text
                            para_text = inline_token.content.strip()
                            content_blocks.append(Paragraph(text=para_text))
                            logger.debug(f"Added Paragraph block: {para_text[:50]}...")
                    i += 3 # Skip paragraph_open, inline, paragraph_close
                    continue

                elif token.type == 'fence': # Code blocks (```)
                    lang = token.info.strip() if token.info else None
                    code = token.content.strip()
                    content_blocks.append(CodeBlock(language=lang, code=code))
                    logger.debug(f"Added Code block (lang: {lang}): {code[:50]}...")
                    i += 1
                    continue

                # Add handlers for other block types: lists, blockquotes, tables etc.
                # elif token.type == 'bullet_list_open': ...
                # elif token.type == 'blockquote_open': ...

                else:
                    # Optional: Capture unhandled blocks if needed
                    # if token.content.strip():
                    #    content_blocks.append(UnparsedBlock(raw_content=token.content))
                    # logger.debug(f"Unhandled token type: {token.type}")
                    i += 1 # Move to the next token

            # --- Create Article Object ---
            article = Article(
                title=article_title,
                content_blocks=content_blocks,
                source_path=os.path.abspath(file_path),
                metadata=metadata # Add parsed frontmatter here
            )
            logger.info(f"Successfully parsed Markdown. Title: '{article.title}'. Blocks found: {len(content_blocks)}")
            return article

        except Exception as e:
            logger.error(f"Failed to parse Markdown file {file_path}: {e}", exc_info=True)
            # Re-raise or return a default/empty Article object depending on desired behavior
            raise


# --- Explanation ---
# Purpose: Converts raw Markdown text into a structured `Article` object using the
#          definitions from `article_model.py`.
# Design Choices:
# - Uses `markdown-it-py` (recommended) which provides a token stream. Processing
#   tokens is more complex than regex but handles nested structures and edge cases
#   more reliably. A simpler `markdown` library could be used initially but might
#   struggle with complex content or identifying blocks cleanly.
# - Defines a `MarkdownParser` class to encapsulate parsing logic.
# - Includes a helper `_get_absolute_media_path` to resolve relative image/video paths
#   correctly based on the Markdown file's location. It also handles web URLs.
# - Iterates through the token stream, identifying headings, paragraphs, images,
#   code blocks, etc., and mapping them to the corresponding `ContentBlock` objects.
# - Extracts the first H1 heading as the article title.
# - Populates the `Article` object and returns it.
# - Includes basic error handling for file reading and parsing.
# - Placeholder logic for handling videos based on file extension (could be improved).
# Improvements/Alternatives:
# - **Robustness:** The token processing logic needs refinement to handle all edge cases,
#   nested elements (like images inside links), lists, blockquotes, tables, etc.
#   This is the most complex part of this module.
# - **Frontmatter:** Integrate a library like `python-frontmatter` to parse metadata
#   at the beginning of the file (e.g., title, author, custom tags).
# - **Library Choice:** Evaluate different Markdown libraries (`mistune`, `commonmark`)
#   based on specific needs for syntax support and ease of extracting structured data.
# - **Video Handling:** Use a more reliable way to distinguish videos (e.g., specific
#   Markdown syntax like `![video](path.mp4)` or frontmatter flags).