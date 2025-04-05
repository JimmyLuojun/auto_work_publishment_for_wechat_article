# /Users/junluo/Documents/auto_work_publishment_for_wechat_article/src/core/article_model.py

"""
Article Data Model Module

Purpose:
Defines data structures (classes) to represent a parsed article
in a structured way, separating content from presentation concerns.

Dependencies:
- dataclasses (standard Python library)
- typing (standard Python library)

Expected Input: Data extracted from Markdown parsing.
Expected Output: Instances of Article and potentially related data classes.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class MediaPlaceholder:
    """Represents a placeholder for media found in the Markdown."""
    original_tag: str  # e.g., ![alt text](placeholder:image_name.jpg)
    placeholder_id: str # e.g., image_name.jpg (used for mapping to actual files/uploads)
    media_type: str = "image" # Could be 'image', 'video', etc.
    alt_text: str = ""
    # Store associated file path if known during parsing (for pre-prepared media)
    file_path: Optional[str] = None
    # Store uploaded media ID and URL after processing
    uploaded_media_id: Optional[str] = None
    uploaded_url: Optional[str] = None # Permanent media URL from WeChat

@dataclass
class ContentElement:
    """Represents a block of content (paragraph, header, list, etc.)."""
    # Using a generic structure for simplicity. Could be more specific (e.g., HeaderElement, ParagraphElement).
    type: str # e.g., 'h1', 'h2', 'p', 'ul', 'ol', 'blockquote', 'code', 'html'
    content: Any # str for text, List[str] for list items, List[ContentElement] for nested structures?
    # Or, store pre-rendered HTML segment directly if easier for templating
    html_content: Optional[str] = None

@dataclass
class Article:
    """
    Represents the structured data of an article parsed from Markdown.
    """
    title: str
    # List of content elements in order
    content_elements: List[ContentElement] = field(default_factory=list)
    # List of identified media placeholders
    media_placeholders: List[MediaPlaceholder] = field(default_factory=list)
    # Optional: Store raw Markdown content if needed later
    raw_markdown: Optional[str] = None
    # Optional: Store fully rendered HTML after processing (might be better handled in Publisher)
    final_html_content: Optional[str] = None
    # Optional: Store metadata extracted from frontmatter or inferred
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Store the generated summary
    summary: Optional[str] = None
    # Store the cover image details (placeholder or actual file)
    cover_image_placeholder: Optional[MediaPlaceholder] = None
    cover_image_file_path: Optional[str] = None # For pre-prepared cover

    def get_placeholder_by_id(self, placeholder_id: str) -> Optional[MediaPlaceholder]:
        """Finds a media placeholder by its unique ID."""
        for p in self.media_placeholders:
            if p.placeholder_id == placeholder_id:
                return p
        # Also check cover image placeholder
        if self.cover_image_placeholder and self.cover_image_placeholder.placeholder_id == placeholder_id:
             return self.cover_image_placeholder
        return None

    def get_content_as_text(self) -> str:
        """
        Provides a simple text representation of the article content,
        useful for feeding into summary generation. Strips HTML/Markdown.
        This is a basic implementation.
        """
        text_parts = []
        for element in self.content_elements:
            if element.type.startswith('h'):
                text_parts.append(str(element.content))
            elif element.type == 'p':
                 text_parts.append(str(element.content))
            elif element.type in ['ul', 'ol']:
                 if isinstance(element.content, list):
                     text_parts.extend([f"- {item}" for item in element.content])
            elif isinstance(element.content, str): # Fallback for simple string content
                 text_parts.append(element.content)
            # Add more sophisticated stripping logic if needed (e.g., remove code blocks)

        full_text = "\n".join(text_parts)
        # Basic cleanup (replace multiple newlines/spaces) - needs refinement
        full_text = "\n".join(line.strip() for line in full_text.splitlines() if line.strip())
        return full_text