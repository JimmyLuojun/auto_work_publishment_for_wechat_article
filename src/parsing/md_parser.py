# /Users/junluo/Documents/auto_work_publishment_for_wechat_article/src/parsing/md_parser.py

"""
Refined Markdown Parsing Module with Frontmatter Support

Purpose:
Reads a Markdown file, parses YAML frontmatter for metadata (title, cover image, etc.),
parses the Markdown content into HTML, identifies both custom `placeholder:` tags
and standard Markdown image links as media placeholders, and populates a comprehensive
Article data model.

Dependencies:
- frontmatter (external library)
- markdown (external library) - Potentially with extensions
- re (standard Python library)
- typing (standard Python library)
- pathlib (standard Python library)
- src.core.article_model
- src.core.settings
- src.utils.logger

Expected Input: Path to a Markdown file, potentially containing YAML frontmatter.
Expected Output: An instance of the Article data model populated with metadata and content.
"""

import re
import markdown
import frontmatter # For parsing YAML frontmatter
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from src.core.article_model import Article, ContentElement, MediaPlaceholder
from src.core import settings # Need settings for INPUT_DIR comparison
from src.utils.logger import log

# Regex to find the first H1 header (fallback title)
TITLE_RE = re.compile(r"^\s*#\s+(.+)\s*$", re.MULTILINE)

# Regex to find custom media placeholders like ![alt](placeholder:id)
CUSTOM_MEDIA_PLACEHOLDER_RE = re.compile(r'!\[(.*?)\]\(placeholder:(.*?)\)')

# Regex to find standard Markdown image links: ![alt text](path/to/image.ext)
# It should *not* match the custom placeholders.
STANDARD_IMAGE_RE = re.compile(r'!\[(?P<alt>.*?)\]\((?P<path>(?!placeholder:).*?)\)')

# Allowed image/video extensions (for simple type detection)
MEDIA_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', # images
                    '.mp4', '.mov', '.avi', '.wmv', '.mkv'} # videos (add more as needed)

class MarkdownParser:
    """Parses Markdown files with frontmatter into a structured Article object."""

    def __init__(self, extensions: List[str] = None):
        """
        Initializes the Markdown parser.

        Args:
            extensions (List[str]): List of python-markdown extensions to use.
                                    Defaults to ['extra', 'fenced_code', 'tables', 'sane_lists'].
                                    Consider making this configurable via settings.py.
        """
        self.extensions = extensions if extensions else ['extra', 'fenced_code', 'tables', 'sane_lists']
        log.info(f"MarkdownParser initialized with extensions: {self.extensions}")

    def parse_file(self, file_path: Path) -> Optional[Article]:
        """
        Parses a single Markdown file, including YAML frontmatter.

        Args:
            file_path (Path): The path to the Markdown file.

        Returns:
            Optional[Article]: An Article object if parsing is successful, None otherwise.
        """
        if not file_path.is_file():
            log.error(f"Markdown input file not found or is not a file: {file_path}")
            return None

        log.info(f"Starting parsing of Markdown file: {file_path}")
        try:
            # Load the file, separating frontmatter (metadata) and content
            post = frontmatter.load(file_path, encoding='utf-8')
            metadata: Dict[str, Any] = post.metadata
            raw_content: str = post.content
            log.debug(f"Successfully loaded frontmatter. Metadata keys: {list(metadata.keys())}")
        except Exception as e:
            log.error(f"Error reading or parsing frontmatter/content from {file_path}: {e}")
            return None

        # --- Extract Metadata ---
        # Prioritize frontmatter, then H1, then filename for title
        title = metadata.get('title')
        if not title:
            title = self._extract_h1_title(raw_content)
            if title:
                log.info("Using H1 header as title (no 'title' in frontmatter).")
            else:
                title = file_path.stem  # Fallback to filename
                log.warning(f"No 'title' in frontmatter or H1 found. Using filename as title: '{title}'")

        # Extract other relevant metadata
        author = metadata.get('author')  # Get author from frontmatter, fallback if missing
        if not author:
            author = settings.ARTICLE_AUTHOR  # If author is missing, fallback to settings' default author

        custom_meta = {k: v for k, v in metadata.items() if k not in ['title', 'author', 'cover_image', 'cover_image_path']}  # Store other metadata

        # --- Identify Cover Image (from Frontmatter) ---
        cover_image_placeholder_id = metadata.get('cover_image')  # Expects a placeholder ID
        cover_image_path_str = metadata.get('cover_image_path')  # Expects a relative path string
        article_cover_placeholder: Optional[MediaPlaceholder] = None
        article_cover_path: Optional[str] = None  # Store relative path string

        if cover_image_placeholder_id:
            log.info(f"Identified cover image via frontmatter 'cover_image' placeholder ID: '{cover_image_placeholder_id}'")
            # Create a placeholder object; the uploader will find the actual file
            article_cover_placeholder = MediaPlaceholder(
                original_tag=f"frontmatter:cover_image:{cover_image_placeholder_id}",
                placeholder_id=cover_image_placeholder_id,
                media_type="thumb",  # Assume thumb for cover
                alt_text="Cover Image"
            )
        elif cover_image_path_str:
            log.info(f"Identified cover image via frontmatter 'cover_image_path': '{cover_image_path_str}'")
            # Store the path; uploader will resolve and use it
            article_cover_path = cover_image_path_str
            # Optionally create a placeholder too, using filename as ID?
            cover_filename = Path(cover_image_path_str).name
            article_cover_placeholder = MediaPlaceholder(
                original_tag=f"frontmatter:cover_image_path:{cover_image_path_str}",
                placeholder_id=cover_filename,  # Use filename as ID
                media_type="thumb",
                alt_text="Cover Image",
                file_path=article_cover_path  # Store relative path here
            )
        else:
            log.warning(f"No 'cover_image' (placeholder ID) or 'cover_image_path' found in frontmatter for {file_path.name}. Cover image must be handled manually or by convention in uploader.")

        # --- Identify Media Placeholders in Content ---
        # Combine custom placeholders and standard Markdown images found
        media_placeholders = self._extract_media_placeholders(raw_content, file_path.parent)

        # --- Convert Markdown Content to HTML ---
        try:
            html_content = markdown.markdown(raw_content, extensions=self.extensions)
            log.debug(f"Markdown content converted to HTML for {file_path.name}")
        except Exception as e:
            log.error(f"Error converting Markdown content to HTML for {file_path.name}: {e}")
            return None  # Cannot proceed without HTML content

        # --- Create Article Object ---
        content_elements = [ContentElement(type='html', content=None, html_content=html_content)]
        article = Article(
            title=title,
            content_elements=content_elements,
            media_placeholders=media_placeholders,
            raw_markdown=raw_content,  # Keep raw MD content if needed
            metadata={**custom_meta, 'author': author},  # Combine custom meta with author
            cover_image_placeholder=article_cover_placeholder,
            cover_image_file_path=article_cover_path  # This is the *relative* path string from frontmatter
        )

        log.info(f"Successfully parsed Markdown file: '{file_path.name}'. Title: '{article.title}'. Found {len(media_placeholders)} content media references.")
        return article

    def _extract_h1_title(self, text: str) -> Optional[str]:
        """Extracts the first H1 header as the title."""
        match = TITLE_RE.search(text)
        if match:
            title = match.group(1).strip()
            log.debug(f"Extracted H1 title: '{title}'")
            return title
        return None

    def _get_media_type_from_path(self, path_str: str) -> str:
         """Determines media type (image/video) based on file extension."""
         ext = Path(path_str).suffix.lower()
         if ext in MEDIA_EXTENSIONS:
             # Basic check, could be refined (e.g., differentiate thumb/image if needed)
             return "video" if any(path_str.lower().endswith(vidext) for vidext in ['.mp4', '.mov', '.avi']) else "image"
         return "image" # Default to image if extension unknown/missing

    def _extract_media_placeholders(self, text: str, base_dir: Path) -> List[MediaPlaceholder]:
        """
        Finds all media placeholders in the text, including custom `placeholder:` syntax
        and standard Markdown image/video links pointing to relative paths.

        Args:
            text (str): The Markdown content string.
            base_dir (Path): The directory containing the Markdown file, used for
                             resolving relative paths.

        Returns:
            List[MediaPlaceholder]: A list of identified media placeholders.
        """
        placeholders = []
        found_ids_or_paths = set()  # Track both IDs and resolved paths to avoid duplicates

        # 1. Find custom ![alt](placeholder:id) tags
        for match in CUSTOM_MEDIA_PLACEHOLDER_RE.finditer(text):
            original_tag = match.group(0)
            alt_text = match.group(1).strip()
            placeholder_id = match.group(2).strip()

            if not placeholder_id:
                log.warning(f"Found custom placeholder with empty ID: {original_tag}. Skipping.")
                continue

            if placeholder_id in found_ids_or_paths:
                log.warning(f"Duplicate media placeholder ID found: '{placeholder_id}'. Skipping subsequent occurrences.")
                continue

            media_type = self._get_media_type_from_path(placeholder_id)  # Infer from ID extension

            placeholder = MediaPlaceholder(
                original_tag=original_tag,
                placeholder_id=placeholder_id,
                alt_text=alt_text,
                media_type=media_type,
                file_path=None  # Path needs to be found by uploader based on ID
            )
            placeholders.append(placeholder)
            found_ids_or_paths.add(placeholder_id)
            log.debug(f"Found custom media placeholder: ID='{placeholder_id}', Type='{media_type}', Alt='{alt_text}'")

        # 2. Find standard ![alt](path/to/media.ext) tags
        for match in STANDARD_IMAGE_RE.finditer(text):
            original_tag = match.group(0)
            alt_text = match.group('alt').strip()
            relative_path_str = match.group('path').strip()

            if not relative_path_str:
                log.warning(f"Found standard image tag with empty path: {original_tag}. Skipping.")
                continue

            # Resolve the relative path based on the Markdown file's location
            # Note: This assumes the path is relative to the MD file itself.
            # If paths are relative to INPUT_DIR, adjust base_dir accordingly.
            try:
                # Security: Prevent path traversal beyond input dir? Maybe not needed if trusted source.
                absolute_path = (base_dir / relative_path_str).resolve()
                # For consistency, store the *original* relative path found in the MD
                stored_path_str = relative_path_str
            except Exception as e:
                log.warning(f"Could not resolve path '{relative_path_str}' from tag {original_tag}: {e}. Skipping.")
                continue

            if stored_path_str in found_ids_or_paths:
                 log.warning(f"Duplicate media path found: '{stored_path_str}'. Skipping subsequent occurrences.")
                 continue

            # Use filename as the placeholder ID for standard links
            placeholder_id = Path(stored_path_str).name
            media_type = self._get_media_type_from_path(stored_path_str)

            # Optional: Check if the resolved path actually exists here?
            # if not absolute_path.is_file():
            #     log.warning(f"Standard media file reference points to non-existent file: '{absolute_path}' from tag {original_tag}. Still creating placeholder.")
            # We'll let the uploader handle the actual file existence check.

            placeholder = MediaPlaceholder(
                original_tag=original_tag,
                placeholder_id=placeholder_id,  # Use filename as ID
                alt_text=alt_text,
                media_type=media_type,
                file_path=stored_path_str  # Store the ORIGINAL relative path string
            )
            placeholders.append(placeholder)
            found_ids_or_paths.add(stored_path_str)
            log.debug(f"Found standard media reference: Path='{stored_path_str}', ID='{placeholder_id}', Type='{media_type}', Alt='{alt_text}'")

        return placeholders


# Example Usage (demonstration - assuming settings.py exists)
if __name__ == '__main__':
    # Create dummy files and directories for testing
    dummy_dir = Path("./temp_parser_test")
    dummy_dir.mkdir(exist_ok=True)
    (dummy_dir / "images").mkdir(exist_ok=True)

    dummy_md_content = """---
title: My Awesome Article Title
author: Test Author
cover_image: cover_placeholder.jpg
# cover_image_path: cover/my_cover.png # Alternative way to specify cover
custom_field: some_value
---

# This H1 will be ignored if title exists in frontmatter

This is the first paragraph.

![Custom placeholder img](placeholder:content_img_1.png)

Here is a standard image link:
![Standard cat image](./images/cat.gif)

Another paragraph.

![Another custom one](placeholder:video1.mp4)

![Duplicate standard path](./images/cat.gif)
![Duplicate placeholder ID](placeholder:content_img_1.png)

End.
"""
    test_file = dummy_dir / "test_article.md"
    test_file.write_text(dummy_md_content, encoding='utf-8')
    (dummy_dir / "images" / "cat.gif").touch() # Create dummy image file

    # Mock settings needed for the example run
    class MockSettings:
        ARTICLE_AUTHOR = "Default Config Author"
        INPUT_DIR = dummy_dir # Make paths relative to test dir

    # Replace actual settings import for example run - IN REAL CODE, USE ACTUAL IMPORT
    import sys
    sys.modules['src.core.settings'] = MockSettings

    parser = MarkdownParser()
    parsed_article = parser.parse_file(test_file)

    if parsed_article:
        print(f"\n--- Parsed Article ---")
        print(f"Title: {parsed_article.title}")
        print(f"Metadata: {parsed_article.metadata}")
        print(f"Cover Placeholder ID: {parsed_article.cover_image_placeholder.placeholder_id if parsed_article.cover_image_placeholder else 'None'}")
        print(f"Cover File Path (relative): {parsed_article.cover_image_file_path if parsed_article.cover_image_file_path else 'None'}")

        print(f"\nContent Media Placeholders ({len(parsed_article.media_placeholders)}):")
        for p in parsed_article.media_placeholders:
            print(f"- ID: {p.placeholder_id:<20} Type: {p.media_type:<7} Path: {p.file_path:<20} Alt: {p.alt_text:<20} Tag: {p.original_tag}")

        print(f"\nHTML Content (first 200 chars):\n{parsed_article.content_elements[0].html_content[:200]}...")

    # Clean up
    import shutil
    shutil.rmtree(dummy_dir)